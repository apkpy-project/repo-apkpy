# -*- coding: utf-8 -*-
"""The native seam: your own Java, and everything it is not allowed to be.

Two halves have to agree here. The Java goes into the Activity and the
``preview=`` answers on the desktop, so most of these tests come in pairs: what
the generator writes, and what the Previewer does with the same declaration.
"""

import unittest

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.diagnostics import ApkpyError
from apkpy_lib.features.native import native as preview_native

HEAD = (
    'from apkpy_lib import Screen, background_job, button, label, native, run, storage\n'
    'home = Screen(id="home")\n'
    'out = label("", id="out", screen=home)\n'
)
SYNC = ('battery = native.java("batteryLevel", code="return String.valueOf(1);",\n'
        '                      preview=lambda: "87")\n')
ASYNC = ('reader = native.java_async("readCard", args=("id",),\n'
         '                           code="done.run(true, id);",\n'
         '                           preview=lambda card, done: done(True, card))\n')


def _files(module="", body="    out.set_value(\"hi\")"):
    source = (HEAD + module + "\n\ndef got(ok, value):\n    out.set_value(value)\n"
              "\n\ndef go():\n" + body +
              '\n\nbutton("Go", id="b", screen=home, command=go)\n'
              'run(start_screen=home)\n')
    return translate_python_to_android(source)


def _java(module="", body="    out.set_value(\"hi\")"):
    files = _files(module, body)
    if "error.txt" in files:
        raise AssertionError(files["error.txt"][:400])
    return "\n".join(value for name, value in files.items()
                     if name.endswith(".java"))


def _error(module="", body="    out.set_value(\"hi\")"):
    """The rendered diagnostic, or None when it compiled."""
    return _files(module, body).get("error.txt")


def _flat(text):
    return " ".join((text or "").split())


class TheGeneratedJavaTests(unittest.TestCase):
    """A block becomes a method of the Activity, with the author's code in it."""

    def test_a_sync_block_is_a_method_that_answers_a_string(self):
        java = _java(SYNC, "    out.set_value(battery())")
        self.assertIn("private String _apkpyNative_batteryLevel() {", java)
        self.assertIn("return String.valueOf(1);", java)
        # The Context is handed over, so a block does not reach for the Activity.
        self.assertIn("final android.content.Context context = this;", java)
        self.assertIn('/** native.java("batteryLevel") -- writehere.py:', java)

    def test_a_value_call_never_puts_the_word_null_on_a_screen(self):
        java = _java(SYNC, "    out.set_value(battery())")
        self.assertIn("_apkpyNativeText(_apkpyNative_batteryLevel())", java)
        self.assertIn("private String _apkpyNativeText(String value) {", java)

    def test_an_async_block_answers_through_done(self):
        java = _java(ASYNC, '    reader("A12", on_result=got)')
        self.assertIn(
            "private void _apkpyNative_readCard(String id, final ApkpyNativeDone done) {",
            java)
        self.assertIn("pythonCallback_got(ok, value);", java)

    def test_the_answer_is_moved_to_the_ui_thread(self):
        # A block may answer from a binder thread; touching a view from there
        # throws CalledFromWrongThreadException far away from the cause.
        java = _java(ASYNC, '    reader("A12", on_result=got)')
        self.assertIn("private ApkpyNativeDone _apkpyNativeMain(", java)
        self.assertIn("runOnUiThread(new Runnable() {", java)
        self.assertIn("_apkpyNativeMain(new ApkpyNativeDone()", java)

    def test_an_async_block_without_on_result_still_runs(self):
        java = _java(ASYNC, '    reader("A12")')
        self.assertIn("_apkpyNative_readCard(String.valueOf(\"A12\")", java)

    def test_imports_are_added_once_each(self):
        module = (
            'a = native.java("first", imports=["android.os.BatteryManager"],\n'
            '                code="return String.valueOf(1);", preview=lambda: "1")\n'
            'b = native.java("second", imports=["android.os.BatteryManager"],\n'
            '                code="return String.valueOf(2);", preview=lambda: "2")\n')
        java = _java(module, "    out.set_value(a() + b())")
        self.assertEqual(java.count("import android.os.BatteryManager;"), 1)

    def test_an_app_without_native_gets_none_of_it(self):
        java = _java()
        self.assertNotIn("ApkpyNativeDone", java)
        self.assertNotIn("_apkpyNativeText", java)
        files = _files()
        self.assertNotIn("native/gradle.txt", files)
        self.assertNotIn("native/keep.pro", files)


