package apkpygame.core;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentLinkedQueue;

/**
 * Touch, mouse and keys. Platforms post events from their own thread; the
 * game applies them at the start of each fixed step, so a step sees one
 * consistent state.
 *
 * Positions are given in virtual-screen units (x, y) and in world units
 * (worldX, worldY) through the scene's camera.
 */
public final class Input {
    public static final class Pointer {
        public final int id;
        public double x, y, worldX, worldY;
        public boolean down, pressed, released;
        /** The interface entity this finger went down on (top-most that takes presses); null: none, it is free. */
        public Entity owner;

        /** May this entity react to this finger? (not if the interface above it took it) */
        public boolean isFor(Entity e) {
            return owner == null || owner == e;
        }

        Pointer(int id) {
            this.id = id;
        }
    }

    private static final class Event {
        final int type;      // 0 down, 1 move, 2 up, 3 key down, 4 key up
        final int id;
        final double x, y;
        final String key;
        final boolean virtual;   // x, y already in virtual units (a journal played again)

        Event(int type, int id, double x, double y, String key, boolean virtual) {
            this.type = type;
            this.id = id;
            this.x = x;
            this.y = y;
            this.key = key;
            this.virtual = virtual;
        }
    }

    /** Virtual-screen point to world point: the 2D camera's inverse, or the 2.5D camera's ray to the ground. */
    public interface Picker {
        void toWorld(double virtualX, double virtualY, double[] out);
    }

    private final ConcurrentLinkedQueue<Event> events = new ConcurrentLinkedQueue<Event>();
    private final double[] picked = new double[2];
    private final List<Pointer> pointers = new ArrayList<Pointer>();
    private final Set<String> keys = new HashSet<String>();
    private final Set<String> keysPressed = new HashSet<String>();

    // ── from the platform (any thread), in surface pixels ────────────────

    public void pointerDown(int id, double surfaceX, double surfaceY) {
        events.add(new Event(0, id, surfaceX, surfaceY, null, false));
    }

    public void pointerMove(int id, double surfaceX, double surfaceY) {
        events.add(new Event(1, id, surfaceX, surfaceY, null, false));
    }

    public void pointerUp(int id, double surfaceX, double surfaceY) {
        events.add(new Event(2, id, surfaceX, surfaceY, null, false));
    }

    /** Key names: "left", "right", "up", "down", "space", "enter", "escape", "a".."z", "0".."9". */
    public void keyDown(String key) {
        events.add(new Event(3, 0, 0, 0, key, false));
    }

    public void keyUp(String key) {
        events.add(new Event(4, 0, 0, 0, key, false));
    }

    // ── for the game ─────────────────────────────────────────────────────

    /** Pointers currently down or released this step. */
    public List<Pointer> pointers() {
        return pointers;
    }

    /** Is the first finger on the interface? (a tap there is not a tap on the world) */
    public boolean pointerOnUi() {
        return !pointers.isEmpty() && pointers.get(0).owner != null;
    }

    public Pointer pointer() {
        return pointers.isEmpty() ? null : pointers.get(0);
    }

    public boolean pointerDown() {
        for (Pointer p : pointers) if (p.down) return true;
        return false;
    }

    public boolean pointerPressed() {
        for (Pointer p : pointers) if (p.pressed) return true;
        return false;
    }

    private final Set<String> virtualNext = new HashSet<String>();
    private final Set<String> virtual = new HashSet<String>();

    /**
     * A key held by an on-screen control (TouchButton) during this step. It
     * counts from the next step, with its own pressed edge, like a real key.
     */
    public void holdVirtual(String key) {
        virtualNext.add(key);
    }

    public boolean isKeyDown(String key) {
        return keys.contains(key) || virtual.contains(key);
    }

    public boolean wasKeyPressed(String key) {
        return keysPressed.contains(key);
    }

    /** -1, 0 or 1 from the arrow keys (and A/D). */
    public double axisX() {
        double v = 0;
        if (isKeyDown("left") || isKeyDown("a")) v -= 1;
        if (isKeyDown("right") || isKeyDown("d")) v += 1;
        return v;
    }

    public double axisY() {
        double v = 0;
        if (isKeyDown("up") || isKeyDown("w")) v -= 1;
        if (isKeyDown("down") || isKeyDown("s")) v += 1;
        return v;
    }

    /** A journal's event, played again (Game.restore): pointers in virtual units. */
    void inject(int type, int id, double virtualX, double virtualY, String key) {
        events.add(new Event(type, id, virtualX, virtualY, key, true));
    }

    /** Called by Game at the start of a step; each event goes into the journal as applied. */
    void apply(Viewport viewport, Picker picker, Journal journal, long step) {
        for (int i = pointers.size() - 1; i >= 0; i--) {
            Pointer p = pointers.get(i);
            if (p.released) pointers.remove(i);
            else p.pressed = false;
        }
        keysPressed.clear();
        if (!virtualNext.isEmpty() || !virtual.isEmpty()) {          // (no iterator garbage when unused)
            for (String k : virtualNext) if (!virtual.contains(k) && !keys.contains(k)) keysPressed.add(k);
            virtual.clear();
            virtual.addAll(virtualNext);
            virtualNext.clear();
        }
        Event e;
        while ((e = events.poll()) != null) {
            if (e.type >= 3) {
                if (journal != null) journal.key(step, e.type == 3, e.key);
                if (e.type == 3 && keys.add(e.key)) keysPressed.add(e.key);
                if (e.type == 4) keys.remove(e.key);
                continue;
            }
            Pointer p = find(e.id);
            if (p == null) {
                if (e.type != 0) continue;
                p = new Pointer(e.id);
                pointers.add(p);
            }
            p.x = e.virtual ? e.x : viewport.toVirtualX(e.x);
            p.y = e.virtual ? e.y : viewport.toVirtualY(e.y);
            if (journal != null) journal.pointer(step, e.type, e.id, p.x, p.y);
            picker.toWorld(p.x, p.y, picked);
            p.worldX = picked[0];
            p.worldY = picked[1];
            if (e.type == 0) {
                p.down = true;
                p.pressed = true;
                p.released = false;
            } else if (e.type == 2) {
                p.down = false;
                p.released = true;
            }
        }
    }

    private Pointer find(int id) {
        for (Pointer p : pointers) if (p.id == id) return p;
        return null;
    }
}
