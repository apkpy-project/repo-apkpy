package apkpygame.core.physics2d;

import apkpygame.core.Component;

/**
 * Arcade physics: velocity, gravity, and (with a Collider) blocked by solid
 * tiles and solid colliders. Controllers set vx/vy; the physics moves the
 * entity after all components have updated.
 */
public final class Body extends Component {
    public double vx, vy;
    /** Units per second², downwards (0: no gravity). */
    public double gravity;
    public double maxFall = 1200;
    /** 0: stop at walls; 1: bounce back at the same speed. */
    public double bounce;
    /** Blocked by solid tiles and colliders (needs a non-trigger Collider). */
    public boolean collide = true;

    public boolean onFloor, onCeiling, onWallLeft, onWallRight;

    @Override protected void start() {
        scene().physics.add(this);
    }

    @Override protected void destroyed() {
        if (entity().scene() != null) scene().physics.remove(this);
    }
}
