"""Wallpaper confirmation, conditional generation and desktop simulation."""
import ast
from concurrent.futures import Future
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, Mock

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import wallpaper as codegen
from apkpy_lib.features import wallpaper as preview

APP = '''from apkpy_lib import Screen, button, gallery, wallpaper, toast, run
home = Screen(id="home")
def finished(ok, reason):
    if ok:
        toast(reason)
    else:
        toast(reason)
def chosen(ok, path):
    if ok:
        wallpaper.set(path, target="both", on_result=finished)
def choose():
    if wallpaper.available():
        gallery.pick(on_result=chosen)
button("Choose", id="choose", screen=home, command=choose)
run(start_screen=home)
'''


def build(source=APP, **kwargs):
    result = translate_python_to_android(source, **kwargs)
    if "error.txt" in result:
        raise AssertionError(result["error.txt"])
    return result


class WallpaperCompilerTests(unittest.TestCase):
    def test_nested_call_and_callback(self):
        files = build()
        java = files["java/Screen_homeActivity.java"]
        self.assertIn("ApkpyWallpaper.preview", java)
        self.assertIn("pythonCallback_finished(_apkpyWallOk, _apkpyWallReason)", java)
        self.assertIn("boolean ok, String reason", java)
        self.assertIn("ApkpyWallpaper.available(getApplicationContext())", java)
        self.assertEqual(files["AndroidManifest.xml"].count("android.permission.SET_WALLPAPER"), 1)

    def test_unused_app_gets_no_helper_or_permission(self):
        files = build('from apkpy_lib import *\nhome=Screen(id="home")\nlabel("Hi", screen=home)\nrun(start_screen=home)')
        self.assertNotIn("java/ApkpyWallpaper.java", files)
        self.assertNotIn("SET_WALLPAPER", files["AndroidManifest.xml"])

    def test_available_only_no_permission(self):
        files = build(APP.replace('wallpaper.set(path, target="both", on_result=finished)', 'toast("ready")'))
        self.assertIn("java/ApkpyWallpaper.java", files)
        self.assertNotIn("SET_WALLPAPER", files["AndroidManifest.xml"])

    def test_keyword_source_and_dynamic_target(self):
        files = build(APP.replace('wallpaper.set(path, target="both", on_result=finished)',
                                 'wallpaper.set(source=path, target=path, on_result=finished)'))
        self.assertIn("String.valueOf(path), String.valueOf(path)", files["java/Screen_homeActivity.java"])

    def test_lambda_result(self):
        java = build(APP.replace("on_result=finished", "on_result=lambda ok, reason: toast(reason)"))["java/Screen_homeActivity.java"]
        self.assertIn("pythonCallback_wallpaper_result", java)

    def test_distinct_lambdas(self):
        src = APP.replace('wallpaper.set(path, target="both", on_result=finished)',
                          'wallpaper.set(path, on_result=lambda ok, reason: toast("first"))\n        wallpaper.set(path, on_result=lambda ok, reason: toast("second"))')
        java = build(src)["java/Screen_homeActivity.java"]
        self.assertIn('"first"', java)
        self.assertIn('"second"', java)

    def test_no_result_callback(self):
        java = build(APP.replace(", on_result=finished", ""))["java/Screen_homeActivity.java"]
        # No callback means no tag either: there is nobody to hand a late
        # answer to, so nothing is held for a screen that never asked.
        self.assertIn('String.valueOf("both"), null, null)', java)
        self.assertNotIn("ApkpyWallpaper.resumed(", java)

    def test_the_answer_survives_the_screen_being_rebuilt(self):
        """Applying a wallpaper destroys the Activity that asked for it.

        Changing the wallpaper changes the system palette, and a changed
        palette is a configuration change: Android tears the screen down and
        builds a new one. Measured on a phone -- the window handle changes --
        and the old code answered nobody, so an app watched the wallpaper
        change while its own status line still read "Ready".
        """
        java = build()["java/Screen_homeActivity.java"]
        # The request says which callback is waiting for it.
        self.assertIn('"finished", (_apkpyWallOk, _apkpyWallReason)', java)
        # The replacement screen offers the same callback back.
        self.assertIn('ApkpyWallpaper.resumed("finished"', java)
        self.assertIn('ApkpyWallpaper.paused(this, "finished");', java)
        resume = java.index("protected void onResume()")
        self.assertLess(resume, java.index('ApkpyWallpaper.resumed("finished"'))

    def test_the_runtime_holds_an_answer_nobody_could_hear(self):
        runtime = codegen.shared_class_java("com.apkpy.app")
        # Both orders have to work: the answer arriving before the new screen
        # resumes, and the new screen resuming before the answer arrives.
        self.assertIn("handOver(tag, ok, reason);", runtime)
        self.assertIn("public static synchronized void resumed(", runtime)
        self.assertIn("public static synchronized void paused(", runtime)
        self.assertIn("PENDING_TAG", runtime)

    def test_a_screen_that_never_asked_collects_nothing(self):
        held = codegen.callbacks_used({}, [])
        self.assertEqual(held, [])

    def test_every_wallpaper_callback_is_offered_back(self):
        source = APP.replace(
            'wallpaper.set(path, target="both", on_result=finished)',
            'wallpaper.set(path, target="home", on_result=finished)\n'
            '        wallpaper.set(path, target="lock", on_result=chosen)')
        java = build(source)["java/Screen_homeActivity.java"]
        for name in ("finished", "chosen"):
            self.assertIn('ApkpyWallpaper.resumed("%s"' % name, java)

    def test_invalid_argument_diagnostics(self):
        for call in ['wallpaper.set()', 'wallpaper.set(path, target="all")',
                     'wallpaper.set(path, silent=True)', 'wallpaper.set(path, source=path)',
                     'wallpaper.set(path, on_result="wrong")',
                     'wallpaper.set(path, on_result=lambda reason: toast(reason))']:
            with self.subTest(call=call):
                result = translate_python_to_android(APP.replace('wallpaper.set(path, target="both", on_result=finished)', call))
                self.assertIn("error.txt", result)
                self.assertIn("C1700", result["error.txt"])

    def test_available_rejects_arguments(self):
        result = translate_python_to_android(APP.replace("wallpaper.available()", 'wallpaper.available("home")'))
        self.assertIn("C1700", result["error.txt"])

    def test_missing_literal_asset_is_build_error(self):
        result = translate_python_to_android(APP.replace("wallpaper.set(path,", 'wallpaper.set("missing-wallpaper.png",'))
        self.assertIn("Wallpaper image not found", result["error.txt"])

    def test_literal_image_bundled_relative_to_project(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "photo.png")
            Image.new("RGB", (4, 4), "navy").save(source)
            files = build(APP.replace("wallpaper.set(path,", 'wallpaper.set("photo.png",'), project_root=directory)
            assets = [(k, v) for k, v in files.items() if k.startswith("app/src/main/assets/")]
            self.assertEqual(len(assets), 1)
            self.assertEqual(assets[0][1], ("COPY_FILE", str(source.resolve())))
            self.assertIn("asset://apkpy_wallpaper/", files["java/Screen_homeActivity.java"])

    def test_background_write_is_rejected(self):
        source = '''from apkpy_lib import *
home=Screen(id="home")
def work():
    wallpaper.set("content://example/image")
job=background_job("wall", run=work)
run(start_screen=home)
'''
        result = translate_python_to_android(source)
        self.assertIn("error.txt", result)
        self.assertIn("cannot run in a background job", result["error.txt"])

    def test_java_safety_contract(self):
        java = codegen.shared_class_java("com.example.wall")
        self.assertIn("package com.example.wall;", java)
        self.assertEqual(java.count(".setBitmap("), 1)
        self.assertIn("id > 0", java)
        self.assertIn("setBitmap(bitmap, (Rect) null, false, flags)", java)
        self.assertIn("isSetWallpaperAllowed", java)
        self.assertIn("isWallpaperSupported", java)
        self.assertIn("BUSY.compareAndSet(false, true)", java)
        self.assertIn("IO.execute", java)
        self.assertIn("MAIN.post", java)
        self.assertIn("inSampleSize", java)
        self.assertIn("MAX_EDGE = 2048", java)
        self.assertIn("setOnClickListener(v -> apply())", java)
        self.assertIn("unregisterActivityLifecycleCallbacks", java)
        self.assertNotIn("getDrawable()", java)
        self.assertNotIn("HttpURLConnection", java)


