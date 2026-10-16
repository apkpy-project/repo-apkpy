# -*- coding: utf-8 -*-
"""``#name`` is a selector, not a typo.

``.name`` had its dot stripped since the beginning, so a stylesheet written
with class syntax worked. ``#name`` did not: the sigil stayed in the key, the
rule matched no component, and the screen rendered unstyled with no message --
the parse succeeded, so no diagnostic had anything to complain about.

An ApkPy selector names a component id or a component type, and neither sigil
changes which one it is.
"""

import unittest

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.style_parser import parse_css


APP = (
    'from apkpy_lib import Screen, Theme, app_bar, label, run\n'
    'home = Screen(id="home")\n'
    'app_bar("T", screen=home)\n'
    'label("ola", id="kicker", screen=home)\n'
    'run(start_screen=home, theme=Theme(mode="dark"))\n'
    'style = """\n%s\n"""\n'
)


class TheThreeSpellingsAgree(unittest.TestCase):

    def test_the_sigil_is_not_part_of_the_name(self):
        styles, _ = parse_css(
            '#kicker { color: #23D5C3; }\n'
            '.other { color: #FF0000; }\n'
            'plain { color: #00FF00; }\n'
        )
        self.assertEqual(
            sorted(styles), ['kicker', 'other', 'plain'])

    def test_a_hex_colour_in_the_value_is_untouched(self):
        styles, _ = parse_css('#kicker { color: #23D5C3; }')
        self.assertEqual(styles['kicker']['color'], '#23D5C3')

    def test_the_layout_is_the_same_however_it_is_written(self):
        hashed = translate_python_to_android(
            APP % '#kicker { color: #23D5C3; font-size: 19px; }')
        bare = translate_python_to_android(
            APP % 'kicker { color: #23D5C3; font-size: 19px; }')
        dotted = translate_python_to_android(
            APP % '.kicker { color: #23D5C3; font-size: 19px; }')
        self.assertEqual(hashed, bare)
        self.assertEqual(dotted, bare)

    def test_the_declaration_actually_reaches_the_layout(self):
        xml = translate_python_to_android(
            APP % '#kicker { font-size: 19px; }'
        )['res/layout/activity_screen_home.xml']
        self.assertIn('19sp', xml)

    def test_a_media_block_reads_the_sigil_too(self):
        styles, _ = parse_css(
            '@media (max-width: 600px) { #kicker { color: #111111; } }')
        keys = [key for key in styles if key.endswith('|kicker')]
        self.assertEqual(len(keys), 1, sorted(styles))


if __name__ == '__main__':
    unittest.main()
