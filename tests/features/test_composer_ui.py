# -*- coding: utf-8 -*-
"""The pieces a chat-style composer needs, and their parity.

A composer is a bordered container holding a borderless field and a row of
pill buttons.  Every piece already existed; what did not was agreement between
the two runtimes about transparency, borders and casing -- the three places a
composer diverged, one of which crashed the Previewer outright.
"""

import unittest

from apkpy_lib import icons
from apkpy_lib.theme import apply_text_transform, normalize_text_transform
from apkpy_lib.core.compiler import (
    _generate_drawable_xml,
    _material_icon_path,
    _resolve_color,
)


class ComposerIconTests(unittest.TestCase):
    def test_the_composer_controls_exist(self):
        for name in ('mic', 'send', 'stop', 'bolt',
                     'expand_more', 'expand_less', 'content_copy'):
            self.assertIsNotNone(icons.resolve(name), name)
            self.assertNotEqual(
                icons.resolve(name), icons.resolve('circle'), name)

    def test_the_composer_controls_resolve_the_same_on_both_sides(self):
        for name in ('mic', 'send', 'stop', 'bolt',
                     'expand_more', 'expand_less', 'content_copy'):
            self.assertEqual(_material_icon_path(name), icons.resolve(name),
                             name)

    def test_the_names_people_actually_type_reach_them(self):
        self.assertEqual(icons.resolve('microphone'), icons.resolve('mic'))
        self.assertEqual(icons.resolve('voice'), icons.resolve('mic'))
        self.assertEqual(icons.resolve('lightning'), icons.resolve('bolt'))
        self.assertEqual(icons.resolve('flash'), icons.resolve('bolt'))
        self.assertEqual(icons.resolve('copy'), icons.resolve('content_copy'))
        self.assertEqual(icons.resolve('chevron_down'),
                         icons.resolve('expand_more'))
        self.assertEqual(icons.resolve('submit'), icons.resolve('send'))

    def test_the_chevrons_are_mirror_images_of_each_other(self):
        # Catches the pair being copied without flipping, which reads as a
        # dropdown that never closes.
        self.assertNotEqual(icons.resolve('expand_more'),
                            icons.resolve('expand_less'))


class TextTransformTests(unittest.TestCase):
    """Material 2 shouts button labels; `text-transform: none` stops it."""

    def test_the_default_keeps_the_shouting(self):
        # Changing it would restyle every app already built.
        self.assertEqual(normalize_text_transform(None), 'uppercase')
        self.assertEqual(normalize_text_transform(''), 'uppercase')
        self.assertEqual(apply_text_transform('Opus 5', None), 'OPUS 5')

    def test_none_leaves_the_label_alone(self):
        self.assertEqual(apply_text_transform('Opus 5', 'none'), 'Opus 5')
        self.assertEqual(apply_text_transform('Opus 5', ' NONE '), 'Opus 5')

    def test_a_value_neither_side_can_do_is_refused_not_guessed(self):
        # capitalize/lowercase would have to rewrite the string at build time
        # and would then not apply to text set at runtime.
        self.assertIsNone(normalize_text_transform('capitalize'))
        self.assertIsNone(normalize_text_transform('lowercase'))
        # ...and the label keeps the look it has rather than changing silently.
        self.assertEqual(apply_text_transform('Opus 5', 'capitalize'),
                         'OPUS 5')


class BorderlessSurfaceTests(unittest.TestCase):
    """`border-width: 0` means no border, in both states, on both sides."""

    def test_no_stroke_when_the_width_is_zero(self):
        xml = _generate_drawable_xml(
            '#00000000', 28, border_color='#3A3A3A', border_width=0,
            focus_color='#2F2F2F',
        )
        self.assertNotIn('<stroke', xml)

    def test_focus_does_not_grow_a_border_that_was_asked_away(self):
        # The focused item used to carry a 1dp stroke unconditionally, so a
        # borderless field sprouted a box on the phone the moment it was
        # tapped -- and never did in the Previewer.
        xml = _generate_drawable_xml(
            '#00000000', 28, border_width=0, focus_color='#2F2F2F',
        )
        self.assertIn('state_focused', xml)
        self.assertNotIn('<stroke', xml)

    def test_an_explicit_border_still_thickens_on_focus(self):
        xml = _generate_drawable_xml(
            '#212121', 12, border_color='#3A3A3A', border_width=2,
            focus_color='#2F2F2F',
        )
        self.assertIn('android:width="2dp" android:color="#3A3A3A"', xml)
        self.assertIn('android:width="2dp" android:color="#2F2F2F"', xml)


class ColourShorthandTests(unittest.TestCase):
    """parseColor accepts only #RRGGBB and #AARRGGBB; CSS writes shorthand."""

    def test_three_digit_shorthand_is_expanded(self):
        self.assertEqual(_resolve_color('#111'), '#111111')

    def test_four_digits_are_the_shorthand_of_eight_not_of_css_rgba(self):
        # This project reads eight digits as #AARRGGBB throughout -- keyword
        # "transparent" is #00000000 -- so #0000 has to be transparent too.
        self.assertEqual(_resolve_color('#0000'), '#00000000')
        self.assertEqual(_resolve_color('transparent'), '#00000000')

    def test_a_full_length_colour_is_passed_through(self):
        self.assertEqual(_resolve_color('#2F2F2F'), '#2F2F2F')
        self.assertEqual(_resolve_color('#FF6750A4'), '#FF6750A4')


if __name__ == '__main__':
    unittest.main()
