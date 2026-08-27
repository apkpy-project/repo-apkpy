---
title: Version 1.4.0
description: ApkPy 1.4.0 talks to an API with typed JSON, renders the answer as Markdown in a row that fits it, and gives an app a drawer, settings rows and a typeface of its own.
---

# ApkPy 1.4.0 — Talking to a model, and an app that looks like yours

Version 1.4.0 is two batches that turned out to be one.

The first is **an app that can hold a conversation with an API**: a request
body that keeps its types, a timeout long enough for something that thinks
first, an answer rendered as Markdown, and a row that takes the height that
answer needs.

The second is **an app that stops looking like every other app built with the
same tool**: a navigation drawer, a settings row, a typeface of your own, and
control over tracking, leading and alignment.

They are one release because they are the same problem seen twice. An
assistant app is not a hard app to *build* — it is a hard app to make **look
right**, and every shape it needs was missing.

Everything here is opt-in. An app that mentions none of it generates
byte-identical XML to the one 1.3.2 generated.

---

## What changed

**Talking to an API**

- a `dict` as `data=` is serialised as JSON with the types of the literal intact;
- `Content-Type: application/json; charset=utf-8` set only when the body is JSON;
- `timeout=` on every verb, in seconds, default 60, capped at 600;
- a module constant joined from pieces (`URL = BASE + MODEL + ":generate"`) is
  folded into one literal;
- UTF-8 on the way out and on the way back, and line breaks in a response survive.

**Showing an answer**

- `virtual_collection(item_height="auto")` — each row wraps its own content;
- a `markdown` slot in a row's `template`;
- CSS `code-copy: button` — a tappable **Copy** under every fenced block;
- `label.stream()` and `collection.stream_item()` — text arriving a few
  characters at a time.

**Making it a conversation**

- `scroll_to_end()`, `scroll_to_top()`, `scroll_to_item(id)`;
- an `avatar` slot — a circle of initials in a colour the name picks;
- CSS `max-rows` — a composer that grows with what you write.

**Shape**

- `drawer()` — the navigation panel that slides in from the leading edge;
- `list_row()` — the settings row, and `set_trailing()` / `set_subtitle()`;
- `divider-color` / `divider-width` / `divider-inset` on any container;
- `text-align` on labels, buttons and app bar titles;
- `letter-spacing` and `line-height`;
- `font()` — your own `.ttf` or `.otf`, four slots;
- `flex-grow`, `justify-content` and `align-items` inside a stacked column;
- `chevron_right` / `chevron_left` — **65 icon names, 96 with aliases**.

**Appearance**

- `appearance.set("dark" | "light" | "system")` and `appearance.get()` — the
  app changes its colours while it runs, and opens the way it was left;
- a colour that came from a theme token is written as a **resource reference**,
  answered by `values/` by day and `values-night/` by night;
- `Theme.counterpart()` — the same theme in the other mode;
- `dark_mode`, `light_mode` and `contrast` in the icon catalogue.

---

## A dict is a JSON body

This is the change with the widest blast radius, because until 1.4.0 every
value in a generated app was a string.

```python
https.post(
    "https://api.anthropic.com/v1/messages",
    data={
        "model": "claude-sonnet-5",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": text}],
    },
    headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
    timeout=120,
    on_response=answered,
)
```

`max_tokens` arrives at the far end as the number `1024`, not as `"1024"` —
which is the difference between an API accepting the request and rejecting it
with a validation error. Nested objects and arrays nest.

It matters just as much that **you are not building the body by
concatenation**. The first time a user types a quote or presses Enter, a
hand-built body stops being JSON. Here the serialiser writes it, so the
escaping is not your problem.

### What it compiles to

The dict becomes a typed construction, not a string:

```java
executeHttpsRequest("POST", String.valueOf(API_URL),
    String.valueOf(_apkpyJsonObj(
        "contents", _apkpyJsonArr(_apkpyJsonObj(
            "parts", _apkpyJsonArr(_apkpyJsonObj("text", String.valueOf(text))))),
        "generationConfig", _apkpyJsonObj("maxOutputTokens", 1024)
    ).toString()),
    _headers_61760, 120000, new HttpsCallback() { ... });
```

