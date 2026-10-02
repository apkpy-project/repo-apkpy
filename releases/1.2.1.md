# ApkPy 1.2.1 — Production Feeds

ApkPy 1.2.1 is a focused extension to the virtual collections introduced in
1.2.0. It adds the missing coordination around large remote datasets:
incremental pages, prefetching, refresh and a loading latch.

The server remains responsible for cursors and page contents. ApkPy is
responsible for asking once, keeping the reader's position and updating the
native collection efficiently.

## The public API

```python
feed = virtual_collection(
    initial_items,
    template={
        "image": "{avatar}",
        "title": "{author}",
        "subtitle": "{message}",
        "meta": "{time}",
        "badge": "{category}",
    },
    layout="list",               # "list" or "grid"
    columns=2,                   # used by a grid
    on_click=open_item,
    on_end_reached=load_more,
    on_refresh=reload_feed,
    prefetch=4,
    screen=home,
)
```

| API | Behaviour |
| --- | --- |
| `on_end_reached=callback` | Requests another page when the final visible row enters the prefetch window. |
| `on_refresh=callback` | Enables the top refresh gesture and manual `refresh()`. |
| `prefetch=4` | Starts the request four records before the end. Values are clamped to a safe range. |
| `append_items(items, has_more=True)` | Appends one page and releases the loading latch. |
| `set_items(items, has_more=True)` | Replaces the dataset, preserves the template and finishes refresh. |
| `finish_load(has_more=True)` | Finishes an empty or failed attempt without changing the dataset. |
| `refresh()` | Runs the same guarded callback as the pull gesture. |

`items` can be an ordinary Python list or a JSON-array string returned by
`json_get()`. Every source field stays available to the row template and click
callback.

## Complete cursor example

```python
from apkpy_lib import (
    Screen, https, json_get, storage, toast, virtual_collection,
)

home = Screen(id="home", scroll=False)
storage.set("feed_cursor", "first")

def open_post(item):
    toast(item["author"])

def page_loaded(success, body):
    if not success:
        status.set_value("Could not load this page. Scroll to retry.")
        feed.finish_load(has_more=True)
        return

    next_cursor = json_get(body, "next_cursor")
    storage.set("feed_cursor", next_cursor)
    feed.append_items(
        json_get(body, "items"),
        has_more=next_cursor != "",
    )

def load_more():
    cursor = storage.get("feed_cursor", "first")
    https.get(
        "https://api.example.com/feed?cursor=" + cursor,
        on_response=page_loaded,
    )

def refresh_loaded(success, body):
    if not success:
        feed.finish_load()
        return

    next_cursor = json_get(body, "next_cursor")
    storage.set("feed_cursor", next_cursor)
    feed.set_items(
        json_get(body, "items"),
        has_more=next_cursor != "",
    )

def reload_feed():
    https.get("https://api.example.com/feed", on_response=refresh_loaded)

feed = virtual_collection(
    [],
    template={
        "image": "{avatar}",
        "title": "{author}",
        "subtitle": "{message}",
        "meta": "{time}",
    },
    on_click=open_post,
    on_end_reached=load_more,
    on_refresh=reload_feed,
    prefetch=4,
    screen=home,
)
```

## Why the loading latch matters

Scroll listeners can run many times during one gesture. Without a latch, the
same cursor can be requested repeatedly and duplicate the page. ApkPy marks the
collection as loading before the callback starts. Another scroll, refresh or
manual request is ignored until one of these methods completes it:

```python
feed.append_items(page)       # success with records
feed.set_items(first_page)    # refresh success
feed.finish_load()            # empty page or recoverable error
```

Passing `has_more=False` closes the end-of-list path. A refresh opens a new
pagination generation and allows the application to decide `has_more` again.

## Native Android output

The generated Activity keeps a small state block for each paginated
collection:

```java
private boolean production_feedLoading = false;
private boolean production_feedRefreshing = false;
private boolean production_feedHasMore = true;
```

The page boundary is observed by a native listener:

```java
production_feed.addOnScrollListener(
    new RecyclerView.OnScrollListener() {
        @Override public void onScrolled(
            RecyclerView recyclerView, int dx, int dy
        ) {
            _apkpyMaybeLoadProduction_FeedPage();
        }
    }
);
```

Appending a page updates only the inserted range:

```java
int oldSize = production_feed_items.size();
production_feed_items.addAll(page);
production_feed_adapter.notifyItemRangeInserted(oldSize, page.size());
```

`SwipeRefreshLayout` and its Gradle dependency are generated only when
`on_refresh` exists. A normal `virtual_collection()` keeps the lean 1.2.0
RecyclerView output.

## Previewer parity

The desktop Previewer:

- watches the visible range and applies the same prefetch threshold;
- preserves the scroll offset when pages are appended;
- retains list/grid templates, click callbacks and source JSON fields;
- exposes a compact loading state;
- supports a top pull gesture and `feed.refresh()`;
- applies the same duplicate-request and `has_more` rules.

The runnable `playground/writehere.py` app contains two independent examples:

1. **Field Notes** — a social timeline that prefetches a second page and ends
   cleanly.
2. **Object Index** — a two-column catalogue that deliberately fails, releases
   its latch, retries the missing page and supports refresh.

These patterns map directly to an Instagram/X/Reddit timeline, a Spotify
library, a delivery catalogue, a store, an inbox or older chat history.

## Deliberate limits

This update does not add Paging 3, a required backend, offline synchronization,
automatic cursor persistence, item-level diffing, deep links or biometrics.
The full dataset currently held by the app remains in memory. Version 1.2.1 is
about predictable UI coordination and efficient native insertion, not about
owning an application's data architecture.
