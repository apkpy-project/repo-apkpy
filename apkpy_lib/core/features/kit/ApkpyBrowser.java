package __PACKAGE__;

import android.app.Activity;
import android.app.Dialog;
import android.content.ActivityNotFoundException;
import android.content.DialogInterface;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowInsets;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

/**
 * browser.* -- a web page, in one of two places.
 *
 * open(url) hands the address to the phone's browser as a tab drawn over the
 * app: the person's own browser, with their sign-ins and their password
 * manager, and one Back from the app. No library is added for it -- a browser
 * tab is an ordinary VIEW intent carrying two extras.
 *
 * show(...) is a page inside the app: a WebView under a bar with a title and a
 * close button, over the whole screen. It is the one to use for your own HTML,
 * and for a page that should not look like a browser.
 */
public final class ApkpyBrowser {

    private static final String SESSION = "android.support.customtabs.extra.SESSION";
    private static final String TOOLBAR_COLOR = "android.support.customtabs.extra.TOOLBAR_COLOR";
    private static final String TITLE_VISIBILITY =
            "android.support.customtabs.extra.TITLE_VISIBILITY";

    private static final String PAGE_CSS = "__PAGE_CSS__";

    private ApkpyBrowser() { }

    /** The address when it is an http(s) one, else null. */
    static Uri web(String url) {
        String address = ApkpyKitRules.webAddress(url);
        return address.isEmpty() ? null : Uri.parse(address);
    }

    private static int themed(Activity activity, int attribute, int fallback) {
        TypedValue found = new TypedValue();
        if (activity.getTheme().resolveAttribute(attribute, found, true)
                && found.type >= TypedValue.TYPE_FIRST_COLOR_INT
                && found.type <= TypedValue.TYPE_LAST_COLOR_INT) {
            return found.data;
        }
        return fallback;
    }

    /** The page as a browser tab over the app. */
    public static String open(Activity activity, String url) {
        Uri address = web(url);
        if (address == null) return "invalid";
        Intent intent = new Intent(Intent.ACTION_VIEW, address);
        // What makes a browser draw this as a tab of the app rather than
        // switch to itself: the session extra, present even when empty.
        Bundle extras = new Bundle();
        extras.putBinder(SESSION, null);
        intent.putExtras(extras);
        intent.putExtra(TOOLBAR_COLOR,
                themed(activity, android.R.attr.colorPrimary, 0xFF202124) | 0xFF000000);
        intent.putExtra(TITLE_VISIBILITY, 1);
        try {
            activity.startActivity(intent);
            return "ok";
        } catch (ActivityNotFoundException nobody) {
            return "no_browser";
        }
    }

    private static int dp(Activity activity, float value) {
        return Math.round(value * activity.getResources().getDisplayMetrics().density);
    }

    private static boolean isDark(int color) {
        double light = (0.299 * Color.red(color) + 0.587 * Color.green(color)
                + 0.114 * Color.blue(color)) / 255.0;
        return light < 0.5;
    }

    /** The page, or your own HTML, inside the app. done: (true, last address) when closed. */
    public static void show(final Activity activity, String url, String html, String title,
                            final ApkpyKit.Done done) {
        final Uri address = web(url);
        final String markup = ApkpyKit.text(html);
        if (address == null && markup.trim().isEmpty()) {
            ApkpyKit.answer(done, false, "invalid");
            return;
        }
        final String heading = ApkpyKit.text(title).trim();

        final int surface = themed(activity, android.R.attr.colorBackground, Color.WHITE)
                | 0xFF000000;
        final int ink = isDark(surface) ? 0xFFF2F2F2 : 0xFF1B1B1F;
        final int accent = themed(activity, android.R.attr.colorPrimary, 0xFF3D5AFE) | 0xFF000000;

        // What Back does is the dialog's own onBackPressed(), not a listener
        // for the key: an app that targets Android 16 is no longer sent the
        // key there, and the page was closed where it should have gone back.
        // Android calls this either way.
        final Runnable[] back = new Runnable[1];
        final Dialog dialog = new Dialog(activity,
                android.R.style.Theme_Translucent_NoTitleBar) {
            @Override public void onBackPressed() {
                if (back[0] != null) back[0].run();
                else super.onBackPressed();
            }
        };
        final LinearLayout root = new LinearLayout(activity);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(surface);

        LinearLayout bar = new LinearLayout(activity);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setGravity(Gravity.CENTER_VERTICAL);

        final TextView close = new TextView(activity);
        close.setText("✕");
        close.setTextColor(ink);
        close.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20);
        close.setGravity(Gravity.CENTER);
        close.setContentDescription("Close");
        close.setFocusable(true);
        close.setClickable(true);
        TypedValue ripple = new TypedValue();
        if (activity.getTheme().resolveAttribute(
                android.R.attr.selectableItemBackgroundBorderless, ripple, true)) {
            close.setBackgroundResource(ripple.resourceId);
        }
        bar.addView(close, new LinearLayout.LayoutParams(dp(activity, 56), dp(activity, 56)));

