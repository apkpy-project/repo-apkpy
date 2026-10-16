# -*- coding: utf-8 -*-
"""Linhas que tomam a altura do que levam, e que sabem desenhar Markdown.

As duas coisas que faltavam a uma conversa. Uma altura unica dava a "sim" o
mesmo espaco que a uma funcao em Python: uma a flutuar num vazio, a outra
cortada a meio da frase. E uma resposta de assistente escrita em texto cru,
com crases pelo meio, nao e' uma resposta -- e' um despejo.

As duas sao opcionais de proposito: uma coleccao que nao as peca tem de gerar
exactamente o mesmo Java e o mesmo XML de antes. E' isso que a maior parte
destes testes segura.
"""

import unittest

from apkpy_lib.core.compiler import translate_python_to_android


CHAT = '''
from apkpy_lib import Screen, run, virtual_collection
TURNS = [
    {"id": "1", "who": "You", "msg": "diz me uma funcao"},
    {"id": "2", "who": "Ora", "msg": "Claro:\\n\\n```python\\ndef f():\\n    pass\\n```"},
]
home = Screen(id="home")
thread = virtual_collection(
    TURNS, template={"title": "{who}", "markdown": "{msg}"},
    id="thread", item_height="auto", buffer=3, screen=home,
)
run(start_screen=home)
'''

PLAIN = '''
from apkpy_lib import Screen, run, virtual_collection
ROWS = [{"id": "1", "title": "A", "subtitle": "b"}]
home = Screen(id="home")
rows = virtual_collection(
    ROWS, template={"title": "{title}", "subtitle": "{subtitle}"},
    id="rows", item_height=150, buffer=3, screen=home,
)
run(start_screen=home)
'''


def _build(source):
    out = translate_python_to_android(source)
    assert 'error.txt' not in out, out['error.txt'][:600]
    return out


class AutoHeightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = _build(CHAT)['java/Screen_homeActivity.java']

    def test_a_row_wraps_its_content_instead_of_being_measured_out(self):
        self.assertIn(
            'autoHeight ? android.view.ViewGroup.LayoutParams.WRAP_CONTENT',
            self.java)

    def test_a_row_still_has_a_floor_so_an_empty_one_is_not_invisible(self):
        self.assertIn('root.setMinimumHeight(', self.java)

    def test_the_list_stops_promising_a_fixed_size(self):
        # setHasFixedSize(true) e' exactamente a promessa que deixa de ser
        # verdade, e o RecyclerView acredita nela para medir o scroll.
        self.assertIn('setHasFixedSize(false)', self.java)

    def test_the_text_stops_being_cut_to_one_line(self):
        # Uma linha que pode crescer, com o texto cortado a uma linha, e' o
        # pior dos dois mundos.
        construction = self.java.split('new ApkpyVirtualAdapter(')[1]
        self.assertIn('99, 99,', construction)

    def test_the_content_column_stops_filling_the_row(self):
        self.assertIn(
            'grid || autoHeight ? android.view.ViewGroup.LayoutParams.WRAP_CONTENT',
            self.java)

    def test_the_generated_java_is_balanced(self):
        self.assertEqual(self.java.count('{'), self.java.count('}'))


class MarkdownRowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = _build(CHAT)
        cls.java = cls.out['java/Screen_homeActivity.java']

    def test_the_slot_reaches_the_adapter(self):
        self.assertIn('_template.put("markdown"', self.java)

    def test_the_row_uses_the_same_renderer_as_the_component(self):
        # Uma segunda implementacao seria uma segunda maneira de desenhar um
        # bloco de codigo, e mais cedo ou mais tarde as duas divergiam.
        self.assertIn('ApkpyRichContentView.apkpyMarkdown(', self.java)

    def test_the_class_that_draws_it_goes_in_the_apk(self):
        # Sem isto e' um cannot-find-symbol no fim do build, longe daqui.
        self.assertIn('java/ApkpyRichContentView.java', self.out)
        self.assertIn(
            'public static CharSequence apkpyMarkdown(',
            self.out['java/ApkpyRichContentView.java'])

    def test_a_row_with_nothing_to_draw_takes_no_space(self):
        self.assertIn('holder.markdown.setVisibility(source.isEmpty()', self.java)

    def test_the_answer_is_not_clipped_or_ellipsised(self):
        block = self.java.split('markdown = new android.widget.TextView')[1][:600]
        self.assertNotIn('setMaxLines', block)
        self.assertNotIn('TruncateAt', block)


