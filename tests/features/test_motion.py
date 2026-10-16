# -*- coding: utf-8 -*-
"""Motion timing, and the four moments that share it."""

import unittest

from apkpy_lib import motion
from apkpy_lib.theme import Theme, apply_theme


class PresetTests(unittest.TestCase):
    def test_every_moment_scales_with_the_preset(self):
        for moment in motion.MOMENTS:
            durations = [motion.duration(moment, preset)
                         for preset in ('subtle', 'standard', 'expressive')]
            self.assertEqual(durations, sorted(durations), moment)
            self.assertTrue(all(value > 0 for value in durations), moment)

    def test_none_switches_everything_off(self):
        for moment in motion.MOMENTS:
            self.assertEqual(motion.duration(moment, 'none'), 0, moment)
        self.assertTrue(motion.is_disabled('none'))
        self.assertFalse(motion.is_disabled(None))

    def test_none_beats_a_per_component_override(self):
        # Otherwise motion="none" would be a suggestion rather than a switch.
        self.assertEqual(motion.duration('visibility', 'none', '400ms'), 0)

    def test_css_durations_are_understood(self):
        self.assertEqual(motion.parse_duration('220ms', 0), 220)
        self.assertEqual(motion.parse_duration('0.5s', 0), 500)
        self.assertEqual(motion.parse_duration('1.5s', 0), 1500)
        self.assertEqual(motion.parse_duration('220', 0), 220)
        self.assertEqual(motion.parse_duration('none', 99), 0)
        self.assertEqual(motion.parse_duration(None, 77), 77)
        self.assertEqual(motion.parse_duration('nonsense', 77), 77)

    def test_a_press_is_quicker_than_a_screen(self):
        self.assertLess(motion.duration('press'), motion.duration('visibility'))
        self.assertLess(motion.duration('visibility'), motion.duration('screen'))

    def test_unknown_names_are_rejected_not_ignored(self):
        with self.assertRaises(ValueError):
            motion.duration('sideways')
        with self.assertRaises(ValueError):
            motion.normalise_preset('turbo')
        with self.assertRaises(ValueError):
            motion.normalise_press('bounce')
        with self.assertRaises(ValueError):
            motion.normalise_transition('flip')
        with self.assertRaises(ValueError):
            motion.normalise_indicator('blob')


class PressTests(unittest.TestCase):
    def test_default_is_a_tint(self):
        self.assertEqual(motion.normalise_press(None), 'tint')
        self.assertEqual(motion.normalise_press(''), 'tint')

    def test_press_none_silences_the_android_ripple(self):
        from apkpy_lib.core.compiler import translate_python_to_android
        result = translate_python_to_android(
            'from apkpy_lib import Screen, button, run\n'
            'home = Screen(id="home")\n'
            'button("a", id="b1", screen=home)\n'
            'button("b", id="b2", screen=home)\n'
            'style = """\nb1 { press: none; }\n"""\n'
            'run(start_screen=home)\n')
        layout = result['res/layout/activity_screen_home.xml']
        # A ripple is the only press feedback Android gives for free, so
        # turning it off has to be explicit rather than merely undocumented.
        self.assertEqual(layout.count('app:rippleColor'), 1)

    def test_a_press_is_the_shortest_moment(self):
        for preset in ('subtle', 'standard', 'expressive'):
            self.assertEqual(
                motion.duration('press', preset),
                min(motion.duration(m, preset) for m in motion.MOMENTS))


class NoWindowSideEffectTests(unittest.TestCase):
    """Motion must not build a Tk window as a side effect.

    ``ui._app`` is a lazy proxy: reading any attribute constructs the
    Previewer. A fade that reached for ``_app.root`` opened an empty window
    from ``apkpy_lib`` alone -- including during ``apkpy build`` -- and broke
    every callback that delivers synchronously when no root exists.
    """

    def test_show_and_hide_do_not_construct_the_previewer(self):
        from apkpy_lib import Screen, label, ui

        if ui._app._instance is not None:
            self.skipTest('a Previewer window already exists in this process')
        screen = Screen(id='motion_probe')
        component = label('x', id='motion_probe_label', screen=screen)
        component.hide()
        component.show()
        self.assertIsNone(ui._app._instance)

    def test_fade_declines_when_there_is_no_window(self):
        from apkpy_lib import ui

        if ui._app._instance is not None:
            self.skipTest('a Previewer window already exists in this process')
        self.assertFalse(ui._fade_component(None, True, 200))


class EasingTests(unittest.TestCase):
    def test_curve_is_bounded_and_monotonic(self):
        self.assertEqual(motion.ease(0.0), 0.0)
        self.assertEqual(motion.ease(1.0), 1.0)
        values = [motion.ease(step / 40.0) for step in range(41)]
        for earlier, later in zip(values, values[1:]):
            self.assertLessEqual(earlier, later + 1e-9)
        self.assertTrue(all(-1e-9 <= value <= 1 + 1e-9 for value in values))

    def test_curve_is_fast_out_slow_in(self):
        # Material's standard easing front-loads: past halfway by mid-flight.
        self.assertGreater(motion.ease(0.5), 0.6)
        self.assertLess(motion.ease(0.1), 0.15)

    def test_out_of_range_progress_is_clamped(self):
        self.assertEqual(motion.ease(-3), 0.0)
        self.assertEqual(motion.ease(4), 1.0)

    def test_the_named_android_interpolator_matches_the_python_curve(self):
        # Both sides must name the same curve; the resource is the contract.
        self.assertEqual(
            motion.android_interpolator(),
            '@android:interpolator/fast_out_slow_in')


