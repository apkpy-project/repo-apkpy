# -*- coding: utf-8 -*-
"""The Previewer's rounded shapes, drawn the way the phone draws them.

People trying ApkPy called the Previewer's buttons "ugly and pixelated" and
took them for what Android would show -- while the same app on a phone looked
right. Rebuilding six well-known screens (25-09-2026) showed why:

* Tk fills a polygon without antialiasing on Windows: every rounded button,
  card and field had stepped edges. Shapes are now images, their corners drawn
  at 4x and scaled down, like the icons.
* A button's CSS ``width``/``height`` never reached the code that draws it: a
  76x76 ring came out as a pill the width of its text.
* ``#AARRGGBB`` lost its alpha, so a glass button (``#33FFFFFF``) was an opaque
  white disc hiding its white icon.
* A rounded image's border was Tk's square highlight frame: a round avatar
  with a ring sat inside a square.

Pinned here, including that the press tint and the theme fade, which change a
shape's colour after it is drawn, still work on an image.
"""

import os
import tkinter as tk
import unittest
from unittest import mock

from apkpy_lib import ui


def _root():
    try:
        root = tk.Tk()
    except tk.TclError as exc:          # no display
        raise unittest.SkipTest(str(exc))
    root.withdraw()
    return root


class ColoursKeepTheirMeaning(unittest.TestCase):

    def test_an_eight_digit_colour_is_read_as_its_colour(self):
        self.assertEqual(ui._hex_to_rgb('#33FFFFFF'), (255, 255, 255))
        self.assertEqual(ui._hex_to_rgb('#80112233'), (0x11, 0x22, 0x33))
        self.assertEqual(ui._hex_to_rgb('#8F00'), (255, 0, 0))

    def test_partial_alpha(self):
        self.assertTrue(ui._partial_alpha('#33FFFFFF'))
        self.assertTrue(ui._partial_alpha('#8FFF'))
        for opaque_or_clear in ('#FFFFFFFF', '#00000000', '#ffffff', 'white', '', None):
            self.assertFalse(ui._partial_alpha(opaque_or_clear), opaque_or_clear)


class TheButtonHasTheSizeTheStylesheetGave(unittest.TestCase):

    def test_absolute_sizes(self):
        self.assertEqual(ui._button_css_size({'width': '76px', 'height': '76px'}), (76, 76))
        self.assertEqual(ui._button_css_size({'width': '48dp'}), (48, None))

    def test_percentages_and_nothing_keep_the_old_behaviour(self):
        self.assertEqual(ui._button_css_size({'width': '100%'}), (None, None))
        self.assertEqual(ui._button_css_size({}), (None, None))
        self.assertEqual(ui._button_css_size({'height': 'auto'}), (None, None))

    def test_a_ring_is_as_wide_as_it_is_tall(self):
        root = _root()
        try:
            host = tk.Frame(root)
            host.pack()
            app = mock.Mock(root=root, layout=host, _bg='#000000')
            draw = ui.AppPreview._draw_material_button.__get__(app)
            for is_flex in (False, True):
                canvas = draw('', '#00000000', '#FFFFFF', 38, None, None,
                              border_color='#FFFFFF', border_width=5,
                              parent=host, bg_color='#000000',
                              pack_side=tk.LEFT if is_flex else None,
                              css_width=76, css_height=76)
                root.update_idletasks()
                self.assertEqual((canvas.winfo_reqwidth(), canvas.winfo_reqheight()),
                                 (76, 76), 'flex' if is_flex else 'column')
        finally:
            root.destroy()


class ShapesAreAntialiased(unittest.TestCase):

    def setUp(self):
        self.root = _root()
        self.canvas = tk.Canvas(self.root, width=200, height=100, bg='#101010')

    def tearDown(self):
        self.root.destroy()

    def test_a_rounded_rectangle_is_an_image(self):
        item = ui._create_rounded_rect(self.canvas, 1, 1, 121, 45, 22,
                                       fill='#D0BCFF', outline='', width=0)
        self.assertEqual(self.canvas.type(item), 'image')

    def test_its_corners_are_soft(self):
        mask = ui._aa_mask(80, 40, 20)
        corner = [mask.getpixel((x, y)) for x in range(8) for y in range(8)]
        self.assertTrue(any(0 < value < 255 for value in corner), corner)
        self.assertEqual(mask.getpixel((40, 20)), 255)
        self.assertEqual(mask.getpixel((0, 0)), 0)

    def test_the_press_tint_and_the_theme_fade_still_reach_it(self):
        item = ui._create_rounded_rect(self.canvas, 1, 1, 121, 45, 22,
                                       fill='#336699', outline='', tags='body')
        before = self.canvas.itemcget(item, 'image')
        self.assertEqual(self.canvas.itemcget(item, 'fill'), '#336699')
        self.canvas.itemconfig('body', fill='#FF0000')
        self.assertEqual(self.canvas.itemcget(item, 'fill'), '#FF0000')
        self.assertNotEqual(self.canvas.itemcget(item, 'image'), before)

    def test_other_items_are_configured_as_before(self):
        ui._create_rounded_rect(self.canvas, 1, 1, 121, 45, 22, fill='#336699')
        text = self.canvas.create_text(10, 10, text='x', fill='#000000', tags='label')
        self.canvas.itemconfig('label', fill='#FFFFFF')
        self.assertEqual(self.canvas.itemcget(text, 'fill'), '#FFFFFF')

    def test_deleting_forgets_the_shape(self):
        ui._create_rounded_rect(self.canvas, 1, 1, 121, 45, 22, fill='#336699')
        self.canvas.delete('all')
        self.assertEqual(self.canvas._apkpy_aa, {})

    def test_an_option_only_a_polygon_has_keeps_the_polygon(self):
        item = ui._create_rounded_rect(self.canvas, 1, 1, 121, 45, 22,
                                       fill='#336699', dash=(2, 2))
        self.assertEqual(self.canvas.type(item), 'polygon')

    def test_the_old_polygons_on_request(self):
        with mock.patch.dict(os.environ, {'APKPY_PREVIEW_AA': '0'}):
            item = ui._create_rounded_rect(self.canvas, 1, 1, 121, 45, 22, fill='#336699')
        self.assertEqual(self.canvas.type(item), 'polygon')

    def test_glass_keeps_its_alpha(self):
        image = ui._aa_shape_image(48, 48, 24, (255, 255, 255, 0x33), None, 0)
        self.assertEqual(image.getpixel((24, 24))[3], 0x33)

    def test_the_border_lies_inside_the_box(self):
        image = ui._aa_shape_image(76, 76, 38, None, (255, 255, 255, 255), 5)
        self.assertEqual(image.getpixel((38, 2))[3], 255)     # on the ring
        self.assertEqual(image.getpixel((38, 38))[3], 0)      # the hole
        self.assertEqual(image.getpixel((0, 0))[3], 0)        # outside the circle


if __name__ == '__main__':
    unittest.main()
