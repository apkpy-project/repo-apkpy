"""Small CSS parser shared by the Previewer and Android compiler."""

import re


MEDIA_RULE_PREFIX = "__media__|"


def _extract_balanced_at_rules(css_text, rule_name):
    """Remove and return balanced ``@rule (...) { ... }`` blocks."""
    blocks = []
    output = []
    cursor = 0
    pattern = re.compile(rf'@{re.escape(rule_name)}\b', re.I)
    while True:
        match = pattern.search(css_text, cursor)
        if match is None:
            output.append(css_text[cursor:])
            break
        output.append(css_text[cursor:match.start()])
        opening = css_text.find('{', match.end())
        if opening < 0:
            output.append(css_text[match.start():])
            break
        depth = 1
        index = opening + 1
        while index < len(css_text) and depth:
            if css_text[index] == '{':
                depth += 1
            elif css_text[index] == '}':
                depth -= 1
            index += 1
        if depth:
            output.append(css_text[match.start():])
            break
        header = css_text[match.end():opening].strip()
        blocks.append((header, css_text[opening + 1:index - 1]))
        cursor = index
    return ''.join(output), blocks


def _parse_style_blocks(css_text):
    parsed = []
    for selector_group, content in re.findall(r'([^{}]+)\{([^{}]*)\}', css_text):
        props = {}
        for key, value in re.findall(r'([\w-]+)\s*:\s*(.*?);', content):
            props[key.strip()] = value.strip()
        for selector in selector_group.split(','):
            # ``.name`` was already accepted; ``#name`` was not, so a
            # stylesheet written out of browser habit parsed cleanly, matched
            # nothing and left the screen unstyled with no message. An ApkPy
            # selector names a component id or a component type, and neither
            # sigil changes which one it is.
            selector = selector.strip().lstrip('.#').strip()
            if selector:
                parsed.append((selector, dict(props)))
    return parsed


def parse_css(css_text):
    styles = {}
    keyframes = {}

    # Comments must be removed before parsing selectors.
    css_text = re.sub(r'/\*.*?\*/', '', css_text, flags=re.S)

    # Keyframes allow one nested level: @keyframes name { from {...} to {...} }.
    kf_blocks = re.findall(
        r'@keyframes\s+(\w+)\s*\{((?:[^{}]*\{[^{}]*\})*[^{}]*)\}', css_text
    )
    for name, content in kf_blocks:
        kf_dict = {}
        for stage, props_str in re.findall(r'([a-zA-Z0-9%]+)\s*\{([^{}]*)\}', content):
            props = {}
            for key, value in re.findall(r'([\w-]+)\s*:\s*(.*?);', props_str):
                props[key.strip()] = value.strip()
            kf_dict[stage.strip()] = props
        keyframes[name.strip()] = kf_dict

    clean_css = re.sub(
        r'@keyframes\s+\w+\s*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}', '', css_text
    )
    clean_css, media_blocks = _extract_balanced_at_rules(clean_css, 'media')

    for selector, props in _parse_style_blocks(clean_css):
        styles.setdefault(selector, {}).update(props)

    # Reserved keys preserve the old dict-of-dicts return shape. Renderers can
    # resolve these rules against their viewport without breaking old projects.
    for order, (condition, content) in enumerate(media_blocks, start=1):
        for selector, props in _parse_style_blocks(content):
            key = f"{MEDIA_RULE_PREFIX}{order:04d}|{condition}|{selector}"
            styles[key] = props

    return styles, keyframes


# `code-copy: button;` puts a tappable "Copy" under every fenced code block.
# It lives here, next to the parser, because both renderers have to read the
# declaration the same way -- one of them reading "Button" and the other not
# is how a stylesheet ends up meaning two different things.
CODE_COPY_MODES = ("none", "button")


def wants_code_copy(style):
    """True when a stylesheet asks for the copy affordance on code blocks."""
    value = str((style or {}).get("code-copy", "")).strip().lower()
    return value == "button"


# --- The stylesheet vocabulary ----------------------------------------------
# Every property either renderer reads. A name that is not here is dropped when
# the layout is written, which looks exactly like the value not working -- so
# it is reported instead. The table lives next to the parser for the same
# reason CODE_COPY_MODES does: both renderers have to agree on what a
# stylesheet means, and a name one of them silently ignores is how a screen
# ends up looking different on the phone.

