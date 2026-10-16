"""A bottom sheet with components in it, on the phone.

``bottom_sheet("Filters", screen=home)`` with ``parent=<the sheet>``
components is still Material's BottomSheetDialog -- the drag, the scrim over
the whole window, the keyboard and Back are the platform's -- around a
layout of its own:

- the sheet is a container in its screen's component list, so every id,
  shape and callback inside it is generated as for any container;
- its XML is written to ``res/layout/sheet_<screen>_<name>.xml`` instead of
  into the screen, under the handle, the title and the text;
- the Activity inflates that layout once in onCreate and answers
  ``findViewById`` from it as well, so the code that sets a component up,
  reads it or writes to it does not know the component lives in a dialog;
- ``open()`` puts the inflated view in a new dialog and shows it. The views
  are kept between openings, so what was typed is still there.

Sizes come from ``sheet_rules``, which the Previewer draws from too.
"""

import re

from ... import sheet_rules as rules
from .. import i18n

CODE = rules.CODE


def _safe(name):
    return re.sub(r'[^a-z0-9_]', '_', str(name).lower())


def java_string(value):
    text = str(value or '')
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def _text_java(value):
    if value and i18n.is_marked(value):
        return 'getString(R.string.%s)' % i18n.resource_name(i18n.key_of(value))
    return java_string(value)


def implicit_id(py_var):
    return 'apkpy_sheet_' + _safe(py_var)


def parse(transpiler, call, overlay, py_var, title, content, on_close):
    """``screen=`` makes the sheet a container of its screen. Returns the
    container, or None for a plain sheet."""
    screen_var = transpiler._kw(call.keywords, 'screen')
    line = getattr(call, 'lineno', 0) or 0
    if screen_var is None:
        return None
    screen_id = transpiler.screens.get(screen_var)
    if not screen_id:
        rules.refuse('screen= of bottom_sheet() is a Screen declared above it.',
                     'screen=%s' % screen_var, line)
    rules.check_plain_arguments(True, transpiler._kw_node(call.keywords, 'items') is not None, line)
    sheet_id = transpiler._kw(call.keywords, 'id') or implicit_id(py_var)
    comp = {
        'comp_type': 'container', 'screen_id': screen_id, '_py_var': py_var,
        'children': [], 'id': sheet_id,
        '_sheet': py_var, '_sheet_title': title or '', '_sheet_content': content or '',
    }
    transpiler.component_vars[py_var] = comp
    transpiler.screen_components.setdefault(screen_id, []).append(comp)
    overlay.update({'composed': True, 'screen_id': screen_id, 'sheet_id': sheet_id,
                    'id': sheet_id, 'title': title or '', 'on_close': on_close})
    return comp


def refuse_child_of_plain_sheet(parent_var, line=0):
    rules.refuse('This sheet has components in it but no screen.',
                 'parent=%s, and %s = bottom_sheet(...) without screen=' % (parent_var, parent_var),
                 line)


def apply_default_styles(overlays, styles):
    """The sheet's body is a column with the rules' defaults under its CSS."""
    for overlay in (overlays or {}).values():
        if overlay.get('composed'):
            styles[overlay['sheet_id']] = rules.body_style(styles.get(overlay['sheet_id'], {}))


def of_screen(overlays, screen_id):
    """{name: overlay} for the sheets that live in this screen, in order."""
    return {name: overlay for name, overlay in (overlays or {}).items()
            if overlay.get('composed') and overlay.get('screen_id') == screen_id}


def layout_name(screen_id, name):
    return 'sheet_%s_%s' % (_safe(screen_id), _safe(name))


def background_name(screen_id, name):
    return 'apkpy_sheet_%s_%s' % (_safe(screen_id), _safe(name))


HANDLE_DRAWABLE = 'apkpy_sheet_handle'


