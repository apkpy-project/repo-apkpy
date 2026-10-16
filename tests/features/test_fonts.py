# -*- coding: utf-8 -*-
"""Custom typefaces, and the one thing that keeps them honest.

A font is the last big reason an app built with ApkPy looked like every other
app built with ApkPy. What makes it tractable is that both sides read the same
four-slot table: Tk addresses a family plus `bold` and `italic`, and Android
expresses the same four as fontWeight/fontStyle pairs.

The tests that carry weight here are the arithmetic ones -- which file answers
a request, and what still has to be faked when the app did not supply it.
Getting that wrong means the phone picks a different file than the desktop,
and nobody notices until the APK is installed.
"""

import os
import struct
import tempfile
import unittest

from apkpy_lib import fonts
from apkpy_lib.core.compiler import (
    _generate_font_family_xml,
    translate_python_to_android,
)


def _sfnt(family):
    """The smallest font file that still says what it is called.

    Only the `name` table, because that is all the parser reads. Building it
    here rather than checking in a real font keeps the test self-contained and
    proves the parser walks a real table directory.
    """
    text = family.encode('utf-16-be')
    # format 0, one record, strings start right after the record array
    name_table = struct.pack('>HHH', 0, 1, 6 + 12)
    name_table += struct.pack(
        '>HHHHHH', 3, 1, 0x409, 1, len(text), 0)   # platform 3 = Windows
    name_table += text
    header = struct.pack('>IHHHH', 0x00010000, 1, 16, 0, 0)
    record = b'name' + struct.pack('>III', 0, 12 + 16, len(name_table))
    return header + record + name_table


class SlotTests(unittest.TestCase):
    def test_four_slots_and_no_more(self):
        # A "medium" would render on the phone and not on the desktop, which
        # is the difference this project exists to avoid.
        self.assertEqual(set(fonts.SLOTS), set(fonts.SLOT_ORDER))
        self.assertEqual(len(fonts.SLOT_ORDER), 4)
        with self.assertRaises(ValueError):
            fonts.normalise_files({'regular': 'a.ttf', 'medium': 'b.ttf'})

    def test_empty_slots_are_dropped_and_the_order_is_stable(self):
        files = fonts.normalise_files(
            {'bold': 'b.ttf', 'regular': 'a.ttf', 'italic': None})
        self.assertEqual(list(files), ['regular', 'bold'])

    def test_a_supplied_slot_is_used_and_nothing_is_faked(self):
        self.assertEqual(
            fonts.resolve_slot({'regular', 'bold'}, bold=True),
            ('bold', False, False))

    def test_a_missing_slot_falls_back_and_says_what_to_fake(self):
        # The Previewer and Android both synthesise; what matters is that they
        # synthesise the same thing.
        self.assertEqual(
            fonts.resolve_slot({'regular'}, bold=True),
            ('regular', True, False))
        self.assertEqual(
            fonts.resolve_slot({'regular'}, bold=True, italic=True),
            ('regular', True, True))
        self.assertEqual(
            fonts.resolve_slot({'regular', 'bold'}, bold=True, italic=True),
            ('bold', False, True))

    def test_a_family_with_no_files_answers_nothing(self):
        self.assertEqual(fonts.resolve_slot(set(), bold=True),
                         (None, True, False))


class ResourceNameTests(unittest.TestCase):
    def test_a_family_becomes_a_legal_android_resource(self):
        # Resource names carry no capitals, spaces or dashes.
        self.assertEqual(fonts.resource_name('Tiempos Text'), 'tiempos_text')
        self.assertEqual(fonts.resource_name('Inter-Display'), 'inter_display')

    def test_a_name_that_cannot_start_a_resource_is_prefixed(self):
        self.assertEqual(fonts.resource_name('2Cool'), 'f_2cool')
        self.assertEqual(fonts.resource_name(''), 'apkpy_font')

    def test_a_slot_never_collides_with_its_family(self):
        self.assertNotEqual(fonts.resource_name('Tiempos'),
                            fonts.slot_resource_name('Tiempos', 'regular'))


class NameTableTests(unittest.TestCase):
    def test_a_font_file_is_read_for_the_family_it_calls_itself(self):
        # Tk is asked for a family by name, not by path: a file called
        # Inter-Bold.ttf may introduce itself as "Inter" or as "Inter Bold",
        # and those are different families as far as Tk is concerned.
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'Whatever-Bold.ttf')
            with open(path, 'wb') as handle:
                handle.write(_sfnt('Tiempos Headline'))
            self.assertEqual(fonts.family_name_from_file(path),
                             'Tiempos Headline')

    def test_something_that_is_not_a_font_is_none_rather_than_a_crash(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'not.ttf')
            with open(path, 'wb') as handle:
                handle.write(b'this is not a font')
            self.assertIsNone(fonts.family_name_from_file(path))
        self.assertIsNone(fonts.family_name_from_file('/no/such/file.ttf'))


