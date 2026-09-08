"""ApkPy 1.7.0 static wallpaper demo. Never applies without confirmation."""
from apkpy_lib import (
    Screen, Theme, app_bar, label, button, gallery, wallpaper, state, run,
)

home = Screen(id="home", scroll=True)
app_bar("Wallpaper Lab", screen=home)
target = state("home")

label("PERSONALISATION / 1.7.0", id="kicker", screen=home)
label("Make it yours.", id="headline", screen=home)
label("Choose a static image, review it and confirm. Nothing changes until you tap Apply.",
      id="intro", screen=home)
selected_target = label("Target: home screen", id="target_label", screen=home)
status = label("Ready - choose where to apply your image.", id="status", screen=home)


def use_home():
    target.set("home")
    selected_target.set_value("Target: home screen")


def use_lock():
    target.set("lock")
    selected_target.set_value("Target: lock screen")


def use_both():
    target.set("both")
    selected_target.set_value("Target: home and lock screens")


def applied(success, reason):
    if success:
        status.set_value("Completed: " + reason)
    else:
        status.set_value("Not changed: " + reason)


def picked(success, path):
    if success:
        status.set_value("Preparing confirmation...")
        wallpaper.set(path, target=target.get(), on_result=applied)
    else:
        status.set_value("No image selected.")


def choose_image():
    if wallpaper.available():
        gallery.pick(on_result=picked)
    else:
        status.set_value("Changing wallpaper is not allowed on this device.")


button("Home screen", id="home_target", variant="outlined", command=use_home, screen=home)
button("Lock screen", id="lock_target", variant="outlined", command=use_lock, screen=home)
button("Both screens", id="both_target", variant="outlined", command=use_both, screen=home)
button("Choose image", id="choose_image", icon="image", command=choose_image, screen=home)
label("The desktop Previewer simulates this flow. Android applies the image locally; your launcher may crop or zoom it.",
      id="notice", screen=home)

style = """
body { background-color: #0C0E15; color: #F1F3F8; padding: 22px; }
label { margin-bottom: 16px; }
#kicker { color: #65E6D4; font-size: 11px; font-weight: bold; margin-top: 20px; }
#headline { font-size: 30px; font-weight: bold; }
#intro, #notice { color: #ADB5C6; font-size: 14px; }
#target_label { font-size: 18px; font-weight: bold; margin-top: 12px; }
#status { color: #65E6D4; font-size: 13px; }
button { min-height: 48px; margin-bottom: 12px; }
#choose_image { margin-top: 12px; }
"""

run(start_screen=home, theme=Theme(mode="dark", primary="#7856FF"))
