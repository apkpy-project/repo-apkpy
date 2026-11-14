# -*- coding: utf-8 -*-
"""Transparency, as a stylesheet writes it, on the phone and in the Previewer.

A friend's app (30-10-2026) tried transparency and "it did not work". It did
not, in four ways:

* ``rgba(0, 0, 0, 0.5)`` reached the phone's XML as written, which the build
  refused, and stopped the Previewer with "invalid color name".
* ``#00000080`` -- black at half strength in every browser, and what every
  assistant that writes CSS writes -- was read in Android's order, alpha
  first: a fully transparent box.
* ``opacity`` worked on an image only, on both sides.
* In the Previewer a glass panel was its colour at full strength, a black box.

Colours are now read once, as the stylesheet is parsed, into the engine's
``#AARRGGBB``; ``opacity`` is ``android:alpha`` on any component; and the
Previewer mixes each colour with what is behind it, which on a plain surface
is exactly what the phone shows.
"""

import re
import tkinter as tk
import unittest

from apkpy_lib.core import css_colors
from apkpy_lib.core.style_parser import _parse_style_blocks
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib import theme as theme_module


def _parsed(css):
    return dict(_parse_style_blocks(css))


def _files(source):
    return translate_python_to_android(source)


def _texts(files, prefix):
    return "\n".join(v for k, v in files.items()
                     if k.startswith(prefix) and isinstance(v, str))


def _layouts(files):
    return _texts(files, "res/layout/")


class ColoursAreReadAsCssWritesThem(unittest.TestCase):

    def test_functions(self):
        self.assertEqual(css_colors.normalize_value("rgba(0, 0, 0, 0.5)"), "#80000000")
        self.assertEqual(css_colors.normalize_value("rgb(255 0 0 / 25%)"), "#40FF0000")
        self.assertEqual(css_colors.normalize_value("rgb(103, 80, 164)"), "#6750A4")
        self.assertEqual(css_colors.normalize_value("hsl(262, 52%, 47%)"), "#673AB6")
        self.assertEqual(css_colors.normalize_value("hsla(0, 100%, 50%, 0.5)"), "#80FF0000")
        self.assertEqual(css_colors.normalize_value("hsl(0.5turn 100% 50%)"), "#00FFFF")

    def test_hex_puts_the_alpha_last(self):
        self.assertEqual(css_colors.normalize_value("#00000080"), "#80000000")
        self.assertEqual(css_colors.normalize_value("#FFFFFF99"), "#99FFFFFF")
        self.assertEqual(css_colors.normalize_value("#0008"), "#88000000")
        self.assertEqual(css_colors.normalize_value("#6750A4FF"), "#6750A4")
        # Opaque forms are left as they were written.
        self.assertEqual(css_colors.normalize_value("#6750A4"), "#6750A4")
        self.assertEqual(css_colors.normalize_value("#FFF"), "#FFF")

    def test_transparent_stays_transparent(self):
        self.assertEqual(css_colors.normalize_value("#00000000"), "#00000000")
        self.assertEqual(css_colors.named("transparent"), "#00000000")

    def test_a_whole_value_is_read(self):
        self.assertEqual(css_colors.normalize_value("0 4px 12px rgba(0,0,0,.3)"),
                         "0 4px 12px #4D000000")
        self.assertEqual(
            css_colors.normalize_value("linear-gradient(90deg, #6750A4, rgba(0, 188, 212, 0.5))"),
            "linear-gradient(90deg, #6750A4, #8000BCD4)")

    def test_what_is_not_a_colour_is_left_alone(self):
        for value in ("16px", "var(--primary)", "calc(100% - 8px)", "bold", "url(a.png)"):
            self.assertEqual(css_colors.normalize_value(value), value)

    def test_a_function_that_cannot_be_read_is_left_as_written(self):
        self.assertEqual(css_colors.normalize_value("rgb(1, 2)"), "rgb(1, 2)")


