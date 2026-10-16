# -*- coding: utf-8 -*-
"""ApkpyTimers itself, run on the desk.

The Previewer's clockwork is tested with a clock of its own; the phone's is
the same steps written again in Java, plus what only Android has: a screen is
started, stopped, closed, or built again when the phone is turned. javac says
that file compiles. This runs it -- against an Android of thirty lines, where
a Handler is a list, the clock is a number, and a screen is started and
stopped by the test -- and reads what was called, and when.

It is no phone. It holds the rules that can be held without one.
"""

import io
import os
import shutil
import subprocess
import tempfile
import unittest

from apkpy_lib.core.features import kit

from test_data_rules import TOOLING

ANDROID = {
    "android/os/SystemClock.java": '''package android.os;
public final class SystemClock {
    public static long now;
    public static long elapsedRealtime() { return now; }
}
''',
    "android/os/Looper.java": '''package android.os;
public final class Looper {
    private static final Looper MAIN = new Looper();
    public static Looper getMainLooper() { return MAIN; }
}
''',
    "android/os/Bundle.java": '''package android.os;
public class Bundle { }
''',
    "android/os/Handler.java": '''package android.os;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
public class Handler {
    private static final class Waiting { long at; long order; Runnable work; }
    private static final List<Waiting> QUEUE = new ArrayList<>();
    private static long count;
    public Handler(Looper looper) { }
    public boolean postDelayed(Runnable work, long millis) {
        Waiting waiting = new Waiting();
        waiting.at = SystemClock.now + millis;
        waiting.order = count++;
        waiting.work = work;
        QUEUE.add(waiting);
        return true;
    }
    public void removeCallbacks(Runnable work) {
        for (Iterator<Waiting> each = QUEUE.iterator(); each.hasNext();) {
            if (each.next().work == work) each.remove();
        }
    }
    /** The test's: time goes by to this moment, and what falls due runs in order. */
    public static void until(long moment) {
        while (true) {
            Waiting next = null;
            for (Waiting waiting : QUEUE) {
                if (waiting.at > moment) continue;
                if (next == null || waiting.at < next.at
                        || (waiting.at == next.at && waiting.order < next.order)) next = waiting;
            }
            if (next == null) break;
            QUEUE.remove(next);
            if (next.at > SystemClock.now) SystemClock.now = next.at;
            next.work.run();
        }
        SystemClock.now = moment;
    }
    public static int waiting() { return QUEUE.size(); }
}
''',
    "android/view/View.java": '''package android.view;
public class View {
    public static final int VISIBLE = 0;
    public static final int GONE = 8;
    public int visibility = GONE;
    public int getWindowVisibility() { return visibility; }
}
''',
    "android/view/Window.java": '''package android.view;
public class Window {
    public View decor = new View();
    public View peekDecorView() { return decor; }
}
''',
    "android/app/Application.java": '''package android.app;
import android.os.Bundle;
import java.util.ArrayList;
import java.util.List;
public class Application {
    public interface ActivityLifecycleCallbacks {
        void onActivityCreated(Activity activity, Bundle saved);
        void onActivityStarted(Activity activity);
        void onActivityResumed(Activity activity);
        void onActivityPaused(Activity activity);
        void onActivityStopped(Activity activity);
        void onActivitySaveInstanceState(Activity activity, Bundle out);
        void onActivityDestroyed(Activity activity);
    }
    public final List<ActivityLifecycleCallbacks> watchers = new ArrayList<>();
    public void registerActivityLifecycleCallbacks(ActivityLifecycleCallbacks callbacks) {
        watchers.add(callbacks);
    }
}
''',
    "android/app/Activity.java": '''package android.app;
import android.view.View;
import android.view.Window;
public class Activity {
    public Application application;
    public Window window = new Window();
    public boolean destroyed;
    public boolean changing;
    public Application getApplication() { return application; }
    public Window getWindow() { return window; }
    public boolean isDestroyed() { return destroyed; }
    public boolean isChangingConfigurations() { return changing; }
    // What Android does to a screen, as far as a timer can tell.
    public void start() {
        window.decor.visibility = View.VISIBLE;
        for (Application.ActivityLifecycleCallbacks each : application.watchers) each.onActivityStarted(this);
    }
    public void stop() {
        window.decor.visibility = View.GONE;
        for (Application.ActivityLifecycleCallbacks each : application.watchers) each.onActivityStopped(this);
    }
    public void destroy(boolean builtAgain) {
        changing = builtAgain;
        destroyed = true;
        for (Application.ActivityLifecycleCallbacks each : application.watchers) each.onActivityDestroyed(this);
    }
}
''',
}

