package __PACKAGE__;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.provider.AlarmClock;

/**
 * clock.alarm() and clock.timer() -- set in the phone's clock app.
 *
 * The clock app keeps them, so they ring with this app closed, after the
 * phone restarts, with Do Not Disturb on: everything an alarm of the app's
 * own would have to fight for. The clock opens on what was set, so the
 * person sees it. The permission is a normal one: nobody is asked.
 */
public final class ApkpyClock {

    private ApkpyClock() { }

    private static String open(Activity activity, Intent intent) {
        try {
            activity.startActivity(intent);
            return "ok";
        } catch (ActivityNotFoundException nobody) {
            return "no_app";
        } catch (SecurityException refused) {
            return "no_app";
        }
    }

    public static String alarm(Activity activity, String hour, String minute, String label) {
        int[] time = ApkpyKitRules.clockAlarm(hour, minute);
        if (time == null) return "invalid";
        Intent intent = new Intent(AlarmClock.ACTION_SET_ALARM);
        intent.putExtra(AlarmClock.EXTRA_HOUR, time[0]);
        intent.putExtra(AlarmClock.EXTRA_MINUTES, time[1]);
        String said = ApkpyKit.text(label).trim();
        if (!said.isEmpty()) intent.putExtra(AlarmClock.EXTRA_MESSAGE, said);
        return open(activity, intent);
    }

    public static String timer(Activity activity, String seconds, String label) {
        long length = ApkpyKitRules.clockSeconds(seconds);
        if (length < 0) return "invalid";
        Intent intent = new Intent(AlarmClock.ACTION_SET_TIMER);
        intent.putExtra(AlarmClock.EXTRA_LENGTH, (int) length);
        String said = ApkpyKit.text(label).trim();
        if (!said.isEmpty()) intent.putExtra(AlarmClock.EXTRA_MESSAGE, said);
        // Started at once, and shown: the person sees it counting.
        intent.putExtra(AlarmClock.EXTRA_SKIP_UI, false);
        return open(activity, intent);
    }
}
