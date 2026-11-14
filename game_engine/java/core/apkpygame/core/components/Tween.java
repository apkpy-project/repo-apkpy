package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.components.Transform2D;

/**
 * Animates one property from its start value to {@code to} in
 * {@code duration} seconds: x, y, rotation, scale, alpha (of the Sprite,
 * Shape or Text). mode: once | loop | pingpong. ease: linear | in | out |
 * inout | sine | back.
 */
public final class Tween extends Component {
    public String property = "scale", ease = "inout", mode = "pingpong";
    public double to = 1, duration = 1, delay;
    private double from, time;
    private boolean done;

    @Override protected void start() {
        from = get();
        time = -delay;
    }

    @Override protected void update(double dt) {
        if (done) return;
        time += dt;
        if (time < 0) return;
        double u = time / duration;
        if (mode.equals("once") && u >= 1) {
            set(to);
            done = true;
            return;
        }
        if (mode.equals("pingpong")) {
            u = u % 2;
            if (u > 1) u = 2 - u;
        } else {
            u = u % 1;
        }
        set(from + (to - from) * ease(u));
    }

    private double ease(double u) {
        if (ease.equals("linear")) return u;
        if (ease.equals("in")) return u * u;
        if (ease.equals("out")) return 1 - (1 - u) * (1 - u);
        if (ease.equals("sine")) return 0.5 - 0.5 * StrictMath.cos(Math.PI * u);
        if (ease.equals("back")) {
            double s = 1.70158;
            double v = u - 1;
            return 1 + v * v * ((s + 1) * v + s);
        }
        return u < 0.5 ? 2 * u * u : 1 - 2 * (1 - u) * (1 - u);
    }

    private double get() {
        Transform2D t = entity().transform;
        if (property.equals("x")) return t.x;
        if (property.equals("y")) return t.y;
        if (property.equals("rotation")) return t.rotation;
        if (property.equals("alpha")) {
            Sprite s = entity().get(Sprite.class);
            if (s != null) return s.alpha;
            Shape sh = entity().get(Shape.class);
            if (sh != null) return sh.alpha;
            Text tx = entity().get(Text.class);
            return tx != null ? tx.alpha : 1;
        }
        return t.scaleX;
    }

    private void set(double v) {
        Transform2D t = entity().transform;
        if (property.equals("x")) t.x = v;
        else if (property.equals("y")) t.y = v;
        else if (property.equals("rotation")) t.rotation = v;
        else if (property.equals("alpha")) {
            Sprite s = entity().get(Sprite.class);
            if (s != null) s.alpha = v;
            Shape sh = entity().get(Shape.class);
            if (sh != null) sh.alpha = v;
            Text tx = entity().get(Text.class);
            if (tx != null) tx.alpha = v;
        } else {
            t.scaleX = v;
            t.scaleY = v;
        }
    }
}
