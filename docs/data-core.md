---
title: Data Core
description: Typed SQLite models, asynchronous CRUD, filters, transactions and explicit migrations in ApkPy 1.3.0.
---

# Data Core

ApkPy 1.3.0 adds a typed layer above the existing SQLite API. You declare the
shape of local data once; ApkPy validates it in the Previewer and generates a
native `SQLiteOpenHelper`, a shared data executor and one Java repository per
model for Android.

There is no Python interpreter, Room database or WebView inside the APK.
Projects that do not declare `db.model()` keep the old output and receive none
of the new repositories or migration runtime.

## A complete model

```python
from apkpy_lib import db

notes = db.model(
    "notes",
    fields={
        "id": db.integer(primary_key=True, auto_increment=True),
        "title": db.text(required=True, max_length=120),
        "content": db.text(default=""),
        "favorite": db.boolean(default=False),
        "priority": db.integer(default=0, min_value=0, max_value=5),
        "metadata": db.json(optional=True),
        "attachment": db.blob(optional=True),
        "updated_at": db.datetime(default=db.now()),
    },
    indexes=[
        db.index(
            "idx_notes_favorite_updated",
            ["favorite", "updated_at"],
        ),
    ],
)

schema = db.schema(
    name="my_app",
    version=1,
    models=[notes],
)
```

`datetime` values are stored as UTC epoch milliseconds. `json` is validated
before insertion and decoded again in query results. A blob should stay small;
large images, audio and documents belong in the file system, with their path
stored in the database.

### Field options

| Option | Purpose |
| --- | --- |
| `required=True` | Refuse missing and null values |
| `optional=True` | Explicitly allow null |
| `default=value` | Supply a value when insertion omits the field |
| `primary_key=True` | Mark the model identity field |
| `auto_increment=True` | Integer primary keys only |
| `unique=True` | Add a uniqueness constraint |
| `min_value` / `max_value` | Bound numeric values |
| `max_length` | Bound text length |
| `choices=[...]` | Accept only a known set of values |

Indexes may contain one or several fields. Pass `unique=True` to
`db.index()` for a composite unique index. Create indexes for filters and sort
paths that the interface actually uses; unnecessary indexes make writes more
expensive.

## Asynchronous CRUD

Typed operations never run SQLite work on the UI thread. Results and errors
return through callbacks on the interface thread.

```python
def created(note_id):
    status.set_value("Saved note #" + str(note_id))
    load_page()

def failed(message):
    status.set_value("Database error · " + str(message))

notes.insert(
    {
        "title": title_input.get_value(),
        "content": content_input.get_value(),
        "favorite": favorite_input.get_value(),
        "priority": priority_input.get_value(),
        "metadata": {"source": "editor"},
    },
    on_result=created,
    on_error=failed,
)
```

The result contract is small and predictable:

| Operation | `on_result` value |
| --- | --- |
| `insert()` | inserted ID |
| `insert_many()` | number of inserted records |
| `get()` | one object, or `""` when absent |
| `find()` | `JsonRows`, iterable and accepted by collection components |
| `update()` | affected row count |
| `delete()` | affected row count |
| `count()` | matching row count |

### Read one row

```python
def note_loaded(note):
    if note == "":
        status.set_value("Note not found")
    else:
        title_input.set_value(note["title"])
        content_input.set_value(note["content"])

notes.get(42, on_result=note_loaded, on_error=failed)
```

### Find, filter, order and page

```python
def page_loaded(rows):
    notes_feed.set_items(rows, has_more=len(rows) == 30)

notes.find(
    filters=[
        db.eq("favorite", True),
        db.contains("title", search_input.get_value()),
        db.gte("priority", 2),
    ],
    order_by=[db.desc("updated_at")],
    limit=30,
    offset=0,
    on_result=page_loaded,
    on_error=failed,
)
```

Available comparisons are `eq`, `ne`, `gt`, `gte`, `lt`, `lte`,
`contains`, `starts_with`, `ends_with`, `in_` and `is_null`. Combine them with
`and_()` and `or_()`; order with `asc()` and `desc()`.

Every filter value is bound as a SQLite parameter. ApkPy does not concatenate
user input into generated SQL.

### Update and delete

```python
notes.update(
    {"favorite": True, "priority": 5},
    filters=[db.eq("id", note_id)],
    on_result=lambda affected: load_page(),
    on_error=failed,
)

notes.delete(
    filters=[db.eq("id", note_id)],
    on_result=lambda affected: load_page(),
    on_error=failed,
)
```

An empty filter list intentionally targets all records. Keep the filter next
to destructive UI actions so the scope is easy to review.

## Batches and transactions

`insert_many()` compiles prepared bindings once and runs the complete batch in
one transaction. If any record fails validation or a database constraint, no
record from that batch is committed.

For several different operations, use `db.transaction()`:

```python
def create_workspace(tx):
    workspace_id = tx.insert(
        workspaces,
        {"name": "Research"},
    )
    tx.insert_many(
        notes,
        [
            {"title": "Inbox", "priority": 1},
            {"title": "Decisions", "priority": 4},
        ],
    )
    return workspace_id

db.transaction(
    run=create_workspace,
    on_result=workspace_created,
    on_error=failed,
)
```

