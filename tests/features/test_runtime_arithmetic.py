# -*- coding: utf-8 -*-
"""- * / // % ** and unary - on values the source does not type.

item["price"] * item["qty"] stopped the build: only + was decided when the
app runs (_apkpyAdd, _apkpyAddRaw), and every other operator wanted both
sides proved numbers. The items of a list of dicts, the answer of an API, a
parameter: their type is known only when the app runs, so _apkpyArith works
it out there, with CPython's answers and CPython's TypeError.

On the way: int(sum(prices)) with decimals stopped with ValueError (the sum
was read back as the text "6.75"), and 7.0 % 0 said "float modulo" where
Python says "float modulo by zero".
"""

import io
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from apkpy_lib.core.compiler import translate_python_to_android
from test_classes import HEAD, _cpython, _generated
from test_data_rules import TOOLING
from test_python_vocabulary import _error, _flat, _java


APP = "import json\n" + HEAD + '''
ROWS = [{"name": "tea", "price": 2.5, "qty": 3, "tag": "ab", "on": True},
        {"name": "cake", "price": 4, "qty": 0, "tag": "x", "on": False},
        {"name": "jam", "price": 1.25, "qty": 4, "tag": "j", "on": True}]


def line_total(row):
    return row["price"] * row["qty"]


def with_vat(p):
    return p * 1.23


def total(prices):
    return int(sum(prices))


def safe(kind, a, b):
    try:
        if kind == "div":
            return str(a // b)
        if kind == "mod":
            return str(a % b)
        return str(a - b)
    except ZeroDivisionError as e:
        return "Z:" + str(e)
    except TypeError as e:
        return "T:" + str(e)


def cart():
    n = len(field.get_value())
    t = 0
    for item in ROWS:
        t += item["price"] * item["qty"]
    cost = 0
    for item in ROWS:
        cost = cost + item["price"] * item["qty"] - item["qty"] // 2
    out.set_value(str(t + n) + " " + str(cost) + " " + str(line_total(ROWS[0]))
                  + " " + str(line_total(ROWS[1])))


def operators():
    r = ROWS[0]
    n = len(field.get_value())
    out.set_value(str(r["qty"] - n) + " " + str(r["price"] / r["qty"]) + " " + str(r["qty"] // 2)
                  + " " + str(r["price"] // 2) + " " + str(r["qty"] % 2) + " " + str(r["price"] % 1)
                  + " " + str(r["qty"] ** 2) + " " + str(r["qty"] ** -1) + " " + str(-r["qty"])
                  + " " + str(-r["price"]) + " " + str(r["on"] * 5) + " " + str(r["on"] - ROWS[1]["on"]))


def text_and_errors():
    r0 = ROWS[0]
    r1 = ROWS[1]
    try:
        wrong = r0["tag"] * r0["price"]
    except TypeError as e:
        wrong = "T:" + str(e)
    out.set_value(r0["tag"] * r0["qty"] + "|" + "-" * r0["qty"] + "|" + "ab" * r0["qty"]
                  + "|" + safe("div", r0["qty"], r1["qty"]) + "|" + safe("mod", r0["qty"], r1["qty"])
                  + "|" + safe("div", r0["price"], r1["qty"]) + "|" + safe("mod", r0["price"], r1["qty"])
                  + "|" + safe("sub", r0["tag"], 1) + "|" + safe("sub", r0["name"], r1["name"])
                  + "|" + wrong)


def combined():
    n = len(field.get_value())
    r0 = ROWS[0]
    a = r0["price"] * r0["qty"]
    b = ROWS[2]["price"] * ROWS[2]["qty"]
    both = r0["price"] * r0["qty"] + ROWS[2]["price"] * ROWS[2]["qty"]
    parts = [str(a + b), str(a - b), str(both), f"{a:.2f}", str(round(a, 1)), str(int(a)),
             str(total([2.5, 3.25, n])), str(with_vat(r0["qty"])), str(r0["qty"] * 2),
             str(max(r0["qty"] * 2, ROWS[2]["qty"] * 3))]
    if a - b > 0:
        parts.append("more")
    if r0["price"] * r0["qty"] > 7:
        parts.append("big")
    out.set_value(" ".join(parts))


def data():
    n = len(field.get_value())
    loaded = json.loads('{"items": [{"p": 3, "q": 2}, {"p": 0.5, "q": 3}]}')
    s = 0
    for it in loaded["items"]:
        s = s + it["p"] * it["q"]
    totals = []
    for it in loaded["items"]:
        totals.append(it["p"] * it["q"] + n)
    by_cost = sorted(ROWS, key=lambda r: r["price"] * r["qty"])
    out.set_value(str(s + n) + " " + str(totals) + " " + json.dumps(totals) + " "
                  + ",".join([r["name"] for r in by_cost]))


button("1", id="b1", command=cart, screen=home)
button("2", id="b2", command=operators, screen=home)
button("3", id="b3", command=text_and_errors, screen=home)
button("4", id="b4", command=combined, screen=home)
button("5", id="b5", command=data, screen=home)
run(start_screen=home)
'''


