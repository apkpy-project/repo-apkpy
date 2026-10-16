# -*- coding: utf-8 -*-
"""The space around and between a screen's own components.

A profile rebuilt for 1.12.0, side by side with the phone (27-09-2026), began
its photo grid 32px higher in the Previewer:

* the screen's ``gap`` -- 12px from a Theme's body -- was a margin on every
  child but the first on the phone, and nothing at all in the Previewer, which
  only spaced a container's children;
* a screen with no padding had 5px above and below and 10px at the sides on
  the phone, and 12px on top only in the Previewer -- still there under
  ``padding: 0px``, where the phone starts at the edge;
* a label's own 2px above and below, which stand in for the phone's 6dp
  between stacked children, stayed on when a gap took their place.

The music grid beside it had square 150px covers; the phone's are the card's
width and 110dp tall.
"""

import tkinter as tk
import unittest

from test_real_screens import Previewed, _build, _layouts

BODY = (
    'home = Screen(id="home")\n'
    'top = container(id="top", screen=home)\n'
    'mid = container(id="mid", screen=home)\n'
    'first = label("Mara Vale", id="first", screen=home)\n'
    'second = label("Photographer in Lisbon.", id="second", screen=home)\n'
)
BLOCKS = 'top, mid { height: 40px; padding: 0px; background-color: #336699; }\n'
SPACED = 'home { padding: 0px; gap: 12px; }\n' + BLOCKS


def _gap_between(upper, lower):
    return lower.winfo_rooty() - (upper.winfo_rooty() + upper.winfo_height())


class ThePhone(unittest.TestCase):

    def test_every_child_but_the_first_gets_the_gap(self):
        layout = _layouts(_build(BODY, SPACED))['res/layout/activity_screen_home.xml']
        top = layout.split('android:id="@+id/cnt1"')[1].split('>')[0]
        mid = layout.split('android:id="@+id/cnt2"')[1].split('>')[0]
        self.assertNotIn('layout_marginTop', top)
        self.assertIn('android:layout_marginTop="12dp"', mid)

    def test_no_padding_is_five_and_ten(self):
        layout = _layouts(_build(BODY, BLOCKS))['res/layout/activity_screen_home.xml']
        self.assertIn('android:paddingLeft="10dp" android:paddingTop="5dp" '
                      'android:paddingRight="10dp" android:paddingBottom="5dp"', layout)


class ThePreviewer(unittest.TestCase):

    def test_the_gap_goes_between_the_screens_children(self):
        with Previewed(BODY, SPACED) as p:
            self.assertEqual(_gap_between(p.widget('top'), p.widget('mid')), 12)

    def test_padding_zero_starts_at_the_edge(self):
        with Previewed(BODY, SPACED) as p:
            self.assertEqual(p.widget('top').winfo_rooty(), p.app.layout.winfo_rooty())

    def test_no_padding_is_five_and_ten_here_too(self):
        with Previewed(BODY, BLOCKS) as p:
            top = p.widget('top')
            self.assertEqual(top.winfo_rooty() - p.app.layout.winfo_rooty(), 5)
            self.assertEqual(top.winfo_rootx() - p.app.layout.winfo_rootx(), 10)

    def test_a_label_on_a_spaced_screen_is_the_gap_away(self):
        with Previewed(BODY, SPACED) as p:
            self.assertEqual(_gap_between(p.widget('first'), p.widget('second')), 12)

    def test_without_a_gap_labels_keep_their_breathing(self):
        with Previewed(BODY, BLOCKS) as p:
            self.assertEqual(_gap_between(p.widget('first'), p.widget('second')), 4)


class TheCardGridCover(unittest.TestCase):

    def test_the_cover_is_the_cards_width_and_110_tall(self):
        body = ('home = Screen(id="home")\n'
                'grid([{"title": "Night Drive", "subtitle": "Mara Vale", "image": ""},\n'
                '      {"title": "Lisbon Rain", "subtitle": "Signal Club", "image": ""}],\n'
                '     id="recent", cols=2, screen=home)\n')
        with Previewed(body, 'home { padding: 16px; }') as p:
            covers = []
            pending = [p.app.layout]
            while pending:
                widget = pending.pop()
                pending.extend(widget.winfo_children())
                if isinstance(widget, tk.Canvas) and widget.winfo_height() == 110:
                    covers.append(widget)
            self.assertEqual(len(covers), 2)
            for cover in covers:
                self.assertEqual(cover.winfo_width(), cover.master.winfo_width())
                self.assertGreater(cover.winfo_width(), 150)


if __name__ == '__main__':
    unittest.main()
