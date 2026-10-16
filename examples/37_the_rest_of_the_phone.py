"""Reach - the calls that go past the app, to the rest of the phone.

A touch you can feel, a voice, a page, a file handed to the person, a
download, the calendar, the dialler, the microphone, the printer -- and what
arrives from outside: a link somebody tapped, text another app shared.

Each row is one call. The ones that hand over to another app answer at once
with a word ("ok", or why not); the ones that need the person or take time
answer later, in on_result(ok, value).

Needs ApkPy 1.13.0.
"""

from apkpy_lib import *

home = Screen(id="home", scroll=True)

# What may come in from outside. These two lines change what is built -- the
# app's manifest -- and preview= is what the Previewer pretends arrived.
incoming.links("reach", preview="reach://open/42")
incoming.shares("text", preview="Shared from another app")

TERMS = "<h1>Terms</h1><p>This page is HTML the app wrote, shown inside the app.</p><p><a href='https://repo-apkpy.pages.dev/'>The ApkPy site</a></p>"
INVOICE = "<h1>Invoice 42</h1><p>Two tickets to Lisbon</p><table border='1' cellpadding='6'><tr><td>Ticket</td><td>2</td><td>34.00</td></tr><tr><td><b>Total</b></td><td></td><td><b>68.00</b></td></tr></table>"

label("Reach", id="title", screen=home)
label("One call each, past the app, to the rest of the phone.", id="lead", screen=home)

answer = container(id="answer", screen=home)
label("LAST ANSWER", id="answer_kicker", parent=answer)
status = label("Nothing yet", id="status", parent=answer)
detail = label("Tap a row to make a call.", id="detail", parent=answer)


def show(call, word):
    status.set_value(word)
    detail.set_value(call)


def arrived():
    link = incoming.link()
    words = incoming.text()
    if link != "":
        show("incoming.link()", link)
        incoming.clear()
    elif words != "":
        show("incoming.text()", words)
        incoming.clear()


lifecycle(home, on_mount=arrived)


def feel():
    show("haptics.success()", haptics.success())


def buzz():
    show("haptics.vibrate(300)", haptics.vibrate(300))


def said(ok, reason):
    show("speech.say() finished", reason)


def say():
    speech.say("Hello from an app written in Python.", on_result=said)
    show("speech.is_speaking()", str(speech.is_speaking()))


def heard(ok, words):
    if ok:
        show("speech.listen() heard this", words)
    else:
        show("speech.listen()", words)


def listen():
    speech.listen(prompt="Say the name of a city", on_result=heard)


def open_site():
    show("browser.open()", browser.open("https://repo-apkpy.pages.dev/"))


def closed(ok, address):
    show("browser.show() was closed", "closed")


def show_terms():
    browser.show(html=TERMS, title="Terms", on_result=closed)


def show_docs():
    browser.show("https://repo-apkpy.pages.dev/getting-started/", on_result=closed)


def add_event():
    show("calendar.add_event()", calendar.add_event("Dentist", "2026-11-03 15:30", location="Rua Augusta 12", notes="Bring the X-ray"))


def dial():
    show("phone.dial()", phone.dial("+351 912 345 678"))


def message():
    show("phone.sms()", phone.sms("912 345 678", "On my way"))


def saved(ok, name):
    if ok:
        show("files.save_as() wrote " + name, "saved")
    else:
        show("files.save_as()", name)


def save_notes():
    files.save_as("apkpy-notes.txt", "Milk\nBread\nA note from ApkPy", on_result=saved)


def landed(ok, name):
    if ok:
        show("downloads.start() left " + name + " in Downloads", "downloaded")
    else:
        show("downloads.start()", name)


def download():
    downloads.start("https://repo-apkpy.pages.dev/llms.txt", name="apkpy-llms.txt", title="ApkPy for assistants", on_result=landed)
    show("downloads.start()", "downloading")


def printed(ok, reason):
    show("printing.html()", reason)


def print_it():
    printing.html(INVOICE, name="Invoice 42", on_result=printed)


def started(ok, reason):
    show("recorder.start()", reason)


def record():
    if recorder.is_recording():
        length = recorder.seconds()
        storage.set("recording", recorder.stop())
        show("recorder.stop()", length + " s recorded")
    else:
        recorder.start(on_result=started)


def play_it():
    audio.play(storage.get("recording", ""))
    show("audio.play()", "playing")


def copied(ok, name):
    if ok:
        show("files.save_copy() wrote " + name, "saved")
    else:
        show("files.save_copy()", name)


def keep_it():
    files.save_copy(storage.get("recording", ""), on_result=copied)


