# -*- coding: utf-8 -*-
"""back(): leave this screen for the one that opened it.

The photo replica's headers (27-09-2026) had an arrow written as
``on_click_navigate(previous)``. On the phone that starts a new copy of the
previous screen on top of this one, so the system's Back then walked through
copies -- settings, profile, settings again. back() is ``finish()``: the
screen closes and the one under it comes back as it was. In the Previewer it
pops the history Alt+Left already used.
"""

import unittest

from test_real_screens import Previewed, _build

TWO = (
    'home = Screen(id="home")\n'
    'detail = Screen(id="detail")\n'
    'button("Open", id="open", screen=home, command=lambda: on_click_navigate(detail))\n'
)


def _detail(files):
    return files['java/Screen_detailActivity.java']


class ThePhone(unittest.TestCase):

    def test_command_back_closes_the_screen(self):
        java = _detail(_build(TWO + 'button("", id="arrow", icon="arrow_back", describe="Back",'
                                    ' screen=detail, command=back)\n'))
        self.assertIn('Screen_detailActivity.this.finish();', java)

    def test_back_in_a_function_and_in_a_lambda(self):
        java = _detail(_build(TWO + 'def done():\n    toast("Saved")\n    back()\n'
                                    'button("Done", id="done", screen=detail, command=done)\n'
                                    'list_row("Close", id="row", screen=detail, command=lambda: back())\n'))
        self.assertGreaterEqual(java.count('Screen_detailActivity.this.finish();'), 2)
        done = java[java.index('void pythonCallback_done()'):]
        self.assertLess(done.index('Toast.makeText'), done.index('finish();'))

    def test_an_apps_own_back_still_wins(self):
        java = _detail(_build(TWO + 'def back():\n    toast("mine")\n'
                                    'button("", id="arrow", icon="arrow_back", describe="Back",'
                                    ' screen=detail, command=back)\n'
                                    'button("x", id="x", screen=detail, command=lambda: back())\n'))
        self.assertNotIn('finish();', java)
        self.assertIn('"mine"', java)

    def test_an_app_that_never_says_back_is_unchanged(self):
        java = _detail(_build(TWO))
        self.assertNotIn('pythonCallback_back', java)
        self.assertNotIn('finish();', java)

    def test_a_background_job_refuses_it(self):
        from apkpy_lib import job_rules
        self.assertEqual(job_rules._COMMANDS['navigate_back'][0], 'navigation')


class ThePreviewer(unittest.TestCase):

    def test_it_returns_to_the_screen_that_opened_this_one(self):
        with Previewed(TWO, '') as p:
            p.ns['on_click_navigate'](p.ns['detail'])
            p.settle(0.2)
            self.assertIs(p.app._active_screen, p.ns['detail'])
            p.ns['back']()
            p.settle(0.2)
            self.assertIs(p.app._active_screen, p.ns['home'])

    def test_on_the_first_screen_it_stays(self):
        with Previewed(TWO, '') as p:
            p.ns['back']()
            p.settle(0.2)
            self.assertIs(p.app._active_screen, p.ns['home'])


if __name__ == '__main__':
    unittest.main()
