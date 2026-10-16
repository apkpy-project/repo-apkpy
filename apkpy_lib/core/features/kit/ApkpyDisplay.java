package __PACKAGE__;

import android.app.Activity;
import android.app.Application;
import android.content.pm.ActivityInfo;
import android.os.Build;
import android.os.Bundle;
import android.os.Looper;
import android.os.SystemClock;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;

import java.util.HashMap;
import java.util.Map;
import java.util.WeakHashMap;

/**
 * display.* -- what the phone's screen does while one of the app's is on show.
 *
 * Staying on, the brightness and the bars are all things Android keeps for
 * one window, and every screen of an app is a window of its own. So what a
 * screen asks for holds while that screen is the one on show and for no
 * longer: a recipe that keeps the phone awake stops doing so when the person
 * goes on to another screen, with nothing for the app to undo.
 *
 * Android rebuilds a screen when the phone is turned or the theme changes,
 * and the window that replaces the old one starts with none of it. What the
 * screen had asked for is handed on to the copy that replaces it; closing the
 * screen ends it. Which way up a screen is, Android carries over by itself.
 */
public final class ApkpyDisplay {

    /** What one screen has asked for. */
    private static final class Asked {
        boolean keepOn;
        float brightness = WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE;
        boolean immersive;

        boolean nothing() {
            return !keepOn && !immersive && brightness < 0f;
        }
    }

    /** What a screen being rebuilt leaves for its replacement, and when. */
    private static final class Left {
        final Asked asked;
        final long at;

        Left(Asked asked, long at) {
            this.asked = asked;
            this.at = at;
        }
    }

    // A rebuilt screen is back within moments. Past this, what was left is
    // from a screen that never returned.
    private static final long HANDED_ON_FOR = 10000L;

    private static final Map<Activity, Asked> ASKED = new WeakHashMap<>();
    private static final Map<String, Left> HANDED_ON = new HashMap<>();
    private static boolean watching;

    private ApkpyDisplay() { }

    public static String keepOn(final Activity activity, String on) {
        final boolean wanted = ApkpyKitRules.truth(on);
        asked(activity).keepOn = wanted;
        onMain(activity, new Runnable() {
            @Override public void run() {
                awake(activity, wanted);
            }
        });
        return "ok";
    }

    public static String brightness(final Activity activity, String level) {
        double read = ApkpyKitRules.displayBrightness(level);
        if (read < -1.5) return "invalid";
        final float wanted = read < 0.0
                ? WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE : (float) read;
        asked(activity).brightness = wanted;
        onMain(activity, new Runnable() {
            @Override public void run() {
                bright(activity, wanted);
            }
        });
        return "ok";
    }

    public static String immersive(final Activity activity, String on) {
        final boolean wanted = ApkpyKitRules.truth(on);
        asked(activity).immersive = wanted;
        onMain(activity, new Runnable() {
            @Override public void run() {
                bars(activity, wanted);
            }
        });
        return "ok";
    }

    public static String orientation(final Activity activity, String kind) {
        String known = ApkpyKitRules.displayOrientation(kind);
        final int wanted;
        if ("portrait".equals(known)) {
            wanted = ActivityInfo.SCREEN_ORIENTATION_PORTRAIT;
        } else if ("landscape".equals(known)) {
            // Either way round: a phone lying on its other side is still lying down.
            wanted = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE;
        } else if ("auto".equals(known)) {
            wanted = ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED;
        } else {
            return "invalid";
        }
        onMain(activity, new Runnable() {
            @Override public void run() {
                activity.setRequestedOrientation(wanted);
            }
        });
        return "ok";
    }

    private static Asked asked(Activity activity) {
        watch(activity);
        synchronized (ASKED) {
            Asked mine = ASKED.get(activity);
            if (mine == null) {
                mine = new Asked();
                ASKED.put(activity, mine);
            }
            return mine;
        }
    }

    private static Asked had(Activity activity) {
        synchronized (ASKED) {
            return ASKED.get(activity);
        }
    }

    /** A window belongs to the thread that made it. */
    private static void onMain(Activity activity, Runnable work) {
        if (Looper.myLooper() == Looper.getMainLooper()) work.run();
        else activity.runOnUiThread(work);
    }

    private static void awake(Activity activity, boolean on) {
        Window window = activity.getWindow();
        if (window == null) return;
        if (on) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    private static void bright(Activity activity, float level) {
        Window window = activity.getWindow();
        if (window == null) return;
        WindowManager.LayoutParams attributes = window.getAttributes();
        attributes.screenBrightness = level;
        window.setAttributes(attributes);
    }

    /**
     * The status bar and the navigation bar, hidden or back. A window that has
     * drawn nothing yet has no bars to hide: the screen is asked again as it
     * comes on show.
     */
    @SuppressWarnings("deprecation")
    private static void bars(Activity activity, boolean hidden) {
        Window window = activity.getWindow();
        View decor = window == null ? null : window.peekDecorView();
        if (decor == null) return;
        if (Build.VERSION.SDK_INT >= 30) {
            WindowInsetsController controller = decor.getWindowInsetsController();
            if (controller == null) return;
            if (hidden) {
                controller.setSystemBarsBehavior(
                        WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
                controller.hide(WindowInsets.Type.systemBars());
            } else {
                controller.show(WindowInsets.Type.systemBars());
            }
            return;
        }
        int hiding = View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION;
        int flags = decor.getSystemUiVisibility();
        decor.setSystemUiVisibility(hidden ? flags | hiding : flags & ~hiding);
    }

    private static void watch(Activity activity) {
        synchronized (ASKED) {
            if (watching) return;
            Application application = activity.getApplication();
            if (application == null) return;
            application.registerActivityLifecycleCallbacks(WATCH);
            watching = true;
        }
    }

    private static final Application.ActivityLifecycleCallbacks WATCH =
            new Application.ActivityLifecycleCallbacks() {
        /**
         * Reached from inside the screen's own onCreate, before any of the
         * app's code for it: a screen that replaces one being rebuilt takes
         * what that one left, and what its on_mount asks for after that is
         * what it has.
         */
        @Override public void onActivityCreated(Activity activity, Bundle saved) {
            Left left;
            synchronized (ASKED) {
                left = HANDED_ON.remove(activity.getClass().getName());
                if (left == null || SystemClock.elapsedRealtime() - left.at > HANDED_ON_FOR) return;
                if (!ASKED.containsKey(activity)) ASKED.put(activity, left.asked);
            }
            awake(activity, left.asked.keepOn);
            bright(activity, left.asked.brightness);
        }

        @Override public void onActivityStarted(Activity activity) { }

        @Override public void onActivityResumed(Activity activity) {
            Asked mine = had(activity);
            if (mine != null && mine.immersive) bars(activity, true);
        }

        @Override public void onActivityPaused(Activity activity) { }

        @Override public void onActivityStopped(Activity activity) { }

        @Override public void onActivitySaveInstanceState(Activity activity, Bundle out) { }

        @Override public void onActivityDestroyed(Activity activity) {
            synchronized (ASKED) {
                Asked mine = ASKED.remove(activity);
                if (mine == null || mine.nothing()) return;
                if (activity.isChangingConfigurations()) {
                    HANDED_ON.put(activity.getClass().getName(),
                            new Left(mine, SystemClock.elapsedRealtime()));
                }
            }
        }
    };
}
