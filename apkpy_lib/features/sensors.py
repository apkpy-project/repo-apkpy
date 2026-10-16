"""What the phone feels -- ``from apkpy_lib import sensors, battery``.

A laptop has no step counter, no proximity sensor and nothing worth calling a
compass. So the Previewer does what it does for the scanner: it says plainly
that it is standing in, and hands you the controls.

Watching a sensor opens a small panel with one row per sensor being watched --
a button that shakes, a dial that turns, a slider for the light, a switch for
near and far. The readings it produces go through the *same* threshold and the
*same* formatting rule the phone uses, read from
:mod:`apkpy_lib.core.features.sensors`, so a callback that fires here fires
there and the text is character for character the same.

**Being able to rehearse this matters more than usual.** A shake is awkward to
test on a phone tethered to a desk, and a proximity sensor needs a hand over
the earpiece. The panel is how those branches get exercised at all.

**battery is real here.** ``battery.level()`` reads the same number the drawn
status strip shows, and moving its slider moves the little battery icon in the
Previewer's status bar too -- because an app that says 14%% next to an icon
showing 80%% is a lie the Previewer would be telling on the app's behalf.
"""

from __future__ import annotations

from ..core.features.sensors import (
    REASONS, SENSORS, SHAKE_G, THRESHOLDS, format_value, passes_threshold,
    shake_detected,
    VECTOR_SENSORS, normalize_vector,
)

__all__ = ["SensorsAPI", "sensors", "BatteryAPI", "battery", "REASONS"]

_PANEL_WIDTH = 300

# What each stand-in starts at, in the unit the sensor reports.
_START = {"compass": 0.0, "light": 300.0, "proximity": 0.0, "steps": 0.0,
          "accelerometer": (0.0, 0.0, 9.80665), "gyroscope": (0.0, 0.0, 0.0),
          "pressure": 1013.2}


