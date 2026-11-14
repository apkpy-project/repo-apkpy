package apkpygame.core.components;

import apkpygame.core.Entity;
import apkpygame.core.Input;

import java.util.List;

/** A click: a finger going down and coming up on the same thing; sliding off, or a list taking the finger, cancels. */
final class Clicker {
    private final Area area = new Area();
    private int holding = -1;
    /** A finger is on it now. */
    boolean over;

    void reset() {
        holding = -1;
        over = false;
    }

    /** Called each step: true in the step of a click. */
    boolean update(Entity e, Input input) {
        List<Input.Pointer> pointers = input.pointers();
        Input.Pointer held = null;
        for (int i = 0; i < pointers.size(); i++) {
            Input.Pointer p = pointers.get(i);
            if (holding < 0 && p.pressed && p.isFor(e) && area.hit(e, p)) holding = p.id;
            if (p.id == holding) held = p;
        }
        if (held == null || (held.owner != null && held.owner != e)) {
            reset();
            return false;
        }
        over = area.hit(e, held);
        if (!held.released) return false;
        boolean click = over;
        reset();
        return click;
    }
}
