package __PACKAGE__;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;

/**
 * phone.call() -- the app places the call itself.
 *
 * phone.dial() opens the dialler and the person presses call; this one rings
 * at once, so Android asks the person, the first time, whether the app may
 * make calls. Google Play lets any app have that permission (CALL_PHONE): it
 * is reading the call log and sending messages that it keeps for the phone's
 * own dialler and messages app.
 */
public final class ApkpyCall {

    private ApkpyCall() { }

    /** Call. done: (true, "ok") once the call is placed, or (false, why not). */
    public static void call(final Activity activity, String number, final ApkpyKit.Done done) {
        final String digits = ApkpyKitRules.phoneNumber(number);
        if (digits.isEmpty()) {
            ApkpyKit.answer(done, false, "invalid");
            return;
        }
        if (!activity.getPackageManager().hasSystemFeature(PackageManager.FEATURE_TELEPHONY)) {
            ApkpyKit.answer(done, false, "no_phone");
            return;
        }
        ApkpyKitActivity.forPermission(activity, Manifest.permission.CALL_PHONE,
                new ApkpyKitActivity.Granted() {
                    @Override public void run(boolean granted, boolean blocked) {
                        if (!granted) {
                            ApkpyKit.answer(done, false,
                                    blocked ? "permission_blocked" : "permission_denied");
                            return;
                        }
                        try {
                            activity.startActivity(new Intent(Intent.ACTION_CALL,
                                    Uri.fromParts("tel", digits, null)));
                            ApkpyKit.answer(done, true, "ok");
                        } catch (ActivityNotFoundException nobody) {
                            ApkpyKit.answer(done, false, "no_app");
                        } catch (SecurityException refused) {
                            ApkpyKit.answer(done, false, "permission_denied");
                        }
                    }
                });
    }
}
