# -*- coding: utf-8 -*-
"""The settings row, and the hairlines that group it.

A row is the one shape a button cannot be: its label starts at the leading
edge, it carries a second line, and it keeps room on the right for a value or
a chevron.  Everything a settings screen is made of, and until now the library
had no word for it -- which is why three stacked buttons read as three pills.

What these tests hold down is the grouping: `showDividers="middle"` draws
between children and never at the edges, and a row inside a group sits flush
against the next one.  A 6dp stacking gap would push every hairline off the
seam it belongs on, and that only shows up once the APK is on a phone.
"""

import unittest

from apkpy_lib import icons
from apkpy_lib.theme import Theme, divider_spec
from apkpy_lib.core.compiler import (
    _generate_divider_xml,
    _material_icon_path,
    translate_python_to_android,
)


APP = '''
from apkpy_lib import Screen, container, list_row, run, toast
home = Screen(id="home")
group = container(id="group", screen=home)
list_row("Profile", icon="person", trailing_icon="chevron_right",
         id="r1", parent=group, command=lambda: toast("Profile"))
list_row("Plan", subtitle="Renews on the 12th", icon="star", trailing="Pro",
         id="r2", parent=group)
list_row("Sign out", id="r3", screen=home)
run(start_screen=home)

style = """
group { divider-color: #3A3A37; divider-inset: 56px; padding: 0px; }
list_row { background-color: #00000000; }
"""
'''


def _build(source=APP):
    result = translate_python_to_android(source)
    assert 'error.txt' not in result, result['error.txt'][:400]
    return result


class RowLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = _build()
        cls.xml = cls.out['res/layout/activity_screen_home.xml']
        cls.java = cls.out['java/Screen_homeActivity.java']

    def test_a_row_is_a_horizontal_strip_that_answers_a_tap(self):
        row = self.xml.split('@+id/lrow1"')[1].split('>')[0]
        self.assertIn('android:orientation="horizontal"', row)
        self.assertIn('android:gravity="center_vertical"', row)
        self.assertIn('android:clickable="true"', row)

    def test_the_text_block_takes_what_the_rest_leaves(self):
        # 0dp plus weight 1, or a long label pushes the trailing pieces off
        # the edge instead of being cut short.
        block = self.xml.split('@+id/lrow1_title')[0].split('<LinearLayout')[-1]
        self.assertIn('android:layout_width="0dp"', block)
        self.assertIn('android:layout_weight="1"', block)

    def test_a_row_cuts_its_label_rather_than_wrapping(self):
        title = self.xml.split('@+id/lrow1_title')[1][:400]
        self.assertIn('android:maxLines="1"', title)
        self.assertIn('android:ellipsize="end"', title)

    def test_the_pieces_that_were_not_asked_for_are_not_there(self):
        row = self.xml.split('@+id/lrow1"')[1].split('</LinearLayout>')[0]
        self.assertNotIn('lrow1_subtitle', self.xml)
        self.assertNotIn('lrow1_trailing', row)

    def test_the_pieces_that_were_asked_for_are(self):
        self.assertIn('@+id/lrow2_subtitle', self.xml)
        self.assertIn('android:text="Renews on the 12th"', self.xml)
        self.assertIn('@+id/lrow2_trailing', self.xml)
        self.assertIn('android:text="Pro"', self.xml)

    def test_a_command_reaches_the_row_the_way_it_reaches_a_button(self):
        self.assertIn('View lrow1 = findViewById(R.id.lrow1);', self.java)
        self.assertIn('lrow1.setOnClickListener(', self.java)
        self.assertIn('String.valueOf("Profile")', self.java)

    def test_a_row_with_nothing_to_do_gets_no_listener(self):
        self.assertNotIn('lrow2.setOnClickListener(', self.java)

    def test_a_row_can_open_a_screen(self):
        out = _build('''
from apkpy_lib import Screen, list_row, run
home = Screen(id="home")
detail = Screen(id="detail")
r = list_row("Open", icon="person", id="r1", screen=home)
home.on_click_navigate(button=r, to=detail)
run(start_screen=home)
''')
        java = out['java/Screen_homeActivity.java']
        self.assertIn('lrow1.setOnClickListener(', java)
        self.assertIn('Screen_detailActivity.class', java)
        self.assertIn('startActivity(intent);', java)

    def test_the_generated_java_is_balanced(self):
        self.assertEqual(self.java.count('{'), self.java.count('}'))

    def test_rows_side_by_side_share_the_width(self):
        # match_parent in a horizontal parent lets the first row eat everything
        # and the rest disappear -- which is exactly what happened.
        out = _build('''
from apkpy_lib import Screen, container, list_row, run
home = Screen(id="home")
strip = container(id="strip", screen=home)
list_row("Left", icon="person", parent=strip)
list_row("Right", icon="star", parent=strip)
run(start_screen=home)

style = """
strip { display: flex; flex-direction: row; gap: 10px; }
"""
''')
        layout = out['res/layout/activity_screen_home.xml']
        for row_id in ('lrow1', 'lrow2'):
            head = layout.split(f'@+id/{row_id}"')[1].split('>')[0]
            self.assertIn('android:layout_width="0dp"', head, row_id)
            self.assertIn('android:layout_weight="1"', head, row_id)

    def test_an_explicit_width_wins_over_sharing(self):
        out = _build(APP.replace('list_row { background-color: #00000000; }',
                                 'list_row { width: 160px; }'))
        head = out['res/layout/activity_screen_home.xml'].split(
            '@+id/lrow1"')[1].split('>')[0]
        self.assertIn('android:layout_width="160dp"', head)


