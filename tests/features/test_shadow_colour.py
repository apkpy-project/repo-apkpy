# -*- coding: utf-8 -*-
"""box-shadow with a colour: the colour of the shadow, on both sides.

It used to give an elevation only, so every shadow was grey; a purple glow
under a button (``0 8px 24px rgba(124, 92, 255, 0.55)``) came out black.
"""

import unittest

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.css_colors import shadow_colour

_APP = '''
from apkpy_lib import *
home = Screen(id="home")
container(id="glow", screen=home)
container(id="plain", screen=home)
style = """
glow { background-color: #6D4AFF; border-radius: 18px; box-shadow: 0 8px 24px rgba(124, 92, 255, 0.55); }
plain { background-color: #FFFFFF; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2); }
"""
run(start_screen=home)
'''


class TheColour(unittest.TestCase):

    def test_read_from_any_form(self):
        self.assertEqual(shadow_colour("0 8px 24px #807C5CFF"), "#807C5CFF")
        self.assertEqual(shadow_colour("0 2px 6px black"), "#FF000000")
        self.assertEqual(shadow_colour("0 2px 6px #fff"), "#FFFFFFFF")
        self.assertIsNone(shadow_colour("0 4px 8px"))


class ThePhone(unittest.TestCase):

    def test_the_shadow_wears_it(self):
        files = translate_python_to_android(_APP, package="dev.apkpy.check.shadow")
        layout = files["res/layout/activity_screen_home.xml"]
        glow = layout[layout.index("glow_shape"):][:600]
        self.assertIn('android:outlineSpotShadowColor="#7C5CFF"', glow)
        self.assertIn('android:outlineAmbientShadowColor="#7C5CFF"', glow)
        # A black shadow stays Android's own.
        self.assertEqual(layout.count("outlineSpotShadowColor"), 1)


class ThePreviewer(unittest.TestCase):

    def test_the_picture_is_that_colour(self):
        import tkinter as tk
        from apkpy_lib import ui
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest(str(exc))
        root.withdraw()
        try:
            canvas = tk.Canvas(root)
            photo = ui._aa_shadow_photo(canvas, 120, 60, 12, 5, "#807C5CFF")
            if photo is None:
                self.skipTest("no Pillow")
            from PIL import ImageTk  # noqa: F401
            r, g, b = (int(v) for v in root.tk.call(str(photo), "get", 60, 50)[:3])
            self.assertGreater(b, r)
            self.assertGreater(r, g)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
