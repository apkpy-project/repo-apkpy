# -*- coding: utf-8 -*-
"""`var(--name)`: the token that resolved, the one that did not, and the app
that never named a theme.

Two defects met here.

The first is the one this project pays the most for.  ``var(--primary)``
resolved to ``#6750A4`` in an app that declared a ``Theme`` and to the literal
text ``var(--primary)`` in an app that did not -- and the generated
``apkpy_theme.xml`` writes that same ``#6750A4`` either way, so the token was
never wrong, only unresolved.  The mistake surfaced forty seconds later as an
AAPT link failure whose stated cause is about stale generated files.

The second: a name with no token behind it resolved to *itself*, silently, on
both sides.  It is now `U2028`, raised in the one module the Previewer and the
compiler share, so whichever you run first is the one that tells you.
"""

import unittest

from apkpy_lib.diagnostics import ApkpyError
from apkpy_lib.theme import Theme, apply_theme
from apkpy_lib.core.compiler import translate_python_to_android


def _app(style, themed):
    run = ('run(start_screen=home, theme=Theme(mode="dark"))' if themed
           else 'run(start_screen=home)')
    return (
        'from apkpy_lib import Screen, Theme, label, run\n'
        'home = Screen(id="home")\n'
        'label("Hello", id="t", screen=home)\n'
        + run + '\n'
        'style = """\n' + style + '\n"""\n'
    )


def _text_color(source):
    files = translate_python_to_android(source)
    if 'error.txt' in files:
        raise AssertionError(files['error.txt'][:200])
    xml = files['res/layout/activity_screen_home.xml']
    for line in xml.splitlines():
        if 'android:textColor' in line:
            return line.split('"')[1]
    return None


class TokensResolveWithoutATheme(unittest.TestCase):
    """The defect: the same token, two answers, depending on one keyword."""

    def test_a_token_resolves_when_no_theme_is_named(self):
        # A referencia e' o que a resolucao produz agora: a cor esta' na
        # tabela, e o layout aponta-lhe para que o modo a possa mudar.
        self.assertEqual(
            _text_color(_app('t { color: var(--primary); }', themed=False)),
            '@color/apkpy_primary',
        )

    def test_it_is_the_colour_the_generated_theme_actually_uses(self):
        # Not an invented default: apkpy_theme.xml is written from this same
        # table, so resolving here cannot disagree with the built app.
        files = translate_python_to_android(
            _app('t { color: var(--primary); }', themed=False)
        )
        self.assertIn(
            '<color name="apkpy_primary">#6750A4</color>',
            files['res/values/apkpy_theme.xml'],
        )

    def test_a_named_theme_still_wins(self):
        files = translate_python_to_android(
            _app('t { color: var(--primary); }', themed=True)
        )
        self.assertEqual(
            _text_color(_app('t { color: var(--primary); }', themed=True)),
            '@color/apkpy_primary',
        )
        # O tema declarado decide o valor, nao a existencia da referencia.
        self.assertIn(
            '<color name="apkpy_primary">#D0BCFF</color>',
            files['res/values-night/apkpy_theme.xml'],
        )

    def test_the_literal_never_reaches_the_layout(self):
        for themed in (True, False):
            xml = translate_python_to_android(
                _app('t { color: var(--primary); }', themed=themed)
            )['res/layout/activity_screen_home.xml']
            self.assertNotIn('var(--', xml)

    def test_a_colour_written_by_hand_stays_a_literal(self):
        # A distincao toda: um token e' uma referencia, um hex e' um hex, e um
        # hex que muda de cor com o modo era uma cor que ninguem pediu.
        self.assertEqual(
            _text_color(_app('t { color: #C96442; }', themed=True)),
            '#C96442',
        )

    def test_a_dash_is_read_as_an_underscore(self):
        self.assertEqual(
            _text_color(_app('t { color: var(--text-secondary); }', themed=True)),
            _text_color(_app('t { color: var(--text_secondary); }', themed=True)),
        )


class UnknownTokenIsReported(unittest.TestCase):
    """A name with nothing behind it used to resolve to itself."""

    def test_it_raises_rather_than_passing_the_text_through(self):
        with self.assertRaises(ApkpyError) as caught:
            apply_theme({'t': {'color': 'var(--muted)'}}, Theme(mode='dark'))
        self.assertEqual(caught.exception.code, 'U2028')

    def test_it_raises_without_a_theme_too(self):
        with self.assertRaises(ApkpyError):
            apply_theme({'t': {'color': 'var(--muted)'}}, None)

    def test_the_report_names_the_rule_it_came_from(self):
        with self.assertRaises(ApkpyError) as caught:
            apply_theme({'card': {'background-color': 'var(--muted)'}}, None)
        self.assertIn('card', caught.exception.received)
        self.assertIn('background-color', caught.exception.received)

    def test_a_near_miss_is_offered_back(self):
        with self.assertRaises(ApkpyError) as caught:
            apply_theme({'t': {'color': 'var(--primry)'}}, None)
        self.assertTrue(
            any('var(--primary)' in s for s in caught.exception.suggestions),
            caught.exception.suggestions,
        )

    def test_the_valid_names_are_listed(self):
        with self.assertRaises(ApkpyError) as caught:
            apply_theme({'t': {'color': 'var(--muted)'}}, None)
        listed = ' '.join(caught.exception.suggestions)
        for token in ('primary', 'surface', 'text_secondary'):
            self.assertIn(token, listed)

    def test_the_compiler_surfaces_it_as_a_friendly_report(self):
        files = translate_python_to_android(
            _app('t { color: var(--muted); }', themed=False)
        )
        self.assertIn('U2028', files.get('error.txt', ''))


class NothingElseMoved(unittest.TestCase):
    """The guard: only tokens are resolved, and every value stays text."""

    def test_a_themeless_app_does_not_inherit_the_theme_stylesheet(self):
        # Resolving tokens must not drag in the theme's default styles, which
        # would rewrite the XML of every app that never asked for a theme.
        resolved = apply_theme({'t': {'color': 'var(--primary)'}}, None)
        self.assertEqual(list(resolved), ['t'])

    def test_values_without_a_token_are_untouched(self):
        resolved = apply_theme({'t': {'color': '#123456', 'rows': '3'}}, None)
        self.assertEqual(resolved['t'], {'color': '#123456', 'rows': '3'})

    def test_every_value_comes_back_as_text(self):
        # apply_theme used to stringify everything on its way through; both
        # renderers read these tables as text and one of them reading an int
        # is a divergence waiting to happen.
        resolved = apply_theme({'t': {'rows': 3}}, None)
        self.assertEqual(resolved['t']['rows'], '3')

    def test_a_themed_app_still_carries_its_tokens(self):
        resolved = apply_theme({}, Theme(mode='dark'))
        self.assertEqual(resolved['__theme__']['mode'], 'dark')
        self.assertEqual(resolved['__theme__']['primary'], '#D0BCFF')

    def test_no_theme_means_no_theme_block(self):
        self.assertNotIn('__theme__', apply_theme({'t': {'color': 'red'}}, None))


if __name__ == '__main__':
    unittest.main()
