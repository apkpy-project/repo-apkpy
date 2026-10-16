"""Text fields with help, an error and a required rule, on the phone.

``inputs(..., help=, error=, required=)`` wraps the EditText in an
``ApkpyField``: the field, and under it one line of supporting text.
``field.set_error(text)`` and ``validate(a, b)`` reach it through its id.
What the line says and when a field counts as empty come from
``field_rules`` -- the module the Previewer draws from -- and ApkpyField
mirrors ``supporting`` and ``check`` one for one.

A field with none of the three, and that no ``set_error`` or ``validate``
names, is the bare EditText it always was: nothing in an existing app moves.

The words travel in the layout, not in Java: the help is the supporting
line's ``android:text`` and the required message its ``android:hint``, so
``t("key")`` in either follows the phone's language like any other text.

``ApkpyField`` is a fixed class, written into the project only when an app
uses it, like ApkpyChoice and ApkpyChart.
"""

import ast

from ... import field_rules as rules
from .. import i18n

CODE = rules.CODE
CHECK = 'validate'          # validate(a, b) and a.validate()
ERROR = 'set_error'         # a.set_error("...")

# Whether the app has a function of its own called validate(): then the name
# is the app's, and only the method form is ours.
_OWN_CHECK = [False]


def java_string(value):
    text = str(value or '')
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def _line(node):
    return getattr(node, 'lineno', 0) or 0


def _is_method(node, name):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == name and isinstance(node.func.value, ast.Name))


def _is_check_function(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == CHECK and not _OWN_CHECK[0])


def is_check_call(node):
    """``validate(a, b)`` or ``a.validate()``, as a value or a condition."""
    return _is_check_function(node) or (_is_method(node, CHECK) and not node.args)


def check_names(node):
    """The fields a check call names, as the Python wrote them."""
    if _is_method(node, CHECK):
        return [node.func.value.id]
    names = []
    for arg in node.args:
        if not isinstance(arg, ast.Name):
            rules.refuse('validate() takes the fields to check, by name.',
                         ast.dump(arg)[:80], _line(node))
        names.append(arg.id)
    return names


def prescan(tree):
    """The names of the fields the app sets an error on or validates. Such a
    field needs the line under it even when its inputs() call asks for none."""
    _OWN_CHECK[0] = any(isinstance(node, ast.FunctionDef) and node.name == CHECK
                        for node in ast.walk(tree))
    names = set()
    for node in ast.walk(tree):
        if _is_method(node, ERROR):
            names.add(node.func.value.id)
        elif is_check_call(node):
            names.update(arg.id for arg in getattr(node, 'args', []) if isinstance(arg, ast.Name))
            if _is_method(node, CHECK):
                names.add(node.func.value.id)
    return names


def _words(transpiler, call, name):
    """``help=`` / ``error=`` / ``required=`` as the build can read them:
    text, a constant declared above, or t("key")."""
    node = transpiler._kw_node(call.keywords, name)
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name) and node.id in getattr(transpiler, 'string_constants', {}):
        return transpiler.string_constants[node.id]
    value = transpiler._kw(call.keywords, name)
    if isinstance(value, str) and i18n.is_marked(value):
        return value
    rules.refuse('%s= of inputs() is written into the layout while the app is built, '
                 'so it has to be text, a constant declared above or t("key").' % name,
                 '%s=%s' % (name, ast.dump(node)[:60]), _line(call),
                 ['Set it while the app runs: field.set_error(...) in a function.'])


def parse(transpiler, call, comp, py_var):
    line = _line(call)
    help_text = rules.words(_words(transpiler, call, 'help'), 'help', line)
    error_text = rules.words(_words(transpiler, call, 'error'), 'error', line)
    required = rules.required_message(_words(transpiler, call, 'required'), line)
    named = py_var in getattr(transpiler, 'field_targets', ())
    if not (rules.wanted(help_text, error_text, required) or named):
        return
    rules.check_type(comp.get('input_type', 'text'), line)
    comp['_field_box'] = True
    comp['help'] = help_text
    comp['error'] = error_text
    comp['required_message'] = required


def boxed(comp):
    return bool(comp and comp.get('_field_box'))


def parse_call(transpiler, call):
    """``a.set_error(text)``, ``a.validate()`` and ``validate(a, b)`` written
    as statements. None for anything else."""
    if _is_method(call, ERROR):
        if not call.args:
            rules.refuse('set_error() takes the words to show; "" clears the error.',
                         'set_error()', _line(call))
        return {'type': 'field_error', 'py_var': call.func.value.id, 'val_node': call.args[0]}
    if is_check_call(call):
        return {'type': 'field_check', 'node': call}
    return None


