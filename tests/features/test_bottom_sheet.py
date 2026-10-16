"""A bottom sheet with components in it, and one that can be dragged.

`bottom_sheet("Filters", screen=home)` holds components put in it with
`parent=`. On the phone it is Material's BottomSheetDialog around a layout
of its own, which the Activity inflates and answers findViewById from; in
the Previewer it is a window over the app that can be dragged down. The
sizes and what a drag decides are one set of rules (apkpy_lib/sheet_rules.py).
"""

import unittest

from apkpy_lib import sheet_rules as rules
from apkpy_lib.diagnostics import ApkpyError

from test_real_screens import Previewed, _build, _layouts

APP = (
    'home = Screen(id="home")\n'
    'shown = label("Newest first", id="shown", screen=home)\n'
    'SEEN = []\n'
    'def apply():\n'
    '    shown.set_value(order.get_value() + " first, up to " + budget.get_value())\n'
    '    filters.close()\n'
    'def closed():\n'
    '    SEEN.append("closed")\n'
    'filters = bottom_sheet("Filters", "Choose what the list shows.", id="filters",\n'
    '                       screen=home, on_close=closed)\n'
    'label("Sort by", id="sort_by", parent=filters)\n'
    'order = segmented(["Newest", "Price"], selected="Newest", parent=filters)\n'
    'budget = inputs("Max price", id="budget", type="number", help="In euros", parent=filters)\n'
    'button("Apply", id="apply", command=apply, parent=filters)\n'
    'button("Filters", id="open", command=filters.open, screen=home)\n'
)
PLAIN = (
    'home = Screen(id="home")\n'
    'PICKED = []\n'
    'sort = bottom_sheet("Sort by", "How the list is ordered.", items=["Newest", "Price"],\n'
    '                    on_select=lambda value: PICKED.append(value))\n'
    'button("Sort", id="open", command=sort.open, screen=home)\n'
)


def _java(files, screen='home'):
    return files['java/Screen_%sActivity.java' % screen]


class TheSharedRules(unittest.TestCase):

    def test_where_a_drag_ends(self):
        self.assertEqual(rules.settle(0, 400), 'open')
        self.assertEqual(rules.settle(199, 400), 'open')
        self.assertEqual(rules.settle(201, 400), 'closed')          # past half way
        self.assertEqual(rules.settle(40, 400, rules.FLING), 'closed')     # flung down
        self.assertEqual(rules.settle(300, 400, -rules.FLING), 'open')     # flung back up
        self.assertEqual(rules.settle(0, 0), 'closed')

    def test_how_tall(self):
        self.assertEqual(rules.height(300, 900), 300)
        self.assertEqual(rules.height(2000, 900), 900 - rules.TOP_GAP)

    def test_the_scrim_fades_with_the_sheet(self):
        self.assertEqual(rules.scrim_alpha(0, 400), rules.SCRIM)
        self.assertEqual(rules.scrim_alpha(400, 400), 0.0)
        self.assertEqual(rules.scrim_alpha(200, 400), round(rules.SCRIM / 2, 4))

    def test_the_bodys_css_wins_over_the_defaults(self):
        style = rules.body_style({'gap': '4px', 'background-color': '#101010'})
        self.assertEqual(style['gap'], '4px')
        self.assertEqual(style['background-color'], '#101010')
        self.assertEqual(style['flex-direction'], 'column')
        self.assertEqual(style['align-items'], 'stretch')
        self.assertIn('%dpx' % rules.SIDE, style['padding'])

    def test_refusals(self):
        with self.assertRaises(ApkpyError) as caught:
            rules.check_plain_arguments(True, ['A'])
        self.assertEqual(caught.exception.code, 'U2045')
        rules.check_plain_arguments(False, ['A'])
        rules.check_plain_arguments(True, None)


