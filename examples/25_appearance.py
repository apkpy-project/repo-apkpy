"""An appearance screen: the app changes its colours while it runs."""

from apkpy_lib import (
    Screen, Theme, action, app_bar, appearance, container, label, lifecycle,
    list_row, run,
)

home = Screen(id="home")
app_bar("Appearance", screen=home)

label("Choose how the app looks. The choice is remembered, so it opens the "
      "way you left it.", id="blurb", screen=home)

modes = container(id="modes", screen=home)
row_dark = list_row("Dark", subtitle="Warm greys, low light", icon="dark_mode",
                    trailing="", id="row_dark", parent=modes,
                    command=lambda: pick("dark"))
row_light = list_row("Light", subtitle="Paper, for daylight",
                     icon="light_mode", trailing="", id="row_light",
                     parent=modes, command=lambda: pick("light"))
row_system = list_row("Follow the system",
                      subtitle="Whatever the phone is doing", icon="contrast",
                      trailing="", id="row_system", parent=modes,
                      command=lambda: pick("system"))

label("THE RULE", id="kicker", screen=home)
swatches = container(id="swatches", screen=home)
label("This one came from a token, and follows the switch.",
      id="from_token", parent=swatches)
label("This one was written by hand, and does not.",
      id="by_hand", parent=swatches)


def pick(choice):
    # One call does the lot: it remembers the choice, puts the matching colour
    # table in force, and lets the screen come back wearing it.
    appearance.set(choice)


def mark():
    current = appearance.get()
    row_dark.set_trailing("Selected" if current == "dark" else "")
    row_light.set_trailing("Selected" if current == "light" else "")
    row_system.set_trailing("Selected" if current == "system" else "")


# The activity is rebuilt when the mode changes, so the marker is set on the
# way in rather than at the moment of the tap.
lifecycle(home, on_resume=mark)

run(start_screen=home,
    theme=Theme(mode="dark", primary="#C96442", background="#1B1B19",
                surface="#262624", text="#F5F4EF"))

style = """
body      { background-color: var(--background); padding: 0 20 24 20; }
blurb     { color: var(--text_secondary); font-size: 14; line-height: 1.5;
            padding: 8 4 20 4; }

modes     { background-color: var(--surface); border-radius: 16;
            divider-color: var(--border); divider-inset: 56; }
row_dark, row_light, row_system { padding: 14 16 14 16; }

kicker    { color: var(--text_secondary); font-size: 11; font-weight: bold;
            letter-spacing: 1.2; padding: 28 4 8 4; }
swatches  { background-color: var(--surface); border-radius: 16;
            padding: 16 16 16 16; }

/* A token: the night table answers it, so this line flips with the switch. */
from_token { color: var(--text); font-size: 14; padding: 0 0 10 0; }

/* A literal: a decision, not a default. It stays exactly this colour in both
   modes -- which is the point, and is why the two lines look different once
   you switch to Light. */
by_hand   { color: #C96442; font-size: 14; }
"""
