"""A CSS gradient as an Android background (codegen side).

``background: linear-gradient(...)`` becomes a drawable resource like any
other background, so the layout, the padding and the shadow work as they do
for a solid colour. Android's own ``<gradient>`` takes three colours and, below
Android 10, only angles in steps of 45; CSS takes any angle and any number of
stops. So the drawable is ``<drawable class="...ApkpyGradient">`` -- a class in
the app, which XML can name from API 24, ApkPy's minimum -- that draws the
gradient with a shader from the same geometry the Previewer uses
(core/gradients.py): the same colour at the same point.

What the resource carries is one attribute, ``app:apkpySpec``, read by the
class when the layout is inflated.
"""

from ..gradients import argb

ATTRS_FILE = "res/values/apkpy_gradient_attrs.xml"
JAVA_FILE = "java/ApkpyGradient.java"

_KIND = {"linear": "0", "radial": "1"}
_CORNER = {"top right": "0", "bottom right": "1", "bottom left": "2", "top left": "3"}
_SHAPE = {"circle": "0", "ellipse": "1"}
_EXTENT = {"closest-side": "0", "closest-corner": "1", "farthest-side": "2",
           "farthest-corner": "3"}


def resolved_stops(gradient, resolve=None):
    """``[((a, r, g, b), position)]`` ready to draw.

    A fully transparent stop takes the colour of its neighbours, split in two
    at the same position when they differ: CSS mixes colours with their alpha
    applied, so ``transparent`` to white fades white, never through grey --
    and a shader, mixing the channels as they are, would go through black.
    """
    stops = []
    for colour, position in gradient.stops:
        value = argb(resolve(colour) if resolve else colour)
        if value is not None:
            stops.append((value, position))
    if len(stops) < 2:
        return stops
    out = []
    for index, (value, position) in enumerate(stops):
        if value[0] != 0:
            out.append((value, position))
            continue
        before = next((stops[i][0] for i in range(index - 1, -1, -1) if stops[i][0][0]), None)
        after = next((stops[i][0] for i in range(index + 1, len(stops)) if stops[i][0][0]), None)
        sides = [s for s in (before, after) if s is not None] or [value]
        if len(sides) == 2 and sides[0][1:] != sides[1][1:]:
            out.append(((0,) + sides[0][1:], position))
            out.append(((0,) + sides[1][1:], position))
        else:
            out.append(((0,) + sides[0][1:], position))
    return out


def _hex8(value):
    return "%02X%02X%02X%02X" % value


def _number(value):
    text = ("%.4f" % float(value)).rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def spec(gradient, resolve=None, base=None, radii=0, border=None, padding=None):
    """The compact description ApkpyGradient reads, or None when no two of
    the gradient's colours can be read."""
    stops = resolved_stops(gradient, resolve)
    if len(stops) < 2:
        return None
    first, last = stops[0][1], stops[-1][1]
    span = None
    if gradient.repeating and last > first:
        span = (first, last)
        stops = [(c, (p - first) / (last - first)) for c, p in stops]
    parts = [
        "kind=" + _KIND[gradient.kind],
        "colors=" + ",".join(_hex8(c) for c, _ in stops),
        "stops=" + ",".join(_number(p) for _, p in stops),
    ]
    if gradient.kind == "linear":
        if gradient.corner is not None:
            parts.append("corner=" + _CORNER[gradient.corner])
        else:
            parts.append("angle=" + _number(gradient.angle % 360.0))
    else:
        parts.append("shape=" + _SHAPE[gradient.shape])
        parts.append("extent=" + _EXTENT[gradient.extent])
        parts.append("center=%s,%s" % (_number(gradient.center[0]), _number(gradient.center[1])))
    if span is not None:
        parts.append("span=%s,%s" % (_number(span[0]), _number(span[1])))
    corners = radii if isinstance(radii, tuple) else (radii,) * 4
    if any(corners):
        parts.append("radii=" + ",".join(_number(c) for c in corners))
    if base:
        value = argb(resolve(base) if resolve else base)
        if value is not None and value[0]:
            parts.append("base=" + _hex8(value))
    if border and border[0] > 0:
        value = argb(resolve(border[1]) if resolve else border[1])
        if value is not None:
            parts.append("stroke=%s,%s" % (_number(border[0]), _hex8(value)))
    if padding is not None:
        parts.append("padding=" + ",".join(_number(p) for p in padding))
    return ";".join(parts)


