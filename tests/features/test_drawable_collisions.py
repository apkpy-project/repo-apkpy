"""Different screens must not overwrite each other's Android backgrounds."""
import unittest
import xml.etree.ElementTree as ET

from apkpy_lib.core.compiler import translate_python_to_android

ANDROID = '{http://schemas.android.com/apk/res/android}'


def button_background(files, screen, text):
    layout = ET.fromstring(files['res/layout/activity_screen_' + screen + '.xml'])
    button = next(node for node in layout.iter() if node.get(ANDROID + 'text') == text)
    name = button.get(ANDROID + 'background').split('/', 1)[1]
    return name, files['res/drawable/' + name + '.xml']


class DrawableCollisionTests(unittest.TestCase):
    def build(self, first='outlined', second='filled'):
        files = translate_python_to_android('''from apkpy_lib import Screen, Theme, button, run
home = Screen(id="home")
detail = Screen(id="detail")
button("First", variant="%s", screen=home)
button("Second", variant="%s", screen=detail)
run(start_screen=home, theme=Theme(mode="dark"))
''' % (first, second))
        self.assertNotIn('error.txt', files)
        return files

    def test_later_filled_button_does_not_fill_earlier_outlined_button(self):
        files = self.build()
        first, outlined = button_background(files, 'home', 'First')
        second, filled = button_background(files, 'detail', 'Second')
        self.assertNotEqual(first, second)
        self.assertIn('<solid android:color="#00000000"', outlined)
        self.assertIn('<stroke ', outlined)
        self.assertIn('<solid android:color="@color/apkpy_primary"', filled)

    def test_reverse_order_also_preserves_both_shapes(self):
        files = self.build('filled', 'outlined')
        first, filled = button_background(files, 'home', 'First')
        second, outlined = button_background(files, 'detail', 'Second')
        self.assertNotEqual(first, second)
        self.assertIn('<solid android:color="@color/apkpy_primary"', filled)
        self.assertIn('<solid android:color="#00000000"', outlined)

    def test_identical_backgrounds_can_share_a_resource(self):
        files = self.build('outlined', 'outlined')
        first = button_background(files, 'home', 'First')
        second = button_background(files, 'detail', 'Second')
        self.assertEqual(first, second)


if __name__ == '__main__':
    unittest.main()