def layout_xml(comp, body_lines, background, escape):
    """The sheet's own layout: handle, title, text, then its components."""
    title, content = comp.get('_sheet_title') or '', comp.get('_sheet_content') or ''
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<androidx.core.widget.NestedScrollView xmlns:android="http://schemas.android.com/apk/res/android"',
        '    xmlns:app="http://schemas.android.com/apk/res-auto"',
        '    android:layout_width="match_parent"',
        '    android:layout_height="wrap_content"',
        f'    android:background="@drawable/{background}">',
        '    <LinearLayout',
        '        android:layout_width="match_parent"',
        '        android:layout_height="wrap_content"',
        '        android:orientation="vertical">',
        '        <View',
        f'            android:layout_width="{rules.HANDLE_WIDTH}dp"',
        f'            android:layout_height="{rules.HANDLE_HEIGHT}dp"',
        '            android:layout_gravity="center_horizontal"',
        f'            android:layout_marginTop="{rules.HANDLE_PAD}dp"',
        f'            android:layout_marginBottom="{rules.HANDLE_PAD}dp"',
        f'            android:alpha="{rules.HANDLE_ALPHA}"',
        '            android:importantForAccessibility="no"',
        f'            android:background="@drawable/{HANDLE_DRAWABLE}" />',
    ]
    if title:
        lines += [
            '        <TextView',
            '            android:layout_width="match_parent"',
            '            android:layout_height="wrap_content"',
            f'            android:paddingStart="{rules.SIDE}dp"',
            f'            android:paddingEnd="{rules.SIDE}dp"',
            f'            android:layout_marginBottom="{rules.TITLE_GAP if content else rules.HEADER_GAP}dp"',
            f'            android:text="{escape(title)}"',
            f'            android:textSize="{rules.TITLE_SIZE}sp"',
            '            android:textStyle="bold"',
            '            android:accessibilityHeading="true"',
            '            android:textColor="@color/apkpy_text" />',
        ]
    if content:
        lines += [
            '        <TextView',
            '            android:layout_width="match_parent"',
            '            android:layout_height="wrap_content"',
            f'            android:paddingStart="{rules.SIDE}dp"',
            f'            android:paddingEnd="{rules.SIDE}dp"',
            f'            android:layout_marginBottom="{rules.HEADER_GAP}dp"',
            f'            android:text="{escape(content)}"',
            f'            android:textSize="{rules.CONTENT_SIZE}sp"',
            '            android:textColor="@color/apkpy_text_secondary" />',
        ]
    lines += ['    ' + line if line else line for line in body_lines]
    while lines and lines[-1] == '':
        lines.pop()
    lines += ['    </LinearLayout>', '</androidx.core.widget.NestedScrollView>', '']
    return '\n'.join(lines)


def background_xml(colour_xml):
    return '\n'.join([
        '<?xml version="1.0" encoding="utf-8"?>',
        '<shape xmlns:android="http://schemas.android.com/apk/res/android">',
        f'    <solid android:color="{colour_xml}" />',
        f'    <corners android:topLeftRadius="{rules.RADIUS}dp" android:topRightRadius="{rules.RADIUS}dp" />',
        '</shape>',
        '',
    ])


def handle_xml():
    return '\n'.join([
        '<?xml version="1.0" encoding="utf-8"?>',
        '<shape xmlns:android="http://schemas.android.com/apk/res/android">',
        '    <solid android:color="@color/apkpy_text_secondary" />',
        f'    <corners android:radius="{rules.HANDLE_HEIGHT / 2:g}dp" />',
        '</shape>',
        '',
    ])


# ── the Activity ─────────────────────────────────────────────────────────────

def _view(name):
    return '_apkpySheet_' + _safe(name)


def _dialog(name):
    return '_apkpySheetDialog_' + _safe(name)


def field_lines(sheets):
    lines = []
    for name in sheets:
        lines.append(f"    private android.view.View {_view(name)};")
        lines.append("    private com.google.android.material.bottomsheet.BottomSheetDialog "
                     f"{_dialog(name)};")
    if lines:
        lines.append("")
    return lines


