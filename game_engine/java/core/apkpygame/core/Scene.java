package apkpygame.core;

import apkpygame.core.math.Color;
import apkpygame.core.math.Mat3;
import apkpygame.core.physics2d.Physics2D;
import apkpygame.core.render.Camera2D;
import apkpygame.core.render.RenderQueue;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * A level, a menu, a screen of the game: entities updated in a fixed step,
 * moved by the physics, drawn through a camera. {@code kind} is "2d" (a "3d"
 * kind gets its own systems later).
 *
 * One step: components update → physics (bodies, tiles, collisions) →
 * camera follow → rules → destroyed entities leave.
 */
public final class Scene {
    public final String name;
    public final String kind;
    public final Game game;
    /** 2D: the camera. 2.5D: its (x, y) is the ground point the 3D camera looks at. */
    public final Camera2D camera;
    /** "2.5d" scenes only (else null): the perspective camera, and what QUAD3D commands share each frame. */
    public final apkpygame.core.render.Camera3D camera3d;
    public final apkpygame.core.render.View3D view3d;
    /** 2.5D: the elevation of the point the camera looks at (the followed entity's). */
    public double cameraElevation;
    private double camPrevX, camPrevY, camPrevE;
    public final Physics2D physics;
    public int background;
    /** What game_play(scene, args) passed. */
    public final Map<String, Object> args;
    /** The music track (bundle path) played while the scene runs, or null. */
    public String music;
    public double musicVolume = 1;
    public boolean musicLoop = true;
    /** What Back (Android) or Esc (desktop) does; empty: end the game with {"reason": "back"}. */
    public final List<Actions.Action> onBack = new ArrayList<Actions.Action>();
    /** "when ... then ..." rules, checked after each step. */
    public final List<Rule> rules = new ArrayList<Rule>();
    /** The camera follows this entity (by name), within the bounds [x, y, w, h] if given. */
    public String follow;
    public double[] cameraBounds;

    private final java.util.Set<String> paused = new java.util.HashSet<String>();
    private final List<Entity> roots = new ArrayList<Entity>();
    /** Every entity, parents before children, in insertion order. */
    private final List<Entity> all = new ArrayList<Entity>();
    private final List<Component> starting = new ArrayList<Component>();
    private final List<Entity> doomed = new ArrayList<Entity>();
    private final List<Component> startingNow = new ArrayList<Component>();     // reused each step
    private final List<Entity> doomedNow = new ArrayList<Entity>();
    private final Mat3 local = new Mat3();
    private int nextId = 1;

    public Scene(Game game, String name, String kind, Map<String, Object> args) {
        this.game = game;
        this.name = name;
        this.kind = kind;
        this.args = args;
        this.camera = new Camera2D(game.viewport.designWidth / 2, game.viewport.designHeight / 2);
        boolean deep = "2.5d".equals(kind);
        this.camera3d = deep ? new apkpygame.core.render.Camera3D() : null;
        this.view3d = deep ? new apkpygame.core.render.View3D() : null;
        this.physics = new Physics2D(this);
        this.background = Color.BLACK;
    }

    /** A rule: when a variable (or the number of entities with a tag) meets a condition, run actions once. */
    public static final class Rule {
        public final String var, countTag, op;
        public final double value;
        public final List<Actions.Action> actions;
        boolean was;

        public Rule(String var, String countTag, String op, double value, List<Actions.Action> actions) {
            this.var = var;
            this.countTag = countTag;
            this.op = op;
            this.value = value;
            this.actions = actions;
        }

        boolean holds(Scene s) {
            return test(s, var, countTag, op, value);
        }

        /** var op value, or the number of entities tagged countTag op value: a rule's and only_if's condition. */
        public static boolean test(Scene s, String var, String countTag, String op, double value) {
            double v = countTag != null ? s.count(countTag) : s.game.var(var);
            if (op.equals("==")) return v == value;
            if (op.equals("!=")) return v != value;
            if (op.equals("<")) return v < value;
            if (op.equals("<=")) return v <= value;
            if (op.equals(">")) return v > value;
            return v >= value;
        }
    }

