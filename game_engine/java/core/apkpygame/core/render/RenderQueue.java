package apkpygame.core.render;

import apkpygame.core.math.Mat3;

import java.util.Arrays;
import java.util.Comparator;

/**
 * What the scene wants drawn this frame: the world, then the interface, each
 * sorted by layer, then order, then submission. Scenes never draw: they fill this queue, and a RenderBackend
 * executes it. That separation is what lets a GLES (or 3D) backend come in
 * later without touching the scene code.
 */
public final class RenderQueue {
    private static final Comparator<DrawCommand> ORDER = new Comparator<DrawCommand>() {
        @Override public int compare(DrawCommand p, DrawCommand q) {
            if (p.ui != q.ui) return p.ui ? 1 : -1;
            if (p.layer != q.layer) return p.layer < q.layer ? -1 : 1;
            if (p.order != q.order) return p.order < q.order ? -1 : 1;
            return p.seq < q.seq ? -1 : (p.seq == q.seq ? 0 : 1);
        }
    };

    private DrawCommand[] pool = new DrawCommand[256];
    private double clipW = Double.MAX_VALUE, clipH = Double.MAX_VALUE;
    private int culled;
    private DrawCommand[] sorted = new DrawCommand[256];
    private int size;

    /** The commands added from now on belong to the interface (ui=True entities, the fade, the bars). */
    public boolean drawingUi;

    private int[] scissors = new int[16];
    private int depth;

    /** What is added from now on is only drawn inside this box of the surface (and of the box around it, if any). */
    public void beginScissor(double x0, double y0, double x1, double y1) {
        int left = (int) Math.floor(Math.min(x0, x1)), top = (int) Math.floor(Math.min(y0, y1));
        int right = (int) Math.ceil(Math.max(x0, x1)), bottom = (int) Math.ceil(Math.max(y0, y1));
        if (depth > 0) {
            int at = (depth - 1) * 4;
            left = Math.max(left, scissors[at]);
            top = Math.max(top, scissors[at + 1]);
            right = Math.min(right, scissors[at] + scissors[at + 2]);
            bottom = Math.min(bottom, scissors[at + 1] + scissors[at + 3]);
        }
        if ((depth + 1) * 4 > scissors.length) scissors = Arrays.copyOf(scissors, scissors.length * 2);
        int at = depth * 4;
        scissors[at] = left;
        scissors[at + 1] = top;
        scissors[at + 2] = Math.max(0, right - left);
        scissors[at + 3] = Math.max(0, bottom - top);
        depth++;
    }

    public void endScissor() {
        depth--;
    }

    public DrawCommand add(DrawCommand.Kind kind) {
        if (size == pool.length) {
            pool = Arrays.copyOf(pool, size * 2);
            sorted = new DrawCommand[pool.length];
        }
        DrawCommand c = pool[size];
        if (c == null) c = pool[size] = new DrawCommand();
        c.reset();
        c.kind = kind;
        c.ui = drawingUi;
        if (depth > 0) {
            c.clipping = true;
            int at = (depth - 1) * 4;
            c.clipX = scissors[at];
            c.clipY = scissors[at + 1];
            c.clipW = scissors[at + 2];
            c.clipH = scissors[at + 3];
        } else {
            c.clipping = false;
        }
        c.seq = size;
        size++;
        return c;
    }

    public int size() {
        return size;
    }

    public void clear() {
        size = 0;
    }

    /** The surface (pixels): commands that fall wholly outside it are not drawn (culling). */
    public void clip(double width, double height) {
        clipW = width;
        clipH = height;
    }

    /** How many commands the last flush left out because they were off the surface. */
    public int culled() {
        return culled;
    }

    /** Sorts, then hands every command on the surface to the backend, in order. */
    public void flush(RenderBackend backend) {
        int n = 0;
        culled = 0;
        for (int i = 0; i < size; i++) {
            if (visible(pool[i])) sorted[n++] = pool[i];
            else culled++;
        }
        Arrays.sort(sorted, 0, n, ORDER);
        for (int i = 0; i < n; i++) {
            backend.draw(sorted[i]);
        }
        clear();
    }

    /** A quad is left out when its four corners are all outside the same plane of the camera's frustum. */
    private static boolean inFrustum(DrawCommand c) {
        double[] m = c.view3d.viewProjection.m;
        int outside = 0x3F;
        for (int i = 0; i < 4; i++) {
            double x = c.xyz[i * 3], y = c.xyz[i * 3 + 1], z = c.xyz[i * 3 + 2];
            double cx = m[0] * x + m[4] * y + m[8] * z + m[12];
            double cy = m[1] * x + m[5] * y + m[9] * z + m[13];
            double cz = m[2] * x + m[6] * y + m[10] * z + m[14];
            double cw = m[3] * x + m[7] * y + m[11] * z + m[15];
            int bits = (cx < -cw ? 1 : 0) | (cx > cw ? 2 : 0) | (cy < -cw ? 4 : 0) | (cy > cw ? 8 : 0)
                    | (cz < -cw ? 16 : 0) | (cz > cw ? 32 : 0);
            outside &= bits;
            if (outside == 0) return true;
        }
        return false;
    }

    /** The box (x, y, w, h) through the matrix, against the surface. Text is always drawn (its width is the backend's). */
    private boolean visible(DrawCommand c) {
        if (c.kind == DrawCommand.Kind.TEXT) return true;
        if (c.kind == DrawCommand.Kind.QUAD3D) return inFrustum(c);
        Mat3 m = c.matrix;
        double x0 = c.x, y0 = c.y, x1 = c.x + c.w, y1 = c.y + c.h;
        double ax = m.mapX(x0, y0), ay = m.mapY(x0, y0), bx = m.mapX(x1, y0), by = m.mapY(x1, y0);
        double cx = m.mapX(x0, y1), cy = m.mapY(x0, y1), dx = m.mapX(x1, y1), dy = m.mapY(x1, y1);
        double pad = c.kind == DrawCommand.Kind.SPRITE ? 1 : c.stroke * (Math.abs(m.a) + Math.abs(m.b)) + 1;
        return Math.max(Math.max(ax, bx), Math.max(cx, dx)) >= -pad
                && Math.min(Math.min(ax, bx), Math.min(cx, dx)) <= clipW + pad
                && Math.max(Math.max(ay, by), Math.max(cy, dy)) >= -pad
                && Math.min(Math.min(ay, by), Math.min(cy, dy)) <= clipH + pad;
    }
}
