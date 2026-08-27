# ApkPy 1.4.0 — Talking to a model, and an app that looks like yours

Two batches that turned out to be one.

**Part 1** is an app that can hold a conversation with an API: a request body
that keeps its types, a timeout long enough for something that thinks first,
an answer rendered as Markdown, and a row that takes the height that answer
needs.

**Part 2** is an app that stops looking like every other app built with the
same tool: a navigation drawer, a settings row, a typeface of your own, and
control over tracking, leading and alignment.

They ship together because they are the same problem seen twice. An assistant
app is not hard to *build* — it is hard to make **look right**, and every
shape it needs was missing.

Everything is opt-in. An app that mentions none of it generates byte-identical
XML to the one 1.3.2 generated.

---

## Part 1 — A conversation with an API

### A dict is a JSON body

Until 1.4.0 every value in a generated app was a string. Now a `dict` passed
as `data=` is serialised as JSON with the types of the literal intact.

```python
from apkpy_lib import Screen, button, https, inputs, json_get, run, storage, virtual_collection

ask = Screen(id="ask")
question = inputs(placeholder="Ask something...", id="question",
                  type="textarea", screen=ask)

answer = virtual_collection(
    [{"id": "a", "who": "", "text": ""}],
    template={"avatar": "{who}", "title": "{who}", "markdown": "{text}"},
    id="answer", item_height="auto", screen=ask,
)


def answered(success, response):
    if success:
        answer.merge_items([{"id": "a", "who": "Answer",
                             "text": json_get(response, "content.0.text")}])
    else:
        answer.merge_items([{"id": "a", "who": "Answer",
                             "text": "That did not go through.\n\n" + response}])


def send():
    https.post(
        "https://api.anthropic.com/v1/messages",
        data={
            "model": "claude-sonnet-5",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": question.get_value()}],
        },
        headers={"x-api-key": storage.get("api_key", ""),
                 "anthropic-version": "2023-06-01"},
        timeout=120,
        on_response=answered,
    )


button("Ask", id="send", variant="filled", command=send, screen=ask)
run(start_screen=ask)

style = """
question { rows: 3; max-rows: 8; }
answer   { code-copy: button; line-height: 1.55; }
"""
```

`max_tokens` reaches the far end as the number `1024`, not as `"1024"` — the
difference between an API accepting the request and rejecting it. Nested
objects and arrays nest.

It matters just as much that you are **not building the body by
concatenation**. The first time a user types a quote or presses Enter, a
hand-built body stops being JSON. Here the serialiser writes it.

A **string** body is still sent exactly as written, so form-encoded and XML
bodies are untouched.

### Timeouts, in seconds

`timeout=` is on every verb. It replaces a hard-coded 10 seconds that nothing
slow could survive — a model, a report, a cold start. Default 60, ceiling 600.

### A URL written the way you would write it

```python
API_MODEL = "gemini-2.5-flash"
API_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
           + API_MODEL + ":generateContent")
```

That used to produce nothing at all, and the Android build then failed with
`cannot find symbol` somewhere else entirely. It is folded into one literal at
build time now, and a join the compiler cannot resolve is reported as `U2027`
with the line.

### An answer is not a paragraph

A `markdown` template slot renders headings, emphasis, links, lists, quotes
and fenced code blocks. `item_height="auto"` lets each row wrap its own
content — one fixed height gives `"yes"` the same space as a twenty-line
answer.

`code-copy: button` in the stylesheet puts a tappable **Copy** under every
fenced block that copies *that block* and nothing else.

### Making it a conversation

```python
thread.merge_items([{"id": reply_id, "author": "Ora", "message": ""}])
thread.scroll_to_end()
```

`scroll_to_end()`, `scroll_to_top()` and `scroll_to_item(id)` move the
viewport, animated over the duration the theme's `motion` preset gives the
`nav` moment. An `avatar` slot draws a circle of initials in a colour the name
picks — the same colour on both runtimes, because one palette decides it.

`rows: 1; max-rows: 6` gives a composer that starts at one line and grows with
what you write.

---

## Part 2 — Shape

### A drawer

```python
menu = drawer(
    [chat, history, you],
    labels=["New chat", "History", "You"],
    icons=["message", "list", "person"],
    header="Ora",
)

app_bar("New chat", icon="menu", command=lambda: menu.open(), screen=chat)
```

Declared once for the whole app, the way `bottom_nav` is. Back closes the
panel before it leaves the screen — which `DrawerLayout` does not do on its
own.

### A settings row

```python
key_row = list_row("API key", subtitle="Paste your own; it stays on the phone",
                   icon="bolt", trailing="Not set",
                   trailing_icon="chevron_right", id="key_row", screen=you)

key_row.set_trailing("Set")
```

The one shape a button could never be: label at the leading edge, a second
line, and room on the right for a value or a chevron. `set_value()`,
`set_trailing()` and `set_subtitle()` reach the three slots.