class RowValueTests(unittest.TestCase):
    """A row shows three texts, so it needs three ways to change one."""

    APP = '''
from apkpy_lib import Screen, button, list_row, run
home = Screen(id="home")
row = list_row("Default model", subtitle="", trailing="Opus 5", id="r",
               screen=home)
def go():
    row.set_value("Model")
    row.set_trailing("Sonnet 5")
    row.set_subtitle("Changed just now")
button("go", id="b", command=go, screen=home)
run(start_screen=home)
'''

    @classmethod
    def setUpClass(cls):
        cls.java = _build(cls.APP)['java/Screen_homeActivity.java']

    def test_set_value_reaches_the_label_and_not_the_row(self):
        # The row is a LinearLayout. setText on it is a cannot-find-symbol at
        # build time, which is exactly what this used to emit.
        self.assertIn('findViewById(R.id.lrow1_title)).setText(', self.java)
        self.assertNotIn('lrow1.setText(', self.java)

    def test_the_other_two_slots_have_their_own_setters(self):
        self.assertIn('R.id.lrow1_trailing', self.java)
        self.assertIn('R.id.lrow1_subtitle', self.java)

    def test_a_slot_the_row_never_declared_is_not_assumed(self):
        # Declaring `subtitle=""` is what creates the TextView; without it the
        # lookup returns null and the guard is the only thing between that and
        # a crash.
        self.assertIn('_slot != null', self.java)

    def test_the_generated_java_is_balanced(self):
        self.assertEqual(self.java.count('{'), self.java.count('}'))


class RowGroupingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = _build()
        cls.xml = cls.out['res/layout/activity_screen_home.xml']

    def test_rows_in_a_group_sit_flush(self):
        # The bug this catches: the 6dp baseline gap between stacked children
        # applying to rows, which lifts every hairline off its seam.
        for row_id in ('lrow1', 'lrow2'):
            head = self.xml.split(f'@+id/{row_id}"')[1].split('>')[0]
            self.assertNotIn('layout_marginTop', head, row_id)

    def test_the_group_draws_between_its_children_and_nowhere_else(self):
        group = self.xml.split('@+id/cnt1"')[1].split('>')[0]
        self.assertIn('android:showDividers="middle"', group)
        self.assertIn('android:divider="@drawable/', group)

    def test_a_container_that_says_nothing_grows_no_lines(self):
        plain = _build(APP.replace(
            'group { divider-color: #3A3A37; divider-inset: 56px;', 'group {'))
        layout = plain['res/layout/activity_screen_home.xml']
        self.assertNotIn('showDividers', layout)
        self.assertFalse([k for k in plain if k.endswith('_divider.xml')])


