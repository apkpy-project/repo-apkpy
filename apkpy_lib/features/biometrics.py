"""The fingerprint check -- ``from apkpy_lib import biometrics``.

Android draws this dialog itself. ``BiometricPrompt`` is a system surface: an
app supplies a title, a subtitle and the words on the cancel button, and the
platform draws everything else. So there is nothing to style here either, and
the Previewer's job is to be a faithful *replica* rather than a design of its
own -- same words, same shape, same result, same timing.

What the two runtimes share exactly is the result vocabulary, which lives in
:mod:`apkpy_lib.core.features.biometrics` and is imported by both.

The desktop has no sensor, so the replica has to be driven by hand. The
affordance is the sensor itself:

* **click the fingerprint** -- a scan that matches;
* **right-click it** -- a scan that does not, which on Android keeps the prompt
  open and lets the person try again, so it does that here too;
* **cancel, Escape, or a click outside** -- ``(False, "cancelled")``.

That hint is drawn on the scrim, outside the card, so the card itself stays a
faithful copy of what the phone shows.
"""

from __future__ import annotations

from ..core.features.biometrics import (
    DEFAULT_CANCEL,
    DEFAULT_TITLE,
    REASONS,
    SUCCESS,
    normalise_prompt,
)

__all__ = ["BiometricsAPI", "biometrics", "REASONS"]

# Material's fingerprint dialog metrics, in dp. The Previewer runs at
# 1px = 1dp, so these are pixels here.
_CARD_WIDTH = 300
_CARD_PAD = 24
_ICON_SIZE = 56
_CORNER = 28

# What the status line says. Android writes these itself; the words are
# copied so a screenshot of the two sits side by side.
_TOUCH = "Touch the fingerprint sensor"
_NOT_RECOGNISED = "Not recognised. Try again."
_USE_PIN = "Use PIN"


class BiometricsAPI:
    """The device's fingerprint or face check, as one call.

        biometrics.unlock(title="Unlock", on_result=opened)

        def opened(ok, reason):
            if ok:
                on_click_navigate(vault)
            else:
                toast(reason)

    ``on_result`` receives ``(success, reason)``. ``reason`` is ``"ok"`` on
    success and otherwise one of ``cancelled``, ``no_hardware``,
    ``not_enrolled``, ``unavailable``, ``lockout`` or ``failed`` -- never an
    empty string, so an app can always say something useful.

    A scan that simply does not match is not a result: the prompt stays open
    and the person tries again, on both runtimes.
    """

    #: The reasons ``on_result`` can receive, and what each means.
    reasons = REASONS

    def unlock(self, title=None, subtitle=None, on_result=None,
               cancel_text=None, allow_pin=False):
        """Show the prompt and report the outcome.

        ``allow_pin=True`` lets the person fall back to the device PIN,
        pattern or password. The cancel button disappears in that mode,
        because Android's builder refuses a negative button alongside the
        device-credential option and draws its own way out instead.
        """
        prompt = normalise_prompt(title, subtitle, cancel_text, allow_pin)
        _show_prompt(prompt, on_result)


biometrics = BiometricsAPI()


# --- The replica -----------------------------------------------------------

def _report(callback, success, reason):
    if not callback:
        return
    from ..ui import report_exception
    try:
        callback(success, reason)
    except Exception as exc:                       # pragma: no cover - user code
        report_exception(exc, context="biometrics.unlock callback")


