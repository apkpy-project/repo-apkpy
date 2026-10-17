# -*- coding: utf-8 -*-
"""``@native`` functions written in Python.

The body is Java written in Python: the build looks every class, field and
method up in ``android.jar`` and writes the Java somebody would have typed.
Three things are checked here that only a build can check -- that the Java it
writes is Java (``javac`` compiles it against ``android.jar``), that what is
wrong is refused with the line, and that the Previewer and the phone read an
argument by the same rules.
"""

import ast
import io
import os
import subprocess
import tempfile
import unittest

from apkpy_lib import native_rules as rules
from apkpy_lib.core import java_api
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import native_python
from apkpy_lib.diagnostics import ApkpyError
from apkpy_lib.features.native import JavaClass, native as preview_native

from test_data_rules import TOOLING

JAR, LEVELS = java_api.find_android_jar()
needs_sdk = unittest.skipUnless(JAR, "no Android SDK on this machine")

CLASSES = '''
Build = native.use("android.os.Build")
Vibrator = native.use("android.os.Vibrator")
VibrationEffect = native.use("android.os.VibrationEffect")
BatteryManager = native.use("android.os.BatteryManager")
Intent = native.use("android.content.Intent")
Uri = native.use("android.net.Uri")
Context = native.use("android.content.Context")
ClipboardManager = native.use("android.content.ClipboardManager")
ClipData = native.use("android.content.ClipData")
WindowManager = native.use("android.view.WindowManager")
CalendarContract = native.use("android.provider.CalendarContract")
ConnectivityManager = native.use("android.net.ConnectivityManager")
NetworkCapabilities = native.use("android.net.NetworkCapabilities")
SensorManager = native.use("android.hardware.SensorManager")
Sensor = native.use("android.hardware.Sensor")
Toast = native.use("android.widget.Toast")
Settings = native.use("android.provider.Settings")
IOException = native.use("java.io.IOException")
ArrayList = native.use("java.util.ArrayList")
HashMap = native.use("java.util.HashMap")
String = native.use("java.lang.String")
System = native.use("java.lang.System")
'''

