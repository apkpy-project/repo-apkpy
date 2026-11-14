# -*- coding: utf-8 -*-
"""background: linear-gradient(...) and radial-gradient(...), on both sides.

``background`` was not a property ApkPy read (U2029 said so) and nothing drew
a gradient. Now one parser (core/gradients.py) reads CSS's forms, the phone
draws them with a drawable of its own (ApkpyGradient, named from XML), and the
Previewer with a Pillow image from the same geometry -- under the widgets in
a card too, where Tk has no transparency.
"""

import re
import tkinter as tk
import unittest

from apkpy_lib.core import gradients
from apkpy_lib.core.css_colors import normalize_value
from apkpy_lib.core.style_parser import parse_css, unknown_properties
from apkpy_lib.core.features import gradient_drawable
from apkpy_lib.core.compiler import translate_python_to_android


def _g(text):
    return gradients.parse(normalize_value(text))


class TheParserReadsCssForms(unittest.TestCase):

    def test_angles_sides_and_corners(self):
        self.assertEqual(_g("linear-gradient(135deg, #000, #fff)").angle, 135.0)
        self.assertEqual(_g("linear-gradient(0.25turn, #000, #fff)").angle, 90.0)
        self.assertEqual(_g("linear-gradient(to left, #000, #fff)").angle, 270.0)
        self.assertEqual(_g("linear-gradient(#000, #fff)").angle, 180.0)    # to bottom
        self.assertEqual(_g("linear-gradient(to top right, #000, #fff)").corner, "top right")
        self.assertEqual(_g("linear-gradient(to left bottom, #000, #fff)").corner, "bottom left")

    def test_stop_positions_are_filled_in_as_css_fills_them(self):
        stops = [p for _, p in _g("linear-gradient(red, #00F 30%, green, blue)").stops]
        self.assertEqual([round(p, 3) for p in stops], [0.0, 0.3, 0.65, 1.0])
        # A position never goes back; two positions make two stops.
        stops = [p for _, p in _g("linear-gradient(red 50%, blue 20%)").stops]
        self.assertEqual(stops, [0.5, 0.5])
        self.assertEqual(len(_g("linear-gradient(red, blue 20% 40%, green)").stops), 4)

    def test_radial(self):
        g = _g("radial-gradient(circle at top left, #fff, #000)")
        self.assertEqual((g.kind, g.shape, g.center), ("radial", "circle", (0.0, 0.0)))
        g = _g("radial-gradient(ellipse closest-side at 30% 70%, #fff, #000)")
        self.assertEqual((g.extent, g.center), ("closest-side", (0.3, 0.7)))
        self.assertEqual(_g("radial-gradient(#fff 20%, #000)").stops[0], ("#fff", 0.2))

    def test_rgba_inside_reaches_it_in_the_engine_form(self):
        g = _g("linear-gradient(rgba(0, 0, 0, 0), rgba(0, 0, 0, 0.6))")
        self.assertEqual([c for c, _ in g.stops], ["#00000000", "#99000000"])

    def test_what_is_not_a_gradient(self):
        for value in ("linear-gradient(#fff)", "linear-gradient(to middle, #fff, #000)",
                      "#fff", "", None, "url(a.png)"):
            self.assertIsNone(_g(value) if value else gradients.parse(value), value)


class TheGeometryIsCss(unittest.TestCase):

    def test_the_line_meets_the_corners(self):
        self.assertEqual(tuple(round(v, 3) for v in _g(
            "linear-gradient(90deg, #000, #fff)").line(100, 50)), (0.0, 25.0, 100.0, 25.0))
        # 45deg on a wide box: 0% and 100% lie beyond the box so the corners
        # are exactly 0% and 100%.
        g = _g("linear-gradient(45deg, #000, #fff)")
        self.assertEqual(g.color_at_point(0, 50, 100, 50), "#000000")
        self.assertEqual(g.color_at_point(100, 0, 100, 50), "#FFFFFF")

    def test_a_corner_puts_the_middle_through_the_other_two(self):
        g = _g("linear-gradient(to top right, #000, #fff)")
        self.assertEqual(round(g.angle_for(200, 100), 2), 26.57)
        self.assertEqual(g.color_at_point(0, 0, 200, 100), g.color_at_point(200, 100, 200, 100))

    def test_radial_sizes(self):
        self.assertEqual(tuple(round(v, 2) for v in _g(
            "radial-gradient(circle, #000, #fff)").radii(200, 100)), (100.0, 50.0, 111.8, 111.8))
        self.assertEqual(tuple(round(v, 2) for v in _g(
            "radial-gradient(circle closest-side, #000, #fff)").radii(200, 100)),
            (100.0, 50.0, 50.0, 50.0))

    def test_colours_between_stops(self):
        g = _g("linear-gradient(red, blue)")
        self.assertEqual(g.middle(), "#800080")
        self.assertEqual(_g("linear-gradient(#FF000080, #FF0000)").color_at(0.0), "#80FF0000")
        stripes = _g("repeating-linear-gradient(#000, #000 10%, #fff 10%, #fff 20%)")
        self.assertEqual(stripes.color_at(0.05), "#000000")
        self.assertEqual(stripes.color_at(0.15), "#FFFFFF")
        self.assertEqual(stripes.color_at(0.25), "#000000")


