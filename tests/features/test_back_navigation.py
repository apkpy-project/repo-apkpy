# -*- coding: utf-8 -*-
"""Leaving a screen: the app bar's back arrow, on both sides.

Android gets this for free. Every `Screen` is an Activity, and the generator
writes `finish()` into the toolbar's navigation listener when the leading
action is an `arrow_back` with no command of its own -- so tapping it returns
to whichever screen started this one.

The Previewer swaps one widget tree for another and remembered nothing. The
arrow was drawn, with no cursor and no binding, and a settings screen was
something you could open and not leave. These tests pin the history the
Previewer now keeps, and the condition both sides use to decide that an arrow
means "go back".
"""

import unittest

from apkpy_lib.core.compiler import translate_python_to_android


class _Screen:
    """The part of a Screen this history cares about: its identity."""

    def __init__(self, name):
        self.id = name

    def __repr__(self):                      # pragma: no cover - debugging aid
        return '<%s>' % self.id


class _History:
    """The Previewer's stack, exercised without opening a window.

    `AppPreview.__init__` builds a Tk root, so the methods are borrowed onto a
    bare object: what is under test is the bookkeeping, not the widgets.
    """

    def __init__(self):
        from apkpy_lib.ui import AppPreview
        self._active_screen = None
        self._screen_stack = []
        self._remember = AppPreview._remember_for_back.__get__(self)
        self._back = AppPreview.go_back.__get__(self)
        self.rendered = []

    def render_screen(self, screen, transition=None, _from_back=False):
        if not _from_back:
            self._remember(screen)
        self._active_screen = screen
        self.rendered.append(screen.id)

    def go_back(self):
        return self._back()

    @property
    def behind(self):
        return [s.id for s in self._screen_stack]


class PreviewerKeepsAHistory(unittest.TestCase):

    def setUp(self):
        self.app = _History()
        self.home = _Screen('home')
        self.you = _Screen('you')
        self.model = _Screen('model')

    def test_the_first_screen_stacks_nothing(self):
        self.app.render_screen(self.home)
        self.assertEqual(self.app.behind, [])

    def test_forward_navigation_stacks_where_it_came_from(self):
        self.app.render_screen(self.home)
        self.app.render_screen(self.you)
        self.app.render_screen(self.model)
        self.assertEqual(self.app.behind, ['home', 'you'])

    def test_back_unwinds_one_screen_at_a_time(self):
        for screen in (self.home, self.you, self.model):
            self.app.render_screen(screen)
        self.assertTrue(self.app.go_back())
        self.assertIs(self.app._active_screen, self.you)
        self.assertTrue(self.app.go_back())
        self.assertIs(self.app._active_screen, self.home)

    def test_back_at_the_root_does_nothing_rather_than_closing(self):
        self.app.render_screen(self.home)
        self.assertFalse(self.app.go_back())
        self.assertIs(self.app._active_screen, self.home)

    def test_going_back_does_not_re_stack_the_screen_it_left(self):
        self.app.render_screen(self.home)
        self.app.render_screen(self.you)
        self.app.go_back()
        self.assertEqual(self.app.behind, [])

    def test_re_rendering_the_same_screen_is_not_navigation(self):
        # A window resize re-renders the active screen; it is not a trip.
        self.app.render_screen(self.home)
        self.app.render_screen(self.home)
        self.assertEqual(self.app.behind, [])

    def test_a_tab_already_open_is_brought_forward_not_stacked(self):
        # FLAG_ACTIVITY_REORDER_TO_FRONT is what a bottom_nav uses on Android.
        # Without this, hopping between two tabs grows the history forever.
        for _ in range(6):
            self.app.render_screen(self.home)
            self.app.render_screen(self.you)
        self.assertEqual(self.app.behind, ['home'])

    def test_returning_to_a_screen_below_drops_what_was_above_it(self):
        for screen in (self.home, self.you, self.model):
            self.app.render_screen(screen)
        self.app.render_screen(self.home)
        self.assertEqual(self.app.behind, [])
        self.assertIs(self.app._active_screen, self.home)


class SystemBackHasAStandIn(unittest.TestCase):
    """Alt+Left, because a screen without an arrow is leaveable on a phone."""

    def setUp(self):
        self.app = _History()
        self.app._drawer_panel = None
        from apkpy_lib.ui import AppPreview
        self.app.close_drawer = self._close_drawer
        self.app._system_back = AppPreview._system_back.__get__(self.app)
        self.closed = []
        self.home = _Screen('home')
        self.you = _Screen('you')

    def _close_drawer(self):
        self.closed.append(True)
        self.app._drawer_panel = None

    def test_it_leaves_the_screen(self):
        self.app.render_screen(self.home)
        self.app.render_screen(self.you)
        self.app._system_back()
        self.assertIs(self.app._active_screen, self.home)

    def test_an_open_drawer_closes_first(self):
        # Android's order: Back dismisses the panel before it leaves.
        self.app.render_screen(self.home)
        self.app.render_screen(self.you)
        self.app._drawer_panel = object()
        self.app._system_back()
        self.assertEqual(self.closed, [True])
        self.assertIs(self.app._active_screen, self.you)

    def test_it_stops_the_event_rather_than_letting_it_through(self):
        self.app.render_screen(self.home)
        self.assertEqual(self.app._system_back(), 'break')

    def test_escape_is_left_to_the_overlays(self):
        # A modal binds Escape itself; one that both closed and navigated
        # would be worse than no shortcut.
        import inspect
        from apkpy_lib import ui
        source = inspect.getsource(ui.AppPreview.__init__)
        self.assertIn("bind_all('<Alt-Left>'", source)
        self.assertNotIn("bind_all('<Escape>'", source)


