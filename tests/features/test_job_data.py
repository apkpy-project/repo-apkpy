# -*- coding: utf-8 -*-
"""The data layer and files.download() inside a background job.

Both used to stop the build with J7005. The natural offline queue -- a job that
saves what it fetched -- could not be written. Now a job body runs them where
it is: the Worker is already off the main thread, so it runs the same Task a
screen would submit (``ApkpyDataExecutor.runHere``), and its next line sees the
answer. The Previewer keeps the same order inside a job.

Pinned here, on both sides:

* the Worker calls the one definition of each operation (``<Repo>.insertTask``)
  that the screens' async wrappers also use -- no third copy;
* ``on_result`` / ``on_error`` exist in the Worker and run before the next line;
* a boolean first argument (``files.download``'s ``ok``, ``https``'s
  ``success``) is a ``boolean`` in the Worker too -- it was a ``String`` called
  with a ``boolean``, which javac refuses;
* a transaction body that returns a value compiles (it was followed by an
  unreachable ``return "";``, on screens as well);
* the screens' observers still hear about the write, and on the screen's side.
"""

import http.server
import os
import tempfile
import threading
import unittest

import apkpy_lib as api
from apkpy_lib import SQLiteAPI, job_rules, ui
from apkpy_lib.core.compiler import translate_python_to_android

HEAD = '''from apkpy_lib import *
note = db.model("note", fields={
    "id": db.integer(primary_key=True, auto_increment=True),
    "title": db.text(),
})
schema = db.schema("app", version=1, models=[note])
home = Screen(id="home")
out = label("", id="out", screen=home)

def saved(new_id):
    storage.set("last_id", new_id)

def failed(message):
    storage.set("error", message)

def fetched(ok, path):
    if ok:
        note.insert({"title": path}, on_result=saved)
    else:
        storage.set("download", "failed")

def seed(tx):
    tx.insert(note, {"title": "seeded"})
    total = tx.count(note)
    return total

def counted(total):
    storage.set("total", total)

def shown(rows):
    out.set_value(rows)

watch = note.observe(on_change=shown, screen=home)

'''
TAIL = '''
j = background_job("sync", run=task)
button("Go", id="b", screen=home, command=lambda: j.enqueue())
run(start_screen=home)
'''


def _files(body):
    files = translate_python_to_android(HEAD + "def task():\n" + body + TAIL)
    if "error.txt" in files:
        raise AssertionError(files["error.txt"][:600])
    return files


def _worker(body):
    return [t for n, t in _files(body).items() if n.endswith("JobWorker.java")][0]


def _do_work(worker):
    start = worker.index("    public Result doWork()")
    return worker[start:worker.index("\n    }", start)]


class TheWorkerRunsTheDataLayer(unittest.TestCase):

    def test_each_operation_runs_its_task_here(self):
        java = _do_work(_worker(
            '    note.insert({"title": "a"}, on_result=saved, on_error=failed)\n'
            '    note.insert_many([{"title": "b"}])\n'
            '    note.get(1)\n'
            '    note.find(filters=[db.contains("title", "a")])\n'
            '    note.update({"title": "c"}, filters=[db.eq("id", 1)])\n'
            '    note.delete(filters=[db.eq("id", 2)])\n'
            '    note.count()\n'))
        for method in ("insert", "insertMany", "get", "find", "update",
                       "delete", "count"):
            with self.subTest(method=method):
                self.assertIn("ApkpyDataExecutor.runHere(NoteRepository.%sTask("
                              "getApplicationContext(), " % method, java)
        self.assertNotIn("ApkpyDataExecutor.submit", java)
        self.assertIn("public void onResult(String value){pythonCallback_saved(value);}", java)
        self.assertIn("public void onError(String message){pythonCallback_failed(message);}", java)

    def test_the_callbacks_exist_in_the_worker(self):
        worker = _worker('    note.insert({"title": "a"}, on_result=saved, on_error=failed)\n')
        self.assertIn("private void pythonCallback_saved(", worker)
        self.assertIn("private void pythonCallback_failed(", worker)

    def test_a_transaction_that_returns_a_value(self):
        java = _do_work(_worker('    db.transaction(run=seed, on_result=counted)\n'))
        self.assertIn("ApkpyDataExecutor.runHere(ApkpyDatabase.getInstance("
                      "getApplicationContext()).transactionTask(_apkpyTx -> {", java)
        self.assertIn("return String.valueOf(total);\n            }), new ApkpyDataExecutor.Callback()", java)
        self.assertNotIn('return String.valueOf(total);\n                return "";', java)
        self.assertNotIn("return Result", java.split("transactionTask", 1)[1].split("}),", 1)[0])

    def test_an_observer_still_belongs_to_the_screen(self):
        files = translate_python_to_android(HEAD + "def task():\n    watch.refresh()\n" + TAIL)
        self.assertIn("J7004", files.get("error.txt", ""))

    def test_a_screen_keeps_submitting(self):
        activity = _files('    storage.set("k", "1")\n')["java/Screen_homeActivity.java"]
        self.assertNotIn("runHere", activity)


