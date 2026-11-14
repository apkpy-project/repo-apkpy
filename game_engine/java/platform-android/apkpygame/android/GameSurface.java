package apkpygame.android;

import android.view.View;

import apkpygame.core.Game;

/**
 * Where a Game is drawn and stepped: GameView (Canvas, on the UI thread) or
 * GlGameView (OpenGL ES, on its GL thread). GameActivity talks to either.
 */
interface GameSurface {
    interface Failure {
        void failed(RuntimeException error);
    }

    Game game();

    View view();

    /** The activity is in front: step and draw. */
    void start();

    /** The activity went to the background: stop stepping. */
    void stop();

    /** Runs {@code task} on the thread that steps the game (Back must not race a step). */
    void onGameThread(Runnable task);
}
