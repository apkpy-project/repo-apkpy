"""Chips and segmented buttons: the rules both runtimes follow.

A row of chips and a segmented button are drawn twice -- by the Previewer's
canvas and by ApkpyChoice on the phone -- and they drift the moment one of
them decides on its own what a tap does, where a chip wraps or which colour
a selected segment takes. Every such decision lives here, and ApkpyChoice
mirrors these functions one for one (tap, flow, segmentEdges, ...).

Sizes are Material 3's, in dp on the phone and px in the Previewer, which is
the same number: the Previewer draws a 411dp-wide phone at one pixel per dp.
Each chip and segment is 48 tall to the finger and smaller to the eye; the
difference is the touch target Material asks for, split above and below.
"""

import json

CODE = "U2043"
DOCS = "https://repo-apkpy.pages.dev/ui-components/#chips-and-segmented-buttons"

KINDS = ('chips', 'segmented')

TOUCH = 48              # every chip and segment, to the finger
TEXT_SIZE = 14          # sp / px, Material's label-large
TEXT_WEIGHT = 500
BORDER = 1
ICON = 18
ICON_GAP = 8            # between the icon and the words

CHIP_HEIGHT = 32
CHIP_RADIUS = 8
CHIP_PAD = 16           # either side of the words
CHIP_PAD_ICON = 8       # the side an icon is on
CHIP_GAP = 8            # between two chips on a line

SEGMENT_HEIGHT = 40
SEGMENT_PAD = 12
MIN_SEGMENTS = 2
MAX_SEGMENTS = 5

CHECK_ICON = 'check'    # what a selected chip or segment shows at its start

# Material 3's secondary container and its ink, for an app with no Theme.
_ACTIVE_FILL = '#E8DEF8'
_ACTIVE_TEXT = '#1D192B'


def refuse(message, received, line=0, suggestions=None):
    from .diagnostics import ApkpyError
    raise ApkpyError(
        message,
        code=CODE,
        title="Chips or a segmented button ApkPy cannot build",
        cause=("chips() and segmented() take their options as a list of "
               "words, and what starts selected has to be one of them."),
        expected=('chips(["All", "Unread", "Starred"], selected="All", '
                  'on_change=show, screen=home)'),
        received=received,
        suggestions=suggestions or [
            'segmented(["Day", "Week", "Month"], selected="Week", on_change=pick)',
            'chips(["Python", "Kotlin"], multiple=True, selected=["Python"])',
        ],
        docs=DOCS,
        line=line or 0,
    )


def normalize_kind(kind):
    value = str(kind or '').strip().lower()
    if value not in KINDS:
        raise ValueError('kind is one of %s, not %r' % (', '.join(KINDS), kind))
    return value


def options_from(kind, raw, line=0):
    """The options as words, checked: none empty, none twice, and a
    segmented button with 2 to 5 of them."""
    if isinstance(raw, str) or not isinstance(raw, (list, tuple)):
        refuse('%s() takes its options as a list of words.' % kind, repr(raw), line,
               ['%s(["Day", "Week", "Month"], ...)' % kind])
    options = []
    for option in raw:
        if not isinstance(option, (str, int, float)) or isinstance(option, bool):
            refuse('Each option of %s() is a word or a number.' % kind, repr(option), line)
        text = str(option)
        if not text.strip():
            refuse('An option of %s() has no words, so nobody could tell it apart.' % kind,
                   repr(option), line)
        if text in options:
            refuse('%r is an option of %s() twice.' % (text, kind), repr(list(raw)), line,
                   ['Give each option its own words.'])
        options.append(text)
    if not options:
        refuse('%s() has no options.' % kind, repr(raw), line)
    if kind == 'segmented' and not (MIN_SEGMENTS <= len(options) <= MAX_SEGMENTS):
        refuse('A segmented button has %d to %d segments, and this one has %d.'
               % (MIN_SEGMENTS, MAX_SEGMENTS, len(options)), repr(options), line,
               ['For more choices than five, use chips(), which wrap onto more lines.'])
    return options


def icons_from(kind, raw, options, line=0):
    """One icon name (or None) per option."""
    if raw is None:
        return [None] * len(options)
    if isinstance(raw, str) or not isinstance(raw, (list, tuple)):
        refuse('icons= of %s() is a list, one icon per option.' % kind, repr(raw), line)
    if len(raw) != len(options):
        refuse('%s() has %d options and %d icons.' % (kind, len(options), len(raw)),
               repr(list(raw)), line, ['Give one icon per option, or None for none.'])
    return [str(icon) if icon else None for icon in raw]


def keeps_one(kind, multiple, required=False):
    """True when one option always stays selected: ``required=True``, and a
    segmented button that is not ``multiple`` -- Material's rule for it."""
    return bool(required) or (kind == 'segmented' and not multiple)


def initial(kind, options, selected, multiple, line=0, required=False):
    """What is selected when the screen opens, in the options' order.

    When one option must stay selected and none is named, it is the first;
    otherwise chips start with nothing unless told."""
    first = [options[0]] if keeps_one(kind, multiple, required) else []
    if multiple:
        if selected is None or (isinstance(selected, (list, tuple)) and not selected):
            return first
        if isinstance(selected, (list, tuple)):
            wanted = [str(v) for v in selected]
        else:
            wanted = [str(selected)]
    else:
        if isinstance(selected, (list, tuple)):
            refuse('Only one option of %s() can be selected unless multiple=True.' % kind,
                   repr(selected), line,
                   ['selected=%r' % (str(selected[0]) if selected else options[0]),
                    '%s(..., multiple=True, selected=%r)' % (kind, list(selected))])
        if selected is None or selected == '':
            return first
        wanted = [str(selected)]
    for value in wanted:
        if value not in options:
            refuse('selected=%r is not one of the options of %s().' % (value, kind),
                   repr(value), line, ['One of: %s' % ', '.join(repr(o) for o in options)])
    return [o for o in options if o in wanted]