label("FEEL AND HEAR", id="k_feel", screen=home)
g_feel = container(id="g_feel", screen=home)
list_row("A touch you can feel", subtitle="The phone's own success effect", icon="touch_app", id="r_feel", parent=g_feel, command=feel)
list_row("Vibrate", subtitle="The motor, for 300 ms", icon="vibration", id="r_buzz", parent=g_feel, command=buzz)
list_row("Read aloud", subtitle="Text to speech", icon="volume_up", id="r_say", parent=g_feel, command=say)
list_row("Dictate", subtitle="Speech to text", icon="mic", id="r_listen", parent=g_feel, command=listen)

label("PAGES", id="k_pages", screen=home)
g_pages = container(id="g_pages", screen=home)
list_row("Open a site", subtitle="A browser tab over the app", icon="public", trailing_icon="chevron_right", id="r_site", parent=g_pages, command=open_site)
list_row("Terms", subtitle="Your own HTML, inside the app", icon="article", trailing_icon="chevron_right", id="r_terms", parent=g_pages, command=show_terms)
list_row("Documentation", subtitle="A site, inside the app", icon="menu_book", trailing_icon="chevron_right", id="r_docs", parent=g_pages, command=show_docs)

label("HAND OVER", id="k_hand", screen=home)
g_hand = container(id="g_hand", screen=home)
list_row("Add to calendar", subtitle="Opens a new event, filled in", icon="event", trailing_icon="chevron_right", id="r_event", parent=g_hand, command=add_event)
list_row("Dial", subtitle="Opens the dialler on a number", icon="call", trailing_icon="chevron_right", id="r_dial", parent=g_hand, command=dial)
list_row("Message", subtitle="Opens a message, already written", icon="sms", trailing_icon="chevron_right", id="r_sms", parent=g_hand, command=message)

label("FILES", id="k_files", screen=home)
g_files = container(id="g_files", screen=home)
list_row("Save notes", subtitle="Where the person chooses", icon="save", id="r_save", parent=g_files, command=save_notes)
list_row("Download", subtitle="Into Downloads, by the system", icon="download", id="r_download", parent=g_files, command=download)
list_row("Print", subtitle="Any printer, or a PDF", icon="print", id="r_print", parent=g_files, command=print_it)

label("RECORDER", id="k_rec", screen=home)
g_rec = container(id="g_rec", screen=home)
list_row("Record", subtitle="Tap to start, tap again to stop", icon="fiber_manual_record", id="r_record", parent=g_rec, command=record)
list_row("Play it back", subtitle="With audio.play()", icon="play_arrow", id="r_play", parent=g_rec, command=play_it)
list_row("Keep a copy", subtitle="Out of the app, where the person chooses", icon="folder", id="r_keep", parent=g_rec, command=keep_it)

theme = Theme(
    primary="#3B5BDB",
    background="#F3F4F8",
    surface="#FFFFFF",
    text="#1A1C23",
    text_secondary="#666B7A",
    border="#E4E6EE",
    radius=18,
)

style = """
home {
    background-color: var(--background);
    padding: 24px 16px 32px 16px;
}
title {
    color: var(--text);
    font-size: 32px;
    font-weight: bold;
    letter-spacing: -0.6px;
}
lead {
    color: var(--text-secondary);
    font-size: 15px;
    line-height: 1.5;
    margin-bottom: 18px;
}
answer {
    background-color: var(--primary);
    border-radius: 22px;
    padding: 18px 20px 20px 20px;
    gap: 4px;
}
answer_kicker {
    color: #E6EBFF;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.2px;
}
status {
    color: #FFFFFF;
    font-size: 22px;
    font-weight: bold;
    letter-spacing: -0.2px;
}
detail {
    color: #ECEFFF;
    font-size: 13px;
}
k_feel, k_pages, k_hand, k_files, k_rec {
    color: var(--text-secondary);
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.2px;
    margin-top: 22px;
    margin-bottom: 8px;
    margin-left: 6px;
}
g_feel, g_pages, g_hand, g_files, g_rec {
    background-color: var(--surface);
    border-radius: 18px;
    padding: 0px;
    divider-color: var(--border);
    divider-inset: 58px;
}
list_row {
    background-color: #00000000;
    border-radius: 0px;
    padding: 0px 18px;
    min-height: 64px;
    color: var(--text);
    subtitle-color: var(--text-secondary);
    trailing-color: var(--text-secondary);
    icon-color: var(--primary);
}
r_record {
    icon-color: #D93446;
}
"""

run(start_screen=home, theme=theme)
