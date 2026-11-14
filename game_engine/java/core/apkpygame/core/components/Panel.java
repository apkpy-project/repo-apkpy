package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.math.Color;
import apkpygame.core.math.Mat3;
import apkpygame.core.render.DrawCommand;
import apkpygame.core.render.RenderQueue;
import apkpygame.core.render.Texture;

/**
 * A box of any size: an image cut in nine (the corners keep their size, the
 * edges and the middle stretch), or a plain colour with a line around it for
 * prototypes. modal: a press anywhere on the screen stops here, so what is
 * below an open menu cannot be tapped.
 */
public final class Panel extends Component implements Boxed {
    public Texture texture;
    public double width = 100, height = 100;
    public int border = 8;
    public double pivotX = 0.5, pivotY = 0.5;
    public int tint = Color.WHITE;
    public int color = 0xFF20242C, line = 0xFFE8E8E8;
    public double alpha = 1;
    public int layer, order;
    public boolean smooth;
    public boolean modal;
    public boolean visible = true;

    @Override public double boxLeft() {
        return -pivotX * width;
    }

    @Override public double boxTop() {
        return -pivotY * height;
    }

    @Override public double boxWidth() {
        return width;
    }

    @Override public double boxHeight() {
        return height;
    }

    @Override protected boolean takesPress(double x, double y) {
        return modal;
    }

    @Override protected int pressLayer() {
        return layer;
    }

    @Override protected int pressOrder() {
        return order;
    }

    @Override protected void render(RenderQueue queue, Mat3 world) {
        if (!visible || alpha <= 0) return;
        draw(queue, world, texture, -pivotX * width, -pivotY * height, width, height, border, tint, color, line, alpha,
                layer, order, smooth);
    }

    /** Shared with Button. */
    static void draw(RenderQueue q, Mat3 world, Texture t, double x, double y, double w, double h, int border,
                     int tint, int color, int line, double alpha, int layer, int order, boolean smooth) {
        if (t == null) {
            rect(q, world, x, y, w, h, color, alpha, layer, order, true);
            rect(q, world, x + 0.5, y + 0.5, w - 1, h - 1, line, alpha, layer, order, false);
            return;
        }
        int b = Math.min(border, Math.min(t.width, t.height) / 2);
        double mw = Math.max(0, w - 2 * b), mh = Math.max(0, h - 2 * b);
        int tw = t.width - 2 * b, th = t.height - 2 * b;
        double[] xs = {x, x + b, x + b + mw};
        double[] ys = {y, y + b, y + b + mh};
        double[] ws = {b, mw, b};
        double[] hs = {b, mh, b};
        int[] sx = {0, b, t.width - b};
        int[] sy = {0, b, t.height - b};
        int[] sw = {b, tw, b};
        int[] sh = {b, th, b};
        for (int r = 0; r < 3; r++) {
            for (int c = 0; c < 3; c++) {
                if (ws[c] <= 0 || hs[r] <= 0 || sw[c] <= 0 || sh[r] <= 0) continue;
                DrawCommand d = q.add(DrawCommand.Kind.SPRITE);
                d.layer = layer;
                d.order = order;
                d.matrix.set(world);
                d.texture = t;
                d.srcX = sx[c];
                d.srcY = sy[r];
                d.srcW = sw[c];
                d.srcH = sh[r];
                d.x = xs[c];
                d.y = ys[r];
                d.w = ws[c];
                d.h = hs[r];
                d.color = tint;
                d.alpha = alpha;
                d.smooth = smooth;
            }
        }
    }

    static void rect(RenderQueue q, Mat3 world, double x, double y, double w, double h, int color, double alpha,
                     int layer, int order, boolean filled) {
        DrawCommand d = q.add(DrawCommand.Kind.RECT);
        d.layer = layer;
        d.order = order;
        d.matrix.set(world);
        d.x = x;
        d.y = y;
        d.w = w;
        d.h = h;
        d.color = Color.withAlpha(color, alpha);
        d.filled = filled;
    }
}
