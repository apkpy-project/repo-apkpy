"""Phone extras - the gallery, the clock, calls, the calendar, the clipboard, reminders.

gallery.save() puts a picture of the app in the phone's gallery.
clock.alarm() and clock.timer() set them in the clock app, where they ring
with this app closed. phone.call() rings a number at once (phone.dial() only
opens the dialler). calendar.events() reads what is in the calendar.
clipboard.paste() reads what the person copied. display.on_screenshot() is
told when the person takes a screenshot. notify(at=) posts a notification
later, even with the app closed; exact=True asks the person, once, to let it
come to the minute (Android may otherwise post it up to an hour late).

Android asks the person before the first call and the first read of the
calendar, and the first reminder to the minute opens "Alarms & reminders" in
Settings. Nothing else here needs a permission the person sees.

In the Previewer, Ctrl+Shift+S takes a screenshot.

Needs ApkPy 1.15.0.
"""

import json

from apkpy_lib import *

home = Screen(id="home", scroll=True)

label("Phone extras", id="title", screen=home)
said = label("Tap something below", id="said", screen=home)

photo_card = container(id="photo_card", screen=home)
label("GALLERY", id="photo_kicker", parent=photo_card)
photo_note = label("A photo from the web, saved to the gallery", id="photo_note", parent=photo_card)

clock_card = container(id="clock_card", screen=home)
label("CLOCK", id="clock_kicker", parent=clock_card)
clock_actions = container(id="clock_actions", parent=clock_card)

call_card = container(id="call_card", screen=home)
label("CALL", id="call_kicker", parent=call_card)
number = inputs("Phone number", id="number", type="text", parent=call_card)

week_card = container(id="week_card", screen=home)
label("THIS WEEK", id="week_kicker", parent=week_card)
week = label("Nothing read yet", id="week", parent=week_card)

paste_card = container(id="paste_card", screen=home)
label("CLIPBOARD", id="paste_kicker", parent=paste_card)
pasted = label("Copy some text somewhere, then paste", id="pasted", parent=paste_card)

remind_card = container(id="remind_card", screen=home)
label("REMINDER", id="remind_kicker", parent=remind_card)
remind_note = label("At a time you type, or every morning at nine", id="remind_note", parent=remind_card)
when = inputs("A time, like 18:45", id="when", parent=remind_card)
remind_actions = container(id="remind_actions", parent=remind_card)


def saved(ok, name):
    if ok:
        photo_note.set_value("In the gallery as " + name)
    else:
        photo_note.set_value("Not saved: " + name)


def downloaded(ok, path):
    if ok:
        gallery.save(path, album="Phone extras", on_result=saved)
    else:
        photo_note.set_value("The photo did not download")


def save_photo():
    photo_note.set_value("Downloading...")
    files.download("https://picsum.photos/id/1015/800/600.jpg", "lake.jpg", on_result=downloaded)


def wake_up():
    said.set_value("Alarm: " + clock.alarm(7, 30, "Wake up"))


def pasta():
    said.set_value("Timer: " + clock.timer(480, "Pasta"))


def called(ok, why):
    if ok:
        said.set_value("Calling...")
    else:
        said.set_value("No call: " + why)


def ring():
    phone.call(number.get_value(), on_result=called)


def read_week(ok, value):
    if not ok:
        week.set_value("Could not read: " + value)
        return
    events = json.loads(value)
    if len(events) == 0:
        week.set_value("Nothing this week")
        return
    lines = ""
    for event in events:
        lines = lines + event["start"] + "  " + event["title"] + "\n"
    week.set_value(lines)


def look():
    calendar.events(on_result=read_week)


def paste():
    if clipboard.has_text():
        pasted.set_value(clipboard.paste())
    else:
        pasted.set_value("The clipboard has no text")


def at_that_time():
    notify("Stretch", "Time to stand up", id="stretch", at=when.get_value())
    remind_note.set_value("Set for " + when.get_value())


def mornings():
    notify("Good morning", "Water, then the plan for the day", id="morning", at="09:00", repeat="daily", exact=True)
    remind_note.set_value("Every day at 09:00")


def screenshot():
    said.set_value("You took a screenshot")


def opened():
    display.on_screenshot(screenshot)


button("Save a photo", id="save_photo", icon="photo_library", command=save_photo, parent=photo_card)
button("Alarm 07:30", id="alarm", icon="alarm", command=wake_up, parent=clock_actions)
button("Timer 8 min", id="timer", icon="timer", variant="outlined", command=pasta, parent=clock_actions)
button("Call", id="call", icon="call", command=ring, parent=call_card)
button("Read the calendar", id="look", icon="event", command=look, parent=week_card)
button("Paste", id="paste", icon="content_paste", command=paste, parent=paste_card)
button("Remind me", id="remind", icon="notifications", command=at_that_time, parent=remind_actions)
button("Every morning", id="mornings", icon="wb_sunny", variant="outlined", command=mornings, parent=remind_actions)

lifecycle(home, on_mount=opened)

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
said {
    color: var(--text-secondary);
    font-size: 15px;
}
photo_card, clock_card, call_card, week_card, paste_card, remind_card {
    background-color: var(--surface);
    border-radius: 18px;
    padding: 18px 4px;
    gap: 6px;
}
photo_kicker, clock_kicker, call_kicker, week_kicker, paste_kicker, remind_kicker {
    color: var(--text-secondary);
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.2px;
}
photo_note, week, pasted, remind_note {
    color: var(--text);
    font-size: 15px;
}
clock_actions, remind_actions {
    display: flex;
    flex-direction: row;
    gap: 10px;
}
"""

run(start_screen=home, theme=theme)
