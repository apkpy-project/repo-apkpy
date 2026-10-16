# -*- coding: utf-8 -*-
"""``inputs(..., on_change=lambda value: ...)`` on a phone.

Found on 05-10-2026 while writing something else, and it had always been so:
a field whose ``on_change=`` was a named function got its listener, and one
whose ``on_change=`` was a lambda got nothing. The build passed and said
nothing; typing, switching and sliding did nothing on the phone; and the
Previewer, which runs the lambda as Python, did what was written -- so it was
only ever found on a phone. The docstring of ``inputs()`` gives a lambda as
its example.

The one lambda that did work is the list search,
``lambda q: rows.set_items([...])``, which has a listener written for it
specially. Every other lambda is now the body of a function named after the
field, called by the listener a named function gets.
"""

import unittest

from apkpy_lib.core.compiler import translate_python_to_android

from test_real_screens import Previewed, _build

HEAD = (
    'home = Screen(id="home")\n'
    'out = label("", id="out", screen=home)\n'
    'seen = []\n'
    'def typed(value):\n'
    '    seen.append(value)\n'
    '    out.set_value(value)\n'
)


def _java(files):
    return ''.join(v for k, v in files.items() if k.endswith('Activity.java'))


def _error(body):
    files = translate_python_to_android(
        'from apkpy_lib import *\n' + HEAD + body + '\nrun(start_screen=home)\n')
    return ' '.join((files or {}).get('error.txt', '').split())


