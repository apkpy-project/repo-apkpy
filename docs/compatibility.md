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

## The Python ApkPy translates

ApkPy reads your module and writes Java. It translates a fixed vocabulary of
Python rather than running it, so this list is the whole of it. Anything
outside it stops the build with [`U2033`](friendly-errors.md), naming what it
found -- it used to compile to nothing at all and leave you with a blank value.

**Control flow and values**

`if` / `elif` / `else`, `for` over a list or `range()`, `while`, `break`,
`continue`, `return`, `try` / `except` / `finally`, function definitions with
arguments, list and dict literals, indexing (`items[0]`, `items[-1]`,
`row["key"]`), `in`, list comprehensions, f-strings, `%` formatting and
`.format()`.

**Builtins**

`len`, `int`, `float`, `str`, `round`, `sorted`, `list`, `abs`, `min`, `max`,
`sum`, and the string methods `upper`, `lower`, `strip`, `split`, `replace`,
`zfill`.

**Lists**

`items.append(x)` works. A list written at module level that the app appends
to is kept in one process-wide store, so every screen sees the same list --
exactly as a module-level list behaves in Python.

**math**

Write `import math` and use the standard module; the Previewer gets Python's
own and the phone gets `java.lang.Math`.

`sqrt` `exp` `log` `log10` `fabs` `pow` `hypot` `floor` `ceil` `trunc`
`sin` `cos` `tan` `asin` `acos` `atan` `atan2` `degrees` `radians`
`pi` `e` `tau`

!!! note "Where numbers used to disagree, and no longer do"

    Three differences between the two runtimes were fixed rather than
    documented away, because each one was invisible until it mattered:

    - **`round(2.5)`** gave `2` in the Previewer and `3` on the phone. Python
      rounds a half to the even neighbour and `Math.round` always rounds up;
      the generator now emits `Math.rint`, which has Python's rule.
    - **`math.pow(10, 8)`** printed `1.0E8` on the phone and `100000000.0` in
      the Previewer. Java switches to exponent notation from 1e7 and Python
      only from 1e16, so numbers are now written out with Python's rule.
    - **`math.floor(2.7)`** printed `2.0` on the phone. `floor`, `ceil` and
      `trunc` return an `int` in Python 3, and now do here too.

    `math.sqrt(-1)` raises on both sides. Java would have returned `NaN` and
    put that word on screen; it now throws, so one `try` / `except` covers the
    Previewer and the phone together.

**Left out on purpose**

`math.log2`, because Java has no `Math.log2` and `log(x)/log(2)` disagrees
with Python on 8 of the first 60 powers of two. `math.inf` and `math.nan`,
because Python writes `inf` where Java writes `Infinity`. A translation that
is right most of the time is worse than one that says no.

**Not translated yet**

`re`, `json.dumps`, `base64`, `uuid`, `datetime` (use the `datetime` API),
string slicing (`text[0:2]`), `startswith`, `find`, `join`, `print`, and
multiple `except` clauses on one `try`.

**Never translatable**

`requests`, `numpy`, `pandas`, `os`, `pathlib`, `threading`, `sqlite3` and
anything else that needs a Python interpreter: there is none on the phone.
Use `https`, `files`, `db` and `background_job` instead. `U2033` names the
replacement when it recognises what you reached for.

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
