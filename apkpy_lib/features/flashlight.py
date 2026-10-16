"""The torch -- ``from apkpy_lib import flashlight``.

A desktop has no flash unit, so the Previewer cannot light one. What it *can*
do is be honest about the state, and the state is the whole of this API: an
app asks the torch to change and later asks whether it is on.

So the Previewer keeps the light and shows it where a device thing belongs --
in the status strip, next to the signal and the battery, as an amber bolt.
It is not app chrome and it is not pretending to be: nothing on a real phone
puts a torch icon there. It is the Previewer saying "the light is on" in the
one place that is already the Previewer's own.

**The stand-in always succeeds.** ``available()`` answers true and every
change works, the same choice the Previewer makes for the camera and the
scanner, because a rehearsal where half the branches never run is not a
rehearsal. The words the phone can answer instead live in
:data:`apkpy_lib.core.features.flashlight.REASONS`, and the reference page
lists them; an app that wants to see one of those has to see it on a phone.
"""

from __future__ import annotations

from ..core.features.flashlight import OK, REASONS

__all__ = ["FlashlightAPI", "flashlight", "REASONS"]


class FlashlightAPI:
    """Turn the torch on the back of the phone on and off."""

    # The words a phone can answer, read from the compiler's table so the two
    # runtimes cannot drift into knowing different ones.
    reasons = REASONS

    def __init__(self):
        self._on = False

    # ── the three that act ────────────────────────────────────────────────────

    def on(self, on_result=None):
        """Light it. ``on_result(ok, reason)`` if you want to know."""
        return self._set(True, on_result)

    def off(self, on_result=None):
        """Put it out."""
        return self._set(False, on_result)

    def toggle(self, on_result=None):
        """On if it is off, off if it is on -- including when something else
        on the phone turned it on."""
        return self._set(not self._on, on_result)

    # ── the two that answer ───────────────────────────────────────────────────

    def is_on(self):
        """Whether the light is lit right now."""
        return self._on

    def available(self):
        """Whether this device has a torch. Always true in the Previewer."""
        return True

    # ── internals ─────────────────────────────────────────────────────────────

    def _set(self, on, on_result):
        self._on = bool(on)
        self._show()
        self._answer(on_result, True, OK)
        return OK

    def _show(self):
        """Repaint the status strip, if there is a Previewer window to paint.

        Asked for by state rather than pushed: reading ``.root`` on the lazy
        proxy would BUILD a window, so an ``apkpy build`` that merely imports
        the module would open one.
        """
        from .. import ui

        app = getattr(ui, "_app", None)
        if app is None or getattr(app, "_instance", None) is None:
            return
        try:
            ui.refresh_status_glyphs()
        except Exception:
            # A repaint that fails must not take the app's click with it.
            pass

    @staticmethod
    def _answer(on_result, ok, reason):
        if on_result is None:
            return
        try:
            on_result(ok, reason)
        except TypeError:
            on_result(ok)


flashlight = FlashlightAPI()
