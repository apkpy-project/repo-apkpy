"""Focused tests for the any-file picker and ``upload_button``."""

import ast
import mimetypes
import unittest

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import file_picker


class NormaliseTypesTests(unittest.TestCase):
    """``types=`` has to mean the same thing in both runtimes."""

    def test_common_shapes(self):
        cases = {
            None: (["*/*"], [("All files", "*.*")]),
            (): (["*/*"], [("All files", "*.*")]),
            "pdf": (["application/pdf"], [("pdf", "*.pdf"), ("All files", "*.*")]),
            (".pdf",): (["application/pdf"], [(".pdf", "*.pdf"), ("All files", "*.*")]),
            ("application/pdf",): (
                ["application/pdf"],
                [("application/pdf", "*.pdf"), ("All files", "*.*")],
            ),
        }
        for value, expected in cases.items():
            with self.subTest(types=value):
                self.assertEqual(expected, file_picker.normalise_types(value))

    def test_family_keeps_the_wildcard_and_expands_extensions(self):
        mimes, filetypes = file_picker.normalise_types(["image/*"])
        self.assertEqual(["image/*"], mimes)
        self.assertIn("*.png", filetypes[0][1])
        self.assertIn("*.jpg", filetypes[0][1])

    def test_any_mime_absorbs_narrower_types(self):
        # Keeping a narrower type beside */* would advertise a filter that the
        # picker is not applying.
        self.assertEqual(
            (["*/*"], [("All files", "*.*")]),
            file_picker.normalise_types(["pdf", "*/*"]),
        )

    def test_unknown_extension_degrades_to_any(self):
        self.assertEqual(
            (["*/*"], [("All files", "*.*")]),
            file_picker.normalise_types(["zzz"]),
        )

    def test_all_files_escape_hatch_is_always_offered(self):
        # Android document providers routinely ignore EXTRA_MIME_TYPES, so the
        # desktop dialog must never be stricter than the phone.
        _, filetypes = file_picker.normalise_types(["pdf", "docx"])
        self.assertEqual(("All files", "*.*"), filetypes[-1])

    def test_curated_table_beats_the_platform_registry(self):
        # mimetypes reads HKEY_CLASSES_ROOT on Windows, so a machine with
        # Acrobat installed must not answer differently from a clean CI box.
        original = dict(mimetypes.types_map)
        try:
            mimetypes.types_map[".pdf"] = "application/x-hostile"
            self.assertEqual(
                ["application/pdf"], file_picker.normalise_types(["pdf"])[0],
            )
        finally:
            mimetypes.types_map.clear()
            mimetypes.types_map.update(original)


class EmitCommandTests(unittest.TestCase):
    def _emit(self, callback, declared_args, mime_types=None):
        lines = []
        functions_map = {callback: {"args": declared_args}} if callback else {}
        file_picker.emit_command(
            lines, "", {"type": "files_pick", "callback": callback,
                        "mime_types": mime_types or ["*/*"]},
            lambda node: '""', functions_map,
        )
        return lines[0]

    def test_forwards_only_the_declared_arity(self):
        for declared, expected in (
            (["success"], "pythonCallback_cb(_fpOk)"),
            (["success", "path"], "pythonCallback_cb(_fpOk, _fpPath)"),
            (["a", "b", "c", "d", "e"],
             "pythonCallback_cb(_fpOk, _fpPath, _fpName, _fpSize, _fpMime)"),
            # More parameters than the picker supplies: clamp, never overflow.
            (["a", "b", "c", "d", "e", "f", "g"],
             "pythonCallback_cb(_fpOk, _fpPath, _fpName, _fpSize, _fpMime)"),
        ):
            with self.subTest(arity=len(declared)):
                emitted = self._emit("cb", declared)
                self.assertIn(expected + ");", emitted)
                # The lambda always binds five, because Java requires it.
                self.assertIn("(_fpOk, _fpPath, _fpName, _fpSize, _fpMime) ->", emitted)

    def test_unknown_callback_falls_back_to_all_five(self):
        lines = []
        file_picker.emit_command(
            lines, "", {"type": "files_pick", "callback": "ghost",
                        "mime_types": ["*/*"]},
            lambda node: '""', {},
        )
        self.assertIn("pythonCallback_ghost(_fpOk, _fpPath, _fpName, _fpSize, _fpMime)",
                      lines[0])

    def test_missing_callback_passes_null(self):
        lines = []
        file_picker.emit_command(
            lines, "", {"type": "files_pick", "callback": None,
                        "mime_types": ["*/*"]},
            lambda node: '""', {},
        )
        self.assertEqual('_filePick(new String[]{"*/*"}, null);', lines[0])

    def test_lambda_parameters_never_shadow_application_names(self):
        # Java rejects a lambda parameter that reuses an enclosing parameter,
        # so these must not be named success/path/name/size/mime.
        emitted = self._emit("cb", ["success", "path", "name", "size", "mime"])
        header = emitted[emitted.index("(_fp"):emitted.index("->")]
        for reserved in ("success", "path", "name", "size", "mime"):
            self.assertNotIn(reserved, header)


