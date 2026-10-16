# -*- coding: utf-8 -*-
"""As quatro coisas que faltavam a uma conversa depois das linhas ricas.

Saltar para a mensagem nova, um campo que cresce com o que se escreve, um
bloco de codigo que se copia, e um circulo com as iniciais de quem fala.

Todas sao opcionais. O que a maior parte destes testes segura e' isso: quem
nao as pede tem de gerar exactamente o mesmo Java e o mesmo XML de antes.
"""

import base64
import json
import unittest

from apkpy_lib import motion
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.style_parser import wants_code_copy
from apkpy_lib.theme import (
    AVATAR_PALETTE,
    avatar_color,
    avatar_initials,
    avatar_text_color,
)


def _build(source):
    out = translate_python_to_android(source)
    assert 'error.txt' not in out, out['error.txt'][:600]
    return out


def _activity(source):
    return _build(source)['java/Screen_homeActivity.java']


CHAT = '''
from apkpy_lib import Screen, button, run, virtual_collection
TURNS = [{"id": "1", "who": "You", "msg": "ola"}]
home = Screen(id="home")
thread = virtual_collection(
    TURNS, template={"title": "{who}", "markdown": "{msg}"},
    id="thread", item_height="auto", screen=home,
)

def send():
    thread.merge_items([{"id": "2", "who": "Ora", "msg": "ola de volta"}])
    thread.scroll_to_end()

button("mandar", id="send", screen=home, command=send)
run(start_screen=home)
'''

PLAIN = '''
from apkpy_lib import Screen, button, run, virtual_collection
ROWS = [{"id": "1", "title": "A"}]
home = Screen(id="home")
rows = virtual_collection(
    ROWS, template={"title": "{title}"}, id="rows", screen=home,
)

def touch():
    rows.merge_items([{"id": "2", "title": "B"}])

button("tocar", id="b", screen=home, command=touch)
run(start_screen=home)
'''


class ScrollToTests(unittest.TestCase):
    """Uma conversa precisa de poder olhar para a mensagem que acabou de
    chegar. Ate' aqui so' existia `scrollToPosition(0)`, para quando se
    acrescenta por cima."""

    @classmethod
    def setUpClass(cls):
        cls.java = _activity(CHAT)

    def test_the_call_reaches_the_generated_java(self):
        self.assertIn('_apkpyScrollTo(vc1, vc1_items.size() - 1,', self.java)

    def test_the_recycler_becomes_a_field_so_a_callback_can_reach_it(self):
        # Sem isto a chamada de dentro de send() nao tem nada para tocar: a
        # RecyclerView era uma variavel local do onCreate.
        self.assertIn('private RecyclerView vc1;', self.java)

    def test_the_duration_comes_from_the_shared_motion_table(self):
        expected = motion.duration('nav', 'standard')
        self.assertIn('vc1_items.size() - 1, %d);' % expected, self.java)

    def test_motion_none_turns_the_animation_into_a_jump(self):
        source = CHAT.replace(
            'run(start_screen=home)',
            'from apkpy_lib import Theme\n'
            'run(start_screen=home, theme=Theme(motion="none"))',
        )
        java = _activity(source)
        self.assertIn('vc1_items.size() - 1, 0);', java)
        # Zero milissegundos e' o ramo que salta em vez de animar.
        self.assertIn('if (manager == null || ms <= 0)', java)

    def test_scroll_to_top_asks_for_position_zero(self):
        source = CHAT.replace(
            'thread.scroll_to_end()', 'thread.scroll_to_top()')
        self.assertIn('_apkpyScrollTo(vc1, 0,', _activity(source))

    def test_scroll_to_item_looks_the_row_up_by_its_key(self):
        source = CHAT.replace(
            'thread.scroll_to_end()', 'thread.scroll_to_item("2")')
        java = _activity(source)
        self.assertIn('_apkpyVcFind(vc1_items,', java)
        self.assertIn('>= 0) _apkpyScrollTo(vc1,', java)

    def test_a_scroll_by_position_does_not_drag_in_the_lookup(self):
        # Uma coleccao que so' salta para o fim nao tem de levar o codigo que
        # procura uma linha por chave.
        source = '''
from apkpy_lib import Screen, button, run, virtual_collection
home = Screen(id="home")
rows = virtual_collection(
    [{"id": "1", "title": "A"}], template={"title": "{title}"},
    id="rows", screen=home,
)

def go():
    rows.scroll_to_end()

button("ir", id="b", screen=home, command=go)
run(start_screen=home)
'''
        java = _activity(source)
        self.assertIn('_apkpyScrollTo(', java)
        self.assertNotIn('_apkpyVcFind(', java)
        self.assertNotIn('_apkpyVcMergeJson(', java)

    def test_the_generated_java_is_balanced(self):
        self.assertEqual(self.java.count('{'), self.java.count('}'))


