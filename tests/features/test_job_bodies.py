# -*- coding: utf-8 -*-
"""A job body either runs on the phone or stops the build -- never silence.

The Worker generator dropped every command it could not write. A job whose body
checked a permission, set a label, inserted a row, downloaded a file or simply
called another of your functions compiled to a ``doWork()`` holding an empty
``try``: it installed, it ran, and it did nothing. Not a word anywhere.

Three things are pinned here:

1. What the Worker can write, it now writes -- a call to your own function,
   ``permissions.has()``, ``files.delete()``, and (test_job_data.py) the data
   layer and ``files.download()``.
2. Everything else stops the build with J7004 or J7005, naming the call and
   the line it is on, however deep in a helper it hides.
3. The Previewer refuses the same calls with the same code when a job body
   reaches them, and nothing else: an observer, ``storage`` or
   ``permissions.has()`` stay open.
"""

import os
import time
import unittest

import apkpy_lib as api
from apkpy_lib import job_rules, ui
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.features import jobs as jobs_preview

HEAD = '''from apkpy_lib import *
note = db.model("note", fields={
    "id": db.integer(primary_key=True, auto_increment=True),
    "title": db.text(),
})
schema = db.schema("app", version=1, models=[note])
home = Screen(id="home")
other = Screen(id="other")
out = label("", id="out", screen=home)

def helper(x):
    storage.set("h", x)

def seed(tx):
    tx.insert(note, {"title": "a"})

'''
# The body starts on this line of the generated source.
BODY_LINE = HEAD.count("\n") + 2

TAIL = '''
j = background_job("sync", run=task)
button("Go", id="b", screen=home, command=lambda: j.enqueue())
run(start_screen=home)
'''


def _source(body):
    return HEAD + "def task():\n" + body + TAIL


def _files(body):
    return translate_python_to_android(_source(body))


def _do_work(body):
    files = _files(body)
    if "error.txt" in files:
        raise AssertionError(files["error.txt"][:600])
    worker = [text for name, text in files.items()
              if name.endswith("JobWorker.java")][0]
    start = worker.index("    public Result doWork()")
    return worker, worker[start:worker.index("\n    }", start) + 6]


def _refusal(body):
    files = _files(body)
    if "error.txt" not in files:
        raise AssertionError("the build went through:\n" + _do_work(body)[1])
    return files["error.txt"]


class TheWorkerWritesWhatItCan(unittest.TestCase):

    def test_a_call_to_your_own_function(self):
        worker, java = _do_work('    helper("a")\n')
        self.assertIn('pythonCallback_helper(String.valueOf("a"));', java)
        self.assertIn("private void pythonCallback_helper(", worker)

    def test_a_call_without_arguments(self):
        source = _source('    notify_done()\n').replace(
            "def task():", 'def notify_done():\n    storage.set("d", "1")\n\ndef task():')
        files = translate_python_to_android(source)
        self.assertNotIn("error.txt", files)
        worker = [t for n, t in files.items() if n.endswith("JobWorker.java")][0]
        self.assertIn("pythonCallback_notify_done();", worker)

    def test_permissions_has_asks_the_application_context(self):
        _, java = _do_work(
            '    if permissions.has("CAMERA"):\n'
            '        storage.set("p", "yes")\n'
            '    else:\n'
            '        storage.set("p", "no")\n')
        self.assertIn(
            "ContextCompat.checkSelfPermission(getApplicationContext(), "
            "android.Manifest.permission.CAMERA)", java)
        self.assertIn('_apkpyStorageSet("p", String.valueOf("yes"));', java)
        self.assertIn('_apkpyStorageSet("p", String.valueOf("no"));', java)

    def test_files_delete(self):
        _, java = _do_work('    files.delete("old.mp3")\n')
        self.assertIn(
            'new java.io.File(getApplicationContext().getFilesDir(), '
            'String.valueOf("old.mp3")).delete();', java)


