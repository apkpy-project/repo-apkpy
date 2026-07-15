# Overlays and content states

Overlays are declared once and opened from a callback. They do not occupy normal screen layout space.

## Bottom sheet

~~~ python
playlist_sheet = bottom_sheet(
    "Add to playlist",
    content="Choose where to save this track.",
    items=["Focus", "Training", "Favourites"],
    on_select=lambda name: audio.add_to_playlist(name),
    close_text="Not now",
)

button("Add to playlist", command=playlist_sheet.open, screen=home)
~~~

## Modal

~~~ python
delete_dialog = modal(
    "Delete download?",
    content="The track will remain in your library.",
    confirm_text="Delete",
    cancel_text="Cancel",
    on_confirm=lambda: files.delete("track.mp3"),
)
~~~

## Menus and tooltips

~~~ python
more = button("More", variant="icon", icon="more_vert", screen=home)

popup_menu(
    anchor=more,
    items=["Share", "Download", "Remove"],
    on_select=handle_option,
)

context_menu(
    target=track_row,
    items=["Play next", "Add to playlist"],
    on_select=handle_track_option,
)

tooltip(more, "More options")
~~~

Desktop right-click maps to Android long-press for context menus.

## Pickers and snackbar

~~~ python
date_dialog = date_picker(
    title="Choose a date",
    on_select=lambda value: selected_date.set_value(value),
)

time_dialog = time_picker(
    title="Choose a time",
    on_select=lambda value: selected_time.set_value(value),
)

snackbar(
    "Track removed",
    action="Undo",
    on_action=restore_track,
    duration=4000,
)
~~~

## Loading skeleton

~~~ python
loading = skeleton(
    variant="music_card",
    count=4,
    visible=True,
    screen=library,
)
~~~

Available variants are <code>music_card</code>, <code>list</code>, <code>card</code> and <code>text</code>. Use <code>loading.show()</code> and <code>loading.hide()</code>.

## Empty and error states

~~~ python
empty = empty_state(
    "No tracks yet",
    message="Add music to see it here.",
    icon="library_music",
    action="Explore",
    on_action=open_explore,
    visible=False,
    screen=library,
)

failed = error_state(
    "Could not load the library",
    message="Check the connection and try again.",
    retry=load_library,
    retry_text="Try again",
    visible=False,
    screen=library,
)
~~~

A typical async flow hides all states, shows the loading state, then reveals either content, empty state or error state after the result arrives.