# The properties whose value is a colour and nothing else. Named separately
# because the theme resolver has to be able to tell `color: var(--text)` from
# `font-size: var(--text-lg)`: two tokens that differ by three characters, one
# of which means #1D1B20 and the other 16px.
COLOR_PROPERTIES = frozenset((
    'color', 'background-color', 'border-color',
    'pressed-color', 'focus-color', 'focus-border-color',
    'accent-color', 'active-color', 'hint-color', 'icon-color',
    'placeholder-color', 'secondary-color', 'subtitle-color', 'title-color',
    'trailing-color', 'meta-color', 'badge-color', 'badge-background-color',
    'item-background-color', 'item-border-color', 'item-border-radius', 'divider-color',
    'badge-position',
    'indicator-color', 'tint',
    'track-color', 'label-color', 'grid-color',
))

KNOWN_PROPERTIES = frozenset(COLOR_PROPERTIES | frozenset((
    # Type
    'font-size', 'font-weight', 'font-family', 'font-style', 'text-align',
    'text-transform', 'letter-spacing', 'line-height', 'title-lines',
    'subtitle-lines', 'subtitle-size', 'trailing-size', 'rows', 'max-rows',
    # Shape
    'border-width', 'border-radius', 'box-shadow', 'stroke-width',
    # Space
    'padding', 'padding-top', 'padding-right', 'padding-bottom',
    'padding-left', 'margin', 'margin-top', 'margin-right', 'margin-bottom',
    'margin-left', 'gap', 'divider-width', 'divider-inset',
    # Size
    'width', 'height', 'min-height', 'max-width',
    'aspect-ratio', 'icon-size', 'item-size',
    # Layout
    'display', 'flex-direction', 'flex-grow', 'flex-shrink', 'flex-basis',
    'flex-wrap', 'justify-content', 'align-items', 'align-self',
    'grid-template-columns', 'grid-column', 'grid-row',
    'position', 'top', 'right', 'bottom', 'left', 'z-index',
    # Media and effects
    'opacity', 'object-fit', 'filter', 'scale',
    # Behaviour
    'transition', 'press', 'code-copy', 'animation-name',
    'animation-duration',
)))

# What difflib will not find on its own, because the right answer is not a
# near-miss of the wrong one.
# ``None`` means say nothing: a browser property with no ApkPy equivalent is
# better answered with silence than with a near-miss that means something else
# entirely -- difflib happily offers `text-transform` for `transform`.
_PROPERTY_HINTS = {
    'elevation': 'box-shadow',
    'shadow': 'box-shadow',
    'background': 'background-color',
    'border': 'border-width',
    'font': 'font-size',
    'text-color': 'color',
    'radius': 'border-radius',
    'align': 'text-align',
    'weight': 'font-weight',
    # Removed from the vocabulary once measured: nothing read them, so the
    # table was promising behaviour the engine never had.
    'border-top-width': 'border-width',
    'border-left-width': 'border-width',
    'border-top-color': 'border-color',
    'border-left-color': 'border-color',
    'animation': 'animation-name',
    'min-width': 'width',
    'max-height': 'height',
    'align-content': None,
    'animation-delay': None,
    'animation-iteration-count': None,
    'transform': None,
    'overflow': None,
    'float': None,
    'cursor': None,
    'visibility': None,
    'box-sizing': None,
    'text-decoration': None,
    'text-shadow': None,
    'backdrop-filter': None,
    'outline': None,
}

_UNKNOWN_PROPERTIES_REPORTED = set()


def unknown_properties(styles, keyframes=None):
    """``[(property, selector)]`` for every name no renderer reads.

    First sighting only, in the order the stylesheet wrote them. Pure: the
    caller decides whether to report, which is what lets a test assert on the
    result without a warning reaching the terminal.
    """
    seen = set()
    found = []
    blocks = list((styles or {}).items())
    for name, stages in (keyframes or {}).items():
        for stage, props in stages.items():
            blocks.append(('@keyframes %s %s' % (name, stage), props))
    for selector, props in blocks:
        if selector.startswith('__'):
            # Reserved keys carry real declarations; the theme's own merged
            # block does not exist yet at the point this is called.
            selector = selector.split('|')[-1]
        for prop in props:
            if prop in KNOWN_PROPERTIES or prop in seen:
                continue
            seen.add(prop)
            found.append((prop, selector))
    return found


