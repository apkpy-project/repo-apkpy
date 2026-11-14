package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.math.Mat3;
import apkpygame.core.render.RenderQueue;

/**
 * A bar that fills from the left and glides to a new value (a life bar):
 * change value, and shown follows it at speed. Its colour changes at two
 * thresholds. Deterministic: scripts can wait for it (self.bar.moving).
 */
public final class Bar extends Component {
    public double value = 1, max = 1;
    public double width = 60, height = 6;
    public double pivotX, pivotY = 0.5;
    public int color = 0xFF58C858, midColor = 0xFFE8C840, lowColor = 0xFFD84840, back = 0xFF303030;
    /** Under these fractions of max, the bar takes midColor and lowColor. */
    public double midAt = 0.5, lowAt = 0.2;
    /** Fractions of max per second; 0: at once. */
    public double speed = 0.5;
    public double alpha = 1;
    public int layer, order;
    public boolean visible = true;
    /** What the bar shows now, on its way to value. */
    public double shown;

    @Override protected void start() {
        shown = value;
    }

    @Override protected void update(double dt) {
        if (speed <= 0) {
            shown = value;
            return;
        }
        double move = speed * max * dt;
        shown = shown < value ? Math.min(value, shown + move) : Math.max(value, shown - move);
    }

    public boolean moving() {
        return shown != value;
    }

    @Override protected void render(RenderQueue queue, Mat3 world) {
        if (!visible || alpha <= 0) return;
        double x = -pivotX * width, y = -pivotY * height;
        Panel.rect(queue, world, x, y, width, height, back, alpha, layer, order, true);
        double f = max > 0 ? Math.max(0, Math.min(1, shown / max)) : 0;
        if (f <= 0) return;
        int c = f <= lowAt ? lowColor : f <= midAt ? midColor : color;
        Panel.rect(queue, world, x, y, width * f, height, c, alpha, layer, order, true);
    }
}
