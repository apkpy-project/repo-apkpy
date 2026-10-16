# -*- coding: utf-8 -*-
"""Two silent bugs an AI agent found while writing a habit tracker.

1. ``x["key"]`` on a screen handed back the whole value unless the compiler
   knew ``x`` was a loop row. It assumed a list_view row's "title — subtitle"
   text: ``item["title"]`` cut the text, and every other key -- a tapped row's
   ``"id"``, ``first["name"]`` after ``first = rows[0]``, a dict written in
   the source, a json_get() record -- became the entire value. The UPDATE
   matched nothing, on the phone only.

2. A function running on one screen that changed a component on another was
   dropped from that screen's Java without a word: each screen is its own
   Activity and only has its own views. The Previewer updated the label.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import pending_views


def _files(source):
    files = translate_python_to_android(source)
    if "error.txt" in files:
        raise AssertionError(files["error.txt"][:500])
    return files


def _method(java, name):
    start = java.index(name)
    return java[start:java.index("\n    }\n", start)]


ONE_SCREEN = '''from apkpy_lib import *
home = Screen(id="home")
out = label("", screen=home)
%s
button("Go", command=go, screen=home)
run(start_screen=home)
'''


class AKeyReadsTheKey(unittest.TestCase):

    def _set_text(self, body):
        java = _files(ONE_SCREEN % body)["java/Screen_homeActivity.java"]
        return re.findall(r"setText\(String\.valueOf\((.*?)\)\);", _method(java, "void pythonCallback_go"))[-1]

    def test_a_dict_written_in_the_source(self):
        self.assertEqual(self._set_text('d = {"a": "x", "b": "y"}\ndef go():\n    out.set_value(d["b"])'),
                         '_jsonGet(String.valueOf(d), "b")')

    def test_a_row_taken_from_a_query(self):
        body = ('def go():\n    rows = db.query("SELECT name FROM t")\n'
                '    first = rows[0]\n    out.set_value(first["name"])')
        self.assertEqual(self._set_text(body), '_jsonGet(String.valueOf(first), "name")')

    def test_title_is_a_key_like_any_other(self):
        body = ('def go():\n    rows = db.query("SELECT title FROM t")\n'
                '    first = rows[0]\n    out.set_value(first["title"])')
        self.assertEqual(self._set_text(body), '_jsonGet(String.valueOf(first), "title")')

    def test_the_em_dash_guess_is_gone(self):
        java = _files(ONE_SCREEN % 'd = {"title": "x"}\ndef go():\n    out.set_value(d["title"])')
        self.assertNotIn('indexOf(" — ")', java["java/Screen_homeActivity.java"])


LIST_APP = '''from apkpy_lib import *
home = Screen(id="home")
db.execute("CREATE TABLE IF NOT EXISTS habits (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, done TEXT)")
def toggle(item):
    db.execute("UPDATE habits SET done = 'yes' WHERE id = ?", [item["id"]])
habits = list_view([{"title": "Read", "id": 7}], id="habits", on_click=toggle, screen=home)
def refresh():
    rows = db.query("SELECT id, name, done FROM habits")
    habits.set_items(rows, title="name", subtitle="done")
refresh()
run(start_screen=home)
'''


class ATappedRowIsTheRow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.java = _files(LIST_APP)["java/Screen_homeActivity.java"]

    def test_the_callback_reads_the_id(self):
        self.assertIn('String.valueOf(_jsonGet(String.valueOf(item), "id"))',
                      _method(self.java, "void pythonCallback_toggle"))

    def test_rows_from_a_query_keep_every_column(self):
        refresh = _method(self.java, "void pythonCallback_refresh")
        self.assertRegex(refresh, r"new org\.json\.JSONObject\(_jo_\w+\.toString\(\)\)")
        self.assertRegex(refresh, r'_no_\w+\.put\("title", _t_\w+\);')
        self.assertRegex(refresh, r"lst1_items\.add\(_no_\w+\.toString\(\)\);")

    def test_a_row_written_in_the_source_keeps_its_keys(self):
        added = re.findall(r"lst1_items\.add\((\".*?\")\);", self.java)
        self.assertTrue(any('\\"id\\": \\"7\\"' in a for a in added), added)

    def test_the_row_still_shows_its_text(self):
        self.assertIn("tv.setText(_apkpyRowText(getItem(pos)));", self.java)
        self.assertIn("private static String _apkpyRowText(String row)", self.java)

    def test_an_app_without_a_list_view_carries_no_row_helper(self):
        java = _files(ONE_SCREEN % 'def go():\n    out.set_value("x")')["java/Screen_homeActivity.java"]
        self.assertNotIn("_apkpyRowText", java)

    def test_the_previewer_hands_over_the_whole_row_too(self):
        from apkpy_lib import ui
        rows_list = ui.ComponentDef("list", items=[])
        rows_list.set_items([{"id": 7, "name": "Read", "done": ""}], title="name", subtitle="done")
        row = rows_list._initial_value[0]
        self.assertEqual((row["id"], row["title"], row["subtitle"]), (7, "Read", ""))


TWO_SCREENS = '''from apkpy_lib import *
home = Screen(id="home")
stats = Screen(id="stats")
total = label("", id="total", screen=stats)
badge = label("New", id="badge", screen=stats)
def add():
    total.set_value("Habits: 1")
    badge.hide()
def local():
    total.set_value("here")
button("Add", command=add, screen=home)
button("Local", command=local, screen=stats)
%s
bottom_nav([home, stats], labels=["Home", "Stats"], icons=["home", "chart"])
run(start_screen=home)
'''


class AnotherScreensComponent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = _files(TWO_SCREENS % "")
        cls.home = cls.files["java/Screen_homeActivity.java"]
        cls.stats = cls.files["java/Screen_statsActivity.java"]

    def test_the_write_is_left_for_the_screen_that_owns_it(self):
        add = _method(self.home, "void pythonCallback_add")
        self.assertIn('ApkpyPending.put("stats", "total:value", String.valueOf("Habits: 1"));', add)
        self.assertIn('ApkpyPending.put("stats", "badge:visible", String.valueOf("0"));', add)

    def test_the_owner_writes_its_own_directly(self):
        local = _method(self.stats, "void pythonCallback_local")
        self.assertIn('setText(String.valueOf("here"));', local)
        self.assertNotIn("ApkpyPending", local)

    def test_the_owner_takes_it_when_it_comes_to_the_front(self):
        apply = _method(self.stats, "private void _apkpyApplyPending()")
        self.assertIn('ApkpyPending.take("stats", "total:value")', apply)
        self.assertIn('ApkpyPending.take("stats", "badge:visible")', apply)
        resume = _method(self.stats, "protected void onResume()")
        self.assertIn('ApkpyPending.inFront("stats", _apkpyApplyPendingRun);', resume)
        self.assertIn("_apkpyApplyPending();", resume)
        self.assertIn('ApkpyPending.behind("stats", _apkpyApplyPendingRun);',
                      _method(self.stats, "protected void onPause()"))

    def test_what_it_computes_on_resume_is_newer(self):
        files = _files(TWO_SCREENS % "def recount():\n    total.set_value(\"fresh\")\n"
                                     "lifecycle(stats, on_resume=recount)")
        resume = _method(files["java/Screen_statsActivity.java"], "protected void onResume()")
        self.assertLess(resume.index("_apkpyApplyPending();"),
                        resume.index("pythonCallback_recount();"))

    def test_the_class_is_written_only_when_needed(self):
        self.assertIn("java/ApkpyPending.java", self.files)
        single = _files(ONE_SCREEN % 'def go():\n    out.set_value("x")')
        self.assertNotIn("java/ApkpyPending.java", single)
        self.assertNotIn("ApkpyPending", single["java/Screen_homeActivity.java"])

    def test_the_plan_names_owner_and_kinds(self):
        from apkpy_lib.core.compiler import MultiScreenTranspiler
        import ast
        transpiler = MultiScreenTranspiler()
        transpiler.visit(ast.parse(TWO_SCREENS % ""))
        owners, targets = pending_views.plan(
            transpiler.screen_components, transpiler.functions, transpiler.module_init_cmds)
        self.assertEqual(owners["total"], "stats")
        self.assertEqual(targets["stats"]["total"], {"value"})
        self.assertEqual(targets["stats"]["badge"], {"visible"})


class AnotherScreensList(unittest.TestCase):
    """set_items on a list that lives on another screen: the rows are
    normalised where the function runs, by the same code the list's own
    screen would run, and left for that screen. Checked on an emulator: with
    the box switched off, a Stats list brought back to the front was stale."""

    APP = '''from apkpy_lib import *
home = Screen(id="home")
stats = Screen(id="stats")
done = list_view([], id="done", screen=stats)
feed = virtual_collection([], template={"title": "{name}"}, id="feed", screen=stats)
def publish():
    rows = db.query("SELECT id, name, 'ok' AS status FROM habits")
    done.set_items(rows, title="name", subtitle="status")
    feed.set_items(rows)
button("Publish", command=publish, screen=home)
bottom_nav([home, stats], labels=["Home", "Stats"], icons=["home", "chart"])
run(start_screen=home)
'''

    @classmethod
    def setUpClass(cls):
        files = _files(cls.APP)
        cls.home = files["java/Screen_homeActivity.java"]
        cls.stats = files["java/Screen_statsActivity.java"]

    def test_the_rows_are_normalised_as_the_list_would_store_them(self):
        publish = _method(self.home, "void pythonCallback_publish")
        # the list_view keeps the record, with the title and subtitle it shows
        self.assertIn('optString("name", "")', publish)
        self.assertIn("_apkpyPend_items.add(_no_", publish)
        self.assertIn('ApkpyPending.put("stats", "done:items", '
                      'String.valueOf(new org.json.JSONArray(_apkpyPend_items).toString()));', publish)
        self.assertIn('ApkpyPending.put("stats", "feed:items"', publish)

    def test_the_owner_fills_and_refreshes_its_lists(self):
        apply = _method(self.stats, "private void _apkpyApplyPending()")
        for key, java_list in (("done:items", "lst1"), ("feed:items", "vc1")):
            block = apply[apply.index(key):]
            end = block.find("\n        }\n")      # the last block ends the method
            block = block if end == -1 else block[:end]
            self.assertIn(f"{java_list}_items.clear();", block)
            self.assertIn(f"{java_list}_items.add(_pa.getString(_pi));", block)
            self.assertIn(f"{java_list}Adapter.notifyDataSetChanged();", block)

    def test_one_screens_own_list_is_filled_directly(self):
        files = _files(self.APP.replace('screen=stats)\nfeed', 'screen=home)\nfeed'))
        publish = _method(files["java/Screen_homeActivity.java"], "void pythonCallback_publish")
        self.assertNotIn('"done:items"', publish)
        self.assertIn("lst1_items.clear();", publish)


class ModuleCodeWritesOnlyToItsOwnScreen(unittest.TestCase):
    """The Previewer runs module-level code once; each Activity runs it again
    in onCreate. A write it made to another screen would be left in the box
    every time a screen opened, and reset that screen -- text somebody typed
    there -- when it came back."""

    APP = '''from apkpy_lib import *
home = Screen(id="home")
stats = Screen(id="stats")
total = label("", id="total", screen=stats)

def refresh():
    total.set_value("Habits: 0")

refresh()
bottom_nav([home, stats], labels=["Home", "Stats"], icons=["home", "chart"])
run(start_screen=home)
'''

    def test_the_box_is_muted_while_module_code_runs(self):
        home = _files(self.APP)["java/Screen_homeActivity.java"]
        on_create = _method(home, "protected void onCreate")
        muted = on_create.index("ApkpyPending.mute(true);")
        self.assertLess(muted, on_create.index("pythonCallback_refresh();"))
        self.assertLess(on_create.index("pythonCallback_refresh();"),
                        on_create.index("ApkpyPending.mute(false);"))

    def test_the_class_honours_it(self):
        java = pending_views.shared_class_java("com.apkpy.app")
        put = java[java.index("public static void put"):]
        self.assertIn("if (muted) return;", put[:put.index("box.put")])

    def test_an_app_that_needs_no_box_has_no_mute(self):
        java = _files(ONE_SCREEN % 'def go():\n    out.set_value("x")')["java/Screen_homeActivity.java"]
        self.assertNotIn("mute(", java)


class EmptyExtraKeysAreNotWritten(unittest.TestCase):

    def test_a_row_keeps_what_it_has_and_skips_what_is_empty(self):
        import json
        from apkpy_lib.core.compiler import _list_row_java_literal
        literal = _list_row_java_literal(
            {"title": "Walk", "subtitle": "", "id": 7, "src": ""})
        row = json.loads(literal[1:-1].encode().decode("unicode_escape"))
        self.assertEqual(row, {"title": "Walk", "subtitle": "", "id": "7"})


def _android_jar():
    sdk = Path(os.environ.get("ANDROID_HOME")
               or Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk")
    jars = sorted(sdk.glob("platforms/android-*/android.jar"),
                  key=lambda p: int(re.sub(r"\D", "", p.parent.name) or 0))
    return jars[-1] if jars else None


def _javac():
    jbr = Path(r"C:\Program Files\Android\Android Studio\jbr\bin\javac.exe")
    return str(jbr) if jbr.exists() else shutil.which("javac")


@unittest.skipUnless(_android_jar() and _javac(), "no JDK or no Android SDK on this machine")
class ThePendingClassCompiles(unittest.TestCase):

    def test_it_compiles_against_android(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ApkpyPending.java"
            path.write_text(pending_views.shared_class_java("com.apkpy.app"), encoding="utf-8")
            result = subprocess.run(
                [_javac(), "-encoding", "UTF-8", "-cp", str(_android_jar()), "-d", tmp, str(path)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr[-1500:])


if __name__ == "__main__":
    unittest.main()