class TheBuildAroundItTests(unittest.TestCase):
    """Most real cases are code plus a dependency plus a manifest line."""

    MODULE = (SYNC +
              'native.gradle("implementation \'com.example:sdk:2.1.0\'")\n'
              'native.manifest(permission="android.permission.VIBRATE")\n'
              'native.manifest(feature="android.hardware.nfc")\n'
              'native.manifest(xml="<service android:name=\\"com.example.Sync\\" />")\n'
              'native.keep("com.example.sdk.**")\n')

    def setUp(self):
        self.files = _files(self.MODULE, "    out.set_value(battery())")
        self.assertNotIn("error.txt", self.files,
                         self.files.get("error.txt", "")[:300])

    def test_the_permission_is_asked_for_like_any_other(self):
        manifest = self.files["AndroidManifest.xml"]
        self.assertIn('<uses-permission android:name="android.permission.VIBRATE"',
                      manifest)

    def test_hardware_is_described_but_never_required(self):
        # required="true" hides the app from every phone without the part.
        self.assertIn('<uses-feature android:name="android.hardware.nfc" '
                      'android:required="false" />',
                      self.files["AndroidManifest.xml"])

    def test_an_element_of_your_own_is_added_inside_the_application(self):
        # Until 1.13.0 this only looked for the element, and it was there --
        # beside <application>, where Android reads a <service> as nothing.
        manifest = self.files["AndroidManifest.xml"]
        self.assertIn('<service android:name="com.example.Sync" />', manifest)
        self.assertLess(manifest.index("<application"), manifest.index("com.example.Sync"))
        self.assertLess(manifest.index("com.example.Sync"), manifest.index("</application>"))

    def test_an_element_that_belongs_beside_the_application_stays_there(self):
        files = _files(SYNC + 'native.manifest(xml="<queries><package '
                              'android:name=\\"com.example\\" /></queries>")\n',
                       "    out.set_value(battery())")
        manifest = files["AndroidManifest.xml"]
        self.assertLess(manifest.index("<queries>"), manifest.index("<application"))

    def test_a_permission_under_its_whole_name_is_the_one_apkpy_asks_for(self):
        # https needs INTERNET and says so by its last word; asked for here
        # under its whole name it was a second constant of the same name in
        # every Activity, and javac stopped the build.
        files = _files(SYNC + 'native.manifest(permission="android.permission.INTERNET")\n',
                       '    out.set_value(battery())\n'
                       '    https.get("https://example.com/a", on_response=got)')
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:300])
        java = files["java/Screen_homeActivity.java"]
        self.assertEqual(java.count("PERMISSION_REQ_INTERNET ="), 1)
        self.assertEqual(
            files["AndroidManifest.xml"].count('android.permission.INTERNET"'), 1)

    def test_the_dependency_and_the_keep_rule_reach_the_build(self):
        self.assertEqual(self.files["native/gradle.txt"].strip(),
                         "implementation 'com.example:sdk:2.1.0'")
        self.assertIn("-keep class com.example.sdk.** { *; }",
                      self.files["native/keep.pro"])


