package apkpygame.core.components;

import apkpygame.core.Component;

/**
 * Moves the entity at a constant velocity (units per second). With
 * {@code bounce}, it turns back at the edges of the visible area.
 */
public final class Mover extends Component {
    public double vx, vy;
    public boolean bounce;

    public Mover(double vx, double vy, boolean bounce) {
        this.vx = vx;
        this.vy = vy;
        this.bounce = bounce;
    }

    @Override protected void update(double dt) {
        Transform2D t = entity().transform;
        t.x += vx * dt;
        t.y += vy * dt;
        if (!bounce) return;
        double w = game().viewport.designWidth, h = game().viewport.designHeight;
        if ((t.x < 0 && vx < 0) || (t.x > w && vx > 0)) vx = -vx;
        if ((t.y < 0 && vy < 0) || (t.y > h && vy > 0)) vy = -vy;
    }
}