def box_id(jv):
    return jv + '_box'


def error_java(box, val_java):
    # Words written in the source are already a String.
    text = val_java if _is_string_literal(val_java) else f"String.valueOf({val_java})"
    return f"ApkpyField.error(findViewById(R.id.{box}), {text});"


def _is_string_literal(java):
    body = java[1:-1]
    return (len(java) >= 2 and java[0] == '"' and java[-1] == '"'
            and '"' not in body.replace('\\"', ''))


def check_java(node, box_of):
    """The check as a Java boolean. ``box_of(name)`` is the box's id on this
    screen, or None: a field of another screen has nothing to show here."""
    boxes = [box for box in (box_of(name) for name in check_names(node)) if box]
    if not boxes:
        return 'true'
    return 'ApkpyField.valid(%s)' % ', '.join('findViewById(R.id.%s)' % box for box in boxes)


def value_java(node, box_of):
    """The same check where a value is wanted: "true" or "false", as a
    switch answers."""
    return '(%s ? "true" : "false")' % check_java(node, box_of)


def condition_java(node, val_to_java):
    """An `if` over a check. val_to_java knows the screen's views, so the
    value form is asked for and its wrapper taken off again."""
    value = val_to_java(node)
    tail = ' ? "true" : "false")'
    if value.startswith('(') and value.endswith(tail):
        return value[1:-len(tail)]
    return 'Boolean.parseBoolean(String.valueOf(%s))' % value


def open_xml(indent, number, package, width, attrs):
    return [
        f'{indent}<{package}.ApkpyField',
        f'{indent}    android:id="@+id/inp{number}_box"',
        f'{indent}    android:layout_width="{width}"',
        f'{indent}    android:layout_height="wrap_content"{attrs}',
        f'{indent}    android:orientation="vertical">',
    ]


def close_xml(indent, number, package, comp, pad_start, pad_end, escape):
    help_text = comp.get('help') or ''
    required = comp.get('required_message') or ''
    lines = [
        f'{indent}    <TextView',
        f'{indent}        android:id="@+id/inp{number}_support"',
        f'{indent}        android:layout_width="match_parent"',
        f'{indent}        android:layout_height="wrap_content"',
        f'{indent}        android:paddingTop="{rules.SUPPORT_GAP}dp"',
        f'{indent}        android:paddingStart="{pad_start}dp"',
        f'{indent}        android:paddingEnd="{pad_end}dp"',
        f'{indent}        android:textSize="{rules.SUPPORT_SIZE}sp"',
        f'{indent}        android:accessibilityLiveRegion="polite"',
    ]
    if required:
        lines.append(f'{indent}        android:hint="{escape(required)}"')
    if help_text:
        lines.append(f'{indent}        android:text="{escape(help_text)}" />')
    else:
        lines.append(f'{indent}        android:visibility="gone" />')
    lines += [f'{indent}</{package}.ApkpyField>', '']
    return lines


def _text_java(value):
    if value and i18n.is_marked(value):
        return 'getString(R.string.%s)' % i18n.resource_name(i18n.key_of(value))
    return java_string(value)


def java_setup(indent, comp, jv, colors, color_java):
    """The lines in onCreate that fill the ApkpyField around EditText ``jv``."""
    box = box_id(jv)
    normal = comp.get('_drawable')
    wrong = comp.get('_error_drawable')
    return [
        f"{indent}ApkpyField {box} = findViewById(R.id.{box});",
        (f"{indent}{box}.configure({color_java(colors['help'])}, {color_java(colors['error'])}, "
         f"{('R.drawable.%s' % normal) if normal and wrong else '0'}, "
         f"{('R.drawable.%s' % wrong) if normal and wrong else '0'}, "
         f"{_text_java(comp.get('error') or '')});"),
    ]


def uses_field(components):
    for comp in components or []:
        if boxed(comp):
            return True
        if uses_field(comp.get('children')):
            return True
    return False


