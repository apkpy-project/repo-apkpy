package __PACKAGE__;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipDescription;
import android.content.ClipboardManager;
import android.content.Context;

/**
 * clipboard.paste() and clipboard.has_text().
 *
 * Android 10 and later let an app read the clipboard only while one of its
 * screens has the focus, and Android 12 and later show the person a short
 * notice each time an app reads it. has_text() only looks at what kind of
 * thing is there, which shows nothing: an app can light its paste button
 * without being seen to read.
 */
public final class ApkpyClipboard {

    private ApkpyClipboard() { }

    private static ClipboardManager board(Activity activity) {
        return (ClipboardManager) activity.getSystemService(Context.CLIPBOARD_SERVICE);
    }

    /** The text on the clipboard, or "" when there is none or it cannot be read. */
    public static String paste(Activity activity) {
        try {
            ClipboardManager board = board(activity);
            if (board == null || !board.hasPrimaryClip()) return "";
            ClipData clip = board.getPrimaryClip();
            if (clip == null || clip.getItemCount() == 0) return "";
            CharSequence text = clip.getItemAt(0).coerceToText(activity);
            return text == null ? "" : text.toString();
        } catch (RuntimeException refused) {
            // Read without the focus: Android answers nothing, or throws.
            return "";
        }
    }

    public static String hasText(Activity activity) {
        try {
            ClipboardManager board = board(activity);
            if (board == null || !board.hasPrimaryClip()) return ApkpyKit.flag(false);
            ClipDescription what = board.getPrimaryClipDescription();
            return ApkpyKit.flag(what != null
                    && (what.hasMimeType(ClipDescription.MIMETYPE_TEXT_PLAIN)
                        || what.hasMimeType(ClipDescription.MIMETYPE_TEXT_HTML)
                        || what.hasMimeType("text/*")));
        } catch (RuntimeException refused) {
            return ApkpyKit.flag(false);
        }
    }
}
