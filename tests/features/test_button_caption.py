# -*- coding: utf-8 -*-
"""A button's caption changed while the app runs.

    start.set_value("Pause")        word = start.get_value()

The phone has always done both: a button is a TextView, so the build writes
setText() and getText(). The Previewer drew the caption once and kept it --
"Start" went on saying "Start" with the count running, and get_value()
answered "". These hold the two sides to the same thing.
"""

import unittest

from test_kit import HEAD, TAIL
from test_real_screens import Previewed
from apkpy_lib.core.compiler import translate_python_to_android

APP = ('home = Screen(id="home")\n'
       'row = container(id="row", screen=home)\n'
       'start = button("Start", id="start", parent=row)\n'
       'wide = button("Start", id="wide", screen=home)\n'
       'edit = button("Edit", id="edit", icon="edit", parent=row)\n'
       'other = Screen(id="other")\n'
       'label("Other", id="there", screen=other)\n')
CSS = 'row { display: flex; flex-direction: row; gap: 8px; }'


def _caption(widget):
    return widget.itemcget('label', 'text')


class OnThePhone(unittest.TestCase):

    def test_the_caption_is_set_and_read_as_text(self):
        source = HEAD + ('start = button("Start", id="start", screen=home)\n\n'
                         'def go():\n'
                         '    out.set_value(start.get_value())\n'
                         '    start.set_value("Pause")\n') + TAIL
        files = translate_python_to_android(source)
        self.assertNotIn("error.txt", files)
        java = files["java/Screen_homeActivity.java"]
        self.assertRegex(java, r'findViewById\(R\.id\.btn\d+\)\)\.getText\(\)\.toString\(\)')
        self.assertRegex(java, r'findViewById\(R\.id\.btn\d+\)\)\.setText\(String\.valueOf\("Pause"\)\);')


class InThePreviewer(unittest.TestCase):

    def test_set_value_changes_what_the_button_says(self):
        with Previewed(APP, CSS) as shown:
            start = shown.ns["start"]
            self.assertEqual(start.get_value(), "Start")
            self.assertEqual(_caption(shown.widget("start")).lower(), "start")
            start.set_value("Pause")
            shown.settle(0.2)
            self.assertEqual(start.get_value(), "Pause")
            self.assertEqual(_caption(shown.widget("start")).lower(), "pause")
            # The button beside it was left alone.
            self.assertEqual(shown.ns["edit"].get_value(), "Edit")

    def test_a_button_as_wide_as_its_text_takes_the_new_width(self):
        with Previewed(APP, CSS) as shown:
            before = shown.widget("start").winfo_width()
            beside = shown.widget("edit").winfo_rootx()
            shown.ns["start"].set_value("Start the countdown")
            shown.settle(0.3)
            self.assertGreater(shown.widget("start").winfo_width(), before + 40)
            # What comes after it in the row moved over, as wrap_content does.
            self.assertGreater(shown.widget("edit").winfo_rootx(), beside + 40)
            # One line: the caption was not broken to fit the old width.
            self.assertNotIn("\n", _caption(shown.widget("start")))
            shown.ns["start"].set_value("Go")
            shown.settle(0.3)
            self.assertLess(shown.widget("start").winfo_width(), before + 1)

    def test_a_button_as_wide_as_the_screen_keeps_its_width(self):
        with Previewed(APP, CSS) as shown:
            before = shown.widget("wide").winfo_width()
            shown.ns["wide"].set_value("Pause")
            shown.settle(0.2)
            self.assertEqual(shown.widget("wide").winfo_width(), before)
            self.assertEqual(_caption(shown.widget("wide")).lower(), "pause")

    def test_the_icon_stays_beside_the_new_caption(self):
        with Previewed(APP, CSS) as shown:
            shown.ns["edit"].set_value("Done")
            shown.settle(0.2)
            canvas = shown.widget("edit")
            self.assertEqual(_caption(canvas).lower(), "done")
            self.assertTrue(canvas.find_withtag('icon'))

    def test_the_caption_is_still_there_when_the_screen_comes_back(self):
        with Previewed(APP, CSS) as shown:
            shown.ns["start"].set_value("Pause")
            shown.app.render_screen(shown.ns["other"])
            shown.settle(0.2)
            # Set while its screen is away: nothing to draw on, and no error.
            shown.ns["wide"].set_value("Resume")
            shown.app.go_back()
            shown.settle(0.3)
            self.assertEqual(_caption(shown.widget("start")).lower(), "pause")
            self.assertEqual(_caption(shown.widget("wide")).lower(), "resume")
            self.assertEqual(shown.ns["wide"].get_value(), "Resume")

    def test_a_number_is_shown_as_its_text(self):
        with Previewed(APP, CSS) as shown:
            shown.ns["start"].set_value(3)
            shown.settle(0.2)
            self.assertEqual(shown.ns["start"].get_value(), "3")
            self.assertEqual(_caption(shown.widget("start")), "3")


if __name__ == "__main__":
    unittest.main()
