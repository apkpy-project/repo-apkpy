package __PACKAGE__;

import android.app.PendingIntent;
import android.content.Intent;
import android.os.Build;
import android.service.quicksettings.TileService;

/**
 * The app's tile, as quick settings sees it.
 *
 * The system binds to this for the moments it needs it -- the tile was
 * added, the app said it changed, the person tapped it -- and lets go again.
 * It is declared an active tile, so opening the quick settings panel does
 * not start the app's process just to ask a question whose answer has not
 * changed.
 */
public final class ApkpyTileService extends TileService {

    @Override
    public void onTileAdded() {
        ApkpyTile.refresh(getApplicationContext());
    }

    @Override
    public void onStartListening() {
        ApkpyTile.show(this, getQsTile());
    }

    @Override
    public void onClick() {
        if (isLocked()) {
            // Over the lock screen the app would open behind it; the person
            // unlocks first, and then it opens.
            unlockAndRun(new Runnable() {
                @Override public void run() {
                    open();
                }
            });
        } else {
            open();
        }
    }

    @SuppressWarnings("deprecation")
    private void open() {
        Intent launch = getPackageManager().getLaunchIntentForPackage(getPackageName());
        if (launch == null) return;
        // At its first screen, which is the one that asks how the person
        // arrived -- as with a link.
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        ApkpyTile.sOpened = true;
        try {
            if (Build.VERSION.SDK_INT >= 34) {
                startActivityAndCollapse(PendingIntent.getActivity(
                        this, 0, launch,
                        PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE));
            } else {
                startActivityAndCollapse(launch);
            }
        } catch (Throwable refused) {
            ApkpyTile.sOpened = false;
        }
    }
}
