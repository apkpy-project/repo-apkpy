package __PACKAGE__;

import android.app.Activity;
import android.content.Context;
import android.content.pm.PackageManager;
import android.print.PrintAttributes;
import android.print.PrintManager;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * printing.* -- Android's print screen.
 *
 * The document is HTML, laid out by a WebView nobody sees and handed to the
 * system's print screen. From there it is the person's choice: any printer
 * the phone knows, or "Save as PDF", which is how an app makes a PDF without
 * drawing one. Nothing is sent anywhere by this app and no permission is
 * involved.
 */
public final class ApkpyPrinting {

    // The WebView has to outlive the call: the print screen reads the pages
    // from it after this method has returned.
    private static WebView sKept;

    private static final String PRINT_CSS = "__PRINT_CSS__";

    private ApkpyPrinting() { }

    private static String escape(String text) {
        return ApkpyKit.text(text).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;");
    }

    /** Plain text, printed as it is written: line breaks and spacing kept. */
    public static void text(Activity activity, String text, String name, ApkpyKit.Done done) {
        html(activity, "<pre class=\"apkpy-text\">" + escape(text) + "</pre>", name, done);
    }

    /** A document written in HTML. done: (true, "ok") once the print screen is open. */
    public static void html(final Activity activity, String html, String name,
                            final ApkpyKit.Done done) {
        if (!activity.getPackageManager().hasSystemFeature(PackageManager.FEATURE_PRINTING)) {
            ApkpyKit.answer(done, false, "unavailable");
            return;
        }
        final String job = ApkpyKit.text(name).trim().isEmpty() ? "Document" : name.trim();
        // Ink on paper, with a margin: the rules a fragment is given.
        final String markup = ApkpyKitRules.document(ApkpyKit.text(html), PRINT_CSS);
        ApkpyKit.main(new Runnable() {
            @Override public void run() {
                try {
                    final ApkpyKit.Mode mode = ApkpyKit.mode(activity);
                    final WebView page = new WebView(activity);
                    mode.keep();
                    // A document, not a web app: nothing in it runs.
                    page.getSettings().setJavaScriptEnabled(false);
                    page.getSettings().setAllowFileAccess(false);
                    page.setWebViewClient(new WebViewClient() {
                        private boolean handed = false;

                        @Override public void onPageFinished(WebView view, String url) {
                            mode.keep();
                            if (handed) return;
                            handed = true;
                            try {
                                PrintManager manager = (PrintManager)
                                        activity.getSystemService(Context.PRINT_SERVICE);
                                manager.print(job, view.createPrintDocumentAdapter(job),
                                        new PrintAttributes.Builder().build());
                                ApkpyKit.answer(done, true, "ok");
                            } catch (Throwable failed) {
                                sKept = null;
                                ApkpyKit.answer(done, false, "failed");
                            }
                        }
                    });
                    sKept = page;
                    page.loadDataWithBaseURL(null, markup, "text/html", "UTF-8", null);
                } catch (Throwable failed) {
                    // No WebView on this device, or the screen is closing.
                    sKept = null;
                    ApkpyKit.answer(done, false, "failed");
                }
            }
        });
    }
}
