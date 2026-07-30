# ApkPy 1.2.2 - Keyed feed mutations { .release12-page-title }

<section class="release12-hero">
  <div>
    <span class="release12-kicker">VERSION 1.2.2 / RELEASE CANDIDATE</span>
    <h2>Change the record, not the whole feed.</h2>
    <p>Prepend new events, patch a like, remove a message and reconcile live data by stable ID. ApkPy keeps scroll position and gives failed optimistic requests a real rollback path.</p>
    <div class="release12-actions">
      <a class="md-button md-button--primary" href="../production-feeds/">Build the complete feed</a>
      <a href="#native-output">Inspect native output <span>→</span></a>
    </div>
  </div>
  <div class="release12-signal" aria-label="Version 1.2.2 mutation pipeline">
    <div class="release12-signal__head"><span>mutations / 1.2.2</span><strong>keyed</strong></div>
    <div class="release12-signal__line"><span>01</span><b>identify</b><i>stable key</i></div>
    <div class="release12-signal__line"><span>02</span><b>snapshot</b><i>optional</i></div>
    <div class="release12-signal__line"><span>03</span><b>mutate</b><i>local data</i></div>
    <div class="release12-signal__line"><span>04</span><b>notify</b><i>small range</i></div>
    <div class="release12-signal__line"><span>05</span><b>settle</b><i>commit / rollback</i></div>
  </div>
</section>

<div class="release12-status">
  <span class="release12-status__dot"></span>
  <strong>Built on Production Feeds</strong>
  <span>Pagination stays application-controlled; keyed mutations stay UI-efficient.</span>
</div>

## The new operations

<div class="release12-output">
  <div><span>prepend_items</span><strong>New records at the top</strong><p>Preserves the record currently under the reader's thumb.</p></div>
  <div><span>update_item</span><strong>Patch one stable ID</strong><p>Merges changed fields and leaves the rest of the record intact.</p></div>
  <div><span>remove_item</span><strong>Delete one row</strong><p>Unknown IDs are a no-op instead of a full refresh.</p></div>
  <div><span>merge_items</span><strong>Reconcile a live batch</strong><p>Known IDs update in place; unseen IDs append without duplicates.</p></div>
</div>

```python
feed.prepend_items([new_post])
feed.update_item("post-42", {"likes": 129})
feed.remove_item("post-19")
feed.merge_items(websocket_items, key="id")
```

All keyed methods default to the `id` field. Pass `key="sku"`,
`key="message_id"` or another stable field when the backend uses a different
identifier.

## Optimistic example

<div id="optimistic-example"></div>

An optimistic action is visible immediately. The network response decides
whether that local transaction becomes permanent:

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
        on_response=lambda success, body: settle_like(success, mutation),
    )

def settle_like(success, mutation):
    if success:
        feed.commit(mutation)
    else:
        feed.rollback(mutation)
```

`optimistic=True` uses the selected item ID as the transaction name. An
explicit string is clearer when the same record may have a like, edit and
delete pending independently.

Several changes can share a transaction name:

```python
feed.update_item(
    "cart-7", {"quantity": 2}, optimistic="checkout-edit"
)
feed.update_item(
    "cart-8", {"quantity": 3}, optimistic="checkout-edit"
)

# Restores the cart before either local edit.
feed.rollback("checkout-edit")
```

The first snapshot wins. `rollback()` or `commit()` without an argument targets
the most recently created pending transaction.

## Merge without duplicates

```python
def live_batch_received(items):
    feed.merge_items(items, key="id")
```

For every incoming record, ApkPy checks its stable key:

1. a matching record is merged at its current position;
2. an unseen key is appended once;
3. fields not present in the incoming patch remain unchanged.

This works for WebSocket events, push-open refreshes, REST polling and local
database reconciliation. ApkPy does not choose which source wins a conflict;
the application decides what data to pass.

## Native output

<div id="native-output"></div>

Small changes use small RecyclerView notifications:

```java
adapter.notifyItemRangeInserted(0, insertedCount);
adapter.notifyItemChanged(position);
adapter.notifyItemRemoved(position);
```

Prepend records the first visible position and pixel offset before insertion,
then restores that record after the adapter notification.

Merges and rollbacks may contain several different changes, so generated
Android uses `DiffUtil`:

```java
DiffUtil.DiffResult result = DiffUtil.calculateDiff(callback, true);
items.clear();
items.addAll(next);
result.dispatchUpdatesTo(adapter);
```

The callback compares the configured stable key for identity and the complete
JSON record for content. No Paging 3 dependency or backend adapter is added.
Projects that do not call a 1.2.2 mutation method receive no mutation history
fields, `DiffUtil` helper or extra generated code.

## Previewer parity

- prepend adjusts the virtual offset rather than jumping to the first row;
- update refreshes the affected pooled cell;
- remove closes the deleted position;
- merge and rollback keep the current absolute offset where possible;
- optimistic snapshots have the same IDs and first-snapshot behaviour as
  generated Android.

The English `playground/writehere.py` demo separates pagination from a mutation
lab. Each Android Activity mutates its own collection, matching the Previewer
instead of relying on cross-screen Python object state.

## Method contract

| Call | Result |
| --- | --- |
| `prepend_items(items)` | Returns the number inserted |
| `update_item(id, changes, key, optimistic)` | Returns `True` when a record matched |
| `remove_item(id, key, optimistic)` | Returns `True` when a record matched |
| `merge_items(items, key)` | Returns the number of changed or appended records |
| `rollback(id=None)` | Returns `True` when a snapshot was restored |
| `commit(id=None)` | Returns `True` when a snapshot was discarded |

`set_items()` is authoritative: it replaces the dataset and clears pending
optimistic snapshots.

## From release note to working app

The [Production Feeds tutorial](production-feeds.md) combines pagination,
refresh, keyed changes and rollback in one backend-shaped flow. It also contains
an interactive mutation lab that makes the otherwise invisible `commit()`
operation explicit.

Use [Compatibility and limits](compatibility.md) for the Previewer/Android
matrix, conditional-generation rules, verified test evidence and the release
checklist. Small runnable examples cover a social feed, product catalogue and
chat history.

## Deliberate boundary

This release does not implement offline synchronization, conflict resolution,
automatic retry queues or cache persistence. It supplies the efficient,
predictable collection operations those systems need.
