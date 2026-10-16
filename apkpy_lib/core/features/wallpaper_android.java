package __PACKAGE__;

import android.app.Activity;
import android.app.Application;
import android.app.WallpaperManager;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Matrix;
import android.graphics.Rect;
import android.media.ExifInterface;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.appcompat.app.AlertDialog;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/** Static wallpapers only. The sole write is behind a visible confirmation. */
public final class ApkpyWallpaper {
    public interface Result { void done(boolean success, String reason); }
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final ExecutorService IO = Executors.newSingleThreadExecutor();
    private static final AtomicBoolean BUSY = new AtomicBoolean();
    private static final int MAX_EDGE = 2048;

    // Applying a wallpaper changes the system palette, and a changed palette
    // is a configuration change: about a second after the answer is delivered,
    // Android tears this screen down and builds a new one from the layout.
    // Anything the callback wrote goes with it -- measured on a phone, where
    // the app set "Completed: ok" and then showed "Ready" again, so it looked
    // like nothing had happened while the wallpaper had in fact changed.
    //
    // So the answer is kept, and said again to the screen that replaces this
    // one. Only after a real rebuild: a screen the person simply walked away
    // from has already had its say, and hearing it twice would mean two of
    // whatever the callback does.
    private static String PENDING_TAG;
    private static boolean PENDING_OK;
    private static String PENDING_REASON;
    private static boolean PENDING_HEARD;
    private static boolean PENDING_REPLAY;

    private static String RESUMED_TAG;
    private static Result RESUMED;

    /** Called by a screen as it resumes, offering the callback it owns. */
    public static synchronized void resumed(String tag, Result callback) {
        RESUMED_TAG = tag;
        RESUMED = callback;
        deliver();
    }

    /**
     * Called by a screen as it pauses.
     *
     * ``isChangingConfigurations`` is the whole distinction: true means this
     * screen is coming straight back as a new instance and the answer must
     * travel with it; false means the person left, and the answer is spent.
     */
    public static synchronized void paused(Activity screen, String tag) {
        if (tag == null || !tag.equals(RESUMED_TAG)) return;
        RESUMED_TAG = null;
        RESUMED = null;
        if (!tag.equals(PENDING_TAG)) return;
        if (screen != null && screen.isChangingConfigurations()) {
            PENDING_REPLAY = true;
        } else {
            clear(tag);
        }
    }

    private static void clear(String tag) {
        if (tag != null && tag.equals(PENDING_TAG)) {
            PENDING_TAG = null;
            PENDING_REASON = null;
            PENDING_HEARD = false;
            PENDING_REPLAY = false;
        }
    }

    /** Say it, if there is a screen listening that has not heard it yet. */
    private static void deliver() {
        if (PENDING_TAG == null || RESUMED == null) return;
        if (!PENDING_TAG.equals(RESUMED_TAG)) return;
        if (PENDING_HEARD && !PENDING_REPLAY) return;
        PENDING_HEARD = true;
        PENDING_REPLAY = false;
        final Result target = RESUMED;
        final boolean ok = PENDING_OK;
        final String reason = PENDING_REASON;
        MAIN.post(() -> answer(target, ok, reason));
    }

    /** Hold the answer, and say it now if a screen is already listening. */
    private static synchronized void handOver(String tag, boolean ok, String reason) {
        if (tag == null) return;
        PENDING_TAG = tag;
        PENDING_OK = ok;
        PENDING_REASON = reason;
        PENDING_HEARD = false;
        PENDING_REPLAY = false;
        deliver();
    }

    private static String support(Context context) {
        try {
            WallpaperManager wm = WallpaperManager.getInstance(context);
            if (!wm.isWallpaperSupported()) return "unsupported";
            return wm.isSetWallpaperAllowed() ? "ok" : "not_allowed";
        } catch (SecurityException e) { return "not_allowed";
        } catch (RuntimeException e) { return "unsupported"; }
    }

    public static boolean available(Context context) {
        return "ok".equals(support(context));
    }

    public static void preview(Activity activity, String source, String target,
                               String tag, Result callback) {
        MAIN.post(() -> {
            if (activity.isFinishing() || activity.isDestroyed()) {
                answer(callback, false, "unavailable"); return;
            }
            int flags = "home".equals(target) ? WallpaperManager.FLAG_SYSTEM
                : "lock".equals(target) ? WallpaperManager.FLAG_LOCK
                : "both".equals(target) ? WallpaperManager.FLAG_SYSTEM | WallpaperManager.FLAG_LOCK : 0;
            if (flags == 0) { answer(callback, false, "invalid_target"); return; }
            String status = support(activity);
            if (!"ok".equals(status)) { answer(callback, false, status); return; }
            if (!BUSY.compareAndSet(false, true)) { answer(callback, false, "busy"); return; }
            new Request(activity, source, target, flags, tag, callback).load();
        });
    }

