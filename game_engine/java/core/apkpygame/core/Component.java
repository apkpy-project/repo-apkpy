package apkpygame.core;

import apkpygame.core.math.Mat3;
import apkpygame.core.render.RenderQueue;

/**
 * A piece of an entity: data (Sprite, Collider...) or behaviour (Spin, a
 * Script...). Subclasses override what they need.
 */
public abstract class Component {
    Entity entity;
    boolean started;

    public final Entity entity() {
        return entity;
    }

    public final Scene scene() {
        return entity.scene;
    }

    public final Game game() {
        return entity.scene.game;
    }

    /** Once, before the first update. */
    protected void start() { }

    /** Every fixed step. */
    protected void update(double dt) { }

    /**
     * Adds draw commands. {@code world} maps the entity's local space to
     * surface pixels (already interpolated); copy it, don't keep it.
     */
    protected void render(RenderQueue queue, Mat3 world) { }

    /**
     * 2.5D scenes: draw with QUAD3D commands. {@code world} places the entity on the ground (its tx, ty are the
     * ground point; rotation and scale as in 2D), {@code elevation} is its height (parents' included).
     * The scene's camera3d and view3d are ready. Nothing by default: a component that does not know the
     * 2.5D is not drawn there (UI entities, ui=True, are drawn in 2D as always).
     */
    protected void render3d(RenderQueue queue, Mat3 world, double elevation) { }

    /** Called after render: may start a scissor for the entity's children; true if it did (the scene ends it). */
    protected boolean clipChildren(RenderQueue queue, Mat3 world) {
        return false;
    }

    /** Does a finger going down at (x, y) of the virtual screen belong to this ui entity? */
    protected boolean takesPress(double x, double y) {
        return false;
    }

    /** Among several that take it, the highest layer and order wins (then the last added): what is drawn on top. */
    protected int pressLayer() {
        return 0;
    }

    protected int pressOrder() {
        return 0;
    }

    /** When the entity leaves the scene. */
    protected void destroyed() { }
}