`1024` is an `int` all the way down to `org.json`. `text` is whatever the user
typed, escaped by `JSONObject`.

A **string** body is still sent exactly as written, so form-encoded and XML
bodies are untouched, and the JSON `Content-Type` is only set when the body
starts with `{` or `[` and you did not choose a header yourself.

### Timeouts

`timeout=` is in seconds on every verb — `get`, `post`, `put`, `patch`,
`delete`. It replaces a hard-coded 10 seconds that nothing slow could survive:
a model, a report, a cold start. The default is 60 and the ceiling is 600.

### A URL written the way you would write it

```python
API_MODEL = "gemini-2.5-flash"
API_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
           + API_MODEL + ":generateContent")
```

That used to produce nothing at all: the constant never reached the generated
Java, the name was used anyway, and the Android build failed somewhere else
entirely with `cannot find symbol`. It is now folded into one literal at build
time. A join the compiler cannot resolve — because a name is declared further
down the file — is reported as **`U2027`** with the line, instead of surfacing
as a Java error nobody can trace back.

---

## An answer is not a paragraph

A model answers with headings, lists and fenced code. Read as plain text with
backticks in it, that is not an answer — it is a dump.

```python
thread = virtual_collection(
    turns,
    template={"title": "{author}", "markdown": "{message}"},
    item_height="auto",
    screen=chat,
)
```

Two things are happening.

**`markdown` is a template slot.** It renders headings, emphasis, links,
lists, quotes and fenced code blocks. It is the *same renderer* the
`markdown()` component uses — extracted, not copied — so a fenced block looks
the same in a row as it does on a page. Two copies would have become two ways
of drawing a code block, and this project's most expensive bug class is
exactly that kind of drift.

**`item_height="auto"` lets each row wrap its own content.** One fixed height
gives `"yes"` the same space as a twenty-line answer: one floats in a void,
the other is cut off mid-sentence. A number still fixes every row, which is
what a grid of cards wants.

With `"auto"`, text also stops being clipped to a single line unless
`title-lines` / `subtitle-lines` say otherwise — a row that can grow, with its
text truncated to one line, was the worst of both worlds.

On Android the row's `LayoutParams` become `WRAP_CONTENT` with a 40dp floor,
and the list stops claiming `setHasFixedSize(true)` — which was precisely the
promise that had stopped being true.

In the Previewer this needed real work: virtualisation had assumed a fixed
height in order to know which row is at the top. It now measures each row
after drawing it, keeps a running table of offsets, and finds the first
visible row by binary search.

### Copying a code block

```css
thread { code-copy: button; }
```

Every fenced block gets a tappable **Copy** under it that puts **that block**
on the clipboard — not the paragraph above it, not the whole message. A block
of code you cannot copy is a block of code you retype by hand.

It works the same in a `markdown()` component. On Android 13 and later the
system shows its own confirmation for every copy, so the app stays quiet
rather than talking over it; below that it says "Copied" itself.

### Text that arrives

```python
answer.stream_item(reply_id, "message", text)      # into one row
status.stream("Working on it...", speed="fast")    # into a label
```

The rate lives in one table both runtimes read, so the phone and the desktop
type at the same speed. `speed="instant"` — and a theme with `motion="none"` —
put the whole thing there at once.

Be clear about what this is: it types text that has **already arrived**. There
is no server-sent-events reader yet, so an API that streams token by token is
still read to the end before the callback fires.

---

## Making it a conversation

### Looking at the message that just arrived

Adding a row does not move the viewport. In a feed that is right. In a
conversation it means sending a question and then looking at your own
question while the answer grows below the fold.

```python
def send():
    text = field.get_value()
    thread.merge_items([{"id": text, "author": "You", "message": text}])
    thread.merge_items([{"id": "reply", "author": "Ora", "message": ""}])
    field.set_value("")
    thread.scroll_to_end()
```

| Method | Contract |
| --- | --- |
| `scroll_to_end()` | bring the newest row into view |
| `scroll_to_top()` | bring the first row into view |
| `scroll_to_item(id, key="id")` | bring one keyed row into view |

