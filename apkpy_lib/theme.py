"""Shared theme primitives for the Previewer and Android compiler.

This module deliberately has no Tkinter or Android-build dependencies.  Both
rendering backends consume the same normalized token/style dictionaries, which
keeps theme behaviour deterministic and prevents preview/device drift.
"""

import ast
import re

from . import motion as _motion


_PALETTES = {
    "light": {
        "primary": "#6750A4",
        "secondary": "#625B71",
        "background": "#FFFBFE",
        "surface": "#F7F2FA",
        # Two more planes, so "a layer above" and "a well below" stop being a
        # hand-written hex.  Light mode stacks *away* from white and dark mode
        # stacks *towards* it, which is why the pair is written out per mode
        # rather than mixed from ``surface`` at render time.
        "surface_low": "#FFFFFF",
        "surface_high": "#ECE6F0",
        "text": "#1D1B20",
        "text_secondary": "#49454F",
        "on_primary": "#FFFFFF",
        "error": "#B3261E",
        "success": "#2E7D32",
        "border": "#79747E",
        # Material's outline is a real border; a divider drawn in it looks
        # like a mistake.  This is Material's outlineVariant -- the hairline
        # every list in the examples was writing by hand.
        "border_subtle": "#CAC4D0",
    },
    "dark": {
        "primary": "#D0BCFF",
        "secondary": "#CCC2DC",
        "background": "#141218",
        "surface": "#211F26",
        "surface_low": "#1D1B20",
        "surface_high": "#2B2930",
        "text": "#E6E1E5",
        "text_secondary": "#CAC4D0",
        "on_primary": "#381E72",
        "error": "#F2B8B5",
        "success": "#81C784",
        "border": "#938F99",
        "border_subtle": "#49454F",
    },
}


#: The type ramp, as multiples of ``Theme(font_size=)``.
#:
#: Sizes were the last thing in this library with no vocabulary at all: the
#: 29 shipped examples between them name **17 different font sizes**, and
#: 13/14/15px -- three ways of writing the same intent -- account for 32 of
#: them.  Every one of those is a decision taken alone and never reviewed.
#:
#: The steps are Material's own sizes, not a geometric series, because the
#: rule here is fidelity to the phone: 11 is labelSmall, 12 bodySmall, 14
#: bodyMedium, 16 bodyLarge, 20 titleLarge, 24 headlineSmall, 32 headlineLarge.
#: At the default base of 14 they come out as those integers exactly, which is
#: also what keeps :func:`label_variant_style` byte-identical to what it
#: emitted before the ramp existed.
_TYPE_SCALE = {
    "text-xs": 11.0 / 14.0,
    "text-sm": 12.0 / 14.0,
    "text-base": 1.0,
    "text-lg": 16.0 / 14.0,
    "text-xl": 20.0 / 14.0,
    "text-2xl": 24.0 / 14.0,
    "text-3xl": 32.0 / 14.0,
}

#: Leading, as ``line-height`` already reads a bare number: a multiple of the
#: font size.  Both runtimes have understood that for as long as
#: ``line-height`` has existed; what was missing was three names worth using.
_LEADING = {
    "leading-tight": "1.2",
    "leading-normal": "1.45",
    "leading-loose": "1.7",
}

#: The step a component falls back to when the stylesheet names no size.
#:
#: It needs a name because the two runtimes had each picked their own number
#: for it and nobody could see that they had: a plain ``label("oi")`` drew at
#: 14px in the Previewer and 16sp on the phone -- the most-used component in
#: the library, 14% out, silently, in every app ever built with it. That is
#: the whole argument for a ramp in one sentence. The phone's figure wins,
#: because the phone is what the app actually is.
DEFAULT_TEXT_STEP = "text-lg"


def default_text_size(theme_tokens=None):
    """The px figure a component uses when the stylesheet names no size."""
    raw = (theme_tokens or {}).get(DEFAULT_TEXT_STEP)
    return int(round(_number(raw))) if raw else 16

_TOKEN_RE = re.compile(r"var\(\s*--([a-zA-Z0-9_-]+)\s*\)")


class TokenValue(str):
    """A resolved token value that still remembers which token it came from.

    Everything downstream treats it as the string it is, so no renderer had to
    learn a new type. What the extra attribute buys is the one distinction
    runtime theming needs: `#C96442` written by hand must stay `#C96442`, while
    the same colour arriving from `var(--primary)` has to become a resource
    reference that a night-mode table can answer differently.

    Mixing, slicing or formatting one produces an ordinary string, which is
    correct -- a colour derived from a token is not that token any more.
    """

    __slots__ = ("token",)

    def __new__(cls, value, token):
        self = str.__new__(cls, value)
        self.token = token
        return self


def token_of(value):
    """The token a value came from, or None if it was written literally."""
    return getattr(value, "token", None)
BUTTON_VARIANTS = frozenset({"filled", "outlined", "tonal", "text", "danger", "icon"})
CARD_VARIANTS = frozenset({"elevated", "filled", "outlined"})
LABEL_VARIANTS = frozenset({"title", "subtitle", "body", "overline"})
SKELETON_VARIANTS = frozenset({"music_card", "list", "card", "text"})
MEDIA_RULE_PREFIX = "__media__|"


def _css_px(value):
    if isinstance(value, (int, float)):
        return f"{value:g}px"
    return str(value)