# Real things people reach for, each one a function of its own. Every one of
# them has to come out as Java that javac accepts.
CORPUS = '''
@native(preview=lambda ms: "ok")
def buzz(ms: int):
    vibrator = context.getSystemService(Vibrator)
    if not vibrator.hasVibrator():
        return "no vibrator"
    if Build.VERSION.SDK_INT >= 26:
        vibrator.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE))
    else:
        vibrator.vibrate(ms)
    return "ok"


@native(preview=lambda: 87)
def battery() -> int:
    manager = context.getSystemService(BatteryManager)
    return manager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)


@native(preview=lambda url: None)
def open_page(url):
    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))


@native(preview=lambda text: None)
def copy_text(text):
    clipboard = context.getSystemService(ClipboardManager)
    clipboard.setPrimaryClip(ClipData.newPlainText("text", text))


@native(preview=lambda on: None)
def keep_awake(on: bool):
    window = activity.getWindow()
    if on:
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    else:
        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)


@native(preview=lambda title, start: None)
def add_event(title, start: "long"):
    intent = Intent(Intent.ACTION_INSERT)
    intent.setData(CalendarContract.Events.CONTENT_URI)
    intent.putExtra(CalendarContract.Events.TITLE, title)
    intent.putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, start)
    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP)
    context.startActivity(intent)


@native(preview=lambda: "Pixel 9")
def phone_name():
    return Build.MANUFACTURER + " " + Build.MODEL


@native(preview=lambda: True)
def online() -> bool:
    manager = context.getSystemService(ConnectivityManager)
    network = manager.getActiveNetwork()
    if network is None:
        return False
    capabilities = manager.getNetworkCapabilities(network)
    return capabilities is not None and capabilities.hasCapability(
        NetworkCapabilities.NET_CAPABILITY_INTERNET)


@native(preview=lambda: None)
def pattern():
    vibrator = context.getSystemService(Vibrator)
    vibrator.vibrate([0, 200, 100, 200], -1)


@native(preview=lambda name, text: "saved")
def save(name, text):
    out = context.openFileOutput(name, Context.MODE_PRIVATE)
    try:
        out.write(text.getBytes())
    except IOException as error:
        return "failed: " + str(error.getMessage())
    finally:
        out.close()
    return "saved"


@native(preview=lambda: "2 sensors")
def sensors():
    manager = context.getSystemService(SensorManager)
    names = ""
    count = 0
    for sensor in manager.getSensorList(Sensor.TYPE_ALL):
        count += 1
        if count <= 3:
            names = names + sensor.getName() + ", "
    return f"{count} sensors: {names}"


@native(preview=lambda text, long_one: None)
def native_toast(text, long_one: bool):
    Toast.makeText(context, text, Toast.LENGTH_LONG if long_one else Toast.LENGTH_SHORT).show()


@native(preview=lambda: 0.5)
def brightness() -> float:
    level = Settings.System.getInt(context.getContentResolver(), Settings.System.SCREEN_BRIGHTNESS, 128)
    return level / 255


@native(preview=lambda level: None)
def set_window_brightness(level: float):
    window = activity.getWindow()
    params = window.getAttributes()
    params.screenBrightness = level
    window.setAttributes(params)


@native(preview=lambda n: 0)
def sum_to(n: int) -> int:
    total = 0
    for i in range(1, n + 1):
        if i % 2 == 0:
            continue
        total += i
    while total > 1000:
        total = total // 2
    return total


@native(preview=lambda words: "a")
def longest(words):
    found = ArrayList()
    for word in words.split(","):
        found.add(word.trim())
    best = ""
    index = 0
    while True:
        if index >= found.size():
            break
        candidate = native.cast(String, found.get(index))
        if len(candidate) > len(best):
            best = candidate
        index += 1
    return best


@native(preview=lambda key: "none")
def lookup(key):
    table = HashMap()
    table.put("a", "first")
    table.put("b", "second")
    if key in table:
        answer = str(table.get(key))
    elif key == "":
        answer = "empty"
    else:
        answer = "none"
    return answer


@native(preview=lambda: 0)
def seconds() -> "long":
    now = System.currentTimeMillis()
    return now // 1000


@native(preview=lambda a, b: "x")
def compare(a: float, b: float):
    if a < b <= 10:
        return "small"
    bigger = a if a > b else b
    if isinstance(context, Context) and not bigger == 0:
        return "big " + str(round(bigger)) + " " + str(abs(a - b)) + " " + str(max(a, b) ** 2)
    raise ValueError("neither")


@native(preview=lambda text: "x")
def odds_and_ends(text):
    parts = text.split(",")
    total = 0.0
    for part in parts:
        if not bool(part):
            continue
        total += float(part)
    first = parts[0] if len(parts) > 0 else ""
    flags = (1 << 3) | ~4 & 255
    smallest = min(int(total), flags >> 1)
    print("total", total, first)
    return f"{first}:{smallest}:{str(total)}:{int('7') + len(first)}"
'''


def _module(body, classes=CLASSES):
    return "from apkpy_lib import native\n" + classes + body


def _blocks(source):
    """``{name: (java arguments, java code)}`` for every @native function."""
    tree = native_python.rewrite(ast.parse(source), "writehere.py")
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) \
                and getattr(node.value.func, "attr", "") == "java":
            keywords = {item.arg: item.value for item in node.value.keywords}
            out[node.value.args[0].value] = (
                [element.value for element in keywords["args"].elts],
                keywords["code"].value)
    return out


def _code(body, name="f", classes=CLASSES):
    return _blocks(_module(body, classes))[name][1]


def _refused(body, classes=CLASSES):
    with_error = None
    try:
        _blocks(_module(body, classes))
    except ApkpyError as error:
        with_error = error
    if with_error is None:
        raise AssertionError("it was translated")
    return with_error


def _said(error):
    return " ".join([str(error), error.cause or ""] + list(error.suggestions or []))


def _harness(blocks):
    """The functions as methods of an Activity, as the generator writes them."""
    lines = ["package probe;", "",
             "public class Probe extends android.app.Activity {",
             "    private String _apkpyFloat(double value) { return String.valueOf(value); }"]
    lines.extend(native_python.helpers_java())
    for name, (arguments, code) in blocks.items():
        lines.append("    private String _apkpyNative_%s(%s) {" % (
            name, ", ".join("String " + argument for argument in arguments)))
        lines.append("        final android.content.Context context = this;")
        lines.extend("        " + line for line in code.split("\n"))
        lines.append("    }")
    lines.append("}")
    return "\n".join(lines)


def _javac(java, class_name="Probe", package="probe"):
    javac, _java_bin, _jar = TOOLING
    work = tempfile.mkdtemp(prefix="apkpy-native-python-")
    folder = os.path.join(work, package) if package else work
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, class_name + ".java")
    with io.open(path, "w", encoding="utf-8") as handle:
        handle.write(java)
    done = subprocess.run(
        [javac, "-encoding", "UTF-8", "-source", "8", "-target", "8",
         "-Xlint:-options", "-cp", JAR, "-d", os.path.join(work, "out"), path],
        capture_output=True, text=True)
    return done, work


