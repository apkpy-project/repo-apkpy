# -*- coding: utf-8 -*-
"""Android 16 (API 36): the level an app is built for.

Google Play takes new apps and updates only at the newest level but one, and
since 31 August 2026 that is 36. The builds said 35 (and the Studio's project
writer 34): an app made with ApkPy could not be sent to the store.

Raising the number is one line. What it switches on is not: an app that
targets 36 gets Android's new Back on a phone with Android 16 -- its
Activities are no longer handed onBackPressed(), and the Back key is no
longer sent to a window. Four places counted on one or the other: the drawer
(Back closes the panel first), the camera screen (Back answers "cancelled"),
the web page inside the app (Back is the page's history first) and the
picture viewer (Back sends the picture home). These hold them to the forms
Android still calls, so the next one written the old way fails here and not
on somebody's phone.

What a phone showed (Android 16, the old code built for 36 beside the new):
the page was the one that broke -- Back on its second page closed it instead
of going a page back. The viewer closed without its way home, the drawer
still closed (its library takes Back itself from Android 13 on), and the
camera's leaving is read as "cancelled" either way. So one fault that
people would have met, and three pieces of code that had stopped running.
"""

import re
import tempfile
import unittest
from pathlib import Path

import apkpy_lib
from apkpy_lib import config
from apkpy_lib import native_build
from apkpy_lib.cli import generate_gradle_files
from apkpy_lib.core import android_project
from apkpy_lib.core.features import kit
from apkpy_lib.core.features import zoom

from test_drawer import APP as DRAWER_APP, _build

ENGINE = Path(apkpy_lib.__file__).resolve().parent
PLAY_ASKS_FOR = 36          # since 2026-08-31; the next one is due a year on


def _sources():
    """Every file of the engine that Java is written in or from."""
    for path in sorted((ENGINE / "core").rglob("*")):
        if path.suffix in (".java", ".py") and "__pycache__" not in path.parts:
            yield path, path.read_text(encoding="utf-8")


