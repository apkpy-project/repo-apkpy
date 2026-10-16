# -*- coding: utf-8 -*-
"""text-align, letter-spacing and line-height, and their parity.

These three are the difference between a screen that looks like a form and one
that looks designed, and all three were missing entirely: a label was always
left, a button was always centred, and neither side had a word for tracking or
leading.

The tests that matter here are the ones that pin the *numbers*: Android
measures tracking in em and leading as what is left over after the font's own
line box, while CSS says px and total height.  Getting that arithmetic wrong is
a divergence you only see once the APK is on the phone.
"""

import unittest

from apkpy_lib.theme import (
    NATURAL_LINE_HEIGHT,
    TEXT_ALIGNS,
    letter_spacing_em,
    letter_spacing_px,
    line_height_px,
    line_spacing_extra,
    normalize_text_align,
)
from apkpy_lib.core.compiler import (
    _ANDROID_GRAVITY,
    _parse_typography_xml,
)
from apkpy_lib.ui import _TK_ANCHOR, _TK_JUSTIFY


class TextAlignTests(unittest.TestCase):
    def test_nothing_set_stays_nothing_set(self):
        # Every app already built relies on the old defaults, which the
        # renderers pick themselves.  A default here would restyle all of them.
        self.assertIsNone(normalize_text_align(None))
        self.assertIsNone(normalize_text_align(''))
        self.assertIsNone(normalize_text_align('   '))

    def test_the_three_values_resolve(self):
        for value in TEXT_ALIGNS:
            self.assertEqual(normalize_text_align(value), value)

    def test_logical_names_are_accepted(self):
        self.assertEqual(normalize_text_align('start'), 'left')
        self.assertEqual(normalize_text_align('END'), 'right')
        self.assertEqual(normalize_text_align('centre'), 'center')

    def test_justify_is_refused_rather_than_faked(self):
        # android:justificationMode arrived at API 26 and ApkPy targets 24, so
        # accepting it would mean an effect only newer phones ever showed.
        self.assertIsNone(normalize_text_align('justify'))
        self.assertIsNone(normalize_text_align('middle'))

    def test_both_backends_have_a_word_for_all_three(self):
        for value in TEXT_ALIGNS:
            self.assertIn(value, _ANDROID_GRAVITY)
            self.assertIn(value, _TK_ANCHOR)
            self.assertIn(value, _TK_JUSTIFY)

    def test_android_uses_logical_edges(self):
        # start/end rather than left/right, so a right-to-left locale mirrors
        # the row without the app asking.
        self.assertEqual(_ANDROID_GRAVITY['left'], 'start')
        self.assertEqual(_ANDROID_GRAVITY['right'], 'end')


class LetterSpacingTests(unittest.TestCase):
    def test_absent_and_normal_mean_no_tracking(self):
        self.assertEqual(letter_spacing_px(None, 16), 0.0)
        self.assertEqual(letter_spacing_px('', 16), 0.0)
        self.assertEqual(letter_spacing_px('normal', 16), 0.0)

    def test_a_bare_number_is_pixels(self):
        self.assertEqual(letter_spacing_px('2', 16), 2.0)
        self.assertEqual(letter_spacing_px('2px', 16), 2.0)

    def test_em_resolves_against_the_size_the_text_renders_at(self):
        self.assertAlmostEqual(letter_spacing_px('0.1em', 20), 2.0)
        self.assertAlmostEqual(letter_spacing_px('10%', 20), 2.0)

    def test_android_gets_em_because_that_is_what_it_measures_in(self):
        # android:letterSpacing is a multiple of the font size, not a length.
        self.assertAlmostEqual(letter_spacing_em('1.6px', 16), 0.1)
        self.assertAlmostEqual(letter_spacing_em('0.1em', 16), 0.1)

    def test_the_same_declaration_means_the_same_thing_in_both_units(self):
        self.assertEqual(
            letter_spacing_px('1.28px', 16), letter_spacing_px('0.08em', 16))

    def test_negative_tracking_survives(self):
        # Tightening a big heading is the one thing tracking is used for as
        # often as loosening a small one.
        self.assertEqual(letter_spacing_px('-0.5px', 16), -0.5)

    def test_nonsense_is_no_tracking_rather_than_a_crash(self):
        self.assertEqual(letter_spacing_px('wide', 16), 0.0)
        self.assertEqual(letter_spacing_px('1 2 3', 16), 0.0)