def inflate_lines(sheets, screen_id, indent="        "):
    """Before any component is set up: their views have to exist."""
    return [f"{indent}{_view(name)} = getLayoutInflater().inflate("
            f"R.layout.{layout_name(screen_id, name)}, null, false);"
            for name in sheets]


def find_override(sheets):
    """A component in a sheet is found like any other."""
    if not sheets:
        return []
    lines = [
        "",
        "    @Override",
        "    public <T extends android.view.View> T findViewById(int id) {",
        "        T found = super.findViewById(id);",
    ]
    for name in sheets:
        lines.append(f"        if (found == null && {_view(name)} != null) "
                     f"found = {_view(name)}.findViewById(id);")
    lines += ["        return found;", "    }"]
    return lines


def open_method(method, name, overlay, dialog_watch):
    """A new dialog each time, around the same views.

    A BottomSheetDialog that was dragged away keeps its behaviour in the
    hidden state, and shown again it can settle off screen. The views are
    what has to last -- what was typed, what was selected -- so they are
    moved into a fresh dialog on every open.
    """
    view, dialog = _view(name), _dialog(name)
    on_close = overlay.get('on_close')
    background = background_name(overlay['screen_id'], name)
    lines = [
        "",
        f"    private void {method}() {{",
        f"        if ({dialog} != null && {dialog}.isShowing()) return;",
        "        final com.google.android.material.bottomsheet.BottomSheetDialog dialog =",
        "                new com.google.android.material.bottomsheet.BottomSheetDialog(this);",
        f"        if ({view}.getParent() instanceof android.view.ViewGroup) {{",
        f"            ((android.view.ViewGroup) {view}.getParent()).removeView({view});",
        "        }",
        f"        dialog.setContentView({view});",
        "        // The frame Material puts around the layout reaches under the",
        "        // navigation bar, so it wears the sheet's shape too: round top",
        "        // corners, one colour to the bottom edge. Material gives it a",
        "        // square surface of its own on the first layout, so the shape is",
        "        // put back after that layout as well as before.",
        f"        final android.view.View frame = (android.view.View) {view}.getParent();",
        "        frame.setBackgroundTintList(null);",
        f"        frame.setBackgroundResource(R.drawable.{background});",
        "        frame.addOnLayoutChangeListener(new android.view.View.OnLayoutChangeListener() {",
        "            @Override public void onLayoutChange(android.view.View v, int l, int t, int r, int b,",
        "                                                 int ol, int ot, int or, int ob) {",
        "                v.removeOnLayoutChangeListener(this);",
        "                v.setBackgroundTintList(null);",
        f"                v.setBackgroundResource(R.drawable.{background});",
        "            }",
        "        });",
        "        // No half-open stop: the sheet is as tall as what is in it.",
        "        dialog.getBehavior().setSkipCollapsed(true);",
        "        dialog.getBehavior().setState("
        "com.google.android.material.bottomsheet.BottomSheetBehavior.STATE_EXPANDED);",
        "        // A field in the sheet stays above the keyboard.",
        "        if (dialog.getWindow() != null) {",
        "            dialog.getWindow().setSoftInputMode("
        "android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);",
        "        }",
    ]
    if overlay.get('title'):
        lines.append(f"        dialog.setTitle({_text_java(overlay['title'])});")
    lines.append("        dialog.setOnDismissListener(d -> {")
    lines.append("            if (_apkpyActiveOverlay == dialog) _apkpyActiveOverlay = null;")
    lines.append(f"            if ({dialog} == dialog) {dialog} = null;")
    if on_close:
        lines.append(f"            pythonCallback_{on_close}();")
    lines += [
        "        });",
        f"        {dialog} = dialog;",
        "        _apkpyActiveOverlay = dialog;",
        "        dialog.show();",
    ]
    if dialog_watch:
        lines.append(dialog_watch)
    lines.append("    }")
    return lines


def absent_method(method):
    """The same function is written into every Activity; the sheet lives in
    one of them."""
    return ["", f"    private void {method}() {{", "        // This sheet belongs to another screen.", "    }"]