    /** Adds an entity (and its children) at the root of the scene. */
    public Entity spawn(Entity entity) {
        if (entity.scene != null) {
            throw new GameException("G3011", "entity '" + entity.name + "' is already in a scene",
                    "Make a new entity, or destroy() it first.");
        }
        roots.add(entity);
        adopt(entity);
        return entity;
    }

    /** A new entity from a bundle template, in no scene yet (a list's rows). */
    public Entity makeEntity(Map<String, Object> template) {
        return SceneLoader.entity(game, template);
    }

    /** A new entity from a bundle template (Spawner, spawn action), at the world point (x, y). */
    public Entity spawnTemplate(Map<String, Object> template, double x, double y) {
        Entity e = SceneLoader.entity(game, template);
        e.transform.x += x;
        e.transform.y += y;
        return spawn(e);
    }

    void adopt(Entity entity) {
        entity.scene = this;
        entity.id = nextId++;
        entity.transform.snap();
        entity.spawnX = entity.transform.x;
        entity.spawnY = entity.transform.y;
        all.add(entity);
        for (Component c : entity.components) componentAdded(c);
        for (Entity child : entity.children) adopt(child);
    }

    void componentAdded(Component c) {
        starting.add(c);
    }

    void destroyLater(Entity entity) {
        if (!entity.destroyed && !doomed.contains(entity)) doomed.add(entity);
    }

    /** scene.tile_tag(x, y, key): a property of the tile at a world point, from the scene's first Tilemap. */
    public String tileTag(double x, double y, String key) {
        for (Entity e : all) {
            apkpygame.core.components.Tilemap map = e.get(apkpygame.core.components.Tilemap.class);
            if (map != null) return map.tileTag(x, y, key);
        }
        return "";
    }

    // ── pausing ──────────────────────────────────────────────────────────

    /** The group stops (components, physics); it is still drawn. A menu pauses "world" and keeps "ui" going. */
    public void pause(String group) {
        paused.add(group);
    }

    public void resume(String group) {
        paused.remove(group);
    }

    public boolean isPaused(String group) {
        return paused.contains(group);
    }

    public boolean isPaused(Entity e) {
        return !paused.isEmpty() && paused.contains(e.groupName());
    }

    // ── presses, Back ────────────────────────────────────────────────────

    /** Each finger that just went down belongs to the top-most ui entity that takes it (if any). */
    private void claimPresses() {
        List<Input.Pointer> pointers = game.input.pointers();
        for (int k = 0; k < pointers.size(); k++) {
            Input.Pointer p = pointers.get(k);
            if (!p.pressed) continue;
            p.owner = null;
            int layer = 0, order = 0;
            for (int i = 0; i < all.size(); i++) {
                Entity e = all.get(i);
                if (!e.isUi() || !e.activeInTree() || isPaused(e)) continue;
                for (int j = 0; j < e.components.size(); j++) {
                    Component c = e.components.get(j);
                    if (!c.takesPress(p.x, p.y)) continue;
                    boolean over = p.owner == null || c.pressLayer() > layer
                            || c.pressLayer() == layer && c.pressOrder() >= order;
                    if (over) {
                        p.owner = e;
                        layer = c.pressLayer();
                        order = c.pressOrder();
                    }
                }
            }
        }
    }

    /** Back goes to the scripts, last added first (the menu on top), until one says it dealt with it. */
    boolean backToScripts() {
        for (int i = all.size() - 1; i >= 0; i--) {
            Entity e = all.get(i);
            if (!e.activeInTree() || isPaused(e)) continue;
            for (int j = 0; j < e.components.size(); j++) {
                Component c = e.components.get(j);
                if (c.started && c instanceof Script && ((Script) c).backPressed()) return true;
            }
        }
        return false;
    }

    // ── the interface and the screen's edges ─────────────────────────────

