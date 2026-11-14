"""CSS as Android has it: colours, sizes, padding, corners, shadows, type."""
import ast
import os
import re

from ...layout_engine import box_shorthand, corner_radii
from ... import theme as _theme
from ...theme import (
    component_style, letter_spacing_em, line_spacing_extra, normalize_text_align,
    normalize_text_transform,
)
from ...diagnostics import Diagnostic, report_diagnostic
from .. import unsupported

from .state import _APP_THEME, _TRANSPILE_FONTS


def _parse_radius(style_dict):
    """The largest corner, for code that draws one radius (see _parse_radii)."""
    return int(max(corner_radii(style_dict.get('border-radius', '0'))))


def _parse_radii(style_dict):
    """One radius, or four when the corners differ (top-left, top-right,
    bottom-right, bottom-left): what _corners_xml writes."""
    corners = tuple(int(round(c)) for c in corner_radii(style_dict.get('border-radius', '0')))
    return corners[0] if len(set(corners)) == 1 else corners


def _corners_xml(radius):
    if isinstance(radius, tuple):
        tl, tr, br, bl = radius
        return (f'<corners android:topLeftRadius="{tl}dp" android:topRightRadius="{tr}dp" '
                f'android:bottomRightRadius="{br}dp" android:bottomLeftRadius="{bl}dp" />')
    return f'<corners android:radius="{radius}dp" />'

def _parse_border_width(style_dict):
    raw = style_dict.get('border-width', '0')
    cleaned = re.sub(r'[^0-9.]', '', str(raw))
    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return 0

def _get_style_bg(style_dict):
    return style_dict.get('background-color') or style_dict.get('backgroundcolor')

def _get_style_fg(style_dict):
    return style_dict.get('color')

def _get_style_pressed_color(style_dict):
    val = style_dict.get('pressed-color')
    return _resolve_color(val) if val else None

def _get_style_border_color(style_dict):
    val = style_dict.get('border-color')
    if val and val.lower() == 'none':
        return 'none'
    elif val:
        return _resolve_color(val)
    return None

def _get_style_focus_border_color(style_dict):
    val = style_dict.get('focus-border-color') or style_dict.get('focus-color')
    if val:
        return _resolve_color(val)
    return None

_PADDING_LONGHAND = ('padding-top', 'padding-right',
                     'padding-bottom', 'padding-left')


def _css_box_sides(raw, fallback):
    """CSS shorthand to ``(top, right, bottom, left)``.

    One, two, three and four values, the way CSS reads them. The Previewer has
    always read all four; this side stopped at two and silently dropped the
    rest, so ``padding: 0 20 24 20`` lost its bottom on the phone only.
    """
    values = [int(float(part))
              for part in re.findall(r'(\d+(?:\.\d+)?)', str(raw or ''))]
    if len(values) == 1:
        return (values[0],) * 4
    if len(values) == 2:
        return (values[0], values[1], values[0], values[1])
    if len(values) == 3:
        return (values[0], values[1], values[2], values[1])
    if len(values) >= 4:
        return tuple(values[:4])
    return fallback


def _apply_box_longhand(sides, style_dict, names):
    """Overlay ``padding-top`` and friends on a shorthand already resolved."""
    out = list(sides)
    for index, name in enumerate(names):
        found = re.findall(r'(\d+(?:\.\d+)?)', str(style_dict.get(name) or ''))
        if found:
            out[index] = int(float(found[0]))
    return tuple(out)


def _parse_padding(style_dict):
    return _apply_box_longhand(
        _css_box_sides(style_dict.get('padding'), (5, 10, 5, 10)),
        style_dict, _PADDING_LONGHAND,
    )


def _declared_padding(style_dict):
    """The padding a stylesheet wrote, as ``(top, right, bottom, left)``.

    None when it wrote none. A side it left out is 0, as in CSS -- not the
    5/10 a shape drawable falls back on.
    """
    if not any(str(style_dict.get(name) or '').strip()
               for name in ('padding',) + _PADDING_LONGHAND):
        return None
    return _apply_box_longhand(
        _css_box_sides(style_dict.get('padding'), (0, 0, 0, 0)),
        style_dict, _PADDING_LONGHAND,
    )

