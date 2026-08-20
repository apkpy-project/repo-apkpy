---
title: Reactive Data
description: One-to-many SQLite relations, batched includes and lifecycle-safe observable queries in ApkPy 1.3.1.
---

# Reactive Data

ApkPy 1.3.1 extends [Data Core](data-core.md) with controlled one-to-many
relations and observable queries. A successful write invalidates only the
models that changed; active queries that depend on those models rerun on the
ordered database executor and deliver their result on the interface thread.

There is no polling, Room, LiveData, Flow, WebView or Python runtime in the
Android application. The callback remains explicit: your app decides whether
the new rows update a `virtual_collection()`, a counter or another component.

## Declare a one-to-many relation

```python
from apkpy_lib import db

folders = db.model(
    "folders",
    fields={
        "id": db.integer(primary_key=True, auto_increment=True),
        "name": db.text(required=True),
    },
)

notes = db.model(
    "notes",
    fields={
        "id": db.integer(primary_key=True, auto_increment=True),
        "folder_id": db.integer(required=True),
        "title": db.text(required=True),
        "updated_at": db.datetime(default=db.now()),
    },
)

folder_notes = db.relation(
    "folder_notes",
    parent=folders,
    child=notes,
    foreign_key="folder_id",
    parent_as="folder",
    children_as="notes",
    on_delete="cascade",
)

schema = db.schema(
    "reactive_vault",
    version=1,
    models=[folders, notes],
    relations=[folder_notes],
)
```

The parent must have a primary key. The child foreign key must exist and have
the same type. Relation names and aliases must be unique inside their model
scope.

### Delete policies

| Policy | Result when the parent is deleted |
| --- | --- |
| `restrict` | SQLite refuses deletion while children exist |
| `cascade` | SQLite deletes the related children in the same commit |
| `set_null` | SQLite clears the child key; the field must use `optional=True` |

ApkPy enables `PRAGMA foreign_keys=ON` in both the Previewer and generated
Android database. These are real SQLite constraints, not checks performed only
by the Python-facing API.

## Load related records

Pass one or more aliases to `include`:

```python
folders.find(
    include=["notes"],
    order_by=[db.asc("name")],
    on_result=folders_loaded,
    on_error=database_failed,
)

notes.get(
    selected_note_id,
    include=["folder"],
    on_result=note_loaded,
    on_error=database_failed,
)
```

The first query adds a `notes` list to every returned folder. The second adds
a `folder` object, or `None` when the optional parent does not exist.

Includes never execute one query per row. ApkPy reads the main page first and
then runs one bound query per included relation, grouping keys into safe
chunks. `limit` and `offset` apply to the main records; child collections are
ordered by their primary key.

Only one level is accepted in 1.3.1. An include such as
`"notes.attachments"` fails with a clear error instead of hiding an expensive
recursive query.

## Observe a query

```python
def notes_changed(rows):
    notes_feed.set_items(rows)
    update_count.set(update_count.get() + 1)

def database_failed(message):
    error_message.set_value(str(message))

notes_live = notes.observe(
    filters=[db.eq("folder_id", active_folder_id.get())],
    order_by=[db.desc("updated_at")],
    include=["folder"],
    limit=50,
    screen=notes_screen,
    on_change=notes_changed,
    on_error=database_failed,
)
```

`screen` is required. It gives the subscription an unambiguous lifecycle:

- `on_resume`: run the initial query or catch up after returning;
- `on_pause`: suspend delivery and database reruns;
- `on_destroy`: detach the subscription permanently.

Every callback receives `JsonRows` on the UI thread. The data layer does not
import or mutate UI components itself.

### Change the active query

```python
def search_changed(text):
    notes_live.update_query(
        filters=[
            db.eq("folder_id", active_folder_id.get()),
            db.contains("title", text),
        ],
        order_by=[db.desc("updated_at")],
    )
```

Omitted arguments keep their previous value. `update_query()` increments a
generation number, ignores any late result from the previous configuration
and immediately schedules the new query while the screen is active.

Use `notes_live.refresh()` to force the same query. Use
`notes_live.close()` when a subscription should end before the screen is
destroyed.

## Writes require no manual reload

```python
def create_note():
    notes.insert(
        {
            "folder_id": active_folder_id.get(),
            "title": title_input.get_value(),
        },
        on_result=lambda note_id: status.set_value(
            "Saved #" + str(note_id)
        ),
        on_error=database_failed,
    )
```

After the commit, the `notes` model is invalidated. Any active observer that
depends on `notes` reruns. A folder query with `include=["notes"]` also
depends on that model and receives the updated child list.

Updates, deletes and successful batches follow the same rule. A transaction
collects all changed models and publishes one combined invalidation only after
commit. Failed writes and rollbacks do not notify observers.

When several writes arrive while a query is already running, invalidations
are coalesced into at most one follow-up query. Identical result snapshots do
not trigger duplicate `on_change` callbacks unless `refresh()` explicitly
forces delivery.

## Generated Android architecture

When `observe()` is used, ApkPy adds two small conditional files:

- `ApkpyDataInvalidationTracker.java`, shared across Activities;
- `ApkpyQuerySubscription.java`, which owns lifecycle, generations,
  coalescing and snapshot comparison.

Repositories notify the tracker only after a successful commit. Includes and
foreign keys stay in `ApkpyDatabase.java`; all reads still run through the
single `ApkpyDataExecutor`. Projects without `db.relation()` receive no
relation metadata or hydration path. Projects without `observe()` receive no
tracker or subscription runtime.

## Migrations and existing databases

Adding a relation changes the schema hash and requires a version increase.
New tables can receive a foreign key through normal table creation. SQLite
cannot attach a physical foreign-key clause to an existing table with
`ALTER COLUMN`, so an existing child table must be rebuilt in a documented
manual migration: create the replacement table, copy validated rows, replace
the old table and recreate indexes.

Do not add the relation declaration at the old version. ApkPy will reject the
changed hash rather than silently running without the expected constraint.

## Current limits

Version 1.3.1 intentionally supports:

- one-to-many relations only;
- one include level;
- eager, batched loading through `include`;
- changes committed through ApkPy data APIs.

It does not include one-to-one or many-to-many helpers, recursive trees, lazy
loading, cross-process observation, external SQLite change detection,
offline-first synchronization or conflict resolution. Transaction reads stay
flat in this version.

See [Version 1.3.1](version-1.3.1.md) for the release validation and
[Data Core](data-core.md) for models, CRUD, filters, transactions and
migrations.
