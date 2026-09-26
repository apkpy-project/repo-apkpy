# Screens and navigation


## Navigation drawer

A bottom bar runs out at five destinations. Past that -- and for anything with
projects, folders or an account behind it -- the panel that slides in from the
leading edge is the shape people expect:

~~~ python
chat = Screen(id="chat")
projects = Screen(id="projects")
artifacts = Screen(id="artifacts")

menu = drawer(
    [chat, projects, artifacts],
    labels=["New chat", "Projects", "Artifacts"],
    icons=["add", "folder", "description"],
    header="Ora",
    subtitle="you@example.com",
)

app_bar("New chat",
        leading=action("menu", command=lambda: menu.open()),
        screen=chat)
~~~

Declared once for the whole app, like `bottom_nav`. Each item starts the screen
it names, the open screen stays highlighted, and the back button closes the
panel before it leaves the screen. `menu.close()` closes it from anywhere.

Style the panel with its `id`:

~~~ css
menu {
    background-color: var(--surface);
    color: var(--text);
    subtitle-color: var(--text-secondary);
    active-color: var(--primary);
}
~~~

**Declare it after your screens.** A drawer needs every screen to exist, and
your app bars usually come with those screens -- so the `drawer(...)` call
naturally lands below the app bars that open it. That is fine: the compiler
looks for it before it reads any function body. What it cannot do is find a
drawer built inside a loop or an `if`, because it reads your module rather than
running it.


## Navigate between screens

~~~ python
home = Screen(id="home")
details = Screen(id="details")

open_button = button("Open details", screen=home)
home.on_click_navigate(button=open_button, to=details)
~~~

The standalone helper also works inside callbacks:

~~~ python
button(
    "Open",
    command=lambda: on_click_navigate(details),
    screen=home,
)
~~~

## Pass data

~~~ python
button(
    "Open track",
    command=lambda: on_click_navigate(
        details,
        data={"title": "Midnight Drive", "track_id": "42"},
    ),
    screen=home,
)

title = label("", screen=details)
title.set_value(details.get_param("title", "Unknown track"))
~~~

Values are passed as Android Intent extras and as screen parameters in the Previewer.

## Change another screen

On a phone every `Screen` is its own Android Activity. A function running on
one screen can still set a label, show or hide a component, or fill a list
that belongs to another: the screen that owns it applies the change when it
comes to the front, or at once if it already is.

~~~ python
home = Screen(id="home")
stats = Screen(id="stats")

total = label("", id="total", screen=stats)
done_list = list_view([], id="done_list", screen=stats)


def refresh():
    counted = db.query("SELECT COUNT(*) AS n FROM habits")
    total.set_value(f"Habits: {counted[0]['n']}")        # a label on Stats
    finished = db.query("SELECT name FROM habits WHERE done_on = ?",
                        [datetime.date()])
    done_list.set_items(finished, title="name")          # a list on Stats


def mark_done(item):                                     # runs on Home
    db.execute("UPDATE habits SET done_on = ? WHERE id = ?",
               [datetime.date(), item["id"]])
    refresh()


habits = list_view([], id="habits", on_click=mark_done, screen=home)
~~~

`set_value()`, `show()`, `hide()` and `set_items()` reach another screen; if
several arrive before it comes back, the last one wins, as in the Previewer.
Reading another screen's component with `get_value()` does not, and neither do
the other list operations (`append_items()`, `merge_items()`,
`update_item()`): keep a value you need to read in `state()` or the database,
and change such a list from code on its own screen, for example with
`lifecycle(stats, on_resume=refresh)`.

Before 1.11.0 these calls did nothing on a phone, while the Previewer, where
every screen lives in one window, showed them working.

## Bottom navigation

~~~ python
bottom_nav(
    [home, library, settings],
    labels=["Home", "Library", "Settings"],
    icons=["home", "list", "settings"],
)
~~~

Use bottom navigation for two to five top-level destinations. Call it once at module level, outside a screen or callback.

## Fixed app bar

~~~ python
app_bar(
    "Library",
    leading="menu",
    actions=[
        action("search", command=open_search, label="Search"),
        action("favorite", command=open_favourites, label="Favourites"),
    ],
    screen=library,
)
~~~

Accessibility labels describe icon-only actions on Android.

### Getting back out

A leading `arrow_back` with no `command=` of its own means "leave this
screen". It needs no wiring:

~~~ python
model_screen = Screen(id="model_screen")

app_bar(
    "Default model",
    leading=action("arrow_back", label="Back"),
    screen=model_screen,
)
~~~

On Android that compiles to `finish()`, which returns to whichever screen
started this one. The Previewer keeps the same history and the arrow walks it
back, so a settings screen behaves the same in both.

Give the arrow a `command=` and it does that instead -- useful when leaving
has to save a draft first, though you then own the navigation too.

**Alt+Left** stands in for the phone's Back gesture in the Previewer, which
matters for a screen that draws no arrow of its own. On both, an open
`drawer()` closes before Back leaves the screen, and Back at the first screen
does nothing.

## Collapsible app bar

Use a sliver bar with a scrollable screen:

~~~ python
album = Screen(id="album", scroll=True)

sliver_app_bar(
    "Midnight Drive",
    image="album-cover.jpg",
    expanded_height=260,
    pinned=True,
    leading="arrow_back",
    screen=album,
)
~~~

The image header collapses while content scrolls and can leave the toolbar pinned.

## Persistent mini-player

~~~ python
mini_player(open=player_screen)
~~~

The mini-player appears above bottom navigation, follows the current background track and opens the specified player screen.

It takes the theme's surface and text colours unless it has its own. Give it an
`id` -- or style `mini_player` -- when a dark player lives in a light app:

~~~ python
mini_player(open=player_screen, id="mini")
~~~

~~~ css
mini { background-color: #3B1F2B; color: #FFFFFF; subtitle-color: #D6C2CA; }
~~~

`color` is the title and the play/pause icon, `subtitle-color` the artist.