class FamilyXmlTests(unittest.TestCase):
    def _entry(self, *slots):
        return {'name': 'Tiempos', 'resource': 'tiempos',
                'files': {slot: slot + '.ttf' for slot in slots}}

    def test_every_row_is_written_in_both_namespaces(self):
        # The framework reads android: from API 26; AppCompat reads app: all
        # the way down to the minSdk this project generates.
        xml = _generate_font_family_xml(self._entry('regular', 'bold'))
        self.assertEqual(xml.count('android:font='), 2)
        self.assertEqual(xml.count('app:font='), 2)

    def test_the_weights_and_styles_match_the_slots(self):
        xml = _generate_font_family_xml(
            self._entry('regular', 'bold', 'italic', 'bold_italic'))
        self.assertIn('android:fontWeight="400" android:font="@font/tiempos_regular"', xml)
        self.assertIn('android:fontWeight="700" android:font="@font/tiempos_bold"', xml)
        self.assertIn('android:fontStyle="italic" android:fontWeight="400"', xml)
        self.assertIn('android:fontStyle="italic" android:fontWeight="700"', xml)

    def test_a_family_with_one_file_is_still_a_family(self):
        xml = _generate_font_family_xml(self._entry('regular'))
        self.assertEqual(xml.count('<font '), 1)
        self.assertIn('</font-family>', xml)


class CompilerTests(unittest.TestCase):
    """The compiler only checks the suffix and that the file is there."""

    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.mkdtemp()
        for name in ('Regular.ttf', 'Bold.ttf'):
            with open(os.path.join(cls.folder, name), 'wb') as handle:
                handle.write(_sfnt('Tiempos'))
        cls.app = os.path.join(cls.folder, 'app.py')

    def _build(self, source):
        result = translate_python_to_android(source, source_name=self.app)
        self.assertNotIn('error.txt', result,
                         result.get('error.txt', '')[:400])
        return result

    APP = '''
from apkpy_lib import Screen, Theme, app_bar, font, label, run
font("Tiempos", regular="Regular.ttf", bold="Bold.ttf")
home = Screen(id="home")
app_bar("Settings", screen=home)
label("Hello", id="t", screen=home)
run(start_screen=home, theme=Theme(mode="dark", font_family="Tiempos"))
'''

    def test_the_files_are_copied_into_res_font(self):
        out = self._build(self.APP)
        for slot in ('regular', 'bold'):
            key = 'res/font/tiempos_%s.ttf' % slot
            self.assertIn(key, out)
            self.assertEqual(out[key][0], 'COPY_FILE')
            self.assertTrue(os.path.exists(out[key][1]))
        self.assertIn('res/font/tiempos.xml', out)

    def test_font_family_resolves_to_the_resource(self):
        layout = self._build(self.APP)['res/layout/activity_screen_home.xml']
        self.assertIn('app:fontFamily="@font/tiempos"', layout)
        # android:fontFamily only learned to take @font/ at API 26, and this
        # project generates minSdk 24.
        self.assertNotIn('android:fontFamily="@font/', layout)

    def test_a_generic_family_is_left_alone(self):
        layout = self._build(self.APP.replace(
            'font_family="Tiempos"', 'font_family="serif"'))[
                'res/layout/activity_screen_home.xml']
        self.assertIn('android:fontFamily="serif"', layout)
        self.assertNotIn('app:fontFamily=', layout)

    def test_the_toolbar_title_carries_the_typeface(self):
        # MaterialToolbar draws its own TextView, so there is no view in the
        # layout to put the attribute on -- it goes through a text appearance.
        out = self._build(self.APP)
        self.assertIn('res/values/apkpy_fonts.xml', out)
        self.assertIn('ApkpyFont_tiempos', out['res/values/apkpy_fonts.xml'])
        self.assertIn(
            'app:titleTextAppearance="@style/ApkpyFont_tiempos"',
            out['res/layout/activity_screen_home.xml'])

    def test_an_app_with_no_font_writes_no_font_resources(self):
        out = self._build('''
from apkpy_lib import Screen, label, run
home = Screen(id="home")
label("Hello", id="t", screen=home)
run(start_screen=home)
''')
        self.assertFalse([k for k in out if k.startswith('res/font/')])
        self.assertNotIn('res/values/apkpy_fonts.xml', out)

    def test_a_broken_slot_does_not_take_the_family_down_with_it(self):
        out = self._build(self.APP.replace('bold="Bold.ttf"',
                                           'bold="Missing.ttf"'))
        self.assertIn('res/font/tiempos_regular.ttf', out)
        self.assertNotIn('res/font/tiempos_bold.ttf', out)
        family = out['res/font/tiempos.xml']
        self.assertEqual(family.count('<font '), 1)

    def test_a_web_font_format_is_refused_rather_than_shipped(self):
        # AAPT rejects .woff outright; better to say so at build time.
        out = self._build(self.APP.replace('regular="Regular.ttf"',
                                           'regular="Regular.woff2"'))
        self.assertNotIn('res/font/tiempos_regular.woff2', out)


if __name__ == '__main__':
    unittest.main()
