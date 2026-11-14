package apkpygame.android;

import android.content.Context;
import android.opengl.GLSurfaceView;
import android.view.MotionEvent;
import android.view.View;

import apkpygame.core.Game;

import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

/**
 * Drives a Game with OpenGL ES 2.0: the GL thread advances the fixed steps
 * and draws through the GlesBackend, once per display frame. Touches and
 * keys go into the game's Input queue (thread-safe); Back and the end of the
 * game cross threads through onGameThread() and the activity's UI thread.
 */
final class GlGameView extends GLSurfaceView implements GLSurfaceView.Renderer, GameSurface {
    private final Game game;
    private final GlesBackend backend;
    private final Failure failure;
    private volatile boolean running;
    private boolean failed;
    private long lastNanos;
    private int width, height;

    GlGameView(Context context, Game game, GlesBackend backend, Failure failure) {
        super(context);
        this.game = game;
        this.backend = backend;
        this.failure = failure;
        setEGLContextClientVersion(2);
        setPreserveEGLContextOnPause(true);
        setRenderer(this);
        setRenderMode(RENDERMODE_CONTINUOUSLY);
        setFocusable(true);
    }

    @Override public Game game() {
        return game;
    }

    @Override public View view() {
        return this;
    }

    @Override public void start() {
        lastNanos = 0;
        running = true;
        onResume();
    }

    @Override public void stop() {
        running = false;
        onPause();
    }

    @Override public void onGameThread(Runnable task) {
        queueEvent(task);
    }

    // ── GL thread ────────────────────────────────────────────────────────

    @Override public void onSurfaceCreated(GL10 unused, EGLConfig config) {
        try {
            backend.contextCreated();           // first context, or a new one after the old was lost
        } catch (RuntimeException e) {
            fail(e);
        }
    }

    @Override public void onSurfaceChanged(GL10 unused, int w, int h) {
        width = w;
        height = h;
    }

    @Override public void onDrawFrame(GL10 unused) {
        if (failed) return;
        try {
            long now = System.nanoTime();
            if (running && lastNanos != 0 && !game.isEnded()) game.advance((now - lastNanos) / 1e9);
            lastNanos = running ? now : 0;
            game.render(width, height);
        } catch (RuntimeException e) {
            fail(e);
        }
    }

    private void fail(final RuntimeException e) {
        failed = true;
        post(new Runnable() {
            @Override public void run() {
                failure.failed(e);
            }
        });
    }

    @Override public boolean onTouchEvent(MotionEvent e) {
        return GameView.touch(game, e);
    }
}
