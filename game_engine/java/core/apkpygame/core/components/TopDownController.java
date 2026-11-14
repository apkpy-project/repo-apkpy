package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.Input;
import apkpygame.core.components.Transform2D;
import apkpygame.core.physics2d.Body;

/**
 * Moves in 2D at {@code speed}: towards the finger while it is down (pointer),
 * else with the arrow keys / WASD / TouchButtons. {@code axis} limits it to
 * "x" or "y" (a ship at the bottom of the screen). {@code clamp} keeps it on
 * the game area. With a Body it sets the velocity (and collides), without one
 * it moves the transform.
 */
public final class TopDownController extends Component {
    public double speed = 200;
    public String axis = "both";
    public boolean pointer = true, clamp = true;
    public double margin = 16;

    @Override protected void update(double dt) {
        Input in = game().input;
        Transform2D t = entity().transform;
        double vx = 0, vy = 0;
        Input.Pointer p = pointer ? firstDown(in) : null;
        if (p != null) {
            double dx = p.worldX - entity().worldX(), dy = p.worldY - entity().worldY();
            if (axis.equals("x")) dy = 0;
            if (axis.equals("y")) dx = 0;
            double dist = Math.sqrt(dx * dx + dy * dy);
            if (dist > 0.5) {
                double v = Math.min(speed, dist / dt);
                vx = dx / dist * v;
                vy = dy / dist * v;
            }
        } else {
            vx = axis.equals("y") ? 0 : in.axisX() * speed;
            vy = axis.equals("x") ? 0 : in.axisY() * speed;
            if (vx != 0 && vy != 0) {
                vx *= 0.70710678118654752;
                vy *= 0.70710678118654752;
            }
        }
        Body b = entity().get(Body.class);
        if (b != null) {
            b.vx = vx;
            b.vy = vy;
        } else {
            t.x += vx * dt;
            t.y += vy * dt;
        }
        if (clamp) {
            double w = game().viewport.designWidth, h = game().viewport.designHeight;
            t.x = Math.max(margin, Math.min(w - margin, t.x));
            t.y = Math.max(margin, Math.min(h - margin, t.y));
        }
    }

    private static Input.Pointer firstDown(Input in) {
        for (Input.Pointer p : in.pointers()) if (p.down && p.owner == null) return p;
        return null;
    }
}
