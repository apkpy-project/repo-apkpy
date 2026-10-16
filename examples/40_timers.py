"""Timers - a function run later, or again and again.

A clock that ticks, a countdown you can pause, a search that waits for the
typing to stop, and a message that goes away on its own. timer.every() runs
a function again and again, timer.after() runs it once, timer.cancel() stops
it, and timer.running() says whether it is waiting.

A timer is known by the function it calls. Starting it again starts it over,
which is all "wait until the typing stops" takes.

Needs ApkPy 1.13.0.
"""

from apkpy_lib import *

home = Screen(id="home", scroll=True)

label("Timers", id="title", screen=home)
label("A function run later, or again and again.", id="lead", screen=home)

clock_card = container(id="clock_card", screen=home)
label("NOW", id="clock_kicker", parent=clock_card)
clock = label("--:--:--", id="clock", parent=clock_card)

rest_card = container(id="rest_card", screen=home)
label("REST", id="rest_kicker", parent=rest_card)
left = label("30", id="left", parent=rest_card)
rest_note = label("Seconds to go", id="rest_note", parent=rest_card)
rest_actions = container(id="rest_actions", parent=rest_card)

search_card = container(id="search_card", screen=home)
label("SEARCH", id="search_kicker", parent=search_card)

save_row = container(id="save_row", screen=home)
saved = label("", id="saved", parent=save_row)


def tick():
    clock.set_value(datetime.time())


def opened():
    tick()
    timer.every(1, tick)


def count_down():
    seconds = int(left.get_value()) - 1
    left.set_value(str(seconds))
    if seconds <= 0:
        timer.cancel(count_down)
        rest_note.set_value("Time is up")
        start.set_value("Start")


def start_or_pause():
    if timer.running(count_down):
        timer.cancel(count_down)
        rest_note.set_value("Paused")
        start.set_value("Start")
    else:
        if int(left.get_value()) <= 0:
            left.set_value("30")
        timer.every(1, count_down)
        rest_note.set_value("Seconds to go")
        start.set_value("Pause")


def reset():
    timer.cancel(count_down)
    left.set_value("30")
    rest_note.set_value("Seconds to go")
    start.set_value("Start")


def search():
    text = query.get_value()
    if text == "":
        found.set_value("Nothing searched yet.")
    else:
        found.set_value("Searched for " + text)


def typed(value):
    found.set_value("Waiting for you to stop...")
    timer.after(0.5, search)


def forget_saved():
    saved.set_value("")


def save():
    saved.set_value("Saved")
    timer.after(2, forget_saved)


lifecycle(home, on_mount=opened)

start = button("Start", id="start", command=start_or_pause, parent=rest_actions)
button("Reset", id="reset", variant="text", command=reset, parent=rest_actions)

query = inputs("Type a word", id="query", on_change=typed, parent=search_card)
found = label("Nothing searched yet.", id="found", parent=search_card)

button("Save", id="save", icon="save", command=save, parent=save_row)

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
clock_card, rest_card, search_card {
    background-color: var(--surface);
    border-radius: 18px;
    padding: 18px 4px;
    gap: 4px;
}
clock_kicker, rest_kicker, search_kicker {
    color: var(--text-secondary);
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.2px;
}
clock {
    color: var(--text);
    font-size: 40px;
    font-weight: bold;
}
left {
    color: var(--primary);
    font-size: 56px;
    font-weight: bold;
}
rest_note {
    color: var(--text-secondary);
    font-size: 14px;
}
rest_actions {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 8px;
    padding: 0px 0px 0px 16px;
    margin-top: 12px;
}
start {
    border-radius: 24px;
    min-height: 48px;
    padding: 0px 28px;
}
query {
    background-color: var(--background);
    border-radius: 14px;
    border-width: 0px;
    padding: 14px 16px;
    font-size: 16px;
    margin-top: 8px;
    margin-bottom: 8px;
}
found {
    color: var(--text-secondary);
    font-size: 14px;
}
save_row {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    padding: 4px 0px 0px 20px;
}
saved {
    color: var(--text-secondary);
    font-size: 14px;
}
save {
    border-radius: 24px;
    min-height: 48px;
    padding: 0px 22px;
}
"""

run(start_screen=home, theme=theme)
