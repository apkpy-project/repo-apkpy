package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.Input;

/**
 * An on-screen button that holds a key while a finger is on it: "left",
 * "right", "jump", "space"... Controllers read it like the keyboard. Put it
 * on a ui entity with a Shape or Sprite (the area). It dims while pressed.
 */
public final class TouchButton extends Component {
    public String key = "space";
    public double pressedAlpha = 0.6;
    private final Area area = new Area();
    private double baseShape = -1, baseSprite = -1;

    public void setArea(double radius, double width, double height) {
        area.radius = radius;
        area.width = width;
        area.height = height;
    }

    @Override protected boolean takesPress(double x, double y) {
        return area.hit(entity(), x, y);
    }

    @Override protected void start() {
        Shape sh = entity().get(Shape.class);
        Sprite s = entity().get(Sprite.class);
        if (sh != null) baseShape = sh.alpha;
        if (s != null) baseSprite = s.alpha;
    }

    @Override protected void update(double dt) {
        boolean pressed = false;
        for (Input.Pointer p : game().input.pointers()) {
            // not isFor: a thumb sliding from one button to the next holds the next
            if (p.down && (p.owner == null || p.owner.get(TouchButton.class) != null) && area.hit(entity(), p)) {
                pressed = true;
                break;
            }
        }
        if (pressed) game().input.holdVirtual(key);
        Shape sh = entity().get(Shape.class);
        Sprite s = entity().get(Sprite.class);
        if (sh != null && baseShape >= 0) sh.alpha = pressed ? baseShape * pressedAlpha : baseShape;
        if (s != null && baseSprite >= 0) s.alpha = pressed ? baseSprite * pressedAlpha : baseSprite;
    }
}
