# -*- coding: utf-8 -*-
"""Rows that swipe and move: virtual_collection(swipe_right=, swipe_left=,
reorder=, on_reorder=) and swipe(icon, text, on_swipe=, color=, keep=, undo=).

A mail inbox and a to-do list for the photo replica (28-09-2026): swipe right
to archive with Undo, left to delete, hold to reorder. The phone does it with
ItemTouchHelper (ApkpyGestures), the Previewer with the mouse, both from the
numbers in gesture_rules; every gesture is also an accessibility action on
the row, which is what the Previewer's right-click menu shows.
"""

import re
import time
import unittest

from apkpy_lib import gesture_rules as rules
from test_real_screens import Previewed, _build

MAIL = (
    'home = Screen(id="home")\n'
    'done = []\n'
    'MAIL = [{"id": "m%d" % i, "title": "Message %d" % i} for i in range(6)]\n'
    'def archive(item):\n'
    '    done.append(("archive", item["id"]))\n'
    'def delete(item):\n'
    '    done.append(("delete", item["id"]))\n'
    'def moved(item, index):\n'
    '    done.append(("moved", item["id"], index))\n'
    'def opened(item):\n'
    '    done.append(("open", item["id"]))\n'
)
LIST = ('inbox = virtual_collection(MAIL, id="inbox", screen=home, item_height=64,\n'
        '    on_click=opened, %s)\n')
BOTH = LIST % ('swipe_right=swipe("archive", "Archive", on_swipe=archive), '
               'swipe_left=swipe("delete", "Delete", on_swipe=delete), on_reorder=moved')
CSS = 'inbox { height: 420px; }'

PHONE = (
    'home = Screen(id="home")\n'
    'MAIL = [{"id": "m1", "title": "Hello"}, {"id": "m2", "title": "Bye"}]\n'
    'def archive(item):\n'
    '    toast("Archived " + item["title"])\n'
    'def moved(item, index):\n'
    '    toast(item["title"] + " to " + str(index + 1))\n'
)


def _java(files):
    return files['java/Screen_homeActivity.java']


class TheRules(unittest.TestCase):

    def test_a_swipe_completes_past_forty_percent(self):
        self.assertFalse(rules.commits(150, 400))
        self.assertTrue(rules.commits(160, 400))
        self.assertTrue(rules.commits(-200, 400))

    def test_reordering_moves_one_row(self):
        self.assertEqual(rules.reorder(list('abcde'), 0, 3), list('bcdae'))
        self.assertEqual(rules.reorder(list('abcde'), 4, 0), list('eabcd'))
        self.assertEqual(rules.reorder(list('abc'), 1, 9), list('acb'))

    def test_the_colour_of_a_strip(self):
        self.assertEqual(rules.swipe_color('delete'), rules.DESTRUCTIVE_COLOR)
        self.assertEqual(rules.swipe_color('archive', tokens={'primary': '#123456'}), '#123456')
        self.assertEqual(rules.swipe_color('archive', '#1E7A46'), '#1E7A46')

    def test_every_gesture_is_an_action(self):
        actions = rules.accessibility_actions(
            right={'text': 'Archive'}, left={'text': 'Delete'},
            reorder_enabled=True, index=0, count=3)
        self.assertEqual([a[1] for a in actions], ['Archive', 'Delete', 'Move up', 'Move down'])
        self.assertEqual([a[2] for a in actions], [True, True, False, True])


