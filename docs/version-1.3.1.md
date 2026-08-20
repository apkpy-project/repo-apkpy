---
title: Version 1.3.1
description: ApkPy 1.3.1 Reactive Data, relations, observable queries and friendly diagnostics.
---

# ApkPy 1.3.1 — Reactive Data

Version 1.3.1 connects the typed SQLite foundation from 1.3.0 to live
interfaces. It adds controlled one-to-many relations, real foreign keys,
batched relation loading and lifecycle-safe observable queries.

## What changed

- `db.relation()` with `restrict`, `cascade` and `set_null` delete policies;
- `relations=[...]` in `db.schema()`;
- `include=[...]` in typed `find()` and `get()`;
- `model.observe()` with initial delivery, selective invalidation and
  snapshot deduplication;
- `refresh()`, `update_query()` and `close()` observer controls;
- Activity lifecycle integration without polling;
- one invalidation after a successful multi-model transaction;
- conditional Android tracker and subscription output.

The release also introduces shared
[friendly diagnostics](friendly-errors.md) for Previewer callbacks, imports,
Data Core, compiler failures and Android toolchain setup. Full tracebacks stay
available through `apkpy preview --debug`.

## Knowledge Vault Live

The new English demonstration uses a separate `knowledge_vault_live.db` and
two screens:

- **Folders** loads each folder with its note collection and demonstrates a
  physical cascading foreign key;
- **Notes** observes the selected folder, changes its SQL filter while the user
  searches and updates after create, edit, favorite and delete operations
  without a manual reload call.

```python
notes_live = notes.observe(
    filters=[db.eq("folder_id", active_folder_id.get())],
    order_by=[db.desc("updated_at")],
    include=["folder"],
    limit=100,
    screen=notes_screen,
    on_change=lambda rows: notes_feed.set_items(rows),
    on_error=notes_failed,
)
```

## Native output

The generated Android project continues to use `SQLiteOpenHelper`. Relation
includes are loaded with one additional bound query per relation rather than
one query per record. `ApkpyDataInvalidationTracker` and
`ApkpyQuerySubscription` are emitted only when observation is used.

The generated Activities resume, pause and close only their own subscriptions.
Callbacks are delivered through the existing main-thread handler, while all
SQLite work remains on the single ordered executor.

## Validation completed locally

| Area | Result |
| --- | --- |
| relation declarations and aliases | passed |
| `restrict`, `cascade` and `set_null` | passed |
| parent→children and child→parent includes | passed |
| observer lifecycle and dynamic queries | passed |
| rollback without invalidation | passed |
| compiler/transpiler regression suite | 167 passed |
| focused Data Core and Reactive Data tests | 21 passed |
| focused friendly-diagnostic tests | 8 passed |
| generated Java compilation with Gradle | passed |
| unused observer runtime | omitted |

The Gradle validation caught and fixed two generator-only issues before this
release was published: escaped SQL identifiers in batched relation reads
and cross-screen nullable observer handles.

### Same-app conditional-overhead control

To test the “pay only when used” rule, the same Data Core-only control app was
generated with 1.3.0 and 1.3.1. It declares neither `db.relation()` nor
`observe()`. Both clean projects were compiled sequentially with JDK 21, the
same Android SDK and Gradle 8.7 with every one of the 31 tasks executed.

| Control | Generated files | Generated source | Debug APK | Clean build |
| --- | ---: | ---: | ---: | ---: |
| ApkPy 1.3.0 | 14 | 49,691 bytes | 5,626,715 bytes | 17.715 s |
| ApkPy 1.3.1 | 14 | 51,158 bytes | 5,627,103 bytes | 17.778 s |

The APK difference was **388 bytes, or 0.0069%**. More importantly, inspection
of the 1.3.1 control confirmed that it contains no generated relation class,
relation hydration, `ApkpyDataInvalidationTracker` or
`ApkpyQuerySubscription`. The small source difference is the public
`include`-compatible API surface and validation, not an unused reactive
runtime. Startup was deliberately left unreported because no device or
emulator was connected; no estimate was invented.

## Migration note

Adding relation metadata changes the schema and requires increasing its
version. Existing tables that need a physical foreign-key clause must be
rebuilt in an explicit manual migration; ApkPy does not pretend SQLite can add
that constraint in place.

## Deliberate limits

This release does not add many-to-many or recursive relations, lazy loading,
Room, LiveData, Flow, polling, offline synchronization or conflict resolution.
Only changes committed through ApkPy APIs automatically invalidate typed
observers.

Read the [Reactive Data guide](reactive-data.md) for the complete contract and
the [Data Core guide](data-core.md) for the 1.3.0 foundation. Project ownership
and future source availability are documented separately in the
[project continuity policy](project-continuity.md); current releases remain
proprietary unless an explicit open-source transition is published.