    private static void answer(Result callback, boolean ok, String reason) {
        if (callback != null) callback.done(ok, reason);
    }

    private static InputStream open(Context context, String source) throws Exception {
        if (source == null || source.isEmpty()) throw new IllegalArgumentException("Empty image");
        if (source.startsWith("content://"))
            return context.getContentResolver().openInputStream(Uri.parse(source));
        if (source.startsWith("asset://")) {
            String asset = source.substring(8);
            if (asset.contains("..") || asset.startsWith("/")) throw new IllegalArgumentException("Invalid asset");
            return context.getAssets().open(asset);
        }
        if (source.contains("://") && !source.startsWith("file://"))
            throw new IllegalArgumentException("Use a local image, not a URL");
        File file = source.startsWith("file://") ? new File(Uri.parse(source).getPath()) : new File(source);
        if (!file.isAbsolute()) file = new File(context.getFilesDir(), source);
        return new FileInputStream(file);
    }

    private static Bitmap decode(Context context, String source) throws Exception {
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inJustDecodeBounds = true;
        try (InputStream stream = open(context, source)) { BitmapFactory.decodeStream(stream, null, options); }
        if (options.outWidth <= 0 || options.outHeight <= 0) throw new IllegalArgumentException("Invalid image");
        options.inSampleSize = 1;
        while ((options.outWidth + (long) options.inSampleSize - 1) / options.inSampleSize > MAX_EDGE
                || (options.outHeight + (long) options.inSampleSize - 1) / options.inSampleSize > MAX_EDGE)
            options.inSampleSize *= 2;
        options.inJustDecodeBounds = false;
        options.inPreferredConfig = Bitmap.Config.ARGB_8888;
        Bitmap bitmap;
        try (InputStream stream = open(context, source)) { bitmap = BitmapFactory.decodeStream(stream, null, options); }
        if (bitmap == null) throw new IllegalArgumentException("Unsupported image");
        int orientation = ExifInterface.ORIENTATION_NORMAL;
        try (InputStream stream = open(context, source)) {
            orientation = new ExifInterface(stream).getAttributeInt(ExifInterface.TAG_ORIENTATION, orientation);
        } catch (Exception ignored) { /* Images without EXIF are already upright. */ }
        Matrix matrix = new Matrix();
        switch (orientation) {
            case 2: matrix.setScale(-1, 1); break;
            case 3: matrix.setRotate(180); break;
            case 4: matrix.setScale(1, -1); break;
            case 5: matrix.setRotate(90); matrix.postScale(-1, 1); break;
            case 6: matrix.setRotate(90); break;
            case 7: matrix.setRotate(-90); matrix.postScale(-1, 1); break;
            case 8: matrix.setRotate(-90); break;
        }
        if (!matrix.isIdentity()) {
            Bitmap upright = Bitmap.createBitmap(bitmap, 0, 0, bitmap.getWidth(), bitmap.getHeight(), matrix, true);
            if (upright != bitmap) bitmap.recycle();
            bitmap = upright;
        }
        return bitmap;
    }

    private static final class Request implements Application.ActivityLifecycleCallbacks {
        final Activity activity;
        final String source, target, tag;
        final int flags;
        Result callback;
        Bitmap bitmap;
        AlertDialog dialog;
        ImageView image;
        boolean finished, applying;
        volatile boolean destroyed;

        Request(Activity activity, String source, String target, int flags,
                String tag, Result callback) {
            this.activity = activity; this.source = source; this.target = target;
            this.flags = flags; this.tag = tag; this.callback = callback;
            activity.getApplication().registerActivityLifecycleCallbacks(this);
        }

        void load() {
            IO.execute(() -> {
                Bitmap decoded = null;
                String error = "invalid_image";
                try { decoded = decode(activity.getApplicationContext(), source);
                } catch (OutOfMemoryError e) { error = "invalid_image";
                } catch (Exception e) { error = "invalid_image"; }
                final Bitmap ready = decoded;
                final String reason = error;
                MAIN.post(() -> {
                    bitmap = ready;
                    if (destroyed || activity.isFinishing() || activity.isDestroyed()) {
                        finish(false, "cancelled"); return;
                    }
                    if (bitmap == null) { finish(false, reason); return; }
                    // Gallery callbacks may arrive before onResume/window focus.
                    // Wait briefly for our own screen, never open over another app.
                    showWhenReady(android.os.SystemClock.uptimeMillis() + 1500);
                });
            });
        }

