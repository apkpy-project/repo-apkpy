"""Network - online or not, over what, and being told when that changes.

A banner that comes when the connection goes, messages that wait for it to
come back, and a big download that waits for Wi-Fi. network.online() says
whether the phone reaches the internet, network.kind() what the connection
is, network.metered() whether it is paid for, and network.on_change() calls
a function when any of the three changes.

In the Previewer, click the connection in the status bar to take it away.

Needs ApkPy 1.13.0.
"""

from apkpy_lib import *

home = Screen(id="home", scroll=True)
online = state(True)

label("Network", id="title", screen=home)
label("Online or not, over what, and when that changes.", id="lead", screen=home)

banner = container(id="banner", screen=home)
label("No connection", id="banner_title", parent=banner)
label("What you send waits here until it is back.", id="banner_text", parent=banner)
online.bind_visibility(banner, when=False)

now_card = container(id="now_card", screen=home)
label("CONNECTION", id="now_kicker", parent=now_card)
kind = label("", id="kind", parent=now_card)
cost = label("", id="cost", parent=now_card)

outbox_card = container(id="outbox_card", screen=home)
label("OUTBOX", id="outbox_kicker", parent=outbox_card)
waiting = label("0", id="waiting", parent=outbox_card)
outbox_note = label("Nothing waiting", id="outbox_note", parent=outbox_card)
outbox_actions = container(id="outbox_actions", parent=outbox_card)

map_card = container(id="map_card", screen=home)
label("OFFLINE MAP", id="map_kicker", parent=map_card)
label("Lisbon, 48 MB", id="map_name", parent=map_card)
map_note = label("Not downloaded", id="map_note", parent=map_card)
map_actions = container(id="map_actions", parent=map_card)


def show():
    if network.kind() == "wifi":
        kind.set_value("Wi-Fi")
    elif network.kind() == "mobile":
        kind.set_value("Mobile data")
    elif network.kind() == "none":
        kind.set_value("None")
    else:
        kind.set_value("Connected")

    if not network.online():
        cost.set_value("Nothing leaves the phone")
    elif network.metered():
        cost.set_value("You pay for what goes over it")
    else:
        cost.set_value("Free to use")
    online.set(network.online())


def changed():
    show()
    if network.online() and int(waiting.get_value()) > 0:
        outbox_note.set_value("Sent the " + waiting.get_value() + " that waited")
        waiting.set_value("0")
    if network.online() and not network.metered() and map_note.get_value() == "Waiting for Wi-Fi":
        map_note.set_value("Downloaded over Wi-Fi")


def opened():
    show()
    network.on_change(changed)


def send():
    if network.online():
        outbox_note.set_value("Sent")
    else:
        waiting.set_value(str(int(waiting.get_value()) + 1))
        outbox_note.set_value("Waiting for a connection")


def download():
    if network.online() and not network.metered():
        map_note.set_value("Downloaded over Wi-Fi")
    else:
        map_note.set_value("Waiting for Wi-Fi")


lifecycle(home, on_mount=opened)

button("Send a message", id="send", icon="send", command=send, parent=outbox_actions)
button("Download", id="download", variant="outlined", command=download, parent=map_actions)

theme = Theme(primary="#3B5BDB")

style = """
home {
    background-color: var(--background);
    padding: 24px;
    gap: 14px;
}
title {
    color: var(--text);
    font-size: 28px;
    font-weight: bold;
}
lead {
    color: var(--text-secondary);
    font-size: 15px;
    line-height: 1.5;
}
banner {
    background-color: var(--error);
    border-radius: 18px;
    padding: 14px 4px;
    gap: 2px;
}
banner_title {
    color: #FFFFFF;
    font-size: 15px;
    font-weight: bold;
}
banner_text {
    color: #FFFFFF;
    font-size: 13px;
}
now_card, outbox_card, map_card {
    background-color: var(--surface);
    border-radius: 18px;
    padding: 18px 4px;
    gap: 4px;
}
now_kicker, outbox_kicker, map_kicker {
    color: var(--text-secondary);
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.2px;
}
kind {
    color: var(--text);
    font-size: 34px;
    font-weight: bold;
}
cost, outbox_note, map_note {
    color: var(--text-secondary);
    font-size: 14px;
}
waiting {
    color: var(--primary);
    font-size: 56px;
    font-weight: bold;
}
map_name {
    color: var(--text);
    font-size: 20px;
    font-weight: bold;
}
outbox_actions, map_actions {
    display: flex;
    flex-direction: row;
    align-items: center;
    padding: 0px 0px 0px 16px;
    margin-top: 12px;
}
send, download {
    border-radius: 24px;
    min-height: 48px;
    padding: 0px 24px;
}
"""

run(start_screen=home, theme=theme)
