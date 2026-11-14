package apkpygame.android;

import android.app.Activity;
import android.content.pm.ActivityInfo;
import android.os.Build;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;

import apkpygame.core.Game;
import apkpygame.core.GameHost;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * The full-screen home of a game. Declared in the engine AAR's manifest
 * (merged into the app), opened by {@link Host#play}; it answers once, through
 * {@link Host#finished}, when the game ends or the activity goes away.
 */
public class GameActivity extends Activity implements GameHost {
    static final String EXTRA_SCENE = "apkpygame.scene";
    static final String EXTRA_ARGS = "apkpygame.args";
    static final String EXTRA_RESUME = "apkpygame.resume";

    private GameSurface view;
    private boolean answered;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        Game game;
        try {
            boolean resume = getIntent().getBooleanExtra(EXTRA_RESUME, false);
            game = Host.takeSuspended(resume);
            String journal = resume && game == null ? Host.savedJournal(this) : null;
            if (journal != null) {
                game = Game.restore(new AndroidPlatform(this), journal);     // the process died meanwhile
                AndroidPlatform.LOGGER.info("suspended game brought back from its journal: " + game.stateHash());
            }
            if (game == null) {
                game = Game.load(new AndroidPlatform(this));
                game.start(getIntent().getStringExtra(EXTRA_SCENE), getIntent().getStringExtra(EXTRA_ARGS));
            } else {
                game.resumeAfterOpen();
            }
        } catch (RuntimeException e) {
            Host.forget(this);
            fail(e);
            return;
        }
        game.setHost(this);
        orientation(game.config.orientation);
        show(game, !"canvas".equals(game.config.renderer) && glesAvailable());
        immersive();
        if (Build.VERSION.SDK_INT >= 33) {
            // targetSdk 36 (what ApkPy generates): onBackPressed() is never called on Android 13+
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT,
                    new android.window.OnBackInvokedCallback() {
                        @Override public void onBackInvoked() {
                            back();
                        }
                    });
        }
    }

    /** The game in a GlGameView (OpenGL ES) or a GameView (Canvas). */
    private void show(final Game game, boolean gles) {
        AndroidPlatform platform = (AndroidPlatform) game.platform;
        if (gles) {
            if (platform.gles == null) platform.gles = new GlesBackend(platform.renderer);
            view = new GlGameView(this, game, platform.gles, new GameSurface.Failure() {
                @Override public void failed(RuntimeException error) {
                    // "auto": OpenGL ES did not start on this device (G3040): the same game, with the Canvas
                    if ("auto".equals(game.config.renderer) && error instanceof apkpygame.core.GameException
                            && "G3040".equals(((apkpygame.core.GameException) error).code)) {
                        AndroidPlatform.LOGGER.warn("OpenGL ES failed, drawing with the Canvas: " + error);
                        view.stop();
                        show(game, false);
                        view.start();
                    } else {
                        fail(error);
                    }
                }
            });
        } else {
            platform.gles = null;
            view = new GameView(this, game, new GameSurface.Failure() {
                @Override public void failed(RuntimeException error) {
                    fail(error);
                }
            });
        }
        setContentView(view.view());
        view.view().requestFocus();
    }

    private boolean glesAvailable() {
        android.app.ActivityManager am = (android.app.ActivityManager) getSystemService(ACTIVITY_SERVICE);
        return am != null && am.getDeviceConfigurationInfo().reqGlEsVersion >= 0x20000;
    }

    private void orientation(String o) {
        if ("landscape".equals(o)) setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE);
        else if ("any".equals(o)) setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_FULL_USER);
        else setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR_PORTRAIT);
    }

    @SuppressWarnings("deprecation")
    private void immersive() {
        if (Build.VERSION.SDK_INT >= 30) {
            WindowInsetsController c = getWindow().getInsetsController();
            if (c != null) {
                c.hide(WindowInsets.Type.systemBars());
                c.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        } else {
            getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    | View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN);
        }
    }

    @Override protected void onResume() {
        super.onResume();
        if (view != null) {
            view.game().platform.audio().resume();
            view.start();
        }
    }

    @Override protected void onPause() {
        if (view != null) {
            view.stop();
            view.game().platform.audio().pause();
        }
        super.onPause();
    }

    @Override protected void onDestroy() {
        if (!answered) {
            answer("{\"v\":1,\"action\":\"none\",\"reason\":\"destroyed\",\"suspended\":false}");
        }
        // a suspended game keeps its sounds loaded for game_resume()
        if (view != null && !Host.holds(view.game())) view.game().platform.audio().release();
        super.onDestroy();
    }

    @SuppressWarnings("deprecation")
    @Override public void onBackPressed() {
        back();     // Android 12 and older
    }

    private void back() {
        if (view == null) {
            finish();
            return;
        }
        final Game game = view.game();
        view.onGameThread(new Runnable() {
            @Override public void run() {
                game.back();       // the scene's on_back, or the end of the game (between two steps)
            }
        });
    }

    @Override public boolean onKeyDown(int keyCode, KeyEvent event) {
        String key = keyName(keyCode);
        if (key != null && view != null && event.getRepeatCount() == 0) {
            view.game().input.keyDown(key);
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override public boolean onKeyUp(int keyCode, KeyEvent event) {
        String key = keyName(keyCode);
        if (key != null && view != null) {
            view.game().input.keyUp(key);
            return true;
        }
        return super.onKeyUp(keyCode, event);
    }

    static String keyName(int code) {
        switch (code) {
            case KeyEvent.KEYCODE_DPAD_LEFT: return "left";
            case KeyEvent.KEYCODE_DPAD_RIGHT: return "right";
            case KeyEvent.KEYCODE_DPAD_UP: return "up";
            case KeyEvent.KEYCODE_DPAD_DOWN: return "down";
            case KeyEvent.KEYCODE_SPACE: return "space";
            case KeyEvent.KEYCODE_ENTER: return "enter";
            case KeyEvent.KEYCODE_BUTTON_A: return "space";
            default:
                if (code >= KeyEvent.KEYCODE_A && code <= KeyEvent.KEYCODE_Z) {
                    return String.valueOf((char) ('a' + code - KeyEvent.KEYCODE_A));
                }
                if (code >= KeyEvent.KEYCODE_0 && code <= KeyEvent.KEYCODE_9) {
                    return String.valueOf((char) ('0' + code - KeyEvent.KEYCODE_0));
                }
                return null;
        }
    }

    /** GameHost: the game ended (exit / openApp), on the thread that steps it; answered on the UI thread. */
    @Override public void ended(final String resultJson) {
        runOnUiThread(new Runnable() {
            @Override public void run() {
                if (resultJson.contains("\"suspended\":true") && view != null) Host.suspend(GameActivity.this, view.game());
                else Host.forget(GameActivity.this);
                answer(resultJson);
                finish();
            }
        });
    }

    private void fail(RuntimeException error) {
        AndroidPlatform.LOGGER.error("the game stopped", error);
        answer(Host.errorJson(error));
        finish();
    }

    private void answer(String json) {
        if (answered) return;
        answered = true;
        Host.finished(this, json);
    }
}