class Theme:
    """A compact, immutable-at-render design-token configuration.

    Keyword colours override the selected Material-inspired light/dark palette.
    CSS can reference any token with ``var(--primary)``, ``var(--surface)``, etc.
    """

    _COLOR_KEYS = tuple(_PALETTES["light"])

    def __init__(self, mode="light", primary=None, secondary=None,
                 background=None, surface=None, text=None, text_secondary=None,
                 on_primary=None, error=None, success=None, border=None,
                 radius=14, spacing=12, font_family="sans-serif",
                 motion="standard", font_size=14, surface_low=None,
                 surface_high=None, border_subtle=None):
        mode = str(mode).strip().lower()
        if mode not in _PALETTES:
            raise ValueError("Theme mode must be 'light' or 'dark'")
        self.mode = mode
        palette = dict(_PALETTES[mode])
        supplied = {
            "primary": primary, "secondary": secondary,
            "background": background, "surface": surface, "text": text,
            "text_secondary": text_secondary, "on_primary": on_primary,
            "error": error, "success": success, "border": border,
            "surface_low": surface_low, "surface_high": surface_high,
            "border_subtle": border_subtle,
        }
        # Kept so counterpart() can rebuild this theme in the other mode with
        # the author's own colours and nothing else.
        self._supplied = dict(supplied)
        palette.update({k: str(v) for k, v in supplied.items() if v is not None})
        # A cor de um botao cheio tem de ser legivel SOBRE a primary escolhida.
        # O default da paleta e' um roxo-escuro do Material: quem trocou a
        # primary por um laranja ficava com texto azul-escuro por cima, e a
        # etiqueta desaparecia. Se o autor escolheu on_primary, manda ele.
        if primary is not None and on_primary is None:
            palette["on_primary"] = _contrast_text(palette["primary"])
        # The same argument, one layer down. An author who picked a warm
        # #262624 surface and never heard of the other two would otherwise get
        # Material's purple-grey planes stacked on top of it -- exactly the
        # accident that put an unwanted blue slab behind every container.
        #
        # The rule is the same in both modes, which is what makes it a rule
        # and not a pair of special cases: *higher* is further from the
        # background and towards the ink, *lower* is nearer the background,
        # and a subtle border is the outline pulled most of the way back into
        # whatever is behind it.
        if surface is not None or background is not None:
            if surface_high is None:
                palette["surface_high"] = _mix_color(
                    palette["surface"], palette["text"], 0.06)
            if surface_low is None:
                palette["surface_low"] = _mix_color(
                    palette["surface"], palette["background"], 0.55)
        if border_subtle is None and (border is not None
                                      or surface is not None):
            # A third of the way from the surface towards the outline, which
            # is where Material puts its own outlineVariant in both modes
            # (33 -> 73 -> 147 dark, 247 -> 202 -> 121 light: ~35% each time).
            # Pulling it towards the *background* instead looked reasonable
            # and rendered as no line at all -- on a theme whose outline is
            # already gentle, three levels of difference is nothing.
            palette["border_subtle"] = _mix_color(
                palette["surface"], palette["border"], 0.35)
        self._palette = palette
        self.radius = radius
        self.spacing = spacing
        self.font_family = str(font_family)
        # One number moves the whole app, the way `radius` and `spacing`
        # already do. The ramp is relative to it, so an author who wants
        # larger text raises this instead of editing every rule.
        self.font_size = _number(font_size) or 14.0
        # Raises on a bad name rather than silently not animating.
        self.motion = _motion.normalise_preset(motion)

    #: What "dark" and "light" actually mean. Surfaces are the difference
    #: between the two modes, so a hand-picked one belongs to the mode it was
    #: written for and must not be carried into the other.
    _SURFACE_KEYS = (
        "background", "surface", "surface_low", "surface_high",
        "text", "text_secondary", "border", "border_subtle",
    )

    def counterpart(self):
        """The same theme in the other mode.

        Runtime appearance switching needs both tables in the APK, and an
        author who declared one should not have to declare the other.

        The accent carries over and the surfaces flip. That split is the whole
        rule, and it is the only one that gives a usable answer: an orange
        primary is orange in both modes, while a background chosen at
        ``#1B1B19`` was chosen *because* the mode was dark -- carrying it into
        light mode would produce a light mode that is still dark, which is a
        switch that appears to do nothing.
        """
        chosen = {
            key: value for key, value in self._supplied.items()
            if value is not None and key not in self._SURFACE_KEYS
        }
        return Theme(
            mode="light" if self.mode == "dark" else "dark",
            radius=self.radius, spacing=self.spacing,
            font_family=self.font_family, motion=self.motion,
            font_size=self.font_size,
            **chosen
        )

    @property
    def tokens(self):
        # Tagged, so a value that reaches a layout can say which token put it
        # there. A colour written by hand carries no tag and never moves.
        values = {
            key: TokenValue(value, key) for key, value in self._palette.items()
        }
        values.update({
            "radius": _css_px(self.radius),
            "spacing": _css_px(self.spacing),
            "font-family": self.font_family,
            "font-size": _css_px(round(self.font_size)),
            "motion": self.motion,
            # The bottom bar's active pill. A tint of the surface, not the
            # full-strength primary: the checked icon is drawn in primary, so
            # a solid primary pill swallowed it whole.
            "nav_indicator": TokenValue(
                _mix_color(
                    self._palette["surface"], self._palette["primary"], 0.22),
                "nav_indicator",
            ),
        })
        # The ramp and its leading. Plain strings, not TokenValue: these are
        # sizes, and only colours have a night-mode table to be answered from.
        # `var(--text-lg)` is replaced by `16px` before either renderer looks
        # at it, which is why neither one needed to learn anything new.
        values.update(self.type_scale())
        values.update(_LEADING)
        return values

    def type_scale(self):
        """The ramp for this theme, as ``{"text-lg": "16px", ...}``."""
        return {
            name: _css_px(int(round(self.font_size * ratio)))
            for name, ratio in _TYPE_SCALE.items()
        }

    def styles(self):
        """Return semantic defaults. User CSS is merged after these rules."""
        t = self.tokens
        radius = t["radius"]
        spacing = t["spacing"]
        return {
            "body": {
                "background-color": t["background"],
                "color": t["text"],
                "font-family": t["font-family"],
                "gap": spacing,
                "padding": spacing,
            },
            "label": {"color": t["text"], "font-family": t["font-family"]},
            "button": {
                "background-color": t["primary"], "color": t["on_primary"],
                "pressed-color": t["secondary"], "border-radius": radius,
                "padding": f"{spacing} {_css_px(_number(self.spacing) * 1.35)}",
                "font-family": t["font-family"], "font-weight": "bold",
            },
            "inputs": {
                "background-color": t["surface"], "color": t["text"],
                "accent-color": t["primary"],
                "border-color": t["border"], "border-width": "1px",
                "focus-border-color": t["primary"], "border-radius": radius,
                "padding": spacing, "font-family": t["font-family"],
            },
            # A container groups things; it is not a surface. It used to be
            # born with the theme's surface, a radius and a padding, so every
            # grouping in an app arrived as a panel nobody asked for -- and
            # against a background the app chose itself, the Material surface
            # reads as a blue slab. Of the 22 containers in the shipped
            # examples, 16 already declared their own background and 17 their
            # own padding: the default was a tax most code was paying to undo.
            # ``card`` is the one that has a surface, which is what its name
            # has always meant.
            "container": {},
            "card": {
                "background-color": t["surface"],
                "border-color": t["border"], "border-width": "0px",
                "border-radius": radius, "padding": spacing,
                "box-shadow": "0 3px 8px #00000033",
            },
            "list": {
                "background-color": t["surface"], "color": t["text"],
                "border-color": t["border"],
            },
            "list_row": {
                "background-color": t["surface"], "color": t["text"],
                "subtitle-color": t["text_secondary"],
                "trailing-color": t["text_secondary"],
                "icon-color": t["text"],
                "pressed-color": _mix_color(t["surface"], t["text"], 0.08),
                "border-radius": radius,
                # No vertical padding: min-height owns the row's height, which
                # is how a list keeps every row the same size whether or not it
                # carries a subtitle.
                "padding": f"0px {_css_px(_number(self.spacing) * 1.35)}",
                "min-height": "56px",
                "font-family": t["font-family"],
            },
            "carousel": {"color": t["text"], "background-color": t["background"]},
            "grid": {"color": t["text"], "background-color": t["background"]},
            "spinner": {"color": t["primary"]},
            "skeleton": {
                "background-color": _mix_color(t["surface"], t["text"], 0.14),
                "border-radius": _css_px(max(6, _number(self.radius) * 0.55)),
            },
            "empty_state": {
                "background-color": "#00000000", "color": t["text"],
                "border-radius": radius, "padding": _css_px(_number(self.spacing) * 2),
            },
            "error_state": {
                "background-color": "#00000000", "color": t["text"],
                "border-radius": radius, "padding": _css_px(_number(self.spacing) * 2),
            },
            "app_bar": {
                "background-color": t["surface"], "color": t["text"],
                "font-family": t["font-family"],
            },
            "sliver_app_bar": {
                "background-color": t["surface"], "color": t["text"],
                "font-family": t["font-family"],
            },
        }

    def __repr__(self):
        return (f"Theme(mode={self.mode!r}, primary={self._palette['primary']!r}, "
                f"motion={self.motion!r})")


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        match = re.search(r"-?\d+(?:\.\d+)?", str(value))
        return float(match.group(0)) if match else 0.0


