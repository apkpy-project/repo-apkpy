package __PACKAGE__;

import java.util.Calendar;
import java.util.GregorianCalendar;
import java.util.TimeZone;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * How the text an app passes is read: apkpy_lib/kit_rules.py again, in Java.
 *
 * Nothing in here touches Android, on purpose. The Previewer answers the same
 * questions with the Python functions, and a test compiles this file and asks
 * both the same texts; a class that needed a phone could not be asked.
 */
public final class ApkpyKitRules {

    private static final String NUMBER = "__NUMBER__";
    private static final Pattern WHEN = Pattern.compile(
            "([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})"
            + "(?:[ T]([0-9]{1,2}):([0-9]{2})(?::([0-9]{2}))?)?");
    private static final String WEB = "__WEB__";
    private static final Pattern WHOLE_PAGE = Pattern.compile("<html", Pattern.CASE_INSENSITIVE);

    private ApkpyKitRules() { }

    /** Python's str.strip() and Java's trim() disagree past ASCII; this is the rule. */
    public static String trim(String text) {
        if (text == null) return "";
        int start = 0, end = text.length();
        while (start < end && text.charAt(start) <= ' ') start++;
        while (end > start && text.charAt(end - 1) <= ' ') end--;
        return text.substring(start, end);
    }

    /** The number in the text, or the fallback when it is not one. */
    public static double number(String text, double fallback) {
        String trimmed = trim(text);
        if (!trimmed.matches(NUMBER)) return fallback;
        double value;
        try {
            value = Double.parseDouble(trimmed);
        } catch (NumberFormatException notOne) {
            return fallback;
        }
        if (Double.isNaN(value) || Double.isInfinite(value)) return fallback;
        return value;
    }

    /** The nearest whole number, halves to even, as Python rounds. */
    public static long whole(String text, long fallback) {
        double value = number(text, (double) fallback);
        if (Math.abs(value) >= 9.0e18) return fallback;
        return (long) Math.rint(value);
    }

    public static boolean truth(String text) {
        return trim(text).equalsIgnoreCase("true");
    }

    /** A yes or no as the app reads it: Python's spelling. */
    public static String flag(boolean value) {
        return value ? "True" : "False";
    }

    public static double clamp(double value, double low, double high) {
        return Math.max(low, Math.min(high, value));
    }

    /** {year, month, day, hour, minute, second, has a time: 1 or 0}, or null. */
    public static int[] when(String text) {
        Matcher found = WHEN.matcher(trim(text));
        if (!found.matches()) return null;
        boolean hasTime = found.group(4) != null;
        int[] parts = {
            Integer.parseInt(found.group(1)), Integer.parseInt(found.group(2)),
            Integer.parseInt(found.group(3)),
            hasTime ? Integer.parseInt(found.group(4)) : 0,
            hasTime ? Integer.parseInt(found.group(5)) : 0,
            found.group(6) != null ? Integer.parseInt(found.group(6)) : 0,
            hasTime ? 1 : 0,
        };
        // The 30th of February is not a date, and a lenient calendar would
        // quietly make it the 2nd of March.
        if (parts[0] < 1 || parts[1] < 1 || parts[1] > 12 || parts[2] < 1
                || parts[3] > 23 || parts[4] > 59 || parts[5] > 59) {
            return null;
        }
        GregorianCalendar check = new GregorianCalendar(TimeZone.getTimeZone("UTC"));
        // Python counts every year by today's leap rule; so does this.
        check.setGregorianChange(new java.util.Date(Long.MIN_VALUE));
        check.clear();
        check.set(Calendar.YEAR, parts[0]);
        check.set(Calendar.MONTH, parts[1] - 1);
        if (parts[2] > check.getActualMaximum(Calendar.DAY_OF_MONTH)) return null;
        return parts;
    }

    private static long millis(int[] parts, boolean wholeDay, int extraDays, TimeZone zone) {
        GregorianCalendar calendar = new GregorianCalendar(zone);
        calendar.clear();
        calendar.set(parts[0], parts[1] - 1, parts[2],
                wholeDay ? 0 : parts[3], wholeDay ? 0 : parts[4], wholeDay ? 0 : parts[5]);
        calendar.add(Calendar.DAY_OF_MONTH, extraDays);
        return calendar.getTimeInMillis();
    }

