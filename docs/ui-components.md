# Components and layouts

## Text, buttons and inputs

~~~ python
title = label("Library", variant="headline", screen=home)

search = inputs(
    "Search tracks",
    type="search",
    on_change=lambda query: filter_tracks(query),
    screen=home,
)

button(
    "Continue",
    variant="filled",
    icon="arrow_forward",
    command=open_library,
    screen=home,
)
~~~

Button variants are <code>filled</code>, <code>outlined</code>, <code>tonal</code>, <code>text</code>, <code>danger</code> and <code>icon</code>.

Input types include <code>text</code>, <code>password</code>, <code>search</code>, <code>number</code>, <code>textarea</code>, <code>select</code>, <code>switch</code>, <code>checkbox</code>, <code>range</code>, <code>radio</code>, <code>date</code> and <code>time</code>.

## Containers and composition

~~~ python
panel = container(id="panel", screen=home)
label("Account", variant="title", parent=panel)
inputs("Email", type="text", parent=panel)
button("Save", variant="filled", parent=panel)
~~~

Style the parent to control its children:

~~~ css
panel {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 18px;
    background-color: var(--surface);
    border-radius: var(--radius);
}
~~~

## Cards

Use a ready-made semantic card:

~~~ python
from apkpy_lib import card, card_action

premium = card(
    title="Premium",
    subtitle="Offline listening and high-quality audio",
    image="headphones.jpg",
    content="Available across your signed-in devices.",
    actions=[
        card_action("Learn more", variant="text", command=show_details),
        card_action("Try it", variant="filled", command=start_trial),
    ],
    variant="elevated",
    screen=home,
)
~~~

Or compose any supported child manually:

~~~ python
custom = card(id="custom_card", variant="outlined", screen=home)
label("Custom content", variant="title", parent=custom)
button("Open", variant="text", parent=custom)
~~~

## Lists

Plain and rich rows use the same <code>list_view</code>:

~~~ python
tracks = list_view(
    [
        {
            "title": "Midnight Drive",
            "subtitle": "Nova",
            "image": "cover.jpg",
            "src": "track.mp3",
        }
    ],
    rich=True,
    on_click=lambda item: audio.play_background(
        item["src"],
        title=item["title"],
        artist=item["subtitle"],
        art=item["image"],
    ),
    screen=home,
)
~~~

Update it later:

~~~ python
tracks.set_items(new_items)
~~~

Database and HTTP JSON can be mapped directly:

~~~ python
rows = db.query("SELECT title, artist FROM tracks ORDER BY title")
tracks.set_items(rows, title="title", subtitle="artist")
~~~

## Settings rows

A `list_view` shows rows it owns and fills from data. When the rows *are* the
screen -- a settings list, an account page, a menu -- write them out with
`list_row`:

~~~ python
prefs = container(id="prefs", screen=you)

list_row("Default model", subtitle="Answers when you do not pick one",
         icon="settings", trailing="Opus 5", trailing_icon="chevron_right",
         id="pref_model", parent=prefs,
         command=lambda: model_sheet.open())
list_row("Appearance", icon="image", trailing="Dark",
         trailing_icon="chevron_right", parent=prefs,
         command=lambda: theme_sheet.open())
list_row("Notifications", icon="bell", trailing="Off",
         trailing_icon="chevron_right", parent=prefs,
         command=lambda: toast("Nothing to notify you about yet"))
~~~

Everything except the label is optional. The label sits at the leading edge
with the icon beside it, the subtitle goes underneath, and `trailing` /
`trailing_icon` are pinned to the right. The text block takes whatever the
icon and the trailing pieces leave, so a long label is cut with an ellipsis
rather than pushing the chevron off the screen.

A row is tapped like a button. `command=` runs a function, and
`screen.on_click_navigate(button=the_row, to=other_screen)` opens a screen --
which is what a settings row usually wants.

Three texts, three setters: `set_value()` changes the label,
`set_trailing()` the value on the right and `set_subtitle()` the second line.
A slot only exists if the row declared it, so pass `trailing=""` or
`subtitle=""` for one you intend to fill later.