def normalize_button_variant(variant):
    """Validate and normalize a public Material button variant."""
    if variant is None or str(variant).strip() == "":
        return None
    normalized = str(variant).strip().lower()
    if normalized not in BUTTON_VARIANTS:
        allowed = ", ".join(sorted(BUTTON_VARIANTS))
        raise ValueError(f"Unknown button variant {variant!r}. Use one of: {allowed}")
    return normalized


def _normalize_variant(variant, allowed, component, default=None):
    if variant is None or str(variant).strip() == "":
        return default
    normalized = str(variant).strip().lower()
    if normalized not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(
            f"Unknown {component} variant {variant!r}. Use one of: {choices}"
        )
    return normalized


def normalize_card_variant(variant):
    return _normalize_variant(variant, CARD_VARIANTS, "card", "elevated")


def normalize_label_variant(variant):
    return _normalize_variant(variant, LABEL_VARIANTS, "label")


def normalize_skeleton_variant(variant):
    return _normalize_variant(
        variant, SKELETON_VARIANTS, "skeleton", "music_card"
    )


TEXT_TRANSFORMS = ("uppercase", "none")


def normalize_text_transform(value, default="uppercase"):
    """Resolve ``text-transform`` for a button label.

    Material 2 shouts button labels, which is why ApkPy has always uppercased
    them and why the default stays ``uppercase`` -- no compiled app changes
    appearance.  ``none`` opts out, which is what every modern composer or chip
    wants.

    Only these two are offered because only these two are a *display*
    attribute on both sides: Android has ``android:textAllCaps`` and nothing
    else.  ``capitalize`` and ``lowercase`` would have to rewrite the string at
    build time and would then not apply to text set at runtime -- a divergence
    that only shows up on the phone, which is the failure mode this project
    exists to avoid.
    """
    raw = str(value or "").strip().lower()
    if raw == "":
        return default
    if raw in TEXT_TRANSFORMS:
        return raw
    return None


def apply_text_transform(text, value, default="uppercase"):
    """Render ``text`` the way ``text-transform`` asks.

    A value neither backend understands keeps the current look rather than
    silently changing it; the compiler reports it as U2021.
    """
    resolved = normalize_text_transform(value, default) or default
    return str(text).upper() if resolved == "uppercase" else str(text)


TEXT_ALIGNS = ("left", "center", "right")

_TEXT_ALIGN_ALIASES = {"start": "left", "end": "right", "centre": "center"}


def normalize_text_align(value, default=None):
    """Resolve ``text-align`` for a label or a button.

    Three values, because three is what both sides can do: Android has
    ``android:gravity`` and Tk has ``anchor``/``justify``.  ``justify`` is left
    out on purpose -- Android only grew ``android:justificationMode`` at API
    26 and ApkPy targets 24, so it would be a phone-only effect.

    Returns ``default`` when nothing is set and ``None`` for a value neither
    side understands, which the compiler reports as U2022.
    """
    raw = str(value or "").strip().lower()
    if raw == "":
        return default
    raw = _TEXT_ALIGN_ALIASES.get(raw, raw)
    if raw in TEXT_ALIGNS:
        return raw
    return None


# A font's own line box, as a share of its size.  Roboto sits at ~1.17; 1.2 is
# the usual rounding and the number CSS calls "normal".  Only used when the
# caller cannot measure the real font -- the compiler never can, the Previewer
# always can.
NATURAL_LINE_HEIGHT = 1.2

_LENGTH_RE = re.compile(r"^(-?[0-9]*\.?[0-9]+)\s*(px|dp|sp|em|rem|%)?$")


