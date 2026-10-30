# -*- coding: utf-8 -*-
"""The torch, and the two things that make it different from the camera.

It asks for no permission, and it does not belong to a screen. Both are easy
to break by accident -- one by reaching for the camera to get at the flash, the
other by keeping the state in a field on an Activity that dies when the person
walks to the next screen -- and neither shows up as a build failure.
"""

import unittest

from apkpy_lib.core.features import flashlight as codegen
from apkpy_lib.core.compiler import translate_python_to_android


APP_WITH_TORCH = '''from apkpy_lib import Screen, button, flashlight, label, run, toast
home = Screen(id="home")
label("dark", id="t", screen=home)


def lit(ok, reason):
    if ok:
        toast("light")
    else:
        toast(reason)


def press():
    if flashlight.available():
        flashlight.toggle(on_result=lit)
    else:
        toast("no torch")


button("Torch", id="go", screen=home, command=press)
run(start_screen=home)
'''

APP_ASKS_ONLY = '''from apkpy_lib import Screen, button, flashlight, label, run, toast
home = Screen(id="home")
label("dark", id="t", screen=home)


def press():
    if flashlight.is_on():
        toast("lit")
    else:
        toast("out")


button("Check", id="go", screen=home, command=press)
run(start_screen=home)
'''

APP_WITHOUT = '''from apkpy_lib import Screen, button, label, run, toast
home = Screen(id="home")
label("plain", id="t", screen=home)
button("Tap", id="go", screen=home, command=lambda: toast("hi"))
run(start_screen=home)
'''

APP_IN_A_JOB = '''from apkpy_lib import Screen, background_job, flashlight, label, run
home = Screen(id="home")
label("x", id="l", screen=home)


def blink():
    flashlight.on()


job = background_job("blink_job", run=blink)
run(start_screen=home)
'''


def _build(source):
    files = translate_python_to_android(source)
    if 'error.txt' in files:
        raise AssertionError(files['error.txt'])
    return files


def _java(source):
    return "\n".join(
        body for name, body in _build(source).items() if name.endswith(".java"))


def _method(source, name):
    """One generated method's body.

    Every user function is written TWICE into an Activity: once as
    ``pythonCallback_x``, and once inlined into the click listener that calls
    it. Counting across the whole file therefore counts everything twice,
    which says nothing about the shape of either copy.
    """
    java = _build(source)["java/Screen_homeActivity.java"]
    head = java.index("private void pythonCallback_%s(" % name)
    depth = 0
    for index in range(java.index("{", head), len(java)):
        if java[index] == "{":
            depth += 1
        elif java[index] == "}":
            depth -= 1
            if depth == 0:
                return java[head:index + 1]
    raise AssertionError("pythonCallback_%s never closes" % name)


class TheVocabularyIsSharedTests(unittest.TestCase):
    """Neither side may invent a word the other does not know."""

    def test_the_previewer_imports_the_compiler_table(self):
        from apkpy_lib.features import flashlight as preview
        self.assertIs(preview.REASONS, codegen.REASONS)
        self.assertIs(preview.flashlight.reasons, codegen.REASONS)

    def test_every_camera_reason_lands_in_the_vocabulary(self):
        for code in list(codegen._ACCESS_CODES) + [0, 99, -3]:
            self.assertIn(codegen.reason_for_access_code(code), codegen.REASONS)

    def test_the_java_switch_has_an_arm_for_every_code(self):
        # The table above is the truth; the switch is generated from it. A hand
        # edit to one and not the other is the drift this catches.
        java = codegen.shared_class_java("com.example")
        for code, reason in codegen._ACCESS_CODES.items():
            self.assertIn('case %d: return "%s";' % (code, reason), java)

    def test_a_reason_the_app_can_read_is_never_empty(self):
        for word, meaning in codegen.REASONS.items():
            self.assertTrue(word.strip(), word)
            self.assertTrue(meaning.strip(), word)


class ItAsksForNoPermissionTests(unittest.TestCase):
    """setTorchMode is not camera access, and the manifest must say so."""

    @classmethod
    def setUpClass(cls):
        cls.files = _build(APP_WITH_TORCH)
        cls.manifest = cls.files["AndroidManifest.xml"]

    def test_the_torch_declares_no_camera_permission(self):
        # The obvious wrong way to get at a flash is to open the camera. That
        # costs a runtime prompt and a line on the store listing, for a light.
        self.assertNotIn("android.permission.CAMERA", self.manifest)

    def test_it_declares_no_permission_at_all(self):
        self.assertNotIn("<uses-permission", self.manifest)

    def test_the_flash_is_described_but_never_required(self):
        self.assertIn(
            '<uses-feature android:name="android.hardware.camera.flash" '
            'android:required="false" />', self.manifest)

    def test_the_implied_camera_feature_is_spelled_out(self):
        # camera.flash implies camera. Left implicit it can inherit a
        # requirement nobody wrote, and the Play Store hides the app from
        # phones without one.
        self.assertIn(
            '<uses-feature android:name="android.hardware.camera" '
            'android:required="false" />', self.manifest)

    def test_an_app_without_a_torch_declares_no_flash(self):
        self.assertNotIn("uses-feature", _build(APP_WITHOUT)["AndroidManifest.xml"])


