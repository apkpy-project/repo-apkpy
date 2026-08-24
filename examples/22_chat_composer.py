"""A chat composer: borderless field, a row of pills, and a send/stop swap."""

from apkpy_lib import (
    Screen, Theme, button, container, device, inputs, label, list_view,
    popup_menu, run, toast,
)


MODELS = ["Opus 5", "Sonnet 5", "Haiku 4.5"]
MODES = ["Auto", "Fast", "Thorough"]

# The starting rows are written out literally in the list_view(...) call as
# well: the Android build reads the initial items from the source at build
# time, so it needs a literal there, not a name.
MESSAGES = [
    {"title": "You", "subtitle": "Summarise the release notes."},
    {"title": "Assistant", "subtitle": "Three things changed this week..."},
]

room = Screen(id="room")

label("Ask anything", id="title", screen=room)

thread = list_view(
    id="thread",
    items=[
        {"title": "You", "subtitle": "Summarise the release notes."},
        {"title": "Assistant", "subtitle": "Three things changed this week..."},
    ],
    screen=room,
)

# The composer is one styled container: a field with no border of its own,
# sitting directly on the container's surface, and a row of controls under it.
composer = container(id="composer", screen=room)
field = inputs(
    id="field", placeholder="Reply to the thread...", type="textarea",
    parent=composer,
)


# The value a menu passes back is what both runtimes can carry into the
# callback, so the confirmation is built from `choice` and nothing else.
def pick_model(choice):
    toast(choice)


def pick_mode(choice):
    toast(choice)


def attach():
    toast("Attach a file")


def send():
    text = field.get_value()
    if not text:
        toast("Nothing to send")
        return
    MESSAGES.append({"title": "You", "subtitle": text})
    thread.set_items(list(MESSAGES))
    # Clearing the field brings the placeholder back, exactly as android:hint
    # does on the phone.
    field.set_value("")
    send_button.hide()
    stop_button.show()


def stop():
    stop_button.hide()
    send_button.show()
    toast("Stopped")


# The controls are declared in the order they appear across the row.
controls = container(id="controls", parent=composer)

button("Attach", id="plus", variant="icon", icon="add",
       command=attach, parent=controls)
model_chip = button("Opus 5", id="model", variant="tonal", icon="expand_more",
                    parent=controls)
mode_chip = button("Auto", id="mode", variant="tonal", icon="bolt",
                   parent=controls)

# An empty flex-grow container is the spacer that pushes the right-hand
# controls to the edge, exactly as it would in CSS.
container(id="spacer", parent=controls)

# One control on the right at a time: a row of six pills overflows a 400dp
# phone, and `flex-shrink: 0` turns that overflow into a clipped button
# instead of a wrapped label. Both are wrong; fitting is the fix.
send_button = button("Send", id="send", variant="icon", icon="send",
                     command=send, parent=controls)
stop_button = button("Stop", id="stop", variant="icon", icon="stop",
                     command=stop, parent=controls)
stop_button.hide()

popup_menu(anchor=model_chip, items=MODELS, on_select=pick_model)
popup_menu(anchor=mode_chip, items=MODES, on_select=pick_mode)

theme = Theme(
    mode="dark", primary="#2F2F2F", secondary="#8E8E8E",
    background="#191919", surface="#212121", text="#F5F5F5",
    text_secondary="#9B9B9B", border="#3A3A3A", radius=28, spacing=12,
    motion="subtle",
)

style = """
room { background-color: var(--background); padding: 18px; }
title { color: var(--text); font-size: 22px; font-weight: bold; }
thread {
    height: 280px; margin-top: 10px;
    item-background-color: var(--surface);
    item-border-color: var(--border);
    title-color: var(--text); subtitle-color: var(--text-secondary);
}

composer {
    margin-top: 14px;
    background-color: var(--surface);
    border-color: var(--border); border-width: 1px; border-radius: 28px;
    padding: 16px;
}

/* #00000000 is a transparent surface: the field is the container behind it,
   with no box of its own. border-width: 0 keeps it that way when focused. */
field {
    background-color: #00000000;
    border-width: 0px;
    /* Starts at one line and stops at six: two fixed lines are half an
       empty composer waiting, and past six a draft eats the thread. */
    rows: 1;
    max-rows: 6;
    color: var(--text);
    placeholder-color: var(--text-secondary);
    font-size: 16px;
    rows: 3;
    margin-bottom: 6px;
}

controls {
    display: flex; flex-direction: row; align-items: center;
    gap: 8px; width: 100%;
    background-color: #00000000; padding: 0px;
}
spacer { flex-grow: 1; background-color: #00000000; padding: 0px; }

/* flex-shrink: 0 keeps a pill at its natural width. Without it the row
   overflows on a narrow phone and Android wraps the label mid-word. */
plus, send, stop {
    background-color: #00000000; color: var(--text);
    min-height: 40px; border-radius: 999px;
    flex-grow: 0; flex-shrink: 0;
}

/* text-transform: none stops Material from shouting "OPUS 5". */
model, mode {
    background-color: #2F2F2F; color: var(--text);
    min-height: 40px; border-radius: 999px;
    padding: 8px 12px;
    font-size: 13px; font-weight: bold;
    text-transform: none; flex-grow: 0; flex-shrink: 0;
}
"""

device("Pixel 9")
run(start_screen=room, theme=theme)
