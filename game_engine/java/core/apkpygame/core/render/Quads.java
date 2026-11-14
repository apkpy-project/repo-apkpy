package apkpygame.core.render;

/**
 * Helpers for the components that draw 2.5D scenes with QUAD3D commands.
 * Corners are given in game terms: ground (x, y) and elevation e; they are
 * stored in OpenGL terms (x, e, y). The 3D image is drawn under the 2D one
 * (UI), so QUAD3D commands take the lowest layers: the opaque/cutout ones
 * first (a depth buffer sorts them), then the see-through ones, far to near.
 */
public final class Quads {
    public static final int LAYER_SOLID = Integer.MIN_VALUE + 1000;
    public static final int LAYER_SEE_THROUGH = Integer.MIN_VALUE + 1001;

    private Quads() { }

    /** A new QUAD3D: texture (null: a plain colour), colour (multiplies), alpha. */
    public static DrawCommand add(RenderQueue queue, View3D view, Texture texture, int color, double alpha,
                                  boolean smooth) {
        DrawCommand c = queue.add(DrawCommand.Kind.QUAD3D);
        c.view3d = view;
        c.texture = texture;
        c.color = color;
        c.alpha = alpha;
        c.smooth = smooth;
        boolean seeThrough = alpha < 1 || (color >>> 24) < 255;
        c.cutout = !seeThrough;
        c.layer = seeThrough ? LAYER_SEE_THROUGH : LAYER_SOLID;
        return c;
    }

    /** Corner i (0..3, in order around the quad) at ground (x, y), elevation e. */
    public static void corner(DrawCommand c, int i, double x, double y, double e) {
        c.xyz[i * 3] = x;
        c.xyz[i * 3 + 1] = e;
        c.xyz[i * 3 + 2] = y;
    }

    /**
     * Texture coordinates for a region of the texture (texels), corners 0..3 being bottom-left, bottom-right,
     * top-right, top-left of the picture. Without a texture: anything.
     */
    public static void region(DrawCommand c, double sx, double sy, double sw, double sh, boolean flipX) {
        double tw = c.texture == null ? 1 : c.texture.width, th = c.texture == null ? 1 : c.texture.height;
        double u0 = sx / tw, u1 = (sx + sw) / tw, v0 = sy / th, v1 = (sy + sh) / th;
        if (flipX) {
            double t = u0;
            u0 = u1;
            u1 = t;
        }
        double[] uv = c.uv;
        uv[0] = u0; uv[1] = v1;
        uv[2] = u1; uv[3] = v1;
        uv[4] = u1; uv[5] = v0;
        uv[6] = u0; uv[7] = v0;
    }

    /** See-through quads are drawn far to near: their order is minus their distance to the eye. */
    public static void sortSeeThrough(DrawCommand c) {
        if (c.cutout) return;
        View3D v = c.view3d;
        double x = (c.xyz[0] + c.xyz[6]) / 2 - v.eyeX, y = (c.xyz[1] + c.xyz[7]) / 2 - v.eyeY,
                z = (c.xyz[2] + c.xyz[8]) / 2 - v.eyeZ;
        c.order = -(int) Math.min(Integer.MAX_VALUE / 2, Math.sqrt(x * x + y * y + z * z) * 16);
    }

    /** Shade factor (0..1) applied to a colour's RGB: the DS look gives each side of a block its own light. */
    public static int shade(int argb, double k) {
        int r = (int) (((argb >> 16) & 255) * k), g = (int) (((argb >> 8) & 255) * k), b = (int) ((argb & 255) * k);
        return (argb & 0xFF000000) | (r << 16) | (g << 8) | b;
    }
}