class TheStylesheet(unittest.TestCase):

    def test_the_shorthand(self):
        styles, _ = parse_css("""
            hero { background: linear-gradient(135deg, #6750A4, #00BCD4); }
            plain { background: navy; }
            scrim { background-image: linear-gradient(transparent, rgba(0, 0, 0, .6)); }
            later { background: linear-gradient(red, blue); background-color: white; }
            reset { background-color: red; background: linear-gradient(red, blue); }
        """)
        self.assertEqual(styles["hero"]["background-image"],
                         "linear-gradient(135deg, #6750A4, #00BCD4)")
        # An opaque gradient's middle stands in as its colour...
        self.assertEqual(styles["hero"]["background-color"], "#3486BC")
        self.assertEqual(styles["plain"], {"background-color": "#000080"})
        # ...never one with alpha: a scrim over a photo would be drawn twice.
        self.assertNotIn("background-color", styles["scrim"])
        self.assertEqual(styles["later"]["background-color"], "#FFFFFF")
        self.assertEqual(styles["reset"]["background-color"], "#800080")

    def test_background_is_a_property_now(self):
        styles, _ = parse_css("a { background: #fff; background-image: linear-gradient(#000, #fff); }")
        self.assertEqual(unknown_properties(styles), [])

    def test_a_theme_token_inside_is_substituted(self):
        from apkpy_lib.theme import Theme, apply_theme
        styles, _ = parse_css("a { background: linear-gradient(var(--primary), #fff); }")
        out = apply_theme(styles, Theme(primary="#123456"))
        self.assertEqual(out["a"]["background-image"], "linear-gradient(#123456, #fff)")


class TheDrawableDescription(unittest.TestCase):

    def test_spec(self):
        spec = gradient_drawable.spec(_g("linear-gradient(135deg, #6750A4, #00BCD4)"),
                                      radii=20, padding=(16, 16, 16, 16), base="#3486BC")
        self.assertEqual(spec, "kind=0;colors=FF6750A4,FF00BCD4;stops=0,1;angle=135;"
                               "radii=20,20,20,20;base=FF3486BC;padding=16,16,16,16")

    def test_transparent_takes_its_neighbours_colour(self):
        stops = gradient_drawable.resolved_stops(_g("linear-gradient(transparent, #fff)"))
        self.assertEqual(stops[0], ((0, 255, 255, 255), 0.0))
        middle = gradient_drawable.resolved_stops(_g("linear-gradient(red, transparent, blue)"))
        self.assertEqual([c for c, _ in middle],
                         [(255, 255, 0, 0), (0, 255, 0, 0), (0, 0, 0, 255), (255, 0, 0, 255)])

    def test_repeating_and_radial(self):
        spec = gradient_drawable.spec(_g(
            "repeating-linear-gradient(45deg, #000, #000 10%, #fff 10%, #fff 20%)"))
        self.assertIn("stops=0,0.5,0.5,1", spec)
        self.assertIn("span=0,0.2", spec)
        spec = gradient_drawable.spec(_g("radial-gradient(circle at top left, #fff, #000 70%)"))
        self.assertIn("kind=1", spec)
        self.assertIn("shape=0;extent=3;center=0,0", spec)

    def test_a_press_that_reads(self):
        self.assertEqual(gradient_drawable.default_ripple(_g("linear-gradient(#000, #222)")),
                         "#33FFFFFF")
        self.assertEqual(gradient_drawable.default_ripple(_g("linear-gradient(#fff, #eee)")),
                         "#1F000000")


_APP = '''
from apkpy_lib import *

home = Screen(id="home")
box = container(id="box", screen=home)
label("x", screen=home, parent=box)
hero = card(id="hero", screen=home)
label("y", screen=home, parent=hero)
button("Go", id="go", screen=home)
label("plain", id="plain", screen=home)

style = """
home { background: linear-gradient(#0F172A, #1E293B); }
box { background: linear-gradient(to right, #FDE68A, #8B5CF6); border-radius: 12px; }
hero { background: radial-gradient(circle, #22D3EE, #0F172A); border-radius: 20px; }
go { background: linear-gradient(90deg, #F97316, #EC4899); }
plain { color: white; }
"""

run(start_screen=home)
'''


