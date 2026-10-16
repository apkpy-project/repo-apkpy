package __PACKAGE__;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.IntentSender;
import android.os.Build;
import android.os.Bundle;

import com.google.android.gms.tasks.OnFailureListener;
import com.google.android.gms.tasks.OnSuccessListener;
import com.google.android.play.core.appupdate.AppUpdateInfo;
import com.google.android.play.core.appupdate.AppUpdateManager;
import com.google.android.play.core.appupdate.AppUpdateManagerFactory;
import com.google.android.play.core.appupdate.AppUpdateOptions;
import com.google.android.play.core.common.IntentSenderForResultStarter;
import com.google.android.play.core.install.InstallException;
import com.google.android.play.core.install.InstallState;
import com.google.android.play.core.install.InstallStateUpdatedListener;
import com.google.android.play.core.install.model.AppUpdateType;
import com.google.android.play.core.install.model.InstallErrorCode;
import com.google.android.play.core.install.model.InstallStatus;
import com.google.android.play.core.install.model.UpdateAvailability;

/**
 * updates.* -- a newer version of the app, from Google Play, inside the app.
 *
 * Play knows whether the copy on this phone is the newest. check() asks it;
 * start() has Play download the new one, either behind the app while the
 * person carries on ("flexible") or over the whole screen until it is done
 * ("immediate"); install() restarts the app into what a flexible update
 * downloaded.
 *
 * All of it is Play's: the question, the screens, the download. A copy of
 * the app that did not come from Play -- one built and installed over a
 * cable -- has nothing to be compared with, and every call says so.
 */
public final class ApkpyUpdates {

    private static AppUpdateManager sManager;
    private static InstallStateUpdatedListener sWatching;
    private static volatile boolean sDownloaded;

    private ApkpyUpdates() { }

    private static synchronized AppUpdateManager manager(Context context) {
        if (sManager == null) {
            sManager = AppUpdateManagerFactory.create(context.getApplicationContext());
        }
        return sManager;
    }

    @SuppressWarnings("deprecation")
    private static boolean fromPlay(Context context) {
        try {
            String installer;
            if (Build.VERSION.SDK_INT >= 30) {
                installer = context.getPackageManager()
                        .getInstallSourceInfo(context.getPackageName()).getInstallingPackageName();
            } else {
                installer = context.getPackageManager()
                        .getInstallerPackageName(context.getPackageName());
            }
            return "com.android.vending".equals(installer);
        } catch (Throwable unknown) {
            return false;
        }
    }

    private static String word(Context context, Exception problem) {
        if (problem instanceof InstallException) {
            int code = ((InstallException) problem).getErrorCode();
            if (code == InstallErrorCode.ERROR_APP_NOT_OWNED
                    || code == InstallErrorCode.ERROR_PLAY_STORE_NOT_FOUND) {
                return "not_from_play";
            }
            if (code == InstallErrorCode.ERROR_INSTALL_NOT_ALLOWED) return "not_allowed";
        }
        return fromPlay(context) ? "failed" : "not_from_play";
    }

    private interface Known {
        void run(AppUpdateInfo info, String problem);
    }

    private static void ask(final Context context, final Known then) {
        // Play answers "no update" for an app it never installed. That is
        // true and tells nobody anything: a copy from a cable can never be
        // told anything else, so it is told what it is.
        if (!fromPlay(context)) {
            then.run(null, "not_from_play");
            return;
        }
        try {
            manager(context).getAppUpdateInfo()
                    .addOnSuccessListener(new OnSuccessListener<AppUpdateInfo>() {
                        @Override public void onSuccess(AppUpdateInfo info) {
                            if (info == null) {
                                then.run(null, word(context, null));
                                return;
                            }
                            sDownloaded = info.installStatus() == InstallStatus.DOWNLOADED;
                            then.run(info, "");
                        }
                    })
                    .addOnFailureListener(new OnFailureListener() {
                        @Override public void onFailure(Exception problem) {
                            then.run(null, word(context, problem));
                        }
                    });
        } catch (Throwable broken) {
            then.run(null, word(context, null));
        }
    }

    private static boolean newer(AppUpdateInfo info) {
        int found = info.updateAvailability();
        return found == UpdateAvailability.UPDATE_AVAILABLE
                || found == UpdateAvailability.DEVELOPER_TRIGGERED_UPDATE_IN_PROGRESS;
    }

