# -*- coding: utf-8 -*-
"""``on_change`` on a switch, a checkbox and a slider.

A settings screen for the photo replica (27-09-2026) had a "Private account"
switch with ``on_change=``, and nothing ever called it: the compiler read the
callback for text fields only and wrote no listener for the others, and the
Previewer's switch never called it either. Both sides now call it with what
get_value() gives -- "true"/"false", or the slider's number as text --
whenever the value changes with the screen showing. The value a screen opens
with (a set_value() at module level, a remembered state) is not a change.

On the way: a checkbox's get_value() was the bool True in the Previewer and
the text "true" on the phone, so ``agree.get_value() == "true"`` only worked
on the phone.
"""

import unittest

from test_real_screens import Previewed, _build

BODY = (
    'home = Screen(id="home")\n'
    'seen = []\n'
    'def private(value):\n'
    '    seen.append(value)\n'
    'def volume(value):\n'
    '    seen.append(value)\n'
    'priv = inputs("Private account", type="switch", id="priv", on_change=private, screen=home)\n'
    'agree = inputs("Agree", type="checkbox", id="agree", on_change=private, screen=home)\n'
    'vol = inputs("", type="range", id="vol", on_change=volume, screen=home)\n'
)


def _java(files):
    return ''.join(v for k, v in files.items() if k.endswith('Activity.java'))


class ThePhone(unittest.TestCase):

    def test_a_switch_and_a_checkbox_call_it_with_true_or_false(self):
        java = _java(_build(BODY))
        self.assertEqual(java.count('.setOnCheckedChangeListener('), 2)
        self.assertEqual(
            java.count('if (_b.isShown()) pythonCallback_private(_on ? "true" : "false");'), 2)

    def test_a_slider_calls_it_with_its_number(self):
        java = _java(_build(BODY))
        self.assertIn('.setOnSeekBarChangeListener(', java)
        self.assertIn('if (_s.isShown()) pythonCallback_volume(String.valueOf(_p));', java)

    def test_the_listener_waits_for_the_screen(self):
        # A saved preference put back at module level comes after the
        # listener in onCreate; isShown() keeps it from counting as a change.
        java = _java(_build(BODY + 'priv.set_value(storage.get("private"))\n'))
        listener = java.index('inp1.setOnCheckedChangeListener(')
        restore = java.index('inp1.setChecked(')
        self.assertLess(listener, restore)
        self.assertIn('if (_b.isShown())', java[listener:restore])


class ThePreviewer(unittest.TestCase):

    def test_tapping_the_switch_calls_it(self):
        with Previewed(BODY, '') as p:
            p.widget('priv').event_generate('<Button-1>', x=10, y=10)
            p.settle(0.2)
            self.assertEqual(p.ns['seen'], ['true'])
            p.widget('priv').event_generate('<Button-1>', x=10, y=10)
            p.settle(0.2)
            self.assertEqual(p.ns['seen'], ['true', 'false'])

    def test_the_value_the_screen_opens_with_is_not_a_change(self):
        with Previewed(BODY + 'priv.set_value("true")\nagree.set_value("true")\n', '') as p:
            p.settle(0.3)
            self.assertEqual(p.ns['seen'], [])
            self.assertEqual(p.ns['priv'].get_value(), 'true')

    def test_set_value_from_a_callback_is_a_change(self):
        with Previewed(BODY, '') as p:
            p.ns['agree'].set_value('true')
            p.settle(0.2)
            self.assertEqual(p.ns['seen'], ['true'])

    def test_a_checkbox_answers_true_as_text(self):
        with Previewed(BODY, '') as p:
            self.assertEqual(p.ns['agree'].get_value(), 'false')
            p.ns['agree'].set_value('true')
            self.assertEqual(p.ns['agree'].get_value(), 'true')


if __name__ == '__main__':
    unittest.main()