class _Panel:
    """The stand-in window. Built once, and only when something is watched."""

    def __init__(self):
        self.window = None
        self.rows = {}

    # ── building ─────────────────────────────────────────────────────────────

    def ensure(self, root):
        import tkinter as tk

        if self.window is not None:
            try:
                if self.window.winfo_exists():
                    # Closing the panel only withdraws it -- watching another
                    # sensor has to bring it back, or the controls are gone
                    # for the rest of the run with no way to ask for them.
                    self.window.deiconify()
                    return True
            except Exception:
                pass
        self.window = tk.Toplevel(root)
        self.window.title("Sensores")
        self.window.transient(root)
        self.window.resizable(False, False)
        self.window.configure(bg="#262624")
        self.rows = {}

        tk.Label(
            self.window, text="PREVIEWER, NAO SAO SENSORES A SERIO",
            bg="#262624", fg="#9C9A93", font=("Segoe UI", 8, "bold"),
        ).pack(padx=16, pady=(14, 8), anchor="w")

        self.body = tk.Frame(self.window, bg="#262624")
        self.body.pack(padx=16, pady=(0, 14), fill="x")

        self.window.protocol("WM_DELETE_WINDOW", self._hide)
        try:
            self.window.update_idletasks()
            self.window.geometry("+%d+%d" % (root.winfo_rootx() + root.winfo_width() + 12,
                                             root.winfo_rooty() + 40))
        except Exception:
            pass
        return True

    def _hide(self):
        try:
            self.window.withdraw()
        except Exception:
            pass

    def add(self, name, api):
        """One row for one watched sensor."""
        import tkinter as tk

        if name in self.rows:
            return
        frame = tk.Frame(self.body, bg="#262624")
        frame.pack(fill="x", pady=(0, 10))
        tk.Label(frame, text=name, bg="#262624", fg="#F5F4EF",
                 font=("Segoe UI", 9, "bold"), width=14, anchor="w").pack(side="left")

        if name in VECTOR_SENSORS:
            controls = tk.Frame(frame, bg="#262624")
            controls.pack(side="left", fill="x", expand=True)
            limit = 20 if name == "accelerometer" else 10

            def moved(text, axis):
                values = list(api._values.get(name, _START[name]))
                values[axis] = float(text)
                api._feed(name, values)

            for axis, axis_name in enumerate(("x", "y", "z")):
                scale = tk.Scale(
                    controls, label=axis_name, from_=-limit, to=limit,
                    resolution=0.01, orient="horizontal", length=170,
                    bg="#262624", fg="#F5F4EF", troughcolor="#1B1B19",
                    highlightthickness=0, relief="flat", showvalue=True,
                )
                scale.set(api._values.get(name, _START[name])[axis])
                scale.configure(command=lambda text, a=axis: moved(text, a))
                scale.pack(fill="x")
        elif name == "shake":
            tk.Button(frame, text="Agitar", relief="flat", bg="#C96442",
                      fg="#FFFFFF", command=lambda: api._fire_shake()).pack(side="left")
        elif name == "proximity":
            var = tk.IntVar(value=0)
            tk.Checkbutton(
                frame, text="perto", variable=var, bg="#262624", fg="#F5F4EF",
                selectcolor="#1B1B19", activebackground="#262624",
                activeforeground="#F5F4EF",
                command=lambda: api._feed("proximity", float(var.get())),
            ).pack(side="left")
        elif name == "steps":
            for step in (1, 10):
                tk.Button(
                    frame, text="+%d" % step, relief="flat", bg="#3A3A37",
                    fg="#F5F4EF", width=4,
                    command=lambda n=step: api._feed(
                        "steps", api._values.get("steps", 0.0) + n),
                ).pack(side="left", padx=(0, 6))
        elif name == "battery":
            from .. import ui

            def _set_level(text):
                ui._STATUS_BATTERY_LEVEL = float(text) / 100.0
                ui.refresh_status_glyphs()

            def _flag(attribute, var):
                setattr(ui, attribute, bool(var.get()))
                ui.refresh_status_glyphs()

            scale = tk.Scale(
                frame, from_=0, to=100, orient="horizontal", length=110,
                bg="#262624", fg="#F5F4EF", troughcolor="#1B1B19",
                highlightthickness=0, relief="flat", showvalue=True,
                command=_set_level,
            )
            scale.set(int(round(ui._STATUS_BATTERY_LEVEL * 100)))
            scale.pack(side="left")
            for text, attribute in (("a carregar", "_STATUS_CHARGING"),
                                    ("poupanca", "_STATUS_POWER_SAVER")):
                var = tk.IntVar(value=0)
                tk.Checkbutton(
                    frame, text=text, variable=var, bg="#262624", fg="#F5F4EF",
                    selectcolor="#1B1B19", activebackground="#262624",
                    activeforeground="#F5F4EF", font=("Segoe UI", 8),
                    command=lambda a=attribute, v=var: _flag(a, v),
                ).pack(side="left", padx=(6, 0))
        else:
            top = {"compass": 359, "light": 2000, "pressure": 1100}[name]
            scale = tk.Scale(
                frame, from_=300 if name == "pressure" else 0, to=top,
                resolution=0.1 if name == "pressure" else 1,
                orient="horizontal", length=170,
                bg="#262624", fg="#F5F4EF", troughcolor="#1B1B19",
                highlightthickness=0, relief="flat", showvalue=True,
                command=lambda text, n=name: api._feed(n, float(text)),
            )
            scale.set(_START[name])
            scale.pack(side="left")
        self.rows[name] = frame

    def remove(self, name):
        frame = self.rows.pop(name, None)
        if frame is not None:
            try:
                frame.destroy()
            except Exception:
                pass
        if not self.rows:
            self._hide()


_panel = _Panel()


