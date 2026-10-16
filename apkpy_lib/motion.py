"""Shared motion timing for the Previewer and the Android compiler.

Like :mod:`apkpy_lib.theme` and :mod:`apkpy_lib.icons`, this module has no
Tkinter and no Android-build dependency.  Both backends resolve durations and
the easing curve from here, so a transition cannot last 180ms on the phone and
300ms on the desktop -- a divergence in *timing* is worse than one in colour,
because you cannot see it in a screenshot.

Four moments change visual state, and until now none of them had a duration:

* ``press``       -- a button acknowledging a touch
* ``visibility``  -- a component appearing or disappearing
* ``nav``         -- a bottom-bar item becoming active
* ``screen``      -- one screen replacing another

A preset sets the base duration; each moment scales it, so raising ``motion``
speeds or slows the whole app coherently instead of one widget at a time.
"""

import re

__all__ = [
    "PRESETS", "MOMENTS", "DEFAULT_PRESET",
    "normalise_preset", "parse_duration", "duration", "is_disabled",
    "ease", "android_interpolator",
    "normalise_press", "normalise_transition", "normalise_indicator",
    "PRESS_MODES", "SCREEN_TRANSITIONS", "NAV_INDICATORS",
    "STREAM_SPEEDS", "DEFAULT_STREAM", "stream_step",
]


# Base duration in milliseconds.  "subtle" is deliberately shorter than
# Material's 200ms baseline: ApkPy animates small components on mid-range
# phones, and a slow interface reads as a slow app.
PRESETS = {
    "none": 0,
    "subtle": 120,
    "standard": 180,
    "expressive": 260,
}

DEFAULT_PRESET = "standard"

# Multipliers per moment.  A press has to feel instant or it feels laggy; a
# whole screen moves further, so it is allowed more time.
MOMENTS = {
    "press": 0.5,
    "nav": 0.8,
    "visibility": 1.0,
    "screen": 1.5,
}

PRESS_MODES = ("none", "tint", "scale")
SCREEN_TRANSITIONS = ("none", "slide", "slide_up")
NAV_INDICATORS = ("none", "line", "pill")


def normalise_preset(value):
    """Accept a preset name, a number of milliseconds, or nothing."""
    if value is None:
        return DEFAULT_PRESET
    text = str(value).strip().lower()
    if text in PRESETS:
        return text
    if text in ("", "default"):
        return DEFAULT_PRESET
    if text in ("off", "false", "0"):
        return "none"
    if text in ("on", "true"):
        return DEFAULT_PRESET
    raise ValueError(
        "Theme(motion=...) expects one of %s, not %r"
        % (", ".join(repr(name) for name in PRESETS), value)
    )


def parse_duration(raw, default=None):
    """CSS duration -> milliseconds.  ``220ms``, ``0.22s``, ``220`` or ``none``."""
    if raw is None:
        return default
    if isinstance(raw, (int, float)):
        return max(0, int(round(raw)))
    text = str(raw).strip().lower()
    if text in ("", "none", "off", "false"):
        return 0
    match = re.match(r'^(-?\d+(?:\.\d+)?)\s*(ms|s)?$', text)
    if not match:
        return default
    amount = float(match.group(1))
    if match.group(2) == "s":
        amount *= 1000.0
    return max(0, int(round(amount)))


def duration(moment, preset=None, override=None):
    """Milliseconds for one moment, honouring a per-component override.

    ``override`` is the CSS value (``transition: 220ms``).  A preset of
    ``none`` wins over it: turning motion off has to turn it off everywhere,
    otherwise ``motion="none"`` would be a suggestion rather than a switch.
    """
    if moment not in MOMENTS:
        raise ValueError(
            "unknown motion moment %r; expected one of %s"
            % (moment, ", ".join(sorted(MOMENTS)))
        )
    name = normalise_preset(preset)
    if name == "none":
        return 0
    if override is not None:
        resolved = parse_duration(override, default=None)
        if resolved is not None:
            return resolved
    return int(round(PRESETS[name] * MOMENTS[moment]))