The scroll is animated over the duration the theme's `motion` preset gives the
`nav` moment — the same table the rest of ApkPy's motion reads — so
`motion="none"` makes it a jump on the desktop and on the phone alike. On
Android that meant a `LinearSmoothScroller` with the time pinned, rather than
`smoothScrollToPosition`, so the duration is something the release can
actually state:

```java
private void _apkpyScrollTo(RecyclerView view, int position, final int ms) {
    if (view == null || position < 0) return;
    RecyclerView.LayoutManager manager = view.getLayoutManager();
    if (manager == null || ms <= 0) { view.scrollToPosition(position); return; }
    LinearSmoothScroller scroller = new LinearSmoothScroller(view.getContext()) {
        @Override protected int calculateTimeForScrolling(int dx) { return ms; }
        @Override protected int getVerticalSnapPreference() { return SNAP_TO_START; }
    };
    scroller.setTargetPosition(position);
    manager.startSmoothScroll(scroller);
}
```

### A mark for who is speaking

```python
template={"avatar": "{author}", "title": "{author}", "markdown": "{message}"}
```

The `avatar` slot draws a circle with up to two initials from its value, over
a colour that value picks. An empty value hides the circle rather than leaving
a coloured hole.

The same name lands on the same colour in the Previewer and on the phone,
because **one palette decides it**. The Previewer reads the table directly;
the compiler writes it into the generated Java as a literal, and only the
index is computed at run time:

```java
private final int[] avatarBg = { 0xFF7C6BF2, 0xFF2E8B7A, 0xFFC2643D, 0xFF3B72C4,
                                 0xFFA2547E, 0xFF4F7A2B, 0xFFB08114, 0xFF5C6B8A };

private int avatarSlot(String value) {
    int sum = 0;
    for (int i = 0; i < value.length(); i++) sum += value.charAt(i);
    return Math.abs(sum) % avatarBg.length;
}
```

Two hand-maintained lists would have drifted the first time somebody edited
one. Summing UTF-16 code units on both sides — rather than Python code points
— is what keeps a name with an emoji in it on the same colour too.

It is a mark for a name, not a picture: for a photo or a remote image, use the
`image` slot.

### A composer that grows

```css
field {
    rows: 1;
    max-rows: 6;
}
```

`rows` is where the field starts, `max-rows` is where it stops growing, and
between the two it follows the text. One line is the right start for a reply
box — two fixed lines are half an empty composer waiting — and past six a
draft starts eating the thread. Beyond the ceiling the field scrolls.

Without `max-rows` the ceiling is what it always was: twice `rows`, never less
than eight.

This one is also a **fix**. Android already grew a `type="textarea"` between
`minLines` and `maxLines`; the Previewer never grew at all. The same composer
was one line on the desktop and three on the phone.

---

## Shape

### A drawer

The last navigation shape that was outright impossible rather than merely
unstyled.

```python
menu = drawer(
    [chat, history, you],
    labels=["New chat", "History", "You"],
    icons=["message", "list", "person"],
    header="Ora",
    subtitle="Signed in",
)

app_bar("New chat", icon="menu", command=lambda: menu.open(), screen=chat)
```

Declared once for the whole app the way `bottom_nav` is. Each item starts the
screen it names, the open screen stays checked, and Back closes the panel
before it leaves the screen — which `DrawerLayout` does not do on its own.

The compiler looks for the drawer *before* it reads any function body, because
a drawer needs every screen to exist and the app bars that open it are written
above it. Parsing strictly top to bottom would have met `menu.open()` before
`menu` was anything and dropped it in silence.

### A settings row

The one shape a button could never be.

```python
key_row = list_row(
    "API key",
    subtitle="Paste your own; it stays on the phone",
    icon="bolt",
    trailing="Not set",
    trailing_icon="chevron_right",
    id="key_row",
    screen=you,
)

key_row.set_trailing("Set")
```

Its label starts at the leading edge with the icon beside it, it carries a
second line, and it keeps room on the right for a value, a plan or a chevron.
The text block takes what the icon and trailing pieces leave, so a long label
is cut with an ellipsis instead of pushing the chevron off the screen. Tapped
like a button — same `command=`, same navigation.

