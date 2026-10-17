# -*- coding: utf-8 -*-
"""chips() and segmented(): options that stay selected, on both runtimes.

The Previewer's canvas and ApkpyChoice on the phone only agree if what a tap
selects, where a chip wraps and how the width is shared come from one place:
``apkpy_lib/choice_rules.py``. ApkpyChoice writes those functions again in
Java; the last test lifts them out of the class as it ships, compiles them
and asks both languages the same questions.
"""

import io
import json
import os
import re
import subprocess
import tempfile
import unittest

from apkpy_lib import choice_rules as rules
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import choice as choice_feature
from apkpy_lib.diagnostics import ApkpyError

from test_data_rules import TOOLING
from test_real_screens import Previewed, _build, _layouts

APP = (
    'home = Screen(id="home", scroll=True)\n'
    'SEEN = []\n'
    'GENRES = ["Pop", "Rock", "Jazz"]\n'
    'def show(choice):\n'
    '    SEEN.append(choice)\n'
    'def retag(selected):\n'
    '    SEEN.append(selected)\n'
    '    if "Kotlin" in selected:\n'
    '        toast("Kotlin")\n'
    'filters = chips(["All", "Unread", "Starred"], selected="All", on_change=show,\n'
    '                id="filters", screen=home)\n'
    'langs = chips(["Python", "Kotlin", "Java"], multiple=True, selected=["Python"],\n'
    '              icons=["code", None, None], on_change=retag, id="langs", screen=home)\n'
    'genres = chips(GENRES, id="genres", screen=home)\n'
    'period = segmented(["Day", "Week", "Month"], selected="Week", id="period",\n'
    '                   on_change=lambda p: SEEN.append(p), screen=home)\n'
    'def reset():\n'
    '    period.set_value("Day")\n'
    '    now = filters.get_value()\n'
    '    toast(now)\n'
    'button("Reset", id="reset", command=reset, screen=home)\n'
)
CSS = 'period { indicator-color: #CDE8D5; active-color: #0B3D1E; }'


def _refused(call):
    with the_error() as seen:
        call()
    return seen


class the_error:
    def __enter__(self):
        return self

    def __exit__(self, kind, error, _tb):
        if kind is None:
            raise AssertionError('nothing was refused')
        if not issubclass(kind, ApkpyError):
            return False
        self.error = error
        return True


