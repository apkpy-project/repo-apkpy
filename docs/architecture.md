# How ApkPy generates an Android app

ApkPy is a source compiler, not a Python runtime for Android. It reads the
supported Python model, builds an internal application tree and emits a normal
Android project.

## The compilation pipeline

```text
writehere.py
    │
    ├─ 1. Python AST parsing
    ├─ 2. screen, component and callback collection
    ├─ 3. CSS + Theme cascade resolution
    ├─ 4. feature detection and permission planning
    ├─ 5. Java, XML and resource emission
    └─ 6. Gradle project packaging or APK compilation
```

### 1. Parse supported Python

The compiler uses Python's abstract syntax tree. It does not execute arbitrary
Python and then attempt to copy a desktop interface. Calls such as `Screen`,
`button`, `db.query` and `audio.play_background` have explicit Android
generation rules.

```python
home = Screen(id="home")

def save():
    value = name_input.get_value()
    if value == "":
        toast("Enter a name")
        return
    storage.set("name", value)

button("Save", command=save, screen=home)
```

The callback becomes a Java method. Supported conditions, loops, conversions
and component operations are translated to their Java equivalents.

### 2. Build the screen tree

Each `Screen` becomes an Activity. Components attached with `screen=` become
root children; components attached with `parent=` are nested in the matching
container, card or layout.

```python
home = Screen(id="home", scroll=True)
summary = card(id="summary", variant="outlined", screen=home)
label("This month", variant="overline", parent=summary)
label("€ 1,240", variant="title", parent=summary)
```

For a scrollable screen, Android receives a `NestedScrollView` and one content
tree. Rich lists inside that screen use a non-nested representation so Android
does not fight over touch scrolling.

### 3. Resolve Theme and CSS

Style resolution follows a predictable cascade:

```text
Theme defaults → component selector → semantic variant → component ID
```

```python
app_theme = Theme(
    mode="dark",
    primary="#8B5CF6",
    surface="#18181B",
    text="#FAFAFA",
    radius=16,
)
```

```css
button { border-radius: var(--radius); }
button:outlined { border-color: var(--primary); }
save_button { background-color: #22D3EE; }
```

The ID rule wins. The generated project receives colors, drawable shapes,
dimensions and a Material-compatible `Theme.App` rather than a CSS engine at
runtime.

### 4. Detect features before emitting helpers

ApkPy scans what the app actually uses:

| Source feature | Generated Android addition |
| --- | --- |
| `https.*` or remote image | `INTERNET` permission and background networking |
| `audio.play_background` | foreground media service, MediaSession and notification |
| `auth.login` | OAuth callback Activity and deep-link manifest entry |
| advanced flex/grid | `ApkpyLayout` ViewGroup |
| image cache/effects | bounded cache, image workers and bitmap helpers |
| `skeleton` | one shared animation helper for the Activity |

A project that does not call one of these APIs does not receive its helper.
This keeps the ordinary path understandable and reduces unused code.

## Representative generated output

Given this declaration:

```python
button(
    "Continue",
    id="continue_button",
    variant="filled",
    command=continue_flow,
    screen=home,
)
```

the layout contains a Material button with a generated style/drawable, while
the Activity locates the view and attaches the callback. Simplified:

```xml
<com.google.android.material.button.MaterialButton
    android:id="@+id/continue_button"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:minHeight="48dp"
    android:text="Continue" />
```

```java
MaterialButton continue_button = findViewById(R.id.continue_button);
continue_button.setOnClickListener(view -> {
    pythonCallback_continue_flow();
});
```

The snippets above are shortened for explanation. The exact output also
contains resolved margins, colors, accessibility text, drawable references and
any imports required by the complete screen.

## Previewer parity

The Hot Previewer interprets the same screen tree and callbacks using desktop
widgets. It is deliberately a development feedback loop, not an Android
emulator.

| Behavior | Previewer | Android |
| --- | --- | --- |
| component state | in-memory desktop objects | native View state |
| key/value storage | encrypted local file | encrypted SharedPreferences |
| SQLite | Python sqlite3 | Android SQLiteDatabase |
| HTTP | background Python request | background HttpURLConnection |
| media | desktop media backend | foreground Android media service |
| date/time picker | desktop simulation | native Android dialog |

Use the Previewer to iterate. Use an emulator or real device to validate
permissions, services, manufacturer behavior and the final platform rendering.

## What remains in your control

- `writehere.py` remains the source of truth;
- `apkpy.toml` controls name, package ID, version and icon;
- Android Studio can inspect the generated project;
- signing keys remain local and must be backed up;
- server-side secrets and privileged authorization stay on your backend.

Continue with [Components and layouts](ui-components.md),
[Data, network and security](data-security.md), or the
[public API reference](api-reference.md).