INT_MAX_JAVA = 2147483647
INT_MIN_JAVA = -2147483648
LONG_MAX_JAVA = 9223372036854775807
LONG_MIN_JAVA = -9223372036854775808


def _java_int_literal(value, node=None):
    """A Python int as a Java literal, with the L a long needs.

    Python counts as high as memory allows and Java's int stops at about two
    billion, so a timestamp in milliseconds written straight into the source
    came out as a plain int and javac refused the whole build -- a raw
    compiler error about generated code nobody wrote by hand.
    """
    if INT_MIN_JAVA <= value <= INT_MAX_JAVA:
        return str(value)
    if LONG_MIN_JAVA <= value <= LONG_MAX_JAVA:
        return '%dL' % value
    unsupported.raise_unsupported(
        node if node is not None else ast.Constant(value=value),
        cause=('Java counts up to %d and this number is bigger, so there is '
               'no literal ApkPy could write for it.' % LONG_MAX_JAVA),
        received=str(value),
        suggestions=['Keep it as text and convert only the part you need.',
                     'Store it with storage.set() instead of writing it in '
                     'the source.'],
    )


def _px_to_dp(val):
    cleaned = re.sub(r'[^0-9.]', '', str(val))
    try:
        return f"{int(float(cleaned))}dp"
    except (ValueError, TypeError):
        return "0dp"


def _parse_image_dim_android(val):
    """Converte uma dimensão CSS de imagem para valor Android XML.
    '200px' → '200dp', '100%' | 'match_parent' → 'match_parent', None → 'wrap_content'.
    """
    if not val:
        return 'wrap_content'
    val_s = str(val).strip().lower()
    if val_s in ('match_parent', '100%', 'fill'):
        return 'match_parent'
    cleaned = re.sub(r'[^0-9.]', '', val_s)
    try:
        return f"{int(float(cleaned))}dp"
    except (ValueError, TypeError):
        return 'wrap_content'


def _parse_aspect_ratio(value):
    """Return a positive width/height ratio or ``None`` for invalid input."""
    if value in (None, ''):
        return None
    try:
        if isinstance(value, (int, float)):
            ratio = float(value)
        else:
            text = str(value).strip().replace('/', ':')
            if ':' in text:
                left, right = text.split(':', 1)
                ratio = float(left.strip()) / float(right.strip())
            else:
                ratio = float(text)
        return ratio if ratio > 0 else None
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _image_blur_amount(comp, style_dict):
    """Combine the image() blur argument and CSS filter without duplicating work."""
    try:
        api_blur = max(0.0, float(comp.get('blur', 0) or 0))
    except (TypeError, ValueError):
        api_blur = 0.0
    match = re.search(r'blur\(\s*([0-9.]+)(?:px|dp)?\s*\)',
                      str(style_dict.get('filter', '')), re.IGNORECASE)
    css_blur = float(match.group(1)) if match else 0.0
    return max(api_blur, css_blur)


def _image_component_style(styles, comp, viewport=None):
    """Resolve CSS plus the explicit point-9 image arguments in one place."""
    resolved = component_style(
        styles, 'image', comp.get('id'), viewport=viewport,
    )
    if comp.get('avatar'):
        size = max(16, int(comp.get('size') or 48))
        resolved.update({
            'width': f'{size}px', 'height': f'{size}px',
            'border-radius': f'{size // 2}px', 'object-fit': 'cover',
            'aspect-ratio': '1 / 1', 'flex-shrink': '0',
        })
    elif comp.get('aspect_ratio'):
        resolved['aspect-ratio'] = str(comp['aspect_ratio'])
    return resolved


def _android_drawable_name(path, fallback='image'):
    base = os.path.splitext(os.path.basename(str(path or fallback)))[0]
    safe = re.sub(r'[^a-z0-9_]', '_', base.lower()) or fallback
    if not safe[0].isalpha():
        safe = 'img_' + safe
    return safe


