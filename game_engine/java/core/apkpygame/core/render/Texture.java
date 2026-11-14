package apkpygame.core.render;

/** An image loaded by the backend. {@code handle} is the backend's own object (Bitmap, BufferedImage...). */
public final class Texture {
    public final String path;
    public final int width, height;
    public final Object handle;

    /**
     * A Canvas's texture: the pixels the game paints, ARGB, row by row, owned by the core; null for an image of
     * the bundle. {@link #version} counts their changes, so a backend draws its own copy ({@link #live}) again
     * only when it moved ({@link #liveVersion} is the version that copy holds).
     */
    public final int[] pixels;
    public int version;
    public Object live;
    public int liveVersion = -1;

    public Texture(String path, int width, int height, Object handle) {
        this.path = path;
        this.width = width;
        this.height = height;
        this.handle = handle;
        this.pixels = null;
    }

    /** A texture the game paints (see Canvas): {@code pixels} is width x height, and stays this texture's. */
    public Texture(String path, int width, int height, int[] pixels) {
        this.path = path;
        this.width = width;
        this.height = height;
        this.handle = null;
        this.pixels = pixels;
    }
}
