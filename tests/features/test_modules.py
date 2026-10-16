# -*- coding: utf-8 -*-
"""More than one file, and parameters that stay numbers.

Two changes that only make sense together. Splitting an app across files is
what stops ``writehere.py`` growing without end; a helper whose arithmetic
stops the build is not worth splitting into.

The Previewer half needs no code: ``import helpers`` next to the script is
what Python already does, which is why these tests read the generated Java --
that is the side that had to learn.
"""

import os
import shutil
import tempfile
import unittest

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import modules as modules_feature

APP = (
    'from apkpy_lib import Screen, button, label, run\n'
    'home = Screen(id="home")\n'
    'out = label("", id="out", screen=home)\n'
)
TAIL = (
    'button("Go", id="b", screen=home, command=go)\n'
    'run(start_screen=home)\n'
)


class _OnDisk(unittest.TestCase):
    """Each test gets a folder, because the feature is about files."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="apkpy-modules-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def write(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def files(self, source):
        self.write("writehere.py", source)
        return translate_python_to_android(
            source,
            source_name=os.path.join(self.dir, "writehere.py"),
            project_root=self.dir,
        )

    def java(self, source):
        files = self.files(source)
        if "error.txt" in files:
            raise AssertionError(files["error.txt"][:600])
        return "\n".join(value for name, value in files.items()
                         if name.endswith(".java"))

    def error(self, source):
        """The rendered diagnostic, or None when it compiled."""
        return self.files(source).get("error.txt")


class TheMergeTests(_OnDisk):

    def test_a_function_from_a_helper_becomes_a_method(self):
        self.write("helpers.py", "def shout(text):\n    return text.upper()\n")
        java = self.java("import helpers\n" + APP +
                         "def go():\n    out.set_value(helpers.shout('hi'))\n" + TAIL)
        self.assertIn("private String pythonCallback_shout(String text)", java)
        self.assertIn("pythonCallback_shout(String.valueOf(\"hi\"))", java)

    def test_a_constant_from_a_helper_becomes_a_field(self):
        self.write("helpers.py", 'TITLE = "Total"\n\ndef name():\n    return TITLE\n')
        java = self.java("import helpers\n" + APP +
                         "def go():\n    out.set_value(helpers.name())\n" + TAIL)
        self.assertIn('private static final String TITLE = "Total";', java)

    def test_an_alias_is_followed(self):
        self.write("helpers.py", "def shout(text):\n    return text.upper()\n")
        java = self.java("import helpers as h\n" + APP +
                         "def go():\n    out.set_value(h.shout('hi'))\n" + TAIL)
        self.assertIn("pythonCallback_shout", java)

    def test_the_import_may_sit_below_the_code_that_uses_it(self):
        self.write("helpers.py", "def shout(text):\n    return text.upper()\n")
        java = self.java(APP + "def go():\n    out.set_value(helpers.shout('hi'))\n"
                         + TAIL + "import helpers\n")
        self.assertIn("pythonCallback_shout", java)

    def test_a_helper_may_import_another_helper(self):
        self.write("inner.py", "def base():\n    return 'x'\n")
        self.write("outer.py", "import inner\n\ndef wrap():\n    return inner.base()\n")
        java = self.java("import outer\n" + APP +
                         "def go():\n    out.set_value(outer.wrap())\n" + TAIL)
        self.assertIn("pythonCallback_base", java)
        self.assertIn("pythonCallback_wrap", java)
        self.assertIn("pythonCallback_base()", java)

    def test_the_merged_files_are_reported(self):
        self.write("helpers.py", "def shout(text):\n    return text.upper()\n")
        self.java("import helpers\n" + APP +
                  "def go():\n    out.set_value(helpers.shout('hi'))\n" + TAIL)
        self.assertEqual(modules_feature.merged_files(), ["helpers.py"])

    def test_an_app_without_imports_reports_nothing(self):
        self.java(APP + "def go():\n    out.set_value('hi')\n" + TAIL)
        self.assertEqual(modules_feature.merged_files(), [])

    def test_a_module_the_compiler_knows_is_left_alone(self):
        java = self.java("import math\n" + APP +
                         "def go():\n    out.set_value(str(math.sqrt(16)))\n" + TAIL)
        self.assertIn("Math.sqrt", java)

    def test_an_import_with_no_file_beside_it_is_left_alone(self):
        java = self.java("import json\n" + APP +
                         "def go():\n    out.set_value('hi')\n" + TAIL)
        self.assertIn("pythonCallback_go", java)


class TheRefusalTests(_OnDisk):

    def test_from_import_names_the_supported_form(self):
        self.write("helpers.py", "def shout(text):\n    return text.upper()\n")
        error = self.error("from helpers import shout\n" + APP +
                           "def go():\n    out.set_value(shout('hi'))\n" + TAIL)
        self.assertIn("U2036", error)
        self.assertIn("import helpers", error)

    def test_a_name_the_helper_does_not_have(self):
        self.write("helpers.py", "def shout(text):\n    return text.upper()\n")
        error = self.error("import helpers\n" + APP +
                           "def go():\n    out.set_value(helpers.whisper('hi'))\n" + TAIL)
        self.assertIn("U2036", error)
        self.assertIn("whisper", error)

    def test_a_name_defined_on_both_sides(self):
        self.write("helpers.py", "def go():\n    return 'x'\n")
        error = self.error("import helpers\n" + APP +
                           "def go():\n    out.set_value('hi')\n" + TAIL)
        self.assertIn("U2036", error)
        self.assertIn("defined twice", error)

    def test_two_helpers_that_define_the_same_name(self):
        self.write("one.py", "def shared():\n    return 'a'\n")
        self.write("two.py", "def shared():\n    return 'b'\n")
        error = self.error("import one\nimport two\n" + APP +
                           "def go():\n    out.set_value(one.shared())\n" + TAIL)
        self.assertIn("U2036", error)
        self.assertIn("shared", error)

    def test_the_same_helper_imported_twice(self):
        self.write("helpers.py", "def shout(text):\n    return text.upper()\n")
        error = self.error("import helpers\nimport helpers\n" + APP +
                           "def go():\n    out.set_value(helpers.shout('hi'))\n" + TAIL)
        self.assertIn("U2036", error)
        self.assertIn("twice", error)

    def test_a_screen_declared_in_a_helper(self):
        self.write("helpers.py",
                   "from apkpy_lib import Screen\nextra = Screen(id='extra')\n")
        error = self.error("import helpers\n" + APP +
                           "def go():\n    out.set_value('hi')\n" + TAIL)
        self.assertIn("U2036", error)
        self.assertIn("helpers.py", error)

    def test_a_helper_with_a_syntax_error(self):
        self.write("helpers.py", "def shout(text)\n    return text\n")
        error = self.error("import helpers\n" + APP +
                           "def go():\n    out.set_value('hi')\n" + TAIL)
        self.assertIn("U2036", error)
        self.assertIn("syntax error", error)

    def test_untranslatable_python_names_the_helper_file(self):
        self.write("helpers.py",
                   "def shout(text):\n"
                   "    return [c for c in text if c]\n")
        error = self.error("import helpers\n" + APP +
                           "def go():\n    out.set_value(helpers.shout('hi'))\n" + TAIL)
        self.assertIn("helpers.py", error)


class TheNumbersStayNumbersTests(_OnDisk):

    def java_for(self, helper, call):
        self.write("helpers.py", helper)
        return self.java("import helpers\n" + APP +
                         "def go():\n    out.set_value(%s)\n" % call + TAIL)

    def test_a_parameter_every_call_fills_with_a_number_does_arithmetic(self):
        java = self.java_for(
            "def half(cents):\n    return str(cents / 2)\n",
            "helpers.half(10)")
        self.assertIn("Integer.parseInt(String.valueOf(cents))", java)
        self.assertIn("(double)", java)

    def test_a_parameter_that_is_given_text_stays_text(self):
        java = self.java_for(
            "def shout(text):\n    return text.upper()\n",
            "helpers.shout('hi')")
        self.assertIn("private String pythonCallback_shout(String text)", java)
        self.assertNotIn("Integer.parseInt(String.valueOf(text))", java)

    def test_one_text_call_site_is_enough_to_keep_it_text(self):
        source = ("import helpers\n" + APP +
                  "def go():\n"
                  "    out.set_value(helpers.label_for(2))\n"
                  "    out.set_value(helpers.label_for('x'))\n" + TAIL)
        self.write("helpers.py", "def label_for(value):\n    return str(value)\n")
        files = self.files(source)
        java = "\n".join(v for k, v in files.items() if k.endswith(".java"))
        self.assertNotIn("Integer.parseInt(String.valueOf(value))", java)

    def test_a_float_call_site_makes_it_a_float(self):
        java = self.java_for(
            "def half(amount):\n    return str(amount / 2)\n",
            "helpers.half(10.5)")
        self.assertIn("Double.parseDouble(String.valueOf(amount))", java)

    def test_int_of_something_counts_as_a_number(self):
        java = self.java_for(
            "def half(cents):\n    return str(cents / 2)\n",
            "helpers.half(int('10'))")
        self.assertIn("Integer.parseInt(String.valueOf(cents))", java)

    def test_a_name_the_app_only_ever_assigns_numbers_counts(self):
        self.write("helpers.py", "def half(cents):\n    return str(cents / 2)\n")
        java = self.java("import helpers\n" + APP +
                         "total = 250\n"
                         "def go():\n    out.set_value(helpers.half(total))\n" + TAIL)
        self.assertIn("Integer.parseInt(String.valueOf(cents))", java)

    def test_a_name_that_is_sometimes_text_does_not_count(self):
        self.write("helpers.py", "def half(cents):\n    return str(cents / 2)\n")
        source = ("import helpers\n" + APP +
                  "total = 250\n"
                  "def go():\n"
                  "    total = 'sold out'\n"
                  "    out.set_value(helpers.half(total))\n" + TAIL)
        files = self.files(source)
        java = "\n".join(v for k, v in files.items() if k.endswith(".java"))
        self.assertNotIn("Integer.parseInt(String.valueOf(cents))", java)

    def test_a_function_nobody_calls_keeps_text_parameters(self):
        java = self.java_for(
            "def unused(value):\n    return str(value)\n",
            "'hi'")
        self.assertIn("private String pythonCallback_unused(String value)", java)

    def test_one_helper_feeding_another(self):
        self.write("helpers.py",
                   "def double(cents):\n    return cents * 2\n"
                   "\n\ndef shown(cents):\n    return str(cents / 100)\n")
        java = self.java("import helpers\n" + APP +
                         "def go():\n"
                         "    out.set_value(helpers.shown(helpers.double(250)))\n" + TAIL)
        self.assertIn("Integer.parseInt(String.valueOf(cents))", java)
        self.assertIn("pythonCallback_shown", java)

    def test_a_parameter_passed_straight_through(self):
        self.write("helpers.py",
                   "def half(cents):\n    return str(cents / 2)\n"
                   "\n\ndef row(name, cents):\n    return name + half(cents)\n")
        java = self.java("import helpers\n" + APP +
                         "def go():\n    out.set_value(helpers.row('mug', 250))\n" + TAIL)
        self.assertIn("Integer.parseInt(String.valueOf(cents))", java)

    def test_a_number_written_at_module_level_is_a_field(self):
        self.write("helpers.py",
                   "VAT = 23\n\n\ndef with_vat(cents):\n"
                   "    return str(cents + cents * VAT / 100)\n")
        java = self.java("import helpers\n" + APP +
                         "def go():\n    out.set_value(helpers.with_vat(100))\n" + TAIL)
        self.assertIn('private static final String VAT = "23";', java)
        self.assertIn("Integer.parseInt(String.valueOf(VAT))", java)

    def test_a_boolean_callback_argument_is_still_boolean(self):
        source = (
            'from apkpy_lib import Screen, button, label, permissions, run\n'
            'home = Screen(id="home")\n'
            'out = label("", id="out", screen=home)\n'
            'def got(granted):\n'
            '    out.set_value("ok")\n'
            'def go():\n'
            '    permissions.request("camera", on_result=got)\n'
            'button("Go", id="b", screen=home, command=go)\n'
            'run(start_screen=home)\n')
        files = self.files(source)
        java = "\n".join(v for k, v in files.items() if k.endswith(".java"))
        self.assertIn("boolean granted", java)


class TheBigNumberTests(_OnDisk):
    """Python counts as high as memory allows; Java's int stops at 2^31-1.

    A timestamp in milliseconds written into the source came out as a plain
    Java int, and javac refused the whole build with an error about generated
    code nobody had written by hand.
    """

    def test_a_number_past_the_java_int_gets_the_long_suffix(self):
        java = self.java(APP + "def go():\n"
                         "    out.set_value(str(1790000000000))\n" + TAIL)
        self.assertIn("1790000000000L", java)

    def test_a_number_inside_the_java_int_is_left_alone(self):
        java = self.java(APP + "def go():\n"
                         "    out.set_value(str(2147483647))\n" + TAIL)
        self.assertIn("2147483647", java)
        self.assertNotIn("2147483647L", java)

    def test_arithmetic_on_a_big_number_still_compiles(self):
        java = self.java(APP + "def go():\n"
                         "    out.set_value(str(1790000000000 + 1))\n" + TAIL)
        self.assertIn("1790000000000L", java)

    def test_a_number_past_the_java_long_is_refused_with_a_reason(self):
        error = self.error(APP + "def go():\n"
                           "    out.set_value(str(99999999999999999999999))\n"
                           + TAIL)
        self.assertIsNotNone(error)
        self.assertIn("U2033", error)
        self.assertIn("9223372036854775807", error)

if __name__ == "__main__":
    unittest.main()