@needs_sdk
class ReadingTheClassesTests(unittest.TestCase):
    """android.jar is read, never run: what a class has and what it answers."""

    @classmethod
    def setUpClass(cls):
        cls.library = java_api.Library([JAR])

    @classmethod
    def tearDownClass(cls):
        cls.library.close()

    def test_a_class_has_its_methods_with_their_arguments(self):
        vibrator = self.library.find("android.os.Vibrator")
        shown = [method.shown() for method in vibrator.methods["vibrate"]]
        self.assertIn("vibrate(long)", shown)
        self.assertIn("vibrate(long[], int)", shown)
        self.assertTrue(vibrator.is_abstract)

    def test_a_class_inside_a_class_is_found_as_people_write_it(self):
        self.assertEqual(self.library.resolve("android.os.Build.VERSION").name,
                         "android.os.Build$VERSION")
        self.assertEqual(self.library.resolve("android.view.WindowManager.LayoutParams").name,
                         "android.view.WindowManager$LayoutParams")
        self.assertIsNone(self.library.resolve("android.os.Vibrater"))

    def test_a_constant_has_its_value_and_a_field_is_found_up_the_family(self):
        field, kind = self.library.field(java_api.Cls("android.os.Build$VERSION_CODES"), "O")
        self.assertEqual((field.constant, kind), (26, java_api.Prim("int")))
        field, kind = self.library.field(java_api.Cls("android.app.Activity"), "VIBRATOR_SERVICE")
        self.assertEqual((field.owner, field.constant), ("android.content.Context", "vibrator"))

    def test_what_a_generic_method_answers_follows_its_class(self):
        strings = java_api.Cls("java.util.ArrayList", (java_api.STRING,))
        (method, bindings), = self.library.methods(strings, "get")
        self.assertEqual(java_api.substitute(method.ret, bindings), java_api.STRING)
        typed = [method for method, _b in self.library.methods(
            java_api.Cls("android.content.Context"), "getSystemService") if method.type_params]
        self.assertEqual(typed[0].ret, java_api.TVar("T"))

    def test_what_a_method_can_throw_is_known(self):
        write = self.library.find("java.io.OutputStream").methods["write"][0]
        self.assertEqual(write.throws, ["java.io.IOException"])

    def test_a_misspelt_class_has_a_near_one(self):
        self.assertEqual(self.library.close_to("Vibrater")[0], "android.os.Vibrator")
        self.assertEqual(self.library.packages_with("Toast"), ["android.widget.Toast"])

    @unittest.skipUnless(LEVELS, "this SDK has no api-versions.xml")
    def test_the_android_a_member_arrived_in(self):
        levels = java_api.ApiLevels(LEVELS)
        self.assertEqual(levels.of_class("android.os.VibrationEffect"), 26)
        self.assertEqual(levels.of_method("android.os.Vibrator", "vibrate", "(J)V"), 1)
        self.assertEqual(levels.of_method(
            "android.os.Vibrator", "vibrate", "(Landroid/os/VibrationEffect;)V"), 26)
        self.assertEqual(java_api.android_version(26), "Android 8.0 (API 26)")


