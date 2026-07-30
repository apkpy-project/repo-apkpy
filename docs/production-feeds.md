# Build a production feed

<section class="feed-guide-hero">
  <div>
    <span>GUIDE / APKPY 1.2.2</span>
    <h2>One collection, three jobs.</h2>
    <p>Page older records, reconcile live data and let the interface answer before the network. The same Python API drives the desktop Previewer and a native Android RecyclerView.</p>
  </div>
  <ol aria-label="Production feed workflow">
    <li><b>01</b><span>load a page</span></li>
    <li><b>02</b><span>mutate by ID</span></li>
    <li><b>03</b><span>settle the request</span></li>
  </ol>
</section>

This guide builds a feed in layers. The application owns URLs, cursors,
authentication and conflict rules. ApkPy owns the loading guard, virtual rows,
scroll preservation and efficient native notifications.

## 1. Start with stable records

Every mutable record needs a key that remains the same across API responses:

```python
FIRST_PAGE = [
    {
        "id": "post-41",
        "avatar": "https://cdn.example.com/avatars/41.jpg",
        "author": "Mira Vale",
        "message": "The first page is ready.",
        "time": "2m",
        "likes": "128 likes",
    }
]
```

Create the collection with a reusable visual template:

```python
feed = virtual_collection(
    FIRST_PAGE,
    template={
        "image": "{avatar}",
        "title": "{author}",
        "subtitle": "{message}",
        "meta": "{time}",
        "badge": "{likes}",
    },
    item_height=122,
    buffer=3,
    on_end_reached=load_more,
    on_refresh=refresh_feed,
    prefetch=4,
    screen=home,
)
```

`buffer` controls the extra reusable rows around the viewport. `prefetch=4`
requests the next page when four records remain. Neither value changes the
server cursor.

## 2. Append pages without losing position

```python
def load_more():
    cursor = storage.get("feed_cursor", "first")
    https.get(
        "https://api.example.com/feed?cursor=" + cursor,
        on_response=page_loaded,
    )


def page_loaded(success, body):
    if success:
        next_cursor = json_get(body, "next_cursor")
        storage.set("feed_cursor", next_cursor)
        feed.append_items(
            json_get(body, "items"),
            has_more=next_cursor != "",
        )
    else:
        feed.finish_load(has_more=True)
        toast("Could not load the next page")
```

While that request is active, additional end-of-list events are ignored.
`append_items()` and `finish_load()` release the loading latch.
`has_more=False` disables new page requests until a refresh.

## 3. Refresh from an authoritative response

```python
def refresh_feed():
    https.get(
        "https://api.example.com/feed",
        on_response=refresh_loaded,
    )


def refresh_loaded(success, body):
    if success:
        feed.set_items(json_get(body, "items"), has_more=True)
    else:
        feed.finish_load(has_more=True)
```

Passing `on_refresh` adds native `SwipeRefreshLayout` on Android.
`feed.refresh()` starts the same callback from a normal button. `set_items()`
replaces the dataset, ends the refresh animation and clears pending optimistic
snapshots because the server response is authoritative.

## 4. Reconcile small changes by key

```python
feed.prepend_items([new_post])
feed.update_item("post-41", {"likes": "129 likes"})
feed.remove_item("post-19")
feed.merge_items(websocket_batch, key="id")
```

- `prepend_items()` keeps the record under the reader at the same visual
  offset. The new record is above it, so there is no disruptive jump.
- `update_item()` changes only fields present in the patch.
- `remove_item()` is a no-op when the key does not exist.
- `merge_items()` updates known keys in place and appends unseen keys once.

For a product catalogue, use `key="sku"`. For messages, use
`key="message_id"`. Array positions and display names are not stable keys.

## 5. Make optimistic actions reversible

```python
def like_post(post_id):
    mutation = "like-" + post_id
    feed.update_item(
        post_id,
        {"liked": True, "likes": "129 likes"},
        optimistic=mutation,
    )
    https.post(
        "https://api.example.com/posts/" + post_id + "/like",
        on_response=lambda success, body: settle(success, mutation),
    )


def settle(success, mutation):
    if success:
        feed.commit(mutation)
    else:
        feed.rollback(mutation)
```

The mutation is visible before the response. `commit()` removes only the
recovery snapshot, so the row should not visibly change. `rollback()` restores
the dataset captured before the first change with that transaction name.

## Try the mutation sequence

This browser-only lab mirrors the contract; it does not contact a backend.

<section class="feed-lab" data-feed-lab>
  <header>
    <div><span>LOCAL DATASET</span><strong>Mutation lab</strong></div>
    <p data-feed-status aria-live="polite">No pending local action</p>
  </header>
  <div class="feed-lab__list" data-feed-list></div>
  <div class="feed-lab__controls" aria-label="Feed mutation controls">
    <button type="button" data-feed-action="prepend">Add Rhea</button>
    <button type="button" data-feed-action="merge">Sync Noor + Cal</button>
    <button type="button" data-feed-action="like">Like Mira</button>
    <button type="button" data-feed-action="commit">Accept like</button>
    <button type="button" data-feed-action="delete">Delete Eli</button>
    <button type="button" data-feed-action="rollback">Restore Eli</button>
    <button type="button" data-feed-action="reset">Reset</button>
  </div>
</section>

`Accept like` deliberately leaves Mira at 129 likes. Its job is to discard the
snapshot after a successful response, not to apply the UI change a second time.

## Error and retry rules

| Situation | Application action |
| --- | --- |
| Next-page request failed | Call `finish_load(has_more=True)` so scrolling can retry |
| Server returned no next cursor | Call `append_items(items, has_more=False)` |
| Refresh failed | Call `finish_load()` to stop the refresh indicator |
| Optimistic request succeeded | Call `commit(transaction)` |
| Optimistic request failed | Call `rollback(transaction)` |
| Full server state arrived | Call `set_items(records, has_more=...)` |
| WebSocket batch arrived | Call `merge_items(records, key=...)` |

Do not call `append_items()` with the same page repeatedly. The loading guard
prevents duplicate callbacks, but the application remains responsible for its
cursor and response identity.

## Native output, only when needed

Android emits targeted RecyclerView operations:

```java
adapter.notifyItemRangeInserted(0, insertedCount);
adapter.notifyItemChanged(position);
adapter.notifyItemRemoved(position);
```

Mixed merges and rollbacks use `DiffUtil`. `SwipeRefreshLayout` is included
only when `on_refresh` exists. Projects that do not use 1.2.2 mutations receive
no optimistic history fields or mutation helpers.

## Copy a complete example

- [`18_social_feed.py`](https://github.com/apkpy-project/repo-apkpy/blob/main/examples/18_social_feed.py)
  — pagination, refresh and live prepend.
- [`19_product_catalog.py`](https://github.com/apkpy-project/repo-apkpy/blob/main/examples/19_product_catalog.py)
  — a two-column grid reconciled by SKU.
- [`20_chat_history.py`](https://github.com/apkpy-project/repo-apkpy/blob/main/examples/20_chat_history.py)
  — older messages, local sends and delivery state.

Continue with [Compatibility and limits](compatibility.md) before shipping.
