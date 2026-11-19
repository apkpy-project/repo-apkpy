# -*- coding: utf-8 -*-
"""progress(): a bar with a value, new in 1.15.1.

It is chart(kind="progress"): in the Previewer the function returns that
chart, and the compiler writes the call as that chart before it reads the
module (core/features/progress.py), so the bar is an ApkpyChart on the phone,
drawn from chart_rules.progress_bar like the Previewer's. test_charts.py asks
the Java and the Python the same questions about it.
"""

import unittest

from apkpy_lib import chart_rules as rules
from apkpy_lib.core.compiler import translate_python_to_android

from test_real_screens import Previewed, _build

APP = (
    'home = Screen(id="home")\n'
    'upload = progress(30, id="upload", screen=home)\n'
    'steps = progress(1, max=5, id="steps", screen=home)\n'
    'def more():\n'
    '    upload.set_value(80)\n'
    'button("More", id="more", command=more, screen=home)\n'
)
CSS = 'steps { color: #10B981; height: 14px; }'


class TheRules(unittest.TestCase):

    def test_the_bar(self):
        self.assertEqual(rules.progress_bar(0, 300, 8), (4.0, 0.0))
        self.assertEqual(rules.progress_bar(0.5, 300, 8), (4.0, 150.0))
        # 1% is a dot as wide as the round end, not nothing.
        self.assertEqual(rules.progress_bar(0.004, 300, 8), (4.0, 8.0))
        self.assertEqual(rules.progress_bar(1.0, 300, 8), (4.0, 300.0))
        # border-radius says less than half the height; never more.
        self.assertEqual(rules.progress_bar(0.5, 300, 8, 2), (2.0, 150.0))
        self.assertEqual(rules.progress_bar(0.5, 300, 8, 20), (4.0, 150.0))
        self.assertEqual(rules.DEFAULT_HEIGHT['progress'], 8)


class ThePhone(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = _build(APP, CSS)
        cls.java = ''.join(v for k, v in cls.files.items() if k.endswith('Activity.java'))

    def test_a_chart_of_the_progress_kind(self):
        self.assertIn('cht1.configure("progress", "label", "value", '
                      'android.graphics.Color.parseColor("#6750A4")', self.java)
        self.assertIn('cht1.setRing(Float.parseFloat(String.valueOf(30)), 100.0f, null);', self.java)
        self.assertIn('cht2.configure("progress", "label", "value", '
                      'android.graphics.Color.parseColor("#10B981")', self.java)
        self.assertIn('14.0f', self.java.split('cht2.configure(')[1].split('\n')[0])
        self.assertIn('cht2.setRing(Float.parseFloat(String.valueOf(1)), 5.0f, null);', self.java)

    def test_set_value_moves_it(self):
        self.assertIn('((ApkpyChart) findViewById(R.id.cht1)).setValue(Float.parseFloat(String.valueOf(80)));',
                      self.java)

    def test_the_view_draws_it_and_says_it(self):
        chart = self.files['java/ApkpyChart.java']
        self.assertIn('drawProgress(canvas, width);', chart)
        self.assertIn('setContentDescription(Math.round(ringFraction(ringValue, ringMax) * 100) + "%");',
                      chart)

    def test_an_app_with_its_own_progress_keeps_it(self):
        source = ('from apkpy_lib import *\nhome = Screen(id="home")\n'
                  'def progress(n):\n    return str(n) + "%"\n'
                  'out = label("", id="l", screen=home)\n'
                  'def go():\n    out.set_value(progress(5))\n'
                  'button("Go", command=go, screen=home)\nrun(start_screen=home)\n')
        files = translate_python_to_android(source)
        self.assertNotIn('error.txt', files, files.get('error.txt', '')[:400])
        self.assertNotIn('java/ApkpyChart.java', files)


class ThePreviewer(unittest.TestCase):

    def test_heights_and_set_value(self):
        with Previewed(APP, CSS) as p:
            self.assertEqual(p.widget('upload').winfo_height(), rules.DEFAULT_HEIGHT['progress'])
            self.assertEqual(p.widget('steps').winfo_height(), 14)
            p.ns['upload'].set_value(80)
            p.settle(0.2)
            self.assertEqual(p.ns['upload'].kwargs['value'], 80)


if __name__ == '__main__':
    unittest.main()
