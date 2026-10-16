# -*- coding: utf-8 -*-
"""What a stylesheet says about placement, on the phone as in the Previewer.

Six well-known screens rebuilt with ApkPy (25-09-2026) found five places where
a phone ignored the CSS, or read it differently from the Previewer:

* ``position: absolute`` on a screen's own child was laid out in the column
  with everything else: no floating button, no composer pinned to the bottom.
  Both runtimes now put such children on a layer over the content.
* A scrolling screen without a bottom bar drew its title under the clock:
  the only root that did not fit the system windows, with targetSdk 35
  making every window edge-to-edge on Android 15+.
* An absolute container with no width was measured as wide as the screen,
  so ``right: 12px`` had nothing to move (a TikTok-style column of buttons
  sat on the left edge).
* ``align-self`` on a child of the screen did nothing, and ``max-width``
  centred every chat bubble -- the reply that belongs on the right included.
* A label with ``flex-grow`` had its text centred on the phone ("Thursday
  plan" in the published Northline) while the Previewer kept it at the start.
"""

import re
import unittest
import xml.dom.minidom

from apkpy_lib import ui
from apkpy_lib.core.compiler import translate_python_to_android


def _build(body, css, extra=''):
    source = ('from apkpy_lib import *\n' + body +
              '\nstyle = """\n' + css + '\n"""\n' + extra +
              'run(start_screen=home)\n')
    files = translate_python_to_android(source)
    if not files or 'error.txt' in files:
        raise AssertionError((files or {}).get('error.txt', 'no output')[:600])
    return files


FAB = ('home = Screen(id="home"%s)\n'
       'label("Stories", id="title", screen=home)\n'
       'button("", id="fab", icon="add", describe="New", screen=home,\n'
       '       command=lambda: toast("new"))\n'
       'button("Later", id="later", screen=home, command=lambda: toast("later"))\n')
FAB_CSS = 'fab { position: absolute; right: 20px; bottom: 24px; width: 56px; height: 56px; }'


class AScreensAbsoluteChildFloats(unittest.TestCase):

    def test_it_leaves_the_column_for_a_layer_over_the_content(self):
        for scroll in ('', ', scroll=True'):
            files = _build(FAB % scroll, FAB_CSS)
            layout = files['res/layout/activity_screen_home.xml']
            xml.dom.minidom.parseString(layout.encode('utf-8'))
            self.assertTrue(layout.lstrip().split('\n', 2)[1].startswith('<FrameLayout'), scroll)
            overlay = layout[layout.index('apkpy_overlay'):]
            self.assertIn('position=absolute;right=20px;bottom=24px', overlay)
            self.assertIn('java/ApkpyLayout.java', files)

    def test_every_id_keeps_the_number_the_java_uses(self):
        files = _build(FAB % '', FAB_CSS)
        layout = files['res/layout/activity_screen_home.xml']
        java = files['java/Screen_homeActivity.java']
        for view_id in re.findall(r'@\+id/(btn\d+|lbl\d+)', layout):
            self.assertIn('R.id.' + view_id, java, view_id)
        # The floating button is the first button of the screen, as written.
        self.assertIn('android:id="@+id/btn1"', layout[layout.index('apkpy_overlay'):])

    def test_with_a_bottom_bar_it_stays_above_the_bar(self):
        body = (FAB % '') + 'more = Screen(id="more")\nlabel("x", screen=more)\n'
        files = _build(body, FAB_CSS,
                       'bottom_nav([home, more], labels=["Home", "More"], icons=["home", "list"])\n')
        layout = files['res/layout/activity_screen_home.xml']
        self.assertTrue(layout.lstrip().split('\n', 2)[1].startswith('<RelativeLayout'))
        self.assertNotIn('<FrameLayout', layout)
        overlay_tag = layout[layout.index('apkpy_overlay'):].split('>', 1)[0]
        self.assertIn('android:layout_above="@id/bottom_nav"', overlay_tag)

    def test_a_screen_without_one_is_unchanged(self):
        files = _build('home = Screen(id="home")\nlabel("x", screen=home)\n', '')
        layout = files['res/layout/activity_screen_home.xml']
        self.assertNotIn('apkpy_overlay', layout)
        self.assertEqual(layout.count('<FrameLayout'), 1)     # the root, no second layer

    def test_a_layer_goes_into_the_root_of_a_plain_screen(self):
        files = _build('home = Screen(id="home")\nlabel("x", screen=home)\n'
                       'button("+", id="fab", screen=home)\n',
                       'fab { position: absolute; bottom: 16px; right: 16px; }')
        layout = files['res/layout/activity_screen_home.xml']
        self.assertIn('apkpy_overlay', layout)
        self.assertEqual(layout.count('<FrameLayout'), 1)


