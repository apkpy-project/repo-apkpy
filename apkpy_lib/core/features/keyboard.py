"""The keyboard of a text field, on the phone.

``type="email"|"phone"|"url"`` is a text field whose android:inputType opens
the keyboard for it; ``action=`` is android:imeOptions, the key in the
keyboard's corner; ``on_submit=`` is an OnEditorActionListener; ``autofill=``
is android:autofillHints. ``hide_keyboard()`` and ``field.focus()`` close and
open the keyboard through two helpers every screen carries (dead_methods drops
them from a screen that never calls them).

A plain one-line field gets android:inputType="text" as well. Without one an
EditText is multi-line: Enter typed a new line and the field grew, where the
Previewer's field is one line and Enter moves on. What each word means is
field_rules', which the Previewer reads too.
"""

import ast

from ... import field_rules as rules

HIDE = 'hide_keyboard'
FOCUS = 'focus'
TEXT_TYPES = ('text', 'search', 'password', 'number')

# name -> type of every field the app keeps in a name (email = inputs(...)),
# found before anything is read: a function above the field may focus it.
_FIELDS = [{}]
# Whether the app has a hide_keyboard() of its own: then the name is the app's.
_OWN_HIDE = [False]


def _line(node):
    return getattr(node, 'lineno', 0) or 0


def prescan(tree):
    fields = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id in ('inputs', 'input_field')):
            kind = 'text'
            for keyword in node.value.keywords:
                if (keyword.arg == 'type' and isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, str)):
                    kind = keyword.value.value
                if (keyword.arg == 'password' and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value):
                    kind = 'password'
            fields[node.targets[0].id] = kind
    _FIELDS[0] = fields
    _OWN_HIDE[0] = any(isinstance(node, ast.FunctionDef) and node.name == HIDE
                       for node in ast.walk(tree))
    return fields


def _word(transpiler, call, name, line):
    node = transpiler._kw_node(call.keywords, name)
    if node is None or (isinstance(node, ast.Constant) and node.value is None):
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    rules.refuse('%s= of inputs() is written as a word in quotes.' % name,
                 '%s=%s' % (name, ast.dump(node)[:60]), line,
                 ['inputs("Message", action="send")', 'inputs("Email", autofill="email")'],
                 keyboard=True)


def parse(transpiler, call, comp, py_var):
    """inputs(): the keyboard type, the corner key, on_submit and autofill."""
    line = _line(call)
    kind = comp.get('input_type', 'text')
    submit = transpiler._kw_node(call.keywords, 'on_submit')
    if isinstance(submit, ast.Constant) and submit.value is None:
        submit = None
    action = rules.action_of(kind, _word(transpiler, call, 'action', line),
                             submit is not None, line)
    hint = rules.autofill_of(_word(transpiler, call, 'autofill', line), line)
    rules.check_autofill_type(kind, hint, line)
    if kind in rules.KEYBOARD_TYPES:
        comp['keyboard'] = kind
        comp['input_type'] = rules.base_type(kind)
    comp['ime_action'] = action
    comp['autofill'] = hint
    comp['on_submit'] = (_submit_function(transpiler, call, submit, str(py_var or comp.get('id') or 'input'), line)
                         if submit is not None else None)


def _submit_function(transpiler, call, node, hint, line):
    """on_submit= as the name of a function of the app, given the text or nothing."""
    if isinstance(node, ast.Name):
        rules.check_submit_arity(getattr(transpiler, 'function_arity', {}).get(node.id, 0), line)
        return node.id
    if isinstance(node, ast.Lambda):
        arguments = node.args
        params = [a.arg for a in arguments.posonlyargs + arguments.args]
        if arguments.vararg or arguments.kwarg or arguments.kwonlyargs:
            rules.check_submit_arity(2, line)
        rules.check_submit_arity(len(params), line)
        body = node.body
        if isinstance(body, ast.IfExp):
            does = [None if isinstance(branch, ast.Constant) else ast.Expr(value=branch)
                    for branch in (body.body, body.orelse)]
            if does[0] is None and does[1] is None:
                statements = []
            elif does[0] is None:
                statements = [ast.If(test=ast.UnaryOp(op=ast.Not(), operand=body.test),
                                     body=[does[1]], orelse=[])]
            else:
                statements = [ast.If(test=body.test, body=[does[0]],
                                     orelse=[does[1]] if does[1] is not None else [])]
        else:
            statements = [ast.Expr(value=body)]
        for statement in statements:
            ast.copy_location(statement, node)
            ast.fix_missing_locations(statement)
        name = transpiler._unique_function_name(hint + '_submit')
        transpiler.functions[name] = {
            'args': params,
            'cmds': transpiler._parse_statements(statements),
            'string_args': set(params),
            'returns_value': False,
        }
        getattr(transpiler, 'function_arity', {})[name] = len(params)
        return name
    if isinstance(node, ast.Attribute):
        # on_submit=chat.send: a bound method, called with nothing.
        return transpiler._parse_callback_kw(call, 'on_submit', hint)
    rules.refuse('on_submit= of inputs() is a function: its name, or a lambda.',
                 'on_submit=%s' % ast.dump(node)[:60], line,
                 ['def send(text):  ...  then  inputs("Message", on_submit=send)'], keyboard=True)


