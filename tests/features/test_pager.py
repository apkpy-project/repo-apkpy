# -*- coding: utf-8 -*-
"""pager() and tab(): tabs over pages that swipe, on both runtimes.

A profile has Posts / Reels / Tagged over one space, a chat app Chats /
Status / Calls; ApkPy had bottom_nav (screens) and nothing for tabs inside a
screen. A pager is a container and each tab() a page inside it:

    tabs = pager(id="tabs", screen=home)
    posts = tab("Posts", icon="grid_on", parent=tabs)
    label("...", parent=posts)

The phone gets Material's TabLayout over ApkpyPager, a fixed class that lays
the pages side by side, follows a finger and takes the height of the page on
screen; the Previewer draws the same strip and slides the same pages.
"""

import tkinter as tk
import unittest

from apkpy_lib import ui
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.theme import pager_colors, tab_bar_height

from test_real_screens import Previewed, _build, _layouts

APP = (
    'home = Screen(id="home", scroll=True)\n'
    'label("Profile", id="title", screen=home)\n'
    'tabs = pager(id="tabs", screen=home)\n'
    'posts = tab("Posts", icon="grid_on", id="posts", parent=tabs)\n'
    'reels = tab("Reels", icon="slideshow", id="reels", parent=tabs)\n'
    'saved = tab("Saved", icon="bookmark_border", id="saved", parent=tabs)\n'
    'first = label("First page", id="one", parent=posts)\n'
    'label("Second page", id="two", parent=reels)\n'
    'container(id="tall", parent=saved)\n'
    'def go():\n'
    '    tabs.select(2)\n'
    'button("Saved", id="go", command=go, screen=home)\n'
)
CSS = '''
tabs { active-color: #111111; color: #999999; indicator-color: #FF3040; border-color: #DDDDDD; }
tall { height: 300px; }
'''


def _activity(files):
    return ''.join(v for k, v in files.items() if k.endswith('Activity.java'))