Inside `run`, use only the supported `tx.insert`, `insert_many`, `get`, `find`,
`update`, `delete` and `count` operations. They execute in order on one database
connection. An exception rolls the complete transaction back.

## Explicit migrations

Existing users already have data. Changing the current model is not enough:
increase the schema version and provide every consecutive step.

```python
migration_1_2 = db.migration(
    from_version=1,
    to_version=2,
    operations=[
        db.add_column(
            notes,
            "favorite",
            db.boolean(default=False),
        ),
        db.create_index(
            notes,
            "idx_notes_favorite_updated",
            ["favorite", "updated_at"],
        ),
    ],
)

schema = db.schema(
    name="my_app",
    version=2,
    models=[notes],
    migrations=[migration_1_2],
)
```

Supported operations are:

- `create_table(model)`;
- `add_column(model, name, field)`;
- `rename_column(model, old, new)`;
- `create_index(model, name, fields, unique=False)`;
- `rename_index(model, old, new)`;
- `drop_index(model, name)`;
- `rename_table(model, new_name)`;
- `sql(statement, params)` for an exceptional, parameterized change.

A migration must move exactly one version. ApkPy refuses missing steps,
downgrades and a changed schema hash without a version increase.

Operations that may destroy information require `destructive=True`. Before
such a path, ApkPy checkpoints and closes SQLite, writes a private backup and
then applies the sequence in one transaction. Failure restores the backup and
keeps the old version.

```python
migration_2_3 = db.migration(
    2,
    3,
    operations=[
        db.sql(
            "DELETE FROM notes WHERE archived = ?",
            [True],
            destructive=True,
        ),
    ],
    destructive=True,
)
```

## Generated Android architecture

When a typed schema is present, ApkPy emits:

- `ApkpyDatabase.java`: one shared `SQLiteOpenHelper`, schema metadata,
  validation and migration logic;
- `ApkpyDataExecutor.java`: a single ordered `ExecutorService` and a main
  thread `Handler`;
- one `<Model>Repository.java` per model, with prepared statements,
  projections, filters and result conversion.

Bulk insertion uses `SQLiteStatement` in a single transaction. Activities call
repositories and receive callbacks; they do not own database connections.

```java
private static final ExecutorService IO =
    Executors.newSingleThreadExecutor();
private static final Handler MAIN =
    new Handler(Looper.getMainLooper());
```

The Android database contains `apkpy_schema_meta`, which records schema name,
version, hash and migration history. This is internal; application records
remain in the declared tables.

## Existing SQL API

The original `db.execute()`, `db.query()`, `db.begin()`, `db.commit()` and
`db.rollback()` calls remain available. A typed schema and legacy SQL can exist
in the same app, but new code should use models where validation and migrations
matter.

Typed models do not encrypt every field automatically. Use `crypto.encrypt()`
before inserting values that must be recoverable, or store secrets through the
encrypted `storage` API. Passwords should be hashed, not encrypted.

## Knowledge Vault pattern

A screen can own its filters and let the model own database execution. The
callback receives rows on the interface thread and can hand them directly to a
virtual collection:

```python
page_size = 30
page_offset = 0

def library_loaded(rows):
    library_feed.set_items(rows, has_more=len(rows) == page_size)
    library_status.set_value(
        "Loaded " + str(len(rows)) + " notes"
    )

def database_failed(message):
    library_feed.finish_load()
    library_status.set_value("Database error · " + str(message))

def reload_library():
    notes.find(
        filters=[
            db.contains("title", search_input.get_value()),
            db.eq("favorite", favorites_input.get_value()),
        ],
        order_by=[
            db.desc("priority"),
            db.desc("updated_at"),
        ],
        limit=page_size,
        offset=page_offset,
        on_result=library_loaded,
        on_error=database_failed,
    )
```

Writes do not update the list until SQLite confirms them:

```python
def create_note():
    notes.insert(
        {
            "title": title_input.get_value(),
            "content": content_input.get_value(),
            "favorite": favorite_input.get_value(),
            "priority": priority_input.get_value(),
        },
        on_result=lambda note_id: reload_library(),
        on_error=database_failed,
    )
```

This keeps the database as the source of truth. Feed-level optimistic mutation
APIs remain useful for remote requests, but local Data Core writes can wait
for their fast repository callback and avoid a second rollback state.

## Validation boundary

The 1.3.0 test set covers declarations, constraints, CRUD, `NULL`, JSON,
datetime conversion, compound indexes, ordering, paging, atomic batches,
transaction rollback, migration paths, schema hashes, downgrade refusal and
destructive backup recovery. The generated Knowledge Vault project also
compiles with Gradle as a real Android debug APK.

The [cross-framework Android benchmark](benchmark.md) intentionally uses an
in-memory list. It measures the small application/runtime floor and should not
be read as a SQLite performance test.

## Current boundary

Data Core 1.3.0 deliberately does not include relations, observable queries,
automatic offline synchronization, conflict resolution or persistent network
jobs. It provides the safe local model, query and migration foundation those
features will build on.

The runnable **Knowledge Vault** example combines indexed search, favorite
filters, pagination into `virtual_collection`, create/update/delete, a batch
transaction and v1-to-v2 migration.
