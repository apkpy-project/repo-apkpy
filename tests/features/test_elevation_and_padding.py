# -*- coding: utf-8 -*-
"""Two things a stylesheet said that only the Previewer heard.

``box-shadow`` drew a shadow on the desktop and nothing on the phone: the
container branch never asked for elevation, and even asking is only half of it,
because a ViewGroup clips its children to its own padding box and cuts the
shadow off exactly where it starts.

``padding`` with three or four values reached the Previewer whole and the
compiler truncated: ``padding: 0 20 24 20`` came out as ``0 20 0 20`` on the
phone, so the bottom disappeared -- on one of the two runtimes only, which is
the worst way for a layout to be wrong.
"""

import unittest

from apkpy_lib.core.compiler import _parse_padding, translate_python_to_android
from apkpy_lib.ui import _parse_margin, _parse_padding_tk


def _layout(css, extra=''):
    source = (
        'from apkpy_lib import Screen, Theme, container, label, run\n'
        'home = Screen(id="home")\n'
        'outer = container(id="outer", screen=home)\n'
        'panel = container(id="panel", parent=outer)\n'
        'label("Hi", id="lab", parent=panel)\n'
        + extra +
        'run(start_screen=home, theme=Theme(mode="dark"))\n'
        'style = """\n' + css + '\n"""\n'
    )
    files = translate_python_to_android(source)
    if 'error.txt' in files:
        raise AssertionError(files['error.txt'][:300])
    return files['res/layout/activity_screen_home.xml']


SHADOWED = 'panel { background-color: #223344; box-shadow: 0 6px 18px #0005; }'


class AShadowReachesThePhone(unittest.TestCase):

    def test_a_shadowed_container_asks_for_elevation(self):
        self.assertIn('android:elevation="6dp"', _layout(SHADOWED))

    def test_the_parent_stops_clipping_its_shadowed_child(self):
        # The shadow is drawn outside the child's own box. Without this the
        # elevation is real and invisible, which is the same bug wearing a
        # different hat.
        xml = _layout(SHADOWED)
        self.assertEqual(xml.count('android:clipChildren="false"'), 2)
        self.assertEqual(xml.count('android:clipToPadding="false"'), 2)

    def test_an_app_with_no_shadow_is_untouched(self):
        xml = _layout('panel { background-color: #223344; }')
        self.assertNotIn('android:elevation', xml)
        self.assertNotIn('clipChildren', xml)
        self.assertNotIn('clipToPadding', xml)

    def test_a_card_finally_shows_the_shadow_the_theme_gave_it(self):
        # Theme() has always written box-shadow into the card defaults, so
        # every card asked for elevation and every root clipped it away.
        source = (
            'from apkpy_lib import Screen, Theme, card, label, run\n'
            'home = Screen(id="home")\n'
            'c = card(id="c", screen=home)\n'
            'label("Hi", id="lab", parent=c)\n'
            'run(start_screen=home, theme=Theme(mode="dark"))\n'
            'style = """\n\n"""\n'
        )
        xml = translate_python_to_android(source)[
            'res/layout/activity_screen_home.xml']
        self.assertIn('app:cardElevation="3dp"', xml)
        self.assertIn('android:clipToPadding="false"', xml)


class ThePaddingIsTheSameOnBothSides(unittest.TestCase):

    CASES = (
        ({'padding': '16px'}, (16, 16, 16, 16)),
        ({'padding': '8px 16px'}, (8, 16, 8, 16)),
        ({'padding': '4px 8px 12px'}, (4, 8, 12, 8)),
        ({'padding': '0 20 24 20'}, (0, 20, 24, 20)),
        ({'padding': '10px', 'padding-bottom': '30px'}, (10, 10, 30, 10)),
    )

    def test_css_shorthand_reads_the_way_css_reads(self):
        for style, expected in self.CASES:
            self.assertEqual(_parse_padding(style), expected, style)

    def test_the_two_renderers_agree(self):
        for style, expected in self.CASES:
            self.assertEqual(_parse_padding_tk(style), expected, style)

    def test_the_fourth_value_survives_to_the_layout(self):
        xml = _layout('panel { background-color: #223344;'
                      ' padding: 0 20 24 20; }')
        self.assertIn('android:paddingBottom="24dp"', xml)

    def test_a_long_name_is_read_by_both(self):
        style = {'padding': '10px', 'padding-top': '2px'}
        self.assertEqual(_parse_padding(style)[0], 2)
        self.assertEqual(_parse_padding_tk(style)[0], 2)


class AMarginWithMoreThanOneValue(unittest.TestCase):
    """`margin: 24px 16px 0px 16px` used to mean a margin of 2,416,016.

    Both renderers stripped the non-digits out of the whole string and read
    what was left as one number, so the screen went blank in the Previewer and
    the layout was pushed off the phone -- with nothing said on either side.
    """

    def test_four_values_reach_the_previewer_as_four_sides(self):
        self.assertEqual(_parse_margin({'margin': '24px 16px 0px 16px'}),
                         (24, 16, 0, 16))

    def test_two_values_mirror(self):
        self.assertEqual(_parse_margin({'margin': '24px 16px'}), (24, 16, 24, 16))

    def test_three_values_reuse_the_left(self):
        self.assertEqual(_parse_margin({'margin': '1px 2px 3px'}), (1, 2, 3, 2))

    def test_one_value_is_every_side(self):
        self.assertEqual(_parse_margin({'margin': '16px'}), (16, 16, 16, 16))

    def test_a_long_name_still_wins_over_the_shorthand(self):
        self.assertEqual(_parse_margin({'margin': '10px', 'margin-top': '40px'}),
                         (40, 10, 10, 10))

    def test_the_phone_gets_one_attribute_per_side(self):
        xml = _layout('panel { margin: 24px 16px 0px 16px; }')
        self.assertIn('android:layout_marginTop="24dp"', xml)
        self.assertIn('android:layout_marginRight="16dp"', xml)
        self.assertIn('android:layout_marginBottom="0dp"', xml)
        self.assertIn('android:layout_marginLeft="16dp"', xml)
        self.assertNotIn('android:layout_margin="', xml)

    def test_one_value_still_uses_the_short_attribute(self):
        xml = _layout('panel { margin: 16px; }')
        self.assertIn('android:layout_margin="16dp"', xml)

    def test_the_two_runtimes_agree_on_every_shape(self):
        for css in ('16px', '24px 16px', '1px 2px 3px', '24px 16px 0px 16px'):
            with self.subTest(css=css):
                top, right, bottom, left = _parse_margin({'margin': css})
                xml = _layout('panel { margin: %s; }' % css)
                for value, name in ((top, 'Top'), (right, 'Right'),
                                    (bottom, 'Bottom'), (left, 'Left')):
                    needle = 'android:layout_margin%s="%ddp"' % (name, value)
                    short = 'android:layout_margin="%ddp"' % value
                    self.assertTrue(needle in xml or short in xml,
                                    '%s nao saiu no XML para %r' % (needle, css))


if __name__ == '__main__':
    unittest.main()