    public double anchorOffsetX(Entity e) {
        return e.anchorX == 0 ? 0 : (game.viewport.width - game.viewport.designWidth) * e.anchorX;
    }

    public double anchorOffsetY(Entity e) {
        return e.anchorY == 0 ? 0 : (game.viewport.height - game.viewport.designHeight) * e.anchorY;
    }

    // ── changing scene ───────────────────────────────────────────────────

    /** The entities that go along to the next scene, out of this one (no on_destroy: they live on). */
    List<Entity> takePersistent() {
        List<Entity> out = new ArrayList<Entity>();
        for (Entity e : roots) if (e.persistent && !e.destroyed && !doomed.contains(e)) out.add(e);
        for (Entity e : out) {
            roots.remove(e);
            leave(e);
        }
        return out;
    }

    private void leave(Entity e) {
        all.remove(e);
        e.scene = null;
        for (Entity child : e.children) leave(child);
    }

    /** An entity arriving from the last scene. One of the same name declared here gives way to it. */
    void receive(Entity e) {
        for (Entity same : new ArrayList<Entity>(roots)) {
            if (same.persistent && same.name.equals(e.name)) {
                roots.remove(same);
                leave(same);
                same.destroyed = true;
            }
        }
        spawn(e);
    }

    /** game.goto(scene, at): entities tagged "arrives" go to the entity (or Tiled object) of that name. */
    void arrive(String at) {
        Entity marker = null;
        for (Entity e : all) {
            if (at.equals(e.marker) || at.equals(e.name)) {
                marker = e;
                break;
            }
        }
        if (marker == null) {
            throw new GameException("G3024", "the scene '" + name + "' has nothing called '" + at + "' to arrive at",
                    "Name a Tiled object or an entity of that scene.");
        }
        for (Entity e : all) {
            if (!e.hasTag("arrives")) continue;
            e.transform.x = marker.worldX();
            e.transform.y = marker.worldY();
            e.transform.elevation = marker.transform.elevation;
            e.transform.snap();
        }
    }

    /** The camera on what it follows at once: a scene does not open with the camera on its way. */
    void settleCamera() {
        followCamera();
        camPrevX = camera.x;
        camPrevY = camera.y;
        camPrevE = cameraElevation;
    }

    /** A step with nothing moving (during a fade): frames between steps stay where they are. */
    void holdStill() {
        for (int i = 0; i < all.size(); i++) all.get(i).transform.savePrevious();
        camPrevX = camera.x;
        camPrevY = camera.y;
        camPrevE = cameraElevation;
    }

    public Entity find(String name) {
        for (Entity e : all) if (!e.destroyed && e.name.equals(name)) return e;
        return null;
    }

    public List<Entity> withTag(String tag) {
        List<Entity> out = new ArrayList<Entity>();
        for (Entity e : all) if (!e.destroyed && e.hasTag(tag) && !doomed.contains(e)) out.add(e);
        return out;
    }

    /** How many entities with this tag are in the scene (not counting ones destroyed this step). */
    public int count(String tag) {
        int n = 0;
        for (Entity e : all) if (!e.destroyed && e.hasTag(tag) && !doomed.contains(e)) n++;
        return n;
    }

    public int entityCount() {
        return all.size();
    }

    public List<Entity> entities() {
        return java.util.Collections.unmodifiableList(all);
    }

    // ── the step ─────────────────────────────────────────────────────────

    public boolean is25d() {
        return camera3d != null;
    }

