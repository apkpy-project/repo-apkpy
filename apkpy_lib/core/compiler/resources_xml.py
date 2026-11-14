"""The files under res/ that are not layouts: drawables, fonts, icons, menus."""
import os
import re

from ... import icons as icon_catalogue
from ... import fonts as _fonts
from ... import motion
from ...diagnostics import Diagnostic, report_diagnostic

from .state import _ASSET_BASE_DIR
from .style import (
    _color_xml, _corners_xml, _get_style_bg, _get_style_fg, _parse_typography_xml, _resolve_color,
    _xml_escape,
)


def _generate_font_family_xml(entry):
    """The <font-family> that maps weights and styles onto files.

    Every row is written twice, once in each namespace: the framework reads
    android: from API 26, and AppCompat reads app: all the way down to the
    minSdk this project generates.
    """
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<font-family xmlns:android="http://schemas.android.com/apk/res/android"',
        '    xmlns:app="http://schemas.android.com/apk/res-auto">',
    ]
    for slot in _fonts.SLOT_ORDER:
        if slot not in entry['files']:
            continue
        weight, italic = _fonts.SLOTS[slot]
        style = 'italic' if italic else 'normal'
        ref = '@font/' + _fonts.slot_resource_name(entry['name'], slot)
        lines.append(
            f'    <font android:fontStyle="{style}"'
            f' android:fontWeight="{weight}" android:font="{ref}"'
        )
        lines.append(
            f'        app:fontStyle="{style}"'
            f' app:fontWeight="{weight}" app:font="{ref}" />'
        )
    lines.append('</font-family>')
    return '\n'.join(lines)


def _validate_font_registry(registry, base_dir):
    """Drop slots that cannot ship, and families left with nothing.

    Runs before any layout is generated, so a family that will not exist in
    the APK is never named by one. Referencing a resource that was never
    written is an AAPT link failure, which is a much worse way to find out
    than a warning at build time.
    """
    for key, entry in list(registry.all().items()):
        usable = {}
        for slot, path in entry['files'].items():
            resolved = path if os.path.isabs(path) else os.path.join(
                base_dir or '.', path)
            suffix = os.path.splitext(str(path))[1].lower()
            if suffix not in _fonts.FONT_SUFFIXES:
                report_diagnostic(Diagnostic(
                    code='U2025',
                    title='This is not a font file',
                    message='font("%s", %s="%s") does not point at a font.'
                            % (entry['name'], slot, path),
                    cause=(
                        'Android accepts TrueType and OpenType in res/font, '
                        'and nothing else. A .woff or .woff2 is a web format '
                        'and the build tools reject it.'
                    ),
                    expected='a .ttf or .otf file',
                    received=repr(str(path)),
                    suggestions=(
                        'Convert the file to .ttf, which every font tool '
                        'exports.',
                    ),
                    docs='https://repo-apkpy.pages.dev/themes-styling/',
                ))
                continue
            if not os.path.exists(resolved):
                report_diagnostic(Diagnostic(
                    code='U2026',
                    title='A font file is missing',
                    message='font("%s", %s="%s"): no file there.'
                            % (entry['name'], slot, path),
                    cause=(
                        'Font paths resolve against the folder your app lives '
                        'in, the same as an image or an icon does.'
                    ),
                    expected='a path relative to %s' % (base_dir or '.'),
                    received=resolved,
                    suggestions=(
                        'Check the spelling, and that the file is inside the '
                        'project folder rather than beside it.',
                    ),
                    docs='https://repo-apkpy.pages.dev/themes-styling/',
                ))
                continue
            usable[slot] = resolved
        if usable:
            # A family with a broken bold still ships and falls back, rather
            # than the whole app losing its typeface over one path.
            entry['files'] = usable
        else:
            registry.drop(key)