class ThemeTests(unittest.TestCase):
    def test_motion_reaches_both_renderers_through_the_theme_tokens(self):
        merged = apply_theme({}, Theme(motion='expressive'))
        self.assertEqual(merged['__theme__']['motion'], 'expressive')

    def test_default_is_on(self):
        # The library looked static because nothing moved by default.
        self.assertEqual(Theme().motion, 'standard')
        self.assertFalse(motion.is_disabled(Theme().motion))

    def test_a_bad_preset_fails_at_declaration_not_silently(self):
        with self.assertRaises(ValueError):
            Theme(motion='swoosh')


class BothRuntimesAgreeTests(unittest.TestCase):
    """The test that holds the design, as with icons and upload_button."""

    def test_previewer_and_compiler_resolve_the_same_duration(self):
        from apkpy_lib import ui
        from apkpy_lib.core import compiler

        self.assertIs(ui._motion, motion)
        self.assertIs(compiler.motion, motion)

        for preset in motion.PRESETS:
            for moment in motion.MOMENTS:
                self.assertEqual(
                    ui._motion.duration(moment, preset),
                    compiler.motion.duration(moment, preset),
                    '%s/%s' % (moment, preset),
                )

    def test_the_previewer_reads_the_preset_from_the_theme(self):
        from apkpy_lib import ui
        previous = dict(ui.global_styles)
        try:
            ui.global_styles.clear()
            ui.global_styles.update(apply_theme({}, Theme(motion='subtle')))
            self.assertEqual(ui._motion_preset(), 'subtle')
            self.assertEqual(
                ui._motion.duration('visibility', ui._motion_preset()), 120)
        finally:
            ui.global_styles.clear()
            ui.global_styles.update(previous)

    def test_the_previewer_fade_reads_the_real_theme_background(self):
        from apkpy_lib import ui
        previous = dict(ui.global_styles)
        try:
            ui.global_styles.clear()
            ui.global_styles.update(apply_theme({}, Theme(mode='dark')))
            # It used to be the literal #ffffff, so a dark app flashed white.
            self.assertNotEqual(ui._theme_background(), (255, 255, 255))
            red, green, blue = ui._theme_background()
            self.assertLess(red + green + blue, 200)
        finally:
            ui.global_styles.clear()
            ui.global_styles.update(previous)


class TheActiveTabLooksTheSameOnBothSides(unittest.TestCase):
    """The bar's state signals, checked against Material's own values.

    Material 1.11's ``Widget.MaterialComponents.BottomNavigationView`` points
    both ``itemTextAppearanceActive`` and ``itemTextAppearanceInactive`` at
    ``textAppearanceCaption`` -- 12sp -- and ``NavigationBarView`` turns
    ``itemTextAppearanceActiveBoldEnabled`` on by default: the active label is
    bold.  That was once read as "only the tint changes", measured on a phone
    whose font theme had lost every bold; the bold is back on both sides.
    """

    def test_the_active_label_is_bold_and_the_others_are_not(self):
        from apkpy_lib import ui
        self.assertIn('bold', ui._nav_label_font(True))
        self.assertNotIn('bold', ui._nav_label_font(False))

    def test_the_phone_is_told_the_same_rule(self):
        from apkpy_lib import theme
        from apkpy_lib.core.compiler import translate_python_to_android
        files = translate_python_to_android(APP_WITH_A_BAR)
        layouts = chr(10).join(
            body for name, body in files.items() if name.startswith('res/layout'))
        self.assertIn(
            'app:itemTextAppearanceActiveBoldEnabled="%s"'
            % str(theme.NAV_ACTIVE_LABEL_BOLD).lower(), layouts)

    def test_the_label_is_sized_in_pixels_not_points(self):
        from apkpy_lib import ui
        # Positive sizes are points: 10pt is 13.3px at 96dpi, which is the
        # mistake _build_tk_font's docstring exists to prevent.
        self.assertLess(font_size(ui._nav_label_font()), 0)

    def test_the_label_is_material_caption_size(self):
        from apkpy_lib import ui
        self.assertEqual(ui.NAV_LABEL_SP, 12)
        self.assertEqual(abs(font_size(ui._nav_label_font())), 12)

    def test_the_compiler_leaves_the_caption_appearance_alone(self):
        # If the generated XML ever set itemTextAppearanceActive, the phone
        # would grow the active label and this parity would silently break.
        from apkpy_lib.core.compiler import translate_python_to_android
        files = translate_python_to_android(APP_WITH_A_BAR)
        layouts = chr(10).join(
            body for name, body in files.items() if name.startswith('res/layout'))
        self.assertIn('BottomNavigationView', layouts)
        self.assertNotIn('itemTextAppearanceActive=', layouts)
        self.assertNotIn('itemTextAppearanceInactive=', layouts)


def font_size(font_tuple):
    return font_tuple[1]


APP_WITH_A_BAR = """from apkpy_lib import Screen, bottom_nav, label, run
home = Screen(id="home")
perfil = Screen(id="perfil")
label("a", id="a", screen=home)
label("b", id="b", screen=perfil)
bottom_nav([home, perfil], labels=["A", "B"], icons=["home", "person"])
run(start_screen=home)
"""


if __name__ == '__main__':
    unittest.main()
