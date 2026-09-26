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

A tapped row reaches `on_click` whole -- every column the query returned,
plus `title` and `subtitle` -- so the callback can read the key it needs:

~~~ python
def remove(item):
    db.execute("DELETE FROM tracks WHERE id = ?", [item["id"]])

tracks = list_view([], on_click=remove, screen=home)
tracks.set_items(db.query("SELECT id, title, artist FROM tracks"),
                 title="title", subtitle="artist")
~~~

Before 1.11.0 the phone handed over only the text shown, and `item["id"]`
was that text: the `DELETE` matched nothing, on the phone only.

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

### Bubbles

A messenger draws the other way: each message a bubble that hugs its text,
yours on the right. Give the rows a kind with `variant=`, and style each kind
with `id:kind`:

~~~ python
thread = virtual_collection(
    messages,
    variant="{kind}",
    template={
        "day":  {"meta": "{text}"},
        "them": {"subtitle": "{text}", "meta": "{time}"},
        "mine": {"subtitle": "{text}", "meta": "{time} ✓✓"},
    },
    id="thread", item_height="auto", screen=chat,
)
~~~

~~~ css
thread { item-background-color: #202C33; item-border-radius: 10px; gap: 6px;
         subtitle-lines: 30; }
thread:them { align-self: flex-start; max-width: 80%; }
thread:mine { align-self: flex-end; max-width: 80%; item-background-color: #005C4B; }
thread:day  { align-self: center; meta-color: #8696A0; }
~~~

`align-self` puts a kind of row at the start, the end or the centre;
`max-width` (pixels or a percentage) is as wide as it may grow, and a short
message is narrower. `item-border-radius` rounds every row and `gap` spaces
them. Each kind can have its own `item-background-color`, `title-color`,
`subtitle-color` and `meta-color`. A collection that sets none of it is drawn
as it always was.

### A list of conversations

Messaging apps all draw a chat list the same way: the time level with the
name, and the unread count under the time, round.
`badge-position: end` does that:

~~~ python
chats = virtual_collection(
    rows,
    template={"avatar": "{name}", "title": "{name}", "subtitle": "{last}",
              "meta": "{time}", "badge": "{unread}"},
    id="chats", item_height="auto", on_click=open_chat, screen=home,
)
~~~

~~~ css
chats { badge-position: end; badge-background-color: #21C063; badge-color: #0B141A; }
~~~

A row with an empty `unread` shows no badge. Without `badge-position`, the badge
follows the subtitle, as before.

### Rows built from components

The slots above draw a chat list or a track list. A feed post -- a header, a
photo, a row of actions, a caption -- a comment or a product card is a small
layout of its own, repeated for every item. Write it once, as a function that
builds one row, and pass it as `row=`:

~~~ python
POSTS = [
    {"user": "mara.vale", "face": "mara.png", "picture": "lisbon.jpg",
     "likes": "1,284", "caption": "Last light over the river"},
    # ... what your server or database returns
]

def like(item):
    toast("You liked " + item["user"] + "'s post")

def post_row(row):
    head = container(id="post_head", parent=row)
    avatar("{face}", size=34, id="post_face", parent=head, describe="{user}")
    label("{user}", id="post_user", parent=head)
    image("{picture}", id="post_pic", parent=row, aspect_ratio="1:1", describe="")
    actions = container(id="post_actions", parent=row)
    button("", icon="favorite_border", describe="Like", parent=actions,
           command=lambda item: like(item))
    button("", icon="send", describe="Share", parent=actions,
           command=lambda: toast("Share"))
    label("{likes} likes", id="post_likes", parent=row)
    label("{caption}", id="post_caption", parent=row)

feed = virtual_collection(POSTS, row=post_row, id="feed", screen=home)
~~~

~~~ css
feed_row { background-color: #FFFFFF; padding: 0px 0px 8px 0px; }
post_head { display: flex; flex-direction: row; align-items: center; gap: 10px; }
~~~

- The function is called once, with the row as its only argument. What it
  builds is the template; every item gets a copy.
- `{field}` in a text, a picture's source or a `describe` is filled from the
  item. Dotted fields (`{author.name}`) reach into nested data.
- A `command` that takes an argument receives the row's item -- the same
  dict `on_click` receives. One that takes none is called as it is.
- The row is styled as `<id>_row`; everything inside it by its own id, like
  anywhere else. Rows take the height of what they hold.
- Pictures can be web addresses, files on the phone or files in the app's
  folder; the ones the items name are packaged with the app.
- `set_items()`, `append_items()` and the rest work as they do for slot rows,
  and a phone recycles the rows: only the ones on screen exist.

On the phone the template becomes a layout of its own, inflated by a
RecyclerView; in the Previewer the visible rows are drawn from the same
components.

#### A row that changes: the red heart

A row is drawn from its item, so to change a row, change its item.
`update_item(id, changes)` patches one item -- found by its `id` field -- and
draws that row again. Two arguments read a field to decide how a component
looks:

- `visible="{field}"` on any component shows it only when the field is on.
- `active="{field}"` on a button shows `active_icon` in the button's
  `active-color` when the field is on, and `icon` when it is off.

A field is off when it is empty, `false`, `0`, `no`, `off`, `none` or `null`;
anything else is on.

~~~ python
POSTS = [
    {"id": "p1", "user": "mara.vale", "likes": 1284, "liked": "", "sponsored": ""},
    {"id": "p2", "user": "northline", "likes": 3410, "liked": "yes", "sponsored": "yes"},
]

def like(item):
    if item["liked"] == "yes":
        posts.update_item(item["id"], {"liked": "", "likes": int(item["likes"]) - 1})
    else:
        posts.update_item(item["id"], {"liked": "yes", "likes": int(item["likes"]) + 1})

def post_row(row):
    label("{user}", id="post_user", parent=row)
    label("Sponsored", id="post_ad", parent=row, visible="{sponsored}")
    button("", icon="favorite_border", active_icon="favorite", active="{liked}",
           describe="Like", id="post_like", parent=row,
           command=lambda item: like(item))
    label("{likes} likes", id="post_likes", parent=row)

posts = virtual_collection(POSTS, row=post_row, id="posts", screen=home)
~~~

~~~ css
post_like { active-color: #FF3040; }
~~~

The heart turns red and the count goes up on that post alone, and back again
on the next tap. The phone draws both icons at build time, the lit one in
`active-color`.

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

A card's title is white and its subtitle grey unless the component says
otherwise, on a dark shelf or a light one:

~~~ css
recent { title-color: #FFFFFF; subtitle-color: #B3B3B3; }
mixes  { color: #111111; }      /* the title, when title-color is not given */
~~~

The page's `body` colour does not reach a card. Until 1.11.0 the phone painted
white and grey whatever the stylesheet said, and the Previewer took the body's
text colour instead -- dark titles on a dark shelf, on the desktop only.

## Pictures

An `image()` or `avatar()` can be tapped, and an image can change what it shows:

~~~ python
story = image("story1.jpg", id="story", screen=viewer, describe="Story",
              command=next_story)
avatar("face.png", size=62, id="ring", screen=home, describe="mara",
       command=open_story)

def next_story():
    story.set_src("story2.jpg")
~~~

`set_src()` takes a file from the app's folder or a URL, as `image()` does; the
files it names are packaged with the app. A `border-color` and `border-width`
on a round avatar draw a ring around the picture, not over it.

## Icons

`icon=` takes any of the 2,000+ Material Icons, by the name fonts.google.com/icons
shows with spaces as underscores: `favorite_border`, `chat_bubble_outline`,
`cameraswitch`, `add_comment`. The glyphs ship with ApkPy (Apache 2.0), and
the phone gets the same paths as vector drawables. To find one:

~~~ python
from apkpy_lib import icons
icons.search("heart")    # ['favorite', 'favorite_border', 'heart_broken', ...]
~~~

A name that is not in the set draws a plain circle and reports `U2015`.

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

### Floating over the screen

`position: absolute` on a screen's own component takes it out of the column
and puts it on a layer over the content, fixed while the content scrolls --
a floating button, a composer or a player bar pinned to the bottom. Inside a
container with `position: relative`, it is placed in that container instead.

~~~python
home = Screen(id="home", scroll=True)
label("Stories", id="title", screen=home)
button("", id="fab", icon="add", describe="New story", screen=home,
       command=new_story)
~~~

```css
fab { position: absolute; right: 20px; bottom: 24px;
      width: 56px; height: 56px; border-radius: 28px; }
```

An absolute box with no `width` is as wide as its content, so `right: 12px`
puts a column of buttons against the right edge; with both `left` and `right`
it stretches between them. On a screen with a bottom bar the layer ends above
the bar. A tap that lands on none of its components reaches the content below.

In the Previewer the layer is drawn the same way, but a desktop widget cannot
be see-through: a transparent component over a picture, the camera or a map
shows its parent's colour where the phone shows what is behind it.

### Rows that start at the start

A `display: flex` row with no `justify-content` centres what it holds, and has
since the first release -- a row of buttons under a form looks right that way.
Chips, a caption made of two labels, an avatar with a name: write where the row
starts.

~~~ css
chips { display: flex; flex-direction: row; justify-content: flex-start; gap: 8px; }
~~~

A `Theme` gives the `body` a 12px `gap` and a 12px `padding`, and the body is
folded into every container. A row that should be tight -- icons inside a pill,
a list of actions under a photo -- says so with `gap: 0px`.

### Aligning one child

`align-self` moves one child across its parent. On a screen's own component
it is what puts your reply on the right of a chat:

```css
their_message { max-width: 260px; align-self: flex-start; }
my_message    { max-width: 260px; align-self: flex-end; }
```

A child narrower than the screen is otherwise centred.

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