class OneDefinitionOfEachOperation(unittest.TestCase):
    """The screens' wrappers and the Worker run the same Task."""

    def setUp(self):
        self.files = _files('    note.count()\n')

    def test_the_repository_wraps_its_tasks(self):
        repo = self.files["java/NoteRepository.java"]
        for method in ("insert", "insertMany", "get", "find", "update", "delete", "count"):
            with self.subTest(method=method):
                self.assertIn("public static ApkpyDataExecutor.Task %sTask(" % method, repo)
                self.assertIn("ApkpyDataExecutor.submit(%sTask(" % method, repo)
        self.assertEqual(repo.count("db.insertSync("), 1)

    def test_the_transaction_too(self):
        database = self.files["java/ApkpyDatabase.java"]
        self.assertIn("public ApkpyDataExecutor.Task transactionTask(TransactionWork work)", database)
        self.assertIn("ApkpyDataExecutor.submit(transactionTask(work),callback);", database)

    def test_run_here_answers_outside_its_try(self):
        executor = self.files["java/ApkpyDataExecutor.java"]
        body = executor[executor.index("public static void runHere"):]
        self.assertLess(body.index("return;"), body.index("callback.onResult"))


class TheWorkerDownloads(unittest.TestCase):

    def test_download_answers_before_the_next_line(self):
        worker = _worker(
            '    files.download("https://example.com/a.txt", "a.txt", on_result=fetched)\n'
            '    storage.set("after", "1")\n')
        java = _do_work(worker)
        self.assertIn('String _apkpyDownload1 = _filesDownloadNow(String.valueOf('
                      '"https://example.com/a.txt"), String.valueOf("a.txt"));', java)
        self.assertLess(java.index("pythonCallback_fetched(!_apkpyDownload1.isEmpty(), _apkpyDownload1);"),
                        java.index('_apkpyStorageSet("after"'))
        self.assertIn("private void pythonCallback_fetched(boolean ok, String path) {\n        if (ok) {", worker)
        self.assertEqual(worker.count("private String _filesDownloadNow(String url, String name)"), 1)

    def test_a_download_asked_for_inside_a_callback(self):
        source = HEAD.replace(
            'def counted(total):\n    storage.set("total", total)',
            'def counted(total):\n    files.download("https://example.com/b", "b", on_result=fetched)')
        files = translate_python_to_android(
            source + "def task():\n    db.transaction(run=seed, on_result=counted)\n" + TAIL)
        worker = [t for n, t in files.items() if n.endswith("JobWorker.java")][0]
        self.assertIn("private String _filesDownloadNow(", worker)

    def test_no_download_no_helper(self):
        self.assertNotIn("_filesDownloadNow", _worker('    note.count()\n'))

    def test_the_screen_uses_the_same_download(self):
        source = HEAD + ('def go():\n    files.download("https://example.com/a", "a", on_result=fetched)\n\n'
                         'button("Get", id="g", screen=home, command=go)\nrun(start_screen=home)\n')
        activity = translate_python_to_android(source)["java/Screen_homeActivity.java"]
        self.assertIn("final String fpath = _filesDownloadNow(url, name);", activity)
        self.assertIn("cb.onResult(!fpath.isEmpty(), fpath);", activity)
        self.assertEqual(activity.count("private String _filesDownloadNow("), 1)


class ABooleanCallbackInTheWorker(unittest.TestCase):
    """https in a job declared `String ok` and called it with a boolean."""

    def test_https_on_response(self):
        source = HEAD + ('def got(ok, body):\n    if ok:\n        storage.set("body", body)\n\n')
        files = translate_python_to_android(
            source + 'def task():\n    https.get("https://example.com", on_response=got)\n' + TAIL)
        worker = [t for n, t in files.items() if n.endswith("JobWorker.java")][0]
        self.assertIn("private void pythonCallback_got(boolean ok, String body) {\n        if (ok) {", worker)


class AScreenTransactionThatReturns(unittest.TestCase):
    """The same unreachable `return "";` existed on screens."""

    def test_it_compiles_on_a_screen(self):
        source = HEAD + ('def go():\n    db.transaction(run=seed, on_result=counted)\n\n'
                         'button("Seed", id="s", screen=home, command=go)\nrun(start_screen=home)\n')
        activity = translate_python_to_android(source)["java/Screen_homeActivity.java"]
        self.assertIn("return String.valueOf(total);\n", activity)
        self.assertNotIn('return String.valueOf(total);\n                    return "";', activity)
        self.assertNotIn('return String.valueOf(total);\n                return "";', activity)

    def test_a_body_that_does_not_return_still_closes(self):
        source = HEAD.replace("    total = tx.count(note)\n    return total\n", "")
        source += ('def go():\n    db.transaction(run=seed)\n\n'
                   'button("Seed", id="s", screen=home, command=go)\nrun(start_screen=home)\n')
        activity = translate_python_to_android(source)["java/Screen_homeActivity.java"]
        self.assertIn('return "";', activity.split("transactionAsync", 1)[1][:600])


