# -*- coding: utf-8 -*-
"""chart(): bars, a line, a donut and a ring, drawn natively on both runtimes.

A chart is drawn twice -- Pillow in the Previewer, ApkpyChart's Canvas on the
phone -- and the two only agree if every number that decides where an axis
ends, how a value is written or where a slice starts comes from one place:
``apkpy_lib/chart_rules.py``. ApkpyChart writes those functions again in Java;
the last test here lifts them out of the class exactly as it ships, compiles
them and asks both languages the same questions.
"""

import io
import json
import os
import re
import subprocess
import tempfile
import unittest

from apkpy_lib import chart_rules as rules
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import chart as chart_feature

from test_data_rules import TOOLING
from test_real_screens import Previewed, _build, _layouts

MONTHS = ('[{"label": "Jan", "value": 820}, {"label": "Feb", "value": 1140},'
          ' {"label": "Mar", "value": 960}]')
APP = (
    'home = Screen(id="home", scroll=True)\n'
    'MONTHS = ' + MONTHS + '\n'
    'def picked(item):\n'
    '    toast(item["label"])\n'
    'monthly = chart(MONTHS, kind="bar", id="monthly", screen=home, on_click=picked)\n'
    'chart([3, 5, 2], kind="line", fill=True, id="trend", screen=home)\n'
    'split = chart([{"label": "Rent", "value": 900}, {"label": "Food", "value": 300}],\n'
    '              kind="donut", center="$1,200", id="split", screen=home,\n'
    '              on_click=lambda item: toast(item["label"]))\n'
    'budget = chart(kind="ring", value=72, max=100, id="budget", screen=home)\n'
    'def more():\n'
    '    budget.set_value(91)\n'
    '    monthly.set_items([{"label": "Apr", "value": 1300}])\n'
    'button("More", id="more", command=more, screen=home)\n'
)
CSS = 'monthly { color: #3B5BDB; } budget { stroke-width: 10px; }'


class TheSharedRules(unittest.TestCase):

    def test_the_axis(self):
        self.assertEqual(rules.nice_scale(4.2), (6.0, 2.0))
        self.assertEqual(rules.nice_scale(100), (100.0, 25.0))
        self.assertEqual(rules.nice_scale(1284), (1500.0, 500.0))
        self.assertEqual(rules.nice_scale(0.37), (0.4, 0.1))
        self.assertEqual(rules.nice_scale(0), (4.0, 1.0))

    def test_numbers(self):
        cases = {12: '12', 2.5: '2.5', 12500: '12.5K', 1234567: '1.2M',
                 -3.25: '-3.3', 0.04: '0.04', 0.005: '0.01', -0.001: '0', 1500: '1.5K'}
        for value, text in cases.items():
            self.assertEqual(rules.format_number(value), text, value)

    def test_labels_that_do_not_fit_are_thinned(self):
        self.assertEqual(rules.label_step(6, 330), 1)
        self.assertEqual(rules.label_step(30, 330), 4)

    def test_slices_go_round_clockwise_from_the_top(self):
        arcs = rules.slices([3, 1, 0, 2])
        self.assertAlmostEqual(arcs[0][0], -89.0)
        self.assertEqual(arcs[2][1], 0.0)                    # a zero draws nothing
        self.assertAlmostEqual(sum(sweep for _s, sweep in arcs), 360.0 - 3 * 2.0)
        self.assertEqual(rules.slices([0, 0]), [(0.0, 0.0), (0.0, 0.0)])

    def test_a_ring(self):
        self.assertEqual(rules.ring_fraction(150, 100), 1.0)
        self.assertEqual(rules.ring_center_text(72, 100), '72%')
        self.assertEqual(rules.ring_center_text(45, 60, '45 min'), '45 min')

    def test_items(self):
        items = rules.items_from([{'day': 'Mon', 'n': '4'}, 7, {'day': 'Tue', 'n': 'x'}],
                                 x='day', y='n')
        self.assertEqual(items, [('Mon', 4.0, None), ('', 7.0, None), ('Tue', 0.0, None)])

    def test_an_unknown_kind_is_refused(self):
        with self.assertRaises(ValueError):
            rules.normalize_kind('pie')


