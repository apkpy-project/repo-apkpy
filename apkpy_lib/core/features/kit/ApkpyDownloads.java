package __PACKAGE__;

import android.app.Activity;
import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.webkit.URLUtil;

import java.util.HashMap;

/**
 * downloads.start() -- a download the phone does itself.
 *
 * files.download() fetches into the app's own folder while the app is open.
 * This one is handed to Android's download service instead: it carries on
 * with the app closed, survives a lost connection, shows its progress in the
 * notification shade, and leaves the file in Downloads where the person
 * looks for it.
 *
 * On Android 10 and later that folder needs no permission. Before it, writing
 * there needed one that the person would have to grant, so on those phones
 * the file goes to the app's own Downloads folder on shared storage -- still
 * opened from the notification, and still no permission.
 */
public final class ApkpyDownloads {

    private static final HashMap<Long, ApkpyKit.Done> WAITING = new HashMap<Long, ApkpyKit.Done>();
    private static boolean sListening = false;

    private ApkpyDownloads() { }

    private static synchronized void listen(final Context app) {
        if (sListening) return;
        BroadcastReceiver finished = new BroadcastReceiver() {
            @Override public void onReceive(Context context, Intent intent) {
                long id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L);
                ApkpyKit.Done done;
                synchronized (ApkpyDownloads.class) { done = WAITING.remove(id); }
                if (done == null) return;
                report(app, id, done);
            }
        };
        IntentFilter filter = new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
        // The download service is another app, so the receiver has to be one
        // other apps may reach -- which Android 13 wants said out loud.
        if (Build.VERSION.SDK_INT >= 33) {
            app.registerReceiver(finished, filter, Context.RECEIVER_EXPORTED);
        } else {
            app.registerReceiver(finished, filter);
        }
        sListening = true;
    }

    private static void report(Context app, long id, ApkpyKit.Done done) {
        DownloadManager manager = (DownloadManager) app.getSystemService(Context.DOWNLOAD_SERVICE);
        Cursor row = null;
        try {
            row = manager.query(new DownloadManager.Query().setFilterById(id));
            if (row == null || !row.moveToFirst()) {
                // Removed from the list before it finished: the person
                // cancelled it from the notification.
                ApkpyKit.answer(done, false, "failed");
                return;
            }
            int status = row.getInt(row.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS));
            if (status == DownloadManager.STATUS_SUCCESSFUL) {
                String where = row.getString(
                        row.getColumnIndexOrThrow(DownloadManager.COLUMN_LOCAL_URI));
                String name = where == null ? "" : Uri.parse(where).getLastPathSegment();
                ApkpyKit.answer(done, true, name == null ? "" : name);
                return;
            }
            int reason = row.getInt(row.getColumnIndexOrThrow(DownloadManager.COLUMN_REASON));
            ApkpyKit.answer(done, false,
                    reason == DownloadManager.ERROR_INSUFFICIENT_SPACE ? "no_space" : "failed");
        } catch (Throwable unknown) {
            ApkpyKit.answer(done, false, "failed");
        } finally {
            if (row != null) row.close();
        }
    }

    /** Start it. done: (true, the file's name) when it is in Downloads, or (false, why not). */
    public static void start(Activity activity, String url, String name, String title,
                             ApkpyKit.Done done) {
        String checked = ApkpyKitRules.webAddress(url);
        if (checked.isEmpty()) {
            ApkpyKit.answer(done, false, "invalid");
            return;
        }
        Uri address = Uri.parse(checked);
        Context app = activity.getApplicationContext();
        String file = ApkpyKit.text(name).trim();
        if (file.isEmpty()) file = URLUtil.guessFileName(address.toString(), null, null);
        // A name is a name: no folders, and nothing that climbs out of one.
        file = file.replace('\\', '/');
        file = file.substring(file.lastIndexOf('/') + 1);
        if (file.isEmpty() || file.equals(".") || file.equals("..")) file = "download";
        String shown = ApkpyKit.text(title).trim();

        try {
            DownloadManager manager =
                    (DownloadManager) app.getSystemService(Context.DOWNLOAD_SERVICE);
            if (manager == null) {
                ApkpyKit.answer(done, false, "unavailable");
                return;
            }
            DownloadManager.Request request = new DownloadManager.Request(address);
            request.setTitle(shown.isEmpty() ? file : shown);
            request.setNotificationVisibility(
                    DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            if (Build.VERSION.SDK_INT >= 29) {
                request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, file);
            } else {
                request.setDestinationInExternalFilesDir(
                        app, Environment.DIRECTORY_DOWNLOADS, file);
            }
            listen(app);
            // Enqueued and remembered under one lock: a download that fails at
            // once must still find who to tell.
            synchronized (ApkpyDownloads.class) {
                long id = manager.enqueue(request);
                if (done != null) WAITING.put(id, done);
            }
        } catch (IllegalArgumentException disabled) {
            // What enqueue() throws when the download service has been
            // disabled in the phone's settings.
            ApkpyKit.answer(done, false, "unavailable");
        } catch (Throwable refused) {
            ApkpyKit.answer(done, false, "failed");
        }
    }
}