        final TextView name = new TextView(activity);
        name.setTextColor(ink);
        name.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18);
        name.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        name.setSingleLine(true);
        name.setEllipsize(TextUtils.TruncateAt.END);
        name.setText(heading);
        LinearLayout.LayoutParams wide = new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        wide.rightMargin = dp(activity, 16);
        bar.addView(name, wide);
        root.addView(bar, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(activity, 56)));

        final ProgressBar progress = new ProgressBar(
                activity, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        progress.setIndeterminate(false);
        if (Build.VERSION.SDK_INT >= 21) {
            progress.setProgressTintList(android.content.res.ColorStateList.valueOf(accent));
        }
        root.addView(progress, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(activity, 3)));

        final ApkpyKit.Mode mode = ApkpyKit.mode(activity);
        final WebView page = new WebView(activity);
        mode.keep();
        WebSettings settings = page.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        // The page is the web's, or text the app wrote: neither gets to read
        // the app's files or another app's content.
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setSupportMultipleWindows(false);
        final String[] last = { address == null ? "" : address.toString() };
        page.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri target = request.getUrl();
                String scheme = target.getScheme() == null ? "" : target.getScheme();
                if (scheme.equalsIgnoreCase("http") || scheme.equalsIgnoreCase("https")) {
                    return false;
                }
                // tel:, mailto:, a shop's own link -- the phone knows who
                // opens those, a WebView does not.
                try {
                    activity.startActivity(new Intent(Intent.ACTION_VIEW, target));
                } catch (Throwable nobody) {
                    // Nothing opens it; staying on the page is the answer.
                }
                return true;
            }

            @Override
            public void onPageStarted(WebView view, String started, Bitmap icon) {
                if (started != null && started.startsWith("http")) last[0] = started;
                progress.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String finished) {
                progress.setVisibility(View.INVISIBLE);
                mode.keep();
            }
        });
        page.setWebChromeClient(new WebChromeClient() {
            @Override public void onProgressChanged(WebView view, int percent) {
                progress.setProgress(percent);
            }

            @Override public void onReceivedTitle(WebView view, String found) {
                // A title the app gave stays; otherwise the page names itself.
                if (heading.isEmpty() && found != null && !found.startsWith("about:")) {
                    name.setText(found);
                }
            }
        });
        root.addView(page, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        // The window runs under the status and navigation bars; the bar and
        // the page are kept clear of them, and of the keyboard when a form
        // on the page opens it.
        FrameLayout frame = new FrameLayout(activity);
        frame.setBackgroundColor(surface);
        frame.addView(root, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        frame.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
            @Override public WindowInsets onApplyWindowInsets(View view, WindowInsets insets) {
                int left, top, right, bottom;
                if (Build.VERSION.SDK_INT >= 30) {
                    android.graphics.Insets bars = insets.getInsets(
                            WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout()
                                    | WindowInsets.Type.ime());
                    left = bars.left; top = bars.top; right = bars.right; bottom = bars.bottom;
                } else {
                    left = insets.getSystemWindowInsetLeft();
                    top = insets.getSystemWindowInsetTop();
                    right = insets.getSystemWindowInsetRight();
                    bottom = insets.getSystemWindowInsetBottom();
                }
                root.setPadding(left, top, right, bottom);
                return insets;
            }
        });
        dialog.setContentView(frame);

        Window window = dialog.getWindow();
        if (window != null) {
            window.setLayout(ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT);
            window.setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(surface));
            window.setSoftInputMode(
                    android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
            // Dark icons on a light bar, light on a dark one.
            ApkpyKit.clearBars(window, !isDark(surface));
        }

        close.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View view) { dialog.dismiss(); }
        });
        back[0] = new Runnable() {
            @Override public void run() {
                // Back is the page's first: one step in its history, and out
                // of it only from the first page.
                if (page.canGoBack()) page.goBack();
                else dialog.dismiss();
            }
        };
        dialog.setOnDismissListener(new DialogInterface.OnDismissListener() {
            @Override public void onDismiss(DialogInterface owner) {
                try {
                    page.stopLoading();
                    ((ViewGroup) page.getParent()).removeView(page);
                    page.destroy();
                } catch (Throwable ignored) { }
                mode.keep();
                ApkpyKit.answer(done, true, last[0]);
            }
        });

        if (address != null) {
            page.loadUrl(address.toString());
        } else {
            // The app's own HTML wears the app's colours until it says otherwise.
            String css = PAGE_CSS.replace("@surface@", ApkpyKit.hex(surface))
                    .replace("@ink@", ApkpyKit.hex(ink))
                    .replace("@accent@", ApkpyKit.hex(accent));
            page.loadDataWithBaseURL(null, ApkpyKitRules.document(markup, css),
                    "text/html", "UTF-8", null);
        }
        try {
            dialog.show();
            mode.keep();
        } catch (Throwable gone) {
            // The screen was closing as this was asked for.
            ApkpyKit.answer(done, false, "invalid");
        }
    }
}
