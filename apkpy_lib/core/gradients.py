"""CSS gradients, read once for both renderers.

``background: linear-gradient(135deg, #6750A4, #00BCD4)`` and
``radial-gradient(circle at top left, ...)`` are parsed here into a
:class:`Gradient`: the stops with their positions filled in as CSS fills them,
and the geometry the phone's drawable and the Previewer's image both draw
from, so the two put the same colour at the same point.

What is read:

* ``linear-gradient(<angle> | to <side> | to <corner>, stops...)``. The angle
  in ``deg``, ``turn``, ``rad`` or ``grad``; without one, ``to bottom``.
* ``radial-gradient([circle | ellipse] [closest-side | closest-corner |
  farthest-side | farthest-corner] [at <position>], stops...)``. The position
  as keywords or percentages.
* A stop is a colour (hex, a name, ``var(--token)``; ``rgba()`` and ``hsl()``
  were already turned into hex by the parser) with an optional position in
  ``%``.
"""

import math
import re

from .css_colors import NAMED

_FUNCTION = re.compile(r"(repeating-)?(linear|radial)-gradient\(", re.I)
_PERCENT = re.compile(r"^([+-]?(?:\d+\.?\d*|\.\d+))%$")
_ANGLE = re.compile(r"^([+-]?(?:\d+\.?\d*|\.\d+))(deg|turn|rad|grad)?$", re.I)

_SIDES = {"top": 0.0, "right": 90.0, "bottom": 180.0, "left": 270.0}
_CORNERS = {
    frozenset(("top", "right")): "top right",
    frozenset(("bottom", "right")): "bottom right",
    frozenset(("bottom", "left")): "bottom left",
    frozenset(("top", "left")): "top left",
}
_POSITION_WORDS = {"left": (0.0, None), "right": (1.0, None), "top": (None, 0.0),
                   "bottom": (None, 1.0), "center": (None, None)}
_EXTENTS = ("closest-side", "closest-corner", "farthest-side", "farthest-corner")


class Gradient(object):
    """A parsed gradient.

    ``kind`` is ``"linear"`` or ``"radial"``. ``stops`` is a list of
    ``(colour, position)`` with every position filled in, 0.0 to 1.0, never
    decreasing. A linear gradient has ``angle`` (CSS degrees: 0 points up,
    90 right) or ``corner`` (``"top right"``...), which depends on the box. A
    radial one has ``shape`` (``"circle"``/``"ellipse"``), ``extent`` and
    ``center`` as fractions of the box.
    """

    def __init__(self, kind, stops, angle=180.0, corner=None, shape="ellipse",
                 extent="farthest-corner", center=(0.5, 0.5), repeating=False):
        self.kind = kind
        self.stops = stops
        self.angle = angle
        self.corner = corner
        self.shape = shape
        self.extent = extent
        self.center = center
        self.repeating = repeating

    def __repr__(self):
        return "Gradient(%r, %r, angle=%r, corner=%r)" % (
            self.kind, self.stops, self.angle, self.corner)

    # ── Geometry ────────────────────────────────────────────────────────

    def angle_for(self, width, height):
        """The CSS angle in degrees for a box this size (a corner depends on it)."""
        if self.corner is None:
            return self.angle % 360.0
        # The line is perpendicular to the diagonal joining the other two
        # corners, so the 50% line runs through them (CSS Images 3).
        towards = math.degrees(math.atan2(max(height, 1e-6), max(width, 1e-6)))
        return {"top right": towards, "bottom right": 180.0 - towards,
                "bottom left": 180.0 + towards, "top left": 360.0 - towards}[self.corner]

    def line(self, width, height):
        """``(x0, y0, x1, y1)``: where 0% and 100% lie, in the box's pixels."""
        a = math.radians(self.angle_for(width, height))
        dx, dy = math.sin(a), -math.cos(a)
        half = (abs(width * dx) + abs(height * dy)) / 2.0
        cx, cy = width / 2.0, height / 2.0
        return (cx - dx * half, cy - dy * half, cx + dx * half, cy + dy * half)

    def radii(self, width, height):
        """``(cx, cy, rx, ry)`` of a radial gradient's 100% ellipse, in pixels."""
        cx, cy = self.center[0] * width, self.center[1] * height
        left, right, top, bottom = cx, width - cx, cy, height - cy
        if self.extent in ("closest-side", "farthest-side"):
            pick = min if self.extent == "closest-side" else max
            rx, ry = pick(left, right), pick(top, bottom)
            if self.shape == "circle":
                rx = ry = pick(rx, ry)
        else:
            pick = min if self.extent == "closest-corner" else max
            sx, sy = pick(left, right), pick(top, bottom)
            if self.shape == "circle":
                rx = ry = math.hypot(sx, sy)
            else:
                # The ellipse through that corner with the sides' ratio.
                rx, ry = sx * math.sqrt(2.0), sy * math.sqrt(2.0)
        return cx, cy, max(rx, 0.5), max(ry, 0.5)

    # ── Colour ──────────────────────────────────────────────────────────

    def middle(self, resolve=None):
        """One colour that stands in for the gradient (the one at 50%)."""
        return self.color_at(0.5, resolve)

    def color_at_point(self, x, y, width, height, resolve=None):
        """The colour at pixel ``(x, y)`` of a box this size."""
        if self.kind == "linear":
            x0, y0, x1, y1 = self.line(width, height)
            dx, dy = x1 - x0, y1 - y0
            t = ((x - x0) * dx + (y - y0) * dy) / ((dx * dx + dy * dy) or 1.0)
        else:
            cx, cy, rx, ry = self.radii(width, height)
            t = math.hypot((x - cx) / rx, (y - cy) / ry)
        return self.color_at(t, resolve)

    def color_at(self, t, resolve=None):
        """``#AARRGGBB``/``#RRGGBB`` at position ``t``."""
        stops = [(argb(resolve(c) if resolve else c), p) for c, p in self.stops]
        stops = [(c, p) for c, p in stops if c is not None]
        if not stops:
            return None
        if self.repeating and stops[-1][1] > stops[0][1]:
            span = stops[-1][1] - stops[0][1]
            t = stops[0][1] + (t - stops[0][1]) % span
        if t <= stops[0][1]:
            return _hex(stops[0][0])
        for (c0, p0), (c1, p1) in zip(stops, stops[1:]):
            if t <= p1:
                f = 0.0 if p1 <= p0 else (t - p0) / (p1 - p0)
                return _hex(tuple(a + (b - a) * f for a, b in zip(c0, c1)))
        return _hex(stops[-1][0])