class ThePhone(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = _build(APP, CSS)
        cls.java = ''.join(v for k, v in cls.files.items() if k.endswith('Activity.java'))
        cls.layout = _layouts(cls.files)['res/layout/activity_screen_home.xml']

    def test_a_view_per_chart(self):
        self.assertEqual(self.layout.count('<com.apkpy.app.ApkpyChart'), 4)

    def test_the_class_ships_only_with_a_chart(self):
        self.assertIn('java/ApkpyChart.java', self.files)
        self.assertNotIn('java/ApkpyChart.java',
                         _build('home = Screen(id="home")\nlabel("x", screen=home)\n'))

    def test_the_activity_configures_each_chart(self):
        java = self.java
        self.assertIn('cht1.configure("bar", "label", "value", android.graphics.Color.parseColor("#3B5BDB")', java)
        self.assertIn('cht1.setItems("[{\\"label\\": \\"Jan\\", \\"value\\": 820}', java)
        self.assertIn('cht2.configure("line"', java)
        self.assertIn('true);', java.split('cht2.configure(')[1].split('\n')[0])   # fill
        self.assertIn('cht3.setCenter("$1,200");', java)
        self.assertIn('cht4.setRing(Float.parseFloat(String.valueOf(72)), 100.0f, null);', java)
        self.assertIn('10.0f', java.split('cht4.configure(')[1].split('\n')[0])  # stroke-width

    def test_a_tap_hands_over_the_item(self):
        self.assertIn('cht1.setOnItemClick(_item -> pythonCallback_picked(_item));', self.java)
        self.assertIn('private void pythonCallback_picked(String item)', self.java)
        self.assertRegex(self.java, r'cht3\.setOnItemClick\(_item -> pythonCallback_\w+\(_item\)\);')

    def test_set_value_and_set_items(self):
        self.assertIn('((ApkpyChart) findViewById(R.id.cht4)).setValue(Float.parseFloat(String.valueOf(91)));',
                      self.java)
        self.assertIn('((ApkpyChart) findViewById(R.id.cht1)).setItems("[{\\"label\\": \\"Apr\\"', self.java)
        # A chart is never treated as a TextView: that cast compiled and threw.
        self.assertNotRegex(self.java, r'TextView\)\s*findViewById\(R\.id\.cht\d')
        self.assertNotIn('_apkpyRememberText(R.id.cht', self.java)

    def test_items_from_a_variable_arrive_as_json(self):
        files = _build('home = Screen(id="home")\n'
                       'rows = db.query("SELECT name AS label, total AS value FROM t")\n'
                       'chart(rows, kind="bar", id="c", screen=home)\n')
        java = ''.join(v for k, v in files.items() if k.endswith('Activity.java'))
        self.assertIn('cht1.setItems(String.valueOf(', java)

    def test_an_unknown_kind_stops_the_build(self):
        source = ('from apkpy_lib import *\nhome = Screen(id="home")\n'
                  'chart([1, 2], kind="pie", screen=home)\nrun(start_screen=home)\n')
        error = translate_python_to_android(source).get('error.txt', '')
        self.assertIn('U2041', error)


class ThePreviewer(unittest.TestCase):

    def test_heights_and_the_donut_legend(self):
        with Previewed(APP, CSS) as p:
            self.assertEqual(p.widget('monthly').winfo_height(), rules.DEFAULT_HEIGHT['bar'])
            legend = rules.legend_height([('Rent', 900, None), ('Food', 300, None)])
            self.assertEqual(p.widget('split').winfo_height(), rules.DEFAULT_HEIGHT['donut'] + legend)

    def test_set_items_redraws(self):
        with Previewed(APP, CSS) as p:
            canvas = p.widget('monthly')
            p.ns['monthly'].set_items([{'label': 'Apr', 'value': 1300}, {'label': 'May', 'value': 10}])
            p.settle(0.3)
            texts = [canvas.itemcget(i, 'text') for i in canvas.find_all() if canvas.type(i) == 'text']
            self.assertIn('Apr', texts)
            self.assertIn('1.5K', texts)          # the axis follows the data
            self.assertNotIn('Jan', texts)

    def test_a_tap_on_a_bar_gives_its_item(self):
        seen = []
        app = APP.replace('def picked(item):\n    toast(item["label"])\n',
                          'def picked(item):\n    SEEN.append(item)\n')
        with Previewed('SEEN = []\n' + app, CSS) as p:
            canvas = p.widget('monthly')
            width = canvas.winfo_width()
            left, plot_w = rules.AXIS_WIDTH, width - rules.AXIS_WIDTH - 8
            x = left + plot_w / 3.0 * 1.5                  # the middle of the second bar
            canvas.event_generate('<Button-1>', x=int(x), y=150)
            p.settle(0.2)
            seen = p.ns['SEEN']
        self.assertEqual(seen, [{'label': 'Feb', 'value': 1140}])

    def test_a_ring_moves(self):
        with Previewed(APP, CSS) as p:
            canvas = p.widget('budget')
            texts = lambda: [canvas.itemcget(i, 'text') for i in canvas.find_all()
                             if canvas.type(i) == 'text']
            self.assertIn('72%', texts())
            p.ns['budget'].set_value(91)
            p.settle(0.2)
            self.assertIn('91%', texts())


@unittest.skipUnless(TOOLING, "no JDK on this machine")
class JavaAnswersTheSameWay(unittest.TestCase):
    """The static rules of ApkpyChart, lifted from the class as it ships."""

    def _harness(self):
        java = chart_feature.generate_java('x')
        constants = [line.strip() for line in java.splitlines()
                     if re.match(r'\s*static final (int|float) [A-Z_]+ =', line)]
        start = java.index('    static double[] niceScale(')
        end = java.index('    static String sliceColor(')
        methods = java[start:end]
        return ('import java.util.Locale;\n'
                'public class ChartRulesHarness {\n'
                + '\n'.join('    ' + c for c in constants) + '\n'
                + methods +
                '    public static void main(String[] args) {\n'
                '        double[] maxes = {4.2, 100, 1284, 0.37, 0, 7, 12500, 1, 3.5};\n'
                '        for (double m : maxes) { double[] s = niceScale(m);\n'
                '            System.out.println("scale|" + m + "|" + s[0] + "," + s[1]); }\n'
                '        double[] nums = {12, 2.5, 12500, 1234567, -3.25, 0.04, 999.95, 0.35, 0.005, -0.001, 1500, 7.05};\n'
                '        for (double n : nums) System.out.println("format|" + n + "|" + formatNumber(n));\n'
                '        System.out.println("step|6/330|" + labelStep(6, 330f));\n'
                '        System.out.println("step|30/330|" + labelStep(30, 330f));\n'
                '        float[][] arcs = slices(new double[]{3, 1, 0, 2});\n'
                '        for (int i = 0; i < arcs.length; i++) System.out.println("slice|" + i + "|" + arcs[i][0] + "," + arcs[i][1]);\n'
                '    }\n}\n')

    def test_both_languages_agree(self):
        javac, java_bin, _jar = TOOLING
        work = tempfile.mkdtemp(prefix='apkpy-chart-')
        source = os.path.join(work, 'ChartRulesHarness.java')
        with io.open(source, 'w', encoding='utf-8') as handle:
            handle.write(self._harness())
        built = subprocess.run([javac, '-encoding', 'UTF-8', '-d', work, source],
                               capture_output=True, text=True)
        self.assertEqual(0, built.returncode, built.stdout + built.stderr)
        ran = subprocess.run([java_bin, '-cp', work, 'ChartRulesHarness'],
                             capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(0, ran.returncode, ran.stdout + ran.stderr)
        answers = dict(((kind, key), value) for kind, key, value in
                       (line.split('|') for line in ran.stdout.splitlines()))
        for m in (4.2, 100, 1284, 0.37, 0, 7, 12500, 1, 3.5):
            top, step = rules.nice_scale(m)
            java_top, java_step = (float(v) for v in answers[('scale', repr(float(m)))].split(','))
            self.assertAlmostEqual(top, java_top, places=9, msg=m)
            self.assertAlmostEqual(step, java_step, places=9, msg=m)
        for n in (12, 2.5, 12500, 1234567, -3.25, 0.04, 999.95, 0.35, 0.005, -0.001, 1500, 7.05):
            self.assertEqual(rules.format_number(n), answers[('format', repr(float(n)))], n)
        self.assertEqual(str(rules.label_step(6, 330)), answers[('step', '6/330')])
        self.assertEqual(str(rules.label_step(30, 330)), answers[('step', '30/330')])
        for index, (start, sweep) in enumerate(rules.slices([3, 1, 0, 2])):
            java_start, java_sweep = (float(v) for v in answers[('slice', str(index))].split(','))
            self.assertAlmostEqual(start, java_start, places=3)
            self.assertAlmostEqual(sweep, java_sweep, places=3)


if __name__ == '__main__':
    unittest.main()