class WallpaperPreviewTests(unittest.TestCase):
    def test_exports_and_vocabulary(self):
        from apkpy_lib import wallpaper, WallpaperAPI
        self.assertIsInstance(wallpaper, WallpaperAPI)
        self.assertIs(wallpaper.reasons, codegen.REASONS)
        self.assertTrue(wallpaper.available())

    def test_no_root_is_created(self):
        api = preview.WallpaperAPI()
        calls = []
        with patch("apkpy_lib.ui.live_preview_root", return_value=None):
            api.set("anything", on_result=lambda *args: calls.append(args))
        self.assertEqual(calls, [(False, "unavailable")])

    def test_invalid_target(self):
        calls = []
        preview.WallpaperAPI().set("anything", "all", lambda *args: calls.append(args))
        self.assertEqual(calls, [(False, "invalid_target")])

    def test_bad_callback(self):
        with self.assertRaises(TypeError):
            preview.WallpaperAPI().set("x", on_result="no")

    def test_busy_does_not_queue_another_image(self):
        api = preview.WallpaperAPI()
        api._request = object()
        calls = []
        with patch("apkpy_lib.ui.live_preview_root", return_value=Mock()):
            api.set("x", on_result=lambda *args: calls.append(args))
        self.assertEqual(calls, [(False, "busy")])

    def test_callback_type_error_not_retried(self):
        callback = Mock(side_effect=TypeError("inside user callback"))
        with self.assertRaisesRegex(TypeError, "inside user"):
            preview._answer(callback, True, "simulated")
        callback.assert_called_once()

    def test_finish_is_exactly_once_and_clears_busy(self):
        owner = preview.WallpaperAPI()
        callback = Mock()
        req = preview._PreviewRequest(owner, Mock(), "x", "both", callback)
        owner._request = req
        req.finish(True, "simulated")
        req.finish(False, "cancelled")
        callback.assert_called_once_with(True, "simulated")
        self.assertIsNone(owner._request)

    def test_destroy_suppresses_callback(self):
        owner = preview.WallpaperAPI()
        callback = Mock()
        req = preview._PreviewRequest(owner, Mock(), "x", "both", callback)
        req._root_destroyed(Mock(widget=req.root))
        self.assertTrue(req.finished)
        callback.assert_not_called()

    def test_decode_image_and_limit(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "photo.jpg")
            Image.new("RGB", (4200, 2200), "#38257A").save(path)
            image = preview._load_image(str(path))
            self.assertLessEqual(max(image.size), 2048)
            self.assertEqual(image.mode, "RGB")
            self.assertLessEqual(max(preview._load_image(path.as_uri()).size), 2048)

    def test_invalid_and_remote_images(self):
        for path in ("", None, "https://example.com/a.png", "content://provider/photo", "missing.png"):
            with self.subTest(path=path), self.assertRaises(Exception):
                preview._load_image(path)

    def test_invalid_decode_completes_on_ui(self):
        future = Future()
        future.set_exception(ValueError("bad image"))
        callback = Mock()
        owner = preview.WallpaperAPI()
        req = preview._PreviewRequest(owner, Mock(), "x", "home", callback)
        req.future = future
        req.poll()
        callback.assert_called_once_with(False, "invalid_image")

    def test_real_tk_buttons_without_moving_mouse(self):
        import tkinter as tk
        from PIL import Image
        root = tk.Tk()
        root.withdraw()
        try:
            for target, text, result in [("home", "Cancel", (False, "cancelled")),
                                          ("lock", "Simulate apply", (True, "simulated")),
                                          ("both", "Simulate apply", (True, "simulated"))]:
                owner = preview.WallpaperAPI()
                received = []
                req = preview._PreviewRequest(owner, root, "x", target,
                    lambda *args: received.append((threading.get_ident(), args)))
                owner._request = req
                req.show(Image.new("RGB", (16, 20), "#38257A"))
                req.window.withdraw()
                buttons = req.window.winfo_children()[-1].winfo_children()
                next(button for button in buttons if button.cget("text") == text).invoke()
                self.assertEqual(received, [(threading.get_ident(), result)])
                self.assertIsNone(owner._request)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
