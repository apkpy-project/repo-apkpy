import os
import tempfile
import threading
import time
import unittest

from apkpy_lib import DataCoreError, SQLiteAPI
from apkpy_lib.core.compiler import translate_python_to_android


def make_database():
    database = SQLiteAPI()
    directory = tempfile.mkdtemp(prefix="apkpy-reactive-data-")
    database._path = os.path.join(directory, "reactive.db")
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
    try:
        future.result(timeout=5)
    except Exception:
        pass
    assert event.wait(5)
    if "error" in received:
        raise AssertionError(received["error"])
    return received.get("value")


def make_schema(on_delete="cascade", optional=False):
    database = make_database()
    folders = database.model("folders", fields={
        "id": database.integer(primary_key=True, auto_increment=True),
        "name": database.text(required=True),
    })
    folder_field = (
        database.integer(optional=True)
        if optional else database.integer(required=True)
    )
    notes = database.model("notes", fields={
        "id": database.integer(primary_key=True, auto_increment=True),
        "folder_id": folder_field,
        "title": database.text(required=True),
        "favorite": database.boolean(default=False),
    })
    relation = database.relation(
        "folder_notes", parent=folders, child=notes,
        foreign_key="folder_id", parent_as="folder",
        children_as="notes", on_delete=on_delete,
    )
    database.schema(
        "reactive_test", 1, [folders, notes], relations=[relation],
    )
    return database, folders, notes


