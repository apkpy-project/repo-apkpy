---
title: Version 1.3.0
description: ApkPy 1.3.0 Data Core release.
---

# ApkPy 1.3.0 — Data Core

Version 1.3.0 turns ApkPy's low-level SQLite support into a declarative data
layer suitable for real local application state.

```python
notes = db.model(
    "notes",
    fields={
        "id": db.integer(primary_key=True, auto_increment=True),
        "title": db.text(required=True, max_length=120),
        "favorite": db.boolean(default=False),
        "metadata": db.json(optional=True),
        "updated_at": db.datetime(default=db.now()),
    },
    indexes=[
        db.index("idx_notes_favorite_updated", ["favorite", "updated_at"]),
    ],
)

schema = db.schema("notes_app", version=1, models=[notes])
```

## What changed

- typed `integer`, `real`, `text`, `boolean`, `datetime`, `json` and `blob`
  fields;
- defaults, nullability, primary keys, uniqueness, numeric bounds, text
  length, choices and composite indexes;
- asynchronous insert, batch insert, get, find, update, delete and count;
- parameterized filters, ordering, limit and offset pagination;
- atomic multi-model transactions;
- explicit consecutive migrations and stored schema hashes;
- private backup and restore around destructive migration paths;
- generated `SQLiteOpenHelper`, one ordered executor and per-model Java
  repositories, without Room or a Python runtime.

## Knowledge Vault

The 1.3.0 example is an English two-screen notes app. **Library** performs
indexed search, favorite filtering and paged reads. **Data Lab** creates,
updates, deletes and archives records in an atomic batch. Initial records are
seeded through a transaction and the schema declares its v1-to-v2 path.

It also demonstrates the important UI states: loading, no matching data, an
explicit database error, retry and the end of pagination.

### Create and reload

```python
def created(note_id):
    status.set_value("Saved note #" + str(note_id))
    reload_library()

notes.insert(
    {
        "title": title_input.get_value(),
        "content": content_input.get_value(),
        "favorite": favorite_input.get_value(),
        "priority": priority_input.get_value(),
    },
    on_result=created,
    on_error=database_failed,
)
```

### Seed several records atomically

```python
def seed_library(tx):
    tx.insert_many(notes, initial_notes)
    return tx.count(notes)

db.transaction(
    run=seed_library,
    on_result=lambda total: status.set_value(str(total) + " notes ready"),
    on_error=database_failed,
)
```

## Migration safety

The data layer refuses to guess how an old database should change. A schema
change at the same version is an error; a missing migration step is an error;
a downgrade is refused. Destructive paths require an explicit flag and create
a recoverable private backup first.

```python
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
```

## Native output and validation

The release candidate has been checked against the existing feed, rich-content
and Gradle-generation suites. Its generated Knowledge Vault project compiles
as a real Android debug APK. The generated source uses `SQLiteStatement`, a
single data executor, main-thread callbacks, repository-specific queries and
sequential migration code.

| Validation | Result |
| --- | --- |
| typed declarations and constraints | passed |
| CRUD, JSON, dates, ordering and pagination | passed |
| batch and transaction rollback | passed |
| v1→v2 data preservation | passed |
| failed destructive migration recovery | passed |
| generated Android Gradle compilation | passed |
| projects without typed models | no Data Core output |

The [Android benchmark](benchmark.md) is documented separately because it
measures a small in-memory UI app, not SQLite query throughput.

Read the [complete Data Core guide](data-core.md) for the API contract,
examples, migration rules and current limits.

## Not in this release

Relations, observable queries, automatic offline-first synchronization,
conflict resolution and persistent background jobs remain outside 1.3.0.
The low-level SQL API remains compatible.
