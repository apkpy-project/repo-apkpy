package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.math.Mat3;
import apkpygame.core.render.RenderQueue;
import apkpygame.core.render.Texture;

/** A box that is on or off, with a label beside it. Scripts: self.toggle.value, self.toggle.changed (for one step). */
public final class Toggle extends Component implements Boxed {
    public String label = "";
    public boolean value;
    public boolean changed;
    public boolean enabled = true, visible = true;
    public double width = 120, height = 24;
    public double pivotX, pivotY = 0.5;
    public Texture image, onImage;
    public int border = 4;
    public int color = 0xFF3A4252, onColor = 0xFF58C858, line = 0xFFE8E8E8;
    public int layer, order;
    public boolean smooth;
    public String sound;
    public final Text text = new Text("");

    private final Clicker clicker = new Clicker();
    private final Area area = new Area();

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

    @Override protected void start() {
        text.layer = layer;
        text.order = order + 1;
        entity().add(text);
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

    @Override protected void update(double dt) {
        changed = false;
        text.text = label;
        text.visible = visible;
        text.offsetX = boxLeft() + height + 6;
        text.offsetY = boxTop() + height / 2 + text.size * 0.35;
        if (!enabled || !visible) {
            clicker.reset();
            return;
        }
        if (clicker.update(entity(), game().input)) {
            value = !value;
            changed = true;
            if (sound != null) game().playSound(sound, 1);
        }
    }

    @Override protected void render(RenderQueue queue, Mat3 world) {
        if (!visible) return;
        Texture t = value && onImage != null ? onImage : image;
        Panel.draw(queue, world, t, boxLeft(), boxTop(), height, height, border, 0xFFFFFFFF, color, line, 1, layer, order,
                smooth);
        if (value && onImage == null) {                     // the mark
            double inset = height / 4;
            Panel.rect(queue, world, boxLeft() + inset, boxTop() + inset, height - 2 * inset, height - 2 * inset, onColor, 1,
                    layer, order, true);
        }
    }
}
