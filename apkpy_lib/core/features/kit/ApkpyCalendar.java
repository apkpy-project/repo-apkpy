package __PACKAGE__;

import android.Manifest;
import android.app.Activity;
import android.content.ContentResolver;
import android.database.Cursor;
import android.provider.CalendarContract;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

/**
 * calendar.events() -- the events already in the phone's calendars.
 *
 * add_event() hands an event to the calendar app for the person to save, and
 * needs nothing. Reading is another matter: Android asks the person, the
 * first time, whether the app may see the calendar. The answer is JSON text,
 * one object per event in the order they start, which json.loads() makes a
 * list of dictionaries:
 *
 *   {"title", "start", "end", "all_day", "location", "notes", "calendar"}
 *
 * start and end are "2026-11-07 15:30" on the phone's clock. An event that
 * lasts all day has days for both, "2026-11-07", its last day as the end:
 * what add_event() takes. A repeating event is there once for each time it
 * happens inside the window. Only the calendars the person shows are read.
 */
public final class ApkpyCalendar {

    private static final String[] COLUMNS = {
            CalendarContract.Instances.TITLE,
            CalendarContract.Instances.BEGIN,
            CalendarContract.Instances.END,
            CalendarContract.Instances.ALL_DAY,
            CalendarContract.Instances.EVENT_LOCATION,
            CalendarContract.Instances.DESCRIPTION,
            CalendarContract.Instances.CALENDAR_DISPLAY_NAME,
    };

    private ApkpyCalendar() { }

    public static void events(final Activity activity, String start, String end,
                              final ApkpyKit.Done done) {
        final long[] window = ApkpyKitRules.calendarWindow(
                start, end, System.currentTimeMillis(), TimeZone.getDefault());
        if (window == null) {
            ApkpyKit.answer(done, false, "invalid");
            return;
        }
        final ContentResolver resolver = activity.getApplicationContext().getContentResolver();
        ApkpyKitActivity.forPermission(activity, Manifest.permission.READ_CALENDAR,
                new ApkpyKitActivity.Granted() {
                    @Override public void run(boolean granted, boolean blocked) {
                        if (!granted) {
                            ApkpyKit.answer(done, false,
                                    blocked ? "permission_blocked" : "permission_denied");
                            return;
                        }
                        // A month of a busy calendar is a query worth keeping
                        // off the screen's thread.
                        new Thread(new Runnable() {
                            @Override public void run() {
                                String read = read(resolver, window[0], window[1]);
                                if (read == null) ApkpyKit.answer(done, false, "failed");
                                else ApkpyKit.answer(done, true, read);
                            }
                        }, "apkpy-calendar").start();
                    }
                });
    }

    private static String read(ContentResolver resolver, long begin, long finish) {
        Cursor rows = null;
        try {
            // Instances, not Events: a weekly meeting is one event and many
            // instances, and the person means the instances.
            rows = CalendarContract.Instances.query(resolver, COLUMNS, begin, finish);
            if (rows == null) return null;
            SimpleDateFormat clock = new SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.US);
            SimpleDateFormat day = new SimpleDateFormat("yyyy-MM-dd", Locale.US);
            // A day with no hour is stored in UTC, from midnight to midnight.
            day.setTimeZone(TimeZone.getTimeZone("UTC"));
            JSONArray out = new JSONArray();
            while (rows.moveToNext()) {
                boolean allDay = rows.getInt(3) != 0;
                long from = rows.getLong(1);
                long to = rows.getLong(2);
                JSONObject event = new JSONObject();
                event.put("title", ApkpyKit.text(rows.getString(0)));
                if (allDay) {
                    event.put("start", day.format(new Date(from)));
                    // Stored ending at the start of the day after its last.
                    event.put("end", day.format(new Date(Math.max(from, to - 1L))));
                } else {
                    event.put("start", clock.format(new Date(from)));
                    event.put("end", clock.format(new Date(to)));
                }
                event.put("all_day", allDay);
                event.put("location", ApkpyKit.text(rows.getString(4)));
                event.put("notes", ApkpyKit.text(rows.getString(5)));
                event.put("calendar", ApkpyKit.text(rows.getString(6)));
                out.put(event);
            }
            return out.toString();
        } catch (RuntimeException failed) {
            // A permission taken away while it read, or a provider that broke.
            return null;
        } catch (JSONException failed) {
            return null;
        } finally {
            if (rows != null) rows.close();
        }
    }
}
