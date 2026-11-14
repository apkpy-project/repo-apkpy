package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.Input;
import apkpygame.core.Py;
import apkpygame.core.math.Color;
import apkpygame.core.math.Mat3;
import apkpygame.core.render.DrawCommand;
import apkpygame.core.render.Png;
import apkpygame.core.render.RenderQueue;
import apkpygame.core.render.Texture;

import java.util.HashMap;
import java.util.Map;

/**
 * Pixels the game paints while it runs: a picture of width x height pixels that scripts change one at a time
 * (set, get), or with lines, rectangles, circles, fills and stamps of the game's images, and that the player
 * can paint with a finger (a brush). One pixel is one world unit, as a texel of a Sprite; the pivot is the
 * point placed at the entity's position.
 *
 * A pixel is replaced, never mixed, so what a script reads back is what it wrote; only stamp() lays an image
 * over what is there. Colours are whole numbers and the brush's path plain double arithmetic (exact on every
 * JVM), so a replay paints the same pixels on every platform, and
 * the pixels are part of the state hash the parity check compares.
 */
public final class Canvas extends Component implements Boxed {
    private static int made;

    public final int width, height;
    private final int[] pixels;
    private final Texture texture;
    public double pivotX = 0.5, pivotY = 0.5;
    public double alpha = 1;
    public int layer, order;
    /** false (the default): each pixel stays a sharp square when the canvas is drawn bigger. */
    public boolean smooth;
    public boolean visible = true;
    /** The width in pixels of what the brush leaves. */
    public int brushSize = 1;
    /** Did the player's brush change a pixel in the last step? */
    public boolean changed;

    private int brush;
    private boolean painting;
    /**
     * Where each finger painting a stroke was at the step before (pointer id -> x, y in canvas pixels, not
     * rounded, and the pixel last painted).
     */
    private final Map<Integer, double[]> strokes = new HashMap<Integer, double[]>();
    private final Mat3 inverse = new Mat3();
    private final double[] local = new double[2];
    private String lastText;
    private int lastColor;

    public Canvas(int width, int height) {
        if (width < 1 || height < 1 || (long) width * height > 4096L * 4096L) {
            throw new apkpygame.core.GameException("G3025", "a Canvas of " + width + " x " + height + " pixels",
                    "Each side is 1 or more, and the whole canvas at most 4096 x 4096 pixels.");
        }
        this.width = width;
        this.height = height;
        this.pixels = new int[width * height];
        this.texture = new Texture("canvas#" + (++made), width, height, pixels);
    }

    // ── what the game declared ──────────────────────────────────────────

    /** The pixels of an image (from its top-left corner, or from a region of it), where they fit. */
    public void start(Png image, int x, int y, int w, int h) {
        for (int row = 0; row < Math.min(h, height); row++) {
            for (int col = 0; col < Math.min(w, width); col++) {
                int sx = x + col, sy = y + row;
                if (sx >= 0 && sy >= 0 && sx < image.width && sy < image.height) {
                    pixels[row * width + col] = image.argb[sy * image.width + sx];
                }
            }
        }
        touched();
    }

    public void setBrushColor(int argb) {
        brush = argb;
        painting = true;
    }

    // ── for scripts ──────────────────────────────────────────────────────

    public void set(int x, int y, String color) {
        if (x >= 0 && y >= 0 && x < width && y < height) {
            pixels[y * width + x] = colour(color);
            touched();
        }
    }

    /** "#rrggbb" ("#aarrggbb" when it is not opaque); "" outside the canvas. */
    public String get(int x, int y) {
        if (x < 0 || y < 0 || x >= width || y >= height) return "";
        return text(pixels[y * width + x]);
    }

    public void fill(String color) {
        java.util.Arrays.fill(pixels, colour(color));
        touched();
    }

    public void clear() {
        java.util.Arrays.fill(pixels, 0);
        touched();
    }

    public void rect(int x, int y, int w, int h, String color) {
        int argb = colour(color);
        int x0 = Math.max(0, x), y0 = Math.max(0, y);
        int x1 = Math.min(width, x + Math.max(0, w)), y1 = Math.min(height, y + Math.max(0, h));
        for (int row = y0; row < y1; row++) java.util.Arrays.fill(pixels, row * width + x0, row * width + Math.max(x0, x1), argb);
        touched();
    }

    public void line(int x1, int y1, int x2, int y2, String color) {
        int argb = colour(color);
        int dx = Math.abs(x2 - x1), dy = -Math.abs(y2 - y1);
        int sx = x1 < x2 ? 1 : -1, sy = y1 < y2 ? 1 : -1;
        int err = dx + dy;
        while (true) {
            put(x1, y1, argb);
            if (x1 == x2 && y1 == y2) break;
            int e2 = 2 * err;
            if (e2 >= dy) {
                err += dy;
                x1 += sx;
            }
            if (e2 <= dx) {
                err += dx;
                y1 += sy;
            }
        }
        touched();
    }

