"""shimmer: a band of light that crosses a box, again and again.

``fill { shimmer: 2.4s; }`` (a colour may follow: ``shimmer: 2.4s
rgba(255, 255, 255, 0.35)``) is the shine a progress bar wears in a web app:
a gradient transparent -> colour -> transparent as wide as the box, carried
from one width to its left to one width to its right in the first 60% of each
period, easing in and out, and gone for the rest. The Previewer
(features/shimmer.py) and the phone (ApkpyShimmer) both place it with
``offset()``.
"""

import re

DEFAULT_MS = 2400
DEFAULT_COLOUR = "#59FFFFFF"     # white at 35%
SWEEP = 0.6


def parse(value):
    """``(milliseconds, colour)`` from the property, or None when unset/off."""
    raw = str(value or "").strip()
    if not raw or raw.lower() in ("none", "off", "0", "0s", "false"):
        return None
    ms, colour = DEFAULT_MS, DEFAULT_COLOUR
    for word in raw.split():
        timed = re.match(r"^(\d+(?:\.\d+)?)(ms|s)$", word, re.I)
        if timed:
            number = float(timed.group(1))
            ms = int(round(number if timed.group(2).lower() == "ms" else number * 1000))
        elif word.startswith("#") or word.lower() in ("white", "black"):
            colour = {"white": "#FFFFFF", "black": "#000000"}.get(word.lower(), word)
    return max(200, ms), colour


def offset(phase):
    """Where the band is, as a fraction of the box's width (-1 .. 1), for a
    phase 0 .. 1 of the period; None while it rests out of sight."""
    phase = phase % 1.0
    if phase >= SWEEP:
        return None
    p = phase / SWEEP
    p = p * p * (3.0 - 2.0 * p)          # ease-in-out
    return -1.0 + 2.0 * p


def strength(x):
    """How much of the colour shows at ``x`` (0 .. 1 across the band)."""
    if x <= 0.0 or x >= 1.0:
        return 0.0
    return 1.0 - abs(2.0 * x - 1.0)
