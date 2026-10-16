# -*- coding: utf-8 -*-
"""Switching the app's appearance while it runs.

The colours used to be written into the layouts as literals -- 472 of them in
a two-screen app -- so nothing could change them without regenerating the
project. A colour that came from a theme token is now a resource reference,
answered by ``values/`` in day mode and ``values-night/`` in night mode, and
switching is `AppCompatDelegate` choosing between the two tables.

The rule that decides everything: **a token becomes a reference, a colour
written by hand stays exactly as written.** ``#C96442`` in a stylesheet was a
decision, not a default, and a decision that changes colour on its own is a
bug.

The two runtimes cannot share the mechanism -- Tk has no resource system, so
the Previewer swaps the ``Theme`` and re-renders -- so what these tests pin is
that both build their two palettes from the *one* theme the app declared.
"""

import unittest

from apkpy_lib.theme import Theme, apply_theme, token_of
from apkpy_lib.core.compiler import translate_python_to_android


DARK = ('run(start_screen=home, theme=Theme(mode="dark", primary="#C96442", '
        'background="#1B1B19", text="#F5F4EF"))')


def _app(style='', run=DARK, body=''):
    return (
        'from apkpy_lib import Screen, Theme, appearance, button, label, run\n'
        'home = Screen(id="home")\n'
        'label("Hello", id="t", screen=home)\n'
        + body +
        run + '\n'
        'style = """\n' + style + '\n"""\n'
    )


def _files(source):
    files = translate_python_to_android(source)
    if 'error.txt' in files:
        raise AssertionError(files['error.txt'][:300])
    return files


class ATokenBecomesAReference(unittest.TestCase):
    """The hinge: what can change, and what must not."""

    def test_a_token_colour_is_a_resource(self):
        xml = _files(_app('t { color: var(--primary); }'))[
            'res/layout/activity_screen_home.xml']
        self.assertIn('android:textColor="@color/apkpy_primary"', xml)

    def test_a_hand_written_colour_is_left_alone(self):
        xml = _files(_app('t { color: #00AA88; }'))[
            'res/layout/activity_screen_home.xml']
        self.assertIn('android:textColor="#00AA88"', xml)
        self.assertNotIn('@color/apkpy_', xml.split('textColor')[1][:40])

    def test_a_derived_shade_is_not_a_token(self):
        # _mix_color produces a new colour, not that token any more, so it
        # cannot claim a reference: the night table has no entry for it.
        theme = Theme(mode='dark')
        merged = apply_theme({}, theme)
        self.assertIsNone(token_of(merged['list_row']['pressed-color']))
        self.assertEqual(token_of(merged['list_row']['background-color']),
                         'surface')

    def test_the_theme_defaults_keep_their_provenance(self):
        merged = apply_theme({}, Theme(mode='dark'))
        self.assertEqual(token_of(merged['button']['background-color']),
                         'primary')
        self.assertEqual(token_of(merged['body']['background-color']),
                         'background')


class TwoTablesFromOneTheme(unittest.TestCase):

    def test_both_tables_are_written(self):
        files = _files(_app())
        self.assertIn('res/values/apkpy_theme.xml', files)
        self.assertIn('res/values-night/apkpy_theme.xml', files)

    def test_day_is_light_and_night_is_dark(self):
        files = _files(_app())
        self.assertIn('<color name="apkpy_background">#FFFBFE</color>',
                      files['res/values/apkpy_theme.xml'])
        self.assertIn('<color name="apkpy_background">#1B1B19</color>',
                      files['res/values-night/apkpy_theme.xml'])

    def test_the_accent_survives_the_flip(self):
        # An orange primary is orange in both modes; that is what an accent is.
        files = _files(_app())
        for table in ('res/values/apkpy_theme.xml',
                      'res/values-night/apkpy_theme.xml'):
            self.assertIn('<color name="apkpy_primary">#C96442</color>',
                          files[table])

    def test_a_hand_picked_surface_does_not_carry_over(self):
        # #1B1B19 was chosen because the mode was dark. Carried into light it
        # would make a light mode that is still dark -- a switch that appears
        # to do nothing.
        light = Theme(mode='dark', background='#1B1B19').counterpart()
        self.assertEqual(light.mode, 'light')
        self.assertNotEqual(str(light.tokens['background']), '#1B1B19')

    def test_the_status_bar_icons_follow_the_mode(self):
        files = _files(_app())
        self.assertIn('<item name="android:windowLightStatusBar">true</item>',
                      files['res/values/themes.xml'])
        self.assertIn('<item name="android:windowLightStatusBar">false</item>',
                      files['res/values-night/themes.xml'])


