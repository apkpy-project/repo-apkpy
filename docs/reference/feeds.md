---
title: Feeds and reactive state API
description: Virtual collections, paging, keyed mutations, state and lifecycle reference.
---

# Feeds and reactive state API

## `virtual_collection`

```python
virtual_collection(
    items,
    template={...},
    layout="list",
    columns=2,
    item_height=None,
    buffer=2,
    on_end_reached=None,
    on_refresh=None,
    prefetch=4,
    screen=home,
)
```

| Method | Result |
| --- | --- |
| `set_items(items, has_more=True)` | replace data and finish refresh |
| `append_items(items, has_more=True)` | add a page without resetting position |
| `prepend_items(items)` | add records before the visible anchor |
| `update_item(id, changes, key="id", optimistic=False)` | patch one keyed row |
| `remove_item(id, key="id", optimistic=False)` | remove one keyed row |
| `merge_items(items, key="id")` | update matches and append new keys |
| `commit(mutation_id=None)` | accept an optimistic snapshot |
| `rollback(mutation_id=None)` | restore a snapshot |
| `finish_load(has_more=True)` | release the paging latch |
| `refresh()` | run the guarded refresh callback |

## State and lifecycle

`state(initial, id=None)` returns a `ReactiveState`. It supports `get`, `set`,
`increment`, `decrement`, `toggle`, `bind` and `bind_visibility`.

`lifecycle(screen, on_mount=None, on_resume=None, on_pause=None,
on_destroy=None)` scopes work to a screen.

See [API-backed feed](../guides/feed-api.md) and
[Production Feeds](../production-feeds.md).
