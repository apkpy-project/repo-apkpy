package apkpygame.core.physics2d;

import apkpygame.core.Component;
import apkpygame.core.Entity;
import apkpygame.core.Scene;
import apkpygame.core.components.OnCollide;
import apkpygame.core.math.Mat3;
import apkpygame.core.render.DrawCommand;
import apkpygame.core.render.RenderQueue;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;

/**
 * The scene's physics, run once per step after the components:
 * <ol>
 * <li>bodies: gravity, then movement X and Y (in small sub-steps, no
 * tunnelling), pushed out of solid tiles and solid colliders;</li>
 * <li>contacts: every pair of overlapping colliders (sort and sweep), and
 * every body stopped by a solid collider in this step (pushed back, it only
 * touches it); a pair that starts touching tells the OnCollide components of
 * both: a ball on a brick, a player at a door.</li>
 * </ol>
 * Deterministic: lists keep insertion order, no hashing decides an order.
 */
public final class Physics2D {
    private static final double EPS = 1e-7;

    private final Scene scene;
    private final List<Collider> colliders = new ArrayList<Collider>();
    private final List<Body> bodies = new ArrayList<Body>();
    private TileGrid tiles;
    private int serials;
    private LongSet touching = new LongSet(), nextTouching = new LongSet();
    private Body[] moving = new Body[64];
    private Collider[] sorted = new Collider[64];
    private final LongSet blocked = new LongSet();
    private final List<Collider> blockedPairs = new ArrayList<Collider>();

    public Physics2D(Scene scene) {
        this.scene = scene;
    }

    void add(Collider c) {
        c.serial = ++serials;
        colliders.add(c);
    }

    void remove(Collider c) {
        colliders.remove(c);
    }

    void add(Body b) {
        bodies.add(b);
    }

    void remove(Body b) {
        bodies.remove(b);
    }

    public void setTiles(TileGrid grid) {
        tiles = grid;
    }

    public TileGrid tiles() {
        return tiles;
    }

    public void step(double dt) {
        blocked.clear();
        blockedPairs.clear();
        int n = bodies.size();                      // a copy: a contact may add or remove bodies
        if (moving.length < n) moving = new Body[n * 2];
        bodies.toArray(moving);
        for (int i = 0; i < n; i++) {
            Body b = moving[i];
            moving[i] = null;
            Entity e = b.entity();
            if (!e.active || e.isDestroyed() || scene.isPaused(e)) continue;
            move(b, e, dt);
        }
        contacts();
    }

    // ── bodies ───────────────────────────────────────────────────────────

    private void move(Body b, Entity e, double dt) {
        if (b.gravity != 0) {
            b.vy += b.gravity * dt;
            if (b.vy > b.maxFall) b.vy = b.maxFall;
        }
        b.onFloor = b.onCeiling = b.onWallLeft = b.onWallRight = false;
        Collider c = solidShape(e);
        double dx = b.vx * dt, dy = b.vy * dt;
        if (c == null || !b.collide) {
            e.transform.x += dx;
            e.transform.y += dy;
            return;
        }
        c.bounds();
        double limit = Math.max(1, Math.min(c.hw, c.hh));
        if (tiles != null) limit = Math.min(limit, Math.min(tiles.tileW, tiles.tileH) / 2);
        int n = (int) Math.min(16, Math.ceil(Math.max(Math.abs(dx), Math.abs(dy)) / limit));
        if (n < 1) n = 1;
        for (int i = 0; i < n; i++) {
            if (dx != 0 && !(b.onWallLeft || b.onWallRight)) {
                e.transform.x += dx / n;
                c.bounds();
                resolveX(b, e, c, dx);
            }
            if (dy != 0 && !(b.onFloor || b.onCeiling)) {
                e.transform.y += dy / n;
                c.bounds();
                resolveY(b, e, c, dy);
            }
        }
    }

    private static Collider solidShape(Entity e) {
        for (Component comp : e.components()) {
            if (comp instanceof Collider && !((Collider) comp).trigger) return (Collider) comp;
        }
        return null;
    }