class TheTorchOutlivesTheScreenTests(unittest.TestCase):
    """A field on an Activity goes out when that Activity does."""

    def test_the_state_lives_in_a_class_of_its_own(self):
        self.assertIn("java/ApkpyTorch.java", _build(APP_WITH_TORCH))

    def test_that_class_holds_no_activity(self):
        java = codegen.shared_class_java("com.example")
        self.assertIn("getApplicationContext()", java)
        self.assertNotIn("Activity", java)

    def test_the_state_is_watched_rather_than_remembered(self):
        # Anything on the phone can change the torch: the quick settings, the
        # camera app, another torch app. A boolean of our own would go on
        # saying "on" about a light somebody else put out.
        java = codegen.shared_class_java("com.example")
        self.assertIn("registerTorchCallback", java)
        self.assertIn("onTorchModeChanged", java)
        self.assertIn("onTorchModeUnavailable", java)

    def test_watching_starts_before_anything_asks(self):
        java = _java(APP_WITH_TORCH)
        self.assertIn("ApkpyTorch.watch(getApplicationContext());", java)
        activity = _build(APP_WITH_TORCH)["java/Screen_homeActivity.java"]
        self.assertLess(activity.index("ApkpyTorch.watch"),
                        activity.index("ApkpyTorch.toggle"))

    def test_the_back_camera_wins(self):
        # A front-facing "flash" is the screen going white, pointed at a face.
        java = codegen.shared_class_java("com.example")
        self.assertIn("LENS_FACING_BACK", java)


class TheStateAtStartupTests(unittest.TestCase):
    """Found on a phone, not in a test: `is_on()` used to lie as a screen opened.

    Registering the callback is how the app learns the state it starts in, and
    the answer comes back through the callback rather than from the call. On a
    phone it took ~34ms -- long after onCreate. A screen asking "is it on?" as
    it opened therefore read the field's default and said "off" about a torch
    that was lit, and a toggle turned an already-lit torch on again.
    """

    @classmethod
    def setUpClass(cls):
        cls.java = codegen.shared_class_java("com.example")

    def test_the_callback_runs_off_the_main_thread(self):
        # This is what makes the wait possible at all: a handler on the main
        # looper could never deliver while the main thread waited for it.
        self.assertIn("HandlerThread", self.java)
        self.assertNotIn("Looper.getMainLooper()", self.java)

    def test_the_first_question_waits_for_the_first_answer(self):
        self.assertIn("CountDownLatch", self.java)
        self.assertIn("sFirstReport.await(", self.java)
        self.assertIn("countDown()", self.java)

    def test_it_waits_at_most_once(self):
        # sSettled is raised BEFORE the wait, so a second caller never queues
        # behind the first.
        head = self.java.index("private static void settle(")
        body = self.java[head:head + 700]
        self.assertLess(body.index("sSettled = true;"), body.index("await("))

    def test_a_phone_with_no_flash_waits_for_nothing(self):
        # Nothing will ever report about a torch that does not exist, so the
        # wait would be the full timeout, every launch.
        head = self.java.index("private static void settle(")
        body = self.java[head:head + 700]
        self.assertLess(body.index("cameraId(context) == null"), body.index("await("))

    def test_the_wait_is_bounded(self):
        self.assertIn("FIRST_REPORT_MS = 300", self.java)
        self.assertIn("TimeUnit.MILLISECONDS", self.java)

    def test_settling_cannot_deadlock_on_the_class_monitor(self):
        # watch() holds the monitor and the callback needs it. Waiting inside
        # it would block the answer being waited for.
        head = self.java.index("private static void settle(")
        self.assertNotIn("synchronized", self.java[head:head + 60])

    def test_toggle_asks_rather_than_assumes(self):
        # A toggle that trusted an unconfirmed state would turn an already-lit
        # torch on again, and the button would look broken.
        head = self.java.index("public static String toggle(")
        self.assertIn("isOn(context)", self.java[head:head + 200])

    def test_setting_the_torch_needs_no_wait(self):
        # An app that acts first knows the state it just wrote.
        head = self.java.index("public static String set(")
        self.assertIn("sSettled = true;", self.java[head:head + 500])


