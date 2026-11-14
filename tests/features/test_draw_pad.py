# -*- coding: utf-8 -*-
"""draw_pad(): a box to sign or scribble in with a finger, kept as a PNG.

The Previewer's canvas and ApkpyDrawPad on the phone take their sizes and
colours from ``apkpy_lib/draw_pad_rules.py`` and draw a stroke the same way
(``rules.smooth``: straight to the first middle, a curve through each point).
clear(), is_empty() and save() do the same on both sides, save() under the
name rules of files.write().
"""

import os
import shutil
import tempfile
import unittest

from apkpy_lib import draw_pad_rules as rules
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import draw_pad as draw_pad_feature
from apkpy_lib.diagnostics import ApkpyError

from test_real_screens import Previewed, _build, _layouts

APP = (
    'home = Screen(id="home", scroll=True)\n'
    'SEEN = []\n'
    'def signed():\n'
    '    SEEN.append("stroke")\n'
    'def send():\n'
    '    if pad.is_empty():\n'
    '        toast("Sign first")\n'
    '        return\n'
    '    answer = pad.save("signature.png")\n'
    '    status.set_value(answer)\n'
    'def again():\n'
    '    pad.clear()\n'
    'status = label("", id="status", screen=home)\n'
    'pad = draw_pad(id="signature", hint="Sign here", pen=4, on_change=signed, screen=home)\n'
    'sketch = draw_pad(id="sketch", screen=home)\n'
    'button("Send", id="send", command=send, screen=home)\n'
    'button("Again", id="again", command=again, screen=home)\n'
)
CSS = 'signature { color: #1A237E; background-color: #FFFDE7; height: 160px; border-radius: 8px; }'


class TheSharedRules(unittest.TestCase):

    def test_pen(self):
        self.assertEqual(rules.pen_from(None), rules.PEN)
        self.assertEqual(rules.pen_from(6), 6.0)
        for bad in (0, 100, "3", True):
            with self.assertRaises(ApkpyError) as caught:
                rules.pen_from(bad)
            self.assertEqual(caught.exception.code, rules.CODE)

    def test_colours(self):
        tokens = {'text': '#111111', 'surface': '#FAFAFA', 'border': '#777777',
                  'text_secondary': '#555555'}
        self.assertEqual(rules.colors(tokens, {}),
                         {'ink': '#111111', 'paper': '#FAFAFA', 'border': '#777777', 'hint': '#555555'})
        own = {'color': '#FF0000', 'background-color': 'transparent', 'border-color': 'none'}
        seen = rules.colors(tokens, own)
        self.assertEqual((seen['ink'], seen['paper'], seen['border']), ('#FF0000', None, None))

    def test_sizes(self):
        self.assertEqual(rules.height({}), rules.HEIGHT)
        self.assertEqual(rules.height({'height': '120px'}), 120.0)
        self.assertEqual(rules.radius({'border-radius': '4px'}), 4.0)

    def test_a_stroke_is_smoothed_as_the_phone_draws_it(self):
        self.assertEqual(rules.smooth([(0, 0)]), [(0, 0)])
        self.assertEqual(rules.smooth([(0, 0), (10, 0)]), [(0, 0), (10, 0)])
        line = rules.smooth([(0, 0), (10, 0), (10, 10)])
        self.assertEqual(line[0], (0, 0))
        self.assertEqual(line[1], (5.0, 0.0))            # straight to the first middle
        self.assertEqual(line[-2], (10.0, 5.0))          # the curve ends at the next middle
        self.assertEqual(line[-1], (10, 10))
        self.assertEqual(len(line), 2 + 8 + 1)