class TheSwitchIsOptIn(unittest.TestCase):
    """An app that never switches carries none of the machinery."""

    BODY = ('button("Light", id="b", screen=home, '
            'command=lambda: appearance.set("light"))\n')

    def test_the_declared_mode_is_pinned_at_startup(self):
        # Without this, values-night/ would make every existing dark app
        # follow the phone -- a behaviour nobody asked for.
        java = _files(_app())['java/Screen_homeActivity.java']
        self.assertIn('_apkpyApplyAppearance(_apkpyAppearanceShown)', java)
        self.assertIn('"dark"', java)

    def test_setting_it_stores_and_applies(self):
        java = _files(_app(body=self.BODY))['java/Screen_homeActivity.java']
        self.assertIn('_apkpyStorageSet("__apkpy_appearance"', java)
        self.assertIn('setDefaultNightMode', java)

    def test_a_stopped_screen_is_recreated_when_it_comes_back(self):
        # AppCompat recreates started activities; one waiting in the back
        # stack came back wearing the appearance it was built with.
        java = _files(_app(body=self.BODY))['java/Screen_homeActivity.java']
        self.assertIn('_apkpyMode.equals(_apkpyAppearanceShown)', java)
        self.assertIn('recreate();', java)

    def test_an_app_that_never_switches_gets_no_resume_check(self):
        java = _files(_app())['java/Screen_homeActivity.java']
        self.assertNotIn('_apkpyMode.equals', java)

    def test_get_reads_the_same_key_the_previewer_writes(self):
        """Read where the value is used, not where the file happens to mention it.

        This asked for ``label(appearance.get(), ...)`` and then looked for the
        key anywhere in the file -- which every app contains, because onCreate
        restores the appearance whether or not anybody calls get(). It passed
        without exercising the call at all, and it passed while that very line
        rendered blank on the phone: a component's text is written into the
        layout at build time, so a call cannot go there.
        """
        source = _app(body=(
            'mode = label("", id="m", screen=home)\n'
            '\n\ndef show():\n    mode.set_value(appearance.get())\n\n\n'
            'button("Show", id="show", screen=home, command=show)\n'
        ))
        java = _files(source)['java/Screen_homeActivity.java']
        reads = [line for line in java.splitlines()
                 if 'setText' in line and '__apkpy_appearance' in line]
        self.assertTrue(reads, 'appearance.get() nao chegou ao label')
        for line in reads:
            self.assertIn('_apkpyDeclaredAppearance()', line)

    def test_a_call_cannot_be_a_components_text(self):
        # The layout is written before the app runs, so this used to leave
        # android:text="" -- the Previewer showed the value, the phone showed
        # nothing, and no build said a word.
        source = _app(body='label(appearance.get(), id="m", screen=home)\n')
        files = translate_python_to_android(source)
        self.assertIn('error.txt', files)
        self.assertIn('U2033', files['error.txt'])


class ThePreviewerAgrees(unittest.TestCase):
    """Different machinery, the same two palettes."""

    def test_the_pair_is_derived_once_and_kept(self):
        # Deriving on every switch loses the author's own colours on the way
        # back, because a counterpart only carries the accent.
        from apkpy_lib import ui
        declared = Theme(mode='dark', primary='#C96442', background='#1B1B19')
        ui._declared_theme[0] = declared
        ui._APPEARANCE_PAIR.clear()
        first = ui._theme_for('dark')
        ui._theme_for('light')
        self.assertIs(ui._theme_for('dark'), first)
        self.assertEqual(str(first.tokens['background']), '#1B1B19')

    def test_the_modes_it_accepts_match_the_generated_java(self):
        from apkpy_lib.ui import APPEARANCE_MODES
        self.assertEqual(set(APPEARANCE_MODES), {'dark', 'light', 'system'})

    def test_an_unknown_mode_is_refused(self):
        from apkpy_lib import appearance
        with self.assertRaises(ValueError):
            appearance.set('sepia')


if __name__ == '__main__':
    unittest.main()
