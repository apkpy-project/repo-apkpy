# Compatibility and limits

<section class="compat-hero">
  <span>RELEASE CONFIDENCE</span>
  <h2>Know what runs where.</h2>
  <p>ApkPy keeps the Previewer and generated Android project on one public API, but a desktop preview is not a device certification. This page separates verified behavior, generated output and application responsibilities.</p>
</section>

## Supported toolchain

| Part | Supported range | Notes |
| --- | --- | --- |
| Python | 3.8–3.13 | The package declares and tests this range |
| JDK | 17–21 | Use `apkpy doctor` to detect an incompatible JDK |
| Android SDK | Android Studio SDK or `apkpy setup` | A real SDK is required for Gradle compilation |
| Desktop Previewer | Windows, macOS or Linux with Tk support | Native device APIs may use a desktop simulation |
| Android output | Java, XML and Gradle project | No Python runtime is embedded in the APK |

## Production Feeds behavior

| Capability | Previewer | Generated Android |
| --- | --- | --- |
| Virtual list/grid | Reusable pooled widgets | Native `RecyclerView` |
| End prefetch | Viewport threshold | `RecyclerView.OnScrollListener` |
| Duplicate request guard | Loading latch | Loading latch |
| Page insertion | Preserves virtual offset | `notifyItemRangeInserted()` |
| Pull-to-refresh | Top gesture and `refresh()` | Native `SwipeRefreshLayout` |
| Prepend | Preserves visible offset | Range insert plus offset restore |
| Update one item | Repaints the affected pooled row | `notifyItemChanged()` |
| Remove one item | Closes the removed position | `notifyItemRemoved()` |
| Merge/rollback | Reconciles the visible dataset | Native `DiffUtil` |
| Optimistic history | Named in-memory snapshots | Named in-memory snapshots |

## Conditional generation

ApkPy scans the current application before adding support code:

| Your source uses | Generated project receives |
| --- | --- |
| Plain `virtual_collection()` | RecyclerView and its adapter |
| `on_end_reached` | Scroll listener, prefetch threshold and loading latch |
| `on_refresh` | `SwipeRefreshLayout` dependency and refresh wrapper |
| `prepend_items()` | Range insertion and scroll-offset restoration |
| `update_item()` / `remove_item()` | Targeted adapter notifications |
| `merge_items()` / `rollback()` | `DiffUtil` helper |
| Optimistic methods | Snapshot maps only for the affected collection |

An application that does not use feeds receives none of this runtime.

## Data Core behavior

| Capability | Previewer | Generated Android |
| --- | --- | --- |
| Database engine | Python `sqlite3` | Native `SQLiteOpenHelper` |
| Operation queue | One ordered worker | One ordered `ExecutorService` |
| Callback thread | Tk interface thread | Android main `Handler` |
| Batch binding | SQLite parameters in one transaction | Reused `SQLiteStatement` in one transaction |
| Schema metadata | `apkpy_schema_meta` | `apkpy_schema_meta` |
| Destructive migration | Private backup, transaction, restore | Private backup, transaction, restore |
| Model repository | Runtime model object | Generated repository per model |
| Foreign keys | SQLite foreign keys enabled | `onConfigure()` enables SQLite foreign keys |
| Relation include | One batched query per relation | One batched query per relation |
| Observation | Screen lifecycle + snapshot comparison | Activity lifecycle + generated invalidation tracker |

Projects without `db.model()` receive no typed repositories, data executor,
schema metadata or migration runtime. Legacy SQL calls remain available.

## What was validated for 1.3.2

<div class="verification-grid">
  <article><strong>185</strong><span>transpiler regression checks passed</span></article>
  <article><strong>21</strong><span>focused Data Core and Reactive Data checks passed</span></article>
  <article><strong>Gradle</strong><span>the generated Reactive Data demo Java compiled successfully</span></article>
  <article><strong>Strict docs</strong><span>the complete MkDocs site built without warnings treated as errors</span></article>
</div>

The generated Java was inspected for `SQLiteOpenHelper`, `SQLiteStatement`,
the single data executor, main-thread callback handler, repositories, indexes,
foreign keys, batched includes, observer generations, lifecycle hooks,
selective post-commit invalidation, sequential migrations, `OnScrollListener`,
`notifyItemRangeInserted`, `notifyItemChanged`, `notifyItemRemoved`, `DiffUtil`
and per-collection optimistic history. A separate plain collection test checks
that those helpers are omitted when unused.

These checks prove repeatable generation and compilation. They do not replace
testing an application's own backend, device permissions, OEM behavior or
release signing.

## Deliberate boundaries

Production Feeds does **not** provide:

- a backend, cursor format or API authentication;
- automatic offline synchronization;
- conflict resolution between REST, WebSocket and local database records;
- durable optimistic transactions after the process is killed;
- automatic retry queues or request deduplication by HTTP response ID;
- Paging 3, Room or Firebase as mandatory dependencies;
- item-level business rules such as who may edit or delete a record.

This division is intentional. ApkPy provides efficient native collection
behavior while the application retains control over product rules and data
ownership.

## Previewer versus device

Use the Previewer for layout, callbacks, data flow and rapid iteration. Use an
Android emulator or physical device before release for:

- permissions and background restrictions;
- notification channels and lock-screen controls;
- hardware codecs, camera, microphone, GPS and Bluetooth;
- lifecycle behavior after process recreation;
- network security configuration and certificate behavior;
- keyboard, accessibility, screen density and manufacturer-specific UI.

If the Previewer and Android differ, preserve the Python API and repair both
the Previewer and generator source. Editing generated Java alone is temporary;
the next `apkpy build` replaces it.

## Release checklist

- [ ] Create a new virtual environment and install the built wheel.
- [ ] Run one small example from the installed package.
- [ ] Generate a fresh Android project with `apkpy build`.
- [ ] Compile the generated project using JDK 17–21.
- [ ] Test narrow and wide screens in the Previewer and Android.
- [ ] Test every backend failure path and rollback.
- [ ] Confirm `has_more=False` stops repeated page requests.
- [ ] Check that refresh returns the authoritative first page.
- [ ] Review the generated manifest and dependencies.
- [ ] Only then create signing material or publish the package.

Start with the [Data Core guide](data-core.md), continue to
[Reactive Data](reactive-data.md), then inspect the complete
[1.3.2 release notes](version-1.3.2.md).

For broader release evidence and the stability contract, continue to
[Trust and maturity](trust-maturity.md). For the renderer boundary, use
[Previewer versus Android](preview-android.md).