class TheGateTests(unittest.TestCase):
    """An app that never mentions the torch pays nothing for it."""

    def test_no_class_no_watch_no_feature(self):
        files = _build(APP_WITHOUT)
        self.assertNotIn("java/ApkpyTorch.java", files)
        self.assertNotIn("ApkpyTorch", _java(APP_WITHOUT))

    def test_asking_alone_still_writes_the_class(self):
        # is_on() and available() are values, not commands, so the command gate
        # cannot see them. Without a second look at the source, an app whose
        # only mention is `if flashlight.is_on():` would call a class that was
        # never written -- and that is a javac error, not a silent one, which
        # is the only reason it would ever have been noticed.
        files = _build(APP_ASKS_ONLY)
        self.assertIn("java/ApkpyTorch.java", files)
        self.assertIn("ApkpyTorch.isOn(getApplicationContext())",
                      files["java/Screen_homeActivity.java"])


class TheThreeDispatchersTests(unittest.TestCase):
    """Every verb has to be wired in each place, or it vanishes in silence."""

    def test_on_and_off_reach_the_same_call(self):
        java = _java('''from apkpy_lib import Screen, button, flashlight, label, run
home = Screen(id="home")
label("x", id="t", screen=home)
def up():
    flashlight.on()
def down():
    flashlight.off()
button("On", id="a", screen=home, command=up)
button("Off", id="b", screen=home, command=down)
run(start_screen=home)
''')
        self.assertIn("ApkpyTorch.set(getApplicationContext(), true);", java)
        self.assertIn("ApkpyTorch.set(getApplicationContext(), false);", java)

    def test_a_background_job_can_light_it_too(self):
        # Without the Worker arm the command is dropped without a word, which
        # is the most expensive bug shape this compiler has.
        files = _build(APP_IN_A_JOB)
        worker = next(body for name, body in files.items()
                      if name.startswith("java/") and "Worker" in name)
        self.assertIn("ApkpyTorch.set(getApplicationContext(), true);", worker)

    def test_the_result_is_read_once_and_named_the_same_every_time(self):
        # A name made unique from a hash would change between builds. The
        # braced block scopes it instead, so two calls in one method compile.
        body = _method('''from apkpy_lib import Screen, button, flashlight, label, run, toast
home = Screen(id="home")
label("x", id="t", screen=home)
def told(ok, reason):
    toast(reason)
def both():
    flashlight.on(on_result=told)
    flashlight.off(on_result=told)
button("Go", id="a", screen=home, command=both)
run(start_screen=home)
''', "both")
        self.assertEqual(body.count("String _torchReason ="), 2)
        self.assertEqual(body.count("pythonCallback_told(_torchReason"), 2)
        # Two declarations, one name -- which only compiles because each sits
        # in braces of its own.
        self.assertEqual(body.count("{"), body.count("}"))

    def test_the_camera_service_is_asked_only_once_per_call(self):
        # Reading the answer twice would ask the camera service twice, and it
        # is free to answer differently the second time.
        body = _method(APP_WITH_TORCH, "press")
        self.assertEqual(
            body.count("ApkpyTorch.toggle(getApplicationContext())"), 1)


class TheValueAndTheConditionTests(unittest.TestCase):
    """is_on() has to work as a question and as a value."""

    def test_a_condition_becomes_a_real_boolean(self):
        java = _java(APP_ASKS_ONLY)
        self.assertIn("if (ApkpyTorch.isOn(getApplicationContext())) {", java)
        # Not the string comparison a fallback would produce.
        self.assertNotIn('"true".equals(ApkpyTorch', java)

    def test_available_works_as_a_condition_too(self):
        self.assertIn("if (ApkpyTorch.available(getApplicationContext())) {",
                      _java(APP_WITH_TORCH))

    def test_a_value_reads_back_the_way_python_writes_it(self):
        java = _java('''from apkpy_lib import Screen, button, flashlight, label, run
home = Screen(id="home")
mirror = label("", id="m", screen=home)
def show():
    mirror.set_value(flashlight.is_on())
button("Show", id="a", screen=home, command=show)
run(start_screen=home)
''')
        self.assertIn('(ApkpyTorch.isOn(getApplicationContext()) '
                      '? "True" : "False")', java)

    def test_str_is_the_spelling_that_works_on_both_sides(self):
        # Found by rendering the example: `"lit: " + flashlight.is_on()`
        # compiles on Android, where every value is already a String, and
        # raises TypeError in the Previewer, where it is a real Python bool.
        # str() is the one spelling both runtimes read the same way.
        from apkpy_lib.features.flashlight import flashlight as preview
        preview.off()
        with self.assertRaises(TypeError):
            "lit: " + preview.is_on()
        self.assertEqual("lit: " + str(preview.is_on()), "lit: False")

        java = _java('''from apkpy_lib import Screen, button, flashlight, label, run
home = Screen(id="home")
m = label("", id="m", screen=home)
def show():
    m.set_value("lit: " + str(flashlight.is_on()))
button("Show", id="a", screen=home, command=show)
run(start_screen=home)
''')
        self.assertIn('"lit: " + ApkpyValues.text(String.valueOf((ApkpyTorch.isOn('
                      'getApplicationContext()) ? "True" : "False")))', java)

    def test_the_two_runtimes_write_the_same_words(self):
        # The Previewer answers a Python bool; the label shows str() of it. The
        # phone has no bool to show, so the generated Java writes the words
        # Python would have. They have to be the same words.
        from apkpy_lib.features.flashlight import flashlight as preview
        preview.off()
        self.assertEqual(str(preview.is_on()), "False")
        preview.on()
        self.assertEqual(str(preview.is_on()), "True")
        preview.off()
        java = codegen.value_java(
            __import__("ast").parse("flashlight.is_on()").body[0].value)
        self.assertIn('"True"', java)
        self.assertIn('"False"', java)


