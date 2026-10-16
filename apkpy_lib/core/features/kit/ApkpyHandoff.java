package __PACKAGE__;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.provider.CalendarContract;

import java.util.TimeZone;

/**
 * calendar.add_event(), phone.dial() and phone.sms() -- the app hands over.
 *
 * None of these does the thing itself. Each opens the phone's own app for it
 * with everything filled in, and the person presses the last button: save,
 * call, send. That is why there is no permission here. Placing a call or
 * sending a message without the person pressing anything is a different
 * permission, one Google Play only allows to an app that is the phone's
 * dialler or its messages app.
 */
public final class ApkpyHandoff {

    private ApkpyHandoff() { }

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

    /** The dialler, on this number. */
    public static String dial(Activity activity, String number) {
        String digits = ApkpyKitRules.phoneNumber(number);
        if (digits.isEmpty()) return "invalid";
        return open(activity, new Intent(Intent.ACTION_DIAL,
                Uri.fromParts("tel", digits, null)));
    }

    /** A message to this number, with the text written. */
    public static String sms(Activity activity, String number, String text) {
        String digits = ApkpyKitRules.phoneNumber(number);
        if (digits.isEmpty()) return "invalid";
        Intent intent = new Intent(Intent.ACTION_SENDTO, Uri.fromParts("smsto", digits, null));
        intent.putExtra("sms_body", ApkpyKit.text(text));
        return open(activity, intent);
    }

    /** The calendar's new-event screen, filled in. */
    public static String addEvent(Activity activity, String title, String start, String end,
                                  String location, String notes, String allDay) {
        long[] times = ApkpyKitRules.eventTimes(start, end, allDay, TimeZone.getDefault());
        if (times == null) return "invalid";
        Intent intent = new Intent(Intent.ACTION_INSERT, CalendarContract.Events.CONTENT_URI);
        intent.putExtra(CalendarContract.Events.TITLE, ApkpyKit.text(title));
        intent.putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, times[0]);
        intent.putExtra(CalendarContract.EXTRA_EVENT_END_TIME, times[1]);
        intent.putExtra(CalendarContract.EXTRA_EVENT_ALL_DAY, times[2] == 1L);
        if (!ApkpyKit.text(location).trim().isEmpty()) {
            intent.putExtra(CalendarContract.Events.EVENT_LOCATION, location);
        }
        if (!ApkpyKit.text(notes).trim().isEmpty()) {
            intent.putExtra(CalendarContract.Events.DESCRIPTION, notes);
        }
        return open(activity, intent);
    }
}