class UploadButtonParseTests(unittest.TestCase):
    """``upload_button`` is sugar: it must leave the emitter untouched."""

    SOURCE = '''
from apkpy_lib import Screen, label, run, upload_button
home = Screen(id="home")
status = label("", id="status", screen=home)
def done(success, response):
    status.set_value(response)
upload_button("SEND", url="https://x.dev/f", types=["pdf"],
              on_result=done, id="send", screen=home, variant="outlined")
run(start_screen=home)
'''

    def test_generates_a_real_button_wired_to_a_picker(self):
        result = translate_python_to_android(self.SOURCE)
        self.assertNotIn("error.txt", result)
        java = result["java/Screen_homeActivity.java"]
        self.assertIn("<Button", result["res/layout/activity_screen_home.xml"])
        self.assertIn('_filePick(new String[]{"application/pdf"}', java)
        # The upload receives the picker callback's own parameter.
        self.assertIn("String.valueOf(path)", java)

    def test_task_id_defaults_to_the_button_id(self):
        # Without a stable id a double tap would race two uploads instead of
        # restarting one, and uploads.cancel(...) would be impossible.
        java = translate_python_to_android(self.SOURCE)["java/Screen_homeActivity.java"]
        self.assertIn('_uploadMultipart(String.valueOf("send")', java)

    def test_explicit_task_id_wins(self):
        source = self.SOURCE.replace(
            'on_result=done, id="send"', 'on_result=done, task_id="custom", id="send"',
        )
        java = translate_python_to_android(source)["java/Screen_homeActivity.java"]
        self.assertIn('_uploadMultipart(String.valueOf("custom")', java)

    def test_declares_internet_but_no_storage_permission(self):
        manifest = translate_python_to_android(self.SOURCE)["AndroidManifest.xml"]
        self.assertIn("android.permission.INTERNET", manifest)
        self.assertNotIn("READ_EXTERNAL_STORAGE", manifest)
        self.assertNotIn("READ_MEDIA_IMAGES", manifest)

    def test_on_file_runs_before_the_upload_and_carries_no_success_flag(self):
        source = self.SOURCE.replace(
            "def done(success, response):",
            "def chosen(path, name, size, mime):\n"
            "    status.set_value(name)\n"
            "def done(success, response):",
        ).replace("on_result=done,", "on_file=chosen, on_result=done,")
        java = translate_python_to_android(source)["java/Screen_homeActivity.java"]
        self.assertIn(
            "private void pythonCallback_chosen(String path, String name, "
            "String size, String mime)", java,
        )
        self.assertLess(java.index("pythonCallback_chosen(String.valueOf(path)"),
                        java.index("_uploadMultipart("))

    def test_picker_runtime_is_omitted_when_unused(self):
        source = (
            "from apkpy_lib import Screen, label, run\n"
            'home = Screen(id="home")\n'
            'label("hi", screen=home)\n'
            "run(start_screen=home)\n"
        )
        java = translate_python_to_android(source)["java/Screen_homeActivity.java"]
        for absent in ("_filePick", "FilePickResultCallback", "OpenDocument"):
            self.assertNotIn(absent, java)


