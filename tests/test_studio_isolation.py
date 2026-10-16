# -*- coding: utf-8 -*-
"""Two projects open in one process must not contaminate each other.

A desktop run compiles one file and exits, so the compiler was free to hand
the theme, the asset folder and the font registry to its generators through
module globals.  ApkPy Studio keeps the interpreter alive and switches between
projects, which turns those globals into shared state: the second project's
theme was reaching the first project's APK, and its artwork with it.

``project_root`` has the same shape of problem from the other end.  Studio
writes the editor buffer to a cache file, so the folder the source sits in is
not the folder the artwork sits in, and the parameter that says so was being
stored and never read.
"""

import os
import shutil
import tempfile
import unittest

from apkpy_lib.core import compiler as _compiler
from apkpy_lib.core.app_ir import compile_to_ir

SQUARE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
          '<path d="M2 2 H22 V22 H2 Z"/></svg>')
TRIANGLE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            '<path d="M12 2 L22 22 L2 22 Z"/></svg>')


def _source(mode='dark', primary='#FF0000', icon=None):
    button = ('button("Go", id="b", screen=home)' if icon is None else
              'button("Go", id="b", icon="%s", screen=home)' % icon)
    return (
        'from apkpy_lib import Screen, Theme, app_bar, button, run\n'
        'home = Screen(id="home")\n'
        'app_bar("T", screen=home)\n'
        + button + '\n'
        'run(start_screen=home, theme=Theme(mode="%s", primary="%s"))\n'
        % (mode, primary) +
        'style = """\n"""\n'
    )


def _icon_path(files):
    for name, value in files.items():
        if (name.startswith('res/drawable/') and isinstance(value, str)
                and 'pathData' in value):
            return value.split('pathData="')[1].split('"')[0]
    return None


class OneProjectDoesNotBuildWithAnothersTheme(unittest.TestCase):

    def test_building_after_a_second_compile_keeps_the_first_theme(self):
        red = _source(primary='#FF0000')
        green = _source(mode='light', primary='#00FF00')

        alone = compile_to_ir(red, source_name='a.py').generate_android_files(
            package='com.x.a')

        held = compile_to_ir(red, source_name='a.py')
        compile_to_ir(green, source_name='b.py')      # the other project
        after = held.generate_android_files(package='com.x.a')

        self.assertEqual(alone, after)

    def test_the_theme_colour_itself_is_the_first_projects(self):
        held = compile_to_ir(_source(primary='#FF0000'), source_name='a.py')
        compile_to_ir(_source(mode='light', primary='#00FF00'),
                      source_name='b.py')
        theme = held.generate_android_files(
            package='com.x.a')['res/values/apkpy_theme.xml']
        self.assertIn('#FF0000', theme)
        self.assertNotIn('#00FF00', theme)


class ArtworkComesFromTheProjectBeingBuilt(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='apkpy-studio-')
        self.a = os.path.join(self.root, 'projA')
        self.b = os.path.join(self.root, 'projB')
        os.makedirs(self.a)
        os.makedirs(self.b)
        with open(os.path.join(self.a, 'logo.svg'), 'w') as handle:
            handle.write(SQUARE)
        with open(os.path.join(self.b, 'logo.svg'), 'w') as handle:
            handle.write(TRIANGLE)
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_a_second_project_does_not_replace_the_first_ones_svg(self):
        source = _source(icon='logo.svg')
        alone = compile_to_ir(
            source, source_name=os.path.join(self.a, 'app.py'),
        ).generate_android_files(package='com.x.a')

        held = compile_to_ir(source, source_name=os.path.join(self.a, 'app.py'))
        compile_to_ir(source, source_name=os.path.join(self.b, 'app.py'))
        after = held.generate_android_files(package='com.x.a')

        self.assertEqual(_icon_path(alone), _icon_path(after))
        self.assertIsNotNone(_icon_path(alone))


class ProjectRootSaysWhereTheArtworkLives(unittest.TestCase):
    """Studio compiles a cache file, so the source folder is not the project."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='apkpy-root-')
        with open(os.path.join(self.root, 'logo.svg'), 'w') as handle:
            handle.write(SQUARE)
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_the_asset_folder_follows_project_root(self):
        compile_to_ir(
            _source(icon='logo.svg'),
            source_name='writehere.py',        # a bare name, as Studio sends
            project_root=self.root,
        )
        self.assertEqual(
            os.path.normcase(_compiler._ASSET_BASE_DIR[0]),
            os.path.normcase(self.root),
        )

    def test_without_project_root_the_source_folder_still_wins(self):
        compile_to_ir(
            _source(), source_name=os.path.join(self.root, 'app.py'),
        )
        self.assertEqual(
            os.path.normcase(_compiler._ASSET_BASE_DIR[0]),
            os.path.normcase(self.root),
        )


if __name__ == '__main__':
    unittest.main()
