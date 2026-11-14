# -*- coding: utf-8 -*-
"""web_page(): a web page inside the screen.

A WebView on the phone, loaded with the app's HTML (or an address) through
ApkpyWeb; in the Previewer, the HTML drawn by features/web_page.py.
``set_value`` replaces it on both sides.
"""

import tkinter as tk
import unittest

from apkpy_lib.core.features import web_page as phone
from apkpy_lib.features import web_page as preview

from test_real_screens import _build, _java

_APP = ('home = Screen(id="home")\n'
        'page = web_page(html="<h1>Hi</h1>", id="pg", screen=home)\n'
        'def go():\n'
        '    page.set_value("<p>new</p>")\n'
        'button("Go", id="go", command=go, screen=home)\n')


class ThePhone(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = _build(_APP, 'pg { height: 200px; background-color: #FFFFFF; }')
        cls.java = _java(cls.files)
        cls.layout = ''.join(v for k, v in cls.files.items() if k.startswith('res/layout/'))

    def test_a_webview_in_the_layout(self):
        self.assertIn('<WebView', self.layout)
        self.assertIn('android:id="@+id/web1"', self.layout)
        self.assertIn('android:layout_height="200dp"', self.layout)

    def test_loaded_with_the_html_and_replaced_by_set_value(self):
        self.assertIn('ApkpyWeb.setup(web1);', self.java)
        self.assertIn('ApkpyWeb.show(web1, "<h1>Hi</h1>");', self.java)
        self.assertIn('ApkpyWeb.show((android.webkit.WebView) findViewById(R.id.web1), '
                      'String.valueOf("<p>new</p>"));', self.java)
        self.assertNotIn('_apkpyRememberText(R.id.web1)', self.java)

    def test_the_helper_ships_and_html_needs_no_internet(self):
        self.assertIn(phone.JAVA_FILE, self.files)
        manifest = self.files.get('AndroidManifest.xml', '')
        self.assertNotIn('android.permission.INTERNET', manifest)

    def test_an_address_asks_for_internet(self):
        files = _build('home = Screen(id="home")\n'
                       'web_page(url="https://example.com", id="pg", screen=home)\n')
        self.assertIn('android.permission.INTERNET', files.get('AndroidManifest.xml', ''))
        self.assertIn('ApkpyWeb.show(web1, "https://example.com");', _java(files))

    def test_no_web_page_no_helper(self):
        files = _build('home = Screen(id="home")\nlabel("Hi", screen=home)\n')
        self.assertNotIn(phone.JAVA_FILE, files)


class TheHtml(unittest.TestCase):

    def _text(self, markup):
        return ''.join(text for text, look in preview.parse(markup)[0] if 'gap' not in look)

    def test_blocks_lists_and_whitespace(self):
        self.assertEqual(self._text('<h1>Hi</h1>\n<p>One  <b>two</b></p><ul><li>a</li><li>b</li></ul>'),
                         'Hi\nOne two\n•  a\n•  b\n')
        self.assertEqual(self._text('<ol><li>x</li><li>y</li></ol>'), '1. x\n2. y\n')

    def test_style_rules_reach_tags_classes_and_ids(self):
        runs, background = preview.parse(
            '<style>h1 { color: #6d4aff; } .note { font-size: 12px } #k { font-weight: bold }'
            ' body { background: #000000 }</style>'
            '<h1>T</h1><p class="note">n</p><p id="k">k</p><p style="color: red">r</p>')
        look = {text: l for text, l in runs if text.strip()}
        self.assertEqual(look['T']['color'], '#6d4aff')
        self.assertTrue(look['T']['bold'])
        self.assertEqual(look['n']['size'], 12.0)
        self.assertTrue(look['k']['bold'])
        self.assertEqual(look['r']['color'], 'red')
        self.assertEqual(background, '#000000')

    def test_scripts_and_styles_are_not_text(self):
        self.assertEqual(self._text('<script>alert(1)</script><p>ok</p>'), 'ok\n')

    def test_an_address_is_told_from_html(self):
        self.assertTrue(preview.is_address('https://example.com'))
        self.assertFalse(preview.is_address('<p>https://x</p>'))


class ThePreviewer(unittest.TestCase):

    def test_fill_draws_the_runs(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest(str(exc))
        root.withdraw()
        try:
            text = tk.Text(root)
            preview.fill(text, '<h1>Ola</h1><p>mundo</p>', 'Segoe UI', lambda c: c)
            self.assertEqual(text.get('1.0', 'end-1c'), 'Ola\nmundo')
            self.assertEqual(str(text.cget('state')), 'disabled')
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
