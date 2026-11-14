from apkpy_lib import *

home = Screen(id="home")
chat = Screen(id="chat")


def icon(name, parent, action):
    button("", id=name, icon=name, describe=name, parent=parent, command=action)


# The chat list

top = container(id="top", screen=home)
label("Chats", id="title", parent=top)
container(id="space", parent=top)
icon("photo_camera", top, lambda: toast("Camera"))
icon("more_vert", top, lambda: toast("Settings"))

inputs("Search", id="search", screen=home)

CHATS = [
    {"name": "Mara Vale", "last": "Yes! 8pm at Barr", "time": "21:42", "unread": "2", "group": ""},
    {"name": "Liv Moreau", "last": "Photo", "time": "20:15", "unread": "", "group": ""},
    {"name": "Family", "last": "Mum: Dinner on Sunday?", "time": "19:03", "unread": "5", "group": "yes"},
    {"name": "Theo Park", "last": "Sent you the tickets", "time": "Yesterday", "unread": "", "group": ""},
    {"name": "Running club", "last": "Ana: 7am at the park", "time": "Yesterday", "unread": "", "group": "yes"},
    {"name": "Nell Shore", "last": "Thank you!!", "time": "Monday", "unread": "", "group": ""},
]

ROW = {"avatar": "{name}", "title": "{name}", "subtitle": "{last}", "meta": "{time}", "badge": "{unread}"}


def show(kind):
    shown = []
    for c in CHATS:
        if kind == "Unread" and c["unread"] == "":
            continue
        if kind == "Groups" and c["group"] == "":
            continue
        shown.append(c)
    chats.set_items(shown)


def open_chat(item):
    name.set_value(item["name"])
    on_click_navigate(chat)


chips(["All", "Unread", "Groups"], selected="All", check=False, on_change=show, id="filters", screen=home)
chats = virtual_collection(CHATS, template=ROW, item_height="auto", on_click=open_chat, id="chats", screen=home)
button("", id="new_chat", icon="add_comment", describe="New chat", screen=home)


# The conversation

bar = container(id="bar", screen=chat)
icon("arrow_back", bar, back)
avatar("face1.png", size=40, id="face", parent=bar, describe="")
who = container(id="who", parent=bar)
name = label("Mara Vale", id="name", parent=who)
label("online", id="status", parent=who)
icon("videocam", bar, lambda: toast("Video call"))
icon("call", bar, lambda: toast("Call"))

MESSAGES = [
    {"kind": "day", "text": "TODAY"},
    {"kind": "them", "text": "Are we still on for tonight?", "time": "21:30"},
    {"kind": "read", "text": "Yes! 8pm at Barr", "time": "21:31"},
    {"kind": "them", "text": "Perfect. I booked a table by the window", "time": "21:40"},
    {"kind": "read", "text": "Amazing, see you there", "time": "21:42"},
]

BUBBLES = {
    "day": {"meta": "{text}"},
    "them": {"subtitle": "{text}", "meta": "{time}"},
    "mine": {"subtitle": "{text}", "meta": "{time} ✓"},
    "read": {"subtitle": "{text}", "meta": "{time} ✓✓"},
}

messages = virtual_collection(MESSAGES, variant="{kind}", template=BUBBLES, item_height="auto", id="messages", screen=chat)

composer = container(id="composer", screen=chat)
field = container(id="field", parent=composer)
icon("mood", field, lambda: toast("Emoji"))
message = inputs("Message", id="message", parent=field)
icon("attach_file", field, lambda: toast("Attach"))


def send():
    text = message.get_value()
    if text == "":
        return
    time = datetime.hour() + ":" + datetime.minute()
    messages.append_items([{"kind": "mine", "text": text, "time": time}])
    messages.scroll_to_end()
    message.set_value("")


icon("send", composer, send)


style = """
home, chat {
    background-color: #0B141A;
    padding: 0px;
    gap: 12px;
}

button {
    width: 48px;
    height: 48px;
    background-color: transparent;
    icon-color: #E9EDEF;
}

top {
    display: flex;
    flex-direction: row;
    align-items: center;
    padding: 14px 8px 6px 16px;
}

title {
    font-size: 24px;
    font-weight: bold;
    color: #FFFFFF;
}

space {
    flex-grow: 1;
}

search {
    margin: 4px 14px;
    padding: 12px 18px;
    border-radius: 24px;
    border-width: 0px;
    background-color: #202C33;
    color: #E9EDEF;
    placeholder-color: #8696A0;
}

filters {
    margin: 2px 14px 0px 14px;
    border-radius: 16px;
    border-color: transparent;
    background-color: #202C33;
    color: #8696A0;
    font-size: 13px;
    active-color: #D9FDD3;
    indicator-color: #103529;
}

chats {
    height: 620px;
    item-background-color: #0B141A;
    item-border-color: #0B141A;
    title-color: #E9EDEF;
    subtitle-color: #8696A0;
    meta-color: #8696A0;
    badge-background-color: #21C063;
    badge-color: #0B141A;
    badge-position: end;
}

new_chat {
    position: absolute;
    right: 18px;
    bottom: 22px;
    width: 56px;
    height: 56px;
    border-radius: 16px;
    background-color: #21C063;
    icon-color: #0B141A;
}

bar {
    display: flex;
    flex-direction: row;
    align-items: center;
    padding: 8px 4px;
    background-color: #1F2C34;
}

who {
    flex-grow: 1;
}

name {
    font-size: 17px;
    font-weight: bold;
    color: #E9EDEF;
}

status {
    font-size: 12px;
    color: #8696A0;
}

messages {
    height: 640px;
    gap: 6px;
    item-border-radius: 10px;
    item-background-color: #202C33;
    subtitle-lines: 30;
    subtitle-color: #E9EDEF;
    meta-color: #8696A0;
}

messages:them {
    align-self: flex-start;
    max-width: 80%;
}

messages:mine, messages:read {
    align-self: flex-end;
    max-width: 80%;
    item-background-color: #005C4B;
    meta-color: #9FC2B9;
}

messages:read {
    meta-color: #53BDEB;
}

messages:day {
    align-self: center;
    item-background-color: #182229;
}

composer {
    position: absolute;
    left: 6px;
    right: 6px;
    bottom: 6px;
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 6px;
}

field {
    flex-grow: 1;
    display: flex;
    flex-direction: row;
    align-items: center;
    border-radius: 26px;
    background-color: #202C33;
}

mood, attach_file {
    icon-color: #8696A0;
}

message {
    flex-grow: 1;
    border-width: 0px;
    background-color: transparent;
    color: #E9EDEF;
    placeholder-color: #8696A0;
    font-size: 16px;
}

send {
    width: 50px;
    height: 50px;
    border-radius: 25px;
    background-color: #21C063;
    icon-color: #0B141A;
}
"""

run(start_screen=home)