class ReactiveDataRuntimeTests(unittest.TestCase):
    def test_relation_validation(self):
        database = make_database()
        parent = database.model("parents", fields={
            "id": database.integer(primary_key=True),
        })
        child = database.model("children", fields={
            "id": database.integer(primary_key=True),
            "parent_id": database.text(required=True),
        })
        with self.assertRaisesRegex(DataCoreError, "type mismatch"):
            database.relation(
                "bad", parent, child, "parent_id", "parent", "children",
            )

        compatible_child = database.model("compatible_children", fields={
            "id": database.integer(primary_key=True),
            "parent_id": database.integer(required=True),
        })
        database.relation(
            "valid", parent, compatible_child, "parent_id",
            "parent", "children",
        )
        second_child = database.model("second_children", fields={
            "id": database.integer(primary_key=True),
            "parent_id": database.integer(required=True),
        })
        with self.assertRaisesRegex(DataCoreError, "aliases must be unique"):
            database.relation(
                "duplicate_alias", parent, second_child, "parent_id",
                "parent", "other_children",
            )

        second = make_database()
        parent = second.model("parents", fields={
            "id": second.integer(primary_key=True),
        })
        child = second.model("children", fields={
            "id": second.integer(primary_key=True),
            "parent_id": second.integer(required=True),
        })
        with self.assertRaisesRegex(DataCoreError, "optional=True"):
            second.relation(
                "bad_null", parent, child, "parent_id", "parent",
                "children", on_delete="set_null",
            )

    def test_include_both_directions_and_foreign_key(self):
        database, folders, notes = make_schema()
        folder_id = await_result(lambda ok, fail: folders.insert(
            {"name": "Research"}, on_result=ok, on_error=fail,
        ))
        await_result(lambda ok, fail: notes.insert_many([
            {"folder_id": folder_id, "title": "Alpha"},
            {"folder_id": folder_id, "title": "Beta"},
        ], on_result=ok, on_error=fail))

        parent_rows = await_result(lambda ok, fail: folders.find(
            include=["notes"], on_result=ok, on_error=fail,
        ))
        self.assertEqual([item["title"] for item in parent_rows[0]["notes"]], [
            "Alpha", "Beta",
        ])
        child = await_result(lambda ok, fail: notes.get(
            1, include=["folder"], on_result=ok, on_error=fail,
        ))
        self.assertEqual(child["folder"]["name"], "Research")

        errors = []
        event = threading.Event()
        future = notes.insert(
            {"folder_id": 999, "title": "Orphan"},
            on_result=lambda _value: event.set(),
            on_error=lambda error: (errors.append(error), event.set()),
        )
        with self.assertRaises(Exception):
            future.result(timeout=5)
        self.assertTrue(event.wait(5))
        self.assertTrue(errors)

    def test_delete_actions(self):
        database, folders, notes = make_schema("cascade")
        folder_id = await_result(lambda ok, fail: folders.insert(
            {"name": "Delete me"}, on_result=ok, on_error=fail,
        ))
        await_result(lambda ok, fail: notes.insert(
            {"folder_id": folder_id, "title": "Child"},
            on_result=ok, on_error=fail,
        ))
        await_result(lambda ok, fail: folders.delete(
            [database.eq("id", folder_id)], on_result=ok, on_error=fail,
        ))
        self.assertEqual(await_result(lambda ok, fail: notes.count(
            on_result=ok, on_error=fail,
        )), 0)

        nullable, parents, children = make_schema("set_null", optional=True)
        parent_id = await_result(lambda ok, fail: parents.insert(
            {"name": "Nullable"}, on_result=ok, on_error=fail,
        ))
        await_result(lambda ok, fail: children.insert(
            {"folder_id": parent_id, "title": "Kept"},
            on_result=ok, on_error=fail,
        ))
        await_result(lambda ok, fail: parents.delete(
            [nullable.eq("id", parent_id)], on_result=ok, on_error=fail,
        ))
        child = await_result(lambda ok, fail: children.get(
            1, on_result=ok, on_error=fail,
        ))
        self.assertIsNone(child["folder_id"])

    def test_observer_lifecycle_invalidation_and_query_update(self):
        database, folders, notes = make_schema()
        folder_id = await_result(lambda ok, fail: folders.insert(
            {"name": "Live"}, on_result=ok, on_error=fail,
        ))
        screen = object()
        changes = []
        changed = threading.Event()

        def received(rows):
            changes.append(list(rows))
            changed.set()

        observer = notes.observe(
            filters=[database.eq("favorite", False)], include=["folder"],
            screen=screen, on_change=received,
        )
        database._data_lifecycle(screen, "on_resume")
        self.assertTrue(changed.wait(5))
        self.assertEqual(changes[-1], [])

        changed.clear()
        await_result(lambda ok, fail: notes.insert(
            {"folder_id": folder_id, "title": "Visible"},
            on_result=ok, on_error=fail,
        ))
        self.assertTrue(changed.wait(5))
        self.assertEqual(changes[-1][0]["folder"]["name"], "Live")

        changed.clear()
        observer.update_query(filters=[database.eq("favorite", True)])
        self.assertTrue(changed.wait(5))
        self.assertEqual(changes[-1], [])

        database._data_lifecycle(screen, "on_pause")
        changed.clear()
        await_result(lambda ok, fail: notes.update(
            {"favorite": True}, filters=[database.eq("id", 1)],
            on_result=ok, on_error=fail,
        ))
        self.assertFalse(changed.wait(0.15))
        database._data_lifecycle(screen, "on_resume")
        self.assertTrue(changed.wait(5))
        self.assertEqual(changes[-1][0]["title"], "Visible")

        database._data_lifecycle(screen, "on_destroy")
        self.assertTrue(observer.closed)

    def test_failed_transaction_does_not_notify(self):
        database, folders, _notes = make_schema()
        screen = object()
        changes = []
        initial = threading.Event()
        observer = folders.observe(
            screen=screen,
            on_change=lambda rows: (changes.append(list(rows)), initial.set()),
        )
        database._data_lifecycle(screen, "on_resume")
        self.assertTrue(initial.wait(5))

        def broken(tx):
            tx.insert(folders, {"name": "Rolled back"})
            raise RuntimeError("stop")

        event = threading.Event()
        future = database.transaction(
            run=broken, on_error=lambda _error: event.set(),
        )
        with self.assertRaises(RuntimeError):
            future.result(timeout=5)
        self.assertTrue(event.wait(5))
        time.sleep(0.1)
        self.assertEqual(len(changes), 1)
        observer.close()


