# -*- coding: utf-8 -*-
"""The navigation drawer.

The panel that slides in from the leading edge, and the last thing on the list
that was outright impossible rather than merely unstyled. A `bottom_nav` runs
out at five destinations; a drawer is what every assistant, mail client and
reader reaches for after that.

The shape is deliberately the same as the bottom bar's: one declaration for the
whole app, screens listed in order, and each item starting the Activity it
names. What these tests hold down is the wrapping -- a DrawerLayout takes its
content child first and its panels after, and getting that backwards gives you
a panel that covers the app permanently.
"""

import unittest

from apkpy_lib import icons
from apkpy_lib.core.compiler import (
    _drawer_item_id,
    _generate_drawer_item_color_xml,
    _generate_drawer_menu_xml,
    translate_python_to_android,
)


APP = '''
from apkpy_lib import Screen, Theme, action, app_bar, drawer, label, run
chat = Screen(id="chat")
projects = Screen(id="projects")
menu = drawer(
    [chat, projects],
    labels=["New chat", "Projects"],
    icons=["add", "folder"],
    header="Ora",
    subtitle="you@example.com",
)
app_bar("New chat", leading=action("menu", command=lambda: menu.open()),
        screen=chat)
app_bar("Projects", leading=action("menu", command=lambda: menu.open()),
        screen=projects)
label("x", id="t", screen=chat)
label("y", id="u", screen=projects)
run(start_screen=chat, theme=Theme(mode="dark"))
'''


def _build(source=APP):
    result = translate_python_to_android(source)
    assert 'error.txt' not in result, result['error.txt'][:500]
    return result


class DrawerLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = _build()
        cls.xml = cls.out['res/layout/activity_screen_chat.xml']
        cls.java = cls.out['java/Screen_chatActivity.java']

    def test_the_screen_goes_inside_the_panel_s_container(self):
        self.assertTrue(
            self.xml.startswith('<?xml version="1.0" encoding="utf-8"?>\n'
                                '<androidx.drawerlayout.widget.DrawerLayout'),
            self.xml[:200])
        self.assertTrue(
            self.xml.rstrip().endswith(
                '</androidx.drawerlayout.widget.DrawerLayout>'))

    def test_the_content_comes_before_the_panel(self):
        # Backwards and the panel covers the app for good: DrawerLayout takes
        # its content child first and its drawers after.
        content = self.xml.index('<androidx.coordinatorlayout')
        panel = self.xml.index('<com.google.android.material.navigation')
        self.assertLess(content, panel)

    def test_the_panel_hangs_off_the_leading_edge(self):
        panel = self.xml.split(
            '<com.google.android.material.navigation.NavigationView')[1]
        self.assertIn('android:layout_gravity="start"', panel)
        self.assertIn('app:menu="@menu/apkpy_drawer_menu"', panel)

    def test_a_header_only_appears_when_one_was_asked_for(self):
        self.assertIn('app:headerLayout="@layout/apkpy_drawer_header"',
                      self.xml)
        self.assertIn('res/layout/apkpy_drawer_header.xml', self.out)
        bare = _build(APP.replace('header="Ora",', '')
                         .replace('subtitle="you@example.com",', ''))
        self.assertNotIn('res/layout/apkpy_drawer_header.xml', bare)
        self.assertNotIn(
            'headerLayout', bare['res/layout/activity_screen_chat.xml'])

    def test_an_app_without_a_drawer_is_untouched(self):
        plain = _build('''
from apkpy_lib import Screen, label, run
home = Screen(id="home")
label("x", id="t", screen=home)
run(start_screen=home)
''')
        layout = plain['res/layout/activity_screen_home.xml']
        self.assertNotIn('DrawerLayout', layout)
        self.assertFalse([k for k in plain if 'drawer' in k])


class DrawerBehaviourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = _build()
        cls.java = cls.out['java/Screen_chatActivity.java']

    def test_menu_open_reaches_the_panel(self):
        # The app bar's leading icon exists already; what it lacked was
        # something to open.
        self.assertIn('_apkpyDrawer(true);', self.java)
        self.assertIn('private void _apkpyDrawer(boolean open)', self.java)

    def test_the_open_screen_is_the_checked_item(self):
        self.assertIn('setCheckedItem(R.id.drawer_chat);', self.java)

    def test_an_item_starts_the_activity_it_names(self):
        self.assertIn('setNavigationItemSelectedListener', self.java)
        self.assertIn('R.id.drawer_projects', self.java)
        self.assertIn('Screen_projectsActivity.class', self.java)
        # Its own screen is not in the list: tapping it would restart the
        # Activity you are already looking at.
        self.assertNotIn('Screen_chatActivity.class);', self.java)

    def test_the_panel_closes_before_it_navigates(self):
        listener = self.java.split('setNavigationItemSelectedListener')[1]
        close = listener.index('_apkpyDrawer(false);')
        start = listener.index('startActivity')
        self.assertLess(close, start)

    def test_back_closes_the_panel_before_leaving_the_screen(self):
        # DrawerLayout does not do this on its own, and every Android user
        # expects it. Through the dispatcher: an app that targets Android 16
        # is not handed onBackPressed() there (see test_android_16.py).
        self.assertNotIn('onBackPressed()', self.java)
        self.assertIn('new androidx.activity.OnBackPressedCallback(false)', self.java)
        self.assertIn('handleOnBackPressed() { _apkpyDrawer(false); }', self.java)
        self.assertIn('getOnBackPressedDispatcher().addCallback(this, _apkpyDrawerBack);',
                      self.java)
        # On only while the panel shows, so Back leaves the screen otherwise.
        self.assertIn('_apkpyDrawerBack.setEnabled(_shown > 0f);', self.java)
        self.assertIn('isDrawerVisible(androidx.core.view.GravityCompat.START)',
                      self.java)

    def test_the_generated_java_is_balanced(self):
        self.assertEqual(self.java.count('{'), self.java.count('}'))


class DrawerResourceTests(unittest.TestCase):
    def test_one_group_so_the_open_screen_stays_highlighted(self):
        xml = _generate_drawer_menu_xml(
            {'screen_ids': ['chat', 'projects'],
             'labels': ['New chat', 'Projects']})
        self.assertIn('android:checkableBehavior="single"', xml)
        self.assertEqual(xml.count('<item '), 2)

    def test_item_ids_are_legal_and_distinct(self):
        self.assertEqual(_drawer_item_id('chat'), 'drawer_chat')
        self.assertNotEqual(_drawer_item_id('a b'), _drawer_item_id('a-c'))

    def test_the_tint_gives_the_open_screen_the_accent(self):
        xml = _generate_drawer_item_color_xml('#C96442', '#F5F4EF')
        self.assertIn('android:state_checked="true" android:color="#C96442"',
                      xml)
        self.assertIn('<item android:color="#F5F4EF" />', xml)

    def test_every_item_ships_its_icon(self):
        out = _build()
        for sid in ('chat', 'projects'):
            self.assertIn('res/drawable/ic_drawer_%s.xml' % sid, out)

    def test_the_icons_a_drawer_reaches_for_exist(self):
        for name in ('add', 'folder', 'description', 'menu'):
            self.assertIsNotNone(icons.resolve(name), name)


if __name__ == '__main__':
    unittest.main()