class TheLevel(unittest.TestCase):

    def test_it_is_one_number_and_it_is_what_the_store_asks_for(self):
        self.assertGreaterEqual(config.TARGET_SDK, PLAY_ASKS_FOR)
        # Built against at least what it says it was made for.
        self.assertGreaterEqual(config.COMPILE_SDK, config.TARGET_SDK)
        self.assertEqual(config.MIN_SDK, 24)

    def test_the_gradle_files_say_it(self):
        with tempfile.TemporaryDirectory() as folder:
            generate_gradle_files(folder, "com.apkpy.app", "level",
                                  application_id="com.example.level")
            app = Path(folder, "app", "build.gradle").read_text(encoding="utf-8")
            properties = Path(folder, "gradle.properties").read_text(encoding="utf-8")
        self.assertIn("compileSdk %d\n" % config.COMPILE_SDK, app)
        self.assertIn("targetSdk %d\n" % config.TARGET_SDK, app)
        self.assertIn("minSdk %d\n" % config.MIN_SDK, app)
        # The plugin was tested up to 35 and would say so on every build.
        self.assertIn("android.suppressUnsupportedCompileSdk=%d\n" % config.COMPILE_SDK,
                      properties)

    def test_the_studios_project_says_the_same(self):
        gradle = android_project._app_build_gradle("com.example.level", 1, "1.0", [])
        self.assertIn("compileSdk %d\n" % config.COMPILE_SDK, gradle)
        self.assertIn("targetSdk %d\n" % config.TARGET_SDK, gradle)
        self.assertIn("minSdk %d\n" % config.MIN_SDK, gradle)

    def test_setup_installs_the_platform_the_build_asks_for(self):
        self.assertIn("platforms;android-%d" % config.COMPILE_SDK, native_build._SDK_PACKAGES)

    def test_an_sdk_is_asked_whether_it_has_the_platform(self):
        with tempfile.TemporaryDirectory() as sdk:
            self.assertFalse(native_build.has_platform(sdk))
            self.assertFalse(native_build.has_platform(""))
            # No sdkmanager in it: nothing is run, and it says so.
            said = []
            self.assertFalse(native_build.install_platform(sdk, "jdk", log=said.append))
            self.assertEqual(said, [])
            older = Path(sdk, "platforms", "android-%d" % (config.COMPILE_SDK - 1))
            older.mkdir(parents=True)
            (older / "android.jar").write_bytes(b"")
            self.assertFalse(native_build.has_platform(sdk))
            there = Path(sdk, "platforms", "android-%d" % config.COMPILE_SDK)
            there.mkdir(parents=True)
            self.assertFalse(native_build.has_platform(sdk))      # a folder is not a platform
            (there / "android.jar").write_bytes(b"")
            self.assertTrue(native_build.has_platform(sdk))
            self.assertTrue(native_build.install_platform(sdk, "jdk", log=said.append))

    def test_doctor_and_setup_say_which_level_is_missing(self):
        from click.testing import CliRunner
        from apkpy_lib import cli
        with tempfile.TemporaryDirectory() as sdk:
            found = {"jdk_home": "jdk", "jdk_major": 17, "sdk": sdk, "gradle": "gradle",
                     "system_java": 17}
            kept = native_build.discover_toolchain
            native_build.discover_toolchain = lambda: dict(found)
            try:
                doctor = CliRunner().invoke(cli.main, ["doctor"]).output
                setup = CliRunner().invoke(cli.main, ["setup"]).output
                there = Path(sdk, "platforms", "android-%d" % config.COMPILE_SDK)
                there.mkdir(parents=True)
                (there / "android.jar").write_bytes(b"")
                with_it = CliRunner().invoke(cli.main, ["doctor"]).output
                setup_with_it = CliRunner().invoke(cli.main, ["setup"]).output
            finally:
                native_build.discover_toolchain = kept
        level = "API %d" % config.COMPILE_SDK
        self.assertIn(level, doctor)
        self.assertIn("not installed yet", doctor)
        self.assertIn("READY", doctor)                  # the build can fetch it
        self.assertIn("without the %s platform" % level, setup)
        self.assertNotIn("Android SDK OK.", setup)
        self.assertRegex(with_it, r"API %d\s+: installed" % config.COMPILE_SDK)
        self.assertIn("Android SDK OK.", setup_with_it)

    def test_no_other_level_is_written_anywhere(self):
        # A line of a Gradle file, not a sentence about one in a comment.
        written = re.compile(r"^\s*(?:compileSdk|targetSdk|minSdk)\s+\d+\s*$", re.M)
        for path in sorted(ENGINE.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            found = written.findall(path.read_text(encoding="utf-8"))
            self.assertEqual(found, [], "%s writes a level of its own" % path.name)


class Back(unittest.TestCase):
    """onBackPressed() of an Activity and the Back key are not called on
    Android 16 for an app that targets it."""

    def test_nothing_listens_for_the_key(self):
        for path, text in _sources():
            for old in ("OnKeyListener", "onKeyDown(", "onKeyUp("):
                self.assertNotIn(old, text, "%s listens for the Back key" % path.name)
            # The key alone is what breaks on Android 16. Beside Android's own
            # callback it is the way the same Back reaches a phone of Android
            # 13 to 15, where an app that has not opted in to the new Back is
            # still sent the key and never the callback.
            if "KEYCODE_BACK" in text:
                self.assertIn("registerOnBackInvokedCallback", text,
                              "%s listens for the Back key alone" % path.name)

    def test_only_a_dialog_has_an_onBackPressed(self):
        # A Dialog's is still called, by the key before Android 16 and by
        # Android's own callback from it on; an Activity's is not.
        allowed = {"ApkpyBrowser.java", "zoom.py"}
        for path, text in _sources():
            if "void onBackPressed()" not in text:
                continue
            self.assertIn(path.name, allowed, "%s overrides onBackPressed()" % path.name)
            for match in re.finditer(r"void onBackPressed\(\)", text):
                before = text[:match.start()]
                opened = before.rfind("new Dialog(")
                self.assertGreater(opened, before.rfind("class "),
                                   "%s: not inside a Dialog made on the spot" % path.name)

    def test_no_screen_that_is_written_overrides_it(self):
        files = _build(DRAWER_APP)
        for name, text in files.items():
            if name.endswith(".java"):
                self.assertNotIn("void onBackPressed()", text, name)
                self.assertNotIn("KEYCODE_BACK", text, name)

    def test_the_drawer_takes_back_only_while_it_shows(self):
        java = _build(DRAWER_APP)["java/Screen_chatActivity.java"]
        self.assertIn("new androidx.activity.OnBackPressedCallback(false)", java)
        self.assertIn("getOnBackPressedDispatcher().addCallback(this, _apkpyDrawerBack);", java)
        self.assertIn("onDrawerSlide(android.view.View _panel, float _shown)", java)
        self.assertIn("onDrawerClosed(android.view.View _panel)", java)
        # Built again with the panel open, no listener says so.
        self.assertIn("_apkpyDrawerRoot.post(() -> _apkpyDrawerBack.setEnabled(", java)
        # Registered after the panel is found, in the same onCreate.
        self.assertLess(java.index("_apkpyDrawerRoot = findViewById(R.id.apkpy_drawer);"),
                        java.index("getOnBackPressedDispatcher().addCallback("))

    def test_a_screen_without_a_drawer_has_none_of_it(self):
        files = _build('from apkpy_lib import *\nhome = Screen(id="home")\n'
                       'label("x", id="t", screen=home)\nrun(start_screen=home)\n')
        java = files["java/Screen_homeActivity.java"]
        self.assertNotIn("OnBackPressed", java)

    def test_the_camera_answers_cancelled(self):
        java = (ENGINE / "core" / "features" / "camera_android.java").read_text(encoding="utf-8")
        self.assertIn("getOnBackPressedDispatcher().addCallback(this,", java)
        self.assertIn("handleOnBackPressed(){cancel();}", java)
        self.assertIn("new androidx.activity.OnBackPressedCallback(true)", java)

    def test_the_page_goes_back_before_it_closes(self):
        java = kit.java_source("ApkpyBrowser", "p")
        override = java[java.index("public void onBackPressed()"):]
        self.assertIn("if (back[0] != null) back[0].run();", override[:200])
        self.assertIn("else super.onBackPressed();", override[:200])
        self.assertRegex(java, r"back\[0\] = new Runnable\(\) \{[^}]*"
                               r"if \(page\.canGoBack\(\)\) page\.goBack\(\);\s*"
                               r"else dialog\.dismiss\(\);")

    def test_the_picture_goes_home(self):
        java = zoom.JAVA
        self.assertIn("public void onBackPressed()", java)
        self.assertRegex(java, r"back\[0\] = new Runnable\(\) \{\s*"
                               r"@Override public void run\(\) \{ viewer\.close\(\); \}")
        # Told what to do before it is shown.
        self.assertLess(java.index("back[0] = new Runnable()"), java.index("dialog.show();"))


if __name__ == "__main__":
    unittest.main()
