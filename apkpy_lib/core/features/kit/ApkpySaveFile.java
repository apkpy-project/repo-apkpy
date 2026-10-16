package __PACKAGE__;

import android.app.Activity;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;
import android.webkit.MimeTypeMap;

import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/**
 * files.save_as() and files.save_copy() -- a file handed to the person.
 *
 * An app's own folder is invisible to its owner: nothing in it shows up in
 * the Files app, and it is deleted with the app. To leave a file where the
 * person can find it, Android has the app ask *where* -- the system's picker
 * opens on Downloads, a drive or a card, the person chooses, and the app is
 * handed that one place to write to. No storage permission exists for this
 * and none is asked for.
 */
public final class ApkpySaveFile {

    private interface Source {
        InputStream open() throws java.io.IOException;
    }

    private ApkpySaveFile() { }

    private static String mimeFor(String name, String fallback) {
        int dot = name.lastIndexOf('.');
        if (dot >= 0 && dot < name.length() - 1) {
            String found = MimeTypeMap.getSingleton().getMimeTypeFromExtension(
                    name.substring(dot + 1).toLowerCase(java.util.Locale.ROOT));
            if (found != null) return found;
        }
        return fallback;
    }

    /** Ask where, and write this text there as UTF-8. */
    public static void saveText(Activity activity, String name, final String text,
                                String mime, ApkpyKit.Done done) {
        String kind = ApkpyKit.text(mime).trim();
        if (kind.isEmpty()) kind = "text/plain";
        final byte[] bytes = ApkpyKit.text(text).getBytes(StandardCharsets.UTF_8);
        ask(activity, ApkpyKit.text(name).trim(), kind, new Source() {
            @Override public InputStream open() {
                return new java.io.ByteArrayInputStream(bytes);
            }
        }, done);
    }

    /** Ask where, and copy one of the app's files there. */
    public static void saveCopy(Activity activity, String path, String name,
                                ApkpyKit.Done done) {
        String given = ApkpyKit.text(path).trim();
        File candidate = new File(given);
        // files.path("x") and recorder.stop() answer the whole path; a bare
        // name is a file in the app's own folder, as it is for files.exists().
        final File file = candidate.isAbsolute()
                ? candidate : new File(activity.getFilesDir(), given);
        if (given.isEmpty() || !file.isFile()) {
            ApkpyKit.answer(done, false, "not_found");
            return;
        }
        String shown = ApkpyKit.text(name).trim();
        if (shown.isEmpty()) shown = file.getName();
        ask(activity, shown, mimeFor(shown, "application/octet-stream"), new Source() {
            @Override public InputStream open() throws java.io.IOException {
                return new FileInputStream(file);
            }
        }, done);
    }

    private static void ask(Activity activity, String name, String mime, final Source source,
                            final ApkpyKit.Done done) {
        final Context app = activity.getApplicationContext();
        Intent picker = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        picker.addCategory(Intent.CATEGORY_OPENABLE);
        picker.setType(mime);
        picker.putExtra(Intent.EXTRA_TITLE, name.isEmpty() ? "untitled" : name);
        ApkpyKitActivity.forResult(activity, picker, new ApkpyKitActivity.Result() {
            @Override public void run(int resultCode, Intent data) {
                if (resultCode == ApkpyKitActivity.NO_APP) {
                    ApkpyKit.answer(done, false, "no_app");
                    return;
                }
                final Uri place = data == null ? null : data.getData();
                if (resultCode != Activity.RESULT_OK || place == null) {
                    ApkpyKit.answer(done, false, "cancelled");
                    return;
                }
                final ContentResolver resolver = app.getContentResolver();
                // The right to write there was given to the screen that asked,
                // and that screen is about to close. Keeping it for the length
                // of the write is what lets a large file be copied off the
                // main thread.
                boolean kept = false;
                try {
                    resolver.takePersistableUriPermission(
                            place, Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
                    kept = true;
                } catch (Throwable notOffered) {
                    // Not every provider offers it; then the write happens
                    // here, before the screen that holds the right goes.
                }
                if (!kept) {
                    write(resolver, place, source, done, false);
                    return;
                }
                new Thread(new Runnable() {
                    @Override public void run() { write(resolver, place, source, done, true); }
                }, "ApkpySaveFile").start();
            }
        });
    }

    private static void write(ContentResolver resolver, Uri place, Source source,
                              ApkpyKit.Done done, boolean release) {
        boolean ok = false;
        InputStream in = null;
        OutputStream out = null;
        try {
            in = source.open();
            out = resolver.openOutputStream(place, "wt");
            if (out != null) {
                byte[] buffer = new byte[64 * 1024];
                int count;
                while ((count = in.read(buffer)) > 0) out.write(buffer, 0, count);
                out.flush();
                ok = true;
            }
        } catch (Throwable failed) {
            ok = false;
        } finally {
            try { if (in != null) in.close(); } catch (Throwable ignored) { }
            try { if (out != null) out.close(); } catch (Throwable ignored) { ok = false; }
        }
        String name = ok ? nameOf(resolver, place) : "";
        if (!ok) {
            // A file that was created and not filled is worse than no file.
            try { android.provider.DocumentsContract.deleteDocument(resolver, place); }
            catch (Throwable ignored) { }
        }
        if (release) {
            try {
                resolver.releasePersistableUriPermission(
                        place, Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            } catch (Throwable ignored) { }
        }
        ApkpyKit.answer(done, ok, ok ? name : "failed");
    }

    /** The name the file ended up with -- the picker lets the person change it. */
    private static String nameOf(ContentResolver resolver, Uri place) {
        Cursor cursor = null;
        try {
            cursor = resolver.query(place, new String[] { OpenableColumns.DISPLAY_NAME },
                    null, null, null);
            if (cursor != null && cursor.moveToFirst()) {
                String found = cursor.getString(0);
                if (found != null && !found.isEmpty()) return found;
            }
        } catch (Throwable unknown) {
            // Falls through to the address.
        } finally {
            if (cursor != null) cursor.close();
        }
        String tail = place.getLastPathSegment();
        return tail == null ? place.toString() : tail;
    }
}
