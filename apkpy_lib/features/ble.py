"""Bluetooth Low Energy -- ``from apkpy_lib import ble``.

The same four verbs as classic serial, over the other radio::

    ble.scan(on_result=found, seconds=8)
    ble.connect(address, on_result=linked, on_line=incoming)
    ble.send("LED ON")
    ble.disconnect()

It defaults to the **Nordic UART Service**, which is what an ESP32, a micro:bit
or an HM-10 exposes: one characteristic the phone writes to and one it
subscribes to, carrying lines of text. So the common case needs no UUIDs. A
device with its own profile names them, in 16-bit shorthand or in full::

    ble.connect(address, service="180d", write_uuid="2a39", notify_uuid="2a37")

Unlike classic serial there is no paired list to read, so this one really does
scan -- which is why it costs a location permission below API 31. See
:mod:`apkpy_lib.core.features.ble` for how narrowly that is declared.

The desktop has no radio. The Previewer answers a scan with **one device,
openly named a simulation**, and opens the same monitor the classic module
uses: what the app sends appears in it, and what you type there arrives at
``on_line``.
"""

from __future__ import annotations

from ..core.features.ble import (
    REASONS, SUCCESS, UART, expand_uuid, normalise_terminator,
)
from . import bluetooth as _serial

__all__ = ["BleAPI", "ble", "REASONS", "UART"]

SIMULATED_NAME = "Simulated BLE device"
SIMULATED_ADDRESS = "00:00:00:00:00:02"


class BleAPI:
    """Bluetooth Low Energy, as four calls.

        def found(ok, devices):
            if ok:
                device_list.set_items(devices, title="name", subtitle="address")

        ble.scan(on_result=found, seconds=8)
        ble.connect(address, on_result=linked, on_line=incoming)
        ble.send("LED ON")

    ``on_line`` is called ``(True, text)`` for every line the device notifies,
    and once as ``(False, reason)`` when the link drops.
    """

    reasons = REASONS
    uart = UART

    def scan(self, on_result=None, seconds=8):
        """Look for advertising devices, and report them as JSON."""
        _serial._report(
            on_result, True,
            '[{"name": "%s", "address": "%s"}]'
            % (SIMULATED_NAME, SIMULATED_ADDRESS))

    def connect(self, address=None, on_result=None, on_line=None,
                service=None, write_uuid=None, notify_uuid=None):
        """Open the GATT link and subscribe to the notify characteristic.

        The UUIDs default to the Nordic UART Service. They are expanded from
        16-bit shorthand here exactly as they are on the phone, so a wrong one
        is wrong in the same way on both.
        """
        expand_uuid(service, UART["service"])
        expand_uuid(write_uuid, UART["write"])
        expand_uuid(notify_uuid, UART["notify"])
        _connect(str(address or ""), on_result, on_line)

    def send(self, text="", on_result=None, terminator=None):
        """Write one line to the device.

        ``terminator`` works exactly as it does on the classic radio.
        """
        normalise_terminator(terminator)
        _serial._send(str(text), on_result)

    def disconnect(self):
        """Close the link. ``on_line`` gets one final ``(False, "lost")``."""
        _serial._disconnect()


ble = BleAPI()


def _connect(address, on_result, on_line):
    ui, app = _serial._window()
    if ui is None:
        _serial._report(on_result, False, "unsupported")
        return
    if address and address != SIMULATED_ADDRESS:
        # The phone fails on an address that never answered the scan, and a
        # Previewer that connects to anything would hide that.
        _serial._report(on_result, False, "not_found")
        return

    # One monitor, shared with the classic module: a phone has two radios but
    # you only ever watch one conversation. The label is passed, not stored.
    _serial._state["connected"] = True
    _serial._state["on_line"] = on_line
    _serial._open_panel(ui, app, "BLE")
    _serial._write("connected to %s" % SIMULATED_NAME, kind="meta")
    _serial._report(on_result, True, SUCCESS)
