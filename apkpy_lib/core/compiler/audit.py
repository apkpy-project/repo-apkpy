"""What the build says about contrast and labels before the app reaches a phone."""
from ... import choice_rules as _choice_rules
from ...theme import component_style
from ..features import accessibility as accessibility_feature
from ..css_colors import over as _css_over

from .style import (
    _content_ink, _get_style_bg, _get_style_fg, _ink_parent_backgrounds, _parse_font_size,
    _resolve_color,
)


def _is_see_through(colour):
    raw = str(colour or '').strip().lower()
    if raw in ('transparent', 'none'):
        return True
    if raw.startswith('#') and len(raw) == 9:
        return raw[1:3] == '00'
    if raw.startswith('#') and len(raw) == 5:
        return raw[1] == '0'
    return False


def _audit_accessibility(screen_components, styles):
    """Everything a screen reader or a low-vision user would trip over.

    Run once over the whole app rather than per screen, so the same shared
    component is not reported five times, and reported rather than refused --
    see :func:`accessibility.report` for why.
    """
    findings = []
    theme = (styles or {}).get('__theme__', {}) or {}
    body = (styles or {}).get('body', {}) or {}
    page_background = (_get_style_bg(body) or theme.get('background')
                       or '#FFFFFF')

    def is_absolute(comp):
        return str(component_style(styles, comp.get('comp_type'), comp.get('id')).get(
            'position', '')).strip().lower() == 'absolute'

    def walk(components, screen_id, behind, over_picture=False):
        """*behind* is the nearest background an ancestor actually paints.

        Reading only body/theme said white for every app that paints its
        background on the screen itself -- and then reported white-on-white,
        1.05:1, for text that is perfectly legible. A check that cries wolf
        gets switched off, so the background has to be the real one.

        *over_picture*: the component sits, position: absolute, over an image
        in the same container. What is behind its text is the picture, which
        no colour stands for -- white words over a dusk photo were reported
        at 1.07:1 against the page (Northline, 14-11-2026).
        """
        siblings = [c for c in components or [] if isinstance(c, dict)]
        picture = any(c.get('comp_type') == 'image' and not is_absolute(c)
                      for c in siblings)
        for comp in components or []:
            if not isinstance(comp, dict):
                continue
            kind = comp.get('comp_type')
            where = '%s.%s' % (screen_id, comp.get('id') or kind)

            if accessibility_feature.needs_a_label(comp):
                findings.append((
                    kind, where,
                    'nothing to announce. Add describe="..." , or describe="" '
                    'if it is decoration.'))

            style = component_style(styles, kind, comp.get('id'),
                                    variant=comp.get('variant'))
            # What this component paints *itself*. The cascade starts at
            # ``body``, which carries the theme's page background, so reading
            # the merged style said every label was sitting on the page --
            # `or behind` never ran and a card's own colour was never used.
            own = component_style(styles, kind, comp.get('id'),
                                  include_body=False,
                                  variant=comp.get('variant'))
            own_background = _get_style_bg(own)
            see_through = _is_see_through(own_background)
            if see_through:
                # #00000000 paints nothing: what is behind shows. Read as the
                # colour 000000 it put black behind every label in a
                # transparent row -- "1.00:1" for black text on white.
                own_background = None
            elif own_background and behind:
                # Glass (rgba(), #RRGGBBAA): what shows is its colour over
                # what is behind. Read at full strength, white text on a
                # translucent white card on a red screen was "1.00:1".
                own_background = _css_over(_resolve_color(own_background),
                                           _resolve_color(behind))
            if kind in ('button', 'card_action', 'list_row'):
                small = accessibility_feature.touch_target_problem(style)
                if small:
                    findings.append((
                        kind, where,
                        '%s, under the %ddp a fingertip needs.'
                        % (small, accessibility_feature.MIN_TOUCH_DP)))

            if kind in _choice_rules.KINDS:
                # Two states to read: the words on an unselected chip (on its
                # fill, or whatever is behind it) and on a selected one.
                colours = _choice_rules.colors(kind, theme, own)
                size = _choice_rules.text_size(own)
                needed = accessibility_feature.required_contrast(size, False)
                for state, ink, paper in (
                        ('unselected', colours['text'], colours['fill'] or behind),
                        ('selected', colours['active_text'], colours['active_fill'])):
                    ratio = accessibility_feature.contrast_ratio(
                        _resolve_color(ink) if ink else None,
                        _resolve_color(paper) if paper else None)
                    if ratio is not None and ratio < needed:
                        findings.append((
                            kind, where,
                            '%s text is %.2f:1 against its fill; %gsp needs %.1f:1.'
                            % (state, ratio, size, needed)))

            # Words that paint their own fill (a pill, a white button) are
            # measured on it as usual.
            on_picture = ((over_picture or (picture and is_absolute(comp)))
                          and not own_background)
            icon_only = kind == 'button' and not str(comp.get('text') or '').strip()
            if on_picture:
                pass
            elif icon_only:
                # A button with only an icon has no text to measure: it was
                # reported as "text is 1.00:1". The icon is what must stand
                # out, against the 3:1 WCAG asks of anything that is not text.
                icon_colour = style.get('icon-color') or style.get('tint')
                ratio = accessibility_feature.contrast_ratio(
                    _resolve_color(icon_colour) if icon_colour else None,
                    _resolve_color(own_background or behind) if (own_background or behind) else None)
                if ratio is not None and ratio < 3.0:
                    findings.append((
                        kind, where,
                        'icon is %.2f:1 against its background; an icon needs 3:1.'
                        % ratio))
            elif kind in ('label', 'button', 'card_action'):
                foreground = _get_style_fg(style) or theme.get('text')
                background = own_background or behind
                if kind == 'label' and not _get_style_fg(own):
                    # The colour the layout writes (theme.content_ink): the
                    # screen's or the Theme's while it reads, else the ink.
                    # Read as the Theme's text, a label on a screen made
                    # dark with `color:` was reported at 1.14:1.
                    background = own_background or parents.get(id(comp)) or behind
                    foreground = _content_ink(
                        styles, own_background, screen_style,
                        parents.get(id(comp)))['text']
                elif kind == 'button' and not own_background and not see_through:
                    # Material fills a button that names no colour with the
                    # primary and writes on it in on_primary. An outlined or
                    # text button is see-through on purpose: its primary words
                    # sit on what is behind, and read on the primary they were
                    # "1.00:1" (07-11-2026, examples/48_phone_extras.py).
                    background = theme.get('primary') or '#6750A4'
                    foreground = (_get_style_fg(style) or theme.get('on_primary')
                                  or '#FFFFFF')
                size = _parse_font_size(style) or 16
                bold = 'bold' in str(style.get('font-weight', '')).lower()
                # A text colour with alpha is what it shows over its background.
                if background:
                    background = _css_over(_resolve_color(background),
                                           _resolve_color(behind) if behind else None)
                ratio = accessibility_feature.contrast_ratio(
                    _css_over(_resolve_color(foreground), _resolve_color(background))
                    if foreground and background else
                    (_resolve_color(foreground) if foreground else None),
                    _resolve_color(background) if background else None)
                needed = accessibility_feature.required_contrast(size, bold)
                if ratio is not None and ratio < needed:
                    findings.append((
                        kind, where,
                        'text is %.2f:1 against its background; %gsp needs '
                        '%.1f:1.' % (ratio, size, needed)))

            walk(comp.get('children'), screen_id,
                 own_background or behind, on_picture)
            # A virtual_collection(row=...) keeps its row -- the components
            # every item is drawn from -- beside its children, and the audit
            # never looked there: a feed's heart with no describe= and its
            # grey caption on white went unreported.
            if isinstance(comp.get('row'), dict):
                walk([comp['row']], screen_id, own_background or behind)

    for screen_id, components in (screen_components or {}).items():
        screen_background = _get_style_bg(
            (styles or {}).get(screen_id, {}) or {}) or page_background
        screen_style = component_style(styles or {}, None, screen_id)
        parents = _ink_parent_backgrounds(components, styles or {})
        walk(components, screen_id, screen_background)
    return findings
