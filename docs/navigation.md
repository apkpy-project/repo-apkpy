# Screens and navigation

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