class TheRefusalTests(unittest.TestCase):
    """Every shape that would compile to something nobody meant."""

    def _says(self, module, body, *phrases):
        text = _error(module, body)
        self.assertIsNotNone(text, "compiled, but should have stopped")
        flat = _flat(text)
        self.assertIn("U2035", flat)
        for phrase in phrases:
            self.assertIn(phrase, flat)

    def test_a_block_without_a_preview(self):
        # Without it the block works on the phone and does nothing on the
        # desktop, which is the divergence this project keeps paying for.
        self._says('x = native.java("a", code="return String.valueOf(1);")',
                   "    out.set_value(x())", "preview= is missing")

    def test_code_that_is_put_together_at_run_time(self):
        self._says('n = "1"\nx = native.java("a", code=f"return {n};", preview=lambda: "1")',
                   "    out.set_value(x())", "cannot be an f-string")

    def test_a_verb_that_does_not_exist(self):
        self._says('native.kotlin("fun main() {}")', '    out.set_value("hi")',
                   "native has no kotlin()")

    def test_a_sync_block_that_never_returns(self):
        self._says('x = native.java("a", code="int n = 1;", preview=lambda: "1")',
                   "    out.set_value(x())", "never returns")

    def test_an_async_block_that_never_answers(self):
        self._says('x = native.java_async("a", code="int n = 1;", preview=lambda d: None)',
                   "    x()", "never calls done")

    def test_too_many_arguments_as_a_value(self):
        self._says(SYNC, '    out.set_value(battery("extra"))',
                   "takes 0 argument(s), got 1")

    def test_too_many_arguments_as_a_statement(self):
        self._says(SYNC, '    battery("extra")', "takes 0 argument(s), got 1")

    def test_an_async_block_used_as_a_value(self):
        self._says(ASYNC, '    out.set_value(reader("A12"))',
                   "answers later, through done")

    def test_on_result_that_is_not_a_function_you_defined(self):
        self._says(ASYNC, '    reader("A12", on_result=lambda ok, v: None)',
                   "has to be a function you defined")

    def test_a_gradle_line_that_is_not_a_dependency(self):
        self._says('native.gradle("compile \'a:b:1.0\'")', '    out.set_value("hi")',
                   "one Gradle dependency line")

    def test_a_directive_used_as_a_value(self):
        self._says('g = native.gradle("implementation \'a:b:1.0\'")',
                   '    out.set_value("hi")', "does not return anything")

    def test_manifest_xml_that_rewrites_the_application(self):
        self._says('native.manifest(xml="<application android:label=\'x\' />")',
                   '    out.set_value("hi")', "cannot rewrite <application>")

    def test_a_block_called_from_a_background_job(self):
        # The method lives on the Activity; a Worker has no screen to borrow.
        module = (SYNC + "\ndef sincronizar():\n    storage.set(\"n\", battery())\n"
                  "\nfila = background_job(\"outbox\", run=sincronizar)\n")
        self._says(module, "    out.set_value(battery())",
                   "runs on a screen, not in a background job")


class ThePreviewerHalfTests(unittest.TestCase):
    """The desktop answers through preview=, and refuses the same shapes."""

    def test_a_sync_block_answers_its_preview(self):
        block = preview_native.java("previewSync", code="return String.valueOf(1);",
                                    preview=lambda: "87")
        self.assertEqual(block(), "87")

    def test_an_async_block_answers_through_on_result(self):
        block = preview_native.java_async(
            "previewAsync", args=("id",), code="done.run(true, id);",
            preview=lambda card, done: done(True, "card:" + card))
        seen = []
        block("A12", on_result=lambda ok, value: seen.append((ok, value)))
        self.assertEqual(seen, [(True, "card:A12")])

    def test_done_run_reads_the_same_as_the_java(self):
        block = preview_native.java_async(
            "previewRun", args=("id",), code="done.run(false, id);",
            preview=lambda card, done: done.run(False, "lost"))
        seen = []
        block("A12", on_result=lambda ok, value: seen.append((ok, value)))
        self.assertEqual(seen, [(False, "lost")])

    def test_an_answer_arrives_once(self):
        def twice(card, done):
            done(True, "first")
            done(True, "second")
        block = preview_native.java_async("previewOnce", args=("id",),
                                          code="done.run(true, id);", preview=twice)
        seen = []
        block("A12", on_result=lambda ok, value: seen.append(value))
        self.assertEqual(seen, ["first"])

    def test_the_desktop_refuses_what_the_build_refuses(self):
        with self.assertRaises(ApkpyError):
            preview_native.java("noPreview", code="return String.valueOf(1);")
        block = preview_native.java("previewArity", code="return String.valueOf(1);",
                                    preview=lambda: "1")
        with self.assertRaises(ApkpyError):
            block("extra")
        with self.assertRaises(ApkpyError):
            block(on_result=print)
        with self.assertRaises(ApkpyError):
            preview_native.manifest()


if __name__ == "__main__":       # pragma: no cover
    unittest.main()
