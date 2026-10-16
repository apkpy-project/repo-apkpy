package __PACKAGE__;

import android.app.Activity;
import android.app.Application;
import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.Build;
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
 * network.* -- whether the phone reaches the internet, over what, and being
 * told when that changes.
 *
 * The three answers are read from one thing, what Android says of the
 * connection it gives apps by default: online() is a connection meant for the
 * internet that the phone has seen reach it, kind() is what it is made of,
 * metered() whether the person pays for what goes over it.
 *
 * on_change() belongs to the screen that asked, like a timer. Its functions
 * are called when the three answers, taken together, are no longer what the
 * screen last heard -- and only while it is on show. A change that comes and
 * goes while the screen is away is not told; one that is still there when it
 * comes back is told once. Closing the screen ends it, and a screen Android
 * builds again (the phone is turned, the theme changes) keeps what it had.
 */
public final class ApkpyNetwork {

    /** How a screen's functions are reached by name; every screen that watches has one. */
    public interface Calls {
        void call(String name);
    }

    /** What one screen asked to be told, and what it was last told. */
    private static final class Watch {
        final ArrayList<String> names = new ArrayList<>();
        String heard;

        Watch(String heard) {
            this.heard = heard;
        }
    }

    /** What a screen being rebuilt leaves for its replacement, and when. */
    private static final class Left {
        final Watch watch;
        final long at;

        Left(Watch watch, long at) {
            this.watch = watch;
            this.at = at;
        }
    }

    // A rebuilt screen is back within moments; see ApkpyTimers.
    private static final long HANDED_ON_FOR = 10000L;

    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final Map<Activity, WeakReference<Calls>> CALLS = new WeakHashMap<>();
    private static final Map<Activity, Watch> WATCHES = new WeakHashMap<>();
    private static final Map<Activity, Boolean> SHOWN = new WeakHashMap<>();
    private static final Map<String, Left> HANDED_ON = new HashMap<>();
    private static boolean watching;        // the screens' comings and goings
    private static boolean listening;       // the phone's word on the connection

    // What the phone last said, once it has said anything. Written on the
    // thread Android calls back on and read on the main one.
    private static volatile Network connection;
    private static volatile NetworkCapabilities current;
    private static volatile boolean reported;

    private ApkpyNetwork() { }

    /**
     * A screen says how its functions are called. Written into every screen
     * of an app that watches the connection, and run as the screen is made:
     * a screen being rebuilt takes what the one before it left.
     */
    public static Calls host(Activity activity, Calls calls) {
        CALLS.put(activity, new WeakReference<>(calls));
        Left left = HANDED_ON.remove(activity.getClass().getName());
        if (left != null && SystemClock.elapsedRealtime() - left.at <= HANDED_ON_FOR) {
            WATCHES.put(activity, left.watch);
        }
        return calls;
    }

    public static String online(Activity activity) {
        return ApkpyKitRules.flag(online(capabilities(activity)));
    }

    public static String kind(Activity activity) {
        return kind(capabilities(activity));
    }

    public static String metered(Activity activity) {
        return ApkpyKitRules.flag(metered(capabilities(activity)));
    }

    public static String onChange(Activity activity, String name) {
        if (!listen(activity)) return "failed";
        watch(activity);
        Watch mine = WATCHES.get(activity);
        if (mine == null) {
            // From here: what the connection is now is what the app can ask
            // for itself, and is not a change.
            mine = new Watch(state(activity));
            WATCHES.put(activity, mine);
        }
        if (!mine.names.contains(name)) mine.names.add(name);
        return "ok";
    }

    // --- what the phone says ---------------------------------------------

    private static ConnectivityManager manager(Context context) {
        return (ConnectivityManager) context.getApplicationContext()
                .getSystemService(Context.CONNECTIVITY_SERVICE);
    }

    /**
     * The connection apps are given, or null for none.
     *
     * An app that only asks is answered by the phone on the spot. One that
     * watches is answered from what the phone last reported: the function it
     * is called with a change then reads the same change, where asking again
     * could be answered a moment behind it.
     */
    private static NetworkCapabilities capabilities(Context context) {
        if (reported) return beneath(context, current);
        try {
            ConnectivityManager manager = manager(context);
            Network network = manager == null ? null : manager.getActiveNetwork();
            return beneath(context, network == null ? null : manager.getNetworkCapabilities(network));
        } catch (RuntimeException refused) {
            return null;
        }
    }

