"""Asking a real API a question, and showing what it answered.

The endpoint here is the Anthropic Messages API because its shape is the one
most people want -- a model name, a token budget and a list of turns -- but
nothing below is specific to it. Point `API_URL` somewhere else, change the
keys in `data=`, and the rest of the file stands.

Two things this example exists to say:

1. `data={...}` goes out as JSON with its types intact. `max_tokens` arrives
   as the number 1024, not as "1024", and the question the user typed is
   escaped by the serialiser -- so a quote or a line break in it does not
   break the request.

2. The key is the user's, not the app's. Anything inside an APK is readable by
   whoever installs it, so an app that ships its own key ships it to everyone.
   Here it is pasted once and kept in `storage`, which is encrypted at rest.
   If the app is meant to speak on *your* account rather than the user's, put
   a server of your own in front of the API instead -- that is the only shape
   where the key never leaves your side.
"""

from apkpy_lib import (
    Screen, Theme, button, container, https, inputs, json_get, label,
    lifecycle, list_row, run, snackbar, storage, toast, virtual_collection,
)

# Three constants describe a provider: where to post, which header carries
# the key, and where in the answer the text lives. Swapping provider is these
# plus the `data=` block in `ask`, and nothing else in the file.
API_URL = "https://api.anthropic.com/v1/messages"
API_MODEL = "claude-sonnet-5"
API_KEY_HEADER = "x-api-key"
API_ANSWER_PATH = "content.0.text"
API_VERSION = "2023-06-01"

# Google Gemini instead:
#
#     API_MODEL = "gemini-2.5-flash"
#     API_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
#                + API_MODEL + ":generateContent")
#     API_KEY_HEADER  = "x-goog-api-key"
#     API_ANSWER_PATH = "candidates.0.content.parts.0.text"
#     data={"contents": [{"parts": [{"text": text}]}],
#           "generationConfig": {"maxOutputTokens": 1024}}
#     headers={API_KEY_HEADER: key}          # drop the anthropic-version one
#
# A constant joined from pieces like that URL is folded into one literal at
# build time, so every name it uses has to be declared above it.


# ------------------------------------------------------------- ask screen

ask_screen = Screen(id="ask")
label("Ask", id="title", screen=ask_screen)
label("The answer comes from the API, and the key is yours.",
      id="blurb", screen=ask_screen)

question = inputs(placeholder="Ask something...", id="question",
                  type="textarea", screen=ask_screen)

actions = container(id="actions", screen=ask_screen)
send_button = button("Ask", id="send", variant="filled",
                     command=lambda: ask(), parent=actions)
button("Settings", id="to_settings", variant="tonal",
       command=lambda: toast("Use the key row below"), parent=actions)

# The answer goes in a collection row with a `markdown` slot rather than a
# label: a model answers with headings, lists and fenced code, and read as
# plain text with backticks in it that is not an answer. `item_height="auto"`
# lets the row take the height the answer needs.
# The `avatar` slot marks who is speaking with a circle of initials, in a
# colour the name itself picks -- the same colour in the Previewer and on the
# phone, because one table decides it.
answer = virtual_collection(
    [{"id": "a", "who": "", "text": ""}],
    template={"avatar": "{who}", "title": "{who}", "markdown": "{text}"},
    id="answer", item_height="auto", screen=ask_screen,
)

key_row = list_row("API key", subtitle="Paste your own; it stays on the phone",
                   icon="bolt", trailing="Not set",
                   trailing_icon="chevron_right",
                   id="key_row", screen=ask_screen)


def answered(success, response):
    """What the API said.

    A callback needs a name -- a lambda does not compile -- and it cannot see
    variables from the function that started the request, because ApkPy reads
    this module rather than running it. Anything it needs comes through
    `storage`, which both sides can actually see.
    """
    if success:
        # content.0.text is where the Messages API keeps the answer. A
        # different API keeps it somewhere else; json_get reads any path.
        answer.merge_items([{"id": "a", "who": "Answer",
                             "text": json_get(response, API_ANSWER_PATH)}])
    else:
        # A failed request still has a body, and it usually says why.
        answer.merge_items([{"id": "a", "who": "Answer",
                             "text": "That did not go through.\n\n"
                                     + response}])
    send_button.show()


def ask():
    text = question.get_value()
    key = storage.get("api_key", "")
    if text == "":
        toast("Type a question first")
    elif key == "":
        toast("Add your API key first")
    else:
        answer.merge_items([{"id": "a", "who": "", "text": "Thinking..."}])
        send_button.hide()
        https.post(
            API_URL,
            # A dict, not a hand-built string: the numbers stay numbers and
            # the escaping is the serialiser's problem rather than yours.
            data={
                "model": API_MODEL,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": text}],
            },
            headers={API_KEY_HEADER: key,
                     "anthropic-version": API_VERSION},
            # Seconds. The default of 60 is already generous for most
            # endpoints and barely enough for one that thinks first.
            timeout=120,
            on_response=answered,
        )


def refresh_ask():
    key_row.set_trailing(storage.get("api_key_state", "Not set"))


lifecycle(ask_screen, on_resume=refresh_ask)


# --------------------------------------------------------- API key screen

key_screen = Screen(id="key")
label("API key", id="key_title", screen=key_screen)
label("Stored on this device and sent to nobody but the API. An app that "
      "shipped its own key would be handing it to everyone who installs it.",
      id="key_note", screen=key_screen)

key_field = inputs(placeholder="sk-ant-...", id="key_field", type="password",
                   screen=key_screen)

key_actions = container(id="key_actions", screen=key_screen)
button("Save", id="key_save", variant="filled", command=lambda: save_key(),
       parent=key_actions)
button("Forget", id="key_clear", variant="tonal", command=lambda: clear_key(),
       parent=key_actions)


def save_key():
    value = key_field.get_value()
    if value == "":
        toast("Nothing to save")
    else:
        storage.set("api_key", value)
        storage.set("api_key_state", "Set")
        key_field.set_value("")
        snackbar("Key saved")


def clear_key():
    storage.delete("api_key")
    storage.set("api_key_state", "Not set")
    key_field.set_value("")
    snackbar("Key forgotten")


ask_screen.on_click_navigate(button=key_row, to=key_screen)

run(start_screen=ask_screen,
    theme=Theme(mode="dark", primary="#C96442", radius=20, spacing=12))

style = """
ask, key { background-color: var(--background); padding: 20px; }

title, key_title {
    font-size: 30px; font-weight: bold;
    letter-spacing: -0.4px; padding-bottom: 4px;
}
blurb, key_note {
    color: var(--text-secondary); font-size: 15px;
    line-height: 1.45; padding-bottom: 18px;
}

/* Starts at three lines and grows to eight as the question does. */
question { rows: 3; max-rows: 8; }

actions, key_actions {
    display: flex; flex-direction: row; gap: 10px; padding-top: 12px;
}

/* The answer is prose, so it gets the leading that prose needs. And a
   model answers with code in it, which is only useful if it can be taken. */
answer {
    padding-top: 22px; font-size: 16px; line-height: 1.55;
    color: var(--text);
    code-copy: button;
}

key_row { margin-top: 28px; border-radius: 16px; }
"""
