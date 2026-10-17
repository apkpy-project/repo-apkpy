# -*- coding: utf-8 -*-
"""ApkpyNetwork itself, run on the desk.

The same Android of thirty lines the timers are run against, with a phone's
connection added to it: the test connects it, takes the connection away, and
goes from Wi-Fi to mobile data the two ways a phone does, and reads which
function of which screen was called, and what it was told when it asked.

It is no phone. What a real one reports, and how fast, is seen on one.
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
    "android/os/Handler.java": CLOCK["android/os/Handler.java"].replace(
        "    public void removeCallbacks(Runnable work) {",
        "    public boolean post(Runnable work) { return postDelayed(work, 0L); }\n"
        "    public void removeCallbacks(Runnable work) {"),
    "android/content/Context.java": '''package android.content;
public class Context {
    public static final String CONNECTIVITY_SERVICE = "connectivity";
    public Context getApplicationContext() { return this; }
    public Object getSystemService(String name) { return android.net.ConnectivityManager.PHONE; }
}
''',
    "android/app/Activity.java": CLOCK["android/app/Activity.java"].replace(
        "public class Activity {", "public class Activity extends android.content.Context {"),
    "android/net/Network.java": '''package android.net;
public class Network {
    public final int id;
    public Network(int id) { this.id = id; }
    @Override public boolean equals(Object other) {
        return other instanceof Network && ((Network) other).id == id;
    }
    @Override public int hashCode() { return id; }
}
''',
    "android/net/NetworkCapabilities.java": '''package android.net;
import java.util.HashSet;
import java.util.Set;
public class NetworkCapabilities {
    public static final int NET_CAPABILITY_NOT_METERED = 11;
    public static final int NET_CAPABILITY_INTERNET = 12;
    public static final int NET_CAPABILITY_VALIDATED = 16;
    public static final int TRANSPORT_CELLULAR = 0;
    public static final int TRANSPORT_WIFI = 1;
    public static final int TRANSPORT_BLUETOOTH = 2;
    public static final int TRANSPORT_ETHERNET = 3;
    public static final int TRANSPORT_VPN = 4;
    public final Set<Integer> has = new HashSet<>();
    public final Set<Integer> over = new HashSet<>();
    public boolean hasCapability(int which) { return has.contains(which); }
    public boolean hasTransport(int which) { return over.contains(which); }
}
''',
    "android/net/ConnectivityManager.java": '''package android.net;
public class ConnectivityManager {
    public static final ConnectivityManager PHONE = new ConnectivityManager();
    public static class NetworkCallback {
        public void onAvailable(Network network) { }
        public void onLost(Network network) { }
        public void onCapabilitiesChanged(Network network, NetworkCapabilities found) { }
    }
    public Network active;
    public NetworkCapabilities made;
    public NetworkCallback heard;
    public int registered;
    public int asked;
    public boolean refuses;
    // What else the phone is connected to, besides the one apps are given.
    public final java.util.Map<Network, NetworkCapabilities> beside = new java.util.LinkedHashMap<>();
    public Network getActiveNetwork() { asked++; return active; }
    public NetworkCapabilities getNetworkCapabilities(Network network) {
        if (network != null && network.equals(active)) return made;
        return network == null ? null : beside.get(network);
    }
    public Network[] getAllNetworks() {
        java.util.List<Network> all = new java.util.ArrayList<>(beside.keySet());
        if (active != null) all.add(active);
        return all.toArray(new Network[0]);
    }
    public void registerDefaultNetworkCallback(NetworkCallback callback) {
        if (refuses) throw new SecurityException("not allowed to ask");
        heard = callback;
        registered++;
    }
    // The test's: what a phone does, and what it says as it does it.
    public void connect(int id, NetworkCapabilities found) {
        active = new Network(id);
        made = found;
        if (heard == null) return;
        heard.onAvailable(active);
        heard.onCapabilitiesChanged(active, found);
    }
    /** Before Android 8: here it is, and nothing about what it is made of. */
    public void connectSayingLittle(int id, NetworkCapabilities found) {
        active = new Network(id);
        made = found;
        if (heard != null) heard.onAvailable(active);
    }
    public void change(NetworkCapabilities found) {
        made = found;
        if (heard != null) heard.onCapabilitiesChanged(active, found);
    }
    public void lose() {
        Network was = active;
        active = null;
        made = null;
        if (heard != null && was != null) heard.onLost(was);
    }
    /** A connection that is not the one in use goes: Wi-Fi, after mobile data took over. */
    public void loseAnother(int id) {
        if (heard != null) heard.onLost(new Network(id));
    }
}
''',
})

HARNESS = '''import android.app.Activity;
import android.app.Application;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.os.Build;
import android.os.Handler;
import android.os.SystemClock;
import java.util.ArrayList;
import java.util.List;

public class Harness {
    static final class Home extends Activity { }
    static final class Detail extends Activity { }

    static final Application APP = new Application();
    static final ConnectivityManager PHONE = ConnectivityManager.PHONE;
    static final List<Object> KEPT = new ArrayList<>();     // a screen holds its own Calls
    static String tag = "";
    static int next = 100;

    static void say(String what) { System.out.println(tag + "|" + what); }

    static NetworkCapabilities made(boolean validated, boolean unmetered, int... over) {
        NetworkCapabilities found = new NetworkCapabilities();
        found.has.add(NetworkCapabilities.NET_CAPABILITY_INTERNET);
        if (validated) found.has.add(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
        if (unmetered) found.has.add(NetworkCapabilities.NET_CAPABILITY_NOT_METERED);
        for (int each : over) found.over.add(each);
        return found;
    }
    static NetworkCapabilities wifi() { return made(true, true, NetworkCapabilities.TRANSPORT_WIFI); }
    static NetworkCapabilities mobile() { return made(true, false, NetworkCapabilities.TRANSPORT_CELLULAR); }

    static String asked(Activity screen) {
        return ApkpyNetwork.online(screen) + " " + ApkpyNetwork.kind(screen)
                + " " + ApkpyNetwork.metered(screen);
    }

    /** Everything that was posted runs; no time goes by. */
    static void settle() { Handler.until(SystemClock.now); }

    static void begin(String name) {
        tag = "between";
        // Long enough for anything a scenario left behind to be too old to hand on.
        Handler.until(SystemClock.now + 100000L);
        PHONE.connect(next++, wifi());
        settle();
        tag = name;
    }

    static Activity open(final Activity screen, final String label) {
        screen.application = APP;
        ApkpyNetwork.Calls calls = new ApkpyNetwork.Calls() {
            @Override public void call(String name) {
                say(label + " " + name + ": " + asked(screen));
            }
        };
        KEPT.add(calls);
        ApkpyNetwork.host(screen, calls);
        return screen;
    }

    public static void main(String[] arguments) {
        // An app that only asks: the phone answers on the spot, and nothing listens.
        tag = "asks";
        Activity only = open(new Home(), "only");
        only.start();
        say(asked(only));
        PHONE.connect(1, wifi());
        say(asked(only));
        PHONE.connect(2, mobile());
        say(asked(only));
        PHONE.connect(3, made(false, true, NetworkCapabilities.TRANSPORT_WIFI));     // a login page
        say(asked(only));
        PHONE.connect(4, made(true, true, NetworkCapabilities.TRANSPORT_VPN,
                NetworkCapabilities.TRANSPORT_WIFI));
        say(asked(only));
        PHONE.connect(5, made(true, true, NetworkCapabilities.TRANSPORT_ETHERNET));
        say(asked(only));
        PHONE.connect(6, made(true, false, NetworkCapabilities.TRANSPORT_BLUETOOTH));    // a shared phone
        say(asked(only));
        PHONE.connect(7, made(true, false, NetworkCapabilities.TRANSPORT_VPN));          // a tunnel over nothing
        say(asked(only));
        PHONE.lose();
        say(asked(only));
        say("listening " + PHONE.registered);
        only.destroy(false);

        tag = "refused";
        Activity shut = open(new Home(), "shut");
        shut.start();
        PHONE.refuses = true;
        say(ApkpyNetwork.onChange(shut, "changed"));
        PHONE.refuses = false;
        PHONE.connect(8, wifi());
        settle();
        say("listening " + PHONE.registered);
        shut.destroy(false);

        begin("told");
        Activity home = open(new Home(), "home");
        home.start();
        say(ApkpyNetwork.onChange(home, "changed") + " listening " + PHONE.registered);
        settle();
        say("nothing yet");
        PHONE.lose();
        settle();
        PHONE.connect(next++, mobile());
        settle();
        PHONE.change(mobile());                 // the signal got stronger: nothing an app asks changed
        PHONE.change(mobile());
        settle();
        say("same");
        PHONE.change(made(false, false, NetworkCapabilities.TRANSPORT_CELLULAR));
        settle();
        int before = PHONE.asked;
        say(asked(home));
        say("asked the phone again " + (PHONE.asked - before));
        home.destroy(false);

        begin("several");
        Activity form = open(new Home(), "form");
        form.start();
        say(ApkpyNetwork.onChange(form, "banner") + " " + ApkpyNetwork.onChange(form, "queue")
                + " " + ApkpyNetwork.onChange(form, "banner") + " listening " + PHONE.registered);
        PHONE.lose();
        settle();
        // Found, lost and found again before the screen could be told: one change, not three.
        PHONE.connect(next++, wifi());
        PHONE.lose();
        PHONE.connect(next++, wifi());
        settle();
        form.destroy(false);

        begin("away");
        Activity list = open(new Home(), "list");
        list.start();
        ApkpyNetwork.onChange(list, "changed");
        list.stop();
        PHONE.lose();
        settle();
        PHONE.connect(next++, wifi());
        settle();
        list.start();
        settle();
        say("came and went");
        list.stop();
        PHONE.lose();
        settle();
        say("still away");
        list.start();
        settle();
        list.destroy(false);

        begin("turned");
        Activity upright = open(new Home(), "upright");
        upright.start();
        ApkpyNetwork.onChange(upright, "changed");
        upright.stop();
        upright.destroy(true);
        PHONE.connect(next++, mobile());        // it changed while the screen was being rebuilt
        settle();
        Activity sideways = open(new Home(), "sideways");
        say(ApkpyNetwork.onChange(sideways, "changed"));    // its on_mount asks again
        sideways.start();
        settle();
        PHONE.lose();
        settle();
        sideways.destroy(false);

        begin("closed");
        Activity detail = open(new Detail(), "detail");
        detail.start();
        ApkpyNetwork.onChange(detail, "changed");
        detail.stop();
        detail.destroy(false);
        Activity again = open(new Detail(), "again");
        again.start();
        PHONE.lose();
        settle();
        say("nobody");
        again.destroy(false);

        begin("stale");
        Activity gone = open(new Detail(), "gone");
        gone.start();
        ApkpyNetwork.onChange(gone, "changed");
        gone.stop();
        gone.destroy(true);
        Handler.until(SystemClock.now + 11000L);
        Activity late = open(new Detail(), "late");
        late.start();
        PHONE.lose();
        settle();
        say("nobody");
        late.destroy(false);

        begin("two");
        Activity under = open(new Home(), "under");
        under.start();
        ApkpyNetwork.onChange(under, "changed");
        Activity top = open(new Detail(), "top");       // another screen is opened over it
        top.start();
        under.stop();
        ApkpyNetwork.onChange(top, "changed");
        PHONE.lose();
        settle();
        top.stop();                                     // and Back
        top.destroy(false);
        under.start();
        settle();
        under.destroy(false);

        // From Wi-Fi to mobile data: the new one is here before the old one goes.
        begin("handover");
        Activity walk = open(new Home(), "walk");
        walk.start();
        ApkpyNetwork.onChange(walk, "changed");
        int old = next - 1;
        PHONE.connect(next++, mobile());
        PHONE.loseAnother(old);
        settle();
        say(asked(walk));
        walk.destroy(false);

        // Android 7: a connection is announced with nothing about what it is.
        begin("seven");
        Build.VERSION.SDK_INT = 24;
        Activity older = open(new Home(), "older");
        older.start();
        ApkpyNetwork.onChange(older, "changed");
        PHONE.connectSayingLittle(next++, mobile());
        settle();
        PHONE.lose();
        settle();
        Build.VERSION.SDK_INT = 36;
        older.destroy(false);

        // A phone with a VPN app: every app is given the tunnel, and in
        // aeroplane mode the tunnel is still there with nothing beneath it.
        begin("tunnel");
        Activity veiled = open(new Home(), "veiled");
        veiled.start();
        PHONE.connect(next++, made(true, true, NetworkCapabilities.TRANSPORT_VPN,
                NetworkCapabilities.TRANSPORT_WIFI));
        settle();
        ApkpyNetwork.onChange(veiled, "changed");
        say(asked(veiled));
        PHONE.change(made(true, false, NetworkCapabilities.TRANSPORT_VPN));     // aeroplane mode
        settle();
        // Something that is no way to the internet does not count: a phone
        // keeps a line to its operator for calls with mobile data off.
        NetworkCapabilities calls = new NetworkCapabilities();
        calls.has.add(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
        calls.over.add(NetworkCapabilities.TRANSPORT_CELLULAR);
        PHONE.beside.put(new android.net.Network(9001), calls);
        PHONE.change(made(true, false, NetworkCapabilities.TRANSPORT_VPN));
        settle();
        say("calls only: " + asked(veiled));
        PHONE.change(made(true, true, NetworkCapabilities.TRANSPORT_VPN,
                NetworkCapabilities.TRANSPORT_WIFI));
        settle();
        // Before Android 10 a tunnel never said what it ran over: it is looked for.
        PHONE.beside.put(new android.net.Network(9002), mobile());
        PHONE.change(made(true, false, NetworkCapabilities.TRANSPORT_VPN));
        settle();
        PHONE.beside.clear();
        veiled.destroy(false);

        begin("end");
        say("waiting " + Handler.waiting() + " listening " + PHONE.registered);
    }
}
'''

WANTED = {
    # online, kind, metered -- as the phone is connected to one thing after another.
    "asks": ["False none False", "True wifi False", "True mobile True",
             "False wifi False",        # a Wi-Fi that wants a login page first
             "True wifi False",         # Wi-Fi behind a VPN is Wi-Fi
             "True ethernet False", "True other True",
             "False none False",        # a VPN with nothing beneath it
             "False none False",
             "listening 0"],
    "refused": ["failed", "listening 0"],
    # Not told what the connection is as it asks; told each time one of the
    # three answers changes, and only then.
    "told": ["ok listening 1", "nothing yet",
             "home changed: False none False", "home changed: True mobile True", "same",
             "home changed: False mobile True",
             "False mobile True", "asked the phone again 0"],
    "several": ["ok ok ok listening 1",
                "form banner: False none False", "form queue: False none False",
                "form banner: True wifi False", "form queue: True wifi False"],
    "away": ["came and went", "still away", "list changed: False none False"],
    "turned": ["ok", "sideways changed: True mobile True", "sideways changed: False none False"],
    "closed": ["nobody"],
    "stale": ["nobody"],
    "two": ["top changed: False none False", "under changed: False none False"],
    "handover": ["walk changed: True mobile True", "True mobile True"],
    "seven": ["older changed: True mobile True", "older changed: False none False"],
    # Seen on a phone with a VPN app, in aeroplane mode: "other, online".
    "tunnel": ["True wifi False",
               "veiled changed: False none False", "calls only: False none False",
               "veiled changed: True wifi False", "veiled changed: True mobile True"],
    "end": ["waiting 0 listening 1"],
    "between": [],
}


@unittest.skipUnless(TOOLING and TOOLING[0], "no JDK on this machine")
class ThePhonesWord(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        javac, java_bin, _jar = TOOLING
        cls.work = tempfile.mkdtemp(prefix="apkpy-network-java-")
        sources = []
        for name, text in ANDROID.items():
            path = os.path.join(cls.work, name.replace("/", os.sep))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with io.open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            sources.append(path)
        for name in ("ApkpyNetwork", "ApkpyKitRules"):
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

    def test_an_app_that_only_asks_is_answered_by_the_phone_and_nothing_listens(self):
        self._same("asks")

    def test_a_phone_that_will_not_say_is_said_so(self):
        self._same("refused")

    def test_told_when_an_answer_changes_and_only_then(self):
        self._same("told")

    def test_every_function_of_the_screen_once_for_each_change(self):
        self._same("several")

    def test_a_screen_not_on_show_is_told_when_it_is_back_if_it_is_still_so(self):
        self._same("away")

    def test_a_screen_built_again_keeps_what_it_asked_for(self):
        self._same("turned")

    def test_a_screen_that_is_closed_is_told_no_more(self):
        self._same("closed")
        self._same("stale")

    def test_each_screen_is_told_while_it_is_the_one_on_show(self):
        self._same("two")

    def test_wifi_to_mobile_data_is_one_change_not_two(self):
        self._same("handover")

    def test_android_seven_says_less_and_is_asked_instead(self):
        self._same("seven")

    def test_a_vpn_with_nothing_beneath_it_is_no_connection(self):
        self._same("tunnel")

    def test_one_listener_for_the_app_and_nothing_left_waiting(self):
        self._same("end")
        self._same("between")
        self.assertEqual(sorted(self.said), sorted(tag for tag in WANTED if WANTED[tag]))


if __name__ == "__main__":
    unittest.main()
