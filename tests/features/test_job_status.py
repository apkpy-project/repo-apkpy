# -*- coding: utf-8 -*-
"""The status a job reports, the same on the desk and on the phone.

``job.observe()`` hands the screen one document. The Previewer built it from
its own queue and the phone from WorkManager's list of WorkInfo, and the two
disagreed where a screen looks most: after a success the phone said progress 0
and no message (WorkManager clears the progress of finished work), a retry was
just "enqueued", and a failure from earlier in the history could outrank the
success that followed it. Found on a phone, in the Job Bodies Lab.

The rule now lives once, in ``job_rules.status_document``, built from facts
both sides have. Pinned here:

1. the rule itself, and the generated ``ApkpyJobs.status()`` compiled with
   ``javac`` against WorkManager's own classes, answering the same table;
2. the Previewer's queue, driven for real, reporting through that rule;
3. the generated Worker leaving its last word where ``status()`` reads it.
"""

import glob
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest

from apkpy_lib import job_rules
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import jobs as jobs_codegen
from apkpy_lib.features import jobs as jobs_preview

F = job_rules.finished
C = job_rules.cancelled

# name -> (running, pending, last, policy, base, history). ``history`` is what
# WorkManager may still hold from earlier items -- the phone must ignore it.
SCENARIOS = {
    "idle": (None, [], None, "exponential", 30, []),
    "enqueued": (None, [0], None, "exponential", 30, []),
    "enqueued_two": (None, [0, 0], None, "exponential", 30, []),
    "running_silent": ({"progress": 0, "message": "", "attempt": 1}, [], None,
                       "exponential", 30, []),
    "running_half": ({"progress": 40, "message": "half way", "attempt": 1}, [0],
                     None, "exponential", 30, []),
    "running_second_try": ({"progress": 10, "message": "again", "attempt": 2}, [],
                           None, "exponential", 30, []),
    "retry_first": (None, [1], None, "exponential", 30, []),
    "retry_linear_third": (None, [3], None, "linear", 20, []),
    "retry_ceiling": (None, [20], None, "exponential", 30, []),
    "retry_floor": (None, [1], None, "linear", 10, []),
    "retry_beside_fresh": (None, [0, 2], None, "exponential", 30, []),
    "success": (None, [], F(True, "done", 1), "exponential", 30, ["SUCCEEDED"]),
    "success_quiet": (None, [], F(True, "", 2), "exponential", 30, ["SUCCEEDED"]),
    "success_after_old_failure": (None, [], F(True, "done", 1), "exponential", 30,
                                  ["FAILED", "SUCCEEDED"]),
    "failed": (None, [], F(False, "gave up", 3), "exponential", 30, ["FAILED"]),
    "cancelled": (None, [], C(), "exponential", 30, ["CANCELLED", "SUCCEEDED"]),
    "running_beats_last": ({"progress": 5, "message": "go", "attempt": 1}, [],
                           F(True, "done", 1), "exponential", 30, ["SUCCEEDED"]),
    "enqueued_beats_last": (None, [0], F(False, "no", 1), "exponential", 30,
                            ["FAILED"]),
}


def _python(name):
    running, pending, last, policy, base, _history = SCENARIOS[name]
    return job_rules.status_document(running, pending, last, policy, base)


class TheRule(unittest.TestCase):

    def test_a_finished_job_keeps_its_last_word(self):
        self.assertEqual(_python("success"), {
            "state": "success", "progress": 100, "message": "done",
            "running": 0, "pending": 0, "attempt": 1})
        self.assertEqual(_python("failed")["message"], "gave up")
        self.assertEqual(_python("failed")["progress"], 0)

    def test_a_retry_says_so(self):
        self.assertEqual(_python("retry_first")["state"], "retry")
        self.assertEqual(_python("retry_first")["message"], "Retrying in 30 s (attempt 1)")
        self.assertEqual(_python("retry_linear_third")["message"], "Retrying in 60 s (attempt 3)")
        self.assertEqual(_python("retry_ceiling")["message"], "Retrying in 18000 s (attempt 20)")
        self.assertEqual(_python("retry_first")["pending"], 1)

    def test_the_backoff_is_workmanagers(self):
        self.assertEqual(job_rules.backoff_seconds("exponential", 30, 1), 30)
        self.assertEqual(job_rules.backoff_seconds("exponential", 30, 3), 120)
        self.assertEqual(job_rules.backoff_seconds("linear", 30, 3), 90)
        self.assertEqual(job_rules.backoff_seconds("linear", 5, 1), 10)
        self.assertEqual(job_rules.backoff_seconds("exponential", 30, 40), 18000)

    def test_the_previewer_hold_is_its_own(self):
        document = job_rules.status_document(None, [0], None, offline=True)
        self.assertEqual(document["state"], "waiting_network")