def argb(colour):
    """(a, r, g, b) of ``#AARRGGBB``/``#RRGGBB``/``#RGB``/a name, or None."""
    raw = str(colour or "").strip()
    raw = NAMED.get(raw.lower(), raw)
    if not raw.startswith("#"):
        return None
    digits = raw[1:]
    if len(digits) == 3:
        digits = "".join(d * 2 for d in digits)
    if len(digits) == 4:
        digits = "".join(d * 2 for d in digits)
    if len(digits) == 6:
        digits = "FF" + digits
    if len(digits) != 8:
        return None
    try:
        return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4, 6))
    except ValueError:
        return None


def _hex(values):
    a, r, g, b = (max(0, min(255, int(v + 0.5))) for v in values)
    if a == 255:
        return "#%02X%02X%02X" % (r, g, b)
    return "#%02X%02X%02X%02X" % (a, r, g, b)


# ── Parsing ─────────────────────────────────────────────────────────────

def _split_top_level(body):
    """Split on commas that are not inside parentheses."""
    parts, depth, current = [], 0, []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    parts.append("".join(current).strip())
    return [p for p in parts if p]


def find(value):
    """``(start, end, repeating, kind, body)`` of the first gradient in a
    value, or None. ``end`` is past its closing parenthesis."""
    if not isinstance(value, str):
        return None
    match = _FUNCTION.search(value)
    if match is None:
        return None
    depth, index = 1, match.end()
    while index < len(value) and depth:
        if value[index] == "(":
            depth += 1
        elif value[index] == ")":
            depth -= 1
        index += 1
    if depth:
        return None
    return (match.start(), index, bool(match.group(1)), match.group(2).lower(),
            value[match.end():index - 1])


def _angle(text):
    match = _ANGLE.match(text.strip())
    if match is None or (match.group(2) is None and float(match.group(1)) != 0):
        return None
    number, unit = float(match.group(1)), (match.group(2) or "deg").lower()
    return number * {"deg": 1.0, "turn": 360.0, "rad": 180.0 / math.pi,
                     "grad": 0.9}[unit]


