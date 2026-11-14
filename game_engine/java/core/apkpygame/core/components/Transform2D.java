package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.math.Mat3;

/**
 * Position, rotation (degrees) and scale relative to the parent entity.
 *
 * The previous step's values are kept so a frame between two steps is drawn
 * interpolated: movement stays smooth at 120 Hz with logic at 60 Hz.
 * {@link #snap()} after a teleport avoids drawing the jump as a slide.
 */
public final class Transform2D extends Component {
    public double x, y, rotation, scaleX = 1, scaleY = 1;
    /** 2.5D scenes: the height above the ground (world units, up). 2D scenes ignore it. */
    public double elevation;
    double px, py, pr, psx = 1, psy = 1, pe;

    public void set(double x, double y) {
        this.x = x;
        this.y = y;
    }

    public void snap() {
        px = x; py = y; pr = rotation; psx = scaleX; psy = scaleY; pe = elevation;
    }

    /** Called by the scene before each step. */
    public void savePrevious() {
        snap();
    }

    /** The elevation at {@code alpha} between the previous step (0) and this one (1). */
    public double elevation(double alpha) {
        return alpha >= 1 ? elevation : pe + (elevation - pe) * alpha;
    }

    /** Where it was at the previous step (2.5D: billboards turn to where they walk). */
    public double previousX() {
        return px;
    }

    public double previousY() {
        return py;
    }

    /** The local matrix at {@code alpha} between the previous step (0) and this one (1). */
    public Mat3 localMatrix(double alpha, Mat3 out) {
        if (alpha >= 1) return out.setTransform(x, y, rotation, scaleX, scaleY);
        return out.setTransform(px + (x - px) * alpha, py + (y - py) * alpha,
                pr + (rotation - pr) * alpha, psx + (scaleX - psx) * alpha, psy + (scaleY - psy) * alpha);
    }
}