class ThePreviewerStandsInTests(unittest.TestCase):
    """A desktop has no flash unit, so it says so where a device thing goes."""

    def setUp(self):
        from apkpy_lib.features.flashlight import flashlight
        self.torch = flashlight
        self.torch.off()

    def tearDown(self):
        self.torch.off()

    def test_toggle_flips_and_is_on_follows(self):
        self.assertFalse(self.torch.is_on())
        self.torch.toggle()
        self.assertTrue(self.torch.is_on())
        self.torch.toggle()
        self.assertFalse(self.torch.is_on())

    def test_the_result_arrives_in_the_house_shape(self):
        seen = []
        self.torch.on(on_result=lambda ok, reason: seen.append((ok, reason)))
        self.assertEqual(seen, [(True, codegen.OK)])

    def test_a_callback_that_only_wants_ok_still_works(self):
        seen = []
        self.torch.on(on_result=lambda ok: seen.append(ok))
        self.assertEqual(seen, [True])

    def test_nothing_opens_a_window_just_to_report(self):
        # Reading .root on the lazy proxy BUILDS the Previewer, so a build that
        # merely imports the module would open one. Checked by standing in a
        # proxy that has no window and screams if asked for one, rather than by
        # reading the real one -- whether a window exists by now depends on
        # which other tests ran first.
        from apkpy_lib import ui

        class NoWindow:
            _instance = None

            @property
            def root(self):
                raise AssertionError("the torch built a Previewer window")

        real = ui._app
        ui._app = NoWindow()
        try:
            self.torch.on()
            self.torch.toggle()
            self.torch.off()
        finally:
            ui._app = real


class TheIndicatorSharesTheStripTests(unittest.TestCase):
    """The bolt is borrowed from the icon catalogue, drawn on a bigger grid."""

    def test_it_sits_on_the_same_band_as_the_others(self):
        from apkpy_lib import ui
        points = [point
                  for subpaths, _hollow in ui._status_glyph_layers('torch')
                  for subpath in subpaths
                  for point in subpath]
        ys = [y for _, y in points]
        self.assertAlmostEqual(min(ys), 8.6, places=1)
        self.assertAlmostEqual(max(ys), 18.8, places=1)

    def test_it_keeps_its_proportions(self):
        # Fitting the height and stretching the width would smear the bolt.
        from apkpy_lib import ui
        raw = [p for part in ui._icons.flatten(ui._icons.path_for('bolt'))
               for p in part]
        fitted = [point
                  for subpaths, _hollow in ui._status_glyph_layers('torch')
                  for subpath in subpaths
                  for point in subpath]

        def ratio(points):
            xs = [x for x, _ in points]
            ys = [y for _, y in points]
            return (max(xs) - min(xs)) / (max(ys) - min(ys))

        self.assertAlmostEqual(ratio(raw), ratio(fitted), places=2)

    def test_it_is_centred_where_a_glyph_goes(self):
        from apkpy_lib import ui
        points = [point
                  for subpaths, _hollow in ui._status_glyph_layers('torch')
                  for subpath in subpaths
                  for point in subpath]
        xs = [x for x, _ in points]
        self.assertAlmostEqual((min(xs) + max(xs)) / 2.0, 12.0, places=1)

    def test_it_is_amber_rather_than_the_screens_ink(self):
        # The strip's palette follows the screen. A lit torch that took that
        # ink would disappear on the screen whose ink is already that colour.
        from apkpy_lib import ui
        self.assertTrue(ui._STATUS_TORCH_COLOR.startswith('#'))
        self.assertNotIn('torch', ui.STATUS_GLYPH_ORDER)

    def test_the_strip_only_carries_it_while_the_light_is_on(self):
        from apkpy_lib import ui
        from apkpy_lib.features.flashlight import flashlight
        flashlight.off()
        self.assertFalse(ui._torch_is_lit())
        flashlight.on()
        self.assertTrue(ui._torch_is_lit())
        flashlight.off()


if __name__ == '__main__':
    unittest.main()
