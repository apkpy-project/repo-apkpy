# -*- coding: utf-8 -*-
"""Two things a chat screen needs: the middle, and text that arrives.

`flex-grow` on a column child is what pins a composer to the bottom and gives
an empty state the whole middle to sit in. `stream` is what makes an answer
look like an answer instead of appearing all at once -- the single most
characteristic thing about talking to an assistant, and until now something
the library had no word for at all.

The tests that carry weight are the timing ones. A rate that differs between
the two runtimes is a divergence you feel and cannot screenshot, which is the
reason the number lives in one table.
"""

import unittest

from apkpy_lib import motion
from apkpy_lib.core.compiler import _column_gravity, translate_python_to_android


def _build(source):
    result = translate_python_to_android(source)
    assert 'error.txt' not in result, result['error.txt'][:500]
    return result


HERO = '''
from apkpy_lib import Screen, Theme, container, inputs, label, run
chat = Screen(id="chat")
hero = container(id="hero", screen=chat)
label("Ora", id="mark", parent=hero)
composer = container(id="composer", screen=chat)
inputs(placeholder="Reply", id="field", type="textarea", parent=composer)
run(start_screen=chat, theme=Theme(mode="dark"))

style = """
hero { flex-grow: 1; justify-content: center; align-items: center; }
"""
'''


class ColumnGravityTests(unittest.TestCase):
    def test_the_old_default_is_still_the_default(self):
        # Every screen already written centres horizontally and nothing else.
        self.assertEqual(_column_gravity({}), 'center_horizontal')

    def test_justify_content_places_children_along_the_column(self):
        self.assertEqual(_column_gravity({'justify-content': 'center'}),
                         'center_horizontal|center_vertical')
        self.assertEqual(_column_gravity({'justify-content': 'flex-end'}),
                         'center_horizontal|bottom')

    def test_align_items_places_them_across_it(self):
        self.assertEqual(_column_gravity({'align-items': 'flex-start'}), 'start')
        self.assertEqual(_column_gravity({'align-items': 'flex-end'}), 'end')

    def test_a_value_nobody_understands_leaves_the_default(self):
        self.assertEqual(_column_gravity({'justify-content': 'space-haggis'}),
                         'center_horizontal')


class FillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.xml = _build(HERO)['res/layout/activity_screen_chat.xml']

    def test_a_growing_child_takes_the_leftover_height(self):
        head = self.xml.split('@+id/cnt1"')[1].split('>')[0]
        # 0dp plus a weight, not wrap_content: weight distributes what is left
        # and a wrap_content child has nothing to distribute.
        self.assertIn('android:layout_height="0dp"', head)
        self.assertIn('android:layout_weight="1"', head)

    def test_it_centres_what_is_inside_it(self):
        head = self.xml.split('@+id/cnt1"')[1].split('>')[0]
        self.assertIn('android:gravity="center_horizontal|center_vertical"',
                      head)

    def test_the_sibling_after_it_is_untouched(self):
        head = self.xml.split('@+id/cnt2"')[1].split('>')[0]
        self.assertNotIn('layout_weight', head)

    def test_a_column_that_asks_for_nothing_is_unchanged(self):
        plain = _build(HERO.replace(
            'hero { flex-grow: 1; justify-content: center; align-items: center; }',
            ''))['res/layout/activity_screen_chat.xml']
        head = plain.split('@+id/cnt1"')[1].split('>')[0]
        self.assertNotIn('layout_weight', head)
        self.assertIn('android:gravity="center_horizontal"', head)