def default_ripple(gradient, resolve=None):
    """The press a button with a gradient shows when it names no pressed-color:
    Material's, light on a dark gradient and dark on a light one."""
    middle = argb(gradient.color_at(0.5, (lambda c: str(resolve(c))) if resolve else None))
    if middle is None:
        return "#1F000000"
    luminance = (0.299 * middle[1] + 0.587 * middle[2] + 0.114 * middle[3]) / 255.0
    return "#33FFFFFF" if luminance < 0.6 else "#1F000000"


def layer_list_xml(names):
    """Several gradients on one box, as CSS stacks ``background: a, b, c``:
    a layer-list of one ApkpyGradient resource each, the bottom one first."""
    items = "".join('    <item android:drawable="@drawable/%s" />\n' % name for name in names)
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<layer-list xmlns:android="http://schemas.android.com/apk/res/android">\n'
            + items + '</layer-list>\n')


def layer_specs(layers, resolve=None, base=None, radii=0, border=None, padding=None):
    """The description of each layer, bottom first. The bottom one carries
    the colour under them all, the border and the padding; every layer keeps
    the corners."""
    specs = []
    for index, gradient in enumerate(reversed(layers)):
        bottom = index == 0
        specs.append(spec(gradient, resolve, base=base if bottom else None, radii=radii,
                          border=border if bottom else None,
                          padding=padding if bottom else None))
    return [one for one in specs if one]


def drawable_xml(package, description, ripple=None):
    """The resource: the class with its description, in a ripple when the
    component is pressed (``ripple`` is the ripple's colour)."""
    element = ('<drawable class="%s.ApkpyGradient" app:apkpySpec="%s" />'
               % (package, description))
    head = ('<?xml version="1.0" encoding="utf-8"?>\n')
    names = ('xmlns:android="http://schemas.android.com/apk/res/android"\n'
             '    xmlns:app="http://schemas.android.com/apk/res-auto"')
    if ripple:
        return (head + '<ripple %s\n    android:color="%s">\n    <item>\n        %s\n'
                '    </item>\n</ripple>\n' % (names, ripple, element))
    return head + element.replace('<drawable ', '<drawable %s\n    ' % names, 1) + '\n'


def attrs_xml():
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<resources>\n'
            '    <declare-styleable name="ApkpyGradient">\n'
            '        <attr name="apkpySpec" format="string" />\n'
            '    </declare-styleable>\n'
            '</resources>\n')


def java_class(package):
    return _JAVA.replace("__PACKAGE__", package)