    /** (true, "available" or "downloaded"), or (false, why there is nothing to do). */
    public static void check(Activity activity, final ApkpyKit.Done done) {
        ask(activity.getApplicationContext(), new Known() {
            @Override public void run(AppUpdateInfo info, String problem) {
                if (info == null) ApkpyKit.answer(done, false, problem);
                else if (sDownloaded) ApkpyKit.answer(done, true, "downloaded");
                else if (newer(info)) ApkpyKit.answer(done, true, "available");
                else ApkpyKit.answer(done, false, "none");
            }
        });
    }

    public static void start(final Activity activity, String mode, final ApkpyKit.Done done) {
        final boolean immediate = "immediate".equals(ApkpyKitRules.trim(mode));
        final Context app = activity.getApplicationContext();
        ask(app, new Known() {
            @Override public void run(AppUpdateInfo info, String problem) {
                if (info == null) {
                    ApkpyKit.answer(done, false, problem);
                } else if (sDownloaded) {
                    ApkpyKit.answer(done, true, "downloaded");
                } else if (!newer(info)) {
                    ApkpyKit.answer(done, false, "none");
                } else {
                    begin(activity, info, immediate, done);
                }
            }
        });
    }

    private static void begin(final Activity activity, AppUpdateInfo info,
                              final boolean immediate, final ApkpyKit.Done done) {
        final Context app = activity.getApplicationContext();
        int type = immediate ? AppUpdateType.IMMEDIATE : AppUpdateType.FLEXIBLE;
        if (!info.isUpdateTypeAllowed(type)) {
            ApkpyKit.answer(done, false, "not_allowed");
            return;
        }
        if (activity.isFinishing() || activity.isDestroyed()) {
            ApkpyKit.answer(done, false, "cancelled");
            return;
        }
        try {
            // Play hands over its own screen sealed; the invisible Activity
            // opens it and hears what the person chose there.
            boolean opened = manager(app).startUpdateFlowForResult(info,
                    new IntentSenderForResultStarter() {
                        @Override public void startIntentSenderForResult(
                                IntentSender sender, int requestCode, Intent fillIn,
                                int flagsMask, int flagsValues, int extraFlags, Bundle options) {
                            ApkpyKitActivity.forSender(activity, sender,
                                    new ApkpyKitActivity.Result() {
                                        @Override public void run(int resultCode, Intent data) {
                                            chosen(app, resultCode, immediate, done);
                                        }
                                    });
                        }
                    }, AppUpdateOptions.newBuilder(type).build(), 1);
            if (!opened) ApkpyKit.answer(done, false, "failed");
        } catch (Throwable broken) {
            ApkpyKit.answer(done, false, "failed");
        }
    }

    private static void chosen(Context app, int resultCode, boolean immediate,
                               final ApkpyKit.Done done) {
        if (resultCode == Activity.RESULT_CANCELED) {
            ApkpyKit.answer(done, false, "cancelled");
        } else if (resultCode != Activity.RESULT_OK) {
            ApkpyKit.answer(done, false, "failed");
        } else if (immediate) {
            // Play installed it and is about to restart the app.
            ApkpyKit.answer(done, true, "ok");
        } else {
            watch(app, done);
        }
    }

    /** The person said yes to a flexible update: answer when it is on the phone. */
    private static synchronized void watch(final Context app, final ApkpyKit.Done done) {
        final AppUpdateManager manager = manager(app);
        if (sWatching != null) manager.unregisterListener(sWatching);
        sWatching = new InstallStateUpdatedListener() {
            @Override public void onStateUpdate(InstallState state) {
                int status = state.installStatus();
                if (status == InstallStatus.DOWNLOADED) {
                    sDownloaded = true;
                    stop(this);
                    ApkpyKit.answer(done, true, "downloaded");
                } else if (status == InstallStatus.FAILED) {
                    stop(this);
                    ApkpyKit.answer(done, false, "failed");
                } else if (status == InstallStatus.CANCELED) {
                    stop(this);
                    ApkpyKit.answer(done, false, "cancelled");
                }
            }

            private void stop(InstallStateUpdatedListener self) {
                synchronized (ApkpyUpdates.class) {
                    manager.unregisterListener(self);
                    if (sWatching == self) sWatching = null;
                }
            }
        };
        manager.registerListener(sWatching);
    }

    /** Restart into the version a flexible update downloaded. */
    public static String install(Activity activity) {
        if (!sDownloaded) return "nothing";
        try {
            manager(activity).completeUpdate();
            sDownloaded = false;
            return "ok";
        } catch (Throwable broken) {
            return "nothing";
        }
    }
}
