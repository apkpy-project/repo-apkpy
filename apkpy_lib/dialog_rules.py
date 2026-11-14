"""alert() and confirm() in the app's own style, the same on both sides.

With a ``dialog { ... }`` block in the stylesheet the two dialogs stop being
the system's and are drawn from these parts:

    dialog          the card: background, border, border-radius, padding
    dialog_title    color, font-size, font-weight
    dialog_message  color, font-size
    dialog_ok       the confirming button: background (a colour or a
                    gradient), color, border, border-radius, font-size
    dialog_cancel   the other button, the same properties

What each part falls back to is decided here, once, and both the Previewer
(features/styled_dialog.py) and the phone (core/features/styled_dialog.py)
read the answer. The card is 340dp wide at most and keeps 24dp from each
side of the screen; behind it the screen dims to 60% black, as Android's
own dialogs do.
"""

import re

PARTS = ("dialog", "dialog_title", "dialog_message", "dialog_ok", "dialog_cancel")
MAX_WIDTH = 340
SIDE_GAP = 24
SCRIM = 0.6
BUTTON_GAP = 12


def wanted(styles):
    """True when the stylesheet styles the dialog."""
    return bool((styles or {}).get("dialog"))


def width(screen_width):
    return max(120, min(MAX_WIDTH, int(screen_width) - 2 * SIDE_GAP))


def _px(value, default):
    match = re.match(r"\s*(-?[\d.]+)", str(value or ""))
    return float(match.group(1)) if match else float(default)


def _first(value):
    """The first length of a shorthand: ``24px 20px`` -> 24."""
    return str(value or "").split()[0] if str(value or "").split() else ""


def _bold(value, default):
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    return raw in ("bold", "bolder") or (raw.isdigit() and int(raw) >= 600)


def _button(style, background, colour, border=None):
    return {
        "background": style.get("background-color") or background,
        "gradient": next((style.get(key) for key in ("background-image", "background")
                          if "gradient(" in str(style.get(key, ""))), None),
        "color": style.get("color") or colour,
        "border": style.get("border-color") or border,
        "border_width": _px(style.get("border-width"), 1 if (style.get("border-color") or border) else 0),
        "radius": _px(style.get("border-radius"), 14),
        "size": _px(style.get("font-size"), 15),
        "bold": _bold(style.get("font-weight"), True),
        "padding": _px(_first(style.get("padding")), 12),
    }


def look(styles):
    """Every part, with the fallbacks filled in. Colours stay as written
    (``rgba()``, ``var(--x)``, a gradient); each side resolves them."""
    styles = styles or {}
    tokens = styles.get("__theme__", {}) or {}
    part = {name: dict(styles.get(name, {}) or {}) for name in PARTS}
    card = part["dialog"]
    surface = tokens.get("surface") or "#FFFFFF"
    text = tokens.get("text") or "#1B1B1F"
    muted = tokens.get("text_secondary") or text
    primary = tokens.get("primary") or "#6750A4"
    border = tokens.get("border") or muted
    return {
        "card": {
            "background": card.get("background-color") or surface,
            "border": card.get("border-color"),
            "border_width": _px(card.get("border-width"), 1 if card.get("border-color") else 0),
            "radius": _px(card.get("border-radius"), 28),
            "padding": _px(_first(card.get("padding")), 24),
        },
        "title": {
            "color": part["dialog_title"].get("color") or card.get("color") or text,
            "size": _px(part["dialog_title"].get("font-size"), 20),
            "bold": _bold(part["dialog_title"].get("font-weight"), True),
        },
        "message": {
            "color": part["dialog_message"].get("color") or muted,
            "size": _px(part["dialog_message"].get("font-size"), 15),
            "bold": _bold(part["dialog_message"].get("font-weight"), False),
        },
        "ok": _button(part["dialog_ok"], primary, "#FFFFFF"),
        "cancel": _button(part["dialog_cancel"], "#00000000", text, border),
    }
