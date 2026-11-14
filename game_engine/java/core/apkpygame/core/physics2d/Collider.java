package apkpygame.core.physics2d;

import apkpygame.core.Component;
import apkpygame.core.math.Mat3;

/**
 * The entity's shape for the physics: a box or a circle, around its position
 * (+ offset), scaled with it. Rotation is ignored (axis-aligned), which is what
 * arcade games want.
 *
 * {@code solid}: bodies cannot go through it (a platform, a wall).
 * {@code trigger}: only reports contacts (OnCollide), never blocks.
 */
public final class Collider extends Component {
    public boolean circle;
    public double width = 10, height = 10, radius = 5, offsetX, offsetY;
    public boolean solid, trigger;

    int serial;
    /** World-space centre and half sizes, refreshed by the physics each step. */
    public double cx, cy, hw, hh;
    private final Mat3 m = new Mat3();

    @Override protected void start() {
        scene().physics.add(this);
    }

    @Override protected void destroyed() {
        if (entity().scene() != null) scene().physics.remove(this);
    }

    /** Recomputes cx, cy, hw, hh from the entity's current transform. */
    public void bounds() {
        entity().worldMatrix(m);
        double sx = Math.sqrt(m.a * m.a + m.b * m.b), sy = Math.sqrt(m.c * m.c + m.d * m.d);
        cx = m.mapX(offsetX, offsetY);
        cy = m.mapY(offsetX, offsetY);
        hw = (circle ? radius : width / 2) * sx;
        hh = (circle ? radius : height / 2) * sy;
    }

    public double left() { return cx - hw; }
    public double right() { return cx + hw; }
    public double top() { return cy - hh; }
    public double bottom() { return cy + hh; }
}
