package apkpygame.core.components;

import apkpygame.core.Entity;
import apkpygame.core.Input;
import apkpygame.core.math.Mat3;

/**
 * "Is this point on the entity?": its first Sprite or Shape as drawn, or an
 * explicit circle (radius) / centred rectangle (width x height). Used by
 * OnTap and TouchButton. A ui entity is hit in virtual-screen units, a world
 * entity in world units.
 */
public final class Area {
    private final Mat3 world = new Mat3();
    public double radius, width, height;

    public boolean hit(Entity e, Input.Pointer p) {
        return e.isUi() ? hit(e, p.x, p.y) : hit(e, p.worldX, p.worldY);
    }

    public boolean hit(Entity e, double x, double y) {
        for (Entity p = e.parent(); p != null; p = p.parent()) {          // not in a list's box: not there
            Clip clip = p.get(Clip.class);
            if (clip != null && !clip.list.entityHit(x, y)) return false;
        }
        e.worldMatrix(world).invert();
        double lx = world.mapX(x, y), ly = world.mapY(x, y);
        if (radius > 0) return lx * lx + ly * ly <= radius * radius;
        if (width > 0 && height > 0) return Math.abs(lx) <= width / 2 && Math.abs(ly) <= height / 2;
        java.util.List<apkpygame.core.Component> parts = e.components();
        for (int i = 0; i < parts.size(); i++) {
            if (parts.get(i) instanceof Boxed) {
                Boxed b = (Boxed) parts.get(i);
                return lx >= b.boxLeft() && lx <= b.boxLeft() + b.boxWidth()
                        && ly >= b.boxTop() && ly <= b.boxTop() + b.boxHeight();
            }
        }
        Sprite s = e.get(Sprite.class);
        if (s != null) {
            double left = -s.pivotX * s.srcW, top = -s.pivotY * s.srcH;
            return lx >= left && lx <= left + s.srcW && ly >= top && ly <= top + s.srcH;
        }
        Shape sh = e.get(Shape.class);
        if (sh != null) {
            double left = -sh.pivotX * sh.width, top = -sh.pivotY * sh.height;
            if (sh.circle) {
                double rx = sh.width / 2, ry = sh.height / 2;
                double dx = (lx - left - rx) / rx, dy = (ly - top - ry) / ry;
                return dx * dx + dy * dy <= 1;
            }
            return lx >= left && lx <= left + sh.width && ly >= top && ly <= top + sh.height;
        }
        return false;
    }
}