def _stop(text):
    """``"#FFF 30%"`` -> [("#FFF", 0.3)]; ``"#FFF 20% 40%"`` -> two stops."""
    words = text.split()
    if not words:
        return []
    positions = []
    while len(words) > 1 and _PERCENT.match(words[-1]):
        positions.insert(0, float(_PERCENT.match(words.pop()).group(1)) / 100.0)
    colour = " ".join(words)
    if not positions:
        return [(colour, None)]
    return [(colour, p) for p in positions[:2]]


def _fill_positions(stops):
    """CSS's rule: the first is 0, the last 1, a position never goes back,
    and stops without one are spread evenly between those that have one."""
    if not stops:
        return stops
    positions = [p for _, p in stops]
    if positions[0] is None:
        positions[0] = 0.0
    if positions[-1] is None:
        positions[-1] = 1.0
    highest = positions[0]
    for index, p in enumerate(positions):
        if p is not None:
            highest = max(highest, p)
            positions[index] = highest
    index = 0
    while index < len(positions):
        if positions[index] is None:
            start = index - 1
            end = index
            while positions[end] is None:
                end += 1
            step = (positions[end] - positions[start]) / (end - start)
            for k in range(start + 1, end):
                positions[k] = positions[start] + step * (k - start)
            index = end
        index += 1
    return [(c, p) for (c, _), p in zip(stops, positions)]


def _position(words):
    """``["top", "left"]`` / ``["30%", "70%"]`` -> (x, y) fractions."""
    x = y = None
    numbers = []
    for word in words:
        word = word.lower()
        if word in _POSITION_WORDS:
            wx, wy = _POSITION_WORDS[word]
            if wx is not None:
                x = wx
            if wy is not None:
                y = wy
        elif _PERCENT.match(word):
            numbers.append(float(_PERCENT.match(word).group(1)) / 100.0)
        else:
            return None
    if numbers:
        x = numbers[0] if x is None else x
        if len(numbers) > 1:
            y = numbers[1]
    return (0.5 if x is None else x, 0.5 if y is None else y)


def parse(value):
    """The first gradient in a stylesheet value as a :class:`Gradient`, or None."""
    found = find(value)
    if found is None:
        return None
    _, _, repeating, kind, body = found
    parts = _split_top_level(body)
    if not parts:
        return None
    first = parts[0].strip().lower()
    options = {}
    if kind == "linear":
        if first.startswith("to "):
            words = frozenset(first[3:].split())
            if len(words) == 1 and next(iter(words)) in _SIDES:
                options["angle"] = _SIDES[next(iter(words))]
            elif words in _CORNERS:
                options["corner"] = _CORNERS[words]
            else:
                return None
            parts = parts[1:]
        else:
            angle = _angle(first)
            if angle is not None:
                options["angle"] = angle
                parts = parts[1:]
    else:
        words = first.split()
        if words and (words[0] in ("circle", "ellipse") or words[0] in _EXTENTS
                      or words[0] == "at"):
            shape, extent, center = "ellipse", "farthest-corner", (0.5, 0.5)
            if "at" in words:
                at = words.index("at")
                center = _position(words[at + 1:])
                if center is None:
                    return None
                words = words[:at]
            for word in words:
                if word in ("circle", "ellipse"):
                    shape = word
                elif word in _EXTENTS:
                    extent = word
                else:
                    return None
            options.update(shape=shape, extent=extent, center=center)
            parts = parts[1:]
    stops = []
    for part in parts:
        stops.extend(_stop(part))
    if len(stops) < 2:
        return None
    return Gradient(kind, _fill_positions(stops), repeating=repeating, **options)


def gradient_of(style):
    """The gradient a component's style paints, or None.

    ``background-image`` first, then ``background``.
    """
    for key in ("background-image", "background"):
        gradient = parse((style or {}).get(key))
        if gradient is not None:
            return gradient
    return None


def layers(value):
    """Every gradient in a value, the top one (CSS writes it first) first."""
    found, rest = [], value if isinstance(value, str) else ""
    while True:
        place = find(rest)
        if place is None:
            return found
        gradient = parse(rest[place[0]:place[1]])
        if gradient is not None:
            found.append(gradient)
        rest = rest[place[1]:]


def layers_of(style):
    """The gradients a component's style stacks, top first; [] for none."""
    for key in ("background-image", "background"):
        found = layers((style or {}).get(key))
        if found:
            return found
    return []
