package apkpygame.core;

import apkpygame.core.components.Area;
import apkpygame.core.json.Json;

import java.util.List;
import java.util.Map;

/**
 * The base of every game script: a class written in Python (class Ship(Script))
 * and translated to Java by apkpygame build. The translated class overrides
 * the on* methods; this base calls them, and turns a Java exception inside one
 * into a G3100 error that points at the Python line.
 */
public abstract class Script extends Component {
    private final Area tapArea = new Area();

    // ── what translated classes override ─────────────────────────────────

    protected void onStart() { }

    protected void onUpdate(double dt) { }

    protected void onCollide(Entity other, String side) { }

    protected void onTap() { }

    protected void onDestroy() { }

    /** on_row in Python: a ScrollList on this entity shows the row of this index. */
    protected void onRow(Entity row, int index) { }

    /** on_back in Python: True when it dealt with Back (closed its menu...). */
    protected boolean onBack() {
        return false;
    }

    /** True when the Python class defines on_tap (the base then checks taps on the entity). */
    protected boolean wantsTaps() {
        return false;
    }

    /** The Python file, and for each Java line of the translated class, its Python line (0: none). */
    protected String pythonFile() {
        return "game/main.py";
    }

    protected int[] pythonLines() {
        return new int[0];
    }

    // ── the engine's calls ───────────────────────────────────────────────

    @Override protected final void start() {
        try {
            onStart();
        } catch (RuntimeException e) {
            throw translated(e, "on_start");
        }
    }

    @Override protected final void update(double dt) {
        try {
            if (wantsTaps()) {
                for (Input.Pointer p : game().input.pointers()) {
                    if (p.pressed && p.isFor(entity()) && tapArea.hit(entity(), p)) {
                        onTap();
                        break;
                    }
                }
            }
            onUpdate(dt);
        } catch (RuntimeException e) {
            throw translated(e, "update");
        }
    }

    @Override protected final void destroyed() {
        try {
            onDestroy();
        } catch (RuntimeException e) {
            throw translated(e, "on_destroy");
        }
    }

    /** Called by a ScrollList on this entity. */
    public final void rowShown(Entity row, int index) {
        try {
            onRow(row, index);
        } catch (RuntimeException e) {
            throw translated(e, "on_row");
        }
    }

    /** Called when Back is pressed: did this script deal with it? */
    final boolean backPressed() {
        try {
            return onBack();
        } catch (RuntimeException e) {
            throw translated(e, "on_back");
        }
    }

    @Override protected boolean takesPress(double x, double y) {
        return wantsTaps() && tapArea.hit(entity(), x, y);
    }

    /** Called by the physics when this entity starts touching another. */
    public final void collided(Entity other, String side) {
        try {
            onCollide(other, side);
        } catch (RuntimeException e) {
            throw translated(e, "on_collide");
        }
    }

    private RuntimeException translated(RuntimeException e, String method) {
        if (e instanceof GameException) return e;
        int line = 0;
        int[] map = pythonLines();
        for (StackTraceElement s : e.getStackTrace()) {
            if (s.getClassName().equals(getClass().getName()) && s.getLineNumber() > 0
                    && s.getLineNumber() < map.length) {
                line = map[s.getLineNumber()];
                if (line > 0) break;
            }
        }
        String what = e instanceof Py.PyError ? e.getMessage() : e.toString();
        return new GameException("G3100", pythonFile() + (line > 0 ? ":" + line : "") + " (" + getClass().getSimpleName()
                + "." + method + "): " + what, "Fix the script at that line.", e);
    }

    // ── helpers the translated code uses ─────────────────────────────────

    protected final Scene sceneNow() {
        return game().scene();
    }

    @SuppressWarnings("unchecked")
    protected static Map<String, Object> template(Object o) {
        return (Map<String, Object>) o;
    }

    protected static Map<String, Object> templateOf(Map<String, Object> json, String key) {
        return Json.obj(json, key);
    }

    /** The first finger down (or the mouse), in world units; 0 when there is none. */
    protected final double pointerX() {
        Input.Pointer p = game().input.pointer();
        return p == null ? 0 : p.worldX;
    }

    protected final double pointerY() {
        Input.Pointer p = game().input.pointer();
        return p == null ? 0 : p.worldY;
    }

    protected static List<Entity> listOf(List<Entity> l) {
        return new java.util.ArrayList<Entity>(l);
    }
}
