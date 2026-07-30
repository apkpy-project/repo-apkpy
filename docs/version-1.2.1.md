# ApkPy 1.2.1 — Production Feeds { .release12-page-title }

<section class="release12-hero">
  <div>
    <span class="release12-kicker">VERSION 1.2.1 / RELEASE CANDIDATE</span>
    <h2>Long feeds should feel uneventful.</h2>
    <p>Production Feeds gives <code>virtual_collection()</code> guarded pagination, prefetching and pull-to-refresh. Pages arrive without moving the reader, duplicate scroll events do not duplicate requests and the application keeps ownership of its backend cursor.</p>
    <div class="release12-actions">
      <a class="md-button md-button--primary" href="#complete-example">Build a feed</a>
      <a href="#generated-android">Inspect the Android path <span>→</span></a>
    </div>
  </div>
  <div class="release12-signal" aria-label="Version 1.2.1 feed pipeline">
    <div class="release12-signal__head"><span>feeds / 1.2.1</span><strong>verified</strong></div>
    <div class="release12-signal__line"><span>01</span><b>observe</b><i>viewport</i></div>
    <div class="release12-signal__line"><span>02</span><b>guard</b><i>one request</i></div>
    <div class="release12-signal__line"><span>03</span><b>fetch</b><i>app cursor</i></div>
    <div class="release12-signal__line"><span>04</span><b>append</b><i>range insert</i></div>
    <div class="release12-signal__line"><span>05</span><b>continue</b><i>same offset</i></div>
  </div>
</section>

<div class="release12-status">
  <span class="release12-status__dot"></span>
  <strong>Small update, narrow contract</strong>
  <span>No Paging 3, mandatory backend or hidden cursor ownership.</span>
</div>

## What changed

`virtual_collection()` can now coordinate remote pages without becoming a data
framework:

```python
feed = virtual_collection(
    [],
    template={
        "image": "{avatar}",
        "title": "{author}",
        "subtitle": "{message}",
        "meta": "{time}",
    },
    on_end_reached=load_more,
    on_refresh=reload_feed,
    prefetch=4,
    screen=home,
)
```

<div class="release12-output">
  <div><span>on_end_reached</span><strong>One guarded page request</strong><p>Runs when the visible range enters the configured prefetch window.</p></div>
  <div><span>append_items</span><strong>Keep rows and position</strong><p>Adds the new page instead of replacing the complete collection.</p></div>
  <div><span>on_refresh</span><strong>Start a new generation</strong><p>Pull from the top or call <code>refresh()</code> with the same callback.</p></div>
  <div><span>has_more</span><strong>Finish explicitly</strong><p>Close the end path with <code>False</code>; refresh may open it again.</p></div>
</div>

## Feed pattern explorer

<div class="release12-explorer" data-release12-explorer>
  <div class="release12-explorer__tabs" role="tablist" aria-label="Production feed patterns">
    <button type="button" role="tab" aria-selected="true" data-release12-tab="timeline">Timeline</button>
    <button type="button" role="tab" aria-selected="false" data-release12-tab="catalog">Catalogue</button>
    <button type="button" role="tab" aria-selected="false" data-release12-tab="history">Chat history</button>
    <button type="button" role="tab" aria-selected="false" data-release12-tab="failure">Retry</button>
  </div>
  <div class="release12-explorer__stage" aria-live="polite">
    <article data-release12-panel="timeline">
      <span>INSTAGRAM / X / REDDIT</span><h3>Prefetch before the reader reaches the final post.</h3>
      <p>Append the next cursor page and leave every visible row exactly where it was.</p>
      <dl><div><dt>Template</dt><dd>Avatar, author, body and timestamp.</dd></div><div><dt>Finish</dt><dd>Pass has_more=False when the API returns no cursor.</dd></div></dl>
    </article>
    <article data-release12-panel="catalog" hidden>
      <span>STORE / DELIVERY / SPOTIFY</span><h3>The same loading contract works in a grid.</h3>
      <p>Two-column cards keep their image, price, click callback and full source record while pages are inserted.</p>
      <dl><div><dt>Layout</dt><dd>layout="grid" with application-selected columns.</dd></div><div><dt>Insertion</dt><dd>Only the appended native adapter range is notified.</dd></div></dl>
    </article>
    <article data-release12-panel="history" hidden>
      <span>MESSAGES / ACTIVITY</span><h3>A bounded request protects older history.</h3>
      <p>Scroll gestures can produce many native events. The loading latch admits one callback until application code completes it.</p>
      <dl><div><dt>Success</dt><dd>append_items(page) releases the latch.</dd></div><div><dt>Empty</dt><dd>finish_load(has_more=False) closes the history.</dd></div></dl>
    </article>
    <article data-release12-panel="failure" hidden>
      <span>RECOVERABLE NETWORK ERROR</span><h3>Keep the current page and make retry explicit.</h3>
      <p>A failed request does not need a fake item or a rebuilt list. Release the latch and let the next gesture or retry button try again.</p>
      <dl><div><dt>Error</dt><dd>finish_load(has_more=True)</dd></div><div><dt>Retry</dt><dd>The next boundary event is accepted once.</dd></div></dl>
    </article>
  </div>
</div>

## Complete example

<div id="complete-example"></div>

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

!!! tip "Retry without rebuilding"
    Use `feed.finish_load(has_more=True)` after a recoverable error. Existing
    rows stay visible and the next end event may retry. Use
    `has_more=False` only when the server has confirmed the end.

## Method contract

| Call | Data | Loading state | `has_more` |
| --- | --- | --- | --- |
| `append_items(page, has_more=True)` | Appends `page` | Finished | Uses argument |
| `set_items(first_page, has_more=True)` | Replaces all items | Finished, including refresh | Uses argument |
| `finish_load(has_more=True)` | Unchanged | Finished | Uses argument |
| `refresh()` | Unchanged until callback finishes | Starts guarded refresh | Temporarily reopened |

Both `append_items()` and `set_items()` accept a Python list or a JSON-array
string. This lets an HTTP callback pass `json_get(body, "items")` directly.

## Generated Android

<div id="generated-android"></div>

The generated Activity uses ordinary RecyclerView APIs:

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

The guard runs before application code:

```java
if (production_feedLoading || !production_feedHasMore) return;
production_feedLoading = true;
pythonCallback_load_more();
```

Appending a page updates only the inserted range:

```java
int oldSize = production_feed_items.size();
production_feed_items.addAll(page);
production_feed_adapter.notifyItemRangeInserted(oldSize, page.size());
```

When `on_refresh` exists, the RecyclerView is wrapped by
`SwipeRefreshLayout`. Without `on_refresh`, neither the wrapper nor the
dependency is generated.

## Previewer behaviour

- Near-end requests use the same prefetch threshold.
- Append preserves the current list/grid scroll offset.
- The loading state is compact and does not replace the records.
- A pull at the top runs `on_refresh`; `feed.refresh()` calls the same path.
- Duplicate requests are ignored until the app calls `append_items()`,
  `set_items()` or `finish_load()`.
- Templates, click callbacks and complete JSON records remain intact.

The repository demonstration has two screens: an English social timeline and
a two-column object catalogue with a deliberate first failure, retry, refresh
and no-more-results state.

## What 1.2.1 does not own

ApkPy does not choose a server cursor, invent page URLs or persist a remote
dataset automatically. This release does not include Paging 3, offline sync,
automatic cache invalidation or item-level diffing. The current application
dataset remains in memory.

That boundary is intentional: Production Feeds makes the UI path reliable
without forcing every application into one backend architecture.
