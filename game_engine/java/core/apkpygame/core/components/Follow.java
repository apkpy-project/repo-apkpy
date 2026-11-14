package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.Entity;
import apkpygame.core.physics2d.Body;

/**
 * Moves towards an entity: the one called {@code target}, else the nearest
 * with {@code tag}. Stops within {@code stop} units. With a Body it sets the
 * velocity (x only if the body has gravity), without one it moves the transform.
 */
public final class Follow extends Component {
    public String target = "", tag = "";
    public double speed = 80, stop = 4;

    @Override protected void update(double dt) {
        Entity goal = target.isEmpty() ? nearest() : scene().find(target);
        if (goal == null) return;
        double dx = goal.worldX() - entity().worldX(), dy = goal.worldY() - entity().worldY();
        double dist = Math.sqrt(dx * dx + dy * dy);
        double v = dist <= stop ? 0 : Math.min(speed, (dist - stop) / dt);
        double vx = dist == 0 ? 0 : dx / dist * v, vy = dist == 0 ? 0 : dy / dist * v;
        Body b = entity().get(Body.class);
        if (b != null) {
            b.vx = b.gravity != 0 ? Math.signum(dx) * (Math.abs(dx) <= stop ? 0 : speed) : vx;
            if (b.gravity == 0) b.vy = vy;
        } else {
            entity().transform.x += vx * dt;
            entity().transform.y += vy * dt;
        }
    }

    private Entity nearest() {
        if (tag.isEmpty()) return null;
        Entity best = null;
        double bestD = Double.MAX_VALUE;
        for (Entity e : scene().withTag(tag)) {
            if (e == entity()) continue;
            double dx = e.worldX() - entity().worldX(), dy = e.worldY() - entity().worldY();
            double d = dx * dx + dy * dy;
            if (d < bestD) {
                bestD = d;
                best = e;
            }
        }
        return best;
    }
}
