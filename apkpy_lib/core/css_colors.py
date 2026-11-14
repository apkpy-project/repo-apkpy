"""Colours as a stylesheet writes them, read once for both renderers.

The engine keeps a colour with alpha in Android's order, ``#AARRGGBB``
(``transparent`` is ``#00000000``). A stylesheet is written in CSS's, and CSS
puts the alpha last: ``#00000080`` is black at half strength in every browser,
and every assistant that writes CSS writes it that way. Read as Android's
order it was a fully transparent box. ``rgba()`` reached the phone's XML as it
was written, which the build refused, and stopped the Previewer when it opened.

So every colour in a stylesheet value is turned into the engine's form here,
as the stylesheet is parsed: ``rgb()``, ``rgba()``, ``hsl()``, ``hsla()``,
``#RGBA`` and ``#RRGGBBAA`` (CSS order). ``#RGB``, ``#RRGGBB``, names and
``var(--token)`` are left as they are.
"""

import colorsys
import re

_NUMBER = r"[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?"
_FUNCTION = re.compile(r"\b(rgba?|hsla?)\(\s*([^()]*)\)", re.I)
_HEX = re.compile(r"#([0-9a-fA-F]{8}|[0-9a-fA-F]{4})\b")


def _channel(text):
    """An rgb() channel, 0-255, from ``128`` or ``50%``."""
    text = text.strip()
    if text.endswith("%"):
        return max(0.0, min(255.0, float(text[:-1]) * 2.55))
    return max(0.0, min(255.0, float(text)))


def _alpha(text):
    """An alpha, 0-1, from ``0.5`` or ``50%``."""
    text = text.strip()
    if text.endswith("%"):
        return max(0.0, min(1.0, float(text[:-1]) / 100.0))
    return max(0.0, min(1.0, float(text)))


def _hue(text):
    """A hue in turns, from ``120``, ``120deg``, ``0.5turn``, ``2rad`` or ``200grad``."""
    text = text.strip().lower()
    for unit, per_turn in (("deg", 360.0), ("grad", 400.0), ("rad", 6.283185307179586),
                           ("turn", 1.0)):
        if text.endswith(unit):
            return (float(text[:-len(unit)]) / per_turn) % 1.0
    return (float(text) / 360.0) % 1.0


def _percent(text):
    text = text.strip()
    value = float(text[:-1]) if text.endswith("%") else float(text)
    return max(0.0, min(1.0, value / 100.0))


def _arguments(body):
    """``"255, 0, 0, 0.5"`` or ``"255 0 0 / 50%"`` -> (["255", "0", "0"], "0.5"|None)."""
    body = body.strip()
    alpha = None
    if "/" in body:
        body, alpha = body.split("/", 1)
        alpha = alpha.strip()
    parts = [p for p in re.split(r"[\s,]+", body.strip()) if p]
    if alpha is None and len(parts) == 4:
        alpha = parts.pop()
    return parts, alpha


def _byte(value):
    """0-255, halves up: alpha 0.3 is 77, as Android's Color and browsers give."""
    return max(0, min(255, int(value + 0.5)))


def _hex(red, green, blue, alpha=1.0):
    rgb = "%02X%02X%02X" % (_byte(red), _byte(green), _byte(blue))
    if alpha >= 1.0:
        return "#" + rgb
    return "#%02X%s" % (_byte(alpha * 255), rgb)


def from_function(name, body):
    """The engine's hex for ``rgb(...)`` / ``hsl(...)``, or None if it cannot be read."""
    try:
        parts, alpha = _arguments(body)
        if len(parts) != 3:
            return None
        opacity = 1.0 if alpha is None else _alpha(alpha)
        if name.lower().startswith("rgb"):
            return _hex(_channel(parts[0]), _channel(parts[1]), _channel(parts[2]), opacity)
        red, green, blue = colorsys.hls_to_rgb(_hue(parts[0]), _percent(parts[2]),
                                               _percent(parts[1]))
        return _hex(red * 255, green * 255, blue * 255, opacity)
    except (ValueError, IndexError):
        return None


def from_css_hex(digits):
    """``RGBA`` / ``RRGGBBAA`` (CSS order) -> ``#AARRGGBB``, or ``#RRGGBB`` when opaque."""
    if len(digits) == 4:
        digits = "".join(d * 2 for d in digits)
    digits = digits.upper()
    if digits[6:] == "FF":
        return "#" + digits[:6]
    return "#" + digits[6:] + digits[:6]


