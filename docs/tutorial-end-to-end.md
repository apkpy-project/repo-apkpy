---
title: Build a native notes app end to end
description: Create, preview, generate, inspect and run a persistent Android app with ApkPy.
---

# Build a native notes app end to end

This tutorial builds **Knowledge Vault**, a small persistent notes app. You will
create a typed SQLite model, render its rows in a virtual collection, test the
same callbacks in the Previewer and generate a native Android Studio project.

The finished application source is available as
[`examples/tutorials/knowledge_vault.py`](https://github.com/apkpy-project/repo-apkpy/blob/main/examples/tutorials/knowledge_vault.py).

## 1. Check the toolchain

Create a clean virtual environment, install ApkPy and check Android tooling:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade apkpy
apkpy doctor
```

If the doctor reports a missing compatible JDK or Android SDK, run:

```powershell
apkpy setup
apkpy doctor
```

ApkPy supports Python 3.8–3.13 and JDK 17–21. Android Studio can supply the SDK
and JDK; `apkpy setup` is the assisted alternative.

## 2. Create the project

```powershell
apkpy start knowledge_vault
cd knowledge_vault
```

The application declaration lives in `writehere.py`. Replace it with the code
below.

```python
from apkpy_lib import (
    Screen, Theme, button, db, inputs, label, lifecycle, run,
    virtual_collection,
)


notes = db.model(
    "notes",
    fields={
        "id": db.integer(primary_key=True, auto_increment=True),
        "title": db.text(required=True, max_length=120),
        "favorite": db.boolean(default=False),
        "updated_at": db.datetime(default=db.now()),
    },
    indexes=[
        db.index("idx_notes_favorite_updated", ["favorite", "updated_at"]),
    ],
)

migration_1_2 = db.migration(
    1,
    2,
    operations=[
        db.add_column(notes, "favorite", db.boolean(default=False)),
        db.create_index(
            notes,
            "idx_notes_favorite_updated",
            ["favorite", "updated_at"],
        ),
    ],
)

db.schema(
    "notes_example",
    version=2,
    models=[notes],
    migrations=[migration_1_2],
)

home = Screen(id="home", scroll=True)
label("DATA CORE / 1.3.0", id="kicker", screen=home)
label("Notes that survive the screen.", id="title", screen=home)

title_input = inputs("Write a note title", id="note_title", screen=home)
status = label("Opening the database...", id="status", screen=home)


def failed(message):
    feed.finish_load()
    status.set_value("Database error · " + str(message))


def loaded(rows):
    feed.set_items(rows, has_more=False)
    status.set_value(str(len(rows)) + " notes stored locally")


def load_notes():
    notes.find(
        order_by=[db.desc("updated_at")],
        limit=100,
        on_result=loaded,
        on_error=failed,
    )


def created(note_id):
    title_input.set_value("")
    status.set_value("Saved note #" + str(note_id))
    load_notes()


def create_note():
    title = title_input.get_value()
    if title == "":
        status.set_value("Write a title first")
        return

    notes.insert(
        {"title": title, "favorite": False},
        on_result=created,
        on_error=failed,
    )


button("SAVE NOTE", command=create_note, screen=home)

feed = virtual_collection(
    [],
    template={
        "title": "{title}",
        "subtitle": "Stored in native SQLite",
        "meta": "#{id}",
    },
    on_refresh=load_notes,
    id="notes_feed",
    screen=home,
)

lifecycle(home, on_mount=load_notes)

style = """
home {
    background-color: var(--background);
    padding: 22px;
    gap: 12px;
}

kicker {
    color: var(--secondary);
    font-size: 11px;
    font-weight: bold;
}

title {
    color: var(--text);
    font-size: 28px;
    font-weight: bold;
    margin-bottom: 8px;
}

note_title {
    background-color: var(--surface);
    color: var(--text);
    border-color: var(--border);
    border-radius: 14px;
    padding: 14px;
}

button {
    background-color: var(--primary);
    color: var(--on-primary);
    border-radius: 14px;
    padding: 14px;
}

status {
    color: var(--secondary);
    font-size: 12px;
}

notes_feed {
    height: 430px;
    background-color: var(--background);
    item-background-color: var(--surface);
    title-color: var(--text);
    subtitle-color: var(--text-secondary);
    meta-color: var(--secondary);
    item-border-color: var(--border);
}
"""

run(
    start_screen=home,
    theme=Theme(
        mode="dark",
        primary="#6D5DFB",
        secondary="#50E3C2",
        background="#090B10",
        surface="#151922",
        text="#F7F8FA",
        text_secondary="#9EA8BA",
        border="#2A3140",
    ),
)
```

## 3. Understand the data flow

The application has one authoritative path:

1. `lifecycle(..., on_mount=load_notes)` requests stored notes when the screen
   first appears.
2. `notes.find(...)` runs on the ordered data worker, not the UI thread.
3. `loaded(rows)` returns on the UI thread and replaces the collection.
4. `notes.insert(...)` validates and writes the new row.
5. `created(note_id)` clears the input and reloads the authoritative dataset.

The app does not mutate the visible list before SQLite confirms the write. That
makes the first version easy to reason about. Optimistic UI is useful when a
remote request is slow, but it should include a rollback path.

## 4. Test in the Hot Previewer

```powershell
python writehere.py
```

Check these behaviors:

- an empty launch reports `0 notes stored locally`;
- pressing **SAVE NOTE** with an empty input shows validation feedback;
- a valid note appears after SQLite confirms the insert;
- restarting the Previewer keeps the note;
- pulling down from the top, or calling `feed.refresh()`, reloads the same data.

The Previewer database belongs to the local project. Delete it only when you
intentionally want a clean data test.

## 5. Generate the Android Studio project

```powershell
apkpy build
```

Open the generated ZIP/project in Android Studio. For this app, inspect:

- `ApkpyDatabase.java` for the shared `SQLiteOpenHelper`;
- the generated notes repository for bound CRUD statements;
- `apkpy_schema_meta` handling for version/hash history;
- the generated Activity and XML for the screen and collection;
- `build.gradle` for the small, feature-dependent dependency set.

The generated Java/XML is inspectable output. Keep `writehere.py` as the source
of truth because another build can replace manual changes to generated files.

## 6. Compile and run on Android

Use Android Studio's Run action, or let ApkPy generate and install a debug APK:

```powershell
apkpy run
```

Repeat the same five Previewer checks on an emulator or physical device. Also
rotate the device, test a narrow display and verify the soft keyboard does not
cover the input or action.

## 7. Diagnose a mismatch

If Previewer behavior differs from Android:

1. run `apkpy doctor`;
2. rebuild from the current `writehere.py`;
3. confirm Android Studio opened the newly generated project;
4. inspect Logcat for the first `FATAL EXCEPTION` or application error;
5. reduce the issue to the smallest screen and component;
6. report both Previewer and Android results.

Use the [troubleshooting guide](troubleshooting.md) for common build, layout,
database, Firebase, WebSocket, media and GPS failures.

## 8. Before a real release

- test a clean install and an upgrade from the previous schema version;
- test invalid input and a database error path;
- verify application ID, version and permissions in `apkpy.toml`;
- inspect the release artifact with Android Studio's APK Analyzer;
- test notification, storage and lifecycle behavior on a physical device;
- create signing material only when the package identity is final.

Continue with [Data Core](data-core.md), the
[essential API reference](reference/essential.md), or the
[release checklist](compatibility.md#release-checklist).
