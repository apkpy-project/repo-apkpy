import os
import sqlite3
import tempfile
import threading
import unittest

from apkpy_lib import DataCoreError, SQLiteAPI
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.features.feeds import normalize_items
from apkpy_lib.ui import ComponentDef, JsonRows


def make_database():
    database = SQLiteAPI()
    directory = tempfile.mkdtemp(prefix="apkpy-data-")
    database._path = os.path.join(directory, "test.db")
    return database


def await_result(start):
    event = threading.Event()
    received = {}

    def success(value):
        received["value"] = value
        event.set()

    def failure(error):
        received["error"] = error
        event.set()

    future = start(success, failure)
    future.result(timeout=5)
    assert event.wait(5)
    if "error" in received:
        raise AssertionError(received["error"])
    return received.get("value")


class DataCoreRuntimeTests(unittest.TestCase):
    def test_offscreen_component_keeps_value_for_async_callbacks(self):
        search = ComponentDef("inputs", placeholder="Search")
        search._initial_value = "Visual"
        self.assertEqual(search.get_value(), "Visual")

    def test_json_rows_feed_bridge_keeps_database_rows(self):
        rows = JsonRows('[{"id": 1, "title": "Kept by the feed"}]')
        self.assertEqual(
            normalize_items(rows),
            [{"id": 1, "title": "Kept by the feed"}],
        )

        feed = ComponentDef("virtual_collection", items=[])

        def stale_preview(*_args):
            raise RuntimeError("destroyed preview widget")

        feed._feed_update_fn = stale_preview
        self.assertEqual(feed.set_items(rows, has_more=False), 1)
        self.assertEqual(feed._initial_value[0]["title"], "Kept by the feed")
        self.assertIsNone(feed._feed_update_fn)

    def test_field_and_model_declarations_reject_invalid_contracts(self):
        database = make_database()
        with self.assertRaisesRegex(DataCoreError, "both required and optional"):
            database.text(required=True, optional=True)
        with self.assertRaisesRegex(DataCoreError, "integer primary key"):
            database.text(primary_key=True, auto_increment=True)
        with self.assertRaisesRegex(DataCoreError, "min_value"):
            database.integer(min_value=5, max_value=1)

        model = database.model("valid_items", fields={
            "id": database.integer(primary_key=True),
            "name": database.text(),
        })
        with self.assertRaisesRegex(DataCoreError, "Duplicate model"):
            database.model("valid_items", fields={"id": database.integer()})

        another = make_database()
        with self.assertRaisesRegex(DataCoreError, "unknown field"):
            another.model(
                "indexed_items",
                fields={"id": another.integer(primary_key=True)},
                indexes=[another.index("idx_missing", ["missing"])],
            )
        self.assertEqual(model.primary_key, "id")

    def test_preview_crud_filters_json_and_ordering(self):
        database = make_database()
        notes = database.model(
        "notes",
        fields={
            "id": database.integer(primary_key=True, auto_increment=True),
            "title": database.text(required=True, max_length=40),
            "favorite": database.boolean(default=False),
            "priority": database.integer(default=0, min_value=0, max_value=5),
            "metadata": database.json(optional=True),
            "updated_at": database.datetime(default=database.now()),
        },
        indexes=[database.index("idx_notes_favorite_updated", ["favorite", "updated_at"])],
    )
        database.schema("test_app", 1, [notes])

        first_id = await_result(lambda ok, fail: notes.insert(
        {"title": "Alpha", "favorite": True, "metadata": {"source": "test"}},
        on_result=ok, on_error=fail,
    ))
        self.assertEqual(first_id, 1)
        self.assertEqual(await_result(lambda ok, fail: notes.insert_many(
        [{"title": "Beta", "priority": 2}, {"title": "Gamma", "priority": 4}],
        on_result=ok, on_error=fail,
        )), 2)

        rows = await_result(lambda ok, fail: notes.find(
        filters=[database.or_(database.eq("favorite", True), database.gte("priority", 4))],
        order_by=[database.desc("updated_at")], limit=20, offset=0,
        on_result=ok, on_error=fail,
    ))
        self.assertEqual(len(rows), 2)
        self.assertIn(rows[0]["metadata"], ({"source": "test"}, None))
        self.assertEqual(await_result(lambda ok, fail: notes.count(
        filters=[database.contains("title", "a")], on_result=ok, on_error=fail,
        )), 3)
        self.assertEqual(await_result(lambda ok, fail: notes.update(
        {"favorite": True}, filters=[database.eq("id", 2)],
        on_result=ok, on_error=fail,
        )), 1)
        self.assertEqual(await_result(lambda ok, fail: notes.delete(
        filters=[database.eq("id", 3)], on_result=ok, on_error=fail,
        )), 1)


    def test_preview_validation_and_transaction_rollback(self):
        database = make_database()
        rows = database.model("rows", fields={
        "id": database.integer(primary_key=True, auto_increment=True),
        "name": database.text(required=True, max_length=8),
    })
        database.schema("rollback_app", 1, [rows])

        def invalid(tx):
            tx.insert(rows, {"name": "valid"})
            tx.insert(rows, {"name": "this is too long"})

        event = threading.Event()
        errors = []
        future = database.transaction(
        run=invalid, on_result=lambda _: event.set(),
        on_error=lambda error: (errors.append(error), event.set()),
    )
        try:
            future.result(timeout=5)
        except Exception:
            pass
        self.assertTrue(event.wait(5))
        self.assertTrue(errors)
        self.assertEqual(await_result(lambda ok, fail: rows.count(on_result=ok, on_error=fail)), 0)


    def test_schema_hash_detects_version_not_incremented(self):
        database = make_database()
        first = database.model("items", fields={"id": database.integer(primary_key=True)})
        database.schema("hash_app", 1, [first])

        changed = SQLiteAPI()
        changed._path = database._path
        model = changed.model("items", fields={
        "id": changed.integer(primary_key=True),
        "title": changed.text(default=""),
    })
        with self.assertRaisesRegex(DataCoreError, "without increasing"):
            changed.schema("hash_app", 1, [model])

    def test_v1_to_v2_migration_preserves_rows_and_adds_index(self):
        first = make_database()
        notes_v1 = first.model("notes", fields={
            "id": first.integer(primary_key=True, auto_increment=True),
            "title": first.text(required=True),
        })
        first.schema("migration_app", 1, [notes_v1])
        await_result(lambda ok, fail: notes_v1.insert(
            {"title": "Preserved"}, on_result=ok, on_error=fail,
        ))

        upgraded = SQLiteAPI()
        upgraded._path = first._path
        notes_v2 = upgraded.model("notes", fields={
            "id": upgraded.integer(primary_key=True, auto_increment=True),
            "title": upgraded.text(required=True),
            "favorite": upgraded.boolean(default=False),
        }, indexes=[upgraded.index("idx_notes_favorite", ["favorite"])])
        migration = upgraded.migration(1, 2, [
            upgraded.add_column(notes_v2, "favorite", upgraded.boolean(default=False)),
            upgraded.create_index(notes_v2, "idx_notes_favorite", ["favorite"]),
        ])
        schema = upgraded.schema("migration_app", 2, [notes_v2], [migration])

        row = await_result(lambda ok, fail: notes_v2.get(
            1, on_result=ok, on_error=fail,
        ))
        self.assertEqual(row["title"], "Preserved")
        self.assertFalse(row["favorite"])
        self.assertEqual(schema.info()["version"], 2)
        with sqlite3.connect(upgraded._path) as connection:
            index_names = {
                item[1] for item in connection.execute("PRAGMA index_list('notes')")
            }
            history = connection.execute(
                "SELECT history FROM apkpy_schema_meta WHERE id=1"
            ).fetchone()[0]
        self.assertIn("idx_notes_favorite", index_names)
        self.assertIn('"from": 1', history)

    def test_missing_migration_and_downgrade_are_refused(self):
        first = make_database()
        item_v1 = first.model("items", fields={
            "id": first.integer(primary_key=True),
        })
        first.schema("version_app", 1, [item_v1])

        missing = SQLiteAPI()
        missing._path = first._path
        item_v2 = missing.model("items", fields={
            "id": missing.integer(primary_key=True),
            "title": missing.text(default=""),
        })
        with self.assertRaisesRegex(DataCoreError, "Missing migration"):
            missing.schema("version_app", 2, [item_v2])

        newer = make_database()
        item_new = newer.model("items", fields={
            "id": newer.integer(primary_key=True),
        })
        newer.schema("downgrade_app", 2, [item_new])
        older = SQLiteAPI()
        older._path = newer._path
        item_old = older.model("items", fields={
            "id": older.integer(primary_key=True),
        })
        with self.assertRaisesRegex(DataCoreError, "Downgrade"):
            older.schema("downgrade_app", 1, [item_old])

    def test_failed_destructive_migration_restores_private_backup(self):
        first = make_database()
        notes_v1 = first.model("notes", fields={
            "id": first.integer(primary_key=True, auto_increment=True),
            "title": first.text(required=True),
        })
        first.schema("backup_app", 1, [notes_v1])
        await_result(lambda ok, fail: notes_v1.insert(
            {"title": "Still here"}, on_result=ok, on_error=fail,
        ))

        broken = SQLiteAPI()
        broken._path = first._path
        notes_v2 = broken.model("notes", fields={
            "id": broken.integer(primary_key=True, auto_increment=True),
            "title": broken.text(required=True),
        })
        migration = broken.migration(
            1, 2,
            [broken.sql("INSERT INTO missing_table(value) VALUES (?)", ["boom"], destructive=True)],
            destructive=True,
        )
        with self.assertRaisesRegex(DataCoreError, "missing_table"):
            broken.schema("backup_app", 2, [notes_v2], [migration])

        self.assertTrue(os.path.exists(first._path + ".backup-v1"))
        with sqlite3.connect(first._path) as connection:
            self.assertEqual(
                connection.execute("SELECT title FROM notes WHERE id=1").fetchone()[0],
                "Still here",
            )
            version = connection.execute(
                "SELECT version FROM apkpy_schema_meta WHERE id=1"
            ).fetchone()[0]
        self.assertEqual(version, 1)

    def test_insert_many_is_atomic_and_query_validation_is_safe(self):
        database = make_database()
        records = database.model("records", fields={
            "id": database.integer(primary_key=True, auto_increment=True),
            "kind": database.text(required=True, choices=["note", "task"]),
            "score": database.real(default=0, min_value=0, max_value=10),
            "payload": database.json(optional=True),
        })
        database.schema("batch_app", 1, [records])

        event = threading.Event()
        errors = []
        future = records.insert_many(
            [
                {"kind": "note", "score": 2.5, "payload": {"ok": True}},
                {"kind": "invalid", "score": 3},
            ],
            on_result=lambda _: event.set(),
            on_error=lambda error: (errors.append(error), event.set()),
        )
        with self.assertRaises(Exception):
            future.result(timeout=5)
        self.assertTrue(event.wait(5))
        self.assertTrue(errors)
        self.assertEqual(await_result(lambda ok, fail: records.count(
            on_result=ok, on_error=fail,
        )), 0)
        with self.assertRaisesRegex(DataCoreError, "Unknown filter field"):
            database._compile_filter(records, database.eq("missing", 1))
        with self.assertRaisesRegex(DataCoreError, "requires a text field"):
            database._compile_filter(records, database.contains("score", "2"))


