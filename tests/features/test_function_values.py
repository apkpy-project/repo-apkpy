# -*- coding: utf-8 -*-
"""Functions as values (features/function_values.py).

f = double, steps = [double, inc], {"add": add}, apply(double, 3) and f(x)
stopped the build. A function handed on as data is its name, and a call of a
value goes through _apkpyCall, a switch over those functions with Python's
TypeError for the wrong number of arguments.
"""

import unittest

from apkpy_lib.core.compiler import translate_python_to_android
from test_classes import HEAD, _cpython, _generated
from test_python_vocabulary import _flat
from test_runtime_arithmetic import HAVE_ANDROID, helpers_compile


APP = HEAD + '''
def double(x):
    return x * 2


def inc(x):
    return x + 1


def add(a, b=10):
    return a + b


def shout(text):
    return text.upper() + "!"


def log(x):
    out.set_value("logged " + str(x))


STEPS = [double, inc, double]


def apply(f, x):
    return f(x)


def pick(name):
    if name == "inc":
        return inc
    return double


def pipeline():
    n = len(field.get_value())
    for f in STEPS:
        n = f(n)
    g = pick("inc")
    out.set_value(str(n) + " " + str(apply(double, 4)) + " " + str(g(n)) + " "
                  + str(pick("x")(1)) + " " + str(STEPS[1] == inc) + " " + str(len(STEPS)))


def table():
    n = len(field.get_value())
    ops = {"add": add, "double": double}
    msg = str(ops["add"](n, 1)) + " " + str(ops["add"](n)) + " " + str(ops["double"](n))
    try:
        ops["double"](1, 2)
    except TypeError as e:
        msg += " | " + str(e)
    try:
        ops["add"]()
    except TypeError as e:
        msg += " | " + str(e)
    out.set_value(msg)


def texts():
    say = shout
    out.set_value(say(field.get_value()) + " " + apply2(shout, "hi"))


def apply2(f, s):
    return f(s)


def statement():
    f = log
    f(len(field.get_value()))


button("1", id="b1", command=pipeline, screen=home)
button("2", id="b2", command=table, screen=home)
button("3", id="b3", command=texts, screen=home)
button("4", id="b4", command=statement, screen=home)
run(start_screen=home)
'''


class TheAnswersTests(unittest.TestCase):
    def test_the_same_answers_as_cpython(self):
        inputs = ["ab", "", "abcde"]
        self.assertEqual(_generated(APP, inputs), _cpython(APP, inputs))


def _refused(body):
    source = HEAD + body + '\nbutton("1", id="b1", command=go, screen=home)\nrun(start_screen=home)\n'
    files = translate_python_to_android(source)
    assert "error.txt" in files, "translated"
    return _flat(files["error.txt"])


class TheRefusalTests(unittest.TestCase):
    def test_a_function_shown(self):
        text = _refused('def double(x):\n    return x * 2\n\n\ndef go():\n    f = double\n'
                        '    out.set_value(str(f))\n')
        self.assertIn('<function double at 0x...>', text)

    def test_a_list_of_functions_shown(self):
        text = _refused('def double(x):\n    return x * 2\n\n\ndef go():\n    fs = [double]\n'
                        '    out.set_value(f"{fs}")\n')
        self.assertIn('changes on every run', text)

    def test_keyword_arguments_to_a_value(self):
        text = _refused('def double(x):\n    return x * 2\n\n\ndef go():\n    f = double\n'
                        '    out.set_value(str(f(x=2)))\n')
        self.assertIn('called with keyword arguments', text)

    def test_a_default_that_is_not_a_constant(self):
        text = _refused('def double(x, k=[]):\n    return x\n\n\ndef go():\n    f = double\n'
                        '    out.set_value(str(f(2)))\n')
        self.assertIn('only a number or text can', text)

    def test_command_keeps_the_function(self):
        source = HEAD + ('def go():\n    out.set_value("x")\n\n\n'
                         'button("1", id="b1", command=go, screen=home)\nrun(start_screen=home)\n')
        java = translate_python_to_android(source)["java/Screen_homeActivity.java"]
        self.assertNotIn("_apkpyCall(", java)


@unittest.skipUnless(HAVE_ANDROID, "no JDK or no Android SDK on this machine")
class TheHelpersCompileAgainstAndroid(unittest.TestCase):
    # _apkpyCall calls the app's own methods, which the JVM test above
    # compiles with the rest of the screen; its helper is compiled here.
    def test_they_compile(self):
        helpers_compile(self, APP, ("_apkpyArity",))


if __name__ == "__main__":
    unittest.main()
