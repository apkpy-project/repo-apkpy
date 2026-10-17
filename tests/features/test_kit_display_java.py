# -*- coding: utf-8 -*-
"""ApkpyDisplay itself, run on the desk.

The same Android of thirty lines the timers are run against, with a window
added to it: flags that can be set, a brightness, bars that can be hidden and
a way up that can be asked for. The test asks as a screen would, turns the
phone -- which is Android throwing the screen away and making another -- and
reads what each window was left with.

It is no phone. Whether a screen really stays lit is seen on one.
"""

import io
import os
import shutil
import subprocess
import tempfile
import unittest

from apkpy_lib.core.features import kit

from test_data_rules import TOOLING
from test_kit_timers_java import ANDROID as CLOCK

ANDROID = dict(CLOCK)
ANDROID.update({
    "android/os/Build.java": '''package android.os;
public class Build {
    public static class VERSION {
        public static int SDK_INT = 36;
    }
}
''',
    "android/os/Looper.java": '''package android.os;
public final class Looper {
    private static final Looper MAIN = new Looper();
    public static Looper here = MAIN;       // the test's: which thread this is
    public static final Looper ELSEWHERE = new Looper();
    public static Looper getMainLooper() { return MAIN; }
    public static Looper myLooper() { return here; }
}
''',
    "android/content/pm/ActivityInfo.java": '''package android.content.pm;
public class ActivityInfo {
    public static final int SCREEN_ORIENTATION_UNSPECIFIED = -1;
    public static final int SCREEN_ORIENTATION_PORTRAIT = 1;
    public static final int SCREEN_ORIENTATION_SENSOR_LANDSCAPE = 6;
}
''',
    "android/view/WindowInsets.java": '''package android.view;
public class WindowInsets {
    public static final class Type {
        public static int systemBars() { return 7; }
    }
}
''',
    "android/view/WindowInsetsController.java": '''package android.view;
public class WindowInsetsController {
    public static final int BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE = 2;
    public int hidden;
    public int behaviour;
    public void hide(int types) { hidden |= types; }
    public void show(int types) { hidden &= ~types; }
    public void setSystemBarsBehavior(int behaviour) { this.behaviour = behaviour; }
}
''',
    "android/view/WindowManager.java": '''package android.view;
public class WindowManager {
    public static class LayoutParams {
        public static final int FLAG_KEEP_SCREEN_ON = 0x80;
        public static final float BRIGHTNESS_OVERRIDE_NONE = -1.0f;
        public float screenBrightness = BRIGHTNESS_OVERRIDE_NONE;
    }
}
''',
    "android/view/View.java": '''package android.view;
public class View {
    public static final int VISIBLE = 0;
    public static final int GONE = 8;
    public static final int SYSTEM_UI_FLAG_HIDE_NAVIGATION = 2;
    public static final int SYSTEM_UI_FLAG_FULLSCREEN = 4;
    public static final int SYSTEM_UI_FLAG_LAYOUT_STABLE = 256;
    public static final int SYSTEM_UI_FLAG_IMMERSIVE_STICKY = 4096;
    public int visibility = GONE;
    public int systemUi = SYSTEM_UI_FLAG_LAYOUT_STABLE;     // something of the app's own
    public WindowInsetsController controller = new WindowInsetsController();
    public int getWindowVisibility() { return visibility; }
    public WindowInsetsController getWindowInsetsController() { return controller; }
    public int getSystemUiVisibility() { return systemUi; }
    public void setSystemUiVisibility(int flags) { systemUi = flags; }
}
''',
    "android/view/Window.java": '''package android.view;
public class Window {
    public View decor = new View();
    public int flags = 0x100;       // something of the app's own
    public WindowManager.LayoutParams attributes = new WindowManager.LayoutParams();
    public int set;                 // how many times the attributes were given back
    public View peekDecorView() { return decor; }
    public void addFlags(int more) { flags |= more; }
    public void clearFlags(int fewer) { flags &= ~fewer; }
    public WindowManager.LayoutParams getAttributes() { return attributes; }
    public void setAttributes(WindowManager.LayoutParams given) { attributes = given; set++; }
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
    public int requested = -99;         // nothing asked
    public int handedToMain;
    public Application getApplication() { return application; }
    public Window getWindow() { return window; }
    public boolean isDestroyed() { return destroyed; }
    public boolean isChangingConfigurations() { return changing; }
    public void setRequestedOrientation(int wanted) { requested = wanted; }
    public void runOnUiThread(Runnable work) { handedToMain++; work.run(); }
    // What Android does to a screen, as far as its window can tell.
    public void create() {
        for (Application.ActivityLifecycleCallbacks each : application.watchers) each.onActivityCreated(this, null);
    }
    public void start() {
        window.decor.visibility = View.VISIBLE;
        for (Application.ActivityLifecycleCallbacks each : application.watchers) each.onActivityStarted(this);
    }
    public void resume() {
        for (Application.ActivityLifecycleCallbacks each : application.watchers) each.onActivityResumed(this);
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
})

HARNESS = '''import android.app.Activity;
import android.app.Application;
import android.os.Build;
import android.os.Looper;
import android.os.SystemClock;
import android.view.View;
import android.view.WindowManager;

public class Harness {
    static final class Recipe extends Activity { }
    static final class Player extends Activity { }
    static final class Pass extends Activity { }
    static final class Old extends Activity { }

    static final Application APP = new Application();
    static String tag = "";

    static void say(String what) { System.out.println(tag + "|" + what); }
    static void begin(String name) { tag = name; }

    static <T extends Activity> T open(T screen) {
        screen.application = APP;
        screen.create();
        screen.start();
        screen.resume();
        return screen;
    }

    /** What a window was left with: awake, how bright, bars, way up. */
    static String has(Activity screen) {
        boolean awake = (screen.window.flags & WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) != 0;
        boolean kept = (screen.window.flags & 0x100) != 0;
        boolean bars = Build.VERSION.SDK_INT >= 30
                ? screen.window.decor.controller.hidden == 0
                : (screen.window.decor.systemUi & (View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION)) == 0;
        return (awake ? "awake" : "sleeps") + " " + screen.window.attributes.screenBrightness
                + " " + (bars ? "bars" : "no-bars") + " way " + screen.requested
                + (kept ? "" : " LOST-ITS-OWN-FLAG");
    }

    public static void main(String[] args) {
        begin("asks");
        Recipe recipe = open(new Recipe());
        say(has(recipe));
        say(ApkpyDisplay.keepOn(recipe, "true") + " " + has(recipe));
        say(ApkpyDisplay.keepOn(recipe, "True") + " " + has(recipe));
        say(ApkpyDisplay.keepOn(recipe, "false") + " " + has(recipe));
        say(ApkpyDisplay.keepOn(recipe, "yes") + " " + has(recipe));
        say(ApkpyDisplay.brightness(recipe, "0.9") + " " + has(recipe));
        say(ApkpyDisplay.brightness(recipe, "90") + " " + has(recipe));
        say(ApkpyDisplay.brightness(recipe, "0") + " " + has(recipe));
        say(ApkpyDisplay.brightness(recipe, "auto") + " " + has(recipe));
        say(ApkpyDisplay.immersive(recipe, "true") + " " + has(recipe)
                + " swipe " + recipe.window.decor.controller.behaviour);
        say(ApkpyDisplay.immersive(recipe, "false") + " " + has(recipe));
        say(ApkpyDisplay.orientation(recipe, "landscape") + " " + has(recipe));
        say(ApkpyDisplay.orientation(recipe, "Portrait") + " " + has(recipe));
        say(ApkpyDisplay.orientation(recipe, "sideways") + " " + has(recipe));
        say(ApkpyDisplay.orientation(recipe, "auto") + " " + has(recipe));
        say("watching " + APP.watchers.size() + " handed to main " + recipe.handedToMain);
        recipe.destroy(false);

        // The phone is turned: Android throws the screen away and makes another.
        begin("turned");
        Recipe before = open(new Recipe());
        ApkpyDisplay.keepOn(before, "true");
        ApkpyDisplay.brightness(before, "0.5");
        ApkpyDisplay.immersive(before, "true");
        before.stop();
        before.destroy(true);
        SystemClock.now += 400;
        Recipe after = new Recipe();
        after.application = APP;
        after.create();
        say("made: " + has(after));             // before any of the app's code for it
        after.start();
        after.resume();
        say("on show: " + has(after));
        ApkpyDisplay.keepOn(after, "false");    // what its own code asks is what it has
        say("asked: " + has(after));
        after.stop();
        after.destroy(true);
        SystemClock.now += 400;
        Recipe third = open(new Recipe());
        say("again: " + has(third));
        third.destroy(false);

        // Closed, and opened again later: a new screen, with nothing.
        begin("closed");
        Pass pass = open(new Pass());
        ApkpyDisplay.brightness(pass, "1");
        ApkpyDisplay.keepOn(pass, "true");
        pass.destroy(false);
        Pass reopened = open(new Pass());
        say(has(reopened));
        reopened.destroy(false);

        // Thrown away for a rebuild that never came.
        begin("stale");
        Pass left = open(new Pass());
        ApkpyDisplay.keepOn(left, "true");
        left.destroy(true);
        SystemClock.now += 10001;
        Pass late = open(new Pass());
        say(has(late));
        late.destroy(false);

        // What one screen asked is nothing to another.
        begin("two");
        Recipe under = open(new Recipe());
        ApkpyDisplay.keepOn(under, "true");
        Player over = open(new Player());
        say("over: " + has(over));
        ApkpyDisplay.immersive(over, "true");
        ApkpyDisplay.orientation(over, "landscape");
        say("over: " + has(over));
        say("under: " + has(under));
        over.destroy(false);
        say("under: " + has(under));
        // Turned while both are open: each copy takes its own.
        under.destroy(true);
        Player other = open(new Player());
        say("other: " + has(other));
        Recipe back = open(new Recipe());
        say("back: " + has(back));
        other.destroy(false);
        back.destroy(false);

        // A screen that asked and then took all of it back leaves nothing.
        begin("undone");
        Recipe tidy = open(new Recipe());
        ApkpyDisplay.keepOn(tidy, "true");
        ApkpyDisplay.keepOn(tidy, "false");
        tidy.destroy(true);
        Recipe next = open(new Recipe());
        say(has(next));
        next.destroy(false);

        // Bars asked for before the window has drawn anything: as it comes on show.
        begin("early");
        Player early = new Player();
        early.application = APP;
        early.create();
        View drawn = early.window.decor;
        early.window.decor = null;
        say(ApkpyDisplay.immersive(early, "true") + " and no window yet");
        early.window.decor = drawn;
        say("made: " + has(early));
        early.start();
        early.resume();
        say("on show: " + has(early));
        early.destroy(false);

        // Before Android 11 the bars are flags of the view.
        begin("older");
        Build.VERSION.SDK_INT = 29;
        Old old = open(new Old());
        say(ApkpyDisplay.immersive(old, "true") + " " + has(old) + " flags " + old.window.decor.systemUi);
        say(ApkpyDisplay.immersive(old, "false") + " " + has(old) + " flags " + old.window.decor.systemUi);
        old.destroy(false);
        Build.VERSION.SDK_INT = 36;

        // Asked from another thread: the window is touched on its own.
        begin("thread");
        Recipe busy = open(new Recipe());
        Looper.here = Looper.ELSEWHERE;
        say(ApkpyDisplay.keepOn(busy, "true") + " " + ApkpyDisplay.brightness(busy, "0.3")
                + " " + ApkpyDisplay.immersive(busy, "true") + " " + ApkpyDisplay.orientation(busy, "portrait"));
        Looper.here = Looper.getMainLooper();
        say(has(busy) + " handed to main " + busy.handedToMain);
        busy.destroy(false);

        begin("end");
        say("watching " + APP.watchers.size());
    }
}
'''

WANTED = {
    "asks": [
        "sleeps -1.0 bars way -99",
        "ok awake -1.0 bars way -99",
        "ok awake -1.0 bars way -99",
        "ok sleeps -1.0 bars way -99",
        "ok sleeps -1.0 bars way -99",          # "yes" is not "true": off, as a switch reads it
        "ok sleeps 0.9 bars way -99",
        "invalid sleeps 0.9 bars way -99",      # 90 changes nothing
        "ok sleeps 0.0 bars way -99",
        "ok sleeps -1.0 bars way -99",          # "auto": the phone's own again
        "ok sleeps -1.0 no-bars way -99 swipe 2",
        "ok sleeps -1.0 bars way -99",
        "ok sleeps -1.0 bars way 6",            # either way round
        "ok sleeps -1.0 bars way 1",
        "invalid sleeps -1.0 bars way 1",
        "ok sleeps -1.0 bars way -1",
        "watching 1 handed to main 0",
    ],
    # The window that replaces the old one starts with none of it, and is
    # given what the old one had before any of the app's code runs.
    "turned": [
        "made: awake 0.5 bars way -99",
        "on show: awake 0.5 no-bars way -99",
        "asked: sleeps 0.5 no-bars way -99",
        "again: sleeps 0.5 no-bars way -99",
    ],
    "closed": ["sleeps -1.0 bars way -99"],
    "stale": ["sleeps -1.0 bars way -99"],
    "two": [
        "over: sleeps -1.0 bars way -99",
        "over: sleeps -1.0 no-bars way 6",
        "under: awake -1.0 bars way -99",
        "under: awake -1.0 bars way -99",
        "other: sleeps -1.0 bars way -99",      # the player was closed, not rebuilt
        "back: awake -1.0 bars way -99",
    ],
    "undone": ["sleeps -1.0 bars way -99"],
    "early": ["ok and no window yet", "made: sleeps -1.0 bars way -99",
              "on show: sleeps -1.0 no-bars way -99"],
    "older": ["ok sleeps -1.0 no-bars way -99 flags 4358",
              "ok sleeps -1.0 bars way -99 flags 256"],
    "thread": ["ok ok ok ok", "awake 0.3 no-bars way 1 handed to main 4"],
    "end": ["watching 1"],
}


@unittest.skipUnless(TOOLING and TOOLING[0], "no JDK on this machine")
class ThePhonesWindow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        javac, java_bin, _jar = TOOLING
        cls.work = tempfile.mkdtemp(prefix="apkpy-display-java-")
        sources = []
        for name, text in ANDROID.items():
            path = os.path.join(cls.work, name.replace("/", os.sep))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with io.open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            sources.append(path)
        for name in ("ApkpyDisplay", "ApkpyKitRules"):
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

    def test_each_call_changes_its_own_thing_and_a_wrong_one_changes_nothing(self):
        self._same("asks")

    def test_a_screen_built_again_keeps_what_it_asked_for(self):
        self._same("turned")

    def test_a_screen_that_is_closed_takes_it_with_it(self):
        self._same("closed")
        self._same("stale")
        self._same("undone")

    def test_what_one_screen_asked_is_nothing_to_another(self):
        self._same("two")

    def test_bars_asked_for_before_the_window_has_drawn(self):
        self._same("early")

    def test_before_android_eleven_the_bars_are_flags(self):
        self._same("older")

    def test_asked_from_another_thread(self):
        self._same("thread")

    def test_one_watcher_for_the_app(self):
        self._same("end")
        self.assertEqual(sorted(self.said), sorted(WANTED))


if __name__ == "__main__":
    unittest.main()