~~~ python
pref_model = list_row("Default model", subtitle="", trailing="Opus 5",
                      trailing_icon="chevron_right", id="pref_model",
                      parent=prefs)

def refresh():
    pref_model.set_trailing(storage.get("model", "Opus 5"))

lifecycle(settings, on_resume=refresh)
you.on_click_navigate(button=pref_model, to=model_screen)
~~~

Reading the value back in `on_resume` is what makes the row show the choice
after you come back from the screen that changed it.

### Grouping rows with hairlines

Give the container that holds them a `divider-color` and the rows are
separated by a hairline, drawn between them and never at the edges. Let the
group own the surface and the corner radius, and the rows carry no box of
their own:

~~~ css
prefs {
    background-color: var(--surface);
    border-radius: 16px;
    padding: 0px;
    divider-color: var(--border);
    divider-inset: 58px;   /* start the line past the icon column */
}
list_row {
    background-color: #00000000;
    border-radius: 0px;
    padding: 0px 18px;
    min-height: 60px;
    subtitle-color: var(--text-secondary);
    trailing-color: var(--text-secondary);
    icon-color: var(--text-secondary);
}
~~~

Rows stacked in a container sit flush against each other, so the hairline
lands on the seam. `divider-width` sets the thickness and defaults to 1px.
Dividers work on any container, not only ones holding rows.

### An empty state in the middle

`flex-grow: 1` on a column child gives it whatever its siblings leave. Put the
greeting in one and the composer after it, and you get the screen every
assistant app opens on -- the welcome in the middle, the input at the bottom:

~~~ python
hero = container(id="hero", screen=chat)
label("Ora", id="mark", parent=hero)
label("Back in action", id="greeting", parent=hero)

composer = container(id="composer", screen=chat)
inputs(placeholder="How can I help you today?", id="field",
       type="textarea", parent=composer)
~~~

~~~ css
hero {
    flex-grow: 1;              /* take what the composer leaves */
    justify-content: center;   /* along the column */
    align-items: center;       /* across it */
    background-color: #00000000;
}
~~~

`justify-content` and `align-items` are the two CSS words for the two halves
`android:gravity` already had. `center`, `flex-start` and `flex-end` on either
axis. A column that names neither still centres horizontally, which it always
did, so nothing already written moves.

### Text that arrives

An answer appearing all at once is the one thing that never happens when you
talk to an assistant. `stream()` types it in:

~~~ python
lead.stream("Thinking about that...", speed="fast")
~~~

And for a chat, add the row empty and stream into one of its fields:

~~~ python
thread.merge_items([{"id": reply_id, "author": "Ora", "message": ""}])
thread.stream_item(reply_id, "message", answer)
~~~

`speed` is `slow`, `normal` or `fast`. `instant` puts the whole thing there at
once, and so does a theme with `motion="none"` whatever the call said --
somebody who turned animations off did not ask to watch text type itself.

The rate lives in one table both runtimes read, so the phone and the desktop
type at the same speed. Text arrives a few characters per tick rather than one
character every few milliseconds, because a Handler and a Tk `after` both stop
being accurate below about 10ms and a rate the runtime cannot keep is a rate
that differs between them.

### A thread that reads as a conversation

A collection row is a card by default, which is right for a feed and wrong for
a chat. Take the surface away and the turn becomes text on the page:

~~~ css
/* No height: the thread takes what is left, which is what pins a composer
   under it to the bottom of the screen instead of leaving it mid-air. */
thread {
    item-background-color: #00000000;
    item-border-color: #00000000;
    title-color: var(--text-secondary);   /* who is speaking, quietly */
    subtitle-color: var(--text);          /* what they said, loudly */
    subtitle-lines: 12;
}
~~~

Leave `height` off and the collection takes the space its siblings do not, so
anything after it sits at the bottom of the screen. Give it a height and it
stops there, which is what you want inside a scrolling page.

