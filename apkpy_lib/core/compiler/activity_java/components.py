"""Each component of the screen, found and made ready in onCreate."""
import json
import re

from ...features import pager as pager_feature
from ...features import chart as chart_feature
from ...features import choice as choice_feature
from .... import choice_rules as _choice_rules
from ...features import field as field_feature
from ...features import shimmer as shimmer_feature
from ...features import web_page as web_page_feature
from ...features import draw_pad as draw_pad_feature
from ...features import keyboard as keyboard_feature
from .... import draw_pad_rules as _draw_pad_rules
from ...features import code_editor as code_editor_feature
from .... import field_rules as _field_rules
from ...features import zoom as zoom_feature
from ...features import gestures as gestures_feature
from .... import chart_rules as _chart_rules
from ...features import feeds as feeds_feature
from ...features import view_state as view_state_feature
from ...features import camera_view as camera_view_feature
from ...style_parser import wants_code_copy
from ....layout_engine import line_count
from .... import motion
from ....theme import badge_at_end, card_text_colors, component_style, input_accent_color
from ..state import _USES_CODE_EDITOR, _USES_SHIMMER
from ..style import (
    _color_java, _content_ink, _get_style_bg, _get_style_border_color, _get_style_fg,
    _has_filter_grayscale, _image_blur_amount, _image_component_style, _ink_parent_backgrounds,
    _parse_aspect_ratio, _parse_border_width, _parse_font_family_android, _parse_font_size,
    _parse_font_weight, _parse_radius, _resolve_color,
)
from ..expressions import (
    _collection_item_java_literal, _escape_java_literal, _list_row_java_literal,
    _rich_item_java_literal,
)
from ..statements import _seed_items_from_state
from ..rows import _emit_row_adapter_setup
from ..layout_xml import _vc_bubble_layout