@needs_sdk
class TheGeneratedJavaTests(unittest.TestCase):
    """Each line is given its Java type, and written as somebody would."""

    def test_a_service_asked_for_by_class_comes_typed(self):
        code = _code('''
@native(preview=lambda: None)
def f():
    vibrator = context.getSystemService(Vibrator)
    vibrator.vibrate(200)
''')
        self.assertIn("android.os.Vibrator vibrator = "
                      "context.getSystemService(android.os.Vibrator.class);", code)
        self.assertIn("vibrator.vibrate(200);", code)
        self.assertTrue(code.endswith('return "";'))

    def test_arguments_cross_as_text_and_are_read_as_what_they_were_declared(self):
        arguments, code = _blocks(_module('''
@native(preview=lambda a, b, c, d, e: None)
def f(a, b: int, c: float, d: bool, e: "long"):
    return a
'''))["f"]
        self.assertEqual(arguments, ["a", "apkpyArg_b", "apkpyArg_c", "apkpyArg_d", "apkpyArg_e"])
        self.assertIn('int b = _apkpyNativeInt(apkpyArg_b, "b");', code)
        self.assertIn('double c = _apkpyNativeDouble(apkpyArg_c, "c");', code)
        self.assertIn("boolean d = _apkpyNativeBool(apkpyArg_d);", code)
        self.assertIn('long e = _apkpyNativeLong(apkpyArg_e, "e");', code)

    def test_every_answer_leaves_as_text(self):
        code = _code('''
@native(preview=lambda n: 0)
def f(n: int):
    if n == 1:
        return n + 1
    if n == 2:
        return n / 2
    if n == 3:
        return n > 2
    if n == 4:
        return None
    return "text"
''')
        self.assertIn("return String.valueOf(n + 1);", code)
        # A decimal is written the way Python writes it, not the way Java does.
        self.assertIn("return _apkpyFloat((double) n / 2);", code)
        self.assertIn("return String.valueOf(n > 2);", code)
        self.assertIn('return "";', code)
        self.assertIn('return "text";', code)

    def test_a_class_is_made_with_new_and_a_constant_keeps_its_class(self):
        code = _code('''
@native(preview=lambda url: None)
def f(url):
    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
''')
        self.assertIn("context.startActivity(new android.content.Intent("
                      "android.content.Intent.ACTION_VIEW, android.net.Uri.parse(url)));", code)

    def test_a_name_first_met_inside_an_if_is_still_there_after_it(self):
        code = _code('''
@native(preview=lambda n: "")
def f(n: int):
    if n > 0:
        word = "some"
    else:
        word = "none"
    return word
''')
        lines = code.split("\n")
        self.assertLess(lines.index("String word = null;"), lines.index("if (n > 0) {"))
        self.assertIn('    word = "some";', lines)

    def test_a_list_goes_where_an_array_is_expected(self):
        code = _code('''
@native(preview=lambda: None)
def f():
    context.getSystemService(Vibrator).vibrate([0, 200, 100], -1)
''')
        self.assertIn("vibrate(new long[]{0, 200, 100}, -1);", code)

    def test_a_float_is_narrowed_where_only_a_float_is_taken(self):
        code = _code('''
@native(preview=lambda level: None)
def f(level: float):
    params = activity.getWindow().getAttributes()
    params.screenBrightness = level
    params.alpha = 0.5
''')
        self.assertIn("final android.app.Activity activity = this;", code)
        self.assertIn("params.screenBrightness = (float) level;", code)
        self.assertIn("params.alpha = 0.5f;", code)

    def test_python_division_and_remainder_keep_their_meaning(self):
        code = _code('''
@native(preview=lambda a, b: 0)
def f(a: int, b: int):
    return str(a / b) + str(a // b) + str(a % b)
''')
        self.assertIn("_apkpyFloat((double) a / b)", code)
        self.assertIn("Math.floorDiv(a, b)", code)
        self.assertIn("Math.floorMod(a, b)", code)

    def test_text_is_compared_by_what_it_says(self):
        code = _code('''
@native(preview=lambda a, b: "")
def f(a, b):
    if a == b or a is None or not a:
        return "same"
    return "other"
''')
        self.assertIn("java.util.Objects.equals(a, b)", code)
        self.assertIn("a == null", code)
        self.assertIn("|| android.text.TextUtils.isEmpty(a)) {", code)

    def test_a_checked_exception_nobody_catches_leaves_as_python_would_let_it(self):
        code = _code('''
@native(preview=lambda name: None)
def f(name):
    out = context.openFileOutput(name, Context.MODE_PRIVATE)
    out.close()
''')
        self.assertTrue(code.startswith("try {"))
        self.assertIn("} catch (Exception apkpyChecked) {", code)
        self.assertIn("throw new RuntimeException(apkpyChecked);", code)

    def test_one_that_is_caught_needs_no_wrapping(self):
        code = _code('''
@native(preview=lambda name: "")
def f(name):
    try:
        out = context.openFileOutput(name, Context.MODE_PRIVATE)
        out.close()
    except IOException as error:
        return str(error.getMessage())
    return "ok"
''')
        self.assertNotIn("apkpyChecked", code)
        self.assertIn("} catch (java.io.IOException error) {", code)

    def test_lines_after_a_return_are_left_out(self):
        code = _code('''
@native(preview=lambda: "")
def f():
    return "a"
    return "b"
''')
        self.assertEqual(code, 'return "a";')

    def test_brackets_only_where_java_needs_them(self):
        code = _code('''
@native(preview=lambda a, b, c: 0)
def f(a: int, b: int, c: int):
    return (a + b) * c - a * (b - c) + (a | b)
''')
        self.assertIn("return String.valueOf((a + b) * c - a * (b - c) + (a | b));", code)

    def test_an_app_without_native_python_is_not_touched(self):
        tree = ast.parse('from apkpy_lib import *\nhome = Screen(id="home")\n')
        before = ast.dump(tree)
        self.assertIs(native_python.rewrite(tree), tree)
        self.assertEqual(ast.dump(tree), before)
        self.assertEqual(native_python.helpers_java(), [])