def _database():
    database = SQLiteAPI()
    database._path = os.path.join(tempfile.mkdtemp(prefix="apkpy-jobdata-"), "t.db")
    return database


class ThePreviewerAnswersBeforeTheNextLine(unittest.TestCase):
    """Inside a job the Previewer runs the operation where it is."""

    @classmethod
    def setUpClass(cls):
        cls.db = _database()
        cls.note = cls.db.model("jobdata_note", fields={
            "id": cls.db.integer(primary_key=True, auto_increment=True),
            "title": cls.db.text(),
        })
        cls.db.schema("jobdata", 1, [cls.note])

    def test_insert_then_the_next_line(self):
        order = []
        with job_rules.running_job():
            self.note.insert({"title": "a"}, on_result=lambda new_id: order.append(("id", new_id)))
            order.append("next line")
        self.assertEqual(order[1], "next line")
        self.assertEqual(order[0][0], "id")

    def test_find_sees_the_insert_just_made(self):
        seen = []
        with job_rules.running_job():
            self.note.insert({"title": "visible"})
            self.note.find(filters=[self.db.eq("title", "visible")],
                           on_result=lambda rows: seen.append(len(rows)))
        self.assertEqual(seen, [1])

    def test_a_transaction_returns_its_value(self):
        seen = []

        def seed(tx):
            tx.insert(self.note, {"title": "in tx"})
            return tx.count(self.note)

        with job_rules.running_job():
            self.db.transaction(run=seed, on_result=seen.append)
        self.assertEqual(len(seen), 1)
        self.assertGreaterEqual(int(seen[0]), 1)

    def test_an_error_goes_to_on_error_before_the_next_line(self):
        order = []
        with job_rules.running_job():
            self.note.insert({"nope": 1}, on_error=lambda message: order.append("error"))
            order.append("next line")
        self.assertEqual(order, ["error", "next line"])

    def test_the_callback_is_part_of_the_body(self):
        component = ui.ComponentDef("label", comp_id="out")
        with job_rules.running_job():
            with self.assertRaises(Exception) as caught:
                self.note.insert({"title": "x"},
                                 on_result=lambda new_id: component.set_value(new_id))
        self.assertEqual(getattr(caught.exception, "code", ""), "J7004")

    def test_outside_a_job_it_is_still_asynchronous(self):
        done = threading.Event()
        future = self.note.count(on_result=lambda value: done.set())
        self.assertTrue(done.wait(5))
        self.assertIsNotNone(future)


class TheScreenStillHearsAboutTheWrite(unittest.TestCase):
    """An observer is the screen: it re-queries on its own side."""

    def test_an_observer_updates_outside_the_job(self):
        db = _database()
        note = db.model("jobdata_watched", fields={
            "id": db.integer(primary_key=True, auto_increment=True),
            "title": db.text(),
        })
        db.schema("jobdata_watch", 1, [note])
        label = ui.ComponentDef("label", comp_id="count")
        arrived = threading.Event()

        def shown(rows):
            label.set_value(str(len(rows)))   # a screen may do this
            if len(rows) == 1:
                arrived.set()

        subscription = note.observe(on_change=shown, screen=api.Screen(id="jobdata_screen"))
        subscription.resume()
        with job_rules.running_job():
            note.insert({"title": "from the job"})
        self.assertTrue(arrived.wait(5), "the observer never heard about the insert")
        self.assertEqual(label._initial_value, "1")
        subscription.close()


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class ThePreviewerDownloadsBeforeTheNextLine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.mkdtemp(prefix="apkpy-jobdl-")
        with open(os.path.join(cls.folder, "hello.txt"), "w", encoding="utf-8") as f:
            f.write("hello from the job")
        handler = lambda *a, **k: _Quiet(*a, directory=cls.folder, **k)
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d/" % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        for name in ("jobdata_hello.txt", "jobdata_missing.txt"):
            try:
                os.remove(api.files.path(name))
            except OSError:
                pass

    def test_the_file_is_there_on_the_next_line(self):
        order = []
        with job_rules.running_job():
            api.files.download(self.base + "hello.txt", "jobdata_hello.txt",
                               on_result=lambda ok, path: order.append((ok, path)))
            order.append(api.files.exists("jobdata_hello.txt"))
        (ok, path), exists = order
        self.assertTrue(ok)
        self.assertTrue(exists)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "hello from the job")

    def test_a_failure_answers_false_and_empty(self):
        seen = []
        with job_rules.running_job():
            api.files.download(self.base + "missing.txt", "jobdata_missing.txt",
                               on_result=lambda ok, path: seen.append((ok, path)))
        self.assertEqual(seen, [(False, "")])


if __name__ == "__main__":
    unittest.main()