class ThePhone(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = _build(APP, 'filters { gap: 10px; }')
        cls.screen = cls.files['res/layout/activity_screen_home.xml']
        cls.sheet = cls.files['res/layout/sheet_home_filters.xml']
        cls.java = _java(cls.files)

    def test_the_sheet_has_a_layout_of_its_own(self):
        for inside in ('Sort by', 'ApkpyChoice', 'android:hint="Max price"', 'android:text="Apply"'):
            self.assertIn(inside, self.sheet)
            self.assertNotIn(inside, self.screen)
        self.assertIn('android:text="Filters"', self.screen)          # the button that opens it
        self.assertIn('android:id="@+id/btn2"', self.screen)
        self.assertIn('android:id="@+id/btn1"', self.sheet)           # numbered in its turn

    def test_the_handle_the_title_and_the_text(self):
        self.assertIn('android:layout_width="%ddp"' % rules.HANDLE_WIDTH, self.sheet)
        self.assertIn('android:layout_height="%ddp"' % rules.HANDLE_HEIGHT, self.sheet)
        self.assertIn('android:layout_marginTop="%ddp"' % rules.HANDLE_PAD, self.sheet)
        self.assertIn('android:textSize="%dsp"' % rules.TITLE_SIZE, self.sheet)
        self.assertIn('android:text="Choose what the list shows."', self.sheet)
        self.assertTrue(self.sheet.lstrip().startswith('<?xml'))
        self.assertIn('<androidx.core.widget.NestedScrollView xmlns:android=', self.sheet)

    def test_the_body_is_a_stretched_column_with_the_sheets_css(self):
        self.assertIn('direction=column', self.sheet)
        self.assertIn('align=stretch', self.sheet)
        self.assertIn('gap=10', self.sheet)                            # the app's CSS
        self.assertIn('android:paddingLeft="%ddp"' % rules.SIDE, self.sheet)

    def test_round_top_corners_in_the_surface_colour(self):
        shape = self.files['res/drawable/apkpy_sheet_home_filters.xml']
        self.assertIn('android:topLeftRadius="%ddp"' % rules.RADIUS, shape)
        self.assertIn('@color/apkpy_surface', shape)
        self.assertIn('res/drawable/apkpy_sheet_handle.xml', self.files)
        painted = _build(APP, 'filters { background-color: #101418; }')
        self.assertIn('#101418', painted['res/drawable/apkpy_sheet_home_filters.xml'].upper()
                      .replace('#FF101418', '#101418'))

    def test_the_activity_inflates_it_before_anything_is_set_up(self):
        inflate = self.java.index('_apkpySheet_filters = getLayoutInflater().inflate('
                                  'R.layout.sheet_home_filters, null, false);')
        self.assertLess(self.java.index('setContentView(R.layout.activity_screen_home);'), inflate)
        self.assertLess(inflate, self.java.index('findViewById(R.id.chc1)'))

    def test_a_component_in_the_sheet_is_found_like_any_other(self):
        self.assertIn('public <T extends android.view.View> T findViewById(int id) {', self.java)
        self.assertIn('if (found == null && _apkpySheet_filters != null) '
                      'found = _apkpySheet_filters.findViewById(id);', self.java)

    def test_open_and_close(self):
        method = self.java.split('private void _apkpyOpen_filters() {')[1].split('\n    }')[0]
        self.assertIn('dialog.setContentView(_apkpySheet_filters);', method)
        # A new dialog each time, around the same views.
        self.assertIn('new com.google.android.material.bottomsheet.BottomSheetDialog(this);', method)
        self.assertIn('.removeView(_apkpySheet_filters);', method)
        # Material squares the frame on its first layout: the sheet's shape
        # goes on before it and again after it.
        self.assertIn('frame.addOnLayoutChangeListener(', method)
        self.assertEqual(method.count('setBackgroundResource(R.drawable.apkpy_sheet_home_filters);'), 2)
        self.assertEqual(method.count('setBackgroundTintList(null);'), 2)
        self.assertIn('SOFT_INPUT_ADJUST_RESIZE', method)
        self.assertIn('setSkipCollapsed(true)', method)
        self.assertIn('dialog.setTitle("Filters");', method)
        self.assertIn('pythonCallback_closed();', method)               # on_close
        self.assertIn('BottomSheetBehavior.STATE_EXPANDED', method)
        self.assertIn('_apkpyCloseOverlay();', self.java)               # filters.close()

    def test_a_function_above_the_sheet_may_close_it(self):
        # apply() is written before the sheet whose button calls it.
        self.assertLess(APP.index('filters.close()'), APP.index('filters = bottom_sheet'))

    def test_another_screen_does_not_carry_the_sheet(self):
        files = _build(APP + 'other = Screen(id="other")\n'
                             'button("Open", id="far", command=filters.open, screen=other)\n')
        far = _java(files, 'other')
        self.assertNotIn('_apkpySheet_filters', far)
        self.assertIn('private void _apkpyOpen_filters() {', far)
        self.assertIn('belongs to another screen', far)
        self.assertNotIn('sheet_other', ''.join(files))

    def test_a_plain_sheet_is_what_it_was(self):
        files = _build(PLAIN)
        self.assertFalse([name for name in files if 'sheet_' in name])
        java = _java(files)
        self.assertIn('new BottomSheetDialog(this);', java)
        self.assertNotIn('findViewById(int id)', java)

    def test_a_plain_sheet_tells_on_close_too(self):
        files = _build('home = Screen(id="home")\n'
                       'def gone():\n    toast("closed")\n'
                       'sort = bottom_sheet("Sort", items=["A"], on_close=gone)\n'
                       'button("Sort", command=sort.open, screen=home)\n')
        self.assertIn('pythonCallback_gone(); });', _java(files))

    def test_translated_title(self):
        files = _build('translations({"en": {"filters": "Filters"}, "pt": {"filters": "Filtros"}})\n'
                       'home = Screen(id="home")\n'
                       'sheet = bottom_sheet(t("filters"), screen=home)\n'
                       'label("x", parent=sheet)\n'
                       'button("Open", command=sheet.open, screen=home)\n')
        layout = files['res/layout/sheet_home_sheet.xml']
        self.assertRegex(layout, r'android:text="@string/\w*filters"')
        self.assertRegex(_java(files), r'dialog\.setTitle\(getString\(R\.string\.\w*filters\)\);')

    def test_what_is_refused(self):
        for body in ('sheet = bottom_sheet("Share")\nlabel("x", parent=sheet)\n',
                     'sheet = bottom_sheet("Share", items=["A"], screen=home)\n'):
            with self.assertRaises(AssertionError) as caught:
                _build('home = Screen(id="home")\n' + body)
            self.assertIn('U2045', str(caught.exception), body)

    def test_a_container_keeps_out_of_the_page_colour(self):
        # A box with no fill of its own is transparent: inside a sheet it
        # used to paint a band of the page's background.
        files = _build('home = Screen(id="home")\n'
                       'sheet = bottom_sheet("Share", screen=home)\n'
                       'row = container(id="row", parent=sheet)\n'
                       'label("x", parent=row)\n',
                       'body { background-color: #112233; }')
        self.assertNotIn('112233', files['res/layout/sheet_home_sheet.xml'])


class ThePreviewer(unittest.TestCase):

    def _open(self, p, name='filters'):
        p.ns[name].open()
        p.settle(0.6)
        return p.ns[name]._sheet

    def test_the_components_are_in_the_sheet(self):
        with Previewed(APP, '') as p:
            sheet = self._open(p)
            self.assertIsNotNone(sheet)
            for name in ('order', 'budget'):
                widget = p.ns[name].widget
                self.assertEqual(str(widget.winfo_toplevel()), str(sheet.win))
            self.assertEqual(sheet.offset, 0)
            self.assertGreater(sheet.height, 200)
            self.assertLessEqual(sheet.height, rules.max_height(sheet.root_h))
            # It stands on the bottom edge of the app.
            self.assertEqual(sheet.win.winfo_rooty() + sheet.win.winfo_height(),
                             sheet.root_y + sheet.root_h)
            p.ns['filters'].close()

    def test_a_short_drag_goes_back_and_a_long_one_closes(self):
        with Previewed(APP, '') as p:
            sheet = self._open(p)
            sheet.drag_to(sheet.height * 0.3)
            p.settle(0.05)
            self.assertEqual(sheet.win.winfo_rooty(), sheet.rest_y + sheet.offset)
            self.assertEqual(sheet.release(), 'open')
            p.settle(0.5)
            self.assertEqual(sheet.offset, 0)
            self.assertEqual(p.ns['SEEN'], [])
            sheet.drag_to(sheet.height * 0.7)
            self.assertEqual(sheet.release(), 'closed')
            p.settle(0.6)
            self.assertIsNone(p.ns['filters'].widget)
            self.assertEqual(p.ns['SEEN'], ['closed'])

    def test_a_fling_closes_from_anywhere(self):
        with Previewed(APP, '') as p:
            sheet = self._open(p)
            sheet.drag_to(30)
            self.assertEqual(sheet.release(rules.FLING + 1), 'closed')
            p.settle(0.6)
            self.assertIsNone(p.ns['filters'].widget)

    def test_it_does_not_go_up(self):
        with Previewed(APP, '') as p:
            sheet = self._open(p)
            sheet.drag_to(-80)
            self.assertEqual(sheet.offset, 0)
            p.ns['filters'].close()

    def test_a_button_inside_reads_the_sheet_and_closes_it(self):
        with Previewed(APP, '') as p:
            self._open(p)
            p.ns['budget'].set_value('120')
            p.ns['order'].set_value('Price')
            p.ns['apply']()
            p.settle(0.3)
            self.assertEqual(p.ns['shown'].get_value(), 'Price first, up to 120')
            self.assertIsNone(p.ns['filters'].widget)
            self.assertEqual(p.ns['SEEN'], ['closed'])

    def test_what_was_typed_is_there_next_time(self):
        with Previewed(APP, '') as p:
            self._open(p)
            p.ns['budget'].set_value('75')
            p.ns['filters'].close()
            p.settle(0.2)
            self._open(p)
            self.assertEqual(p.ns['budget'].get_value(), '75')
            p.ns['filters'].close()

    def test_a_plain_sheet_still_lists_and_drags(self):
        with Previewed(PLAIN, '') as p:
            sheet = self._open(p, 'sort')
            self.assertFalse(sheet.composed)
            sheet.drag_to(sheet.height)
            self.assertEqual(sheet.release(), 'closed')
            p.settle(0.6)
            self.assertIsNone(p.ns['sort'].widget)

    def test_components_without_a_screen_are_refused(self):
        # At the line that asks, before anything is drawn.
        from apkpy_lib import bottom_sheet, label, modal
        for overlay in (bottom_sheet("Share"), modal("Sure?")):
            with self.assertRaises(ApkpyError) as caught:
                label("x", parent=overlay)
            self.assertEqual(caught.exception.code, 'U2045')


if __name__ == '__main__':
    unittest.main()
