# -*- coding: utf-8 -*-
"""A profile: a header, two buttons that share the row, and a photo grid.

Rebuilding a profile screen (26-09-2026) found three things a real app needs:

* ``virtual_collection(row=..., layout="grid", columns=3)`` drew its cells 10px
  apart in the Previewer -- 5px of padding each side that the phone's
  GridLayoutManager never adds. A photo grid is 1px apart, set by the row.
* A collection in a scrolling screen scrolled inside it, at a fixed 480dp on
  the phone and 520px here. ``height: auto`` makes it as tall as its items, so
  the grid scrolls with the header above it.
* ``flex-grow: 1`` on two buttons in a row: the phone stretched them, the
  Previewer left them the width of their text.
"""

import tkinter as tk
import unittest

from test_real_screens import Previewed, _build, _layouts

PROFILE = (
    'home = Screen(id="home", scroll=True)\n'
    'label("Mara Vale", id="name", screen=home)\n'
    'actions = container(id="actions", screen=home)\n'
    'edit = button("Edit profile", id="edit", parent=actions)\n'
    'share = button("Share profile", id="share", parent=actions)\n'
    'PHOTOS = [{"id": str(i), "picture": ""} for i in range(30)]\n'
    'def tile(row):\n'
    '    container(id="tile", parent=row)\n'
    'grid = virtual_collection(PHOTOS, row=tile, layout="grid", columns=3,\n'
    '                          id="grid", screen=home)\n'
)
PHONE_PROFILE = PROFILE.replace(
    'PHOTOS = [{"id": str(i), "picture": ""} for i in range(30)]\n',
    'PHOTOS = [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}]\n')
CSS = '''
home { padding: 0px; }
actions { display: flex; flex-direction: row; gap: 6px; padding: 0px 16px; }
edit, share { flex-grow: 1; height: 34px; }
grid { height: auto; }
grid_row { padding: 1px; }
tile { height: 40px; background-color: #336699; padding: 0px; }
'''


class ThePhone(unittest.TestCase):

    def test_the_grid_has_three_columns(self):
        java = ''.join(v for k, v in _build(PHONE_PROFILE, CSS).items()
                       if k.endswith('Activity.java'))
        self.assertIn('new GridLayoutManager(this, 3)', java)

    def test_height_auto_grows_with_the_items(self):
        layout = _layouts(_build(PHONE_PROFILE, CSS))['res/layout/activity_screen_home.xml']
        recycler = layout.split('<androidx.recyclerview.widget.RecyclerView')[1].split('/>')[0]
        self.assertIn('android:layout_height="wrap_content"', recycler)
        self.assertIn('android:nestedScrollingEnabled="false"', recycler)

    def test_without_it_the_list_scrolls_inside(self):
        layout = _layouts(_build(PHONE_PROFILE, CSS.replace('grid { height: auto; }', '')))[
            'res/layout/activity_screen_home.xml']
        recycler = layout.split('<androidx.recyclerview.widget.RecyclerView')[1].split('/>')[0]
        self.assertIn('android:layout_height="480dp"', recycler)
        self.assertIn('android:nestedScrollingEnabled="true"', recycler)


class ThePreviewer(unittest.TestCase):

    def test_every_row_is_drawn_and_nothing_scrolls_inside(self):
        with Previewed(PROFILE, CSS) as p:
            canvas = p.widget('grid')
            p.settle(0.8)
            shown = [item for item in canvas.find_all()
                     if canvas.type(item) == 'window'
                     and canvas.itemcget(item, 'state') != 'hidden']
            self.assertEqual(len(shown), 10)          # 30 photos, 3 a row
            region = [float(v) for v in str(canvas.cget('scrollregion')).split()]
            self.assertLessEqual(abs(region[3] - canvas.winfo_height()), 2)
            self.assertGreater(canvas.winfo_height(), 10 * 40)

    def test_cells_are_not_spaced_by_the_previewer(self):
        with Previewed(PROFILE, CSS) as p:
            canvas = p.widget('grid')
            rows = [canvas.nametowidget(canvas.itemcget(item, 'window'))
                    for item in canvas.find_all() if canvas.type(item) == 'window']
            cell = rows[0].grid_slaves(row=0, column=0)[0]
            info = cell.grid_info()
            self.assertEqual((str(info['padx']), str(info['pady'])), ('0', '0'))

    def test_an_empty_box_has_its_height(self):
        # A tile, a spacer, a colour bar: nothing inside to measure. The
        # Previewer drew it 1px tall; layout_height gives it 40dp.
        with Previewed('home = Screen(id="home")\nbox = container(id="tile", screen=home)\n',
                       CSS) as p:
            self.assertEqual(p.widget('box').winfo_height(), 40)

    def test_growing_buttons_share_the_row(self):
        with Previewed(PROFILE, CSS) as p:
            edit, share = p.widget('edit'), p.widget('share')
            self.assertLessEqual(abs(edit.winfo_width() - share.winfo_width()), 2)
            # 411px wide, 16px padding each side, 6px gap: ~186px each.
            self.assertGreater(edit.winfo_width(), 150)


if __name__ == '__main__':
    unittest.main()
