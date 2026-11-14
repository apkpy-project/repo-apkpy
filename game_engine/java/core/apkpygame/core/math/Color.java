package apkpygame.core.math;

/** Colours are ARGB ints (the same layout as android.graphics.Color and java.awt.Color). */
public final class Color {
    public static final int WHITE = 0xFFFFFFFF;
    public static final int BLACK = 0xFF000000;

    private Color() { }

    /** "#rgb", "#rrggbb" or "#aarrggbb". */
    public static int parse(String text, int fallback) {
        if (text == null || !text.startsWith("#")) return fallback;
        String hex = text.substring(1);
        try {
            if (hex.length() == 3) {
                hex = "" + hex.charAt(0) + hex.charAt(0) + hex.charAt(1) + hex.charAt(1)
                        + hex.charAt(2) + hex.charAt(2);
            }
            if (hex.length() == 6) return 0xFF000000 | Integer.parseInt(hex, 16);
            if (hex.length() == 8) return (int) Long.parseLong(hex, 16);
        } catch (NumberFormatException ignored) {
            // fall through
        }
        return fallback;
    }

    public static int alpha(int argb) { return (argb >>> 24) & 0xFF; }
    public static int red(int argb) { return (argb >> 16) & 0xFF; }
    public static int green(int argb) { return (argb >> 8) & 0xFF; }
    public static int blue(int argb) { return argb & 0xFF; }

    public static int withAlpha(int argb, double alpha) {
        int a = (int) Math.round(alpha(argb) * Math.max(0, Math.min(1, alpha)));
        return (a << 24) | (argb & 0x00FFFFFF);
    }
}