def _parse_length(value):
    """Split a CSS length into ``(number, unit)``, or ``None``."""
    match = _LENGTH_RE.match(str(value or "").strip().lower())
    if not match:
        return None
    try:
        return float(match.group(1)), (match.group(2) or "")
    except ValueError:
        return None


def letter_spacing_px(value, font_size):
    """``letter-spacing`` as pixels of tracking between glyphs.

    ``em``/``rem``/``%`` resolve against ``font_size`` so one declaration means
    the same thing on both sides.  A bare number is read as px.  ``normal``, an
    absent value, and anything unparseable all mean no tracking.
    """
    raw = str(value or "").strip().lower()
    if raw in ("", "normal"):
        return 0.0
    parsed = _parse_length(raw)
    if parsed is None:
        return 0.0
    number, unit = parsed
    size = float(font_size or 0) or 14.0
    if unit in ("em", "rem"):
        return number * size
    if unit == "%":
        return number * size / 100.0
    return number


def letter_spacing_em(value, font_size):
    """The em figure ``android:letterSpacing`` wants."""
    size = float(font_size or 0) or 14.0
    return letter_spacing_px(value, size) / size


def line_height_px(value, font_size):
    """``line-height`` as the height of one line box in px, or ``None``.

    A bare number is a multiple of the font size, the way CSS reads it -- which
    is why this differs from ``letter-spacing``, where a bare number is px.
    ``normal`` returns ``None``, meaning "leave the font's own line box alone".
    """
    raw = str(value or "").strip().lower()
    if raw in ("", "normal"):
        return None
    parsed = _parse_length(raw)
    if parsed is None:
        return None
    number, unit = parsed
    size = float(font_size or 0) or 14.0
    if unit in ("em", "rem", ""):
        return number * size
    if unit == "%":
        return number * size / 100.0
    return number


def line_spacing_extra(value, font_size, natural=None):
    """The leading ``line-height`` adds on top of the font's own line box, px.

    ``natural`` is the line box the font already occupies.  The Previewer
    measures it; the compiler cannot measure Roboto at build time and falls
    back to :data:`NATURAL_LINE_HEIGHT`.  A ``line-height`` asking for less room
    than the font already takes gives ``0.0`` rather than a negative leading --
    Android clamps there anyway, and so the two sides agree.
    """
    target = line_height_px(value, font_size)
    if target is None:
        return 0.0
    size = float(font_size or 0) or 14.0
    if natural is None:
        natural = NATURAL_LINE_HEIGHT * size
    return max(0.0, target - float(natural))


def _length_px(value, default=0.0):
    """A CSS length as a plain number of pixels.

    ``px``/``dp``/``sp`` are one to one here and a bare number is px.  Relative
    units have nothing to resolve against on a divider, so they read as px too
    rather than silently becoming zero.
    """
    parsed = _parse_length(value)
    return float(default) if parsed is None else parsed[0]


def divider_spec(style, default_width=1):
    """The hairline a container draws between its children, or ``None``.

    Opt-in, and deliberately so: a container grows dividers only once it names
    a colour, so no app already written changes shape.  Android gets
    ``android:showDividers="middle"``, which draws between children and never
    at the edges -- the thing that separates a grouped list from a stack of
    boxes -- and the Previewer packs a strip of the same height in the same
    places.

    ``divider-inset`` starts the line past the leading edge, which is how a
    settings list keeps its hairlines clear of the icon column.
    """
    color = str(style.get('divider-color', '') or '').strip()
    if not color or color.lower() in ('none', 'transparent'):
        return None
    return {
        'color': color,
        'width': max(1, int(round(_length_px(style.get('divider-width'),
                                             default_width)))),
        'inset': max(0, int(round(_length_px(style.get('divider-inset'), 0)))),
    }


