# -*- coding: utf-8 -*-
"""Text kept in the app's own folder.

    files.write("notes.txt", text)      files.append("log.txt", line)
    text = files.read("notes.txt")

Three calls of the same table as the rest of the kit. What these tests hold:
the phone and the desk take the same names and refuse the same ones, text
comes back exactly as it went in, a name never leaves the app's folder, and
an app that only keeps text is not built with the screen that waits for a
file picker.
"""

import io
import os
import re
import shutil
import subprocess
import tempfile
import unittest

import apkpy_lib
from apkpy_lib import job_rules
from apkpy_lib import kit_rules as rules
from apkpy_lib import ui
from apkpy_lib.core import unsupported
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import kit
from apkpy_lib.diagnostics import ApkpyError
from apkpy_lib.features import kit as preview

from test_data_rules import TOOLING
from test_kit import HEAD, TAIL, _built, _error, _java, needs_sdk

# name -> what file_name() makes of it
NAMES = [
    ("notes.txt", "notes.txt"),
    (" notes.txt ", "notes.txt"),
    ("drafts/monday.txt", "drafts/monday.txt"),
    ("a/b/c.json", "a/b/c.json"),
    (".hidden", ".hidden"),
    ("a b.txt", "a b.txt"),
    ("caf\u00e9.txt", "caf\u00e9.txt"),
    ("\u65e5\u672c\u8a9e/\u30e1\u30e2.txt", "\u65e5\u672c\u8a9e/\u30e1\u30e2.txt"),
    ("party\U0001f389.txt", "party\U0001f389.txt"),
    ("console.txt", "console.txt"),
    ("COM10.log", "COM10.log"),
    ("x" * 255, "x" * 255),
    ("\u00e9" * 127 + "a", "\u00e9" * 127 + "a"),
    # nothing at all
    ("", ""), ("   ", ""),
    # leaving the folder
    ("/etc/passwd", ""), ("../secret", ""), ("a/../b", ""), ("./a", ""), ("..", ""),
    ("a//b", ""), ("a/", ""),
    # what a desk cannot write
    ("a:b", ""), ("C:\\Users\\x", ""), ("a\\b", ""), ("what?", ""), ("star*", ""),
    ("<x>", ""), ("pipe|", ""), ('q"uote', ""), ("tab\there", ""), ("a\nb", ""),
    ("a\x7fb", ""), ("end.", ""), ("a./b", ""), ("a /b", ""), ("a/ b", ""),
    ("nul", ""), ("NUL.txt", ""), ("com1.log", ""), ("lpt9", ""), ("Con", ""),
    ("aux.tar.gz", ""),
    # too long for a file system
    ("x" * 256, ""), ("\u00e9" * 128, ""),
    # ApkPy's own
    (".apkpy-notes.txt.tmp", ""), ("drafts/.apkpy-x", ""),
]


class TheNames(unittest.TestCase):
    """One rule says what a file may be called, and both sides ask it."""

    def test_a_name_is_kept_or_refused(self):
        for given, wanted in NAMES:
            self.assertEqual(rules.file_name(given), wanted, repr(given))

    def test_what_is_not_text_is_read_as_text(self):
        self.assertEqual(rules.file_name(None), "")
        self.assertEqual(rules.file_name(7), "7")

    @needs_sdk
    def test_the_two_languages_agree(self):
        def literal(text):
            out = []
            for ch in text:
                if ch in '"\\':
                    out.append("\\" + ch)
                elif ch == "\n":
                    out.append("\\n")
                elif ch == "\t":
                    out.append("\\t")
                elif 32 <= ord(ch) < 127:
                    out.append(ch)
                else:
                    units = ch.encode("utf-16-be")
                    out.extend("\\u%02x%02x" % (units[i], units[i + 1])
                               for i in range(0, len(units), 2))
            return '"' + "".join(out) + '"'

        def plain(text):
            units = text.encode("utf-16-be")
            out = []
            for i in range(0, len(units), 2):
                code = units[i] * 256 + units[i + 1]
                out.append(chr(code) if code < 128 else "<%04x>" % code)
            return "".join(out)

        lines = ['System.out.println("%d|" + plain(ApkpyKitRules.fileName(%s)));'
                 % (index, literal(given)) for index, (given, _wanted) in enumerate(NAMES)]
        javac, java_bin, _jar = TOOLING
        work = tempfile.mkdtemp(prefix="apkpy-files-rules-")
        with io.open(os.path.join(work, "ApkpyKitRules.java"), "w", encoding="utf-8") as handle:
            handle.write(kit.java_source("ApkpyKitRules", "p").replace("package p;", ""))
        with io.open(os.path.join(work, "Harness.java"), "w", encoding="utf-8") as handle:
            handle.write("public class Harness {\n"
                         "    static String plain(String text) {\n"
                         "        StringBuilder out = new StringBuilder();\n"
                         "        for (char ch : text.toCharArray()) {\n"
                         "            if (ch < 128) out.append(ch);\n"
                         "            else out.append(String.format(\"<%04x>\", (int) ch));\n"
                         "        }\n"
                         "        return out.toString();\n"
                         "    }\n"
                         "    public static void main(String[] a) {\n        "
                         + "\n        ".join(lines) + "\n    }\n}\n")
        built = subprocess.run([javac, "-encoding", "UTF-8", "-d", work,
                                os.path.join(work, "ApkpyKitRules.java"),
                                os.path.join(work, "Harness.java")],
                               capture_output=True, text=True)
        self.assertEqual(0, built.returncode, built.stdout + built.stderr)
        ran = subprocess.run([java_bin, "-cp", work, "Harness"],
                             capture_output=True, text=True, encoding="ascii")
        self.assertEqual(0, ran.returncode, ran.stdout + ran.stderr)
        answers = ran.stdout.splitlines()
        self.assertEqual(len(answers), len(NAMES))
        for line in answers:
            index, answer = line.split("|", 1)
            given, wanted = NAMES[int(index)]
            self.assertEqual(answer, plain(wanted), repr(given))
        shutil.rmtree(work, ignore_errors=True)