_JAVA = r"""package __PACKAGE__;

import android.content.res.Resources;
import android.content.res.TypedArray;
import android.graphics.Canvas;
import android.graphics.ColorFilter;
import android.graphics.LinearGradient;
import android.graphics.Matrix;
import android.graphics.Outline;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.RadialGradient;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.drawable.Drawable;
import android.os.Build;
import android.util.AttributeSet;

import org.xmlpull.v1.XmlPullParser;
import org.xmlpull.v1.XmlPullParserException;

import java.io.IOException;

/**
 * A CSS gradient as a background, written by ApkPy from
 * {@code background: linear-gradient(...)} or {@code radial-gradient(...)}.
 * The geometry is CSS's: an angle where 0 points up and 90 right, a gradient
 * line long enough for its ends to meet the corners, stops anywhere.
 */
public class ApkpyGradient extends Drawable {
    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint base = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path path = new Path();
    private final Path edge = new Path();
    private final RectF box = new RectF();
    private int kind;
    private float angle = 180f;
    private int corner = -1;
    private int[] colors = {0, 0};
    private float[] stops = {0f, 1f};
    private float spanStart = 0f, spanEnd = 1f;
    private boolean repeating;
    private int shape = 1, extent = 3;
    private float centerX = 0.5f, centerY = 0.5f;
    private final float[] radii = new float[8];
    private boolean hasBase;
    private float strokeWidth;
    private final Rect padding = new Rect();
    private boolean hasPadding;
    private int alpha = 255;
    private float minAlpha = 1f;

    public ApkpyGradient() {
        stroke.setStyle(Paint.Style.STROKE);
    }

    @Override
    public void inflate(Resources r, XmlPullParser parser, AttributeSet attrs,
                        Resources.Theme theme) throws XmlPullParserException, IOException {
        super.inflate(r, parser, attrs, theme);
        TypedArray a = theme != null
                ? theme.obtainStyledAttributes(attrs, R.styleable.ApkpyGradient, 0, 0)
                : r.obtainAttributes(attrs, R.styleable.ApkpyGradient);
        String description = a.getString(R.styleable.ApkpyGradient_apkpySpec);
        a.recycle();
        read(description == null ? "" : description, r.getDisplayMetrics().density);
    }

    private static int argb(String hex) {
        return (int) Long.parseLong(hex.trim(), 16);
    }

    private static float[] numbers(String text) {
        String[] parts = text.split(",");
        float[] out = new float[parts.length];
        for (int i = 0; i < parts.length; i++) out[i] = Float.parseFloat(parts[i].trim());
        return out;
    }

    private void read(String description, float density) {
        for (String part : description.split(";")) {
            int eq = part.indexOf('=');
            if (eq < 0) continue;
            String key = part.substring(0, eq), value = part.substring(eq + 1);
            switch (key) {
                case "kind": kind = Integer.parseInt(value); break;
                case "angle": angle = Float.parseFloat(value); break;
                case "corner": corner = Integer.parseInt(value); break;
                case "shape": shape = Integer.parseInt(value); break;
                case "extent": extent = Integer.parseInt(value); break;
                case "center": { float[] c = numbers(value); centerX = c[0]; centerY = c[1]; break; }
                case "span": { float[] s = numbers(value); spanStart = s[0]; spanEnd = s[1]; repeating = true; break; }
                case "stops": stops = numbers(value); break;
                case "colors": {
                    String[] hex = value.split(",");
                    colors = new int[hex.length];
                    minAlpha = 1f;
                    for (int i = 0; i < hex.length; i++) {
                        colors[i] = argb(hex[i]);
                        minAlpha = Math.min(minAlpha, ((colors[i] >>> 24) & 0xFF) / 255f);
                    }
                    break;
                }
                case "radii": {
                    float[] c = numbers(value);
                    for (int i = 0; i < 4; i++) { radii[i * 2] = c[i] * density; radii[i * 2 + 1] = c[i] * density; }
                    break;
                }
                case "base": base.setColor(argb(value)); hasBase = true; break;
                case "stroke": {
                    int comma = value.indexOf(',');
                    strokeWidth = Float.parseFloat(value.substring(0, comma)) * density;
                    stroke.setStrokeWidth(strokeWidth);
                    stroke.setColor(argb(value.substring(comma + 1)));
                    break;
                }
                case "padding": {
                    float[] p = numbers(value);
                    padding.set(Math.round(p[3] * density), Math.round(p[0] * density),
                            Math.round(p[1] * density), Math.round(p[2] * density));
                    hasPadding = true;
                    break;
                }
                default: break;
            }
        }
    }

    private float cssAngle(float w, float h) {
        if (corner < 0) return angle;
        float towards = (float) Math.toDegrees(Math.atan2(Math.max(h, 1e-6f), Math.max(w, 1e-6f)));
        switch (corner) {
            case 0: return towards;
            case 1: return 180f - towards;
            case 2: return 180f + towards;
            default: return 360f - towards;
        }
    }

    private void build() {
        Rect b = getBounds();
        float w = b.width(), h = b.height();
        path.reset();
        edge.reset();
        if (w <= 0 || h <= 0) return;
        box.set(b);
        path.addRoundRect(box, radii, Path.Direction.CW);
        if (strokeWidth > 0) {
            float half = strokeWidth / 2f;
            float[] inner = new float[8];
            for (int i = 0; i < 8; i++) inner[i] = Math.max(0f, radii[i] - half);
            edge.addRoundRect(new RectF(box.left + half, box.top + half,
                    box.right - half, box.bottom - half), inner, Path.Direction.CW);
        }
        Shader.TileMode mode = repeating ? Shader.TileMode.REPEAT : Shader.TileMode.CLAMP;
        if (kind == 0) {
            double a = Math.toRadians(cssAngle(w, h));
            float dx = (float) Math.sin(a), dy = (float) -Math.cos(a);
            float half = (Math.abs(w * dx) + Math.abs(h * dy)) / 2f;
            float sx = b.left + w / 2f - dx * half, sy = b.top + h / 2f - dy * half;
            float ex = sx + dx * 2f * half, ey = sy + dy * 2f * half;
            float x0 = sx + (ex - sx) * spanStart, y0 = sy + (ey - sy) * spanStart;
            float x1 = sx + (ex - sx) * spanEnd, y1 = sy + (ey - sy) * spanEnd;
            fill.setShader(new LinearGradient(x0, y0, x1, y1, colors, stops, mode));
        } else {
            float cx = centerX * w, cy = centerY * h;
            float left = cx, right = w - cx, top = cy, bottom = h - cy;
            float rx, ry;
            if (extent == 0 || extent == 2) {
                boolean closest = extent == 0;
                rx = closest ? Math.min(left, right) : Math.max(left, right);
                ry = closest ? Math.min(top, bottom) : Math.max(top, bottom);
                if (shape == 0) rx = ry = closest ? Math.min(rx, ry) : Math.max(rx, ry);
            } else {
                boolean closest = extent == 1;
                float sx = closest ? Math.min(left, right) : Math.max(left, right);
                float sy = closest ? Math.min(top, bottom) : Math.max(top, bottom);
                if (shape == 0) { rx = ry = (float) Math.hypot(sx, sy); }
                else { rx = sx * 1.41421356f; ry = sy * 1.41421356f; }
            }
            rx = Math.max(rx, 0.5f);
            ry = Math.max(ry, 0.5f);
            // A unit circle scaled to the ellipse. A repeating one repeats
            // every (last stop - first stop) of the radius.
            float scale = repeating ? (spanEnd - spanStart) : 1f;
            RadialGradient g = new RadialGradient(0f, 0f, Math.max(scale, 1e-3f), colors, stops, mode);
            Matrix m = new Matrix();
            m.setScale(rx, ry);
            m.postTranslate(b.left + cx, b.top + cy);
            g.setLocalMatrix(m);
            fill.setShader(g);
        }
    }

    @Override
    protected void onBoundsChange(Rect bounds) {
        super.onBoundsChange(bounds);
        build();
    }

    @Override
    public void draw(Canvas canvas) {
        if (path.isEmpty()) build();
        if (path.isEmpty()) return;
        if (hasBase) canvas.drawPath(path, base);
        canvas.drawPath(path, fill);
        if (strokeWidth > 0) canvas.drawPath(edge, stroke);
    }

    @Override
    public boolean getPadding(Rect out) {
        if (!hasPadding) return super.getPadding(out);
        out.set(padding);
        return true;
    }

    @Override
    public void getOutline(Outline outline) {
        Rect b = getBounds();
        boolean same = true;
        for (float r : radii) if (r != radii[0]) { same = false; break; }
        if (same) {
            outline.setRoundRect(b, radii[0]);
        } else if (!path.isEmpty()) {
            if (Build.VERSION.SDK_INT >= 30) outline.setPath(path);
            else outline.setConvexPath(path);
        }
        outline.setAlpha(hasBase ? alpha / 255f : minAlpha * alpha / 255f);
    }

    @Override
    public void setAlpha(int value) {
        alpha = value;
        fill.setAlpha(value);
        base.setAlpha(value);
        stroke.setAlpha(value);
        invalidateSelf();
    }

    @Override
    public int getAlpha() {
        return alpha;
    }

    @Override
    public void setColorFilter(ColorFilter filter) {
        fill.setColorFilter(filter);
        base.setColorFilter(filter);
        stroke.setColorFilter(filter);
        invalidateSelf();
    }

    @Override
    public int getOpacity() {
        return PixelFormat.TRANSLUCENT;
    }
}
"""