class AndroidFinishesOnTheSameCondition(unittest.TestCase):
    """The rule is the icon name and nothing else, so both sides agree."""

    SOURCE = '''
from apkpy_lib import Screen, action, app_bar, label, run
home = Screen(id="home")
app_bar("Settings", leading=action("%s", label="Back"), screen=home)
label("Body", id="b", screen=home)
run(start_screen=home)
'''

    def _java(self, icon):
        files = translate_python_to_android(self.SOURCE % icon)
        self.assertNotIn('error.txt', files, files.get('error.txt', '')[:200])
        return files['java/Screen_homeActivity.java']

    def test_a_back_arrow_with_no_command_finishes(self):
        java = self._java('arrow_back')
        self.assertIn('setNavigationOnClickListener', java)
        self.assertIn('finish();', java)

    def test_another_leading_icon_with_no_command_does_not(self):
        # close is a leading icon too, and it has no meaning of its own -- the
        # Previewer must not invent one either.
        java = self._java('close')
        self.assertNotIn('setNavigationOnClickListener', java)

    def test_the_previewer_reads_the_same_icon_name(self):
        import inspect
        from apkpy_lib import ui
        source = inspect.getsource(ui.AppPreview._render_app_bar)
        self.assertIn("leading_icon == 'arrow_back'", source)
        self.assertIn('self.go_back', source)


class BackFindsTheScrollItLeft(unittest.TestCase):
    """On the phone the Activity under the one on top stays as it was, so Back
    lands where the list was left. The Previewer drew the screen again from
    the top, and a long feed lost its place each time a post was opened."""

    BODY = '''
feed = Screen(id="feed", scroll=True)
detail = Screen(id="detail", scroll=True)
other = Screen(id="other", scroll=True)
for n in range(60):
    label("Post number %d" % n, screen=feed)
for n in range(40):
    label("Detail line %d" % n, screen=detail)
    label("Other line %d" % n, screen=other)
'''

    def setUp(self):
        from test_real_screens import Previewed
        self.view = Previewed(self.BODY, '', screen='feed').__enter__()
        self.app = self.view.app

    def tearDown(self):
        self.view.__exit__()

    def open(self, name):
        self.app.render_screen(self.view.ns[name])
        self.view.settle(0.1)

    def back(self):
        self.app.go_back()
        self.view.settle(0.1)

    def scroll(self, pixels):
        from apkpy_lib import ui
        ui._reload_scroll_to(self.app._scroll_canvas, pixels)
        self.view.settle(0.1)

    def where(self):
        from apkpy_lib import ui
        self.app.root.update_idletasks()
        return round(ui._reload_scrolled_by(self.app._scroll_canvas))

    def test_back_lands_where_the_list_was_left(self):
        self.scroll(600)
        self.open('detail')
        self.assertEqual(self.where(), 0)
        self.scroll(200)
        self.back()
        self.assertEqual(self.where(), 600)

    def test_a_screen_opened_again_starts_at_the_top(self):
        # A new Activity each time: the detail read before is not where the
        # next one opens.
        self.scroll(600)
        self.open('detail')
        self.scroll(200)
        self.back()
        self.open('detail')
        self.assertEqual(self.where(), 0)
        self.back()
        self.assertEqual(self.where(), 600)

    def test_the_same_screen_drawn_again_stays_put(self):
        # A turn of the phone, a new theme or a new language draws the screen
        # again; a ScrollView with an id keeps its place through all three.
        self.scroll(600)
        self.app.render_screen(self.app._active_screen)
        self.view.settle(0.1)
        self.assertEqual(self.where(), 600)

    def test_a_screen_brought_forward_keeps_its_place(self):
        # The bottom bar's tabs: going to a screen already behind brings it
        # forward with its scroll, as FLAG_ACTIVITY_REORDER_TO_FRONT does.
        self.scroll(600)
        self.open('detail')
        self.scroll(200)
        self.open('other')
        self.open('feed')
        self.assertEqual(self.where(), 600)

    def test_a_reload_carries_the_screens_behind(self):
        from apkpy_lib import ui
        self.scroll(600)
        self.open('detail')
        self.scroll(120)
        state = ui._reload_state(self.app)
        self.assertEqual(state['behind'], {'feed': 600})
        self.assertEqual(state['scroll'], 120)


if __name__ == '__main__':
    unittest.main()
