package __PACKAGE__;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;

/**
 * Where "why does this app want my health data?" leads.
 *
 * Health Connect puts a link to the app's privacy policy on the screen where
 * the person decides, and refuses to ask at all for an app that has nowhere
 * for that link to go. This is where it goes: the address the app declared
 * with health.policy(), opened in the browser.
 */
public final class ApkpyHealthPolicyActivity extends Activity {

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(ApkpyHealth.POLICY)));
        } catch (Throwable nobody) {
            // No browser on the phone: there is nothing to show it with.
        }
        finish();
        overridePendingTransition(0, 0);
    }
}
