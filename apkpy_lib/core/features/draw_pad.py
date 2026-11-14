"""draw_pad() on the phone: one ApkpyDrawPad view.

The box, the ink and the hint are drawn by the view itself, from the colours
and sizes draw_pad_rules gives the Previewer too. A stroke is kept as its
points and drawn as a path through them (a curve through each point to the
middle of the next segment), as the Previewer draws it. The strokes outlive a
turn of the phone. ``pad.save(name)`` writes a PNG into the app's folder under
the same name rules as files.write(), from ApkpyKitRules.
"""
import ast

from ... import draw_pad_rules as rules

COMPONENT = rules.COMPONENT
JAVA_FILE = "java/ApkpyDrawPad.java"
METHODS = ("clear", "save", "is_empty")

# The names the app gives its draw_pad()s (pad = draw_pad(...)), found before
# anything is read: a function above the pad may already call pad.save().
_PADS = [frozenset()]


def prescan(tree):
    names = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == COMPONENT):
            names.add(node.targets[0].id)
    _PADS[0] = frozenset(names)
    return _PADS[0]


def _pad_method(node, methods):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in methods and isinstance(node.func.value, ast.Name)
            and node.func.value.id in _PADS[0])


def is_value_call(node):
    """pad.is_empty() / pad.save(name), used as a value or a condition."""
    return _pad_method(node, ("is_empty", "save"))


def parse_call(transpiler, call):
    """pad.clear() / pad.save(name) on a line of their own; None for anything else."""
    if not _pad_method(call, METHODS):
        return None
    method = call.func.attr
    if method == "save" and not (call.args or transpiler._kw_node(call.keywords, "name")):
        rules.refuse("save() of a draw_pad takes the name of the PNG.", "%s.save()" % call.func.value.id,
                     getattr(call, "lineno", 0), ['%s.save("signature.png")' % call.func.value.id])
    return {"type": "draw_pad_call", "py_var": call.func.value.id, "method": method,
            "arg_node": (call.args[0] if call.args else transpiler._kw_node(call.keywords, "name"))
            if method == "save" else None}


def command_java(cmd, jv, val_to_java):
    """The line of a draw_pad_call command; None on a screen the pad is not on."""
    if not jv:
        return None
    arg = val_to_java(cmd["arg_node"]) if cmd.get("arg_node") is not None else None
    return call_java(jv, cmd["method"], arg) + ";"


def condition_java(value):
    """A pad's value (value_java) as a Java boolean: isEmpty() itself when the pad is here."""
    if value.startswith("(") and value.endswith(' ? "True" : "False")'):
        return value[1:-len(' ? "True" : "False")')]
    return '"True".equals(%s)' % value


def value_java(node, jv, val_to_java):
    """pad.is_empty() as "True"/"False", pad.save(name) as its answer. On a screen the pad is
    not on, it is empty and cannot be saved."""
    method = node.func.attr
    if method == "is_empty":
        if not jv:
            return '"True"'
        return '(%s ? "True" : "False")' % call_java(jv, "is_empty")
    if not jv:
        return '"failed"'
    arg = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "name"), None)
    return call_java(jv, "save", val_to_java(arg) if arg is not None else '""')


def parse(transpiler, call, comp, py_var):
    line = getattr(call, "lineno", 0)
    comp["id"] = transpiler._kw(call.keywords, "id")
    pen_node = transpiler._kw_node(call.keywords, "pen")
    if pen_node is not None and not (isinstance(pen_node, ast.Constant)
                                     and isinstance(pen_node.value, (int, float))):
        rules.refuse("pen= of draw_pad() is written as a number.", ast.dump(pen_node)[:80], line,
                     ["draw_pad(pen=3)"])
    comp["pen"] = rules.pen_from(pen_node.value if pen_node is not None else None, line)
    comp["hint_node"] = transpiler._kw_node(call.keywords, "hint")
    change = transpiler._kw_node(call.keywords, "on_change")
    if isinstance(change, ast.Name) and getattr(transpiler, "function_arity", {}).get(change.id, 0) > 0:
        rules.refuse("on_change= of draw_pad() is called with nothing: its function takes no "
                     "arguments.", "def %s(...)" % change.id, line,
                     ["def signed():  ...  then  draw_pad(on_change=signed)",
                      "draw_pad(on_change=lambda: ok.set_value(\"Signed\"))"])
    if isinstance(change, ast.Lambda) and change.args.args:
        rules.refuse("on_change= of draw_pad() is called with nothing: the lambda takes no "
                     "arguments.", "lambda %s: ..." % change.args.args[0].arg, line)
    comp["on_change"] = (transpiler._parse_callback_kw(call, "on_change", str(py_var or comp["id"] or "pad"))
                         if change is not None else None)


def uses(components):
    return any(c.get("comp_type") == COMPONENT or uses(c.get("children", []))
               for c in components or [])


def layout_xml(indent, number, package, height_dp, margin_xml):
    return [
        "%s<%s.ApkpyDrawPad" % (indent, package),
        '%s    android:id="@+id/dpad%d"' % (indent, number),
        '%s    android:layout_width="match_parent"' % indent,
        '%s    android:layout_height="%ddp"%s />' % (indent, int(round(height_dp)), margin_xml),
        "",
    ]