def _parse_object_fit_android(style_dict):
    """Mapeia object-fit CSS para android:scaleType."""
    fit = style_dict.get('object-fit', 'fill').strip().lower()
    mapping = {
        'cover':   'centerCrop',
        'contain': 'fitCenter',
        'fill':    'fitXY',
        'none':    'center',
    }
    return mapping.get(fit, 'fitXY')


def _parse_opacity_android(style_dict):
    """Lê opacity CSS para android:alpha. Devolve string ou None se não definido."""
    raw = style_dict.get('opacity', '')
    if not raw:
        return None
    try:
        v = max(0.0, min(1.0, float(str(raw).strip())))
        return str(round(v, 2))
    except (ValueError, TypeError):
        return None


def _parse_box_shadow_android(style_dict):
    """Extrai o valor de elevação (box-shadow) em dp para android:elevation."""
    raw = style_dict.get('box-shadow', '')
    if not raw:
        return None
    # Apanha o primeiro valor numérico (ex: '0 4px 8px #000' → '4dp')
    m = re.search(r'(\d+)px', raw)
    if m:
        return f"{m.group(1)}dp"
    return None


def _shadow_colour_xml(style_dict, indent):
    """``box-shadow: 0 8px 24px rgba(124, 92, 255, 0.5)``: the colour of the
    shadow Android casts (API 28+; older phones keep it black). Android
    scales it by the theme's shadow alpha, so the colour goes in opaque."""
    from ..css_colors import shadow_colour
    colour = shadow_colour(style_dict.get('box-shadow'))
    if not colour or colour[3:].upper() == '000000':
        return ''
    opaque = '#' + colour[3:]
    return (f'\n{indent}    android:outlineSpotShadowColor="{opaque}"'
            f'\n{indent}    android:outlineAmbientShadowColor="{opaque}"')


def _casts_a_shadow(xml):
    """True when something in this layout asks Android to draw a shadow."""
    if 'android:elevation="' in xml:
        return True
    # Every card carries app:cardElevation, most of them "0dp". Only a real
    # depth counts, so an app that never asked keeps the XML it always had.
    return bool(re.search(r'app:cardElevation="(?!0dp")', xml))


# An absolute child at bottom: 0 is drawn down under the navigation bar
# (ApkpyLayout.onLayout), which the root's padding would otherwise clip.
_FLUSH_BOTTOM = re.compile(r'apkpy-child;[^"]*position=absolute[^"]*;bottom=0(?:px|dp)?[;"]')


def _open_shadow_clipping(xml):
    """Stop the screen root from clipping a child's shadow away.

    A ViewGroup clips its children to its padding box, so a card with room to
    breathe around it had its shadow cut off exactly where the shadow starts.
    That is most of why ``box-shadow`` looked like it did nothing.
    """
    if not (_casts_a_shadow(xml) or _FLUSH_BOTTOM.search(xml)):
        return xml
    opening = re.search(r'<(?!\?)[A-Za-z][\w.]*\b', xml)
    if opening is None:
        return xml
    close = xml.find('>', opening.end())
    if close < 0:
        return xml
    tag = xml[opening.start():close]
    wanted = ''
    for attribute in ('clipToPadding', 'clipChildren'):
        if attribute not in tag:
            wanted += ' android:%s="false"' % attribute
    if not wanted:
        return xml
    # A root element always has children, but never assume it: inserting after
    # the slash of a self-closing tag would produce invalid XML.
    cut = close - 1 if xml[:close].rstrip().endswith('/') else close
    while cut < close and xml[cut] != '/':
        cut += 1
    return xml[:cut] + wanted + xml[cut:]


def _has_filter_grayscale(style_dict):
    """Verifica se há filter: grayscale() definido."""
    raw = style_dict.get('filter', '')
    return 'grayscale' in raw


