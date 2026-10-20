# -*- coding: utf-8 -*-
"""O corpo de um pedido, e o tempo que se espera pela resposta.

Estes testes seguram três defeitos que só apareciam depois de compilar:

1. `data={...}` compilava para `""`. O corpo desaparecia em silêncio, e um
   `body = {...}` nem sequer chegava a ser declarado em Java -- o nome ficava
   a ser usado sem existir. O Previewer, que corre o Python a sério, via o
   dicionário todo: a divergência clássica deste projeto.
2. Os tipos evaporavam. Uma API que valida o que recebe rejeita `"512"` onde
   esperava `512`, e o modelo "tudo é String" do gerador transformava todos
   os números em texto.
3. O timeout era 10 segundos, cravado dos dois lados. Uma resposta de um
   modelo de linguagem não cabe em 10s -- o pedido morria antes de chegar,
   sempre, e o que sobrava era um timeout genérico que não dizia porquê.

O que NÃO se testa aqui é o escape: quem serializa é o org.json de um lado e
o json do Python do outro, e nenhum dos dois precisa que lhe seguremos a mão.
O que se testa é que o texto do utilizador chega ao serializador em vez de ser
colado a uma string.
"""

import ast
import json
import unittest

from apkpy_lib.core.compiler import (
    _HTTPS_READ_TIMEOUT_MS,
    _https_body_java,
    _https_timeout_java,
    _json_node_to_java,
    _track_json_struct,
    translate_python_to_android,
)
from apkpy_lib.ui import _https_encode_body, _https_looks_json


def _build(source):
    result = translate_python_to_android(source)
    assert 'error.txt' not in result, result['error.txt'][:600]
    return result


def _java_of(source, screen='home'):
    return _build(source)['java/Screen_%sActivity.java' % screen]


def _to_java(literal, struct_vars=()):
    """Converte um literal Python escrito como texto na expressão Java."""
    node = ast.parse(literal, mode='eval').body
    return _json_node_to_java(node, _fake_val_to_java, struct_vars)