def java_setup(indent, comp, jv, colors, corner, color_java, val_to_java):
    def paint(colour):
        return color_java(colour) if colour else "android.graphics.Color.TRANSPARENT"

    hint = val_to_java(comp["hint_node"]) if comp.get("hint_node") is not None else '""'
    lines = [
        "%sApkpyDrawPad %s = findViewById(R.id.%s);" % (indent, jv, jv),
        "%s%s.configure(%s, %s, %s, %s, %sf, %sf, %sf, %sf, String.valueOf(%s));" % (
            indent, jv, color_java(colors["ink"]), paint(colors["paper"]), paint(colors["border"]),
            color_java(colors["hint"]), float(corner), float(rules.BORDER) if colors["border"] else 0.0,
            float(comp.get("pen", rules.PEN)), float(rules.HINT_SIZE), hint),
    ]
    if comp.get("on_change"):
        lines.append("%s%s.setOnChange(() -> pythonCallback_%s());" % (indent, jv, comp["on_change"]))
    return lines


def view_java(jv):
    return "((ApkpyDrawPad) findViewById(R.id.%s))" % jv


def call_java(jv, method, arg_java=None):
    """pad.clear() / pad.save(name) / pad.is_empty(), as Java (an expression)."""
    view = view_java(jv)
    if method == "clear":
        return "%s.clear()" % view
    if method == "save":
        return "%s.save(String.valueOf(%s))" % (view, arg_java if arg_java is not None else '""')
    return "%s.isEmpty()" % view


