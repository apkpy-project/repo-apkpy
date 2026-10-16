package __PACKAGE__;

import android.app.Activity;
import android.app.Application;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.View;
import android.view.Window;

import java.lang.ref.WeakReference;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;
import java.util.WeakHashMap;

/**
 * timer.* -- a function of the app run later, or again and again.
 *
 * A timer belongs to the screen that started it and is known by the function
 * it calls: one function has one timer on a screen, and starting it again
 * starts it over. That is what makes "wait until the typing stops" one line,
 * and what lets cancel() name what to stop without the app keeping anything.
 *
 * Time keeps going by while the screen is not on show, and nothing is run
 * meanwhile: a function that draws on a screen nobody sees is work for
 * nothing, and a phone left to it stops the process whenever it likes, which
 * is no rule an app can count on. When the screen comes back, what fell due
 * runs once, at once, and an every() goes on from there, a full period on.
 *
 * Android rebuilds a screen when the phone is turned or the theme changes.
 * Its timers are handed on to the copy that replaces it, with the moments
 * they were waiting for; closing the screen ends them.
 */
public final class ApkpyTimers {

    /** How a screen's functions are reached by name; every screen has one. */
    public interface Calls {
        void call(String name);
    }

    private static final class Timer {
        final String name;
        final long period;      // 0 for one that runs once
        long due;               // on the clock that also counts the phone asleep
        Runnable posted;        // what waits on the main thread, or null

        Timer(String name, long period, long due) {
            this.name = name;
            this.period = period;
            this.due = due;
        }
    }

    /** What a screen being rebuilt leaves for its replacement, and when. */
    private static final class Left {
        final Map<String, Timer> timers;
        final long at;

        Left(Map<String, Timer> timers, long at) {
            this.timers = timers;
            this.at = at;
        }
    }

    // A rebuilt screen is back within moments. Past this, what was left is
    // from a screen that never returned, and starting it would be a surprise.
    private static final long HANDED_ON_FOR = 10000L;

    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    // Weak on both sides: a screen's Calls is held by the screen itself, and
    // a map that held it too would keep every closed screen in memory.
    private static final Map<Activity, WeakReference<Calls>> CALLS = new WeakHashMap<>();
    private static final Map<Activity, Map<String, Timer>> TIMERS = new WeakHashMap<>();
    private static final Map<Activity, Boolean> SHOWN = new WeakHashMap<>();
    private static final Map<String, Left> HANDED_ON = new HashMap<>();
    private static boolean watching;

    private ApkpyTimers() { }

    /**
     * A screen says how its functions are called. Written into every screen,
     * and run as the screen is made -- before its onCreate, so before the
     * app's on_mount. That is the moment a screen being rebuilt takes what
     * the one before it left: an on_mount that asks running(), or cancels,
     * is answered about the timers it really has. (Taken at onStart, they
     * were there a moment too late, and a countdown that was going was
     * reported stopped.)
     */
    public static Calls host(Activity activity, Calls calls) {
        CALLS.put(activity, new WeakReference<>(calls));
        adopt(activity);
        return calls;
    }

    public static String after(Activity activity, String seconds, String name) {
        return start(activity, seconds, name, false);
    }

    public static String every(Activity activity, String seconds, String name) {
        return start(activity, seconds, name, true);
    }

    public static String cancel(Activity activity, String name) {
        Map<String, Timer> mine = TIMERS.get(activity);
        Timer timer = mine == null ? null : mine.remove(name);
        if (timer == null) return "not_running";
        unpost(timer);
        return "ok";
    }

    public static String running(Activity activity, String name) {
        Map<String, Timer> mine = TIMERS.get(activity);
        return ApkpyKitRules.flag(mine != null && mine.containsKey(name));
    }

    private static String start(Activity activity, String seconds, String name,
                                boolean repeating) {
        long millis = ApkpyKitRules.timerMillis(seconds, repeating);
        if (millis < 0) return "invalid";
        watch(activity);
        Map<String, Timer> mine = TIMERS.get(activity);
        if (mine == null) {
            mine = new HashMap<>();
            TIMERS.put(activity, mine);
        }
        Timer before = mine.remove(name);
        if (before != null) unpost(before);
        Timer timer = new Timer(name, repeating ? millis : 0L, now() + millis);
        mine.put(name, timer);
        if (shown(activity)) post(activity, timer);
        return "ok";
    }