class TheWorkerRefusesInsteadOfDropping(unittest.TestCase):

    CASES = (
        ('    out.set_value("x")\n', "J7004", "out.set_value()"),
        ('    v = out.get_value()\n', "J7004", "out.get_value()"),
        ('    permissions.request("CAMERA")\n', "J7004", "permissions.request()"),
        ('    on_click_navigate(other)\n', "J7004", "on_click_navigate(other)"),
        ('    alert("a", "b")\n', "J7004", "alert()"),
        ('    confirm("a", "b")\n', "J7004", "confirm()"),
        ('    audio.play("a.mp3")\n', "J7004", "audio.play()"),
        ('    uploads.cancel("avatar")\n', "J7005", "uploads.cancel()"),
    )

    def test_each_one_names_the_call_and_its_line(self):
        for body, code, what in self.CASES:
            with self.subTest(what=what):
                error = _refusal('    storage.set("k", "1")\n' + body)
                self.assertIn("APKPY " + code, error)
                self.assertIn(what + " cannot run inside a background job", error)
                self.assertIn("writehere.py:%d" % (BODY_LINE + 1), error)

    def test_the_example_from_the_task(self):
        """The body that started it: both branches used to vanish."""
        error = _refusal(
            '    if permissions.has("CAMERA"):\n'
            '        out.set_value("yes")\n'
            '    else:\n'
            '        out.set_value("no")\n')
        self.assertIn("J7004", error)
        self.assertIn("writehere.py:%d" % (BODY_LINE + 1), error)

    def test_a_call_hidden_in_a_helper_points_at_the_helper(self):
        source = _source('    refresh()\n').replace(
            "def task():",
            'def refresh():\n    storage.set("a", "1")\n    out.set_value("x")\n\n'
            'def task():')
        error = translate_python_to_android(source)["error.txt"]
        line = source.splitlines().index('    out.set_value("x")') + 1
        self.assertIn("J7004", error)
        self.assertIn("writehere.py:%d" % line, error)

    def test_service_every_shares_the_rule(self):
        source = (HEAD + 'def tick():\n    out.set_value("x")\n\n'
                  'service.every(run=tick, minutes=15)\nrun(start_screen=home)\n')
        error = translate_python_to_android(source).get("error.txt", "")
        self.assertIn("J7004", error)

    def test_sensors_are_refused_instead_of_commented_out(self):
        error = _refusal('    sensors.shake(on_shake=helper)\n')
        self.assertIn("J7004", error)
        self.assertIn("sensors.", error)

    def test_a_screen_function_the_job_never_reaches_still_builds(self):
        source = _source('    storage.set("k", "1")\n').replace(
            "def task():",
            'def on_screen():\n    out.set_value("fine here")\n\ndef task():'
        ).replace('command=lambda: j.enqueue()', 'command=on_screen')
        files = translate_python_to_android(source)
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:400])


class TheServiceIsReadTheWayThePreviewerReadsIt(unittest.TestCase):
    """service.every(sync, minutes=15) is what the Previewer's signature
    allows -- and on the phone it produced no Worker and no word."""

    BASE = ('from apkpy_lib import *\nhome = Screen(id="home")\n'
            'def sync():\n    storage.set("s", "1")\n\n%s\n'
            'run(start_screen=home)\n')

    def _workers(self, call):
        files = translate_python_to_android(self.BASE % call)
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:400])
        return sorted(n for n in files if n.endswith("Worker.java"))

    def test_by_name_as_before(self):
        self.assertEqual(self._workers(
            'service.every(run=sync, minutes=15, id="sync")'),
            ["java/SyncWorker.java"])

    def test_by_position(self):
        self.assertEqual(self._workers('service.every(sync, 15, "sync")'),
                         ["java/SyncWorker.java"])

    def test_by_position_then_name(self):
        self.assertEqual(self._workers('service.every(sync, minutes=30, id="sync")'),
                         ["java/SyncWorker.java"])

    def test_a_function_that_does_not_exist_stops_the_build(self):
        files = translate_python_to_android(
            self.BASE % 'service.every(run=missing, minutes=15)')
        self.assertIn("J7002", files.get("error.txt", ""))

    def test_no_function_at_all_stops_the_build(self):
        files = translate_python_to_android(self.BASE % 'service.every(minutes=15)')
        self.assertIn("service.every", files.get("error.txt", ""))


