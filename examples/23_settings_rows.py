"""A settings screen: grouped rows, hairlines, tracking and leading."""

from apkpy_lib import (
    Screen, Theme, container, device, label, list_row, modal, run,
    snackbar, storage, toast,
)

# Drop your own .ttf beside this file and the screen stops looking like
# every other app built with the same tool. Left commented because the
# example ships no font of its own:
#
#     from apkpy_lib import font
#     font("Display",
#          regular="fonts/YourSerif-Regular.ttf",
#          bold="fonts/YourSerif-Bold.ttf")


settings = Screen(id="settings")

label("Martim", id="account_name", screen=settings)
label("martim@example.com - Free plan", id="account_mail", screen=settings)

# A section header is a label, not a component: what makes it read as one is
# the tracking, the weight and the size, all in the stylesheet below.
label("ACCOUNT", id="account_kicker", screen=settings)

# One container, three rows, hairlines between them and never at the edges.
account = container(id="account", screen=settings)
list_row("Profile", subtitle="Name, photo and handle", icon="person",
         trailing_icon="chevron_right", id="row_profile", parent=account,
         command=lambda: toast("Profile"))
list_row("Billing", icon="star", trailing="Pro",
         trailing_icon="chevron_right", id="row_billing", parent=account,
         command=lambda: toast("Billing"))
list_row("Usage", subtitle="4,812 of 20,000 messages", icon="chart",
         trailing="24%", trailing_icon="chevron_right", id="row_usage",
         parent=account, command=lambda: toast("Usage"))

label("PREFERENCES", id="prefs_kicker", screen=settings)

prefs = container(id="prefs", screen=settings)
list_row("Appearance", icon="image", trailing="Dark",
         trailing_icon="chevron_right", id="row_theme", parent=prefs,
         command=lambda: toast("Dark, and staying that way"))
list_row("Notifications", icon="bell", trailing="Off",
         trailing_icon="chevron_right", id="row_bell", parent=prefs,
         command=lambda: toast("Nothing to notify you about yet"))

label("DATA", id="data_kicker", screen=settings)

data_group = container(id="data_group", screen=settings)
list_row("Export everything", subtitle="A JSON file you keep",
         icon="description", trailing_icon="chevron_right", id="row_export",
         parent=data_group, command=lambda: toast("Nothing to export yet"))
list_row("Delete everything", icon="delete", id="row_wipe",
         parent=data_group, command=lambda: wipe_dialog.open())

label("Deleting clears this device only. Anything already synced stays where "
      "it is, which is the part people forget.", id="footnote", screen=settings)


def wipe_everything():
    storage.set("wiped", "1")
    snackbar("Everything deleted")


wipe_dialog = modal(
    "Delete everything?",
    content="There is no undo. This clears every note on this device.",
    confirm_text="Delete",
    cancel_text="Keep it",
    on_confirm=wipe_everything,
    id="wipe_dialog",
)


theme = Theme(
    mode="dark",
    primary="#C96442", secondary="#8A8880",
    background="#1B1B19", surface="#262624",
    text="#F5F4EF", text_secondary="#9C9A93",
    border="#3A3A37", error="#C4443A",
    radius=16, spacing=12, motion="subtle",
)

style = """
settings { background-color: var(--background); padding: 16px; }

/* Big text wants tightening, not loosening -- the gaps a 24px face leaves
   between letters are already wider than they look at 13px. */
account_name {
    color: var(--text); font-size: 24px; font-weight: bold;
    letter-spacing: -0.4px;
    /* font-family: "Display";  <- with the font() call above */
}
account_mail {
    color: var(--text-secondary); font-size: 13px; line-height: 1.6;
}

/* Tracking is what turns small caps into a section header instead of a
   squashed label. Tk cannot draw it, so the Previewer shows these tight. */
account_kicker, prefs_kicker, data_kicker {
    color: var(--text-secondary); font-size: 11px; font-weight: bold;
    letter-spacing: 1.2px;
    margin-top: 20px; margin-bottom: 6px;
}

/* The group owns the surface, the corners and the hairlines. divider-inset
   starts each line past the icon column, which is the difference between a
   list and a stack of boxes. */
account, prefs, data_group {
    background-color: var(--surface);
    border-radius: 16px;
    padding: 0px;
    divider-color: var(--border);
    divider-inset: 58px;
}

/* The rows sit on the group, so they carry no box of their own. */
list_row {
    background-color: #00000000;
    border-radius: 0px;
    padding: 0px 18px;
    min-height: 60px;
    color: var(--text);
    subtitle-color: var(--text-secondary);
    trailing-color: var(--text-secondary);
    icon-color: var(--text-secondary);
}
row_wipe { color: var(--error); icon-color: var(--error); }

footnote {
    color: var(--text-secondary); font-size: 12px; line-height: 1.7;
    margin-top: 12px;
}
"""

device("Pixel 9")
run(start_screen=settings, theme=theme)