def _tooling():
    """javac, java, WorkManager, kotlin-stdlib and org.json -- or None."""
    javac, java = shutil.which("javac"), shutil.which("java")
    if not javac or not java:
        return None
    caches = os.path.join(os.path.expanduser("~"), ".gradle", "caches")
    work = (glob.glob(os.path.join(caches, "transforms-*", "*", "transformed",
                                   "work-runtime-2.9.0-runtime.jar"))
            + glob.glob(os.path.join(caches, "transforms-*", "*", "transformed",
                                     "work-runtime-2.9.0", "jars", "classes.jar")))
    kotlin = sorted(path for path in glob.glob(os.path.join(
        caches, "modules-2", "files-2.1", "org.jetbrains.kotlin", "kotlin-stdlib",
        "*", "*", "kotlin-stdlib-*.jar"))
        if not any(bad in os.path.basename(path) for bad in ("RC", "sources", "common")))
    org_json = sorted(glob.glob(os.path.join(
        caches, "modules-2", "files-2.1", "org.json", "json", "*", "*", "json-*.jar")))
    if not (work and kotlin and org_json):
        return None
    return javac, java, [work[0], kotlin[-1], org_json[-1]]


TOOLING = _tooling()


def _generated_runtime():
    job = {"name": "sync", "safe": "sync", "worker_class": "SyncJobWorker",
           "requires_unmetered": False, "requires_network": False,
           "requires_charging": False, "requires_battery_not_low": False,
           "retry": "exponential", "retry_seconds": 30, "unique": True,
           "on_conflict": "append"}
    return jobs_codegen.generate_files("com.example", [job])["java/ApkpyJobs.java"]


def _method(java, start):
    """Lift one method out of the generated file, exactly as it was written."""
    index = java.index(start)
    depth = 0
    for position in range(java.index("{", index), len(java)):
        if java[position] == "{":
            depth += 1
        elif java[position] == "}":
            depth -= 1
            if depth == 0:
                return java[index:position + 1]
    raise AssertionError("method not closed: " + start)


def _java_string(text):
    return json.dumps(text)


