package apkpygame.core;

import apkpygame.core.components.Transform2D;
import apkpygame.core.math.Mat3;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** A thing in a scene: a name, tags, a transform, components and children. */
public final class Entity {
    public final String name;
    public final Transform2D transform = new Transform2D();
    public boolean active = true;
    /** The custom properties of the Tiled object it was made from (Props.NONE otherwise). */
    public Props props = Props.NONE;
    /** Drawn in screen space (virtual-screen units), over the world and outside the camera: HUD, buttons. */
    public boolean ui;
    /** Pausing group; null: its parent's, or "ui" / "world". */
    public String group;
    /** Goes along when the scene changes. */
    public boolean persistent;
    /** Interface entities: where the design area's spare room goes (0 left/top, 0.5 centre, 1 right/bottom). */
    public double anchorX, anchorY;
    /** The name of the Tiled object it was made from: where game.goto(..., at) can arrive. */
    public String marker;
    /** Where it entered the scene (respawn goes back there). */
    public double spawnX, spawnY;

    Scene scene;
    Entity parent;
    boolean destroyed;
    int id;
    final List<Component> components = new ArrayList<Component>();
    final List<Entity> children = new ArrayList<Entity>();
    private final List<String> tags = new ArrayList<String>();
    final Mat3 renderMatrix = new Mat3();
    private final Mat3 tmp = new Mat3(), local = new Mat3();

    public Entity(String name) {
        this.name = name == null ? "" : name;
        attach(transform);
    }

    public Entity add(Component component) {
        attach(component);
        if (scene != null) scene.componentAdded(component);
        return this;
    }

    private void attach(Component component) {
        if (component.entity != null) {
            throw new GameException("G3010", "a component can belong to one entity only",
                    "Make a new component for each entity.");
        }
        component.entity = this;
        components.add(component);
    }

    @SuppressWarnings("unchecked")
    public <T extends Component> T get(Class<T> type) {
        for (Component c : components) if (type.isInstance(c)) return (T) c;
        return null;
    }

    public List<Component> components() {
        return Collections.unmodifiableList(components);
    }

    public Entity addTag(String tag) {
        if (!tags.contains(tag)) tags.add(tag);
        return this;
    }

    public boolean hasTag(String tag) {
        return tags.contains(tag);
    }

    public List<String> tags() {
        return Collections.unmodifiableList(tags);
    }

    public Entity addChild(Entity child) {
        if (child.parent != null) child.parent.children.remove(child);
        child.parent = this;
        children.add(child);
        if (scene != null && child.scene == null) scene.adopt(child);
        return this;
    }

    public List<Entity> children() {
        return Collections.unmodifiableList(children);
    }

    public Entity parent() {
        return parent;
    }

    public Scene scene() {
        return scene;
    }

    public int id() {
        return id;
    }

    public String groupName() {
        for (Entity e = this; e != null; e = e.parent) if (e.group != null) return e.group;
        return isUi() ? "ui" : "world";
    }

    /** The first entity of this name below this one (self.entity.child("name")), or null. */
    public Entity child(String name) {
        for (int i = 0; i < children.size(); i++) {
            Entity c = children.get(i);
            if (c.name.equals(name)) return c;
            Entity deeper = c.child(name);
            if (deeper != null) return deeper;
        }
        return null;
    }

    /** It and all its parents are active. */
    public boolean activeInTree() {
        for (Entity e = this; e != null; e = e.parent) if (!e.active) return false;
        return true;
    }

    /** True for an entity drawn in screen space (it or an ancestor has ui). */
    public boolean isUi() {
        for (Entity e = this; e != null; e = e.parent) if (e.ui) return true;
        return false;
    }

    /** The transform from this entity's space to world space (to the virtual screen for ui), at the last step. */
    public Mat3 worldMatrix(Mat3 out) {
        if (parent == null) out.identity();
        else parent.worldMatrix(out);
        if (scene != null && (anchorX != 0 || anchorY != 0)) {
            double ox = scene.anchorOffsetX(this), oy = scene.anchorOffsetY(this);
            out.tx += out.a * ox + out.c * oy;
            out.ty += out.b * ox + out.d * oy;
        }
        return out.multiply(transform.localMatrix(1, local));
    }

    public double worldX() {
        return parent == null && anchorX == 0 ? transform.x : worldMatrix(tmp).tx;
    }

    public double worldY() {
        return parent == null && anchorY == 0 ? transform.y : worldMatrix(tmp).ty;
    }

    /** Leaves the scene at the end of the current step, with its children. */
    public void destroy() {
        if (scene != null) scene.destroyLater(this);
    }

    public boolean isDestroyed() {
        return destroyed;
    }
}
