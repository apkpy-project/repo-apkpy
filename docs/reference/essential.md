---
title: Essential API reference
description: Exact ApkPy signatures, callback contracts and the smallest useful examples.
---

# Essential API reference

This page is the fastest route from an API name to working code. It documents
the supported public surface exported by `apkpy_lib`; generated Java helper
classes are implementation details.

## Conventions

```python
from apkpy_lib import Screen, Theme, button, label, run

home = Screen(id="home", scroll=True)
label("Hello", id="title", screen=home)
button("Continue", id="continue", command=lambda: None, screen=home)

style = """
home { padding: 24px; gap: 12px; }
title { font-size: 28px; font-weight: bold; }
continue { border-radius: 14px; }
"""

run(start_screen=home, theme=Theme(mode="dark"))
```

- Pass `screen=` to attach a top-level component to a screen.
- Pass `parent=` to put a component inside a `container` or `card`.
- An `id` is both the stable component name and its CSS-like selector.
- Network, uploads and typed database work run outside the UI thread. Their
  callbacks return to the Previewer/Android UI thread.
- The Previewer exercises layout and application flow. Permissions, Firebase,
  codecs, background restrictions and GPS still need an Android test.

## App, screens and navigation

| API | Signature | Returns |
| --- | --- | --- |
| `Screen` | `Screen(id, background_image=None, scroll=False)` | screen definition |
| `run` | `run(start_screen=None, theme=None)` | starts the app/Previewer |
| `bottom_nav` | `bottom_nav(screens, labels=None, icons=None)` | `BottomNav` |
| `on_click_navigate` | `on_click_navigate(screen, data=None)` | callback suitable for `command=` |
| `app_bar` | `app_bar(title, leading=None, actions=None, id=None, screen=None)` | app-bar definition |
| `sliver_app_bar` | `sliver_app_bar(title, image, expanded_height=240, pinned=True, leading=None, actions=None, id=None, screen=None)` | collapsible app bar |
| `action` | `action(icon, command=None, label=None, id=None)` | app-bar action |

Navigation data is read on the destination screen:

```python
details = Screen(id="details", scroll=True)
button(
    "Open note",
    command=on_click_navigate(details, {"note_id": 42}),
    screen=home,
)

selected_id = details.get_param("note_id", 0)
```

## Components

| API | Exact public signature |
| --- | --- |
| `label` | `label(text, id=None, screen=None, parent=None, variant=None)` |
| `button` | `button(text, id=None, command=None, screen=None, parent=None, variant=None, icon=None)` |
| `inputs` | `inputs(placeholder="", id=None, type="text", screen=None, parent=None, on_change=None)` |
| `image` | `image(src, id=None, screen=None, parent=None, *, placeholder=None, fallback=None, cache=True, fade_in=False, blur=0, tint=None, aspect_ratio=None)` |
| `video` | `video(src, id=None, screen=None, parent=None, *, poster=None, autoplay=False, controls=True, loop=False, muted=False, preload=True, aspect_ratio="16:9", fit="contain", on_ready=None, on_progress=None, on_end=None, on_error=None)` |
| `avatar` | `avatar(src, size=48, status=None, id=None, screen=None, parent=None, *, placeholder=None, fallback=None, cache=True, fade_in=True, blur=0, tint=None)` |
| `container` | `container(id=None, screen=None, parent=None)` |
| `card` | `card(title=None, subtitle=None, image=None, content=None, actions=None, id=None, variant="elevated", screen=None, parent=None)` |
| `list_view` | `list_view(items=None, id=None, screen=None, parent=None, on_click=None, rich=False)` |

Common returned-component methods are `get_value()`, `set_value(value)`,
`show()` and `hide()`. Images expose `set_src()`. Videos expose `play()`,
`pause()`, `stop()`, `seek(seconds)`, `set_source()`, `set_speed()` and
`set_muted()`.