    /**
     * What calendar.add_event makes of start, end and all_day:
     * {begin, finish, whole day: 1 or 0}, or null when they cannot be read.
     *
     * A whole-day event is counted in UTC, which is how a calendar stores a
     * day that has no hour; one with a time is counted in the zone given.
     */
    public static long[] eventTimes(String start, String end, String allDay, TimeZone zone) {
        int[] first = when(start);
        if (first == null) return null;
        boolean wholeDay = truth(allDay) || first[6] == 0;
        TimeZone counted = wholeDay ? TimeZone.getTimeZone("UTC") : zone;
        long begin = millis(first, wholeDay, 0, counted);
        long finish;
        if (!trim(end).isEmpty()) {
            int[] last = when(end);
            if (last == null) return null;
            finish = millis(last, wholeDay, wholeDay ? 1 : 0, counted);
        } else {
            finish = wholeDay ? millis(first, true, 1, counted) : begin + 3600000L;
        }
        if (finish <= begin) return null;
        return new long[] { begin, finish, wholeDay ? 1L : 0L };
    }

    /**
     * What health.read makes of its two times: {begin, finish}, or null.
     *
     * Nothing given is today so far. A start with no hour is that day's
     * midnight; an end with no hour is the whole of that day. No end is now.
     */
    public static long[] healthPeriod(String start, String end, long now, TimeZone zone) {
        String givenStart = trim(start);
        String givenEnd = trim(end);
        long begin;
        if (!givenStart.isEmpty()) {
            int[] first = when(givenStart);
            if (first == null) return null;
            begin = millis(first, false, 0, zone);
        } else {
            GregorianCalendar today = new GregorianCalendar(zone);
            today.setTimeInMillis(now);
            today.set(Calendar.HOUR_OF_DAY, 0);
            today.set(Calendar.MINUTE, 0);
            today.set(Calendar.SECOND, 0);
            today.set(Calendar.MILLISECOND, 0);
            begin = today.getTimeInMillis();
        }
        long finish;
        if (!givenEnd.isEmpty()) {
            int[] last = when(givenEnd);
            if (last == null) return null;
            finish = millis(last, false, last[6] == 1 ? 0 : 1, zone);
        } else {
            finish = now;
            // Asked at midnight exactly: today has only just begun.
            if (givenStart.isEmpty() && finish <= begin) finish = begin + 1000L;
        }
        if (finish <= begin) return null;
        return new long[] { begin, finish };
    }

    /** A reading as the text an app gets: whole, except what is weighed or poured. */
    public static String healthValue(String kind, double number) {
        int places = "weight".equals(kind) ? 1 : "hydration".equals(kind) ? 2 : 0;
        // Half to even on the number as it is held, which is what Python's
        // "%.1f" and round() do: the two sides print the same digits.
        return new java.math.BigDecimal(number)
                .setScale(places, java.math.RoundingMode.HALF_EVEN).toPlainString();
    }

    private static final Pattern AD_UNIT = Pattern.compile("ca-app-pub-[0-9]{16}/[0-9]{10}");

    /** The ad unit, Google's sample of that kind for "test", or "". */
    public static String adUnit(String text, String kind) {
        String given = trim(text);
        if (given.equals("test")) {
            if ("banner".equals(kind)) return "__ADS_TEST_BANNER__";
            if ("interstitial".equals(kind)) return "__ADS_TEST_INTERSTITIAL__";
            return "__ADS_TEST_REWARDED__";
        }
        return AD_UNIT.matcher(given).matches() ? given : "";
    }

    /** The address when it is an http(s) one, else "". */
    public static String webAddress(String text) {
        String trimmed = trim(text);
        return trimmed.matches(WEB) ? trimmed : "";
    }

    /** HTML an app wrote, as a whole page: left alone when it is one already. */
    public static String document(String markup, String css) {
        String text = markup == null ? "" : markup;
        if (WHOLE_PAGE.matcher(text).find()) return text;
        return "<!doctype html><html><head><meta charset=\"utf-8\">"
                + "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                + "<style>" + css + "</style></head><body>" + text + "</body></html>";
    }

    private static final String FILE_FORBIDDEN = "<>:\"|?*\\";
    private static final java.util.List<String> FILE_DEVICES = java.util.Arrays.asList(
            "CON", "PRN", "AUX", "NUL",
            "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
            "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9");

    /**
     * The name of a file in the app's folder as given, or "" when it is not
     * one. A name the desk cannot write is refused here too, so an app that
     * works in the Previewer works on the phone.
     */
    public static String fileName(String text) {
        String given = trim(text);
        if (given.isEmpty()) return "";
        for (String part : given.split("/", -1)) {
            if (part.isEmpty() || part.equals(".") || part.equals("..")) return "";
            char last = part.charAt(part.length() - 1);
            if (part.charAt(0) == ' ' || last == ' ' || last == '.') return "";
            for (int i = 0; i < part.length(); i++) {
                char ch = part.charAt(i);
                if (ch < 32 || ch == 127 || FILE_FORBIDDEN.indexOf(ch) >= 0) return "";
            }
            int dot = part.indexOf('.');
            String stem = dot < 0 ? part : part.substring(0, dot);
            if (FILE_DEVICES.contains(stem.toUpperCase(java.util.Locale.ROOT))
                    || part.startsWith(".apkpy-")) {
                return "";
            }
            if (part.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > 255) return "";
        }
        return given;
    }

