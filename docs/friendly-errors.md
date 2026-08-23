# Friendly errors

<section class="friendly-hero">
  <div>
    <span class="eyebrow">DEBUG THE APP, NOT THE TRACEBACK</span>
    <h2>Errors written for the person fixing them.</h2>
    <p>ApkPy turns Python, Previewer, Data Core, compiler and Android build failures into short diagnostics that explain where the problem is, why it happened, what was received and what to change.</p>
    <div class="friendly-hero__actions">
      <a class="md-button md-button--primary" href="#run-with-friendly-startup-diagnostics">Start with <code>apkpy preview</code></a>
      <a href="#error-families">Browse the error codes <span>↓</span></a>
    </div>
  </div>
  <aside>
    <span>What stays available</span>
    <strong>The original exception is never discarded.</strong>
    <p>Use the short correction first. Turn on debug mode only when you need the complete Python traceback.</p>
  </aside>
</section>

<div class="friendly-contract">
  <div><span>01</span><strong>Find it</strong><p>The relevant file, line and source statement.</p></div>
  <div><span>02</span><strong>Understand it</strong><p>Why the rule exists, plus the received and expected values.</p></div>
  <div><span>03</span><strong>Fix it</strong><p>Ordered actions based on the actual failure.</p></div>
</div>

## One error, without the noise

```text
APKPY E1401 - Text and a non-text value were joined

Context:
  Previewer callback

Where:
  writehere.py:42
  total_label.set_value("Items: " + len(rows))

What happened:
  can only concatenate str (not "int") to str

Why this happened:
  Python does not convert automatically when joining with +. This is the
  most common Previewer callback failure, because progress values, counts
  and ids arrive as numbers.

Expected:
  every part of the expression as text

How to fix:
  1. Convert the non-text value first, for example 'Items: ' + str(len(rows)).

Read more:
  https://repo-apkpy.pages.dev/friendly-errors/#p3001-previewer-runtime
```

This output is intended to be useful without a community answer or a search
through a long traceback. **Why this happened** is the part that matters most:
it explains the rule that was broken, not just the symptom.

## Run with friendly startup diagnostics

Use the ApkPy command when testing an application:

```powershell
apkpy preview
```

This catches import and startup failures as well as errors raised after ApkPy
has loaded. Tkinter callback failures use the same format automatically while
the Previewer is running.

For a Python syntax error, `apkpy preview` is important: plain
`python writehere.py` fails before Python can import ApkPy, so no library can
replace that interpreter-owned syntax traceback.

## Read a diagnostic

| Section | Meaning |
| --- | --- |
| `APKPY E1102` | Stable category code that can be searched in the docs or an issue |
| `Context` | The layer that failed, such as Previewer, Data Core or Android compiler |
| `Where` | Application file, line, column and source line when available |
| `What happened` | The concise failure reported by Python or ApkPy |
| `Why this happened` | The rule that was broken, and why ApkPy enforces it |
| `Received` / `Expected` | The contract mismatch when ApkPy knows both sides |
| `How to fix` | Specific next actions, ordered from most likely to least likely |
| `Read more` | The page covering this family |
| `Technical details` | Original exception type and message |

## Error families

Every message ApkPy raises is mapped to one of these codes, with its own
explanation and corrections. The code is stable, so it can be searched here or
quoted in an issue.

### E1001 Python and environment

| Code | Meaning |
| --- | --- |
| `E1001` | Python could not parse the file: a missing colon, quote, bracket or parenthesis |
| `E1101` | A required module is not installed in the interpreter that is running |
| `E1102` | An ApkPy public name is misspelled or comes from another version |
| `E1201` | A name is used above the line that creates it |
| `E1301` | A required file or path was not found |
| `E1401` | Text and a non-text value were combined |
| `E1402` | A value is outside an ApkPy contract that has no more specific code |
| `E1999` | An unexpected error that does not match a known family yet |

### U2001 Components and arguments

| Code | Meaning |
| --- | --- |
| `U2001` | A component was created without `screen=` or `parent=` |
| `U2002` | `screen=` received something that is not a `Screen` |
| `U2003` | An argument that needs an ApkPy component received something else |
| `U2004` | A callback argument received a value instead of a function |
| `U2005` | An argument that only accepts an ApkPy factory (`action()`, `db.index()`, ...) |
| `U2006` | A value outside the accepted set for that argument |
| `U2007` | A numeric argument of the wrong kind, or outside its range |
| `U2008` | An argument with the wrong container type (dict, list, string) |
| `U2009` | `aspect_ratio` was not a ratio ApkPy can divide |
| `U2010` | `responsive()` arrangements do not hold the same components |
| `U2011` | An icon name that is not in the Material set |
| `U2012` | A structural limit was exceeded (nesting depth, payload size) |
| `U2013` | A feed operation that requires `virtual_collection()` |
| `U2014` | An argument that needs a specific ApkPy object, such as a `Theme` |

### D2001 Data Core

| Code | Meaning |
| --- | --- |
| `D2001` | A name SQLite cannot accept as an identifier |
| `D2002` | The schema version and the migration chain do not line up |
| `D2003` | A migration would drop data without `destructive=True` |
| `D2004` | A required column has no value |
| `D2005` | A field or index name that does not exist in the model |
| `D2006` | A value that does not match the column's declared type |
| `D2007` | A relation declaration or use that is not valid |
| `D2008` | A schema or model declaration that is not valid |
| `D2009` | A field or index not built with a `db.*` helper |
| `D2010` | A migration step with no Java equivalent |
| `D2011` | A query filter that does not suit the field |
| `D2012` | Field options that contradict each other |
| `D2013` | `offset=` without `limit=` |