class ThePhone(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = _build(APP, CSS)
        cls.java = ''.join(v for k, v in cls.files.items() if k.endswith('Activity.java'))
        cls.layout = _layouts(cls.files)['res/layout/activity_screen_home.xml']

    def test_one_view_each(self):
        self.assertEqual(self.layout.count('<com.apkpy.app.ApkpyDrawPad'), 2)
        self.assertIn('android:id="@+id/dpad1"', self.layout)
        self.assertIn('android:layout_height="160dp"', self.layout)
        self.assertIn('android:layout_height="200dp"', self.layout)

    def test_the_classes_ship_only_when_used(self):
        self.assertIn('java/ApkpyDrawPad.java', self.files)
        self.assertIn('java/ApkpyKitRules.java', self.files)          # save() names files as files.write()
        plain = _build('home = Screen(id="home")\nlabel("x", screen=home)\n')
        self.assertNotIn('java/ApkpyDrawPad.java', plain)

    def test_each_view_is_configured(self):
        line = self.java.split('dpad1.configure(')[1].split('\n')[0]
        self.assertIn('android.graphics.Color.parseColor("#1A237E")', line)
        self.assertIn('android.graphics.Color.parseColor("#FFFDE7")', line)
        self.assertIn('8.0f, 1.0f, 4.0f, 16.0f, String.valueOf("Sign here"));', line)
        self.assertIn('dpad1.setOnChange(() -> pythonCallback_signed());', self.java)
        self.assertNotIn('dpad2.setOnChange', self.java)

    def test_clear_save_and_is_empty(self):
        self.assertIn('((ApkpyDrawPad) findViewById(R.id.dpad1)).clear();', self.java)
        self.assertIn('((ApkpyDrawPad) findViewById(R.id.dpad1)).save(String.valueOf("signature.png"))', self.java)
        self.assertIn('if (((ApkpyDrawPad) findViewById(R.id.dpad1)).isEmpty()) {', self.java)

    def test_on_another_screen_nothing_is_looked_for(self):
        files = _build('home = Screen(id="home")\nother = Screen(id="other")\n'
                       'def wipe():\n    pad.clear()\n    if pad.is_empty():\n        toast("empty")\n'
                       'pad = draw_pad(id="p", screen=home)\n'
                       'button("Wipe", command=wipe, screen=other)\n')
        other = files['java/Screen_otherActivity.java']
        self.assertNotIn('ApkpyDrawPad', other)            # no pad here: no findViewById that gives null
        self.assertIn('"empty"', other)                    # and a pad that is not here is empty

    def test_what_the_build_refuses(self):
        for body in ('draw_pad(pen=0, screen=home)\n',
                     'draw_pad(pen="thick", screen=home)\n',
                     'def f(x):\n    pass\ndraw_pad(on_change=f, screen=home)\n',
                     'pad = draw_pad(screen=home)\ndef f():\n    pad.save()\n'):
            source = ('from apkpy_lib import *\nhome = Screen(id="home")\n' + body +
                      'run(start_screen=home)\n')
            error = translate_python_to_android(source).get('error.txt', '')
            self.assertIn(rules.CODE, error, body)


class ThePreviewer(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        from apkpy_lib import ui
        self._dir = ui.files._dir
        ui.files._dir = lambda: self.folder

    def tearDown(self):
        from apkpy_lib import ui
        ui.files._dir = self._dir
        shutil.rmtree(self.folder, ignore_errors=True)

    def _stroke(self, canvas, points):
        x, y = points[0]
        canvas.event_generate('<ButtonPress-1>', x=x, y=y)
        for x, y in points[1:]:
            canvas.event_generate('<B1-Motion>', x=x, y=y)
        canvas.event_generate('<ButtonRelease-1>', x=x, y=y)

    def test_a_stroke_draws_and_tells(self):
        with Previewed(APP, CSS) as p:
            pad = p.ns['pad']
            canvas = p.widget('pad')
            self.assertEqual(canvas.winfo_height(), 160)
            hints = [i for i in canvas.find_all() if canvas.type(i) == 'text']
            self.assertEqual([canvas.itemcget(i, 'text') for i in hints], ['Sign here'])
            self.assertTrue(pad.is_empty())
            self._stroke(canvas, [(40, 60), (80, 70), (120, 60), (160, 90)])
            p.settle(0.1)
            self.assertFalse(pad.is_empty())
            self.assertEqual(p.ns['SEEN'], ['stroke'])
            self.assertFalse([i for i in canvas.find_all() if canvas.type(i) == 'text'])
            lines = [i for i in canvas.find_all() if canvas.type(i) == 'line']
            self.assertEqual(len(lines), 1)
            self.assertEqual(float(canvas.itemcget(lines[0], 'width')), 4.0)

    def test_save_writes_the_png_and_clear_empties(self):
        from PIL import Image
        with Previewed(APP, CSS) as p:
            pad = p.ns['pad']
            canvas = p.widget('pad')
            self._stroke(canvas, [(20, 80), (200, 80)])
            p.settle(0.1)
            self.assertEqual(pad.save('signature.png'), 'ok')
            image = Image.open(os.path.join(self.folder, 'signature.png')).convert('RGBA')
            self.assertEqual(image.size, (canvas.winfo_width(), 160))
            self.assertEqual(image.getpixel((100, 80))[:3], (0x1A, 0x23, 0x7E))      # the ink
            self.assertEqual(image.getpixel((100, 20))[:3], (0xFF, 0xFD, 0xE7))      # the paper
            self.assertEqual(pad.save('../outside.png'), 'invalid')
            pad.clear()
            p.settle(0.1)
            self.assertTrue(pad.is_empty())
            self.assertEqual(p.ns['SEEN'], ['stroke'])                               # clear() tells nobody

    def test_the_app_saves_from_a_button(self):
        with Previewed(APP, CSS) as p:
            self._stroke(p.widget('pad'), [(30, 50), (90, 120)])
            p.settle(0.1)
            p.ns['send']()
            self.assertEqual(p.ns['status'].get_value(), 'ok')
            self.assertTrue(os.path.isfile(os.path.join(self.folder, 'signature.png')))


class TheJavaShips(unittest.TestCase):

    def test_the_view_class(self):
        source = draw_pad_feature.java_source('com.apkpy.app')
        self.assertIn('public final class ApkpyDrawPad extends View', source)
        self.assertIn('ApkpyKitRules.fileName(given)', source)
        self.assertIn('requestDisallowInterceptTouchEvent(true)', source)
        self.assertIn('onSaveInstanceState', source)


if __name__ == '__main__':
    unittest.main()