    /** A filled circle: the pixels whose distance to (cx, cy) is at most radius (a little rounder, as drawn by hand). */
    public void circle(int cx, int cy, int radius, String color) {
        int argb = colour(color);
        int r = Math.max(0, radius);
        for (int dy = -r; dy <= r; dy++) {
            for (int dx = -r; dx <= r; dx++) {
                if (dx * dx + dy * dy <= r * r + r) put(cx + dx, cy + dy, argb);
            }
        }
        touched();
    }

    /** The paint bucket: the area of the colour at (x, y), joined by sides, becomes this colour. */
    public void flood(int x, int y, String color) {
        int argb = colour(color);
        if (x < 0 || y < 0 || x >= width || y >= height) return;
        int old = pixels[y * width + x];
        if (old == argb) return;
        int[] stack = new int[64];
        int top = 0;
        stack[top++] = y * width + x;
        while (top > 0) {
            int at = stack[--top];
            int row = at / width;
            int left = at % width, right = left;
            if (pixels[at] != old) continue;
            while (left > 0 && pixels[row * width + left - 1] == old) left--;
            while (right < width - 1 && pixels[row * width + right + 1] == old) right++;
            for (int col = left; col <= right; col++) {
                pixels[row * width + col] = argb;
                for (int next = row - 1; next <= row + 1; next += 2) {
                    if (next < 0 || next >= height) continue;
                    int i = next * width + col;
                    if (pixels[i] == old && (col == left || pixels[i - 1] != old)) {
                        if (top == stack.length) stack = java.util.Arrays.copyOf(stack, top * 2);
                        stack[top++] = i;
                    }
                }
            }
        }
        touched();
    }

    /** How many pixels are exactly this colour. */
    public int count(String color) {
        int argb = colour(color), n = 0;
        for (int p : pixels) if (p == argb) n++;
        return n;
    }

    /** An image of the game laid over the canvas with its top-left corner at (x, y): its see-through parts mix. */
    public void stamp(String image, int x, int y) {
        Png png = game().assets.get("pixels", image);
        for (int row = 0; row < png.height; row++) {
            int ty = y + row;
            if (ty < 0 || ty >= height) continue;
            for (int col = 0; col < png.width; col++) {
                int tx = x + col;
                if (tx < 0 || tx >= width) continue;
                int i = ty * width + tx;
                pixels[i] = over(png.argb[row * png.width + col], pixels[i]);
            }
        }
        touched();
    }

    /** The colour the player paints with ("" stops the brush). */
    public void setBrush(String color) {
        if (color == null || color.isEmpty()) {
            painting = false;
            strokes.clear();
        } else {
            setBrushColor(colour(color));
        }
    }

    public String brushText() {
        return painting ? text(brush) : "";
    }

    /** The pixel under the first finger (or the mouse); -1 when there is none or it is off the canvas. */
    public int pointerX() {
        return pointerPixel() ? (int) Math.floor(local[0]) : -1;
    }

    public int pointerY() {
        return pointerPixel() ? (int) Math.floor(local[1]) : -1;
    }

    private boolean pointerPixel() {
        Input.Pointer p = game().input.pointer();
        if (p == null || !toPixels(p)) return false;
        return local[0] >= 0 && local[1] >= 0 && local[0] < width && local[1] < height;
    }

    // ── the engine ───────────────────────────────────────────────────────

    @Override protected void update(double dt) {
        changed = false;
        if (!painting || !visible) {
            strokes.clear();
            return;
        }
        for (Input.Pointer p : game().input.pointers()) {
            if (!p.down) {
                strokes.remove(p.id);
                continue;
            }
            double[] last = strokes.get(p.id);
            if (last == null && !(p.pressed && p.isFor(entity()))) continue;      // a stroke starts on the canvas
            if (!toPixels(p)) continue;
            if (last == null) {
                int px = (int) Math.floor(local[0]), py = (int) Math.floor(local[1]);
                if (px < 0 || py < 0 || px >= width || py >= height) continue;
                dab(px, py);
                strokes.put(p.id, new double[]{local[0], local[1], px, py});
            } else if (last[0] != local[0] || last[1] != local[1]) {
                stroke(last, local[0], local[1]);
            }
        }
    }

    /** The finger's point in canvas pixels (local[0], local[1]); false when it cannot be placed. */
    private boolean toPixels(Input.Pointer p) {
        entity().worldMatrix(inverse);
        if (inverse.a * inverse.d - inverse.b * inverse.c == 0) return false;
        inverse.invert();
        boolean ui = entity().isUi();
        double x = ui ? p.x : p.worldX, y = ui ? p.y : p.worldY;
        local[0] = inverse.mapX(x, y) + pivotX * width;
        local[1] = inverse.mapY(x, y) + pivotY * height;
        return true;
    }

