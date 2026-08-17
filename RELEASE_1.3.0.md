# ApkPy 1.3.0 — Data Core

ApkPy 1.3.0 introduces typed SQLite models, asynchronous CRUD, filters,
pagination, batch writes, atomic transactions and explicit migrations. Android
output remains native Java and SQLite; no Room or Python runtime is bundled.

## Small working example

```python
from apkpy_lib import Screen, db, label, run, virtual_collection

notes = db.model(
    "notes",
    fields={
        "id": db.integer(primary_key=True, auto_increment=True),
        "title": db.text(required=True, max_length=120),
        "favorite": db.boolean(default=False),
        "updated_at": db.datetime(default=db.now()),
    },
    indexes=[db.index("idx_notes_updated", ["updated_at"])],
)
schema = db.schema("notes_app", 1, [notes])

home = Screen(id="home", scroll=True)
status = label("Loading", screen=home)

def loaded(rows):
    feed.set_items(rows, has_more=len(rows) == 30)
    status.set_value(str(len(rows)) + " notes")

def failed(error):
    feed.finish_load()
    status.set_value("Database error · " + str(error))

def reload_notes():
    notes.find(
        order_by=[db.desc("updated_at")],
        limit=30,
        on_result=loaded,
        on_error=failed,
    )

feed = virtual_collection(
    [],
    template={"title": "{title}", "meta": "#{id}"},
    on_refresh=reload_notes,
    screen=home,
)

reload_notes()
run(start_screen=home)
```

## Main guarantees

- database work runs on one ordered background executor;
- UI callbacks return through the main thread;
- values are validated and bound, never pasted into SQL;
- batch operations and transactions roll back completely after a failure;
- migrations must be explicit and consecutive;
- destructive migration paths create a private backup and restore it on
  failure;
- unchanged projects do not receive Data Core code.

See [`docs/data-core.md`](docs/data-core.md) for the complete API and
[`docs/version-1.3.0.md`](docs/version-1.3.0.md) for the release overview.

## Knowledge Vault: complete data path

The release example is not a static mock-up. Library rows are loaded from the
typed model, while the Data Lab screen writes through the same generated
repository:

```python
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
        limit=30,
        offset=0,
        on_result=library_loaded,
        on_error=database_failed,
    )

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

Initial content is seeded atomically, so a partially-created workspace cannot
become visible:

```python
def seed(tx):
    tx.insert_many(notes, initial_notes)
    return tx.count(notes)

db.transaction(run=seed, on_result=seeded, on_error=database_failed)
```

## Validation completed locally

| Area | Checked behavior |
| --- | --- |
| Declarations | types, defaults, constraints, duplicate names and indexes |
| CRUD | insert, batch, get, find, update, delete, count and `NULL` |
| Queries | bound filters, text search, ordering, limit and offset |
| Transactions | ordered operations and complete rollback after failure |
| Migrations | v1→v2 preservation, missing paths, downgrade refusal and schema hash |
| Recovery | backup restoration after a failed destructive migration |
| Android | generated repositories, executor, callbacks and real Gradle APK |
| Compatibility | existing feed/rich-content suites and projects without models |

The separate [Benchmark Notes](BENCHMARKS.md) run measures a small in-memory UI
app across Android Python stacks. It is useful runtime evidence, but it is not
presented as a Data Core throughput benchmark.
