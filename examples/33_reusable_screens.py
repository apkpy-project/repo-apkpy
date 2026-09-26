"""Pace - three screens built from two functions.

header() and stat() are written once. header() puts a title and a line of
text on each screen; stat() builds a card and hands back the number inside it,
so the button on Today can change it later. The History and Profile cards come
out of plain loops over lists written in the file.

The Previewer runs this as Python. For the phone, ApkPy puts each call's body
where the call is before it translates anything -- the same components, on the
same screens. Call header() from a button instead and the build stops with
U2038: by then the screens exist.

Needs ApkPy 1.11.0.
"""

from apkpy_lib import *

style = """
body { background-color: #0f1115; }
#screen_title { color: #f3f4f6; font-size: 24px; font-weight: bold;
                margin-top: 24px; margin-left: 18px; }
#screen_subtitle { color: #9ca3af; font-size: 14px; margin-top: 4px;
                   margin-left: 18px; }
#stat { background-color: #181b22; border-radius: 16px; margin-top: 14px;
        margin-left: 18px; margin-right: 18px; padding: 16px; }
#stat_name { color: #9ca3af; font-size: 13px; }
#stat_value { color: #f3f4f6; font-size: 24px; font-weight: bold;
              margin-top: 4px; }
#log { background-color: #4f46e5; color: #ffffff; border-radius: 12px;
       font-size: 16px; margin-top: 22px; margin-left: 18px;
       margin-right: 18px; }
"""

today = Screen(id="today")
history = Screen(id="history")
profile = Screen(id="profile")


def header(title, subtitle, screen):
    label(title, id="screen_title", screen=screen)
    label(subtitle, id="screen_subtitle", screen=screen)


def stat(name, value, screen):
    box = card(id="stat", screen=screen)
    label(name, id="stat_name", parent=box)
    number = label(value, id="stat_value", parent=box)
    return number


header("Today", "One run a day keeps the streak alive.", today)
distance = stat("Distance", "0.0 km", today)
streak = stat("Streak", "4 days", today)


def log_run():
    distance.set_value("5.2 km")
    streak.set_value("5 days")


button("Log a 5 km run", id="log", screen=today, command=log_run)

header("History", "The last three weeks.", history)
for week, km in [
    ("This week", "18.4 km"),
    ("Last week", "22.1 km"),
    ("Two weeks ago", "15.0 km"),
]:
    stat(week, km, history)

header("Profile", "Shoes, goal and units.", profile)
for name, value in [
    ("Shoes", "Pegasus 41 - 212 km"),
    ("Monthly goal", "80 km"),
    ("Units", "Kilometres"),
]:
    stat(name, value, profile)

bottom_nav(
    [today, history, profile],
    labels=["Today", "History", "Profile"],
    icons=["home", "chart", "person"],
)
run(start_screen=today)