def _emit_font_resources(registry, output_files):
    """Copy every surviving font file into res/font and write its family."""
    if not registry:
        return
    for entry in registry.all().values():
        for slot, resolved in entry['files'].items():
            name = _fonts.slot_resource_name(entry['name'], slot)
            suffix = os.path.splitext(resolved)[1].lower()
            output_files['res/font/%s%s' % (name, suffix)] = (
                'COPY_FILE', resolved,
            )
        output_files['res/font/%s.xml' % entry['resource']] = (
            _generate_font_family_xml(entry)
        )

    # A MaterialToolbar title is not a view we can put an attribute on from
    # the layout, so the typeface reaches it through a text appearance.
    # Written in both spellings for the same reason the family XML is.
    lines = ['<?xml version="1.0" encoding="utf-8"?>', '<resources>']
    for entry in registry.all().values():
        resource = entry['resource']
        lines += [
            '    <style name="ApkpyFont_%s"' % resource,
            '           parent="TextAppearance.Widget.AppCompat.Toolbar.Title">',
            '        <item name="android:fontFamily">@font/%s</item>' % resource,
            '        <item name="fontFamily">@font/%s</item>' % resource,
            '    </style>',
        ]
    lines.append('</resources>')
    output_files['res/values/apkpy_fonts.xml'] = chr(10).join(lines)


def _generate_divider_xml(divider, horizontal=False):
    """The hairline a LinearLayout draws between its children.

    Both dimensions are written because a vertical layout reads the drawable's
    intrinsic height and a horizontal one reads its width.  ``divider-inset``
    becomes an ``<inset>`` wrapper: Android has no attribute for it, so the
    drawable is the only place the offset can live.
    """
    color = _resolve_color(divider['color'])
    thickness = divider['width']
    ns = ' xmlns:android="http://schemas.android.com/apk/res/android"'
    header = '<?xml version="1.0" encoding="utf-8"?>\n'

    def _shape(pad, namespace):
        return (
            f'{pad}<shape{namespace} android:shape="rectangle">\n'
            f'{pad}    <size android:width="{thickness}dp"'
            f' android:height="{thickness}dp" />\n'
            f'{pad}    <solid android:color="{_color_xml(color)}" />\n'
            f'{pad}</shape>'
        )

    if not divider['inset']:
        return header + _shape('', ns)
    side = 'insetTop' if horizontal else 'insetLeft'
    return (
        f'{header}<inset{ns}\n'
        f'    android:{side}="{divider["inset"]}dp">\n'
        f'{_shape("    ", "")}\n'
        '</inset>'
    )


def _generate_drawable_xml(bg_color, radius_px, border_color=None, border_width=0, pressed_color=None, focus_color=None, padding=None):
    stroke_w = border_width if border_width > 0 else 1

    # Só desenha borda quando o utilizador define `border-color` — paridade com o
    # preview (que NÃO mete borda por defeito). Antes punha um stroke cinzento
    # #808080 em todos os botões → pareciam "cinzentos quadradões" no Android.
    stroke_xml = ""
    if border_color and border_color != 'none' and border_width > 0:
        stroke_xml = f'        <stroke android:width="{stroke_w}dp" android:color="{_color_xml(border_color)}" />'

    if padding is None:
        padding = (5, 10, 5, 10)
    padding_xml = f'        <padding android:left="{padding[3]}dp" android:top="{padding[0]}dp" android:right="{padding[1]}dp" android:bottom="{padding[2]}dp" />'

    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<selector xmlns:android="http://schemas.android.com/apk/res/android">' if (pressed_color or focus_color) else '<shape xmlns:android="http://schemas.android.com/apk/res/android">',
    ]

    if pressed_color:
        lines += [
            '    <item android:state_pressed="true">',
            '        <shape>',
            f'            <solid android:color="{_color_xml(pressed_color)}" />',
            f'            {_corners_xml(radius_px)}'
        ]
        if stroke_xml: lines.append(stroke_xml)
        lines.append(padding_xml)
        lines += [
            '        </shape>',
            '    </item>'
        ]

    if focus_color:
        # Focus thickens the border; a field asked to have none must not grow
        # one, or a borderless composer input sprouts a box on the phone that
        # the Previewer never draws.
        lines += [
            '    <item android:state_focused="true">',
            '        <shape>',
            f'            <solid android:color="{_color_xml(bg_color)}" />',
            f'            {_corners_xml(radius_px)}',
        ]
        if border_width > 0:
            lines.append(
                f'        <stroke android:width="{stroke_w}dp" '
                f'android:color="{_color_xml(focus_color)}" />'
            )
        lines += [
            padding_xml,
            '        </shape>',
            '    </item>'
        ]

    if pressed_color or focus_color:
        lines += [
            '    <item>',
            '        <shape>',
            f'            <solid android:color="{_color_xml(bg_color)}" />',
            f'            {_corners_xml(radius_px)}'
        ]
        if stroke_xml: lines.append(stroke_xml)
        lines.append(padding_xml)
        lines += [
            '        </shape>',
            '    </item>',
            '</selector>'
        ]
    else:
        lines += [
            f'    <solid android:color="{_color_xml(bg_color)}" />',
            f'    {_corners_xml(radius_px)}'
        ]
        if stroke_xml: lines.append(stroke_xml[4:])
        lines.append(padding_xml[4:])
        lines.append('</shape>')

    return "\n".join(lines)