@unittest.skipUnless(TOOLING, "no JDK on this machine, or no WorkManager jars in the Gradle cache")
class ThePhoneAnswersTheSameTable(unittest.TestCase):
    """The generated status() -- lifted verbatim, compiled, run on real
    WorkInfo objects -- against the rule, scenario by scenario."""

    def _harness(self):
        java = _generated_runtime()
        methods = [_method(java, "    static String status(List<WorkInfo> infos"),
                   _method(java, "    static long backoffSeconds("),
                   _method(java, "    static String retryMessage(")]
        calls = []
        for name, (running, pending, last, policy, base, history) in SCENARIOS.items():
            calls.append("        l = new ArrayList<>();")
            for state in history:
                calls.append("        l.add(info(WorkInfo.State.%s, 1, -1, null));" % state)
            if running:
                calls.append("        l.add(info(WorkInfo.State.RUNNING, %d, %d, %s));" % (
                    running["attempt"], running["progress"], _java_string(running["message"])))
            for used in pending:
                calls.append("        l.add(info(WorkInfo.State.ENQUEUED, %d, -1, null));" % used)
            calls.append('        System.out.println(%s + "|" + status(l, %s, %dL, %s));' % (
                _java_string(name), _java_string(json.dumps(last) if last else ""),
                base, "true" if policy == "linear" else "false"))
        return ("import androidx.work.Data;\nimport androidx.work.WorkInfo;\n"
                "import org.json.JSONObject;\nimport java.util.*;\n"
                "public class StatusHarness {\n"
                '    static final String PROGRESS = "%s";\n'
                '    static final String MESSAGE = "%s";\n'
                % (jobs_codegen.PROGRESS_KEY, jobs_codegen.MESSAGE_KEY)
                + "\n".join(methods) + "\n"
                "    static WorkInfo info(WorkInfo.State state, int count, int progress, String message) {\n"
                "        Data.Builder b = new Data.Builder();\n"
                "        if (progress >= 0) b.putInt(PROGRESS, progress);\n"
                "        if (message != null) b.putString(MESSAGE, message);\n"
                "        return new WorkInfo(UUID.randomUUID(), state, new HashSet<String>(),"
                " Data.EMPTY, b.build(), count, 0);\n"
                "    }\n"
                "    public static void main(String[] args) {\n"
                "        List<WorkInfo> l;\n" + "\n".join(calls) + "\n    }\n}\n")

    def test_both_sides_answer_every_scenario_the_same(self):
        javac, java, jars = TOOLING
        work = tempfile.mkdtemp(prefix="apkpy-jobstatus-")
        source = os.path.join(work, "StatusHarness.java")
        with open(source, "w", encoding="utf-8") as handle:
            handle.write(self._harness())
        classpath = os.pathsep.join(jars)
        built = subprocess.run([javac, "-nowarn", "-encoding", "UTF-8", "-cp", classpath,
                                "-d", work, source], capture_output=True, text=True)
        self.assertEqual(0, built.returncode, built.stdout + built.stderr)
        ran = subprocess.run([java, "-Dfile.encoding=UTF-8", "-cp",
                              work + os.pathsep + classpath, "StatusHarness"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, ran.returncode, ran.stdout + ran.stderr)
        answers = dict(line.split("|", 1) for line in ran.stdout.splitlines() if "|" in line)
        self.assertEqual(set(answers), set(SCENARIOS))
        for name in SCENARIOS:
            with self.subTest(scenario=name):
                self.assertEqual(json.loads(answers[name]), _python(name))


class ThePreviewersQueueReportsThroughTheRule(unittest.TestCase):
    """The real JobDef, its thread and its persistence."""

    def setUp(self):
        self.names = []

    def tearDown(self):
        for name in self.names:
            try:
                os.remove(os.path.join(jobs_preview._jobs_dir(),
                                       "%s.json" % jobs_preview._safe_name(name)))
            except OSError:
                pass

    def _job(self, name, run, **options):
        name = "jobstatus_" + name
        self.names.append(name)
        try:
            os.remove(os.path.join(jobs_preview._jobs_dir(),
                                   "%s.json" % jobs_preview._safe_name(name)))
        except OSError:
            pass
        job = jobs_preview.JobDef(name, run=run, **options)
        return job

    def _wait(self, job, state, seconds=6):
        deadline = time.time() + seconds
        while time.time() < deadline:
            if job.status()["state"] == state:
                return job.status()
            time.sleep(0.03)
        self.fail("never reached %s; last: %s" % (state, job._status_document()))

    def test_success_keeps_the_last_word_and_survives_a_restart(self):
        holder = {}

        def body():
            holder["job"].progress(60, "almost")
            holder["job"].progress(90, "done")

        job = holder["job"] = self._job("success", body)
        job.enqueue({})
        status = self._wait(job, "success")
        self.assertEqual((status["progress"], status["message"], status["attempt"]),
                         ("100", "done", "1"))
        again = jobs_preview.JobDef(job.name, run=body)
        self.assertEqual(again.status()["state"], "success")
        self.assertEqual(again.status()["message"], "done")

    def test_fail_keeps_its_message(self):
        holder = {}

        def body():
            holder["job"].progress(30, "gave up")
            holder["job"].fail()

        job = holder["job"] = self._job("fail", body)
        job.enqueue({})
        status = self._wait(job, "failed")
        self.assertEqual((status["progress"], status["message"]), ("0", "gave up"))

    def test_a_retry_is_a_retry_and_still_pending(self):
        holder = {"tries": 0}
        release = threading.Event()

        def body():
            holder["tries"] += 1
            if holder["tries"] == 1:
                holder["job"].retry()

        job = holder["job"] = self._job("retry", body)
        # Keep the real backoff out of the test: the message still says 30 s,
        # because it comes from the rule, not from this sleep.
        job._backoff_seconds = lambda attempt: 0.4
        job.enqueue({})
        status = self._wait(job, "retry")
        self.assertEqual(status["message"], "Retrying in 30 s (attempt 1)")
        self.assertEqual((status["pending"], status["attempt"]), ("1", "1"))
        status = self._wait(job, "success")
        self.assertEqual(status["attempt"], "2")
        release.set()

    def test_enqueue_while_running_stays_running(self):
        started, release = threading.Event(), threading.Event()

        def body():
            started.set()
            release.wait(5)

        job = self._job("busy", body, unique=False)
        job.enqueue({})
        self.assertTrue(started.wait(5))
        job.enqueue({})
        status = job.status()
        self.assertEqual((status["state"], status["pending"]), ("running", "1"))
        release.set()
        self._wait(job, "success")

    def test_cancel(self):
        release = threading.Event()
        job = self._job("cancel", lambda: release.wait(5))
        job.enqueue({})
        job.cancel()
        status = job.status()
        self.assertEqual((status["state"], status["progress"], status["message"]),
                         ("cancelled", "0", ""))
        release.set()


class TheWorkerLeavesItsLastWord(unittest.TestCase):

    HEAD = ('from apkpy_lib import *\nhome = Screen(id="home")\n'
            'out = label("", id="out", screen=home)\n')
    TAIL = ('j = background_job("sync", run=task, retry="linear", retry_seconds=20)\n'
            'def shown(doc):\n    out.set_value(doc["state"])\n'
            'j.observe(on_change=shown, screen=home)\n'
            'button("Go", id="b", screen=home, command=lambda: j.enqueue())\n'
            'run(start_screen=home)\n')

    def _files(self, body):
        files = translate_python_to_android(self.HEAD + "def task():\n" + body + self.TAIL)
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:400])
        return files

    def _worker(self, files):
        return [t for n, t in files.items() if n.endswith("JobWorker.java")][0]

    def test_a_plain_job_finishes_through_the_record(self):
        worker = self._worker(self._files('    j.progress(50, "half")\n'))
        self.assertIn("        return _jobFinish(true);\n    }", worker)
        self.assertIn('ApkpyJobs.record(getApplicationContext(), "sync", ok ? "success" : "failed",', worker)
        self.assertIn("_apkpyJobMessage = message == null ? \"\" : message;", worker)
        self.assertNotIn("return Result.success();\n    }", worker.split("private Result _jobFinish")[0])

    def test_retry_and_fail_go_through_it_too(self):
        worker = self._worker(self._files('    j.fail()\n'))
        self.assertIn('if ("retry".equals(_apkpyJobOutcome)) return Result.retry();', worker)
        self.assertIn('return _jobFinish(!"fail".equals(_apkpyJobOutcome));', worker)

    def test_an_early_return(self):
        worker = self._worker(self._files('    if storage.get("k") == "x":\n        return\n'
                                          '    storage.set("k", "x")\n'))
        self.assertIn("return _jobFinish(true);", worker.split("} catch")[0])

    def test_the_observer_and_cancel_read_and_write_the_same_place(self):
        files = self._files('    storage.set("k", "1")\n')
        runtime = files["java/ApkpyJobs.java"]
        activity = files["java/Screen_homeActivity.java"]
        self.assertIn('ApkpyJobs.status(getApplicationContext(), "sync", _infos)', activity)
        self.assertIn('record(context, name, "cancelled", 0, "", 0);', runtime)
        self.assertIn('if ("sync".equals(name)) return 20L;', runtime)
        self.assertIn('if ("sync".equals(name)) return true;', runtime)

    def test_a_service_is_not_a_job(self):
        source = (self.HEAD + 'def tick():\n    storage.set("t", "1")\n\n'
                  'service.every(run=tick, minutes=15)\nrun(start_screen=home)\n')
        files = translate_python_to_android(source)
        worker = [t for n, t in files.items() if n.endswith("Worker.java")][0]
        self.assertIn("return Result.success();", worker)
        self.assertNotIn("_jobFinish", worker)


if __name__ == "__main__":
    unittest.main()
