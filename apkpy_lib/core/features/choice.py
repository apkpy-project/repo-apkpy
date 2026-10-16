"""Chips and segmented buttons on the phone.

``chips(options, selected=, multiple=, on_change=, icons=)`` and
``segmented(...)`` become one ``ApkpyChoice`` view. What a tap selects, where
a chip wraps and every size come from ``choice_rules`` -- the module the
Previewer draws from -- and ApkpyChoice mirrors its functions one for one.

The view draws the shapes, icons and words itself, the way the Previewer's
canvas does. Each option also gets an invisible child over its 48dp touch
area: that is what the finger presses, what ripples and what TalkBack reads,
as a checkbox (or a radio button when only one can be on) that says whether
it is checked.

``ApkpyChoice`` is a fixed class, written into the project only when an app
uses it, like ApkpyChart and ApkpyPager.
"""

import ast
import json

from ... import choice_rules as rules

COMPONENTS = rules.KINDS
CODE = rules.CODE


def java_string(value):
    if value is None:
        return 'null'
    text = str(value)
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def _line(node):
    return getattr(node, 'lineno', 0) or 0


def _literal(node, list_assignments):
    """The Python value written in the source, or a marker when it is not
    written out."""
    if isinstance(node, ast.Name) and node.id in (list_assignments or {}):
        node = list_assignments[node.id]
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return _NOT_LITERAL


_NOT_LITERAL = object()


def _on_change(transpiler, node, hint):
    """A named function or a one-parameter lambda, as the name of a function
    the view calls with the value. None when there is none."""
    if node is None or (isinstance(node, ast.Constant) and node.value is None):
        return None, 0
    if isinstance(node, ast.Name):
        return node.id, getattr(transpiler, 'function_arity', {}).get(node.id, 1)
    if isinstance(node, ast.Lambda):
        params = [a.arg for a in node.args.args][:1]
        name = transpiler._unique_function_name(hint + '_change')
        body = ast.Expr(value=node.body)
        ast.fix_missing_locations(body)
        transpiler.functions[name] = {
            'args': params,
            'cmds': transpiler._parse_statements([body]),
            'string_args': set(params),
            'returns_value': False,
        }
        return name, len(params)
    rules.refuse('on_change= of chips() and segmented() is a function.',
                 ast.dump(node)[:80], _line(node),
                 ['on_change=show  (def show(choice): ...)',
                  'on_change=lambda choice: label_x.set_value(choice)'])


def parse(transpiler, kind, call, comp, py_var):
    lists = getattr(transpiler, 'list_assignments', {}) or {}
    line = _line(call)
    options_node = call.args[0] if call.args else transpiler._kw_node(call.keywords, 'options')
    raw_options = _literal(options_node, lists) if options_node is not None else None
    if raw_options is _NOT_LITERAL:
        rules.refuse('The options of %s() have to be written out, as a list of words or '
                     'the name of one at the top of the file.' % kind,
                     ast.dump(options_node)[:80], line,
                     ['%s(["Day", "Week", "Month"], ...)' % kind,
                      'PERIODS = ["Day", "Week", "Month"]  and  %s(PERIODS, ...)' % kind])
    options = rules.options_from(kind, raw_options, line)
    icons_node = transpiler._kw_node(call.keywords, 'icons')
    raw_icons = _literal(icons_node, lists) if icons_node is not None else None
    if raw_icons is _NOT_LITERAL:
        rules.refuse('icons= of %s() has to be written out, one name per option.' % kind,
                     ast.dump(icons_node)[:80], line)
    multiple_node = transpiler._kw_node(call.keywords, 'multiple')
    multiple = bool(multiple_node.value) if isinstance(multiple_node, ast.Constant) else False
    check_node = transpiler._kw_node(call.keywords, 'check')
    check = bool(check_node.value) if isinstance(check_node, ast.Constant) else True
    required_node = transpiler._kw_node(call.keywords, 'required')
    required = bool(required_node.value) if isinstance(required_node, ast.Constant) else False
    selected_node = transpiler._kw_node(call.keywords, 'selected')
    raw_selected = (_literal(selected_node, lists) if selected_node is not None else None)
    if raw_selected is _NOT_LITERAL:
        # Known when the screen opens, not now: the view starts as the rules
        # say for nothing selected and takes the value at run time.
        initial = rules.initial(kind, options, None, multiple, line, required)
        comp['selected_node'] = selected_node
    else:
        initial = rules.initial(kind, options, raw_selected, multiple, line, required)
        comp['selected_node'] = None
    callback, arity = _on_change(transpiler, transpiler._kw_node(call.keywords, 'on_change'),
                                 str(py_var or transpiler._kw(call.keywords, 'id') or kind))
    comp.update({
        'id': transpiler._kw(call.keywords, 'id'),
        'kind': kind,
        'options': options,
        'icons': rules.icons_from(kind, raw_icons, options, line),
        'multiple': multiple,
        'check': check,
        'required': required,
        'initial': initial,
        'on_change': callback,
        'on_change_arity': arity,
    })
    if callback and multiple:
        transpiler.choice_list_callbacks = getattr(transpiler, 'choice_list_callbacks', set())
        transpiler.choice_list_callbacks.add(callback)


