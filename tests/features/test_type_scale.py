# -*- coding: utf-8 -*-
"""A vocabulary for sizes and for the planes under them.

Colours have had names since the beginning -- ``var(--primary)`` -- and sizes
have had none. The 25 shipped examples name **17 different font sizes** between
them, with 13px, 14px and 15px accounting for 32 uses: the same intent, written
three ways, because there was nothing to write instead. Nobody chose that; it
is what happens when every size is decided alone.

The same was true one layer down. There was exactly one ``--surface``, so a
panel above a panel, or a hairline between two rows, had to be a hand-written
hex -- and a hand-written hex is the one thing that cannot follow the theme
into night mode.

Two things have to hold for this to be worth having:

* the ramp must reach the phone as ``sp`` and the Previewer as ``px``, from the
  same table, or it becomes another way for the two to disagree;
* adding it must not move a single pixel of an app that never asks for it.
"""

import unittest

from apkpy_lib import theme as _theme
from apkpy_lib.theme import Theme, apply_theme, label_variant_style
from apkpy_lib.core.compiler import (
    _THEMED_COLOR_TOKENS, translate_python_to_android,
)
from apkpy_lib.core.style_parser import COLOR_PROPERTIES, KNOWN_PROPERTIES
from apkpy_lib.diagnostics import ApkpyError


APP = (
    'from apkpy_lib import Screen, Theme, container, label, run\n'
    'h = Screen(id="h")\n'
    'label("T", variant="title", screen=h)\n'
    'label("B", variant="body", screen=h)\n'
    'label("R", id="big", screen=h)\n'
    'panel = container(id="panel", screen=h)\n'
    'label("P", parent=panel)\n'
    'run(start_screen=h, theme=Theme(mode="dark"%s))\n'
    'style = """\n%s\n"""\n'
)


def _files(css='', theme_args=''):
    out = translate_python_to_android(APP % (theme_args, css))
    if not out or 'error.txt' in out:
        raise AssertionError((out or {}).get('error.txt', 'no output')[:400])
    return out


def _text_sizes(css='', theme_args=''):
    xml = _files(css, theme_args)['res/layout/activity_screen_h.xml']
    return [line.split('"')[1]
            for line in xml.splitlines() if 'android:textSize' in line]


class TheRampIsMaterialsOwnSizes(unittest.TestCase):
    """Not a geometric series.

    A ratio produces 29.3px and someone rounds it differently on each side.
    These are the sp values Android's own type scale uses, which is the only
    tie-breaker this project accepts.
    """

    def test_the_default_base_gives_the_material_integers(self):
        scale = Theme().type_scale()
        self.assertEqual(scale, {
            'text-xs': '11px',    # labelSmall
            'text-sm': '12px',    # bodySmall
            'text-base': '14px',  # bodyMedium
            'text-lg': '16px',    # bodyLarge
            'text-xl': '20px',    # titleLarge
            'text-2xl': '24px',   # headlineSmall
            'text-3xl': '32px',   # headlineLarge
        })

    def test_the_steps_only_ever_go_up(self):
        order = ('text-xs', 'text-sm', 'text-base', 'text-lg', 'text-xl',
                 'text-2xl', 'text-3xl')
        for base in (12, 14, 16, 18, 24):
            sizes = Theme(font_size=base).type_scale()
            values = [float(sizes[name][:-2]) for name in order]
            self.assertEqual(values, sorted(values),
                             'ramp is not monotonic at base %d' % base)
            self.assertEqual(len(set(values)), len(values),
                             'two steps collapsed onto one at base %d' % base)

    def test_one_number_moves_the_whole_app(self):
        # The point of a ramp: raise the base, everything follows. This is the
        # same bargain `radius` and `spacing` already offer.
        small = Theme(font_size=14).type_scale()
        large = Theme(font_size=28).type_scale()
        for name in small:
            self.assertEqual(float(large[name][:-2]),
                             float(small[name][:-2]) * 2, name)

    def test_leading_is_a_multiple_not_a_length(self):
        # `line-height` has always read a bare number as a multiple of the
        # font size, on both sides. The tokens say the same thing.
        tokens = Theme().tokens
        for name in ('leading-tight', 'leading-normal', 'leading-loose'):
            self.assertNotIn('px', tokens[name])
            self.assertGreater(float(tokens[name]), 1.0)