class GeneratedJavaShapeTests(unittest.TestCase):
    def test_launcher_and_helper_are_balanced(self):
        for snippet in (file_picker.launcher_java(),
                        file_picker.activity_runtime_java()):
            self.assertEqual(snippet.count("{"), snippet.count("}"), snippet[:60])
            self.assertEqual(snippet.count("("), snippet.count(")"), snippet[:60])

    def test_cancelled_pick_reports_the_same_tuple_as_the_previewer(self):
        # The Previewer answers (False, "", "", "0", ""); size is the string
        # "0" so application code can convert it without a guard.
        self.assertIn('cb.onResult(false, "", "", "0", "");',
                      file_picker.launcher_java())
        self.assertIn('cb.onResult(false, "", "", "0", "");',
                      file_picker.activity_runtime_java())

    def test_openable_columns_query_stays_off_the_main_thread(self):
        # A Drive- or OneDrive-backed provider can block on the network here.
        launcher = file_picker.launcher_java()
        self.assertIn("new Thread(new Runnable()", launcher)
        self.assertIn("runOnUiThread", launcher)
        self.assertIn("isDestroyed()", launcher)
        self.assertLess(launcher.index("new Thread(new Runnable()"),
                        launcher.index("OpenableColumns.DISPLAY_NAME"))

    def test_no_persistable_uri_permission_is_requested(self):
        # Persisted grants are a scarce per-app resource and leak silently;
        # OpenDocument's grant already outlives the pick-then-upload flow.
        self.assertNotIn("takePersistableUriPermission", file_picker.launcher_java())
        self.assertNotIn("takePersistableUriPermission",
                         file_picker.activity_runtime_java())


class IsCallTests(unittest.TestCase):
    def _call(self, source):
        return ast.parse(source, mode="eval").body

    def test_matches_only_files_pick(self):
        self.assertTrue(file_picker.is_call(self._call("files.pick(on_result=cb)")))
        self.assertFalse(file_picker.is_call(self._call("gallery.pick(on_result=cb)")))
        self.assertFalse(file_picker.is_call(self._call("files.download(a, b)")))
        self.assertFalse(file_picker.is_call(self._call("pick(on_result=cb)")))


class UploadProgressParityTests(unittest.TestCase):
    """The progress callback must receive the same types on both runtimes.

    Android calls it with three Strings, so `"Uploading " + percent + "%"`
    compiles there.  The Previewer used to pass ints, so the identical line
    raised TypeError on the desktop -- the exact Preview/Android divergence the
    Previewer exists to catch.
    """

    SOURCE = '''
from apkpy_lib import Screen, button, label, uploads, run
home = Screen(id="home")
status = label("", id="status", screen=home)
def progress(percent, sent, total):
    status.set_value("Uploading " + percent + "%")
def start():
    uploads.file("t", "https://x.dev/u", "/tmp/a.bin", on_progress=progress)
button("Go", id="go", command=start, screen=home)
run(start_screen=home)
'''

    def test_android_passes_three_strings(self):
        java = translate_python_to_android(self.SOURCE)["java/Screen_homeActivity.java"]
        self.assertIn(
            "private void pythonCallback_progress(String percent, String sent, "
            "String total)", java,
        )

    def test_previewer_passes_three_strings(self):
        import http.server
        import os
        import tempfile
        import threading

        from apkpy_lib import uploads

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                while length > 0:
                    chunk = self.rfile.read(min(8192, length))
                    if not chunk:
                        break
                    length -= len(chunk)
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()

        received = []
        done = threading.Event()
        handle, path = tempfile.mkstemp(suffix=".bin")
        try:
            with os.fdopen(handle, "wb") as out:
                out.write(b"x" * 200000)
            uploads.file(
                "parity-probe",
                "http://127.0.0.1:%d/upload" % server.server_address[1],
                path,
                on_progress=lambda *args: received.append(args),
                on_result=lambda success, response: done.set(),
            )
            self.assertTrue(done.wait(10), "upload did not finish")
        finally:
            server.shutdown()
            try:
                os.remove(path)
            except OSError:
                pass

        self.assertTrue(received, "no progress callback fired")
        for args in received:
            self.assertEqual(3, len(args))
            for value in args:
                self.assertIsInstance(value, str, received)
        self.assertEqual("0", received[0][0])
        self.assertEqual("100", received[-1][0])


if __name__ == "__main__":
    unittest.main()
