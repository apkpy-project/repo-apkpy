"""Compiler coverage; the shared corpus also runs against native Android ICU."""
import ast
import re
import unittest

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import regex


def source(body, imports="import re", module=""):
    return '''from apkpy_lib import Screen, inputs, label, button, run
%s
home=Screen(id="home")
field=inputs("Text",screen=home)
out=label("Result",screen=home)
%s
def go():
%s
button("Go",screen=home,command=go)
run(start_screen=home)
''' % (imports, module, "\n".join("    " + line for line in body.splitlines()))


def build(body, **kwargs):
    files = translate_python_to_android(source(body, **kwargs))
    if "error.txt" in files:
        raise AssertionError(files["error.txt"])
    return files


class RegexCompilerTests(unittest.TestCase):
    def test_match_and_named_group_in_a_real_callback(self):
        f = build('m=re.search(r"(?P<id>[0-9]+)", field.get_value())\nif m is not None:\n    out.set_value(m.group("id"))')
        self.assertIn("java/ApkpyRegex.java", f)
        java = f["java/Screen_homeActivity.java"]
        self.assertIn("ApkpyRegex.search(", java)
        self.assertIn("m != null", java)
        self.assertIn('ApkpyRegex.group(m, String.valueOf("n:id"))', java)
        self.assertNotIn("_apkpy_re_", java)

    def test_direct_conditions_and_ternary(self):
        java = build('if re.match(r"a", field.get_value()):\n    out.set_value("yes")\nif not re.search(r"z", field.get_value()):\n    out.set_value("no")\nout.set_value("yes" if re.search("a", "a") else "no")')["java/Screen_homeActivity.java"]
        self.assertIn("!= null", java)
        self.assertIn("Boolean.parseBoolean", java)

    def test_none_group_comparisons(self):
        java = build('m=re.match("(a)?", "")\nif m.group(1) is None:\n    out.set_value("absent")')["java/Screen_homeActivity.java"]
        self.assertIn("== null", java)

    def test_findall_iteration_index_length_and_truthiness(self):
        java = build('items=re.findall(r"[0-9]+", field.get_value())\nif items:\n    out.set_value(items[0])\nfor item in items:\n    out.set_value(item)\nout.set_value(str(len(items)))')["java/Screen_homeActivity.java"]
        self.assertIn("ApkpyRegex.nonempty(items)", java)
        self.assertIn("new org.json.JSONArray", java)
        self.assertIn("_apkpyListGet", java)

    def test_sub_dynamic_replacement_and_count(self):
        java = build('replacement=field.get_value()\nout.set_value(re.sub("[0-9]+", replacement, "a12b34", count=1))')["java/Screen_homeActivity.java"]
        self.assertIn("ApkpyRegex.sub(", java)
        self.assertIn("ApkpyRegex.text(replacement)", java)

    def test_aliases_and_flags(self):
        f = build('m=find("a", "A", flags=rx.I | rx.A)\nif m:\n    out.set_value(m.group())', imports="import re as rx\nfrom re import search as find")
        self.assertIn("ApkpyRegex.search", f["java/Screen_homeActivity.java"])

    def test_constant_pattern_and_optional_groups(self):
        f = build('m=re.match(PATTERN,"a")\nout.set_value(m.groups())', module='PATTERN="(a)(b)?"')
        self.assertIn("ApkpyRegex.groups(m, null)", f["java/Screen_homeActivity.java"])

    def test_pattern_is_deduplicated(self):
        tree, plan = regex.prepare(ast.parse('import re\ndef go():\n x=re.match("a","a")\n y=re.search("a","b")'))
        self.assertEqual(len(plan.patterns), 1)

    def test_plain_projects_do_not_receive_regex_code(self):
        f = build('out.set_value("plain")')
        self.assertNotIn("java/ApkpyRegex.java", f)
        self.assertNotIn("ApkpyRegex", f["java/Screen_homeActivity.java"])

    def test_regex_does_not_leak_across_compilations(self):
        build('out.set_value(re.sub("a","b","a"))')
        self.test_plain_projects_do_not_receive_regex_code()

    def test_unknown_and_dynamic_patterns_fail_with_source_line(self):
        for body in ('out.set_value(re.compile("a"))',
                     'out.set_value(re.search(field.get_value(), "a"))',
                     'out.set_value(re.search(b"a", "a"))',
                     'out.set_value(re.search("(?<=a)b", "ab"))',
                     'out.set_value(re.sub("a", lambda m: "b", "a"))',
                     'out.set_value(re.search("[", "a"))'):
            f = translate_python_to_android(source(body), source_name="regex_example.py")
            self.assertIn("C1701", f.get("error.txt", ""), body)
            self.assertIn("regex_example.py:", f["error.txt"])

    def test_unicode_word_class_is_python_not_java(self):
        spec = regex.compile_pattern(r"\w+")
        self.assertNotIn(r"\p", spec["java"])
        self.assertNotIn(r"\w", spec["java"])

    def test_strict_end_and_dot_are_translated(self):
        self.assertEqual(regex.compile_pattern(r"\Z")["java"], r"\z")
        self.assertEqual(regex.compile_pattern(r".")["java"], r"[^\n]")

    def test_rejected_constructs_are_not_silently_approximated(self):
        for pattern in (r"(a)\1", r"(?>a)", r"a++", r"(?<=a)b", r"(a)?(?(1)b|c)"):
            # Before Python 3.11, re itself cannot read (?>a) and a++ and says
            # so with re.error, which the build reports the same way.
            with self.assertRaises((ValueError, re.error), msg=pattern):
                regex.compile_pattern(pattern)

    def test_match_is_not_a_fullmatch(self):
        template = regex.Path(regex.__file__).with_name("regex_android.java").read_text(encoding="utf-8")
        self.assertIn("m.lookingAt()", template)
        self.assertNotIn("m.matches()", template)

    def test_boolean_assignment_and_nullable_input(self):
        java = build('m=re.match("(a)?", "")\nyes=bool(m)\nif yes:\n    out.set_value("match")\nx=m.group(1)\nout.set_value(re.sub("a","b",x))')["java/Screen_homeActivity.java"]
        self.assertIn("Boolean.parseBoolean(yes)", java)
        self.assertIn("ApkpyRegex.text(x)", java)

    def test_unsupported_calls_fail_before_java(self):
        for body in ('m=re.match("a","a")\nout.set_value(m.groups(123))',
                     'm=re.match("a","a")\nout.set_value(m.group(field.get_value()))',
                     'out.set_value(re.sub("a","b","a",count=1.5))',
                     'PATTERN="a"\nPATTERN=field.get_value()\nout.set_value(re.search(PATTERN,"a"))'):
            self.assertIn("C1701", translate_python_to_android(source(body)).get("error.txt", ""))

    def test_module_call_is_not_silently_dropped(self):
        f = translate_python_to_android(source('out.set_value("ok")', module='m=re.match("a","a")'))
        self.assertIn("inside a callback", f.get("error.txt", ""))

    def test_local_parameter_does_not_use_global_pattern(self):
        f = translate_python_to_android(source('out.set_value("ok")', module='PATTERN="a"\ndef helper(PATTERN):\n    return re.search(PATTERN,"a")'))
        self.assertIn("C1701", f.get("error.txt", ""))

    def test_plain_ast_is_unchanged(self):
        tree = ast.parse('A="abc"\nB=A\ndef f():\n return B')
        before = ast.dump(tree)
        changed, plan = regex.prepare(tree)
        self.assertEqual(before, ast.dump(changed))
        self.assertEqual([], plan.patterns)

    def test_group_name_and_index_are_not_conflated(self):
        java = build('m=re.match("(a)","a")\nout.set_value(m.group(1))\nout.set_value(m.group("1"))')["java/Screen_homeActivity.java"]
        self.assertIn('"i:1"', java)
        self.assertIn('"n:1"', java)

    def test_error_line_survives_a_stylesheet_before_callback(self):
        code = source('out.set_value(re.search("[", "text"))',
                      module='style = """\nbody {\n    background-color: #111111;\n}\n"""')
        expected = next(i for i, line in enumerate(code.splitlines(), 1) if 're.search' in line)
        result = translate_python_to_android(code, source_name="with_style.py")
        self.assertIn("with_style.py:%d" % expected, result.get("error.txt", ""))


if __name__ == "__main__":
    unittest.main()