```css
settings {
    divider-color: var(--border);
    divider-inset: 56px;
}
```

Hairlines between rows, never at the edges, starting past the icon column.

### Your own typeface

```python
font("Ora Serif",
     regular="fonts/Tiempos-Regular.ttf",
     bold="fonts/Tiempos-Bold.ttf")
```

Four slots, because four is what both runtimes can address. A fifth would
render on the phone and not on the desktop, so it is reported rather than
half-done. Plus `letter-spacing`, `line-height` and `text-align` on labels,
buttons and app bar titles.

---

## Part 3 — Appearance, at run time

```python
from apkpy_lib import appearance

appearance.set("light")     # "dark", "light" or "system"
appearance.get()            # what is in force
```

The choice is remembered, so the app opens the way it was left.

### Why it could not be done before

Colours were written into the layouts as literals — **472 of them across 115
files** in a two-screen app. Nothing at run time rewrites a compiled layout.

A colour that came from a theme token is a resource reference now, answered by
`values/` by day and `values-night/` by night, and switching is
`AppCompatDelegate` choosing between the two tables. It costs nothing while the
app runs: the resource system does the work as the layout inflates.

**A colour written by hand is left exactly as written.** Provenance travels
with the value, so the rule is not "does this hex match a token" — two colours
that happen to match are not the same colour.

### The second palette

You declare one mode; the other is built from the same `Theme`. The accent
carries over and the surfaces flip, because a background chosen at `#1B1B19`
was chosen *because* the mode was dark, and carrying it into light would give a
light mode that is still dark.

### Three things only a phone showed

1. **A screen waiting in the back stack came back in the old colours.**
   AppCompat recreates started activities; a stopped one is not. Each Activity
   records what it was built with and checks in `onResume`.
2. **The clock and the battery went invisible.** They are drawn by the system
   over whatever the app puts behind them; deciding light-on-dark at build time
   left them white on white. `values-night/themes.xml` answers it now.
3. **The declared mode is pinned at startup.** Without that, adding
   `values-night/` would have made every existing app follow the phone.

### Also

`dark_mode`, `light_mode` and `contrast` joined the icon catalogue — an
appearance screen needs a moon, a sun and a half-filled circle, and there were
none. **65 names, 96 with aliases.**

---

## Two fixes worth naming

**A theme token only worked half the time.** `var(--primary)` resolved to
`#6750A4` in an app that declared a `Theme` and to the literal text
`var(--primary)` in an app that did not, which failed the Android build with
an AAPT error about something else. The generated `apkpy_theme.xml` writes
that same colour either way, so the token was never wrong -- only unresolved.
It reads the same tokens now, theme or no theme.

**A token that does not exist is `U2028`.** `var(--muted)` used to resolve to
itself and travel into the layout XML. It is now reported by name, with the
closest match and the full list, in the one module both runtimes read.

---

## The soft keyboard, measured

ApkPy does not declare `windowSoftInputMode`. Whether it should was settled on
a Pixel 9 Pro rather than by reading the manifest: across all three shapes a
generated screen takes, Android's default resolved to a window resize and the
field stayed above the keyboard. The attribute was not added.

A `virtual_collection` does not follow the keyboard, so call `scroll_to_end()`
when the field takes focus if the screen is a conversation.

---

## What an app that uses none of this gets

The same bytes it got from 1.3.2. Every feature is gated on the app asking for
it, and there are tests holding that line: no `markdown` slot means the
Markdown renderer is never written into the project; no `scroll_to_*` means no
scroll helper; no `font()` means no `res/font`.

---

## Verification

- 256 transpiler-harness checks
- 380 feature tests
- 21 core tests
- all 25 examples transpile with balanced braces in every generated Java file
- exercised end to end on a Pixel 9 Pro emulator: a real API call with a
  user-supplied key, a Markdown answer, a code block copied to the clipboard
  and pasted back, and the composer growing and shrinking with its text

---

## Known limits

- Markdown is a subset: no tables, no images inside a row, and a fenced block
  is monospace on a tinted background rather than a widget with a language
  header.
- `scroll_to_end()` moves once and does not follow text that keeps arriving.
- **Every row in a collection has the same shape.** The adapter has one view
  type, so a row cannot change its alignment, surface or width based on its
  data. A chat where your turn is an inset bubble and the reply is full-width
  text is not expressible yet.
- `https` still delivers the whole answer at once — no server-sent-events
  reader. `label.stream()` types text that has already arrived.
- Nothing keeps the conversation for you; sending the history back is your
  `data=` dict to build.

## Two behaviours that changed without an opt-in

Both because they were defects:

1. The Previewer now **verifies TLS certificates**. A request to a host with a
   self-signed certificate that silently succeeded before will now fail.
2. `Theme(primary=...)` derives `on_primary` from the primary's luminance, so
   a filled button stops carrying an unreadable label.

Full detail, with the generated Java: [Version 1.4.0](docs/version-1.4.0.md).
