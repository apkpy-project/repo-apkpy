"""ApkpyLayout.java, the view group for the layouts Android's own do not give."""


def _generate_apkpy_layout_java(package="com.apkpy.app"):
    """Runtime pequeno para flex/grid avançado, incluído apenas quando usado."""
    return r'''package __PACKAGE__;

import android.content.Context;
import android.graphics.Rect;
import android.util.AttributeSet;
import android.view.View;
import android.view.ViewGroup;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;

/** Gerado pela ApkPy. Implementa o subconjunto declarativo de Flexbox/Grid sem
 * bibliotecas externas e sem criar objetos durante onLayout(). */
public final class ApkpyLayout extends ViewGroup {
    private final IdentityHashMap<View, Rect> boxes = new IdentityHashMap<>();
    private final ArrayList<Item> flow = new ArrayList<>();
    private final ArrayList<Item> absolute = new ArrayList<>();
    // Absolute children at bottom: 0 -- a sheet or bar that sits on the bottom.
    private final java.util.HashSet<View> flushBottom = new java.util.HashSet<>();
    private final Map<String,String> config = new HashMap<>();
    private float density;
    // Set by a parent ApkpyLayout when this one is position:absolute with no
    // width: CSS sizes such a box to its content (shrink-to-fit).
    boolean shrinkToFit;

    private static final class Item {
        View view; Map<String,String> css; int reqW, reqH, main, cross;
        int row, col, rowSpan = 1, colSpan = 1;
        Item(View v, Map<String,String> values) { view = v; css = values; }
    }

    public ApkpyLayout(Context c) { super(c); init(); }
    public ApkpyLayout(Context c, AttributeSet a) { super(c, a); init(); }
    public ApkpyLayout(Context c, AttributeSet a, int s) { super(c, a, s); init(); }
    private void init() { density = getResources().getDisplayMetrics().density; setClipChildren(false); }

    // A tag is the same few strings for the life of the app, and onMeasure
    // read each one again for every child on every pass. Read once, shared:
    // nobody writes into the map that comes back.
    private static final HashMap<String, Map<String,String>> PARSED = new HashMap<>();
    private static final HashMap<String, Float> NUMBERS = new HashMap<>();
    private static final java.util.regex.Pattern NOT_NUMBER = java.util.regex.Pattern.compile("[^0-9.+-]");
    private static Map<String,String> parse(Object raw) {
        String text = raw == null ? "" : String.valueOf(raw);
        Map<String,String> known = PARSED.get(text);
        if (known != null) return known;
        HashMap<String,String> out = new HashMap<>();
        for (String piece : text.split(";")) {
            int at = piece.indexOf('=');
            if (at > 0) out.put(piece.substring(0, at), piece.substring(at + 1));
        }
        PARSED.put(text, out);
        return out;
    }
    private static float number(String raw, float fallback) {
        if (raw == null) return fallback;
        Float known = NUMBERS.get(raw);
        if (known == null) {
            try { known = Float.parseFloat(NOT_NUMBER.matcher(raw).replaceAll("")); }
            catch (Exception ignored) { known = Float.NaN; }
            NUMBERS.put(raw, known);
        }
        return known.isNaN() ? fallback : known;
    }

    // What each child was last measured with, in this onMeasure. A box was
    // measured for its content, then at its width in the row, then at its
    // final size -- three times, and a box inside it three times for each of
    // those: four levels deep, a label was measured 81 times before the first
    // frame. A spec that only pins a view to the size it already measured to
    // gives the same answer, so it is not asked again. A TextView keeps its
    // width re-measure: Android's line breaking is not greedy.
    private final HashMap<View, int[]> specs = new HashMap<>();
    private void measureView(View view, int widthSpec, int heightSpec) {
        int[] last = specs.get(view);
        if (last != null
                && same(last[0], widthSpec, view.getMeasuredWidth(), !(view instanceof android.widget.TextView))
                && same(last[1], heightSpec, view.getMeasuredHeight(), true)) {
            last[0] = widthSpec; last[1] = heightSpec;
            return;
        }
        view.measure(widthSpec, heightSpec);
        specs.put(view, new int[]{widthSpec, heightSpec});
    }
    private static boolean same(int before, int now, int measured, boolean pinnable) {
        if (before == now) return true;
        return pinnable && MeasureSpec.getMode(now) == MeasureSpec.EXACTLY
                && MeasureSpec.getSize(now) == measured;
    }
    private int dim(String raw, int base, int fallback) {
        if (raw == null || raw.length() == 0 || "auto".equals(raw)) return fallback;
        if (raw.endsWith("%")) return Math.round(base * number(raw, 0f) / 100f);
        if (raw.endsWith("vw")) return Math.round(getResources().getDisplayMetrics().widthPixels * number(raw, 0f) / 100f);
        if (raw.endsWith("vh")) return Math.round(getResources().getDisplayMetrics().heightPixels * number(raw, 0f) / 100f);
        return Math.round(number(raw, fallback / density) * density);
    }
    private static int integer(Map<String,String> values, String key, int fallback) {
        try { return Integer.parseInt(values.get(key)); } catch (Exception ignored) { return fallback; }
    }
    private static String value(Map<String,String> values, String key, String fallback) {
        String found = values.get(key); return found == null ? fallback : found;
    }
    private static int childState(List<Item> items) {
        int state = 0; for (Item item : items) state = combineMeasuredStates(state, item.view.getMeasuredState()); return state;
    }

    @Override protected void onMeasure(int widthSpec, int heightSpec) {
        config.clear(); config.putAll(parse(getTag())); boxes.clear(); flow.clear(); absolute.clear(); flushBottom.clear();
        specs.clear();
        int widthMode = MeasureSpec.getMode(widthSpec);
        int widthSize = MeasureSpec.getSize(widthSpec);
        int innerW = Math.max(1, widthSize - getPaddingLeft() - getPaddingRight());
        if (widthMode == MeasureSpec.UNSPECIFIED) innerW = Math.max(1, getSuggestedMinimumWidth());
        boolean flexRow = !"grid".equals(value(config, "mode", "flex"))
                && "row".equals(value(config, "direction", "column"));

        for (int i = 0; i < getChildCount(); i++) {
            View child = getChildAt(i);
            if (child.getVisibility() == GONE) continue;
            Item item = new Item(child, parse(child.getTag()));
            // A box with no width in a row starts as wide as its content, as in
            // CSS and the Previewer. It was measured as wide as the row, so
            // seven day columns were squeezed to equal slices and clipped
            // the circles inside them.
            if (flexRow && child instanceof ApkpyLayout
                    && child.getLayoutParams().width == LayoutParams.WRAP_CONTENT)
                ((ApkpyLayout) child).shrinkToFit = true;
            MarginLayoutParams lp = (MarginLayoutParams) child.getLayoutParams();
            measureView(child,
                    getChildMeasureSpec(widthSpec, getPaddingLeft() + getPaddingRight() + lp.leftMargin + lp.rightMargin, lp.width),
                    getChildMeasureSpec(heightSpec, getPaddingTop() + getPaddingBottom() + lp.topMargin + lp.bottomMargin, lp.height));
            // width: 48px on a label or a button is in its tag, not in its
            // layout_width (wrap_content). The tile was as wide as its text.
            int ownW = lp.width == LayoutParams.WRAP_CONTENT ? dim(item.css.get("width"), innerW, -1) : -1;
            if (ownW > 0) measureView(child, MeasureSpec.makeMeasureSpec(ownW, MeasureSpec.EXACTLY),
                    getChildMeasureSpec(heightSpec, getPaddingTop() + getPaddingBottom() + lp.topMargin + lp.bottomMargin, lp.height));
            item.reqW = child.getMeasuredWidth() + lp.leftMargin + lp.rightMargin;
            item.reqH = child.getMeasuredHeight() + lp.topMargin + lp.bottomMargin;
            if ("absolute".equals(value(item.css, "position", ""))) {
                // An absolute box with no width is as wide as its content, as in
                // CSS. Measured as match_parent it was the screen's width, so
                // `right: 12px` had nothing to move: a TikTok-style column of
                // buttons sat against the left edge.
                if (!item.css.containsKey("width")
                        && !(item.css.containsKey("left") && item.css.containsKey("right"))) {
                    if (child instanceof ApkpyLayout) ((ApkpyLayout) child).shrinkToFit = true;
                    measureView(child, MeasureSpec.makeMeasureSpec(innerW, MeasureSpec.AT_MOST),
                            MeasureSpec.makeMeasureSpec(0, MeasureSpec.UNSPECIFIED));
                    item.reqW = child.getMeasuredWidth() + lp.leftMargin + lp.rightMargin;
                    item.reqH = child.getMeasuredHeight() + lp.topMargin + lp.bottomMargin;
                }
                absolute.add(item);
            } else flow.add(item);
        }
        if (shrinkToFit && widthMode == MeasureSpec.AT_MOST
                && !"grid".equals(value(config, "mode", "flex"))) {
            boolean row = value(config, "direction", "row").startsWith("row");
            int natural = 0, count = 0;
            for (Item item : flow) {
                natural = row ? natural + item.reqW : Math.max(natural, item.reqW);
                count++;
            }
            if (row && count > 1) natural += gap() * (count - 1);
            int wanted = natural + getPaddingLeft() + getPaddingRight();
            if (wanted < widthSize) {
                widthSize = Math.max(1, wanted);
                innerW = Math.max(1, natural);
            }
        }

        int contentH = "grid".equals(value(config, "mode", "flex")) ? layoutGrid(innerW) : layoutFlex(innerW, heightSpec);
        int desiredH = Math.max(getSuggestedMinimumHeight(), contentH + getPaddingTop() + getPaddingBottom());
        int measuredW = resolveSizeAndState(widthSize, widthSpec, childState(flow));
        int measuredH = resolveSizeAndState(desiredH, heightSpec, childState(flow) << MEASURED_HEIGHT_STATE_SHIFT);
        setMeasuredDimension(measuredW, measuredH);
        layoutAbsolute(innerW, Math.max(contentH, measuredH - getPaddingTop() - getPaddingBottom()));
    }

    private int gap() { return Math.round(number(config.get("gap"), 0f) * density); }
    private static int justifyOffset(String justify, int free, int count) {
        if ("center".equals(justify)) return free / 2;
        if ("end".equals(justify) || "flex-end".equals(justify)) return free;
        if ("space-around".equals(justify) && count > 0) return free / count / 2;
        if ("space-evenly".equals(justify) && count > 0) return free / (count + 1);
        return 0;
    }
    private static int extraGap(String justify, int free, int count) {
        if ("space-between".equals(justify) && count > 1) return free / (count - 1);
        if ("space-around".equals(justify) && count > 0) return free / count;
        if ("space-evenly".equals(justify) && count > 0) return free / (count + 1);
        return 0;
    }

    private int measureRowCross(Item item) {
        MarginLayoutParams lp = (MarginLayoutParams) item.view.getLayoutParams();
        int childWidth = Math.max(1, item.main - lp.leftMargin - lp.rightMargin);
        int childWidthSpec = MeasureSpec.makeMeasureSpec(childWidth, MeasureSpec.EXACTLY);
        int childHeightSpec;
        if (lp.height >= 0) {
            childHeightSpec = MeasureSpec.makeMeasureSpec(lp.height, MeasureSpec.EXACTLY);
        } else if (lp.height == LayoutParams.MATCH_PARENT) {
            childHeightSpec = MeasureSpec.makeMeasureSpec(
                Math.max(1, item.cross - lp.topMargin - lp.bottomMargin),
                MeasureSpec.EXACTLY
            );
        } else {
            childHeightSpec = MeasureSpec.makeMeasureSpec(0, MeasureSpec.UNSPECIFIED);
        }
        measureView(item.view, childWidthSpec, childHeightSpec);
        return item.view.getMeasuredHeight() + lp.topMargin + lp.bottomMargin;
    }

    private int layoutFlex(int innerW, int heightSpec) {
        boolean row = "row".equals(value(config, "direction", "column"));
        boolean wrap = "1".equals(config.get("wrap"));
        int mainLimit = row ? innerW : Math.max(1, MeasureSpec.getSize(heightSpec) - getPaddingTop() - getPaddingBottom());
        if (!row && MeasureSpec.getMode(heightSpec) == MeasureSpec.UNSPECIFIED) mainLimit = Integer.MAX_VALUE / 8;
        int g = gap();
        ArrayList<ArrayList<Item>> lines = new ArrayList<>();
        ArrayList<Item> line = new ArrayList<>(); int used = 0;
        for (Item item : flow) {
            int requested = row ? item.reqW : item.reqH;
            item.main = Math.max(1, dim(item.css.get("basis"), mainLimit, requested));
            item.cross = Math.max(1, row ? item.reqH : item.reqW);
            float ratio = number(item.css.get("ratio"), 0f);
            if (ratio > 0f) item.cross = row ? Math.round(item.main / ratio) : Math.round(item.main * ratio);
            int addition = item.main + (line.isEmpty() ? 0 : g);
            if (wrap && !line.isEmpty() && used + addition > mainLimit) {
                lines.add(line); line = new ArrayList<>(); used = 0;
            }
            line.add(item); used += item.main + (line.size() > 1 ? g : 0);
        }
        if (!line.isEmpty()) lines.add(line);

        int crossCursor = 0;
        for (ArrayList<Item> current : lines) {
            int total = g * Math.max(0, current.size() - 1); float grow = 0f, shrink = 0f;
            for (Item item : current) { total += item.main; grow += number(item.css.get("grow"), 0f); shrink += number(item.css.get("shrink"), 1f) * item.main; }
            int remaining = mainLimit == Integer.MAX_VALUE / 8 ? 0 : mainLimit - total;
            if (remaining > 0 && grow > 0f) for (Item item : current) item.main += Math.round(remaining * number(item.css.get("grow"), 0f) / grow);
            if (remaining < 0 && shrink > 0f) for (Item item : current) item.main = Math.max(1, item.main + Math.round(remaining * number(item.css.get("shrink"), 1f) * item.main / shrink));
            // The final width can make button/label text wrap. Measure again
            // with that exact width before choosing the row height; otherwise
            // Android keeps the old one-line height and clips the next line.
            if (row) for (Item item : current) if (!item.css.containsKey("ratio")) item.cross = Math.max(item.cross, measureRowCross(item));
            int lineCross = 0; total = g * Math.max(0, current.size() - 1);
            for (Item item : current) { total += item.main; lineCross = Math.max(lineCross, item.cross); }
            // A column that does not wrap has one line, as wide as the box --
            // layout_engine.py's rule. The widest child stood in for it, so
            // align-items: center centred an avatar under its caption and
            // left the pair against the left edge of a full-width column.
            if (!row && !wrap) lineCross = Math.max(1, innerW);
            int free = Math.max(0, mainLimit == Integer.MAX_VALUE / 8 ? 0 : mainLimit - total);
            String justify = value(config, "justify", "start");
            int cursor = justifyOffset(justify, free, current.size()); int between = g + extraGap(justify, free, current.size());
            for (Item item : current) {
                String align = value(item.css, "alignSelf", value(config, "align", "stretch"));
                int crossSize = item.cross;
                // A width (a height, in a row) of its own is not stretched,
                // as in layout_engine.py and CSS.
                if ("stretch".equals(align) && !item.css.containsKey("ratio")
                        && !item.css.containsKey(row ? "height" : "width")) crossSize = lineCross;
                int crossOffset = "center".equals(align) ? (lineCross - crossSize) / 2 : (("end".equals(align) || "flex-end".equals(align)) ? lineCross - crossSize : 0);
                int x = row ? cursor : crossCursor + crossOffset;
                int y = row ? crossCursor + crossOffset : cursor;
                int w = row ? item.main : crossSize; int h = row ? crossSize : item.main;
                placeMeasured(item, x, y, w, h); cursor += item.main + between;
            }
            crossCursor += lineCross + g;
        }
        if (lines.isEmpty()) return 0;
        if (row) return Math.max(0, crossCursor - g);
        int maxBottom = 0; for (Item item : flow) { Rect r = boxes.get(item.view); if (r != null) maxBottom = Math.max(maxBottom, r.bottom); } return maxBottom;
    }

    private int[] tracks(int innerW) {
        String[] raw = value(config, "tracks", "1fr").split(","); int g = gap();
        int usable = Math.max(1, innerW - g * Math.max(0, raw.length - 1)); int fixed = 0; float fr = 0f;
        int[] out = new int[raw.length];
        for (int i = 0; i < raw.length; i++) { if (raw[i].endsWith("fr")) fr += Math.max(0f, number(raw[i], 1f)); else { out[i] = dim(raw[i], usable, 0); fixed += out[i]; } }
        int free = Math.max(0, usable - fixed);
        if (fr > 0f) for (int i = 0; i < raw.length; i++) if (raw[i].endsWith("fr")) out[i] = Math.round(free * Math.max(0f, number(raw[i], 1f)) / fr);
        return out;
    }
    private int layoutGrid(int innerW) {
        int[] cols = tracks(innerW); int count = cols.length, g = gap(), cursor = 0, maxRow = 0;
        ArrayList<boolean[]> occupied = new ArrayList<>();
        for (Item item : flow) {
            item.colSpan = Math.min(count, Math.max(1, integer(item.css, "colSpan", 1)));
            item.rowSpan = Math.max(1, integer(item.css, "rowSpan", 1));
            int explicitCol = integer(item.css, "col", -1), explicitRow = integer(item.css, "row", -1);
            if (explicitCol >= 0 || explicitRow >= 0) { item.col = Math.max(0, Math.min(count - item.colSpan, explicitCol < 0 ? 0 : explicitCol)); item.row = Math.max(0, explicitRow); }
            else {
                while (true) {
                    item.row = cursor / count; item.col = cursor % count;
                    if (item.col + item.colSpan <= count && free(occupied, item.row, item.col, item.rowSpan, item.colSpan, count)) break;
                    cursor++;
                }
                cursor = item.row * count + item.col + item.colSpan;
            }
            occupy(occupied, item.row, item.col, item.rowSpan, item.colSpan, count); maxRow = Math.max(maxRow, item.row + item.rowSpan);
        }
        int[] rowH = new int[maxRow];
        for (Item item : flow) {
            int cellW = span(cols, item.col, item.colSpan, g);
            // Measured again at the cell's width: measured at the grid's, a
            // card's title stayed on one line, and at half the width its
            // second line pushed the subtitle out of the cell.
            MarginLayoutParams cellLp = (MarginLayoutParams) item.view.getLayoutParams();
            measureView(item.view, MeasureSpec.makeMeasureSpec(Math.max(1, cellW - cellLp.leftMargin - cellLp.rightMargin), MeasureSpec.EXACTLY),
                    cellLp.height >= 0 ? MeasureSpec.makeMeasureSpec(cellLp.height, MeasureSpec.EXACTLY)
                            : MeasureSpec.makeMeasureSpec(0, MeasureSpec.UNSPECIFIED));
            int h = item.view.getMeasuredHeight() + cellLp.topMargin + cellLp.bottomMargin;
            float ratio = number(item.css.get("ratio"), 0f); if (ratio > 0f) h = Math.round(cellW / ratio);
            int share = Math.max(1, (h - g * (item.rowSpan - 1) + item.rowSpan - 1) / item.rowSpan);
            for (int r = item.row; r < item.row + item.rowSpan; r++) rowH[r] = Math.max(rowH[r], share);
        }
        int[] x = starts(cols, g), y = starts(rowH, g);
        for (Item item : flow) {
            int w = span(cols, item.col, item.colSpan, g), h = span(rowH, item.row, item.rowSpan, g);
            float ratio = number(item.css.get("ratio"), 0f); if (ratio > 0f) h = Math.round(w / ratio);
            placeMeasured(item, x[item.col], y[item.row], w, h);
        }
        return span(rowH, 0, rowH.length, g);
    }
    private static boolean free(ArrayList<boolean[]> used, int row, int col, int rs, int cs, int count) {
        for (int r = row; r < row + rs; r++) if (r < used.size()) for (int c = col; c < col + cs; c++) if (used.get(r)[c]) return false; return true;
    }
    private static void occupy(ArrayList<boolean[]> used, int row, int col, int rs, int cs, int count) {
        while (used.size() < row + rs) used.add(new boolean[count]); for (int r = row; r < row + rs; r++) for (int c = col; c < col + cs; c++) used.get(r)[c] = true;
    }
    private static int[] starts(int[] sizes, int gap) { int[] out = new int[sizes.length]; for (int i = 1; i < sizes.length; i++) out[i] = out[i-1] + sizes[i-1] + gap; return out; }
    private static int span(int[] sizes, int start, int amount, int gap) { int total = gap * Math.max(0, amount - 1); for (int i = start; i < Math.min(sizes.length, start + amount); i++) total += sizes[i]; return total; }

    private void layoutAbsolute(int innerW, int innerH) {
        for (Item item : absolute) {
            int left = item.css.containsKey("left") ? dim(item.css.get("left"), innerW, 0) : Integer.MIN_VALUE;
            int right = item.css.containsKey("right") ? dim(item.css.get("right"), innerW, 0) : Integer.MIN_VALUE;
            int top = item.css.containsKey("top") ? dim(item.css.get("top"), innerH, 0) : Integer.MIN_VALUE;
            int bottom = item.css.containsKey("bottom") ? dim(item.css.get("bottom"), innerH, 0) : Integer.MIN_VALUE;
            int w = dim(item.css.get("width"), innerW, item.reqW), h = dim(item.css.get("height"), innerH, item.reqH);
            if (left != Integer.MIN_VALUE && right != Integer.MIN_VALUE) w = Math.max(1, innerW - left - right);
            float ratio = number(item.css.get("ratio"), 0f); if (ratio > 0f) h = Math.round(w / ratio);
            int x = left != Integer.MIN_VALUE ? left : Math.max(0, innerW - (right == Integer.MIN_VALUE ? 0 : right) - w);
            int y = top != Integer.MIN_VALUE ? top : Math.max(0, innerH - (bottom == Integer.MIN_VALUE ? 0 : bottom) - h);
            if (bottom == 0 && top == Integer.MIN_VALUE) flushBottom.add(item.view);
            placeMeasured(item, x, y, w, h);
        }
    }
    // How far below this layout the window goes, when that is only the
    // navigation bar the screen root leaves free (fitsSystemWindows).
    private int navigationBarBelow() {
        androidx.core.view.WindowInsetsCompat insets = androidx.core.view.ViewCompat.getRootWindowInsets(this);
        if (insets == null) return 0;
        int nav = insets.getInsets(androidx.core.view.WindowInsetsCompat.Type.navigationBars()).bottom;
        if (nav <= 0) return 0;
        int[] at = new int[2];
        getLocationInWindow(at);
        int gap = getRootView().getHeight() - (at[1] + getHeight() - getPaddingBottom());
        return (gap > 0 && gap <= nav + 1) ? gap : 0;
    }
    private void placeMeasured(Item item, int x, int y, int width, int height) {
        MarginLayoutParams lp = (MarginLayoutParams) item.view.getLayoutParams();
        int w = Math.max(1, width - lp.leftMargin - lp.rightMargin), h = Math.max(1, height - lp.topMargin - lp.bottomMargin);
        measureView(item.view, MeasureSpec.makeMeasureSpec(w, MeasureSpec.EXACTLY), MeasureSpec.makeMeasureSpec(h, MeasureSpec.EXACTLY));
        boxes.put(item.view, new Rect(x + lp.leftMargin, y + lp.topMargin, x + lp.leftMargin + w, y + lp.topMargin + h));
        item.view.setZ(number(item.css.get("z"), 0f) * density);
    }

    @Override protected void onLayout(boolean changed, int l, int t, int r, int b) {
        // A sheet at bottom: 0 used to stop at the navigation bar, with a strip
        // of the screen colour under it; its background now runs to the bottom
        // of the glass, under the gesture bar, and its content stays put.
        int below = flushBottom.isEmpty() ? 0 : navigationBarBelow();
        for (int i = 0; i < getChildCount(); i++) {
            View child = getChildAt(i); Rect box = boxes.get(child);
            if (child.getVisibility() == GONE || box == null) continue;
            int bottom = box.bottom;
            if (below > 0 && flushBottom.contains(child)) {
                bottom += below;
                child.measure(MeasureSpec.makeMeasureSpec(box.width(), MeasureSpec.EXACTLY),
                        MeasureSpec.makeMeasureSpec(bottom - box.top, MeasureSpec.EXACTLY));
            }
            child.layout(getPaddingLeft() + box.left, getPaddingTop() + box.top, getPaddingLeft() + box.right, getPaddingTop() + bottom);
        }
    }
    @Override protected LayoutParams generateDefaultLayoutParams() { return new MarginLayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT); }
    @Override public LayoutParams generateLayoutParams(AttributeSet attrs) { return new MarginLayoutParams(getContext(), attrs); }
    @Override protected LayoutParams generateLayoutParams(LayoutParams source) { return new MarginLayoutParams(source); }
    @Override protected boolean checkLayoutParams(LayoutParams params) { return params instanceof MarginLayoutParams; }
}'''.replace("__PACKAGE__", package)
