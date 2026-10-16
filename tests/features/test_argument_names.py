# -*- coding: utf-8 -*-
"""An argument the component does not take should say so.

The Previewer gets this free: Python checks the call and raises TypeError the
moment it runs. The compiler reads the source as text, so
``image("p.png", blurr=8)`` transpiled clean and shipped a blur that was never
applied -- visible only to whoever happened to open the Previewer first.

This is U2029 one level up: same shape, same silence, same fix.
"""

import inspect
import unittest

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.style_parser import (
    COMPONENT_ARGUMENTS, unknown_arguments,
)


APP = (
    'from apkpy_lib import Screen, Theme, app_bar, image, button, run\n'
    'home = Screen(id="home")\n'
    'app_bar("T", screen=home)\n'
    '%s\n'
    'run(start_screen=home, theme=Theme(mode="dark"))\n'
    'style = """\n"""\n'
)


class TheTableCannotDriftFromTheSignatures(unittest.TestCase):
    """The reason this is a test and not a comment.

    A hand-kept list of argument names is exactly the kind of thing that goes
    stale in silence -- which is the bug it exists to catch. Rebuilding it from
    the live signatures means adding an argument and forgetting the table
    fails here rather than in someone's app.
    """

    def test_every_component_matches_its_signature(self):
        import apkpy_lib

        for name, listed in sorted(COMPONENT_ARGUMENTS.items()):
            factory = getattr(apkpy_lib, name, None)
            self.assertIsNotNone(factory, name)
            real = {
                parameter.name
                for parameter in inspect.signature(factory).parameters.values()
                if parameter.kind in (
                    parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY,
                )
            }
            self.assertEqual(set(listed), real, name)

    def test_the_mini_player_takes_names_not_letters(self):
        # frozenset(('open')) is frozenset({'o','p','e','n'}) -- the missing
        # comma turns one argument into four letters, and every real call
        # then reports as unknown.
        self.assertEqual(set(COMPONENT_ARGUMENTS['mini_player']), {'id', 'open'})
        self.assertFalse([name for name in COMPONENT_ARGUMENTS['mini_player'] if len(name) == 1])


class AnUnknownArgumentIsReported(unittest.TestCase):

    def test_a_near_miss_is_named(self):
        self.assertEqual(
            unknown_arguments('image', ['src', 'blurr']),
            [('blurr', 'blur')],
        )

    def test_a_valid_call_says_nothing(self):
        self.assertEqual(
            unknown_arguments('image', ['src', 'blur', 'tint', 'screen']), [])

    def test_a_name_with_no_near_miss_still_reports(self):
        found = unknown_arguments('button', ['colour'])
        self.assertEqual([name for name, _ in found], ['colour'])

    def test_an_unknown_component_is_left_alone(self):
        # Screen, run and Theme are not in the table; guessing at them would
        # be worse than silence.
        self.assertEqual(unknown_arguments('run', ['start_screen']), [])
        self.assertEqual(unknown_arguments('nao_existe', ['x']), [])


class TheBuildStillHappens(unittest.TestCase):

    def test_a_bad_argument_is_a_warning_not_a_failure(self):
        files = translate_python_to_android(
            APP % 'image("p.png", id="i", screen=home, blurr=8)')
        self.assertNotIn('error.txt', files)
        self.assertIn('res/layout/activity_screen_home.xml', files)

    def test_the_generated_layout_is_the_same_as_without_it(self):
        with_bad = translate_python_to_android(
            APP % 'image("p.png", id="i", screen=home, blurr=8)')
        without = translate_python_to_android(
            APP % 'image("p.png", id="i", screen=home)')
        self.assertEqual(with_bad, without)


class EveryShippedExampleIsClean(unittest.TestCase):
    """Zero false positives, or the warning is worse than the bug."""

    def test_no_example_trips_the_check(self):
        import ast
        import io
        import os

        import _layout
        if _layout.examples() is None:
            self.skipTest('the examples are not in this checkout')
        # The folder used to be looked for from wherever the suite was
        # started, found nothing, and this passed having read no example.
        paths = sorted(str(path) for path in _layout.examples().glob('*.py'))
        self.assertGreater(len(paths), 30)
        offenders = []
        for path in paths:
            tree = ast.parse(io.open(path, encoding='utf-8').read())
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Name):
                    continue
                names = [kw.arg for kw in node.keywords if kw.arg]
                for name, _ in unknown_arguments(node.func.id, names):
                    offenders.append(
                        '%s:%d %s(%s=)' % (os.path.basename(path),
                                           node.lineno, node.func.id, name))
        self.assertEqual(offenders, [])


if __name__ == '__main__':
    unittest.main()