class TheSharedRules(unittest.TestCase):

    def test_options_are_words_each_once(self):
        self.assertEqual(rules.options_from('chips', ['A', 2]), ['A', '2'])
        for bad in (['A', 'A'], ['A', '  '], [], 'A|B', [['A']]):
            with self.assertRaises(ApkpyError) as caught:
                rules.options_from('chips', bad)
            self.assertEqual(caught.exception.code, 'U2043')

    def test_a_segmented_button_has_two_to_five(self):
        rules.options_from('segmented', ['A', 'B'])
        rules.options_from('segmented', list('ABCDE'))
        for bad in (['A'], list('ABCDEF')):
            with self.assertRaises(ApkpyError):
                rules.options_from('segmented', bad)

    def test_what_starts_selected(self):
        options = ['Day', 'Week', 'Month']
        self.assertEqual(rules.initial('segmented', options, None, False), ['Day'])
        self.assertEqual(rules.initial('chips', options, None, False), [])
        self.assertEqual(rules.initial('chips', options, 'Week', False), ['Week'])
        self.assertEqual(rules.initial('chips', options, ['Month', 'Day'], True),
                         ['Day', 'Month'])                  # in the options' order
        self.assertEqual(rules.initial('segmented', options, None, True), [])
        with self.assertRaises(ApkpyError):
            rules.initial('chips', options, 'Year', False)
        with self.assertRaises(ApkpyError):
            rules.initial('chips', options, ['Day'], False)  # a list needs multiple

    def test_a_tap(self):
        options = ['A', 'B', 'C']
        self.assertEqual(rules.tap('chips', options, ['A'], 'B', False), ['B'])
        self.assertEqual(rules.tap('chips', options, ['A'], 'A', False), [])
        self.assertEqual(rules.tap('segmented', options, ['A'], 'A', False), ['A'])
        self.assertEqual(rules.tap('segmented', options, [], 'C', True), ['C'])
        self.assertEqual(rules.tap('chips', options, ['C'], 'A', True), ['A', 'C'])
        self.assertEqual(rules.tap('chips', options, ['A', 'C'], 'A', True), ['C'])
        self.assertEqual(rules.tap('chips', options, ['A'], 'Z', False), ['A'])

    def test_required_keeps_one(self):
        options = ['All', 'Unread', 'Groups']
        self.assertTrue(rules.keeps_one('chips', False, True))
        self.assertTrue(rules.keeps_one('segmented', False))
        self.assertFalse(rules.keeps_one('segmented', True))
        self.assertFalse(rules.keeps_one('chips', False))
        # Nothing named: the first starts selected.
        self.assertEqual(rules.initial('chips', options, None, False, required=True), ['All'])
        self.assertEqual(rules.initial('chips', options, None, True, required=True), ['All'])
        self.assertEqual(rules.initial('chips', options, [], True, required=True), ['All'])
        self.assertEqual(rules.initial('chips', options, 'Groups', False, required=True), ['Groups'])
        # A tap on the selected one changes nothing; another still moves it.
        self.assertEqual(rules.tap('chips', options, ['Groups'], 'Groups', False, True), ['Groups'])
        self.assertEqual(rules.tap('chips', options, ['Groups'], 'All', False, True), ['All'])
        # With multiple, the last one on stays on; the others still turn off.
        self.assertEqual(rules.tap('chips', options, ['All'], 'All', True, True), ['All'])
        self.assertEqual(rules.tap('chips', options, ['All', 'Groups'], 'All', True, True), ['Groups'])
        # A multiple segmented button may be emptied unless required.
        self.assertEqual(rules.tap('segmented', options, ['All'], 'All', True), [])
        self.assertEqual(rules.tap('segmented', options, ['All'], 'All', True, True), ['All'])
        # set_value that selects nothing leaves it as it was.
        self.assertEqual(rules.from_value('chips', options, ['Unread'], 'Nope', False, True), ['Unread'])
        self.assertEqual(rules.from_value('chips', options, ['Unread'], [], True, True), ['Unread'])
        self.assertEqual(rules.from_value('chips', options, ['Unread'], ['Groups'], True, True), ['Groups'])

    def test_values(self):
        self.assertEqual(rules.value_of(['A'], False), 'A')
        self.assertEqual(rules.value_of([], False), '')
        self.assertEqual(rules.value_of(['A', 'B'], True), ['A', 'B'])
        self.assertEqual(rules.encode(['A', 'B'], True), '["A", "B"]')
        options = ['A', 'B', 'C']
        self.assertEqual(rules.from_value('segmented', options, ['A'], 'Z', False), ['A'])
        self.assertEqual(rules.from_value('chips', options, ['A'], 'Z', False), [])
        self.assertEqual(rules.from_value('chips', options, [], 'B', False), ['B'])
        self.assertEqual(rules.from_value('chips', options, [], ['C', 'A'], True), ['A', 'C'])
        self.assertEqual(rules.from_value('chips', options, [], '["B"]', True), ['B'])
        self.assertEqual(rules.from_value('chips', options, [], 'C', True), ['C'])

    def test_chips_wrap(self):
        self.assertEqual(rules.flow([100, 100, 100], 250), [(0, 0), (108, 0), (0, 1)])
        self.assertEqual(rules.flow([300, 50], 250), [(0, 0), (0, 1)])
        self.assertEqual(rules.lines_of(rules.flow([300, 50], 250)), 2)
        self.assertEqual(rules.chip_width(40, False), 16 + 40 + 16)
        self.assertEqual(rules.chip_width(40, True), 8 + 18 + 8 + 40 + 16)

    def test_segments_share_the_width(self):
        self.assertEqual(rules.segment_edges(3, 100), [0, 33, 66, 100])
        self.assertEqual(rules.segment_edges(2, 387), [0, 193, 387])

    def test_colours(self):
        tokens = {'border_subtle': '#CCC', 'border': '#777', 'text_secondary': '#444',
                  'text': '#111', 'primary': '#60A', 'nav_indicator': '#EEDDFF'}
        chips = rules.colors('chips', tokens)
        self.assertEqual((chips['border'], chips['text'], chips['icon']), ('#CCC', '#444', '#60A'))
        self.assertEqual((chips['active_fill'], chips['active_text']), ('#EEDDFF', '#111'))
        self.assertIsNone(chips['fill'])
        segmented = rules.colors('segmented', tokens, {'indicator-color': '#0F0',
                                                       'background-color': 'transparent'})
        self.assertEqual((segmented['border'], segmented['active_fill']), ('#777', '#0F0'))
        self.assertIsNone(segmented['fill'])
        self.assertEqual(rules.colors('chips', {})['active_fill'], '#E8DEF8')

    def test_sizes(self):
        self.assertEqual(rules.vertical_inset('chips'), 8)
        self.assertEqual(rules.vertical_inset('segmented'), 4)
        self.assertEqual(rules.radius('chips'), 8.0)
        self.assertEqual(rules.radius('segmented'), 20.0)
        self.assertEqual(rules.radius('chips', {'border-radius': '16px'}), 16.0)