    void step(double dt) {
        for (int i = 0; i < all.size(); i++) all.get(i).transform.savePrevious();
        camPrevX = camera.x;
        camPrevY = camera.y;
        camPrevE = cameraElevation;
        if (!starting.isEmpty()) {
            startingNow.addAll(starting);
            starting.clear();
            for (int i = 0; i < startingNow.size(); i++) {
                Component c = startingNow.get(i);
                if (!c.started && !c.entity.destroyed) {
                    c.started = true;
                    c.start();
                }
            }
            startingNow.clear();
        }
        claimPresses();
        // by index: entities spawned during the step are updated from the next one
        int count = all.size();
        for (int i = 0; i < count; i++) {
            Entity e = all.get(i);
            if (e.destroyed || !e.activeInTree() || isPaused(e)) continue;
            for (int j = 0; j < e.components.size(); j++) {
                Component c = e.components.get(j);
                if (c.started) c.update(dt);
            }
        }
        physics.step(dt);
        followCamera();
        for (int i = 0; i < rules.size(); i++) {
            Rule r = rules.get(i);
            boolean now = r.holds(this);
            if (now && !r.was && !game.isEnded()) Actions.runAll(r.actions, game, null, null);
            r.was = now;
        }
        if (!doomed.isEmpty()) {
            doomedNow.addAll(doomed);
            doomed.clear();
            for (int i = 0; i < doomedNow.size(); i++) remove(doomedNow.get(i));
            doomedNow.clear();
        }
    }

    private void followCamera() {
        if (follow == null) return;
        Entity target = find(follow);
        if (target == null) return;
        double x = target.worldX(), y = target.worldY();
        double halfW = game.viewport.width / 2 / camera.zoom, halfH = game.viewport.height / 2 / camera.zoom;
        double halfTop = halfH;
        if (is25d()) {
            cameraElevation = elevationOf(target);
            // in perspective the ground seen around the point looked at is not centred: from the point to the
            // bottom edge of the view (towards the camera), and half the width at that point to each side
            apkpygame.core.render.Camera3D c = camera3d;
            double p = StrictMath.toRadians(c.pitch), half = StrictMath.toRadians(c.fov / 2);
            double height = StrictMath.sin(p) * c.distance, ahead = StrictMath.cos(p) * c.distance;
            halfH = Math.max(0, ahead - height / StrictMath.tan(Math.min(p + half, Math.PI / 2 - 1e-6)));
            halfW = c.distance * StrictMath.tan(half) * game.viewport.width / game.viewport.height;
            halfTop = 0;
            if (c.yaw % 360 != 0) halfTop = halfW = halfH = Math.max(halfW, halfH);   // turned: the same margin all round
        }
        if (cameraBounds != null) {
            x = clamp(x, cameraBounds[0] + halfW, cameraBounds[0] + cameraBounds[2] - halfW);
            y = clamp(y, cameraBounds[1] + halfTop, cameraBounds[1] + cameraBounds[3] - halfH);
        }
        camera.x = x;
        camera.y = y;
    }

    private static double clamp(double v, double lo, double hi) {
        return lo > hi ? (lo + hi) / 2 : Math.max(lo, Math.min(hi, v));
    }

    private void remove(Entity e) {
        if (e.destroyed) return;
        for (Entity child : new ArrayList<Entity>(e.children)) remove(child);
        e.destroyed = true;
        for (Component c : e.components) c.destroyed();
        all.remove(e);
        roots.remove(e);
        if (e.parent != null) e.parent.children.remove(e);
        e.scene = null;
    }

    // ── drawing ──────────────────────────────────────────────────────────

    /** {@code view} maps world to surface pixels (screen * camera); {@code screen} maps the virtual screen (ui). */
    void render(RenderQueue queue, Mat3 view, Mat3 screen, double alpha) {
        if (is25d()) {
            ground.identity();
            for (int i = 0; i < roots.size(); i++) {
                Entity e = roots.get(i);
                if (e.ui) drawUi(e, queue, screen, alpha);
                else draw3d(e, queue, ground, 0, alpha);
            }
            return;
        }
        for (int i = 0; i < roots.size(); i++) {
            Entity e = roots.get(i);
            if (e.ui) drawUi(e, queue, screen, alpha);
            else draw(e, queue, view, alpha);
        }
    }

    private void drawUi(Entity e, RenderQueue queue, Mat3 screen, double alpha) {
        queue.drawingUi = true;
        draw(e, queue, screen, alpha);
        queue.drawingUi = false;
    }