def _get_flex_orientation(style_dict):
    """
    Determina a orientação do LinearLayout a partir das propriedades CSS flexbox.

    Regras:
      - Se 'display' == 'flex' e 'flex-direction' == 'column' → 'vertical'
      - Se 'display' == 'flex' e 'flex-direction' == 'row' (ou omitido) → 'horizontal'
      - Se 'display' != 'flex', usa 'flex-direction' directamente (legado):
          'row' → 'horizontal', qualquer outro valor → 'vertical'

    Retorna: 'horizontal' | 'vertical'
    """
    display = style_dict.get('display', '').strip().lower()
    flex_dir = style_dict.get('flex-direction', '').strip().lower()

    if display == 'flex':
        # CSS default para flex-direction é 'row'
        return 'horizontal' if flex_dir != 'column' else 'vertical'
    elif display == 'grid':
        columns = str(style_dict.get('grid-template-columns', '1fr')).strip()
        return 'horizontal' if len(columns.split()) > 1 else 'vertical'
    else:
        # Legado: apenas flex-direction sem display:flex
        return 'horizontal' if flex_dir == 'row' else 'vertical'


def _responsive_android_dim(value, viewport, axis='width', percent_base=None):
    """Resolve px/dp, %, vw and vh into an Android dimension string."""
    if value is None or str(value).strip() == '':
        return None
    width, height = viewport
    text = str(value).strip().lower()
    if text in ('match_parent', 'fill'):
        return 'match_parent'
    match = re.match(r'^(-?[\d.]+)\s*(px|dp|%|vw|vh)?$', text)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2) or 'px'
    if unit == '%':
        if number >= 100:
            return 'match_parent'
        base = percent_base or (width if axis == 'width' else height)
        number = base * number / 100.0
    elif unit == 'vw':
        number = width * number / 100.0
    elif unit == 'vh':
        number = height * number / 100.0
    return f"{max(0, int(round(number)))}dp"


# ── Typography helpers ────────────────────────────────────────────────────────

def _parse_font_size(style_dict):
    """Extrai font-size em px e devolve o valor numérico (int). 0 = não definido."""
    raw = style_dict.get('font-size', '')
    cleaned = re.sub(r'[^0-9.]', '', str(raw))
    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return 0


_FONT_FAMILY_MAP_ANDROID = {
    'sans-serif': 'sans-serif',
    'serif':      'serif',
    'monospace':  'monospace',
}


def _android_font_resource(style_dict):
    """@font/<family> when the app registered this family, else None."""
    registry = _TRANSPILE_FONTS[0]
    if registry is None:
        return None
    entry = registry.lookup(style_dict.get('font-family', ''))
    return '@font/' + entry['resource'] if entry else None


def _parse_font_family_android(style_dict):
    """Devolve o valor android:fontFamily a injetar no XML, ou None se não definido."""
    raw = style_dict.get('font-family', '').strip().lower()
    if not raw:
        return None
    # Aceita tanto "sans-serif" como variantes (ex: 'sans-serif, arial')
    for key in _FONT_FAMILY_MAP_ANDROID:
        if key in raw:
            return _FONT_FAMILY_MAP_ANDROID[key]
    return raw  # passa o valor literal (ex: 'Roboto')


def _parse_font_weight(style_dict):
    """Devolve o valor android:textStyle ('bold', 'italic', 'bold|italic', ou None)."""
    weight = style_dict.get('font-weight', '').strip().lower()
    style  = style_dict.get('font-style', '').strip().lower()
    bold   = weight in ('bold', '700', '800', '900')
    italic = style == 'italic'
    if bold and italic:
        return 'bold|italic'
    if bold:
        return 'bold'
    if italic:
        return 'italic'
    return None


def _body_text_size():
    """The ramp's body step, or 16 when the app declared no Theme.

    16 is what this default has always been, and it is what the ramp resolves
    to at the default base -- so nothing an existing app generates moves. What
    changes is that ``Theme(font_size=)`` now reaches it, and that the
    Previewer reads the same figure instead of its own 14.
    """
    theme = _APP_THEME[0]
    return _theme.default_text_size(theme.tokens if theme is not None else None)


