package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.math.Color;
import apkpygame.core.math.Mat3;
import apkpygame.core.render.DrawCommand;
import apkpygame.core.render.FontData;
import apkpygame.core.render.RenderQueue;

import java.util.ArrayList;
import java.util.List;

/**
 * Text; the entity's position is the baseline of the first line at the
 * alignment point. A plain line in the system font goes straight to the
 * backend. Anything more (a font of the game, max_width, \n, colours in the
 * text, pages, letter by letter) is laid out here, with the font's measures
 * from the bundle: the same line breaks on every platform.
 */
public final class Text extends Component {
    public String text = "";
    public double size = 16;
    public int color = Color.WHITE;
    public double alpha = 1;
    /** -1 left, 0 centre, 1 right */
    public int align = -1;
    public int layer, order;
    public boolean visible = true;
    /** The font's path in the bundle; null: the game's font, or the system's. */
    public String font;
    /** Where the text starts, from the entity (a Button's label). */
    public double offsetX, offsetY;
    /** Lines are broken to fit this width (local units); 0: only at \n. */
    public double maxWidth;
    /** Times the font's distance between lines. */
    public double lineSpacing = 1;
    /** Lines per page; 0: one page. */
    public int maxLines;
    /** The page shown, from 0. */
    public int page;
    /** How many characters of the page are shown (letter by letter); -1: all. */
    public int visibleChars = -1;

    public Text(String text) {
        this.text = text;
    }

    private String shown;
    private String shownFrom;
    private int shownVersion = -1;

    /** The text with {variable} replaced (recomputed only when a variable or the text changed). */
    public String shown() {
        if (text == null || text.indexOf('{') < 0) return text;
        int version = game().varsVersion();
        if (version != shownVersion || !text.equals(shownFrom)) {
            shown = game().format(text);
            shownFrom = text;
            shownVersion = version;
        }
        return shown;
    }

    // ── layout ───────────────────────────────────────────────────────────

    /** A run of one colour on a line. */
    private static final class Run {
        String text;
        int color;              // 0: the Text's colour
        double x;               // from the line's start
    }

    private static final class Line {
        final List<Run> runs = new ArrayList<Run>();
        double width;
        int chars;
    }

    private final List<Line> lines = new ArrayList<Line>();
    private FontData fontData;
    private String laidText, laidFont;
    private double laidSize, laidWidth;

    private FontData fontData() {
        String path = font != null ? font : game().config.font;
        if (fontData == null || !equal(path, laidFont)) {
            fontData = path == null ? FontData.SYSTEM : game().assets.<FontData>get("font", path);
            laidFont = path;
            laidText = null;
        }
        return fontData;
    }

    private static boolean equal(String a, String b) {
        return a == null ? b == null : a.equals(b);
    }

    private void layout() {
        FontData f = fontData();
        String s = shown();
        if (s == null) s = "";
        if (s.equals(laidText) && size == laidSize && maxWidth == laidWidth) return;
        laidText = s;
        laidSize = size;
        laidWidth = maxWidth;
        lines.clear();

        Line line = new Line();
        lines.add(line);
        StringBuilder run = new StringBuilder();     // the run being written
        int runColor = 0;
        int at = 0;
        while (at < s.length()) {
            // colours: [c=#rrggbb] ... [/c]
            if (s.startsWith("[c=", at) && s.indexOf(']', at) > 0) {
                int end = s.indexOf(']', at);
                flush(line, run, runColor, f);
                runColor = Color.parse(s.substring(at + 3, end), color) | 0xFF000000;
                at = end + 1;
                continue;
            }
            if (s.startsWith("[/c]", at)) {
                flush(line, run, runColor, f);
                runColor = 0;
                at += 4;
                continue;
            }
            char c = s.charAt(at);
            if (c == '\n') {
                flush(line, run, runColor, f);
                line = new Line();
                lines.add(line);
                at++;
                continue;
            }
            if (maxWidth > 0 && c == ' ') {
                // does the next word fit? (colour marks inside it do not count)
                double word = 0;
                for (int i = at + 1; i < s.length(); ) {
                    char w = s.charAt(i);
                    if (w == ' ' || w == '\n') break;
                    if (s.startsWith("[c=", i) && s.indexOf(']', i) > 0) {
                        i = s.indexOf(']', i) + 1;
                        continue;
                    }
                    if (s.startsWith("[/c]", i)) {
                        i += 4;
                        continue;
                    }
                    word += f.advance(w) * size;
                    i++;
                }
                double now = width(line, run, f);
                if (now > 0 && now + (f.advance(' ') * size) + word > maxWidth) {
                    flush(line, run, runColor, f);
                    line = new Line();
                    lines.add(line);
                    at++;                            // the space at the break is dropped
                    continue;
                }
            } else if (maxWidth > 0 && width(line, run, f) + f.advance(c) * size > maxWidth
                    && width(line, run, f) > 0) {
                // a word wider than the line: cut it here
                flush(line, run, runColor, f);
                line = new Line();
                lines.add(line);
            }
            run.append(c);
            at++;
        }
        flush(line, run, runColor, f);
    }

    private double width(Line line, StringBuilder run, FontData f) {
        double w = line.width;
        for (int i = 0; i < run.length(); i++) w += f.advance(run.charAt(i)) * size;
        return w;
    }

    private void flush(Line line, StringBuilder run, int color, FontData f) {
        if (run.length() == 0) return;
        Run r = new Run();
        r.text = run.toString();
        r.color = color;
        r.x = line.width;
        line.runs.add(r);
        line.chars += run.length();
        line.width = width(line, run, f);
        run.setLength(0);
    }