def _hex_rgb(value):
    value = str(value or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        return None
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _mix_color(base, overlay, amount):
    base_rgb = _hex_rgb(base)
    overlay_rgb = _hex_rgb(overlay)
    if base_rgb is None or overlay_rgb is None:
        return str(overlay or base)
    amount = max(0.0, min(1.0, float(amount)))
    values = [round(a + (b - a) * amount) for a, b in zip(base_rgb, overlay_rgb)]
    return "#" + "".join(f"{value:02X}" for value in values)


NAV_FALLBACK = {"surface": "#1E293B", "primary": "#6366F1",
                "text_secondary": "#64748B"}

# The bottom bar's geometry, in dp, drawn from these by both runtimes. What
# the bar carries adds up to its height: 6 above, the 32dp pill, 4 between
# pill and label, a 12sp label (~16dp tall) and 6 below -- 64. On a phone the
# Material 2 bar kept its own 56dp and squeezed the label against the edge;
# `android:minHeight` is what sets it.
NAV_BAR_DP = 64
NAV_ITEM_PAD_DP = 6
NAV_LABEL_GAP_DP = 4

# The active item's label is bold: Material 1.11 turns
# itemTextAppearanceActiveBoldEnabled on unless told otherwise, so every
# phone whose bold works has always drawn it that way. It was once read as
# "only the tint changes" -- measured on a Xiaomi whose font theme lost every
# bold (see core/features/font_weight.py).
NAV_ACTIVE_LABEL_BOLD = True


def nav_colors(tokens):
    """The bottom bar's four colours -- bar, active, inactive, pill -- read
    from one set of tokens by both runtimes.

    Without a Theme() the phone used to paint the bar with the dark fallback
    and its items with the light palette: a lilac pill and dark-grey labels on
    a navy bar, while the Previewer drew the same bar with colours that belong
    to it. Now both take the bar, and everything on it, from the same place.
    """
    tokens = tokens or {}
    bar = tokens.get("surface") or NAV_FALLBACK["surface"]
    active = tokens.get("primary") or NAV_FALLBACK["primary"]
    inactive = tokens.get("text_secondary") or NAV_FALLBACK["text_secondary"]
    pill = tokens.get("nav_indicator") or _mix_color(bar, active, 0.22)
    return bar, active, inactive, pill


# Above this weighted luminance a surface is light and wants dark ink. The
# Activity applies the same number to its status bar icons at run time
# (_apkpySystemIconsFollowBackground), so keep the two in step.
LIGHT_SURFACE_LUMINANCE = 0.62


def _contrast_text(color):
    rgb = _hex_rgb(color)
    if rgb is None:
        return "#FFFFFF"
    luminance = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255
    return "#1D1B20" if luminance > LIGHT_SURFACE_LUMINANCE else "#FFFFFF"


def system_icon_color(background):
    """The clock and status icons over a screen without an app bar.

    Android picked them from day or night mode alone, so a dark screen in a
    light app -- a chat, a player, a story -- had dark icons on a dark strip:
    no clock at all. They follow the colour behind them now, on the phone
    and in the Previewer."""
    return _contrast_text(background)


def button_variant_style(styles, variant):
    """Return Material 3 defaults for one explicit button variant."""
    variant = normalize_button_variant(variant)
    if variant is None:
        return {}

    tokens = dict(_PALETTES["light"])
    tokens.update(styles.get("__theme__", {}))
    radius = tokens.get("radius", "20px")
    surface = tokens["surface"]
    primary = tokens["primary"]
    secondary = tokens["secondary"]
    error = tokens["error"]
    tonal = _mix_color(surface, secondary, 0.22)
    tonal_pressed = _mix_color(surface, secondary, 0.34)

    common = {
        "border-radius": radius,
        "font-weight": "bold",
        "border-width": "0px",
        "border-color": "none",
    }
    variants = {
        "filled": {
            "background-color": primary,
            "color": tokens["on_primary"],
            "pressed-color": secondary,
        },
        "outlined": {
            "background-color": "#00000000",
            "color": primary,
            "border-color": tokens["border"],
            "border-width": "1px",
            "pressed-color": tonal,
        },
        "tonal": {
            "background-color": tonal,
            "color": tokens["text"],
            "pressed-color": tonal_pressed,
        },
        "text": {
            "background-color": "#00000000",
            "color": primary,
            "pressed-color": tonal,
            "padding": "10px 14px",
        },
        "danger": {
            "background-color": error,
            "color": _contrast_text(error),
            "pressed-color": _mix_color(error, "#000000", 0.16),
        },
        "icon": {
            "background-color": "#00000000",
            "color": primary,
            "pressed-color": tonal,
            "border-radius": "999px",
            "padding": "10px",
        },
    }
    common.update(variants[variant])
    common.update(styles.get(f"button:{variant}", {}))
    return common


def card_variant_style(styles, variant):
    variant = normalize_card_variant(variant)
    tokens = dict(_PALETTES["light"])
    tokens.update(styles.get("__theme__", {}))
    common = {
        "border-radius": tokens.get("radius", "14px"),
        "padding": tokens.get("spacing", "12px"),
    }
    variants = {
        "elevated": {
            "background-color": tokens["surface"],
            "border-width": "0px",
            "box-shadow": "0 3px 8px #00000033",
        },
        "filled": {
            "background-color": _mix_color(
                tokens["surface"], tokens["primary"], 0.10
            ),
            "border-width": "0px", "box-shadow": "none",
        },
        "outlined": {
            "background-color": tokens["surface"],
            "border-color": tokens["border"], "border-width": "1px",
            "box-shadow": "none",
        },
    }
    result = dict(common)
    result.update(variants[variant])
    result.update(styles.get(f"card:{variant}", {}))
    return result


def label_variant_style(styles, variant):
    variant = normalize_label_variant(variant)
    if variant is None:
        return {}
    tokens = dict(_PALETTES["light"])
    tokens.update(styles.get("__theme__", {}))
    # The four roles now name steps on the ramp instead of carrying loose
    # numbers, which is what makes ``Theme(font_size=)`` move them. At the
    # default base of 14 the steps *are* 20/14/11, so nothing an existing app
    # generates changes; the fallbacks say the same thing for a stylesheet
    # that never named a Theme and so has no ramp to read.
    variants = {
        "title": {
            "color": tokens["text"],
            "font-size": tokens.get("text-xl", "20px"),
            "font-weight": "bold", "margin-bottom": "4px",
        },
        "subtitle": {
            "color": tokens["text_secondary"],
            "font-size": tokens.get("text-base", "14px"),
            "margin-bottom": "8px",
        },
        "body": {
            "color": tokens["text"],
            "font-size": tokens.get("text-base", "14px"),
            "margin-bottom": "8px",
        },
        "overline": {
            "color": tokens["secondary"],
            "font-size": tokens.get("text-xs", "11px"),
            "font-weight": "bold", "margin-bottom": "4px",
        },
    }
    result = dict(variants[variant])
    result.update(styles.get(f"label:{variant}", {}))
    return result


def _media_number(value):
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(match.group(0)) if match else None


def media_matches(condition, viewport):
    """Return whether a compact CSS media query matches ``(width, height)``."""
    if not viewport or len(viewport) < 2:
        return False
    width, height = float(viewport[0]), float(viewport[1])
    tests = re.findall(r"\(\s*([\w-]+)\s*:\s*([^)]+)\)", str(condition))
    if not tests:
        return False
    for feature, raw_value in tests:
        feature = feature.lower()
        value = str(raw_value).strip().lower()
        number = _media_number(value)
        if feature == "min-width" and (number is None or width < number):
            return False
        if feature == "max-width" and (number is None or width > number):
            return False
        if feature == "min-height" and (number is None or height < number):
            return False
        if feature == "max-height" and (number is None or height > number):
            return False
        if feature == "orientation":
            if value == "landscape" and width <= height:
                return False
            if value == "portrait" and height < width:
                return False
        elif feature not in {"min-width", "max-width", "min-height", "max-height"}:
            return False
    return True


def _media_rule_parts(key):
    if not str(key).startswith(MEDIA_RULE_PREFIX):
        return None
    parts = str(key).split("|", 3)
    return (parts[2], parts[3]) if len(parts) == 4 else None


def has_responsive_styles(styles, selectors=None):
    """Detect rules/dimensions that need Android resource variants."""
    # ``min-width`` used to be here. It is not a property any renderer reads,
    # so writing one bought four extra layout folders and changed nothing on
    # screen. ``grid-template-columns`` only decides anything under
    # ``display: grid`` -- on its own it is inert, and paying for the variants
    # is the same waste one step along.
    responsive_props = {"max-width", "min-height"}
    eligible = {str(item).lstrip('.') for item in selectors} if selectors else None
    for selector, values in (styles or {}).items():
        if str(selector).startswith(MEDIA_RULE_PREFIX):
            parsed = _media_rule_parts(selector)
            if parsed and (eligible is None or parsed[1].lstrip('.') in eligible):
                return True
            continue
        if eligible is not None and str(selector).lstrip('.') not in eligible:
            continue
        is_grid = str(values.get("display", "")).strip().lower() == "grid"
        for key, value in values.items():
            text = str(value).lower()
            if key in responsive_props or re.search(r"[\d.]+(?:vw|vh|%)\b", text):
                return True
            if key == "grid-template-columns" and is_grid:
                return True
    return False


_BUBBLE_ALIGN = {'flex-start': 0, 'start': 0, 'left': 0,
                 'flex-end': 1, 'end': 1, 'right': 1, 'center': 2}


def mini_player_colors(tokens, own_style=None):
    """The fixed mini-player's bar, title (and play icon) and artist colours.

    Its own block -- ``mini_player { }`` or its ``id`` -- first
    (``background-color``, ``color``, ``subtitle-color``), then the theme's
    ``surface``/``text``/``text_secondary``, then the dark bar it always had.
    It could only follow the theme: a light app got a light bar over a dark
    player screen, with nothing to write to change it."""
    tokens = tokens or {}
    own = own_style or {}
    background = own.get('background-color') or tokens.get('surface') or '#181818'
    text = own.get('color') or own.get('title-color') or tokens.get('text') or '#FFFFFF'
    muted = own.get('subtitle-color') or tokens.get('text_secondary') or '#B3B3B3'
    return background, text, muted


TAB_INDICATOR_HEIGHT = 2


def pager_colors(tokens, own_style=None):
    """The tab strip of a ``pager``: its background, the colour of the tab on
    screen (text, icon), the others, the indicator under the one on screen,
    and an optional line under the strip.

    The pager's own block first (``background-color``, ``active-color``,
    ``color``, ``indicator-color``, ``border-color``), then the theme. With
    no background the strip is transparent -- the screen shows through, as
    the Previewer and the phone both draw it -- and with no border-color there
    is no line."""
    tokens = tokens or {}
    own = own_style or {}
    active = own.get('active-color') or tokens.get('primary') or '#6750A4'
    return {
        'background': own.get('background-color') or '',
        'active': active,
        'inactive': own.get('color') or tokens.get('text_secondary') or '#64748B',
        'indicator': own.get('indicator-color') or active,
        'divider': own.get('border-color') or '',
    }


def tab_bar_height(has_text, has_icon):
    """Material's tab heights: 48dp for text or an icon, 72dp for an icon
    above its text."""
    return 72 if (has_text and has_icon) else 48


def card_text_colors(own_style):
    """Title and subtitle colours of a grid or carousel card, from the
    component's own block (``title-color``, or ``color``; ``subtitle-color``).

    The phone painted them white and #B3B3B3 whatever the stylesheet said,
    and the Previewer took the body's text colour instead -- dark titles in
    a light theme, white ones on the phone. The body is left out: a card's
    text sits on its cover and the shelf, not on the page."""
    style = own_style or {}
    title = style.get('title-color') or style.get('color') or '#FFFFFF'
    subtitle = style.get('subtitle-color') or '#B3B3B3'
    return title, subtitle


_BADGE_AT_END = ('end', 'right', 'trailing', 'flex-end')


def badge_at_end(style):
    """``badge-position: end`` on a virtual_collection: the row's time goes to
    the top right, level with the title, and the badge sits under it -- the
    unread count of every conversation list. By default the badge follows the
    subtitle, as it always has."""
    return str((style or {}).get('badge-position', '')).strip().lower() in _BADGE_AT_END


def collection_bubbles(styles, comp_id, variant_names):
    """How a virtual_collection draws its rows as bubbles.

    ``thread:mine { align-self: flex-end; max-width: 78%; }`` makes that kind
    of row a bubble on the right that hugs its text (a chat);
    ``item-border-radius`` and ``gap`` on the collection round its rows and
    space them. Returns ``({variant: (align, max_width, is_percent)},
    (radius, gap) or None)`` -- align 0 start, 1 end, 2 centre; -1 for a
    radius or gap not given. Nothing set, nothing returned, so a collection
    that asks for none of it is drawn as it always was.
    """
    styles = styles or {}
    table = {}
    for name in variant_names or ():
        own = dict(styles.get('virtual_collection:%s' % name, {}))
        if comp_id:
            own.update(styles.get('%s:%s' % (comp_id, name), {}))
        if 'align-self' not in own and 'max-width' not in own:
            continue
        align = _BUBBLE_ALIGN.get(str(own.get('align-self', '')).strip().lower(), 0)
        raw = str(own.get('max-width', '') or '').strip().lower()
        width = _number(raw) if raw else 0.0
        table[name] = (align, width, 1 if raw.endswith('%') else 0)
    own = styles.get(comp_id or '', {}) if comp_id else {}
    shape = None
    if 'item-border-radius' in own or 'gap' in own:
        shape = (int(_number(own['item-border-radius'])) if 'item-border-radius' in own else -1,
                 int(_number(own['gap'])) if 'gap' in own else -1)
    return table, shape


def component_style(styles, comp_type=None, comp_id=None, include_body=True,
                    variant=None, viewport=None, row_variant=None):
    """Resolve the shared cascade: body -> type -> variant -> component id.

    ``row_variant`` refines one row of a collection and so lands *after* the
    id block: ``thread { }`` is what every turn shares and ``thread:user { }``
    is what one kind of turn changes. It reuses the ``name:variant`` selector
    the button and card variants already read.
    """
    aliases = {
        "input_field": "inputs", "list_view": "list", "image": "image",
    }
    kind = aliases.get(comp_type, comp_type)
    merged = dict(styles.get("body", {})) if include_body else {}
    if kind:
        merged.update(styles.get(kind, {}))
    if kind == "button" and variant is not None:
        merged.update(button_variant_style(styles, variant))
    elif kind == "card":
        merged.update(card_variant_style(styles, variant))
    elif kind == "label" and variant is not None:
        merged.update(label_variant_style(styles, variant))
    if comp_id:
        merged.update(styles.get(comp_id, {}))
    if row_variant:
        if kind:
            merged.update(styles.get("%s:%s" % (kind, row_variant), {}))
        if comp_id:
            merged.update(styles.get("%s:%s" % (comp_id, row_variant), {}))
    if viewport:
        eligible = []
        if include_body:
            eligible.append("body")
        if kind:
            eligible.append(kind)
        if kind == "button" and variant is not None:
            eligible.append(f"button:{normalize_button_variant(variant)}")
        elif kind == "card":
            eligible.append(f"card:{normalize_card_variant(variant)}")
        elif kind == "label" and variant is not None:
            eligible.append(f"label:{normalize_label_variant(variant)}")
        if comp_id:
            eligible.append(str(comp_id))
        if row_variant:
            if kind:
                eligible.append("%s:%s" % (kind, row_variant))
            if comp_id:
                eligible.append("%s:%s" % (comp_id, row_variant))
        for key, values in styles.items():
            parsed = _media_rule_parts(key)
            if parsed is None:
                continue
            condition, selector = parsed
            if selector.lstrip('.') in eligible and media_matches(condition, viewport):
                merged.update(values)
    return merged


def input_accent_color(styles, comp_id=None, fallback="#4CAF50"):
    """Resolve a control accent without reusing the regular input surface.

    An ID-specific ``background-color`` remains a legacy switch accent, while
    ``accent-color`` is the unambiguous option for semantic input styles.
    """
    id_style = styles.get(comp_id, {}) if comp_id else {}
    semantic = styles.get("inputs", {})
    tokens = styles.get("__theme__", {})
    return (
        id_style.get("accent-color")
        or id_style.get("accentcolor")
        or id_style.get("background-color")
        or id_style.get("backgroundcolor")
        or semantic.get("accent-color")
        or semantic.get("accentcolor")
        or tokens.get("primary")
        or semantic.get("background-color")
        or semantic.get("backgroundcolor")
        or fallback
    )


def _unknown_token_error(name, selector, prop, tokens):
    """A `var(--x)` naming a token that does not exist.

    It used to resolve to itself: the literal text ``var(--muted)`` travelled
    all the way into the layout XML, and the mistake surfaced forty seconds
    later as an AAPT link failure whose advice -- that the project folder
    still holds files from an earlier generation -- is about something else
    entirely. Reported here, in the one module both runtimes read, it is
    caught by whichever one you run first.
    """
    from .diagnostics import ApkpyError
    import difflib

    known = sorted(tokens)
    close = difflib.get_close_matches(name.replace('-', '_'), known, n=1)
    suggestions = []
    if close:
        suggestions.append('Did you mean var(--%s)?' % close[0])
    suggestions.append('The tokens are: %s.' % ', '.join(known))
    suggestions.append(
        'A colour of your own goes in as itself, for example #C96442.'
    )
    raise ApkpyError(
        '%r is not a theme token.' % ('--' + name),
        code='U2028',
        title='This stylesheet asks for a theme token that does not exist',
        cause=(
            'var(--name) is replaced by the theme token of that name before '
            'either renderer sees it. A name with no token behind it has '
            'nothing to be replaced by, so the text stays as written and '
            'reaches Android as a colour it cannot parse.'
        ),
        expected='one of the theme tokens, or a literal value',
        received='%s { %s: var(--%s); }' % (selector, prop, name),
        suggestions=suggestions,
        docs='https://repo-apkpy.pages.dev/themes-styling/',
    )


#: What each token *is*, for the one check below. Anything not listed is a
#: colour -- the palette is the open part of the table, and a new colour token
#: should not have to be registered in two places to behave.
_TOKEN_KINDS = dict(
    [(name, "a size") for name in _TYPE_SCALE],
    **{
        "radius": "a size", "spacing": "a size", "font-size": "a size",
        "font-family": "a typeface name", "motion": "a motion preset",
        **{name: "a line-height multiplier" for name in _LEADING},
    }
)


def _kind_mismatch_error(name, value, selector, prop, wanted, got):
    from .diagnostics import ApkpyError

    if wanted == "a colour":
        alternatives = sorted(
            token for token in _PALETTES["light"] if token != name
        )
        advice = (
            'A colour token goes here: %s.'
            % ', '.join('var(--%s)' % t for t in alternatives[:6])
        )
    else:
        advice = (
            'A size token goes here: %s.'
            % ', '.join('var(--%s)' % t for t in _TYPE_SCALE)
        )
    raise ApkpyError(
        'var(--%s) is %s, and %s wants %s.' % (name, got, prop, wanted),
        code='U2031',
        title='This token is the wrong kind for the property it is in',
        cause=(
            'Tokens are substituted as text, so the value reaches the '
            'renderers as whatever the token held. %r arrives where %s was '
            'expected, and neither side can do anything sensible with it: a '
            'size in a colour slot dies at Android\'s colour parser, and a '
            'colour in a size slot silently becomes the first digits in the '
            'hex -- a font-size of 21px from #211F26.'
            % (str(value), wanted)
        ),
        expected=wanted,
        received='%s { %s: var(--%s); }  /* %s */' % (
            selector, prop, name, str(value)),
        suggestions=[advice],
        docs='https://repo-apkpy.pages.dev/themes-styling/',
    )


def _check_token_kind(name, value, selector, prop, tokens):
    """Refuse a token whose kind the property cannot use.

    The ramp put ``--text-lg`` next to ``--text``, three characters apart and
    meaning entirely different things. This is the check that keeps the pair
    from being a footgun.
    """
    from .core.style_parser import COLOR_PROPERTIES

    if name not in tokens:
        name = name.replace('-', '_')
    kind = _TOKEN_KINDS.get(name, "a colour")
    if prop in COLOR_PROPERTIES:
        if kind != "a colour":
            _kind_mismatch_error(name, value, selector, prop, "a colour", kind)
    elif kind == "a colour" and prop in _SIZE_PROPERTIES:
        _kind_mismatch_error(name, value, selector, prop, "a size", kind)


#: Properties measured in px or in multiples of the font size. A colour landing
#: in one of these is the silent half of the trap: ``_number()`` finds the
#: first digits in the hex and carries on.
_SIZE_PROPERTIES = frozenset((
    'font-size', 'letter-spacing', 'line-height', 'subtitle-size',
    'trailing-size', 'border-width', 'border-radius',
    'padding', 'padding-top', 'padding-right', 'padding-bottom',
    'padding-left', 'margin', 'margin-top', 'margin-right', 'margin-bottom',
    'margin-left', 'gap', 'divider-width', 'divider-inset',
    'width', 'height', 'min-height', 'max-width', 'icon-size', 'item-size',
))


def _resolve_tokens(styles, tokens):
    """Replace every ``var(--name)`` in a style table, in place."""
    for selector, values in styles.items():
        for key, value in tuple(values.items()):
            # Every value is stringified, whether or not it holds a token:
            # both renderers read these tables as text, and a number that
            # stayed a number here used to come out as "12" from one side and
            # 12 from the other. A value that already arrived tagged keeps its
            # tag -- str() would strip it, and the theme's own defaults are
            # exactly the values that need to survive.
            text = str(value)
            if 'var(' not in text:
                values[key] = (
                    value if isinstance(value, TokenValue) else text
                )
                continue

            def resolve_token(match, _sel=selector, _key=key):
                name = match.group(1)
                if name in tokens:
                    return tokens[name]
                underscored = name.replace('-', '_')
                if underscored in tokens:
                    return tokens[underscored]
                _unknown_token_error(name, _sel, _key, tokens)

            resolved = _TOKEN_RE.sub(resolve_token, text)
            # A value that is nothing but one token reference keeps that
            # token's identity. A composite -- "0 3px 8px var(--border)" --
            # does not: half of it was written by hand, and a resource
            # reference cannot stand for the whole thing.
            whole = _TOKEN_RE.fullmatch(text.strip())
            if whole is not None:
                name = whole.group(1)
                # Only when the value is one token and nothing else: a
                # composite -- "0 3px 8px var(--border)" -- is half hand-written
                # and its property says nothing useful about the parts.
                _check_token_kind(name, resolved, selector, key, tokens)
                if name not in tokens:
                    name = name.replace('-', '_')
                resolved = TokenValue(resolved, name)
            values[key] = resolved
    return styles


def apply_theme(user_styles, theme):
    """Merge theme defaults with CSS rules and resolve CSS token references."""
    user_styles = user_styles or {}
    if theme is None:
        # An app that never names a Theme still has one: the generated
        # apkpy_theme.xml is written from this same default palette, which is
        # why var(--primary) resolving to #6750A4 here invents nothing. It
        # used to resolve to itself, and the literal text `var(--primary)`
        # travelled into the layout and died at AAPT -- so the token worked or
        # not depending on whether the app happened to name a theme.
        #
        # Only the tokens are resolved: merging the theme's default styles
        # would change the XML of every app that never asked for a theme.
        return _resolve_tokens(
            {k: dict(v) for k, v in user_styles.items()}, Theme().tokens
        )
    merged = {k: dict(v) for k, v in theme.styles().items()}
    for selector, values in user_styles.items():
        merged.setdefault(selector, {}).update(values)
    _resolve_tokens(merged, theme.tokens)
    merged["__theme__"] = dict(theme.tokens, mode=theme.mode)
    return merged


def theme_from_ast(tree):
    """Extract the literal Theme passed to run(theme=...) without executing code."""
    definitions = {}
    selected = None

    def parse_call(node):
        if not isinstance(node, ast.Call):
            return None
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "Theme"):
            return None
        kwargs = {}
        for kw in node.keywords:
            if kw.arg is None:
                return None
            try:
                kwargs[kw.arg] = ast.literal_eval(kw.value)
            except (ValueError, TypeError):
                return None
        try:
            return Theme(**kwargs)
        except (TypeError, ValueError):
            return None

    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            parsed = parse_call(value)
            if parsed is not None:
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        definitions[target.id] = parsed
    # run(...) normally lives inside ``if __name__ == '__main__'``; walk the
    # whole tree after collecting top-level definitions so that common pattern
    # is handled without executing the source.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "run":
            for kw in node.keywords:
                if kw.arg == "theme":
                    if isinstance(kw.value, ast.Name):
                        selected = definitions.get(kw.value.id)
                    else:
                        selected = parse_call(kw.value)
    return selected