SOURCE = r'''
from apkpy_lib import *

notes = db.model(
    "notes",
    fields={
        "id": db.integer(primary_key=True, auto_increment=True),
        "title": db.text(required=True, max_length=120),
        "favorite": db.boolean(default=False),
        "updated_at": db.datetime(default=db.now()),
    },
    indexes=[db.index("idx_notes_favorite_updated", ["favorite", "updated_at"])],
)
migration_1_2 = db.migration(
    from_version=1,
    to_version=2,
    operations=[db.add_column(notes, "favorite", db.boolean(default=False))],
)
schema = db.schema("apkpy_app", version=2, models=[notes], migrations=[migration_1_2])

home = Screen(id="home", scroll=True)
status = label("Waiting", id="status", screen=home)

def loaded(rows):
    status.set_value("Loaded " + str(len(rows)))

def failed(error):
    status.set_value(error)

def seed(tx):
    tx.insert_many(notes, [{"title": "One"}, {"title": "Two"}])

def load_notes():
    notes.find(
        filters=[db.eq("favorite", False), db.contains("title", "o")],
        order_by=[db.desc("updated_at")], limit=30, offset=0,
        on_result=loaded, on_error=failed,
    )

button("Load", command=load_notes, screen=home)
db.transaction(run=seed, on_result=lambda result: load_notes(), on_error=failed)
run(start_screen=home)
'''