    /**
     * From where the finger was at the step before to where it is, along the true line between the two points
     * (steps of at most a pixel, so no gap however fast the finger). Joining the pixels instead would bend a
     * slow diagonal at every step, where rounding moved its ends. Plain double arithmetic: the same on every JVM.
     */
    private void stroke(double[] last, double x2, double y2) {
        double x1 = last[0], y1 = last[1];
        int px = (int) last[2], py = (int) last[3];
        int n = (int) Math.ceil(Math.max(Math.abs(x2 - x1), Math.abs(y2 - y1)));
        for (int i = 1; i <= n; i++) {
            double t = (double) i / n;
            int x = (int) Math.floor(x1 + (x2 - x1) * t), y = (int) Math.floor(y1 + (y2 - y1) * t);
            if (x != px || y != py) {
                dab(x, y);
                px = x;
                py = y;
            }
        }
        last[0] = x2;
        last[1] = y2;
        last[2] = px;
        last[3] = py;
    }

    /** What the brush leaves at a pixel: that pixel at size 1, a round spot as wide as brushSize otherwise. */
    private void dab(int x, int y) {
        int s = Math.max(1, brushSize);
        boolean any = false;
        for (int dy = -s; dy <= s; dy++) {
            for (int dx = -s; dx <= s; dx++) {
                if (4 * (dx * dx + dy * dy) > s * s) continue;
                int px = x + dx, py = y + dy;
                if (px < 0 || py < 0 || px >= width || py >= height) continue;
                int i = py * width + px;
                if (pixels[i] != brush) {
                    pixels[i] = brush;
                    any = true;
                }
            }
        }
        if (any) {
            changed = true;
            touched();
        }
    }

    private void put(int x, int y, int argb) {
        if (x >= 0 && y >= 0 && x < width && y < height) pixels[y * width + x] = argb;
    }

    private void touched() {
        texture.version++;
    }

    /** A colour of a script, read once while it stays the same text (a loop that paints with one colour). */
    private int colour(String text) {
        if (text != null && text.equals(lastText)) return lastColor;
        int argb = Color.parse(text, 1);                         // 1 is "#00000001", which no one writes
        if (argb == 1 && !"#00000001".equals(text)) {
            throw new Py.PyError("ValueError: '" + text + "' is not a colour (write \"#rrggbb\" or \"#aarrggbb\")");
        }
        lastText = text;
        lastColor = argb;
        return argb;
    }

    static String text(int argb) {
        String hex = Integer.toHexString(argb & 0xFFFFFF);
        while (hex.length() < 6) hex = "0" + hex;
        if ((argb >>> 24) == 255) return "#" + hex;
        String a = Integer.toHexString(argb >>> 24);
        return "#" + (a.length() < 2 ? "0" + a : a) + hex;
    }

    /** src over dst, in whole numbers (the same on every platform). */
    static int over(int src, int dst) {
        int sa = src >>> 24;
        if (sa == 255) return src;
        if (sa == 0) return dst;
        int da = dst >>> 24;
        int outA = sa + da * (255 - sa) / 255;
        if (outA == 0) return 0;
        int r = channel(src >> 16, dst >> 16, sa, da, outA);
        int g = channel(src >> 8, dst >> 8, sa, da, outA);
        int b = channel(src, dst, sa, da, outA);
        return (outA << 24) | (r << 16) | (g << 8) | b;
    }

    private static int channel(int s, int d, int sa, int da, int outA) {
        s &= 255;
        d &= 255;
        return (s * sa * 255 + d * da * (255 - sa) + outA * 255 / 2) / (outA * 255);
    }

    /** What the backends draw: the canvas's own pixels, with the count of their changes. */
    public Texture texture() {
        return texture;
    }

    /** The pixels, for the state hash. */
    public long hash(long h) {
        for (int p : pixels) {
            for (int i = 0; i < 4; i++) {
                h ^= (p >>> (i * 8)) & 0xFF;
                h *= 0x100000001b3L;
            }
        }
        return h;
    }

    @Override protected void render(RenderQueue queue, Mat3 world) {
        if (!visible || alpha <= 0) return;
        DrawCommand c = queue.add(DrawCommand.Kind.SPRITE);
        c.layer = layer;
        c.order = order;
        c.matrix.set(world);
        c.texture = texture;
        c.srcX = 0;
        c.srcY = 0;
        c.srcW = width;
        c.srcH = height;
        c.x = -pivotX * width;
        c.y = -pivotY * height;
        c.w = width;
        c.h = height;
        c.color = Color.WHITE;
        c.alpha = alpha;
        c.smooth = smooth;
    }

    /** A ui canvas with a brush keeps the finger that goes down on it (the world under it does not get it). */
    @Override protected boolean takesPress(double x, double y) {
        if (!painting || !visible) return false;
        entity().worldMatrix(inverse);
        if (inverse.a * inverse.d - inverse.b * inverse.c == 0) return false;
        inverse.invert();
        double lx = inverse.mapX(x, y) + pivotX * width, ly = inverse.mapY(x, y) + pivotY * height;
        return lx >= 0 && ly >= 0 && lx < width && ly < height;
    }

    @Override protected int pressLayer() {
        return layer;
    }

    @Override protected int pressOrder() {
        return order;
    }

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
}