def mark_list_params(transpiler):
    """With multiple=True the value is a list, and on the phone a list is
    JSON text. Marked, so `"Kotlin" in selected` asks the list and not the
    text (where "Kot" would be found inside "Kotlin")."""
    for name in getattr(transpiler, 'choice_list_callbacks', set()):
        info = transpiler.functions.get(name)
        if isinstance(info, dict) and info.get('args'):
            info.setdefault('list_args', set()).add(info['args'][0])


def layout_xml(indent, number, package, margin_xml):
    return [
        f'{indent}<{package}.ApkpyChoice',
        f'{indent}    android:id="@+id/chc{number}"',
        f'{indent}    android:layout_width="match_parent"',
        f'{indent}    android:layout_height="wrap_content"{margin_xml} />',
        '',
    ]


def java_setup(indent, comp, jv, colors, radius, text_size, color_java, val_to_java):
    """The lines in onCreate that fill ApkpyChoice ``jv``."""
    drawables = comp.get('_choice_drawables') or [None] * len(comp.get('options') or [])
    icons_java = 'new int[]{%s}' % ', '.join(
        ('R.drawable.%s' % name) if name else '0' for name in drawables)
    def paint(colour):
        return color_java(colour) if colour else 'android.graphics.Color.TRANSPARENT'

    check = ('R.drawable.%s' % (comp.get('_check_drawable') or 'ic_choice_check')
             if comp.get('check', True) else '0')
    lines = [
        f"{indent}ApkpyChoice {jv} = findViewById(R.id.{jv});",
        (f"{indent}{jv}.configure({'true' if comp['kind'] == 'segmented' else 'false'}, "
         f"{'true' if comp.get('multiple') else 'false'}, "
         f"{'true' if comp.get('required') else 'false'}, "
         f"{java_string(json.dumps(comp['options'], ensure_ascii=False))}, "
         f"{icons_java}, {check}, "
         f"{paint(colors['fill'])}, {paint(colors['border'])}, {color_java(colors['text'])}, "
         f"{color_java(colors['icon'])}, {color_java(colors['active_fill'])}, "
         f"{color_java(colors['active_text'])}, {float(radius)}f, {float(text_size)}f, "
         f"{java_string(json.dumps(comp.get('initial') or [], ensure_ascii=False))});"),
    ]
    if comp.get('selected_node') is not None:
        lines.append(f"{indent}{jv}.setValue(String.valueOf({val_to_java(comp['selected_node'])}));")
    if comp.get('on_change'):
        call = (f"pythonCallback_{comp['on_change']}(_value)" if comp.get('on_change_arity', 1)
                else f"pythonCallback_{comp['on_change']}()")
        lines.append(f"{indent}{jv}.setOnChange(_value -> {call});")
    return lines


def get_java(jv):
    return f"((ApkpyChoice) findViewById(R.id.{jv})).getValue()"