`set_value()`, `set_trailing()` and `set_subtitle()` reach the three slots. A
slot has to have been declared: pass `trailing=""` for one you intend to fill
later.

### Grouping rows

```css
settings {
    divider-color: var(--border);
    divider-width: 1px;
    divider-inset: 56px;
}
```

Hairlines are drawn **between** rows and never at the edges
(`android:showDividers="middle"`), and `divider-inset` starts the line past
the icon column. It works on any container, not only ones holding rows.

Rows stacked in a container now sit flush against each other: the 6dp baseline
gap between stacked children would have lifted every hairline off the seam it
belongs on — visible only once the APK was on a phone.

### Alignment

```css
row_button { text-align: left; }
title      { text-align: center; }
```

A button centred its label and nothing could move it, so three stacked rows
read as three fat pills instead of a settings list. Written to Android as
`start` / `center` / `end`, so a right-to-left locale mirrors for free, and an
aligned button pins its icon to the leading edge rather than grouping it with
the label.

`text-align: center` on an app bar centres its title through
`app:titleCentered`. `justify` is reported as **`U2022`** rather than
half-done: it needs `android:justificationMode`, which arrived at API 26 while
the generated app targets 24.

---

## Type

### Your own typeface

```python
font("Ora Serif",
     regular="fonts/Tiempos-Regular.ttf",
     bold="fonts/Tiempos-Bold.ttf")
```

```css
title { font-family: "Ora Serif"; }
```

The Android build copies the files into `res/font`, writes the
`<font-family>` that maps weights onto them, and reaches them through
`app:fontFamily` — the AppCompat attribute, because the framework one only
learned to take a font resource at API 26. The Previewer loads the same files
into the session without installing anything.

Four slots and no more — `regular`, `bold`, `italic`, `bold_italic` — because
four is what both sides can address. Tk has a family plus bold and italic;
Android expresses the same four as `fontWeight`/`fontStyle` pairs. A `medium`
would render on the phone and not on the desktop, so it is reported as
**`U2024`** instead of shipping half-done.

A missing file or a web font format is reported at build time (**`U2025`**,
**`U2026`**) and that slot is dropped. The family still ships with whatever
survived, and a family left with nothing is never named by a layout —
referencing a resource that was never written is an AAPT link failure, which
is a much worse way to find out.

### Tracking and leading

```css
title { letter-spacing: -0.4px; }
copy  { line-height: 1.55; }
```

Both accept `px` or `em`, and `line-height` also takes a bare multiple, the
way CSS reads it. They resolve through one shared module, so the em Android
receives and the pixels the Previewer measures come from the same arithmetic.

`letter-spacing: 0px` is written out even though it is zero: a
`MaterialButton` tracks its own label at about `0.089em`, and silence would
have left the phone spaced out while the Previewer sat tight.

---

## Layout: the empty state every assistant app opens on

```css
chat {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
}
greeting { flex-grow: 1; }
```

`flex-grow: 1` on a stacked column child takes whatever its siblings leave,
and `justify-content` / `align-items` place children along and across the
column. Together they are the greeting in the middle with the composer pinned
under it.

A column that names neither still centres horizontally, which it always did.

---

## A token that only worked half the time

`var(--primary)` resolved to `#6750A4` in an app that declared a `Theme`, and
to the literal text `var(--primary)` in an app that did not. The second one
failed the Android build -- forty seconds in, with an AAPT link error whose
stated cause is that the project folder holds files from an earlier
generation. It does not.

The token was never wrong. The generated `apkpy_theme.xml` writes that same
`#6750A4` either way:

```xml
<color name="apkpy_primary">#6750A4</color>
```

So whether a stylesheet worked came down to a keyword the stylesheet has
nothing to do with. It reads the same tokens now, theme or no theme:

```python
from apkpy_lib import Screen, button, label, run

home = Screen(id="home")
label("Welcome", id="title", screen=home)
button("Continue", id="go", variant="filled", screen=home)
run(start_screen=home)          # no theme named

style = """
title { color: var(--primary); }
"""
```

Declaring a theme changes what a token resolves to, never whether it resolves.
Nothing else moved: the theme's default stylesheet is still not merged into an
app that never asked for one, so the rest of its XML is unchanged.