class NothingMovesForAnAppThatNeverAsks(unittest.TestCase):
    """The contract the whole library is held to.

    ``label(variant="title")`` was 20px before the ramp existed and has to
    still be 20px, or every shipped app changes appearance because a *default*
    was refactored.
    """

    def test_the_label_variants_keep_their_sizes(self):
        for variant, size in (('title', '20px'), ('subtitle', '14px'),
                              ('body', '14px'), ('overline', '11px')):
            style = label_variant_style(apply_theme({}, Theme()), variant)
            self.assertEqual(style['font-size'], size, variant)

    def test_a_stylesheet_with_no_theme_at_all_still_gets_them(self):
        # No Theme() means no `__theme__` and so no ramp to read; the roles
        # fall back to the literals they always carried.
        for variant, size in (('title', '20px'), ('body', '14px')):
            self.assertEqual(
                label_variant_style({}, variant)['font-size'], size)

    def test_the_variants_now_follow_the_base(self):
        # And this is what the refactor bought: they are steps, not numbers.
        # The last two are the plain labels, on the body step.
        self.assertEqual(_text_sizes(), ['20sp', '14sp', '16sp', '16sp'])
        self.assertEqual(_text_sizes(theme_args=', font_size=28'),
                         ['40sp', '28sp', '32sp', '32sp'])

    def test_the_new_colours_reach_no_layout_on_their_own(self):
        files = _files()
        for path, body in files.items():
            if 'apkpy_theme.xml' in path:
                continue
            for token in ('surface_low', 'surface_high', 'border_subtle'):
                self.assertNotIn(token, str(body), '%s leaked into %s'
                                 % (token, path))


class TheRampReachesThePhone(unittest.TestCase):

    def test_a_step_becomes_sp(self):
        self.assertIn('32sp', _text_sizes('big { font-size: var(--text-3xl); }'))

    def test_both_runtimes_read_the_same_table(self):
        # The test that holds the design, and the same one the icons and the
        # motion presets are held to: there is one source, so there is nothing
        # for the two sides to disagree about. The compiler's sp figure is the
        # Previewer's px figure.
        theme = Theme(mode='dark', font_size=17)
        px = theme.type_scale()['text-2xl']
        sp = _text_sizes('big { font-size: var(--text-2xl); }',
                         ', font_size=17')[2]
        self.assertEqual(sp, px.replace('px', 'sp'))

    def test_leading_survives_the_trip(self):
        xml = _files('big { line-height: var(--leading-loose); }')[
            'res/layout/activity_screen_h.xml']
        self.assertIn('lineSpacingExtra', xml)


class BodyTextIsOneSizeOnBothSides(unittest.TestCase):
    """The divergence the ramp was dug up to fix.

    ``label("oi")`` with no stylesheet at all drew at **14px** in the Previewer
    and **16sp** on the phone. Not a rounding difference and not a font metric:
    two literals, written into two files years apart, each perfectly reasonable
    on its own. There was no name for "body text" for them to share, so nobody
    could see they disagreed -- and the desktop quietly under-drew the most
    used component in the library in every app ever written with it.

    The phone's figure wins. The desktop is the approximation; the APK is the
    product.
    """

    def _previewer(self, theme=None):
        from apkpy_lib import ui
        before = ui.global_styles
        try:
            ui.global_styles = (
                {} if theme is None else {'__theme__': dict(theme.tokens)})
            return ui._body_text_size()
        finally:
            ui.global_styles = before

    def _compiler(self, theme=None):
        from apkpy_lib.core import compiler
        before = compiler._APP_THEME[0]
        try:
            compiler._APP_THEME[0] = theme
            return compiler._body_text_size()
        finally:
            compiler._APP_THEME[0] = before

    def test_they_agree_with_no_theme_declared(self):
        self.assertEqual(self._previewer(), self._compiler())

    def test_they_agree_with_a_theme(self):
        for base in (None, 12, 14, 18, 22):
            theme = Theme() if base is None else Theme(font_size=base)
            self.assertEqual(self._previewer(theme), self._compiler(theme),
                             'base %r' % base)

    def test_and_the_figure_is_the_phones_old_one(self):
        # 16, not 14 -- so no compiled app changes size, and the Previewer
        # stops under-drawing.
        self.assertEqual(self._compiler(), 16)
        self.assertEqual(self._previewer(), 16)

    def test_it_is_the_body_step_and_moves_with_the_base(self):
        theme = Theme(font_size=21)
        self.assertEqual(self._compiler(theme),
                         int(theme.type_scale()[_theme.DEFAULT_TEXT_STEP][:-2]))


