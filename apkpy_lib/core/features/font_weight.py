"""Bold that the phone's own font forgets -- ``ApkpyWeight``.

Seen on a Xiaomi (HyperOS, Android 16) with a font theme installed: every
weight of the system font -- Roboto-Bold, Roboto-Medium, Miui-Bold -- is a
link to one variable file, and the system never turns that file's weight
axis. ``textStyle="bold"``, ``Typeface.DEFAULT_BOLD``, a Material button's
medium and a toolbar title all came out regular. Measured on that phone at
100px: regular 1034, DEFAULT_BOLD 1046, the same file with ``'wght' 700``
1115 -- and only the last one looked bold.

So the app measures, once per process, whether the system's bold reaches
the weight the axis can reach. Where it does -- every phone whose bold works,
static fonts included, since their axis moves nothing -- ``watch()`` returns
at once and nothing about the app changes. Where it does not, each text
drawn at 500 or more is given its weight through the axis, in the font the
person chose.

Why at runtime, from the window, rather than next to each bold in the
generated code: bold comes from a dozen places -- ``textStyle`` in the XML,
``setTypeface`` in row and overlay builders, Material's own buttons, titles
and tabs -- and a rule written at each of them is a rule one of them forgets.
Bold inside a text (markdown ``**...**``, headings) is a span, not a view;
``boldSpan()`` covers those.
"""

CLASS = "ApkpyWeight"

# One line for every window that shows text: each Activity after
# setContentView, and each overlay the app builds (bottom sheet, modal,
# alert, confirm).
ACTIVITY_WATCH = "        ApkpyWeight.watch(getWindow());"


def dialog_watch(dialog_var, indent="        "):
    return f"{indent}ApkpyWeight.watch({dialog_var}.getWindow());"


def shared_class_java(package):
    return '''package %(package)s;

import android.graphics.Paint;
import android.graphics.Typeface;
import android.os.Build;
import android.text.TextPaint;
import android.text.style.MetricAffectingSpan;
import android.text.style.StyleSpan;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewTreeObserver;
import android.view.Window;
import android.widget.TextView;

import java.util.WeakHashMap;

/**
 * Bold that the phone's own font forgets.
 *
 * Some font themes point every weight of the system font at one variable
 * file and never turn its weight axis, so bold comes out regular. Asking the
 * axis directly -- 'wght' 700 -- draws it, in the font the person chose.
 * Measured once per process; on a phone whose bold works this does nothing.
 */
public final class %(klass)s {

    private static final String SAMPLE = "Hamburgefonstiv";
    private static Boolean forgotten;
    // The typeface each text had when it was last looked at. A text whose
    // typeface has not changed since is not looked at again.
    private static final WeakHashMap<TextView, Typeface> SEEN = new WeakHashMap<>();
    // The texts given a weight here, so one that stops being bold loses it.
    private static final WeakHashMap<TextView, String> GIVEN = new WeakHashMap<>();

    private %(klass)s() {}

    /**
     * True when the system's bold reaches less than a quarter of the width
     * the same font reaches through its weight axis. A static font's axis
     * moves nothing, so a phone with one is never counted.
     */
    public static boolean systemBoldIsForgotten() {
        if (forgotten == null) {
            boolean result = false;
            if (Build.VERSION.SDK_INT >= 26) {
                Paint paint = new Paint();
                paint.setTextSize(100f);
                paint.setTypeface(Typeface.DEFAULT);
                float regular = paint.measureText(SAMPLE);
                paint.setTypeface(Typeface.DEFAULT_BOLD);
                float bold = paint.measureText(SAMPLE);
                paint.setTypeface(Typeface.DEFAULT);
                float axis = paint.setFontVariationSettings("'wght' 700")
                        ? paint.measureText(SAMPLE) : regular;
                result = axis - regular > 1f && bold - regular < 0.25f * (axis - regular);
            }
            forgotten = result;
        }
        return forgotten;
    }

    /** Looks after every text in this window, including ones added later. */
    public static void watch(Window window) {
        if (window == null || !systemBoldIsForgotten()) return;
        final View root = window.getDecorView();
        root.getViewTreeObserver().addOnPreDrawListener(new ViewTreeObserver.OnPreDrawListener() {
            private int held;

            @Override
            public boolean onPreDraw() {
                // A text given its weight is measured again before it is
                // drawn, so the first frame is already bold. Never twice in
                // a row: nothing here may stop the screen from drawing.
                if (fix(root) && held == 0) {
                    held = 1;
                    return false;
                }
                held = 0;
                return true;
            }
        });
    }

    /** Bold inside a text -- a markdown **word** or a heading. */
    public static Object boldSpan() {
        return systemBoldIsForgotten() ? new AxisBold() : new StyleSpan(Typeface.BOLD);
    }

    private static boolean fix(View view) {
        boolean changed = false;
        if (view instanceof TextView) {
            changed = fixText((TextView) view);
        }
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0, n = group.getChildCount(); i < n; i++) {
                changed |= fix(group.getChildAt(i));
            }
        }
        return changed;
    }

    private static boolean fixText(TextView text) {
        if (Build.VERSION.SDK_INT < 26) return false;
        Typeface typeface = text.getTypeface();
        if (SEEN.containsKey(text) && SEEN.get(text) == typeface) return false;
        int weight = weightOf(typeface);
        boolean changed = false;
        if (weight >= 500) {
            String wanted = "'wght' " + weight;
            // Cleared first: a TextView ignores settings equal to the ones it
            // holds, and a new typeface has already dropped them.
            text.setFontVariationSettings(null);
            changed = text.setFontVariationSettings(wanted);
            GIVEN.put(text, wanted);
        } else if (GIVEN.remove(text) != null) {
            text.setFontVariationSettings(null);
            changed = true;
        }
        SEEN.put(text, text.getTypeface());
        return changed;
    }

    private static int weightOf(Typeface typeface) {
        if (typeface == null) return 400;
        if (Build.VERSION.SDK_INT >= 28) return typeface.getWeight();
        return typeface.isBold() ? 700 : 400;
    }

    /** StyleSpan(BOLD), plus the weight through the axis. */
    private static final class AxisBold extends MetricAffectingSpan {
        @Override
        public void updateMeasureState(TextPaint paint) {
            embolden(paint);
        }

        @Override
        public void updateDrawState(TextPaint paint) {
            embolden(paint);
        }

        private static void embolden(TextPaint paint) {
            Typeface old = paint.getTypeface();
            int style = (old == null ? Typeface.NORMAL : old.getStyle()) | Typeface.BOLD;
            paint.setTypeface(Typeface.create(old, style));
            if (Build.VERSION.SDK_INT >= 26) {
                paint.setFontVariationSettings(null);
                paint.setFontVariationSettings("'wght' 700");
            }
        }
    }
}
''' % {"package": package, "klass": CLASS}