# ── hide_keyboard() and field.focus() ───────────────────────────────────────

def parse_call(transpiler, call):
    """hide_keyboard() / field.focus() on a line of their own; None for anything else."""
    line = _line(call)
    if isinstance(call.func, ast.Name) and call.func.id == HIDE and not _OWN_HIDE[0]:
        if call.args or call.keywords:
            rules.refuse('hide_keyboard() takes nothing.', 'hide_keyboard(...)', line,
                         ['hide_keyboard()'], keyboard=True)
        return {'type': 'keyboard_call', 'method': 'hide', 'py_var': None}
    if (isinstance(call.func, ast.Attribute) and call.func.attr == FOCUS
            and isinstance(call.func.value, ast.Name) and call.func.value.id in _FIELDS[0]):
        name = call.func.value.id
        if call.args or call.keywords:
            rules.refuse('focus() takes nothing.', '%s.focus(...)' % name, line,
                         ['%s.focus()' % name], keyboard=True)
        rules.check_focus(_FIELDS[0][name], line)
        return {'type': 'keyboard_call', 'method': 'focus', 'py_var': name}
    return None


def command_java(cmd, comp):
    """The line of a keyboard_call; None for a field that is not on this screen."""
    if cmd['method'] == 'hide':
        return '_apkpyHideKeyboard();'
    if not comp or not comp.get('_java_var') or comp.get('comp_type') not in ('inputs', 'input_field'):
        return None
    return '_apkpyShowKeyboard(findViewById(R.id.%s));' % comp['_java_var']


# ── The EditText ────────────────────────────────────────────────────────────

def xml_attrs(comp, indent, itype):
    """The keyboard's attributes of a one-line EditText of type ``itype``
    (text, search, password or number: the last two carry their inputType)."""
    out = ''
    if itype in ('text', 'search'):
        out += '\n%s    android:inputType="%s"' % (indent, rules.INPUT_TYPES[comp.get('keyboard') or itype])
    if comp.get('ime_action'):
        out += '\n%s    android:imeOptions="%s"' % (indent, rules.ACTIONS[comp['ime_action']])
    if comp.get('autofill'):
        out += ('\n%s    android:autofillHints="%s"'
                '\n%s    android:importantForAutofill="yes"') % (
                    indent, rules.AUTOFILL[comp['autofill']], indent)
    return out


def java_setup(indent, comp, jv, functions_map):
    """The corner key's listener, when it does something of ours: on_submit,
    or closing the keyboard after "done", "search" or "go". "next" with no
    on_submit, and a field with no action, are Android's own."""
    callback = comp.get('on_submit')
    action = comp.get('ime_action')
    runs = bool(callback) and callback in functions_map
    hides = action in rules.HIDES_KEYBOARD
    if not (runs or hides):
        return []
    body = []
    if runs:
        text = '_v.getText().toString()' if functions_map[callback].get('args') else ''
        body.append('pythonCallback_%s(%s);' % (callback, text))
    if hides:
        body.append('_apkpyHideKeyboard();')
    elif action == 'next':
        # Done here, not left to Android: an Enter key that comes as a key
        # event with FLAG_EDITOR_ACTION would reach the listener twice.
        body.append('android.view.View _next = _v.focusSearch(android.view.View.FOCUS_FORWARD);')
        body.append('if (_next != null) _next.requestFocus();')
    lines = [
        '%s%s.setOnEditorActionListener((_v, _action, _key) -> {' % (indent, jv),
        # A hardware Enter (or a keyboard that sends one) comes as IME_NULL,
        # down and then up: the down does it, the up is only taken.
        '%s    if (_action == android.view.inputmethod.EditorInfo.IME_NULL) {' % indent,
        '%s        if (_key == null || _key.getKeyCode() != android.view.KeyEvent.KEYCODE_ENTER) return false;' % indent,
        '%s        if (_key.getAction() != android.view.KeyEvent.ACTION_DOWN) return true;' % indent,
        '%s    }' % indent,
    ]
    lines += ['%s    %s' % (indent, line) for line in body]
    lines += ['%s    return true;' % indent, '%s});' % indent]
    return lines


def has_typed_field(components):
    """Whether a screen has a field you type in: its onCreate then keeps the
    field the keyboard opens over in sight (_apkpyKeepFieldAboveKeyboard)."""
    for comp in components or []:
        if (comp.get('comp_type') in ('inputs', 'input_field')
                and comp.get('input_type', 'text') in rules.TYPES):
            return True
    return False