class TheNewPlanesFollowTheMode(unittest.TestCase):
    """A hand-written hex cannot switch to night mode; a token can.

    That is the entire reason these are tokens and not a note in the docs.
    """

    def _tables(self):
        files = _files()
        return (files['res/values/apkpy_theme.xml'],
                files['res/values-night/apkpy_theme.xml'])

    def test_each_new_colour_is_in_both_tables(self):
        day, night = self._tables()
        for token in ('surface_low', 'surface_high', 'border_subtle'):
            self.assertIn('apkpy_%s' % token, day)
            self.assertIn('apkpy_%s' % token, night)

    def test_and_answers_differently_in_each(self):
        day, night = self._tables()

        def value(table, token):
            for line in table.splitlines():
                if 'apkpy_%s"' % token in line:
                    return line.split('>')[1].split('<')[0]
            raise AssertionError('%s missing' % token)

        for token in ('surface_low', 'surface_high', 'border_subtle'):
            self.assertNotEqual(value(day, token), value(night, token), token)

    def _generated(self, css):
        # A container's fill leaves as a shape drawable, not an inline
        # attribute, so the reference has to be looked for across the project
        # rather than in the layout alone.
        return '\n'.join(str(body) for path, body in _files(css).items()
                         if 'apkpy_theme.xml' not in path)

    def test_a_layout_using_one_gets_a_reference_not_a_hex(self):
        out = self._generated('panel { background-color: var(--surface-high); }')
        self.assertIn('@color/apkpy_surface_high', out)
        self.assertNotIn('#2B2930', out)

    def test_a_hand_written_colour_still_never_moves(self):
        out = self._generated('panel { background-color: #C96442; }')
        self.assertIn('#C96442', out)
        self.assertNotIn('@color/apkpy_surface_high', out)

    def test_the_underscore_and_the_hyphen_are_the_same_token(self):
        for spelling in ('surface_high', 'surface-high'):
            self.assertIn('@color/apkpy_surface_high', self._generated(
                'panel { background-color: var(--%s); }' % spelling))


class ATokenCannotLandInTheWrongKindOfSlot(unittest.TestCase):
    """``--text`` is a colour and ``--text-lg`` is a size.

    Three characters apart, and each is silently wrong in the other's place: a
    size reaches Android's colour parser and kills the screen on open, while a
    colour in a size slot becomes the first digits in the hex -- ``#211F26``
    quietly means 21px. The second one has no symptom at all, which is why the
    ramp could not ship without this check.
    """

    def _refuse(self, css):
        with self.assertRaises(ApkpyError) as caught:
            apply_theme(css, Theme())
        self.assertEqual(caught.exception.code, 'U2031')

    def test_a_size_in_a_colour_property(self):
        self._refuse({'a': {'color': 'var(--text-lg)'}})
        self._refuse({'a': {'background-color': 'var(--radius)'}})

    def test_a_colour_in_a_size_property(self):
        self._refuse({'a': {'font-size': 'var(--surface)'}})
        self._refuse({'a': {'padding': 'var(--primary)'}})

    def test_a_typeface_name_is_not_a_colour_either(self):
        self._refuse({'a': {'color': 'var(--font-family)'}})

    def test_the_honest_uses_all_still_pass(self):
        # A guard that fires on correct code is worse than no guard.
        resolved = apply_theme({
            'a': {'box-shadow': '0 3px 8px var(--border)'},
            'b': {'padding': 'var(--spacing)'},
            'c': {'line-height': 'var(--leading-loose)'},
            'd': {'color': 'var(--text-secondary)'},
            'e': {'border-radius': 'var(--radius)'},
            'f': {'font-family': 'var(--font-family)'},
            'g': {'font-size': 'var(--text-sm)'},
            'h': {'item-background-color': 'var(--surface-low)'},
        }, Theme())
        self.assertEqual(resolved['b']['padding'], '12px')
        self.assertEqual(resolved['g']['font-size'], '12px')

    def test_an_unknown_token_is_still_the_other_error(self):
        # U2031 must not swallow U2028: a name with nothing behind it is a
        # different mistake with different advice.
        with self.assertRaises(ApkpyError) as caught:
            apply_theme({'a': {'color': 'var(--muted)'}}, Theme())
        self.assertEqual(caught.exception.code, 'U2028')