# Icon geometry now lives in apkpy_lib/icons.py, which both this compiler and
# the Previewer read.  The two used to keep private tables that shared only 29
# of their 48 names, so the same ``icon=`` produced different drawings -- or a
# plain circle -- depending on where the app was running.

_DOCS_ICONS = 'https://repo-apkpy.pages.dev/reference/icons/'

_UNKNOWN_ICONS_REPORTED = set()


def _material_icon_path(icon_name):
    """Path data for a catalogue name, falling back to ``circle``.

    Kept as a thin shim because the regression suite imports it by name.
    """
    return icon_catalogue.path_for(icon_name)


def _icon_path_data(icon_name, style='filled'):
    """Path data for a catalogue name *or* a user-supplied ``.svg``.

    User SVG is flattened to polylines here so the phone draws exactly the
    points the Previewer drew: transforms and arcs are resolved once, in
    Python, instead of twice by two different renderers.
    """
    raw = str(icon_name or '').strip()
    if icon_catalogue.is_file_reference(raw):
        # ValueError carries a message the diagnostics catalogue recognises.
        return icon_catalogue.load_svg(raw, base_dir=_ASSET_BASE_DIR[0])
    resolved = icon_catalogue.resolve(raw, style)
    if resolved is None:
        if raw and raw.lower() not in _UNKNOWN_ICONS_REPORTED:
            _UNKNOWN_ICONS_REPORTED.add(raw.lower())
            hint = icon_catalogue.suggest(raw)
            report_diagnostic(Diagnostic(
                code='U2015',
                title='This icon name is not in the ApkPy catalogue',
                message='icon=%r was drawn as a plain circle.' % raw,
                cause=(
                    'ApkPy draws the %d Material Icons by their Material name '
                    '(share, chat_bubble_outline, favorite_border, ...). A name '
                    'it does not know cannot be drawn, so both the Previewer and '
                    'the phone fall back to a circle -- which looks like a design '
                    'choice rather than a typo, and is why it can go unnoticed.'
                    % len(icon_catalogue.all_names())
                ),
                expected=(
                    "a Material Icons name such as 'search', 'share' or "
                    "'chat_bubble_outline', or a path to your own .svg file"
                ),
                received=repr(raw),
                suggestions=(
                    (['Did you mean icon="%s"?' % hint] if hint else [])
                    + ['Pass your own artwork instead: icon="assets/%s.svg"'
                       % re.sub(r'[^a-z0-9_]+', '_', raw.lower()).strip('_')]
                ),
                docs=_DOCS_ICONS,
            ))
        return icon_catalogue.path_for(raw, style)
    return resolved


def _generate_bottom_nav_vector(icon_name, style='filled'):
    path = _icon_path_data(icon_name, style)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
        '    android:width="24dp"\n'
        '    android:height="24dp"\n'
        '    android:viewportWidth="24"\n'
        '    android:viewportHeight="24">\n'
        f'    <path android:fillColor="#FF000000" android:pathData="{path}"/>\n'
        '</vector>'
    )


def _generate_button_icon_vector(icon_name, color):
    path = _icon_path_data(icon_name)
    fill = _resolve_color(color or '#212121')
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
        '    android:width="20dp"\n'
        '    android:height="20dp"\n'
        '    android:viewportWidth="24"\n'
        '    android:viewportHeight="24">\n'
        f'    <path android:fillColor="{_color_xml(fill)}" android:pathData="{path}"/>\n'
        '</vector>'
    )


