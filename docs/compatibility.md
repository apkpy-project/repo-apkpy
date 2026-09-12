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

**Control flow**

`if` / `elif` / `else`, `while`, `break`, `continue`, `return`,
`try` / `except` / `finally`, and function definitions with arguments.
A condition compares with `==`, `!=`, `<`, `>`, `<=` or `>=`, tests membership
with `in` and `not in`, and joins those with `and`, `or` and `not`.

`in` is membership against a list, tuple, set or dict written in the source, a
list kept at module level, or a `split()` call. Against anything else it
searches text. That is decided from the source, never from the running value.

`for` loops over `range()`, over a list or tuple written in the source, over a
list held in a name, and over the result of `split()`. A `range()` index is a
number, so `i + 1` and `i % 2` are arithmetic.

**Values**

Assignment to one name, and `+=`, `-=`, `*=`, `/=` and `%=`. List and dict
literals, indexing (`items[0]`, `items[-1]`, `row["key"]`), slicing text
(`text[0:2]`), the conditional expression `a if test else b`, and f-strings
with `{value}`, `{value:.2f}` and `{value:,.2f}`.

A list comprehension is translated in one place: the search callback,
`on_change=lambda q: notes.set_items([...])`.

**Arithmetic**

`+`, `-`, `*`, `/` and `%` work between values ApkPy knows are numbers: a
number written in the source, `int(...)` or `float(...)`, a name assigned from
one of those, and a `range()` index. `/` always gives a float, as in Python.
Text read from an input or from storage stays text until you convert it, so
`float(price) * 2` works and `price * 2` stops the build. Between values that
are not known to be numbers, `+` joins text.

**Builtins and text**

`len`, `int`, `float`, `str`, `round`, `list`, `abs`, `min`, `max`, `sum`, and
the string methods `upper`, `lower`, `strip`, `replace`, `split`, `title`,
`find`, `count`, `join`, `startswith` and `endswith`; `isdigit` in a condition.

`split()` gives a list with Python's rules: the separator is text rather than a
regular expression, empty parts are kept, `maxsplit` is honoured, and with no
separator it splits on runs of whitespace.

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

**Not translated -- the build stops and says so**

Each of these stops the build with `U2033`, naming the line and a form that
does compile:

- `%` formatting (`"n=%s" % n`) and `.format()` -- use an f-string;
- `sorted`, `zfill`, `lstrip`, `rstrip`, and a slice with a step (`text[::2]`);
- `is`, and chained comparisons such as `0 < x < 10`;
- a comprehension anywhere except the search callback, module level included;
- unpacking (`a, b = parts`, `for key, value in pairs:`), `a = b = 0`,
  `for ... else`, and assigning to an item or an attribute (`row["k"] = v`,
  `status.text = v`);
- `not x`, `a or b`, or a comparison used as a value instead of a condition;
- a tuple or a set used as a value, and a `for` over text, a dict or a set;
- arithmetic on a value not known to be a number (`price * 2` on text from an
  input), and repeating text with `*`;
- an f-string format other than `.2f` or `,.2f`;
- `json.dumps`, `base64`, `uuid`, `datetime` (use the `datetime` API), `print`,
  and more than one `except` clause on a `try`.

**Differences that do not stop the build**

Everything on the phone is text, and ApkPy decides from the source rather than
from the running value. These four still give a different answer from Python:

- `text[0]` on text reads it as a list and gives empty text. Slice it instead:
  `text[0:1]`.
- `+` on a function's parameter joins text: `n + 1` with `n` set to `1` shows
  `11`. Convert it first: `int(n) + 1`.
- `x in name`, where `name` is a local variable holding a list, searches the
  list's text. Test the call itself (`x in text.split(",")`), a list written in
  the source, or a list kept at module level.
- A list shown with `set_value()` reads `["a","b"]` on the phone and
  `['a', 'b']` in the Previewer.

### Regular expressions — 1.7.0 subset

`re.match`, `re.search`, `re.sub` and `re.findall` now have an Android
translation in ApkPy **1.7.0**. Use constant Unicode patterns and flags inside callbacks/helper
functions; input and replacement text may be dynamic.

```python
import re

def check_text():
    text = message.get_value()
    found = re.search(r"\bREF-(?P<code>[0-9]{4,8})\b", text, re.I)
    if found is not None:
        reference.set_value(found.group("code"))
    else:
        reference.set_value("No reference")
    matches = re.findall(r"#[\w]+", text)
    tags.set_items(matches)
    cleaned.set_value(re.sub(r"\s+", " ", text).strip())
```

`match` checks the beginning, not the entire string: add `\Z` for full-input
format checks. Match objects support `group`, `groups`, `start`, `end`, `span`
and checks against `None`; group selectors must be constant. `findall` returns
strings without captures, a capture with one group, and grouped sequences with
multiple captures. Assign its result before iteration or passing it to a list.

Supported flags are `IGNORECASE`, `MULTILINE`, `DOTALL`, `VERBOSE`, `ASCII` and
`UNICODE` (including short aliases and `|` combinations). Named groups,
lookahead, greedy/lazy quantifiers, common character classes and boundaries
are supported. Replacements use Python's `\1` / `\g<name>` syntax; `$` is literal.

Dynamic patterns, `re.compile`, `fullmatch`, `finditer`, `split`, bytes,
callable replacements, lookbehind, pattern backreferences, conditionals,
atomic groups and possessive repetition are outside this subset. Unsupported
forms fail the build with `C1701`; do not assume everything accepted by the
desktop `re` module can be exported to Android.

The generator fixes Unicode classes and case folding to the **build Python's**
tables. Use the same Python version for preview and build. Regex calls are
synchronous: bound input sizes and avoid pathological patterns. Java's native
regex helper adds no Python runtime, permission or Android dependency, and is
only emitted when used. This supports format validation and text extraction;
it does not prove an email address exists or replace server-side validation.

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