    private void resolveX(Body b, Entity e, Collider c, double dx) {
        double push = 0;
        if (tiles != null) {
            int r0 = tiles.row(c.top() + EPS), r1 = tiles.row(c.bottom() - EPS);
            if (dx > 0) {
                int col = tiles.col(c.right() - EPS);
                for (int r = r0; r <= r1; r++) {
                    if (tiles.solidAt(col, r)) push = Math.min(push, tiles.originX + col * tiles.tileW - c.right());
                }
            } else {
                int col = tiles.col(c.left() + EPS);
                for (int r = r0; r <= r1; r++) {
                    if (tiles.solidAt(col, r)) {
                        push = Math.max(push, tiles.originX + (col + 1) * tiles.tileW - c.left());
                    }
                }
            }
        }
        for (Collider s : colliders) {
            if (!s.solid || s.trigger || s.entity() == e || !s.entity().active) continue;
            s.bounds();
            if (!overlaps(c, s)) continue;
            stoppedBy(c, s);
            if (dx > 0) push = Math.min(push, s.left() - c.right());
            else push = Math.max(push, s.right() - c.left());
        }
        if (push != 0) {
            e.transform.x += push;
            c.bounds();
            if (dx > 0) b.onWallRight = true;
            else b.onWallLeft = true;
            b.vx = b.bounce > 0 ? -b.vx * b.bounce : 0;
        }
    }

    private void resolveY(Body b, Entity e, Collider c, double dy) {
        double push = 0;
        if (tiles != null) {
            int c0 = tiles.col(c.left() + EPS), c1 = tiles.col(c.right() - EPS);
            if (dy > 0) {
                int row = tiles.row(c.bottom() - EPS);
                for (int k = c0; k <= c1; k++) {
                    if (tiles.solidAt(k, row)) push = Math.min(push, tiles.originY + row * tiles.tileH - c.bottom());
                }
            } else {
                int row = tiles.row(c.top() + EPS);
                for (int k = c0; k <= c1; k++) {
                    if (tiles.solidAt(k, row)) {
                        push = Math.max(push, tiles.originY + (row + 1) * tiles.tileH - c.top());
                    }
                }
            }
        }
        for (Collider s : colliders) {
            if (!s.solid || s.trigger || s.entity() == e || !s.entity().active) continue;
            s.bounds();
            if (!overlaps(c, s)) continue;
            stoppedBy(c, s);
            if (dy > 0) push = Math.min(push, s.top() - c.bottom());
            else push = Math.max(push, s.bottom() - c.top());
        }
        if (push != 0) {
            e.transform.y += push;
            c.bounds();
            if (dy > 0) b.onFloor = true;
            else b.onCeiling = true;
            b.vy = b.bounce > 0 ? -b.vy * b.bounce : 0;
        }
    }

    /** The body's collider c ran into the solid s: after the push they only touch, so contacts() is told here. */
    private void stoppedBy(Collider c, Collider s) {
        long key = key(c, s);
        if (blocked.contains(key)) return;
        blocked.add(key);
        blockedPairs.add(c);
        blockedPairs.add(s);
    }

    private static long key(Collider a, Collider b) {
        return a.serial < b.serial ? ((long) a.serial << 32) | b.serial : ((long) b.serial << 32) | a.serial;
    }

    private static boolean overlaps(Collider a, Collider b) {
        return a.left() < b.right() - EPS && a.right() > b.left() + EPS
                && a.top() < b.bottom() - EPS && a.bottom() > b.top() + EPS;
    }

    // ── contacts ─────────────────────────────────────────────────────────

    private static final Comparator<Collider> BY_LEFT = new Comparator<Collider>() {
        @Override public int compare(Collider p, Collider q) {
            int c = Double.compare(p.left(), q.left());
            return c != 0 ? c : (p.serial < q.serial ? -1 : (p.serial == q.serial ? 0 : 1));
        }
    };