class ReactiveDataCompilerTests(unittest.TestCase):
    def test_android_relation_validation_matches_preview_contract(self):
        invalid_set_null = '''
from apkpy_lib import *
home = Screen("Home")
parents = db.model("parents", fields={
    "id": db.integer(primary_key=True),
})
children = db.model("children", fields={
    "id": db.integer(primary_key=True),
    "parent_id": db.integer(),
})
relation = db.relation(
    "parent_children", parents, children, "parent_id",
    "parent", "children", on_delete="set_null",
)
schema = db.schema("invalid", 1, [parents, children], relations=[relation])
'''
        invalid_files = translate_python_to_android(invalid_set_null)
        self.assertIn("error.txt", invalid_files)
        self.assertIn("requires an optional foreign key", invalid_files["error.txt"])

        recursive = '''
from apkpy_lib import *
home = Screen("Home")
nodes = db.model("nodes", fields={
    "id": db.integer(primary_key=True),
    "parent_id": db.integer(optional=True),
})
relation = db.relation(
    "node_children", nodes, nodes, "parent_id",
    "parent", "children", on_delete="set_null",
)
schema = db.schema("invalid", 1, [nodes], relations=[relation])
'''
        recursive_files = translate_python_to_android(recursive)
        self.assertIn("error.txt", recursive_files)
        self.assertIn("cannot relate a model to itself", recursive_files["error.txt"])

    def test_android_relations_includes_and_observer_lifecycle(self):
        source = '''
from apkpy_lib import Screen, db

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
    "reactive_codegen", version=1, models=[folders, notes],
    relations=[folder_notes],
)
library = Screen("library")

def changed(rows):
    pass

def failed(error):
    pass

live_notes = notes.observe(
    filters=[db.contains("title", "live")],
    include=["folder"], limit=50, screen=library,
    on_change=changed, on_error=failed,
)

def controls():
    live_notes.refresh()
    live_notes.update_query(filters=[db.contains("title", "new")])
'''
        files = translate_python_to_android(source, "com.example.reactive")
        self.assertIn("java/ApkpyDataInvalidationTracker.java", files)
        self.assertIn("java/ApkpyQuerySubscription.java", files)
        database = files["java/ApkpyDatabase.java"]
        activity = files["java/Screen_libraryActivity.java"]
        notes_repository = files["java/NotesRepository.java"]
        self.assertIn(
            'FOREIGN KEY (\\\"folder_id\\\") REFERENCES \\\"folders\\\" '
            '(\\\"id\\\") ON DELETE CASCADE', database,
        )
        self.assertIn("hydrateChildren", database)
        self.assertIn("hydrateParent", database)
        self.assertIn(r'"\""+field+"\" IN ("', database)
        self.assertNotIn('"""+field+"" IN ("', database)
        self.assertIn("queryDependencies", database)
        self.assertIn("new ApkpyQuerySubscription", activity)
        self.assertIn("live_notes.resume()", activity)
        self.assertIn("live_notes.pause()", activity)
        self.assertIn("live_notes.close()", activity)
        self.assertIn("JSONArray include", notes_repository)
        self.assertIn("ApkpyDataInvalidationTracker.invalidate", notes_repository)

    def test_relation_without_observer_does_not_emit_tracker(self):
        source = '''
from apkpy_lib import Screen, db
parents = db.model("parents", fields={"id": db.integer(primary_key=True)})
children = db.model("children", fields={
    "id": db.integer(primary_key=True),
    "parent_id": db.integer(required=True),
})
link = db.relation("link", parents, children, "parent_id", "parent", "children")
schema = db.schema("relations_only", 1, [parents, children], relations=[link])
home = Screen("home")
'''
        files = translate_python_to_android(source, "com.example.relations")
        self.assertNotIn("java/ApkpyDataInvalidationTracker.java", files)
        self.assertNotIn("ApkpyDataInvalidationTracker", files["java/ParentsRepository.java"])
        self.assertIn("FOREIGN KEY", files["java/ApkpyDatabase.java"])

    def test_plain_data_core_does_not_emit_relation_or_observer_runtime(self):
        source = '''
from apkpy_lib import Screen, db
items = db.model("items", fields={
    "id": db.integer(primary_key=True),
    "title": db.text(required=True),
})
schema = db.schema("plain_data_core", 1, [items])
home = Screen("home")
'''
        files = translate_python_to_android(source, "com.example.plain")
        database = files["java/ApkpyDatabase.java"]
        self.assertNotIn("java/ApkpyDataInvalidationTracker.java", files)
        self.assertNotIn("java/ApkpyQuerySubscription.java", files)
        self.assertNotIn("static final class Relation", database)
        self.assertNotIn("hydrateChildren", database)
        self.assertNotIn("hydrateParent", database)
        self.assertNotIn("queryDependencies", database)
        self.assertNotIn("expandInvalidations", database)

    def test_cross_screen_observer_commands_compile_as_nullable_handles(self):
        source = '''
from apkpy_lib import Screen, db
items = db.model("items", fields={"id": db.integer(primary_key=True)})
schema = db.schema("cross_screen_observer", 1, [items])
one = Screen("one")
two = Screen("two")
def changed(rows):
    pass
live = items.observe(screen=two, on_change=changed)
def from_first_screen():
    live.refresh()
'''
        files = translate_python_to_android(source, "com.example.crossscreen")
        first = files["java/Screen_oneActivity.java"]
        second = files["java/Screen_twoActivity.java"]
        self.assertIn("private ApkpyQuerySubscription live;", first)
        self.assertNotIn("live = new ApkpyQuerySubscription", first)
        self.assertIn("live = new ApkpyQuerySubscription", second)


if __name__ == "__main__":
    unittest.main()