    /** Seconds as the whole milliseconds a timer waits, or -1 when it is not a time. */
    public static long timerMillis(String seconds, boolean repeating) {
        double value = number(seconds, -1.0);
        if (value < 0) return -1L;
        long millis = (long) Math.rint(Math.min(value * 1000.0, (double) __TIMER_LONGEST__L));
        return repeating ? Math.max(__TIMER_SHORTEST__L, millis) : millis;
    }

    /**
     * When an every() runs next, having just run at {@code now} what was due
     * at {@code due}. A little late, the next moment of its own grid; a whole
     * period late or more -- the screen was away -- a full period from now,
     * so the run that catches up is not followed at once by another.
     */
    public static long timerNext(long due, long period, long now) {
        if (now - due >= period) return now + period;
        return due + period;
    }

    /** network.kind(): what the connection is, the first of these that is true. */
    public static String networkKind(boolean connected, boolean wifi, boolean mobile,
                                     boolean ethernet) {
        if (!connected) return "none";
        if (wifi) return "wifi";
        if (mobile) return "mobile";
        if (ethernet) return "ethernet";
        return "other";
    }

    /** A connection that is meant to reach the internet, and has been seen to. */
    public static boolean networkOnline(boolean connected, boolean internet, boolean validated) {
        return connected && internet && validated;
    }

    /** Nothing is paid for a connection that is not there. */
    public static boolean networkMetered(boolean connected, boolean unmetered) {
        return connected && !unmetered;
    }

    /** The three answers as one text: a screen hears again when it is another. */
    public static String networkState(boolean online, String kind, boolean metered) {
        return (online ? "online" : "offline") + " " + kind + (metered ? " metered" : "");
    }

    /** Lower case for A to Z and nothing else, which is all a word of the table has. */
    private static String lower(String text) {
        String trimmed = trim(text);
        StringBuilder out = new StringBuilder(trimmed.length());
        for (int i = 0; i < trimmed.length(); i++) {
            char ch = trimmed.charAt(i);
            out.append(ch >= 'A' && ch <= 'Z' ? (char) (ch + 32) : ch);
        }
        return out.toString();
    }

    /** display.orientation(): "auto", "portrait" or "landscape", or "" for anything else. */
    public static String displayOrientation(String text) {
        String kind = lower(text);
        return "auto".equals(kind) || "portrait".equals(kind) || "landscape".equals(kind)
                ? kind : "";
    }

    /**
     * display.brightness(): 0 to 1, -1 for "auto" (the phone's own) and -2 for
     * anything else. A number outside 0 to 1 is not brought inside it.
     */
    public static double displayBrightness(String text) {
        if ("auto".equals(lower(text))) return -1.0;
        double level = number(text, -2.0);
        if (!(level >= 0.0 && level <= 1.0)) return -2.0;
        return level + 0.0;
    }

    /** The minutes in the text, 0 or more; -1.0 when it is not a number of minutes. */
    public static double appLockMinutes(String text) {
        double minutes = number(text, -1.0);
        if (minutes < 0.0) return -1.0;
        return minutes + 0.0;
    }

    /** Whether an app gone from the front at leftAt (wall clock, ms; 0 or less
     *  when not known) is to be locked as it comes back at now. Not knowing,
     *  and a clock that went backwards, both lock. */
    public static boolean appLockDue(long leftAt, long now, double minutes) {
        if (leftAt <= 0L || now < leftAt) return true;
        return (now - leftAt) >= minutes * 60000.0;
    }

    /** What the cover says over the padlock. */
    public static String appLockHeading(String appName) {
        String name = trim(appName);
        return name.length() > 0 ? name + " is locked" : "The app is locked";
    }

    /** The prompt's title: the app's own words, or "Unlock" and its name. */
    public static String appLockTitle(String title, String appName) {
        String said = trim(title);
        if (said.length() > 0) return said;
        String name = trim(appName);
        return "Unlock " + (name.length() > 0 ? name : "the app");
    }

    /** The number as the dialler takes it, or "" when no digit is left. */
    public static String phoneNumber(String text) {
        StringBuilder kept = new StringBuilder();
        boolean digit = false;
        String given = text == null ? "" : text;
        for (int i = 0; i < given.length(); i++) {
            char ch = given.charAt(i);
            if (ch >= '0' && ch <= '9') {
                digit = true;
                kept.append(ch);
            } else if ("+*#,;".indexOf(ch) >= 0) {
                kept.append(ch);
            }
        }
        return digit ? kept.toString() : "";
    }
}