def _parse_typography_xml(style_dict, default_size=None, indent='        '):
    """
    Devolve uma string com os atributos android de tipografia prontos a injetar no XML.
    Exemplo: '\n        android:textSize="18sp"\n        android:fontFamily="sans-serif"'

    ``default_size=None`` means the ramp's body step; ``0`` means no size
    attribute at all, which is what a component whose parent sets the size
    wants.
    """
    if default_size is None:
        default_size = _body_text_size()
    attrs = []
    size = _parse_font_size(style_dict)
    if size > 0:
        attrs.append(f'android:textSize="{size}sp"')
    elif default_size:
        attrs.append(f'android:textSize="{default_size}sp"')

    resource = _android_font_resource(style_dict)
    if resource:
        # app:, not android:. AppCompat resolves @font/ from API 16 up;
        # the framework attribute only learned to at 26, and this
        # project generates minSdk 24.
        attrs.append(f'app:fontFamily="{resource}"')
    else:
        family = _parse_font_family_android(style_dict)
        if family:
            attrs.append(f'android:fontFamily="{family}"')

    weight = _parse_font_weight(style_dict)
    if weight:
        attrs.append(f'android:textStyle="{weight}"')

    # Tracking and leading are measured against the size the text actually
    # renders at, so an em value means the same thing here and in the Previewer.
    effective_size = size or default_size or 14
    raw_spacing = str(style_dict.get('letter-spacing', '')).strip().lower()
    if raw_spacing and raw_spacing != 'normal':
        # Written whenever it is declared, zero included: a MaterialButton
        # tracks its label at ~0.089em on its own, so `letter-spacing: 0` has
        # to say so out loud or the phone keeps the Material spacing while the
        # Previewer drops it -- and a settings row reads as a shouty button.
        attrs.append(
            'android:letterSpacing="%s"'
            % round(letter_spacing_em(raw_spacing, effective_size), 4)
        )

    leading = round(
        line_spacing_extra(style_dict.get('line-height'), effective_size),
    )
    if leading:
        # sp, not dp: the leading has to grow with the font size the reader
        # picked in Android's own settings, exactly like the text does.
        attrs.append(f'android:lineSpacingExtra="{int(leading)}sp"')

    color = _get_style_fg(style_dict)
    if color:
        attrs.append(f'android:textColor="{_color_xml(color)}"')

    if not attrs:
        return ''
    joiner = chr(10) + indent
    return joiner + joiner.join(attrs)


class _FoldedStyle(dict):
    """A style whose ``margin`` shorthand was written out as longhands.
    ``explicit_left`` says whether ``margin-left`` itself was in the sheet:
    only that one has ever moved a view to the start (layout_gravity), and a
    shorthand doing it now would move buttons in apps already written."""
    explicit_left = True


def _fold_margin_shorthand(style_dict):
    """``margin: 4px 14px 0px 14px`` as its four longhands, in the order the
    cascade wrote them, so a later ``margin-top`` still wins and an earlier one
    loses. Everything downstream reads longhands: the stacking baseline added
    6dp to a ``margin-top`` the shorthand never set, and the XML then carried
    layout_marginTop twice -- which AAPT refuses, so the app did not build.
    The label indent missed the shorthand's left side the same way."""
    if not style_dict or 'margin' not in style_dict:
        return style_dict
    folded = _FoldedStyle()
    folded.explicit_left = 'margin-left' in style_dict
    for key, value in style_dict.items():
        if key == 'margin':
            sides = box_shorthand(value)
            if sides:
                for name, side in zip(('top', 'right', 'bottom', 'left'), sides):
                    folded['margin-' + name] = f"{side:g}px"
            continue
        folded[key] = value
    return folded