# CSS's named colours. Tk knows most of them, so `color: orange` showed in the
# Previewer and reached the phone's XML as the word, which the build refused.
NAMED = {
    "aliceblue": "#F0F8FF", "antiquewhite": "#FAEBD7", "aqua": "#00FFFF",
    "aquamarine": "#7FFFD4", "azure": "#F0FFFF", "beige": "#F5F5DC",
    "bisque": "#FFE4C4", "black": "#000000", "blanchedalmond": "#FFEBCD",
    "blue": "#0000FF", "blueviolet": "#8A2BE2", "brown": "#A52A2A",
    "burlywood": "#DEB887", "cadetblue": "#5F9EA0", "chartreuse": "#7FFF00",
    "chocolate": "#D2691E", "coral": "#FF7F50", "cornflowerblue": "#6495ED",
    "cornsilk": "#FFF8DC", "crimson": "#DC143C", "cyan": "#00FFFF",
    "darkblue": "#00008B", "darkcyan": "#008B8B", "darkgoldenrod": "#B8860B",
    "darkgray": "#A9A9A9", "darkgreen": "#006400", "darkgrey": "#A9A9A9",
    "darkkhaki": "#BDB76B", "darkmagenta": "#8B008B", "darkolivegreen": "#556B2F",
    "darkorange": "#FF8C00", "darkorchid": "#9932CC", "darkred": "#8B0000",
    "darksalmon": "#E9967A", "darkseagreen": "#8FBC8F", "darkslateblue": "#483D8B",
    "darkslategray": "#2F4F4F", "darkslategrey": "#2F4F4F", "darkturquoise": "#00CED1",
    "darkviolet": "#9400D3", "deeppink": "#FF1493", "deepskyblue": "#00BFFF",
    "dimgray": "#696969", "dimgrey": "#696969", "dodgerblue": "#1E90FF",
    "firebrick": "#B22222", "floralwhite": "#FFFAF0", "forestgreen": "#228B22",
    "fuchsia": "#FF00FF", "gainsboro": "#DCDCDC", "ghostwhite": "#F8F8FF",
    "gold": "#FFD700", "goldenrod": "#DAA520", "gray": "#808080",
    "green": "#008000", "greenyellow": "#ADFF2F", "grey": "#808080",
    "honeydew": "#F0FFF0", "hotpink": "#FF69B4", "indianred": "#CD5C5C",
    "indigo": "#4B0082", "ivory": "#FFFFF0", "khaki": "#F0E68C",
    "lavender": "#E6E6FA", "lavenderblush": "#FFF0F5", "lawngreen": "#7CFC00",
    "lemonchiffon": "#FFFACD", "lightblue": "#ADD8E6", "lightcoral": "#F08080",
    "lightcyan": "#E0FFFF", "lightgoldenrodyellow": "#FAFAD2", "lightgray": "#D3D3D3",
    "lightgreen": "#90EE90", "lightgrey": "#D3D3D3", "lightpink": "#FFB6C1",
    "lightsalmon": "#FFA07A", "lightseagreen": "#20B2AA", "lightskyblue": "#87CEFA",
    "lightslategray": "#778899", "lightslategrey": "#778899", "lightsteelblue": "#B0C4DE",
    "lightyellow": "#FFFFE0", "lime": "#00FF00", "limegreen": "#32CD32",
    "linen": "#FAF0E6", "magenta": "#FF00FF", "maroon": "#800000",
    "mediumaquamarine": "#66CDAA", "mediumblue": "#0000CD", "mediumorchid": "#BA55D3",
    "mediumpurple": "#9370DB", "mediumseagreen": "#3CB371", "mediumslateblue": "#7B68EE",
    "mediumspringgreen": "#00FA9A", "mediumturquoise": "#48D1CC",
    "mediumvioletred": "#C71585", "midnightblue": "#191970", "mintcream": "#F5FFFA",
    "mistyrose": "#FFE4E1", "moccasin": "#FFE4B5", "navajowhite": "#FFDEAD",
    "navy": "#000080", "oldlace": "#FDF5E6", "olive": "#808000",
    "olivedrab": "#6B8E23", "orange": "#FFA500", "orangered": "#FF4500",
    "orchid": "#DA70D6", "palegoldenrod": "#EEE8AA", "palegreen": "#98FB98",
    "paleturquoise": "#AFEEEE", "palevioletred": "#DB7093", "papayawhip": "#FFEFD5",
    "peachpuff": "#FFDAB9", "peru": "#CD853F", "pink": "#FFC0CB",
    "plum": "#DDA0DD", "powderblue": "#B0E0E6", "purple": "#800080",
    "rebeccapurple": "#663399", "red": "#FF0000", "rosybrown": "#BC8F8F",
    "royalblue": "#4169E1", "saddlebrown": "#8B4513", "salmon": "#FA8072",
    "sandybrown": "#F4A460", "seagreen": "#2E8B57", "seashell": "#FFF5EE",
    "sienna": "#A0522D", "silver": "#C0C0C0", "skyblue": "#87CEEB",
    "slateblue": "#6A5ACD", "slategray": "#708090", "slategrey": "#708090",
    "snow": "#FFFAFA", "springgreen": "#00FF7F", "steelblue": "#4682B4",
    "tan": "#D2B48C", "teal": "#008080", "thistle": "#D8BFD8",
    "tomato": "#FF6347", "turquoise": "#40E0D0", "violet": "#EE82EE",
    "wheat": "#F5DEB3", "white": "#FFFFFF", "whitesmoke": "#F5F5F5",
    "yellow": "#FFFF00", "yellowgreen": "#9ACD32", "transparent": "#00000000",
}