class GrowingComposerTests(unittest.TestCase):
    """`rows` e' o minimo e `max-rows` o tecto. Entre os dois o campo cresce
    com o texto -- e agora nos dois lados, que era o problema."""

    def _layout(self, css):
        source = '''
from apkpy_lib import Screen, inputs, run
home = Screen(id="home")
inputs(id="field", placeholder="Escreve...", type="textarea", screen=home)
style = """%s"""
run(start_screen=home)
''' % css
        return _build(source)['res/layout/activity_screen_home.xml']

    def test_max_rows_becomes_the_ceiling(self):
        xml = self._layout('field { rows: 1; max-rows: 6; }')
        self.assertIn('android:minLines="1"', xml)
        self.assertIn('android:maxLines="6"', xml)

    def test_without_it_the_old_ceiling_is_untouched(self):
        xml = self._layout('field { rows: 4; }')
        self.assertIn('android:minLines="4"', xml)
        self.assertIn('android:maxLines="8"', xml)

    def test_a_ceiling_below_the_floor_is_raised_to_it(self):
        # Um tecto abaixo do chao nao e' um tecto, e' um campo de altura zero.
        xml = self._layout('field { rows: 5; max-rows: 2; }')
        self.assertIn('android:minLines="5"', xml)
        self.assertIn('android:maxLines="5"', xml)


class CodeCopyTests(unittest.TestCase):
    """`code-copy: button;` poe um "Copy" tocavel debaixo de cada bloco com
    fence, no componente markdown() e na linha da coleccao."""

    DOC = '''
from apkpy_lib import Screen, markdown, run, virtual_collection
home = Screen(id="home")
markdown("um bloco:\\n\\n```py\\nx = 1\\n```", id="doc", screen=home)
virtual_collection(
    [{"id": "1", "who": "Ora", "msg": "```py\\ny = 2\\n```"}],
    template={"title": "{who}", "markdown": "{msg}"},
    id="thread", item_height="auto", screen=home,
)
style = """%s"""
run(start_screen=home)
'''

    def _payload(self, css):
        xml = _build(self.DOC % css)['res/layout/activity_screen_home.xml']
        for line in xml.split('\n'):
            if 'apkpy-rich:' in line:
                blob = line.split('apkpy-rich:')[1].split('"')[0]
                return json.loads(base64.b64decode(blob).decode('utf-8'))
        self.fail('nao encontrei o payload do markdown')

    def test_the_stylesheet_declaration_reaches_the_component(self):
        self.assertTrue(self._payload('doc { code-copy: button; }')['copyCode'])

    def test_the_key_is_absent_when_nobody_asks(self):
        # O payload vai dentro do XML: uma chave a mais mudava o build de
        # todas as apps ja' escritas.
        self.assertNotIn('copyCode', self._payload('doc { color: #fff; }'))

    def test_the_row_passes_the_flag_to_the_adapter(self):
        java = _activity(self.DOC % 'thread { code-copy: button; }')
        self.assertIn('accentColor, copyCode));', java)
        construction = java.split('new ApkpyVirtualAdapter(')[1]
        self.assertIn('true, null);', construction)

    def test_a_row_that_does_not_ask_passes_false(self):
        java = _activity(self.DOC % 'doc { color: #fff; }')
        construction = java.split('new ApkpyVirtualAdapter(')[1]
        self.assertIn('false, null);', construction)

    def test_both_runtimes_read_the_declaration_with_the_same_parser(self):
        # Um lado a aceitar "Button" e o outro nao e' como uma folha de
        # estilos passa a querer dizer duas coisas.
        self.assertTrue(wants_code_copy({'code-copy': 'button'}))
        self.assertTrue(wants_code_copy({'code-copy': ' Button '}))
        self.assertFalse(wants_code_copy({'code-copy': 'none'}))
        self.assertFalse(wants_code_copy({}))