### And a name with nothing behind it

`var(--muted)` is not a token. It used to resolve to itself and travel into
the layout the same way. It is now **`U2028`**, raised where both runtimes
resolve tokens -- so the Previewer catches it in a second, and `apkpy build`
catches it before Gradle starts:

```text
APKPY U2028 - This stylesheet asks for a theme token that does not exist

Received:
  title { color: var(--muted); }

How to fix:
  1. Did you mean var(--text_secondary)?
  2. The tokens are: background, border, error, font-family, motion,
     nav_indicator, on_primary, primary, radius, secondary, spacing,
     success, surface, text, text_secondary.
```

---

## Appearance, at run time

```python
from apkpy_lib import appearance

appearance.set("light")     # "dark", "light" or "system"
appearance.get()            # what is in force
```

The choice is remembered, so the app opens the way it was left. Three rows are
the whole screen:

```python
group = container(id="modes", screen=you)

list_row("Dark", icon="dark_mode",
         command=lambda: choose("dark"), parent=group)
list_row("Light", icon="light_mode",
         command=lambda: choose("light"), parent=group)
list_row("Follow the system", icon="contrast",
         command=lambda: choose("system"), parent=group)


def choose(mode):
    appearance.set(mode)
    for name, row in rows.items():
        row.set_trailing("Selected" if name == mode else "")
```

### What made this impossible before

Colours were written into the layouts as literals — **472 of them across 115
files** in a two-screen app — and nothing at run time rewrites a compiled
layout.

A colour that came from a theme token is no longer written into the layout.
A reference to it is:

```xml
<!-- res/layout/activity_screen_you.xml -->
<TextView android:textColor="@color/apkpy_text" ... />
```

```xml
<!-- res/values/apkpy_theme.xml -->
<color name="apkpy_primary">#C96442</color>
<color name="apkpy_background">#FFFBFE</color>
<color name="apkpy_text">#1D1B20</color>

<!-- res/values-night/apkpy_theme.xml -->
<color name="apkpy_primary">#C96442</color>
<color name="apkpy_background">#1B1B19</color>
<color name="apkpy_text">#E6E1E5</color>
```

Android answers that reference from one table or the other. Switching costs
nothing at run time: the resource system does the work while the layout
inflates. The same app now carries **98 literal colours**, and the ones left
are the ones that should be left — mixed shades, transparents, and the colours
you wrote by hand.

### The rule that decides every colour

**A token becomes a reference. A colour written by hand stays exactly as
written.** `#C96442` in a stylesheet was a decision, not a default, and a
decision that changes on its own is a bug.

Comparing hex would not do it — two colours that happen to match are not the
same colour. Provenance travels with the value instead, so nothing downstream
had to learn a new type.

### Where the second palette comes from

You declare one appearance; ApkPy builds the other from the same `Theme`:

| Token | In the counterpart |
| --- | --- |
| `primary`, `secondary`, `on_primary`, `error`, `success` | kept |
| `background`, `surface`, `text`, `text_secondary`, `border` | from the opposite palette |

A background you chose at `#1B1B19` was chosen *because* the mode was dark.
Carrying it into light mode would give a light mode that is still dark — a
switch that appears to do nothing.

### What it compiles to

```java
private void _apkpyApplyAppearance(String mode) {
    int night;
    if ("light".equals(mode)) {
        night = androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_NO;
    } else if ("dark".equals(mode)) {
        night = androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_YES;
    } else {
        night = androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM;
    }
    if (androidx.appcompat.app.AppCompatDelegate.getDefaultNightMode()
            != night) {
        // AppCompat recreates the started activities itself; calling
        // recreate() here as well would run onCreate twice.
        androidx.appcompat.app.AppCompatDelegate.setDefaultNightMode(night);
    }
}
```

### Three things only a phone showed

**A screen waiting in the back stack came back wearing the old colours.**
AppCompat recreates the activities that are *started*; one that is stopped is
not. Each Activity records the appearance it was built with and checks on the
way back in:

```java
protected void onResume() {
    super.onResume();
    String _apkpyMode = _apkpyStorageGet("__apkpy_appearance", "dark");
    if (!_apkpyMode.equals(_apkpyAppearanceShown)) {
        _apkpyApplyAppearance(_apkpyMode);
        recreate();
        return;
    }
}
```

That check is written only for an app that calls `appearance.set(...)`.

**The clock and the battery went invisible.** They are drawn by the system over
whatever the app puts behind them, and deciding light-on-dark at build time
left them white on white the moment the app switched. The answer comes from the
same qualifier the colours do:

```xml
<!-- res/values/themes.xml -->
<item name="android:windowLightStatusBar">true</item>

<!-- res/values-night/themes.xml -->
<item name="android:windowLightStatusBar">false</item>
```

**The declared mode has to be pinned at startup.** Without that, adding
`values-night/` would make every existing app start following the phone — a
behaviour change nobody asked for:

```java
_apkpyAppearanceShown = _apkpyStorageGet("__apkpy_appearance", "dark");
_apkpyApplyAppearance(_apkpyAppearanceShown);
super.onCreate(savedInstanceState);
```

An app that declares `Theme(mode="dark")` and never calls `appearance.set(...)`
opens dark on a phone set to light, and the other way round, exactly as before.

---

## The soft keyboard: measured, and left alone

ApkPy does not declare `windowSoftInputMode`, and the question of whether it
should was settled by testing rather than by reading the manifest. On a
Pixel 9 Pro (API 36), across the three shapes a generated screen takes:

| Screen | Root the generator writes | Keyboard opens |
| --- | --- | --- |
| No app bar, `scroll=False` | `LinearLayout` | window resizes; content stays visible |
| With an `app_bar()` | `RelativeLayout` over a `NestedScrollView` | window resizes; the bar stays put |
| `Screen(scroll=True)` | `NestedScrollView` | window resizes; the field scrolls into view |

Android's default resolved to a resize in all three, so the attribute was not
added: it would change the manifest of every app to no observable effect.

Two things this does not promise. A `virtual_collection` **does not follow the
keyboard** -- it keeps its scroll position when the window shrinks, so call
`scroll_to_end()` when the field takes focus if the screen is a conversation.
And it was measured on one API level: on API 24-29 a screen with no scrolling
view can resolve to `adjustPan` instead, which slides the whole window up.

---

## What an app that uses none of this gets

The same bytes it got from 1.3.2.

Every feature above is gated on the app actually asking for it, and there are
tests that hold that line:

| If your app never... | ...then the APK never carries |
| --- | --- |
| uses a `markdown` slot | `ApkpyRichContentView.java`, or the row code that calls it |
| uses an `avatar` slot | the palette, the initials helper, the circle drawable |
| calls `scroll_to_*` | `_apkpyScrollTo` or `LinearSmoothScroller` |
| calls `scroll_to_item` | the key lookup (`scroll_to_end` alone does not drag it in) |
| mutates a feed | the merge, diff and rollback helpers |
| declares a `font()` | `res/font`, the family XML or the text appearance |
| declares a `drawer()` | `DrawerLayout`, the navigation view or the back handler |
| sets `code-copy` | the copy affordance |

This needed two levels of gating in more than one place: one for the code
inside a generated class, another for whether the class file is written into
the project at all. Missing the second is a `cannot find symbol` at the end of
a build.

---

## Fixed

- A dict as an `https` body compiled to an **empty string**, silently, and
  `body = {...}` on a line of its own generated no Java at all — the name was
  then used without ever having been declared. The Previewer, which *runs* the
  Python, saw the whole dictionary. That divergence is the one this compiler
  pays the most for.
- A list of objects became a list of strings: `[{"role": "user"}]` was written
  as `["{\"role\":\"user\"}"]`, handing the far end a quoted blob where an
  array belonged.
- A response body was read with `readLine()` into a `StringBuilder`, which
  dropped every line break, and both directions used the platform charset
  instead of UTF-8.
- The Previewer form-encoded a dict body while Android sent nothing at all,
  and **disabled TLS certificate verification for every request**. It now
  sends JSON like the phone does and verifies certificates by default, falling
  back to an unverified context only when the system has no CA store — and
  saying so once, in the console, rather than quietly downgrading a request
  carrying an API key.