def set_java(jv, val_java):
    return f"((ApkpyChoice) findViewById(R.id.{jv})).setValue(String.valueOf({val_java}));"


def uses_choice(components):
    for comp in components or []:
        if comp.get('comp_type') in COMPONENTS:
            return True
        if uses_choice(comp.get('children')):
            return True
    return False


JAVA = r'''package __PACKAGE__;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.InsetDrawable;
import android.graphics.drawable.RippleDrawable;
import android.os.Build;
import android.os.Bundle;
import android.os.Parcelable;
import android.text.TextPaint;
import android.text.TextUtils;
import android.util.AttributeSet;
import android.util.SparseArray;
import android.util.TypedValue;
import android.view.View;
import android.view.ViewGroup;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.TextView;

import org.json.JSONArray;

import java.util.ArrayList;

/**
 * Chips and segmented buttons. What a tap selects, where a chip wraps and
 * every size come from choice_rules.py and are mirrored here one for one
 * (tap, flow, segmentEdges, chipWidth), so the phone and the Previewer agree.
 *
 * The view draws the shapes, icons and words itself. Each option also has an
 * invisible child over its touch area: the finger presses it, it ripples,
 * and TalkBack reads it as a checkbox, or a radio button when only one can be
 * on, checked or not.
 */
public class ApkpyChoice extends ViewGroup {

    public interface OnChange { void onChange(String value); }

    private static final float TOUCH = __TOUCH__f;
    private static final float BORDER = __BORDER__f;
    private static final float ICON = __ICON__f;
    private static final float ICON_GAP = __ICON_GAP__f;
    private static final float CHIP_HEIGHT = __CHIP_HEIGHT__f;
    private static final float CHIP_PAD = __CHIP_PAD__f;
    private static final float CHIP_PAD_ICON = __CHIP_PAD_ICON__f;
    private static final float CHIP_GAP = __CHIP_GAP__f;
    private static final float SEGMENT_HEIGHT = __SEGMENT_HEIGHT__f;
    private static final float SEGMENT_PAD = __SEGMENT_PAD__f;
    private static final int WEIGHT = __WEIGHT__;

    private final ArrayList<String> options = new ArrayList<>();
    private final ArrayList<Integer> icons = new ArrayList<>();
    private final ArrayList<String> selected = new ArrayList<>();
    private int[] left = new int[0], top = new int[0], right = new int[0], bottom = new int[0];
    private final SparseArray<Drawable> drawables = new SparseArray<>();
    private final TextPaint words = new TextPaint(Paint.ANTI_ALIAS_FLAG);
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path path = new Path();
    private final RectF box = new RectF();
    private final float den;
    private boolean segmented;
    private boolean multiple;
    private boolean required;
    private int fill, border, text, icon, activeFill, activeText, checkIcon;
    private float radius = 8f;
    private OnChange listener;

    public ApkpyChoice(Context context) {
        this(context, null);
    }

    public ApkpyChoice(Context context, AttributeSet attrs) {
        super(context, attrs);
        den = context.getResources().getDisplayMetrics().density;
        setWillNotDraw(false);
        setSaveEnabled(true);
        // The theme's typeface, at Material's label weight where Android has one.
        Typeface face = new TextView(context).getTypeface();
        if (Build.VERSION.SDK_INT >= 28) face = Typeface.create(face, WEIGHT, false);
        words.setTypeface(face);
    }

    private float dp(float value) {
        return value * den;
    }

    public void configure(boolean segmented, boolean multiple, boolean required,
                          String optionsJson, int[] iconIds,
                          int checkIcon, int fill, int border, int text, int icon,
                          int activeFill, int activeText, float radius, float textSizeSp,
                          String initialJson) {
        this.segmented = segmented;
        this.multiple = multiple;
        this.required = required;
        this.checkIcon = checkIcon;
        this.fill = fill;
        this.border = border;
        this.text = text;
        this.icon = icon;
        this.activeFill = activeFill;
        this.activeText = activeText;
        this.radius = radius;
        words.setTextSize(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, textSizeSp,
                getResources().getDisplayMetrics()));
        options.clear();
        icons.clear();
        ArrayList<String> parsed = parse(optionsJson);
        if (parsed != null) options.addAll(parsed);
        for (int i = 0; i < options.size(); i++) {
            icons.add(iconIds != null && i < iconIds.length ? iconIds[i] : 0);
        }
        ArrayList<String> first = parse(initialJson);
        selected.clear();
        if (first != null) selected.addAll(inOrder(first));
        removeAllViews();
        for (String option : options) addView(target(option));
        requestLayout();
        invalidate();
    }

    public void setOnChange(OnChange listener) {
        this.listener = listener;
    }

    /** choice_rules.value_of: the selected word, or "" -- a JSON list of them when multiple. */
    public String getValue() {
        if (multiple) {
            JSONArray array = new JSONArray();
            for (String option : selected) array.put(option);
            return array.toString();
        }
        return selected.isEmpty() ? "" : selected.get(0);
    }

    /** choice_rules.from_value. The listener is not called: it answers taps. */
    public void setValue(String value) {
        String given = value == null ? "" : value;
        boolean keep = keepsOne(segmented, multiple, required);
        ArrayList<String> wanted = new ArrayList<>();
        if (multiple) {
            String trimmed = given.trim();
            ArrayList<String> parsed = trimmed.startsWith("[") ? parse(trimmed) : null;
            if (parsed != null) wanted.addAll(parsed);
            else if (!trimmed.isEmpty()) wanted.add(trimmed);
            ArrayList<String> chosen = inOrder(wanted);
            if (!(keep && chosen.isEmpty())) apply(chosen);
        } else if (options.contains(given)) {
            wanted.add(given);
            apply(wanted);
        } else if (!keep) {
            apply(wanted);
        }
    }

    /** choice_rules.keeps_one: one option always stays selected. */
    static boolean keepsOne(boolean segmented, boolean multiple, boolean required) {
        return required || (segmented && !multiple);
    }

    /** choice_rules.tap: the selection after a tap on option. */
    static ArrayList<String> tap(boolean segmented, ArrayList<String> options,
                                 ArrayList<String> current, String option, boolean multiple,
                                 boolean required) {
        ArrayList<String> out = new ArrayList<>();
        if (!options.contains(option)) {
            out.addAll(current);
            return out;
        }
        boolean keep = keepsOne(segmented, multiple, required);
        if (multiple) {
            boolean on = current.contains(option);
            for (String each : options) {
                if (each.equals(option)) {
                    if (!on) out.add(each);
                } else if (current.contains(each)) {
                    out.add(each);
                }
            }
            if (keep && out.isEmpty()) out.addAll(current);
            return out;
        }
        if (current.contains(option)) {
            if (keep) out.addAll(current);
            return out;
        }
        out.add(option);
        return out;
    }

    /** choice_rules.flow: {x, line} for each chip. */
    static int[][] flow(int[] widths, int maxWidth, int gap) {
        int[][] out = new int[widths.length][2];
        int x = 0;
        int line = 0;
        for (int i = 0; i < widths.length; i++) {
            if (x > 0 && x + widths[i] > maxWidth) {
                x = 0;
                line++;
            }
            out[i][0] = x;
            out[i][1] = line;
            x += widths[i] + gap;
        }
        return out;
    }

    /** choice_rules.segment_edges: the width shared equally. */
    static int[] segmentEdges(int count, int width) {
        int[] out = new int[count + 1];
        for (int i = 0; i <= count; i++) out[i] = (int) (((long) i * width) / count);
        return out;
    }

    /** choice_rules.chip_width, in pixels. */
    private int chipWidth(float textWidth, boolean hasIcon) {
        float start = hasIcon ? CHIP_PAD_ICON + ICON + ICON_GAP : CHIP_PAD;
        return Math.round(dp(start) + textWidth + dp(CHIP_PAD));
    }

    private static ArrayList<String> parse(String json) {
        try {
            JSONArray array = new JSONArray(json == null ? "[]" : json);
            ArrayList<String> out = new ArrayList<>();
            for (int i = 0; i < array.length(); i++) out.add(String.valueOf(array.get(i)));
            return out;
        } catch (Exception e) {
            return null;
        }
    }

    private ArrayList<String> inOrder(ArrayList<String> wanted) {
        ArrayList<String> out = new ArrayList<>();
        for (String option : options) if (wanted.contains(option)) out.add(option);
        return out;
    }

    private void apply(ArrayList<String> next) {
        selected.clear();
        selected.addAll(next);
        // A chip gains a check when it is selected, and is wider for it.
        requestLayout();
        invalidate();
    }

    private void tapped(String option) {
        ArrayList<String> next = tap(segmented, options, selected, option, multiple, required);
        if (next.equals(selected)) return;
        apply(next);
        if (listener != null) listener.onChange(getValue());
    }

    private View target(final String option) {
        View view = new View(getContext());
        view.setContentDescription(option);
        view.setFocusable(true);
        view.setClickable(true);
        view.setOnClickListener(v -> tapped(option));
        view.setAccessibilityDelegate(new View.AccessibilityDelegate() {
            @Override
            public void onInitializeAccessibilityNodeInfo(View host, AccessibilityNodeInfo info) {
                super.onInitializeAccessibilityNodeInfo(host, info);
                info.setClassName(multiple ? "android.widget.CheckBox" : "android.widget.RadioButton");
                info.setCheckable(true);
                info.setChecked(selected.contains(option));
            }
        });
        return view;
    }

    /** choice_rules.leading_icon: the check on a selected option, when there is one. */
    private int leadIcon(int index) {
        return selected.contains(options.get(index)) && checkIcon != 0 ? checkIcon : icons.get(index);
    }

    private boolean hasLead(int index) {
        return leadIcon(index) != 0;
    }

    private int inset() {
        return Math.round(dp((TOUCH - (segmented ? SEGMENT_HEIGHT : CHIP_HEIGHT)) / 2f));
    }

    @Override
    protected void onMeasure(int widthSpec, int heightSpec) {
        int count = options.size();
        int mode = MeasureSpec.getMode(widthSpec);
        int width = MeasureSpec.getSize(widthSpec);
        int touch = Math.round(dp(TOUCH));
        left = new int[count];
        top = new int[count];
        right = new int[count];
        bottom = new int[count];
        int height = touch;
        if (!segmented) {
            int room = mode == MeasureSpec.UNSPECIFIED ? Integer.MAX_VALUE : width;
            int[] widths = new int[count];
            for (int i = 0; i < count; i++) {
                widths[i] = Math.min(room, chipWidth(words.measureText(options.get(i)), hasLead(i)));
            }
            int[][] places = flow(widths, room, Math.round(dp(CHIP_GAP)));
            int lines = count == 0 ? 1 : places[count - 1][1] + 1;
            height = lines * touch;
            int widest = 0;
            for (int i = 0; i < count; i++) {
                left[i] = places[i][0];
                top[i] = places[i][1] * touch;
                right[i] = left[i] + widths[i];
                bottom[i] = top[i] + touch;
                widest = Math.max(widest, right[i]);
            }
            if (mode == MeasureSpec.UNSPECIFIED) width = widest;
        } else {
            if (mode == MeasureSpec.UNSPECIFIED) {
                float natural = 0f;
                for (int i = 0; i < count; i++) {
                    float lead = hasLead(i) ? dp(ICON + ICON_GAP) : 0f;
                    natural = Math.max(natural, words.measureText(options.get(i)) + lead + dp(2 * SEGMENT_PAD));
                }
                width = Math.round(natural * count);
            }
            int[] edges = segmentEdges(Math.max(1, count), width);
            for (int i = 0; i < count; i++) {
                left[i] = edges[i];
                top[i] = 0;
                right[i] = edges[i + 1];
                bottom[i] = touch;
            }
        }
        setMeasuredDimension(width, resolveSize(height, heightSpec));
        for (int i = 0; i < getChildCount() && i < count; i++) {
            getChildAt(i).measure(
                    MeasureSpec.makeMeasureSpec(Math.max(0, right[i] - left[i]), MeasureSpec.EXACTLY),
                    MeasureSpec.makeMeasureSpec(Math.max(0, bottom[i] - top[i]), MeasureSpec.EXACTLY));
        }
    }

    @Override
    protected void onLayout(boolean changed, int l, int t, int r, int b) {
        int count = Math.min(getChildCount(), left.length);
        int inset = inset();
        float corner = dp(radius);
        for (int i = 0; i < count; i++) {
            View child = getChildAt(i);
            child.layout(left[i], top[i], right[i], bottom[i]);
            GradientDrawable mask = new GradientDrawable();
            mask.setColor(Color.WHITE);
            if (segmented) {
                float r0 = Math.min(corner, dp(SEGMENT_HEIGHT) / 2f);
                float start = i == 0 ? r0 : 0f;
                float end = i == count - 1 ? r0 : 0f;
                mask.setCornerRadii(new float[]{start, start, end, end, end, end, start, start});
            } else {
                mask.setCornerRadius(Math.min(corner, dp(CHIP_HEIGHT) / 2f));
            }
            int ripple = (activeText & 0x00FFFFFF) | 0x1F000000;
            child.setBackground(new RippleDrawable(ColorStateList.valueOf(ripple), null,
                    new InsetDrawable(mask, 0, inset, 0, inset)));
        }
    }

    @Override
    public boolean shouldDelayChildPressedState() {
        return false;
    }

    private Drawable icon(int id, int color) {
        if (id == 0) return null;
        Drawable drawable = drawables.get(id);
        if (drawable == null) {
            try {
                drawable = getContext().getDrawable(id).mutate();
            } catch (Exception e) {
                return null;
            }
            drawables.put(id, drawable);
        }
        drawable.setTint(color);
        return drawable;
    }

    private void drawWords(Canvas canvas, String option, float x, float centerY, float room, int color) {
        CharSequence shown = TextUtils.ellipsize(option, words, Math.max(0f, room), TextUtils.TruncateAt.END);
        words.setColor(color);
        canvas.drawText(shown, 0, shown.length(), x, centerY - (words.descent() + words.ascent()) / 2f, words);
    }

    private void drawLead(Canvas canvas, int index, boolean on, float x, float centerY) {
        Drawable lead = icon(leadIcon(index), on ? activeText : icon);
        if (lead == null) return;
        int size = Math.round(dp(ICON));
        int y = Math.round(centerY - size / 2f);
        lead.setBounds(Math.round(x), y, Math.round(x) + size, y + size);
        lead.draw(canvas);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        int count = Math.min(options.size(), left.length);
        if (count == 0) return;
        int inset = inset();
        float stroke = Math.max(1f, dp(BORDER));
        if (!segmented) {
            float corner = Math.min(dp(radius), dp(CHIP_HEIGHT) / 2f);
            for (int i = 0; i < count; i++) {
                boolean on = selected.contains(options.get(i));
                box.set(left[i], top[i] + inset, right[i], top[i] + inset + dp(CHIP_HEIGHT));
                int body = on ? activeFill : fill;
                if (Color.alpha(body) != 0) {
                    paint.setStyle(Paint.Style.FILL);
                    paint.setColor(body);
                    canvas.drawRoundRect(box, corner, corner, paint);
                }
                if (!on) {
                    paint.setStyle(Paint.Style.STROKE);
                    paint.setStrokeWidth(stroke);
                    paint.setColor(border);
                    box.inset(stroke / 2f, stroke / 2f);
                    canvas.drawRoundRect(box, corner - stroke / 2f, corner - stroke / 2f, paint);
                    box.inset(-stroke / 2f, -stroke / 2f);
                }
                float middle = box.centerY();
                float textX = left[i] + dp(CHIP_PAD);
                if (hasLead(i)) {
                    drawLead(canvas, i, on, left[i] + dp(CHIP_PAD_ICON), middle);
                    textX = left[i] + dp(CHIP_PAD_ICON + ICON + ICON_GAP);
                }
                drawWords(canvas, options.get(i), textX, middle, right[i] - dp(CHIP_PAD) - textX,
                        on ? activeText : text);
            }
            return;
        }
        float frameTop = inset;
        float frameBottom = inset + dp(SEGMENT_HEIGHT);
        float corner = Math.min(dp(radius), dp(SEGMENT_HEIGHT) / 2f);
        paint.setStyle(Paint.Style.FILL);
        for (int i = 0; i < count; i++) {
            boolean on = selected.contains(options.get(i));
            int body = on ? activeFill : fill;
            if (Color.alpha(body) == 0) continue;
            float start = i == 0 ? corner : 0f;
            float end = i == count - 1 ? corner : 0f;
            box.set(left[i], frameTop, right[i], frameBottom);
            path.reset();
            path.addRoundRect(box, new float[]{start, start, end, end, end, end, start, start},
                    Path.Direction.CW);
            paint.setColor(body);
            canvas.drawPath(path, paint);
        }
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(stroke);
        paint.setColor(border);
        box.set(left[0], frameTop, right[count - 1], frameBottom);
        box.inset(stroke / 2f, stroke / 2f);
        canvas.drawRoundRect(box, corner - stroke / 2f, corner - stroke / 2f, paint);
        for (int i = 1; i < count; i++) {
            canvas.drawLine(left[i], frameTop, left[i], frameBottom, paint);
        }
        float middle = (frameTop + frameBottom) / 2f;
        for (int i = 0; i < count; i++) {
            boolean on = selected.contains(options.get(i));
            boolean lead = hasLead(i);
            float leadWidth = lead ? dp(ICON + ICON_GAP) : 0f;
            float room = (right[i] - left[i]) - dp(2 * SEGMENT_PAD) - leadWidth;
            CharSequence shown = TextUtils.ellipsize(options.get(i), words, Math.max(0f, room),
                    TextUtils.TruncateAt.END);
            float content = words.measureText(shown, 0, shown.length()) + leadWidth;
            float x = left[i] + ((right[i] - left[i]) - content) / 2f;
            if (lead) {
                drawLead(canvas, i, on, x, middle);
                x += leadWidth;
            }
            words.setColor(on ? activeText : text);
            canvas.drawText(shown, 0, shown.length(), x,
                    middle - (words.descent() + words.ascent()) / 2f, words);
        }
    }

    @Override
    protected Parcelable onSaveInstanceState() {
        Bundle state = new Bundle();
        state.putParcelable("apkpy:super", super.onSaveInstanceState());
        state.putStringArrayList("apkpy:selected", new ArrayList<>(selected));
        return state;
    }

    @Override
    protected void onRestoreInstanceState(Parcelable state) {
        if (state instanceof Bundle) {
            Bundle bundle = (Bundle) state;
            ArrayList<String> kept = bundle.getStringArrayList("apkpy:selected");
            super.onRestoreInstanceState(bundle.getParcelable("apkpy:super"));
            if (kept != null) apply(inOrder(kept));
            return;
        }
        super.onRestoreInstanceState(state);
    }
}
'''


def java_source(package):
    values = {
        '__PACKAGE__': package,
        '__TOUCH__': rules.TOUCH, '__BORDER__': rules.BORDER, '__ICON__': rules.ICON,
        '__ICON_GAP__': rules.ICON_GAP, '__CHIP_HEIGHT__': rules.CHIP_HEIGHT,
        '__CHIP_PAD__': rules.CHIP_PAD, '__CHIP_PAD_ICON__': rules.CHIP_PAD_ICON,
        '__CHIP_GAP__': rules.CHIP_GAP, '__SEGMENT_HEIGHT__': rules.SEGMENT_HEIGHT,
        '__SEGMENT_PAD__': rules.SEGMENT_PAD, '__WEIGHT__': rules.TEXT_WEIGHT,
    }
    source = JAVA
    # Longest names first: __CHIP_PAD__ is inside __CHIP_PAD_ICON__.
    for key in sorted(values, key=len, reverse=True):
        source = source.replace(key, str(values[key]))
    return source
