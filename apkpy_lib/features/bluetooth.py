"""Classic Bluetooth serial -- ``from apkpy_lib import bluetooth``.

Talking to hardware: an Arduino, an ESP32, a thermal printer, a scale. Lines of
text out, lines of text back.

    bluetooth.devices(on_result=found)                  # (ok, json | reason)
    bluetooth.connect(address, on_result=..., on_line=...)
    bluetooth.send("LED ON")
    bluetooth.disconnect()

The desktop has no paired serial hardware, so the Previewer offers **one
device, openly named a simulation**, and a serial monitor you drive by hand:
what the app sends appears in it, and what you type there arrives at
``on_line``. That is the same bargain the biometric prompt makes -- the
Previewer cannot have the radio, so it gives you the loop instead of pretending.

The vocabulary of reasons lives in
:mod:`apkpy_lib.core.features.bluetooth` and is imported by both runtimes.
"""

from __future__ import annotations

from ..core.features.bluetooth import REASONS, SUCCESS, normalise_terminator

__all__ = ["BluetoothAPI", "bluetooth", "REASONS"]

# Named so nobody mistakes it for their own hardware.
SIMULATED_NAME = "Simulated serial device"
SIMULATED_ADDRESS = "00:00:00:00:00:01"

_PANEL_HEIGHT = 190
_MAX_LINES = 200


class BluetoothAPI:
    """Classic Bluetooth serial (SPP), as four calls.

        def found(ok, devices):
            if ok:
                device_list.set_items(devices, title="name", subtitle="address")

        bluetooth.devices(on_result=found)
        bluetooth.connect(address, on_result=linked, on_line=incoming)
        bluetooth.send("LED ON")

    ``devices()`` lists **paired** devices and does not scan: an RFCOMM socket
    needs a bonded device, pairing asks for a PIN and belongs to system
    Settings, and skipping the scan keeps ``ACCESS_FINE_LOCATION`` out of the
    manifest.

    ``on_line`` is called ``(True, text)`` for every line the device sends, and
    once as ``(False, reason)`` when the link drops -- so an app cannot forget
    to handle the disconnect.
    """

    reasons = REASONS

    def devices(self, on_result=None):
        """Report the paired devices as JSON, ready for ``set_items``."""
        _report(on_result, True,
                '[{"name": "%s", "address": "%s"}]'
                % (SIMULATED_NAME, SIMULATED_ADDRESS))

    def connect(self, address=None, on_result=None, on_line=None):
        """Open the serial link, and start reporting lines to ``on_line``."""
        _connect(str(address or ""), on_result, on_line)

    def send(self, text="", on_result=None, terminator=None):
        """Send one line.

        ``terminator`` is what goes on the end: ``"newline"`` (the default),
        ``"return"`` for hardware that wants a carriage return -- a car
        diagnostics adapter answers nothing without one -- ``"crlf"``,
        ``"none"``, or the characters themselves.
        """
        normalise_terminator(terminator)
        _send(str(text), on_result)

    def disconnect(self):
        """Close the link. ``on_line`` gets one final ``(False, "lost")``."""
        _disconnect()


bluetooth = BluetoothAPI()


# --- The simulator ---------------------------------------------------------

# One simulated link at a time, shared with the BLE module: a phone with two
# radios still has one monitor to look at. Each module passes its own label
# to _open_panel rather than storing it here -- shared state that only one
# side wrote is how the panel ended up saying "BLE" for a serial link.
_state = {"connected": False, "on_line": None, "panel": None, "log": None}


def _report(callback, success, value):
    if not callback:
        return
    from ..ui import report_exception
    try:
        callback(success, value)
    except Exception as exc:                       # pragma: no cover - user code
        report_exception(exc, context="bluetooth callback")


def _window():
    """The running Previewer, or ``None`` -- without constructing one.

    ``ui._app`` is a lazy proxy: reading ``.root`` builds the window. During
    ``apkpy build`` there is none and there must not become one.
    """
    from .. import ui

    app = getattr(ui, "_app", None)
    if app is None or getattr(app, "_instance", None) is None:
        return None, None
    return ui, app