def _fake_val_to_java(node):
    """O `_val_to_java` real vive dentro do gerador; aqui basta o essencial."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return '"%s"' % node.value
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Name):
        return node.id
    raise AssertionError('no test uses %r' % ast.dump(node))


APP = '''
from apkpy_lib import Screen, button, https, label, run
home = Screen(id="home")
out = label("", id="out", screen=home)
def got(success, response):
    out.set_value(response)
def ask():
    https.post("https://example.test/v1",
               data={"model": "m", "max_tokens": 512, "stream": False,
                     "messages": [{"role": "user", "content": "olá"}]},
               headers={"x-api-key": "k"},
               timeout=120,
               on_response=got)
button("go", id="b", command=ask, screen=home)
run(start_screen=home)
'''


class BodyReachesTheWireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = _java_of(APP)

    def test_the_body_is_no_longer_an_empty_string(self):
        # O que aqui estava: executeHttpsRequest(..., "" != null ? ... : null)
        self.assertIn('_apkpyJsonObj(', self.java)
        self.assertNotIn('String.valueOf("")', self.java.split('executeHttpsRequest')[1][:400])

    def test_a_number_stays_a_number(self):
        call = self.java.split('_apkpyJsonObj(')[1]
        self.assertIn('"max_tokens", 512', call)
        self.assertNotIn('"max_tokens", "512"', call)

    def test_a_boolean_stays_a_boolean(self):
        self.assertIn('"stream", false', self.java)
        self.assertNotIn('"stream", "false"', self.java)

    def test_a_nested_list_of_objects_stays_nested(self):
        self.assertIn('_apkpyJsonArr(_apkpyJsonObj("role", "user"', self.java)

    def test_the_literal_is_built_once_and_not_twice(self):
        # A guarda `x != null ? String.valueOf(x) : null` construía o objeto
        # nos dois ramos do ternário. Um literal nunca é null.
        body = self.java.split('executeHttpsRequest("POST"')[1].split('new HttpsCallback')[0]
        self.assertEqual(body.count('"model", "m"'), 1, body)

    def test_a_name_keeps_its_null_guard(self):
        # Um nome pode mesmo ser null, e aí a guarda é o que evita o NPE.
        self.assertEqual(_https_body_java(None, _fake_val_to_java), 'null')
        named = _https_body_java(ast.parse('body', mode='eval').body, _fake_val_to_java)
        self.assertIn('!= null', named)

    def test_the_helpers_the_body_needs_are_in_the_class(self):
        for helper in ('private org.json.JSONObject _apkpyJsonObj(',
                       'private org.json.JSONArray _apkpyJsonArr(',
                       'private Object _apkpyJsonVal(',
                       'private int _apkpyTimeoutMs('):
            self.assertIn(helper, self.java, helper)

    def test_the_generated_java_is_balanced(self):
        # Uma chaveta solta dentro de uma string do Java gerado faria esta
        # conta mentir -- e é esta conta que diz se o ficheiro fecha.
        self.assertEqual(self.java.count('{'), self.java.count('}'))


class AssignedBodyTests(unittest.TestCase):
    """`body = {...}` numa linha e usado na seguinte."""

    APP = '''
from apkpy_lib import Screen, button, https, run
home = Screen(id="home")
def ask():
    msgs = [{"role": "user", "content": "olá"}]
    body = {"model": "m", "messages": msgs}
    https.post("https://example.test/v1", data=body)
button("go", id="b", command=ask, screen=home)
run(start_screen=home)
'''

    @classmethod
    def setUpClass(cls):
        cls.java = _java_of(cls.APP)

    def test_a_dict_assignment_declares_the_variable(self):
        # Sem o ramo do ast.Dict o assign não gerava linha nenhuma, e o Java
        # ficava a usar `body` sem que `body` existisse: cannot find symbol.
        self.assertIn('String body = _apkpyJsonObj(', self.java)

    def test_a_list_of_objects_is_not_a_list_of_strings(self):
        self.assertIn('String msgs = _apkpyJsonArr(_apkpyJsonObj(', self.java)

    def test_a_name_holding_json_goes_back_in_as_structure(self):
        # `{"messages": msgs}` com msgs em texto daria o array inteiro entre
        # aspas, que é uma coisa que nenhuma API aceita.
        self.assertIn('"messages", _apkpyJsonVal(String.valueOf(msgs))', self.java)

    def test_the_generated_java_is_balanced(self):
        self.assertEqual(self.java.count('{'), self.java.count('}'))


class StructTrackingTests(unittest.TestCase):
    def test_a_name_is_only_structure_while_it_holds_one(self):
        seen = set()
        _track_json_struct('x', ast.parse('{"a": 1}', mode='eval').body, seen)
        self.assertIn('x', seen)
        # Reatribuir a texto tem de esquecer: reinjetar isto como objeto daria
        # um corpo partido em vez de uma string.
        _track_json_struct('x', ast.parse('"olá"', mode='eval').body, seen)
        self.assertNotIn('x', seen)

    def test_an_untracked_name_is_quoted_like_any_other_text(self):
        # _apkpyJsonOut leaves text as it is; only the app's True, False and
        # None become JSON true, false and null.
        self.assertEqual(_to_java('{"a": b}'), '_apkpyJsonObj("a", _apkpyJsonOut(String.valueOf(b)))')

    def test_a_tracked_name_is_reparsed(self):
        self.assertEqual(_to_java('{"a": b}', {'b'}),
                         '_apkpyJsonObj("a", _apkpyJsonVal(String.valueOf(b)))')


class LiteralTypeTests(unittest.TestCase):
    def test_the_types_a_json_body_can_hold(self):
        self.assertEqual(_to_java('1'), '1')
        self.assertEqual(_to_java('True'), 'true')
        self.assertEqual(_to_java('False'), 'false')
        self.assertEqual(_to_java('None'), 'org.json.JSONObject.NULL')
        self.assertEqual(_to_java('"olá"'), '"olá"')
        self.assertEqual(_to_java('-3'), '-3')
        self.assertEqual(_to_java('0.7'), '0.7')

    def test_a_number_too_big_for_an_int_keeps_its_width(self):
        # Sem o L o javac recusa o literal, e o build morre no fim de tudo.
        self.assertEqual(_to_java('10000000000'), '10000000000L')

    def test_an_empty_object_is_still_an_object(self):
        self.assertEqual(_to_java('{}'), '_apkpyJsonObj()')
        self.assertEqual(_to_java('[]'), '_apkpyJsonArr()')


class TimeoutTests(unittest.TestCase):
    def test_the_default_is_long_enough_for_a_model(self):
        self.assertEqual(_https_timeout_java(None, _fake_val_to_java),
                         str(_HTTPS_READ_TIMEOUT_MS))
        self.assertGreaterEqual(_HTTPS_READ_TIMEOUT_MS, 30000)

    def test_seconds_become_milliseconds(self):
        node = ast.parse('120', mode='eval').body
        self.assertEqual(_https_timeout_java(node, _fake_val_to_java), '120000')

    def test_an_absurd_timeout_is_capped(self):
        node = ast.parse('99999', mode='eval').body
        self.assertEqual(_https_timeout_java(node, _fake_val_to_java), '600000')

    def test_a_value_that_is_not_a_literal_goes_through_the_helper(self):
        # Um Double.parseDouble nu rebentaria com um valor mau; o helper cai
        # no default em vez de matar o pedido.
        node = ast.parse('wait', mode='eval').body
        self.assertEqual(_https_timeout_java(node, _fake_val_to_java),
                         '_apkpyTimeoutMs(String.valueOf(wait), %d)' % _HTTPS_READ_TIMEOUT_MS)

    def test_the_timeout_reaches_the_connection(self):
        java = _java_of(APP)
        self.assertIn(', 120000, new HttpsCallback()', java)
        self.assertIn('conn.setReadTimeout(readTimeoutMs);', java)
        self.assertNotIn('conn.setReadTimeout(10000);', java)

    def test_a_request_without_a_timeout_gets_the_default(self):
        java = _java_of(APP.replace('               timeout=120,\n', ''))
        self.assertIn(', %d, new HttpsCallback()' % _HTTPS_READ_TIMEOUT_MS, java)


class WireDetailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = _java_of(APP)

    def test_a_json_body_says_so_without_being_asked(self):
        self.assertIn('_apkpyTagJsonBody(conn, data);', self.java)
        self.assertIn('application/json; charset=utf-8', self.java)

    def test_a_header_the_author_wrote_is_never_overwritten(self):
        self.assertIn('conn.getRequestProperty("Content-Type") != null) return;',
                      self.java)

    def test_the_body_and_the_answer_are_utf8(self):
        # O charset da plataforma servia por acaso no Android; um acento numa
        # resposta não é sítio para depender de um acaso.
        self.assertIn('os.write(data.getBytes("UTF-8"));', self.java)
        self.assertIn('buffer.toString("UTF-8")', self.java)

    def test_the_answer_keeps_its_line_breaks(self):
        # O readLine() colava as linhas todas sem separador.
        self.assertNotIn('while ((line = reader.readLine()) != null)', self.java)
        self.assertIn('_apkpyReadBody(is)', self.java)


class WorkerTests(unittest.TestCase):
    """O mesmo, no Worker -- a duplicação estrutural do costume."""

    APP = '''
from apkpy_lib import Screen, background_job, https, label, run
home = Screen(id="home")
label("x", id="l", screen=home)
def sync():
    https.post("https://example.test/v1",
               data={"model": "m", "max_tokens": 512}, timeout=90)
job = background_job("sync_job", run=sync, requires_network=True)
run(start_screen=home)
'''

    @classmethod
    def setUpClass(cls):
        out = _build(cls.APP)
        key = next(k for k in out if k.startswith('java/') and 'Worker' in k)
        cls.java = out[key]

    def test_the_worker_builds_the_same_body(self):
        self.assertIn('_apkpyJsonObj("model", "m", "max_tokens", 512)', self.java)

    def test_the_worker_honours_the_timeout_too(self):
        self.assertIn(', 90000);', self.java)
        self.assertIn('conn.setReadTimeout(readTimeoutMs);', self.java)

    def test_the_generated_java_is_balanced(self):
        self.assertEqual(self.java.count('{'), self.java.count('}'))


class ModuleConstantTests(unittest.TestCase):
    """Um URL escreve-se por pedaços, e isso tem de chegar ao Java."""

    APP = '''
from apkpy_lib import Screen, button, https, run
BASE = "https://api.example.test/v1beta/models/"
MODEL = "some-model"
URL = BASE + MODEL + ":generate"
KEY_HEADER = "x-goog-api-key"
home = Screen(id="home")
def ask():
    https.post(URL, data={"contents": []}, headers={KEY_HEADER: "k"})
button("go", id="b", command=ask, screen=home)
run(start_screen=home)
'''

    @classmethod
    def setUpClass(cls):
        cls.java = _java_of(cls.APP)

    def test_a_constant_built_by_joining_is_declared(self):
        # Sem isto o nome era usado sem existir, e o build morria longe daqui.
        self.assertIn(
            'private static final String URL = '
            '"https://api.example.test/v1beta/models/some-model:generate";',
            self.java)

    def test_the_joined_constant_is_the_one_that_gets_used(self):
        self.assertIn('String.valueOf(URL)', self.java)

    def test_a_name_can_be_a_header_key(self):
        self.assertIn('.put(KEY_HEADER, "k");', self.java)

    def test_a_piece_declared_later_is_reported_and_not_swallowed(self):
        # Isto lê o módulo de cima para baixo, como o Python o executaria.
        out = translate_python_to_android(self.APP.replace(
            'MODEL = "some-model"\nURL = BASE + MODEL + ":generate"',
            'URL = BASE + MODEL + ":generate"\nMODEL = "some-model"'))
        self.assertIn('error.txt', out)
        self.assertIn('U2027', out['error.txt'])

    def test_joining_things_that_are_not_text_is_left_alone(self):
        # `A + B` entre duas listas continua a ser assunto de outra pessoa.
        out = translate_python_to_android('''
from apkpy_lib import Screen, label, run
A = [1]
B = [2]
C = A + B
home = Screen(id="home")
label("x", id="l", screen=home)
run(start_screen=home)
''')
        self.assertNotIn('error.txt', out)


class PreviewerParityTests(unittest.TestCase):
    """O Previewer corre o Python a sério; o que tem de bater certo é a forma."""

    def test_a_dict_becomes_json_and_not_a_form(self):
        # O urlencode que aqui estava nunca teve par do outro lado -- no
        # Android um dict compilava para "", por isso não há uma única app
        # publicada a depender do form-encoding.
        body = _https_encode_body({"model": "m", "max_tokens": 512})
        parsed = json.loads(body.decode('utf-8'))
        self.assertEqual(parsed['max_tokens'], 512)
        self.assertNotIn(b'max_tokens=512', body)

    def test_the_types_survive_the_trip(self):
        parsed = json.loads(_https_encode_body(
            {"n": 512, "f": 0.7, "b": False, "xs": [{"k": "v"}]}).decode('utf-8'))
        self.assertIsInstance(parsed['n'], int)
        self.assertIsInstance(parsed['f'], float)
        self.assertIsInstance(parsed['b'], bool)
        self.assertEqual(parsed['xs'], [{"k": "v"}])

    def test_the_user_text_is_escaped_by_the_serialiser(self):
        raw = 'diz "olá"\ncom quebra'
        parsed = json.loads(_https_encode_body({"q": raw}).decode('utf-8'))
        self.assertEqual(parsed['q'], raw)

    def test_a_string_body_is_left_exactly_as_written(self):
        self.assertEqual(_https_encode_body('a=1&b=2'), b'a=1&b=2')
        self.assertEqual(_https_encode_body(b'raw'), b'raw')
        self.assertIsNone(_https_encode_body(None))

    def test_the_shape_rule_is_the_one_the_android_side_uses(self):
        # _apkpyJsonShape olha para o primeiro caractere, e isto também.
        self.assertTrue(_https_looks_json(b'  {"a": 1}'))
        self.assertTrue(_https_looks_json(b'[1]'))
        self.assertFalse(_https_looks_json(b'a=1'))
        self.assertFalse(_https_looks_json(b''))
        self.assertFalse(_https_looks_json(None))


if __name__ == '__main__':
    unittest.main()