    private final Mat3 ground = new Mat3();

    private void draw3d(Entity e, RenderQueue queue, Mat3 parentMatrix, double parentElevation, double alpha) {
        if (!e.active) return;
        e.transform.localMatrix(alpha, local);
        Mat3 m = e.renderMatrix.set(parentMatrix).multiply(local);
        double elevation = parentElevation + e.transform.elevation(alpha);
        for (int j = 0; j < e.components.size(); j++) {
            Component c = e.components.get(j);
            if (c.started) c.render3d(queue, m, elevation);
        }
        for (int i = 0; i < e.children.size(); i++) draw3d(e.children.get(i), queue, m, elevation, alpha);
    }

    /** An entity's height above the ground, its parents' included. */
    public static double elevationOf(Entity e) {
        double h = 0;
        for (Entity p = e; p != null; p = p.parent) h += p.transform.elevation;
        return h;
    }

    /**
     * 2.5D: points the camera (its matrices) at the target, between the last two steps at {@code alpha}
     * (1 for game logic: picking), for a view of {@code aspect}.
     */
    public void aimCamera3d(double alpha, double aspect) {
        double a = Math.max(0, Math.min(1, alpha));
        camera3d.update(camPrevX + (camera.x - camPrevX) * a, camPrevY + (camera.y - camPrevY) * a,
                camPrevE + (cameraElevation - camPrevE) * a, aspect);
    }

    private void draw(Entity e, RenderQueue queue, Mat3 parentMatrix, double alpha) {
        if (!e.active) return;
        e.transform.localMatrix(alpha, local);
        Mat3 m = e.renderMatrix.set(parentMatrix);
        if (e.anchorX != 0 || e.anchorY != 0) {
            double ox = anchorOffsetX(e), oy = anchorOffsetY(e);
            m.tx += m.a * ox + m.c * oy;
            m.ty += m.b * ox + m.d * oy;
        }
        m.multiply(local);
        boolean clipped = false;
        for (int j = 0; j < e.components.size(); j++) {
            Component c = e.components.get(j);
            if (c.started) {
                c.render(queue, m);
                if (c.clipChildren(queue, m)) clipped = true;
            }
        }
        for (int i = 0; i < e.children.size(); i++) draw(e.children.get(i), queue, m, alpha);
        if (clipped) queue.endScissor();
    }

    // ── checks ───────────────────────────────────────────────────────────

    /**
     * A hash of every transform, bit for bit: two platforms that ran the same
     * steps must give the same text (the parity test).
     */
    public String stateHash() {
        long h = 0xcbf29ce484222325L;
        for (Entity e : all) {
            h = mix(h, Double.doubleToLongBits(e.transform.x));
            h = mix(h, Double.doubleToLongBits(e.transform.y));
            h = mix(h, Double.doubleToLongBits(e.transform.rotation));
            h = mix(h, Double.doubleToLongBits(e.transform.scaleX));
            h = mix(h, Double.doubleToLongBits(e.transform.scaleY));
            if (e.transform.elevation != 0) h = mix(h, Double.doubleToLongBits(e.transform.elevation));
            apkpygame.core.components.Canvas canvas = e.get(apkpygame.core.components.Canvas.class);
            if (canvas != null) h = canvas.hash(h);              // what was painted (only in games that paint)
        }
        for (Map.Entry<String, Double> v : game.vars().entrySet()) {
            h = mix(h, v.getKey().hashCode());
            h = mix(h, Double.doubleToLongBits(v.getValue()));
        }
        if (ScriptState.any()) h = ScriptState.mixAll(h);     // module state (STATE = ... in game/ modules)
        return Long.toHexString(h);
    }

    private static long mix(long h, long v) {
        for (int i = 0; i < 8; i++) {
            h ^= (v >>> (i * 8)) & 0xFF;
            h *= 0x100000001b3L;
        }
        return h;
    }
}