class DataCoreCompilerTests(unittest.TestCase):
    def test_android_codegen_is_opt_in_and_emits_repositories_executor_and_migrations(self):
        files = translate_python_to_android(SOURCE, package="com.example.data")
        self.assertNotIn("error.txt", files, files.get("error.txt"))
        self.assertIn("java/ApkpyDatabase.java", files)
        self.assertIn("java/ApkpyDataExecutor.java", files)
        self.assertIn("java/NotesRepository.java", files)
        database = files["java/ApkpyDatabase.java"]
        activity = files["java/Screen_homeActivity.java"]
        self.assertIn("extends SQLiteOpenHelper", database)
        self.assertIn("SQLiteStatement", database)
        self.assertIn("idx_notes_favorite_updated", database)
        self.assertIn("ALTER TABLE", database)
        self.assertIn("newSingleThreadExecutor", files["java/ApkpyDataExecutor.java"])
        self.assertIn("NotesRepository.find", activity)
        self.assertIn("transactionAsync", activity)
        self.assertNotIn("pythonCallback_seed", activity)

        legacy = translate_python_to_android(
        'from apkpy_lib import *\nhome=Screen(id="home")\nlabel("Legacy", screen=home)\nrun(start_screen=home)'
    )
        self.assertNotIn("java/ApkpyDatabase.java", legacy)
        self.assertNotIn("java/ApkpyDataExecutor.java", legacy)


