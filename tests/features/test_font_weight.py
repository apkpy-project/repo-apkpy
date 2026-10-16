# -*- coding: utf-8 -*-
"""Bold that the phone's font forgets.

On a Xiaomi (HyperOS, Android 16) with a font theme, every weight of the
system font links to one variable file and the system never turns its weight
axis: `font-weight: bold`, DEFAULT_BOLD, a button's medium and a toolbar title
all drew regular. Measured there at 100px: regular 1034, DEFAULT_BOLD 1046,
`'wght' 700` 1115 -- only the last looked bold. The app now measures that once
and, only where bold is forgotten, gives each text its weight through the axis.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import font_weight

APP = '''from apkpy_lib import *
style = """
#title { font-weight: bold; font-size: 22px; }
"""
home = Screen(id="home")
other = Screen(id="other")
label("Today", id="title", screen=home)
label("Other", screen=other)
'''

APP_WITH_OVERLAYS = '''from apkpy_lib import *
home = Screen(id="home")
sheet = bottom_sheet("Pick", items=["A", "B"])
ask = modal("Delete?", "It cannot be undone.")

def warn():
    alert("Hi", "there")

button("Sheet", command=lambda: sheet.open(), screen=home)
button("Ask", command=lambda: ask.open(), screen=home)
button("Alert", command=warn, screen=home)
'''


def _files(source):
    files = translate_python_to_android(source)
    if "error.txt" in files:
        raise AssertionError(files["error.txt"][:400])
    return files


class EveryWindowIsWatched(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = _files(APP)

    def test_the_class_is_written(self):
        self.assertIn("java/ApkpyWeight.java", self.files)

    def test_each_screen_watches_right_after_its_layout(self):
        for sid in ("home", "other"):
            activity = self.files[f"java/Screen_{sid}Activity.java"]
            self.assertRegex(
                activity,
                r"setContentView\(R\.layout\.activity_screen_%s\);\n"
                r"\s+ApkpyWeight\.watch\(getWindow\(\)\);" % sid)

    def test_the_xml_still_asks_for_bold(self):
        """The fix adds to the bold, it does not replace it: a phone whose
        bold works draws exactly what it drew before."""
        layout = self.files["res/layout/activity_screen_home.xml"]
        self.assertIn('android:textStyle="bold"', layout)
        self.assertNotIn("fontVariationSettings", layout)


class OverlaysAreWindowsToo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.activity = _files(APP_WITH_OVERLAYS)["java/Screen_homeActivity.java"]

    def test_each_overlay_is_watched_after_it_is_shown(self):
        self.assertGreaterEqual(
            self.activity.count("dialog.show();\n        ApkpyWeight.watch(dialog.getWindow());"), 2)

    def test_the_alert_is_watched(self):
        self.assertIn("ApkpyWeight.watch(new AlertDialog.Builder(this)", self.activity)
        self.assertIn(".show().getWindow());", self.activity)


class TheRule(unittest.TestCase):
    """Read off the Java, because the rule is the part that decides whether a
    phone is touched at all."""

    JAVA = font_weight.shared_class_java("com.apkpy.app")

    def test_measured_against_the_axis_not_a_fixed_number(self):
        self.assertIn(
            "axis - regular > 1f && bold - regular < 0.25f * (axis - regular)", self.JAVA)

    def test_a_phone_whose_bold_works_is_left_alone(self):
        watch = self.JAVA[self.JAVA.index("public static void watch"):]
        self.assertIn("if (window == null || !systemBoldIsForgotten()) return;",
                      watch[:watch.index("}")])

    def test_below_android_8_nothing_is_measured(self):
        self.assertIn("if (Build.VERSION.SDK_INT >= 26) {", self.JAVA)

    def test_medium_counts_as_well_as_bold(self):
        self.assertIn("if (weight >= 500) {", self.JAVA)

    def test_a_text_that_stops_being_bold_loses_the_weight(self):
        self.assertIn("} else if (GIVEN.remove(text) != null) {", self.JAVA)

    def test_the_screen_is_never_held_twice_in_a_row(self):
        self.assertIn("if (fix(root) && held == 0) {", self.JAVA)


class BoldInsideAText(unittest.TestCase):

    def test_rich_content_asks_for_its_bold_through_the_class(self):
        from apkpy_lib.core.features import rich_content
        java = rich_content.generate_rich_content_view_java("com.apkpy.app")
        self.assertNotIn("new StyleSpan(Typeface.BOLD)", java)
        self.assertEqual(java.count("ApkpyWeight.boldSpan()"), 3)
        # italic is not a weight; it stays as it was
        self.assertIn("new StyleSpan(Typeface.ITALIC)", java)


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
class ItCompiles(unittest.TestCase):

    def test_the_class_compiles_against_android(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ApkpyWeight.java"
            path.write_text(font_weight.shared_class_java("com.apkpy.app"), encoding="utf-8")
            result = subprocess.run(
                [_javac(), "-encoding", "UTF-8", "-cp", str(_android_jar()),
                 "-d", tmp, str(path)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr[-1500:])


if __name__ == "__main__":
    unittest.main()
