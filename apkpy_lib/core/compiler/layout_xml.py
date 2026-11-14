"""A screen's layout file."""
import os
import re

from ..features import gradient_drawable as gradient_feature
from ..gradients import gradient_of as _gradient_of
from ..gradients import layers_of as _gradient_layers_of
from ..features import pager as pager_feature
from ..features import choice as choice_feature
from ..features import field as field_feature
from ..features import web_page as web_page_feature
from ..features import draw_pad as draw_pad_feature
from ..features import keyboard as keyboard_feature
from ... import draw_pad_rules as _draw_pad_rules
from ..features import sheet as sheet_feature
from ..features import rich_content as rich_content_feature
from ..features import feeds as feeds_feature
from ..style_parser import wants_code_copy
from ...layout_engine import encode_child_tag, encode_container_tag, is_advanced_container
from ... import motion
from ...theme import nav_look as _nav_look
from ...theme import NAV_ACTIVE_LABEL_BOLD, NAV_BAR_DP, NAV_ITEM_PAD_DP, NAV_LABEL_GAP_DP
from ...theme import mini_player_colors, collection_bubbles, component_style, _length_px, _number
from ..features import accessibility as accessibility_feature

from .state import _SCREEN_GRADIENTS, _SHEET_LAYOUTS, _USES_GRADIENT
from .style import (
    _ANDROID_GRAVITY, _android_drawable_name, _android_font_resource, _app_bar_colors, _color_xml,
    _column_gravity, _content_ink, _declared_padding, _fold_margin_shorthand,
    _get_flex_orientation, _get_style_bg,
    _get_style_border_color, _get_style_fg, _image_component_style, _ink_parent_backgrounds,
    _open_shadow_clipping, _parse_aspect_ratio, _parse_border_width, _parse_box_shadow_android,
    _parse_font_size, _parse_image_dim_android, _parse_margins_to_xml, _parse_object_fit_android,
    _parse_opacity_android, _parse_padding, _parse_radii, _parse_radius, _parse_typography_xml,
    _px_to_dp, _resolve_color, _resolve_text_align, _resolve_text_transform,
    _responsive_android_dim, _shadow_colour_xml, _xml_escape,
)
from .resources_xml import _safe_android_id
from .rows import _row_components, _row_layout_name


def _describe_xml(component, indent):
    """O que um leitor de ecrã anuncia sobre isto.

    Uma descrição **vazia** é uma decisão, não um esquecimento: marca o
    elemento como decorativo e o TalkBack salta-o, em vez de anunciar o nome
    de um ficheiro. Sem descrição nenhuma não se escreve atributo — quem o diz
    é o relatório de acessibilidade, uma vez, em vez de o gerador inventar
    texto que ninguém escolheu.
    """
    described = accessibility_feature.describes(component)
    if described is None:
        return ''
    if described == '':
        return chr(10) + indent + '    android:importantForAccessibility="no"'
    return (chr(10) + indent + '    android:contentDescription="'
            + _xml_escape(described) + '"')


def _vc_bubble_layout(comp, styles):
    """The shared rule (theme.collection_bubbles) for one parsed collection."""
    return collection_bubbles(styles, comp.get('id'), list((comp.get('variants') or {})))


# align-self on a child of a vertical LinearLayout, as layout_gravity.
_ALIGN_SELF_GRAVITY = {
    'flex-end': 'end', 'end': 'end', 'right': 'end',
    'flex-start': 'start', 'start': 'start', 'left': 'start',
    'center': 'center_horizontal',
}

# The overlay is a plain column; only its absolute children are placed.
_SCREEN_OVERLAY_TAG = encode_container_tag(
    {'display': 'flex', 'flex-direction': 'column', 'align-items': 'flex-start'})


def _screen_overlay_comps(components, styles, viewport):
    """A screen's own children with ``position: absolute``."""
    found = []
    for comp in components or []:
        ctype = comp.get('comp_type')
        style = component_style(
            styles or {}, ctype, comp.get('id'),
            variant=(comp.get('variant') if ctype in ('button', 'label', 'card') else None),
            viewport=viewport,
        )
        if str(style.get('position', '')).strip().lower() == 'absolute':
            found.append(comp)
    return found