def _show_prompt(prompt, callback):
    """Draw the dialog over the running app, or report why we cannot."""
    from .. import ui

    # ui._app is a LAZY PROXY: reading .root constructs the Previewer. Asking
    # it for a window is therefore how you accidentally open an empty one --
    # during `apkpy build`, or in a unit test. Ask whether it was built first.
    app = getattr(ui, "_app", None)
    if app is None or getattr(app, "_instance", None) is None:
        # No window, and there must not become one. The phone answers when it
        # cannot show the prompt, so answer here too rather than raising.
        _report(callback, False, "unavailable")
        return
    root = getattr(app, "root", None)
    body = getattr(app, "body", None)
    if root is None or body is None:
        _report(callback, False, "unavailable")
        return

    import tkinter as tk

    tokens = ui.global_styles.get("__theme__", {})
    surface = tokens.get("surface_high") or tokens.get("surface", "#1C1B1F")
    on_surface = tokens.get("text", "#E6E1E5")
    muted = tokens.get("text_secondary", "#CAC4D0")
    primary = tokens.get("primary", "#D0BCFF")
    error = tokens.get("error", "#F2B8B5")
    background = tokens.get("background", "#000000")

    ramp = _sizes(tokens)

    root.update_idletasks()
    host_w = max(1, body.winfo_width())
    host_h = max(1, body.winfo_height())

    width = min(_CARD_WIDTH, max(240, host_w - 48))
    inner = width - 2 * _CARD_PAD

    # Something always sits in the action row: the app's cancel wording, or
    # the system's PIN fallback when it supplied one instead.
    action_text = prompt["cancel_text"] or (_USE_PIN if prompt["allow_pin"] else "")

    scrim = tk.Frame(body, bg=_scrim_colour(background), cursor="arrow")
    scrim.place(x=0, y=0, relwidth=1, relheight=1)

    # Tall to begin with, then trimmed to what the text actually needed. The
    # subtitle wraps -- the bundled example already runs to two lines -- so
    # guessing one line per string collides the moment somebody writes three.
    card = tk.Canvas(body, width=width, height=host_h, bg=_scrim_colour(background),
                     highlightthickness=0, bd=0)
    card.place(x=0, y=0, width=width, height=host_h)

    def _bottom(item):
        box = card.bbox(item)
        return box[3] if box else 0

    y = _CARD_PAD
    title = card.create_text(width // 2, y, text=prompt["title"], fill=on_surface,
                             font=(ui.get_native_font(""), -ramp["title"], "bold"),
                             width=inner, justify="center", anchor="n")
    y = _bottom(title) + 6
    if prompt["subtitle"]:
        subtitle = card.create_text(
            width // 2, y, text=prompt["subtitle"], fill=muted,
            font=(ui.get_native_font(""), -ramp["body"]),
            width=inner, justify="center", anchor="n")
        y = _bottom(subtitle)
    y += 26
    icon_y = y + _ICON_SIZE // 2
    y += _ICON_SIZE + 22
    status_y = y
    y += ramp["caption"] + 4
    if action_text:
        y += 14
        cancel_y = y
        y += ramp["body"] + 4
    else:
        cancel_y = None
    height = y + _CARD_PAD - 4

    card_x = (host_w - width) // 2
    card_y = max(24, (host_h - height) // 2 - 24)
    card.configure(height=height)
    card.place_configure(x=card_x, y=card_y, height=height)

    plate = ui._create_rounded_rect(card, 0, 0, width - 1, height - 1, _CORNER,
                                    fill=surface, outline="")
    try:
        card.tag_lower(plate)
    except Exception:
        pass

    state = {"closed": False}

    def _close(reason, success=False):
        if state["closed"]:
            return
        state["closed"] = True
        for widget in (card, scrim, hint):
            try:
                widget.destroy()
            except Exception:
                pass
        try:
            root.unbind("<Escape>", state.get("escape"))
        except Exception:
            pass
        _report(callback, success, reason)

    ui._draw_material_icon(card, "fingerprint", width // 2, icon_y, primary,
                           size=_ICON_SIZE, tags="sensor")
    # A generous invisible target: on the phone the sensor is a place you
    # touch, not a glyph you have to hit.
    card.create_oval(width // 2 - 34, icon_y - 34, width // 2 + 34, icon_y + 34,
                     outline="", fill="", tags="sensor")
    card.itemconfig("sensor", state="normal")
    card.tag_bind("sensor", "<Enter>",
                  lambda _e: card.configure(cursor="hand2"))
    card.tag_bind("sensor", "<Leave>",
                  lambda _e: card.configure(cursor=""))

    status = card.create_text(width // 2, status_y, text=_TOUCH, fill=muted,
                              font=(ui.get_native_font(""), -ramp["caption"]),
                              width=inner, justify="center", anchor="n")

    if cancel_y is not None:
        card.create_text(
            width - _CARD_PAD, cancel_y, text=action_text,
            fill=primary, anchor="ne",
            font=(ui.get_native_font(""), -ramp["body"], "bold"), tags="cancel")
        card.tag_bind("cancel", "<Enter>",
                      lambda _e: card.configure(cursor="hand2"))
        card.tag_bind("cancel", "<Leave>",
                      lambda _e: card.configure(cursor=""))
        if prompt["allow_pin"]:
            # A correct PIN authenticates on Android, so it lands in
            # onAuthenticationSucceeded like a matching finger does.
            card.tag_bind("cancel", "<Button-1>",
                          lambda _e: _close(SUCCESS, success=True))
        else:
            card.tag_bind("cancel", "<Button-1>",
                          lambda _e: _close("cancelled"))

    # --- the desktop's own affordance, outside the card ---
    # Kept to one short line: it has to fit a 360dp phone, and it is scenery
    # rather than part of the dialog.
    hint = tk.Label(
        body, text="Click the sensor  ·  right-click to fail  ·  Esc to cancel",
        bg=_scrim_colour(background),
        fg=ui._mix_hex(_scrim_colour(background), muted, 0.65),
        font=(ui.get_native_font(""), -ramp["caption"]),
        wraplength=max(200, host_w - 32), justify="center",
    )
    hint.place(x=host_w // 2, y=card_y + height + 18, anchor="n")

    def _scan_ok(_event=None):
        _close(SUCCESS, success=True)

    def _scan_bad(_event=None):
        # Android keeps the prompt open here, so this must not report a
        # result -- it only changes the line under the sensor.
        if state["closed"]:
            return
        card.itemconfig(status, text=_NOT_RECOGNISED, fill=error)

    card.tag_bind("sensor", "<Button-1>", _scan_ok)
    card.tag_bind("sensor", "<Button-3>", _scan_bad)
    scrim.bind("<Button-1>", lambda _e: _close("cancelled"))
    state["escape"] = root.bind("<Escape>", lambda _e: _close("cancelled"), "+")

    # The prompt arrives on the shared `visibility` beat, so it takes the same
    # time to appear as anything else the app shows.
    _fade_in(ui, card, scrim, hint)


def _sizes(tokens):
    """Title, body and caption sizes, from the shared type ramp."""
    def _px(name, fallback):
        raw = tokens.get(name)
        if not raw:
            return fallback
        try:
            return int(round(float(str(raw).replace("px", "").strip())))
        except (TypeError, ValueError):
            return fallback

    return {
        "title": _px("text-xl", 20),
        "body": _px("text-base", 14),
        "caption": _px("text-sm", 12),
    }


def _scrim_colour(background):
    from ..ui import _mix_color

    return _mix_color(str(background or "#000000"), "#000000", 0.55)


def _fade_in(ui, card, scrim, hint):
    """Nudge the card up onto its mark over the shared visibility duration."""
    from .. import motion as _motion

    duration = _motion.duration("visibility", ui._motion_preset())
    if duration <= 0:
        return
    try:
        start_y = int(card.place_info().get("y", 0))
    except Exception:
        return
    offset = 12
    frames = max(1, int(duration / 16))

    def step(index):
        if index > frames:
            return
        try:
            eased = _motion.ease(index / float(frames))
            card.place_configure(y=int(round(start_y + offset * (1.0 - eased))))
            card.after(16, lambda: step(index + 1))
        except Exception:
            pass

    card.place_configure(y=start_y + offset)
    step(1)