def is_disabled(preset=None):
    return normalise_preset(preset) == "none"


# --- The curve --------------------------------------------------------------
# Material's standard easing is the cubic bezier (0.4, 0.0, 0.2, 1.0), which
# Android exposes as @android:interpolator/fast_out_slow_in.  Reimplementing it
# here rather than approximating with ease-out is the whole point: the same
# progress value at the same moment on both sides.

_C1X, _C1Y, _C2X, _C2Y = 0.4, 0.0, 0.2, 1.0


def _bezier(t, a, b):
    return 3.0 * (1.0 - t) ** 2 * t * a + 3.0 * (1.0 - t) * t * t * b + t ** 3


def _bezier_slope(t, a, b):
    return (3.0 * (1.0 - t) ** 2 * a
            + 6.0 * (1.0 - t) * t * (b - a)
            + 3.0 * t * t * (1.0 - b))


def ease(progress):
    """Eased progress in ``[0, 1]`` for a linear ``progress`` in ``[0, 1]``.

    Solves the curve's x component for t by Newton-Raphson, then reads y --
    the standard way to evaluate a CSS/Material cubic bezier.
    """
    x = float(progress)
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    t = x
    for _ in range(8):
        slope = _bezier_slope(t, _C1X, _C2X)
        if abs(slope) < 1e-6:
            break
        t -= (_bezier(t, _C1X, _C2X) - x) / slope
        t = min(1.0, max(0.0, t))
    return _bezier(t, _C1Y, _C2Y)


def android_interpolator():
    """The platform resource that draws the same curve as :func:`ease`."""
    return "@android:interpolator/fast_out_slow_in"


# --- CSS / keyword vocabulary ----------------------------------------------
# Small, closed sets rather than an open animation API.  The Previewer runs on
# Tk, which has no vsync; a free-form API would drift from the phone in time,
# and timing drift is not something a test can catch after the fact.

def _one_of(value, allowed, label, default):
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in ("", "default"):
        return default
    if text in allowed:
        return text
    raise ValueError(
        "%s expects one of %s, not %r"
        % (label, ", ".join(repr(name) for name in allowed), value)
    )


def normalise_press(value):
    return _one_of(value, PRESS_MODES, "press:", "tint")


def normalise_transition(value):
    return _one_of(value, SCREEN_TRANSITIONS, "transition=", "none")


def normalise_indicator(value):
    return _one_of(value, NAV_INDICATORS, "bottom_nav(indicator=...)", "pill")


# --- Streamed text ----------------------------------------------------------
# Text arriving a few characters at a time, the way an answer does. The rate
# lives here for the same reason every other duration does: typing at 25ms on
# the phone and 40ms on the desktop is a difference you feel and cannot
# screenshot.
#
# (characters per tick, milliseconds per tick). Several characters per tick
# rather than one every few ms because a Handler and a Tk `after` both stop
# being accurate below about 10ms, and lying about the rate is the thing this
# module exists to prevent.

STREAM_SPEEDS = {
    "slow": (1, 45),
    "normal": (2, 25),
    "fast": (4, 12),
    "instant": (0, 0),
}
DEFAULT_STREAM = "normal"


def stream_step(speed=None, preset=None):
    """How much text to add, and how often.

    ``(0, 0)`` means put it all there at once -- what ``instant`` asks for, and
    what an app whose theme says ``motion="none"`` gets whatever it asked for.
    Somebody who turned animations off did not ask to watch text type itself.
    """
    if is_disabled(preset):
        return STREAM_SPEEDS["instant"]
    raw = str(speed or "").strip().lower() or DEFAULT_STREAM
    return STREAM_SPEEDS.get(raw, STREAM_SPEEDS[DEFAULT_STREAM])
