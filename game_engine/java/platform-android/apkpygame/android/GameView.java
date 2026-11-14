package apkpygame.android;

import android.content.Context;
import android.graphics.Canvas;
import android.view.Choreographer;
import android.view.MotionEvent;
import android.view.View;

import apkpygame.core.Game;

/**
 * Drives a Game from the display: each vsync advances the fixed steps and
 * asks for a redraw; onDraw renders through the CanvasBackend.
 */
final class GameView extends View implements Choreographer.FrameCallback, GameSurface {
    final Game game;
    private final CanvasBackend backend;
    private final Failure failure;
    private boolean running;
    private long lastNanos;

    GameView(Context context, Game game, Failure failure) {
        super(context);
        this.game = game;
        this.backend = ((AndroidPlatform) game.platform).renderer;
        this.failure = failure;
        setFocusable(true);
    }

    @Override public Game game() {
        return game;
    }

    @Override public View view() {
        return this;
    }

    /** The Canvas view steps the game on the UI thread, where this is called from. */
    @Override public void onGameThread(Runnable task) {
        task.run();
    }

    @Override public void start() {
        if (running) return;
        running = true;
        lastNanos = 0;
        Choreographer.getInstance().postFrameCallback(this);
    }

    @Override public void stop() {
        running = false;
        Choreographer.getInstance().removeFrameCallback(this);
    }

    @Override protected void onDetachedFromWindow() {
        stop();
        super.onDetachedFromWindow();
    }

    @Override public void doFrame(long nanos) {
        if (!running) return;
        try {
            if (lastNanos != 0) game.advance((nanos - lastNanos) / 1e9);
        } catch (RuntimeException e) {
            stop();
            failure.failed(e);
            return;
        }
        lastNanos = nanos;
        invalidate();
        if (!game.isEnded()) Choreographer.getInstance().postFrameCallback(this);
    }

    @Override protected void onDraw(Canvas canvas) {
        try {
            backend.setCanvas(canvas);
            game.render(getWidth(), getHeight());
        } catch (RuntimeException e) {
            stop();
            failure.failed(e);
        }
    }

    @Override public boolean onTouchEvent(MotionEvent e) {
        return touch(game, e);
    }

    /** Touches (every finger) into the game's Input queue; shared with GlGameView. */
    static boolean touch(Game game, MotionEvent e) {
        int action = e.getActionMasked();
        switch (action) {
            case MotionEvent.ACTION_DOWN:
            case MotionEvent.ACTION_POINTER_DOWN: {
                int i = e.getActionIndex();
                game.input.pointerDown(e.getPointerId(i), e.getX(i), e.getY(i));
                break;
            }
            case MotionEvent.ACTION_MOVE:
                for (int i = 0; i < e.getPointerCount(); i++) {
                    game.input.pointerMove(e.getPointerId(i), e.getX(i), e.getY(i));
                }
                break;
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_POINTER_UP: {
                int i = e.getActionIndex();
                game.input.pointerUp(e.getPointerId(i), e.getX(i), e.getY(i));
                break;
            }
            case MotionEvent.ACTION_CANCEL:
                for (int i = 0; i < e.getPointerCount(); i++) {
                    game.input.pointerUp(e.getPointerId(i), e.getX(i), e.getY(i));
                }
                break;
            default:
                break;
        }
        return true;
    }
}