KEEP_CALL = '_apkpyKeepFieldAboveKeyboard();'


def helpers_java():
    """_apkpyHideKeyboard(), _apkpyShowKeyboard(view) and
    _apkpyKeepFieldAboveKeyboard(), for every screen."""
    return [
        "",
        "    // Since targetSdk 35 the window is edge to edge: adjustResize gives the",
        "    // screen the keyboard's height as padding instead of shrinking it, and a",
        "    // scrolling screen no longer scrolls the field the keyboard opens over into",
        "    // sight (seen 14-11-2026: \"A plain field\" stayed under the keyboard). Each",
        "    // time the keyboard comes up or the focus moves, the field is scrolled",
        "    // above it -- or, if it is taller than the room left, its top to the top.",
        "    private void _apkpyKeepFieldAboveKeyboard() {",
        "        final android.view.View _decor = getWindow().getDecorView();",
        "        final int[] _seen = {-1};",
        "        final android.view.View[] _was = {null};",
        "        final Runnable _check = () -> {",
        "            androidx.core.view.WindowInsetsCompat _in = androidx.core.view.ViewCompat.getRootWindowInsets(_decor);",
        "            if (_in == null) return;",
        "            int _ime = _in.isVisible(androidx.core.view.WindowInsetsCompat.Type.ime())",
        "                    ? _in.getInsets(androidx.core.view.WindowInsetsCompat.Type.ime()).bottom : 0;",
        "            android.view.View _f = getCurrentFocus();",
        "            if (_ime == _seen[0] && _f == _was[0]) return;",
        "            _seen[0] = _ime;",
        "            _was[0] = _f;",
        "            if (_ime == 0 || !(_f instanceof android.widget.EditText)) return;",
        "            android.view.ViewParent _p = _f.getParent();",
        "            while (_p != null && !(_p instanceof androidx.core.widget.NestedScrollView)",
        "                    && !(_p instanceof android.widget.ScrollView)) _p = _p.getParent();",
        "            if (!(_p instanceof android.view.View)) return;",
        "            int _gap = (int) (16 * getResources().getDisplayMetrics().density);",
        "            int _top = _in.getInsets(androidx.core.view.WindowInsetsCompat.Type.systemBars()).top + _gap;",
        "            int _bottom = _decor.getHeight() - _ime - _gap;",
        "            int[] _at = new int[2];",
        "            _f.getLocationInWindow(_at);",
        "            int _by = 0;",
        "            if (_at[1] + _f.getHeight() > _bottom) _by = Math.min(_at[1] + _f.getHeight() - _bottom, _at[1] - _top);",
        "            else if (_at[1] < _top) _by = _at[1] - _top;",
        "            if (_by != 0) ((android.view.View) _p).scrollBy(0, _by);",
        "        };",
        "        // The keyboard coming up is a layout; \"next\" moving the cursor to the",
        "        // next field is not, so the focus is listened to as well.",
        "        _decor.getViewTreeObserver().addOnGlobalLayoutListener(() -> _check.run());",
        "        _decor.getViewTreeObserver().addOnGlobalFocusChangeListener((_old, _now) -> _decor.post(_check));",
        "    }",
        "",
        "    private void _apkpyHideKeyboard() {",
        "        android.view.View _f = getCurrentFocus();",
        "        android.view.inputmethod.InputMethodManager _imm =",
        "                (android.view.inputmethod.InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);",
        "        android.view.View _w = _f != null ? _f : getWindow().getDecorView();",
        "        if (_imm != null) _imm.hideSoftInputFromWindow(_w.getWindowToken(), 0);",
        "        if (_f != null) _f.clearFocus();",
        "    }",
        "",
        "    private void _apkpyShowKeyboard(final android.view.View _v) {",
        "        if (_v == null) return;",
        "        _v.requestFocus();",
        "        final android.view.inputmethod.InputMethodManager _imm =",
        "                (android.view.inputmethod.InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);",
        "        if (_imm == null) return;",
        "        if (_v.hasWindowFocus()) {",
        "            _v.post(() -> _imm.showSoftInput(_v, 0));",
        "            return;",
        "        }",
        "        // Asked as the screen opens: the window has no focus yet, and a",
        "        // keyboard asked for before it has one does not come.",
        "        _v.getViewTreeObserver().addOnWindowFocusChangeListener(",
        "                new android.view.ViewTreeObserver.OnWindowFocusChangeListener() {",
        "            @Override public void onWindowFocusChanged(boolean _has) {",
        "                if (!_has) return;",
        "                _v.getViewTreeObserver().removeOnWindowFocusChangeListener(this);",
        "                _v.post(() -> _imm.showSoftInput(_v, 0));",
        "            }",
        "        });",
        "    }",
    ]