def report_unknown_properties(styles, keyframes=None):
    """Say so, once per name per process, and carry on building."""
    import difflib

    for prop, selector in unknown_properties(styles, keyframes):
        if prop in _UNKNOWN_PROPERTIES_REPORTED:
            continue
        _UNKNOWN_PROPERTIES_REPORTED.add(prop)
        if prop in _PROPERTY_HINTS:
            near = _PROPERTY_HINTS[prop]
        else:
            close = difflib.get_close_matches(prop, KNOWN_PROPERTIES, 1, 0.75)
            near = close[0] if close else None
        # Imported here: diagnostics is the layer above this one, and a
        # top-level import would tie the parser to it.
        from ..diagnostics import Diagnostic, report_diagnostic
        report_diagnostic(Diagnostic(
            code='U2029',
            title='This is not a property ApkPy reads',
            message='%s in %r was ignored.' % (prop, selector),
            cause=(
                'An ApkPy stylesheet is not a browser stylesheet. It has a '
                'fixed vocabulary of %d properties, and a name outside it is '
                'dropped when the layout is written -- which looks like the '
                'value not working rather than the name not existing, and is '
                'why it can go unnoticed.' % len(KNOWN_PROPERTIES)
            ),
            expected='a property from the ApkPy stylesheet vocabulary',
            received=repr(prop),
            suggestions=(
                (['Did you mean %s?' % near] if near else [])
                + ['Remove the line, or check the property table in the docs.']
            ),
            docs='https://repo-apkpy.pages.dev/themes-styling/',
        ))


# --- The component argument vocabulary --------------------------------------
# The same hole as KNOWN_PROPERTIES, one level up. ``image("p.png", blurr=8)``
# transpiled clean: the Previewer raises TypeError the moment it runs, but a
# person who goes straight to ``apkpy build`` never saw anything and shipped a
# blur that is not there.
#
# Generated from the real signatures. tests/features/test_argument_names.py
# rebuilds this from ``inspect.signature`` and fails if the two drift, so the
# table cannot quietly go stale the way a hand-written list would.
COMPONENT_ARGUMENTS = {
    'action': frozenset(('command', 'icon', 'id', 'label')),
    'app_bar': frozenset(('actions', 'id', 'leading', 'screen', 'title')),
    'avatar': frozenset(('blur', 'cache', 'command', 'describe', 'fade_in',
        'fallback', 'id', 'parent', 'placeholder', 'screen', 'size', 'src',
        'status', 'tint', 'visible')),
    'bottom_nav': frozenset(('icons', 'icons_active', 'indicator', 'labels',
        'screens')),
    'button': frozenset(('active', 'active_icon', 'command', 'describe', 'icon',
        'id', 'parent', 'screen', 'text', 'variant', 'visible')),
    'card': frozenset(('actions', 'content', 'id', 'image', 'parent',
        'screen', 'subtitle', 'title', 'variant')),
    'card_action': frozenset(('command', 'icon', 'id', 'text', 'variant')),
    'carousel': frozenset(('id', 'items', 'on_click', 'parent', 'screen')),
    'chart': frozenset(('center', 'fill', 'id', 'items', 'kind', 'max', 'on_click',
        'parent', 'screen', 'value', 'x', 'y')),
    'chips': frozenset(('check', 'icons', 'id', 'multiple', 'on_change', 'options',
        'parent', 'required', 'screen', 'selected')),
    'container': frozenset(('id', 'parent', 'screen', 'visible')),
    'drawer': frozenset(('header', 'icons', 'id', 'labels', 'screens',
        'subtitle')),
    'empty_state': frozenset(('action', 'icon', 'id', 'message', 'on_action',
        'parent', 'screen', 'title', 'visible')),
    'error_state': frozenset(('icon', 'id', 'message', 'parent', 'retry',
        'retry_text', 'screen', 'title', 'visible')),
    'grid': frozenset(('cols', 'id', 'items', 'on_click', 'parent',
        'screen')),
    'pager': frozenset(('id', 'parent', 'screen')),
    'segmented': frozenset(('check', 'icons', 'id', 'multiple', 'on_change', 'options',
        'parent', 'required', 'screen', 'selected')),
    'tab': frozenset(('describe', 'icon', 'id', 'parent', 'text')),
    'image': frozenset(('aspect_ratio', 'blur', 'cache', 'command',
        'describe', 'fade_in', 'fallback', 'id', 'parent', 'placeholder',
        'screen', 'src', 'tint', 'visible', 'zoom')),
    'input_field': frozenset(('error', 'help', 'id', 'on_change', 'parent',
        'placeholder', 'required', 'screen', 'type')),
    'inputs': frozenset(('error', 'help', 'id', 'on_change', 'parent',
        'placeholder', 'required', 'screen', 'type')),
    'label': frozenset(('id', 'parent', 'screen', 'text', 'variant', 'visible')),
    'list_row': frozenset(('command', 'icon', 'id', 'parent', 'screen',
        'subtitle', 'text', 'trailing', 'trailing_icon')),
    'list_view': frozenset(('id', 'items', 'on_click', 'parent', 'rich',
        'screen')),
    'map_view': frozenset(('attribution', 'cache_days', 'disk_cache',
        'follow_user', 'id', 'latitude', 'longitude', 'markers', 'on_tap',
        'parent', 'preview_label', 'route', 'screen', 'show_user', 'tile_url',
        'tile_user_agent', 'zoom')),
    'markdown': frozenset(('id', 'parent', 'screen', 'selectable', 'source')),
    'mini_player': frozenset(('id', 'open')),
    'rich_text': frozenset(('id', 'parent', 'screen', 'selectable', 'spans')),
    'skeleton': frozenset(('count', 'id', 'parent', 'screen', 'variant',
        'visible')),
    'sliver_app_bar': frozenset(('actions', 'expanded_height', 'id', 'image',
        'leading', 'pinned', 'screen', 'title')),
    'spinner': frozenset(('id', 'parent', 'screen', 'visible')),
    'tree_view': frozenset(('expand_depth', 'id', 'nodes', 'parent',
        'row_height', 'screen')),
    'upload_button': frozenset(('content_type', 'field', 'fields', 'headers',
        'icon', 'id', 'on_cancel', 'on_file', 'on_progress', 'on_result',
        'parent', 'screen', 'task_id', 'text', 'title', 'types', 'url',
        'variant')),
    'video': frozenset(('aspect_ratio', 'autoplay', 'controls', 'fit', 'id',
        'loop', 'muted', 'on_end', 'on_error', 'on_progress', 'on_ready',
        'parent', 'poster', 'preload', 'screen', 'src')),
    'virtual_collection': frozenset(('buffer', 'columns', 'id', 'item_height', 'row',
        'items', 'layout', 'on_click', 'on_end_reached', 'on_refresh',
        'on_reorder', 'parent', 'prefetch', 'reorder', 'screen', 'swipe_left',
        'swipe_right', 'template', 'variant')),
}

