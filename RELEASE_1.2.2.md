# ApkPy 1.2.2 - Keyed feed mutations

ApkPy 1.2.2 is a focused extension of Production Feeds. Pagination already
adds pages efficiently; this release handles the smaller changes that happen
after records are visible: a new post at the top, a like count, an edited
message, a deleted row or a batch of live updates.

The application continues to own its API, cursor and persistence. ApkPy owns
the in-memory collection, Previewer behaviour and native adapter updates.

## Complete API

```python
feed.prepend_items(items)
feed.update_item(item_id, changes, key="id", optimistic=False)
feed.remove_item(item_id, key="id", optimistic=False)
feed.merge_items(items, key="id")
feed.rollback(mutation_id=None)
feed.commit(mutation_id=None)
```

Records used with keyed mutations should be dictionaries and should include a
stable identifier:

```python
posts = [
    {
        "id": "post-42",
        "author": "Mira Vale",
        "message": "Small changes should stay small.",
        "liked": False,
        "likes": 128,
    }
]
```

`id` is the default key. A catalogue may use another key:

```python
catalog.merge_items(api_items, key="sku")
catalog.update_item(
    "SKU-1042",
    {"stock": "LOW"},
    key="sku",
)
```

## Insert new records above the reader

```python
def live_posts_received(items):
    feed.prepend_items(items)
```

Incoming order is retained. The Previewer adjusts its virtual offset and
Android records the first visible position before calling
`notifyItemRangeInserted(0, count)`, then restores the same visible record.

This is useful for timelines, chat history, notifications and activity logs
where new records may arrive while somebody is reading older content.

## Patch one record

```python
feed.update_item(
    "post-42",
    {
        "message": "Edited copy",
        "edited": True,
    },
)
```

The patch is merged into the existing dictionary, so fields not included in
`changes` remain available to the template and click callback. Android calls
`notifyItemChanged(position)` for that record only.

## Remove one record

```python
feed.remove_item("post-42")
```

The first matching key is removed. Android calls
`notifyItemRemoved(position)` rather than refreshing every `ViewHolder`.
Unknown IDs return `False` and leave the collection unchanged.

## Merge a live response

```python
feed.merge_items([
    {"id": "post-42", "likes": 130},
    {"id": "post-81", "author": "New author", "message": "New post"},
])
```

Matching IDs are patched in their existing positions. Missing IDs are appended
once. The operation never creates a second copy of a known ID.

Android calculates a native `DiffUtil` result and dispatches only the required
insert, move, remove and change notifications. The application does not need
Paging 3 or a mandatory backend adapter.

## Optimistic updates

Optimistic UI makes a local change before the network request finishes:

```python
def like_post(post_id):
    mutation = "like-" + post_id
    feed.update_item(
        post_id,
        {"liked": True, "likes": 129},
        optimistic=mutation,
    )
    https.post(
        "https://api.example.com/posts/" + post_id + "/like",
        on_response=lambda success, body: finish_like(success, mutation),
    )

def finish_like(success, mutation):
    if success:
        feed.commit(mutation)
    else:
        feed.rollback(mutation)
```

The same pattern works for deletes:

```python
feed.remove_item(
    "message-19",
    key="id",
    optimistic="delete-message-19",
)
```

- `optimistic=False` performs the local change without retaining history.
- `optimistic=True` uses the selected item ID as the transaction ID.
- `optimistic="custom-id"` gives the transaction an explicit name.
- `rollback()` without an argument restores the latest pending transaction.
- `commit()` without an argument accepts the latest pending transaction.

When several local changes reuse the same transaction ID, ApkPy keeps the
first snapshot. One rollback therefore returns to the state before the
transaction began, not merely to the previous line of Python.

Calling `set_items()` starts from authoritative data and clears pending
optimistic snapshots.

## Generated Android

The generated code follows the size of each change:

| Python operation | Native adapter path |
| --- | --- |
| `prepend_items()` | `notifyItemRangeInserted(0, count)` and offset restore |
| `update_item()` | `notifyItemChanged(position)` |
| `remove_item()` | `notifyItemRemoved(position)` |
| `merge_items()` | `DiffUtil.calculateDiff()` |
| `rollback()` | `DiffUtil.calculateDiff()` |
| `commit()` | Drops the stored snapshot; no redraw |

Mutation helpers and history fields are emitted only in applications that call
one of the 1.2.2 methods. Existing virtual collections without keyed mutations
keep their earlier output.

## Previewer

The Previewer uses the same stable-key rules and transaction history:

- prepend keeps the record being read in view;
- update redraws the affected pooled row;
- remove closes the deleted row without resetting the screen;
- merge and rollback retain the current collection offset;
- templates, nested JSON fields and click callbacks continue to receive the
  complete record.

The runnable `playground/writehere.py` application contains a paginated feed
and a separate mutation lab for insert, like, delete, merge, commit and
rollback.

Three smaller examples are available for copying:

- `examples/18_social_feed.py`;
- `examples/19_product_catalog.py`;
- `examples/20_chat_history.py`.

The site includes a complete
[Production Feeds tutorial](docs/production-feeds.md) and a separate
[compatibility and limits matrix](docs/compatibility.md).

## Validation

- 164 transpiler regression checks passed;
- 16 focused feed, generation and module checks passed;
- the demonstration generated a complete Android Studio project;
- Gradle compiled that project into a debug APK;
- the documentation site passed a strict MkDocs build;
- unused mutation helpers remain absent from plain collections.

## Scope

Version 1.2.2 does not add offline synchronization, conflict-resolution rules,
automatic API retries, cache persistence or a backend protocol. It gives
applications the precise collection operations needed to implement those
policies without rebuilding their interfaces.