def _generate_state_icon_vector(icon_name, color):
    path = _icon_path_data(icon_name)
    fill = _resolve_color(color or '#6750A4')
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
        '    android:width="64dp"\n'
        '    android:height="64dp"\n'
        '    android:viewportWidth="24"\n'
        '    android:viewportHeight="24">\n'
        f'    <path android:fillColor="{_color_xml(fill)}" android:pathData="{path}"/>\n'
        '</vector>'
    )

def _generate_bottom_nav_menu_xml(bottom_nav_info):
    lines = ['<?xml version="1.0" encoding="utf-8"?>', '<menu xmlns:android="http://schemas.android.com/apk/res/android">']
    for sid, label, icon in zip(bottom_nav_info['screen_ids'], bottom_nav_info['labels'], bottom_nav_info['icons']):
        item_id = f'nav_{sid}'
        drawable = f'ic_nav_{sid}'
        lines.append(f'    <item android:id="@+id/{item_id}" android:icon="@drawable/ic_nav_sel_{sid}" android:title="{label}" />')
    lines.append('</menu>')
    return '\n'.join(lines)


def _safe_android_id(value, fallback):
    value = re.sub(r'[^a-z0-9_]', '_', str(value or fallback).lower())
    if not value or not value[0].isalpha():
        value = 'apkpy_' + value
    return value


def _generate_app_bar_menu_xml(screen_id, app_bar_info):
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<menu xmlns:android="http://schemas.android.com/apk/res/android"',
        '    xmlns:app="http://schemas.android.com/apk/res-auto">',
    ]
    for index, item in enumerate(app_bar_info.get('actions') or [], 1):
        item_id = _safe_android_id(item.get('id'), f'appbar_{screen_id}_{index}')
        item['_android_id'] = item_id
        drawable = f'ic_appbar_{_safe_android_id(screen_id, "screen")}_{index}'
        item['_drawable'] = drawable
        lines.append(
            f'    <item android:id="@+id/{item_id}" '
            f'android:icon="@drawable/{drawable}" '
            f'android:title="{_xml_escape(item.get("label") or item.get("icon") or "Action")}" '
            'app:showAsAction="always" />'
        )
    lines.append('</menu>')
    return '\n'.join(lines)


def _generate_drawer_item_color_xml(active, resting):
    """The panel item tint: the open screen takes the accent."""
    return chr(10).join([
        '<?xml version="1.0" encoding="utf-8"?>',
        '<selector xmlns:android="http://schemas.android.com/apk/res/android">',
        f'    <item android:state_checked="true" android:color="{_color_xml(active)}" />',
        f'    <item android:color="{_color_xml(resting)}" />',
        '</selector>',
    ])


def _drawer_item_id(screen_id):
    return 'drawer_' + _safe_android_id(screen_id, 'item')


def _generate_drawer_menu_xml(drawer_info):
    """The panel's items.

    ``checkableBehavior="single"`` is what gives the open screen its highlight;
    NavigationView draws it from the theme without the app asking.
    """
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<menu xmlns:android="http://schemas.android.com/apk/res/android">',
        '    <group android:checkableBehavior="single">',
    ]
    for sid, label in zip(drawer_info['screen_ids'], drawer_info['labels']):
        lines.append(
            f'        <item android:id="@+id/{_drawer_item_id(sid)}"'
            f' android:icon="@drawable/ic_drawer_{_safe_android_id(sid, "item")}"'
            f' android:title="{_xml_escape(str(label))}" />'
        )
    lines += ['    </group>', '</menu>']
    return '\n'.join(lines)