class Components:
    """Each component of the screen, found and made ready in onCreate."""

    def _generate_java_typography(self, jv, style_dict, default_size=0):
        typo_lines = []
        size = _parse_font_size(style_dict) or default_size
        if size > 0:
            typo_lines.append(f"        {jv}.setTextSize({size});")
        
        family = _parse_font_family_android(style_dict)
        weight = _parse_font_weight(style_dict)
        
        tf_style = "android.graphics.Typeface.NORMAL"
        if weight == 'bold':
            tf_style = "android.graphics.Typeface.BOLD"
        elif weight == 'italic':
            tf_style = "android.graphics.Typeface.ITALIC"
        elif weight == 'bold|italic':
            tf_style = "android.graphics.Typeface.BOLD_ITALIC"
            
        if family:
            typo_lines.append(f"        {jv}.setTypeface(android.graphics.Typeface.create(\"{family}\", {tf_style}));")
        elif tf_style != "android.graphics.Typeface.NORMAL":
            typo_lines.append(f"        {jv}.setTypeface(null, {tf_style});")
            
        color = _get_style_fg(style_dict)
        if color:
            typo_lines.append(f"        {jv}.setTextColor(android.graphics.Color.parseColor(\"{_resolve_color(color)}\"));")
            
        return typo_lines

    def _inject_animation(self, jv, style_dict):
        lines = self.lines
        anim_name = style_dict.get('animation-name')
        if anim_name:
            safe_name = anim_name.lower().replace('-', '_')
            # Shared parser: stripping non-digits turned "0.5s" into 5ms, and
            # the default was 1000ms here against 600ms in the Previewer.
            duration = motion.parse_duration(
                style_dict.get('animation-duration'), 600)
            lines.append(f"        Animation anim_{jv} = AnimationUtils.loadAnimation(this, R.anim.{safe_name});")
            lines.append(f"        anim_{jv}.setDuration({duration});")
            lines.append(f"        {jv}.startAnimation(anim_{jv});")
            lines.append("")

    def _gen_java_comps(self, comp_list, parent_jv, indent="        "):
        styles = self.styles
        lines = self.lines
        _vc_ink_cache = self._vc_ink_cache
        for comp in comp_list:
            ctype = comp['comp_type']

            if ctype == 'button':
                self.cnt['btn'] += 1
                jv = f"btn{self.cnt['btn']}"
                comp['_java_var'] = jv
                comp_id = comp.get('id')
                comp_style = component_style(
                    styles, 'button', comp_id, variant=comp.get('variant')
                )

                lines.append(f"{indent}Button {jv} = findViewById(R.id.{jv});")
                self._inject_animation(jv, comp_style)

            elif ctype == 'list_row':
                self.cnt['lrow'] += 1
                jv = f"lrow{self.cnt['lrow']}"
                comp['_java_var'] = jv
                lines.append(f"{indent}View {jv} = findViewById(R.id.{jv});")
                self._inject_animation(
                    jv, component_style(styles, 'list_row', comp.get('id')),
                )

            elif ctype == 'label':
                self.cnt['lbl'] += 1
                jv = f"lbl{self.cnt['lbl']}"
                comp['_java_var'] = jv
                comp_id = comp.get('id')
                comp_style = component_style(
                    styles, 'label', comp_id, variant=comp.get('variant')
                )

                lines.append(f"{indent}TextView {jv} = findViewById(R.id.{jv});")
                self._inject_animation(jv, comp_style)

            elif ctype in ('inputs', 'input_field'):
                self.cnt['inp'] += 1
                jv = f"inp{self.cnt['inp']}"
                comp['_java_var'] = jv
                itype = comp.get('input_type', 'text')
                placeholder = comp.get('placeholder', '')

                if itype in ('text', 'password', 'search', 'textarea', 'number'):
                    comp_id = comp.get('id')
                    comp_style = component_style(styles, 'inputs', comp_id)
                    lines.append(f"{indent}EditText {jv} = findViewById(R.id.{jv});")
                    self._inject_animation(jv, comp_style)
                    if field_feature.boxed(comp):
                        lines.extend(field_feature.java_setup(
                            indent, comp, jv,
                            _field_rules.colors(styles.get('__theme__', {})), _color_java))
                    lines.extend(keyboard_feature.java_setup(indent, comp, jv, self.functions_map))
                    _syntax = code_editor_feature.language(comp_style) if itype == 'textarea' else None
                    if _syntax:
                        _USES_CODE_EDITOR[0] = True
                        lines.append(code_editor_feature.setup_java(indent, jv, _syntax))

                elif itype == 'switch':
                    comp_id = comp.get('id')
                    comp_style = component_style(styles, 'inputs', comp_id)
                    fg_raw  = _get_style_fg(comp_style) or '#212121'
                    acc_raw = input_accent_color(styles, comp_id)
                    fg_hex  = _resolve_color(fg_raw)
                    acc_hex = _resolve_color(acc_raw)
                    lines.append(f"{indent}final SwitchCompat {jv} = findViewById(R.id.{jv});")
                    lines.append(f"{indent}{jv}.setTextColor(android.graphics.Color.parseColor(\"{fg_hex}\"));")
                    lines.append(f"{indent}final int {jv}_acc = android.graphics.Color.parseColor(\"{acc_hex}\");")
                    lines.append(f"{indent}int[][] {jv}_sw_st = {{{{android.R.attr.state_checked}}, {{}}}};")
                    lines.append(f"{indent}{jv}.setThumbTintList(new android.content.res.ColorStateList({jv}_sw_st, new int[]{{ {jv}_acc, 0xFFBDBDBD }}));")
                    lines.append(f"{indent}{jv}.setTrackTintList(new android.content.res.ColorStateList({jv}_sw_st, new int[]{{({jv}_acc & 0x00FFFFFF) | 0x80000000, 0xFFE0E0E0}}));")
                    lines.append("")

                elif itype == 'checkbox':
                    lines.append(f"{indent}CheckBox {jv} = findViewById(R.id.{jv});")
                    lines.append("")

                elif itype == 'range':
                    lines.append(f"{indent}SeekBar {jv} = findViewById(R.id.{jv});")
                    lines.append("")

                elif itype == 'date':
                    comp_id = comp.get('id')
                    comp_style = component_style(styles, 'inputs', comp_id)
                    fg_hex = _resolve_color(_get_style_fg(comp_style) or '#212121')
                    lines.append(f"{indent}final TextView {jv} = findViewById(R.id.{jv});")
                    lines.append(f"{indent}{jv}.setOnClickListener(_v_{jv} -> {{")
                    lines.append(f"{indent}    java.util.Calendar _cal_{jv} = java.util.Calendar.getInstance();")
                    lines.append(f"{indent}    int _dd_{jv} = _cal_{jv}.get(java.util.Calendar.DAY_OF_MONTH);")
                    lines.append(f"{indent}    int _mm_{jv} = _cal_{jv}.get(java.util.Calendar.MONTH);")
                    lines.append(f"{indent}    int _yy_{jv} = _cal_{jv}.get(java.util.Calendar.YEAR);")
                    lines.append(f"{indent}    String[] _p_{jv} = {jv}.getText().toString().split(\"/\");")
                    lines.append(f"{indent}    if (_p_{jv}.length == 3) {{ try {{ _dd_{jv} = Integer.parseInt(_p_{jv}[0]); _mm_{jv} = Integer.parseInt(_p_{jv}[1]) - 1; _yy_{jv} = Integer.parseInt(_p_{jv}[2]); }} catch (Exception _e_{jv}) {{}} }}")
                    lines.append(f"{indent}    new android.app.DatePickerDialog(this, (_dv_{jv}, _yr_{jv}, _mo_{jv}, _dy_{jv}) -> {{")
                    lines.append(f"{indent}        {jv}.setText(String.format(\"%02d/%02d/%04d\", _dy_{jv}, _mo_{jv} + 1, _yr_{jv}));")
                    view_state_feature.remember(lines, indent + "        ", comp, jv)
                    lines.append(f"{indent}        {jv}.setTextColor(android.graphics.Color.parseColor(\"{fg_hex}\"));")
                    lines.append(f"{indent}    }}, _yy_{jv}, _mm_{jv}, _dd_{jv}).show();")
                    lines.append(f"{indent}}});")
                    lines.append("")

                elif itype == 'time':
                    comp_id = comp.get('id')
                    comp_style = component_style(styles, 'inputs', comp_id)
                    fg_hex = _resolve_color(_get_style_fg(comp_style) or '#212121')
                    lines.append(f"{indent}final TextView {jv} = findViewById(R.id.{jv});")
                    lines.append(f"{indent}{jv}.setOnClickListener(_v_{jv} -> {{")
                    lines.append(f"{indent}    java.util.Calendar _cal_{jv} = java.util.Calendar.getInstance();")
                    lines.append(f"{indent}    int _hh_{jv} = _cal_{jv}.get(java.util.Calendar.HOUR_OF_DAY);")
                    lines.append(f"{indent}    int _mi_{jv} = _cal_{jv}.get(java.util.Calendar.MINUTE);")
                    lines.append(f"{indent}    String[] _p_{jv} = {jv}.getText().toString().split(\":\");")
                    lines.append(f"{indent}    if (_p_{jv}.length == 2) {{ try {{ _hh_{jv} = Integer.parseInt(_p_{jv}[0]); _mi_{jv} = Integer.parseInt(_p_{jv}[1]); }} catch (Exception _e_{jv}) {{}} }}")
                    lines.append(f"{indent}    new android.app.TimePickerDialog(this, (_tv_{jv}, _hr_{jv}, _mn_{jv}) -> {{")
                    lines.append(f"{indent}        {jv}.setText(String.format(\"%02d:%02d\", _hr_{jv}, _mn_{jv}));")
                    view_state_feature.remember(lines, indent + "        ", comp, jv)
                    lines.append(f"{indent}        {jv}.setTextColor(android.graphics.Color.parseColor(\"{fg_hex}\"));")
                    lines.append(f"{indent}    }}, _hh_{jv}, _mi_{jv}, true).show();")
                    lines.append(f"{indent}}});")
                    lines.append("")

                elif itype == 'radio':
                    options = [o.strip() for o in placeholder.split('|')] if placeholder else ['Option 1', 'Option 2']
                    lines.append(f"{indent}RadioGroup {jv}Group = findViewById(R.id.{jv}Group);")
                    for i, opt in enumerate(options):
                        rb = f"{jv}_rb{i}"
                        lines.append(f"{indent}RadioButton {rb} = findViewById(R.id.{rb});")
                    lines.append("")

                elif itype == 'select':
                    comp_id = comp.get('id')
                    comp_style = component_style(styles, 'inputs', comp_id)
                    options = [o.strip() for o in placeholder.split('|')] if placeholder else ['Option 1']
                    opts_java = ', '.join(f'"{o}"' for o in options)
                    fg_raw  = _get_style_fg(comp_style) or '#212121'
                    bg_raw  = _get_style_bg(comp_style) or '#ffffff'
                    bc_raw  = _get_style_border_color(comp_style) or '#bdbdbd'
                    bw_val  = _parse_border_width(comp_style)
                    r_val   = _parse_radius(comp_style)
                    fg_hex  = _resolve_color(fg_raw)
                    bg_hex  = _resolve_color(bg_raw)
                    bc_hex  = _resolve_color(bc_raw)
                    r_dp    = int(r_val) if r_val else 0
                    bw_dp   = int(bw_val) if bw_val else 0
                    lines.extend([
                        f"{indent}final Spinner {jv} = findViewById(R.id.{jv});",
                        f"{indent}final float {jv}_den = getResources().getDisplayMetrics().density;",
                        f"{indent}final int {jv}_fg = android.graphics.Color.parseColor(\"{fg_hex}\");",
                        f"{indent}final int {jv}_bg = android.graphics.Color.parseColor(\"{bg_hex}\");",
                        f"{indent}final int {jv}_bc = android.graphics.Color.parseColor(\"{bc_hex}\");",
                        f"{indent}// Background: solid color + border-radius + stroke",
                        f"{indent}android.graphics.drawable.GradientDrawable {jv}_bgd = new android.graphics.drawable.GradientDrawable();",
                        f"{indent}{jv}_bgd.setColor({jv}_bg);",
                        f"{indent}{jv}_bgd.setCornerRadius({r_dp} * {jv}_den);",
                        f"{indent}{jv}_bgd.setStroke((int)({bw_dp if bw_dp > 0 else 1} * {jv}_den), {jv}_bc);",
                        f"{indent}{jv}.setBackground({jv}_bgd);",
                        f"{indent}// Adapter: applies text color + arrow + padding to selected view and dropdown items",
                        f"{indent}String[] {jv}_opts = new String[]{{{opts_java}}};",
                        f"{indent}ArrayAdapter<String> {jv}Adapter = new ArrayAdapter<String>(this, android.R.layout.simple_spinner_item, {jv}_opts) {{",
                        f"{indent}    private android.graphics.drawable.Drawable makeArrow() {{",
                        f"{indent}        return new android.graphics.drawable.Drawable() {{",
                        f"{indent}            private final android.graphics.Paint _p = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);",
                        f"{indent}            @Override public void draw(android.graphics.Canvas c) {{",
                        f"{indent}                _p.setColor({jv}_fg); android.graphics.Path path = new android.graphics.Path();",
                        f"{indent}                android.graphics.Rect b = getBounds();",
                        f"{indent}                path.moveTo(b.left, b.top); path.lineTo(b.right, b.top); path.lineTo(b.centerX(), b.bottom); path.close();",
                        f"{indent}                c.drawPath(path, _p);",
                        f"{indent}            }}",
                        f"{indent}            @Override public void setAlpha(int a) {{}} @Override public void setColorFilter(android.graphics.ColorFilter cf) {{}}",
                        f"{indent}            @Override public int getOpacity() {{ return android.graphics.PixelFormat.TRANSPARENT; }}",
                        f"{indent}            @Override public int getIntrinsicWidth() {{ return (int)(12 * {jv}_den); }}",
                        f"{indent}            @Override public int getIntrinsicHeight() {{ return (int)(8 * {jv}_den); }}",
                        f"{indent}        }};",
                        f"{indent}    }}",
                        f"{indent}    @Override public android.view.View getView(int pos, android.view.View cv, android.view.ViewGroup parent) {{",
                        f"{indent}        android.widget.TextView tv = (android.widget.TextView) super.getView(pos, cv, parent);",
                        f"{indent}        tv.setTextColor({jv}_fg); tv.setBackground(null);",
                        f"{indent}        int pad = (int)(14 * {jv}_den);",
                        f"{indent}        tv.setPadding(pad, pad, (int)(36 * {jv}_den), pad);",
                        f"{indent}        android.graphics.drawable.Drawable arrow = makeArrow();",
                        f"{indent}        arrow.setBounds(0, 0, arrow.getIntrinsicWidth(), arrow.getIntrinsicHeight());",
                        f"{indent}        tv.setCompoundDrawables(null, null, arrow, null);",
                        f"{indent}        tv.setCompoundDrawablePadding((int)(8 * {jv}_den));",
                        f"{indent}        return tv;",
                        f"{indent}    }}",
                        f"{indent}    @Override public android.view.View getDropDownView(int pos, android.view.View cv, android.view.ViewGroup parent) {{",
                        f"{indent}        android.widget.TextView tv = (android.widget.TextView) super.getDropDownView(pos, cv, parent);",
                        f"{indent}        tv.setTextColor({jv}_fg); tv.setBackgroundColor({jv}_bg);",
                        f"{indent}        int pad = (int)(14 * {jv}_den); tv.setPadding(pad, pad, pad, pad);",
                        f"{indent}        return tv;",
                        f"{indent}    }}",
                        f"{indent}}};",
                        f"{indent}{jv}.setAdapter({jv}Adapter);",
                        f"{indent}{jv}.setPopupBackgroundDrawable(new android.graphics.drawable.ColorDrawable({jv}_bg));",
                        f"{indent}{jv}.setDropDownVerticalOffset((int)(2 * {jv}_den));",
                        f"",
                    ])

            elif ctype == web_page_feature.COMPONENT:
                self.cnt['web'] = self.cnt.get('web', 0) + 1
                jv = f"web{self.cnt['web']}"
                comp['_java_var'] = jv
                _web_own = component_style(styles, ctype, comp.get('id'), include_body=False)
                _web_bg = _get_style_bg(_web_own)
                lines.extend(web_page_feature.java_setup(
                    indent, comp, jv, _resolve_color(_web_bg) if _web_bg else None))

            elif ctype == draw_pad_feature.COMPONENT:
                self.cnt['dpad'] = self.cnt.get('dpad', 0) + 1
                jv = f"dpad{self.cnt['dpad']}"
                comp['_java_var'] = jv
                _pad_own = component_style(styles, ctype, comp.get('id'), include_body=False)
                lines.extend(draw_pad_feature.java_setup(
                    indent, comp, jv,
                    _draw_pad_rules.colors(styles.get('__theme__', {}), _pad_own),
                    _draw_pad_rules.radius(_pad_own), _color_java, self._val_to_java))

            elif ctype in choice_feature.COMPONENTS:
                self.cnt['chc'] = self.cnt.get('chc', 0) + 1
                jv = f"chc{self.cnt['chc']}"
                comp['_java_var'] = jv
                _choice_own = component_style(styles, ctype, comp.get('id'),
                                              include_body=False)
                lines.extend(choice_feature.java_setup(
                    indent, comp, jv,
                    _choice_rules.colors(ctype, styles.get('__theme__', {}), _choice_own),
                    _choice_rules.radius(ctype, _choice_own),
                    _choice_rules.text_size(_choice_own),
                    _color_java, self._val_to_java))

            elif ctype == 'chart':
                self.cnt['chart'] = self.cnt.get('chart', 0) + 1
                jv = f"cht{self.cnt['chart']}"
                comp['_java_var'] = jv
                _chart_style = component_style(styles, 'chart', comp.get('id'),
                                               include_body=False)
                _chart_colors = _chart_rules.chart_colors(
                    styles.get('__theme__', {}), _chart_style)

                def _chart_number(key, default):
                    match = re.search(r'([0-9.]+)', str(_chart_style.get(key, '')))
                    return float(match.group(1)) if match else default

                _kind = comp.get('kind', 'bar')
                lines.append(f"{indent}ApkpyChart {jv} = findViewById(R.id.{jv});")
                lines.append(
                    f"{indent}{jv}.configure({chart_feature.java_string(_kind)}, "
                    f"{chart_feature.java_string(comp.get('x', 'label'))}, "
                    f"{chart_feature.java_string(comp.get('y', 'value'))}, "
                    f"{_color_java(_chart_colors['series'])}, {_color_java(_chart_colors['track'])}, "
                    f"{_color_java(_chart_colors['label'])}, {_color_java(_chart_colors['grid'])}, "
                    f"{_color_java(_chart_colors['center'])}, "
                    f"{_chart_number('height', _chart_rules.DEFAULT_HEIGHT[_kind])}f, "
                    f"{_chart_number('stroke-width', -1.0)}f, "
                    f"{_chart_number('border-radius', -1.0)}f, "
                    f"{_chart_number('font-size', float(_chart_rules.LABEL_SIZE))}f, "
                    f"{'true' if comp.get('fill') else 'false'});")
                if comp.get('items_json') is not None:
                    lines.append(f"{indent}{jv}.setItems({chart_feature.java_string(comp['items_json'])});")
                elif comp.get('items_node') is not None:
                    lines.append(f"{indent}{jv}.setItems(String.valueOf({self._val_to_java(comp['items_node'])}));")
                if _kind in ('ring', 'progress'):
                    _value_node = comp.get('value_node')
                    _value_java = ('0f' if _value_node is None else
                                   f"Float.parseFloat(String.valueOf({self._val_to_java(_value_node)}))")
                    _max = comp.get('max')
                    _max_java = f"{float(_max) if isinstance(_max, (int, float)) else 100.0}f"
                    lines.append(f"{indent}{jv}.setRing({_value_java}, {_max_java}, "
                                 f"{chart_feature.java_string(comp.get('center'))});")
                elif comp.get('center') is not None:
                    lines.append(f"{indent}{jv}.setCenter({chart_feature.java_string(comp.get('center'))});")
                if comp.get('on_click'):
                    lines.append(f"{indent}{jv}.setOnItemClick(_item -> pythonCallback_{comp['on_click']}(_item));")

            elif ctype == 'container' and comp.get('_pager'):
                self.cnt['pager'] = self.cnt.get('pager', 0) + 1
                _pager_number = self.cnt['pager']
                comp['_java_var'] = f"pgr{_pager_number}_host"
                _pager_style = component_style(styles, 'pager', comp.get('id'),
                                               include_body=False)
                _pager_colors = pager_feature.colors(
                    _pager_style, styles.get('__theme__', {}))
                lines.extend(pager_feature.java_setup(
                    _pager_number, indent, pager_feature.tabs_of(comp),
                    _color_java(_pager_colors['active']),
                    _color_java(_pager_colors['inactive']),
                    _color_java(_pager_colors['indicator']),
                    pager_feature.all_caps(_pager_style)))
                if comp.get('children'):
                    self._gen_java_comps(comp['children'], f"pgr{_pager_number}", indent)

            elif ctype == 'container':
                self.cnt['container'] += 1
                jv = f"cnt{self.cnt['container']}"
                # The <LinearLayout> already carries android:id="@+id/cntN";
                # what was missing was anyone recording the name. show()/hide()
                # look the view up through _java_var, so a container that was
                # hidden on the desktop simply stayed put on the phone -- and
                # the rest of the function kept transpiling, so nothing said a
                # line had gone missing. No findViewById is emitted here: the
                # visibility helpers address the view by R.id, so an app that
                # never hides a container generates the XML and Java it always
                # generated.
                comp['_java_var'] = jv
                _shine = component_style(styles, 'container', comp.get('id'),
                                         include_body=False).get('shimmer')
                if _shine:
                    _shine_lines = shimmer_feature.setup_java(
                        indent, jv, _shine,
                        _parse_radius(component_style(styles, 'container', comp.get('id'),
                                                      include_body=False)),
                        lambda c: str(_resolve_color(c)))
                    if _shine_lines:
                        _USES_SHIMMER[0] = True
                        lines.extend(_shine_lines)

                # Recurse into children
                if comp.get('children'):
                    self._gen_java_comps(comp['children'], jv, indent)

            elif ctype in ('markdown', 'rich_text'):
                # Same gap as the container: the view is in the layout as
                # @+id/richN and nothing wrote the name down, so hiding a
                # rendered document worked on the desktop and did nothing on
                # the phone. The counter has to walk in step with the layout
                # pass, which numbers markdown and rich_text together.
                self.cnt['rich'] += 1
                comp['_java_var'] = f"rich{self.cnt['rich']}"

            elif ctype == 'card':
                self.cnt['card'] += 1
                jv = f"card{self.cnt['card']}"
                comp['_java_var'] = jv
                comp_style = component_style(
                    styles, 'card', comp.get('id'),
                    variant=comp.get('variant'),
                )
                lines.append(
                    f"{indent}com.google.android.material.card.MaterialCardView "
                    f"{jv} = findViewById(R.id.{jv});"
                )
                self._inject_animation(jv, comp_style)
                if comp.get('children'):
                    self._gen_java_comps(comp['children'], jv, indent)

            elif ctype in ('empty_state', 'error_state'):
                # The state body is static XML, but its optional action is a
                # regular ApkPy button. Walk it here so the Java listener and
                # callback are generated in the same order as the XML ids.
                if comp.get('children'):
                    self._gen_java_comps(
                        comp['children'], comp.get('_java_var', parent_jv), indent
                    )

            elif ctype == 'image':
                self.cnt['img'] += 1
                jv = f"img{self.cnt['img']}"
                comp['_java_var'] = jv
                comp_id = comp.get('id')
                comp_style = _image_component_style(styles, comp)
                tint_value = comp.get('tint') or comp_style.get('tint')
                radius = _parse_radius(comp_style)
                bw     = _parse_border_width(comp_style)
                # ShapeableImageView se tiver border-radius ou borda
                if radius > 0 or bw > 0:
                    lines.append(f"{indent}com.google.android.material.imageview.ShapeableImageView {jv} = findViewById(R.id.{jv});")
                else:
                    lines.append(f"{indent}android.widget.ImageView {jv} = findViewById(R.id.{jv});")
                if comp.get('zoom'):
                    lines.append(zoom_feature.click_java(indent, jv, comp.get('describe') or ''))
                # Grayscale via ColorMatrix
                if _has_filter_grayscale(comp_style) and not tint_value:
                    lines.append(f"{indent}android.graphics.ColorMatrix _cm_{jv} = new android.graphics.ColorMatrix();")
                    lines.append(f"{indent}_cm_{jv}.setSaturation(0);")
                    lines.append(f"{indent}{jv}.setColorFilter(new android.graphics.ColorMatrixColorFilter(_cm_{jv}));")
                if tint_value:
                    tint_color = _resolve_color(tint_value).replace('"', '\\"')
                    lines.append(
                        f'{indent}_apkpyApplyImageTint({jv}, "{tint_color}");'
                    )
                blur_amount = _image_blur_amount(comp, comp_style)
                if blur_amount > 0:
                    lines.append(f"{indent}if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S) {{")
                    lines.append(f"{indent}    {jv}.setRenderEffect(android.graphics.RenderEffect.createBlurEffect({blur_amount:.2f}f, {blur_amount:.2f}f, android.graphics.Shader.TileMode.CLAMP));")
                    lines.append(f"{indent}}}")
                ratio_value = _parse_aspect_ratio(
                    comp.get('aspect_ratio') or comp_style.get('aspect-ratio')
                )
                if ratio_value and not comp.get('avatar') and not comp_style.get('height'):
                    lines.append(f"{indent}{jv}.post(() -> {{")
                    lines.append(f"{indent}    android.view.ViewGroup.LayoutParams _lp = {jv}.getLayoutParams();")
                    lines.append(f"{indent}    if ({jv}.getWidth() > 0) {{ _lp.height = Math.max(1, Math.round({jv}.getWidth() / {ratio_value:.6f}f)); {jv}.setLayoutParams(_lp); }}")
                    lines.append(f"{indent}}});")
                lines.append("")

            elif ctype == 'camera_view':
                camera_view_feature.emit_init(lines, indent, comp)

            elif ctype == 'video':
                jv = comp.get('_java_var')
                src = _escape_java_literal(str(comp.get('src') or ''))
                repeat_mode = (
                    "Player.REPEAT_MODE_ONE"
                    if comp.get('loop') else "Player.REPEAT_MODE_OFF"
                )
                volume = "0f" if comp.get('muted') else "1f"
                lines.append(f"{indent}{jv} = findViewById(R.id.{jv});")
                lines.append(
                    f"{indent}{jv}Player = new ExoPlayer.Builder(this).build();"
                )
                lines.append(f"{indent}{jv}.setPlayer({jv}Player);")
                lines.append(
                    f"{indent}{jv}Player.setRepeatMode({repeat_mode});"
                )
                lines.append(f"{indent}{jv}Player.setVolume({volume});")
                lines.append(
                    f"{indent}{jv}Player.setHandleAudioBecomingNoisy(true);"
                )
                lines.append(
                    f'{indent}{jv}Player.setMediaItem('
                    f'MediaItem.fromUri("{src}"));'
                )
                lines.append(f"{indent}{jv}Player.addListener(new Player.Listener() {{")
                lines.append(
                    f"{indent}    @Override public void onPlaybackStateChanged("
                    "int state) {"
                )
                lines.append(f"{indent}        if (state == Player.STATE_READY) {{")
                if comp.get('on_ready'):
                    lines.append(
                        f"{indent}            if (!{jv}ReadySent) {{ "
                        f"{jv}ReadySent = true; "
                        f"pythonCallback_{comp['on_ready']}(); }}"
                    )
                lines.append(f"{indent}        }} else if (state == Player.STATE_ENDED) {{")
                if comp.get('on_end'):
                    lines.append(
                        f"{indent}            pythonCallback_{comp['on_end']}();"
                    )
                lines.append(f"{indent}        }}")
                lines.append(f"{indent}    }}")
                if comp.get('on_error'):
                    lines.append(
                        f"{indent}    @Override public void onPlayerError("
                        "PlaybackException error) {"
                    )
                    lines.append(
                        f"{indent}        pythonCallback_{comp['on_error']}("
                        "error.getMessage() == null ? "
                        "error.getClass().getSimpleName() : error.getMessage());"
                    )
                    lines.append(f"{indent}    }}")
                lines.append(f"{indent}}});")
                if comp.get('preload') or comp.get('autoplay'):
                    lines.append(f"{indent}{jv}Player.prepare();")
                    lines.append(f"{indent}{jv}Prepared = true;")
                if comp.get('autoplay'):
                    lines.append(f"{indent}{jv}Player.play();")
                if comp.get('on_progress'):
                    lines.append(f"{indent}{jv}ProgressTick = new Runnable() {{")
                    lines.append(f"{indent}    @Override public void run() {{")
                    lines.append(
                        f"{indent}        if ({jv}Player == null) return;"
                    )
                    lines.append(
                        f"{indent}        long position = Math.max(0L, "
                        f"{jv}Player.getCurrentPosition());"
                    )
                    lines.append(
                        f"{indent}        long duration = Math.max(0L, "
                        f"{jv}Player.getDuration());"
                    )
                    lines.append(
                        f"{indent}        pythonCallback_{comp['on_progress']}("
                        "String.valueOf(position / 1000L), "
                        "String.valueOf(duration / 1000L), "
                        f"String.valueOf({jv}Player.getBufferedPercentage()));"
                    )
                    lines.append(
                        f"{indent}        {jv}Handler.postDelayed(this, 500L);"
                    )
                    lines.append(f"{indent}    }}")
                    lines.append(f"{indent}}};")
                ratio_value = comp.get('aspect_ratio') or (16.0 / 9.0)
                comp_style = component_style(styles, 'video', comp.get('id'))
                if ratio_value and not comp_style.get('height'):
                    lines.append(f"{indent}{jv}.post(() -> {{")
                    lines.append(
                        f"{indent}    android.view.ViewGroup.LayoutParams _lp = "
                        f"{jv}.getLayoutParams();"
                    )
                    lines.append(
                        f"{indent}    if ({jv}.getWidth() > 0) {{ "
                        f"_lp.height = Math.max(1, Math.round("
                        f"{jv}.getWidth() / {float(ratio_value):.6f}f)); "
                        f"{jv}.setLayoutParams(_lp); }}"
                    )
                    lines.append(f"{indent}}});")
                lines.append("")

            elif ctype == 'map':
                jv = comp.get('_java_var')
                markers_json = _escape_java_literal(json.dumps(
                    comp.get('markers', []), ensure_ascii=False,
                    separators=(',', ':'),
                ))
                route_json = _escape_java_literal(json.dumps(
                    comp.get('route', []), ensure_ascii=False,
                    separators=(',', ':'),
                ))
                lines.append(f"{indent}{jv} = findViewById(R.id.{jv});")
                lines.append(
                    f"{indent}{jv}.setCenter({float(comp.get('latitude', 0.0))}d, "
                    f"{float(comp.get('longitude', 0.0))}d, {int(comp.get('zoom', 14))});"
                )
                lines.append(
                    f"{indent}{jv}.setShowUser({str(bool(comp.get('show_user', True))).lower()});"
                )
                lines.append(
                    f"{indent}{jv}.setFollowUser({str(bool(comp.get('follow_user', False))).lower()});"
                )
                lines.append(
                    f'{indent}{jv}.setTileConfig('
                    f'"{_escape_java_literal(comp.get("tile_url", "https://tile.openstreetmap.org/{z}/{x}/{y}.png"))}", '
                    f'"{_escape_java_literal(comp.get("attribution", "© OpenStreetMap contributors"))}", '
                    f'"{_escape_java_literal(comp.get("tile_user_agent", "ApkPy Android/1.2 (+https://repo-apkpy.pages.dev/)"))}", '
                    f'{int(comp.get("cache_days", 7))}, '
                    f'{str(bool(comp.get("disk_cache", True))).lower()});'
                )
                lines.append(f'{indent}{jv}.setMarkersJson("{markers_json}");')
                lines.append(f'{indent}{jv}.setRouteJson("{route_json}");')
                if comp.get('on_tap'):
                    lines.append(
                        f"{indent}{jv}.setOnMapTapListener((latitude, longitude) -> "
                        f"pythonCallback_{comp['on_tap']}("
                        "String.format(java.util.Locale.US, \"%.6f\", latitude), "
                        f"String.format(java.util.Locale.US, \"%.6f\", longitude)));"
                    )
                lines.append("")

            elif ctype == 'list_view':
                self.cnt['lst'] += 1
                jv = comp.get('_java_var') or f"lst{self.cnt['lst']}"
                comp['_java_var'] = jv
                comp_id = comp.get('id')
                comp_style = component_style(styles, 'list', comp_id)

                fg_hex  = _resolve_color(_get_style_fg(comp_style) or '#212121')
                item_bg = _resolve_color(_get_style_bg(comp_style)) if _get_style_bg(comp_style) else None

                if self.scroll:
                    # Scroll mode: use LinearLayout container + TextViews (no ListView)
                    method_name = f"update{jv[0].upper()}{jv[1:]}List"
                    _is_rich = bool(comp.get('rich'))
                    lines.append(f"{indent}{jv}_items = new java.util.ArrayList<>();")
                    _seeded = _seed_items_from_state(lines, indent, jv, comp)
                    for item in ([] if _seeded else comp.get('items', [])):
                        lines.append(
                            f'{indent}{jv}_items.add({_list_row_java_literal(item, _is_rich)});')
                    lines.append(f"{indent}{method_name}();")
                else:
                    _is_rich = bool(comp.get('rich'))
                    lines.append(f"{indent}final ListView {jv} = findViewById(R.id.{jv});")
                    lines.append(f"{indent}{jv}_items = new java.util.ArrayList<>();")
                    _seeded = _seed_items_from_state(lines, indent, jv, comp)
                    for item in ([] if _seeded else comp.get('items', [])):
                        lines.append(
                            f'{indent}{jv}_items.add({_list_row_java_literal(item, _is_rich)});')
                    if _is_rich:
                        bg_line = f'\n{indent}        view.setBackgroundColor(android.graphics.Color.parseColor("{item_bg}"));' if item_bg else ''
                        lines.append(f"{indent}{jv}Adapter = new android.widget.ArrayAdapter<String>(this, R.layout.apkpy_list_row, R.id.apkpy_row_title, {jv}_items) {{")
                        lines.append(f"{indent}    @Override")
                        lines.append(f"{indent}    public android.view.View getView(int pos, android.view.View cv, android.view.ViewGroup parent) {{")
                        lines.append(f"{indent}        android.view.View view = super.getView(pos, cv, parent);")
                        lines.append(f"{indent}        android.widget.TextView _t = view.findViewById(R.id.apkpy_row_title);")
                        lines.append(f"{indent}        android.widget.TextView _s = view.findViewById(R.id.apkpy_row_sub);")
                        lines.append(f"{indent}        android.widget.ImageView _im = view.findViewById(R.id.apkpy_row_img);")
                        lines.append(f'{indent}        String _ti = "", _su = "", _url = "";')
                        lines.append(f"{indent}        try {{")
                        lines.append(f"{indent}            org.json.JSONObject _ro = new org.json.JSONObject({jv}_items.get(pos));")
                        lines.append(f'{indent}            _ti = _ro.optString("title", "");')
                        lines.append(f'{indent}            _su = _ro.optString("subtitle", "");')
                        lines.append(f'{indent}            _url = _ro.optString("image", "");')
                        lines.append(f"{indent}        }} catch (Exception _e) {{ _ti = {jv}_items.get(pos); }}")
                        lines.append(f"{indent}        _t.setText(_ti);")
                        lines.append(f'{indent}        _t.setTextColor(android.graphics.Color.parseColor("{fg_hex}"));')
                        lines.append(f"{indent}        _s.setText(_su);")
                        lines.append(f"{indent}        _s.setVisibility(_su.isEmpty() ? android.view.View.GONE : android.view.View.VISIBLE);{bg_line}")
                        lines.append(f"{indent}        _im.setTag(_url);")
                        lines.append(f"{indent}        _im.setImageBitmap(null);")
                        # A row with no image has no thumbnail, which is what
                        # the Previewer draws. The reserved slot showed up as
                        # an empty blue square on the phone and nowhere else.
                        lines.append(
                            f"{indent}        _im.setVisibility(_url.isEmpty()"
                            " ? android.view.View.GONE"
                            " : android.view.View.VISIBLE);"
                        )
                        lines.append(f'{indent}        if (!_url.isEmpty()) _loadListThumb(_im, _url);')
                        lines.append(f"{indent}        return view;")
                        lines.append(f"{indent}    }}")
                        lines.append(f"{indent}}};")
                    else:
                        # A row may be a record (JSON) or text; the row shows
                        # "title — subtitle" either way, as it always did.
                        _colour_lines = ''
                        if fg_hex != '#212121' or item_bg:
                            _colour_lines = f'\n{indent}        tv.setTextColor(android.graphics.Color.parseColor("{fg_hex}"));'
                            if item_bg:
                                _colour_lines += f'\n{indent}        tv.setBackgroundColor(android.graphics.Color.parseColor("{item_bg}"));'
                        lines.append(f"{indent}{jv}Adapter = new android.widget.ArrayAdapter<String>(this, android.R.layout.simple_list_item_1, {jv}_items) {{")
                        lines.append(f"{indent}    @Override")
                        lines.append(f"{indent}    public android.view.View getView(int pos, android.view.View cv, android.view.ViewGroup parent) {{")
                        lines.append(f"{indent}        android.view.View view = super.getView(pos, cv, parent);")
                        lines.append(f"{indent}        android.widget.TextView tv = (android.widget.TextView) view.findViewById(android.R.id.text1);")
                        lines.append(f"{indent}        tv.setText(_apkpyRowText(getItem(pos)));{_colour_lines}")
                        lines.append(f"{indent}        return view;")
                        lines.append(f"{indent}    }}")
                        lines.append(f"{indent}}};")
                    lines.append(f"{indent}{jv}.setAdapter({jv}Adapter);")

                    on_click = comp.get('on_click')
                    if on_click:
                        lines.append(f"{indent}{jv}.setOnItemClickListener((parent, view, position, id) -> {{")
                        lines.append(f"{indent}    pythonCallback_{on_click}({jv}_items.get(position));")
                        lines.append(f"{indent}}});")
                # Pesquisa em tempo real: snapshot do dataset completo p/ filtrar.
                if comp.get('_py_var') in self._search_target_pyvars:
                    lines.append(f"{indent}{jv}_src = new java.util.ArrayList<>({jv}_items);")
                lines.append("")

            elif ctype == 'virtual_collection':
                self.cnt['vc'] += 1
                jv = comp.get('_java_var') or f"vc{self.cnt['vc']}"
                comp['_java_var'] = jv
                comp_id = comp.get('id')
                comp_style = component_style(styles, 'virtual_collection', comp_id)
                theme_tokens = styles.get('__theme__', {})

                def _vc_color(style_key, fallback):
                    return _resolve_color(comp_style.get(style_key) or fallback)

                # A cor que o Markdown usa para links e marcadores de lista.
                # A mesma escolha que o Previewer faz, para que um link nao
                # seja de uma cor no telemovel e de outra no computador.
                accent_color = _vc_color(
                    'accent-color',
                    theme_tokens.get('secondary')
                    or theme_tokens.get('primary', '#6750A4'),
                )
                # Without a Theme the rows sit on the screen's own background
                # and their text is the one that reads there (theme.content_ink),
                # as the Previewer draws them. They were a dark theme's colours,
                # #18181B rows with #FAFAFA text: dark cards on a light screen.
                item_bg = _vc_color(
                    'item-background-color',
                    _get_style_bg(comp_style)
                    or theme_tokens.get('surface', '#00000000'),
                )
                if '_ink_parents' not in _vc_ink_cache:
                    _vc_ink_cache['_ink_parents'] = _ink_parent_backgrounds(self.components, styles)
                _ink = _content_ink(
                    styles, item_bg, component_style(styles, None, self.screen_id),
                    _vc_ink_cache['_ink_parents'].get(id(comp)))
                # body's colour comes in through the screen's, where
                # content_ink sees whether it reads on the rows.
                title_color = _vc_color(
                    'title-color',
                    _get_style_fg(component_style(
                        styles, 'virtual_collection', comp_id, include_body=False))
                    or _ink['text'],
                )
                subtitle_color = _vc_color('subtitle-color', _ink['muted'])
                meta_color = _vc_color(
                    'meta-color', theme_tokens.get('primary') or title_color
                )
                badge_bg = _vc_color(
                    'badge-background-color',
                    theme_tokens.get('primary', '#6750A4'),
                )
                badge_color = _vc_color(
                    'badge-color', theme_tokens.get('on_primary', '#FFFFFF')
                )
                border_color = _vc_color(
                    'item-border-color',
                    _get_style_border_color(comp_style) or _ink['border'],
                )
                # One line is the list-row default. A chat message needs more,
                # and reads as nonsense ellipsised to a single line.
                auto_height = bool(comp.get('auto_height'))
                # Com altura automatica o default deixa de ser uma linha: uma
                # linha que pode crescer, com o texto cortado a uma linha, e'
                # o pior dos dois mundos. O CSS continua a mandar se falar.
                _lines_default = 99 if auto_height else 1
                title_lines = line_count(
                    comp_style.get('title-lines'), _lines_default)
                subtitle_lines = line_count(
                    comp_style.get('subtitle-lines'), _lines_default)
                template = comp.get('template') or {}
                is_grid = comp.get('layout') == 'grid'
                columns = max(1, int(comp.get('columns', 2) or 2))
                item_height = max(56, int(comp.get('item_height', 88) or 88))
                buffer = max(1, int(comp.get('buffer', 2) or 2))
                on_click = comp.get('on_click')

                declaration = (
                    "" if (
                        feeds_feature.is_paginated(comp)
                        or comp.get('_py_var') in self._recycler_field_pyvars
                    ) else "RecyclerView "
                )
                lines.append(
                    f"{indent}{declaration}{jv} = findViewById(R.id.{jv});"
                )
                lines.append(
                    f"{indent}{jv}_items = new java.util.ArrayList<>();"
                )
                for item in comp.get('items', []):
                    lines.append(
                        f"{indent}{jv}_items.add("
                        f"{_collection_item_java_literal(item)});"
                    )
                lines.append(
                    f"{indent}java.util.Map<String, String> {jv}_template = "
                    f"new java.util.HashMap<>();"
                )
                for slot in ('title', 'subtitle', 'markdown', 'avatar',
                             'image', 'meta', 'badge'):
                    value = _escape_java_literal(template.get(slot, ''))
                    lines.append(
                        f'{indent}{jv}_template.put("{slot}", "{value}");'
                    )
                if is_grid:
                    lines.append(
                        f"{indent}{jv}.setLayoutManager("
                        f"new GridLayoutManager(this, {columns}));"
                    )
                else:
                    lines.append(
                        f"{indent}{jv}.setLayoutManager("
                        f"new LinearLayoutManager(this));"
                    )
                lines.append(
                    f"{indent}{jv}.setHasFixedSize("
                    f"{'false' if auto_height else 'true'});"
                )
                lines.append(
                    f"{indent}{jv}.setItemViewCacheSize({max(4, buffer * columns * 2)});"
                )
                lines.append(f"{indent}{jv}.setItemAnimator(null);")
                click_java = (
                    f"_item -> pythonCallback_{on_click}(_item)"
                    if on_click else "null"
                )
                if comp.get('row'):
                    _emit_row_adapter_setup(
                        lines, indent, jv, comp, styles, self.screen_id, click_java,
                        self.json_item_callbacks or set())
                    lines.append(f"{indent}{jv}.setAdapter({jv}Adapter);")
                    feeds_feature.emit_setup(lines, indent, comp)
                    gestures_feature.emit_setup(lines, indent, comp,
                                                styles.get('__theme__', {}) or {})
                    if comp.get('_py_var') in self._search_target_pyvars:
                        lines.append(f"{indent}{jv}_src = new java.util.ArrayList<>({jv}_items);")
                    lines.append("")
                    continue
                lines.append(
                    f"{indent}{jv}Adapter = new ApkpyVirtualAdapter("
                    f"{jv}_items, {jv}_template, {str(is_grid).lower()}, "
                    f"{item_height}, {str(auto_height).lower()}, "
                    f'android.graphics.Color.parseColor("{item_bg}"), '
                    f'android.graphics.Color.parseColor("{title_color}"), '
                    f'android.graphics.Color.parseColor("{subtitle_color}"), '
                    f'android.graphics.Color.parseColor("{meta_color}"), '
                    f'android.graphics.Color.parseColor("{badge_bg}"), '
                    f'android.graphics.Color.parseColor("{badge_color}"), '
                    f'android.graphics.Color.parseColor("{border_color}"), '
                    f'android.graphics.Color.parseColor("{accent_color}"), '
                    f"{title_lines}, {subtitle_lines}, "
                    + (f"{str(wants_code_copy(comp_style)).lower()}, "
                       if self.has_vc_markdown else "")
                    + f"{click_java});"
                )
                if comp.get('variants'):
                    lines.append(
                        f"{indent}java.util.Map<String, java.util.Map<String,"
                        f" String>> {jv}_shapes = new java.util.HashMap<>();"
                    )
                    lines.append(
                        f"{indent}java.util.Map<String, int[]> {jv}_shades = "
                        f"new java.util.HashMap<>();"
                    )
                    for _name, _shape in comp['variants'].items():
                        _safe = re.sub(r'[^A-Za-z0-9_]', '_', str(_name))
                        lines.append(
                            f"{indent}java.util.Map<String, String> "
                            f"{jv}_shape_{_safe} = new java.util.HashMap<>();"
                        )
                        for _slot in ('title', 'subtitle', 'markdown',
                                      'avatar', 'image', 'meta', 'badge'):
                            lines.append(
                                f'{indent}{jv}_shape_{_safe}.put("{_slot}", '
                                f'"{_escape_java_literal(_shape.get(_slot, ""))}");'
                            )
                        lines.append(
                            f'{indent}{jv}_shapes.put('
                            f'"{_escape_java_literal(str(_name))}", '
                            f'{jv}_shape_{_safe});'
                        )
                        # ``thread:user { ... }`` refines one kind of row. The
                        # cascade is the same one every other selector uses.
                        _vstyle = component_style(
                            styles, 'virtual_collection', comp.get('id'),
                            row_variant=_name,
                        )
                        _v_bg = _resolve_color(
                            _vstyle.get('item-background-color') or item_bg)
                        _v_title = _resolve_color(
                            _vstyle.get('title-color')
                            or _get_style_fg(_vstyle) or title_color)
                        _v_sub = _resolve_color(
                            _vstyle.get('subtitle-color') or subtitle_color)
                        _v_meta_xml = ''
                        if _vc_bubble_layout(comp, styles)[0]:
                            # A read message's ticks are another colour than a
                            # sent one's: the meta colour is per variant too.
                            _v_meta = _resolve_color(
                                _vstyle.get('meta-color') or meta_color)
                            _v_meta_xml = (f', android.graphics.Color.parseColor('
                                           f'"{_v_meta}")')
                        lines.append(
                            f'{indent}{jv}_shades.put('
                            f'"{_escape_java_literal(str(_name))}", new int[]{{'
                            f'android.graphics.Color.parseColor("{_v_bg}"), '
                            f'android.graphics.Color.parseColor("{_v_title}"), '
                            f'android.graphics.Color.parseColor("{_v_sub}"){_v_meta_xml}}});'
                        )
                    lines.append(
                        f'{indent}{jv}Adapter.setVariants('
                        f'"{_escape_java_literal(str(comp["variant"]))}", '
                        f'{jv}_shapes, {jv}_shades);'
                    )
                _bubble_table, _item_shape = _vc_bubble_layout(comp, styles)
                if _bubble_table:
                    lines.append(f"{indent}java.util.Map<String, float[]> {jv}_bubbles = new java.util.HashMap<>();")
                    for _name, (_align, _width, _percent) in _bubble_table.items():
                        lines.append(
                            f'{indent}{jv}_bubbles.put("{_escape_java_literal(str(_name))}", '
                            f'new float[]{{{_align}f, {_width:g}f, {_percent}f}});')
                    lines.append(f"{indent}{jv}Adapter.setBubbles({jv}_bubbles);")
                if _item_shape:
                    lines.append(f"{indent}{jv}Adapter.setItemShape({_item_shape[0]}, {_item_shape[1]});")
                if badge_at_end(component_style(styles, 'virtual_collection', comp.get('id'))):
                    lines.append(f"{indent}{jv}Adapter.setBadgeEnd(true);")
                lines.append(f"{indent}{jv}.setAdapter({jv}Adapter);")
                feeds_feature.emit_setup(lines, indent, comp)
                gestures_feature.emit_setup(lines, indent, comp,
                                            styles.get('__theme__', {}) or {})
                if comp.get('_py_var') in self._search_target_pyvars:
                    lines.append(
                        f"{indent}{jv}_src = "
                        f"new java.util.ArrayList<>({jv}_items);"
                    )
                lines.append("")

            elif ctype == 'carousel':
                self.cnt['car'] += 1
                jv = f"car{self.cnt['car']}"
                comp['_java_var'] = jv
                on_click = comp.get('on_click')
                _card_title, _card_sub = (_color_java(c) for c in card_text_colors(
                    component_style(styles, 'carousel', comp.get('id'), include_body=False)))
                lines.append(f"{indent}android.widget.LinearLayout {jv}_row = findViewById(R.id.{jv}_row);")
                lines.append(f"{indent}final float {jv}_den = getResources().getDisplayMetrics().density;")
                for item in comp.get('items', []):
                    if not isinstance(item, dict):
                        item = {'title': str(item), 'subtitle': '', 'image': '', 'src': ''}
                    _t = '"' + _escape_java_literal(item.get('title', '')) + '"'
                    _s = '"' + _escape_java_literal(item.get('subtitle', '')) + '"'
                    _img = '"' + _escape_java_literal(item.get('image', '')) + '"'
                    _json = _rich_item_java_literal(item.get('title', ''), item.get('subtitle', ''), item.get('image', ''), item.get('src', ''))
                    lines.append(f"{indent}{{")
                    lines.append(f"{indent}    android.widget.LinearLayout _card = new android.widget.LinearLayout(this);")
                    lines.append(f"{indent}    _card.setOrientation(android.widget.LinearLayout.VERTICAL);")
                    lines.append(f"{indent}    android.widget.LinearLayout.LayoutParams _clp = new android.widget.LinearLayout.LayoutParams((int)(150 * {jv}_den), android.widget.LinearLayout.LayoutParams.WRAP_CONTENT);")
                    lines.append(f"{indent}    _clp.setMargins((int)(8 * {jv}_den), (int)(4 * {jv}_den), (int)(8 * {jv}_den), (int)(4 * {jv}_den));")
                    lines.append(f"{indent}    _card.setLayoutParams(_clp);")
                    lines.append(f"{indent}    android.widget.ImageView _iv = new android.widget.ImageView(this);")
                    lines.append(f"{indent}    _iv.setLayoutParams(new android.widget.LinearLayout.LayoutParams((int)(150 * {jv}_den), (int)(150 * {jv}_den)));")
                    lines.append(f"{indent}    _iv.setScaleType(android.widget.ImageView.ScaleType.CENTER_CROP);")
                    lines.append(f"{indent}    _card.addView(_iv);")
                    lines.append(f"{indent}    android.widget.TextView _t = new android.widget.TextView(this);")
                    lines.append(f"{indent}    _t.setText({_t}); _t.setTextColor({_card_title}); _t.setTextSize(14); _t.setMaxLines(1); _t.setEllipsize(android.text.TextUtils.TruncateAt.END); _t.setPadding(0, (int)(6 * {jv}_den), 0, 0);")
                    lines.append(f"{indent}    _card.addView(_t);")
                    lines.append(f"{indent}    android.widget.TextView _sub = new android.widget.TextView(this);")
                    lines.append(f"{indent}    _sub.setText({_s}); _sub.setTextColor({_card_sub}); _sub.setTextSize(12); _sub.setMaxLines(1); _sub.setEllipsize(android.text.TextUtils.TruncateAt.END);")
                    lines.append(f"{indent}    _card.addView(_sub);")
                    lines.append(f"{indent}    {jv}_row.addView(_card);")
                    lines.append(f"{indent}    _loadCarThumb(_iv, {_img});")
                    if on_click:
                        lines.append(f"{indent}    _card.setOnClickListener(_cv -> pythonCallback_{on_click}({_json}));")
                    lines.append(f"{indent}}}")
                lines.append("")

            elif ctype == 'grid':
                self.cnt['grid'] += 1
                jv = f"grid{self.cnt['grid']}"
                comp['_java_var'] = jv
                on_click = comp.get('on_click')
                _card_title, _card_sub = (_color_java(c) for c in card_text_colors(
                    component_style(styles, 'grid', comp.get('id'), include_body=False)))
                lines.append(f"{indent}android.widget.GridLayout {jv} = findViewById(R.id.{jv});")
                lines.append(f"{indent}final float {jv}_den = getResources().getDisplayMetrics().density;")
                for item in comp.get('items', []):
                    if not isinstance(item, dict):
                        item = {'title': str(item), 'subtitle': '', 'image': '', 'src': ''}
                    _t = '"' + _escape_java_literal(item.get('title', '')) + '"'
                    _s = '"' + _escape_java_literal(item.get('subtitle', '')) + '"'
                    _img = '"' + _escape_java_literal(item.get('image', '')) + '"'
                    _json = _rich_item_java_literal(item.get('title', ''), item.get('subtitle', ''), item.get('image', ''), item.get('src', ''))
                    lines.append(f"{indent}{{")
                    lines.append(f"{indent}    android.widget.LinearLayout _card = new android.widget.LinearLayout(this);")
                    lines.append(f"{indent}    _card.setOrientation(android.widget.LinearLayout.VERTICAL);")
                    # GridLayout.spec(UNDEFINED, 1f) → auto-coloca + estica para preencher a coluna.
                    lines.append(f"{indent}    android.widget.GridLayout.LayoutParams _glp = new android.widget.GridLayout.LayoutParams();")
                    lines.append(f"{indent}    _glp.width = 0;")
                    lines.append(f"{indent}    _glp.columnSpec = android.widget.GridLayout.spec(android.widget.GridLayout.UNDEFINED, 1f);")
                    lines.append(f"{indent}    _glp.setMargins((int)(6 * {jv}_den), (int)(6 * {jv}_den), (int)(6 * {jv}_den), (int)(6 * {jv}_den));")
                    lines.append(f"{indent}    _card.setLayoutParams(_glp);")
                    lines.append(f"{indent}    android.widget.ImageView _iv = new android.widget.ImageView(this);")
                    lines.append(f"{indent}    _iv.setLayoutParams(new android.widget.LinearLayout.LayoutParams(android.widget.LinearLayout.LayoutParams.MATCH_PARENT, (int)(110 * {jv}_den)));")
                    lines.append(f"{indent}    _iv.setScaleType(android.widget.ImageView.ScaleType.CENTER_CROP);")
                    lines.append(f"{indent}    _card.addView(_iv);")
                    lines.append(f"{indent}    android.widget.TextView _t = new android.widget.TextView(this);")
                    lines.append(f"{indent}    _t.setText({_t}); _t.setTextColor({_card_title}); _t.setTextSize(14); _t.setMaxLines(1); _t.setEllipsize(android.text.TextUtils.TruncateAt.END); _t.setPadding(0, (int)(6 * {jv}_den), 0, 0);")
                    lines.append(f"{indent}    _card.addView(_t);")
                    lines.append(f"{indent}    android.widget.TextView _sub = new android.widget.TextView(this);")
                    lines.append(f"{indent}    _sub.setText({_s}); _sub.setTextColor({_card_sub}); _sub.setTextSize(12); _sub.setMaxLines(1); _sub.setEllipsize(android.text.TextUtils.TruncateAt.END);")
                    lines.append(f"{indent}    _card.addView(_sub);")
                    lines.append(f"{indent}    {jv}.addView(_card);")
                    lines.append(f"{indent}    _loadCarThumb(_iv, {_img});")
                    if on_click:
                        lines.append(f"{indent}    _card.setOnClickListener(_cv -> pythonCallback_{on_click}({_json}));")
                    lines.append(f"{indent}}}")
                lines.append("")
