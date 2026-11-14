package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.Entity;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Makes new entities from a template every {@code every} seconds (± jitter),
 * at the spawner's position (+ offset) or at a random point of {@code area}
 * [x, y, w, h] (relative to the spawner). {@code limit}: at most that many
 * alive; {@code total}: stops after that many (0: no limit).
 * Uses the game's seeded random: the same seed, the same waves.
 */
public final class Spawner extends Component {
    public Map<String, Object> template;
    public double every = 1, jitter, delay;
    public double offsetX, offsetY;
    public double[] area;
    public int limit, total;

    private double wait;
    private int made;
    private final List<Entity> alive = new ArrayList<Entity>();

    @Override protected void start() {
        wait = delay;
    }

    @Override protected void update(double dt) {
        if (template == null || (total > 0 && made >= total)) return;
        wait -= dt;
        if (wait > 0) return;
        wait = every + (jitter > 0 ? game().random.range(-jitter, jitter) : 0);
        for (int i = alive.size() - 1; i >= 0; i--) if (alive.get(i).isDestroyed()) alive.remove(i);
        if (limit > 0 && alive.size() >= limit) return;
        double x = entity().worldX() + offsetX, y = entity().worldY() + offsetY;
        if (area != null) {
            x += area[0] + game().random.next() * area[2];
            y += area[1] + game().random.next() * area[3];
        }
        alive.add(scene().spawnTemplate(template, x, y));
        made++;
    }
}