def _parse_margins_to_xml(style_dict):
    attrs = []
    if not style_dict:
        return ""
        
    def _margin_dp(val):
        # A negative margin counts as 0, as in the Previewer: _px_to_dp drops
        # the sign, so -8px was written as 8dp -- the opposite of the CSS.
        return "0dp" if str(val).strip().startswith('-') else _px_to_dp(val)

    # `margin: 24px 16px` is four sides written short, and Android has no
    # shorthand attribute for it: each side goes out on its own.
    sides = box_shorthand(style_dict.get('margin'))
    if sides:
        top, right, bottom, left = (max(0, side) for side in sides)
        if top == right == bottom == left:
            attrs.append(f'android:layout_margin="{_margin_dp(top)}"')
        else:
            attrs.append(f'android:layout_marginTop="{_margin_dp(top)}"')
            attrs.append(f'android:layout_marginRight="{_margin_dp(right)}"')
            attrs.append(f'android:layout_marginBottom="{_margin_dp(bottom)}"')
            attrs.append(f'android:layout_marginLeft="{_margin_dp(left)}"')
    _sides = [style_dict.get('margin-' + side) for side in ('top', 'right', 'bottom', 'left')]
    if not sides and all(v is not None for v in _sides) and len({str(v) for v in _sides}) == 1:
        # A shorthand written out by _fold_margin_shorthand, four sides equal.
        attrs.append(f'android:layout_margin="{_margin_dp(_sides[0])}"')
        return "\n        " + "\n        ".join(attrs)
    if 'margin-top' in style_dict:
        attrs.append(f'android:layout_marginTop="{_margin_dp(style_dict["margin-top"])}"')
    if 'margin-bottom' in style_dict:
        attrs.append(f'android:layout_marginBottom="{_margin_dp(style_dict["margin-bottom"])}"')
    if 'margin-left' in style_dict:
        attrs.append(f'android:layout_marginLeft="{_margin_dp(style_dict["margin-left"])}"')
    if 'margin-right' in style_dict:
        attrs.append(f'android:layout_marginRight="{_margin_dp(style_dict["margin-right"])}"')
        
    if not attrs:
        return ""
        
    return "\n        " + "\n        ".join(attrs)


def _content_ink(styles, own_bg, screen_style, parent_bg=None):
    """theme.content_ink (the text of a label, markdown, a tree, a list's rows
    that name none of their own), with this compiler's readings of the styles.
    *own_bg* is what the component paints under its text; *parent_bg* the
    fill of the card or container it sits in (_ink_parent_backgrounds)."""
    def colour(value):
        return _resolve_color(value) if value else None
    return _theme.content_ink(
        (styles or {}).get('__theme__', {}),
        own_bg=colour(own_bg),
        screen_fg=colour(_get_style_fg(screen_style)),
        screen_bg=colour(_get_style_bg(screen_style)),
        parent_bg=colour(parent_bg),
    )


def _ink_parent_backgrounds(components, styles, viewport=None):
    """{id(comp): the fill of the card or container it sits in, or None}.

    The layout and the Activity's Java are written apart (the Java first),
    and both need it: a label in a dark card on a light screen reads on the
    card. Cards paint their colour or white, as the layout writes them; a
    container paints its own colour, never body's, or nothing.
    """
    found = {}

    def walk(comps, under):
        for comp in comps or []:
            found[id(comp)] = under
            ctype, comp_id = comp.get('comp_type'), comp.get('id')
            here = under
            if ctype == 'card':
                here = _get_style_bg(component_style(
                    styles, 'card', comp_id, variant=comp.get('variant'),
                    viewport=viewport)) or '#FFFFFF'
            elif ctype == 'container':
                here = _get_style_bg(component_style(
                    styles, 'container', comp_id, include_body=False,
                    viewport=viewport)) or under
            walk(comp.get('children'), here)

    walk(components, None)
    return found


def _app_bar_colors(styles, bar_style):
    """(background, text) of the top bar: theme.app_bar_colors, with this
    compiler's readings of the bar's style."""
    own_bg, own_fg = _get_style_bg(bar_style), _get_style_fg(bar_style)
    background, text = _theme.app_bar_colors(
        (styles or {}).get('__theme__', {}),
        own_bg=_resolve_color(own_bg) if own_bg else None,
        own_fg=own_fg or None,
    )
    return _resolve_color(background), _resolve_color(text)