def named(value):
    """``orange`` -> ``#FFA500``; anything that is not a CSS colour name, as it was."""
    if not isinstance(value, str):
        return value
    return NAMED.get(value.strip().lower(), value)


_PLAIN = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")
_WITH_ALPHA = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{4})$")


def _plain_rgb(color):
    raw = str(color or "").strip()
    if not _PLAIN.match(raw):
        return None
    digits = raw[1:]
    if len(digits) == 3:
        digits = "".join(d * 2 for d in digits)
    return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4))


def over(color, behind):
    """The plain colour the eye sees where ``color`` lies over ``behind``.

    ``color`` in the engine's form (``#AARRGGBB``, ``#ARGB``, ``transparent``)
    over a plain ``#RRGGBB`` / ``#RGB``. Anything else comes back as it was:
    an opaque colour, a ``var()``, or a backdrop that is not known.
    """
    raw = str(color or "").strip()
    under = _plain_rgb(behind)
    if under is None:
        return color
    if raw.lower() == "transparent":
        return str(behind).strip()
    if not _WITH_ALPHA.match(raw):
        return color
    digits = raw[1:]
    if len(digits) == 4:
        digits = "".join(d * 2 for d in digits)
    alpha = int(digits[:2], 16) / 255.0
    top = (int(digits[2:4], 16), int(digits[4:6], 16), int(digits[6:8], 16))
    return _hex(*(u + (t - u) * alpha for u, t in zip(under, top)))


def normalize_value(value):
    """Every colour in a stylesheet value, in the engine's form.

    Works on a whole value, so ``box-shadow: 0 4px 12px rgba(0,0,0,.3)`` and
    the colours of a gradient are read the same way as ``color: #0008``.
    """
    if not isinstance(value, str) or ("#" not in value and "(" not in value):
        return value

    def function(match):
        return from_function(match.group(1), match.group(2)) or match.group(0)

    # The hex the author wrote first: what rgba() becomes is already in the
    # engine's order, and read again as CSS's it was turned round a second
    # time (rgba(0, 0, 0, 0.5) came out #00800000).
    value = _HEX.sub(lambda match: from_css_hex(match.group(1)), value)
    return _FUNCTION.sub(function, value)


def shadow_colour(value):
    """The colour of a ``box-shadow`` as ``#AARRGGBB``, or None when it names
    none (``0 4px 12px`` alone is CSS's currentColor; ApkPy keeps black)."""
    for token in reversed(str(value or "").split()):
        token = named(token)
        if not isinstance(token, str) or not token.startswith("#"):
            continue
        digits = token[1:]
        if len(digits) == 3:
            digits = "".join(ch * 2 for ch in digits)
        if len(digits) == 6:
            return "#FF" + digits.upper()
        if len(digits) == 8:
            return "#" + digits.upper()
    return None