def _connect(address, on_result, on_line):
    ui, app = _window()
    if ui is None:
        _report(on_result, False, "unsupported")
        return
    if address and address != SIMULATED_ADDRESS:
        # Be strict rather than agreeable: on the phone an address that is not
        # paired fails, and a Previewer that connects to anything would hide
        # exactly that mistake.
        _report(on_result, False, "not_paired")
        return

    _state["connected"] = True
    _state["on_line"] = on_line
    _open_panel(ui, app, "SERIAL")
    _write("connected to %s" % SIMULATED_NAME, kind="meta")
    _report(on_result, True, SUCCESS)


def _send(text, on_result):
    if not _state["connected"]:
        _report(on_result, False, "not_connected")
        return
    _write(text, kind="out")
    _report(on_result, True, SUCCESS)


def _disconnect():
    if not _state["connected"]:
        return
    _state["connected"] = False
    _write("disconnected", kind="meta")
    on_line = _state.get("on_line")
    _state["on_line"] = None
    _close_panel()
    _report(on_line, False, "lost")


# --- The serial monitor ----------------------------------------------------

def _open_panel(ui, app, transport="SERIAL"):
    import tkinter as tk

    if _state.get("panel") is not None:
        return
    body = getattr(app, "body", None)
    if body is None:
        return

    tokens = ui.global_styles.get("__theme__", {})
    surface = tokens.get("surface_high") or tokens.get("surface", "#1C1B1F")
    text_colour = tokens.get("text", "#E6E1E5")
    muted = tokens.get("text_secondary", "#CAC4D0")
    primary = tokens.get("primary", "#D0BCFF")
    border = tokens.get("border_subtle") or tokens.get("border", "#49454F")
    mono = "Consolas" if ui.os.name == "nt" else "Courier"

    panel = tk.Frame(body, bg=surface, highlightthickness=1,
                     highlightbackground=border)
    panel.place(relx=0, rely=1.0, anchor="sw", relwidth=1, height=_PANEL_HEIGHT)

    header = tk.Frame(panel, bg=surface)
    header.pack(fill="x", padx=10, pady=(8, 4))
    tk.Label(header, text="%s MONITOR  ·  Previewer only" % transport, bg=surface,
             fg=muted, font=(ui.get_native_font(""), -11, "bold")).pack(side="left")
    tk.Button(header, text="✕", command=_disconnect, bg=surface, fg=muted,
              relief="flat", bd=0, activebackground=surface,
              font=(ui.get_native_font(""), -12), cursor="hand2").pack(side="right")

    log = tk.Text(panel, bg=surface, fg=text_colour, relief="flat", bd=0,
                  font=(mono, -11), height=6, wrap="word",
                  highlightthickness=0, padx=10)
    log.pack(fill="both", expand=True)
    log.tag_configure("out", foreground=primary)
    log.tag_configure("in", foreground=text_colour)
    log.tag_configure("meta", foreground=muted)
    log.configure(state="disabled")

    entry_row = tk.Frame(panel, bg=surface)
    entry_row.pack(fill="x", padx=10, pady=(4, 8))
    tk.Label(entry_row, text="←", bg=surface, fg=muted,
             font=(mono, -12)).pack(side="left", padx=(0, 6))
    entry = tk.Entry(entry_row, bg=ui._mix_hex(surface, text_colour, 0.08),
                     fg=text_colour, relief="flat", bd=0,
                     insertbackground=text_colour, font=(mono, -11))
    entry.pack(side="left", fill="x", expand=True, ipady=5)

    def _reply(_event=None):
        line = entry.get().strip()
        if not line:
            return
        entry.delete(0, "end")
        _write(line, kind="in")
        _report(_state.get("on_line"), True, line)

    entry.bind("<Return>", _reply)
    entry.after_idle(entry.focus_set)

    _state["panel"] = panel
    _state["log"] = log


def _close_panel():
    panel = _state.get("panel")
    _state["panel"] = None
    _state["log"] = None
    try:
        if panel is not None:
            panel.destroy()
    except Exception:
        pass


def _write(text, kind="meta"):
    """Append one line to the monitor, if it is open."""
    log = _state.get("log")
    if log is None:
        return
    marker = {"out": "→ ", "in": "← ", "meta": "· "}.get(kind, "  ")
    try:
        log.configure(state="normal")
        log.insert("end", marker + text + "\n", kind)
        if int(log.index("end-1c").split(".")[0]) > _MAX_LINES:
            log.delete("1.0", "2.0")
        log.see("end")
        log.configure(state="disabled")
    except Exception:
        pass