class SensorsAPI:
    """Watch what the phone feels."""

    thresholds = THRESHOLDS
    shake_g = SHAKE_G
    reasons = REASONS

    def __init__(self):
        self._watches = {}
        self._values = {}
        self._last = {}

    # ── sensor streams ───────────────────────────────────────────────────────

    def shake(self, on_shake=None, on_change=None):
        """Call back when the phone is shaken. No permission, no arguments."""
        return self._watch("shake", on_shake or on_change)

    def compass(self, on_change=None):
        """Heading in degrees, 0 to 359, as text."""
        return self._watch("compass", on_change)

    def steps(self, on_change=None):
        """Steps taken since this watch started.

        On the phone this needs ``ACTIVITY_RECOGNITION`` from Android 10, and
        the counter it reads runs from the last reboot -- so the first reading
        becomes zero and the app counts its own steps, not the phone's.
        """
        return self._watch("steps", on_change)

    def light(self, on_change=None):
        """Ambient light in lux."""
        return self._watch("light", on_change)

    def proximity(self, on_change=None):
        """``True`` when something is close to the earpiece."""
        return self._watch("proximity", on_change)

    def accelerometer(self, on_change=None):
        """Acceleration including gravity, in m/s2; JSON text with x/y/z.

        Read axes with ``json_get(reading, "x")``. Axes follow the device's
        natural orientation, not the current screen rotation.
        """
        return self._watch("accelerometer", on_change)

    def gyroscope(self, on_change=None):
        """Rotation rate in rad/s; JSON text with x/y/z, not Euler angles."""
        return self._watch("gyroscope", on_change)

    def pressure(self, on_change=None):
        """Atmospheric pressure in hPa, as text. Requires a barometer."""
        return self._watch("pressure", on_change)

    def stop(self, name=None):
        """Stop one watch, or every watch."""
        for which in ([name] if name else list(self._watches)):
            self._watches.pop(which, None)
            self._values.pop(which, None)
            self._last.pop(which, None)
            _panel.remove(which)

    def available(self, name):
        """Whether this device has that sensor. Always true in the Previewer,
        for the same reason the scanner always reads: a rehearsal where half
        the branches never run is not a rehearsal."""
        return str(name) in SENSORS

    # ── the stand-in ─────────────────────────────────────────────────────────

    def _watch(self, name, callback):
        if callback is None:
            print("[ApkPy sensors] sensors.%s() sem on_change -- nada a fazer."
                  % name)
            return None
        self._watches[name] = callback
        self._values.setdefault(name, _START.get(name, 0.0))
        self._open_row(name)
        return None

    def _open_row(self, name):
        from .. import ui

        instance = ui.live_preview()
        # live_preview(), never ui._app.root: asking the proxy would BUILD a
        # Previewer, so a headless build that happens to watch a sensor would
        # open a window nobody asked for.
        if instance is None:
            return
        root = getattr(instance, "root", None)
        if root is None:
            return
        try:
            if _panel.ensure(root):
                _panel.add(name, self)
        except Exception as problem:
            print("[ApkPy sensors] painel indisponivel (%s)" % problem)

    def _feed(self, name, value):
        """A reading from the stand-in, filtered exactly as the phone filters."""
        if name in VECTOR_SENSORS:
            value = normalize_vector(value)
        self._values[name] = value
        callback = self._watches.get(name)
        if callback is None:
            return
        if not passes_threshold(name, self._last.get(name), value):
            return
        self._last[name] = value
        text = format_value(name, value)
        if name == "proximity":
            self._deliver(callback, text == "True")
        else:
            self._deliver(callback, text)

    def _fire_shake(self):
        callback = self._watches.get("shake")
        if callback is None:
            return
        self._deliver(callback, None)

    @staticmethod
    def _deliver(callback, value):
        try:
            if value is None:
                callback()
            else:
                callback(value)
        except TypeError:
            callback()


class BatteryAPI:
    """The battery, which needs no permission on either side.

    Reading it once puts a row in the sensor panel, because "what does this
    screen do at 8%%?" is a branch that otherwise only gets tested by waiting
    for a real phone to run down.
    """

    def level(self):
        """Charge as a percentage, as text -- ``"80"``."""
        from .. import ui

        sensors._open_row("battery")
        return str(int(round(ui._STATUS_BATTERY_LEVEL * 100)))

    def charging(self):
        """Whether it is plugged in."""
        from .. import ui

        sensors._open_row("battery")
        return bool(getattr(ui, "_STATUS_CHARGING", False))

    def saver(self):
        """Whether battery saver is on."""
        from .. import ui

        sensors._open_row("battery")
        return bool(getattr(ui, "_STATUS_POWER_SAVER", False))


sensors = SensorsAPI()
battery = BatteryAPI()
