# -*- coding: utf-8 -*-
"""A release build keeps every picture and sound the app brought.

`apkpy release` shrinks resources: the shrinker keeps only what the code
names. A picture named in the app's data -- {"art": "art/cover.jpg"} in the
list a row shows -- is looked up by name while the app runs, which the
shrinker cannot follow, so the signed showcase Afterglow (1.15.0) showed a
row without its cover where the debug build showed it. Since 1.15.1 the
compiler writes res/raw/apkpy_app_keep.xml naming every file it copied from
the app.
"""

import os
import shutil
import tempfile
import unittest

from apkpy_lib.core.compiler import translate_python_to_android

APP = '''from apkpy_lib import *

home = Screen(id="home")
image("art/hero.png", id="hero", screen=home)

SHELF = [
    {"id": "1", "art": "art/cover_one.png", "title": "One"},
    {"id": "2", "art": "art/cover_two.png", "title": "Two"},
]


def shelf_item(row):
    image("{art}", id="shelf_art", parent=row, describe="")
    label("{title}", id="shelf_title", parent=row)


virtual_collection(SHELF, row=shelf_item, id="shelf", screen=home)
run(start_screen=home)
'''


class TheKeepListTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="apkpy-keep-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        os.makedirs(os.path.join(self.tmp, "art"))
        png = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
               b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe"
               b"\x02\xfe\xa7\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82")
        for name in ("hero", "cover_one", "cover_two"):
            with open(os.path.join(self.tmp, "art", name + ".png"), "wb") as f:
                f.write(png)

    def test_pictures_named_in_data_are_kept(self):
        files = translate_python_to_android(APP, project_root=self.tmp)
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:600])
        keep = files.get("res/raw/apkpy_app_keep.xml", "")
        for name in ("@drawable/cover_one", "@drawable/cover_two", "@drawable/hero"):
            self.assertIn(name, keep)
        self.assertIn('xmlns:tools="http://schemas.android.com/tools"', keep)

    def test_an_app_with_no_files_of_its_own_has_no_list(self):
        files = translate_python_to_android(
            'from apkpy_lib import *\nhome = Screen(id="home")\nlabel("x", screen=home)\n'
            'run(start_screen=home)\n')
        self.assertNotIn("res/raw/apkpy_app_keep.xml", files)


if __name__ == "__main__":
    unittest.main()