class ThePhone(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = _build(APP, CSS)
        cls.java = ''.join(v for k, v in cls.files.items() if k.endswith('Activity.java'))
        cls.layout = _layouts(cls.files)['res/layout/activity_screen_home.xml']

    def test_one_view_each(self):
        self.assertEqual(self.layout.count('<com.apkpy.app.ApkpyChoice'), 4)
        for n in range(1, 5):
            self.assertIn('android:id="@+id/chc%d"' % n, self.layout)

    def test_the_class_ships_only_when_used(self):
        self.assertIn('java/ApkpyChoice.java', self.files)
        self.assertNotIn('java/ApkpyChoice.java',
                         _build('home = Screen(id="home")\nlabel("x", screen=home)\n'))

    def test_each_view_is_configured(self):
        line = self.java.split('chc1.configure(')[1].split('\n')[0]
        self.assertTrue(line.startswith('false, false, false, "[\\"All\\", \\"Unread\\", \\"Starred\\"]"'))
        self.assertTrue(line.endswith(', "[\\"All\\"]");'))
        langs = self.java.split('chc2.configure(')[1].split('\n')[0]
        self.assertIn('false, true, ', langs)
        self.assertRegex(langs, r'new int\[\]\{R\.drawable\.ic_choice_home_\d+, 0, 0\}')
        self.assertIn('R.drawable.ic_choice_check', langs)
        genres = self.java.split('chc3.configure(')[1].split('\n')[0]
        self.assertIn('"[\\"Pop\\", \\"Rock\\", \\"Jazz\\"]"', genres)     # a list by name
        period = self.java.split('chc4.configure(')[1].split('\n')[0]
        self.assertTrue(period.startswith('true, false, '))
        self.assertIn('android.graphics.Color.parseColor("#CDE8D5")', period)
        self.assertIn('20.0f, 14.0f', period)
        self.assertIn('res/drawable/ic_choice_check.xml', self.files)

    def test_on_change(self):
        self.assertIn('chc1.setOnChange(_value -> pythonCallback_show(_value));', self.java)
        self.assertIn('chc2.setOnChange(_value -> pythonCallback_retag(_value));', self.java)
        self.assertRegex(self.java, r'chc4\.setOnChange\(_value -> pythonCallback_\w+_change\(_value\)\);')
        self.assertNotIn('chc3.setOnChange', self.java)

    def test_a_list_is_asked_as_a_list(self):
        self.assertIn('_apkpyListHas(String.valueOf(selected), String.valueOf("Kotlin"))', self.java)
        self.assertNotIn('String.valueOf(selected).contains(', self.java)

    def test_get_and_set_value(self):
        self.assertIn('((ApkpyChoice) findViewById(R.id.chc4)).setValue(String.valueOf("Day"));',
                      self.java)
        self.assertIn('((ApkpyChoice) findViewById(R.id.chc1)).getValue()', self.java)
        self.assertNotIn('_apkpyRememberText(R.id.chc', self.java)
        self.assertNotRegex(self.java, r'TextView\)\s*findViewById\(R\.id\.chc\d')

    def test_selected_known_only_at_run_time(self):
        files = _build('home = Screen(id="home")\n'
                       'last = storage.get("period", "Week")\n'
                       'segmented(["Day", "Week"], selected=last, id="p", screen=home)\n')
        java = ''.join(v for k, v in files.items() if k.endswith('Activity.java'))
        self.assertIn('"[\\"Day\\"]");', java)                 # the first, until then
        self.assertIn('chc1.setValue(String.valueOf(', java)

    def test_required_reaches_the_view(self):
        files = _build('home = Screen(id="home")\n'
                       'chips(["All", "Unread"], required=True, id="f", screen=home)\n')
        java = ''.join(v for k, v in files.items() if k.endswith('Activity.java'))
        line = java.split('chc1.configure(')[1].split('\n')[0]
        self.assertTrue(line.startswith('false, false, true, '))
        self.assertTrue(line.endswith(', "[\\"All\\"]");'))      # the first starts selected

    def test_no_check_and_no_border(self):
        files = _build('home = Screen(id="home")\n'
                       'chips(["All", "Music"], selected="All", check=False, id="spot",'
                       ' screen=home)\n',
                       'spot { border-color: transparent; background-color: #2A2A2A; }')
        java = ''.join(v for k, v in files.items() if k.endswith('Activity.java'))
        line = java.split('chc1.configure(')[1].split('\n')[0]
        self.assertIn('new int[]{0, 0}, 0, android.graphics.Color.parseColor("#2A2A2A"), '
                      'android.graphics.Color.TRANSPARENT, ', line)
        self.assertEqual(rules.leading_icon('star', True, check=False), 'star')
        self.assertEqual(rules.leading_icon(None, True), rules.CHECK_ICON)

    def test_a_filter_walks_a_list_from_the_top_of_the_file(self):
        # The loop over MAIL, inside the function a chip calls, named MAIL as
        # if Java had a field of that name: javac stopped with cannot find
        # symbol. It walks the literal now, as `x in MAIL` already did.
        files = _build('home = Screen(id="home")\n'
                       'MAIL = [{"id": "a", "unread": "yes"}, {"id": "b", "unread": ""}]\n'
                       'GONE = []\n'
                       'def row(r):\n'
                       '    label("{id}", id="t", parent=r)\n'
                       'def pick(kind):\n'
                       '    shown = []\n'
                       '    for mail in MAIL:\n'
                       '        if mail["id"] in GONE:\n'
                       '            continue\n'
                       '        if kind == "Unread" and mail["unread"] != "yes":\n'
                       '            continue\n'
                       '        shown.append(mail)\n'
                       '    box.set_items(shown)\n'
                       'chips(["All", "Unread"], on_change=pick, id="f", screen=home)\n'
                       'box = virtual_collection(MAIL, row=row, id="box", screen=home)\n')
        java = ''.join(v for k, v in files.items() if k.endswith('Activity.java'))
        method = java.split('private void pythonCallback_pick(')[1].split('\n    }\n')[0]
        self.assertNotIn('String.valueOf(MAIL)', method)
        self.assertIn('_apkpyJsonObj("id", "a"', method)
        self.assertIn('continue;', method)

    def test_the_audit_reads_both_states(self):
        import contextlib
        import io as _io
        source = ('from apkpy_lib import *\nhome = Screen(id="home")\n'
                  'chips(["A", "B"], id="pale", screen=home)\n'
                  'style = """pale { color: #BBBBBB; active-color: #FFFFFF; }"""\n'
                  'run(start_screen=home)\n')
        buffer = _io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            translate_python_to_android(source)
        said = buffer.getvalue()
        self.assertIn('U2035', said)
        self.assertIn('home.pale (chips): unselected text is', said)
        self.assertIn('home.pale (chips): selected text is', said)
        buffer = _io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            translate_python_to_android(source.replace(
                'pale { color: #BBBBBB; active-color: #FFFFFF; }', ''))
        self.assertNotIn('(chips)', buffer.getvalue())

    def test_what_the_build_refuses(self):
        for body in ('opts = storage.get("o")\nchips(opts, screen=home)\n',
                     'segmented(["Only"], screen=home)\n',
                     'chips(["A", "B"], selected="C", screen=home)\n',
                     'chips(["A", "B"], icons=["x"], screen=home)\n'):
            source = ('from apkpy_lib import *\nhome = Screen(id="home")\n' + body +
                      'run(start_screen=home)\n')
            error = translate_python_to_android(source).get('error.txt', '')
            self.assertIn('U2043', error, body)


class ThePreviewer(unittest.TestCase):

    def _hit(self, p, name, option):
        canvas = p.widget(name)
        for item in canvas.find_all():
            if canvas.type(item) == 'text' and canvas.itemcget(item, 'text') == option:
                x, y = canvas.coords(item)[:2]
                canvas.event_generate('<Button-1>', x=int(x) + 4, y=int(y))
                p.settle(0.15)
                return
        raise AssertionError('no %r on %s' % (option, name))

    def test_a_tap_selects_and_tells(self):
        with Previewed(APP, CSS) as p:
            self._hit(p, 'filters', 'Unread')
            self.assertEqual(p.ns['filters'].get_value(), 'Unread')
            self._hit(p, 'filters', 'Unread')                  # again: cleared
            self.assertEqual(p.ns['filters'].get_value(), '')
            self._hit(p, 'langs', 'Java')
            self._hit(p, 'period', 'Week')                     # already on: nothing
            self._hit(p, 'period', 'Month')
            self.assertEqual(p.ns['SEEN'], ['Unread', '', ['Python', 'Java'], 'Month'])

    def test_required_in_the_previewer(self):
        app = ('home = Screen(id="home")\nSEEN = []\n'
               'filters = chips(["All", "Unread"], required=True, id="filters",'
               ' on_change=lambda v: SEEN.append(v), screen=home)\n')
        with Previewed(app, '') as p:
            self.assertEqual(p.ns['filters'].get_value(), 'All')
            self._hit(p, 'filters', 'All')                     # stays
            self._hit(p, 'filters', 'Unread')
            self._hit(p, 'filters', 'Unread')                  # stays
            self.assertEqual(p.ns['filters'].get_value(), 'Unread')
            self.assertEqual(p.ns['SEEN'], ['Unread'])

    def test_set_value_does_not_call_on_change(self):
        with Previewed(APP, CSS) as p:
            p.ns['period'].set_value('Day')
            p.ns['langs'].set_value(['Java', 'Kotlin'])
            p.settle(0.1)
            self.assertEqual(p.ns['period'].get_value(), 'Day')
            self.assertEqual(p.ns['langs'].get_value(), ['Kotlin', 'Java'])
            self.assertEqual(p.ns['SEEN'], [])

    def test_heights(self):
        with Previewed(APP, CSS) as p:
            self.assertEqual(p.widget('period').winfo_height(), rules.TOUCH)
            self.assertEqual(p.widget('filters').winfo_height(), rules.TOUCH)
            many = ('home = Screen(id="home")\n'
                    'tags = chips(["Python", "Android", "Kotlin", "Java", "Rust", "Swift",'
                    ' "Dart", "Go"], id="tags", screen=home)\n')
        with Previewed(many, '') as p:
            self.assertEqual(p.widget('tags').winfo_height(), 2 * rules.TOUCH)

    def test_the_selected_chip_shows_a_check(self):
        with Previewed(APP, CSS) as p:
            canvas = p.widget('filters')
            images = [i for i in canvas.find_all() if canvas.type(i) == 'image']
            # The selected chip's shape and its check; the others are shapes.
            self.assertGreaterEqual(len(images), 4)


@unittest.skipUnless(TOOLING, "no JDK on this machine")
class JavaAnswersTheSameWay(unittest.TestCase):
    """The static rules of ApkpyChoice, lifted from the class as it ships."""

    CASES = [
        ('chips', ['A', 'B', 'C'], ['A'], 'B', False, False),
        ('chips', ['A', 'B', 'C'], ['A'], 'A', False, False),
        ('segmented', ['A', 'B', 'C'], ['A'], 'A', False, False),
        ('segmented', ['A', 'B', 'C'], [], 'C', True, False),
        ('chips', ['A', 'B', 'C'], ['C'], 'A', True, False),
        ('chips', ['A', 'B', 'C'], ['A', 'C'], 'A', True, False),
        ('chips', ['A', 'B', 'C'], ['A'], 'Z', False, False),
        ('chips', ['A', 'B', 'C'], ['A'], 'A', False, True),
        ('chips', ['A', 'B', 'C'], ['A'], 'A', True, True),
        ('chips', ['A', 'B', 'C'], ['A', 'B'], 'A', True, True),
        ('segmented', ['A', 'B', 'C'], ['B'], 'B', True, False),
        ('segmented', ['A', 'B', 'C'], ['B'], 'B', True, True),
    ]
    FLOWS = [([100, 100, 100], 250, 8), ([300, 50], 250, 8), ([40, 60, 80, 20], 130, 8),
             ([], 100, 8)]
    EDGES = [(3, 100), (2, 387), (5, 1080), (4, 3)]

    def _harness(self):
        java = choice_feature.java_source('x')
        start = java.index('    /** choice_rules.keeps_one')
        end = java.index('    /** choice_rules.chip_width')
        methods = java[start:end]
        calls = []
        for index, (kind, options, current, option, multiple, required) in enumerate(self.CASES):
            calls.append('System.out.println("tap|%d|" + tap(%s, list(%s), list(%s), "%s", %s, %s));'
                         % (index, 'true' if kind == 'segmented' else 'false',
                            ', '.join('"%s"' % o for o in options) or '',
                            ', '.join('"%s"' % o for o in current) or '',
                            option, 'true' if multiple else 'false',
                            'true' if required else 'false'))
        for index, (widths, room, gap) in enumerate(self.FLOWS):
            calls.append('System.out.println("flow|%d|" + java.util.Arrays.deepToString('
                         'flow(new int[]{%s}, %d, %d)));'
                         % (index, ', '.join(str(w) for w in widths), room, gap))
        for index, (count, width) in enumerate(self.EDGES):
            calls.append('System.out.println("edges|%d|" + java.util.Arrays.toString('
                         'segmentEdges(%d, %d)));' % (index, count, width))
        return ('import java.util.ArrayList;\n'
                'public class ChoiceRulesHarness {\n'
                '    static ArrayList<String> list(String... items) {\n'
                '        ArrayList<String> out = new ArrayList<>();\n'
                '        for (String item : items) out.add(item);\n'
                '        return out;\n'
                '    }\n'
                + methods +
                '    public static void main(String[] args) {\n        '
                + '\n        '.join(calls) +
                '\n    }\n}\n')

    def test_both_languages_agree(self):
        if not TOOLING:
            self.skipTest("no JDK on this machine")
        javac, java_bin, _jar = TOOLING
        work = tempfile.mkdtemp(prefix='apkpy-choice-')
        source = os.path.join(work, 'ChoiceRulesHarness.java')
        with io.open(source, 'w', encoding='utf-8') as handle:
            handle.write(self._harness())
        built = subprocess.run([javac, '-encoding', 'UTF-8', '-d', work, source],
                               capture_output=True, text=True)
        self.assertEqual(0, built.returncode, built.stdout + built.stderr)
        ran = subprocess.run([java_bin, '-cp', work, 'ChoiceRulesHarness'],
                             capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(0, ran.returncode, ran.stdout + ran.stderr)
        answers = dict(((kind, key), value) for kind, key, value in
                       (line.split('|') for line in ran.stdout.splitlines()))
        for index, (kind, options, current, option, multiple, required) in enumerate(self.CASES):
            expected = rules.tap(kind, options, current, option, multiple, required)
            self.assertEqual('[' + ', '.join(expected) + ']', answers[('tap', str(index))],
                             self.CASES[index])
        for index, (widths, room, gap) in enumerate(self.FLOWS):
            expected = [[x, line] for x, line in rules.flow(widths, room, gap)]
            self.assertEqual(json.loads(answers[('flow', str(index))]), expected)
        for index, (count, width) in enumerate(self.EDGES):
            self.assertEqual(json.loads(answers[('edges', str(index))]),
                             rules.segment_edges(count, width))

    def test_the_sizes_are_the_rules(self):
        java = choice_feature.java_source('x')
        for name, value in (('TOUCH', rules.TOUCH), ('CHIP_HEIGHT', rules.CHIP_HEIGHT),
                            ('CHIP_PAD', rules.CHIP_PAD), ('CHIP_PAD_ICON', rules.CHIP_PAD_ICON),
                            ('SEGMENT_HEIGHT', rules.SEGMENT_HEIGHT), ('ICON', rules.ICON)):
            self.assertRegex(java, r'static final float %s = %sf;' % (name, value))
        self.assertNotRegex(java, r'__[A-Z_]+__')


if __name__ == '__main__':
    unittest.main()