    /**
     * What a VPN runs over, when a VPN is the connection apps are given.
     *
     * A phone with a VPN app hands every app the tunnel, and the tunnel
     * outlives what it runs over: in aeroplane mode it is still there, still
     * marked as having reached the internet, with nothing beneath it. Seen
     * on a phone: an app was told it was online over "other" with every
     * radio off. Since Android 10 a tunnel says what it runs over, and one
     * that says nothing runs over nothing. Before that it never said, so the
     * connection beneath is looked for; found, it is the answer.
     */
    private static NetworkCapabilities beneath(Context context, NetworkCapabilities found) {
        if (found == null || !found.hasTransport(NetworkCapabilities.TRANSPORT_VPN)) return found;
        if (found.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
                || found.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)
                || found.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) {
            return found;
        }
        try {
            ConnectivityManager manager = manager(context);
            if (manager == null) return null;
            for (Network each : manager.getAllNetworks()) {
                NetworkCapabilities other = manager.getNetworkCapabilities(each);
                if (other != null && !other.hasTransport(NetworkCapabilities.TRANSPORT_VPN)
                        && other.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)) {
                    return other;
                }
            }
        } catch (RuntimeException refused) {
            return null;
        }
        return null;
    }

    private static boolean online(NetworkCapabilities found) {
        return ApkpyKitRules.networkOnline(found != null,
                found != null && found.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET),
                found != null && found.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED));
    }

    private static String kind(NetworkCapabilities found) {
        return ApkpyKitRules.networkKind(found != null,
                found != null && found.hasTransport(NetworkCapabilities.TRANSPORT_WIFI),
                found != null && found.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR),
                found != null && found.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET));
    }

    private static boolean metered(NetworkCapabilities found) {
        return ApkpyKitRules.networkMetered(found != null,
                found != null && found.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_METERED));
    }

    private static String state(Context context) {
        NetworkCapabilities found = capabilities(context);
        return ApkpyKitRules.networkState(online(found), kind(found), metered(found));
    }

    /** One listener for the whole app, kept for as long as the app runs. */
    private static boolean listen(Context context) {
        if (listening) return true;
        try {
            ConnectivityManager manager = manager(context);
            if (manager == null) return false;
            manager.registerDefaultNetworkCallback(HEARS);
        } catch (RuntimeException refused) {
            return false;
        }
        listening = true;
        return true;
    }

    private static final ConnectivityManager.NetworkCallback HEARS =
            new ConnectivityManager.NetworkCallback() {
        @Override public void onAvailable(Network network) {
            // Since Android 8 what the connection is made of always follows.
            // Before it, it may not: what is kept could be the connection
            // that was there before, so the phone is asked again instead.
            if (Build.VERSION.SDK_INT < 26) reported = false;
            changed();
        }

        @Override public void onCapabilitiesChanged(Network network, NetworkCapabilities found) {
            connection = network;
            current = found;
            reported = true;
            changed();
        }

        @Override public void onLost(Network network) {
            // Going from Wi-Fi to mobile data, the old one can be lost after
            // the new one is already here: only the loss of the one in use
            // leaves the phone with none.
            if (reported && network.equals(connection)) current = null;
            changed();
        }
    };

    /** Called on Android's own thread; the screens are told on theirs. */
    private static void changed() {
        MAIN.removeCallbacks(TELL);
        MAIN.post(TELL);
    }

    private static final Runnable TELL = new Runnable() {
        @Override public void run() {
            for (Activity activity : new ArrayList<>(WATCHES.keySet())) tell(activity);
        }
    };

    private static void tell(Activity activity) {
        Watch mine = WATCHES.get(activity);
        if (mine == null || mine.names.isEmpty()) return;
        if (activity.isDestroyed() || !shown(activity)) return;       // it waits for the screen
        String now = state(activity);
        if (now.equals(mine.heard)) return;
        mine.heard = now;
        WeakReference<Calls> held = CALLS.get(activity);
        Calls calls = held == null ? null : held.get();
        if (calls == null) return;
        for (String name : new ArrayList<>(mine.names)) calls.call(name);
    }

    // --- the screens ---------------------------------------------------------

    /** Whether the screen is on show; see ApkpyTimers.shown(). */
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

    private static final Application.ActivityLifecycleCallbacks WATCH =
            new Application.ActivityLifecycleCallbacks() {
        @Override public void onActivityCreated(Activity activity, Bundle saved) { }

        @Override public void onActivityStarted(Activity activity) {
            SHOWN.put(activity, Boolean.TRUE);
            // What changed while the screen was away, and still is changed.
            if (WATCHES.containsKey(activity)) changed();
        }

        @Override public void onActivityResumed(Activity activity) { }

        @Override public void onActivityPaused(Activity activity) { }

        @Override public void onActivityStopped(Activity activity) {
            SHOWN.put(activity, Boolean.FALSE);
        }

        @Override public void onActivitySaveInstanceState(Activity activity, Bundle out) { }

        @Override public void onActivityDestroyed(Activity activity) {
            SHOWN.remove(activity);
            CALLS.remove(activity);
            Watch mine = WATCHES.remove(activity);
            if (mine != null && !mine.names.isEmpty() && activity.isChangingConfigurations()) {
                HANDED_ON.put(activity.getClass().getName(),
                        new Left(mine, SystemClock.elapsedRealtime()));
            }
        }
    };
}
