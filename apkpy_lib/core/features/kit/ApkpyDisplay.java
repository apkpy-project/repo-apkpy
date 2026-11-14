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

import java.lang.ref.WeakReference;
import java.util.ArrayList;
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
 *
 * on_screenshot() is told by Android 14 and later, which says so to the
 * screen on show when the person takes a screenshot of it. The screenshot is
 * taken all the same: secure_screen() is what stops it.
 */
public final class ApkpyDisplay {

    /** How a screen's functions are reached by name; see ApkpyNetwork. */
    public interface Calls {
        void call(String name);
    }

    /** What one screen has asked for. */
    private static final class Asked {
        boolean keepOn;
        float brightness = WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE;
        boolean immersive;
        final ArrayList<String> shots = new ArrayList<>();

        boolean nothing() {
            return !keepOn && !immersive && brightness < 0f && shots.isEmpty();
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
    private static final Map<Activity, WeakReference<Calls>> CALLS = new WeakHashMap<>();
    private static boolean watching;

    private ApkpyDisplay() { }

    /**
     * A screen says how its functions are called. Written into every screen
     * of an app that asks to be told of screenshots, and run as it is made.
     */
    public static Calls host(Activity activity, Calls calls) {
        synchronized (ASKED) {
            CALLS.put(activity, new WeakReference<>(calls));
        }
        return calls;
    }

    public static String onScreenshot(final Activity activity, String name) {
        if (Build.VERSION.SDK_INT < 34) return "unsupported";
        Asked mine = asked(activity);
        boolean first;
        synchronized (ASKED) {
            first = mine.shots.isEmpty();
            if (!mine.shots.contains(name)) mine.shots.add(name);
        }
        if (first) {
            onMain(activity, new Runnable() {
                @Override public void run() {
                    Shots.listen(activity);
                }
            });
        }
        return "ok";
    }

    /** A screenshot was taken of this screen: its functions are called. */
    private static void shot(Activity activity) {
        ArrayList<String> names;
        Calls calls;
        synchronized (ASKED) {
            Asked mine = ASKED.get(activity);
            if (mine == null || mine.shots.isEmpty()) return;
            names = new ArrayList<>(mine.shots);
            WeakReference<Calls> held = CALLS.get(activity);
            calls = held == null ? null : held.get();
        }
        if (calls == null || activity.isDestroyed()) return;
        for (String name : names) calls.call(name);
    }

    /** Android 14's own, kept apart so that an older phone never loads it. */
    private static final class Shots {
        private static final Map<Activity, Activity.ScreenCaptureCallback> LISTENING =
                new WeakHashMap<>();

        static void listen(Activity activity) {
            if (activity.isDestroyed() || LISTENING.containsKey(activity)) return;
            // Held weakly: the map's value must not keep its own key alive.
            final WeakReference<Activity> held = new WeakReference<>(activity);
            Activity.ScreenCaptureCallback told = new Activity.ScreenCaptureCallback() {
                @Override public void onScreenCaptured() {
                    Activity screen = held.get();
                    if (screen != null) shot(screen);
                }
            };
            try {
                activity.registerScreenCaptureCallback(activity.getMainExecutor(), told);
                LISTENING.put(activity, told);
            } catch (RuntimeException refused) {
                // DETECT_SCREEN_CAPTURE missing from the manifest.
            }
        }

        static void stop(Activity activity) {
            Activity.ScreenCaptureCallback told = LISTENING.remove(activity);
            if (told == null) return;
            try {
                activity.unregisterScreenCaptureCallback(told);
            } catch (RuntimeException ignored) { }
        }
    }

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
            if (Build.VERSION.SDK_INT >= 34 && !left.asked.shots.isEmpty()) Shots.listen(activity);
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
            if (Build.VERSION.SDK_INT >= 34) Shots.stop(activity);
            synchronized (ASKED) {
                CALLS.remove(activity);
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