HARNESS = '''import android.app.Activity;
import android.app.Application;
import android.os.Handler;
import android.os.SystemClock;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class Harness {
    static final class Home extends Activity { }
    static final class Detail extends Activity { }

    static final Application APP = new Application();
    static final List<Object> KEPT = new ArrayList<>();     // a screen holds its own Calls
    static final Map<String, Runnable> DO = new HashMap<>();
    static String tag = "";
    static long zero;

    static void say(String what) { System.out.println(tag + "|" + what); }

    static void begin(String name) {
        tag = "between";
        DO.clear();
        // Long enough for anything a scenario left behind to be too old to hand on.
        Handler.until(SystemClock.now + 100000L);
        zero = SystemClock.now;
        tag = name;
    }

    static void until(long moment) { Handler.until(zero + moment); }

    static Activity open(Activity screen, final String label) {
        screen.application = APP;
        ApkpyTimers.Calls calls = new ApkpyTimers.Calls() {
            @Override public void call(String name) {
                say(label + " " + name + " @" + (SystemClock.now - zero));
                Runnable more = DO.get(name);
                if (more != null) more.run();
            }
        };
        KEPT.add(calls);
        ApkpyTimers.host(screen, calls);
        return screen;
    }

    public static void main(String[] arguments) {
        begin("grid");
        final Activity home = open(new Home(), "home");
        home.start();
        say(ApkpyTimers.every(home, "1", "tick") + " " + ApkpyTimers.after(home, "2.5", "once")
                + " " + ApkpyTimers.every(home, "soon", "bad") + " " + ApkpyTimers.after(home, "-1", "bad"));
        until(3200);
        say("running " + ApkpyTimers.running(home, "tick") + " " + ApkpyTimers.running(home, "once")
                + " " + ApkpyTimers.running(home, "bad"));

        tag = "away";
        home.stop();
        until(7300);
        say("still " + ApkpyTimers.running(home, "tick"));
        home.start();
        until(7300);
        say("back");
        until(9100);
        say(ApkpyTimers.cancel(home, "tick") + " " + ApkpyTimers.cancel(home, "tick")
                + " " + ApkpyTimers.cancel(home, "never"));
        until(12000);
        say("waiting " + Handler.waiting());
        home.destroy(false);

        begin("typing");
        Activity form = open(new Home(), "form");
        form.start();
        for (int key = 0; key < 4; key++) {
            until(key * 100);
            ApkpyTimers.after(form, "0.4", "search");
        }
        until(5000);
        form.destroy(false);

        begin("mount");
        Activity fresh = open(new Home(), "fresh");
        say(ApkpyTimers.every(fresh, "1", "tick"));     // in onCreate: nothing is on show yet
        until(2500);
        say("not yet " + Handler.waiting());
        fresh.start();
        until(2500);
        say("shown");
        until(3100);
        fresh.destroy(false);

        begin("turned");
        Activity before = open(new Home(), "before");
        before.start();
        ApkpyTimers.every(before, "1", "tick");
        ApkpyTimers.every(before, "1", "count");
        ApkpyTimers.after(before, "5", "once");
        until(1500);
        before.stop();
        before.destroy(true);
        Activity after = open(new Home(), "after");
        // In its on_mount, before it is on show: asked about what it was handed.
        say("at mount " + ApkpyTimers.running(after, "count") + " " + ApkpyTimers.running(after, "tick")
                + " waiting " + Handler.waiting());
        ApkpyTimers.every(after, "1", "tick");          // its on_mount starts the clock again
        after.start();
        say("handed on " + ApkpyTimers.running(after, "count") + " " + ApkpyTimers.running(after, "once")
                + " old " + ApkpyTimers.running(before, "count"));
        until(5100);
        after.destroy(false);

        begin("closed");
        Activity detail = open(new Detail(), "detail");
        detail.start();
        ApkpyTimers.every(detail, "1", "tick");
        until(1200);
        detail.stop();
        detail.destroy(false);
        Activity again = open(new Detail(), "again");
        again.start();
        say("again " + ApkpyTimers.running(again, "tick"));
        until(5000);
        say("waiting " + Handler.waiting());
        again.destroy(false);

        begin("stale");
        Activity gone = open(new Detail(), "gone");
        gone.start();
        ApkpyTimers.every(gone, "1", "tick");
        until(500);
        gone.stop();
        gone.destroy(true);
        until(11000);
        Activity late = open(new Detail(), "late");
        late.start();
        say("late " + ApkpyTimers.running(late, "tick"));
        until(15000);
        late.destroy(false);

        begin("inside");
        final Activity self = open(new Home(), "self");
        self.start();
        final int[] ticks = {0};
        final int[] onces = {0};
        DO.put("tick", new Runnable() {
            @Override public void run() {
                if (++ticks[0] == 3) say("stop " + ApkpyTimers.cancel(self, "tick"));
            }
        });
        DO.put("once", new Runnable() {
            @Override public void run() {
                say("inside " + ApkpyTimers.running(self, "once"));
                if (++onces[0] < 3) ApkpyTimers.after(self, "0.5", "once");
            }
        });
        ApkpyTimers.every(self, "1", "tick");
        ApkpyTimers.after(self, "0.5", "once");
        until(9000);
        say("waiting " + Handler.waiting());
        self.destroy(false);

        begin("two");
        Activity list = open(new Home(), "list");
        list.start();
        ApkpyTimers.every(list, "1", "tick");
        until(1100);
        Activity top = open(new Detail(), "top");       // another screen is opened over it
        top.start();
        list.stop();
        ApkpyTimers.every(top, "1", "tick");
        until(3500);
        say("list " + ApkpyTimers.running(list, "tick") + " top " + ApkpyTimers.running(top, "tick"));
        top.stop();                                     // and Back
        top.destroy(false);
        list.start();
        until(4600);
        say("top " + ApkpyTimers.running(top, "tick"));
        list.destroy(false);

        begin("end");
        say("waiting " + Handler.waiting());
    }
}
'''