class AvatarTests(unittest.TestCase):
    """Um circulo com as iniciais de quem fala, na cor que o nome escolhe --
    a mesma cor nos dois lados, porque a tabela e' uma so'."""

    CHAT = '''
from apkpy_lib import Screen, run, virtual_collection
home = Screen(id="home")
virtual_collection(
    [{"id": "1", "who": "Ora", "msg": "ola"}],
    template={"avatar": "{who}", "title": "{who}", "markdown": "{msg}"},
    id="thread", item_height="auto", screen=home,
)
run(start_screen=home)
'''

    @classmethod
    def setUpClass(cls):
        cls.java = _activity(cls.CHAT)

    def test_the_palette_written_into_java_is_the_python_table(self):
        # Escrita a partir da tabela e nao a' mao: duas listas separadas
        # divergem no dia em que alguem mexe numa.
        expected = ', '.join(
            '0xFF' + colour.lstrip('#').upper() for colour in AVATAR_PALETTE
        )
        self.assertIn('private final int[] avatarBg = { %s };' % expected,
                      self.java)

    def test_the_ink_is_derived_by_the_same_rule_as_on_primary(self):
        expected = ', '.join(
            '0xFF' + avatar_text_color(colour).lstrip('#').upper()
            for colour in AVATAR_PALETTE
        )
        self.assertIn('private final int[] avatarInk = { %s };' % expected,
                      self.java)

    def test_the_index_is_a_sum_of_utf16_units_on_both_sides(self):
        self.assertIn('sum += value.charAt(i);', self.java)
        self.assertIn('Math.abs(sum) % avatarBg.length;', self.java)

    def test_the_pattern_reaches_the_template_the_adapter_reads(self):
        # O defeito que o APK apanhou e os testes nao: a paleta e os
        # ajudantes iam todos, mas o mapa do template nao levava a chave, e
        # `template.get("avatar")` vinha nulo -- circulo nenhum no ecra.
        self.assertIn('vc1_template.put("avatar", "{who}");', self.java)

    def test_the_circle_is_drawn_and_hidden_when_the_name_is_empty(self):
        self.assertIn('GradientDrawable.OVAL', self.java)
        self.assertIn('if (mark.isEmpty()) {', self.java)

    def test_a_collection_without_the_slot_carries_none_of_it(self):
        java = _activity(PLAIN)
        self.assertNotIn('avatarBg', java)
        self.assertNotIn('private String initials(', java)

    def test_initials_take_at_most_two_letters_and_uppercase_them(self):
        self.assertEqual(avatar_initials('Ora'), 'O')
        self.assertEqual(avatar_initials('Ana Silva'), 'AS')
        self.assertEqual(avatar_initials('  maria  joao  pereira  '), 'MJ')
        self.assertEqual(avatar_initials(''), '')
        self.assertEqual(avatar_initials(None), '')

    def test_the_same_name_always_lands_on_the_same_colour(self):
        self.assertEqual(avatar_color('Ora'), avatar_color('Ora'))
        self.assertIn(avatar_color('Ora'), AVATAR_PALETTE)

    def test_the_generated_java_is_balanced(self):
        self.assertEqual(self.java.count('{'), self.java.count('}'))


class UntouchedWhenUnusedTests(unittest.TestCase):
    """A promessa: uma app que nao peca nenhuma destas coisas gera o mesmo
    que gerava antes."""

    def test_a_plain_collection_carries_no_scroll_helper(self):
        java = _activity(PLAIN)
        self.assertNotIn('_apkpyScrollTo', java)
        self.assertNotIn('LinearSmoothScroller', java)

    def test_a_plain_collection_keeps_its_recycler_local(self):
        # Continua a ser campo porque merge_items mexe nela; o que nao pode
        # e' passar a campo so' por causa do scroll.
        source = PLAIN.replace(
            '    rows.merge_items([{"id": "2", "title": "B"}])',
            '    pass')
        self.assertNotIn('private RecyclerView vc1;', _activity(source))


if __name__ == '__main__':
    unittest.main()