class LineHeightTests(unittest.TestCase):
    def test_absent_and_normal_leave_the_font_alone(self):
        self.assertIsNone(line_height_px(None, 16))
        self.assertIsNone(line_height_px('normal', 16))
        self.assertEqual(line_spacing_extra(None, 16), 0.0)

    def test_a_bare_number_is_a_multiple_the_way_css_reads_it(self):
        # The one place line-height and letter-spacing disagree, and CSS is why.
        self.assertEqual(line_height_px('1.5', 16), 24.0)
        self.assertEqual(line_height_px('24px', 16), 24.0)

    def test_the_leading_is_what_is_left_after_the_font_s_own_line_box(self):
        # The bug this catches: handing 1.5 straight to
        # android:lineSpacingMultiplier, which multiplies the font's box
        # (~1.2em) and lands 20% taller than the CSS asked for.
        self.assertAlmostEqual(
            line_spacing_extra('1.5', 16, natural=19.2), 4.8)
        self.assertAlmostEqual(
            line_spacing_extra('24px', 16, natural=19.2), 4.8)

    def test_asking_for_less_than_the_font_takes_gives_no_leading(self):
        # Android clamps at zero, so this is where the two sides agree.
        self.assertEqual(line_spacing_extra('1.0', 16, natural=19.2), 0.0)
        self.assertEqual(line_spacing_extra('8px', 16, natural=19.2), 0.0)

    def test_the_compiler_falls_back_to_the_font_s_usual_box(self):
        # It cannot measure Roboto at build time; the Previewer always can.
        self.assertAlmostEqual(
            line_spacing_extra('1.5', 16),
            24.0 - NATURAL_LINE_HEIGHT * 16,
        )


class TypographyXmlTests(unittest.TestCase):
    def test_an_untouched_style_emits_nothing_new(self):
        xml = _parse_typography_xml({'font-size': '16px'}, default_size=16)
        self.assertNotIn('letterSpacing', xml)
        self.assertNotIn('lineSpacingExtra', xml)

    def test_tracking_is_measured_against_the_declared_size(self):
        xml = _parse_typography_xml(
            {'font-size': '11px', 'letter-spacing': '1.5px'}, default_size=16)
        self.assertIn('android:letterSpacing="0.1364"', xml)

    def test_tracking_falls_back_to_the_size_the_component_renders_at(self):
        # No font-size on a label means 16sp, and the em has to match.
        xml = _parse_typography_xml({'letter-spacing': '1.6px'}, default_size=16)
        self.assertIn('android:letterSpacing="0.1"', xml)

    def test_zero_tracking_is_written_out_loud(self):
        # A MaterialButton tracks its label at ~0.089em by itself.  Skipping
        # the attribute because the number is zero would leave the phone
        # spaced out while the Previewer sat tight -- the exact shape of bug
        # this project keeps paying to avoid.
        xml = _parse_typography_xml(
            {'font-size': '15px', 'letter-spacing': '0px'}, default_size=0)
        self.assertIn('android:letterSpacing="0.0"', xml)

    def test_normal_means_leave_the_component_s_own_tracking_alone(self):
        xml = _parse_typography_xml(
            {'font-size': '15px', 'letter-spacing': 'normal'}, default_size=0)
        self.assertNotIn('letterSpacing', xml)

    def test_leading_is_written_in_sp_so_it_grows_with_the_text(self):
        # dp would keep the gap fixed while the reader's font-size setting
        # pushed the lines into each other.
        xml = _parse_typography_xml(
            {'font-size': '22px', 'line-height': '1.4'}, default_size=16)
        self.assertIn('android:lineSpacingExtra="4sp"', xml)

    def test_a_leading_that_rounds_to_nothing_is_not_written(self):
        xml = _parse_typography_xml(
            {'font-size': '16px', 'line-height': '1.2'}, default_size=16)
        self.assertNotIn('lineSpacingExtra', xml)


if __name__ == '__main__':
    unittest.main()