class UntouchedWhenUnusedTests(unittest.TestCase):
    """O contrato do projecto: quem nao pede, nao paga."""

    @classmethod
    def setUpClass(cls):
        cls.out = _build(PLAIN)
        cls.java = cls.out['java/Screen_homeActivity.java']

    def test_a_plain_collection_keeps_its_fixed_rows(self):
        self.assertIn('setHasFixedSize(true)', self.java)
        self.assertIn('dp(parent, itemHeight)', self.java)

    def test_a_plain_collection_carries_no_markdown_code(self):
        self.assertNotIn('apkpyMarkdown', self.java)
        self.assertNotIn('markdownPattern', self.java)

    def test_the_rich_class_is_not_shipped_for_nothing(self):
        self.assertNotIn('java/ApkpyRichContentView.java', self.out)

    def test_a_plain_collection_still_cuts_its_text_to_one_line(self):
        construction = self.java.split('new ApkpyVirtualAdapter(')[1]
        self.assertIn('1, 1,', construction)


class ItemHeightValueTests(unittest.TestCase):
    def test_a_bad_item_height_is_reported_and_not_guessed(self):
        out = translate_python_to_android(PLAIN.replace(
            'item_height=150', 'item_height="tall"'))
        # O compilador nao corre o Python, por isso um valor mau cai no
        # default em vez de rebentar -- mas nunca em "auto".
        java = out['java/Screen_homeActivity.java']
        self.assertIn('setHasFixedSize(true)', java)

    def test_auto_is_recognised_whatever_the_casing(self):
        for value in ('"auto"', '"AUTO"', '" Auto "'):
            java = _build(PLAIN.replace(
                'item_height=150', 'item_height=%s' % value)
            )['java/Screen_homeActivity.java']
            self.assertIn('setHasFixedSize(false)', java, value)


class PreviewerParityTests(unittest.TestCase):
    """O Previewer aproxima os pixeis, mas a forma tem de ser a mesma."""

    def test_both_sides_read_the_same_two_options(self):
        from apkpy_lib.ui import virtual_collection, Screen
        screen = Screen(id="p")
        comp = virtual_collection(
            [{"id": "1", "who": "A", "msg": "# oi"}],
            template={"title": "{who}", "markdown": "{msg}"},
            id="p_thread", item_height="auto", screen=screen,
        )
        self.assertTrue(comp.kwargs['auto_height'])
        self.assertEqual(comp.kwargs['template']['markdown'], '{msg}')
        # E o numero continua a ser um numero.
        fixed = virtual_collection(
            [{"id": "1"}], template={"title": "{id}"},
            id="p_fixed", item_height=150, screen=screen,
        )
        self.assertFalse(fixed.kwargs['auto_height'])
        self.assertEqual(fixed.kwargs['item_height'], 150)

    def test_a_bad_item_height_says_what_it_wanted(self):
        from apkpy_lib.ui import virtual_collection, Screen
        screen = Screen(id="p2")
        with self.assertRaises(ValueError) as caught:
            virtual_collection([{"id": "1"}], id="bad", item_height="tall",
                               screen=screen)
        self.assertIn('auto', str(caught.exception))

    def test_the_markdown_styles_come_from_one_place(self):
        # Duas copias disto seriam duas maneiras de desenhar um bloco de
        # codigo, e o componente e a linha acabavam diferentes.
        from apkpy_lib.features import rich_content
        self.assertTrue(hasattr(rich_content, 'configure_markdown_tags'))
        self.assertTrue(hasattr(rich_content, 'render_markdown'))


if __name__ == '__main__':
    unittest.main()
