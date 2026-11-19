# -*- coding: utf-8 -*-
"""The app's icon: a square PNG for Android 7, an adaptive icon for 8 and later.

Until 1.15.1 the build wrote only the square PNG, and Android 8 and later
shrank it inside a white circle. apkpy_lib/app_icon.py writes the two layers
too: a picture with a filled background fills what the phone shows and gives
its colour to the background layer; a picture with a transparent background
sits inside the circle every shape keeps, on icon_background or white.
"""

import os
import shutil
import tempfile
import unittest

try:
    from PIL import Image, ImageDraw
except ImportError:      # the CI installs Pillow; a bare machine may not
    Image = None

from apkpy_lib import app_icon, config


def _filled(path):
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, 511, 511), 110, fill=(103, 80, 164, 255))
    draw.ellipse((136, 136, 376, 376), fill=(255, 255, 255, 255))
    img.save(path)


def _glyph(path):
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    ImageDraw.Draw(img).polygon([(256, 40), (472, 440), (40, 440)], fill=(245, 124, 0, 255))
    img.save(path)


@unittest.skipIf(Image is None, "Pillow is not installed")
class TheIconTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="apkpy-icon-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.res = os.path.join(self.tmp, "res")

    def test_a_filled_picture_gives_its_colour_and_fills_the_shape(self):
        icon = os.path.join(self.tmp, "icon.png")
        _filled(icon)
        self.assertEqual(app_icon.write(self.res, icon), "#6750A4")
        layer = Image.open(os.path.join(self.res, "mipmap-xxxhdpi", "ic_launcher_foreground.png"))
        self.assertEqual(layer.size, (432, 432))
        # The picture is 72 dp of the 108: transparent outside, filled inside.
        self.assertEqual(layer.getpixel((60, 216))[3], 0)
        self.assertEqual(layer.getpixel((80, 216))[:3], (103, 80, 164))
        with open(os.path.join(self.res, "values", "apkpy_icon.xml"), encoding="utf-8") as f:
            self.assertIn('<color name="apkpy_icon_background">#6750A4</color>', f.read())

    def test_a_transparent_picture_sits_inside_the_safe_circle(self):
        icon = os.path.join(self.tmp, "icon.png")
        _glyph(icon)
        self.assertEqual(app_icon.write(self.res, icon), "#FFFFFF")
        self.assertEqual(app_icon.write(self.res, icon, background="#102030"), "#102030")
        layer = Image.open(os.path.join(self.res, "mipmap-mdpi", "ic_launcher_foreground.png"))
        box = layer.getbbox()
        # 60 dp of 108, centred: inside the 66 dp circle.
        self.assertLessEqual(box[2] - box[0], 61)
        self.assertGreaterEqual(box[0], 23)

    def test_every_file_android_reads(self):
        icon = os.path.join(self.tmp, "icon.png")
        _filled(icon)
        app_icon.write(self.res, icon)
        for density in app_icon.LEGACY:
            for name in ("ic_launcher.png", "ic_launcher_round.png", "ic_launcher_foreground.png"):
                self.assertTrue(os.path.isfile(os.path.join(self.res, "mipmap-" + density, name)),
                                density + "/" + name)
        for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
            with open(os.path.join(self.res, "mipmap-anydpi-v26", name), encoding="utf-8") as f:
                text = f.read()
            self.assertIn('<background android:drawable="@color/apkpy_icon_background" />', text)
            self.assertIn('<foreground android:drawable="@mipmap/ic_launcher_foreground" />', text)

    def test_a_picture_that_is_not_square(self):
        icon = os.path.join(self.tmp, "icon.png")
        Image.new("RGBA", (300, 200), (10, 20, 30, 255)).save(icon)
        app_icon.write(self.res, icon)
        self.assertEqual(Image.open(os.path.join(self.res, "mipmap-hdpi", "ic_launcher.png")).size,
                         (72, 72))


class TheConfigTests(unittest.TestCase):

    def test_icon_background_is_read_from_apkpy_toml(self):
        tmp = tempfile.mkdtemp(prefix="apkpy-icon-")
        self.addCleanup(shutil.rmtree, tmp, True)
        with open(os.path.join(tmp, "apkpy.toml"), "w", encoding="utf-8") as f:
            f.write('[app]\nname = "A"\nicon_background = "#1e88e5"\n')
        cfg = config.load_config(tmp)
        if not cfg["_found"] or any("tomli" in w for w in cfg["_warnings"]):
            self.skipTest("no TOML reader on this Python")
        self.assertEqual(cfg["icon_background"], "#1E88E5")

    def test_a_colour_that_is_not_one(self):
        tmp = tempfile.mkdtemp(prefix="apkpy-icon-")
        self.addCleanup(shutil.rmtree, tmp, True)
        with open(os.path.join(tmp, "apkpy.toml"), "w", encoding="utf-8") as f:
            f.write('[app]\nname = "A"\nicon_background = "blue-ish"\n')
        cfg = config.load_config(tmp)
        if not cfg["_found"] or any("tomli" in w for w in cfg["_warnings"]):
            self.skipTest("no TOML reader on this Python")
        self.assertIsNone(cfg["icon_background"])
        self.assertTrue(any("icon_background" in w for w in cfg["_warnings"]))


if __name__ == "__main__":
    unittest.main()
