# -*- coding: utf-8 -*-
"""``flex-grow`` is what pins a composer to the bottom of a screen.

One child takes the space its siblings leave; whatever follows sits under it.
It is the plan of nearly every modern screen -- a chat, a map with a panel, a
feed with an action bar -- and the phone has always honoured it.

The Previewer did not, in one case: writing ``display: flex`` on the screen,
which is the first thing a person reaches for to make a column, *disabled* the
property that fills it. The desktop showed both blocks huddled at the top while
the device pinned them correctly, so the natural next move was to change the
stylesheet to work around a bug that only existed on the desktop.
"""

import unittest

from apkpy_lib.core.compiler import translate_python_to_android


APP = (
    'from apkpy_lib import Screen, Theme, app_bar, container, label, run\n'
    'home = Screen(id="home")\n'
    'app_bar("T", screen=home)\n'
    'hero = container(id="hero", screen=home)\n'
    'label("oi", id="greeting", parent=hero)\n'
    'composer = container(id="composer", screen=home)\n'
    'label("x", id="field", parent=composer)\n'
    'run(start_screen=home, theme=Theme(mode="dark"))\n'
    'style = """\n%s\n"""\n'
)


def _layout(css):
    files = translate_python_to_android(APP % css)
    if not files or 'error.txt' in files:
        raise AssertionError((files or {}).get('error.txt', 'no output')[:400])
    return files['res/layout/activity_screen_home.xml']


class TheDeviceGivesTheLeftoverSpaceAway(unittest.TestCase):

    def test_a_growing_child_gets_a_weight(self):
        xml = _layout('hero { flex-grow: 1; }')
        self.assertIn('android:layout_weight="1"', xml)
        self.assertIn('android:layout_height="0dp"', xml)

    def test_declaring_the_screen_a_flex_column_changes_nothing(self):
        # The trap: this is the declaration a person writes first, and on the
        # desktop it used to switch the growing off.
        plain = _layout('hero { flex-grow: 1; }')
        flex = _layout(
            'body { display: flex; flex-direction: column; }\n'
            'hero { flex-grow: 1; }')
        self.assertEqual(flex.count('android:layout_weight="1"'),
                         plain.count('android:layout_weight="1"'))
        self.assertEqual(flex.count('android:layout_height="0dp"'),
                         plain.count('android:layout_height="0dp"'))

    def test_without_it_nothing_takes_the_leftover(self):
        xml = _layout('hero { background-color: #111111; }')
        self.assertNotIn('android:layout_weight="1"', xml)


class ThePreviewerAgreesWithIt(unittest.TestCase):
    """The rule itself, without opening a window.

    ``_render_container`` decides this from the parent's packing side, so the
    condition can be checked directly -- and it is the condition, not the
    pixels, that diverged.
    """

    def _grows(self, flex_grow, parent_is_flex, pack_side):
        import tkinter as tk

        from apkpy_lib.theme import _number

        parent_is_column = pack_side in (tk.TOP, tk.BOTTOM)
        return (_number(flex_grow) > 0
                and (not parent_is_flex or parent_is_column))

    def test_a_plain_screen_grows_its_child(self):
        import tkinter as tk
        self.assertTrue(self._grows('1', False, tk.TOP))

    def test_a_flex_column_screen_still_grows_its_child(self):
        import tkinter as tk
        self.assertTrue(self._grows('1', True, tk.TOP))

    def test_a_flex_row_screen_does_not(self):
        # Across a row the leftover is width, and the vertical expand would be
        # the wrong axis.
        import tkinter as tk
        self.assertFalse(self._grows('1', True, tk.LEFT))

    def test_no_declaration_no_growing(self):
        import tkinter as tk
        self.assertFalse(self._grows(None, False, tk.TOP))
        self.assertFalse(self._grows('0', True, tk.TOP))


if __name__ == '__main__':
    unittest.main()
