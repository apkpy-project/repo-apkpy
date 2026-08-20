# ApkPy 1.3.1 — Reactive Data

ApkPy 1.3.1 adds one-to-many SQLite relations and lifecycle-safe observable
queries to Data Core. The generated APK still contains native Java/SQLite
code, not Room, polling or a Python runtime.

It also replaces raw callback and compiler tracebacks for common failures with
friendly diagnostics: stable error codes, the relevant `writehere.py` line,
the original cause and a concrete correction. Developers can restore the full
traceback with `apkpy preview --debug` or `APKPY_DEBUG=1`.

## Small working example

```python
from apkpy_lib import Screen, db, run, virtual_collection

folders = db.model("folders", fields={
    "id": db.integer(primary_key=True, auto_increment=True),
    "name": db.text(required=True),
})
notes = db.model("notes", fields={
    "id": db.integer(primary_key=True, auto_increment=True),
    "folder_id": db.integer(required=True),
    "title": db.text(required=True),
})

folder_notes = db.relation(
    "folder_notes", parent=folders, child=notes,
    foreign_key="folder_id", parent_as="folder",
    children_as="notes", on_delete="cascade",
)
schema = db.schema(
    "reactive_vault", 1, [folders, notes],
    relations=[folder_notes],
)

library = Screen("library")
feed = virtual_collection([], template={"title": "{title}"}, screen=library)

live = notes.observe(
    include=["folder"],
    screen=library,
    on_change=lambda rows: feed.set_items(rows),
)

run(start_screen=library)
```

## Guarantees

- foreign keys are enabled in Previewer and Android;
- includes use batched bound queries, not one query per record;
- observers run the first query when their screen resumes;
- committed writes invalidate only relevant model dependencies;
- transaction changes are announced once after commit;
- rollback and failed writes produce no invalidation;
- in-flight invalidations are coalesced and stale generations are ignored;
- repeated snapshots are not delivered twice;
- projects that do not observe data receive no observer runtime.

## Local verification

- 21 focused Data Core/Reactive Data tests passed;
- 8 focused friendly-diagnostic tests passed;
- 167 existing transpiler checks passed;
- the generated Knowledge Vault Live Java compiled successfully with Gradle;
- the generated source contains real `FOREIGN KEY ... ON DELETE CASCADE`,
  batched includes, a shared invalidation tracker and Activity lifecycle hooks.

### Conditional-overhead control

The same small Data Core-only app was generated once with 1.3.0 and once with
1.3.1, then compiled from clean Android projects with the same JDK, Android
SDK and Gradle 8.7 invocation. It declares no relation and no observer.

| Control | Generated source | Debug APK | Clean Gradle build |
| --- | ---: | ---: | ---: |
| 1.3.0 | 49,691 bytes | 5,626,715 bytes | 17.715 s |
| 1.3.1 | 51,158 bytes | 5,627,103 bytes | 17.778 s |

The 1.3.1 APK added **388 bytes (0.0069%)** in this control. Both projects
contained 14 generated files, and the 1.3.1 output contained no relation
class, include hydration, invalidation tracker or query subscription. Startup
was not reported because no Android device or emulator was connected during
this run.

See [`docs/reactive-data.md`](docs/reactive-data.md) for the API and
[`docs/version-1.3.1.md`](docs/version-1.3.1.md) for limits and migration
guidance.

See [`docs/friendly-errors.md`](docs/friendly-errors.md) for the diagnostic
families, examples, debug mode and opt-out behavior.

## Project continuity

ApkPy remains proprietary while it is actively developed and maintained. The
core may be opened later; if active development is ever permanently abandoned,
the maintainer commits to releasing the core as open source so that existing
applications and knowledge are not trapped behind an unmaintained package.

A pause or slower release cadence does not by itself change the licence. Any
transition will be announced explicitly together with the source and its new
licence. See [`docs/project-continuity.md`](docs/project-continuity.md) for the
complete policy.
