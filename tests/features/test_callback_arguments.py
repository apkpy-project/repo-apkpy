# -*- coding: utf-8 -*-
"""Two ways an argument stopped being itself between the call and the Java.

Both came from the same audit, both were reproduced before being fixed, and
they are opposites: one produced Java that would not compile, which is loud
and annoying; the other produced Java that compiled and answered the wrong
thing, which is the failure this project exists to remove.
"""

import unittest

from apkpy_lib.core.compiler import translate_python_to_android

HEAD = (
    'from apkpy_lib import Screen, button, camera, contacts, label, nfc, run\n'
    'home = Screen(id="home")\n'
    'out = label("", id="out", screen=home)\n'
)
BRANCHING = (
    'def result(ok, value):\n'
    '    if ok:\n'
    '        out.set_value("success")\n'
    '    else:\n'
    '        out.set_value("failure")\n\n'
)
PLAIN = 'def result(ok, value):\n    out.set_value(value)\n\n'
TAIL = (
    'button("Go", id="b", screen=home, command=go)\n'
    'run(start_screen=home)\n'
)


def _files(declaration, body):
    return translate_python_to_android(
        HEAD + declaration + 'def go():\n    ' + body + '\n\n' + TAIL)


def _java(declaration, body):
    files = _files(declaration, body)
    if 'error.txt' in files:
        raise AssertionError(files['error.txt'][:400])
    return '\n'.join(value for name, value in files.items()
                     if name.endswith('.java'))


def _error(declaration, body):
    return _files(declaration, body).get('error.txt')


class ABooleanHandedOnStaysABoolean(unittest.TestCase):
    """`false` used to arrive as the text "false", which is not empty.

    Only the callback named in the API call was marked as taking a boolean
    first. Written through a lambda, the lambda was marked and the function it
    forwarded to was not, so its parameter stayed a String and `if ok:` took
    the success branch on a cancelled camera -- without a word.
    """

    def test_a_lambda_forwarding_to_a_function_marks_that_function(self):
        java = _java(BRANCHING,
                     'nfc.status(on_result=lambda ok, value: result(ok, value))')
        self.assertIn('private void pythonCallback_result(boolean ok, String value)', java)
        self.assertIn('pythonCallback_result((ok), String.valueOf(value))', java)

    def test_the_branch_reads_the_boolean_and_not_the_text(self):
        java = _java(BRANCHING,
                     'nfc.status(on_result=lambda ok, value: result(ok, value))')
        self.assertIn('if (ok) {', java)
        self.assertNotIn('if (ok != null && !ok.isEmpty())', java)

    def test_the_camera_forwards_the_same_way(self):
        java = _java(BRANCHING,
                     'camera.capture(on_result=lambda ok, value: result(ok, value))')
        self.assertIn('private void pythonCallback_result(boolean ok, String value)', java)

    def test_a_named_callback_was_already_right_and_still_is(self):
        java = _java(BRANCHING, 'nfc.status(on_result=result)')
        self.assertIn('boolean ok', java)

    def test_a_second_hop_is_followed_too(self):
        declaration = (
            'def inner(ok, value):\n'
            '    if ok:\n        out.set_value("success")\n'
            '    else:\n        out.set_value("failure")\n\n'
            'def outer(ok, value):\n    inner(ok, value)\n\n')
        java = _java(declaration,
                     'nfc.status(on_result=lambda ok, value: outer(ok, value))')
        self.assertIn('private void pythonCallback_inner(boolean ok, String value)', java)

    def test_a_value_that_is_not_the_boolean_is_left_alone(self):
        declaration = (
            'def shout(text):\n    out.set_value(text)\n\n')
        java = _java(declaration,
                     'nfc.status(on_result=lambda ok, value: shout(value))')
        self.assertIn('private void pythonCallback_shout(String text)', java)


class AKeywordArgumentReachesTheJava(unittest.TestCase):
    """`result(ok=False, value="denied")` declared two and passed none.

    The parser kept `call.args` and dropped `call.keywords`, so the generated
    Java had a call with no arguments against a two-parameter method. There
    was no diagnostic: the build went on and javac failed on code nobody wrote
    by hand.
    """

    # False reaches a parameter that travels as text as Python writes it.
    CALL = 'pythonCallback_result(ApkpyValues.FALSE, String.valueOf("denied"))'

    def test_every_argument_by_name(self):
        self.assertIn(self.CALL, _java(PLAIN, 'result(ok=False, value="denied")'))

    def test_one_by_position_and_one_by_name(self):
        self.assertIn(self.CALL, _java(PLAIN, 'result(False, value="denied")'))

    def test_names_out_of_order_are_put_back_in_order(self):
        self.assertIn(self.CALL, _java(PLAIN, 'result(value="denied", ok=False)'))

    def test_positional_only_is_untouched(self):
        self.assertIn(self.CALL, _java(PLAIN, 'result(False, "denied")'))

    def test_a_missing_parameter_stops_the_build(self):
        error = _error(PLAIN, 'result(ok=False)')
        self.assertIn('U2037', error)
        self.assertIn('value', error)

    def test_the_same_parameter_twice_stops_the_build(self):
        error = _error(PLAIN, 'result(False, ok=True)')
        self.assertIn('U2037', error)
        self.assertIn('twice', error)

    def test_a_name_the_function_does_not_have_stops_the_build(self):
        error = _error(PLAIN, 'result(False, nope="x")')
        self.assertIn('U2037', error)
        self.assertIn('nope', error)

    def test_both_fixes_together_on_the_reported_call(self):
        java = _java(
            BRANCHING,
            'contacts.pick(on_result=lambda ok, value: result(ok=ok, value=value))')
        self.assertIn('private void pythonCallback_result(boolean ok, String value)', java)
        self.assertIn('if (ok) {', java)


if __name__ == '__main__':
    unittest.main()