INLINE_SOURCE = r'''
from apkpy_lib import *

notes = db.model(
    "notes",
    fields={
        "id": db.integer(primary_key=True, auto_increment=True),
        "title": db.text(required=True),
        "favorite": db.boolean(default=False),
    },
)
tags = db.model(
    "tags",
    fields={
        "id": db.integer(primary_key=True, auto_increment=True),
        "notes_id": db.integer(),
        "label": db.text(),
    },
)
schema = db.schema(
    "apkpy_app", version=2, models=[notes, tags],
    relations=[
        db.relation("notes_tags", notes, tags, "notes_id", "note", "tags",
                    on_delete="cascade"),
    ],
    migrations=[
        db.migration(from_version=1, to_version=2,
                     operations=[db.add_column(notes, "favorite",
                                               db.boolean(default=False))]),
    ],
)

home = Screen(id="home")
out = label("", id="out", screen=home)

def loaded(rows):
    out.set_value(str(len(rows)))

def failed(error):
    out.set_value(error)

def go():
    notes.find(on_result=loaded, on_error=failed)

# Um observador com nome: sem ele o gerador emite a invalidacao rasa e a
# relacao nao teria por onde se notar.
watcher = tags.observe(on_change=loaded, on_error=failed, screen=home)
button("Go", id="b", screen=home, command=go)
run(start_screen=home)
'''


