package apkpygame.core.render;

import apkpygame.core.math.Mat3;

/**
 * One thing to draw. Commands are pooled by the RenderQueue: a backend reads
 * them during draw() and must not keep them.
 *
 * {@link #matrix} maps the command's local space to surface pixels; the local
 * rectangle is (x, y, w, h).
 */
public final class DrawCommand {
    public enum Kind { SPRITE, RECT, CIRCLE, TEXT, QUAD3D }

    public Kind kind;
    /** Drawn after everything that is not (see RenderQueue.drawingUi). */
    public boolean ui;
    /** Only this rectangle of the surface is drawn (pixels), when clipping. */
    public boolean clipping;
    public int clipX, clipY, clipW, clipH;
    public int layer, order;
    int seq;
    public final Mat3 matrix = new Mat3();

    public double x, y, w, h;
    /** SPRITE: the source region in texels. */
    public int srcX, srcY, srcW, srcH;
    public Texture texture;
    /** SPRITE: a multiply tint (white = none). Others: the colour. */
    public int color;
    public double alpha;
    public boolean smooth;
    /** RECT/CIRCLE */
    public boolean filled;
    public double stroke;
    /** TEXT: the size in local units, align -1 left, 0 centre, 1 right; the baseline is at y. */
    public String text;
    /** TEXT: what RenderBackend.loadFont made of the font's file; null: the system font. */
    public Object face;
    public double size;
    public int align;
    /**
     * QUAD3D (2.5D scenes): four corners in OpenGL world coordinates (x, elevation, y), in order around the
     * quad, and their texture coordinates (0..1 of the texture, or of the region srcX/Y/W/H when the texture
     * is a sheet). texture == null: a plain colour. cutout: texels under half alpha are not drawn (and do
     * not hide what is behind), as on the DS. The colour multiplies the texture (white = as is).
     */
    public final double[] xyz = new double[12];
    public final double[] uv = new double[8];
    public boolean cutout;
    public View3D view3d;

    void reset() {
        kind = null;
        layer = order = 0;
        matrix.identity();
        x = y = w = h = 0;
        srcX = srcY = srcW = srcH = 0;
        texture = null;
        color = 0xFFFFFFFF;
        alpha = 1;
        smooth = true;
        filled = true;
        stroke = 1;
        text = null;
        face = null;
        size = 16;
        align = -1;
        cutout = true;
        view3d = null;
    }
}