class ThePhone(unittest.TestCase):

    def test_a_text_field_gets_its_listener(self):
        java = _java(_build(HEAD + 'name = inputs("Name", id="name", screen=home, '
                                   'on_change=lambda value: out.set_value("Hello " + value))\n'))
        self.assertEqual(java.count('.addTextChangedListener('), 1)
        self.assertIn('pythonCallback_name_change(_ed.toString());', java)
        self.assertIn('private void pythonCallback_name_change(String value) {', java)
        self.assertIn('"Hello " + value', java)

    def test_the_lambda_can_call_a_function_of_the_app(self):
        java = _java(_build(HEAD + 'name = inputs("Name", id="name", screen=home, '
                                   'on_change=lambda v: typed(v))\n'))
        method = java[java.index('private void pythonCallback_name_change(String v) {'):]
        self.assertIn('pythonCallback_typed(', method[:300])

    def test_a_switch_a_checkbox_and_a_slider_get_theirs(self):
        java = _java(_build(
            HEAD
            + 'dark = inputs("Dark", type="switch", id="dark", screen=home, on_change=lambda on: typed(on))\n'
            + 'agree = inputs("Agree", type="checkbox", id="agree", screen=home, on_change=lambda on: typed(on))\n'
            + 'vol = inputs("", type="range", id="vol", screen=home, on_change=lambda n: typed(n))\n'))
        self.assertEqual(java.count('.setOnCheckedChangeListener('), 2)
        self.assertIn('if (_b.isShown()) pythonCallback_dark_change(_on ? "true" : "false");', java)
        self.assertIn('if (_b.isShown()) pythonCallback_agree_change(_on ? "true" : "false");', java)
        self.assertIn('if (_s.isShown()) pythonCallback_vol_change(String.valueOf(_p));', java)

    def test_one_thing_or_another_is_an_if(self):
        java = _java(_build(
            HEAD + 'vol = inputs("", type="range", id="vol", screen=home, '
                   'on_change=lambda n: typed("loud") if int(n) > 50 else typed("quiet"))\n'))
        method = java[java.index('private void pythonCallback_vol_change(String n) {'):]
        method = method[:method.index('\n    }\n')]
        self.assertIn('if (', method)
        self.assertIn('} else {', method)
        self.assertEqual(method.count('pythonCallback_typed('), 2)

    def test_one_thing_or_nothing_is_an_if_with_no_else_to_run(self):
        java = _java(_build(
            HEAD + 'name = inputs("Name", id="name", screen=home, '
                   'on_change=lambda v: typed(v) if v != "" else None)\n'))
        method = java[java.index('private void pythonCallback_name_change(String v) {'):]
        method = method[:method.index('\n    }\n')]
        self.assertEqual(method.count('pythonCallback_typed('), 1)

    def test_two_fields_with_no_id_do_not_share_a_function(self):
        java = _java(_build(
            HEAD
            + 'inputs("First", screen=home, on_change=lambda v: typed("first " + v))\n'
            + 'inputs("Last", screen=home, on_change=lambda v: typed("last " + v))\n'))
        self.assertEqual(java.count('.addTextChangedListener('), 2)
        methods = set(part.split('(')[0] for part in java.split('private void pythonCallback_')[1:])
        changes = sorted(name for name in methods if name.endswith('_change') or '_change_' in name)
        self.assertEqual(len(changes), 2, changes)
        self.assertIn('"first " + v', java)
        self.assertIn('"last " + v', java)

    def test_the_list_search_is_still_the_list_search(self):
        java = _java(_build(
            HEAD
            + 'rows = list_view(items=[{"title": "Ana"}, {"title": "Rui"}], id="rows", screen=home)\n'
            + 'find = inputs("Find", id="find", screen=home, on_change=lambda q: rows.set_items('
              '[i for i in [{"title": "Ana"}, {"title": "Rui"}] if q.lower() in i["title"].lower()]))\n'))
        self.assertEqual(java.count('.addTextChangedListener('), 1)
        self.assertNotIn('pythonCallback_find_change', java)

    def test_a_named_function_is_as_it_was(self):
        java = _java(_build(HEAD + 'name = inputs("Name", id="name", screen=home, on_change=typed)\n'))
        self.assertIn('pythonCallback_typed(_ed.toString());', java)
        self.assertNotIn('_change(', java)

    def test_a_field_with_no_on_change_has_no_listener(self):
        java = _java(_build(HEAD + 'name = inputs("Name", id="name", screen=home)\n'))
        self.assertNotIn('.addTextChangedListener(', java)

    def test_a_lambda_that_does_not_take_the_value_stops_the_build(self):
        # At the desk it is called with the value, fails, and the Previewer
        # shows nothing: the build is where it gets said.
        for bad in ('lambda: toast("typing")', 'lambda a, b: typed(a)', 'lambda *all: typed("x")'):
            text = _error('name = inputs("Name", id="name", screen=home, on_change=%s)' % bad)
            self.assertIn('U2033', text, bad)
            self.assertIn('takes one parameter', text, bad)
            self.assertIn('on_change=lambda value: ...', text, bad)
            self.assertIn('writehere.py:8', text, bad)


class ThePreviewer(unittest.TestCase):
    """What the desk always did, pinned so the two stay together."""

    def test_typing_calls_the_lambda_with_the_text(self):
        body = HEAD + 'name = inputs("Name", id="name", screen=home, on_change=lambda v: typed("Hello " + v))\n'
        with Previewed(body, '') as p:
            entry = p.widget('name')
            # A key goes to whoever has the focus; focusing also takes the
            # placeholder out of the field, as a tap does.
            entry.focus_force()
            p.settle(0.1)
            entry.delete(0, 'end')
            entry.insert(0, 'Ana')
            entry.event_generate('<KeyRelease>', keysym='a')
            p.settle(0.2)
            self.assertEqual(p.ns['seen'], ['Hello Ana'])
            self.assertEqual(p.ns['out'].get_value(), 'Hello Ana')

    def test_a_switch_calls_the_lambda_with_true_or_false(self):
        body = HEAD + 'dark = inputs("Dark", type="switch", id="dark", screen=home, on_change=lambda on: typed("dark " + on))\n'
        with Previewed(body, '') as p:
            p.widget('dark').event_generate('<Button-1>', x=10, y=10)
            p.settle(0.2)
            self.assertEqual(p.ns['seen'], ['dark true'])


if __name__ == '__main__':
    unittest.main()