@needs_sdk
@unittest.skipUnless(TOOLING, "no JDK on this machine")
class JavacAgreesTests(unittest.TestCase):
    """The claim that matters: what is written is Java, checked by javac
    against the same android.jar, the way Gradle will."""

    def test_the_whole_corpus_compiles(self):
        blocks = _blocks(_module(CORPUS))
        self.assertEqual(len(blocks), 20)
        done, _work = _javac(_harness(blocks))
        self.assertEqual(0, done.returncode, (done.stdout + done.stderr)[-3000:])

    def test_an_app_builds_the_block_into_every_screen_that_calls_it(self):
        files = translate_python_to_android(
            'from apkpy_lib import *\n'
            'home = Screen(id="home")\n'
            'BatteryManager = native.use("android.os.BatteryManager")\n'
            'out = label("", id="out", screen=home)\n'
            '@native(preview=lambda: 87)\n'
            'def battery() -> int:\n'
            '    manager = context.getSystemService(BatteryManager)\n'
            '    return manager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)\n'
            'def show():\n'
            '    out.set_value("Battery: " + battery() + "%")\n'
            'button("Read", id="go", command=show, screen=home)\n'
            'run(start_screen=home)\n')
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:600])
        java = files["java/Screen_homeActivity.java"]
        self.assertIn("/** @native def battery -- writehere.py:6 */", java)
        self.assertIn("private String _apkpyNative_battery() {", java)
        self.assertIn('"Battery: " + _apkpyNativeText(_apkpyNative_battery()) + "%"', java)
        self.assertIn("private static int _apkpyNativeInt(String text, String name) {", java)

    def test_the_two_languages_read_an_argument_alike(self):
        texts = ["12", " 12 ", "+12", "-7", "12.0", "12.5", "1e3", "1e400", "",
                 "abc", "1_000", "0x10", "12f", "NaN", "Infinity", ".5", "5.",
                 "2147483647", "2147483648", "-2147483648", "-2147483649",
                 "9223372036854775807", "9223372036854775808", "1.0E2",
                 "١٢", "true", "TRUE", " true ", "false", "yes", "1"]
        calls = []
        for index, text in enumerate(texts):
            literal = native_python._java_string(text)
            for kind, call in (("int", "_apkpyNativeInt(%s, \"n\")"),
                               ("long", "_apkpyNativeLong(%s, \"n\")"),
                               ("double", "_apkpyNativeDouble(%s, \"n\")")):
                calls.append(
                    'try { System.out.println("%s|%d|ok|" + %s); } '
                    'catch (IllegalArgumentException e) { System.out.println("%s|%d|no|"); }'
                    % (kind, index, call % literal, kind, index))
            calls.append('System.out.println("boolean|%d|ok|" + _apkpyNativeBool(%s));'
                         % (index, literal))
        helpers = "\n".join(native_python_helpers())
        java = ("public class NativeRulesHarness {\n" + helpers +
                "\n    public static void main(String[] args) {\n        "
                + "\n        ".join(calls) + "\n    }\n}\n")
        if not TOOLING:
            self.skipTest("no JDK on this machine")
        javac, java_bin, _jar = TOOLING
        work = tempfile.mkdtemp(prefix="apkpy-native-rules-")
        path = os.path.join(work, "NativeRulesHarness.java")
        with io.open(path, "w", encoding="utf-8") as handle:
            handle.write(java)
        built = subprocess.run([javac, "-encoding", "UTF-8", "-d", work, path],
                               capture_output=True, text=True)
        self.assertEqual(0, built.returncode, built.stdout + built.stderr)
        ran = subprocess.run([java_bin, "-cp", work, "NativeRulesHarness"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, ran.returncode, ran.stdout + ran.stderr)
        seen = 0
        for line in ran.stdout.splitlines():
            kind, index, ok, answer = line.split("|", 3)
            text = texts[int(index)]
            try:
                wanted = rules.read(kind, text, "n")
            except ValueError:
                self.assertEqual(ok, "no", (kind, text, answer))
                continue
            seen += 1
            self.assertEqual(ok, "ok", (kind, text))
            if kind == "double":
                self.assertEqual(float(answer), wanted, (kind, text))
            elif kind == "boolean":
                self.assertEqual(answer == "true", wanted, (kind, text))
            else:
                self.assertEqual(int(answer), wanted, (kind, text))
        self.assertGreater(seen, 40)


def native_python_helpers():
    """The Activity's helpers, with a block declared so they are written."""
    _blocks(_module('''
@native(preview=lambda: None)
def f():
    pass
'''))
    return native_python.helpers_java()


@needs_sdk
class WhatStopsTheBuildTests(unittest.TestCase):
    """A mistake is found while the app is built, with the line -- not on a phone."""

    def _stops(self, body, *words, classes=CLASSES):
        error = _refused(body, classes)
        self.assertEqual(error.code, "U2047")
        text = _said(error)
        for word in words:
            self.assertIn(word, text)
        return error

    def test_a_method_that_is_not_there(self):
        error = self._stops('''
@native(preview=lambda: None)
def f():
    vibrator = context.getSystemService(Vibrator)
    vibrator.vibrat(200)
''', "Vibrator has no method vibrat()", "Did you mean vibrate()?")
        self.assertEqual(error.line, CLASSES.count("\n") + 6)

    def test_an_argument_of_the_wrong_kind_lists_what_is_taken(self):
        self._stops('''
@native(preview=lambda: None)
def f():
    context.getSystemService(Vibrator).vibrate("long")
''', 'vibrate() does not take (the text "long")', "It takes: vibrate(long)",
                    "vibrate(VibrationEffect)")

    def test_a_class_that_is_not_in_android(self):
        self._stops('''
@native(preview=lambda: None)
def f():
    pass
''', "there is no class android.os.Vibrater", 'native.use("android.os.Vibrator")',
                    classes='Vib = native.use("android.os.Vibrater")\n')
        self._stops('''
@native(preview=lambda: None)
def f():
    pass
''', 'native.use("android.widget.Toast")', classes='Toast = native.use("Toast")\n')

    def test_a_field_that_is_not_there(self):
        self._stops('''
@native(preview=lambda: "")
def f():
    return Build.MODL
''', "Build has no MODL", "Did you mean Build.MODEL?")

    def test_a_service_asked_for_by_name_is_only_an_object(self):
        self._stops('''
@native(preview=lambda: None)
def f():
    vibrator = context.getSystemService(Context.VIBRATOR_SERVICE)
    vibrator.vibrate(200)
''', "Object has no method vibrate()", "context.getSystemService(Vibrator)",
                    "native.cast(")

    def test_the_app_is_not_reachable_from_inside(self):
        self._stops('''
@native(preview=lambda: None)
def f():
    toast("hi")
''', "toast() is not known inside this block", "outside the block")
        self._stops('''
@native(preview=lambda: None)
def f():
    return status
''', "'status' is not known inside this block", "pass it as an argument")

    def test_a_java_class_is_not_reachable_from_the_app(self):
        self._stops('''
@native(preview=lambda: None)
def f():
    pass
def go():
    held = Vibrator
''', "Vibrator is a Java class: it only exists inside a @native function")

    def test_a_variable_keeps_its_kind(self):
        self._stops('''
@native(preview=lambda: None)
def f():
    x = 5
    x = "five"
''', 'the text "five" cannot be kept in x', "an int")

    def test_an_object_cannot_leave_its_block(self):
        self._stops('''
@native(preview=lambda: None)
def f():
    return context.getSystemService(Vibrator)
''', "a block answers text or a number, not a Vibrator")
        self._stops('''
@native(preview=lambda v: None)
def f(v: list):
    pass
''', "v cannot be list", 'str, int, float, bool, "long"')

    def test_preview_is_not_optional(self):
        for decorator in ("@native()", "@native"):
            self._stops('''
%s
def f():
    pass
''' % decorator, "@native needs preview=", "The Previewer cannot run Java")

    def test_an_abstract_class_says_how_to_get_one(self):
        self._stops('''
@native(preview=lambda: None)
def f():
    v = Vibrator()
''', "Vibrator cannot be made with Vibrator()", "context.getSystemService(Vibrator)")

    def test_python_that_has_no_java(self):
        for line, word in (("g = lambda: 1", "a lambda"),
                           ("d = {'a': 1}", "a dict"),
                           ("xs = [x for x in range(3)]", "a comprehension"),
                           ("import os", "import"),
                           ("with open('x') as f: pass", "with")):
            self._stops('''
@native(preview=lambda: None)
def f():
    %s
''' % line, "%s is not available inside a native block" % word, "native.java(...)")

    def test_text_is_joined_to_text(self):
        self._stops('''
@native(preview=lambda: "")
def f():
    return "level " + 5
''', "text can only be joined to text", "str(...)")

    def test_an_except_for_what_cannot_happen(self):
        self._stops('''
@native(preview=lambda: "")
def f():
    try:
        x = 1
    except IOException:
        return "no"
''', "nothing in this try can fail with IOException")

    def test_keyword_arguments_and_defaults(self):
        self._stops('''
@native(preview=lambda: None)
def f():
    context.getSystemService(Vibrator).vibrate(milliseconds=200)
''', "a Java method takes its arguments by position")
        self._stops('''
@native(preview=lambda ms=1: None)
def f(ms: int = 1):
    pass
''', "an argument cannot have a default")

    def test_more_than_one_method_fits(self):
        self._stops('''
@native(preview=lambda: None)
def f():
    Intent(Intent.ACTION_VIEW).putExtra("k", None)
''', "putExtra() could be more than one method", "native.cast(")

    def test_names_that_are_taken(self):
        self._stops('''
@native(preview=lambda: None)
def f():
    context = 1
''', "'context' is taken")
        self._stops('''
@native(preview=lambda: None)
def f():
    final = 1
''', "'final' is a word of the Java language")

    def test_declarations_belong_at_the_top_of_the_file(self):
        self._stops('''
def outer():
    Thing = native.use("android.os.Vibrator")
''', "native.use() names a class at the top of the file")
        self._stops('''
def outer():
    @native(preview=lambda: None)
    def inner():
        pass
''', "@native goes on a function at the top of the file")

    def test_calling_it_with_the_wrong_number_of_values_names_the_def(self):
        files = translate_python_to_android(
            'from apkpy_lib import *\n'
            'home = Screen(id="home")\n'
            '@native(preview=lambda ms: None)\n'
            'def buzz(ms: int):\n'
            '    pass\n'
            'def go():\n'
            '    buzz()\n'
            'button("x", id="b", command=go, screen=home)\n'
            'run(start_screen=home)\n')
        self.assertIn("buzz() takes 1 argument(s), got 0", files["error.txt"])
        self.assertIn("It was written def buzz(ms).", files["error.txt"])
        self.assertNotIn("apkpyArg", files["error.txt"])


@needs_sdk
@unittest.skipUnless(LEVELS, "this SDK has no api-versions.xml")
class OlderPhonesTests(unittest.TestCase):
    """Something newer than the oldest Android the app runs on would crash
    there. The build says so, and a test on SDK_INT is what lets it through."""

    NEW = "vibrator.vibrate(VibrationEffect.createOneShot(200, 255))"

    def _body(self, lines):
        return ('''
@native(preview=lambda: None)
def f():
    vibrator = context.getSystemService(Vibrator)
''' + "".join("    " + line + "\n" for line in lines))

    def test_unguarded_it_stops_the_build(self):
        error = _refused(self._body([self.NEW]))
        self.assertEqual(error.code, "U2047")
        self.assertIn("VibrationEffect.createOneShot() arrived in Android 8.0 (API 26)", str(error))
        self.assertIn("from Android 7.0 (API 24)", error.cause)
        self.assertIn("if Build.VERSION.SDK_INT >= 26:", " ".join(error.suggestions))

    def test_under_a_test_of_the_version_it_passes(self):
        for lines in (
                ["if Build.VERSION.SDK_INT >= 26:", "    " + self.NEW, "else:",
                 "    vibrator.vibrate(200)"],
                ["if Build.VERSION.SDK_INT >= Build.VERSION_CODES.O:", "    " + self.NEW],
                ["if Build.VERSION.SDK_INT > 25:", "    " + self.NEW],
                ["if 26 <= Build.VERSION.SDK_INT:", "    " + self.NEW],
                ["if Build.VERSION.SDK_INT < 26:", "    vibrator.vibrate(200)", "else:",
                 "    " + self.NEW],
                ["if Build.VERSION.SDK_INT < 26:", "    vibrator.vibrate(200)",
                 "    return", self.NEW],
                ["if Build.VERSION.SDK_INT >= 26 and vibrator.hasAmplitudeControl():",
                 "    " + self.NEW],
                ["strong = vibrator.hasAmplitudeControl() "
                 "if Build.VERSION.SDK_INT >= 26 else False"],
        ):
            code = _code(self._body(lines))
            self.assertIn("SDK_INT", code, lines)

    def test_the_wrong_side_of_the_test_does_not_pass(self):
        for lines in (
                ["if Build.VERSION.SDK_INT >= 26:", "    vibrator.vibrate(200)", "else:",
                 "    " + self.NEW],
                ["if Build.VERSION.SDK_INT >= 25:", "    " + self.NEW],
                ["if Build.VERSION.SDK_INT >= 26:", "    vibrator.vibrate(200)", self.NEW],
                ["if Build.VERSION.SDK_INT >= 26 or vibrator.hasAmplitudeControl():",
                 "    pass"],
        ):
            self.assertIn("arrived in Android 8.0", str(_refused(self._body(lines))), lines)

    def test_what_every_supported_android_has_needs_no_test(self):
        self.assertIn("vibrator.vibrate(200);", _code(self._body(["vibrator.vibrate(200)"])))


class ThePreviewerTests(unittest.TestCase):
    """On the desk the body never runs: preview= answers, and the values that
    reach it are read by the rules the phone uses."""

    def test_preview_gets_what_the_function_declared(self):
        seen = []

        @preview_native(preview=lambda name, count, ratio, on, at: seen.append(
            (name, count, ratio, on, at)) or 7)
        def block(name, count: int, ratio: float, on: bool, at: "long"):
            raise AssertionError("the body runs on the phone, never here")

        self.assertEqual(block("Ana", "3", "0.5", "true", 1790000000000), "7")
        self.assertEqual(seen, [("Ana", 3, 0.5, True, 1790000000000)])
        # What a screen hands over is text, and a division leaves a .0.
        self.assertEqual(block(5, 3.0, 2, True, "12"), "7")
        self.assertEqual(seen[-1], ("5", 3, 2.0, True, 12))

    def test_the_answer_is_text_spelt_as_the_phone_spells_it(self):
        for answer, text in ((True, "true"), (False, "false"), (None, ""),
                             (87, "87"), (0.5, "0.5"), ("x", "x")):
            block = preview_native(preview=lambda value=answer: value)(lambda: None)
            self.assertEqual(block(), text)

    def test_a_value_the_phone_would_refuse_is_refused_here(self):
        @preview_native(preview=lambda count: count)
        def block(count: int):
            pass

        for wrong in ("abc", "", "1.5", "3000000000"):
            with self.assertRaises(ApkpyError) as raised:
                block(wrong)
            self.assertIn("count", str(raised.exception))

    def test_the_wrong_number_of_values(self):
        @preview_native(preview=lambda a: a)
        def block(a):
            pass

        with self.assertRaises(ApkpyError) as raised:
            block()
        self.assertIn("takes 1 argument(s), got 0", str(raised.exception))

    def test_preview_is_not_optional_here_either(self):
        with self.assertRaises(ApkpyError) as raised:
            preview_native()
        self.assertIn("@native needs preview=", str(raised.exception))
        with self.assertRaises(ApkpyError):
            preview_native(preview="87")

    def test_a_java_class_is_only_a_name_on_the_desk(self):
        vibrator = preview_native.use("android.os.Vibrator")
        self.assertIsInstance(vibrator, JavaClass)
        self.assertEqual(vibrator.java_name, "android.os.Vibrator")
        for touch in (lambda: vibrator(), lambda: vibrator.EFFECT_CLICK):
            with self.assertRaises(ApkpyError) as raised:
                touch()
            self.assertEqual(raised.exception.code, "U2047")
            self.assertIn("only exists on the phone", str(raised.exception))


class TheRulesTests(unittest.TestCase):

    def test_whole_numbers(self):
        self.assertEqual(rules.whole(" 12 ", "n"), 12)
        self.assertEqual(rules.whole("12.0", "n"), 12)
        self.assertEqual(rules.whole("1e3", "n"), 1000)
        self.assertEqual(rules.whole("9223372036854775807", "n", "long"), 2 ** 63 - 1)
        for wrong in ("", "abc", "12.5", "1_000", "0x10", "1e400", "2147483648"):
            with self.assertRaises(ValueError):
                rules.whole(wrong, "n")

    def test_what_an_annotation_says(self):
        self.assertEqual([rules.kind_of(a) for a in (None, str, int, float, bool, "long", "double")],
                         ["text", "text", "int", "double", "boolean", "long", "double"])
        self.assertIsNone(rules.kind_of(list))
        self.assertIsNone(rules.kind_of("Vibrator"))


if __name__ == "__main__":
    unittest.main()