class ThePhone(unittest.TestCase):

    def _build(self, gestures, extra=''):
        return _build(PHONE + extra + 'inbox = virtual_collection(MAIL, id="inbox", '
                      'screen=home, ' + gestures + ')\n')

    def test_an_item_touch_helper_on_the_list(self):
        files = self._build('swipe_right=swipe("archive", "Archive", on_swipe=archive), '
                            'swipe_left=swipe("delete", "Delete", on_swipe=lambda item: toast("x")), '
                            'on_reorder=moved')
        java = _java(files)
        self.assertIn('ApkpyGestures.attach(vc1, vc1_items, new ApkpyGestures.Side('
                      'android.graphics.Color.parseColor("#6750A4")', java)
        self.assertIn('parseColor("%s")' % rules.DESTRUCTIVE_COLOR, java)
        self.assertIn('java/ApkpyGestures.java', files)
        self.assertEqual(len([k for k in files if k.startswith('res/drawable/ic_swipe_')]), 2)
        self.assertIn('#FFFFFF', files['res/drawable/ic_swipe_home_1.xml'].upper())

    def test_the_class_reads_the_shared_numbers(self):
        files = self._build('swipe_left=swipe("delete", "Delete"), reorder=True')
        gestures = files['java/ApkpyGestures.java']
        self.assertIn('THRESHOLD = %rf' % float(rules.SWIPE_THRESHOLD), gestures)
        self.assertIn('MOVE_UP = "%s"' % rules.MOVE_UP, gestures)
        self.assertIn('ViewCompat.addAccessibilityAction(row, MOVE_DOWN', gestures)
        self.assertIn('isLongPressDragEnabled() { return reorder; }', gestures)

    def test_undo_waits_before_telling_the_app(self):
        java = _java(self._build(
            'swipe_right=swipe("archive", "Archive", on_swipe=archive, undo="Archived")'))
        method = java[java.index('private void _apkpySwipedVc1'):]
        method = method[:method.index('\n    }\n')]
        self.assertIn('Snackbar.make(findViewById(android.R.id.content), "Archived"', method)
        self.assertIn('bar.setDuration(%d);' % rules.UNDO_MS, method)
        self.assertIn('if (!undone[0]) { pythonCallback_archive(item); }', method)
        self.assertIn('vc1_items.add(at, item);', method)

    def test_keep_slides_the_row_back(self):
        java = _java(self._build(
            'swipe_left=swipe("mark_email_read", "Read", on_swipe=archive, keep=True)'))
        method = java[java.index('private void _apkpySwipedVc1'):]
        method = method[:method.index('\n    }\n')]
        self.assertIn('vc1Adapter.notifyItemChanged(position);', method)
        self.assertNotIn('vc1_items.remove(position);', method)

    def test_a_kept_row_comes_back_by_itself(self):
        # With no item animator, ItemTouchHelper left a kept row off the edge
        # over its strip (seen on a phone, 28-09-2026).
        files = self._build('swipe_left=swipe("event", "Tomorrow", on_swipe=archive, keep=True)')
        self.assertIn('"Tomorrow", true)', _java(files))
        gestures = files['java/ApkpyGestures.java']
        self.assertIn('if (side != null && side.keep) comeBack(holder.itemView);', gestures)
        self.assertIn('SLIDE_MS = %dL' % rules.SLIDE_MS, gestures)

    def test_the_new_position_is_a_number(self):
        java = _java(self._build('on_reorder=moved'))
        self.assertIn('pythonCallback_moved(vc1_items.get(to), String.valueOf(to));', java)
        body = java[java.index('void pythonCallback_moved'):]
        self.assertIn('Integer.parseInt(String.valueOf(index)) + 1', body[:600])

    def test_a_swipe_kept_in_a_variable(self):
        files = _build(PHONE + 'right = swipe("archive", "Archive", on_swipe=archive)\n'
                       'inbox = virtual_collection(MAIL, id="inbox", screen=home, swipe_right=right)\n')
        self.assertIn('ApkpyGestures.attach(', _java(files))

    def test_a_list_without_gestures_is_unchanged(self):
        files = _build(PHONE + 'inbox = virtual_collection(MAIL, id="inbox", screen=home)\n')
        self.assertNotIn('ApkpyGestures', _java(files))
        self.assertNotIn('java/ApkpyGestures.java', files)

    def test_a_grid_says_why(self):
        with self.assertRaises(AssertionError) as caught:
            self._build('layout="grid", swipe_left=swipe("delete", "Delete")')
        self.assertIn('U2042', str(caught.exception))

    def test_something_that_is_not_a_swipe_says_why(self):
        with self.assertRaises(AssertionError) as caught:
            self._build('swipe_left="delete"')
        self.assertIn('U2042', str(caught.exception))