# --- Avatars ----------------------------------------------------------------
# A row that shows who is speaking needs a mark for the name, and the mark has
# to be the SAME mark on both runtimes: the same two letters, over the same
# colour.  One table, read by the Previewer directly and written into the
# generated Java as a literal, is what stops the desktop and the phone from
# disagreeing about who is blue.
AVATAR_PALETTE = (
    "#7C6BF2", "#2E8B7A", "#C2643D", "#3B72C4",
    "#A2547E", "#4F7A2B", "#B08114", "#5C6B8A",
)


_AVATAR_WORDS = re.compile(r"[ \t\n\x0b\f\r]+")


def avatar_initials(name):
    r"""Up to two initials for a display name; empty for an empty name.

    Words are split on the same characters Java's ``\s+`` matches, and each
    initial is one character, so a name cannot produce two letters here and
    three on the phone.
    """
    parts = [part for part in _AVATAR_WORDS.split(str(name or "")) if part]
    return "".join(part[0].upper()[:1] for part in parts[:2])


def avatar_color(name):
    """Pick a palette entry from a name, the way the generated Java does.

    The sum is over UTF-16 code units, because that is what Java's
    ``charAt`` walks -- summing Python code points instead would put an
    emoji-bearing name on a different colour on each side.
    """
    units = str(name or "").encode("utf-16-le")
    total = 0
    for index in range(0, len(units), 2):
        total += units[index] | (units[index + 1] << 8)
    return AVATAR_PALETTE[total % len(AVATAR_PALETTE)]


def avatar_text_color(background):
    """Readable ink for an avatar circle, by the same rule as ``on_primary``."""
    return _contrast_text(background)