def _generate_drawer_header_xml(drawer_info, style, tokens):
    """The block above the items -- an account name, usually."""
    text = _resolve_color(_get_style_fg(style) or tokens.get('text', '#111111'))
    muted = _resolve_color(
        style.get('subtitle-color') or tokens.get('text_secondary', '#6B7280'))
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"',
        '    xmlns:app="http://schemas.android.com/apk/res-auto"',
        '    android:layout_width="match_parent"',
        '    android:layout_height="wrap_content"',
        '    android:orientation="vertical"',
        '    android:paddingLeft="24dp" android:paddingRight="16dp"',
        '    android:paddingTop="24dp" android:paddingBottom="16dp">',
    ]
    if drawer_info.get('header'):
        lines += [
            '    <TextView',
            '        android:layout_width="wrap_content"',
            '        android:layout_height="wrap_content"',
            f'        android:text="{_xml_escape(str(drawer_info["header"]))}"'
            + _parse_typography_xml(
                {**style, 'color': _get_style_fg(style) or text,
                 'font-weight': 'bold',
                 'font-size': style.get('font-size', '20px')},
                20, '        ') + ' />',
        ]
    if drawer_info.get('subtitle'):
        lines += [
            '    <TextView',
            '        android:layout_width="wrap_content"',
            '        android:layout_height="wrap_content"',
            '        android:layout_marginTop="4dp"',
            f'        android:text="{_xml_escape(str(drawer_info["subtitle"]))}"'
            + _parse_typography_xml(
                {**style, 'color': muted, 'font-weight': 'normal',
                 'font-size': '13px'},
                13, '        ') + ' />',
        ]
    # The Previewer draws a hairline under the header. Without it the panel
    # reads as one block and the account name runs into the destinations.
    divider = style.get('divider-color') or tokens.get('border', '')
    if divider:
        lines += [
            '    <View',
            '        android:layout_width="match_parent"',
            '        android:layout_height="1dp"',
            '        android:layout_marginTop="16dp"',
            '        android:background="%s" />' % _resolve_color(divider),
        ]
    lines.append('</LinearLayout>')
    return '\n'.join(lines)


def _generate_drawer_item_background_xml(pill_color, radius_dp):
    """The lit pill behind the active destination.

    A plain Android selector rather than the Material 3 active-indicator
    attribute: the generated apps run a Material 2 theme, and the pill has to
    look the same there.
    """
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<selector xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <item android:state_checked="true">\n'
        '        <shape android:shape="rectangle">\n'
        '            <solid android:color="%s" />\n'
        '            <corners android:radius="%ddp" />\n'
        '        </shape>\n'
        '    </item>\n'
        '    <item android:drawable="@android:color/transparent" />\n'
        '</selector>\n' % (pill_color, radius_dp)
    )


def _generate_drawer_item_style_xml(size_sp):
    """``item-size`` reaches a NavigationView through a text appearance."""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<resources>\n'
        '    <style name="ApkpyDrawerItem"'
        ' parent="TextAppearance.AppCompat.Body1">\n'
        '        <item name="android:textSize">%dsp</item>\n'
        '    </style>\n'
        '</resources>\n' % size_sp
    )


def _wrap_layout_in_drawer(layout_xml, drawer_info, style, tokens):
    """Put the finished screen inside a DrawerLayout with the panel beside it.

    A DrawerLayout takes its content child first and its panels after, so the
    screen goes in untouched and the NavigationView is appended. The inner root
    redeclares the namespaces, which XML allows and which keeps this a wrap
    rather than a rewrite of the layout generator.
    """
    body = layout_xml.split('\n')
    if body and body[0].startswith('<?xml'):
        body = body[1:]
    surface = _resolve_color(_get_style_bg(style) or tokens.get('surface', '#FFFFFF'))
    header = (
        '\n        app:headerLayout="@layout/apkpy_drawer_header"'
        if drawer_info.get('header') or drawer_info.get('subtitle') else ''
    )
    return '\n'.join([
        '<?xml version="1.0" encoding="utf-8"?>',
        '<androidx.drawerlayout.widget.DrawerLayout',
        '    xmlns:android="http://schemas.android.com/apk/res/android"',
        '    xmlns:app="http://schemas.android.com/apk/res-auto"',
        '    android:id="@+id/apkpy_drawer"',
        '    android:layout_width="match_parent"',
        '    android:layout_height="match_parent"',
        '    android:fitsSystemWindows="true">',
        '',
        *['    ' + line if line.strip() else line for line in body],
        '',
        '    <com.google.android.material.navigation.NavigationView',
        '        android:id="@+id/apkpy_drawer_view"',
        '        android:layout_width="wrap_content"',
        '        android:layout_height="match_parent"',
        '        android:layout_gravity="start"',
        '        android:fitsSystemWindows="true"',
        f'        android:background="{_color_xml(surface)}"',
        '        app:itemIconTint="@color/apkpy_drawer_item_color"',
        '        app:itemTextColor="@color/apkpy_drawer_item_color"',
        # The Previewer has always lit a pill behind the active item and sized
        # the item text from ``item-size``. Neither reached the phone, so a
        # styled drawer arrived looking like the default one.
        '        app:itemBackground="@drawable/apkpy_drawer_item_bg"',
        f'        app:itemTextAppearance="@style/ApkpyDrawerItem"{header}',
        '        app:menu="@menu/apkpy_drawer_menu" />',
        '</androidx.drawerlayout.widget.DrawerLayout>',
    ])