class ThePhone(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = translate_python_to_android(_APP, package="dev.apkpy.check.grad")
        cls.layout = cls.files["res/layout/activity_screen_home.xml"]

    def test_the_class_and_its_attribute_ship(self):
        java = self.files[gradient_drawable.JAVA_FILE]
        self.assertTrue(java.startswith("package dev.apkpy.check.grad;"))
        self.assertIn("public class ApkpyGradient extends Drawable", java)
        self.assertIn('name="apkpySpec"', self.files[gradient_drawable.ATTRS_FILE])

    def test_a_container_wears_it_as_its_background(self):
        box = self.files["res/drawable/box_shape.xml"]
        self.assertIn('class="dev.apkpy.check.grad.ApkpyGradient"', box)
        self.assertIn("radii=12,12,12,12", box)
        self.assertIn('android:background="@drawable/box_shape"', self.layout)

    def test_a_card_puts_it_on_its_content(self):
        name = "apkpy_home_hero_gradient"
        self.assertIn("kind=1", self.files["res/drawable/%s.xml" % name])
        block = self.layout[self.layout.index("MaterialCardView"):]
        self.assertIn('android:background="@drawable/%s"' % name, block[:1500])

    def test_the_screen_root(self):
        self.assertIn("apkpy_screen_bg_home", self.layout)
        self.assertIn("kind=0", self.files["res/drawable/apkpy_screen_bg_home.xml"])

    def test_a_button_keeps_a_press(self):
        go = self.files["res/drawable/go_shape.xml"]
        self.assertTrue(go.lstrip().startswith("<?xml"))
        self.assertIn("<ripple", go)
        self.assertIn("ApkpyGradient", go)

    def test_an_app_without_one_ships_nothing(self):
        files = translate_python_to_android(_APP.replace("background: linear-gradient", "x-: (")
                                            .replace("background: radial-gradient", "x-: ("),
                                            package="dev.apkpy.check.grad")
        self.assertNotIn(gradient_drawable.JAVA_FILE, files)


def _root():
    try:
        root = tk.Tk()
    except tk.TclError as exc:          # no display
        raise unittest.SkipTest(str(exc))
    root.withdraw()
    return root


class ThePreviewer(unittest.TestCase):

    def test_the_picture(self):
        from apkpy_lib.features import gradient_image
        picture = gradient_image.render(_g("linear-gradient(90deg, #000, #fff)"), 101, 10)
        self.assertEqual(picture.size, (101, 10))
        self.assertLess(picture.getpixel((0, 5))[0], 8)
        self.assertGreater(picture.getpixel((100, 5))[0], 247)
        self.assertAlmostEqual(picture.getpixel((50, 5))[0], 128, delta=4)
        radial = gradient_image.render(_g("radial-gradient(circle, #fff, #000)"), 40, 40)
        self.assertGreater(radial.getpixel((20, 20))[0], 240)
        self.assertLess(radial.getpixel((0, 0))[0], 15)

    def test_a_shape_filled_with_it(self):
        from apkpy_lib import ui
        from apkpy_lib.features import gradient_image
        picture = gradient_image.render(_g("linear-gradient(90deg, #f00, #00f)"), 40, 20)
        shape = ui._aa_shape_image(40, 20, 10, None, None, 0, fill_image=picture)
        self.assertEqual(shape.getpixel((0, 0))[3], 0)            # outside the corner
        self.assertEqual(shape.getpixel((20, 10))[3], 255)
        self.assertGreater(shape.getpixel((12, 10))[0], shape.getpixel((28, 10))[0])

    def test_a_label_keeps_its_text_where_it_was(self):
        from PIL import Image
        from apkpy_lib.features import gradient_under
        root = _root()
        try:
            # Mapped, so Tk lays it out, but invisible and off the screen.
            root.attributes("-alpha", 0.0)
            root.geometry("300x80+-4000+-4000")
            root.deiconify()
            root.update()
            frame = tk.Frame(root, bg="#123456", width=300, height=80)
            frame.pack(fill="both", expand=True)
            label = tk.Label(frame, text="Hello", bg="#123456", anchor="w", padx=16)
            label.pack(fill="x")
            root.update()
            width = label.winfo_width()
            border = int(label.cget("bd")) + int(label.cget("highlightthickness"))
            text_width = label.winfo_reqwidth() - 2 * (16 + border)
            asked = []

            def region(x, y, w, h):
                asked.append((x, y, w, h))
                return Image.new("RGB", (w, h), (255, 0, 0))

            gradient_under.paint_label(label, region)
            x, y, w, h = asked[-1]
            # The picture is anchored on the right and its centre is the
            # text's centre: past the border and 16px in, as without a picture.
            self.assertEqual(label.cget("anchor")[-1], "e")
            self.assertAlmostEqual(x + w / 2.0, border + 16 + text_width / 2.0, delta=1)
            self.assertEqual(x + w, width)
            self.assertEqual(int(label.cget("width")), width)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