    private void contacts() {
        int n = 0;
        if (sorted.length < colliders.size()) sorted = new Collider[colliders.size() * 2];
        for (int i = 0; i < colliders.size(); i++) {
            Collider c = colliders.get(i);
            if (!c.entity().active || c.entity().isDestroyed() || c.entity().isUi()) continue;
            c.bounds();
            sorted[n++] = c;
        }
        // insertion sort: almost sorted from the last step, so close to linear, and no garbage
        // (the order is total, so it is the same order any sort would give: determinism holds)
        for (int i = 1; i < n; i++) {
            Collider c = sorted[i];
            int j = i - 1;
            while (j >= 0 && BY_LEFT.compare(sorted[j], c) > 0) {
                sorted[j + 1] = sorted[j];
                j--;
            }
            sorted[j + 1] = c;
        }
        nextTouching.clear();
        for (int i = 0; i < n; i++) {
            Collider a = sorted[i];
            for (int j = i + 1; j < n; j++) {
                Collider b = sorted[j];
                if (b.left() > a.right()) break;
                if (a.entity() == b.entity() || !touch(a, b)) continue;
                long key = key(a, b);
                nextTouching.add(key);
                if (!touching.contains(key)) {
                    tell(a, b);
                    tell(b, a);
                }
            }
        }
        java.util.Arrays.fill(sorted, 0, n, null);
        for (int i = 0; i < blockedPairs.size(); i += 2) {
            Collider a = blockedPairs.get(i), b = blockedPairs.get(i + 1);
            long key = key(a, b);
            if (nextTouching.contains(key)) continue;
            nextTouching.add(key);
            if (!touching.contains(key)) {
                a.bounds();
                b.bounds();
                tell(a, b);
                tell(b, a);
            }
        }
        LongSet t = touching;
        touching = nextTouching;
        nextTouching = t;
    }

    private static boolean touch(Collider a, Collider b) {
        if (a.circle && b.circle) {
            double dx = a.cx - b.cx, dy = a.cy - b.cy, r = a.hw + b.hw;
            return dx * dx + dy * dy < r * r;
        }
        if (a.circle || b.circle) {
            Collider round = a.circle ? a : b, box = a.circle ? b : a;
            double px = Math.max(box.left(), Math.min(round.cx, box.right()));
            double py = Math.max(box.top(), Math.min(round.cy, box.bottom()));
            double dx = round.cx - px, dy = round.cy - py;
            return dx * dx + dy * dy < round.hw * round.hw;
        }
        return overlaps(a, b);
    }

    /** {@code mine} started touching {@code theirs}: where is the other one, seen from mine? */
    private static void tell(Collider mine, Collider theirs) {
        Entity self = mine.entity(), other = theirs.entity();
        if (self.isDestroyed() || other.isDestroyed()) return;
        double ox = Math.min(mine.right(), theirs.right()) - Math.max(mine.left(), theirs.left());
        double oy = Math.min(mine.bottom(), theirs.bottom()) - Math.max(mine.top(), theirs.top());
        String side = oy < ox ? (theirs.cy < mine.cy ? "top" : "bottom") : "sides";
        for (Component comp : new ArrayList<Component>(self.components())) {
            if (comp instanceof OnCollide) ((OnCollide) comp).contact(other, side);
            else if (comp instanceof apkpygame.core.Script) ((apkpygame.core.Script) comp).collided(other, side);
        }
    }

    // ── debug ────────────────────────────────────────────────────────────

    /** Collider outlines (game.json "debug": true). */
    public void debugDraw(RenderQueue queue, Mat3 view) {
        for (Collider c : colliders) {
            if (!c.entity().active || c.entity().isUi()) continue;
            c.bounds();
            DrawCommand d = queue.add(c.circle ? DrawCommand.Kind.CIRCLE : DrawCommand.Kind.RECT);
            d.layer = Integer.MAX_VALUE - 2;
            d.matrix.set(view);
            d.x = c.left();
            d.y = c.top();
            d.w = c.hw * 2;
            d.h = c.hh * 2;
            d.filled = false;
            d.stroke = 1;
            d.color = c.trigger ? 0xFF5CD6FF : c.solid ? 0xFFFFD45C : 0xFF8AFF5C;
        }
    }
}
