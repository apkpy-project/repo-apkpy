package __PACKAGE__;

import android.app.Activity;

/**
 * incoming.* -- what opened the app from outside.
 *
 * A link somebody tapped, or text or a file another app shared into this one.
 * It arrives at ApkpyIncomingActivity, which keeps it here and opens the app
 * at its first screen; that screen asks what came in. It is kept for the
 * process rather than for a screen, and it stays until the app says it has
 * dealt with it -- incoming.clear() -- so going back to the first screen does
 * not find it a second time by accident, and does not lose it either.
 */
public final class ApkpyIncoming {

    static volatile String sLink = "";
    static volatile String sText = "";
    static volatile String sFile = "";

    private ApkpyIncoming() { }

    static void set(String link, String text, String file) {
        sLink = link == null ? "" : link;
        sText = text == null ? "" : text;
        sFile = file == null ? "" : file;
    }

    public static String link(Activity activity) {
        return sLink;
    }

    public static String text(Activity activity) {
        return sText;
    }

    public static String file(Activity activity) {
        return sFile;
    }

    public static String clear(Activity activity) {
        set("", "", "");
        return "ok";
    }
}