Input types include `text`, `password`, `number`, `date`, `time`, `textarea`,
`select`, `checkbox`, `radio` and `range`. Options and range values are passed
through `set_items()` or `set_value()` as shown in the component guides.

## Layout

```python
actions = container(id="actions", screen=home)
save = button("Save", parent=actions)
cancel = button("Cancel", variant="outlined", parent=actions)

responsive(
    mobile=column(save, cancel),
    tablet=row(save, cancel),
    breakpoint=600,
    parent=actions,
)
```

| API | Purpose |
| --- | --- |
| `row(*children)` | horizontal composition |
| `column(*children)` | vertical composition |
| `responsive(mobile, tablet=None, landscape=None, breakpoint=600, ...)` | switches layout by viewport |

## Virtual collections and live state

```python
feed = virtual_collection(
    [],
    template={
        "title": "{author}",
        "subtitle": "{message}",
        "meta": "{time}",
        "image": "{avatar}",
    },
    on_end_reached=load_more,
    on_refresh=reload,
    prefetch=4,
    screen=home,
)
```

| Method | Contract |
| --- | --- |
| `set_items(items, title=None, subtitle=None, image=None, has_more=True)` | replace the dataset and finish refresh; legacy rich-row keys remain supported |
| `append_items(items, has_more=True)` | append a page without resetting position |
| `prepend_items(items)` | insert above the visible anchor |
| `update_item(id, changes, key="id", optimistic=False)` | patch one keyed row |
| `remove_item(id, key="id", optimistic=False)` | remove one keyed row |
| `merge_items(items, key="id")` | update matches and append new keys |
| `commit(mutation_id=None)` | accept an optimistic snapshot |
| `rollback(mutation_id=None)` | restore one optimistic snapshot |
| `finish_load(has_more=True)` | release a failed/empty load latch |
| `refresh()` | start the guarded refresh callback |

`state(initial, id=None)` returns a reactive value with `get`, `set`,
`increment`, `decrement`, `toggle`, `bind` and `bind_visibility`.

```python
count = state(0, id="cart_count")
badge = label("0 items", screen=home)
count.bind(badge, template="{value} items")
button("Add", command=lambda: count.increment(), screen=home)
```

Use `lifecycle(screen, on_mount=None, on_resume=None, on_pause=None,
on_destroy=None)` to start and stop screen-owned work.

## Typed SQLite Data Core

```python
notes = db.model(
    "notes",
    fields={
        "id": db.integer(primary_key=True, auto_increment=True),
        "title": db.text(required=True, max_length=120),
        "favorite": db.boolean(default=False),
        "updated_at": db.datetime(default=db.now()),
    },
    indexes=[db.index("idx_notes_updated", ["updated_at"])],
)

db.schema("notes_app", version=1, models=[notes])
```

| Area | Public API |
| --- | --- |
| Fields | `integer`, `real`, `text`, `boolean`, `datetime`, `json`, `blob`, `now` |
| Model | `model(name, fields, indexes=None)` and `index(name, fields, unique=False)` |
| CRUD | `insert`, `insert_many`, `get`, `find`, `update`, `delete`, `count` |
| Filters | `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `contains`, `starts_with`, `ends_with`, `in_`, `is_null`, `and_`, `or_` |
| Order | `asc(name)`, `desc(name)` |
| Schema | `schema(name, version, models, migrations=None)` |
| Migration | `migration`, `create_table`, `add_column`, `rename_column`, `create_index`, `rename_index`, `drop_index`, `rename_table`, `sql` |

CRUD callbacks:

| Call | `on_result` receives |
| --- | --- |
| `insert` | new row ID |
| `insert_many` | inserted row count |
| `get` | JSON object or empty value |
| `find` | iterable `JsonRows` |
| `update` / `delete` | affected row count |
| `count` | integer count |

Every operation accepts `on_error(message)`. Use parameterized filters and
values; do not build SQL strings with user input.

### Reactive Data

```python
folder_notes = db.relation(
    "folder_notes",
    parent=folders,
    child=notes,
    foreign_key="folder_id",
    parent_as="folder",
    children_as="notes",
    on_delete="cascade",
)

