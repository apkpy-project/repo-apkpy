"""Charts: the numbers both runtimes draw from.

A chart is drawn twice -- by Pillow in the Previewer and by ApkpyChart's
Canvas on the phone -- and the two drift the moment one of them decides on
its own where an axis ends, how a number is written or where a slice starts.
Every such decision lives here. ApkpyChart mirrors these functions one for
one (niceScale, formatNumber, labelStep, ...), and a test compiles the Java
and puts the same questions to both languages.

Sizes are in dp on the phone and px in the Previewer, which is the same
number: the Previewer draws a 411dp-wide phone at one pixel per dp.
"""

import math

KINDS = ('bar', 'line', 'donut', 'ring')

# Heights of the drawing itself; a donut's legend comes on top of its height.
DEFAULT_HEIGHT = {'bar': 200, 'line': 200, 'donut': 180, 'ring': 160}

TICKS = 4               # gridlines above the zero line
AXIS_WIDTH = 36         # the y labels' column, left of the plot
LABEL_HEIGHT = 22       # the x labels' row, under the plot
LABEL_SIZE = 12         # sp / px
MIN_LABEL_SPACE = 36    # a label needs this much width, or every k-th is shown
BAR_GAP = 0.35          # of each bar's slot, shared either side of it
BAR_RADIUS = 6
LINE_WIDTH = 3
POINT_RADIUS = 3.5
FILL_ALPHA = 0.18       # a filled line's area
DONUT_THICKNESS = 26
RING_THICKNESS = 14
SLICE_GAP_DEGREES = 2.0
LEGEND_ROW = 24
LEGEND_DOT = 10

# The first colour is replaced by the chart's own (its CSS color, or the
# theme's primary); the rest tell the slices of a donut apart.
PALETTE = ('#6750A4', '#10B981', '#F59E0B', '#EF4444', '#3B82F6',
           '#8B5CF6', '#EC4899', '#14B8A6')


def normalize_kind(kind):
    value = str(kind or 'bar').strip().lower()
    if value not in KINDS:
        raise ValueError('chart(kind=...) is one of %s, not %r' % (', '.join(KINDS), kind))
    return value


def nice_scale(max_value, ticks=TICKS):
    """The top of the axis and its step.

    The step is the smallest 1, 2, 2.5, 5 or 10 (times a power of ten) that
    reaches ``max_value / ticks``; the top is the first multiple of it at or
    above ``max_value``. 4.2 over four ticks: the raw step is 1.05, the step
    2, the top 6 -- gridlines at 0, 2, 4, 6."""
    if max_value is None or max_value <= 0:
        return 1.0 * ticks, 1.0
    raw = float(max_value) / ticks
    magnitude = 10.0 ** math.floor(math.log10(raw))
    step = 10.0 * magnitude
    for multiple in (1.0, 2.0, 2.5, 5.0, 10.0):
        candidate = multiple * magnitude
        if candidate >= raw * (1 - 1e-9):
            step = candidate
            break
    top = math.ceil(float(max_value) / step - 1e-9) * step
    return top, step


def format_number(value):
    """How an axis or a legend writes a number: 12, 2.5, 1.2K, 3M.

    Whole numbers lose their decimals, others keep one (two under 1), and
    thousands and millions are shortened -- 12500 is 12.5K. Halves round up,
    as Java's Math.floor(x + 0.5) does; Python's round() goes to even."""
    v = float(value)
    sign = '-' if v < 0 else ''
    v = abs(v)
    suffix = ''
    if v >= 1e6:
        v, suffix = v / 1e6, 'M'
    elif v >= 1e3:
        v, suffix = v / 1e3, 'K'
    decimals = 2 if v < 1 else 1
    scale = 10 ** decimals
    rounded = math.floor(v * scale + 0.5) / scale
    if rounded == int(rounded):
        text = '%d' % int(rounded)
    else:
        text = ('%.*f' % (decimals, rounded)).rstrip('0')
    if text == '0':
        sign = ''
    return sign + text + suffix


