"""draw_pad(): what the Previewer (features/draw_pad.py) and the phone (ApkpyDrawPad,
core/features/draw_pad.py) share.

A box the person signs or scribbles in with a finger, kept as a PNG. The sizes,
the colours it takes from the theme and the stylesheet, and the checks on what
the app wrote live here, so both sides draw the same box.
"""

CODE = "U2050"
DOCS = "https://repo-apkpy.pages.dev/ui-components/#draw-pad"

COMPONENT = "draw_pad"
HEIGHT = 200            # dp / px, when the stylesheet gives none
PEN = 3.0               # dp / px, the width of the line
MIN_PEN, MAX_PEN = 0.5, 48.0
RADIUS = 12             # the box's corners
BORDER = 1
HINT_SIZE = 16          # sp / px


def refuse(message, received, line=0, suggestions=None):
    from .diagnostics import ApkpyError
    raise ApkpyError(
        message,
        code=CODE,
        title="A draw_pad() ApkPy cannot build",
        cause=("draw_pad() is a box to draw in with a finger: its pen is a width "
               "between %g and %g, and on_change= is a function." % (MIN_PEN, MAX_PEN)),
        expected='pad = draw_pad(id="signature", pen=3, hint="Sign here", on_change=signed, screen=home)',
        received=received,
        suggestions=suggestions or [
            'draw_pad(id="sketch", screen=home)',
            'if not pad.is_empty(): pad.save("signature.png")',
        ],
        docs=DOCS,
        line=line,
    )


def pen_from(value, line=0):
    """The pen's width, from what the app wrote."""
    if value is None:
        return PEN
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        refuse("pen= of draw_pad() is a number: the width of the line.", repr(value), line,
               ['draw_pad(pen=3)', 'draw_pad(pen=6)  for a marker'])
    if not MIN_PEN <= float(value) <= MAX_PEN:
        refuse("pen= of draw_pad() is between %g and %g." % (MIN_PEN, MAX_PEN), repr(value), line)
    return float(value)


def _paint(colour):
    """None for no paint: nothing given, or transparent."""
    if not colour or str(colour).strip().lower() in ('transparent', 'none', '#00000000'):
        return None
    return colour


def colors(tokens, own_style=None):
    """The ink, the paper, the border and the hint, from the stylesheet first
    and then the theme: the main text colour on the surface, outlined as a
    text field is. ``paper`` and ``border`` are None for none."""
    tokens = tokens or {}
    own = own_style or {}
    paper = own.get('background-color') or tokens.get('surface') or '#FFFFFF'
    return {
        'ink': own.get('color') or tokens.get('text') or '#1D1B20',
        'paper': _paint(paper),
        'border': _paint(own.get('border-color') or tokens.get('border') or '#79747E'),
        'hint': own.get('hint-color') or tokens.get('text_secondary') or '#49454F',
    }


def radius(own_style=None):
    value = (own_style or {}).get('border-radius')
    try:
        return max(0.0, float(str(value).strip().lower().replace('px', '').replace('dp', '')))
    except (TypeError, ValueError):
        return float(RADIUS)


def height(own_style=None):
    value = (own_style or {}).get('height')
    try:
        found = float(str(value).strip().lower().replace('px', '').replace('dp', ''))
        return found if found > 0 else float(HEIGHT)
    except (TypeError, ValueError):
        return float(HEIGHT)


def smooth(points):
    """A stroke as the phone draws it: straight to the first middle, then a
    curve through each point to the middle of the next segment, then straight
    to the end. ``[(x, y), ...]`` in, the list of points along that path out
    (each curve as 8 steps), which is what the Previewer draws and saves."""
    if len(points) < 3:
        return list(points)
    out = [points[0]]
    mids = [((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0) for a, b in zip(points, points[1:])]
    out.append(mids[0])
    for i in range(1, len(points) - 1):
        start, control, end = mids[i - 1], points[i], mids[i]
        for step in range(1, 9):
            t = step / 8.0
            u = 1 - t
            out.append((u * u * start[0] + 2 * u * t * control[0] + t * t * end[0],
                        u * u * start[1] + 2 * u * t * control[1] + t * t * end[1]))
    out.append(points[-1])
    return out
