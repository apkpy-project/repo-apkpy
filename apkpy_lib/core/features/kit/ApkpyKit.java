package __PACKAGE__;

import android.app.Activity;
import android.content.res.Configuration;
import android.content.res.Resources;
import android.graphics.Color;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.Window;
import android.view.WindowInsetsController;
import android.view.WindowManager;

/**
 * What the calls that reach the rest of the phone have in common: the shape of
 * an answer that comes later, and how the text an app passes is read.
 *
 * The reading itself is in ApkpyKitRules, which is apkpy_lib/kit_rules.py again
 * in Java; the Previewer uses the Python one, so both accept the same texts.
 */
public final class ApkpyKit {

    /** An answer that arrives later: ok, and the value or the word for why not. */
    public interface Done {
        void run(boolean ok, String value);
    }

    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    private ApkpyKit() { }

    /** Run on the thread that owns the screens, now if this is it. */
    public static void main(Runnable work) {
        if (Looper.myLooper() == Looper.getMainLooper()) work.run();
        else MAIN.post(work);
    }

    public static void later(Runnable work, long milliseconds) {
        MAIN.postDelayed(work, milliseconds);
    }

    /** Answer, on the main thread, never with null. */
    public static void answer(final Done done, final boolean ok, final String value) {
        if (done == null) return;
        main(new Runnable() {
            @Override public void run() {
                done.run(ok, value == null ? "" : value);
            }
        });
    }

    public static String text(String value) {
        return value == null ? "" : value;
    }

    // How text is read lives in ApkpyKitRules, which a test can run on a
    // desk; these are the short names the other classes use.
    public static double number(String text, double fallback) {
        return ApkpyKitRules.number(text, fallback);
    }

    public static long whole(String text, long fallback) {
        return ApkpyKitRules.whole(text, fallback);
    }

    public static boolean truth(String text) {
        return ApkpyKitRules.truth(text);
    }

    public static String flag(boolean value) {
        return ApkpyKitRules.flag(value);
    }

    public static double clamp(double value, double low, double high) {
        return ApkpyKitRules.clamp(value, low, high);
    }

    /** A colour as CSS writes it. */
    public static String hex(int color) {
        return String.format("#%06X", color & 0xFFFFFF);
    }

    // ── a window of ours over a screen of the app ────────────────────────────

    /** Whether this screen's clock and battery are drawn dark, on a light bar. */
    public static boolean lightBars(Activity activity) {
        try {
            Window window = activity.getWindow();
            if (Build.VERSION.SDK_INT >= 30 && window.getInsetsController() != null
                    && (window.getInsetsController().getSystemBarsAppearance()
                        & WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS) != 0) {
                return true;
            }
            return (window.getDecorView().getSystemUiVisibility()
                    & View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR) != 0;
        } catch (Throwable unknown) {
            return !isNight(activity.getResources());
        }
    }

    /**
     * Draw under the system bars, and draw nothing there.
     *
     * A window with one of the old themes -- the see-through one a screen
     * with nothing on it needs -- is not asked to draw behind the status and
     * navigation bars, and Android fills them with black. This asks, and
     * leaves them clear: what is behind shows through. light says which way
     * the clock and the battery have to contrast.
     */
    public static void clearBars(Window window, boolean light) {
        if (window == null) return;
        try {
            window.clearFlags(WindowManager.LayoutParams.FLAG_TRANSLUCENT_STATUS
                    | WindowManager.LayoutParams.FLAG_TRANSLUCENT_NAVIGATION);
            window.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
            window.setStatusBarColor(Color.TRANSPARENT);
            window.setNavigationBarColor(Color.TRANSPARENT);
            if (Build.VERSION.SDK_INT >= 29) {
                window.setStatusBarContrastEnforced(false);
                window.setNavigationBarContrastEnforced(false);
            }
            if (Build.VERSION.SDK_INT >= 30) {
                window.setDecorFitsSystemWindows(false);
                WindowInsetsController bars = window.getInsetsController();
                if (bars != null) {
                    int both = WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS
                            | WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
                    bars.setSystemBarsAppearance(light ? both : 0, both);
                }
            } else {
                int flags = View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION;
                if (light) flags |= View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
                if (light && Build.VERSION.SDK_INT >= 26) {
                    flags |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
                }
                window.getDecorView().setSystemUiVisibility(flags);
            }
        } catch (Throwable odd) {
            // A window that will not take it keeps the bars it had.
        }
    }

    // ── light or dark, kept ──────────────────────────────────────────────────

    public static boolean isNight(Resources resources) {
        return night(resources) == Configuration.UI_MODE_NIGHT_YES;
    }

    private static int night(Resources resources) {
        return resources.getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK;
    }

    private static boolean put(Resources resources, int night) {
        Configuration now = resources.getConfiguration();
        if ((now.uiMode & Configuration.UI_MODE_NIGHT_MASK) == night) return false;
        Configuration kept = new Configuration(now);
        kept.uiMode = (now.uiMode & ~Configuration.UI_MODE_NIGHT_MASK) | night;
        resources.updateConfiguration(kept, resources.getDisplayMetrics());
        return true;
    }

    /**
     * The light or dark an app is in, to put back after a WebView.
     *
     * The first WebView a process makes brings the WebView package's
     * resources into the app's, and the phone's own night setting comes in
     * with them. An app that keeps itself light on a dark phone -- or dark on
     * a light one -- would leave the page with this screen reading the other
     * mode's colours: the next dialog, the next row, in the wrong one.
     *
     *     ApkpyKit.Mode mode = ApkpyKit.mode(activity);
     *     WebView page = new WebView(activity);
     *     mode.keep();
     */
    public static final class Mode {
        private final Activity mActivity;
        private final int mOwn;
        private final int mShared;

        private Mode(Activity activity) {
            mActivity = activity;
            mOwn = night(activity.getResources());
            mShared = night(activity.getApplicationContext().getResources());
        }

        /** Put back what was there, if it moved. Cheap enough to call often. */
        public void keep() {
            try {
                put(mActivity.getApplicationContext().getResources(), mShared);
                if (!put(mActivity.getResources(), mOwn)) return;
                // The theme read its values under the other mode.
                int theme = mActivity.getPackageManager()
                        .getActivityInfo(mActivity.getComponentName(), 0).getThemeResource();
                if (theme != 0) mActivity.getTheme().applyStyle(theme, true);
            } catch (Throwable odd) {
                // Nothing here is worth failing a page over.
            }
        }
    }

    public static Mode mode(Activity activity) {
        return new Mode(activity);
    }
}