_JAVA = r'''package __PACKAGE__;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.os.Bundle;
import android.os.Parcelable;
import android.util.AttributeSet;
import android.view.MotionEvent;
import android.view.View;

import java.io.File;
import java.io.FileOutputStream;
import java.util.ArrayList;

/**
 * draw_pad(): a box to sign or scribble in with a finger (ApkPy). Each stroke is kept as its
 * points and drawn as a path through them: straight to the middle of the first segment, a curve
 * through each point to the middle of the next, straight to the end -- the line the Previewer
 * draws (draw_pad_rules.smooth). The strokes outlive a turn of the phone.
 */
public final class ApkpyDrawPad extends View {
    public interface OnChange { void changed(); }

    private final ArrayList<float[]> strokes = new ArrayList<>();
    private float[] live = new float[0];
    private int liveCount;
    private final Paint ink = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint dot = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint paper = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint border = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint hintPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path path = new Path();
    private final RectF box = new RectF();
    private int paperColor = 0;
    private float corner, borderWidth, pen;
    private String hint = "";
    private OnChange onChange;

    public ApkpyDrawPad(Context context) { this(context, null); }

    public ApkpyDrawPad(Context context, AttributeSet attrs) {
        super(context, attrs);
        ink.setStyle(Paint.Style.STROKE);
        ink.setStrokeCap(Paint.Cap.ROUND);
        ink.setStrokeJoin(Paint.Join.ROUND);
        border.setStyle(Paint.Style.STROKE);
        hintPaint.setTextAlign(Paint.Align.CENTER);
        setSaveEnabled(true);
        setFocusable(true);
    }

    private float dp(float value) {
        return value * getResources().getDisplayMetrics().density;
    }

    public void configure(int inkColor, int paperColor, int borderColor, int hintColor, float cornerDp,
                          float borderDp, float penDp, float hintSp, String hint) {
        ink.setColor(inkColor);
        dot.setColor(inkColor);
        this.paperColor = paperColor;
        paper.setColor(paperColor);
        border.setColor(borderColor);
        hintPaint.setColor(hintColor);
        hintPaint.setTextSize(android.util.TypedValue.applyDimension(
                android.util.TypedValue.COMPLEX_UNIT_SP, hintSp, getResources().getDisplayMetrics()));
        corner = dp(cornerDp);
        borderWidth = borderColor == 0 ? 0 : dp(borderDp);
        border.setStrokeWidth(borderWidth);
        pen = dp(penDp);
        ink.setStrokeWidth(pen);
        this.hint = hint == null ? "" : hint;
        setContentDescription(this.hint.isEmpty() ? "Drawing area" : this.hint);
        invalidate();
    }

    public void setOnChange(OnChange onChange) { this.onChange = onChange; }

    public boolean isEmpty() { return strokes.isEmpty(); }

    public void clear() {
        strokes.clear();
        liveCount = 0;
        invalidate();
    }

    /** What is drawn, as the PNG `name` in the app's folder: "ok", "invalid" or "failed". */
    public String save(String name) {
        File folder = getContext().getFilesDir();
        String given = ApkpyKitRules.trim(name);
        String root = folder.getAbsolutePath() + File.separator;
        if (given.startsWith(root)) given = given.substring(root.length());
        String clean = ApkpyKitRules.fileName(given);
        if (clean.isEmpty()) return "invalid";
        File file = new File(folder, clean);
        int width = getWidth(), height = getHeight();
        if (width <= 0 || height <= 0) return "failed";
        File parent = file.getParentFile();
        if (parent != null && !parent.isDirectory() && !parent.mkdirs()) return "failed";
        File spare = new File(parent, ".apkpy-" + file.getName() + ".tmp");
        boolean ok = false;
        FileOutputStream out = null;
        try {
            Bitmap bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
            Canvas canvas = new Canvas(bitmap);
            canvas.drawColor(paperColor);
            for (float[] stroke : strokes) drawStroke(canvas, stroke, stroke.length / 2);
            out = new FileOutputStream(spare);
            ok = bitmap.compress(Bitmap.CompressFormat.PNG, 100, out);
            out.flush();
            out.getFD().sync();
            bitmap.recycle();
        } catch (Throwable failed) {
            ok = false;
        } finally {
            try { if (out != null) out.close(); } catch (Throwable ignored) { ok = false; }
        }
        if (ok) ok = spare.renameTo(file);
        if (!ok) spare.delete();
        return ok ? "ok" : "failed";
    }

    @Override protected void onDraw(Canvas canvas) {
        float half = borderWidth / 2f;
        box.set(half, half, getWidth() - half, getHeight() - half);
        if (paperColor != 0) canvas.drawRoundRect(box, corner, corner, paper);
        if (borderWidth > 0) canvas.drawRoundRect(box, corner, corner, border);
        if (strokes.isEmpty() && liveCount == 0 && !hint.isEmpty()) {
            Paint.FontMetrics m = hintPaint.getFontMetrics();
            canvas.drawText(hint, getWidth() / 2f, getHeight() / 2f - (m.ascent + m.descent) / 2f, hintPaint);
        }
        for (float[] stroke : strokes) drawStroke(canvas, stroke, stroke.length / 2);
        if (liveCount > 0) drawStroke(canvas, live, liveCount);
    }

    private void drawStroke(Canvas canvas, float[] p, int n) {
        if (n == 1) {
            canvas.drawCircle(p[0], p[1], pen / 2f, dot);
            return;
        }
        path.reset();
        path.moveTo(p[0], p[1]);
        if (n == 2) {
            path.lineTo(p[2], p[3]);
        } else {
            path.lineTo((p[0] + p[2]) / 2f, (p[1] + p[3]) / 2f);
            for (int i = 1; i < n - 1; i++) {
                float mx = (p[2 * i] + p[2 * i + 2]) / 2f, my = (p[2 * i + 1] + p[2 * i + 3]) / 2f;
                path.quadTo(p[2 * i], p[2 * i + 1], mx, my);
            }
            path.lineTo(p[2 * n - 2], p[2 * n - 1]);
        }
        canvas.drawPath(path, ink);
    }

    private void add(float x, float y) {
        if (liveCount > 0 && live[2 * liveCount - 2] == x && live[2 * liveCount - 1] == y) return;
        if (2 * liveCount + 2 > live.length) live = java.util.Arrays.copyOf(live, Math.max(64, live.length * 2));
        live[2 * liveCount] = x;
        live[2 * liveCount + 1] = y;
        liveCount++;
    }

    @Override public boolean onTouchEvent(MotionEvent event) {
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                // A stroke down the box is drawing, not scrolling the screen.
                if (getParent() != null) getParent().requestDisallowInterceptTouchEvent(true);
                liveCount = 0;
                add(event.getX(), event.getY());
                invalidate();
                return true;
            case MotionEvent.ACTION_MOVE:
                for (int h = 0; h < event.getHistorySize(); h++) add(event.getHistoricalX(h), event.getHistoricalY(h));
                add(event.getX(), event.getY());
                invalidate();
                return true;
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_CANCEL:
                if (liveCount == 0) return true;
                add(event.getX(), event.getY());
                strokes.add(java.util.Arrays.copyOf(live, 2 * liveCount));
                liveCount = 0;
                invalidate();
                if (event.getActionMasked() == MotionEvent.ACTION_UP) performClick();
                if (onChange != null) onChange.changed();
                return true;
            default:
                return true;
        }
    }

    @Override public boolean performClick() { return super.performClick(); }

    @Override protected Parcelable onSaveInstanceState() {
        Bundle out = new Bundle();
        out.putParcelable("view", super.onSaveInstanceState());
        out.putInt("strokes", strokes.size());
        for (int i = 0; i < strokes.size(); i++) out.putFloatArray("s" + i, strokes.get(i));
        return out;
    }

    @SuppressWarnings("deprecation")     // getParcelable(key, Class) is API 33
    @Override protected void onRestoreInstanceState(Parcelable state) {
        if (!(state instanceof Bundle)) {
            super.onRestoreInstanceState(state);
            return;
        }
        Bundle in = (Bundle) state;
        super.onRestoreInstanceState(in.getParcelable("view"));
        strokes.clear();
        int count = in.getInt("strokes", 0);
        for (int i = 0; i < count; i++) {
            float[] stroke = in.getFloatArray("s" + i);
            if (stroke != null && stroke.length >= 2) strokes.add(stroke);
        }
        invalidate();
    }
}
'''


def java_source(package):
    return _JAVA.replace("__PACKAGE__", package)