class ThePreviewer(unittest.TestCase):

    def _first_row(self, canvas):
        rows = sorted((w for w in canvas.winfo_children() if w.winfo_ismapped()),
                      key=lambda w: w.winfo_y())
        return rows[0]

    def _ids(self, p):
        return [item['id'] for item in p.ns['inbox'].kwargs['items']]

    def test_a_drag_to_the_right_archives(self):
        with Previewed(MAIL + BOTH, CSS) as p:
            row = self._first_row(p.widget('inbox'))
            row.event_generate('<ButtonPress-1>', x=30, y=20)
            for dx in (20, 80, 160, 260):
                row.event_generate('<B1-Motion>', x=30 + dx, y=20)
            row.event_generate('<ButtonRelease-1>', x=30, y=20)
            p.settle(0.6)
            self.assertEqual(p.ns['done'], [('archive', 'm0')])
            self.assertEqual(self._ids(p)[0], 'm1')

    def test_a_short_drag_slides_back(self):
        with Previewed(MAIL + BOTH, CSS) as p:
            row = self._first_row(p.widget('inbox'))
            row.event_generate('<ButtonPress-1>', x=30, y=20)
            row.event_generate('<B1-Motion>', x=90, y=20)
            row.event_generate('<ButtonRelease-1>', x=30, y=20)
            p.settle(0.5)
            self.assertEqual(p.ns['done'], [])
            self.assertEqual(len(self._ids(p)), 6)

    def test_a_tap_still_opens_the_row(self):
        with Previewed(MAIL + BOTH, CSS) as p:
            # The cell fills the row; a click lands on it, not on the frame.
            cell = self._first_row(p.widget('inbox')).winfo_children()[0]
            cell.event_generate('<ButtonPress-1>', x=30, y=20)
            cell.event_generate('<ButtonRelease-1>', x=30, y=20)
            p.settle(0.2)
            self.assertEqual(p.ns['done'], [('open', 'm0')])

    def test_the_actions_a_screen_reader_would_offer(self):
        with Previewed(MAIL + BOTH, CSS) as p:
            comp = p.ns['inbox']
            self.assertEqual([a[1] for a in comp._row_actions(0)],
                             ['Archive', 'Delete', 'Move up', 'Move down'])
            comp._row_perform('left', 0)
            comp._row_perform('down', 0)
            p.settle(0.3)
            self.assertEqual(p.ns['done'], [('delete', 'm0'), ('moved', 'm1', 1)])
            self.assertEqual(self._ids(p)[:3], ['m2', 'm1', 'm3'])

    def test_a_long_press_lifts_the_row_and_a_drop_moves_it(self):
        with Previewed(MAIL + BOTH, CSS) as p:
            row = self._first_row(p.widget('inbox'))
            row.event_generate('<ButtonPress-1>', x=30, y=20)
            p.settle(rules.LONG_PRESS_MS / 1000.0 + 0.2)
            row.event_generate('<B1-Motion>', x=30, y=150)
            row.event_generate('<ButtonRelease-1>', x=30, y=150)
            p.settle(0.3)
            moves = [d for d in p.ns['done'] if d[0] == 'moved']
            self.assertEqual(len(moves), 1)
            self.assertEqual(moves[0][1], 'm0')
            self.assertGreater(moves[0][2], 0)
            self.assertIsInstance(moves[0][2], int)
            self.assertEqual(self._ids(p).index('m0'), moves[0][2])

    def test_keep_leaves_the_row(self):
        body = MAIL + LIST % 'swipe_left=swipe("event", "Tomorrow", on_swipe=delete, keep=True)'
        with Previewed(body, CSS) as p:
            p.ns['inbox']._row_perform('left', 2)
            p.settle(0.2)
            self.assertEqual(p.ns['done'], [('delete', 'm2')])
            self.assertEqual(len(self._ids(p)), 6)

    def test_undo_brings_it_back_and_the_app_never_hears(self):
        from apkpy_lib import ui
        shown = []
        original = ui._show_snackbar_preview
        ui._show_snackbar_preview = lambda message, action=None, on_action=None, duration=0: \
            shown.append((message, action, on_action))
        old_ms = rules.UNDO_MS
        rules.UNDO_MS = 200
        try:
            body = MAIL + LIST % ('swipe_right=swipe("archive", "Archive", on_swipe=archive, '
                                  'undo="Archived")')
            with Previewed(body, CSS) as p:
                comp = p.ns['inbox']
                comp._row_perform('right', 1)
                p.settle(0.05)
                self.assertEqual(shown[0][:2], ('Archived', 'Undo'))
                self.assertNotIn('m1', self._ids(p))
                shown[0][2]()                 # Undo
                p.settle(0.5)
                self.assertEqual(self._ids(p)[1], 'm1')
                self.assertEqual(p.ns['done'], [])
                comp._row_perform('right', 1)
                p.settle(0.5)                 # nobody pressed Undo this time
                self.assertEqual(p.ns['done'], [('archive', 'm1')])
        finally:
            ui._show_snackbar_preview = original
            rules.UNDO_MS = old_ms

    def test_a_grid_refuses(self):
        from apkpy_lib import swipe, virtual_collection
        with self.assertRaises(ValueError):
            virtual_collection([], layout='grid', swipe_left=swipe('delete', 'Delete'))


if __name__ == '__main__':
    unittest.main()
