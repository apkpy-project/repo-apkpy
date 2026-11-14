"""The first transpiler, for an app of one screen: the body of a MainActivity."""
import ast

from ..style_parser import parse_css
from ...theme import apply_theme, theme_from_ast
from ...diagnostics import format_exception
from .. import ast_compat

from .style import (
    _get_style_bg, _get_style_border_color, _get_style_focus_border_color, _get_style_pressed_color,
    _parse_border_width, _parse_padding, _parse_radius, _resolve_color,
)
from .resources_xml import _generate_drawable_xml


class JavaTranspiler(ast.NodeVisitor):
    def __init__(self, styles=None):
        self.java_lines = []
        self.counter = 0
        self.input_counter = 0
        self.styles = styles or {}
        self.drawables = {}

    def visit_Call(self, node):
        # ── BUTTON ────────────────────────────────────────────────────────────
        if isinstance(node.func, ast.Name) and node.func.id == 'button':
            self.counter += 1
            button_id = None
            for kw in node.keywords:
                if kw.arg == 'id':
                    button_id = kw.value.value

            label = node.args[0].value
            var_name = f"btn{self.counter}"

            java_code  = f'\n        Button {var_name} = new Button(this);'
            java_code += f'\n        {var_name}.setText("{label}");'

            if button_id in self.styles:
                s = self.styles[button_id]
                radius = _parse_radius(s)
                if radius > 0:
                    bg = _get_style_bg(s)
                    color = _resolve_color(bg)
                    bc = _get_style_border_color(s)
                    bw = _parse_border_width(s)
                    pc = _get_style_pressed_color(s)
                    fc = _get_style_focus_border_color(s)
                    pd = _parse_padding(s)
                    drawable_name = f"{button_id}_shape"
                    self.drawables[f"res/drawable/{drawable_name}.xml"] = _generate_drawable_xml(color, radius, border_color=bc, border_width=bw, pressed_color=pc, focus_color=fc, padding=pd)
                    java_code += f'\n        {var_name}.setBackgroundResource(R.drawable.{drawable_name});'
                elif 'background-color' in s or 'backgroundcolor' in s:
                    bg = _get_style_bg(s)
                    color_macro = bg.upper() if bg.lower() in ('blue', 'red', 'green', 'black', 'white', 'yellow') else 'BLUE'
                    java_code += f'\n        {var_name}.setBackgroundColor(android.graphics.Color.{color_macro});'
                    
                if 'color' in s:
                    java_code += f'\n        {var_name}.setTextColor(android.graphics.Color.WHITE);'

            java_code += f'\n        layout.addView({var_name});'
            self.java_lines.append(java_code)

        # ── INPUTS ────────────────────────────────────────────────────────────
        elif isinstance(node.func, ast.Name) and node.func.id in ('inputs', 'input_field'):
            self.input_counter += 1
            placeholder = node.args[0].value if node.args else ""
            input_id   = None
            input_type = "text"

            for kw in node.keywords:
                if kw.arg == 'id':
                    input_id = kw.value.value
                elif kw.arg == 'type':
                    input_type = kw.value.value

            var_name   = f"input{self.input_counter}"
            style_code = ""
            if input_id and input_id in self.styles:
                s = self.styles[input_id]
                radius = _parse_radius(s)
                if radius > 0:
                    bg = _get_style_bg(s)
                    color = _resolve_color(bg)
                    bc = _get_style_border_color(s)
                    bw = _parse_border_width(s)
                    pc = _get_style_pressed_color(s)
                    fc = _get_style_focus_border_color(s)
                    pd = _parse_padding(s)
                    drawable_name = f"{input_id}_shape"
                    self.drawables[f"res/drawable/{drawable_name}.xml"] = _generate_drawable_xml(color, radius, border_color=bc, border_width=bw, pressed_color=pc, focus_color=fc, padding=pd)
                    style_code += f'\n        {var_name}.setBackgroundResource(R.drawable.{drawable_name});'
                elif 'background-color' in s or 'backgroundcolor' in s:
                    bg = _get_style_bg(s)
                    color_macro = bg.upper() if bg.lower() in ('blue', 'red', 'green', 'black', 'white', 'yellow') else 'BLUE'
                    style_code += f'\n        {var_name}.setBackgroundColor(android.graphics.Color.{color_macro});'
                    
                if 'color' in s:
                    style_code += f'\n        {var_name}.setTextColor(android.graphics.Color.BLACK);'

            if input_type in ("text", "password", "search"):
                java_code  = f'\n        EditText {var_name} = new EditText(this);'
                java_code += f'\n        {var_name}.setHint("{placeholder}");'
                if input_type == "password":
                    java_code += (f'\n        {var_name}.setInputType('
                                  f'android.text.InputType.TYPE_CLASS_TEXT | '
                                  f'android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);')
                else:
                    java_code += f'\n        {var_name}.setInputType(android.text.InputType.TYPE_CLASS_TEXT);'
            elif input_type == "switch":
                java_code  = f'\n        SwitchCompat {var_name} = new SwitchCompat(this);'
                java_code += f'\n        {var_name}.setText("{placeholder}");'
            elif input_type == "checkbox":
                java_code  = f'\n        CheckBox {var_name} = new CheckBox(this);'
                java_code += f'\n        {var_name}.setText("{placeholder}");'
            elif input_type == "range":
                java_code  = f'\n        SeekBar {var_name} = new SeekBar(this);'
                java_code += f'\n        {var_name}.setMax(100);'
            elif input_type == "radio":
                options   = [o.strip() for o in placeholder.split("|")] if placeholder else ["Option 1", "Option 2"]
                java_code = f'\n        RadioGroup {var_name}Group = new RadioGroup(this);'
                for i, opt in enumerate(options):
                    rb_var = f"{var_name}_rb{i}"
                    java_code += f'\n        RadioButton {rb_var} = new RadioButton(this);'
                    java_code += f'\n        {rb_var}.setText("{opt}");'
                    java_code += f'\n        {var_name}Group.addView({rb_var});'
                java_code += f'\n        layout.addView({var_name}Group);'
                self.java_lines.append(java_code)
                self.generic_visit(node)
                return
            else:
                java_code  = f'\n        EditText {var_name} = new EditText(this);'
                java_code += f'\n        {var_name}.setHint("{placeholder}");'

            java_code += style_code
            java_code += f'\n        layout.addView({var_name});'
            self.java_lines.append(java_code)

        self.generic_visit(node)


def translate_python_to_java(python_code, source_name="writehere.py"):
    """Traduz código Python single-screen para o corpo de uma MainActivity Java."""
    try:
        import re
        style_match = re.search(r'style\s*=\s*"""(.*?)"""', python_code, re.DOTALL)
        styles = {}
        clean_code = python_code

        if style_match:
            styles, keyframes = parse_css(style_match.group(1))
            clean_code = python_code.replace(style_match.group(0), "")

        tree = ast_compat.parse(clean_code)
        styles = apply_theme(styles, theme_from_ast(tree))
        transpiler = JavaTranspiler(styles=styles)
        transpiler.visit(tree)

        if not transpiler.java_lines:
            return "        // Nenhum componente detectado", transpiler.drawables
        return "\n".join(transpiler.java_lines), transpiler.drawables

    except Exception as e:
        rendered = format_exception(
            e, context="Android single-screen compiler",
            source_code=python_code, filename=source_name,
        )
        lines = ["        // APKPY_DIAGNOSTIC"]
        lines.extend(
            "        // " + line.replace("*/", "* /")
            for line in rendered.splitlines()
        )
        return "\n".join(lines), {}