- `label.stream()` inside a named function referred to the view by a local
  name that only exists inside `onCreate`: `cannot find symbol` at build time.
- `Theme(primary=...)` left `on_primary` at the Material baseline dark purple,
  so a filled button on any custom primary carried a label nobody could read.
  It is now derived from the primary's luminance unless you set it yourself.
- `storage.get(key, default)` used **inside** an expression — as an argument
  rather than on a line of its own — compiled to an empty string in silence.
- `set_value()` on a `list_row` emitted `setText` on a `LinearLayout`.
- `item-background-color: #00000000` on a collection took the Previewer down
  at startup. Tk has no per-widget alpha, so a collection's colours now
  resolve against whatever sits behind them — which is how a chat turn asks to
  be text on the page rather than a card.
- A collection drew a scrollbar in the Previewer even with one item in it. A
  RecyclerView draws none until you drag it.
- A `type="textarea"` grew on Android and never grew in the Previewer.
- The `avatar` slot reached the generated adapter but not the template map the
  adapter reads, so the circle was computed and never drawn — caught by
  reading the generated Java, which is why that step is part of the process.

---

## Known limits

Stated plainly, because finding them yourself is worse.

- **Markdown is a subset.** No tables and no images inside a row. A fenced
  block is monospace on a tinted background with a Copy under it — not a
  widget with a language header, and long lines wrap rather than scrolling
  sideways.
- **`scroll_to_end()` moves once**, when you call it. It does not follow text
  that keeps arriving, so a long streamed answer still grows past the bottom
  edge after the jump. On Android a very long jump also takes longer than the
  stated duration: the RecyclerView re-aims as it goes, because it cannot know
  a row's height before laying it out.
- **Row heights in the Previewer are measured after a row is drawn**, so a
  long row is estimated once before settling into its real height. The phone
  has no such pass. The shape matches; the first frame may not.
- **`https` still delivers the whole answer at once.** No server-sent-events
  reader yet. `label.stream()` types text that has already arrived; it is not
  the same thing.
- **Every row in a collection has the same shape.** The adapter has one view
  type, so a row cannot change its alignment, surface or width based on its
  data. A chat where your turn is an inset bubble and the reply is full-width
  text is not expressible yet.
- **No conversation memory helper.** Sending the history is your `data=` dict
  to build; nothing in ApkPy keeps it for you.
- **The counterpart palette is Material's, with your accent.** You declare one
  mode and describe its surfaces; the other mode's surfaces come from the
  built-in palette. There is no way to hand-pick both — a cream light mode
  next to your own dark one is not expressible yet.
- **A hand-written colour does not follow the switch**, by design. That is the
  rule working, but it means a stylesheet full of literals switches only its
  themed parts. Reach for `var(--token)` where you want the colour to move.

---

## Verification

| Suite | Count |
| --- | ---: |
| Transpiler harness (`playground/transpile_tests.py`) | 256 |
| Feature tests (`tests/features`) | 380 |
| Core tests (`tests`) | 21 |

Every one of the 25 examples in `examples/` transpiles with balanced braces in
every generated Java file, and the release was exercised end to end on a
Pixel 9 Pro emulator: a request to a real API with a user-supplied key, the
answer rendered as Markdown in a row that fits it, a code block copied to the
clipboard and pasted back to prove the round trip, and the composer growing
and shrinking with its text.

Appearance was exercised on the same device in all three modes, including the
case the emulator is there for: a screen left waiting in the back stack, which
has to come forward wearing the colours chosen while it was away.

---

## Upgrading

```powershell
python -m pip install --upgrade apkpy
```

Nothing in 1.4.0 requires a change to an existing app. Every addition is
opt-in, and an app that mentions none of it generates the same project it
generated on 1.3.2.

Two behaviours changed without an opt-in, both because they were defects:

1. The Previewer now **verifies TLS certificates**. A request to a host with a
   self-signed certificate that silently succeeded before will now fail, which
   is the correct outcome.
2. `Theme(primary=...)` now derives `on_primary` from the primary's luminance.
   If you were relying on the old dark-purple label, set `on_primary`
   explicitly.
