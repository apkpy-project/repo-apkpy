# -*- coding: utf-8 -*-
"""background: several gradients and a colour, as CSS stacks them.

``background: radial-gradient(...), radial-gradient(...), #0C0C14`` kept only
the first gradient and lost the colour; written over several lines it was
dropped altogether.
"""

import unittest

from apkpy_lib.core import gradients
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.style_parser import parse_css

_CSS = """home {
    background:
        radial-gradient(circle at 10% 0%, rgba(124, 92, 255, 0.4), transparent 55%),
        radial-gradient(circle at 100% 35%, rgba(45, 212, 191, 0.16), transparent 45%),
        #0C0C14;
    padding: 20px;
}"""


class TheStylesheet(unittest.TestCase):

    def test_every_layer_and_the_colour(self):
        style = parse_css(_CSS)[0]["home"]
        self.assertEqual(style["background-color"], "#0C0C14")
        self.assertEqual(style["padding"], "20px")
        found = gradients.layers_of(style)
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0].center, (0.1, 0.0))      # the top one first

    def test_a_value_over_several_lines(self):
        style = parse_css("a {\n  color:\n    #FF0000;\n  margin: 4px;\n}")[0]["a"]
        self.assertEqual(style, {"color": "#FF0000", "margin": "4px"})


class ThePhone(unittest.TestCase):

    def test_a_layer_list_of_one_gradient_each(self):
        app = ('from apkpy_lib import *\nhome = Screen(id="home")\nlabel("x", screen=home)\n'
               'style = """\n' + _CSS + '\n"""\nrun(start_screen=home)\n')
        files = translate_python_to_android(app, package="dev.apkpy.check.layers")
        stack = files["res/drawable/apkpy_screen_bg_home.xml"]
        self.assertIn("<layer-list", stack)
        self.assertLess(stack.index("_l0"), stack.index("_l1"))
        bottom = files["res/drawable/apkpy_screen_bg_home_l0.xml"]
        self.assertIn("BASE=FF0C0C14", bottom.upper())
        self.assertIn("CENTER=1,0.35", files["res/drawable/apkpy_screen_bg_home_l0.xml"].upper())
        self.assertNotIn("BASE=", files["res/drawable/apkpy_screen_bg_home_l1.xml"].upper())


class ThePreviewer(unittest.TestCase):

    def test_the_picture_stacks_them(self):
        from apkpy_lib.features import gradient_image
        found = gradients.layers_of(parse_css(_CSS)[0]["home"])
        picture = gradient_image.render(found, 100, 100)
        self.assertEqual(picture.size, (100, 100))
        top_left, right = picture.getpixel((10, 0)), picture.getpixel((99, 35))
        self.assertGreater(top_left[2], top_left[1])       # purple
        self.assertGreater(right[1], right[0])             # teal


if __name__ == "__main__":
    unittest.main()