def tap(kind, options, current, option, multiple, required=False):
    """The selection after a tap on ``option``.

    Many: the option turns on or off. One: the option is selected; a tap on
    the one already selected clears it -- unless one must stay selected
    (``keeps_one``), and then the tap changes nothing, as it does for the
    last option left on with ``multiple``."""
    if option not in options:
        return list(current)
    keep = keeps_one(kind, multiple, required)
    if multiple:
        if option in current:
            rest = [o for o in options if o in current and o != option]
            return list(current) if (keep and not rest) else rest
        return [o for o in options if o in current or o == option]
    if option in current:
        return list(current) if keep else []
    return [option]


def value_of(current, multiple):
    """What get_value() and on_change see: the word, or "" for none; a
    list of words when ``multiple``."""
    if multiple:
        return list(current)
    return current[0] if current else ''


def encode(current, multiple):
    """The same value as the phone's text: a list travels as JSON."""
    if multiple:
        return json.dumps(list(current), ensure_ascii=False)
    return current[0] if current else ''


def from_value(kind, options, current, value, multiple, required=False):
    """The selection set_value(value) asks for. A value that selects
    nothing clears chips, and leaves them as they were when one must stay
    selected."""
    keep = keeps_one(kind, multiple, required)
    if multiple:
        if isinstance(value, (list, tuple)):
            wanted = [str(v) for v in value]
        else:
            text = '' if value is None else str(value).strip()
            if text.startswith('['):
                try:
                    wanted = [str(v) for v in json.loads(text)]
                except ValueError:
                    wanted = [text]
            else:
                wanted = [text] if text else []
        chosen = [o for o in options if o in wanted]
        return list(current) if (keep and not chosen) else chosen
    text = '' if value is None else str(value)
    if text in options:
        return [text]
    return list(current) if keep else []


def colors(kind, tokens, own_style=None):
    """Fill, border, words and icon, unselected and selected.

    Unselected chips are outlined in the subtle border with their words in
    the secondary text colour and their icons in primary; a segmented
    button is outlined in the full border. Selected, both take the secondary
    container (the bottom bar's indicator) and the main text colour.
    ``fill`` is None for see-through."""
    tokens = tokens or {}
    own = own_style or {}
    if kind == 'chips':
        border = own.get('border-color') or tokens.get('border_subtle') or '#CAC4D0'
        text = own.get('color') or tokens.get('text_secondary') or '#49454F'
        icon = own.get('color') or tokens.get('primary') or '#6750A4'
    else:
        border = own.get('border-color') or tokens.get('border') or '#79747E'
        text = own.get('color') or tokens.get('text') or '#1D1B20'
        icon = text
    return {
        'fill': _paint(own.get('background-color')),
        'border': _paint(border),
        'text': text,
        'icon': icon,
        'active_fill': own.get('indicator-color') or tokens.get('nav_indicator') or _ACTIVE_FILL,
        'active_text': own.get('active-color') or tokens.get('text') or _ACTIVE_TEXT,
    }


def _paint(colour):
    """None for no paint: nothing given, or transparent."""
    if not colour or str(colour).strip().lower() in ('transparent', 'none', '#00000000'):
        return None
    return colour


def leading_icon(icon, selected, check=True):
    """A selected chip or segment shows a check where its icon was, unless
    ``check=False`` (Spotify's chips have none)."""
    return CHECK_ICON if (selected and check) else icon


def chip_width(text_width, has_icon):
    """A chip's width around words ``text_width`` wide."""
    left = CHIP_PAD_ICON + ICON + ICON_GAP if has_icon else CHIP_PAD
    return int(round(left + text_width + CHIP_PAD))


def flow(widths, max_width, gap=CHIP_GAP):
    """Where each chip goes: (x, line). A chip that would pass the edge
    starts a new line, unless it is the first on its line."""
    out = []
    x, line = 0, 0
    for width in widths:
        if x > 0 and x + width > max_width:
            x, line = 0, line + 1
        out.append((x, line))
        x += width + gap
    return out


def lines_of(positions):
    return (max(line for _x, line in positions) + 1) if positions else 0


def segment_edges(count, width):
    """The left edge of each segment and the right edge of the last: the
    width shared equally, any leftover pixel going to the later ones."""
    return [(i * width) // count for i in range(count + 1)]


def vertical_inset(kind):
    """How far the visible shape sits inside its 48-tall touch area."""
    height = CHIP_HEIGHT if kind == 'chips' else SEGMENT_HEIGHT
    return (TOUCH - height) // 2


def radius(kind, own_style=None):
    """The corner: 8 for a chip, a full pill for a segmented button, or
    the CSS border-radius."""
    import re
    match = re.search(r'([0-9.]+)', str((own_style or {}).get('border-radius', '')))
    if match:
        return float(match.group(1))
    return float(CHIP_RADIUS if kind == 'chips' else SEGMENT_HEIGHT / 2.0)


def text_size(own_style=None):
    import re
    match = re.search(r'([0-9.]+)', str((own_style or {}).get('font-size', '')))
    return float(match.group(1)) if match else float(TEXT_SIZE)


def role(multiple):
    """What a screen reader calls each option."""
    return 'checkbox' if multiple else 'radio'
