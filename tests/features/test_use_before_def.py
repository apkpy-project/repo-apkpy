"""A name used at the top of the file before the line that makes it (E1201).

button(..., command=save) above def save() built, and the phone's app worked,
while the Previewer stopped with NameError: Python runs the file from the top.
The build stops now with the Previewer's own error.
"""

import unittest

from apkpy_lib.core.compiler import translate_python_to_android

HEAD = 'from apkpy_lib import *\nhome = Screen(id="home")\nout = label("", id="out", screen=home)\n'
TAIL = 'run(start_screen=home)\n'


def _error(body):
    files = translate_python_to_android(HEAD + body + TAIL)
    return files.get("error.txt", "")


class Refused(unittest.TestCase):

    def test_a_command_named_before_its_def(self):
        text = _error('button("Save", id="b", command=save, screen=home)\n\n'
                      'def save():\n    out.set_value("saved")\n\n')
        self.assertIn("E1201", text)
        self.assertIn("name 'save' is not defined", text)
        self.assertIn("writehere.py:4", text)
        self.assertIn("command=lambda: save()", text)

    def test_a_value_read_before_it_is_given(self):
        text = _error('out.set_value(TITLE)\nTITLE = "Notes"\n')
        self.assertIn("name 'TITLE' is not defined: line 4 uses it, and line 5 makes it", text)

    def test_a_default_runs_when_the_def_does(self):
        text = _error('def show(text=GREETING):\n    out.set_value(text)\n\nGREETING = "hi"\n')
        self.assertIn("name 'GREETING' is not defined", text)


class Built(unittest.TestCase):

    def assertBuilds(self, body):
        text = _error(body)
        self.assertEqual(text, "", text[:600])

    def test_a_lambda_looks_the_name_up_later(self):
        self.assertBuilds('button("Save", id="b", command=lambda: save(), screen=home)\n\n'
                          'def save():\n    out.set_value("saved")\n\n')

    def test_a_function_body_may_call_one_defined_below(self):
        self.assertBuilds('def first():\n    second()\n\n'
                          'def second():\n    out.set_value("2")\n\n'
                          'button("Go", id="b", command=first, screen=home)\n')

    def test_a_name_the_statement_gives_itself(self):
        self.assertBuilds('for n in range(2):\n    label(str(n), screen=home)\n\n'
                          'def n():\n    pass\n\n')

    def test_a_name_made_before_and_again_after(self):
        self.assertBuilds('TITLE = "a"\nout.set_value(TITLE)\nTITLE = "b"\n')

    def test_a_builtin_shadowed_further_down(self):
        import ast
        from apkpy_lib.core.features import use_before_def
        tree = ast.parse('x = len("abc")\n\ndef len(v):\n    return 0\n')
        self.assertIs(use_before_def.check(tree), tree)

    def test_a_star_import_may_bring_it(self):
        import ast
        from apkpy_lib.core.features import use_before_def
        tree = ast.parse('from apkpy_lib import *\nlabel("a")\n\ndef label(t):\n    pass\n')
        self.assertIs(use_before_def.check(tree), tree)


if __name__ == "__main__":
    unittest.main()
