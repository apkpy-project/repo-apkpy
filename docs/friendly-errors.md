# Friendly errors

<section class="friendly-hero">
  <div>
    <span class="eyebrow">DEBUG THE APP, NOT THE TRACEBACK</span>
    <h2>Errors written for the person fixing them.</h2>
    <p>ApkPy turns common Python, Previewer, Data Core and Android build failures into short diagnostics that explain where the problem is, what was received and what to change.</p>
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
  <div><span>02</span><strong>Understand it</strong><p>Received and expected values in plain language.</p></div>
  <div><span>03</span><strong>Fix it</strong><p>Ordered actions based on the actual failure.</p></div>
</div>

## One error, without the noise

```text
APKPY E1401 - A value has the wrong type

Context:
  Previewer callback

Where:
  writehere.py:42
  upload_message.set("Uploading - " + percent + "%")

What happened:
  can only concatenate str (not "int") to str

How to fix:
  1. Convert the numeric value first, for example str(percent).
```

This output is intended to be useful without a community answer or a search
through a long traceback.

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
| `Received` / `Expected` | The contract mismatch when ApkPy knows both sides |
| `How to fix` | Specific next actions, ordered from most likely to least likely |
| `Technical details` | Original exception type and message |

## Error families

| Code | Area | Typical cause |
| --- | --- | --- |
| `E1001` | Python syntax | Missing colon, quote, bracket or parenthesis |
| `E1101` | Python environment | Required module is not installed in the active interpreter |
| `E1102` | Imports | Public name is misspelled, unavailable or from another ApkPy version |
| `E1201` | Python names | A component, callback or variable is used before it exists |
| `E1301` | Files | `writehere.py` or another required path cannot be found |
| `E1401` | Types | A callback received an integer, record or other unexpected value |
| `E1402` | Values | A value is outside the accepted ApkPy contract |
| `D2001` | Data Core | Invalid model, relation, filter, constraint or migration |
| `P3001` | Previewer | An application callback failed while handling an interaction |
| `C4001` | Compiler | Python could not be translated to the supported Android form |
| `B5001` | Build setup | JDK, Android SDK or Gradle is missing or incompatible |
| `E1999` | Application | Unexpected error that does not match a known family yet |

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
def upload_progress_changed(percent):
    upload_message.set("Uploading - " + str(percent) + "%")
```

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