Drop `meta` and `badge` from the `template=` as well -- a timestamp on the
right and a pill under the text are what make a chat read as a notification
feed.

## Rich text, Markdown and trees

Use `rich_text()` for exact inline spans, `markdown()` for structured documents
and `tree_view()` for recursive expandable data. Android generates native
selectable text and a recycled hierarchy rather than a WebView.

~~~ python
rich_text(
    [
        {"text": "Status: ", "bold": True},
        {"text": "ready", "bold": True, "color": "#22C55E"},
    ],
    screen=home,
)

markdown("## Notes\n\n- [x] Native text", screen=home)

tree_view(
    [{
        "title": "Workspace",
        "children": [{"title": "Release notes"}],
    }],
    screen=home,
)
~~~

[See the complete native rich-content guide](rich-content.md).

## Carousels and grids

~~~ python
carousel(albums, on_click=open_album, screen=home)
grid(categories, cols=2, on_click=open_category, screen=home)
~~~

Rich items can contain <code>title</code>, <code>subtitle</code>, <code>image</code> and application-specific fields such as <code>src</code>.

## Responsive layouts

Describe how the same component tree rearranges:

~~~ python
profile_panel = container(id="profile_panel")
details_panel = container(id="details_panel")

responsive(
    mobile=column(profile_panel, details_panel),
    tablet=row(profile_panel, details_panel),
    breakpoint=600,
    screen=home,
)
~~~

The Android build chooses the appropriate layout for the available width. In the Previewer:

~~~ python
device("responsive")
~~~

Resize the window to test the breakpoint.

## CSS flex and grid

ApkPy supports the layout properties needed for application interfaces, including:

- <code>display</code>, <code>flex-direction</code>, <code>flex-wrap</code> and <code>gap</code>;
- <code>justify-content</code>, <code>align-items</code> and <code>align-self</code>;
- <code>flex-grow</code>, <code>flex-shrink</code> and <code>flex-basis</code>;
- grid columns/rows, spans and gaps;
- width, height, min/max sizes, margins and padding;
- relative/absolute positioning, offsets and z-index.

Use responsive composition for major structural changes and CSS for sizing/alignment inside a structure.

## Accessibility

Accessibility fails quietly. An image with no description is announced as
nothing at all; text at 3:1 against its background is unreadable for a good
share of people and looks fine to whoever chose the colours. Neither shows up
in a build, a test or a screenshot — so ApkPy says it during the build.

### Describing what has no words

~~~python
image("shelf.png", id="shelf", screen=home, describe="Aisle 4, third shelf")
image("divider.png", id="rule", screen=home, describe="")      # decoration
button("", id="settings", screen=home, icon="settings", describe="Settings")
~~~

`describe=` becomes `android:contentDescription`. **An empty description is a
decision, not an omission**: it marks the element as decorative and TalkBack
skips it, instead of announcing a file name. A button with words already
announces those words and needs nothing.

### What the build tells you

A `U2035` report lists what it found and lets the build finish — every app in
existence has an image somebody forgot to describe, and refusing to build over
it would only teach people to switch the check off.

~~~
home.photo (image): nothing to announce. Add describe="...", or describe=""
                    if it is decoration.
home.save (button): text is 3.90:1 against its background; 16sp needs 4.5:1.
home.tiny (button): height is 32dp, under the 48dp a fingertip needs.
~~~

The numbers are WCAG's and Material's, not opinions:

| | Minimum |
| --- | --- |
| Body text | 4.5:1 |
| Large text — 18pt (24sp), or 14pt bold (18.7sp) | 3:1 |
| Anything you tap | 48dp |

!!! note "Large text is measured in points, not in sp"

    WCAG says 18pt, or 14pt bold; Android sizes text in sp, and 1pt is 1.333sp
    at the default density. So the thresholds are **24sp and 18.7sp** — writing
    them as 18 and 14 would let 18sp body text pass at 3:1 when it needs 4.5:1.

Text is already emitted in `sp`, so it grows when someone has enlarged the
system font — nothing to do there.