_UNKNOWN_ARGUMENTS_REPORTED = set()


def unknown_arguments(component, names):
    """``[(name, suggestion)]`` for keywords this component does not take."""
    import difflib

    valid = COMPONENT_ARGUMENTS.get(component)
    if not valid:
        return []
    found = []
    for name in names:
        if name in valid:
            continue
        close = difflib.get_close_matches(name, sorted(valid), 1, 0.7)
        found.append((name, close[0] if close else None))
    return found


def report_unknown_arguments(component, names, line=0):
    """Say so, once per component/name per process, and carry on building."""
    for name, near in unknown_arguments(component, names):
        key = (component, name)
        if key in _UNKNOWN_ARGUMENTS_REPORTED:
            continue
        _UNKNOWN_ARGUMENTS_REPORTED.add(key)
        from ..diagnostics import (
            Diagnostic, SourceLocation, report_diagnostic,
        )
        report_diagnostic(Diagnostic(
            code='U2030',
            title='This component does not take that argument',
            message='{0}({1}=...) was ignored.'.format(component, name),
            cause=(
                'The Previewer raises a TypeError here, because Python checks '
                'the call. The compiler reads the source without running it, '
                'so an argument it does not know simply never reaches the '
                'layout -- and going straight to a build showed nothing at '
                'all.'
            ),
            expected='one of: ' + ', '.join(
                sorted(COMPONENT_ARGUMENTS.get(component, ()))),
            received=repr(name),
            location=(SourceLocation(path='', line=line) if line else None),
            suggestions=(
                (['Did you mean ' + near + '?'] if near else [])
                + ['Remove the argument, or check ' + component
                   + ' in the component reference.']
            ),
            docs='https://repo-apkpy.pages.dev/reference/components/',
        ))