class WhatIsBuilt(unittest.TestCase):
    """Each call is one line of Java in a class that needs nothing around it."""

    BODY = ('text = files.read("notes.txt")\n'
            'word = files.write("notes.txt", text)\n'
            'files.append("log.txt", word)\n'
            'out.set_value(text)')

    def test_each_call_is_one_line(self):
        java = _java(self.BODY)
        self.assertIn("return ApkpyFiles.read(this, name);", java)
        self.assertIn("return ApkpyFiles.write(this, name, text);", java)
        self.assertIn("return ApkpyFiles.append(this, name, text);", java)

    def test_an_app_that_keeps_text_is_built_with_nothing_else(self):
        files = _built(self.BODY)
        folder = os.path.dirname(kit.__file__)
        ours = {file[:-5] for file in os.listdir(folder) if file.endswith(".java")}
        written = sorted(name[5:-5] for name in files
                         if name.startswith("java/") and name[5:-5] in ours)
        self.assertEqual(written, ["ApkpyFiles", "ApkpyKit", "ApkpyKitRules"])
        manifest = files["AndroidManifest.xml"]
        self.assertNotIn("ApkpyKitActivity", manifest)
        self.assertNotIn("uses-permission", manifest)

    def test_beside_a_file_for_the_person(self):
        files = _built('files.write("a.txt", "a")\n'
                       'files.save_copy("a.txt", on_result=answered)')
        for name in ("ApkpyFiles", "ApkpySaveFile", "ApkpyKitActivity"):
            self.assertIn("java/%s.java" % name, files)

    def test_the_older_verbs_are_still_the_generators_own(self):
        java = _java('if files.exists("a.txt"):\n'
                     '    out.set_value(files.read(files.path("a.txt")))')
        self.assertIn("getFilesDir()", java)
        self.assertIn("_apkpyNative_files_read(", java)

    def test_a_verb_with_a_class_of_its_own_is_in_that_class(self):
        for namespace in rules.SPEC:
            for name in rules.verbs(namespace):
                found = rules.verb(namespace, name)
                if not found.home:
                    continue
                source = kit.java_source(found.home, "p")
                self.assertRegex(source, r"public static String %s\(Context context" % found.java,
                                 rules.label(namespace, name))


class WhatStopsTheBuild(unittest.TestCase):

    def _stops(self, body, *words, code="U2048"):
        text = _error(body)
        self.assertIn(code, text)
        for word in words:
            self.assertIn(word, text)

    def test_a_call_written_wrong(self):
        self._stops('files.write("a.txt")', "files.write() needs text")
        self._stops('files.read()', "files.read() needs name")
        self._stops('files.read("a.txt", on_result=answered)', "files.read() has no on_result=")
        self._stops('out.set_value(files.read)', "files.read() is missing its brackets")

    def test_inside_a_background_job(self):
        source = (HEAD +
                  'def work(job):\n'
                  '    files.write("a.txt", "a")\n\n'
                  'sync = background_job("sync", run=work)\n'
                  'def go():\n'
                  '    sync.enqueue()\n' + TAIL)
        text = " ".join(translate_python_to_android(source).get("error.txt", "").split())
        self.assertIn("J7004", text)
        self.assertIn("files.write() cannot run inside a background job", text)

    def test_open_is_answered_with_calls_that_exist(self):
        self._stops('handle = open("a.txt")', "files.read(name)", code="U2033")
        # Every files call the advice names is one the library has: twice an
        # error sent people to files.read() before there was one.
        advice = [unsupported.BUILTINS, unsupported.REPLACEMENTS,
                  {key: " ".join(value[1]) for key, value in unsupported.STATEMENT_ADVICE.items()}]
        named = set()
        for table in advice:
            for text in table.values():
                named |= set(re.findall(r"\bfiles\.([a-z_]+)\(", text))
        self.assertTrue({"read", "write"} <= named)
        for name in named:
            self.assertTrue(callable(getattr(apkpy_lib.files, name, None)), name)