class ThePlanesFollowTheColoursTheAuthorChose(unittest.TestCase):
    """A new token must not smuggle Material's palette into someone's app.

    ``writehere.py`` picks a warm near-black ``#262624``. Handing it
    Material's ``#2B2930`` for the plane above would drop a purple-grey slab
    into a brown app -- the same accident that put an unwanted blue behind
    every container, arriving by a different door.
    """

    WARM = dict(mode='dark', background='#1B1B19', surface='#262624',
                text='#F5F4EF', border='#3A3A37')

    def _channels(self, value):
        v = str(value).lstrip('#')
        return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))

    def test_the_stack_runs_in_the_right_direction(self):
        t = Theme(**self.WARM)
        rise = [sum(self._channels(t.tokens[name]))
                for name in ('background', 'surface_low', 'surface',
                             'surface_high')]
        self.assertEqual(rise, sorted(rise), rise)
        self.assertEqual(len(set(rise)), 4, 'two planes came out identical')

    def test_the_derived_planes_keep_the_authors_hue(self):
        # Warm means red >= blue here. Material's dark planes are the other
        # way round, which is exactly how the mistake would show up.
        t = Theme(**self.WARM)
        for name in ('surface_low', 'surface_high', 'border_subtle'):
            red, _green, blue = self._channels(t.tokens[name])
            self.assertGreaterEqual(red, blue,
                                    '%s came out cool: %s'
                                    % (name, t.tokens[name]))

    def test_a_declared_plane_still_wins(self):
        t = Theme(surface='#262624', surface_high='#445566')
        self.assertEqual(str(t.tokens['surface_high']), '#445566')

    def test_a_theme_that_changed_nothing_keeps_materials_own(self):
        # Derivation is for authors who chose; it must not quietly replace the
        # palette for everyone else.
        self.assertEqual(str(Theme().tokens['surface_high']), '#ECE6F0')
        self.assertEqual(str(Theme(mode='dark').tokens['surface_low']),
                         '#1D1B20')

    def test_changing_only_the_accent_leaves_the_planes_alone(self):
        # An orange primary says nothing about what the surfaces should be.
        self.assertEqual(str(Theme(primary='#C96442').tokens['surface_high']),
                         '#ECE6F0')

    def test_a_subtle_border_is_quieter_than_the_real_one(self):
        t = Theme(**self.WARM)
        background = sum(self._channels(t.tokens['background']))
        border = sum(self._channels(t.tokens['border']))
        subtle = sum(self._channels(t.tokens['border_subtle']))
        self.assertLess(abs(subtle - background), abs(border - background))


class TheTablesCannotDriftApart(unittest.TestCase):
    """Each of these caught a duplicate that had to stay in step by hand."""

    def test_every_themed_colour_exists_in_both_palettes(self):
        # A token listed for the resource table but missing from a palette is
        # a KeyError in _color_table -- and only for apps that never declared
        # a Theme, which is the half the suite exercises least.
        for token in _THEMED_COLOR_TOKENS:
            if token == 'nav_indicator':   # mixed, not declared
                continue
            for mode in ('light', 'dark'):
                self.assertIn(token, _theme._PALETTES[mode],
                              '%s missing from the %s palette' % (token, mode))

    def test_the_colour_properties_are_part_of_the_vocabulary(self):
        self.assertTrue(COLOR_PROPERTIES <= KNOWN_PROPERTIES)

    def test_the_counterpart_keeps_the_ramp(self):
        # Night mode is the same theme in the other mode; an author who set a
        # base did not set it for one mode only.
        theme = Theme(mode='dark', font_size=17)
        self.assertEqual(theme.counterpart().type_scale(), theme.type_scale())

    def test_the_counterpart_flips_the_planes(self):
        # Surfaces belong to the mode they were written for. A dark
        # surface_high carried into light mode is a light mode that is dark.
        dark = Theme(mode='dark')
        light = dark.counterpart()
        for token in ('surface_low', 'surface_high', 'border_subtle'):
            self.assertNotEqual(dark.tokens[token], light.tokens[token], token)


if __name__ == '__main__':
    unittest.main()