class TheParserNormalisesOnce(unittest.TestCase):

    def test_colour_properties(self):
        props = _parsed("""
            a { background-color: rgba(0, 0, 0, 0.5); color: #FFFFFF99; }
            b { border-color: orange; color: green; background-color: transparent; }
        """)
        self.assertEqual(props["a"]["background-color"], "#80000000")
        self.assertEqual(props["a"]["color"], "#99FFFFFF")
        self.assertEqual(props["b"]["border-color"], "#FFA500")
        self.assertEqual(props["b"]["color"], "#008000")       # CSS's green
        self.assertEqual(props["b"]["background-color"], "#00000000")

    def test_names_only_in_colour_properties(self):
        props = _parsed("a { animation-name: gold; font-family: navy; color: gold; }")
        self.assertEqual(props["a"]["animation-name"], "gold")
        self.assertEqual(props["a"]["font-family"], "navy")
        self.assertEqual(props["a"]["color"], "#FFD700")

    def test_a_theme_takes_the_same_forms(self):
        palette = theme_module.Theme(primary="rgba(103, 80, 164, 0.5)",
                                     background="#00000080").tokens
        self.assertEqual(palette["primary"], "#806750A4")
        self.assertEqual(palette["background"], "#80000000")


class AColourWrittenAlphaFirstIsNamed(unittest.TestCase):
    """U2049: a stylesheet written for the old order says so at build time."""

    def test_the_old_order_is_found_with_the_colour_to_write(self):
        from apkpy_lib.core.style_parser import hex_order_suspects
        found = hex_order_suspects("""
            /* a comment with #80000000 is not a colour */
            glass { background-color: #80000000; color: #FFFFFF00; }
            seg { background-color: #66FFFFFF; }
            short { border-color: #8000; }
        """)
        self.assertEqual(found, [
            ("glass", "background-color", "#80000000", "#00000080"),
            ("glass", "color", "#FFFFFF00", "#FFFF00"),
            ("seg", "background-color", "#66FFFFFF", "#FFFFFF66"),
            ("short", "border-color", "#8000", "#00000088"),
        ])

    def test_colours_that_mean_the_same_either_way_are_left_alone(self):
        from apkpy_lib.core.style_parser import hex_order_suspects
        self.assertEqual(hex_order_suspects("""
            a { background-color: #00000000; color: #00000080; }
            b { background-color: #00FF0000; border-color: #FFFFFFFF; color: #6750A499; }
            c { box-shadow: 0 4px 8px #80000000; background-color: transparent; }
        """), [])

    def test_it_is_said_once(self):
        from unittest import mock
        from apkpy_lib.core import style_parser
        with mock.patch("apkpy_lib.diagnostics.report_diagnostic") as report:
            style_parser._HEX_ORDER_REPORTED.discard("#80112233")
            style_parser.report_hex_order("a { color: #80112200; }")
            style_parser.report_hex_order("a { color: #80112200; }")
        style_parser._HEX_ORDER_REPORTED.discard("#80112200")
        self.assertEqual(report.call_count, 1)
        self.assertEqual(report.call_args[0][0].code, "U2049")
        self.assertIn("write #11220080", report.call_args[0][0].received)


class OverWhatIsBehind(unittest.TestCase):

    def test_mixes(self):
        self.assertEqual(css_colors.over("#80000000", "#E53935"), "#721C1A")
        self.assertEqual(css_colors.over("#8000", "#FFF"), "#777777")
        self.assertEqual(css_colors.over("transparent", "#123456"), "#123456")
        self.assertEqual(css_colors.over("#00FF0000", "#123456"), "#123456")

    def test_leaves_what_it_cannot_mix(self):
        self.assertEqual(css_colors.over("#FF0000", "#000000"), "#FF0000")
        self.assertEqual(css_colors.over("#80000000", "var(--bg)"), "#80000000")
        self.assertEqual(css_colors.over("#80000000", None), "#80000000")