class OnTheDesk(unittest.TestCase):
    """The Previewer keeps the same files, by the same rule."""

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="apkpy-files-")
        ui.files._dir = lambda: self.folder
        self.files = apkpy_lib.files

    def tearDown(self):
        del ui.files._dir
        shutil.rmtree(self.folder, ignore_errors=True)

    def _bytes(self, *parts):
        with open(os.path.join(self.folder, *parts), "rb") as handle:
            return handle.read()

    def test_what_is_written_comes_back(self):
        text = "caf\u00e9 \U0001f389\r\nsecond line\nthird"
        self.assertEqual(self.files.write("notes.txt", text), "ok")
        self.assertEqual(self.files.read("notes.txt"), text)
        # UTF-8, and no line ending changed on the way.
        self.assertEqual(self._bytes("notes.txt"), text.encode("utf-8"))

    def test_writing_again_replaces_and_leaves_nothing_behind(self):
        self.files.write("notes.txt", "a long first version")
        self.assertEqual(self.files.write("notes.txt", "short"), "ok")
        self.assertEqual(self.files.read("notes.txt"), "short")
        self.assertEqual(os.listdir(self.folder), ["notes.txt"])

    def test_append_adds_to_the_end_and_makes_the_file(self):
        self.assertEqual(self.files.append("log.txt", "one\n"), "ok")
        self.assertEqual(self.files.append("log.txt", "two\n"), "ok")
        self.assertEqual(self.files.read("log.txt"), "one\ntwo\n")

    def test_a_folder_in_the_name_is_made(self):
        self.assertEqual(self.files.write("drafts/2026/monday.txt", "x"), "ok")
        self.assertEqual(self._bytes("drafts", "2026", "monday.txt"), b"x")
        self.assertEqual(self.files.read("drafts/2026/monday.txt"), "x")

    def test_the_whole_path_means_the_same_file(self):
        whole = self.files.path("notes.txt")
        self.assertEqual(self.files.write(whole, "by path"), "ok")
        self.assertEqual(self.files.read("notes.txt"), "by path")
        self.assertEqual(self.files.read(whole), "by path")
        self.assertTrue(self.files.exists("notes.txt"))

    def test_a_name_never_leaves_the_folder(self):
        outside = os.path.join(os.path.dirname(self.folder), "apkpy-files-outside.txt")
        with open(outside, "w") as handle:
            handle.write("not the app's")
        try:
            for name in ("../apkpy-files-outside.txt", outside, "", "a/../../x.txt"):
                self.assertEqual(self.files.write(name, "taken"), "invalid", name)
                self.assertEqual(self.files.append(name, "taken"), "invalid", name)
                self.assertEqual(self.files.read(name), "", name)
            with open(outside) as handle:
                self.assertEqual(handle.read(), "not the app's")
            self.assertEqual(os.listdir(self.folder), [])
        finally:
            os.remove(outside)

    def test_no_file_reads_as_nothing(self):
        self.assertEqual(self.files.read("never-written.txt"), "")
        os.mkdir(os.path.join(self.folder, "box"))
        self.assertEqual(self.files.read("box"), "")

    def test_a_folder_is_not_written_over(self):
        os.mkdir(os.path.join(self.folder, "box"))
        self.assertEqual(self.files.write("box", "x"), "failed")
        self.assertEqual(self.files.append("box", "x"), "failed")
        self.assertEqual(os.listdir(self.folder), ["box"])

    def test_a_byte_order_mark_is_not_part_of_the_text(self):
        with open(os.path.join(self.folder, "from-an-editor.txt"), "wb") as handle:
            handle.write(b"\xef\xbb\xbfhello")
        self.assertEqual(self.files.read("from-an-editor.txt"), "hello")

    def test_a_file_that_is_not_text_does_not_stop_the_app(self):
        with open(os.path.join(self.folder, "photo.jpg"), "wb") as handle:
            handle.write(b"\xff\xd8\xffA")
        self.assertTrue(self.files.read("photo.jpg").endswith("A"))

    def test_what_is_not_text_is_written_as_text(self):
        self.assertEqual(self.files.write("count.txt", 12), "ok")
        self.assertEqual(self.files.read("count.txt"), "12")
        self.assertEqual(self.files.write("empty.txt", None), "ok")
        self.assertEqual(self.files.read("empty.txt"), "")

    def test_a_job_body_is_refused_with_the_builds_words(self):
        calls = {"read": lambda: preview.read("a.txt"),
                 "write": lambda: preview.write("a.txt", "a"),
                 "append": lambda: preview.append("a.txt", "a")}
        for name, call in calls.items():
            with job_rules.running_job():
                with self.assertRaises(ApkpyError) as caught:
                    call()
            self.assertEqual(caught.exception.code, "J7004")
            self.assertIn("files.%s() cannot run inside a background job" % name,
                          str(caught.exception))
        self.assertEqual(os.listdir(self.folder), [])


if __name__ == "__main__":
    unittest.main()