db.schema(
    "knowledge_vault_live",
    version=1,
    models=[folders, notes],
    relations=[folder_notes],
)

live_notes = notes.observe(
    filters=[db.eq("folder_id", active_folder_id)],
    include=["folder"],
    screen=notes_screen,
    on_change=lambda rows: notes_feed.set_items(rows),
)
```

| Area | Public API |
| --- | --- |
| Relation | `db.relation(name, parent, child, foreign_key, parent_as, children_as, on_delete)` |
| Eager read | `get(..., include=None)` and `find(..., include=None)` |
| Observer | `model.observe(..., screen, on_change, on_error=None)` |
| Observer control | `refresh()`, `update_query(...)`, `close()` |

`on_delete` accepts `restrict`, `cascade` or `set_null`. Includes are limited
to one level and are loaded in batches. Observers pause and resume with their
screen, coalesce rapid invalidations and deliver callbacks on the UI thread.
See [Reactive Data](../reactive-data.md) for lifecycle and migration rules.

## HTTP and JSON

```python
def received(success, body):
    if success:
        title.set_value(json_get(body, "title"))
    else:
        snackbar("Request failed")

https.get("https://api.example.com/note/42", on_response=received)
```

`https.get`, `post`, `put`, `patch` and `delete` call
`on_response(success, body)`. `json_get(json_text, "items.0.title")` safely
reads a dotted path.

## WebSocket

```python
websocket.connect(
    "room",
    "wss://example.com/live",
    headers={"Authorization": "Bearer " + token},
    on_open=lambda: status.set_value("Live"),
    on_message=lambda message: messages.prepend_items([{"text": message}]),
    on_error=lambda message: status.set_value("Offline · " + message),
    reconnect=True,
)

websocket.send("room", "hello")
websocket.close("room")
```

`connect()` also accepts `protocols`, `on_close`, `reconnect_delay`,
`max_reconnect_delay` and `ping_interval`. Sends made during the handshake are
queued with a bounded limit.

## Storage and cryptography

| Object | Methods |
| --- | --- |
| `storage` | `set`, `get`, `delete`, `clear`, `keys` |
| `crypto` | `hash_password`, `verify_password`, `encrypt`, `decrypt` |
| `files` | `download`, `path`, `exists`, `delete` |

Encrypted values are tied to the app/device key. Copying only the ciphertext to
another installation is not a backup strategy. Never ship API secrets in
client code.

## Overlays and feedback

| API | Callback shape |
| --- | --- |
| `bottom_sheet(..., on_select=...)` | selected item |
| `modal(..., on_confirm=..., on_cancel=...)` | no arguments |
| `menu` / `popup_menu` / `context_menu` | selected item |
| `date_picker` / `time_picker` | selected value |
| `snackbar(message, action=None, on_action=None, duration=3000)` | action callback |
| `confirm(title, message, on_result=None)` | boolean result |

Overlay objects expose `open()` and `close()`.

## Android integrations

| API | What it controls |
| --- | --- |
| `permissions` | runtime permission checks and requests |
| `notify` / `push` | local notifications and Firebase Cloud Messaging |
| `camera` / `gallery` | capture and media selection |
| `location` | current, continuous and foreground-service tracking |
| `map_view` | tiles, markers, route line, user position and follow mode |
| `routes` | cancellable driving, walking or cycling route request |
| `service` | periodic and one-shot WorkManager tasks |
| `audio` / `video` | background audio and Media3 video |
| `uploads` | multipart transfer with progress and cancellation |

For setup requirements and complete examples, continue to the
[module reference](../api-reference.md) or the [guide index](../guides/index.md).
