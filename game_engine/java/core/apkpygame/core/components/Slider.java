package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.Input;
import apkpygame.core.math.Mat3;
import apkpygame.core.render.RenderQueue;
import apkpygame.core.render.Texture;

import java.util.List;

/** A value set with a finger along a track. Scripts: self.slider.value, self.slider.changed (for one step). */
public final class Slider extends Component implements Boxed {
    public double value, min, max = 1;
    /** Values go in these steps; 0: any. */
    public double step;
    public boolean changed;
    public boolean enabled = true, visible = true;
    public double width = 160, height = 24;
    public double pivotX, pivotY = 0.5;
    public int color = 0xFF58C858, back = 0xFF303030, thumb = 0xFFE8E8E8;
    /** The thumb, instead of a colour. */
    public Texture image;
    public int layer, order;
    public boolean smooth;

    private final Area area = new Area();
    private final Mat3 inverse = new Mat3();
    private int holding = -1;

    @Override public double boxLeft() {
        return -pivotX * width;
    }

    @Override public double boxTop() {
        return -pivotY * height;
    }

    @Override public double boxWidth() {
        return width;
    }

    @Override public double boxHeight() {
        return height;
    }

    @Override protected boolean takesPress(double x, double y) {
        return visible && area.hit(entity(), x, y);
    }

    @Override protected int pressLayer() {
        return layer;
    }

    @Override protected int pressOrder() {
        return order;
    }

    private double thumbWidth() {
        return height / 2;
    }

    @Override protected void update(double dt) {
        changed = false;
        if (!enabled || !visible) {
            holding = -1;
            return;
        }
        List<Input.Pointer> pointers = game().input.pointers();
        Input.Pointer held = null;
        for (int i = 0; i < pointers.size(); i++) {
            Input.Pointer p = pointers.get(i);
            if (holding < 0 && p.pressed && p.isFor(entity()) && area.hit(entity(), p)) holding = p.id;
            if (p.id == holding) held = p;
        }
        if (held == null) {
            holding = -1;
            return;
        }
        entity().worldMatrix(inverse).invert();
        double room = Math.max(1, width - thumbWidth());
        double f = (inverse.mapX(held.x, held.y) - boxLeft() - thumbWidth() / 2) / room;
        double v = min + Math.max(0, Math.min(1, f)) * (max - min);
        if (step > 0) v = min + Math.rint((v - min) / step) * step;
        v = Math.max(min, Math.min(max, v));
        if (v != value) {
            value = v;
            changed = true;
        }
        if (held.released) holding = -1;
    }

    @Override protected void render(RenderQueue queue, Mat3 world) {
        if (!visible) return;
        double f = max > min ? Math.max(0, Math.min(1, (value - min) / (max - min))) : 0;
        double trackY = boxTop() + height / 2 - 2, tw = thumbWidth();
        double at = boxLeft() + f * (width - tw);
        Panel.rect(queue, world, boxLeft(), trackY, width, 4, back, 1, layer, order, true);
        Panel.rect(queue, world, boxLeft(), trackY, at + tw / 2 - boxLeft(), 4, color, 1, layer, order, true);
        if (image != null) {
            Panel.draw(queue, world, image, at, boxTop(), tw, height, 0, 0xFFFFFFFF, 0, 0, 1, layer, order, smooth);
        } else {
            Panel.rect(queue, world, at, boxTop(), tw, height, thumb, 1, layer, order, true);
        }
    }
}