WANTED = {
    "grid": ["ok ok invalid invalid",
             "home tick @1000", "home tick @2000", "home once @2500", "home tick @3000",
             "running True False False"],
    # Stopped at 3200 and back at 7300: four moments went by, one tick is run
    # for them, and it goes on from there -- the next a full second on, not
    # at 8000 right behind it.
    "away": ["still True", "home tick @7300", "back", "home tick @8300",
             "ok not_running not_running", "waiting 0"],
    # Four keys a tenth of a second apart, one search, 0.4 s after the last.
    "typing": ["form search @700"],
    # Started in onCreate, as on_mount does: it waits for the screen to be on show.
    "mount": ["ok", "not yet 0", "fresh tick @2500", "shown"],
    # The phone is turned at 1500. count and once go on to the new screen with
    # the moments they had; tick is the new screen's own, started as it opened.
    # Handed on as the new screen is made, so its on_mount is told the truth
    # ("at mount"); nothing runs for it until it is on show.
    "turned": ["before tick @1000", "before count @1000",
               "at mount True True waiting 0",
               "handed on True True old False",
               "after count @2000", "after tick @2500", "after count @3000",
               "after tick @3500", "after count @4000", "after tick @4500",
               "after once @5000", "after count @5000"],
    "closed": ["detail tick @1000", "again False", "waiting 0"],
    "stale": ["late False"],
    "inside": ["self once @500", "inside False",
               "self tick @1000", "self once @1000", "inside False",
               "self once @1500", "inside False",
               "self tick @2000", "self tick @3000", "stop ok", "waiting 0"],
    "two": ["list tick @1000", "top tick @2100", "top tick @3100", "list True top True",
            "list tick @3500", "list tick @4500", "top False"],
    "end": ["waiting 0"],
    # Whatever a scenario left waiting would be called here.
    "between": [],
}


@unittest.skipUnless(TOOLING[0], "no JDK on this machine")
class ThePhonesClockwork(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        javac, java_bin, _jar = TOOLING
        cls.work = tempfile.mkdtemp(prefix="apkpy-timers-java-")
        sources = []
        for name, text in ANDROID.items():
            path = os.path.join(cls.work, name.replace("/", os.sep))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with io.open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            sources.append(path)
        for name in ("ApkpyTimers", "ApkpyKitRules"):
            path = os.path.join(cls.work, name + ".java")
            with io.open(path, "w", encoding="utf-8") as handle:
                handle.write(kit.java_source(name, "p").replace("package p;", ""))
            sources.append(path)
        path = os.path.join(cls.work, "Harness.java")
        with io.open(path, "w", encoding="utf-8") as handle:
            handle.write(HARNESS)
        sources.append(path)
        out = os.path.join(cls.work, "classes")
        os.makedirs(out)
        built = subprocess.run([javac, "-encoding", "UTF-8", "-nowarn", "-d", out] + sources,
                               capture_output=True, text=True)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([java_bin, "-cp", out, "Harness"], capture_output=True, text=True)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        cls.said = {}
        for line in ran.stdout.splitlines():
            tag, _bar, what = line.partition("|")
            cls.said.setdefault(tag, []).append(what)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, ignore_errors=True)

    def _same(self, tag):
        self.assertEqual(self.said.get(tag, []), WANTED[tag])

    def test_every_keeps_to_its_grid_and_after_runs_once(self):
        self._same("grid")

    def test_a_screen_not_on_show_runs_nothing_and_catches_up_once(self):
        self._same("away")

    def test_starting_again_starts_over(self):
        self._same("typing")

    def test_started_as_the_screen_is_made_it_waits_to_be_shown(self):
        self._same("mount")

    def test_a_screen_built_again_is_handed_its_timers(self):
        self._same("turned")

    def test_a_screen_that_is_closed_takes_its_timers_with_it(self):
        self._same("closed")

    def test_what_was_left_is_not_handed_to_a_screen_opened_much_later(self):
        self._same("stale")

    def test_a_function_can_stop_itself_or_start_itself_over(self):
        self._same("inside")

    def test_each_screen_has_its_own_and_only_the_one_on_show_runs(self):
        self._same("two")

    def test_nothing_is_left_waiting(self):
        self._same("end")
        self._same("between")
        self.assertEqual(sorted(self.said), sorted(tag for tag in WANTED if WANTED[tag]))


if __name__ == "__main__":
    unittest.main()
