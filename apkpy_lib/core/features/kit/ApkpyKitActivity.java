package __PACKAGE__;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.IntentSender;
import android.content.pm.PackageManager;
import android.os.Bundle;

/**
 * The screen that waits for another screen.
 *
 * Asking the system for something -- where to save a file, what was said, may
 * the microphone be used -- means opening a screen that is not ours and being
 * told later what happened there. Android delivers that answer to an Activity,
 * so this is one: invisible, opened for the length of the question, gone as
 * soon as the answer is in. The screens of the app never see it, which is why
 * a call written in one of them can be a single line.
 *
 * The one asking is kept in memory. If Android ends the app's process while
 * the other screen is up, the answer has nobody to go to and is dropped: the
 * app that comes back is a new one, at its first screen.
 */
public final class ApkpyKitActivity extends Activity {

    /** Another screen came back. NO_APP when there was none to open. */
    public interface Result {
        void run(int resultCode, Intent data);
    }

    /** A permission was answered. blocked: refused, and Android will not ask again. */
    public interface Granted {
        void run(boolean granted, boolean blocked);
    }

    public static final int NO_APP = -1000;

    private static final String ID = "apkpy.kit.id";
    private static final String TARGET = "apkpy.kit.target";
    private static final String PERMISSION = "apkpy.kit.permission";
    private static final String PERMISSIONS = "apkpy.kit.permissions";
    private static final String SENDER = "apkpy.kit.sender";
    private static final String LIGHT = "apkpy.kit.light";

    private static final java.util.HashMap<Integer, Object> WAITING =
            new java.util.HashMap<Integer, Object>();
    private static int sNext = 1;

    private int mId;
    private String mPermission;

    private static synchronized int keep(Object waiting) {
        int id = sNext++;
        WAITING.put(id, waiting);
        return id;
    }

    private static synchronized Object take(int id) {
        return WAITING.remove(id);
    }

    /** Open target and answer with what it gave back. */
    public static void forResult(Context from, Intent target, Result result) {
        Intent self = new Intent(from, ApkpyKitActivity.class);
        self.putExtra(ID, keep(result));
        self.putExtra(TARGET, target);
        open(from, self);
    }

    /** Ask for one permission; answers at once when it is already held. */
    public static void forPermission(Context from, String permission, Granted granted) {
        if (from.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED) {
            granted.run(true, false);
            return;
        }
        Intent self = new Intent(from, ApkpyKitActivity.class);
        self.putExtra(ID, keep(granted));
        self.putExtra(PERMISSION, permission);
        open(from, self);
    }

    /**
     * Ask for several permissions in one go; granted means every one of them.
     * Answers at once when they are all held already.
     */
    public static void forPermissions(Context from, String[] permissions, Granted granted) {
        boolean all = true;
        for (String permission : permissions) {
            all &= from.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED;
        }
        if (all) {
            granted.run(true, false);
            return;
        }
        Intent self = new Intent(from, ApkpyKitActivity.class);
        self.putExtra(ID, keep(granted));
        self.putExtra(PERMISSIONS, permissions);
        open(from, self);
    }

    /** Open a screen another app handed over sealed, and answer what it gave back. */
    public static void forSender(Context from, IntentSender sender, Result result) {
        Intent self = new Intent(from, ApkpyKitActivity.class);
        self.putExtra(ID, keep(result));
        self.putExtra(SENDER, sender);
        open(from, self);
    }

    private static void open(Context from, Intent self) {
        if (from instanceof Activity) {
            // This screen is see-through: the clock over it has to stay the
            // colour it is over the screen underneath.
            self.putExtra(LIGHT, ApkpyKit.lightBars((Activity) from));
        } else {
            self.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        }
        self.addFlags(Intent.FLAG_ACTIVITY_NO_ANIMATION);
        from.startActivity(self);
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        ApkpyKit.clearBars(getWindow(), getIntent().getBooleanExtra(
                LIGHT, !ApkpyKit.isNight(getResources())));
        mId = getIntent().getIntExtra(ID, 0);
        mPermission = getIntent().getStringExtra(PERMISSION);
        // Made again after the question was already put -- the other screen is
        // still up and will answer this instance.
        if (state != null) return;
        Intent target = getIntent().getParcelableExtra(TARGET);
        IntentSender sender = getIntent().getParcelableExtra(SENDER);
        String[] several = getIntent().getStringArrayExtra(PERMISSIONS);
        try {
            if (target != null) {
                startActivityForResult(target, 1);
            } else if (sender != null) {
                startIntentSenderForResult(sender, 1, null, 0, 0, 0);
            } else if (mPermission != null) {
                requestPermissions(new String[] { mPermission }, 2);
            } else if (several != null && several.length > 0) {
                requestPermissions(several, 2);
            } else {
                close();
            }
        } catch (ActivityNotFoundException nobody) {
            deliver(NO_APP, null);
        } catch (IntentSender.SendIntentException stale) {
            deliver(NO_APP, null);
        } catch (SecurityException refused) {
            deliver(NO_APP, null);
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        deliver(resultCode, data);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions,
                                           int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        boolean granted = results != null && results.length > 0;
        if (granted) {
            for (int result : results) granted &= result == PackageManager.PERMISSION_GRANTED;
        }
        // Refused with nothing more to explain: Android has stopped showing
        // the dialog, and only the settings screen can change the answer.
        boolean blocked = !granted && mPermission != null
                && !shouldShowRequestPermissionRationale(mPermission);
        Object waiting = take(mId);
        close();
        if (waiting instanceof Granted) ((Granted) waiting).run(granted, blocked);
    }

    private void deliver(int resultCode, Intent data) {
        Object waiting = take(mId);
        // The grant to read or write what the other screen handed over belongs
        // to this Activity, so the one waiting has to use it before the close
        // -- which is why it runs first.
        try {
            if (waiting instanceof Result) ((Result) waiting).run(resultCode, data);
        } finally {
            close();
        }
    }

    private void close() {
        finish();
        overridePendingTransition(0, 0);
    }
}
