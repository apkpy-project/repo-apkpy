# -*- coding: utf-8 -*-
"""Colours for code: a fenced block in markdown() and a textarea while you type.

```` ```cpp numbers ```` colours the block's words and numbers its lines;
``syntax: html`` on an ``inputs(type="textarea")`` colours as you type. One
table of patterns (core/code_highlight.py) serves both, in the Previewer and
written into the Java, so a keyword is the same colour everywhere.
"""

import re
import tkinter as tk
import unittest

from apkpy_lib.core import code_highlight as code
from apkpy_lib.core.features import code_editor as editor_feature
from apkpy_lib.core.features import rich_content as rich_feature
from apkpy_lib.features import code_editor as editor_preview
from apkpy_lib.features import rich_content as rich_preview

from test_real_screens import _build, _java


def _kinds(line, lang):
    return [(line[s:e], kind) for s, e, kind in code.tokens(line, lang)]


class TheTable(unittest.TestCase):

    def test_a_cpp_line_is_split_into_kinds(self):
        found = _kinds('int a = 7; std::cout << a / b; // fim', 'c')
        self.assertIn(('int', 'type'), found)
        self.assertIn(('7', 'number'), found)
        self.assertIn(('cout', 'type'), found)
        self.assertIn(('// fim', 'comment'), found)

    def test_html_tags_attributes_and_strings(self):
        found = _kinds('<a href="x.html">ir</a>', 'html')
        self.assertIn(('<a', 'tag'), found)
        self.assertIn(('href', 'attr'), found)
        self.assertIn(('"x.html"', 'string'), found)
        self.assertIn(('</a', 'tag'), found)

    def test_the_fence_names_language_and_numbers(self):
        self.assertEqual(code.language('cpp numbers'), 'c')
        self.assertTrue(code.numbered('cpp numbers'))
        self.assertFalse(code.numbered('numbers'))
        self.assertIsNone(code.language('cobol'))
        self.assertEqual(code.tokens('x = 1', None), [])

    def test_alternative_n_is_group_n(self):
        # Java reads the kind from the group number: no capturing group may
        # hide inside an alternative.
        for lang, rules in code._TABLE.items():
            for kind, pattern in rules:
                self.assertEqual(re.compile(pattern).groups, 0, (lang, kind))

    def test_the_palette_follows_the_text(self):
        self.assertIs(code.palette('#F4F4F8'), code.PALETTES['dark'])
        self.assertIs(code.palette('#111111'), code.PALETTES['light'])

    def test_the_java_tables_match_the_python_ones(self):
        java = code.java_tables()
        self.assertEqual(java.count('Pattern.compile('), len(code.LANGUAGES))
        for lang in code.LANGUAGES:
            self.assertIn('"%s"' % lang, java)
        self.assertIn('CODE_ALIASES.put("cpp", "c");', java)


class ThePhone(unittest.TestCase):

    def test_the_markdown_view_carries_the_tables(self):
        java = rich_feature.generate_rich_content_view_java('dev.x')
        self.assertNotIn('__CODE_TABLES__', java)
        self.assertIn('CODE_PATTERNS[codeLang].matcher(raw)', java)
        self.assertIn('codeNumbers', java)

    def test_a_textarea_with_syntax_colours_as_you_type(self):
        files = _build('home = Screen(id="home")\n'
                       'inputs(type="textarea", id="src", screen=home)\n',
                       'src { syntax: html; }')
        self.assertIn(editor_feature.JAVA_FILE, files)
        self.assertIn('ApkpyCodeColors.watch(inp1, "html");', _java(files))
        source = files[editor_feature.JAVA_FILE]
        self.assertNotIn('__CODE_TABLES__', source)
        self.assertIn('afterTextChanged(Editable s) { paint(s, lang, palette); }', source)

    def test_without_syntax_nothing_ships(self):
        files = _build('home = Screen(id="home")\n'
                       'inputs(type="textarea", id="src", screen=home)\n')
        self.assertNotIn(editor_feature.JAVA_FILE, files)
        self.assertNotIn('ApkpyCodeColors', _java(files))


class ThePreviewer(unittest.TestCase):

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest(str(exc))
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()

    def _spans(self, text, tag):
        ranges = text.tag_ranges(tag)
        return [text.get(ranges[i], ranges[i + 1]) for i in range(0, len(ranges), 2)]

    def test_a_fenced_block_is_coloured_and_numbered(self):
        text = tk.Text(self.root, foreground='#F4F4F8')
        rich_preview._render_markdown(text, '```cpp numbers\nint a = 7;\n```')
        self.assertEqual(self._spans(text, 'code_type'), ['int'])
        self.assertEqual(self._spans(text, 'code_number'), ['7'])
        self.assertEqual([s.strip() for s in self._spans(text, 'code_lineno')], ['1'])

    def test_a_plain_block_stays_one_colour(self):
        text = tk.Text(self.root, foreground='#F4F4F8')
        rich_preview._render_markdown(text, '```\nint a = 7;\n```')
        self.assertEqual(text.tag_ranges('code_type'), ())
        self.assertIn('int a = 7;', text.get('1.0', 'end'))

    def test_the_editor_recolours_after_a_change(self):
        text = tk.Text(self.root)
        self.assertTrue(editor_preview.watch(text, {'syntax': 'html'}, '#E5E7EB'))
        text.insert('1.0', '<h1>Ola</h1>')
        self.root.update()
        self.assertEqual(self._spans(text, 'syntax_tag'), ['<h1>', '</h1>'])
        text.delete('1.0', 'end')
        text.insert('1.0', 'body')
        self.root.update()
        self.assertEqual(self._spans(text, 'syntax_tag'), [])

    def test_no_syntax_no_watch(self):
        text = tk.Text(self.root)
        self.assertFalse(editor_preview.watch(text, {}, '#E5E7EB'))


class IconSize(unittest.TestCase):

    def test_a_button_icon_takes_the_stylesheet_size(self):
        files = _build('home = Screen(id="home")\n'
                       'button("", icon="star", variant="icon", id="fav", screen=home)\n'
                       'button("Go", icon="star", id="go", screen=home)\n',
                       'fav { icon-size: 17px; }')
        layout = ''.join(v for k, v in files.items() if k.startswith('res/layout/'))
        self.assertIn('app:iconSize="17dp"', layout)
        self.assertIn('app:iconSize="20dp"', layout)


if __name__ == '__main__':
    unittest.main()
