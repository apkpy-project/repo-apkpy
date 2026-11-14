package apkpygame.core.components;

import apkpygame.core.Actions;
import apkpygame.core.Component;
import apkpygame.core.Input;

import java.util.ArrayList;
import java.util.List;

/**
 * Runs actions (see {@link Actions}), in order, when a finger (or the mouse)
 * goes down on the entity. The area is the entity's first Sprite or Shape, or
 * an explicit circle (radius) / rectangle (width x height, centred).
 */
public final class OnTap extends Component {
    public final List<Actions.Action> actions = new ArrayList<Actions.Action>();
    private final Area area = new Area();

    public void setArea(double radius, double width, double height) {
        area.radius = radius;
        area.width = width;
        area.height = height;
    }

    @Override protected void update(double dt) {
        for (Input.Pointer p : game().input.pointers()) {
            if (p.pressed && p.isFor(entity()) && area.hit(entity(), p)) {
                Actions.runAll(actions, game(), entity(), null);
                return;
            }
        }
    }

    @Override protected boolean takesPress(double x, double y) {
        return area.hit(entity(), x, y);
    }

    /** Is the point (world units; virtual-screen units for ui entities) inside the area? */
    public boolean hit(double x, double y) {
        return area.hit(entity(), x, y);
    }
}