_APP = '''
from apkpy_lib import *

home = Screen(id="home")
glass = container(id="glass", screen=home)
label("on glass", id="onglass", screen=home, parent=glass)
dim = container(id="dim", screen=home)
label("inside", id="inside", screen=home, parent=dim)
label("soft", id="soft", screen=home)
button("Faded", id="faded", screen=home)
image("a.png", id="pic", screen=home)

style = """
home { background-color: #E53935; }
glass { background-color: rgba(0, 0, 0, 0.5); padding: 16px; }
onglass { color: white; }
dim { background-color: #000000; opacity: 0.5; padding: 16px; }
inside { color: white; }
soft { color: rgba(255, 255, 255, 0.6); }
faded { opacity: 0.4; }
pic { opacity: 0.3; }
"""

run(start_screen=home)
'''


class ThePhone(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = _files(_APP)
        cls.layout = _layouts(cls.files)

    def test_rgba_reaches_android_as_aarrggbb(self):
        shapes = _texts(self.files, "res/drawable/")
        self.assertIn('android:color="#80000000"', shapes)
        self.assertIn('android:textColor="#99FFFFFF"', self.layout)
        self.assertNotIn("rgba(", self.layout + shapes)

    def test_opacity_on_any_component(self):
        alphas = re.findall(r'android:alpha="([0-9.]+)"', self.layout)
        self.assertIn("0.5", alphas)        # the container, children and all
        self.assertIn("0.4", alphas)        # the button

    def test_an_image_keeps_its_own_opacity_once(self):
        block = self.layout[self.layout.index("ImageView"):]
        block = block[:block.index("/>")]
        self.assertEqual(block.count("android:alpha"), 1)


class TheContrastAuditSeesTheGlass(unittest.TestCase):

    def test_white_on_a_translucent_white_card_is_not_white_on_white(self):
        from apkpy_lib.core.compiler import _audit_accessibility
        styles = dict(_parse_style_blocks("""
            home { background-color: #E53935; }
            c { background-color: rgba(255, 255, 255, 0.25); }
            t { color: white; }
            s { color: rgba(255, 255, 255, 0.6); font-size: 20px; }
        """))
        screens = {"home": [
            {"comp_type": "card", "id": "c",
             "children": [{"comp_type": "label", "id": "t", "text": "x"}]},
            {"comp_type": "label", "id": "s", "text": "y"},
        ]}
        found = {where: text for _, where, text in _audit_accessibility(screens, styles)}
        card = re.search(r"([0-9.]+):1", found["home.t"]).group(1)
        soft = re.search(r"([0-9.]+):1", found["home.s"]).group(1)
        self.assertGreater(float(card), 2.5)    # was 1.00: white read on white
        self.assertLess(float(soft), 3.0)       # was 4.23: the alpha was dropped

    def test_content_ink_reads_the_glass_over_the_screen(self):
        # A dark glass card on a white screen is grey: the ink is chosen for that.
        self.assertEqual(theme_module._seen_background(
            ("#CC000000", None, "#FFFFFF", None, theme_module.LIGHT_BACKGROUND)), "#333333")
        ink = theme_module.content_ink({}, own_bg="#CC000000", screen_bg="#FFFFFF")
        self.assertEqual(ink["text"], "#FAFAFA")
        # A clear one says nothing: what is under it decides, as before.
        ink = theme_module.content_ink({}, own_bg="#00000000", screen_bg="#000000")
        self.assertEqual(ink["text"], "#FAFAFA")


def _root():
    try:
        root = tk.Tk()
    except tk.TclError as exc:          # no display
        raise unittest.SkipTest(str(exc))
    root.withdraw()
    return root


class ThePreviewer(unittest.TestCase):

    def setUp(self):
        from apkpy_lib.features import alpha
        self.alpha = alpha
        self._options = tk.Misc._options
        alpha.install_alpha_net()
        self.root = _root()
        self.root.configure(bg="#E53935")

    def tearDown(self):
        try:
            self.root.destroy()
        finally:
            tk.Misc._options = self._options

    def test_a_colour_with_alpha_no_longer_stops_the_app(self):
        frame = tk.Frame(self.root, bg="#80000000")
        label = tk.Label(frame, text="x", fg="#99FFFFFF")
        self.assertEqual(frame.cget("bg").upper(), "#721C1A")
        # The text lies over the frame it is in.
        self.assertEqual(label.cget("fg").upper(), "#C7A4A3")
        label.configure(fg="#00FFFFFF")
        self.assertEqual(label.winfo_rgb(label.cget("fg")), label.winfo_rgb(label.cget("bg")))

    def test_a_canvas_shape_with_alpha(self):
        canvas = tk.Canvas(self.root, bg="#FFFFFF")
        clear = canvas.create_rectangle(0, 0, 10, 10, fill="#00000000", outline="#80000000")
        self.assertEqual(canvas.itemcget(clear, "fill"), "")
        self.assertEqual(canvas.itemcget(clear, "outline").upper(), "#7F7F7F")

    def test_the_net_installs_once(self):
        first = tk.Misc._options
        self.alpha.install_alpha_net()
        self.assertIs(tk.Misc._options, first)

    def test_opacity_mixes_towards_what_is_behind(self):
        box = tk.Frame(self.root, bg="#000000")
        text = tk.Label(box, text="x", bg="#000000", fg="#FFFFFF")
        self.alpha.apply_opacity([box], 0.5, (0xE5, 0x39, 0x35))
        self.assertEqual(tk.Misc.cget(box, "bg").upper(), "#721C1A")
        self.assertEqual(tk.Misc.cget(text, "fg").upper(), "#F29C9A")
        # The code still reads the colour it set, so a fade can write it back.
        self.assertEqual(text.cget("fg"), "#FFFFFF")
        text.configure(fg="#000000")            # a hover, a fade step
        self.assertEqual(tk.Misc.cget(text, "fg").upper(), "#721C1A")

    def test_nested_opacities_compose(self):
        outer = tk.Frame(self.root, bg="#FFFFFF")
        inner = tk.Label(outer, text="x", bg="#000000")
        self.alpha.apply_opacity([inner], 0.5, (255, 255, 255))
        self.alpha.apply_opacity([outer], 0.5, (0, 0, 0))
        # black at half over white, then all of it at half over black
        self.assertEqual(tk.Misc.cget(inner, "bg").upper(), "#404040")
        self.assertEqual(tk.Misc.cget(outer, "bg").upper(), "#808080")

    def test_a_canvas_keeps_its_opacity_through_a_redraw(self):
        canvas = tk.Canvas(self.root, bg="#000000")
        first = canvas.create_rectangle(0, 0, 10, 10, fill="#FFFFFF", outline="")
        self.alpha.apply_opacity([canvas], 0.25, (0, 0, 0))
        self.assertEqual(tk.Canvas.itemcget(canvas, first, "fill").upper(), "#404040")
        canvas.delete("all")                    # a resize redraws from scratch
        again = canvas.create_rectangle(0, 0, 10, 10, fill="#FFFFFF")
        self.assertEqual(tk.Canvas.itemcget(canvas, again, "fill").upper(), "#404040")
        self.assertEqual(canvas.itemcget(again, "fill"), "#FFFFFF")

    def test_a_shape_drawn_as_an_image_mixes_as_it_is_drawn(self):
        from apkpy_lib import ui
        canvas = tk.Canvas(self.root, bg="#000000")
        canvas._apkpy_opacity_layers = [(0.5, (0, 0, 0))]
        self.assertEqual(ui._aa_rgba(canvas, "#FFFFFF"), (128, 128, 128, 255))
        self.assertEqual(ui._aa_rgba(canvas, "#80FFFFFF"), (128, 128, 128, 128))


if __name__ == "__main__":
    unittest.main()