class ThePreviewerRefusesTheSameCalls(unittest.TestCase):
    """Parity: what stops the build stops the desk, with the same code."""

    def setUp(self):
        self.component = ui.ComponentDef("label", comp_id="out")
        self.screen = api.Screen(id="jobrules_other")

    def _preview_code(self, call):
        try:
            with job_rules.running_job():
                call()
        except Exception as error:   # noqa: BLE001 - the code is the answer
            return getattr(error, "code", type(error).__name__)
        return None

    def test_the_same_code_on_both_sides(self):
        pairs = (
            ('    out.set_value("x")\n', lambda: self.component.set_value("x")),
            ('    v = out.get_value()\n', lambda: self.component.get_value()),
            ('    permissions.request("CAMERA")\n',
             lambda: api.permissions.request("CAMERA")),
            ('    on_click_navigate(other)\n',
             lambda: api.on_click_navigate(self.screen)),
            ('    alert("a", "b")\n', lambda: api.alert("a", "b")),
            ('    confirm("a", "b")\n', lambda: api.confirm("a", "b")),
            ('    audio.play("a.mp3")\n', lambda: api.audio.play("a.mp3")),
            ('    uploads.cancel("avatar")\n', lambda: api.uploads.cancel("avatar")),
        )
        for body, call in pairs:
            with self.subTest(body=body.strip()):
                error = _refusal(body)
                android = error.split("APKPY ", 1)[1][:5]
                self.assertEqual(android, self._preview_code(call))

    def test_what_the_phone_runs_stays_open(self):
        self.assertIsNone(self._preview_code(
            lambda: api.permissions.has("CAMERA")))
        self.assertIsNone(self._preview_code(
            lambda: api.files.path("x") and api.files.exists("x")))
        self.assertIsNone(self._preview_code(
            lambda: api.json_get('{"a": "1"}', "a")))

    def test_outside_a_job_nothing_changes(self):
        self.component.set_value("desk")
        self.assertEqual(self.component._initial_value, "desk")

    def test_an_observer_is_the_screen_not_the_body(self):
        seen = []
        with job_rules.running_job():
            with job_rules.outside_job():
                self.component.set_value("from an observer")
                seen.append(True)
            self.assertTrue(job_rules.inside_job())
        self.assertEqual(seen, [True])


class ThePreviewerJobStopsInsteadOfRetrying(unittest.TestCase):
    """A body the phone would not build is not a flaky one: no backoff."""

    NAME = "jobrules_refused_body"

    def tearDown(self):
        try:
            os.remove(os.path.join(jobs_preview._jobs_dir(),
                                   "%s.json" % jobs_preview._safe_name(self.NAME)))
        except OSError:
            pass

    def test_the_job_fails_once_and_the_observer_still_hears_it(self):
        component = ui.ComponentDef("label", comp_id="status")
        ran, states = [], []

        def body():
            ran.append("before")
            component.set_value("from the job")
            ran.append("after")

        def watch(status):
            states.append(status["state"])
            # An observer setting a label is the screen, not the job body.
            component.set_value(status["state"])

        job = jobs_preview.JobDef(self.NAME, run=body, retry_seconds=5)
        job.observe(on_change=watch)
        job.enqueue({})
        deadline = time.time() + 5
        while time.time() < deadline and job.status()["state"] != "failed":
            time.sleep(0.05)
        time.sleep(0.3)   # a retry would show up here
        self.assertEqual(job.status()["state"], "failed")
        self.assertEqual(ran, ["before"])
        self.assertNotIn("retry", states)
        self.assertEqual(component._initial_value, "failed")

    def test_a_service_body_is_guarded_too(self):
        stopped = []
        body = ui._as_worker_body(
            lambda: ui.ComponentDef("label", comp_id="x").set_value("x"),
            "tick", lambda: stopped.append(True))
        body()
        self.assertEqual(stopped, [True])


class TheTableIsComplete(unittest.TestCase):

    def test_every_preview_guard_points_at_a_real_method(self):
        for name, family, verbs in job_rules.PREVIEW_GUARDS:
            target = getattr(api, name, None) or vars(ui).get(name)
            self.assertIsNotNone(target, name)
            cls = target if isinstance(target, type) else type(target)
            for verb in verbs:
                with self.subTest(api=name, verb=verb):
                    method = getattr(cls, verb, None)
                    self.assertTrue(callable(method), "%s.%s" % (name, verb))
                    self.assertEqual(getattr(method, "_apkpy_job_family", None),
                                     family)

    def test_every_family_has_a_code(self):
        for family, (code, why) in job_rules.FAMILIES.items():
            self.assertIn(code, job_rules.CODES, family)
            self.assertTrue(why)


if __name__ == "__main__":
    unittest.main()
