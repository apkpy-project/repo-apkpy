package __PACKAGE__;

import android.Manifest;
import android.app.Activity;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.media.MediaScannerConnection;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

/**
 * gallery.save() -- a picture or a video of the app, put in the gallery.
 *
 * From Android 10 an app adds to the gallery with no permission: the file
 * goes to Pictures/<album> (Movies/<album> for a video) and shows in the
 * phone's gallery and in Google Photos at once. Android 9 and older ask the
 * person, once, to let the app write to the phone's storage. The album is
 * named after the app unless album= names it.
 */
public final class ApkpyGallery {

    private ApkpyGallery() { }

    public static void save(final Activity activity, String path, String album,
                            final ApkpyKit.Done done) {
        final Context app = activity.getApplicationContext();
        String given = ApkpyKit.text(path).trim();
        File candidate = new File(given);
        // A bare name is a file in the app's own folder, as for files.save_copy().
        final File file = candidate.isAbsolute() ? candidate : new File(app.getFilesDir(), given);
        if (given.isEmpty() || !file.isFile()) {
            ApkpyKit.answer(done, false, "not_found");
            return;
        }
        final String type = ApkpyKitRules.galleryType(file.getName());
        if (type.isEmpty()) {
            ApkpyKit.answer(done, false, "invalid");
            return;
        }
        String named = ApkpyKit.text(album).trim();
        final String folder = folderName(named.isEmpty()
                ? app.getApplicationInfo().loadLabel(app.getPackageManager()).toString() : named);
        if (Build.VERSION.SDK_INT >= 29) {
            copyInBackground(app, file, type, folder, done);
            return;
        }
        ApkpyKitActivity.forPermission(activity, Manifest.permission.WRITE_EXTERNAL_STORAGE,
                new ApkpyKitActivity.Granted() {
                    @Override public void run(boolean granted, boolean blocked) {
                        if (!granted) {
                            ApkpyKit.answer(done, false,
                                    blocked ? "permission_blocked" : "permission_denied");
                            return;
                        }
                        copyInBackground(app, file, type, folder, done);
                    }
                });
    }

    /** What may be a folder's name on every phone. */
    private static String folderName(String text) {
        String kept = text.replaceAll("[\\\\/:*?\"<>|\\x00-\\x1f]", "_").trim();
        while (kept.startsWith(".")) kept = kept.substring(1);
        return kept.isEmpty() ? "ApkPy" : kept;
    }

    private static void copyInBackground(final Context app, final File file, final String type,
                                         final String folder, final ApkpyKit.Done done) {
        // A video can be hundreds of megabytes: never on the screen's thread.
        new Thread(new Runnable() {
            @Override public void run() {
                String saved = Build.VERSION.SDK_INT >= 29
                        ? intoMediaStore(app, file, type, folder)
                        : intoFolder(app, file, type, folder);
                if (saved == null) ApkpyKit.answer(done, false, "failed");
                else ApkpyKit.answer(done, true, saved);
            }
        }, "apkpy-gallery").start();
    }

    /** Android 10 and later: MediaStore writes it, the gallery sees it. */
    private static String intoMediaStore(Context app, File file, String type, String folder) {
        boolean video = type.startsWith("video/");
        ContentResolver resolver = app.getContentResolver();
        ContentValues values = new ContentValues();
        values.put(MediaStore.MediaColumns.DISPLAY_NAME, file.getName());
        values.put(MediaStore.MediaColumns.MIME_TYPE, type);
        values.put(MediaStore.MediaColumns.RELATIVE_PATH,
                (video ? Environment.DIRECTORY_MOVIES : Environment.DIRECTORY_PICTURES) + "/" + folder);
        // Hidden from the gallery until the last byte is written.
        values.put(MediaStore.MediaColumns.IS_PENDING, 1);
        Uri collection = video
                ? MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
                : MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
        Uri item;
        try {
            item = resolver.insert(collection, values);
        } catch (RuntimeException refused) {
            return null;
        }
        if (item == null) return null;
        InputStream in = null;
        OutputStream out = null;
        try {
            in = new FileInputStream(file);
            out = resolver.openOutputStream(item);
            if (out == null) throw new IOException("no stream");
            copy(in, out);
        } catch (IOException | RuntimeException failed) {
            close(in);
            close(out);
            try { resolver.delete(item, null, null); } catch (RuntimeException ignored) { }
            return null;
        }
        close(in);
        close(out);
        values.clear();
        values.put(MediaStore.MediaColumns.IS_PENDING, 0);
        try {
            resolver.update(item, values, null, null);
        } catch (RuntimeException ignored) { }
        return file.getName();
    }

    /** Android 9 and older: a file in Pictures/<album>, then the scanner is told. */
    @SuppressWarnings("deprecation")
    private static String intoFolder(Context app, File file, String type, String folder) {
        boolean video = type.startsWith("video/");
        File base = Environment.getExternalStoragePublicDirectory(
                video ? Environment.DIRECTORY_MOVIES : Environment.DIRECTORY_PICTURES);
        File place = new File(base, folder);
        if (!place.isDirectory() && !place.mkdirs()) return null;
        String name = file.getName();
        int dot = name.lastIndexOf('.');
        String stem = dot > 0 ? name.substring(0, dot) : name;
        String ending = dot > 0 ? name.substring(dot) : "";
        File target = new File(place, name);
        for (int copy = 2; target.exists(); copy++) {
            target = new File(place, stem + "-" + copy + ending);
        }
        InputStream in = null;
        OutputStream out = null;
        try {
            in = new FileInputStream(file);
            out = new FileOutputStream(target);
            copy(in, out);
        } catch (IOException failed) {
            close(in);
            close(out);
            target.delete();
            return null;
        }
        close(in);
        close(out);
        MediaScannerConnection.scanFile(app, new String[] { target.getAbsolutePath() },
                new String[] { type }, null);
        return target.getName();
    }

    private static void copy(InputStream in, OutputStream out) throws IOException {
        byte[] chunk = new byte[64 * 1024];
        int read;
        while ((read = in.read(chunk)) != -1) out.write(chunk, 0, read);
        out.flush();
    }

    private static void close(java.io.Closeable closeable) {
        if (closeable == null) return;
        try { closeable.close(); } catch (IOException ignored) { }
    }
}