class StreamRateTests(unittest.TestCase):
    def test_the_rate_is_one_table(self):
        for name in ('slow', 'normal', 'fast', 'instant'):
            self.assertIn(name, motion.STREAM_SPEEDS)
        chars, step = motion.stream_step('normal')
        self.assertGreater(chars, 0)
        self.assertGreater(step, 0)

    def test_faster_means_more_text_per_second(self):
        def rate(speed):
            chars, step = motion.stream_step(speed)
            return chars / step

        self.assertLess(rate('slow'), rate('normal'))
        self.assertLess(rate('normal'), rate('fast'))

    def test_a_speed_nobody_understands_is_the_default(self):
        self.assertEqual(motion.stream_step('quickly'),
                         motion.stream_step('normal'))
        self.assertEqual(motion.stream_step(None), motion.stream_step('normal'))

    def test_instant_means_all_of_it_at_once(self):
        self.assertEqual(motion.stream_step('instant'), (0, 0))

    def test_animations_off_means_no_typing(self):
        # Somebody who turned animations off did not ask to watch text type
        # itself, whatever the call said.
        self.assertEqual(motion.stream_step('fast', preset='none'), (0, 0))

    def test_the_step_is_slow_enough_for_a_handler_to_hit(self):
        # A Handler and a Tk `after` both stop being accurate below ~10ms, and
        # a rate the runtime cannot keep is a rate that differs between them.
        for name in ('slow', 'normal', 'fast'):
            self.assertGreaterEqual(motion.STREAM_SPEEDS[name][1], 10, name)


STREAM_APP = '''
from apkpy_lib import Screen, Theme, button, label, run, virtual_collection
home = Screen(id="home")
lead = label("x", id="lead", screen=home)
thread = virtual_collection([{"id": "a", "message": "hi"}],
                            template={"title": "{message}"}, id="t",
                            screen=home)
def go():
    lead.stream("Once upon a time", speed="fast")
    thread.stream_item("a", "message", "An answer arriving")
button("go", id="b", command=go, screen=home)
run(start_screen=home, theme=Theme(mode="dark"))
'''


class StreamCodegenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = _build(STREAM_APP)['java/Screen_homeActivity.java']

    def test_the_rate_is_baked_in_from_the_shared_table(self):
        chars, step = motion.stream_step('fast')
        # A view chega por findViewById e nao pelo nome local: `lbl1` so'
        # existe dentro do onCreate, e um stream() numa funcao com nome
        # referia-o na mesma -- cannot-find-symbol no javac.
        self.assertIn('_apkpyStreamText((android.widget.TextView) '
                      'findViewById(R.id.lbl1), String.valueOf("Once upon a '
                      'time"), %d, %d);' % (chars, step), self.java)
        self.assertNotIn('_apkpyStreamText(lbl1', self.java)

    def test_streaming_into_a_row_reaches_the_adapter(self):
        self.assertIn('_apkpyStreamItem(vc1_items, vc1Adapter, "id"', self.java)
        self.assertIn('adapter.notifyItemChanged(index);', self.java)

    def test_the_helpers_are_there_and_the_java_is_balanced(self):
        self.assertIn('private void _apkpyStreamText(', self.java)
        self.assertIn('private void _apkpyStreamItem(', self.java)
        self.assertEqual(self.java.count('{'), self.java.count('}'))

    def test_an_app_that_streams_nothing_carries_no_helpers(self):
        java = _build('''
from apkpy_lib import Screen, label, run
home = Screen(id="home")
label("x", id="t", screen=home)
run(start_screen=home)
''')['java/Screen_homeActivity.java']
        self.assertNotIn('_apkpyStream', java)

    def test_a_screen_without_the_widget_carries_no_helper_for_it(self):
        # The commands come from the whole module; the helper touches a class
        # only the screen with a collection has. Emitting it everywhere is a
        # "cannot find symbol" on every other screen.
        out = _build(STREAM_APP.replace(
            'run(start_screen=home, theme=Theme(mode="dark"))',
            'other = Screen(id="other")\n'
            'label("y", id="u", screen=other)\n'
            'run(start_screen=home, theme=Theme(mode="dark"))'))
        other = out['java/Screen_otherActivity.java']
        self.assertNotIn('_apkpyStreamItem', other)
        self.assertNotIn('ApkpyVirtualAdapter', other)


if __name__ == '__main__':
    unittest.main()
