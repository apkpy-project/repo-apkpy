package __PACKAGE__;

import android.app.Activity;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;

/**
 * Where a link or a share lands.
 *
 * The manifest points the addresses named by incoming.links() and the kinds
 * named by incoming.shares() at this Activity. It draws nothing. It writes
 * down what arrived, copies a shared file into the app while the right to
 * read it lasts -- that right is given to this Activity and goes when it
 * does -- and then opens the app at its first screen, new, with nothing of
 * an earlier visit on top. That screen is the one place that asks
 * incoming.link(), so it has to be the one the person lands on.
 */
public final class ApkpyIncomingActivity extends Activity {

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        ApkpyKit.clearBars(getWindow(), !ApkpyKit.isNight(getResources()));
        final Intent arrived = getIntent();
        String action = arrived == null ? null : arrived.getAction();
        if (Intent.ACTION_VIEW.equals(action)) {
            ApkpyIncoming.set(arrived.getDataString(), "", "");
            openApp();
            return;
        }
        if (Intent.ACTION_SEND.equals(action)) {
            CharSequence words = arrived.getCharSequenceExtra(Intent.EXTRA_TEXT);
            final String text = words == null ? "" : words.toString();
            final Uri stream = arrived.getParcelableExtra(Intent.EXTRA_STREAM);
            if (stream == null) {
                ApkpyIncoming.set("", text, "");
                openApp();
                return;
            }
            new Thread(new Runnable() {
                @Override public void run() {
                    final String path = copy(stream);
                    runOnUiThread(new Runnable() {
                        @Override public void run() {
                            ApkpyIncoming.set("", text, path);
                            openApp();
                        }
                    });
                }
            }, "ApkpyIncoming").start();
            return;
        }
        openApp();
    }

    private void openApp() {
        Intent launch = getPackageManager().getLaunchIntentForPackage(getPackageName());
        if (launch != null) {
            launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
            startActivity(launch);
        }
        finish();
        overridePendingTransition(0, 0);
    }

    private String nameOf(Uri stream) {
        Cursor cursor = null;
        try {
            cursor = getContentResolver().query(
                    stream, new String[] { OpenableColumns.DISPLAY_NAME }, null, null, null);
            if (cursor != null && cursor.moveToFirst()) {
                String found = cursor.getString(0);
                if (found != null && !found.isEmpty()) return found;
            }
        } catch (Throwable unknown) {
            // Falls through to the address.
        } finally {
            if (cursor != null) cursor.close();
        }
        String tail = stream.getLastPathSegment();
        return tail == null || tail.isEmpty() ? "shared" : tail;
    }

    /** A copy in the app's cache, under the file's own name. "" when it cannot be read. */
    private String copy(Uri stream) {
        // A name is a name: whatever the other app called the file, it is
        // written inside the one folder and nowhere else.
        String name = nameOf(stream).replace('\\', '/');
        name = name.substring(name.lastIndexOf('/') + 1);
        if (name.isEmpty() || name.equals(".") || name.equals("..")) name = "shared";
        File folder = new File(getCacheDir(), "incoming");
        InputStream in = null;
        OutputStream out = null;
        try {
            if (!folder.isDirectory() && !folder.mkdirs()) return "";
            // One share at a time is kept: the folder is the app's cache, not
            // an archive.
            File[] old = folder.listFiles();
            if (old != null) for (File file : old) file.delete();
            File target = new File(folder, name);
            in = getContentResolver().openInputStream(stream);
            if (in == null) return "";
            out = new FileOutputStream(target);
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = in.read(buffer)) > 0) out.write(buffer, 0, count);
            out.flush();
            return target.getAbsolutePath();
        } catch (Throwable unreadable) {
            return "";
        } finally {
            try { if (in != null) in.close(); } catch (Throwable ignored) { }
            try { if (out != null) out.close(); } catch (Throwable ignored) { }
        }
    }
}
