package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.physics2d.Body;
import apkpygame.core.physics2d.Collider;
import apkpygame.core.physics2d.TileGrid;

/**
 * Walks left and right: turns at walls, at ledges (edges), or after
 * {@code distance} units from where it started (0: no limit). Needs a Body
 * (and a Collider for walls and ledges). Flips the Sprite.
 */
public final class Patrol extends Component {
    public double speed = 60, distance;
    public boolean edges = true;
    public int direction = 1;
    private double startX;

    @Override protected void start() {
        startX = entity().transform.x;
    }

    @Override protected void update(double dt) {
        Body b = entity().get(Body.class);
        if (b == null) return;
        if ((direction > 0 && b.onWallRight) || (direction < 0 && b.onWallLeft)) direction = -direction;
        double x = entity().transform.x;
        if (distance > 0 && ((direction > 0 && x - startX >= distance) || (direction < 0 && startX - x >= distance))) {
            direction = -direction;
        }
        if (edges && b.onFloor && ledgeAhead()) direction = -direction;
        b.vx = direction * speed;
        Sprite s = entity().get(Sprite.class);
        if (s != null) s.flipX = direction < 0;
    }

    private boolean ledgeAhead() {
        TileGrid tiles = scene().physics.tiles();
        Collider c = entity().get(Collider.class);
        if (tiles == null || c == null) return false;
        c.bounds();
        double footX = direction > 0 ? c.right() + 1 : c.left() - 1;
        return !tiles.solidAt(tiles.col(footX), tiles.row(c.bottom() + 1));
    }
}