def label_step(count, plot_width, min_space=MIN_LABEL_SPACE):
    """Show every k-th x label so none overlaps: 1 while they fit."""
    if count <= 0 or plot_width <= 0:
        return 1
    return max(1, int(math.ceil(count * float(min_space) / plot_width)))


def items_from(raw_items, x='label', y='value'):
    """(label, value, colour) for each item: a dict read by the x and y
    names, or a bare number. A value that is not a number counts as 0."""
    out = []
    for item in raw_items or []:
        if isinstance(item, dict):
            label = item.get(x, '')
            raw_value = item.get(y, 0)
            colour = item.get('color') or None
        else:
            label, raw_value, colour = '', item, None
        try:
            value = float(raw_value)
            if value != value:          # NaN
                value = 0.0
        except (TypeError, ValueError):
            value = 0.0
        out.append(('' if label is None else str(label), value, colour))
    return out


def chart_colors(tokens, own_style=None):
    """The series, the track under a ring or donut, the labels, the
    gridlines and the text in a ring's centre."""
    tokens = tokens or {}
    own = own_style or {}
    series = own.get('color') or tokens.get('primary') or PALETTE[0]
    return {
        'series': series,
        'track': own.get('track-color') or tokens.get('surface_high') or '#E7E0EC',
        'label': own.get('label-color') or tokens.get('text_secondary') or '#64748B',
        'grid': (own.get('grid-color') or tokens.get('border_subtle')
                 or tokens.get('border') or '#E2E8F0'),
        'center': own.get('title-color') or tokens.get('text') or '#1D1B20',
    }


def slice_color(index, item_color, series):
    """A slice's colour: its item's own, else the palette with the chart's
    colour first."""
    if item_color:
        return item_color
    if index % len(PALETTE) == 0:
        return series
    return PALETTE[index % len(PALETTE)]


def slices(values):
    """(start, sweep) in degrees for each value, clockwise from 12 o'clock,
    with a small gap between slices. Negative values count as 0."""
    positive = [max(0.0, float(v)) for v in values]
    total = sum(positive)
    if total <= 0:
        return [(0.0, 0.0) for _ in values]
    shown = sum(1 for v in positive if v > 0)
    gap = SLICE_GAP_DEGREES if shown > 1 else 0.0
    start = -90.0
    out = []
    for v in positive:
        sweep = v / total * 360.0
        out.append((start + gap / 2.0, max(0.0, sweep - gap)) if v > 0 else (start, 0.0))
        start += sweep
    return out


def ring_fraction(value, maximum):
    try:
        v, m = float(value), float(maximum)
    except (TypeError, ValueError):
        return 0.0
    if m <= 0:
        return 0.0
    return max(0.0, min(1.0, v / m))


def ring_center_text(value, maximum, center=None):
    if center is not None:
        return str(center)
    return '%d%%' % int(round(ring_fraction(value, maximum) * 100))


def bar_rects(values, left, top, width, height, scale_top):
    """(x0, y0, x1, y1) for each bar in a plot box, from the zero line up."""
    count = len(values)
    if count == 0 or width <= 0:
        return []
    slot = float(width) / count
    bar_width = slot * (1.0 - BAR_GAP)
    rects = []
    for index, value in enumerate(values):
        fraction = max(0.0, min(1.0, float(value) / scale_top)) if scale_top > 0 else 0.0
        x0 = left + index * slot + (slot - bar_width) / 2.0
        y1 = top + height
        rects.append((x0, y1 - fraction * height, x0 + bar_width, y1))
    return rects


def line_points(values, left, top, width, height, scale_top):
    """(x, y) of each point, at the centre of its slot -- where a bar would
    stand -- so the first and last labels fit under the plot."""
    count = len(values)
    if count == 0:
        return []
    slot = float(width) / count
    points = []
    for index, value in enumerate(values):
        x = left + index * slot + slot / 2.0
        fraction = max(0.0, min(1.0, float(value) / scale_top)) if scale_top > 0 else 0.0
        points.append((x, top + height - fraction * height))
    return points


def legend_height(items):
    """A donut lists its slices under it, one row each, when they have labels."""
    labelled = [item for item in items if item[0]]
    return len(labelled) * LEGEND_ROW + (8 if labelled else 0)