class DividerSpecTests(unittest.TestCase):
    def test_opting_in_takes_a_colour_and_nothing_else(self):
        self.assertIsNone(divider_spec({}))
        self.assertIsNone(divider_spec({'divider-width': '2px'}))
        self.assertIsNone(divider_spec({'divider-color': 'none'}))
        self.assertIsNone(divider_spec({'divider-color': 'transparent'}))

    def test_a_hairline_is_the_default_thickness(self):
        self.assertEqual(divider_spec({'divider-color': '#333'})['width'], 1)
        self.assertEqual(
            divider_spec({'divider-color': '#333', 'divider-width': '2px'})['width'], 2)

    def test_the_inset_is_read_and_never_negative(self):
        spec = {'divider-color': '#333', 'divider-inset': '56px'}
        self.assertEqual(divider_spec(spec)['inset'], 56)
        spec['divider-inset'] = '-8px'
        self.assertEqual(divider_spec(spec)['inset'], 0)

    def test_the_drawable_carries_both_dimensions(self):
        # A vertical layout reads the intrinsic height and a horizontal one
        # reads the width; writing only one leaves the other layout lineless.
        xml = _generate_divider_xml({'color': '#3A3A37', 'width': 1, 'inset': 0})
        self.assertIn('android:width="1dp"', xml)
        self.assertIn('android:height="1dp"', xml)
        self.assertNotIn('<inset', xml)

    def test_the_inset_becomes_the_wrapper_android_has_no_attribute_for(self):
        xml = _generate_divider_xml(
            {'color': '#3A3A37', 'width': 1, 'inset': 56})
        self.assertIn('android:insetLeft="56dp"', xml)
        horizontal = _generate_divider_xml(
            {'color': '#3A3A37', 'width': 1, 'inset': 56}, horizontal=True)
        self.assertIn('android:insetTop="56dp"', horizontal)

    def test_the_namespace_is_declared_once(self):
        for xml in (
            _generate_divider_xml({'color': '#333', 'width': 1, 'inset': 0}),
            _generate_divider_xml({'color': '#333', 'width': 1, 'inset': 8}),
        ):
            self.assertEqual(xml.count('xmlns:android'), 1)


class RowThemeTests(unittest.TestCase):
    def test_a_row_looks_right_with_no_css_at_all(self):
        row = Theme(mode='dark').styles()['list_row']
        for key in ('background-color', 'color', 'subtitle-color',
                    'trailing-color', 'icon-color', 'pressed-color',
                    'min-height'):
            self.assertIn(key, row)

    def test_the_quiet_pieces_are_quieter_than_the_label(self):
        row = Theme(mode='dark').styles()['list_row']
        self.assertNotEqual(row['color'], row['subtitle-color'])
        self.assertEqual(row['subtitle-color'], row['trailing-color'])

    def test_the_chevron_a_row_needs_exists_on_both_sides(self):
        # Without it a row has no way of saying that tapping opens something,
        # and the catalogue had no sideways chevron at all.
        for name in ('chevron_right', 'chevron_left'):
            self.assertIsNotNone(icons.resolve(name), name)
            self.assertEqual(_material_icon_path(name), icons.resolve(name))
        self.assertNotEqual(icons.resolve('chevron_right'),
                            icons.resolve('chevron_left'))
        self.assertEqual(icons.resolve('navigate_next'),
                         icons.resolve('chevron_right'))


if __name__ == '__main__':
    unittest.main()
