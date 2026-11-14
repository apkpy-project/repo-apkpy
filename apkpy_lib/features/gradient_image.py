"""CSS gradients as pictures, for the Previewer.

The phone draws ``background: linear-gradient(...)`` with a shader
(core/features/gradient_drawable.py); here it is a Pillow image from the same
geometry (core/gradients.py), so the same colour lands on the same pixel.

A linear gradient is a one-pixel ramp of its colours stretched along the
gradient line by an affine transform, which Pillow does in C. A radial one is
worked out pixel by pixel, which is slower, so images are cached by size.
"""

import math

from ..core import gradients as _gradients
from ..core.features.gradient_drawable import resolved_stops

_CACHE = {}
_CACHE_LIMIT = 48


def _ramp(stops, length, mix=None):
    """A 1 x length RGBA image of the colours from 0 to 1."""
    from PIL import Image
    length = max(2, int(length))
    pixels = []
    for i in range(length):
        t = i / float(length - 1)
        if t <= stops[0][1]:
            colour = stops[0][0]
        elif t >= stops[-1][1]:
            colour = stops[-1][0]
        else:
            colour = stops[-1][0]
            for (c0, p0), (c1, p1) in zip(stops, stops[1:]):
                if t <= p1:
                    f = 0.0 if p1 <= p0 else (t - p0) / (p1 - p0)
                    colour = tuple(a + (b - a) * f for a, b in zip(c0, c1))
                    break
        a, r, g, b = colour
        if mix is not None:
            r, g, b = mix((r, g, b))
        pixels.append((int(r + 0.5), int(g + 0.5), int(b + 0.5), int(a + 0.5)))
    image = Image.new("RGBA", (length, 1))
    image.putdata(pixels)
    return image


def render(gradient, width, height, resolve=None, mix=None, key=None):
    """An RGBA image ``width`` x ``height`` of the gradient, or None.

    ``resolve`` turns a stop's colour (a ``var()``) into hex; ``mix`` takes
    ``(r, g, b)`` and returns what shows through an ``opacity`` around it.
    ``key`` adds to the cache key what ``mix`` depends on.
    """
    width, height = int(width), int(height)
    if width < 1 or height < 1 or gradient is None:
        return None
    if isinstance(gradient, (list, tuple)):
        # Several layers, the top one first (CSS's order): drawn bottom up.
        stacked = None
        for layer in reversed(list(gradient)):
            picture = render(layer, width, height, resolve, mix, key)
            if picture is None:
                continue
            if stacked is None:
                stacked = picture.copy()
            else:
                stacked.alpha_composite(picture)
        return stacked
    try:
        from PIL import Image
    except Exception:
        return None
    stops = resolved_stops(gradient, resolve)
    if len(stops) < 2:
        return None
    cache_key = (repr(gradient.__dict__), width, height, key,
                 tuple((c, p) for c, p in stops))
    image = _CACHE.pop(cache_key, None)
    if image is None:
        image = (_linear if gradient.kind == "linear" else _radial)(
            gradient, stops, width, height, mix)
    _CACHE[cache_key] = image
    while len(_CACHE) > _CACHE_LIMIT:
        _CACHE.pop(next(iter(_CACHE)))
    return image


def _span(gradient, stops):
    """The stops over 0..1 and the part of the line they repeat over."""
    first, last = stops[0][1], stops[-1][1]
    if gradient.repeating and last > first:
        return [(c, (p - first) / (last - first)) for c, p in stops], (first, last)
    return stops, None


def _linear(gradient, stops, width, height, mix):
    from PIL import Image
    stops, span = _span(gradient, stops)
    x0, y0, x1, y1 = gradient.line(width, height)
    if span is not None:
        x0, y0, x1, y1 = (x0 + (x1 - x0) * span[0], y0 + (y1 - y0) * span[0],
                          x0 + (x1 - x0) * span[1], y0 + (y1 - y0) * span[1])
    dx, dy = x1 - x0, y1 - y0
    length2 = dx * dx + dy * dy or 1.0
    steps = max(256, int(math.sqrt(length2)) + 1)
    ramp = _ramp(stops, steps, mix)
    repeats = 1
    if span is not None:
        # Enough copies of the ramp for the whole box, starting a few
        # periods before 0 so the corners behind the start are covered.
        before = 4
        corners = [((cx - x0) * dx + (cy - y0) * dy) / length2
                   for cx, cy in ((0, 0), (width, 0), (0, height), (width, height))]
        before = int(math.ceil(max(0.0, -min(corners)))) + 1
        repeats = before + int(math.ceil(max(corners))) + 1
        tiled = Image.new("RGBA", (steps * repeats, 1))
        for i in range(repeats):
            tiled.paste(ramp, (i * steps, 0))
        ramp = tiled
        offset = before * steps
    else:
        offset = 0
    # t(x, y) = ((x - x0) * dx + (y - y0) * dy) / |d|^2; the ramp is sampled
    # at t * (steps - 1) (+ offset), its only row.
    scale = (steps - 1) / length2
    a, b = dx * scale, dy * scale
    c = offset - (x0 * dx + y0 * dy) * scale + 0.5 * (a + b)
    wide = ramp.resize((ramp.width, 2))
    return wide.transform((width, height), Image.AFFINE, (a, b, c, 0, 0, 0.5),
                          resample=Image.BILINEAR)


def _radial(gradient, stops, width, height, mix):
    from PIL import Image
    stops, span = _span(gradient, stops)
    cx, cy, rx, ry = gradient.radii(width, height)
    steps = 512
    ramp = _ramp(stops, steps, mix).load()
    period = (span[1] - span[0]) if span is not None else None
    start = span[0] if span is not None else 0.0
    data = []
    for y in range(height):
        fy = (y + 0.5 - cy) / ry
        fy2 = fy * fy
        for x in range(width):
            fx = (x + 0.5 - cx) / rx
            t = math.sqrt(fx * fx + fy2)
            if period:
                t = ((t - start) / period) % 1.0
            index = int(t * (steps - 1) + 0.5)
            data.append(ramp[min(steps - 1, max(0, index)), 0])
    image = Image.new("RGBA", (width, height))
    image.putdata(data)
    return image


def middle(gradient, resolve=None):
    """One colour for the gradient: what to paint where a picture cannot go."""
    return gradient.color_at(0.5, resolve) if gradient is not None else None


def find(value):
    """The gradient in a stylesheet value, or None."""
    return _gradients.parse(value) if isinstance(value, str) else None