class ThePhone(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = _build(APP, CSS)
        cls.layout = _layouts(cls.files)['res/layout/activity_screen_home.xml']
        cls.java = _activity(cls.files)

    def test_the_strip_the_line_and_the_pages(self):
        layout = self.layout
        self.assertIn('<com.google.android.material.tabs.TabLayout', layout)
        self.assertIn('android:id="@+id/pgr1_tabs"', layout)
        self.assertIn('android:layout_height="72dp"', layout)   # icons above text
        self.assertIn('android:id="@+id/pgr1_divider"', layout)
        pager = layout.split('<com.apkpy.app.ApkpyPager')[1].split('</com.apkpy.app.ApkpyPager>')[0]
        # One page per tab (the Saved page holds a container of its own).
        self.assertEqual(pager.count('<LinearLayout'), 4)
        self.assertIn('android:layout_height="300dp"', pager)
        self.assertIn('First page', pager)
        self.assertIn('Second page', pager)

    def test_the_class_ships_only_with_a_pager(self):
        self.assertIn('java/ApkpyPager.java', self.files)
        plain = _build('home = Screen(id="home")\nlabel("x", screen=home)\n')
        self.assertNotIn('java/ApkpyPager.java', plain)

    def test_the_activity_hands_over_the_tabs(self):
        java = self.java
        self.assertIn('ApkpyPager pgr1 = findViewById(R.id.pgr1);', java)
        self.assertIn('new String[]{"Posts", "Reels", "Saved"}', java)
        self.assertIn('R.drawable.ic_tab_home_', java)
        self.assertIn('android.graphics.Color.parseColor("#111111")', java)
        self.assertIn('android.graphics.Color.parseColor("#FF3040")', java)

    def test_each_tab_icon_is_a_white_vector(self):
        icons = [k for k in self.files if k.startswith('res/drawable/ic_tab_home_')]
        self.assertEqual(len(icons), 3)
        self.assertIn('#FFFFFF', self.files[icons[0]])

    def test_select_slides_to_a_page(self):
        self.assertIn('((ApkpyPager) findViewById(R.id.pgr1)).select(2, true);', self.java)

    def test_a_component_in_a_page_keeps_its_id(self):
        # The page's label is found like any other: its id is in the layout
        # the Activity inflates, inside the pager.
        self.assertIn('android:text="First page"', self.layout)

    def test_a_tab_needs_a_pager(self):
        source = ('from apkpy_lib import *\nhome = Screen(id="home")\n'
                  'box = container(id="box", screen=home)\n'
                  'tab("Lost", parent=box)\nrun(start_screen=home)\n')
        files = translate_python_to_android(source)
        self.assertIn('U2040', files.get('error.txt', ''))
        self.assertIn('tab() needs a pager() as its parent.', files['error.txt'])

    def test_the_java_class_compiles_in_spirit(self):
        java = self.files['java/ApkpyPager.java']
        self.assertIn('package com.apkpy.app;', java)
        self.assertIn('public void select(int index, boolean animate)', java)
        self.assertIn('public void attachTabs(TabLayout strip', java)


class TheSharedRule(unittest.TestCase):

    def test_colours(self):
        colors = pager_colors({'primary': '#123456'}, {'color': '#999999'})
        self.assertEqual(colors['active'], '#123456')
        self.assertEqual(colors['indicator'], '#123456')
        self.assertEqual(colors['inactive'], '#999999')
        self.assertEqual(colors['background'], '')          # the screen shows through
        self.assertEqual(colors['divider'], '')              # no line unless asked

    def test_heights(self):
        self.assertEqual(tab_bar_height(True, False), 48)
        self.assertEqual(tab_bar_height(False, True), 48)
        self.assertEqual(tab_bar_height(True, True), 72)


class ThePreviewer(unittest.TestCase):

    def _viewport(self, p):
        outer = p.widget('tabs')
        return [w for w in outer.winfo_children() if isinstance(w, tk.Frame)][-1]

    def test_the_strip_has_a_cell_per_tab(self):
        with Previewed(APP, CSS) as p:
            strip = p.widget('tabs').winfo_children()[0]
            cells = [w for w in strip.winfo_children() if isinstance(w, tk.Canvas)]
            self.assertEqual(len(cells), 3)
            self.assertEqual(strip.winfo_height(), 72)

    def test_select_moves_the_page_and_the_height_follows_it(self):
        with Previewed(APP, CSS) as p:
            viewport = self._viewport(p)
            short = viewport.winfo_height()
            p.ns['tabs'].select(2)
            p.settle(0.9)
            self.assertEqual(p.ns['tabs']._current_page, 2)
            self.assertGreater(viewport.winfo_height(), short)
            self.assertGreaterEqual(viewport.winfo_height(), 300)
            saved_page = p.ns['saved'].widget
            self.assertEqual(saved_page.winfo_x(), 0)            # on screen
            self.assertLess(p.ns['posts'].widget.winfo_x(), 0)  # off to the left

    def test_a_drag_goes_to_the_next_page(self):
        with Previewed(APP, CSS) as p:
            page = p.ns['first'].widget
            x, y = page.winfo_rootx() + 150, page.winfo_rooty() + 5
            page.event_generate('<ButtonPress-1>', x=5, y=5, rootx=x, rooty=y)
            for step in range(1, 11):
                page.event_generate('<B1-Motion>', x=5, y=5, rootx=x - step * 20, rooty=y)
            page.event_generate('<ButtonRelease-1>', x=5, y=5, rootx=x - 200, rooty=y)
            p.settle(0.9)
            self.assertEqual(p.ns['tabs']._current_page, 1)

    def test_a_small_drag_stays(self):
        with Previewed(APP, CSS) as p:
            page = p.ns['first'].widget
            x, y = page.winfo_rootx() + 150, page.winfo_rooty() + 5
            page.event_generate('<ButtonPress-1>', x=5, y=5, rootx=x, rooty=y)
            page.event_generate('<B1-Motion>', x=5, y=5, rootx=x - 40, rooty=y)
            page.event_generate('<ButtonRelease-1>', x=5, y=5, rootx=x - 40, rooty=y)
            p.settle(0.9)
            self.assertEqual(p.ns['tabs']._current_page, 0)

    def test_a_tab_outside_a_pager_is_refused(self):
        with self.assertRaises(ValueError):
            ui.tab("Lost", parent=ui.container(id="box"))


if __name__ == '__main__':
    unittest.main()
