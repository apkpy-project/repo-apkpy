package apkpygame.core;

import apkpygame.core.math.Mat3;

/**
 * Maps the game's virtual resolution onto the real surface.
 *
 * <ul>
 * <li>{@code fit}: everything visible, bars where the shapes differ</li>
 * <li>{@code fill}: no bars, the edges are cut</li>
 * <li>{@code expand}: no bars, no cut: the visible world grows (width/height change)</li>
 * </ul>
 * With a whole scale (pixel art), a virtual pixel is always the same whole number
 * of screen pixels; {@code fit} and {@code expand} round down, {@code fill} up.
 * Where the surface stands for a bigger phone screen (the ApkPy Previewer shows
 * a 1080p phone in a few hundred window pixels), the whole number is counted in
 * that phone's pixels, so the Previewer shows the world the phone shows.
 */
public final class Viewport {
    public final double designWidth, designHeight;
    public final String mode;
    private final boolean wholeScale;
    private final int phoneShortSide;

    /** The virtual size actually visible (differs from the design size only in "expand"). */
    public double width, height;
    public double scale = 1, offsetX, offsetY;
    public int surfaceWidth, surfaceHeight;

    public Viewport(double designWidth, double designHeight, String mode) {
        this(designWidth, designHeight, mode, false);
    }

    public Viewport(double designWidth, double designHeight, String mode, boolean wholeScale) {
        this(designWidth, designHeight, mode, wholeScale, 0);
    }

    /** phoneShortSide: the short side, in pixels, of the phone screen the surface stands for (0: the surface is one). */
    public Viewport(double designWidth, double designHeight, String mode, boolean wholeScale, int phoneShortSide) {
        this.wholeScale = wholeScale;
        this.phoneShortSide = phoneShortSide;
        this.designWidth = designWidth;
        this.designHeight = designHeight;
        this.mode = mode == null ? "fit" : mode;
        width = designWidth;
        height = designHeight;
    }

    public void update(int surfaceWidth, int surfaceHeight) {
        if (surfaceWidth == this.surfaceWidth && surfaceHeight == this.surfaceHeight) return;
        this.surfaceWidth = surfaceWidth;
        this.surfaceHeight = surfaceHeight;
        double sx = surfaceWidth / designWidth, sy = surfaceHeight / designHeight;
        double density = phoneShortSide > 0 && surfaceWidth > 0 && surfaceHeight > 0
                ? phoneShortSide / (double) Math.min(surfaceWidth, surfaceHeight) : 1;
        width = designWidth;
        height = designHeight;
        if (mode.equals("fill")) {
            scale = Math.max(sx, sy);
            if (wholeScale) scale = Math.ceil(scale * density - 1e-9) / density;
        } else {
            scale = Math.min(sx, sy);
            if (wholeScale && scale * density >= 1) scale = Math.floor(scale * density + 1e-9) / density;
            if (mode.equals("expand")) {
                width = surfaceWidth / scale;
                height = surfaceHeight / scale;
            }
        }
        offsetX = (surfaceWidth - width * scale) / 2;
        offsetY = (surfaceHeight - height * scale) / 2;
    }

    /** Virtual screen to surface pixels. */
    public Mat3 screenMatrix(Mat3 out) {
        return out.set(scale, 0, 0, scale, offsetX, offsetY);
    }

    public double toVirtualX(double surfaceX) {
        return (surfaceX - offsetX) / scale;
    }

    public double toVirtualY(double surfaceY) {
        return (surfaceY - offsetY) / scale;
    }
}
