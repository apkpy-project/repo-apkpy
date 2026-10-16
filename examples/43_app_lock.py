"""App lock - the app locks itself, and the phone's own lock opens it.

A journal that locks a minute after you leave it, and a button that locks it
at once. app_lock.after() says after how many minutes away or untouched,
app_lock.now() locks it, app_lock.off() stops locking, and app_lock.locked()
says whether it is locked.

Locked, the app is covered and the phone asks for a fingerprint, a face or
the screen lock -- its own prompt, which no app can draw or read. The rule is
kept on the phone: closing the app from the recent apps does not open it.

In the Previewer, minimise the window to send the app to the background.

Needs ApkPy 1.13.0.
"""

from apkpy_lib import *

home = Screen(id="home", scroll=True)
unprotected = state(False)

label("Journal", id="title", screen=home)
label("It locks itself a minute after you leave it.", id="lead", screen=home)

banner = container(id="banner", screen=home)
label("No screen lock", id="banner_title", parent=banner)
label("This phone has no PIN, pattern or fingerprint, so the journal cannot lock.", id="banner_text", parent=banner)
unprotected.bind_visibility(banner, when=True)

first = container(id="first", screen=home)
label("12 OCTOBER", id="first_date", parent=first)
label("The day the build went green", id="first_title", parent=first)
label("Three weeks of red, and then one missing comma.", id="first_text", parent=first)

second = container(id="second", screen=home)
label("9 OCTOBER", id="second_date", parent=second)
label("Lisbon to Porto by train", id="second_title", parent=second)
label("Window seat, and the sea on the left for an hour.", id="second_text", parent=second)

actions = container(id="actions", screen=home)


def opened():
    if app_lock.after(1) == "no_lock":
        unprotected.set(True)


lifecycle(home, on_mount=opened)

button("Lock now", id="lock", icon="lock", command=app_lock.now, parent=actions)

theme = Theme(primary="#2F6F5E")

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
first, second {
    background-color: var(--surface);
    border-radius: 18px;
    padding: 18px 4px;
    gap: 4px;
}
first_date, second_date {
    color: var(--text-secondary);
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.2px;
}
first_title, second_title {
    color: var(--text);
    font-size: 20px;
    font-weight: bold;
}
first_text, second_text {
    color: var(--text-secondary);
    font-size: 14px;
    line-height: 1.5;
}
actions {
    display: flex;
    flex-direction: row;
    align-items: center;
    padding: 0px 0px 0px 16px;
    margin-top: 6px;
}
lock {
    border-radius: 24px;
    min-height: 48px;
    padding: 0px 24px;
}
"""

run(start_screen=home, theme=theme)
