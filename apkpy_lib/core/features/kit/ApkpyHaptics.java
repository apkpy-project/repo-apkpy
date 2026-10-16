package __PACKAGE__;

import android.app.Activity;
import android.content.Context;
import android.os.Build;
import android.os.VibrationAttributes;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.os.VibratorManager;
import android.provider.Settings;
import android.view.HapticFeedbackConstants;
import android.view.View;

/**
 * haptics.* -- a touch you can feel.
 *
 * Two different things share the motor, and the owner of the phone has a
 * switch for each.
 *
 * tap(), tick(), heavy(), success() and error() are touch feedback: Android's
 * own effect for each, tuned to this phone's motor, with no permission. They
 * follow the touch-feedback setting -- a phone with it off stays still, and
 * that is the right outcome rather than something to work around.
 *
 * vibrate(ms) is the app itself buzzing: a timer that ended, a hit in a game.
 * It runs the motor for a length of time, which is the VIBRATE permission
 * (granted at install, never asked for). Left to guess, Android takes a short
 * vibration for touch feedback and drops it on a phone that has the clicks of
 * the keyboard switched off; so this one says what it is -- the app's own, the
 * kind a game makes -- and follows the phone's vibration switch instead.
 *
 * Either answers "off" when the setting it follows is off. Android reports a
 * request it then ignores as performed, so the settings are read here: an app
 * should be told the truth.
 */
public final class ApkpyHaptics {

    private ApkpyHaptics() { }

    private static int constant(String kind) {
        boolean modern = Build.VERSION.SDK_INT >= 30;
__FEEDBACK_ARMS__
        return HapticFeedbackConstants.VIRTUAL_KEY;
    }

    private static int setting(Context context, String name, int fallback) {
        try {
            return Settings.System.getInt(context.getContentResolver(), name, fallback);
        } catch (Throwable unreadable) {
            // Not every phone lets an app read every one of these; one that
            // will not say is taken to have it on.
            return fallback;
        }
    }

    /** The phone's one switch for every vibration (Android 13 on). */
    private static boolean motorOn(Context context) {
        return setting(context, "vibrate_on", 1) != 0;
    }

    /**
     * Whether touch feedback is on. Android keeps it under two names: the
     * older yes-or-no, and the strength the vibrator obeys, where 0 is off.
     * A phone can have the first on and the second at 0 -- one was seen, with
     * its own settings screen showing it on -- and it stays still.
     */
    private static boolean touchOn(Context context) {
        return motorOn(context)
                && setting(context, Settings.System.HAPTIC_FEEDBACK_ENABLED, 1) != 0
                && setting(context, "haptic_feedback_intensity", 1) != 0;
    }

    /** Whether a vibration of the app's own is on: a setting since Android 13. */
    private static boolean buzzOn(Context context) {
        return motorOn(context) && setting(context, "media_vibration_intensity", 1) != 0;
    }

    /** One of Android's own touch effects, on the window of this screen. */
    public static String feedback(Activity activity, String kind) {
        if (activity == null || activity.getWindow() == null) return "off";
        View view = activity.getWindow().getDecorView();
        if (view == null) return "off";
        boolean asked = view.performHapticFeedback(constant(kind));
        return asked && touchOn(activity) ? "ok" : "off";
    }

    private static Vibrator vibrator(Context context) {
        try {
            if (Build.VERSION.SDK_INT >= 31) {
                VibratorManager manager = (VibratorManager)
                        context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE);
                return manager == null ? null : manager.getDefaultVibrator();
            }
            return (Vibrator) context.getSystemService(Context.VIBRATOR_SERVICE);
        } catch (Throwable unavailable) {
            return null;
        }
    }

    /** The motor, for this many milliseconds. */
    public static String vibrate(Activity activity, String ms) {
        Vibrator motor = vibrator(activity.getApplicationContext());
        if (motor == null || !motor.hasVibrator()) return "no_vibrator";
        long length = (long) ApkpyKit.clamp(
                (double) ApkpyKit.whole(ms, __DEFAULT_MS__L), __MIN_MS__, __MAX_MS__);
        try {
            if (Build.VERSION.SDK_INT >= 33) {
                motor.vibrate(
                        VibrationEffect.createOneShot(length, VibrationEffect.DEFAULT_AMPLITUDE),
                        VibrationAttributes.createForUsage(VibrationAttributes.USAGE_MEDIA));
            } else if (Build.VERSION.SDK_INT >= 26) {
                // Before Android 13 there is no word for it, and no setting
                // of its own either: the phone decides.
                motor.vibrate(VibrationEffect.createOneShot(
                        length, VibrationEffect.DEFAULT_AMPLITUDE));
            } else {
                motor.vibrate(length);
            }
        } catch (Throwable refused) {
            return "off";
        }
        return Build.VERSION.SDK_INT < 33 || buzzOn(activity) ? "ok" : "off";
    }

    public static String available(Activity activity) {
        Vibrator motor = vibrator(activity.getApplicationContext());
        return ApkpyKit.flag(motor != null && motor.hasVibrator());
    }
}
