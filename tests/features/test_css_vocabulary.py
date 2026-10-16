# -*- coding: utf-8 -*-
"""A property ApkPy does not read has to say so.

``frobnicate: 3px`` used to transpile clean. So did ``elevation``,
``transform``, ``overflow`` and ``background`` -- four names a person reaches
for out of browser habit, all of them dropped when the layout was written.
That looks like the *value* not working rather than the *name* not existing,
which is why it goes unnoticed: designing is a loop -- try, look, adjust -- and
half the loop returning nothing with no message turns it into guessing.

It is a warning, not a failure. The build carries on, the way an unknown icon
name does.
"""

import contextlib
import io as _io
import unittest

from apkpy_lib.core.style_parser import (
    KNOWN_PROPERTIES, parse_css, unknown_properties,
)
from apkpy_lib.core.compiler import translate_python_to_android


def _found(css):
    styles, keyframes = parse_css(css)
    return dict((prop, selector)
                for prop, selector in unknown_properties(styles, keyframes))


class AnUnknownNameIsFound(unittest.TestCase):

    def test_a_name_nothing_reads_is_reported_with_its_selector(self):
        self.assertEqual(_found('card { frobnicate: 3px; }'),
                         {'frobnicate': 'card'})

    def test_the_vocabulary_itself_is_never_reported(self):
        css = ' '.join('sel%d { %s: 1px; }' % (i, prop)
                       for i, prop in enumerate(sorted(KNOWN_PROPERTIES)))
        self.assertEqual(_found(css), {})

    def test_a_name_inside_keyframes_counts_too(self):
        found = _found('@keyframes slide { from { wobble: 2px; } }')
        self.assertIn('wobble', found)

    def test_each_name_is_reported_once_however_often_it_appears(self):
        found = unknown_properties(
            parse_css('a { nope: 1px; } b { nope: 2px; }')[0])
        self.assertEqual([prop for prop, _ in found], ['nope'])

    def test_a_media_block_is_checked_like_any_other(self):
        css = '@media (min-width: 600px) { card { frobnicate: 1px; } }'
        self.assertIn('frobnicate', _found(css))


class ItIsAWarningAndNotAFailure(unittest.TestCase):

    SOURCE = ('from apkpy_lib import Screen, Theme, container, run\n'
              'home = Screen(id="home")\n'
              'container(id="panel", screen=home)\n'
              'run(start_screen=home, theme=Theme(mode="dark"))\n'
              'style = """\npanel { frobnicate: 3px; }\n"""\n')

    def test_the_project_is_still_generated(self):
        # The report goes to stderr; catching it keeps the suite's own output
        # readable and proves the warning happened at all.
        said = _io.StringIO()
        with contextlib.redirect_stderr(said):
            files = translate_python_to_android(self.SOURCE)
        self.assertNotIn('error.txt', files)
        self.assertIn('res/layout/activity_screen_home.xml', files)
        self.assertIn('U2029', said.getvalue())
        self.assertIn('frobnicate', said.getvalue())


class TheSuggestionHasToBeWorthReading(unittest.TestCase):
    """A near-miss that means something else is worse than no suggestion."""

    def test_a_browser_property_with_no_equivalent_suggests_nothing(self):
        from apkpy_lib.core.style_parser import _PROPERTY_HINTS
        # difflib offers `text-transform` for `transform`, which sets the
        # casing of a label and has nothing to do with moving one.
        self.assertIn('transform', _PROPERTY_HINTS)
        self.assertIsNone(_PROPERTY_HINTS['transform'])

    def test_the_names_people_actually_reach_for_point_somewhere(self):
        from apkpy_lib.core.style_parser import _PROPERTY_HINTS
        self.assertEqual(_PROPERTY_HINTS['elevation'], 'box-shadow')
        self.assertEqual(_PROPERTY_HINTS['background'], 'background-color')

    def test_every_hint_points_at_something_real(self):
        from apkpy_lib.core.style_parser import _PROPERTY_HINTS
        for name, target in _PROPERTY_HINTS.items():
            self.assertNotIn(name, KNOWN_PROPERTIES, name)
            if target is not None:
                self.assertIn(target, KNOWN_PROPERTIES, name)


if __name__ == '__main__':
    unittest.main()
