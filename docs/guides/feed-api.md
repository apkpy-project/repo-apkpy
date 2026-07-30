---
title: API-backed production feed
description: Build a paginated and refreshable native RecyclerView with guarded ApkPy callbacks.
---

# API-backed production feed

This pattern keeps the cursor in application code while ApkPy owns the loading
latch, visible rows and efficient Android insertions.

```python
from apkpy_lib import Screen, json_get, label, https, run, storage, virtual_collection

home = Screen(id="home")

status = label("Ready", id="feed_status", screen=home)

def load_more():
    cursor = storage.get("feed_cursor", "")
    https.get(
        "https://api.example.com/feed?cursor=" + cursor,
        on_response=page_loaded,
    )

def refresh_feed():
    https.get(
        "https://api.example.com/feed",
        on_response=refresh_loaded,
    )

def page_loaded(success, body):
    if not success:
        status.set_value("Could not load. Scroll or refresh to retry.")
        feed.finish_load(has_more=True)
        return

    items = json_get(body, "items")
    cursor = json_get(body, "next_cursor")
    storage.set("feed_cursor", cursor)
    has_more = cursor != ""
    feed.append_items(items, has_more=has_more)

def refresh_loaded(success, body):
    if not success:
        status.set_value("Refresh failed. Pull down to retry.")
        feed.finish_load(has_more=True)
        return

    cursor = json_get(body, "next_cursor")
    storage.set("feed_cursor", cursor)
    feed.set_items(
        json_get(body, "items"),
        has_more=cursor != "",
    )

feed = virtual_collection(
    [],
    template={
        "image": "{avatar}",
        "title": "{author}",
        "subtitle": "{message}",
        "meta": "{time}",
    },
    on_end_reached=load_more,
    on_refresh=refresh_feed,
    prefetch=4,
    screen=home,
)

run(home)
```

## What Android receives

- a native `RecyclerView`;
- `RecyclerView.OnScrollListener` only when end loading is used;
- `notifyItemRangeInserted()` for appended pages;
- `SwipeRefreshLayout` only when `on_refresh` exists;
- a per-feed loading latch that blocks duplicate callbacks.

## Add live mutations

```python
mutation = feed.update_item(
    post_id,
    {"likes": new_count, "liked": True},
    optimistic=True,
)

def like_finished(success, _body):
    if success:
        feed.commit(mutation)
    else:
        feed.rollback(mutation)
```

Use `prepend_items()` for a new post, `remove_item()` for deletion and
`merge_items()` for a WebSocket patch. The backend remains the canonical owner
of cursors, permissions and final record state.

See [Production Feeds](../production-feeds.md) for the full mutation model.