def _generate_anim_xml(frames_dict):
    """
    Gera o XML de animação (res/anim/*.xml) a partir do dicionário de frames (from/to).
    Usa deltas percentuais para translate (independente de densidade de ecrã).
    """
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        # The interpolator is named explicitly so the phone draws the same
        # curve as motion.ease(); without it Android defaults to
        # accelerate_decelerate while the Previewer eased differently.
        '<set xmlns:android="http://schemas.android.com/apk/res/android"'
        ' android:fillAfter="true"'
        f' android:interpolator="{motion.android_interpolator()}"'
        ' android:shareInterpolator="true">'
    ]

    from_dict = frames_dict.get('from', frames_dict.get('0%', {}))
    to_dict   = frames_dict.get('to',   frames_dict.get('100%', {}))

    # ── Alpha ────────────────────────────────────────────────────────────────
    if 'opacity' in from_dict or 'opacity' in to_dict:
        f_alpha = from_dict.get('opacity', '1.0')
        t_alpha = to_dict.get('opacity', '1.0')
        lines.append(
            f'    <alpha android:fromAlpha="{f_alpha}" android:toAlpha="{t_alpha}"'
            f' android:fillAfter="true" />'
        )

    # ── Translate Y (margin-top keyframes → percentagem relativa à view) ────
    if 'margin-top' in from_dict or 'margin-top' in to_dict:
        try:
            f_y = float(re.sub(r'[^0-9.-]', '', from_dict.get('margin-top', '0')))
            t_y = float(re.sub(r'[^0-9.-]', '', to_dict.get('margin-top', '0')))
            # Delta: quanto a view se desloca do estado inicial ao final.
            # Ex: from=-40px, to=0px → desloca +40px → fromYDelta="-40%", toYDelta="0%"
            delta = f_y - t_y
            from_pct = f"{int(delta)}%"
            to_pct   = "0%"
        except (ValueError, TypeError):
            from_pct, to_pct = "0%", "0%"
        lines.append(
            f'    <translate android:fromYDelta="{from_pct}" android:toYDelta="{to_pct}"'
            f' android:fillAfter="true" />'
        )

    # ── Translate X (margin-left keyframes → percentagem relativa à view) ───
    if 'margin-left' in from_dict or 'margin-left' in to_dict:
        try:
            f_x = float(re.sub(r'[^0-9.-]', '', from_dict.get('margin-left', '0')))
            t_x = float(re.sub(r'[^0-9.-]', '', to_dict.get('margin-left', '0')))
            delta_x = f_x - t_x
            from_pct_x = f"{int(delta_x)}%"
            to_pct_x   = "0%"
        except (ValueError, TypeError):
            from_pct_x, to_pct_x = "0%", "0%"
        lines.append(
            f'    <translate android:fromXDelta="{from_pct_x}" android:toXDelta="{to_pct_x}"'
            f' android:fillAfter="true" />'
        )

    # ── Scale ────────────────────────────────────────────────────────────────
    if 'scale' in from_dict or 'scale' in to_dict:
        f_s = from_dict.get('scale', '1.0')
        t_s = to_dict.get('scale', '1.0')
        lines.append(
            f'    <scale android:fromXScale="{f_s}" android:toXScale="{t_s}"'
            f' android:fromYScale="{f_s}" android:toYScale="{t_s}"'
            f' android:pivotX="50%" android:pivotY="50%" android:fillAfter="true" />'
        )

    lines.append('</set>')
    return "\n".join(lines)