class ADeclarationWrittenInsideTheSchemaReachesAndroid(unittest.TestCase):
    """db.schema() used to read names out of its lists and drop the rest.

    A model, a relation or a migration written inline is ordinary Python and
    the Previewer takes it -- but the compiler collected variable names, so a
    call simply was not there: no table, no foreign key, no ALTER TABLE, and
    nothing said. The app worked at the desk and not in your hand.

    Refusing the inline form would only have moved the divergence to the end
    of the build, so it is read on the spot instead.
    """

    def setUp(self):
        self.files = translate_python_to_android(INLINE_SOURCE,
                                                 package="com.example.inline")
        self.assertNotIn("error.txt", self.files,
                         self.files.get("error.txt", "")[:400])
        self.database = self.files["java/ApkpyDatabase.java"]

    def test_the_relation_becomes_a_foreign_key(self):
        self.assertIn("FOREIGN KEY", self.database)
        self.assertIn("ON DELETE CASCADE", self.database)

    def test_the_relation_reaches_the_invalidation(self):
        self.assertIn("while(added)", self.database,
                      "sem a relacao, a invalidacao volta a ser a versao rasa")

    def test_the_migration_becomes_an_alter_table(self):
        self.assertIn("ALTER TABLE", self.database)

    def test_a_model_written_inline_becomes_a_table(self):
        source = INLINE_SOURCE.replace(
            "schema = db.schema(\n    \"apkpy_app\", version=2, models=[notes, tags],",
            "schema = db.schema(\n    \"apkpy_app\", version=2, models=[\n"
            "        notes, tags,\n"
            "        db.model(\"extra\", fields={\"id\": db.integer("
            "primary_key=True, auto_increment=True)}),\n    ],")
        files = translate_python_to_android(source, package="com.example.inline2")
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:400])
        self.assertIn("extra", files["java/ApkpyDatabase.java"])

    def test_naming_them_first_still_works(self):
        """The form every example uses has to be untouched by this."""
        named = INLINE_SOURCE.replace(
            '''    relations=[
        db.relation("notes_tags", notes, tags, "notes_id", "note", "tags",
                    on_delete="cascade"),
    ],''',
            "    relations=[liga],")
        named = named.replace(
            "schema = db.schema(",
            '''liga = db.relation("notes_tags", notes, tags, "notes_id", "note",
                   "tags", on_delete="cascade")
schema = db.schema(''')
        files = translate_python_to_android(named, package="com.example.named")
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:400])
        self.assertIn("FOREIGN KEY", files["java/ApkpyDatabase.java"])


class AnEntryTheCompilerCannotReadStopsTheBuild(unittest.TestCase):
    """The other half: never drop one in silence again."""

    SOURCE = r'''
from apkpy_lib import *

def build():
    return db.model("x", fields={"id": db.integer(primary_key=True,
                                                  auto_increment=True)})

notes = db.model("notes", fields={"id": db.integer(primary_key=True,
                                                   auto_increment=True)})
schema = db.schema("apkpy_app", version=1, models=[notes, build()])

home = Screen(id="home")
out = label("", id="out", screen=home)

def loaded(rows):
    out.set_value(str(len(rows)))

def failed(error):
    out.set_value(error)

def go():
    notes.find(on_result=loaded, on_error=failed)

button("Go", id="b", screen=home, command=go)
run(start_screen=home)
'''

    def test_a_call_that_is_not_a_declaration_is_refused(self):
        files = translate_python_to_android(self.SOURCE, package="com.example.bad")
        report = files.get("error.txt", "")
        self.assertIn("C4004", report)
        self.assertIn("models", report)

if __name__ == "__main__":
    unittest.main()
