package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.Entity;
import apkpygame.core.Input;
import apkpygame.core.physics2d.TileGrid;

import java.util.ArrayList;
import java.util.List;

/**
 * Walks one cell at a time, from cell centre to cell centre, as in grid RPGs:
 * arrows/WASD (and TouchButton keys), or a tap on a cell (it walks there,
 * the longer axis first, and stops at anything in the way). A short press in
 * a new direction only turns the entity (its Billboard); holding it walks.
 * Solid tiles (the scene's Tilemap) and entities with one of the {@code block}
 * tags stop it: such an entity fills its own cell, and one with a Block (a house)
 * every cell the Block is on. 2D and 2.5D alike (the ground is the 2D world).
 */
public final class GridController extends Component {
    public double tile = 16;
    /** Cells per second. */
    public double speed = 4;
    public boolean tap = true;
    public final List<String> block = new ArrayList<String>();

    private boolean walking;
    private double fromX, fromY, toX, toY, progress;
    private int dirX, dirY = 1;
    private double turnHold;
    private boolean hasTarget;
    private int targetCol, targetRow;

    /** How many cells it has arrived at (when walking on without stopping, walking() stays true). */
    public int arrivals;

    /** Stops where it last arrived, and forgets where it was going (an event starts, a door...). */
    public void stop() {
        if (walking) {
            entity().transform.x = fromX;
            entity().transform.y = fromY;
        }
        walking = false;
        hasTarget = false;
        progress = 0;
    }

    /** Whether it is between two cells. */
    public boolean walking() {
        return walking;
    }

    @Override protected void start() {
        Entity e = entity();
        e.transform.x = centre(e.transform.x);          // stand on a cell's centre
        e.transform.y = centre(e.transform.y);
    }

    private double centre(double v) {
        return (Math.floor(v / tile) + 0.5) * tile;
    }

    @Override protected void update(double dt) {
        Entity e = entity();
        if (walking) {
            progress += speed * dt;
            if (progress < 1) {
                e.transform.x = fromX + (toX - fromX) * progress;
                e.transform.y = fromY + (toY - fromY) * progress;
                return;
            }
            e.transform.x = toX;
            e.transform.y = toY;
            walking = false;
            progress -= 1;
            arrivals++;
        } else {
            progress = 0;
        }
        Input in = game().input;
        if (tap && in.pointerPressed() && !in.pointerOnUi()) {
            Input.Pointer p = in.pointer();
            hasTarget = true;
            targetCol = (int) Math.floor(p.worldX / tile);
            targetRow = (int) Math.floor(p.worldY / tile);
        }
        int kx = (int) Math.signum(in.axisX()), ky = kx != 0 ? 0 : (int) Math.signum(in.axisY());
        if (kx != 0 || ky != 0) hasTarget = false;
        if (hasTarget) {
            int col = (int) Math.floor(e.transform.x / tile), row = (int) Math.floor(e.transform.y / tile);
            int dc = targetCol - col, dr = targetRow - row;
            if (dc == 0 && dr == 0) {
                hasTarget = false;
                return;
            }
            if (Math.abs(dc) >= Math.abs(dr)) kx = dc > 0 ? 1 : -1;
            else ky = dr > 0 ? 1 : -1;
            if (!step(e, kx, ky)) hasTarget = false;                    // something is in the way: stop there
            return;
        }
        if (kx == 0 && ky == 0) {
            turnHold = 0;
            progress = 0;
            walkedLast = false;
            return;
        }
        if ((kx != dirX || ky != dirY) && !walkedLast) {                // standing, a new direction: turn first
            face(kx, ky);
            turnHold = 0;
            return;
        }
        turnHold += dt;
        if (turnHold < 0.08 && !walkedLast) return;                   // a short press only turned
        step(e, kx, ky);
    }

    private boolean walkedLast;

    /** Starts walking one cell towards (kx, ky); false (and only turned) if the cell is blocked. */
    private boolean step(Entity e, int kx, int ky) {
        face(kx, ky);
        double nx = e.transform.x + kx * tile, ny = e.transform.y + ky * tile;
        if (blocked(e, nx, ny)) {
            walkedLast = false;
            return false;
        }
        fromX = e.transform.x;
        fromY = e.transform.y;
        toX = nx;
        toY = ny;
        walking = true;
        walkedLast = true;
        return true;
    }

    private void face(int kx, int ky) {
        dirX = kx;
        dirY = ky;
        Billboard b = entity().get(Billboard.class);
        if (b != null) b.facing = kx > 0 ? 90 : kx < 0 ? 270 : ky < 0 ? 180 : 0;
    }

    private boolean blocked(Entity self, double x, double y) {
        TileGrid tiles = scene().physics.tiles();
        if (tiles != null && tiles.solidAt(tiles.col(x), tiles.row(y))) return true;
        for (int i = 0; i < block.size(); i++) {
            for (Entity other : scene().withTag(block.get(i))) {
                if (other == self) continue;
                GridController g = other.get(GridController.class);
                double ox = g != null && g.walking ? g.toX : other.worldX(), oy = g != null && g.walking ? g.toY : other.worldY();
                Block box = other.get(Block.class);
                double hx = tile / 2, hy = tile / 2;
                if (box != null) {                                      // a cell the Block is on, even partly
                    hx = Math.max(hx, box.width / 2 + tile / 2 - 1);
                    hy = Math.max(hy, box.depth / 2 + tile / 2 - 1);
                }
                if (Math.abs(ox - x) < hx && Math.abs(oy - y) < hy) return true;
            }
        }
        return false;
    }
}