        void showWhenReady(long deadline) {
            if (finished) return;
            if (destroyed || activity.isFinishing() || activity.isDestroyed()) {
                finish(false, "cancelled"); return;
            }
            if (activity.hasWindowFocus()) { show(); return; }
            if (android.os.SystemClock.uptimeMillis() >= deadline) {
                finish(false, "unavailable"); return;
            }
            MAIN.postDelayed(() -> showWhenReady(deadline), 50);
        }

        void show() {
            try {
                float density = activity.getResources().getDisplayMetrics().density;
                LinearLayout body = new LinearLayout(activity);
                body.setOrientation(LinearLayout.VERTICAL);
                int pad = (int) (20 * density);
                body.setPadding(pad, pad / 2, pad, 0);
                image = new ImageView(activity);
                image.setImageBitmap(bitmap);
                image.setScaleType(ImageView.ScaleType.FIT_CENTER);
                image.setContentDescription("Selected wallpaper preview");
                int height = Math.min((int) (300 * density), activity.getResources().getDisplayMetrics().heightPixels / 3);
                body.addView(image, new LinearLayout.LayoutParams(-1, height));
                TextView description = new TextView(activity);
                description.setText("Apply to " + ("home".equals(target) ? "home screen" : "lock".equals(target) ? "lock screen" : "home and lock screens")
                    + ".\nAndroid may crop or zoom the image. Your current wallpaper will be replaced.");
                description.setPadding(0, pad / 2, 0, 0);
                body.addView(description);
                dialog = new AlertDialog.Builder(activity).setTitle("Set wallpaper")
                    .setView(body).setNegativeButton("Cancel", (d, which) -> finish(false, "cancelled"))
                    .setPositiveButton("Apply", null).create();
                dialog.setOnCancelListener(d -> finish(false, "cancelled"));
                dialog.show();
                dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> apply());
            } catch (RuntimeException e) { finish(false, "unavailable"); }
        }

        void apply() {
            if (applying || finished || destroyed) return;
            applying = true;
            dialog.setCancelable(false);
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);
            dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false);
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setText("Applying...");
            IO.execute(() -> {
                String reason = support(activity.getApplicationContext());
                if ("ok".equals(reason)) {
                    try {
                        // This is the only write, reached solely by the Apply button.
                        int id = WallpaperManager.getInstance(activity.getApplicationContext())
                            .setBitmap(bitmap, (Rect) null, false, flags);
                        reason = id > 0 ? "ok" : "failed";
                    } catch (SecurityException e) { reason = "not_allowed";
                    } catch (Exception | OutOfMemoryError e) { reason = "failed"; }
                }
                final String result = reason;
                MAIN.post(() -> finish("ok".equals(result), result));
            });
        }

        void finish(boolean ok, String reason) {
            if (finished) return;
            finished = true;
            activity.getApplication().unregisterActivityLifecycleCallbacks(this);
            if (dialog != null) { dialog.setOnCancelListener(null); dialog.dismiss(); }
            if (image != null) image.setImageDrawable(null);
            if (bitmap != null) { bitmap.recycle(); bitmap = null; }
            BUSY.set(false);
            Result result = callback; callback = null;
            if (tag != null) {
                // Through the pending slot even when this screen looks
                // fine: the rebuild caused by this very change is still
                // about a second away.
                handOver(tag, ok, reason);
            } else if (!destroyed && !activity.isDestroyed()) {
                answer(result, ok, reason);
            }
        }

        public void onActivityDestroyed(Activity a) {
            if (a != activity) return;
            destroyed = true;
            callback = null;
            if (dialog != null) dialog.dismiss();
            // Loading/applying owns the bitmap until its IO task completes.
            if (bitmap != null && !applying) finish(false, "cancelled");
        }
        public void onActivityCreated(Activity a, Bundle b) {}
        public void onActivityStarted(Activity a) {}
        public void onActivityResumed(Activity a) {}
        public void onActivityPaused(Activity a) {}
        public void onActivityStopped(Activity a) {}
        public void onActivitySaveInstanceState(Activity a, Bundle b) {}
    }
}
