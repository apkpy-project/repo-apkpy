package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.Entity;
import apkpygame.core.Input;
import apkpygame.core.Script;
import apkpygame.core.math.Mat3;
import apkpygame.core.render.RenderQueue;

import java.util.List;
import java.util.Map;

/**
 * A long list (or a grid, columns greater than 1) that costs what its screen
 * costs: only the rows that fit exist, and they are used again as the list
 * scrolls; a Script on the entity fills each one in on_row(row, index). Drag
 * to scroll, with inertia worked out in the fixed step from the fingers, so a
 * replay scrolls the same everywhere. A row is an entity at the centre of its
 * cell; what is outside the list's box is not drawn and cannot be tapped.
 */
public final class ScrollList extends Component implements Boxed {
    private static final double DRAG = 4;           // virtual units a finger moves before it is a drag, not a tap
    private static final double FRICTION = 0.95;    // of the speed kept per step (at 60 steps per second)

    public Map<String, Object> template;
    public int count;
    public double width = 200, height = 200, itemWidth = 200, itemHeight = 32, gap;
    public int columns = 1;
    public double pivotX, pivotY;
    public int layer, order;
    /** The colour of the bar that shows the position; 0: no bar. */
    public int barColor = 0x80FFFFFF;
    public boolean visible = true;
    /** How far it has scrolled, from 0 to maxScroll(). */
    public double scroll;
    /** The index tapped in this step (a tap on the row, not taken by a Button in it), else -1. */
    public int tapped = -1;

    private final Area area = new Area();
    private final Mat3 inverse = new Mat3();
    private Entity[] rows = new Entity[0];
    private int[] shown = new int[0];
    private int shownCount = -1;
    private int holding = -1;
    private boolean dragging;
    private double startY, lastY, speed;

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

    /** Is this point (virtual screen) in the list's box? */
    boolean entityHit(double x, double y) {
        return area.hit(entity(), x, y);
    }

    public double maxScroll() {
        int lines = (count + columns - 1) / columns;
        return Math.max(0, lines * (itemHeight + gap) - gap - height);
    }

    /** Fill every row again (the data changed, not the number of rows). */
    public void refresh() {
        for (int i = 0; i < shown.length; i++) shown[i] = -1;
    }

    /** Puts the row of this index in view (at the top, if the list can go that far). */
    public void scrollTo(int index) {
        scroll = (index / columns) * (itemHeight + gap);
        speed = 0;
    }

    @Override protected void start() {
        int lines = (int) Math.ceil(height / (itemHeight + gap)) + 1;
        rows = new Entity[lines * columns];
        shown = new int[rows.length];
        Entity holder = new Entity("rows");
        holder.add(new Clip(this));
        entity().addChild(holder);
        for (int i = 0; i < rows.length; i++) {
            rows[i] = scene().makeEntity(template);
            rows[i].active = false;
            shown[i] = -1;
            holder.addChild(rows[i]);
        }
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

    /** May this list follow this finger? (it went down on the list or on something in it) */
    private boolean mine(Input.Pointer p) {
        for (Entity e = p.owner; e != null; e = e.parent()) if (e == entity()) return true;
        return p.owner == null;
    }

    @Override protected void update(double dt) {
        tapped = -1;
        follow();
        double max = maxScroll();
        if (scroll < 0 || scroll > max) {
            scroll = Math.max(0, Math.min(max, scroll));
            speed = 0;
        }
        if (count != shownCount) {
            shownCount = count;
            refresh();
        }
        place();
    }

    private void follow() {
        List<Input.Pointer> pointers = game().input.pointers();
        Input.Pointer held = null;
        for (int i = 0; i < pointers.size(); i++) {
            Input.Pointer p = pointers.get(i);
            if (holding < 0 && p.pressed && mine(p) && area.hit(entity(), p)) {
                holding = p.id;
                startY = lastY = p.y;
                dragging = false;
                speed = 0;
            }
            if (p.id == holding) held = p;
        }
        if (held == null) {
            holding = -1;
            scroll += speed;
            speed *= FRICTION;
            if (Math.abs(speed) < 0.05) speed = 0;
            return;
        }
        double moved = lastY - held.y;
        lastY = held.y;
        if (!dragging && Math.abs(held.y - startY) > DRAG) {
            dragging = true;
            held.owner = entity();                 // a Button under the finger lets go: this is a drag
        }
        if (dragging) {
            scroll += moved;
            speed = speed * 0.6 + moved * 0.4;
        }
        if (held.released) {
            if (!dragging && held.owner == entity()) tapped = indexAt(held);
            holding = -1;
        }
    }

    private int indexAt(Input.Pointer p) {
        entity().worldMatrix(inverse).invert();
        double lx = inverse.mapX(p.x, p.y) - boxLeft(), ly = inverse.mapY(p.x, p.y) - boxTop() + scroll;
        int col = (int) Math.floor(lx / (itemWidth + gap)), line = (int) Math.floor(ly / (itemHeight + gap));
        if (col < 0 || col >= columns || line < 0) return -1;
        if (lx - col * (itemWidth + gap) > itemWidth || ly - line * (itemHeight + gap) > itemHeight) return -1;
        int index = line * columns + col;
        return index < count ? index : -1;
    }

    private void place() {
        int firstLine = (int) Math.floor(scroll / (itemHeight + gap));
        for (int i = 0; i < rows.length; i++) {
            Entity row = rows[i];
            int index = firstLine * columns + i;
            boolean used = index < count;
            row.active = used;
            if (!used) {
                shown[i] = -1;
                continue;
            }
            int col = index % columns, line = index / columns;
            row.transform.x = boxLeft() + col * (itemWidth + gap) + itemWidth / 2;
            row.transform.y = boxTop() + line * (itemHeight + gap) + itemHeight / 2 - scroll;
            if (shown[i] != index) {
                shown[i] = index;
                row.transform.snap();             // used again elsewhere: it does not fly there
                fill(row, index);
            }
        }
    }

    private void fill(Entity row, int index) {
        List<Component> components = entity().components();
        for (int i = 0; i < components.size(); i++) {
            Component c = components.get(i);
            if (c instanceof Script) ((Script) c).rowShown(row, index);
        }
    }

    boolean scissor(RenderQueue queue, Mat3 world) {
        queue.beginScissor(world.mapX(boxLeft(), boxTop()), world.mapY(boxLeft(), boxTop()),
                world.mapX(boxLeft() + width, boxTop() + height), world.mapY(boxLeft() + width, boxTop() + height));
        return true;
    }

    @Override protected void render(RenderQueue queue, Mat3 world) {
        double max = maxScroll();
        if (!visible || barColor == 0 || max <= 0) return;
        double h = Math.max(12, height * height / (height + max));
        Panel.rect(queue, world, boxLeft() + width - 3, boxTop() + (height - h) * (scroll / max), 2, h, barColor, 1,
                layer, order + 1000, true);
    }
}
