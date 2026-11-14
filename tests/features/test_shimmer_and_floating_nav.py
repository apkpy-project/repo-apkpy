# -*- coding: utf-8 -*-
"""shimmer: on a box, and the floating bottom bar (bottom_nav { ... }).

Both come from the stylesheet and are decided once for both runtimes:
shimmer_rules says where the band of light is, theme.nav_look how the bar
looks and whether it floats.
"""

import unittest

from apkpy_lib import shimmer_rules
from apkpy_lib.theme import nav_look

from test_real_screens import _build, _java

_NAV_APP = ('home = Screen(id="home", scroll=True)\n'
            'other = Screen(id="other")\n'
            'label("Hi", screen=home)\n'
            'label("Yo", screen=other)\n'
            'bottom_nav([home, other], labels=["A", "B"], icons=["home", "person"])\n')
_FLOAT = ('bottom_nav { margin: 16px; border-radius: 28px; background-color: rgba(20, 19, 34, 0.78);'
          ' border-color: #333344; border-width: 1px; color: #6D6B8C; active-color: #8B6CFF;'
          ' indicator-color: #2A2A3A; }')


def _layout(files, name):
    return next(v for k, v in files.items() if k.startswith('res/layout/') and name in k)


class ShimmerRules(unittest.TestCase):

    def test_parse(self):
        self.assertEqual(shimmer_rules.parse('2.4s'), (2400, '#59FFFFFF'))
        self.assertEqual(shimmer_rules.parse('900ms #80FF0000'), (900, '#80FF0000'))
        self.assertIsNone(shimmer_rules.parse('none'))
        self.assertIsNone(shimmer_rules.parse(''))

    def test_the_band_sweeps_then_rests(self):
        self.assertEqual(shimmer_rules.offset(0.0), -1.0)
        self.assertAlmostEqual(shimmer_rules.offset(0.3), 0.0)
        self.assertIsNone(shimmer_rules.offset(0.7))
        self.assertEqual(shimmer_rules.strength(0.5), 1.0)
        self.assertEqual(shimmer_rules.strength(1.2), 0.0)


class ShimmerOnThePhone(unittest.TestCase):

    def test_a_box_with_shimmer_gets_the_overlay(self):
        files = _build('home = Screen(id="home")\n'
                       't = container(id="track", screen=home)\n'
                       'container(id="fill", parent=t)\n',
                       'fill { background-color: #7C5CFF; border-radius: 4px; height: 7px;'
                       ' shimmer: 2.4s rgba(255, 255, 255, 0.35); }')
        self.assertIn('java/ApkpyShimmer.java', files)
        self.assertIn('ApkpyShimmer.on(findViewById(R.id.cnt2), 0x59FFFFFF, 2400, 4.0f);',
                      _java(files))

    def test_without_it_nothing_ships(self):
        files = _build('home = Screen(id="home")\ncontainer(id="fill", screen=home)\n')
        self.assertNotIn('java/ApkpyShimmer.java', files)


class FloatingNav(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = _build(_NAV_APP, _FLOAT)
        cls.plain = _build(_NAV_APP)

    def test_the_look(self):
        look = nav_look({'bottom_nav': {'margin': '16px', 'border-radius': '28px'}})
        self.assertTrue(look['floating'])
        self.assertEqual(look['margin'], 16.0)
        self.assertFalse(nav_look({'bottom_nav': {'color': '#FFFFFF'}})['floating'])
        self.assertEqual(nav_look({'bottom_nav': {'color': '#FFFFFF'}})['inactive'], '#FFFFFF')

    def test_the_bar_is_a_card_off_the_edges(self):
        home = _layout(self.files, 'home')
        self.assertIn('android:layout_marginBottom="16dp"', home)
        self.assertIn('android:background="@drawable/apkpy_nav_bar"', home)
        self.assertIn('app:elevation="0dp"', home)
        shape = self.files['res/drawable/apkpy_nav_bar.xml']
        self.assertIn('<corners android:radius="28dp" />', shape)
        self.assertIn('android:left="0dp"', shape)

    def test_the_content_runs_on_under_it(self):
        home = _layout(self.files, 'home')
        self.assertNotIn('android:layout_above="@id/bottom_nav"', home)
        self.assertIn('android:paddingBottom="96dp"', home)
        self.assertIn('android:clipToPadding="false"', home)
        other = _layout(self.files, 'other')
        self.assertIn('android:layout_marginBottom="96dp"', other)

    def test_the_stylesheet_colours_reach_the_items(self):
        colours = self.files['res/color/nav_item_color.xml']
        self.assertIn('android:color="#8B6CFF"', colours)
        self.assertIn('android:color="#6D6B8C"', colours)

    def test_it_keeps_clear_of_the_gesture_bar_with_the_root(self):
        self.assertIn('if (false && _apkpyNavHost.getFitsSystemWindows()) {', _java(self.files))

    def test_without_the_block_the_bar_is_as_it_was(self):
        home = _layout(self.plain, 'home')
        self.assertIn('android:layout_above="@id/bottom_nav"', home)
        self.assertNotIn('apkpy_nav_bar', home)
        self.assertNotIn('res/drawable/apkpy_nav_bar.xml', self.plain)
        self.assertIn('if (_apkpyNavHost.getFitsSystemWindows()) {', _java(self.plain))


if __name__ == '__main__':
    unittest.main()