    private int perPage() {
        return maxLines > 0 ? maxLines : Integer.MAX_VALUE;
    }

    /** How many lines the text takes. */
    public int lineCount() {
        layout();
        return lines.size();
    }

    public int pages() {
        layout();
        return maxLines > 0 ? (lines.size() + maxLines - 1) / maxLines : 1;
    }

    /** How many characters the current page has (for letter by letter: done when visible_chars reaches it). */
    public int pageChars() {
        layout();
        int n = 0;
        int first = firstLine();
        for (int i = first; i < lines.size() && i - first < perPage(); i++) n += lines.get(i).chars;
        return n;
    }

    private int firstLine() {
        if (maxLines <= 0) return 0;
        return Math.max(0, Math.min(page, pages() - 1)) * maxLines;
    }

    /** The width of a text in this Text's font and size, in local units (one line, no colour marks). */
    public double measure(String s) {
        FontData f = fontData();
        double w = 0;
        for (int i = 0; i < s.length(); i++) w += f.advance(s.charAt(i)) * size;
        return w;
    }

    public void setColor(String hex) {
        color = Color.parse(hex, color);
    }

    /** The widest line. */
    public double width() {
        layout();
        double w = 0;
        for (Line l : lines) w = Math.max(w, l.width);
        return w;
    }

    /** The distance between two lines' baselines. */
    public double lineHeight() {
        return fontData().line * size * lineSpacing;
    }

    // ── drawing ──────────────────────────────────────────────────────────

    private boolean plain() {
        return font == null && game().config.font == null && maxWidth <= 0 && maxLines <= 0 && visibleChars < 0
                && (shown() == null || (shown().indexOf('\n') < 0 && shown().indexOf("[c=") < 0));
    }

    @Override protected void render(RenderQueue queue, Mat3 world) {
        if (!visible || text == null || text.isEmpty() || alpha <= 0) return;
        if (plain()) {
            DrawCommand c = queue.add(DrawCommand.Kind.TEXT);
            c.layer = layer;
            c.order = order;
            c.matrix.set(world);
            c.text = shown();
            c.size = size;
            c.color = Color.withAlpha(color, alpha);
            c.align = align;
            c.x = offsetX;
            c.y = offsetY;
            return;
        }
        layout();
        FontData f = fontData();
        if (f.bitmap) {
            if (f.texture == null) f.texture = game().assets.texture(f.image);
        } else if (!f.faceLoaded) {
            f.face = game().platform.renderer().loadFont(laidFont, game().assets.bytes(laidFont));
            f.faceLoaded = true;
        }
        int left = visibleChars < 0 ? Integer.MAX_VALUE : visibleChars;
        int first = firstLine();
        double step = lineHeight();
        for (int i = first; i < lines.size() && i - first < perPage() && left > 0; i++) {
            Line line = lines.get(i);
            double y = (i - first) * step;
            boolean whole = line.runs.size() == 1 && visibleChars < 0;
            double start = whole && !f.bitmap ? 0 : align < 0 ? 0 : align == 0 ? -line.width / 2 : -line.width;
            for (Run r : line.runs) {
                if (left <= 0) break;
                String s = r.text.length() <= left ? r.text : r.text.substring(0, left);
                left -= s.length();
                int rgb = r.color != 0 ? r.color : color;
                if (f.bitmap) {
                    glyphs(queue, world, f, s, offsetX + start + r.x, offsetY + y, rgb);
                } else {
                    DrawCommand c = queue.add(DrawCommand.Kind.TEXT);
                    c.layer = layer;
                    c.order = order;
                    c.matrix.set(world);
                    c.text = s;
                    c.size = size;
                    c.color = Color.withAlpha(rgb, alpha);
                    c.align = whole ? align : -1;          // one run: the backend centres it exactly
                    c.face = f.face;
                    c.x = offsetX + start + r.x;
                    c.y = offsetY + y;
                }
            }
        }
    }

    /**
     * A bitmap font: one sprite per glyph, at a whole number of screen pixels per
     * texel, on whole screen pixels, so it never blurs. The pen moves by the
     * font's measures, so the line takes the same room at any screen size.
     */
    private void glyphs(RenderQueue queue, Mat3 world, FontData f, String s, double x, double y, int rgb) {
        double screen = Math.max(0.0001, Math.sqrt(world.a * world.a + world.b * world.b));
        double texel = Math.max(1, Math.round(size / f.nativeSize * screen)) / screen;     // local units per texel
        boolean straight = world.b == 0 && world.c == 0;
        double pen = x, top = y - f.base * texel;
        for (int i = 0; i < s.length(); i++) {
            char ch = s.charAt(i);
            FontData.Glyph g = f.glyph(ch);
            if (g != null && g.w > 0 && g.h > 0) {
                DrawCommand c = queue.add(DrawCommand.Kind.SPRITE);
                c.layer = layer;
                c.order = order;
                c.matrix.set(world);
                c.texture = f.texture;
                c.srcX = g.x;
                c.srcY = g.y;
                c.srcW = g.w;
                c.srcH = g.h;
                c.x = pen + g.offsetX * texel;
                c.y = top + g.offsetY * texel;
                if (straight) {
                    c.x = (Math.round(world.tx + world.a * c.x) - world.tx) / world.a;
                    c.y = (Math.round(world.ty + world.d * c.y) - world.ty) / world.d;
                }
                c.w = g.w * texel;
                c.h = g.h * texel;
                c.color = rgb | 0xFF000000;
                c.alpha = alpha;
                c.smooth = false;
            }
            pen += f.advance(ch) * size;
        }
    }
}