    private static long now() {
        return SystemClock.elapsedRealtime();
    }

    private static void unpost(Timer timer) {
        if (timer.posted != null) MAIN.removeCallbacks(timer.posted);
        timer.posted = null;
    }

    private static void post(Activity activity, final Timer timer) {
        unpost(timer);
        final WeakReference<Activity> screen = new WeakReference<>(activity);
        timer.posted = new Runnable() {
            @Override public void run() {
                timer.posted = null;
                Activity there = screen.get();
                if (there != null) fire(there, timer);
            }
        };
        MAIN.postDelayed(timer.posted, Math.max(0L, timer.due - now()));
    }

    private static void fire(Activity activity, Timer timer) {
        Map<String, Timer> mine = TIMERS.get(activity);
        if (mine == null || mine.get(timer.name) != timer) return;    // stopped, or started over
        if (activity.isDestroyed() || !shown(activity)) return;       // it waits for the screen
        WeakReference<Calls> held = CALLS.get(activity);
        Calls calls = held == null ? null : held.get();
        if (calls == null) return;
        // Settled before the function runs, so the function finds what it
        // would expect: running() is false inside an after(), and either
        // kind can stop itself or start itself over.
        if (timer.period > 0) {
            timer.due = ApkpyKitRules.timerNext(timer.due, timer.period, now());
            post(activity, timer);
        } else {
            mine.remove(timer.name);
        }
        calls.call(timer.name);
    }

    /**
     * Whether the screen is on show. Android says so from the moment it is
     * being watched; a screen that started before that is asked for its
     * window, which is visible between the same two moments.
     */
    private static boolean shown(Activity activity) {
        Boolean known = SHOWN.get(activity);
        if (known != null) return known;
        Window window = activity.getWindow();
        View decor = window == null ? null : window.peekDecorView();
        return decor != null && decor.getWindowVisibility() == View.VISIBLE;
    }

    private static void watch(Activity activity) {
        if (watching) return;
        Application application = activity.getApplication();
        if (application == null) return;
        application.registerActivityLifecycleCallbacks(WATCH);
        watching = true;
    }

    /** A screen that replaces one being rebuilt takes what that one left. */
    private static void adopt(Activity activity) {
        Left left = HANDED_ON.remove(activity.getClass().getName());
        if (left == null || now() - left.at > HANDED_ON_FOR) return;
        Map<String, Timer> mine = TIMERS.get(activity);
        if (mine == null) {
            mine = new HashMap<>();
            TIMERS.put(activity, mine);
        }
        // Nothing of the new screen's own can be here yet: it has run no code.
        // What its on_mount starts for a function replaces what was handed
        // on for it, as starting any timer again does.
        for (Map.Entry<String, Timer> entry : left.timers.entrySet()) {
            if (!mine.containsKey(entry.getKey())) mine.put(entry.getKey(), entry.getValue());
        }
    }

    private static final Application.ActivityLifecycleCallbacks WATCH =
            new Application.ActivityLifecycleCallbacks() {
        @Override public void onActivityCreated(Activity activity, Bundle saved) { }

        @Override public void onActivityStarted(Activity activity) {
            SHOWN.put(activity, Boolean.TRUE);
            Map<String, Timer> mine = TIMERS.get(activity);
            if (mine == null) return;
            // What fell due while the screen was away runs now: the wait
            // that is left is zero.
            for (Timer timer : new ArrayList<>(mine.values())) post(activity, timer);
        }

        @Override public void onActivityResumed(Activity activity) { }

        @Override public void onActivityPaused(Activity activity) { }

        @Override public void onActivityStopped(Activity activity) {
            SHOWN.put(activity, Boolean.FALSE);
            Map<String, Timer> mine = TIMERS.get(activity);
            if (mine == null) return;
            for (Timer timer : mine.values()) unpost(timer);
        }

        @Override public void onActivitySaveInstanceState(Activity activity, Bundle out) { }

        @Override public void onActivityDestroyed(Activity activity) {
            SHOWN.remove(activity);
            CALLS.remove(activity);
            Map<String, Timer> mine = TIMERS.remove(activity);
            if (mine == null) return;
            for (Timer timer : mine.values()) unpost(timer);
            if (activity.isChangingConfigurations() && !mine.isEmpty()) {
                HANDED_ON.put(activity.getClass().getName(), new Left(mine, now()));
            }
        }
    };
}
