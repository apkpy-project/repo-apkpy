# -*- coding: utf-8 -*-
"""The Previewer's status strip: signal, wifi and battery.

They used to be the string ``"▮▮▮  ▲  ▮▮▮"`` -- whatever bars and triangle
the system font happened to carry, at whatever size it happened to draw them --
and read as a row of dashes. They are vectors now, on the icon catalogue's
24x24 grid and through the same antialiasing rasteriser, so what is worth
pinning is the two things a hand edit breaks silently: the band they share,
which is the whole reason they line up, and the winding that makes the battery
a battery instead of a pill.
"""

import unittest

from apkpy_lib import icons as _icons
from apkpy_lib import ui


def _points(name):
    return [point
            for subpaths, _hollow in ui._status_glyph_layers(name)
            for subpath in subpaths
            for point in subpath]


def _signed_area(points):
    """Shoelace. The sign is the direction the outline was drawn in."""
    total = 0.0
    for i in range(len(points)):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % len(points)]
        total += x0 * y1 - x1 * y0
    return total / 2.0


class OneBandForAllThree(unittest.TestCase):
    """They line up because they share a band, not because each was nudged."""

    def test_every_glyph_fills_the_same_width(self):
        for name in ui.STATUS_GLYPH_ORDER:
            xs = [x for x, _ in _points(name)]
            self.assertAlmostEqual(min(xs), 3.0, places=1, msg=name)
            self.assertAlmostEqual(max(xs), 21.0, places=1, msg=name)

    def test_every_glyph_stays_inside_the_band(self):
        # Drawn at one size and laid out at one pitch, a glyph that grew taller
        # than the band would sit off the clock's centre line with nothing to
        # say so.
        for name in ui.STATUS_GLYPH_ORDER:
            ys = [y for _, y in _points(name)]
            self.assertGreaterEqual(min(ys), 8.5, name)
            self.assertLessEqual(max(ys), 18.9, name)

    def test_the_signal_bars_ascend(self):
        bars = ui._status_glyph_layers('signal')[0][0]
        self.assertEqual(len(bars), 4)
        by_height = sorted((min(y for _, y in bar), min(x for x, _ in bar))
                           for bar in bars)
        # Tallest first, and the tallest bar is the rightmost one.
        self.assertEqual([x for _, x in by_height],
                         sorted(x for _, x in by_height)[::-1])


class TheBatteryIsHollow(unittest.TestCase):
    """A battery filled in solid is a pill, and reads as one."""

    def test_the_hollow_is_wound_against_the_shell(self):
        # nonZero fills whatever two same-direction outlines overlap on.
        # Reversing the points is the whole of what turns the inner rectangle
        # into a hole.
        layers = ui._status_glyph_layers('battery')
        hollow = [subpaths for subpaths, is_hollow in layers if is_hollow]
        self.assertEqual(len(hollow), 1)
        self.assertLess(_signed_area(hollow[0][0])
                        * _signed_area(layers[0][0][0]), 0)

    def test_it_reads_as_a_battery_once_rasterised(self):
        parts = [subpath
                 for subpaths, _hollow in ui._status_glyph_layers('battery')
                 for subpath in subpaths]
        coverage = _icons.rasterize(parts, 24, supersample=4)

        def at(x, y):
            return coverage[y * 24 + x]

        self.assertEqual(at(3, 13), 255)    # the shell's left wall
        self.assertEqual(at(10, 13), 255)   # the charge inside it
        self.assertEqual(at(16, 13), 0)     # the gap the charge stops at
        self.assertEqual(at(20, 13), 255)   # the terminal on the right
        self.assertEqual(at(22, 13), 0)     # and nothing past it


class TheColourIsTheScreensColour(unittest.TestCase):

    def test_a_named_colour_falls_back_to_the_canvas(self):
        # _hex_to_rgb answers a colour name with its dark fallback, which on a
        # dark strip is invisible ink. Tk resolves names itself, so the polygon
        # path takes those.
        self.assertIsNone(ui._status_glyph_photo('signal', 'white'))


if __name__ == '__main__':
    unittest.main()
