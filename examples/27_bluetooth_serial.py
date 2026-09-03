"""Talking to a board over Bluetooth: pick a radio, connect, send lines.

The list and the conversation are two screens, and the link crosses between
them: the second screen calls ``connect()`` again, which finds the link
already open and hands it the lines. See "The link outlives the screen".
"""

from apkpy_lib import (
    Screen, Theme, app_bar, ble, bluetooth, button, container, label,
    lifecycle, list_view, on_click_navigate, run, storage,
)

home = Screen(id="home")
talk = Screen(id="talk")

app_bar("Devices", screen=home)
label("Pick a radio", id="title", screen=home)
label("Classic is what an HC-05 module and most receipt printers use, and it "
      "has to be paired in Settings first. Low Energy is what an ESP32 or a "
      "micro:bit speaks, and it advertises instead.", id="blurb", screen=home)

radios = container(id="radios", screen=home)
button("PAIRED (CLASSIC)", id="b_classic", icon="bluetooth", parent=radios,
       command=lambda: list_paired())
button("SCAN (LOW ENERGY)", id="b_ble", icon="search", parent=radios,
       command=lambda: scan_ble())

status = label("", id="status", screen=home)

devices = list_view([], id="devices", screen=home,
                    on_click=lambda item: connect(item["subtitle"]))

app_bar("Serial", screen=talk)
label("Last line received", id="heading", screen=talk)
last = label("nothing yet", id="last", screen=talk)
talk_status = label("", id="talk_status", screen=talk)

sending = container(id="sending", screen=talk)
button("LED ON", id="b_on", parent=sending, command=lambda: shout("LED ON"))
button("LED OFF", id="b_off", parent=sending, command=lambda: shout("LED OFF"))
button("DISCONNECT", id="b_close", icon="close", parent=sending,
       command=lambda: close())

# Which radio the person chose, and what they picked. Both live in storage
# rather than in module variables: the two screens are separate Activities,
# and storage is what crosses between them.


def listed(ok, found):
    if ok:
        devices.set_items(found, title="name", subtitle="address")
        status.set_value("")
    else:
        status.set_value(explain(found))


def incoming(ok, line):
    if ok:
        last.set_value(line)
    else:
        # The link dropped. One callback carries the data and its loss, so
        # there is nowhere to forget this.
        talk_status.set_value("The link dropped.")
        last.set_value("nothing yet")


def linked(ok, reason):
    if ok:
        on_click_navigate(talk)
    else:
        status.set_value(explain(reason))


def adopted(ok, reason):
    # The conversation screen asking for the lines. The link is already open,
    # so this costs nothing and just re-points the callback at this screen.
    if not ok:
        talk_status.set_value(explain(reason))


def sent(ok, reason):
    if not ok:
        talk_status.set_value(explain(reason))


def listen_here():
    if storage.get("radio") == "ble":
        ble.connect(storage.get("address"), on_result=adopted, on_line=incoming)
    else:
        bluetooth.connect(storage.get("address"), on_result=adopted,
                          on_line=incoming)


def explain(reason):
    """Turn a reason into something worth reading on screen."""
    if reason == "off":
        return "Bluetooth is off. Say yes when the phone asks."
    if reason == "denied":
        return "Without the Bluetooth permission there is nothing to show."
    if reason == "unsupported":
        return "This phone has no Bluetooth radio."
    if reason == "not_paired":
        return "Pair it in Settings first, then come back."
    if reason == "not_found":
        return "Nothing answered. Is the board powered on and near?"
    if reason == "unreachable":
        return "It did not answer. Out of range, or busy with something else."
    if reason == "no_service":
        return "Connected, but it does not speak the service we asked for."
    if reason == "not_connected":
        return "Connect to something first."
    return "That did not work: " + reason


def list_paired():
    status.set_value("")
    storage.set("radio", "classic")
    bluetooth.devices(on_result=listed)


def scan_ble():
    status.set_value("Looking for six seconds...")
    storage.set("radio", "ble")
    ble.scan(on_result=listed, seconds=6)


def connect(address):
    storage.set("address", address)
    if storage.get("radio") == "ble":
        # No UUIDs: the default is the Nordic UART service, which is what an
        # ESP32 or a micro:bit exposes.
        ble.connect(address, on_result=linked, on_line=incoming)
    else:
        bluetooth.connect(address, on_result=linked, on_line=incoming)


def shout(text):
    # A board that wants a carriage return instead would say
    # terminator="return" here.
    if storage.get("radio") == "ble":
        ble.send(text, on_result=sent)
    else:
        bluetooth.send(text, on_result=sent)


def close():
    bluetooth.disconnect()
    ble.disconnect()
    on_click_navigate(home)


# Asking again on arrival is how this screen starts receiving: the link is
# already open, so it is free.
lifecycle(talk, on_resume=listen_here)


run(start_screen=home, theme=Theme(mode="dark"))

style = """
home, talk { background-color: var(--background); padding: 20px; }

title {
    color: var(--text); font-size: var(--text-2xl); font-weight: bold;
    margin-bottom: 6px;
}
blurb {
    color: var(--text-secondary); font-size: var(--text-base);
    line-height: var(--leading-normal); margin-bottom: 16px;
}
status, talk_status {
    color: var(--error); font-size: var(--text-base);
    line-height: var(--leading-normal); margin-bottom: 12px;
}
heading {
    color: var(--text-secondary); font-size: var(--text-xs);
    font-weight: bold; letter-spacing: 1.1px; margin-bottom: 4px;
}
last {
    color: var(--primary); font-size: var(--text-xl); font-weight: bold;
    margin-bottom: 18px;
}

radios, sending { background-color: #00000000; }
b_classic, b_ble, b_on, b_off, b_close {
    width: 100%; min-height: 46px; border-radius: 14px;
    font-weight: bold; margin-bottom: 10px;
}

devices {
    background-color: var(--surface-high); border-radius: 16px;
    divider-color: var(--border); divider-width: 1px;
    margin-bottom: 16px;
}
"""
