"""Chat history that prepends older messages and reconciles a local send."""

from apkpy_lib import (
    Screen, Theme, app_bar, button, container, device, inputs, label, run,
    toast, virtual_collection,
)


MESSAGES = [
    {"id": "msg-3", "avatar": "https://picsum.photos/seed/chat-jules/128/128",
     "author": "Jules", "message": "The latest brief is in the shared folder.",
     "time": "10:42", "state": "DELIVERED"},
    {"id": "msg-4", "avatar": "https://picsum.photos/seed/chat-you/128/128",
     "author": "You", "message": "Got it. I will leave comments before lunch.",
     "time": "10:44", "state": "READ"},
    {"id": "msg-5", "avatar": "https://picsum.photos/seed/chat-jules/128/128",
     "author": "Jules",
     "message": "Perfect. No need to rebuild the whole thread.",
     "time": "10:45", "state": "LIVE"},
]

OLDER = [
    {"id": "msg-1", "avatar": "https://picsum.photos/seed/chat-jules/128/128",
     "author": "Jules",
     "message": "Morning - are we still reviewing the release today?",
     "time": "09:18", "state": "HISTORY"},
    {"id": "msg-2", "avatar": "https://picsum.photos/seed/chat-you/128/128",
     "author": "You", "message": "Yes. Send the final build when it is ready.",
     "time": "09:21", "state": "HISTORY"},
]

room = Screen(id="room", scroll=True)
app_bar("Release room", screen=room)


def open_message(item):
    toast(item["author"] + " at " + item["time"])


def load_earlier():
    # Keep repeated refreshes deterministic in this standalone example.
    thread.remove_item("msg-1")
    thread.remove_item("msg-2")
    thread.prepend_items(OLDER)
    thread.finish_load(has_more=True)
    status.set_value("Two older messages inserted above the current view")
    toast("Earlier messages loaded without a jump")


def send_message():
    message = composer.get_value()
    if message == "":
        toast("Write a message first")
    else:
        thread.merge_items(
            [{
                "id": "local-draft",
                "avatar": "https://picsum.photos/seed/chat-you/128/128",
                "author": "You", "message": message, "time": "now",
                "state": "SENDING",
            }]
        )
        composer.set_value("")
        # Adding a row does not move the viewport by itself. In a feed that
        # is right; in a conversation it means writing a message and then
        # looking at the one above it.
        thread.scroll_to_end()
        status.set_value("Local message visible while the server responds")


def accept_message():
    thread.update_item(
        "local-draft",
        {"state": "DELIVERED"},
        optimistic="delivery-state",
    )
    thread.commit("delivery-state")
    status.set_value("Server accepted the local message")


label("MESSAGE HISTORY", id="kicker", screen=room)
label("Older context, same reading position.", id="title", screen=room)
label(
    "Pull down or use LOAD EARLIER. New messages reconcile by message ID.",
    id="copy",
    screen=room,
)
status = label("Three recent messages", id="status", screen=room)

thread = virtual_collection(
    MESSAGES,
    template={
        "image": "{avatar}", "title": "{author}", "subtitle": "{message}",
        "meta": "{time}", "badge": "{state}",
    },
    id="thread",
    item_height=120,
    buffer=3,
    on_click=open_message,
    on_refresh=load_earlier,
    screen=room,
)

button("LOAD EARLIER", id="load_earlier", variant="outlined",
       command=thread.refresh, screen=room)
composer = inputs("Write a message", id="composer", screen=room)
send_row = container(id="send_row", screen=room)
button("SEND", command=send_message, parent=send_row)
button("MARK DELIVERED", variant="outlined", command=accept_message,
       parent=send_row)

theme = Theme(
    mode="dark", primary="#2E7CF6", secondary="#69E1C2",
    background="#090C12", surface="#151A23", text="#F4F7FC",
    text_secondary="#9DA8B8", border="#2D3542", radius=18, spacing=14,
)

style = """
room { background-color: var(--background); padding: 18px; }
kicker { color: var(--secondary); font-size: 11px; font-weight: bold; }
title { color: var(--text); font-size: 25px; font-weight: bold; }
copy { color: var(--text-secondary); font-size: 13px; }
status { color: var(--secondary); font-size: 12px; font-weight: bold; }
thread {
    height: 480px; item-background-color: var(--surface);
    item-border-color: var(--border); title-color: var(--text);
    subtitle-color: var(--text-secondary); meta-color: var(--secondary);
    badge-background-color: var(--primary); badge-color: #FFFFFF;
}
load_earlier { width: 100%; margin-top: 10px; }
composer { margin-top: 12px; border-radius: 16px; min-height: 48px; }
send_row { display: flex; flex-direction: row; gap: 10px; margin-top: 10px; }
button { flex-grow: 1; border-radius: 15px; min-height: 46px; }
"""

device("Pixel 9")
run(start_screen=room, theme=theme)