def _xml_escape(text):
    """Escapa caracteres especiais de XML para uso em atributos android:text / android:hint."""
    return (str(text)
            .replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


_INVALID_COLORS_REPORTED = set()
_INVALID_TRANSFORMS_REPORTED = set()
_INVALID_ALIGNS_REPORTED = set()


# CSS on the left, android:gravity on the right.  start/end rather than
# left/right so a right-to-left locale mirrors the layout for free.
_ANDROID_GRAVITY = {
    'left': 'start',
    'center': 'center',
    'right': 'end',
}


def _resolve_text_align(raw, default=None):
    """text-align for a label or button, or the default with a warning."""
    resolved = normalize_text_align(raw, default)
    if resolved is None and str(raw or '').strip():
        key = str(raw).strip().lower()
        if key not in _INVALID_ALIGNS_REPORTED:
            _INVALID_ALIGNS_REPORTED.add(key)
            report_diagnostic(Diagnostic(
                code='U2022',
                title='ApkPy cannot do this text-align',
                message='text-align: %s is not something both sides can do.'
                        % raw,
                cause=(
                    'Alignment here is android:gravity on one side and Tk\'s '
                    'anchor on the other, and both stop at three values. '
                    '"justify" would need android:justificationMode, which '
                    'arrived at API 26 while ApkPy targets 24 -- so it would '
                    'be an effect you only ever see on a newer phone.'
                ),
                expected='text-align: left, center, or right',
                received=repr(raw),
                suggestions=(
                    'Use text-align: left for a settings row, center for a '
                    'button, right for a trailing value.',
                ),
                docs='https://repo-apkpy.pages.dev/themes-styling/',
            ))
        return default
    return resolved


def _resolve_text_transform(raw):
    """text-transform for a button label, or the default with a warning."""
    resolved = normalize_text_transform(raw)
    if resolved is None:
        key = str(raw).strip().lower()
        if key not in _INVALID_TRANSFORMS_REPORTED:
            _INVALID_TRANSFORMS_REPORTED.add(key)
            report_diagnostic(Diagnostic(
                code='U2021',
                title='ApkPy cannot do this text-transform',
                message='text-transform: %s is not something both sides can do.'
                        % raw,
                cause=(
                    'Casing is a display attribute here: Android has '
                    'android:textAllCaps and nothing else. "capitalize" and '
                    '"lowercase" would mean rewriting the label at build '
                    'time, which would then not apply to text you set while '
                    'the app runs -- a difference that only shows up on the '
                    'phone.'
                ),
                expected='text-transform: uppercase, or text-transform: none',
                received=repr(raw),
                suggestions=(
                    'Write the label with the casing you want and use '
                    'text-transform: none.',
                ),
                docs='https://repo-apkpy.pages.dev/reference/ui-layouts/',
            ))
        return 'uppercase'
    return resolved


# The tokens written into res/values/apkpy_theme.xml, and therefore the ones
# a layout can reference and night mode can answer differently. Anything else
# -- a mixed shade, a colour written by hand -- stays a literal.
_THEMED_COLOR_TOKENS = (
    'primary', 'secondary', 'background', 'surface', 'text', 'text_secondary',
    'on_primary', 'error', 'success', 'border', 'nav_indicator',
    'surface_low', 'surface_high', 'border_subtle',
)


def _color_resource(value):
    """`@color/apkpy_x` when a colour came from a token, else None.

    This is the whole hinge of runtime appearance. A layout that writes
    `#141218` can never be anything else; one that writes
    `@color/apkpy_background` is answered by `values/` or `values-night/`
    depending on the mode in force, and switching is then a matter of telling
    Android which table to read.

    Only tokens get a reference. `#C96442` written by hand stays exactly that,
    in both modes, which is what writing it by hand asked for.
    """
    token = _theme.token_of(value)
    if token and token in _THEMED_COLOR_TOKENS:
        return '@color/apkpy_%s' % token
    return None


def _color_xml(value, fallback=None):
    """A colour as a layout or drawable attribute writes it."""
    reference = _color_resource(value)
    if reference is not None:
        return reference
    return _resolve_color(value if value else fallback)


def _color_java(value, context='this'):
    """A colour as a Java expression, following night mode when it can."""
    token = _theme.token_of(value)
    if token and token in _THEMED_COLOR_TOKENS:
        return (
            'androidx.core.content.ContextCompat.getColor(%s, R.color.apkpy_%s)'
            % (context, token)
        )
    return 'android.graphics.Color.parseColor("%s")' % _resolve_color(value)


def _resolve_color(c):
    if not c: return "#d9d9d9"
    # A tagged colour keeps its tag through normalisation: the tag is lost on
    # the first _resolve_color() otherwise, and every call site downstream
    # reads a plain hex with no idea a token put it there.
    _token = _theme.token_of(c)
    if _token is not None:
        return _theme.TokenValue(_resolve_color(str(c)), _token)
    c_lower = str(c).strip().lower()
    mapping = {
        'blue': '#0000FF', 'red': '#FF0000', 'green': '#00FF00',
        'yellow': '#FFFF00', 'black': '#000000', 'white': '#FFFFFF',
        'grey': '#808080', 'gray': '#808080', 'darkblue': '#00008B',
        'transparent': '#00000000',
    }
    if c_lower in mapping:
        return mapping[c_lower]

    # CSS shorthand has to be expanded: android.graphics.Color.parseColor only
    # accepts #RRGGBB and #AARRGGBB, so "#111" reached the device and threw
    # IllegalArgumentException in onCreate -- an app that rendered perfectly in
    # the Previewer, which expands the shorthand, and died on the phone.
    if c_lower.startswith('#'):
        digits = c_lower[1:]
        # Four digits are the shorthand of the eight-digit form, which this
        # project reads as #AARRGGBB throughout ("transparent" is #00000000).
        # Treating them as CSS #RGBA instead made #0000 opaque black.
        if len(digits) in (3, 4) and all(d in '0123456789abcdef' for d in digits):
            return '#' + ''.join(d * 2 for d in digits).upper()
        if len(digits) in (6, 8) and all(d in '0123456789abcdef' for d in digits):
            return c
    # Android resource references resolve at build time, not here. `?attr/x`
    # is one too -- it reads a value off the theme in force -- and wrapping
    # the background attributes in _color_xml started sending those through
    # here, which reported a perfectly good ripple as an unreadable colour.
    if not c_lower.startswith(('@', '?')):
        if c_lower not in _INVALID_COLORS_REPORTED:
                _INVALID_COLORS_REPORTED.add(c_lower)
                report_diagnostic(Diagnostic(
                    code='U2020',
                    title='Android cannot read this colour',
                    message='%r is not a colour Android understands.' % c,
                    cause=(
                        'A stylesheet colour can be a hex (#RGB, #RRGGBB, or with '
                        'the alpha last as in CSS: #RGBA, #RRGGBBAA), rgb(), '
                        'rgba(), hsl(), hsla(), a CSS colour name or var(--token). '
                        'Anything else would reach android.graphics.Color.parseColor, '
                        'which throws while the screen is being created, so the '
                        'app would close the moment it opens.'
                    ),
                    expected='a colour such as #6750A4, #6750A480 or rgba(103, 80, 164, 0.5)',
                    received=repr(c),
                    docs='https://repo-apkpy.pages.dev/reference/ui-layouts/',
                ))
    return c


# CSS on the left, the half of android:gravity it controls on the right.
_MAIN_AXIS_GRAVITY = {
    'center': 'center_vertical', 'flex-start': 'top', 'start': 'top',
    'flex-end': 'bottom', 'end': 'bottom',
}
_CROSS_AXIS_GRAVITY = {
    'center': 'center_horizontal', 'flex-start': 'start', 'start': 'start',
    'flex-end': 'end', 'end': 'end', 'stretch': 'center_horizontal',
}


def _column_gravity(style):
    """Where a stacked column puts its children.

    ``center_horizontal`` has always been the default and stays it, so nothing
    already written moves. ``justify-content`` places them along the column and
    ``align-items`` across it -- the two CSS words for the two halves
    ``android:gravity`` already had.
    """
    main = _MAIN_AXIS_GRAVITY.get(
        str(style.get('justify-content', '')).strip().lower())
    cross = _CROSS_AXIS_GRAVITY.get(
        str(style.get('align-items', '')).strip().lower(), 'center_horizontal')
    return '|'.join([part for part in (cross, main) if part])
