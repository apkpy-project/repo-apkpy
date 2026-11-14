package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.math.Color;
import apkpygame.core.math.Mat3;
import apkpygame.core.render.DrawCommand;
import apkpygame.core.render.RenderQueue;

/** A rectangle or a circle, filled or outlined: for prototypes, effects and simple UI. */
public final class Shape extends Component {
    public boolean circle;
    /** Rectangle size; for a circle, width is the diameter. */
    public double width = 10, height = 10;
    public double pivotX = 0.5, pivotY = 0.5;
    public int color = Color.WHITE;
    public double alpha = 1;
    public boolean filled = true;
    public double stroke = 1;
    public int layer, order;
    public boolean visible = true;

    public void setColor(String hex) {
        color = Color.parse(hex, color);
    }

    public static Shape rect(double w, double h, int color) {
        Shape s = new Shape();
        s.width = w;
        s.height = h;
        s.color = color;
        return s;
    }

    public static Shape circle(double radius, int color) {
        Shape s = new Shape();
        s.circle = true;
        s.width = s.height = radius * 2;
        s.color = color;
        return s;
    }

    @Override protected void render(RenderQueue queue, Mat3 world) {
        if (!visible || alpha <= 0) return;
        DrawCommand c = queue.add(circle ? DrawCommand.Kind.CIRCLE : DrawCommand.Kind.RECT);
        c.layer = layer;
        c.order = order;
        c.matrix.set(world);
        c.x = -pivotX * width;
        c.y = -pivotY * height;
        c.w = width;
        c.h = height;
        c.color = Color.withAlpha(color, alpha);
        c.filled = filled;
        c.stroke = stroke;
    }
}
