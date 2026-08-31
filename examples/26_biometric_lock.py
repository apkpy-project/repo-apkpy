"""A vault behind the fingerprint, and the seven reasons a check can fail."""

from apkpy_lib import (
    Screen, Theme, app_bar, biometrics, button, container, label,
    on_click_navigate, run,
)

home = Screen(id="home")
vault = Screen(id="vault")

app_bar("Locked", screen=home)
label("Your notes", id="title", screen=home)
label("They stay closed until you confirm it is you.", id="blurb", screen=home)

# The reason is worth showing rather than swallowing: "no sensor on this phone"
# and "you pressed cancel" need different answers from the app, and an empty
# string would give it neither.
status = label("", id="status", screen=home)

actions = container(id="actions", screen=home)
button("UNLOCK", id="go", icon="lock", parent=actions,
       command=lambda: ask())
button("UNLOCK, PIN ALLOWED", id="gopin", icon="fingerprint", parent=actions,
       command=lambda: ask_pin())

app_bar("Your notes", screen=vault)
label("You are in", id="vtitle", screen=vault)
label("Everything here was worth a fingerprint.", id="vblurb", screen=vault)


def unlocked(ok, reason):
    if ok:
        on_click_navigate(vault)
    elif reason == "cancelled":
        status.set_value("")                 # they chose to stop; say nothing
    elif reason == "no_hardware":
        status.set_value("This phone has no fingerprint sensor.")
    elif reason == "not_enrolled":
        status.set_value("Add a fingerprint in Settings first.")
    elif reason == "lockout":
        status.set_value("Too many tries. Wait, or use your PIN.")
    else:
        status.set_value("Could not confirm it was you.")


def ask():
    # Android draws this dialog itself, so these three strings are the whole
    # design: the platform draws the shape, the colours and the sensor.
    biometrics.unlock(
        title="Unlock your notes",
        subtitle="Use your fingerprint",
        cancel_text="Use password",
        on_result=unlocked,
    )


def ask_pin():
    # allow_pin adds the device PIN, pattern or password. The cancel button
    # goes away in this mode -- Android's builder refuses a negative button
    # next to the credential option, and draws its own way out instead.
    biometrics.unlock(
        title="Confirm it's you",
        allow_pin=True,
        on_result=unlocked,
    )


run(start_screen=home, theme=Theme(mode="dark"))

style = """
home, vault { background-color: var(--background); padding: 22px; }

title, vtitle {
    color: var(--text); font-size: var(--text-2xl); font-weight: bold;
    margin-bottom: 6px;
}
blurb, vblurb {
    color: var(--text-secondary); font-size: var(--text-base);
    line-height: var(--leading-normal); margin-bottom: 20px;
}
status {
    color: var(--error); font-size: var(--text-base);
    line-height: var(--leading-normal); margin-bottom: 14px;
}

actions { background-color: #00000000; }
go, gopin {
    width: 100%; min-height: 52px; border-radius: 16px;
    font-weight: bold; margin-bottom: 12px;
}
"""
