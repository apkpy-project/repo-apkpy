"""NFC Tags — read NDEF text/URLs and write a spare, rewritable test tag.

Unreleased: intended for ApkPy 1.9.0. The Previewer uses simulated tags.
Never use a payment, travel or access card as a write test.
"""
from apkpy_lib import (
    Screen, Theme, app_bar, button, inputs, json_get, label, lifecycle, nfc, run,
)

home = Screen(id="home")
app_bar("NFC Tags", screen=home)
label("Small tag. Useful shortcut.", id="title", screen=home)
label("Read a label, inspect a link, or write a spare test tag. "
      "Keep the tag against your phone until the result arrives.", id="intro", screen=home)
status = label("Checking NFC…", id="status", screen=home)
tag_id = label("No tag read yet", id="tag_id", screen=home)
content = label("Text and links will appear here.", id="content", screen=home)


def failed(ok, reason):
    if reason == "off":
        status.set_value("NFC is off. Open NFC settings to enable it.")
    elif reason == "unsupported":
        status.set_value("This device has no NFC radio.")
    elif reason == "not_started":
        status.set_value("Start reading before arming a write.")
    elif reason == "read_only":
        status.set_value("Read-only tag. Choose a rewritable test tag.")
    elif reason == "too_small":
        status.set_value("This message is too large for the tag.")
    elif reason == "no_ndef":
        status.set_value("This tag cannot store an NDEF message.")
    elif reason == "tag_lost":
        status.set_value("Tag moved away. Keep it still and try again.")
    else:
        status.set_value("NFC failed. See the technical log: " + reason)


def tagged(ok, tag):
    tag_id.set_value("ID: " + json_get(tag, "id") + " · " + json_get(tag, "type"))
    content.set_value("Text: " + json_get(tag, "text") + "\nURL: " + json_get(tag, "url")
                      + "\nWritable: " + json_get(tag, "writable") + " · Capacity: " + json_get(tag, "size"))
    status.set_value("Tag received. Links are displayed, never opened automatically.")


def checked(ok, reason):
    if ok:
        status.set_value("Ready. Hold a tag near the back of the phone.")
        nfc.start(on_tag=tagged, on_error=failed)
    else:
        failed(ok, reason)


def start_reading():
    nfc.status(on_result=checked)


def written(ok, reason):
    if ok:
        status.set_value("Write acknowledged. Updated content follows.")
    else:
        failed(ok, reason)


def write_text():
    status.set_value("Write armed. Touch a spare tag now; existing content will be replaced.")
    nfc.write(text=text_input.get_value(), on_result=written)


def write_url():
    status.set_value("URL write armed. Touch a spare tag now; existing content will be replaced.")
    nfc.write(url="https://example.com/nfc", on_result=written)


def cancel():
    nfc.cancel_write()
    status.set_value("Write cancelled. Reading is still available.")


def stop():
    nfc.stop()
    status.set_value("Reader stopped.")


button("Start reading", id="start", screen=home, command=start_reading)
button("NFC settings", id="settings", variant="outlined", screen=home, command=lambda: nfc.settings())
text_input = inputs("Message for a spare test tag", id="message", screen=home)
button("Write text to next tag", id="write_text", screen=home, command=write_text)
button("Write example URL", id="write_url", variant="outlined", screen=home, command=write_url)
button("Cancel pending write", id="cancel", variant="outlined", screen=home, command=cancel)
button("Stop reader", id="stop", variant="text", screen=home, command=stop)
label("Desktop: use the NFC SIMULATOR panel. Android: a physical tag is needed. "
      "Tags are not secure identity credentials.", id="tip", screen=home)

lifecycle(home, on_resume=start_reading)

style = """
home { background-color: var(--background); padding: 18px; }
title { color: var(--text); font-size: 24px; font-weight: bold; margin-bottom: 8px; }
intro, tip { color: var(--text-secondary); font-size: 13px; margin-bottom: 18px; }
status { color: var(--primary); font-size: 14px; margin-bottom: 14px; }
tag_id { color: var(--text); font-size: 14px; font-weight: bold; margin-bottom: 6px; }
content { color: var(--text-secondary); font-size: 13px; margin-bottom: 16px; }
start, settings, write_text, write_url, cancel, stop, message {
    width: 100%; min-height: 46px; border-radius: 14px; margin-bottom: 10px;
}
tip { margin-top: 10px; margin-bottom: 210px; }
"""

run(start_screen=home, theme=Theme(mode="dark"))