def _generate_layout_xml(screen_id, components, has_bg=False, styles=None, scroll=False,
                         bottom_nav_info=None, mini_player_info=None,
                         viewport=(411, 914), package="com.apkpy.app",
                         app_bar_info=None):
    """Gera o conteúdo de um ficheiro activity_screen_<id>.xml."""
    styles = styles or {}
    _SHEET_LAYOUTS[0] = {}
    s = component_style(styles, None, screen_id, viewport=viewport)
    _screen_ink_style = s       # what content with no colour of its own reads
    _ink_parents = _ink_parent_backgrounds(components, styles, viewport)

    gap_raw = s.get('gap', '0')
    gap_match = re.search(r'(\d+)', str(gap_raw))
    gap = int(gap_match.group(1)) if gap_match else 0

    # Determina orientação a partir das propriedades CSS Flexbox
    orientation = _get_flex_orientation(s)

    # O ecrã está em modo flex? (igual à regra do Previewer: só centra quando
    # display:flex está definido). Usado para decidir o alinhamento dos labels.
    screen_is_flex = str(s.get('display', '')).strip().lower() in ('flex', 'grid')

    # Background do ecrã
    screen_bg = _get_style_bg(s)
    screen_bg_attr = ''
    if screen_bg:
        screen_bg_attr = f'\n    android:background="{_color_xml(screen_bg)}"'
    _screen_grad = _gradient_of(s)
    _screen_spec = gradient_feature.spec(
        _screen_grad, lambda c: str(_resolve_color(c)), base=screen_bg) if _screen_grad else None
    if _screen_spec and package:
        # The page's gradient, on the root: it stays put while the content
        # scrolls, as an app's background does.
        _name = 'apkpy_screen_bg_' + re.sub(r'[^a-z0-9_]', '_', str(screen_id).lower())
        _SCREEN_GRADIENTS[0][_name] = gradient_feature.drawable_xml(package, _screen_spec)
        _screen_layers = _gradient_layers_of(s)
        if len(_screen_layers) > 1:
            # background: a, b, #colour -- every glow, one over the other.
            _layer_names = []
            for _i, _sp in enumerate(gradient_feature.layer_specs(
                    _screen_layers, lambda c: str(_resolve_color(c)), base=screen_bg)):
                _layer_names.append('%s_l%d' % (_name, _i))
                _SCREEN_GRADIENTS[0][_layer_names[-1]] = gradient_feature.drawable_xml(package, _sp)
            _SCREEN_GRADIENTS[0][_name] = gradient_feature.layer_list_xml(_layer_names)
        _USES_GRADIENT[0] = True
        screen_bg_attr = f'\n    android:background="@drawable/{_name}"'
        
    # Padding do ecrã
    pad = _parse_padding(s)
    pad_str = f'android:paddingLeft="{pad[3]}dp" android:paddingTop="{pad[0]}dp" android:paddingRight="{pad[1]}dp" android:paddingBottom="{pad[2]}dp"'

    lines = ['<?xml version="1.0" encoding="utf-8"?>']

    # Se o container for vertical, tentamos centrar, mas permitimos override por margens
    c_grav = (f'\n        android:gravity="{_column_gravity(s)}"'
              if orientation == 'vertical' else '')

    # Bottom nav e/ou mini-player: ambos exigem um RelativeLayout root com barras
    # ancoradas em baixo. O conteúdo fica `layout_above` da barra mais alta:
    # mini-player se houver (ele próprio fica acima do bottom_nav), senão bottom_nav.
    bnav = bottom_nav_info
    mp = mini_player_info
    _relative = bool(bnav) or bool(mp)
    _above_id = 'apkpy_miniplayer' if mp else ('bottom_nav' if bnav else None)
    bnav_above = f'\n        android:layout_above="@id/{_above_id}"' if _above_id else ''
    bnav_above_outer = f'\n    android:layout_above="@id/{_above_id}"' if _above_id else ''
    bnav_above_scroll = bnav_above_plain = bnav_above
    _floating_nav = bool(bnav) and _above_id == 'bottom_nav' and _nav_look(styles)['floating']
    if _floating_nav:
        # bottom_nav { margin; border-radius }: a card over the content, which
        # runs on under it. A scroll keeps room at its end so the last line
        # can come out from under the bar.
        _clear = int(round(NAV_BAR_DP + 2 * _nav_look(styles)['margin']))
        bnav_above_scroll = (f'\n        android:paddingBottom="{_clear}dp"'
                             f'\n        android:clipToPadding="false"')
        bnav_above_plain = f'\n        android:layout_marginBottom="{_clear}dp"'
    # AppCompat replaces plain <Button> at inflation time and applies its own
    # backgroundTint. Keep the namespace available on every generated layout
    # so custom ApkPy drawables can explicitly opt out of that theme tint.
    xmlns_app = '\n    xmlns:app="http://schemas.android.com/apk/res-auto"'

    if has_bg:
        scroll_open  = ['    <androidx.core.widget.NestedScrollView', '        android:layout_width="match_parent"', '        android:layout_height="match_parent"', f'        android:fillViewport="true"{bnav_above_scroll}>', ''] if scroll else []
        scroll_inner = '        ' if scroll else '    '
        above_attr   = bnav_above_plain if not scroll else ''  # for LinearLayout inside NestedScrollView, outer already has above
        lines += [
            f'<RelativeLayout xmlns:android="http://schemas.android.com/apk/res/android"{xmlns_app}',
            '    android:layout_width="match_parent"',
            '    android:fitsSystemWindows="true"',
            '    android:layout_height="match_parent">',
            f'    <ImageView',
            f'        android:layout_width="match_parent"',
            f'        android:layout_height="match_parent"',
            f'        android:src="@drawable/screen_{screen_id}_bg"',
            f'        android:scaleType="centerCrop" />',
        ] + scroll_open + [
            f'{scroll_inner}<LinearLayout',
            f'{scroll_inner}    android:layout_width="match_parent"',
            f'{scroll_inner}    android:layout_height="wrap_content"' if scroll else f'{scroll_inner}    android:layout_height="match_parent"{above_attr}',
            f'{scroll_inner}    android:orientation="{orientation}"{c_grav}',
            f'{scroll_inner}    {pad_str}>',
            '',
        ]
    else:
        if _relative:
            # Wrap everything in RelativeLayout, content gets layout_above bottom_nav
            lines += [
                f'<RelativeLayout xmlns:android="http://schemas.android.com/apk/res/android"{xmlns_app}',
                f'    android:layout_width="match_parent"',
                f'    android:fitsSystemWindows="true"',
                f'    android:layout_height="match_parent"{screen_bg_attr}>',
                '',
            ]
            if scroll:
                lines += [
                    f'    <androidx.core.widget.NestedScrollView',
                    f'        android:layout_width="match_parent"',
                    f'        android:layout_height="match_parent"',
                    f'        android:fillViewport="true"{bnav_above_scroll}>',
                    f'    <LinearLayout',
                    f'        android:layout_width="match_parent"',
                    f'        android:layout_height="wrap_content"',
                    f'        android:orientation="{orientation}"{c_grav}',
                    f'        {pad_str}>',
                    '',
                ]
            else:
                lines += [
                    f'    <LinearLayout',
                    f'        android:layout_width="match_parent"',
                    f'        android:layout_height="match_parent"{bnav_above_plain}',
                    f'        android:orientation="{orientation}"{c_grav}',
                    f'        {pad_str}>',
                    '',
                ]
        elif scroll:
            # Every other root fits the system windows; this one did not, and
            # with targetSdk 35 the window is edge-to-edge on Android 15+, so a
            # scrolling screen without a bottom bar drew its title under the
            # clock (the Stories replica, on a phone).
            lines += [
                f'<androidx.core.widget.NestedScrollView xmlns:android="http://schemas.android.com/apk/res/android"{xmlns_app}',
                f'    android:layout_width="match_parent"',
                f'    android:layout_height="match_parent"',
                f'    android:fitsSystemWindows="true"',
                f'    android:fillViewport="true"{screen_bg_attr}>',
                f'    <LinearLayout',
                f'        android:layout_width="match_parent"',
                f'        android:layout_height="wrap_content"',
                f'        android:orientation="{orientation}"{c_grav}',
                f'        {pad_str}>',
                '',
            ]
        else:
            # A view that fits the system windows has its padding REPLACED by
            # the bars' on an edge-to-edge window (targetSdk 35, Android 15+).
            # The screen's own padding sat on that same view, so the phone
            # dropped it -- chips and charts touched the edge of the glass --
            # while the Previewer and older phones kept it. The other roots
            # already carry the padding one level in; this one does too now.
            lines += [
                f'<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"{xmlns_app}',
                f'    android:layout_width="match_parent"',
                f'    android:layout_height="match_parent"',
                f'    android:fitsSystemWindows="true"{screen_bg_attr}>',
                f'    <LinearLayout',
                f'        android:layout_width="match_parent"',
                f'        android:layout_height="match_parent"',
                f'        android:orientation="{orientation}"{c_grav}',
                f'        {pad_str}>',
                '',
            ]

    counters = {
        'lbl': 0, 'btn': 0, 'inp': 0, 'cnt': 0, 'card': 0,
        'img': 0, 'video': 0, 'camera_view': 0, 'map': 0, 'lst': 0, 'vc': 0, 'spin': 0, 'skeleton': 0,
        'state': 0, 'car': 0, 'grid': 0, 'rich': 0, 'tree': 0,
        'lrow': 0,
    }

    def _row_layout_xml(root, id_prefix):
        """A row's own layout. Its ids are counted from zero -- they live in
        the row, not on the screen -- and must be the ones _assign_row_ids
        handed the adapter; if the generator ever counts otherwise, the build
        says so here instead of binding the wrong views."""
        saved = dict(counters)
        for key in counters:
            counters[key] = 0
        try:
            body = _generate_xml_for_comp([root], 'vertical', 0, indent="    ")
        finally:
            counters.clear()
            counters.update(saved)
        xml = '\n'.join([
            '<?xml version="1.0" encoding="utf-8"?>',
            '<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"',
            '    xmlns:app="http://schemas.android.com/apk/res-auto"',
            '    android:layout_width="match_parent"',
            '    android:layout_height="wrap_content">',
            '',
        ] + body + ['</FrameLayout>', ''])
        missing = [part['_xml_id'] for part in _row_components(root)
                   if part.get('_xml_id')
                   and ('android:id="@+id/%s"' % part['_xml_id']) not in xml]
        if missing:
            raise AssertionError('virtual_collection(row=...): the row layout does '
                                 'not have the views %s' % ', '.join(missing))
        # A row's views live inside the screen's hierarchy once the list
        # shows them. With the screen's own names (btn1, lbl3) a later
        # findViewById on the screen could find a row's view first; their
        # own prefix keeps every name to one view.
        xml = re.sub(r'(@\+?id/)(\w+)', lambda m: m.group(1) + id_prefix + m.group(2), xml)
        return _open_shadow_clipping(xml)

    def _generate_xml_for_comp(comp_list, parent_orientation, parent_gap, indent="    ",
                               parent_is_flex=False, parent_is_advanced=False,
                               overlay_sink=None, overlay_indent="        "):
        comp_lines = []
        first = True
        for comp in comp_list:
            ctype = comp['comp_type']
            comp_id = comp.get('id')
            if comp.get('_sheet') and not comp.get('_sheet_writing'):
                # A sheet's components are a layout of their own, inflated
                # into a BottomSheetDialog. Written here, in its turn, so the
                # ids after it keep the numbers the Java was written with.
                comp['_sheet_writing'] = True
                try:
                    _sheet_body = _generate_xml_for_comp(
                        [comp], 'vertical', 0, '    ',
                        parent_is_flex=False, parent_is_advanced=False)
                finally:
                    comp['_sheet_writing'] = False
                _SHEET_LAYOUTS[0][comp['_sheet']] = sheet_feature.layout_xml(
                    comp, _sheet_body,
                    sheet_feature.background_name(screen_id, comp['_sheet']), _xml_escape)
                continue
            comp_style = _fold_margin_shorthand(component_style(
                styles, ctype, comp_id,
                variant=(comp.get('variant') if ctype in ('button', 'label', 'card') else None),
                viewport=viewport,
            ))
            if (overlay_sink is not None
                    and str(comp_style.get('position', '')).strip().lower() == 'absolute'):
                # A screen's own absolute child goes to the overlay above the
                # content. Generated here, in its turn, so the ids after it keep
                # the numbers the Java was written with.
                overlay_sink.extend(_generate_xml_for_comp(
                    [comp], 'vertical', 0, overlay_indent,
                    parent_is_flex=True, parent_is_advanced=True,
                ))
                continue
            if ctype == 'image':
                comp_style = _fold_margin_shorthand(
                    _image_component_style(styles, comp, viewport=viewport))
            if comp.get('card_actions'):
                comp_style.update({
                    'display': 'flex', 'flex-direction': 'row',
                    'gap': comp_style.get('gap', '8px'),
                    'background-color': '#00000000', 'border-width': '0px',
                    'border-radius': '0px', 'padding': '0px',
                })
            
            # Rows in a list sit flush against each other: the divider is
            # the separator, and a 6dp baseline gap would push the
            # hairline off the seam it belongs on. An explicit CSS
            # margin still applies.
            stacked_rows = ctype == 'list_row'
            if (not parent_is_advanced and not first and not stacked_rows
                    and parent_orientation == 'vertical'):
                # Espaçamento entre componentes empilhados. Usa o `gap` quando
                # definido; caso contrário aplica um baseline de 6px para que os
                # componentes não fiquem "colados" no Android (o Previewer já
                # mostra esse respiro via pady). Só afeta ecrãs SEM gap.
                extra = parent_gap if parent_gap > 0 else 6
                current_mt = comp_style.get('margin-top', '0px')
                current_mt_val = int(current_mt.replace('px', '').strip()) if 'px' in str(current_mt) else 0
                comp_style['margin-top'] = f"{current_mt_val + extra}px"
            elif not parent_is_advanced and not first and parent_gap > 0:
                current_ml = comp_style.get('margin-left', '0px')
                current_ml_val = int(current_ml.replace('px', '').strip()) if 'px' in current_ml else 0
                comp_style['margin-left'] = f"{current_ml_val + parent_gap}px"
            
            margin_xml = _parse_margins_to_xml(comp_style)
            # opacity reached only images (their branch writes it); a card, a
            # label or a button at opacity: 0.5 was drawn solid.
            _opacity_attr = _parse_opacity_android(comp_style) if ctype != 'image' else None
            if _opacity_attr is not None and _opacity_attr != '1.0':
                margin_xml += f'\n{indent}    android:alpha="{_opacity_attr}"'
            if parent_is_advanced and ctype != 'container':
                encoded_child = encode_child_tag(comp_style, parent_orientation)
                if encoded_child:
                    margin_xml += (
                        f'\n{indent}    android:tag="{_xml_escape(encoded_child)}"'
                    )
            spacing = ''
            first = False

            # Calcular margem esquerda para definir layout_gravity="start" globalmente
            raw_ml = comp_style.get('margin-left', '0')
            try:
                left_margin = float(re.sub(r'[^0-9.]', '', str(raw_ml)))
            except (ValueError, TypeError):
                left_margin = 0.0
            ml_val = left_margin if getattr(comp_style, 'explicit_left', True) else 0.0

            layout_gravity_xml = f'\n{indent}    android:layout_gravity="start"' if ml_val > 0 else ''

            if ctype == 'label':
                counters['lbl'] += 1
                typo_xml = _parse_typography_xml(comp_style)
                _label_own = component_style(
                    styles, 'label', comp_id, include_body=False,
                    variant=comp.get('variant'), viewport=viewport)
                if not _get_style_fg(_label_own):
                    # A label that names no colour: the screen's (body's
                    # included), the Theme's, or the one that reads on the
                    # background (theme.content_ink), as the Previewer draws
                    # it. With no textColor Android drew it in Material's
                    # secondary grey, #757575 on a light app; with body's
                    # colour written as its own, a Theme's dark text went
                    # into a dark card and onto a screen made dark.
                    typo_xml = re.sub(r'\s*android:textColor="[^"]*"', '', typo_xml)
                    _label_ink = _content_ink(
                        styles, _get_style_bg(_label_own),
                        _screen_ink_style, _ink_parents.get(id(comp)))['text']
                    typo_xml += f'\n{indent}    android:textColor="{_color_xml(_resolve_color(_label_ink))}"'

                # O espaçamento vertical entre componentes é tratado pelo baseline
                # de margem acima; aqui só controlamos o indent horizontal.
                lbl_pad = ''
                lbl_pad_column = False

                # Alinhamento — paridade com o Previewer:
                #  • margin-left > 0  → esquerda, medido desde a borda (match_parent + start)
                #  • display:flex     → centrado (igual ao branch is_flex do Previewer)
                #  • por omissão      → esquerda com indent de 16dp (anchor='w', padx=16)
                if left_margin > 0:
                    lbl_w    = 'match_parent'
                    lbl_grav = 'start'
                elif parent_is_flex and (parent_is_advanced
                                         or _number(comp_style.get('flex-grow')) > 0):
                    # A label that grows is stretched by ApkpyLayout, so its
                    # gravity has room to move the text -- and centre put
                    # "Thursday plan" in the middle of Northline's header on a
                    # phone while the Previewer (and CSS, text-align: start)
                    # kept it at the start. The same goes for any label in an
                    # ApkpyLayout that is wider than its words: a stretched
                    # column, or text that wraps -- "mentioned you: @mara.vale
                    # next week?" broke onto a second line centred. The
                    # Previewer's layout-engine slot keeps it at the start.
                    lbl_w    = 'wrap_content'
                    lbl_grav = 'start|center_vertical'
                elif parent_is_flex:
                    lbl_w    = 'wrap_content'
                    lbl_grav = 'center'
                else:
                    lbl_w    = 'match_parent'
                    lbl_grav = 'start'
                    lbl_pad  = ' android:paddingLeft="16dp" android:paddingRight="16dp"'
                    lbl_pad_column = True

                # The label's own padding is the room around its text. In a
                # column it replaces the 16dp indent: "$486.20" with padding:
                # 0px sat 16dp right of "Spending" in the same card, on the
                # phone and in the Previewer. With no background there is no
                # shape drawable to carry it, so the TextView takes all of it.
                _own_pad = _declared_padding(_label_own)
                if _own_pad is not None:
                    _pt, _pr, _pb, _pl = _own_pad
                    lbl_pad = ''
                    if lbl_pad_column or not comp.get('_drawable'):
                        lbl_pad += (f' android:paddingLeft="{_pl}dp"'
                                    f' android:paddingRight="{_pr}dp"')
                    if not comp.get('_drawable'):
                        lbl_pad += (f' android:paddingTop="{_pt}dp"'
                                    f' android:paddingBottom="{_pb}dp"')

                # An explicit text-align wins over all of the above. In a flex
                # row the TextView is wrap_content, so gravity has no room to
                # move anything -- which is what CSS does with a shrink-to-fit
                # box too, so the two agree by doing nothing.
                lbl_align = _resolve_text_align(comp_style.get('text-align'))
                if lbl_align:
                    lbl_grav = _ANDROID_GRAVITY[lbl_align]

                # background-color num label chegava ao Previewer e desaparecia
                # no telemovel: o TextView nunca levava fundo nenhum. Quem
                # escrevesse texto escuro sobre uma faixa clara via a faixa no
                # desktop e texto invisivel no aparelho.
                lbl_bg = (chr(10) + indent + '    android:background="@drawable/'
                          + str(comp['_drawable']) + '"'
                          if comp.get('_drawable') else '')
                comp_lines += [
                    f'{indent}<TextView',
                    f'{indent}    android:id="@+id/lbl{counters["lbl"]}"',
                    f'{indent}    android:layout_width="{lbl_w}"',
                    f'{indent}    android:layout_height="wrap_content"{spacing}{margin_xml}',
                    f'{indent}    android:gravity="{lbl_grav}"{lbl_pad}{lbl_bg}',
                    f'{indent}    android:text="{_xml_escape(comp["text"])}"{typo_xml} />',
                    '',
                ]

            elif ctype == 'button':
                counters['btn'] += 1
                attr_bg = ''
                if comp.get('_drawable'):
                    attr_bg = (
                        f'\n{indent}    android:background="@drawable/{comp["_drawable"]}"'
                        f'\n{indent}    android:backgroundTint="@null"'
                        f'\n{indent}    app:backgroundTint="@null"'
                    )
                typo_xml  = _parse_typography_xml(comp_style, default_size=0)
                # Material 2 shouts button labels and always has, so the
                # attribute is only written when the app asks -- an existing
                # app's XML stays byte-identical.
                if 'text-transform' in comp_style:
                    all_caps = _resolve_text_transform(
                        comp_style.get('text-transform')
                    ) == 'uppercase'
                    typo_xml += (
                        f'\n{indent}    android:textAllCaps='
                        f'"{"true" if all_caps else "false"}"'
                    )
                # Material groups the icon with the label and centres the pair.
                # A row aligned to one edge wants the icon pinned to the leading
                # edge instead, which is what iconGravity="start" does -- the
                # difference between three fat pills and a settings list.
                btn_align = _resolve_text_align(comp_style.get('text-align'))
                btn_grav  = _ANDROID_GRAVITY.get(btn_align, 'center')
                if btn_align in ('left', 'right'):
                    btn_grav += '|center_vertical'
                icon_grav = 'start' if btn_align in ('left', 'right') else 'textStart'

                variant   = comp.get('variant')
                icon_drawable = comp.get('_icon_drawable')
                icon_xml = ''
                icon_only = bool(icon_drawable) and (
                    variant == 'icon' or not str(comp.get('text') or '').strip())
                if icon_drawable:
                    # Under Theme.MaterialComponents, <Button> is inflated as a
                    # MaterialButton. Its icon helper replaces framework compound
                    # drawables, so android:drawableStart silently disappears.
                    # Feed the generated vector through the Material API instead.
                    _icon_dp = int(_length_px(comp_style.get('icon-size'), 20))
                    icon_xml = (f'\n{indent}    app:icon="@drawable/{icon_drawable}"'
                                f'\n{indent}    app:iconSize="{_icon_dp}dp"'
                                f'\n{indent}    app:iconPadding="{"0dp" if icon_only else "8dp"}"'
                                f'\n{indent}    app:iconGravity="{"textStart" if icon_only else icon_grav}"'
                                f'\n{indent}    app:iconTint="@null"')
                    if icon_only:
                        # The icon is the whole content: centred, with nothing
                        # beside it to leave room for.
                        icon_xml += f'\n{indent}    android:padding="0dp"'

                # A button of a fixed height centres its text in that height,
                # as the Previewer draws it. MaterialButton kept its own 4dp
                # top and bottom inside it, and a 34dp button's bold 14sp label
                # was cut at the bottom on a phone whose font runs tall.
                _fixed_h = str(comp_style.get('height', '')).strip().lower()
                _centred_h = (not icon_only and bool(_fixed_h)
                              and _fixed_h not in ('auto', 'match_parent', 'fill')
                              and not _fixed_h.endswith('%'))
                if _centred_h:
                    icon_xml += (f'\n{indent}    android:paddingTop="0dp"'
                                 f'\n{indent}    android:paddingBottom="0dp"')

                # press: none silences the MaterialButton ripple, which is the
                # only piece of press feedback Android gives for free.
                if motion.normalise_press(comp_style.get('press')) == 'none':
                    icon_xml += f'\n{indent}    app:rippleColor="@android:color/transparent"'
                button_text = '' if variant == 'icon' and icon_drawable else comp['text']
                description_xml = _describe_xml(comp, indent)
                if not description_xml and variant == 'icon':
                    description_xml = f'\n{indent}    android:contentDescription="{_xml_escape(comp["text"] or comp.get("icon", "button"))}"'
                
                raw_w = str(comp_style.get('width', '')).strip().lower()
                if raw_w in ('100%', 'match_parent', 'fill'):
                    b_w = 'match_parent'
                elif raw_w:
                    b_w = _px_to_dp(raw_w)
                elif variant == 'icon' or parent_is_flex or parent_orientation == 'horizontal':
                    # Numa row (flex/horizontal), match_parent fazia o 1º botão comer
                    # toda a largura e os outros desapareciam → wrap_content lado a lado.
                    b_w = 'wrap_content'
                else:
                    b_w = 'match_parent'

                # Remove only the implicit Material minimums in compact rows.
                # An explicit CSS min-height remains authoritative on both
                # Android and the Previewer.
                raw_min_height = str(comp_style.get('min-height', '')).strip()
                android_min_height = (
                    _px_to_dp(raw_min_height) if raw_min_height else ''
                )
                raw_h = str(comp_style.get('height', '')).strip().lower()
                has_css_h = bool(raw_h) and not raw_h.endswith('%') and raw_h not in (
                    'auto', 'match_parent', 'fill')
                # An icon alone, with no size from the stylesheet, is a 48dp
                # square -- the touch target Android asks for and the size the
                # Previewer draws. With no padding and no minimum it shrank to
                # its 20dp icon: a sliver of a pill the finger misses.
                icon_min = f'{accessibility_feature.MIN_TOUCH_DP}dp' if icon_only else '0dp'
                min_attrs = ''
                if b_w == 'wrap_content':
                    min_attrs += f'\n{indent}    android:minWidth="{icon_min}"'
                if android_min_height:
                    min_attrs += (
                        f'\n{indent}    android:minHeight="{android_min_height}"'
                    )
                elif b_w == 'wrap_content':
                    min_attrs += (f'\n{indent}    android:minHeight='
                                  f'"{icon_min if not has_css_h else "0dp"}"')

                b_h = 'wrap_content'
                if has_css_h:
                    b_h = _px_to_dp(raw_h)
                    if not android_min_height and 'minHeight' not in min_attrs:
                        min_attrs += f'\n{indent}    android:minHeight="0dp"'
                # The stylesheet's padding goes on the Button too. It was only
                # the shape's <padding>, and MaterialButton's own 16dp at the
                # sides beat it: padding: 8px 0px on seven keys in a row
                # broke "Tab" into T / a / b.
                if any(key in comp_style for key in
                       ('padding', 'padding-left', 'padding-right',
                        'padding-top', 'padding-bottom')):
                    _bp_t, _bp_r, _bp_b, _bp_l = _parse_padding(comp_style)
                    min_attrs += f'\n{indent}    android:paddingLeft="{_bp_l}dp"'
                    # A fixed height already set the top and bottom to 0dp (above):
                    # written twice, the attribute stops AAPT and the whole build.
                    if not _centred_h:
                        min_attrs += f'\n{indent}    android:paddingTop="{_bp_t}dp"'
                    min_attrs += f'\n{indent}    android:paddingRight="{_bp_r}dp"'
                    if not _centred_h:
                        min_attrs += f'\n{indent}    android:paddingBottom="{_bp_b}dp"'
                comp_lines += [
                    f'{indent}<Button',
                    f'{indent}    android:id="@+id/btn{counters["btn"]}"',
                    f'{indent}    android:layout_width="{b_w}"',
                    f'{indent}    android:layout_height="{b_h}"{spacing}{margin_xml}{layout_gravity_xml}',
                    f'{indent}    android:gravity="{btn_grav}"{min_attrs}',
                    f'{indent}    android:text="{_xml_escape(button_text)}"{description_xml}{icon_xml}{typo_xml}{attr_bg} />',
                    '',
                ]

            elif ctype in ('inputs', 'input_field'):
                counters['inp'] += 1
                itype       = comp.get('input_type', 'text')
                placeholder = comp.get('placeholder', '')

                raw_w = str(comp_style.get('width', '')).strip().lower()
                if raw_w in ('100%', 'match_parent', 'fill'):
                    i_w = 'match_parent'
                elif raw_w:
                    i_w = _px_to_dp(raw_w)
                else:
                    i_w = 'match_parent' if ml_val == 0 and itype in ('text', 'password', 'search', 'range', 'textarea', 'number', 'date', 'time') else 'wrap_content'

                # A field with help, an error or a required rule sits in an
                # ApkpyField with its supporting text. The box takes the
                # field's place in the parent -- width, margins, the layout
                # tag -- and the EditText fills the box.
                _field_indent = None
                if field_feature.boxed(comp):
                    comp_lines += field_feature.open_xml(
                        indent, counters['inp'], package, i_w,
                        spacing + margin_xml + layout_gravity_xml)
                    _field_indent = indent
                    indent += '    '
                    spacing = margin_xml = layout_gravity_xml = ''
                    if i_w != 'wrap_content':
                        i_w = 'match_parent'

                inp_typo_xml = _parse_typography_xml(comp_style, default_size=0)
                hint_raw = (
                    comp_style.get('placeholder-color')
                    or comp_style.get('hint-color')
                    or '#9E9E9E'
                )
                hint_color_xml = (
                    f'\n{indent}    android:textColorHint="{_color_xml(hint_raw)}"'
                )

                if comp_style.get('padding'):
                    pd = _parse_padding(comp_style)
                    inp_pad_xml = (f'\n{indent}    android:paddingTop="{pd[0]}dp"'
                                   f'\n{indent}    android:paddingBottom="{pd[2]}dp"'
                                   f'\n{indent}    android:paddingStart="{pd[3]}dp"'
                                   f'\n{indent}    android:paddingEnd="{pd[1]}dp"')
                else:
                    inp_pad_xml = f'\n{indent}    android:padding="12dp"'

                # The keyboard: inputType (one line), the corner key, autofill.
                _keys_xml = keyboard_feature.xml_attrs(comp, indent, itype)
                if itype in ('text', 'search'):
                    attr_bg = f'\n{indent}    android:background="@drawable/{comp["_drawable"]}"' if comp.get('_drawable') else ''
                    comp_lines += [
                        f'{indent}<EditText',
                        f'{indent}    android:id="@+id/inp{counters["inp"]}"',
                        f'{indent}    android:layout_width="{i_w}"',
                        f'{indent}    android:layout_height="wrap_content"{spacing}{margin_xml}{layout_gravity_xml}{inp_pad_xml}',
                        f'{indent}    android:hint="{_xml_escape(placeholder)}"{hint_color_xml}{_keys_xml}{inp_typo_xml}{attr_bg} />',
                        '',
                    ]
                elif itype == 'password':
                    attr_bg = f'\n{indent}    android:background="@drawable/{comp["_drawable"]}"' if comp.get('_drawable') else ''
                    comp_lines += [
                        f'{indent}<EditText',
                        f'{indent}    android:id="@+id/inp{counters["inp"]}"',
                        f'{indent}    android:layout_width="{i_w}"',
                        f'{indent}    android:layout_height="wrap_content"{spacing}{margin_xml}{layout_gravity_xml}{inp_pad_xml}',
                        f'{indent}    android:hint="{_xml_escape(placeholder)}"{hint_color_xml}',
                        f'{indent}    android:inputType="textPassword"{_keys_xml}{inp_typo_xml}{attr_bg} />',
                        '',
                    ]
                elif itype == 'number':
                    attr_bg = f'\n{indent}    android:background="@drawable/{comp["_drawable"]}"' if comp.get('_drawable') else ''
                    comp_lines += [
                        f'{indent}<EditText',
                        f'{indent}    android:id="@+id/inp{counters["inp"]}"',
                        f'{indent}    android:layout_width="{i_w}"',
                        f'{indent}    android:layout_height="wrap_content"{spacing}{margin_xml}{layout_gravity_xml}{inp_pad_xml}',
                        f'{indent}    android:hint="{_xml_escape(placeholder)}"{hint_color_xml}',
                        f'{indent}    android:inputType="numberDecimal|numberSigned"{_keys_xml}{inp_typo_xml}{attr_bg} />',
                        '',
                    ]
                elif itype == 'date':
                    attr_bg = f'\n{indent}    android:background="@drawable/{comp["_drawable"]}"' if comp.get('_drawable') else ''
                    comp_style_dt = component_style(
                        styles, 'inputs', comp.get('id'), viewport=viewport
                    )
                    fg_raw_dt = _get_style_fg(comp_style_dt)
                    fg_xml_dt = f'\n{indent}    android:textColor="{_color_xml(fg_raw_dt)}"' if fg_raw_dt else ''
                    comp_lines += [
                        f'{indent}<TextView',
                        f'{indent}    android:id="@+id/inp{counters["inp"]}"',
                        f'{indent}    android:layout_width="{i_w}"',
                        f'{indent}    android:layout_height="wrap_content"{spacing}{margin_xml}{layout_gravity_xml}{inp_pad_xml}',
                        f'{indent}    android:text="{_xml_escape(placeholder) or "DD/MM/AAAA"}"',
                        f'{indent}    android:textColor="#9E9E9E"',
                        f'{indent}    android:clickable="true"',
                        f'{indent}    android:focusable="true"{attr_bg} />',
                        '',
                    ]
                elif itype == 'time':
                    attr_bg = f'\n{indent}    android:background="@drawable/{comp["_drawable"]}"' if comp.get('_drawable') else ''
                    comp_lines += [
                        f'{indent}<TextView',
                        f'{indent}    android:id="@+id/inp{counters["inp"]}"',
                        f'{indent}    android:layout_width="{i_w}"',
                        f'{indent}    android:layout_height="wrap_content"{spacing}{margin_xml}{layout_gravity_xml}{inp_pad_xml}',
                        f'{indent}    android:text="{_xml_escape(placeholder) or "HH:MM"}"',
                        f'{indent}    android:textColor="#9E9E9E"',
                        f'{indent}    android:clickable="true"',
                        f'{indent}    android:focusable="true"{attr_bg} />',
                        '',
                    ]
                elif itype == 'textarea':
                    attr_bg = f'\n{indent}    android:background="@drawable/{comp["_drawable"]}"' if comp.get('_drawable') else ''
                    raw_rows = str(comp_style.get('rows', '')).strip()
                    min_lines = int(raw_rows) if raw_rows.isdigit() else 4
                    # `rows` e' o minimo e `max-rows` o tecto: entre os dois o
                    # campo cresce com o texto. Um compositor de conversa quer
                    # comecar numa linha e parar em seis, nao ocupar meio ecra
                    # a' espera que alguem escreva.
                    raw_max = str(comp_style.get('max-rows', '')).strip()
                    if raw_max.isdigit():
                        max_lines = max(min_lines, int(raw_max))
                    else:
                        max_lines = max(min_lines * 2, 8)
                    comp_lines += [
                        f'{indent}<EditText',
                        f'{indent}    android:id="@+id/inp{counters["inp"]}"',
                        f'{indent}    android:layout_width="{i_w}"',
                        f'{indent}    android:layout_height="wrap_content"{spacing}{margin_xml}{layout_gravity_xml}{inp_pad_xml}',
                        f'{indent}    android:hint="{_xml_escape(placeholder)}"{hint_color_xml}',
                        f'{indent}    android:inputType="textMultiLine"',
                        f'{indent}    android:minLines="{min_lines}"',
                        f'{indent}    android:maxLines="{max_lines}"',
                        f'{indent}    android:gravity="top|start"',
                        f'{indent}    android:scrollbars="vertical"{inp_typo_xml}{attr_bg} />',
                        '',
                    ]
                elif itype == 'switch':
                    sw_text_color = ''
                    fg_raw = _get_style_fg(comp_style)
                    if fg_raw:
                        sw_text_color = f'\n{indent}    android:textColor="{_color_xml(fg_raw)}"'
                    comp_lines += [
                        f'{indent}<androidx.appcompat.widget.SwitchCompat',
                        f'{indent}    android:id="@+id/inp{counters["inp"]}"',
                        f'{indent}    android:layout_width="match_parent"',
                        f'{indent}    android:layout_height="wrap_content"{spacing}{margin_xml}',
                        f'{indent}    android:paddingTop="12dp"',
                        f'{indent}    android:paddingBottom="12dp"',
                        f'{indent}    android:text="{_xml_escape(placeholder)}"{sw_text_color} />',
                        '',
                    ]
                elif itype == 'checkbox':
                    comp_lines += [
                        f'{indent}<CheckBox',
                        f'{indent}    android:id="@+id/inp{counters["inp"]}"',
                        f'{indent}    android:layout_width="{i_w}"',
                        f'{indent}    android:layout_height="wrap_content"{spacing}{margin_xml}{layout_gravity_xml}',
                        f'{indent}    android:text="{_xml_escape(placeholder)}"{inp_typo_xml} />',
                        '',
                    ]
                elif itype == 'range':
                    # accent-color: the Previewer drew the thumb in it and the
                    # phone kept the theme's blue.
                    _range_accent = comp_style.get('accent-color')
                    _range_tint = ''
                    if _range_accent:
                        _tint = _color_xml(_resolve_color(_range_accent))
                        _range_tint = (f'\n{indent}    android:progressTint="{_tint}"'
                                       f'\n{indent}    android:thumbTint="{_tint}"')
                    comp_lines += [
                        f'{indent}<SeekBar',
                        f'{indent}    android:id="@+id/inp{counters["inp"]}"',
                        f'{indent}    android:layout_width="{i_w}"',
                        f'{indent}    android:layout_height="wrap_content"{spacing}{margin_xml}{layout_gravity_xml}{_range_tint}',
                        f'{indent}    android:max="100" />',
                        '',
                    ]
                elif itype == 'radio':
                    options = [o.strip() for o in placeholder.split('|')] if placeholder else ['Option 1', 'Option 2']
                    comp_lines.append(f'{indent}<RadioGroup')
                    comp_lines.append(f'{indent}    android:id="@+id/inp{counters["inp"]}Group"')
                    comp_lines.append(f'{indent}    android:layout_width="{i_w}"')
                    comp_lines.append(f'{indent}    android:layout_height="wrap_content"{spacing}{margin_xml}{layout_gravity_xml}>')
                    for i, opt in enumerate(options):
                        comp_lines += [
                            f'{indent}    <RadioButton',
                            f'{indent}        android:id="@+id/inp{counters["inp"]}_rb{i}"',
                            f'{indent}        android:layout_width="wrap_content"',
                            f'{indent}        android:layout_height="wrap_content"',
                            f'{indent}        android:text="{_xml_escape(opt)}" />',
                        ]
                    comp_lines += [f'{indent}</RadioGroup>', '']

                elif itype == 'select':
                    attr_bg = f'\n{indent}    android:background="@drawable/{comp["_drawable"]}"' if comp.get('_drawable') else ''
                    # Only apply padding if explicitly set in CSS — don't use the default 12dp
                    sel_pad = ''
                    if comp_style.get('padding'):
                        pd = _parse_padding(comp_style)
                        sel_pad = (f'\n{indent}    android:paddingTop="{pd[0]}dp"'
                                   f'\n{indent}    android:paddingBottom="{pd[2]}dp"'
                                   f'\n{indent}    android:paddingStart="{pd[3]}dp"'
                                   f'\n{indent}    android:paddingEnd="{pd[1]}dp"')
                    comp_lines += [
                        f'{indent}<Spinner',
                        f'{indent}    android:id="@+id/inp{counters["inp"]}"',
                        f'{indent}    android:layout_width="match_parent"',
                        f'{indent}    android:layout_height="wrap_content"{spacing}{margin_xml}{layout_gravity_xml}',
                        f'{indent}    android:spinnerMode="dropdown"',
                        f'{indent}    android:dropDownWidth="match_parent"',
                        f'{indent}    android:gravity="start|center_vertical"{sel_pad}{attr_bg} />',
                        '',
                    ]

                if _field_indent is not None:
                    indent = _field_indent
                    _field_pad = (_parse_padding(comp_style) if comp_style.get('padding')
                                  else (12, 12, 12, 12))
                    while comp_lines and comp_lines[-1] == '':
                        comp_lines.pop()
                    comp_lines += field_feature.close_xml(
                        indent, counters['inp'], package, comp,
                        _field_pad[3], _field_pad[1], _xml_escape)

            elif ctype == 'card':
                counters['card'] += 1
                card_bg = _resolve_color(_get_style_bg(comp_style) or '#FFFFFF')
                card_radius = _parse_radius(comp_style)
                card_border = _get_style_border_color(comp_style)
                card_border = (
                    card_border if card_border and card_border != 'none'
                    else '#00000000'
                )
                card_border_width = _parse_border_width(comp_style)
                card_elevation = _parse_box_shadow_android(comp_style) or '0dp'
                card_padding = _parse_padding(comp_style)
                card_orientation = _get_flex_orientation(comp_style)

                card_w = _responsive_android_dim(
                    comp_style.get('width'), viewport, 'width', viewport[0]
                )
                card_weight = ''
                if card_w is None:
                    if parent_is_advanced:
                        card_w = 'wrap_content'
                    elif parent_orientation == 'horizontal':
                        card_w = '0dp'
                        card_weight = f'\n{indent}    android:layout_weight="1"'
                    else:
                        card_w = 'match_parent'
                elif (card_w == 'match_parent' and parent_orientation == 'horizontal'
                      and not parent_is_advanced):
                    card_w = '0dp'
                    card_weight = f'\n{indent}    android:layout_weight="1"'
                card_h = _responsive_android_dim(
                    comp_style.get('height'), viewport, 'height', viewport[1]
                ) or 'wrap_content'
                min_height = _responsive_android_dim(
                    comp_style.get('min-height'), viewport, 'height', viewport[1]
                )
                min_height_attr = (
                    f'\n{indent}    android:minHeight="{min_height}"'
                    if min_height and min_height.endswith('dp') else ''
                )
                card_pad_attr = (
                    f'\n{indent}        android:paddingLeft="{card_padding[3]}dp"'
                    f'\n{indent}        android:paddingTop="{card_padding[0]}dp"'
                    f'\n{indent}        android:paddingRight="{card_padding[1]}dp"'
                    f'\n{indent}        android:paddingBottom="{card_padding[2]}dp"'
                ) if any(card_padding) else ''
                # A gradient goes on the card's content: a MaterialCardView
                # draws its own shape and takes no background. Same corners,
                # so it fills the card; the card's colour (the gradient's
                # middle) stays under it for the shadow.
                card_inner_h = 'wrap_content'
                _card_grad = _gradient_of(component_style(
                    styles, 'card', comp.get('id'), include_body=False,
                    variant=comp.get('variant'), viewport=viewport))
                _card_spec = gradient_feature.spec(
                    _card_grad, lambda c: str(_resolve_color(c)),
                    radii=_parse_radii(comp_style)) if _card_grad else None
                if _card_spec and package:
                    _card_name = 'apkpy_%s_%s_gradient' % (
                        re.sub(r'[^a-z0-9_]', '_', str(screen_id).lower()),
                        re.sub(r'[^a-z0-9_]', '_', str(comp.get('id') or 'card%d' % counters['card']).lower()))
                    _SCREEN_GRADIENTS[0][_card_name] = gradient_feature.drawable_xml(package, _card_spec)
                    _USES_GRADIENT[0] = True
                    card_pad_attr += f'\n{indent}        android:background="@drawable/{_card_name}"'
                    card_inner_h = 'match_parent'
                comp_lines += [
                    f'{indent}<com.google.android.material.card.MaterialCardView',
                    f'{indent}    xmlns:app="http://schemas.android.com/apk/res-auto"',
                    f'{indent}    android:id="@+id/card{counters["card"]}"',
                    f'{indent}    android:layout_width="{card_w}"',
                    f'{indent}    android:layout_height="{card_h}"{card_weight}{min_height_attr}{spacing}{margin_xml}{layout_gravity_xml}',
                    f'{indent}    app:cardBackgroundColor="{_color_xml(card_bg)}"',
                    f'{indent}    app:cardCornerRadius="{card_radius}dp"',
                    f'{indent}    app:cardElevation="{card_elevation}"'
                    f'{_shadow_colour_xml(comp_style, indent)}',
                    f'{indent}    app:strokeColor="{_color_xml(card_border)}"',
                    f'{indent}    app:strokeWidth="{card_border_width}dp"',
                    f'{indent}    app:cardUseCompatPadding="false">',
                    f'{indent}    <LinearLayout',
                    f'{indent}        android:layout_width="match_parent"',
                    f'{indent}        android:layout_height="{card_inner_h}"',
                    f'{indent}        android:orientation="{card_orientation}"{card_pad_attr}>',
                    '',
                ]
                card_gap_raw = comp_style.get('gap', '0')
                card_gap_match = re.search(r'(\d+)', str(card_gap_raw))
                card_is_flex = str(comp_style.get('display', '')).strip().lower() in ('flex', 'grid')
                card_gap = int(card_gap_match.group(1)) if card_gap_match and card_is_flex else 0
                if comp.get('children'):
                    comp_lines += _generate_xml_for_comp(
                        comp['children'], card_orientation, card_gap,
                        indent + '        ', parent_is_flex=card_is_flex,
                    )
                comp_lines += [
                    f'{indent}    </LinearLayout>',
                    f'{indent}</com.google.android.material.card.MaterialCardView>',
                    '',
                ]

            elif ctype in choice_feature.COMPONENTS:
                counters['chc'] = counters.get('chc', 0) + 1
                comp_lines += choice_feature.layout_xml(
                    indent, counters['chc'], package, margin_xml)

            elif ctype == draw_pad_feature.COMPONENT:
                counters['dpad'] = counters.get('dpad', 0) + 1
                comp_lines += draw_pad_feature.layout_xml(
                    indent, counters['dpad'], package,
                    _draw_pad_rules.height(component_style(styles, ctype, comp.get('id'),
                                                           include_body=False)),
                    margin_xml)

            elif ctype == web_page_feature.COMPONENT:
                counters['web'] = counters.get('web', 0) + 1
                _web_h = (_responsive_android_dim(comp_style.get('height'), viewport, 'height',
                                                  viewport[1])
                          if comp_style.get('height') else None) or 'wrap_content'
                comp_lines += web_page_feature.layout_xml(
                    indent, counters['web'], _web_h, margin_xml)

            elif ctype == 'chart':
                counters['cht'] = counters.get('cht', 0) + 1
                # width: 92px is the chart's width, as the Previewer draws it.
                # It was always the parent's: a ring beside its text in a row
                # took the whole row and left the text 1px wide.
                chart_w = _responsive_android_dim(
                    comp_style.get('width'), viewport, 'width', viewport[0]
                ) or 'match_parent'
                comp_lines += [
                    f'{indent}<{package}.ApkpyChart',
                    f'{indent}    android:id="@+id/cht{counters["cht"]}"',
                    f'{indent}    android:layout_width="{chart_w}"',
                    f'{indent}    android:layout_height="wrap_content"{margin_xml} />',
                    '',
                ]

            elif ctype == 'container' and comp.get('_pager'):
                counters['pgr'] = counters.get('pgr', 0) + 1
                _pager_style = component_style(styles, 'pager', comp.get('id'),
                                               include_body=False, viewport=viewport)
                _pager_colors = pager_feature.colors(_pager_style, styles.get('__theme__', {}))
                _raw_pager_h = _pager_style.get('height')
                _fixed_pager_h = (_responsive_android_dim(_raw_pager_h, viewport, 'height', viewport[1])
                                  if _raw_pager_h else None)
                if _fixed_pager_h and _fixed_pager_h != 'wrap_content':
                    _host_height, _fills = f'android:layout_height="{_fixed_pager_h}"', True
                elif (parent_orientation == 'vertical' and not parent_is_advanced
                        and _number(_pager_style.get('flex-grow')) > 0):
                    _host_height = ('android:layout_height="0dp"\n'
                                    f'{indent}    android:layout_weight="1"')
                    _fills = True
                else:
                    _host_height, _fills = 'android:layout_height="wrap_content"', False
                comp_lines += pager_feature.layout_xml(
                    counters['pgr'], indent, package, _host_height, _fills, margin_xml,
                    _color_xml(_pager_colors['background']) if _pager_colors['background']
                    else '@android:color/transparent',
                    _color_xml(_pager_colors['divider']) if _pager_colors['divider'] else '',
                    pager_feature.bar_height(comp),
                    _generate_xml_for_comp(
                        pager_feature.tabs_of(comp), 'vertical', 0, indent + '        ',
                        parent_is_flex=False, parent_is_advanced=False),
                )

            elif ctype == 'container':
                counters['cnt'] += 1
                c_orient = _get_flex_orientation(comp_style)
                responsive_config = comp.get('responsive') or {}
                if responsive_config:
                    vp_width, vp_height = viewport
                    if vp_width > vp_height and responsive_config.get('landscape'):
                        direction = responsive_config['landscape']
                    elif vp_width >= int(responsive_config.get('breakpoint', 600)):
                        direction = responsive_config.get(
                            'tablet', responsive_config.get('mobile', 'column')
                        )
                    else:
                        direction = responsive_config.get('mobile', 'column')
                    c_orient = 'horizontal' if direction == 'row' else 'vertical'
                child_styles = [
                    component_style(
                        styles, child.get('comp_type'), child.get('id'),
                        variant=(child.get('variant')
                                 if child.get('comp_type') in ('button', 'label', 'card')
                                 else None),
                        viewport=viewport,
                    )
                    for child in comp.get('children', [])
                ]
                c_advanced = is_advanced_container(
                    comp_style, child_styles, responsive=bool(responsive_config)
                )
                element_name = f'{package}.ApkpyLayout' if c_advanced else 'LinearLayout'
                c_elevation = _parse_box_shadow_android(comp_style)
                c_elev_attr = (
                    f'\n{indent}    android:elevation="{c_elevation}"'
                    + _shadow_colour_xml(comp_style, indent)
                    if c_elevation else ''
                )
                # The shadow of a child is drawn outside that child's own box,
                # and this container clips its children to its padding. Opened
                # only when a child actually asks for one.
                c_clip_attr = ''
                if any(_parse_box_shadow_android(s) for s in child_styles):
                    c_clip_attr = (
                        f'\n{indent}    android:clipToPadding="false"'
                        f'\n{indent}    android:clipChildren="false"'
                    )
                # Its own fill, never the page's: the cascade folds ``body``
                # into every component, and a container that painted the page
                # colour drew a band of it across a sheet or a card. A box
                # with nothing of its own is transparent, as in the Previewer.
                c_bg = _get_style_bg(component_style(
                    styles, 'container', comp_id, include_body=False, viewport=viewport))
                if comp.get('_drawable'):
                    c_bg_attr = f'\n{indent}    android:background="@drawable/{comp["_drawable"]}"'
                else:
                    c_bg_attr = f'\n{indent}    android:background="{_color_xml(c_bg)}"' if c_bg else ''
                c_pad = _parse_padding(comp_style)
                c_pad_attr = (f'\n{indent}    android:paddingLeft="{c_pad[3]}dp"'
                              f'\n{indent}    android:paddingTop="{c_pad[0]}dp"'
                              f'\n{indent}    android:paddingRight="{c_pad[1]}dp"'
                              f'\n{indent}    android:paddingBottom="{c_pad[2]}dp"') if any(c_pad) else ''
                # vertical → centra horizontalmente; horizontal → centra os filhos
                # na row (senão ficavam colados à esquerda).
                if c_advanced:
                    c_grav = ''
                elif comp.get('card_actions'):
                    c_grav = f'\n{indent}    android:gravity="end|center_vertical"'
                elif c_orient == 'vertical':
                    c_grav = (
                        f'\n{indent}    android:gravity="{_column_gravity(comp_style)}"'
                    )
                else:
                    c_grav = f'\n{indent}    android:gravity="center"'
                raw_width = comp_style.get('width')
                cnt_w = _responsive_android_dim(
                    raw_width, viewport, 'width', viewport[0]
                )
                max_width = _responsive_android_dim(
                    comp_style.get('max-width'), viewport, 'width', viewport[0]
                )
                if max_width and max_width.endswith('dp'):
                    max_value = int(max_width[:-2])
                    if cnt_w in (None, 'match_parent') and viewport[0] > max_value:
                        cnt_w = max_width
                    elif cnt_w and cnt_w.endswith('dp'):
                        cnt_w = f"{min(int(cnt_w[:-2]), max_value)}dp"
                weight_attr = ''
                if cnt_w is None:
                    if parent_is_advanced:
                        cnt_w = 'wrap_content'
                    elif parent_orientation == 'horizontal':
                        cnt_w = '0dp'
                        weight_attr = f'\n{indent}    android:layout_weight="1"'
                    else:
                        cnt_w = 'wrap_content' if ml_val > 0 else 'match_parent'
                elif (cnt_w == 'match_parent' and parent_orientation == 'horizontal'
                      and not parent_is_advanced):
                    cnt_w = '0dp'
                    weight_attr = f'\n{indent}    android:layout_weight="1"'
                raw_height = comp_style.get('height')
                cnt_h = _responsive_android_dim(
                    raw_height, viewport, 'height', viewport[1]
                ) or 'wrap_content'
                # A column child with flex-grow takes what its siblings do
                # not: 0dp plus a weight. This is what pins whatever comes
                # after it to the bottom of the screen, and what gives an
                # empty state the whole middle to sit in.
                if (not weight_attr and not parent_is_advanced
                        and parent_orientation == 'vertical'
                        and _number(comp_style.get('flex-grow')) > 0):
                    cnt_h = '0dp'
                    weight_attr = f'\n{indent}    android:layout_weight="1"'
                min_height = _responsive_android_dim(
                    comp_style.get('min-height'), viewport, 'height', viewport[1]
                )
                min_height_attr = (
                    f'\n{indent}    android:minHeight="{min_height}"'
                    if min_height and min_height.endswith('dp') else ''
                )
                if max_width and cnt_w != 'match_parent' and ml_val <= 0:
                    layout_gravity_xml = f'\n{indent}    android:layout_gravity="center_horizontal"'
                # align-self in a plain column (the screen itself; a container
                # with such a child is already an ApkpyLayout, which reads it
                # from the tag). max-width centred every chat bubble on the
                # phone, the reply that belongs on the right included.
                _self_gravity = _ALIGN_SELF_GRAVITY.get(
                    str(comp_style.get('align-self', '')).strip().lower())
                if _self_gravity and not parent_is_advanced and parent_orientation == 'vertical':
                    layout_gravity_xml = f'\n{indent}    android:layout_gravity="{_self_gravity}"'
                layout_tag_attr = ''
                orientation_attr = f'\n{indent}    android:orientation="{c_orient}"'
                tag_parts = []
                if parent_is_advanced:
                    child_layout_tag = encode_child_tag(
                        comp_style, parent_orientation
                    )
                    if child_layout_tag:
                        tag_parts.append(child_layout_tag)
                if c_advanced:
                    fallback_direction = 'row' if c_orient == 'horizontal' else 'column'
                    effective_style = dict(comp_style)
                    if responsive_config and effective_style.get('display', '').lower() != 'grid':
                        effective_style['display'] = 'flex'
                        effective_style['flex-direction'] = fallback_direction
                    tag_parts.append(encode_container_tag(
                        effective_style, fallback_direction
                    ))
                    orientation_attr = ''
                if tag_parts:
                    layout_tag_attr = (
                        f'\n{indent}    android:tag="{_xml_escape(";".join(tag_parts))}"'
                    )
                # showDividers="middle" draws between children and never
                # at the edges, which is the whole difference between a
                # grouped list and a stack of boxes. ApkpyLayout is not a
                # LinearLayout and ignores both attributes, so an advanced
                # container says nothing rather than lying about it.
                divider_attr = ''
                if comp.get('_divider_drawable') and not c_advanced:
                    divider_attr = (
                        f'\n{indent}    android:divider='
                        f'"@drawable/{comp["_divider_drawable"]}"'
                        f'\n{indent}    android:showDividers="middle"'
                    )
                comp_lines += [
                    f'{indent}<{element_name}',
                    f'{indent}    android:id="@+id/cnt{counters["cnt"]}"',
                    f'{indent}    android:layout_width="{cnt_w}"',
                    f'{indent}    android:layout_height="{cnt_h}"{weight_attr}{min_height_attr}{spacing}{margin_xml}{layout_gravity_xml}',
                    f'{indent}    {orientation_attr}{layout_tag_attr}{c_bg_attr}{c_pad_attr}{c_grav}{divider_attr}{c_elev_attr}{c_clip_attr}>',
                    '',
                ]
                
                if 'children' in comp and comp['children']:
                    c_gap_raw = comp_style.get('gap', '0')
                    c_gap_match = re.search(r'(\d+)', str(c_gap_raw))
                    c_is_flex = bool(responsive_config) or str(
                        comp_style.get('display', '')
                    ).strip().lower() in ('flex', 'grid')
                    c_gap = int(c_gap_match.group(1)) if c_gap_match and c_is_flex else 0
                    comp_lines += _generate_xml_for_comp(
                        comp['children'], c_orient, c_gap, indent + "    ",
                        parent_is_flex=c_is_flex,
                        parent_is_advanced=c_advanced,
                    )
                    
                comp_lines.append(f'{indent}</{element_name}>')
                comp_lines.append('')

            elif ctype == 'list_row':
                counters['lrow'] += 1
                row_id = f'lrow{counters["lrow"]}'
                pad = _parse_padding(comp_style)
                pad_l = pad[3] or 16
                pad_r = pad[1] or 16
                row_min = _px_to_dp(
                    str(comp_style.get('min-height', '56px')).strip() or '56px'
                )
                # In a row a sibling cannot ask for match_parent -- the
                # first one would eat the width and the rest would vanish.
                # 0dp plus a weight makes them share, which is what the
                # Previewer's expanding pack does.
                raw_row_w = str(comp_style.get('width', '')).strip().lower()
                row_weight = ''
                if raw_row_w in ('100%', 'match_parent', 'fill'):
                    row_w = 'match_parent'
                elif raw_row_w:
                    row_w = _px_to_dp(raw_row_w)
                elif parent_is_flex or parent_orientation == 'horizontal':
                    row_w = '0dp'
                    row_weight = f'{chr(10)}{indent}    android:layout_weight="1"'
                else:
                    row_w = 'match_parent'
                icon_dp = int(_length_px(comp_style.get('icon-size'), 24))
                # A row with no surface of its own still has to answer a tap.
                # ?attr/selectableItemBackground is the framework ripple, and
                # it is what a grouped list uses -- the group owns the shape.
                if comp.get('_drawable'):
                    row_bg = f'@drawable/{comp["_drawable"]}'
                elif motion.normalise_press(comp_style.get('press')) == 'none':
                    row_bg = '@android:color/transparent'
                else:
                    row_bg = '?attr/selectableItemBackground'

                title_style = dict(comp_style)
                title_style.pop('min-height', None)
                sub_style = {
                    **comp_style,
                    'color': comp_style.get('subtitle-color')
                             or comp_style.get('color'),
                    'font-size': comp_style.get('subtitle-size', '13px'),
                    'font-weight': 'normal',
                }
                trail_style = {
                    **comp_style,
                    'color': comp_style.get('trailing-color')
                             or comp_style.get('subtitle-color')
                             or comp_style.get('color'),
                    'font-size': comp_style.get('trailing-size', '13px'),
                    'font-weight': 'normal',
                }

                comp_lines += [
                    f'{indent}<LinearLayout',
                    f'{indent}    android:id="@+id/{row_id}"',
                    f'{indent}    android:layout_width="{row_w}"',
                    f'{indent}    android:layout_height="wrap_content"{row_weight}{spacing}{margin_xml}',
                    f'{indent}    android:minHeight="{row_min}"',
                    f'{indent}    android:orientation="horizontal"',
                    f'{indent}    android:gravity="center_vertical"',
                    f'{indent}    android:clickable="true"',
                    f'{indent}    android:focusable="true"',
                    f'{indent}    android:background="{_color_xml(row_bg)}"',
                    f'{indent}    android:paddingLeft="{pad_l}dp"'
                    f' android:paddingTop="{pad[0]}dp"'
                    f' android:paddingRight="{pad_r}dp"'
                    f' android:paddingBottom="{pad[2]}dp">',
                    '',
                ]
                if comp.get('_icon_drawable'):
                    comp_lines += [
                        f'{indent}    <ImageView',
                        f'{indent}        android:layout_width="{icon_dp}dp"',
                        f'{indent}        android:layout_height="{icon_dp}dp"',
                        f'{indent}        android:layout_marginEnd="16dp"',
                        f'{indent}        android:importantForAccessibility="no"',
                        f'{indent}        android:src="@drawable/{comp["_icon_drawable"]}" />',
                        '',
                    ]
                # 0dp + weight 1 is the text block taking whatever the icon and
                # the trailing pieces leave behind, rather than pushing them
                # off the edge when the label is long.
                comp_lines += [
                    f'{indent}    <LinearLayout',
                    f'{indent}        android:layout_width="0dp"',
                    f'{indent}        android:layout_height="wrap_content"',
                    f'{indent}        android:layout_weight="1"',
                    f'{indent}        android:orientation="vertical">',
                    '',
                    f'{indent}        <TextView',
                    f'{indent}            android:id="@+id/{row_id}_title"',
                    f'{indent}            android:layout_width="match_parent"',
                    f'{indent}            android:layout_height="wrap_content"',
                    f'{indent}            android:maxLines="1"',
                    f'{indent}            android:ellipsize="end"',
                    f'{indent}            android:text="{_xml_escape(str(comp.get("text") or ""))}"'
                    f'{_parse_typography_xml(title_style, 15, indent + chr(32) * 12)} />',
                    '',
                ]
                if comp.get('subtitle') is not None:
                    comp_lines += [
                        f'{indent}        <TextView',
                        f'{indent}            android:id="@+id/{row_id}_subtitle"',
                        f'{indent}            android:layout_width="match_parent"',
                        f'{indent}            android:layout_height="wrap_content"',
                        f'{indent}            android:maxLines="1"',
                        f'{indent}            android:ellipsize="end"',
                        f'{indent}            android:text="{_xml_escape(str(comp.get("subtitle")))}"'
                        f'{_parse_typography_xml(sub_style, 13, indent + chr(32) * 12)} />',
                        '',
                    ]
                comp_lines += [f'{indent}    </LinearLayout>', '']
                if comp.get('trailing') is not None:
                    comp_lines += [
                        f'{indent}    <TextView',
                        f'{indent}        android:id="@+id/{row_id}_trailing"',
                        f'{indent}        android:layout_width="wrap_content"',
                        f'{indent}        android:layout_height="wrap_content"',
                        f'{indent}        android:layout_marginStart="12dp"',
                        f'{indent}        android:maxLines="1"',
                        f'{indent}        android:text="{_xml_escape(str(comp.get("trailing")))}"'
                        f'{_parse_typography_xml(trail_style, 13, indent + chr(32) * 8)} />',
                        '',
                    ]
                if comp.get('_trailing_icon_drawable'):
                    comp_lines += [
                        f'{indent}    <ImageView',
                        f'{indent}        android:layout_width="20dp"',
                        f'{indent}        android:layout_height="20dp"',
                        f'{indent}        android:layout_marginStart="8dp"',
                        f'{indent}        android:importantForAccessibility="no"',
                        f'{indent}        android:src="@drawable/{comp["_trailing_icon_drawable"]}" />',
                        '',
                    ]
                comp_lines += [f'{indent}</LinearLayout>', '']

            elif ctype == 'image':
                counters['img'] += 1
                src = comp.get('src', '')
                safe_name = _android_drawable_name(src, f'img_{counters["img"]}')

                w_attr = _parse_image_dim_android(comp_style.get('width'))
                h_attr = _parse_image_dim_android(comp_style.get('height'))
                ratio_value = _parse_aspect_ratio(
                    comp.get('aspect_ratio') or comp_style.get('aspect-ratio')
                )
                if ratio_value and not comp.get('avatar'):
                    if not comp_style.get('width'):
                        w_attr = 'match_parent'
                    if not comp_style.get('height') and w_attr.endswith('dp'):
                        width_number = int(re.sub(r'[^0-9]', '', w_attr) or 0)
                        h_attr = f'{max(1, int(round(width_number / ratio_value)))}dp'
                scale_type = _parse_object_fit_android(comp_style)
                # A flex container lets its children draw outside (shadows,
                # transforms), and centerCrop scales a portrait photo past a
                # square box: a 44dp thumbnail ran the height of its row. The
                # view crops its own drawing, which leaves the shadow alone.
                crop_attr = (' android:cropToPadding="true"'
                             if scale_type == 'centerCrop' else '')
                opacity_val = _parse_opacity_android(comp_style)
                elevation_val = _parse_box_shadow_android(comp_style)
                radius = _parse_radius(comp_style)
                bc = _get_style_border_color(comp_style)
                bw = _parse_border_width(comp_style)
                alpha_attr     = f'\n{indent}    android:alpha="{opacity_val}"' if opacity_val else ''
                elevation_attr = (f'\n{indent}    android:elevation="{elevation_val}"'
                                  + _shadow_colour_xml(comp_style, indent)) if elevation_val else ''

                is_remote = bool(comp.get('_is_remote'))
                initial_asset = comp.get('placeholder') if is_remote else src
                if '{' in str(initial_asset or ''):
                    initial_asset = None      # a row's {field}: filled on bind
                initial_name = _android_drawable_name(initial_asset) if initial_asset else None
                src_attr = (
                    f'\n{indent}    android:src="@drawable/{initial_name}"'
                    if initial_name and not str(initial_asset).startswith(('http://', 'https://'))
                    else ''
                )

                if radius > 0 or bw > 0:
                    stroke_color_attr = f'\n{indent}    app:strokeColor="{_color_xml(bc)}"' if bc and bc != 'none' else ''
                    stroke_width_attr = f'\n{indent}    app:strokeWidth="{bw}dp"' if bw > 0 else ''
                    if bw > 0:
                        stroke_width_attr += f'\n{indent}    android:padding="{bw / 2:g}dp"'
                    shape_token = _safe_android_id(
                        comp.get('id'), f'{safe_name}_{counters["img"]}',
                    )
                    shape_style_name = f'RoundedImg_{shape_token}'
                    shape_attr = f'\n{indent}    app:shapeAppearanceOverlay="@style/{shape_style_name}"' if radius > 0 else ''
                    comp['_shape_style_name'] = shape_style_name
                    comp['_shape_radius'] = radius
                    if comp.get('avatar'):
                        size = max(16, int(comp.get('size') or 48))
                        dot = max(10, size // 4)
                        status_drawable = comp.get('_status_drawable')
                        status_view = []
                        if status_drawable:
                            status_view = [
                                f'{indent}    <View',
                                f'{indent}        android:layout_width="{dot}dp"',
                                f'{indent}        android:layout_height="{dot}dp"',
                                f'{indent}        android:layout_gravity="bottom|end"',
                                f'{indent}        android:background="@drawable/{status_drawable}" />',
                            ]
                        comp_lines += [
                            f'{indent}<FrameLayout',
                            f'{indent}    android:layout_width="{size}dp"',
                            f'{indent}    android:layout_height="{size}dp"{margin_xml}{layout_gravity_xml}>',
                            f'{indent}    <com.google.android.material.imageview.ShapeableImageView',
                            f'{indent}        xmlns:app="http://schemas.android.com/apk/res-auto"',
                            f'{indent}        android:id="@+id/img{counters["img"]}"',
                            f'{indent}        android:layout_width="match_parent"',
                            f'{indent}        android:layout_height="match_parent"{src_attr}',
                            # describe= reached every image but the avatar: a
                            # story ring was a nameless button to TalkBack.
                            f'{indent}        android:scaleType="{scale_type}"{crop_attr}{alpha_attr}{elevation_attr}{stroke_color_attr}{stroke_width_attr}{shape_attr}{_describe_xml(comp, indent + "    ")} />',
                            *status_view,
                            f'{indent}</FrameLayout>',
                            '',
                        ]
                        continue
                    comp_lines += [
                        f'{indent}<com.google.android.material.imageview.ShapeableImageView',
                        f'{indent}    xmlns:app="http://schemas.android.com/apk/res-auto"',
                        f'{indent}    android:id="@+id/img{counters["img"]}"',
                        f'{indent}    android:layout_width="{w_attr}"',
                        f'{indent}    android:layout_height="{h_attr}"{margin_xml}{layout_gravity_xml}{src_attr}',
                        f'{indent}    android:scaleType="{scale_type}"{crop_attr}{alpha_attr}{elevation_attr}{stroke_color_attr}{stroke_width_attr}{shape_attr}{_describe_xml(comp, indent)} />',
                        '',
                    ]
                else:
                    comp_lines += [
                        f'{indent}<ImageView',
                        f'{indent}    android:id="@+id/img{counters["img"]}"',
                        f'{indent}    android:layout_width="{w_attr}"',
                        f'{indent}    android:layout_height="{h_attr}"{margin_xml}{layout_gravity_xml}{src_attr}',
                        f'{indent}    android:scaleType="{scale_type}"{crop_attr}{alpha_attr}{elevation_attr}{_describe_xml(comp, indent)} />',
                        '',
                    ]

            elif ctype == 'camera_view':
                counters['camera_view'] += 1
                jv = comp.get('_java_var') or f'cameraView{counters["camera_view"]}'
                width = _parse_image_dim_android(comp_style.get('width')) if comp_style.get('width') else 'match_parent'
                height = _parse_image_dim_android(comp_style.get('height')) if comp_style.get('height') else '280dp'
                comp_lines += [f'{indent}<{package}.ApkpyCameraView android:id="@+id/{jv}"',
                               f'{indent}    android:layout_width="{width}" android:layout_height="{height}"{margin_xml}{layout_gravity_xml} />', '']

            elif ctype == 'video':
                counters['video'] += 1
                jv = comp.get('_java_var') or f'video{counters["video"]}'
                w_attr = _parse_image_dim_android(comp_style.get('width'))
                h_attr = _parse_image_dim_android(comp_style.get('height'))
                if not comp_style.get('width'):
                    w_attr = 'match_parent'
                if not comp_style.get('height'):
                    h_attr = '220dp'
                fit_map = {
                    'contain': 'fit',
                    'cover': 'zoom',
                    'fill': 'fill',
                }
                resize_mode = fit_map.get(comp.get('fit'), 'fit')
                use_controller = (
                    'true' if comp.get('controls', True) else 'false'
                )
                background = (
                    _resolve_color(_get_style_bg(comp_style))
                    if _get_style_bg(comp_style) else '#000000'
                )
                poster = comp.get('poster')
                poster_attr = ''
                if poster and not str(poster).startswith(('http://', 'https://')):
                    poster_name = _android_drawable_name(poster)
                    poster_attr = (
                        f'\n{indent}    app:default_artwork='
                        f'"@drawable/{poster_name}"'
                    )
                comp_lines += [
                    f'{indent}<androidx.media3.ui.PlayerView',
                    f'{indent}    android:id="@+id/{jv}"',
                    f'{indent}    android:layout_width="{w_attr}"',
                    f'{indent}    android:layout_height="{h_attr}"'
                    f'{margin_xml}{layout_gravity_xml}',
                    f'{indent}    android:background="{_color_xml(background)}"',
                    f'{indent}    android:keepScreenOn="true"',
                    f'{indent}    app:keep_content_on_player_reset="true"',
                    f'{indent}    app:show_buffering="when_playing"',
                    f'{indent}    app:use_artwork="true"',
                    f'{indent}    app:use_controller="{use_controller}"',
                    f'{indent}    app:resize_mode="{resize_mode}"'
                    f'{poster_attr} />',
                    '',
                ]

            elif ctype == 'map':
                counters['map'] += 1
                jv = comp.get('_java_var') or f'map{counters["map"]}'
                raw_width = str(comp_style.get('width', '')).strip().lower()
                map_width = (
                    _parse_image_dim_android(comp_style.get('width'))
                    if raw_width and raw_width not in ('100%', 'match_parent', 'fill')
                    else 'match_parent'
                )
                map_height = (
                    _parse_image_dim_android(comp_style.get('height'))
                    if comp_style.get('height') else '290dp'
                )
                radius = max(0, _parse_radius(comp_style))
                clip_attr = (
                    f'\n{indent}    android:clipToOutline="true"'
                    if radius > 0 else ''
                )
                comp_lines += [
                    f'{indent}<{package}.ApkpyMapView',
                    f'{indent}    android:id="@+id/{jv}"',
                    f'{indent}    android:layout_width="{map_width}"',
                    f'{indent}    android:layout_height="{map_height}"{margin_xml}{layout_gravity_xml}{clip_attr} />',
                    '',
                ]

            elif ctype in ('markdown', 'rich_text'):
                counters['rich'] += 1
                theme_tokens = styles.get('__theme__', {})
                # A colour of its own, else the screen's, else the one that
                # reads on what is under it (theme.content_ink), as the
                # Previewer draws it. It was #FAFAFA, a dark theme's: white
                # text on the light screen of an app without a Theme.
                # body's colour reaches it through the screen's, so that
                # content_ink can see whether it reads on what is under it.
                _rich_own = component_style(styles, ctype, comp_id, include_body=False,
                                            viewport=viewport)
                _ink = _content_ink(styles, _get_style_bg(_rich_own), _screen_ink_style,
                                    _ink_parents.get(id(comp)))
                payload = rich_content_feature.encoded_payload(
                    comp,
                    text_color=_resolve_color(
                        _get_style_fg(_rich_own) or _ink['text']
                    ),
                    secondary_color=_resolve_color(
                        comp_style.get('secondary-color') or comp_style.get('subtitle-color')
                        or _ink['muted']
                    ),
                    accent_color=_resolve_color(
                        comp_style.get('accent-color')
                        or theme_tokens.get('secondary')
                        or theme_tokens.get('primary', '#6750A4')
                    ),
                    background_color=_resolve_color(
                        _get_style_bg(comp_style) or '#00000000'
                    ),
                    border_color=_resolve_color(
                        comp_style.get('border-color')
                        or theme_tokens.get('border', '#00000000')
                    ),
                    border_width=_parse_border_width(comp_style),
                    radius=_parse_radius(comp_style),
                    padding=_parse_padding(comp_style),
                    font_size=_parse_font_size(comp_style) or 14,
                    copy_code=wants_code_copy(comp_style),
                )
                comp_lines += [
                    f'{indent}<{package}.ApkpyRichContentView',
                    f'{indent}    android:id="@+id/rich{counters["rich"]}"',
                    f'{indent}    android:layout_width="match_parent"',
                    f'{indent}    android:layout_height="wrap_content"{margin_xml}{layout_gravity_xml}',
                    f'{indent}    android:contentDescription="apkpy-rich:{payload}" />',
                    '',
                ]

            elif ctype == 'tree_view':
                counters['tree'] += 1
                theme_tokens = styles.get('__theme__', {})
                # body's colour reaches it through the screen's, so that
                # content_ink can see whether it reads on what is under it.
                _rich_own = component_style(styles, ctype, comp_id, include_body=False,
                                            viewport=viewport)
                _ink = _content_ink(styles, _get_style_bg(_rich_own), _screen_ink_style,
                                    _ink_parents.get(id(comp)))
                payload = rich_content_feature.encoded_payload(
                    comp,
                    text_color=_resolve_color(
                        _get_style_fg(_rich_own) or _ink['text']
                    ),
                    secondary_color=_resolve_color(
                        comp_style.get('secondary-color') or comp_style.get('subtitle-color')
                        or _ink['muted']
                    ),
                    accent_color=_resolve_color(
                        comp_style.get('accent-color')
                        or theme_tokens.get('secondary')
                        or theme_tokens.get('primary', '#6750A4')
                    ),
                    background_color=_resolve_color(
                        _get_style_bg(comp_style) or '#00000000'
                    ),
                    border_color=_resolve_color(
                        comp_style.get('border-color')
                        or theme_tokens.get('border', '#00000000')
                    ),
                    border_width=_parse_border_width(comp_style),
                    radius=_parse_radius(comp_style),
                    padding=_parse_padding(comp_style),
                    font_size=_parse_font_size(comp_style) or 14,
                )
                raw_h = comp_style.get('height')
                if raw_h:
                    tree_height = _parse_image_dim_android(raw_h)
                    tree_weight = ''
                elif scroll:
                    tree_height = '360dp'
                    tree_weight = ''
                else:
                    tree_height = '0dp'
                    tree_weight = f'\n{indent}    android:layout_weight="1"'
                comp_lines += [
                    f'{indent}<{package}.ApkpyTreeView',
                    f'{indent}    android:id="@+id/tree{counters["tree"]}"',
                    f'{indent}    android:layout_width="match_parent"',
                    f'{indent}    android:layout_height="{tree_height}"{tree_weight}{margin_xml}{layout_gravity_xml}',
                    f'{indent}    android:contentDescription="apkpy-tree:{payload}"',
                    f'{indent}    android:clipToPadding="false"',
                    f'{indent}    android:nestedScrollingEnabled="true"',
                    f'{indent}    android:overScrollMode="never" />',
                    '',
                ]

            elif ctype == 'list_view':
                counters['lst'] += 1
                # Altura: se o utilizador não definir `height`, a lista ajusta-se ao
                # conteúdo (wrap_content) — tal como o Previewer e como o README
                # recomenda. Só usa altura fixa quando explicitamente pedida.
                raw_h = comp_style.get('height')
                h_match = re.search(r'(\d+)', str(raw_h)) if raw_h is not None else None
                list_h_attr = f"{int(h_match.group(1))}dp" if h_match else "wrap_content"
                # Fundo: sem `background-color`, a lista fica transparente e herda o
                # fundo do ecrã (paridade com o Previewer, que usa `or bg_color`).
                # Antes era branco fixo → "caixas brancas" sobre ecrãs escuros.
                list_bg_style = _get_style_bg(comp_style)
                bg_hex      = _resolve_color(list_bg_style) if list_bg_style else '#00000000'
                divider_hex = _resolve_color(_get_style_border_color(comp_style) or '#E2E8F0')
                if divider_hex == '#d9d9d9':
                    divider_hex = '#E2E8F0'
                if scroll:
                    # Inside NestedScrollView: use LinearLayout container filled with TextViews at runtime
                    comp_lines += [
                        f'{indent}<LinearLayout',
                        f'{indent}    android:id="@+id/lst{counters["lst"]}_container"',
                        f'{indent}    android:layout_width="match_parent"',
                        f'{indent}    android:layout_height="wrap_content"{margin_xml}',
                        f'{indent}    android:orientation="vertical"',
                        f'{indent}    android:background="{_color_xml(bg_hex)}" />',
                        '',
                    ]
                else:
                    comp_lines += [
                        f'{indent}<ListView',
                        f'{indent}    android:id="@+id/lst{counters["lst"]}"',
                        f'{indent}    android:layout_width="match_parent"',
                        f'{indent}    android:layout_height="{list_h_attr}"{margin_xml}',
                        f'{indent}    android:background="{_color_xml(bg_hex)}"',
                        f'{indent}    android:divider="{_color_xml(divider_hex)}"',
                        f'{indent}    android:dividerHeight="1dp" />',
                        '',
                    ]

            elif ctype == 'virtual_collection':
                counters['vc'] += 1
                raw_h = comp_style.get('height')
                h_match = (
                    re.search(r'([0-9.]+)', str(raw_h))
                    if raw_h is not None else None
                )
                # height: auto -- as tall as its items, scrolling with the
                # screen: a profile's photo grid under its header. Every item
                # is laid out, so it is for tens of items, not thousands.
                grows_with_items = str(raw_h or '').strip().lower() == 'auto'
                if grows_with_items:
                    collection_h = 'wrap_content'
                    weight_attr = ''
                elif h_match:
                    collection_h = f"{int(float(h_match.group(1)))}dp"
                    weight_attr = ''
                elif scroll:
                    # Evita uma RecyclerView sem altura dentro de NestedScrollView.
                    collection_h = '480dp'
                    weight_attr = ''
                else:
                    # Num ecrã normal ocupa o espaço restante sem criar todos os itens.
                    collection_h = '0dp'
                    weight_attr = f'\n{indent}    android:layout_weight="1"'
                collection_bg = _get_style_bg(comp_style)
                bg_attr = (
                    f'\n{indent}    android:background="{_color_xml(collection_bg)}"'
                    if collection_bg else ''
                )
                jv = f'vc{counters["vc"]}'
                paginated_xml = feeds_feature.layout_xml(
                    comp, jv, indent, collection_h, weight_attr,
                    margin_xml, bg_attr,
                )
                if paginated_xml is not None:
                    comp_lines += paginated_xml
                else:
                    comp_lines += [
                        f'{indent}<androidx.recyclerview.widget.RecyclerView',
                        f'{indent}    android:id="@+id/{jv}"',
                        f'{indent}    android:layout_width="match_parent"',
                        f'{indent}    android:layout_height="{collection_h}"{weight_attr}{margin_xml}{bg_attr}',
                        f'{indent}    android:clipToPadding="false"',
                        f'{indent}    android:nestedScrollingEnabled="{"false" if grows_with_items else "true"}"',
                        f'{indent}    android:overScrollMode="never" />',
                        '',
                    ]
                if comp.get('row'):
                    comp['_row_layout'] = _row_layout_name(screen_id, jv)
                    comp['_row_xml'] = _row_layout_xml(comp['row'], comp['_row_layout'] + '_')

            elif ctype == 'carousel':
                counters['car'] += 1
                # Carrossel horizontal: HorizontalScrollView + LinearLayout (row).
                # Os cartões são criados em runtime (onCreate). Aqui só o contentor.
                comp_lines += [
                    f'{indent}<HorizontalScrollView',
                    f'{indent}    android:id="@+id/car{counters["car"]}"',
                    f'{indent}    android:layout_width="match_parent"',
                    f'{indent}    android:layout_height="wrap_content"{margin_xml}',
                    f'{indent}    android:scrollbars="none">',
                    f'{indent}    <LinearLayout',
                    f'{indent}        android:id="@+id/car{counters["car"]}_row"',
                    f'{indent}        android:layout_width="wrap_content"',
                    f'{indent}        android:layout_height="wrap_content"',
                    f'{indent}        android:orientation="horizontal" />',
                    f'{indent}</HorizontalScrollView>',
                    '',
                ]

            elif ctype == 'grid':
                counters['grid'] += 1
                # Grelha: GridLayout com N colunas. Os cartões são criados em runtime
                # (onCreate), espalhados pelas colunas com peso igual.
                _gcols = int(comp.get('cols', 2) or 2)
                comp_lines += [
                    f'{indent}<GridLayout',
                    f'{indent}    android:id="@+id/grid{counters["grid"]}"',
                    f'{indent}    android:layout_width="match_parent"',
                    f'{indent}    android:layout_height="wrap_content"{margin_xml}',
                    f'{indent}    android:columnCount="{_gcols}" />',
                    '',
                ]

            elif ctype == 'spinner':
                counters['spin'] += 1
                # ProgressBar circular indeterminado (anima sozinho). Cor via
                # indeterminateTint; visibilidade inicial via `visible`.
                spin_color = _get_style_fg(comp_style)
                tint_attr  = f'\n{indent}    android:indeterminateTint="{_color_xml(spin_color)}"' if spin_color else ''
                sp_w = _parse_image_dim_android(comp_style.get('width'))  if comp_style.get('width')  else 'wrap_content'
                sp_h = _parse_image_dim_android(comp_style.get('height')) if comp_style.get('height') else 'wrap_content'
                vis_attr = 'gone' if not comp.get('visible', True) else 'visible'
                comp_lines += [
                    f'{indent}<ProgressBar',
                    f'{indent}    android:id="@+id/spin{counters["spin"]}"',
                    f'{indent}    style="?android:attr/progressBarStyle"',
                    f'{indent}    android:layout_width="{sp_w}"',
                    f'{indent}    android:layout_height="{sp_h}"{margin_xml}{layout_gravity_xml}',
                    f'{indent}    android:visibility="{vis_attr}"{tint_attr} />',
                    '',
                ]

            elif ctype == 'skeleton':
                counters['skeleton'] += 1
                variant = comp.get('variant', 'music_card')
                count = max(1, int(comp.get('count', 1)))
                vis_attr = 'visible' if comp.get('visible', True) else 'gone'
                shape = comp.get('_drawable', 'apkpy_skeleton_shape')
                comp_lines += [
                    f'{indent}<LinearLayout',
                    f'{indent}    android:id="@+id/skeleton{counters["skeleton"]}"',
                    f'{indent}    android:layout_width="match_parent"',
                    f'{indent}    android:layout_height="wrap_content"{margin_xml}',
                    f'{indent}    android:orientation="vertical"',
                    f'{indent}    android:visibility="{vis_attr}">',
                ]
                for index in range(count):
                    top = 0 if index == 0 else 12
                    if variant in ('music_card', 'list'):
                        avatar = 56 if variant == 'music_card' else 48
                        avatar_radius = ''
                        comp_lines += [
                            f'{indent}    <LinearLayout',
                            f'{indent}        android:layout_width="match_parent"',
                            f'{indent}        android:layout_height="{72 if variant == "music_card" else 64}dp"',
                            f'{indent}        android:layout_marginTop="{top}dp"',
                            f'{indent}        android:gravity="center_vertical"',
                            f'{indent}        android:orientation="horizontal">',
                            f'{indent}        <View',
                            f'{indent}            android:layout_width="{avatar}dp"',
                            f'{indent}            android:layout_height="{avatar}dp"',
                            f'{indent}            android:background="@drawable/{shape}" />',
                            f'{indent}        <LinearLayout',
                            f'{indent}            android:layout_width="0dp"',
                            f'{indent}            android:layout_height="wrap_content"',
                            f'{indent}            android:layout_marginLeft="16dp"',
                            f'{indent}            android:layout_weight="1"',
                            f'{indent}            android:orientation="vertical">',
                            f'{indent}            <View',
                            f'{indent}                android:layout_width="match_parent"',
                            f'{indent}                android:layout_height="14dp"',
                            f'{indent}                android:layout_marginRight="48dp"',
                            f'{indent}                android:background="@drawable/{shape}" />',
                            f'{indent}            <View',
                            f'{indent}                android:layout_width="160dp"',
                            f'{indent}                android:layout_height="11dp"',
                            f'{indent}                android:layout_marginTop="12dp"',
                            f'{indent}                android:background="@drawable/{shape}" />',
                            f'{indent}        </LinearLayout>',
                            f'{indent}    </LinearLayout>',
                        ]
                    elif variant == 'card':
                        comp_lines += [
                            f'{indent}    <LinearLayout',
                            f'{indent}        android:layout_width="match_parent"',
                            f'{indent}        android:layout_height="wrap_content"',
                            f'{indent}        android:layout_marginTop="{top}dp"',
                            f'{indent}        android:orientation="vertical">',
                            f'{indent}        <View',
                            f'{indent}            android:layout_width="match_parent"',
                            f'{indent}            android:layout_height="124dp"',
                            f'{indent}            android:background="@drawable/{shape}" />',
                            f'{indent}        <View',
                            f'{indent}            android:layout_width="240dp"',
                            f'{indent}            android:layout_height="16dp"',
                            f'{indent}            android:layout_marginTop="18dp"',
                            f'{indent}            android:background="@drawable/{shape}" />',
                            f'{indent}        <View',
                            f'{indent}            android:layout_width="160dp"',
                            f'{indent}            android:layout_height="12dp"',
                            f'{indent}            android:layout_marginTop="14dp"',
                            f'{indent}            android:background="@drawable/{shape}" />',
                            f'{indent}    </LinearLayout>',
                        ]
                    else:
                        right = (24, 72, 128)[index % 3]
                        comp_lines += [
                            f'{indent}    <View',
                            f'{indent}        android:layout_width="match_parent"',
                            f'{indent}        android:layout_height="14dp"',
                            f'{indent}        android:layout_marginTop="{top if index else 3}dp"',
                            f'{indent}        android:layout_marginRight="{right}dp"',
                            f'{indent}        android:background="@drawable/{shape}" />',
                        ]
                comp_lines += [f'{indent}</LinearLayout>', '']

            elif ctype in ('empty_state', 'error_state'):
                counters['state'] += 1
                vis_attr = 'visible' if comp.get('visible', True) else 'gone'
                state_bg = _get_style_bg(comp_style)
                state_bg_attr = (
                    f'\n{indent}    android:background="{_color_xml(state_bg)}"'
                    if state_bg and str(state_bg).lower() not in ('transparent', '#00000000')
                    else ''
                )
                state_fg = _resolve_color(
                    _get_style_fg(comp_style)
                    or styles.get('__theme__', {}).get('text', '#1D1B20')
                )
                secondary_fg = _resolve_color(
                    styles.get('__theme__', {}).get('text_secondary', '#49454F')
                )
                pad = _parse_padding(comp_style)
                icon_drawable = comp.get('_state_icon_drawable', 'ic_state_default')
                comp_lines += [
                    f'{indent}<LinearLayout',
                    f'{indent}    android:id="@+id/state{counters["state"]}"',
                    f'{indent}    android:layout_width="match_parent"',
                    f'{indent}    android:layout_height="wrap_content"{margin_xml}',
                    f'{indent}    android:minHeight="300dp"',
                    f'{indent}    android:gravity="center"',
                    f'{indent}    android:orientation="vertical"',
                    f'{indent}    android:paddingLeft="{pad[3]}dp"',
                    f'{indent}    android:paddingTop="{pad[0]}dp"',
                    f'{indent}    android:paddingRight="{pad[1]}dp"',
                    f'{indent}    android:paddingBottom="{pad[2]}dp"',
                    f'{indent}    android:visibility="{vis_attr}"{state_bg_attr}>',
                    f'{indent}    <ImageView',
                    f'{indent}        android:layout_width="64dp"',
                    f'{indent}        android:layout_height="64dp"',
                    f'{indent}        android:contentDescription="{_xml_escape(comp.get("title", ""))}"',
                    f'{indent}        android:src="@drawable/{icon_drawable}" />',
                    f'{indent}    <TextView',
                    f'{indent}        android:layout_width="match_parent"',
                    f'{indent}        android:layout_height="wrap_content"',
                    f'{indent}        android:layout_marginTop="16dp"',
                    f'{indent}        android:gravity="center"',
                    f'{indent}        android:text="{_xml_escape(comp.get("title", ""))}"',
                    f'{indent}        android:textColor="{_color_xml(state_fg)}"',
                    f'{indent}        android:textSize="20sp"',
                    f'{indent}        android:textStyle="bold" />',
                ]
                if comp.get('message'):
                    comp_lines += [
                        f'{indent}    <TextView',
                        f'{indent}        android:layout_width="match_parent"',
                        f'{indent}        android:layout_height="wrap_content"',
                        f'{indent}        android:layout_marginTop="8dp"',
                        f'{indent}        android:gravity="center"',
                        f'{indent}        android:text="{_xml_escape(comp.get("message", ""))}"',
                        f'{indent}        android:textColor="{_color_xml(secondary_fg)}"',
                        f'{indent}        android:textSize="14sp" />',
                    ]
                if comp.get('children'):
                    comp_lines += [
                        f'{indent}    <View',
                        f'{indent}        android:layout_width="1dp"',
                        f'{indent}        android:layout_height="16dp" />',
                    ]
                    comp_lines += _generate_xml_for_comp(
                        comp['children'], 'vertical', 10, indent + '    ',
                    )
                comp_lines += [f'{indent}</LinearLayout>', '']

        return comp_lines

    if app_bar_info:
        bar_type = app_bar_info.get('type', 'app_bar')
        bar_style = component_style(
            styles, bar_type, app_bar_info.get('id'), viewport=viewport,
        )
        bar_bg, bar_fg = _app_bar_colors(styles, bar_style)
        title = _xml_escape(app_bar_info.get('title', ''))
        # The toolbar title picks up a registered typeface through a text
        # appearance -- MaterialToolbar draws its own TextView, so there is
        # no view in the layout to put app:fontFamily on.
        bar_font = _android_font_resource(bar_style)
        title_appearance = (
            ' app:titleTextAppearance="@style/ApkpyFont_%s"'
            % bar_font.split('/')[-1] if bar_font else ''
        )
        # text-align on the bar centres the title. Material centres it in
        # the whole toolbar, which is what the Previewer copies.
        if _resolve_text_align(bar_style.get('text-align')) == 'center':
            title_appearance += ' app:titleCentered="true"'
        leading = app_bar_info.get('leading') or {}
        nav_icon = (
            f'\n                app:navigationIcon="@drawable/{leading.get("_drawable")}"'
            if leading.get('_drawable') else ''
        )
        menu_attr = (
            f'\n                app:menu="@menu/app_bar_{_safe_android_id(screen_id, "screen")}_menu"'
            if app_bar_info.get('actions') else ''
        )
        content_above = f'\n        android:layout_above="@id/{_above_id}"' if _above_id else ''
        lines = [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<RelativeLayout xmlns:android="http://schemas.android.com/apk/res/android"',
            '    xmlns:app="http://schemas.android.com/apk/res-auto"',
            '    android:layout_width="match_parent"',
            # No fitsSystemWindows: the Activity gives this root the sides
            # and the bottom of the system bars (and the keyboard), and the
            # top goes to the MaterialToolbar, which grows under the status
            # bar in its own colour, as the Previewer draws it. With the root
            # fitted, the toolbar saw zero and the strip above it kept the
            # screen's colour: a light band over a dark bar.
            f'    android:layout_height="match_parent"{screen_bg_attr}>',
        ]
        if has_bg:
            lines += [
                '    <ImageView',
                '        android:layout_width="match_parent"',
                '        android:layout_height="match_parent"',
                f'        android:src="@drawable/screen_{screen_id}_bg"',
                '        android:scaleType="centerCrop" />',
            ]
        lines += [
            '    <androidx.coordinatorlayout.widget.CoordinatorLayout',
            '        android:id="@+id/apkpy_appbar_content"',
            '        android:layout_width="match_parent"',
            f'        android:layout_height="match_parent"{content_above}>',
            '        <com.google.android.material.appbar.AppBarLayout',
            '            android:layout_width="match_parent"',
            '            android:layout_height="wrap_content"',
            f'            android:background="{_color_xml(bar_bg)}">',
        ]
        if bar_type == 'sliver_app_bar':
            expanded_height = max(72, int(app_bar_info.get('expanded_height', 240)))
            pinned = bool(app_bar_info.get('pinned', True))
            collapse_mode = 'pin' if pinned else 'parallax'
            image = app_bar_info.get('image') or ''
            image_src = ''
            if image and not app_bar_info.get('_is_remote'):
                base = os.path.splitext(os.path.basename(str(image)))[0]
                safe = re.sub(r'[^a-z0-9_]', '_', base.lower())
                if safe and not safe[0].isalpha():
                    safe = 'img_' + safe
                image_src = f'\n                    android:src="@drawable/{safe}"'
            lines += [
                '            <com.google.android.material.appbar.CollapsingToolbarLayout',
                '                android:id="@+id/apkpy_collapsing_toolbar"',
                '                android:layout_width="match_parent"',
                f'                android:layout_height="{expanded_height}dp"',
                '                android:minHeight="72dp"',
                '                app:layout_scrollFlags="scroll|exitUntilCollapsed"',
                f'                app:contentScrim="{bar_bg}"',
                '                app:titleEnabled="false">',
                '                <ImageView',
                '                    android:id="@+id/apkpy_appbar_image"',
                '                    android:layout_width="match_parent"',
                f'                    android:layout_height="{expanded_height}dp"',
                f'                    android:contentDescription="{title}"',
                f'                    android:scaleType="centerCrop"{image_src}',
                '                    app:layout_collapseMode="parallax"',
                '                    app:layout_collapseParallaxMultiplier="0.7" />',
                '                <com.google.android.material.appbar.MaterialToolbar',
                '                    android:id="@+id/apkpy_toolbar"',
                '                    android:layout_width="match_parent"',
                '                    android:layout_height="48dp"',
                '                    android:layout_gravity="bottom"',
                f'                    android:background="{_color_xml(bar_bg)}"',
                f'                    app:title="{title}"',
                f'                    app:titleTextColor="{_color_xml(bar_fg)}"{title_appearance}',
                f'                    app:navigationIconTint="{_color_xml(bar_fg)}"{nav_icon}{menu_attr}',
                f'                    app:layout_collapseMode="{collapse_mode}" />',
                '            </com.google.android.material.appbar.CollapsingToolbarLayout>',
            ]
        else:
            lines += [
                '            <com.google.android.material.appbar.MaterialToolbar',
                '                android:id="@+id/apkpy_toolbar"',
                '                android:layout_width="match_parent"',
                '                android:layout_height="48dp"',
                f'                android:background="{_color_xml(bar_bg)}"',
                f'                app:title="{title}"',
                f'                app:titleTextColor="{_color_xml(bar_fg)}"{title_appearance}',
                f'                app:navigationIconTint="{_color_xml(bar_fg)}"{nav_icon}{menu_attr} />',
            ]
        lines += [
            '        </com.google.android.material.appbar.AppBarLayout>',
            '        <androidx.core.widget.NestedScrollView',
            '            android:layout_width="match_parent"',
            '            android:layout_height="match_parent"',
            '            android:fillViewport="true"',
            '            app:layout_behavior="@string/appbar_scrolling_view_behavior">',
            '            <LinearLayout',
            '                android:layout_width="match_parent"',
            '                android:layout_height="wrap_content"',
            f'                android:orientation="{orientation}"{c_grav}',
            f'                {pad_str}>',
            '',
        ]

    overlay_lines = []
    lines += _generate_xml_for_comp(
        components, orientation, gap, parent_is_flex=screen_is_flex,
        overlay_sink=overlay_lines, overlay_indent='        ',
    )

    def _overlay_xml(indent='    ', above=''):
        """`position: absolute` on a screen's own child: a layer over the
        content, fixed like a floating button, with the same placement rules
        as an absolute child of a container. It was laid out in the column
        with everything else -- no floating button, no bar pinned to the
        bottom. Touches that land on no child fall through to the content."""
        if not overlay_lines:
            return []
        return [
            f'{indent}<com.apkpy.app.ApkpyLayout',
            f'{indent}    android:id="@+id/apkpy_overlay"',
            f'{indent}    android:layout_width="match_parent"',
            f'{indent}    android:layout_height="match_parent"{above}',
            f'{indent}    android:tag="{_SCREEN_OVERLAY_TAG}"',
            f'{indent}    android:clipChildren="false">',
            '',
        ] + overlay_lines + [f'{indent}</com.apkpy.app.ApkpyLayout>', '']

    _theme_tokens = styles.get('__theme__', {})
    # The same rule the Previewer draws the bar with (theme.nav_colors).
    _nav_bg = _resolve_color(_nav_look(styles)['bar'])
    _nav_float = _nav_look(styles) if (bnav and _nav_look(styles)['floating']) else None
    _mp_bg, _mp_text, _mp_muted = (_resolve_color(c) for c in mini_player_colors(
        _theme_tokens, component_style(styles, 'mini_player',
                                       (mini_player_info or {}).get('id'),
                                       include_body=False)))

    # BottomNavigationView snippet (reused below)
    def _bnav_xml(indent='    '):
        return [
            f'{indent}<com.google.android.material.bottomnavigation.BottomNavigationView',
            f'{indent}    android:id="@+id/bottom_nav"',
            f'{indent}    android:layout_width="match_parent"',
            f'{indent}    android:layout_height="wrap_content"',
            f'{indent}    android:layout_alignParentBottom="true"',
            *([f'{indent}    android:layout_marginLeft="{int(_nav_float["margin"])}dp"',
               f'{indent}    android:layout_marginRight="{int(_nav_float["margin"])}dp"',
               f'{indent}    android:layout_marginBottom="{int(_nav_float["margin"])}dp"',
               f'{indent}    android:background="@drawable/apkpy_nav_bar"',
               # Material's 8dp shadow shows through a see-through bar.
               f'{indent}    app:elevation="0dp"']
              if _nav_float else
              [f'{indent}    android:background="{_color_xml(_nav_bg)}"']),
            f'{indent}    app:itemIconTint="@color/nav_item_color"',
            *([f'{indent}    app:itemActiveIndicatorStyle="@style/ApkpyNavIndicator"']
              if (bottom_nav_info or {}).get('indicator', 'pill') == 'pill' else []),
            f'{indent}    app:itemTextColor="@color/nav_item_color"',
            # The pill is 32dp around a 24dp icon; with the Material 2 bar's
            # own spacing it covered the top of the label on a phone. These
            # put the label below the pill, and give the bar the height what
            # it carries adds up to -- the Previewer's. Without minHeight the
            # M2 bar stays 56dp and the label sits on its bottom edge. The
            # gesture inset is added below it (see the onCreate listener).
            f'{indent}    android:minHeight="{NAV_BAR_DP}dp"',
            f'{indent}    app:itemPaddingTop="{NAV_ITEM_PAD_DP}dp"',
            f'{indent}    app:itemPaddingBottom="{NAV_ITEM_PAD_DP}dp"',
            f'{indent}    app:activeIndicatorLabelPadding="{NAV_LABEL_GAP_DP}dp"',
            # Material's own default, written down so the Previewer's rule and
            # the phone's cannot drift apart on a library upgrade.
            f'{indent}    app:itemTextAppearanceActiveBoldEnabled='
            f'"{str(NAV_ACTIVE_LABEL_BOLD).lower()}"',
            f'{indent}    app:labelVisibilityMode="labeled"',
            f'{indent}    app:menu="@menu/bottom_nav_menu" />',
        ]

    # Mini-player fixo: barra ancorada em baixo (acima do bottom_nav, se houver).
    # Começa escondida (visibility=gone); o onCreate mostra-a quando há música.
    def _miniplayer_xml(indent='    '):
        mp_anchor = (f'\n{indent}    android:layout_above="@id/bottom_nav"' if bnav
                     else f'\n{indent}    android:layout_alignParentBottom="true"')
        return [
            f'{indent}<LinearLayout',
            f'{indent}    android:id="@+id/apkpy_miniplayer"',
            f'{indent}    android:layout_width="match_parent"',
            f'{indent}    android:layout_height="wrap_content"{mp_anchor}',
            f'{indent}    android:orientation="horizontal"',
            f'{indent}    android:gravity="center_vertical"',
            f'{indent}    android:background="{_color_xml(_mp_bg)}"',
            f'{indent}    android:padding="8dp"',
            f'{indent}    android:visibility="gone">',
            f'{indent}    <ImageView',
            f'{indent}        android:id="@+id/apkpy_mp_cover"',
            f'{indent}        android:layout_width="48dp"',
            f'{indent}        android:layout_height="48dp"',
            f'{indent}        android:scaleType="centerCrop" />',
            f'{indent}    <LinearLayout',
            f'{indent}        android:layout_width="0dp"',
            f'{indent}        android:layout_height="wrap_content"',
            f'{indent}        android:layout_weight="1"',
            f'{indent}        android:orientation="vertical"',
            f'{indent}        android:paddingLeft="10dp"',
            f'{indent}        android:paddingRight="10dp">',
            f'{indent}        <TextView',
            f'{indent}            android:id="@+id/apkpy_mp_title"',
            f'{indent}            android:layout_width="match_parent"',
            f'{indent}            android:layout_height="wrap_content"',
            f'{indent}            android:textColor="{_color_xml(_mp_text)}"',
            f'{indent}            android:textStyle="bold"',
            f'{indent}            android:textSize="14sp"',
            f'{indent}            android:singleLine="true"',
            f'{indent}            android:ellipsize="end" />',
            f'{indent}        <TextView',
            f'{indent}            android:id="@+id/apkpy_mp_artist"',
            f'{indent}            android:layout_width="match_parent"',
            f'{indent}            android:layout_height="wrap_content"',
            f'{indent}            android:textColor="{_color_xml(_mp_muted)}"',
            f'{indent}            android:textSize="12sp"',
            f'{indent}            android:singleLine="true"',
            f'{indent}            android:ellipsize="end" />',
            f'{indent}    </LinearLayout>',
            f'{indent}    <Button',
            f'{indent}        android:id="@+id/apkpy_mp_pp"',
            f'{indent}        android:layout_width="48dp"',
            f'{indent}        android:layout_height="48dp"',
            f'{indent}        android:minWidth="0dp"',
            f'{indent}        android:minHeight="0dp"',
            f'{indent}        android:padding="0dp"',
            f'{indent}        android:text=""',
            f'{indent}        android:contentDescription="Play or pause"',
            f'{indent}        app:icon="@drawable/apkpy_mp_pause"',
            f'{indent}        app:iconSize="26dp"',
            f'{indent}        app:iconPadding="0dp"',
            f'{indent}        app:iconGravity="textStart"',
            f'{indent}        app:iconTint="@null"',
            f'{indent}        android:background="@android:color/transparent"',
            f'{indent}        android:backgroundTint="@null"',
            f'{indent}        app:backgroundTint="@null" />',
            f'{indent}</LinearLayout>',
        ]

    if app_bar_info:
        lines.append('            </LinearLayout>')
        lines.append('        </androidx.core.widget.NestedScrollView>')
        lines.append('    </androidx.coordinatorlayout.widget.CoordinatorLayout>')
        lines += _overlay_xml('    ', bnav_above_outer)
        if mp:
            lines += _miniplayer_xml('    ')
        if bnav:
            lines += _bnav_xml('    ')
        lines.append('</RelativeLayout>')
    elif has_bg:
        indent_close = '        ' if scroll else '    '
        lines.append(f'{indent_close}</LinearLayout>')
        if scroll:
            lines.append('    </androidx.core.widget.NestedScrollView>')
        lines += _overlay_xml('    ', bnav_above_outer)
        if mp:
            lines += _miniplayer_xml('    ')
        if bnav:
            lines += _bnav_xml('    ')
        lines.append('</RelativeLayout>')
    else:
        if _relative:
            if scroll:
                lines.append('    </LinearLayout>')
                lines.append('    </androidx.core.widget.NestedScrollView>')
            else:
                lines.append('    </LinearLayout>')
            lines += _overlay_xml('    ', bnav_above_outer)
            if mp:
                lines += _miniplayer_xml('    ')
            if bnav:
                lines += _bnav_xml('    ')
            lines.append('</RelativeLayout>')
        elif scroll:
            lines.append('    </LinearLayout>')
            lines.append('</androidx.core.widget.NestedScrollView>')
        else:
            lines.append('    </LinearLayout>')
            # The root is a FrameLayout already: a layer goes straight in.
            lines += _overlay_xml('    ')
            lines.append('</FrameLayout>')
        if overlay_lines and not _relative and scroll:
            # These two roots cannot hold a layer: a FrameLayout holds both.
            # It fits the system windows and carries the screen colour, so the
            # strip under the status bar keeps it.
            lines[1:1] = [
                f'<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"{xmlns_app}',
                '    android:layout_width="match_parent"',
                '    android:layout_height="match_parent"',
                f'    android:fitsSystemWindows="true"{screen_bg_attr}>',
                '',
            ]
            lines += _overlay_xml('    ')
            lines.append('</FrameLayout>')
    return "\n".join(lines)


def _generate_list_row_xml():
    """Layout de uma linha rica de list_view: miniatura (ImageView) + título +
    subtítulo. Usado pelo adapter quando list_view(... rich=True) ou os itens
    trazem "image"."""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"\n'
        '    android:layout_width="match_parent"\n'
        '    android:layout_height="wrap_content"\n'
        '    android:orientation="horizontal"\n'
        '    android:gravity="center_vertical"\n'
        '    android:paddingLeft="14dp"\n'
        '    android:paddingRight="14dp"\n'
        '    android:paddingTop="8dp"\n'
        '    android:paddingBottom="8dp">\n'
        '    <ImageView\n'
        '        android:id="@+id/apkpy_row_img"\n'
        '        android:layout_width="56dp"\n'
        '        android:layout_height="56dp"\n'
        '        android:scaleType="centerCrop"\n'
        '        android:background="#1E293B" />\n'
        '    <LinearLayout\n'
        '        android:layout_width="0dp"\n'
        '        android:layout_height="wrap_content"\n'
        '        android:layout_weight="1"\n'
        '        android:orientation="vertical"\n'
        '        android:layout_marginLeft="12dp">\n'
        '        <TextView\n'
        '            android:id="@+id/apkpy_row_title"\n'
        '            android:layout_width="match_parent"\n'
        '            android:layout_height="wrap_content"\n'
        '            android:textSize="16sp"\n'
        '            android:textColor="#F8FAFC"\n'
        '            android:maxLines="1"\n'
        '            android:ellipsize="end" />\n'
        '        <TextView\n'
        '            android:id="@+id/apkpy_row_sub"\n'
        '            android:layout_width="match_parent"\n'
        '            android:layout_height="wrap_content"\n'
        '            android:textSize="13sp"\n'
        '            android:textColor="#94A3B8"\n'
        '            android:maxLines="1"\n'
        '            android:ellipsize="end" />\n'
        '    </LinearLayout>\n'
        '</LinearLayout>\n'
    )