JAVA = r'''package __PACKAGE__;

import android.content.Context;
import android.content.res.ColorStateList;
import android.os.Bundle;
import android.os.Parcelable;
import android.text.Editable;
import android.text.TextWatcher;
import android.util.AttributeSet;
import android.view.View;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.core.view.ViewCompat;

/**
 * A text field and the line of words under it: help, or an error in its
 * place. The layout gives it two children, the EditText and the supporting
 * TextView. Mirrors apkpy_lib/field_rules.py.
 */
public final class ApkpyField extends LinearLayout {
    private EditText field;
    private TextView support;
    private String help = "";
    private String required = "";
    private String error = "";
    private int helpColor;
    private int errorColor;
    private int normalBackground;
    private int errorBackground;
    private boolean ready;
    private boolean paintedError;

    public ApkpyField(Context context, AttributeSet attrs) {
        super(context, attrs);
        setOrientation(VERTICAL);
    }

    /**
     * The backgrounds are drawable resources, or 0 for a field that keeps
     * the framework's underline: that one is tinted instead.
     */
    public void configure(int helpColor, int errorColor, int normalBackground,
                          int errorBackground, String initialError) {
        field = (EditText) getChildAt(0);
        support = (TextView) getChildAt(1);
        this.helpColor = helpColor;
        this.errorColor = errorColor;
        this.normalBackground = normalBackground;
        this.errorBackground = errorBackground;
        // The words come from the layout, so they follow the language.
        help = String.valueOf(support.getText());
        CharSequence message = support.getHint();
        required = message == null ? "" : message.toString();
        support.setHint(null);
        field.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int a, int b, int c) {}
            @Override public void onTextChanged(CharSequence s, int a, int b, int c) {}
            @Override public void afterTextChanged(Editable s) {
                // Typing answers the complaint. Text put back by the system
                // or by set_value arrives without the focus and leaves it.
                if (error.length() > 0 && field.hasFocus()) setError("");
            }
        });
        field.setAccessibilityDelegate(new View.AccessibilityDelegate() {
            @Override
            public void onInitializeAccessibilityNodeInfo(View host, AccessibilityNodeInfo info) {
                super.onInitializeAccessibilityNodeInfo(host, info);
                if (error.length() > 0) {
                    info.setContentInvalid(true);
                    info.setError(error);
                }
            }
        });
        ready = true;
        setError(initialError);
    }

    /** field_rules.supporting: the words under the field. */
    static String supportingText(String help, String error) {
        if (error != null && error.length() > 0) return error;
        return help == null ? "" : help;
    }

    /** field_rules.supporting: whether those words are an error. */
    static boolean supportingIsError(String help, String error) {
        return error != null && error.length() > 0;
    }

    /** field_rules.check: the error an unfinished field shows, or "". */
    static String check(String value, String required) {
        if (required == null || required.length() == 0) return "";
        String text = value == null ? "" : value;
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (!Character.isWhitespace(c) && !Character.isSpaceChar(c)) return "";
        }
        return required;
    }

    public void setError(CharSequence message) {
        error = message == null ? "" : message.toString();
        if (!ready) return;
        boolean wrong = supportingIsError(help, error);
        String words = supportingText(help, error);
        support.setText(words);
        support.setTextColor(wrong ? errorColor : helpColor);
        support.setVisibility(words.length() == 0 ? GONE : VISIBLE);
        if (wrong == paintedError) return;
        paintedError = wrong;
        if (normalBackground != 0 && errorBackground != 0) {
            int left = field.getPaddingLeft(), top = field.getPaddingTop();
            int right = field.getPaddingRight(), bottom = field.getPaddingBottom();
            field.setBackgroundResource(wrong ? errorBackground : normalBackground);
            field.setPadding(left, top, right, bottom);
        } else {
            ViewCompat.setBackgroundTintList(field, wrong ? ColorStateList.valueOf(errorColor) : null);
        }
    }

    /** Checks the field's own rule, shows or clears its error, says whether it passed. */
    public boolean validate() {
        String problem = check(field.getText().toString(), required);
        setError(problem);
        return problem.length() == 0;
    }

    /** Every field is checked, so all the errors show at once; the first that failed takes the cursor. */
    public static boolean valid(View... fields) {
        ApkpyField first = null;
        for (View view : fields) {
            if (!(view instanceof ApkpyField)) continue;
            ApkpyField one = (ApkpyField) view;
            if (!one.validate() && first == null) first = one;
        }
        if (first != null) first.field.requestFocus();
        return first == null;
    }

    public static void error(View view, String message) {
        if (view instanceof ApkpyField) ((ApkpyField) view).setError(message);
    }

    @Override
    protected Parcelable onSaveInstanceState() {
        Bundle state = new Bundle();
        state.putParcelable("apkpy:super", super.onSaveInstanceState());
        state.putString("apkpy:error", error);
        return state;
    }

    @Override
    protected void onRestoreInstanceState(Parcelable state) {
        if (state instanceof Bundle) {
            Bundle bundle = (Bundle) state;
            super.onRestoreInstanceState(bundle.getParcelable("apkpy:super"));
            final String saved = bundle.getString("apkpy:error", "");
            // After the children: the field's own text comes back first.
            post(new Runnable() {
                @Override public void run() { setError(saved); }
            });
            return;
        }
        super.onRestoreInstanceState(state);
    }
}
'''


def java_source(package):
    return JAVA.replace('__PACKAGE__', package)
