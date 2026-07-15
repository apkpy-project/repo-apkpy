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
