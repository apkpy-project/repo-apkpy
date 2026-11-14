package apkpygame.core.components;

import apkpygame.core.Actions;
import apkpygame.core.Component;
import apkpygame.core.math.Mat3;
import apkpygame.core.render.RenderQueue;
import apkpygame.core.render.Texture;

import java.util.ArrayList;
import java.util.List;

/**
 * A button with a label. A click is a finger that goes down on it and comes up
 * on it: sliding off cancels, as on any phone. On a click it plays its sound,
 * runs its actions, and scripts see self.button.clicked for one step.
 */
public final class Button extends Component implements Boxed {
    public String label = "";
    public double width = 100, height = 32;
    public double pivotX = 0.5, pivotY = 0.5;
    public int border = 8;
    public Texture image, pressedImage, disabledImage;
    public int color = 0xFF3A4252, pressedColor = 0xFF596479, disabledColor = 0xFF2A2E36, line = 0xFFE8E8E8;
    public int tint = 0xFFFFFFFF;
    public double alpha = 1;
    public int layer, order;
    public boolean smooth;
    public boolean enabled = true;
    public boolean visible = true;
    public String sound;
    public final List<Actions.Action> actions = new ArrayList<Actions.Action>();
    /** True during the step after a click (scripts read it whichever order they run in). */
    public boolean clicked;
    /** The label: its font, size and colour are this Text's. */
    public final Text text = new Text("");

    private final Area area = new Area();
    private final Clicker clicker = new Clicker();

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
        text.text = label;
        text.align = 0;
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
        clicked = false;
        text.text = label;
        text.visible = visible;
        text.alpha = alpha;
        text.offsetX = (0.5 - pivotX) * width;
        text.offsetY = (0.5 - pivotY) * height + text.size * 0.35;
        if (!enabled || !visible) {
            clicker.reset();
            return;
        }
        if (clicker.update(entity(), game().input)) {
            clicked = true;
            if (sound != null) game().playSound(sound, 1);
            Actions.runAll(actions, game(), entity(), null);
        }
    }

    @Override protected void render(RenderQueue queue, Mat3 world) {
        if (!visible || alpha <= 0) return;
        boolean over = clicker.over;
        Texture t = !enabled && disabledImage != null ? disabledImage
                : over && pressedImage != null ? pressedImage : image;
        int fill = !enabled ? disabledColor : over ? pressedColor : color;
        int shade = t != null && t == image && !enabled ? 0xFF808080 : t != null && t == image && over ? 0xFFC0C0C0 : tint;
        Panel.draw(queue, world, t, -pivotX * width, -pivotY * height, width, height, border, shade, fill, line, alpha,
                layer, order, smooth);
    }
}
