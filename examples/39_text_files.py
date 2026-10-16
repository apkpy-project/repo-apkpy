"""Journal - text kept in the app's own files.

One page that is still there the next time the app opens, and a history of
every save. files.write() keeps the page, files.append() adds a line to the
history, files.read() brings both back, and files.delete() starts the
history again.

The files live in the app's own folder. There is no permission to ask for,
and nothing the person has to choose.

Needs ApkPy 1.13.0.
"""

from apkpy_lib import *

home = Screen(id="home", scroll=True)

label("Journal", id="title", screen=home)
label("Kept in a file of the app. Close it, and it is still here.", id="lead", screen=home)

page = inputs("Write something", id="page", type="textarea", screen=home)

actions = container(id="actions", screen=home)
status = label("", id="status", parent=actions)

past = container(id="past", screen=home)
past_head = container(id="past_head", parent=past)
label("HISTORY", id="past_kicker", parent=past_head)
history = label("", id="history", parent=past)


def show_history():
    lines = files.read("history.txt").strip()
    if lines == "":
        history.set_value("Nothing saved yet.")
    else:
        history.set_value(lines)


def opened():
    page.set_value(files.read("journal.txt"))
    show_history()


def save():
    text = page.get_value()
    word = files.write("journal.txt", text)
    if word == "ok":
        files.append("history.txt", datetime.now() + "   " + str(len(text)) + " characters\n")
        status.set_value("Saved")
    else:
        status.set_value("Not saved: " + word)
    show_history()


def forget():
    files.delete("history.txt")
    status.set_value("")
    show_history()


lifecycle(home, on_mount=opened)

button("Save", id="save", icon="save", command=save, parent=actions)
button("Clear", id="forget", variant="text", command=forget, parent=past_head)

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
page {
    background-color: var(--surface);
    border-radius: 18px;
    border-width: 0px;
    padding: 16px;
    font-size: 16px;
    rows: 6;
    max-rows: 10;
}
actions {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    padding: 0px 0px 0px 16px;
}
status {
    color: var(--text-secondary);
    font-size: 14px;
}
save {
    border-radius: 24px;
    min-height: 48px;
    padding: 0px 22px;
}
past {
    background-color: var(--surface);
    border-radius: 18px;
    padding: 6px 8px 18px 0px;
    margin-top: 8px;
}
past_head {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    padding: 0px 0px 0px 16px;
}
past_kicker {
    color: var(--text-secondary);
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.2px;
}
history {
    color: var(--text);
    font-size: 14px;
    line-height: 1.6;
}
"""

run(start_screen=home, theme=theme)