class TheAnswersTests(unittest.TestCase):
    """The generated Java shows what CPython shows, button by button."""

    def test_the_same_answers_as_cpython(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        inputs = ["abc", "", "x"]
        self.assertEqual(_cpython(APP, inputs), _generated(APP, inputs))


class TheJavaTests(unittest.TestCase):

    def test_an_item_times_an_item_is_decided_when_the_app_runs(self):
        java = _java('    out.set_value(str(ROWS[0]["price"] * ROWS[0]["qty"]))',
                     module_lines='ROWS = [{"price": 2.5, "qty": 3}]\n')
        self.assertIn('_apkpyArith("*", _apkpyRawOr(', java)
        self.assertIn('private String _apkpyArith(String op, Object a, int am, Object b, int bm) {', java)

    def test_a_parameter_goes_in_as_text_of_an_unknown_kind(self):
        java = _java('    out.set_value(str(vat(field.get_value())))',
                     module_lines='def vat(p):\n    return p * 1.23\n')
        # Nothing says what p is: its text is read as the number it writes,
        # or as text, when the app runs (mode 0).
        self.assertIn('_apkpyArith("*", String.valueOf(p), 0, String.valueOf(1.23), 0)', java)

    def test_two_names_given_a_product_add_when_the_app_runs(self):
        java = _java('    a = ROWS[0]["p"] * ROWS[0]["q"]\n'
                     '    b = ROWS[1]["p"] * ROWS[1]["q"]\n'
                     '    out.set_value(str(a + b))',
                     module_lines='ROWS = [{"p": 2, "q": 3}, {"p": 4, "q": 5}]\n')
        self.assertIn('_apkpyAddAny(String.valueOf(a), false, String.valueOf(b), false)', java)

    def test_int_of_a_sum_reads_it_as_a_number(self):
        java = _java('    out.set_value(str(total([2.5, len(field.get_value())])))',
                     module_lines='def total(prices):\n    return int(sum(prices))\n')
        self.assertIn('_apkpyIntOfNumber(', java)

    def test_python_says_float_modulo_by_zero(self):
        java = _java('    out.set_value(str(ROWS[0]["p"] % 0.0))',
                     module_lines='ROWS = [{"p": 2.5}]\n')
        self.assertIn('"float modulo by zero"', java)
        self.assertNotIn('"float modulo")', java)


class TheRefusalTests(unittest.TestCase):
    """What the source says is text, a list or a dict still stops the build,
    and so does x * 2 with an x whose kind nobody says."""

    def test_an_unknown_times_an_int_is_not_guessed(self):
        # [x * 2 for x in "a5"] is ['aa', '55'] in Python: the "5" is a str.
        # Read as the number its text writes, it gave 10.
        text = _flat(_error('    t = field.get_value()\n    out.set_value(str([x * 2 for x in t]))'))
        self.assertIn('U2033', text)
        text = _flat(_error('    out.set_value(str(twice(field.get_value())))',
                            module_lines='def twice(s):\n    return s * 2\n'))
        self.assertIn('U2033', text)

    def test_an_unknown_times_a_float_is_a_number(self):
        java = _java('    out.set_value(str(vat(field.get_value())))',
                     module_lines='def vat(p):\n    return p * 1.23\n')
        self.assertIn('_apkpyArith("*"', java)

    def test_text_written_out_minus_a_number(self):
        text = _flat(_error('    out.set_value(str("abc" - len(field.get_value())))'))
        self.assertIn('U2033', text)

    def test_a_dict_times_a_number(self):
        text = _flat(_error('    d = {"a": 1}\n    out.set_value(str(d * len(field.get_value())))'))
        self.assertIn('U2033', text)

    def test_a_list_minus_a_number(self):
        text = _flat(_error('    xs = [1, 2]\n    out.set_value(str(xs - len(field.get_value())))'))
        self.assertIn('U2033', text)


def _android_jar():
    sdk = Path(os.environ.get("ANDROID_HOME")
               or Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk")
    jars = sorted(sdk.glob("platforms/android-*/android.jar"),
                  key=lambda p: int(re.sub(r"\D", "", p.parent.name) or 0))
    return jars[-1] if jars else None


def _javac():
    jbr = Path(r"C:\Program Files\Android\Android Studio\jbr\bin\javac.exe")
    return str(jbr) if jbr.exists() else shutil.which("javac")


def helpers_compile(test, source, roots, screen="home"):
    """Compile the _apkpy* helpers *roots* need, and what they call, against
    android.jar (shared by the other features' tests)."""
    files = translate_python_to_android(source)
    test.assertNotIn("error.txt", files, files.get("error.txt", "")[:600])
    java = files["java/Screen_%sActivity.java" % screen]

    def definition(name):
        m = re.search(r"^    private [\w.<>\[\]]+ %s\(" % re.escape(name), java, re.M)
        return java[m.start():java.index("\n    }\n", m.start()) + 7] if m else None

    done, order, todo = set(), [], list(roots)
    while todo:
        name = todo.pop()
        if name in done:
            continue
        done.add(name)
        found = definition(name)
        if found:
            order.append(found)
            todo.extend(re.findall(r"\b(_apkpy\w+)\(", found))
    missing = [r for r in roots if definition(r) is None]
    test.assertEqual(missing, [], "not in the generated Java")
    with tempfile.TemporaryDirectory() as tmp:
        with io.open(os.path.join(tmp, "H.java"), "w", encoding="utf-8") as f:
            f.write("public class H {\n%s}\n" % "\n".join(order))
        with io.open(os.path.join(tmp, "ApkpyValues.java"), "w", encoding="utf-8") as f:
            f.write(files["java/ApkpyValues.java"].replace("package com.apkpy.app;", ""))
        result = subprocess.run(
            [_javac(), "-encoding", "UTF-8", "-nowarn", "-cp", str(_android_jar()), "-d", tmp,
             os.path.join(tmp, "H.java"), os.path.join(tmp, "ApkpyValues.java")],
            capture_output=True, text=True)
        test.assertEqual(result.returncode, 0, result.stderr[-1500:])


HAVE_ANDROID = bool(_android_jar() and _javac())


@unittest.skipUnless(HAVE_ANDROID, "no JDK or no Android SDK on this machine")
class TheHelpersCompileAgainstAndroid(unittest.TestCase):
    """Android's JSONException is checked and the PC's org.json jar is not:
    `new JSONArray(text)` outside a try passed the JVM test above and stopped
    the Gradle build. The helpers are compiled here against android.jar."""

    def test_they_compile(self):
        helpers_compile(self, APP, ("_apkpyArith", "_apkpyAddAny", "_apkpyArithValue",
                                    "_apkpyIntOfNumber"))


if __name__ == "__main__":
    unittest.main()