### P3001 Previewer runtime

| Code | Meaning |
| --- | --- |
| `P3001` | An application callback failed and matched no more specific rule |
| `P3002` | A component or value is `None` at that point |
| `P3003` | A key is missing from a record |
| `P3004` | A list was read past its end |
| `P3005` | A string was used as if it were a record |
| `P3006` | Two incompatible types were combined |
| `P3007` | A value was called as if it were a function |
| `P3008` | A callback signature does not match what ApkPy passes |
| `P3009` | A function has no argument with that name |
| `P3010` | A division used zero as the divisor |
| `P3011` | `int()` or `float()` received text that is not a number |

### N6001 Network and URLs

| Code | Meaning |
| --- | --- |
| `N6001` | A URL without its scheme (`https://`, `wss://`) |
| `N6002` | A WebSocket connection that did not survive the handshake |
| `N6004` | The routing service found no route between the points |

### J7001 Background jobs

| Code | Meaning |
| --- | --- |
| `J7001` | A `background_job()` option with no WorkManager equivalent |
| `J7002` | `run=` names a function that is not in this file |
| `J7003` | `observe(on_change=)` did not receive a one-argument function |

A job body that raises is reported in full as well, with the job name, the
attempt number, the payload keys and the fact that the item returns to the
queue. It runs off the interface thread, so nothing else would show it:

```text
Context:
  Background job 'outbox' - attempt 1 of run=deliver_message() raised, so the
  item goes back to the queue and is retried with backoff (payload keys: text)
```

An observer that raises is reported the same way, noting that the queue kept
running while the interface stopped receiving updates.

### C4001 Android compiler

| Code | Meaning |
| --- | --- |
| `C4001` | A construct with no supported Android translation |
| `C4002` | A real-time search filter that could not become a `TextWatcher` |
| `C4003` | `db.model()` declared without a `db.schema()` |

`C4002` matters more than it looks: the Previewer runs the filter lambda in
Python, so search keeps working there, while the APK would be generated without
it. ApkPy reports the divergence rather than shipping it silently.

Compiler diagnostics point at the line in `writehere.py`, not at ApkPy's own
source. The compiler reads the application as text, so it carries the
declaration's line through to the report.

### B5001 Android build

| Code | Meaning |
| --- | --- |
| `B5001` | The toolchain is incomplete: JDK, Android SDK or Gradle is missing |
| `B5002` | Gradle ran on a Java version it does not support |
| `B5003` | The Android SDK is incomplete or its licences are not accepted |
| `B5004` | Android could not link the generated resources (AAPT) |
| `B5005` | The generated Java did not compile |
| `B5006` | Gradle ran out of memory, or its daemon died |
| `B5007` | Gradle could not download a dependency |
| `B5008` | The APK was built but the device refused the install |
| `B5009` | A Gradle failure whose signature ApkPy does not recognise yet |

`apkpy run` and `apkpy release` stream Gradle's output and keep it, so a failure
is explained instead of leaving a wall of log to scroll through. `Received`
leads with the line that names the file, the position and the reason:

```text
Received:
  ...\app\src\main\java\com\apkpy\app\Screen_homeActivity.java:30: error: cannot find symbol
  symbol:   variable thisSymbolDoesNotExist
  location: class Screen_homeActivity
```

Even `B5009` carries Gradle's own reason and the path of the generated project.

## Common fixes

### A public API name is misspelled

```python
# Wrong
from apkpy_lib import bottom_nva

# Right
from apkpy_lib import bottom_nav
```

For close matches, `E1102` includes a `Did you mean` suggestion. If the name is
correct, confirm that installation and execution use the same interpreter:

```powershell
python -m pip show apkpy
python -c "import apkpy_lib; print(apkpy_lib.__file__)"
```

### A callback joins text and a number

```python
def rows_loaded(rows):
    total_label.set_value("Items: " + str(len(rows)))
```

Values that cross to Android are always text, so `uploads` progress,
`background_job` status and picked file sizes need no conversion. Values
produced in Python -- `len()`, arithmetic, a count -- still do.

### A Data Core declaration is rejected

`D2001` keeps the exact Data Core cause and adds a likely correction. Check the
field names, relation aliases, foreign-key type, schema version and migration
path shown in the diagnostic.

```python
folder_id = db.integer(optional=True)

folder_notes = db.relation(
    "folder_notes",
    parent=folders,
    child=notes,
    foreign_key="folder_id",
    on_delete="set_null",
)
```

`set_null` requires an optional foreign key because SQLite must be allowed to
write `NULL` when the parent is removed.

### The Android toolchain is incomplete

`B5001` reports each required tool separately. Repair and verify it with:

```powershell
apkpy setup
apkpy doctor
```

## Full traceback and opt-out

Friendly mode hides traceback noise; it does not discard it. Enable the full
traceback for debugging:

```powershell
apkpy preview --debug
```

or for any run:

```powershell
$env:APKPY_DEBUG="1"
python writehere.py
```

To temporarily restore Python's default uncaught-exception output before
importing ApkPy:

```powershell
$env:APKPY_FRIENDLY_ERRORS="0"
python writehere.py
```

When reporting a problem, include the complete `APKPY` diagnostic, the ApkPy
version and the smallest `writehere.py` that reproduces it. Do not include API
keys, tokens or personal data.