class TheScreensPaddingSurvivesTheSystemBars(unittest.TestCase):
    """A view that fits the system windows has its padding replaced by the
    bars' on an edge-to-edge window (targetSdk 35, Android 15+). The padding
    of a plain screen sat on that view, and the phone dropped it: chips and
    charts touched the edge of the glass while the Previewer showed a margin.
    """

    def _root_and_padded(self, layout):
        tags = re.findall(r'<([\w.]+)((?:\s+[\w:]+="[^"]*")*)\s*/?>', layout.split('?>', 1)[1])
        return tags

    def test_no_root_carries_both(self):
        for body in ('home = Screen(id="home")\n',
                     'home = Screen(id="home", scroll=True)\n',
                     'home = Screen(id="home")\nother = Screen(id="other")\n'
                     'bottom_nav([home, other], labels=["A", "B"], icons=["home", "star"])\n'):
            files = _build(body + 'label("x", screen=home)\n', 'home { padding: 20px; }')
            layout = files['res/layout/activity_screen_home.xml']
            for tag, attrs in self._root_and_padded(layout):
                if 'fitsSystemWindows="true"' in attrs:
                    self.assertNotRegex(attrs, r'android:padding\w*="[1-9]', (body, tag))
            self.assertIn('android:paddingLeft="20dp"', layout, body)


class AScrollingScreenFitsTheSystemWindows(unittest.TestCase):

    def test_the_scrolling_root_asks_for_the_status_bar(self):
        files = _build('home = Screen(id="home", scroll=True)\nlabel("Title", screen=home)\n', '')
        root = files['res/layout/activity_screen_home.xml'].split('>', 2)[1]
        self.assertIn('NestedScrollView', root)
        self.assertIn('android:fitsSystemWindows="true"', root)


class AnAbsoluteBoxIsAsWideAsItsContent(unittest.TestCase):

    def test_the_phone_measures_it_for_its_content(self):
        body = ('home = Screen(id="home")\nstage = container(id="stage", screen=home)\n'
                'label("pic", id="pic", parent=stage)\n'
                'col = container(id="col", parent=stage)\n'
                'button("", id="like", icon="heart", describe="Like", parent=col,\n'
                '       command=lambda: toast("x"))\n')
        css = ('stage { position: relative; height: 400px; }\n'
               'col { position: absolute; right: 12px; bottom: 40px;\n'
               '      display: flex; flex-direction: column; }\n'
               'like { width: 48px; height: 48px; }')
        java = _build(body, css)['java/ApkpyLayout.java']
        self.assertIn('boolean shrinkToFit;', java)
        self.assertIn('MeasureSpec.AT_MOST', java)

    def test_the_previewer_asks_the_same_question(self):
        self.assertTrue(ui._shrinks_to_fit({'position': 'absolute', 'right': '12px'}))
        self.assertFalse(ui._shrinks_to_fit({'position': 'absolute', 'width': '80px'}))
        self.assertFalse(ui._shrinks_to_fit({'position': 'absolute', 'left': '8px', 'right': '8px'}))
        self.assertFalse(ui._shrinks_to_fit({'right': '12px'}))


class AlignSelfOnAScreensChild(unittest.TestCase):

    def test_my_bubble_goes_right(self):
        body = ('home = Screen(id="home")\n'
                'theirs = container(id="theirs", screen=home)\nlabel("Hi", parent=theirs)\n'
                'mine = container(id="mine", screen=home)\nlabel("Hey", parent=mine)\n')
        css = ('theirs { max-width: 260px; align-self: flex-start; }\n'
               'mine { max-width: 260px; align-self: flex-end; }')
        layout = _build(body, css)['res/layout/activity_screen_home.xml']
        gravities = re.findall(r'android:layout_gravity="([^"]+)"', layout)
        self.assertEqual(gravities, ['start', 'end'])

    def test_the_previewer_anchors_it_the_same_way(self):
        self.assertEqual(ui._ALIGN_SELF_ANCHOR['flex-end'], 'e')
        self.assertEqual(ui._ALIGN_SELF_ANCHOR['flex-start'], 'w')


class AGrowingLabelKeepsItsTextAtTheStart(unittest.TestCase):

    def test_text_align_start_as_in_css(self):
        body = ('home = Screen(id="home")\nhead = container(id="head", screen=home)\n'
                'label("Thursday plan", id="plan", parent=head)\n'
                'label("LOCAL TIME", id="tz", parent=head)\n')
        css = ('head { display: flex; flex-direction: row; align-items: center; }\n'
               'plan { flex-grow: 1; }')
        layout = _build(body, css)['res/layout/activity_screen_home.xml']
        plan = layout[layout.rfind('<TextView', 0, layout.index('Thursday plan')):]
        self.assertIn('android:gravity="start|center_vertical"', plan.split('/>', 1)[0])
        # One that hugs its words has nothing to move; since 1.12.0 it is at
        # the start too, so its lines stay there when it wraps
        # (test_flex_text_and_crop), and text-align: center still centres it.
        tz = layout[layout.rfind('<TextView', 0, layout.index('LOCAL TIME')):]
        self.assertIn('android:gravity="start|center_vertical"', tz.split('/>', 1)[0])
        centred = _build(body, css + '\ntz { text-align: center; }')[
            'res/layout/activity_screen_home.xml']
        tz = centred[centred.rfind('<TextView', 0, centred.index('LOCAL TIME')):]
        self.assertIn('android:gravity="center"', tz.split('/>', 1)[0])


if __name__ == '__main__':
    unittest.main()
