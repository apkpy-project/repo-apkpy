"""The Java of what runs with the app closed: services and background jobs."""
import ast
import json

from ..features import data as data_feature
from ..features import jobs as jobs_feature
from ..features import native as native_feature
from ..features import nfc as nfc_feature
from ..features import contacts as contacts_feature
from ..features import flashlight as flashlight_feature
from ..features import wallpaper as wallpaper_feature
from ..features import sensors as sensors_feature
from ..features import regex as regex_feature
from ..features import unpacking as unpacking_feature
from ..features import tuples as tuples_feature
from ..features import item_assignment as item_feature
from ..features import classes as classes_feature
from ..features import sets as sets_feature
from ..features import counters as counters_feature
from ..features import function_values as function_values_feature
from ..features import notifications as notifications_feature
from ..features import camera as camera_feature
from ... import job_rules
from .. import unsupported
from .. import i18n as i18n_feature

from .state import (
    _BODY_KEYS, _GLOBALS, _I18N, _MUTATED_LISTS, _NUMBERISH_NAMES, _NUMERIC_CONSTS,
    _NUMERIC_CONST_TEXT, _RETURNS_VALUE,
)
from .style import _java_int_literal
from .kinds import _int_literal, _json_call, _kind_from, _static_kind
from .expressions import (
    _shown_raw_java,
    _HTTPS_CONNECT_TIMEOUT_MS, _add_java, _affix_java, _arith_any_java, _callback_call_args,
    _check_translation_key, _cmds_definitely_return, _cond_shape_supported, _cond_to_java,
    _counter_call_java, _datetime_call_to_java, _delitem_java, _dict_method_java,
    _drop_unused_struct_fields, _escape_java_literal, _extreme_by_java, _forget_numberish,
    _format_kind, _formatted_java, _fstring_node_to_java, _has_sort_keys, _https_body_java,
    _https_timeout_java, _if_compare_cond, _index_java, _is_isinstance, _isinstance_java,
    _java_string_field, _json_module_java, _json_node_to_java, _json_value_java, _len_java,
    _list_call_java, _listop_java, _logic_value_java, _math_java, _may_be_singleton,
    _module_struct_fields, _mutated_list_read, _negate_any_java, _note_numberish,
    _numeric_call_java, _parenthesized, _percent_java, _repeat_java, _round_java, _set_call_java,
    _setitem_java, _slice_java, _sorted_java, _split_java, _sql_params_java, _storage_default_java,
    _storage_key_java, _str_format_java, _ternary_to_java, _text_method_java, _text_value_java,
    _track_json_struct, _truthy_java, _typed_operand, _unpack_java,
)
from .statements import (
    _assign_rhs_java, _emit_for_loop, _emit_list_append, _emit_print, _emit_raise, _emit_try_block,
    _emit_while_loop, _files_download_now_java, _line_mark,
)
from .numeric import (
    _ARITH_OPS, _arith_java, _bool_operand, _dict_copy_call, _float_call_java, _int_call_java,
)
from .prescan import _global_read, _global_sync_java, _singleton_fields
from .runtime_java import _emit_crypto_helpers, _emit_json_build_helpers


def _generate_worker_java(worker_class_name, cmds, package="com.apkpy.app", string_constants=None, functions_map=None, job=None, job_vars=None, boolean_first_arg_callbacks=None):
    """
    Gera uma classe `Worker` (androidx.work) que executa, periodicamente e em
    segundo plano, o corpo da função Python associada a `service.every(...)`.

    Com `job` preenchido (um dict de `jobs_feature`), o MESMO gerador serve as
    tarefas persistentes de `background_job(...)`: acrescenta o acesso aos dados
    de entrada (`job.input`), o reporte de progresso (`job.progress`) e o
    resultado (`job.retry()` / `job.fail()`), em vez de duplicar o gerador.

    O Worker corre fora de qualquer Activity (pode até executar com a app
    fechada), por isso só suporta o subconjunto de comandos "background-safe":
    storage, db, https, toast e lógica simples (if/atribuições). Chamadas que
    dependem de uma Activity (componentes de UI, permissões em runtime) são
    ignoradas — o utilizador é avisado disso na documentação da API.
    """
    string_constants = string_constants or {}
    functions_map = functions_map or {}
    _job_vars = set(job_vars or ())
    # A mesma marca da Activity: um callback cujo 1o argumento e um booleano
    # (https on_response, files.download on_result). Sem ela o Worker
    # declarava `String ok` e chamava-o com um boolean -- o javac recusava.
    _bool_callbacks = set(boolean_first_arg_callbacks or ())
    _uses_download = [False]
    _download_seq = [0]
    _cur_bool_args = [set()]

    def _cmds_use_notify(cmds_list):
        for c in cmds_list:
            if isinstance(c, dict):
                if c.get('type') == 'notify':
                    return True
                for body_key in ('true_body', 'false_body'):
                    if c.get(body_key) and _cmds_use_notify(c[body_key]):
                        return True
        return False
    has_notify = _cmds_use_notify(cmds)

    def _cmds_use_share(cmds_list):
        for c in cmds_list:
            if isinstance(c, dict):
                if c.get('type') == 'share':
                    return True
                for body_key in ('true_body', 'false_body'):
                    if c.get(body_key) and _cmds_use_share(c[body_key]):
                        return True
        return False
    has_share = _cmds_use_share(cmds)

    def _cmds_use_clipboard_copy(cmds_list):
        for c in cmds_list:
            if isinstance(c, dict):
                if c.get('type') == 'clipboard_copy':
                    return True
                for body_key in ('true_body', 'false_body'):
                    if c.get(body_key) and _cmds_use_clipboard_copy(c[body_key]):
                        return True
        return False
    has_clipboard_copy = _cmds_use_clipboard_copy(cmds)

    lines = []
    lines.append(f"package {package};")
    lines.append("")
    lines.append("import androidx.annotation.NonNull;")
    lines.append("import androidx.work.Worker;")
    lines.append("import androidx.work.WorkerParameters;")
    lines.append("import android.content.Context;")
    lines.append("import android.content.SharedPreferences;")
    lines.append("import android.widget.Toast;")
    lines.append("import android.os.Handler;")
    lines.append("import android.os.Looper;")
    lines.append("")
    lines.append(f"public class {worker_class_name} extends Worker {{")
    lines.append("")

    # doWork() devolve Result; os pythonCallback_ devolvem void/String.
    # Um `return` cru tem de gerar Java diferente em cada caso.
    _in_do_work = [True]
    _job_needs_outcome = bool(job) and jobs_feature.commands_set_outcome(cmds, functions_map)
    if _job_needs_outcome:
        lines.extend(jobs_feature.worker_fields())
        lines.append("")

    for const_name, const_val in string_constants.items():
        lines.append(_java_string_field(const_name, const_val))
    # Um numero escrito no modulo (VAT = 23) e um campo como os outros: viaja
    # como String e a aritmetica le-o de la.
    for _num_name, _num_val in _NUMERIC_CONST_TEXT[0].items():
        if _num_name in (string_constants or {}):
            continue
        lines.append(f'    private static final String {_num_name} = "{_num_val}";')
    # Uma lista, um tuplo ou um dict escrito no modulo e' um campo tambem,
    # com o seu texto JSON: sem ele, len(ITEMS) ou PRICES["tea"] numa funcao
    # nomeavam um simbolo que nenhuma classe declarava.
    lines.extend(_module_struct_fields(string_constants))
    lines.extend(_singleton_fields())
    if string_constants:
        lines.append("")

    lines.append(f"    public {worker_class_name}(@NonNull Context context, @NonNull WorkerParameters params) {{")
    lines.append("        super(context, params);")
    lines.append("    }")
    lines.append("")
    lines.append("    @NonNull")
    lines.append("    @Override")
    lines.append("    public Result doWork() {")
    lines.append("        try {")

    def _numeric_java_expr(node):
        """Ver _numeric_java_expr em _generate_activity_java — mesma lógica,
        duplicada aqui porque _generate_worker_java tem o seu próprio _val_to_java.
        Devolve (expressão Java, is_float) ou None."""
        if isinstance(node, ast.Name) and node.id in _numeric_vars:
            # variável local já conhecida como número (preserva int vs float)
            _ref = _global_read(node.id) if node.id in _GLOBALS[0] else node.id
            if _numeric_vars[node.id]:
                return (f"Double.parseDouble(String.valueOf({_ref}))", True)
            return (f"Long.parseLong(String.valueOf({_ref}))", False)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'int':
            return (_int_call_java(node, _numeric_java_expr, _val_to_java), False)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'float':
            return (_float_call_java(node, _numeric_java_expr, _val_to_java), True)
        _nc = _numeric_call_java(node, _numeric_java_expr, _val_to_java)
        if _nc is not None:
            return _nc
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            return None
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return (_java_int_literal(node.value, node), False)
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            return (str(node.value), True)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            # -x: o sinal de um numero que ja se sabe ser numero.
            inner = _numeric_java_expr(node.operand)
            if inner is None:
                return None
            if isinstance(node.op, ast.USub) and not inner[1]                     and _int_literal(node.operand) is None:
                # -n de um int: o menor long trocado de sinal dava-se a si
                # proprio; os ints do Python nao tem esse fundo.
                return (f"Math.negateExact((long)({inner[0]}))", False)
            sign = '-' if isinstance(node.op, ast.USub) else '+'
            return (f"({sign}{inner[0]})", inner[1])
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Invert):
            # ~n of an int is -(n + 1) in Python and in Java's long alike.
            inner = _numeric_java_expr(node.operand)
            if inner is None or inner[1]:
                return None
            return (f"(~((long)({inner[0]})))", False)
        if isinstance(node, ast.BinOp) and isinstance(node.op, _ARITH_OPS):
            left = _bool_operand(node.left) or _numeric_java_expr(node.left)
            right = _bool_operand(node.right) or _numeric_java_expr(node.right)
            if left is None or right is None:
                return None
            return _arith_java(node.op, left, right, node.right)
        if isinstance(node, ast.IfExp):
            # Both sides the same kind of number (see _numeric_arg_kind).
            yes = _numeric_java_expr(node.body)
            no = _numeric_java_expr(node.orelse)
            if yes is None or no is None or yes[1] != no[1] \
                    or not _cond_shape_supported(node.test):
                return None
            cond = _cond_to_java(node.test, _val_to_java, _cur_bool_args[0])
            if not cond:
                return None
            return (f"({cond} ? {yes[0]} : {no[0]})", yes[1])
        return None

    # Variáveis de `for row in rows:` (JSON): row["k"] compila p/ _jsonGet
    _json_iter_vars = set()

    # Nomes locais que o gerador viu receber um dict ou uma lista literal. Em
    # Java guardam texto JSON, por isso aninhá-los noutro literal tem de os
    # repor como estrutura — senão `{"messages": msgs}` sai com o array inteiro
    # entre aspas, que é uma coisa que nenhuma API aceita.
    _json_struct_vars = set()

    # O que cada nome local guarda, quando o codigo o diz: 'list', 'dict',
    # 'text', ou 'other' depois de ser reatribuido a outra coisa.
    _struct_kinds = {}

    # Variáveis locais que guardam um número (assign de int()/float()/aritmética).
    # Mapeia nome -> is_float, para que `valor = float(x)` continue numérico em
    # `valor * 2` (senão seria tratado como String e a conta evaporava). Reset no
    # início de cada corpo de função/handler (ver _gen_cmds / _gen_cmds_local).
    _numeric_vars = {}

    def _val_to_java(node):
        if notifications_feature.is_value_call(node):
            return notifications_feature.value_java(node)
        if regex_feature.internal(node):
            return regex_feature.java_value(node, _val_to_java)
        if sets_feature.op_of(node) is not None:
            return _set_call_java(node, _val_to_java)
        if counters_feature.op_of(node) is not None:
            return _counter_call_java(node, _val_to_java)
        if function_values_feature.internal(node) == function_values_feature.FN:
            # A function handed on as a value: its name.
            return '"%s"' % node.args[0].value
        if function_values_feature.internal(node) == function_values_feature.CALL:
            return "_apkpyCall(%s)" % ", ".join(
                "String.valueOf(%s)" % _val_to_java(a) for a in node.args)
        if _dict_copy_call(node, _val_to_java):
            # dict(d): a copy, as d.copy() is.
            return _val_to_java(ast.copy_location(ast.Call(
                func=ast.Attribute(value=node.args[0], attr='copy', ctx=ast.Load()),
                args=[], keywords=[]), node))
        if classes_feature.is_intrinsic(node):
            return classes_feature.value_java(node, _val_to_java, _assign_rhs_java)
        if node is None:
            return '""'
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                return f'"{_escape_java_literal(node.value)}"'
            elif isinstance(node.value, bool):
                return 'true' if node.value else 'false'
            elif node.value is None:
                return "ApkpyValues.NONE"
            if isinstance(node.value, int):
                return _java_int_literal(node.value, node)
            if isinstance(node.value, (bytes, complex)) or node.value is Ellipsis:
                # b"abc" went out as b'abc', 2j as 2j: Java has neither, and
                # javac stopped far from the line that wrote them.
                unsupported.raise_unsupported(
                    node, cause="bytes (b\"...\"), complex numbers (2j) and ... as a value "
                                "are not translated yet. Text on the phone is a str.",
                    suggestions=["Write text instead: \"abc\"."])
            return str(node.value)
        elif isinstance(node, ast.UnaryOp) and isinstance(
                node.op, (ast.USub, ast.UAdd, ast.Invert)):
            try:
                literal = ast.literal_eval(node)
                if isinstance(literal, (int, float)) and not isinstance(literal, bool):
                    return str(literal)
            except (TypeError, ValueError, SyntaxError):
                pass
            _ne = _numeric_java_expr(node)
            if _ne is not None:
                return f"_apkpyFloat({_ne[0]})" if _ne[1] else f"String.valueOf({_ne[0]})"
            if unsupported.reaches_other_runtime(node):
                return '""'
            _rt = _negate_any_java(node, _val_to_java)
            if _rt is not None:
                return _rt
            # -n de um texto voltava como "", sem uma palavra.
            unsupported.raise_untranslated_arithmetic(node)
        elif isinstance(node, ast.Name):
            # Uma lista de modulo a que a app faz append vive no estado
            # partilhado: inlinar o literal aqui daria sempre a lista de
            # origem, por muito que ela tivesse crescido.
            if node.id in _MUTATED_LISTS[0]:
                return _mutated_list_read(node.id)
            if node.id in _GLOBALS[0]:
                return _global_read(node.id)
            return node.id
        elif isinstance(node, ast.IfExp):
            return _ternary_to_java(node, _val_to_java, _cur_bool_args[0]) or unsupported.raise_untranslated_condition(node.test)
        elif isinstance(node, (ast.List, ast.Tuple)):
            # Lista Python → array JSON em runtime (iterável com `for x in xs:`).
            # Passa pelo mesmo conversor do dict para que uma lista de objetos
            # continue a ser uma lista de objetos: o `asList(String.valueOf(...))`
            # que aqui estava punha cada `{...}` entre aspas, como texto.
            # Um tuplo e' o mesmo aqui: `return total, count` devolvia vazio,
            # e stats()[0] lia de nada.
            return _json_node_to_java(
                node, _val_to_java, _json_struct_vars) + ".toString()"
        elif isinstance(node, ast.Dict):
            # Dicionário Python → objeto JSON. Sem este ramo caía no `""` do
            # fim: o corpo de um https.post desaparecia em silêncio, e um
            # `body = {...}` nem sequer chegava a ser declarado em Java.
            return _json_node_to_java(
                node, _val_to_java, _json_struct_vars) + ".toString()"
        elif isinstance(node, ast.Subscript):
            slice_node = node.slice
            # texto[0:2] — uma fatia saía daqui como `(x)[Integer.parseInt("")]`,
            # que nem é Java: o build morria com um erro de sintaxe longe daqui,
            # ou pior, não morria. Apanhada na origem em vez de na guarda final.
            if isinstance(slice_node, ast.Slice):
                # texto[a:b]. O Python apara fora dos limites e conta do fim
                # com indices negativos; o substring do Java rebenta. O helper
                # tem as regras do Python, para os dois lados responderem o
                # mesmo em vez de um devolver texto e o outro fechar a app.
                return _slice_java(node, _val_to_java)
            if isinstance(slice_node, ast.Index):  # Python 3.8 compat
                slice_node = slice_node.value
            if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str) \
                    and isinstance(node.value, ast.Name) and node.value.id in _json_iter_vars:
                # row["k"] dentro de `for row in rows:` — row é texto JSON
                key_esc = slice_node.value.replace('"', '\\"')
                return f'_jsonGet(String.valueOf({node.value.id}), "{key_esc}")'
            if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
                # Uma chave em texto e sempre a leitura de um objeto, nunca um
                # indice. Mandada para o _apkpyListGet, o parseInt falhava e a
                # resposta era vazio, sem uma palavra.
                key_esc = slice_node.value.replace('"', '\\"')
                return (f'_jsonGet(String.valueOf({_val_to_java(node.value)}), '
                        f'"{key_esc}")')
            # lista[0] saia daqui como `(x)[Integer.parseInt(...)]`, que nao e
            # Java: nao se indexa uma String com parentesis retos. E uma lista
            # aqui e texto JSON, por isso quem sabe le-la e o helper.
            return _index_java(node, _val_to_java)
        elif (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'get'
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == 'storage'):
            # storage.get(k, d) inside an expression rather than on its
            # own line. Without this it fell through to "" in silence --
            # the failure mode this compiler pays the most for, because
            # the Previewer reads the value and the phone reads nothing.
            _sk = _val_to_java(node.args[0]) if node.args else '""'
            _sd = None
            if len(node.args) > 1:
                _sd = node.args[1]
            else:
                for _kw in node.keywords:
                    if _kw.arg == 'default':
                        _sd = _kw.value
            return ('_apkpyStorageGet(String.valueOf(%s), String.valueOf(%s))'
                    % (_sk, _val_to_java(_sd)))
        # appearance.get() -- o modo em vigor, para uma linha poder dizer
        # qual esta' escolhido. O default e' o que o Theme declarou.
        elif (isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute)
              and node.func.attr == 'get'
              and isinstance(node.func.value, ast.Name)
              and node.func.value.id == 'appearance'):
            return ('_apkpyStorageGet("__apkpy_appearance", '
                    '_apkpyDeclaredAppearance())')
        # app.version_code() / app.version_name() -- lidos do pacote
        # INSTALADO, por isso sao a versao que esta mesmo a correr e
        # nao a que o codigo-fonte esperava.
        elif (isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute)
              and node.func.attr in ('version_code', 'version_name')
              and isinstance(node.func.value, ast.Name)
              and node.func.value.id == 'app'):
            return ('_apkpyVersionCode()' if node.func.attr == 'version_code'
                    else '_apkpyVersionName()')
        # flashlight.is_on() / available() — o estado real da luz, que
        # qualquer coisa no telemóvel pode ter mudado.
        elif flashlight_feature.is_value_call(node):
            return flashlight_feature.value_java(node)
        elif wallpaper_feature.is_value_call(node):
            return wallpaper_feature.value_java(node)
        elif camera_feature.is_value_call(node):
            return camera_feature.value_java(node)
        # sensors.available() / battery.level/charging/saver()
        elif sensors_feature.is_value_call(node):
            return sensors_feature.value_java(node)
        # crash.last() -- o relatorio da execucao anterior, ou vazio.
        elif (isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute)
              and node.func.attr == 'last'
              and isinstance(node.func.value, ast.Name)
              and node.func.value.id == 'crash'):
            return 'ApkpyCrashHandler.last(getApplicationContext())'
        # language.get() -- a escolha guardada, senao a lingua do aparelho.
        # E a mesma ordem do Previewer, que e o que faz os dois concordarem.
        elif (isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute)
              and node.func.attr in ('get', 'available')
              and isinstance(node.func.value, ast.Name)
              and node.func.value.id == 'language'):
            if node.func.attr == 'available':
                _tags = [_I18N[0]['default']] + sorted(
                    tag for tag in _I18N[0]['table'] if tag != _I18N[0]['default'])
                return '"%s"' % _escape_java_literal(
                    json.dumps([tag for tag in _tags if tag]))
            return ('_apkpyStorageGet("__apkpy_language", '
                    'java.util.Locale.getDefault().toLanguageTag())')
        # d.get(k, padrao), d.keys(), d.values(), d.items(), x.copy(): after
        # storage.get(), state.get() and the rest, which are the app's calls.
        elif _dict_method_java(node, _val_to_java) is not None:
            return _dict_method_java(node, _val_to_java)
        elif _text_method_java(node, _val_to_java) is not None:
            return _text_method_java(node, _val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == 'format' and isinstance(node.func.value, ast.Constant) \
                and isinstance(node.func.value.value, str) \
                and _str_format_java(node, _val_to_java) is not None:
            return _str_format_java(node, _val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'format' and 1 <= len(node.args) <= 2 and not node.keywords:
            # format(x, spec): the f-string's {x:spec}.
            _spec = node.args[1] if len(node.args) > 1 else ast.Constant(value='')
            if isinstance(_spec, ast.Constant):
                _spec = ast.JoinedStr(values=[_spec] if _spec.value else [])
            else:
                _spec = ast.JoinedStr(values=[ast.FormattedValue(value=_spec, conversion=-1, format_spec=None)])
            return _formatted_java(_val_to_java(node.args[0]), _format_kind(node.args[0], _val_to_java),
                                   _spec, -1, node, _val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'chr' and len(node.args) == 1:
            return "_apkpyChr(Long.parseLong(String.valueOf(%s).trim()))" % _val_to_java(node.args[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'ord' and len(node.args) == 1:
            return "String.valueOf(_apkpyOrd(String.valueOf(%s)))" % _val_to_java(node.args[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'split':
            # Uma lista, que aqui e texto JSON. O String[] do Java nao era:
            # String.valueOf dele e um endereco, e um for sobre isso nao corria.
            return _split_java(node, _val_to_java)

        # Métodos de string: .upper()/.lower()/.strip()/.replace(a, b)
        # (devolvem String → encaixam no modelo "tudo é String")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in (
                'upper', 'lower', 'strip', 'replace', 'title', 'find',
                'count', 'join', 'startswith', 'endswith'):
            base = _val_to_java(node.func.value)
            m = node.func.attr
            _a0 = (f"String.valueOf({_val_to_java(node.args[0])})"
                   if node.args else '""')
            if m == 'title':
                return f"_apkpyTitle(String.valueOf({base}))"
            if m == 'find':
                return f"String.valueOf(String.valueOf({base}).indexOf({_a0}))"
            if m == 'count':
                if _kind_from(_val_to_java, node.func.value) == 'list':
                    return f"_apkpyListCount(String.valueOf({base}), {_a0})"
                return f"_apkpyCount(String.valueOf({base}), {_a0})"
            if m == 'join':
                if node.args and _kind_from(_val_to_java, node.args[0]) == 'dict':
                    # A dict gives its keys, as in Python; its JSON text
                    # was joined letter by letter.
                    _a0 = f"_apkpyKeys(String.valueOf({_val_to_java(node.args[0])})).toString()"
                return f"_apkpyJoin(String.valueOf({base}), {_a0})"
            if m in ('startswith', 'endswith'):
                # str(True) em Python e "True", com maiuscula; o
                # String.valueOf(boolean) do Java da "true". Mostrar um ao
                # lado do outro seria divergencia visivel numa etiqueta.
                return f'_apkpyBool({_affix_java(node, base, _val_to_java)})'
            if m == 'upper':
                # Locale.ROOT: sem ele um telemovel turco transforma "I" num
                # i sem ponto e deixa de bater certo com o Python.
                return f"String.valueOf({base}).toUpperCase(java.util.Locale.ROOT)"
            if m == 'lower':
                return f"String.valueOf({base}).toLowerCase(java.util.Locale.ROOT)"
            if m == 'strip':
                return f"String.valueOf({base}).trim()"
            a = _val_to_java(node.args[0]) if node.args else '""'
            b = _val_to_java(node.args[1]) if len(node.args) > 1 else '""'
            return f"String.valueOf({base}).replace(String.valueOf({a}), String.valueOf({b}))"

        # len(x): nº de itens se x for lista/JSON, senão nº de caracteres.
        # Devolvido como String (modelo "tudo é String"); _apkpyLen decide em runtime.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'len':
            return _len_java(node, _val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == unpacking_feature.UNPACK:
            return _unpack_java(node, _val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == item_feature.LISTOP:
            return _listop_java(node, _val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in ('sorted', 'reversed') and len(node.args) == 1 \
                and not isinstance(node.args[0], ast.Starred):
            return _sorted_java(node, _val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == 'index' and len(node.args) == 1 and not node.keywords:
            # lista.index(x) or texto.index(sub): where it is, or the ValueError.
            _ik = 3 if _kind_from(_val_to_java, node.func.value) == 'text' else 0
            return "_apkpyIndexOf(String.valueOf(%s), %s, %d)" % (
                _val_to_java(node.func.value), _json_value_java(node.args[0], _val_to_java), _ik)
        elif isinstance(node, (ast.Compare, ast.BoolOp)) or (
                isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not)):
            return _logic_value_java(node, _val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == item_feature.SETITEM:
            return _setitem_java(node, _val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == item_feature.DELITEM:
            return _delitem_java(node, _val_to_java)
        # list(x) — em Python isto tira uma copia para quem recebe nao ficar
        # com a mesma lista. Aqui o valor E texto JSON, que ja e imutavel: a
        # copia acontece por si, e a traducao honesta e o proprio valor.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name)                 and node.func.id == 'list':
            return _list_call_java(node, _val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'json_get':
            json_arg = _val_to_java(node.args[0]) if node.args else '""'
            path_arg = _val_to_java(node.args[1]) if len(node.args) > 1 else '""'
            return f"_jsonGet(String.valueOf({json_arg}), {path_arg})"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'db' \
                and node.func.attr == 'last_insert_id':
            return '_dbLastInsertId()'
        # db.query(...) inline numa expressão (ex.: for row in db.query(...))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'db' \
                and node.func.attr == 'query':
            sql_arg = _val_to_java(node.args[0]) if node.args else '""'
            params_node = node.args[1] if len(node.args) > 1 else None
            if params_node is None:
                for kw in node.keywords:
                    if kw.arg == 'params':
                        params_node = kw.value
            _qp = _sql_params_java(params_node, _val_to_java)
            return f"_sqliteQuery(String.valueOf({sql_arg}), {_qp})" if _qp else f"_sqliteQuery(String.valueOf({sql_arg}))"
        # random.randint(a, b) / random.choice(lista) / random.random()
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'random':
            _rattr = node.func.attr
            if _rattr == 'randint' and len(node.args) >= 2:
                _ra = _val_to_java(node.args[0]); _rb = _val_to_java(node.args[1])
                return f"_apkpyRandInt(String.valueOf({_ra}), String.valueOf({_rb}))"
            if _rattr == 'choice' and node.args:
                _rl = _val_to_java(node.args[0])
                return f"_apkpyChoice(String.valueOf({_rl}))"
            if _rattr == 'random':
                return "String.valueOf(Math.random())"

        # datetime.now()/date()/time()/year()/month()/day()/hour()/minute()/second()
        # (o preview corre o datetime real do Python; no Android usa SimpleDateFormat
        # — o formato coincide, os valores ao milissegundo não, igual ao random.)
        elif _datetime_call_to_java(node) is not None:
            return _datetime_call_to_java(node)
        # job.input("chave") / job.attempt() — valores do Worker de um job
        elif jobs_feature.value_expression(node, _val_to_java, _job_vars) is not None:
            return jobs_feature.value_expression(node, _val_to_java, _job_vars)
        # files.path("nome") → caminho absoluto do ficheiro local (offline)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'files' \
                and node.func.attr == 'path':
            _name = _val_to_java(node.args[0]) if node.args else '""'
            return f"(new java.io.File(getApplicationContext().getFilesDir(), String.valueOf({_name})).getAbsolutePath())"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'auth' \
                and node.func.attr == 'token':
            # Renewed in the background a few minutes before it expires.
            return 'ApkpyAuth.token(getApplicationContext())'
        # auth.claims() -> the id_token's payload, as a JSON object.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'auth' \
                and node.func.attr == 'claims':
            return 'ApkpyAuth.claims(getApplicationContext())'
        # auth.is_logged_in() as a value, not only in an if.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'auth' \
                and node.func.attr == 'is_logged_in':
            return '(ApkpyAuth.loggedIn(getApplicationContext()) ? ApkpyValues.TRUE : ApkpyValues.FALSE)'
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'crypto' \
                and node.func.attr == 'hash_password':
            pw_arg = _val_to_java(node.args[0]) if node.args else '""'
            algo, iters = 'sha256', 200000
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                algo = str(node.args[1].value).lower()
            if len(node.args) > 2 and isinstance(node.args[2], ast.Constant):
                iters = int(node.args[2].value)
            for kw in node.keywords:
                if kw.arg == 'algo' and isinstance(kw.value, ast.Constant):
                    algo = str(kw.value.value).lower()
                elif kw.arg == 'iterations' and isinstance(kw.value, ast.Constant):
                    iters = int(kw.value.value)
            algo = 'sha512' if algo == 'sha512' else 'sha256'
            iters = max(1, iters)
            return f'_apkpyHashPassword(String.valueOf({pw_arg}), "{algo}", {iters})'
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'crypto' \
                and node.func.attr in ('encrypt', 'decrypt'):
            arg = _val_to_java(node.args[0]) if node.args else '""'
            # password= changes the key AND the format: the result becomes a
            # standard AES-GCM box that travels, instead of one only this
            # phone's Keystore can open.
            pw_node = None
            for _kw in node.keywords:
                if _kw.arg == 'password':
                    pw_node = _kw.value
            if pw_node is None and len(node.args) > 1:
                pw_node = node.args[1]
            if pw_node is not None:
                pw = _val_to_java(pw_node)
                helper = ('_apkpyEncryptPw' if node.func.attr == 'encrypt'
                          else '_apkpyDecryptPw')
                return (f'{helper}(String.valueOf({arg}), '
                        f'String.valueOf({pw}))')
            helper = '_apkpyEncrypt' if node.func.attr == 'encrypt' else '_apkpyDecrypt'
            return f'{helper}(String.valueOf({arg}))'

        # crypto.token(n) -> n bytes de SecureRandom em hex. Existe porque
        # quem precisa de um id de sessao alcanca o `random`, que e' previsivel.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'crypto' \
                and node.func.attr == 'token':
            count = 16
            if node.args and isinstance(node.args[0], ast.Constant):
                try:
                    count = max(1, min(64, int(node.args[0].value)))
                except (TypeError, ValueError):
                    count = 16
            return f'_apkpyToken({count})'

        # crypto.totp(secret) -> os digitos de um autenticador. Sem rede,
        # sem conta: HMAC-SHA1 sobre o relogio, como manda o RFC 6238.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'crypto' \
                and node.func.attr == 'totp':
            secret = _val_to_java(node.args[0]) if node.args else '""'
            digits, period = 6, 30
            for _kw in node.keywords:
                if _kw.arg in ('digits', 'period') and isinstance(_kw.value, ast.Constant):
                    try:
                        if _kw.arg == 'digits':
                            digits = max(6, min(8, int(_kw.value.value)))
                        else:
                            period = max(1, int(_kw.value.value))
                    except (TypeError, ValueError):
                        pass
            return f'_apkpyTotp(String.valueOf({secret}), {digits}, {period})'

        # crypto.hash(t) / crypto.hash_file(p) -> SHA-256 em hex. Integridade
        # e comparacao; palavras-passe continuam no hash_password.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'crypto' \
                and node.func.attr in ('hash', 'hash_file'):
            arg = _val_to_java(node.args[0]) if node.args else '""'
            helper = '_apkpySha256' if node.func.attr == 'hash' else '_apkpySha256File'
            return f'{helper}(String.valueOf({arg}))'
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'int':
            return f"String.valueOf({_int_call_java(node, _numeric_java_expr, _val_to_java)})"

        # float(x) → parsing numérico decimal (String, como o int())
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'float':
            # _apkpyFloat: float("12345678") is 12345678.0 in Python and
            # was 1.2345678E7 here.
            return f"_apkpyFloat({_float_call_java(node, _numeric_java_expr, _val_to_java)})"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'str':
            if node.args and isinstance(node.args[0], ast.Constant) \
                    and (node.args[0].value is None or isinstance(node.args[0].value, bool)):
                return '"%s"' % node.args[0].value      # str(False) is "False", not "false"
            inner = _val_to_java(node.args[0]) if node.args else '""'
            if node.args and tuples_feature.is_tuple(node.args[0]):
                # str((1, 2)) is (1, 2), and str((1,)) is (1,).
                return f"_apkpyShowTuple(String.valueOf({inner}))"
            if node.args and tuples_feature.holds_tuples(node.args[0]):
                # str(c.most_common(2)) is [('tea', 2), ('jam', 1)].
                return f"_apkpyShowTuples(String.valueOf({inner}))"
            if node.args and _kind_from(_val_to_java, node.args[0]) in ('list', 'dict'):
                # str([1, "a", None]) is [1, 'a', None], not the JSON it is kept as.
                return f"_apkpyShow(String.valueOf({inner}))"
            # str(flag) is the text "True", not the True of the app: in a
            # list it went in as JSON true and came out "true". Only what can
            # hold one of them is wrapped: text written out, a sum, an
            # f-string are text already.
            text = (f"ApkpyValues.text(String.valueOf({inner}))"
                    if node.args and _may_be_singleton(node.args[0])
                    else f"String.valueOf({inner})")
            # str(d["a"]) of {"a": ["tea"]}: ['tea'], not the JSON ["tea"].
            raw = _shown_raw_java(node.args[0], text, _val_to_java) if node.args else None
            return raw or text
        # isinstance(x, T): True / False of the app.
        elif _is_isinstance(node):
            return f"({_isinstance_java(node, _val_to_java)} ? ApkpyValues.TRUE : ApkpyValues.FALSE)"
        # bool(x): Python's truth of x, as the True / False of the app.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'bool' \
                and len(node.args) <= 1 and not node.keywords:
            if not node.args:
                return "ApkpyValues.FALSE"
            return f"({_truthy_java(node.args[0], _val_to_java)} ? ApkpyValues.TRUE : ApkpyValues.FALSE)"

        # t("chave") dentro de uma funcao: em runtime e o getString que
        # escolhe a lingua, exactamente como o layout faz com @string/.
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 't' and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)):
            _key = node.args[0].value
            _check_translation_key(_key, node)
            return "getString(R.string.%s)" % i18n_feature.resource_name(_key)

        # math.sqrt(x) / math.pi -> java.lang.Math, 1 para 1 (ver _MATH_CALLS).
        elif (isinstance(node, (ast.Call, ast.Attribute))
                and _math_java(node, _val_to_java) is not None):
            return "String.valueOf(%s)" % _math_java(node, _val_to_java)
        elif _json_call(node) is not None and _json_module_java(node, _val_to_java) is not None:
            # json.loads(text) / json.dumps(value, ...): features/json_module.py
            return _json_module_java(node, _val_to_java)

        # pow(a, b, m): a whole number, exact (see _numeric_call_java).
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'pow' and len(node.args) == 3 and not node.keywords:
            _pm = _numeric_call_java(node, _numeric_java_expr, _val_to_java)
            if _pm is None:
                unsupported.raise_unsupported(
                    node,
                    cause=('pow() with a modulus works on whole numbers, and ApkPy '
                           'cannot tell that these are.'),
                    suggestions=['Say which kind of number each one is: '
                                 'pow(int(a), int(b), 7).'],
                )
            return f"String.valueOf({_pm[0]})"

        # min/max(items, key=...): the keys came from features/sort_key.py.
        elif _has_sort_keys(node):
            return _extreme_by_java(node, _val_to_java)
        # abs / min / max / sum. Passam por helpers em vez de irem diretos ao
        # Math porque o Python distingue inteiro de decimal (abs(-3) e 3, nao
        # 3.0) e aqui todos os valores sao texto -- so um helper pode manter
        # essa diferenca.
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in ('abs', 'min', 'max', 'sum')
                and node.args and not node.keywords):
            _bn = node.func.id
            if _bn == 'abs' and len(node.args) == 1:
                return "_apkpyAbs(String.valueOf(%s))" % _val_to_java(node.args[0])
            if _bn == 'sum' and len(node.args) == 1:
                return "_apkpySum(String.valueOf(%s))" % _val_to_java(node.args[0])
            if _bn in ('min', 'max'):
                _vals = ", ".join("String.valueOf(%s)" % _val_to_java(a)
                                  for a in node.args)
                return "_apkpyExtreme(%s, %s)" % (
                    'true' if _bn == 'max' else 'false', _vals)
            unsupported.raise_unsupported(node)

        # round(x) -> inteiro mais próximo ; round(x, n) -> n casas decimais.
        #
        # Math.rint e nao Math.round. O Python arredonda o meio para o PAR
        # (round(2.5) == 2) e o Math.round manda sempre para cima, por isso
        # round(2.5) dava 2 no Previewer e 3 no telemovel, sem uma palavra.
        # Estava aqui escrito que era "irrelevante para dinheiro vindo de uma
        # divisao" — e' o contrario: dividir uma conta ao meio e' o caminho
        # mais curto para um .5 exato. O Math.rint tem a regra do Python.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'round':
            # round(x) devolve um int em Python, e round(um int, n) tambem.
            return _round_java(node, _val_to_java, _numeric_java_expr)
        elif isinstance(node, ast.JoinedStr):
            return _fstring_node_to_java(node, _val_to_java)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) \
                and isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
            # "%.2f" % x: text formatting, not the remainder of a division.
            return _percent_java(node, _val_to_java)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, _ARITH_OPS):
            _ne = _numeric_java_expr(node)
            if _ne is not None:
                # O sinalizador is_float diz quando o resultado e um decimal:
                # so ai a apresentacao do Java diverge da do Python.
                if _ne[1]:
                    return f"_apkpyFloat({_ne[0]})"
                return f"String.valueOf({_ne[0]})"
            if isinstance(node.op, ast.Add):
                return _add_java(node, _val_to_java, _numeric_java_expr)
            if _repeat_java(node, _val_to_java, _numeric_java_expr) is not None:
                return _repeat_java(node, _val_to_java, _numeric_java_expr)
            if unsupported.reaches_other_runtime(node):
                # job.attempt() e vazio na copia da Activity, e de proposito.
                return '""'
            # item["price"] * item["qty"]: decidido quando a app corre.
            _rt = _arith_any_java(node, _val_to_java)
            if _rt is not None:
                return _rt
            # Uma conta sem traducao voltava como "": o Previewer calculava e o
            # telemovel mostrava nada, sem uma palavra no build.
            unsupported.raise_untranslated_arithmetic(node, _typed_operand(node, _val_to_java))
        # Um bloco native e um metodo da Activity do ecra; o corpo de um job
        # corre num Worker, que nao tem ecra nenhum de onde o pedir.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and native_feature.function_for(node.func.id) is not None:
            native_feature.refuse_in_job_call(node)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions_map:
            _fargs = ", ".join(f"String.valueOf({_val_to_java(a)})" for a in node.args)
            return f"pythonCallback_{node.func.id}({_fargs})"
        # A mesma guarda da cópia da Activity (ver _val_to_java lá em cima).
        unsupported.check_value(node)
        return '""'

    # A comparison between two values that are not written out asks this
    # whether either is a number (_compare_node_to_java).
    _val_to_java.numeric = _numeric_java_expr
    _val_to_java.bool_names = lambda: _cur_bool_args[0]

    _val_to_java.kind_of = lambda node: _static_kind(node, _struct_kinds)

    def _dict_node_to_java(node, var_name, indent):
        result = [f"{indent}java.util.Map<String, String> {var_name} = new java.util.HashMap<>();"]
        if isinstance(node, ast.Dict):
            for k_node, v_node in zip(node.keys, node.values):
                result.append(f"{indent}{var_name}.put({_val_to_java(k_node)}, {_val_to_java(v_node)});")
        return result

    # Variáveis declaradas como boolean no Worker (p/ _cond_to_java)
    _worker_bool_vars = set()

    def _gen_lambda_body(cmds_list, indent, declared):
        """O corpo de uma transacao e um lambda que devolve String: la dentro
        um `return x` e `return String.valueOf(x)`, nao o Result do doWork()."""
        saved = _in_do_work[0]
        _in_do_work[0] = False
        try:
            _gen_cmds(cmds_list, indent, declared)
        finally:
            _in_do_work[0] = saved

    def _gen_cmds(cmds_list, indent, declared=None, params=(), list_params=(), param_kinds=None):
        # *declared* — ver o _gen_cmds das Activities: evita redeclarar uma
        # variável Java quando o Python a reatribui (ex.: dentro de um for).
        # *params*: os parametros do metodo, que o Java ja declarou.
        if declared is None:
            declared = set(params)
            _numeric_vars.clear()  # novo corpo top-level → esquece numéricos anteriores
            _NUMBERISH_NAMES[0] = set()
            _struct_kinds.clear()
            _struct_kinds.update(param_kinds or {})
            _struct_kinds.update({p: 'list' for p in list_params})
            _numeric_vars.update(_NUMERIC_CONSTS[0])
        for c in cmds_list:
            _line_mark(lines, c, indent)
            ctype = c['type'] if isinstance(c, dict) else None
            _forget_numberish(c)
            if isinstance(c, str):
                lines.append(f"{indent}_toast(\"{c}\");")
            elif ctype in jobs_feature.COMMAND_TYPES:
                jobs_feature.emit_command(lines, indent, c, _val_to_java, "worker")
            elif ctype in flashlight_feature.COMMAND_TYPES:
                flashlight_feature.emit_command(
                    lines, indent, c, _val_to_java, functions_map, scope="worker",
                )
            elif ctype in wallpaper_feature.COMMAND_TYPES:
                wallpaper_feature.emit_command(
                    lines, indent, c, _val_to_java, functions_map, scope="worker",
                )
            elif ctype in camera_feature.COMMAND_TYPES:
                camera_feature.emit_command(lines, indent, c, _val_to_java, functions_map, scope='worker')
            elif ctype in nfc_feature.COMMAND_TYPES:
                nfc_feature.emit_command(lines, indent, c, _val_to_java, functions_map, scope='worker')
            elif ctype in contacts_feature.COMMAND_TYPES:
                contacts_feature.emit_command(lines, indent, c, _val_to_java, scope='worker')
            elif ctype == 'camera_view_control' or ctype in sensors_feature.COMMAND_TYPES:
                # A sensor is registered against a screen's lifecycle and a
                # Worker has no screen. Watching one here would keep the
                # sensor hub awake with nobody to tell -- and a comment in the
                # Java was all anyone got told.
                job_rules.refuse_command(c)
            elif ctype == 'function_call':
                # Uma chamada a uma funcao do proprio utilizador. O metodo era
                # gerado (_collect_callback_names encontrava-o) e nunca era
                # chamado: `def task(): enviar()` dava um doWork() vazio.
                if native_feature.function_for(c['name']) is not None:
                    native_feature.refuse_in_job(c)
                if function_values_feature.is_call_name(c['name']):
                    unsupported.raise_unsupported(
                        c.get('node') or ast.copy_location(ast.Pass(), ast.Pass()),
                        cause='A function kept in a value is not called inside a background '
                              'job yet.',
                        suggestions=['Call the function by its name in the job.'])
                if c['name'] not in functions_map:
                    unsupported.raise_unknown_function(
                        c['name'], c.get('lineno', 0), functions_map)
                _fc_args = _callback_call_args(
                    c['name'], c.get('args_nodes', []), _val_to_java,
                    functions_map, _bool_callbacks, _cur_bool_args[0])
                lines.append(f"{indent}pythonCallback_{c['name']}({_fc_args});")
            elif ctype == 'if_has_permission':
                # Ver se uma permissao ja foi dada nao precisa de ecra -- so
                # PEDI-LA precisa. O contexto da aplicacao responde igual.
                lines.append(
                    f"{indent}if (androidx.core.content.ContextCompat.checkSelfPermission("
                    f"getApplicationContext(), android.Manifest.permission.{c['perm']})"
                    f" == android.content.pm.PackageManager.PERMISSION_GRANTED) {{")
                _gen_cmds(c['true_body'], indent + "    ", declared)
                lines.append(f"{indent}}} else {{")
                _gen_cmds(c['false_body'], indent + "    ", declared)
                lines.append(f"{indent}}}")
            elif ctype == 'files_delete':
                name_expr = _val_to_java(c['name_node']) if c.get('name_node') else '""'
                lines.append(
                    f"{indent}new java.io.File(getApplicationContext().getFilesDir(),"
                    f" String.valueOf({name_expr})).delete();")
            elif ctype == 'files_download':
                # O Worker ja esta fora da UI thread: descarrega aqui e responde
                # antes da linha seguinte, como o Previewer faz dentro de um job.
                _uses_download[0] = True
                _download_seq[0] += 1
                url_expr = _val_to_java(c['url_node']) if c.get('url_node') else '""'
                name_expr = _val_to_java(c['name_node']) if c.get('name_node') else '""'
                path_var = f"_apkpyDownload{_download_seq[0]}"
                lines.append(
                    f"{indent}String {path_var} = _filesDownloadNow("
                    f"String.valueOf({url_expr}), String.valueOf({name_expr}));")
                if c.get('callback'):
                    lines.append(
                        f"{indent}pythonCallback_{c['callback']}"
                        f"(!{path_var}.isEmpty(), {path_var});")
            elif ctype == 'data_observer':
                job_rules.refuse_command(c)
            elif ctype in data_feature.COMMAND_TYPES:
                data_feature.emit_command(
                    lines, indent, c, _val_to_java, _gen_lambda_body,
                    functions_map, declared, scope='worker',
                    returns=_cmds_definitely_return,
                )
            elif ctype == 'toast':
                msg_expr = _val_to_java(c['msg_node']) if c.get('msg_node') else '""'
                lines.append(f"{indent}_toast(String.valueOf({msg_expr}));")
            elif ctype == 'notify' or ctype.startswith('notification_'):
                notifications_feature.emit_command(lines, c, _val_to_java, indent, scope='worker')
            elif ctype == 'share':
                text_expr  = _val_to_java(c['text_node']) if c.get('text_node') else '""'
                title_expr = f"String.valueOf({_val_to_java(c['title_node'])})" if c.get('title_node') else 'null'
                lines.append(f"{indent}_share(String.valueOf({text_expr}), {title_expr});")
            elif ctype == 'clipboard_copy':
                text_expr = _val_to_java(c['text_node']) if c.get('text_node') else '""'
                lines.append(f"{indent}_clipboardCopy(String.valueOf({text_expr}));")
            elif ctype == 'storage_set':
                lines.append(f"{indent}_apkpyStorageSet({_storage_key_java(c, _val_to_java)}, String.valueOf({_val_to_java(c['val_node'])}));")
            elif ctype == 'storage_delete':
                lines.append(f"{indent}getApplicationContext().getSharedPreferences(\"apkpy_storage\", Context.MODE_PRIVATE).edit().remove({_storage_key_java(c, _val_to_java)}).apply();")
            elif ctype == 'storage_clear':
                lines.append(f"{indent}SharedPreferences prefs_clr = getApplicationContext().getSharedPreferences(\"apkpy_storage\", Context.MODE_PRIVATE);")
                lines.append(f"{indent}prefs_clr.edit().clear().apply();")
            elif ctype == 'storage_get_assign':
                _decl = "" if c['var'] in declared else "String "
                declared.add(c['var'])
                lines.append(f"{indent}{_decl}{c['var']} = _apkpyStorageGet({_storage_key_java(c, _val_to_java)}, {_storage_default_java(c, _val_to_java)});")
            elif ctype == 'db_execute':
                _p = _sql_params_java(c.get('params_node'), _val_to_java)
                _args = f", {_p}" if _p else ""
                lines.append(f"{indent}_sqliteExecute(String.valueOf({_val_to_java(c['sql_node'])}){_args});")
            elif ctype == 'db_begin':
                lines.append(f"{indent}_dbBegin();")
            elif ctype == 'db_commit':
                lines.append(f"{indent}_dbCommit();")
            elif ctype == 'db_rollback':
                lines.append(f"{indent}_dbRollback();")
            elif ctype == 'db_query_assign':
                _p = _sql_params_java(c.get('params_node'), _val_to_java)
                _args = f", {_p}" if _p else ""
                _decl = "" if c['var'] in declared else "String "
                declared.add(c['var'])
                lines.append(f"{indent}{_decl}{c['var']} = _sqliteQuery(String.valueOf({_val_to_java(c['sql_node'])}){_args});")
            elif ctype == 'global_sync':
                lines.append(f"{indent}{_global_sync_java(c['name'])}")
            elif ctype == 'local_string_assign':
                _decl = "" if c['var'] in declared else "String "
                declared.add(c['var'])
                lines.append(f"{indent}{_decl}{c['var']} = {_assign_rhs_java(c['val_node'], _val_to_java)};")
                _track_json_struct(c['var'], c['val_node'], _json_struct_vars, _struct_kinds, _val_to_java.kind_of)
                _ne_t = _numeric_java_expr(c['val_node'])
                if _ne_t is not None:
                    _numeric_vars[c['var']] = _ne_t[1]
                else:
                    _numeric_vars.pop(c['var'], None)
                _note_numberish(c['var'], c['val_node'], _numeric_java_expr, _ne_t)
            elif ctype == 'crypto_verify_assign':
                _decl = "" if c['var'] in declared else "boolean "
                declared.add(c['var'])
                lines.append(f"{indent}{_decl}{c['var']} = _apkpyVerifyPassword(String.valueOf({_val_to_java(c['pw_node'])}), String.valueOf({_val_to_java(c['stored_node'])}));")
                _worker_bool_vars.add(c['var'])
            elif ctype in ('https_get', 'https_post'):
                method = c.get('method', "GET" if ctype == 'https_get' else "POST")
                url_val = _val_to_java(c['url_node'])
                callback_name = c['callback'] if c.get('callback') else None
                _timeout = _https_timeout_java(c.get('timeout_node'), _val_to_java)
                headers_node = c.get('headers_node')
                if headers_node is not None:
                    h_var = f"_headers_{id(c) & 0xFFFF}"
                    lines.extend(_dict_node_to_java(headers_node, h_var, indent))
                    headers_arg = h_var
                else:
                    headers_arg = "null"
                data_arg = (_https_body_java(c.get('data_node'), _val_to_java)
                            if method in ("POST", "PUT", "PATCH") else "null")
                resp_var = f"_resp_{id(c) & 0xFFFF}"
                lines.append(f"{indent}String[] {resp_var} = _executeHttpsRequestSync(\"{method}\", String.valueOf({url_val}), {data_arg}, {headers_arg}, {_timeout});")
                if callback_name:
                    lines.append(f"{indent}pythonCallback_{callback_name}(Boolean.parseBoolean({resp_var}[0]), {resp_var}[1]);")
            elif ctype == 'if_compare':
                cond = _if_compare_cond(c, _val_to_java)
                lines.append(f"{indent}if ({cond}) {{")
                _gen_cmds(c['true_body'], indent + "    ", declared)
                lines.append(f"{indent}}} else {{")
                _gen_cmds(c['false_body'], indent + "    ", declared)
                lines.append(f"{indent}}}")
            elif ctype == 'if_cond':
                cond = _cond_to_java(c['test'], _val_to_java, _worker_bool_vars | _cur_bool_args[0]) or unsupported.raise_untranslated_condition(c['test'])
                lines.append(f"{indent}if ({cond}) {{")
                _gen_cmds(c['true_body'], indent + "    ", declared)
                lines.append(f"{indent}}} else {{")
                _gen_cmds(c['false_body'], indent + "    ", declared)
                lines.append(f"{indent}}}")
            elif ctype == 'if_var':
                # Tambem os argumentos booleanos do callback em curso (o `ok` de
                # um on_response/on_result), como a Activity ja fazia.
                lines.append(f"{indent}if {_parenthesized(_cond_to_java(ast.Name(id=c['var'], ctx=ast.Load()), _val_to_java, _worker_bool_vars | _cur_bool_args[0]))} {{")
                _gen_cmds(c['true_body'], indent + "    ", declared)
                lines.append(f"{indent}}} else {{")
                _gen_cmds(c['false_body'], indent + "    ", declared)
                lines.append(f"{indent}}}")
            elif ctype == 'list_append':
                _emit_list_append(lines, indent, c, _val_to_java, _json_iter_vars)
            elif ctype == 'raise':
                _emit_raise(lines, indent, c, _val_to_java, _numeric_java_expr)
            elif ctype == 'print':
                _emit_print(lines, indent, c, _val_to_java)
            elif ctype == 'try_block':
                _emit_try_block(lines, indent, c,
                                lambda b, ind: _gen_cmds(b, ind, declared),
                                declared)
            elif ctype == 'for_loop':
                declared.add(c['var'])
                _emit_for_loop(lines, indent, c, _val_to_java,
                               lambda b, ind: _gen_cmds(b, ind, declared),
                               _json_iter_vars, _numeric_vars)
            elif ctype == 'while_loop':
                _emit_while_loop(lines, indent, c, _val_to_java,
                                 lambda b, ind: _gen_cmds(b, ind, declared),
                                 _worker_bool_vars | _cur_bool_args[0])
            elif ctype == 'break':
                lines.append(f"{indent}break;")
            elif ctype == 'continue':
                lines.append(f"{indent}continue;")
            elif ctype == 'return':
                if _in_do_work[0]:
                    # doWork() devolve Result — `return;` ou `return String...`
                    # aqui era ERRO de compilacao Java. Um return antecipado
                    # (tipico a seguir a job.retry()) fecha o trabalho com o
                    # resultado certo.
                    if _job_needs_outcome:
                        lines.append(
                            f"{indent}return {jobs_feature.worker_return_expression()};"
                        )
                    elif job:
                        # O resultado de um job deixa a ultima palavra onde o
                        # status() do ecra a le (o WorkManager apaga o progress).
                        lines.append(f"{indent}return _jobFinish(true);")
                    else:
                        lines.append(f"{indent}return Result.success();")
                elif c.get('value_node') is not None:
                    lines.append(f"{indent}return {_text_value_java(c['value_node'], _val_to_java)};")
                else:
                    lines.append(f"{indent}return ApkpyValues.NONE;" if _RETURNS_VALUE[0] else f"{indent}return;")
            else:
                # Tudo o que o Worker nao sabe escrever era deitado fora aqui,
                # e o doWork() compilava vazio. Agora para o build a dizer o
                # que foi escrito, em que linha, e porque.
                job_rules.refuse_command(c)

    _gen_cmds(cmds, "            ")

    lines.append("        } catch (Exception e) {")
    lines.append("            e.printStackTrace();")
    lines.append("            return Result.retry();")
    lines.append("        }")
    # Se o corpo ja devolve em todos os caminhos, este resultado final e
    # INALCANCAVEL, e em Java um statement inalcancavel nao compila. Era o que
    # acontecia a qualquer `def task(): ... return x` -- a forma mais natural
    # de escrever um trabalho. O exemplo publicado escapava por acaso: acaba
    # num notify(), sem return.
    if not _cmds_definitely_return(cmds):
        if _job_needs_outcome:
            lines.extend(jobs_feature.worker_result_lines("        "))
        elif job:
            lines.append("        return _jobFinish(true);")
        else:
            lines.append("        return Result.success();")
    lines.append("    }")
    lines.append("")
    if job:
        _job_helpers = jobs_feature.worker_helpers(lines, job)
        if _job_helpers:
            lines.extend(_job_helpers)
            lines.append("")

    # ── Helpers (toast thread-safe, SQLite, HTTPS síncrono, JSON) ────────────
    lines.append("    private void _toast(final String msg) {")
    lines.append("        new Handler(Looper.getMainLooper()).post(new Runnable() {")
    lines.append("            @Override")
    lines.append("            public void run() {")
    lines.append("                Toast.makeText(getApplicationContext(), msg, Toast.LENGTH_SHORT).show();")
    lines.append("            }")
    lines.append("        });")
    lines.append("    }")
    lines.append("")
    if has_share:
        lines.append("    private void _share(String text, String title) {")
        lines.append("        android.content.Intent sendIntent = new android.content.Intent(android.content.Intent.ACTION_SEND);")
        lines.append("        sendIntent.setType(\"text/plain\");")
        lines.append("        sendIntent.putExtra(android.content.Intent.EXTRA_TEXT, text);")
        lines.append("        android.content.Intent chooser = android.content.Intent.createChooser(sendIntent, (title == null || title.isEmpty()) ? \"Partilhar via\" : title);")
        lines.append("        chooser.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK);")
        lines.append("        getApplicationContext().startActivity(chooser);")
        lines.append("    }")
        lines.append("")
    if has_clipboard_copy:
        lines.append("    private void _clipboardCopy(String text) {")
        lines.append("        android.content.ClipboardManager cm = (android.content.ClipboardManager) getApplicationContext().getSystemService(Context.CLIPBOARD_SERVICE);")
        lines.append("        cm.setPrimaryClip(android.content.ClipData.newPlainText(\"ApkPy\", text));")
        lines.append("    }")
        lines.append("")
    lines.append("    // Conexão partilhada durante uma transação (db.begin/commit/rollback); null fora dela.")
    lines.append("    private android.database.sqlite.SQLiteDatabase _txDb = null;")
    lines.append("    // rowid do último INSERT — devolvido por db.last_insert_id().")
    lines.append("    private long _lastInsertId = -1;")
    lines.append("")
    lines.append("    private void _sqliteExecute(String query) {")
    lines.append("        _sqliteExecute(query, null);")
    lines.append("    }")
    lines.append("")
    lines.append("    /** Versão parametrizada: os `?` da query são preenchidos com bind seguro (anti SQL injection). */")
    lines.append("    private void _sqliteExecute(String query, String[] args) {")
    lines.append("        try {")
    lines.append("            android.database.sqlite.SQLiteDatabase db = (_txDb != null) ? _txDb : getApplicationContext().openOrCreateDatabase(\"apkpy_app.db\", Context.MODE_PRIVATE, null);")
    lines.append("            if (args == null) { db.execSQL(query); } else { db.execSQL(query, args); }")
    lines.append("            android.database.Cursor _idCur = db.rawQuery(\"SELECT last_insert_rowid()\", null);")
    lines.append("            if (_idCur.moveToFirst()) { _lastInsertId = _idCur.getLong(0); }")
    lines.append("            _idCur.close();")
    lines.append("            if (_txDb == null) { db.close(); }")
    lines.append("        } catch (Exception e) {")
    lines.append("            e.printStackTrace();")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    private String _sqliteQuery(String query) {")
    lines.append("        return _sqliteQuery(query, null);")
    lines.append("    }")
    lines.append("")
    lines.append("    /** Versão parametrizada: os `?` da query são preenchidos com bind seguro (anti SQL injection). */")
    lines.append("    private String _sqliteQuery(String query, String[] args) {")
    lines.append("        org.json.JSONArray jsonArray = new org.json.JSONArray();")
    lines.append("        boolean _ownDb = (_txDb == null);")
    lines.append("        android.database.sqlite.SQLiteDatabase db = null;")
    lines.append("        android.database.Cursor cursor = null;")
    lines.append("        try {")
    lines.append("            db = _ownDb ? getApplicationContext().openOrCreateDatabase(\"apkpy_app.db\", Context.MODE_PRIVATE, null) : _txDb;")
    lines.append("            cursor = db.rawQuery(query, args);")
    lines.append("            if (cursor.moveToFirst()) {")
    lines.append("                do {")
    lines.append("                    org.json.JSONObject jsonObject = new org.json.JSONObject();")
    lines.append("                    int columnCount = cursor.getColumnCount();")
    lines.append("                    for (int i = 0; i < columnCount; i++) {")
    lines.append("                        jsonObject.put(cursor.getColumnName(i), cursor.getString(i));")
    lines.append("                    }")
    lines.append("                    jsonArray.put(jsonObject);")
    lines.append("                } while (cursor.moveToNext());")
    lines.append("            }")
    lines.append("        } catch (Exception e) {")
    lines.append("            e.printStackTrace();")
    lines.append("        } finally {")
    lines.append("            if (cursor != null) cursor.close();")
    lines.append("            if (_ownDb && db != null) db.close();")
    lines.append("        }")
    lines.append("        return jsonArray.toString();")
    lines.append("    }")
    lines.append("")
    lines.append("    /** db.last_insert_id() — rowid do último INSERT, como String. */")
    lines.append("    private String _dbLastInsertId() {")
    lines.append("        return String.valueOf(_lastInsertId);")
    lines.append("    }")
    lines.append("")
    lines.append("    /** db.begin() — abre uma transação na conexão partilhada. */")
    lines.append("    private void _dbBegin() {")
    lines.append("        try {")
    lines.append("            if (_txDb != null) return;")
    lines.append("            _txDb = getApplicationContext().openOrCreateDatabase(\"apkpy_app.db\", Context.MODE_PRIVATE, null);")
    lines.append("            _txDb.beginTransaction();")
    lines.append("        } catch (Exception e) { e.printStackTrace(); }")
    lines.append("    }")
    lines.append("")
    lines.append("    /** db.commit() — grava tudo o que foi feito desde db.begin(). */")
    lines.append("    private void _dbCommit() {")
    lines.append("        if (_txDb == null) return;")
    lines.append("        try {")
    lines.append("            _txDb.setTransactionSuccessful();")
    lines.append("        } catch (Exception e) { e.printStackTrace(); }")
    lines.append("        finally {")
    lines.append("            try { _txDb.endTransaction(); _txDb.close(); } catch (Exception ignored) {}")
    lines.append("            _txDb = null;")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    /** db.rollback() — desfaz tudo desde db.begin() (sem setTransactionSuccessful). */")
    lines.append("    private void _dbRollback() {")
    lines.append("        if (_txDb == null) return;")
    lines.append("        try { _txDb.endTransaction(); _txDb.close(); } catch (Exception e) { e.printStackTrace(); }")
    lines.append("        _txDb = null;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** Pedido HTTPS síncrono — seguro aqui porque doWork() já corre fora da UI thread. */")
    lines.append("    private String[] _executeHttpsRequestSync(String method, String urlString, String data, java.util.Map<String, String> extraHeaders, int readTimeoutMs) {")
    lines.append("        try {")
    lines.append("            java.net.URL url = new java.net.URL(urlString);")
    lines.append("            java.net.HttpURLConnection conn = (java.net.HttpURLConnection) url.openConnection();")
    lines.append("            try {")
    lines.append("                conn.setRequestMethod(method);")
    lines.append("            } catch (java.net.ProtocolException pe) {")
    lines.append("                // HttpURLConnection não aceita PATCH — fallback standard via override")
    lines.append("                conn.setRequestProperty(\"X-HTTP-Method-Override\", method);")
    lines.append("                conn.setRequestMethod(\"POST\");")
    lines.append("            }")
    lines.append("            conn.setRequestProperty(\"User-Agent\", \"ApkPyApp\");")
    lines.append("            if (extraHeaders != null) {")
    lines.append("                for (java.util.Map.Entry<String, String> _entry : extraHeaders.entrySet()) {")
    lines.append("                    conn.setRequestProperty(_entry.getKey(), _entry.getValue());")
    lines.append("                }")
    lines.append("            }")
    lines.append("            conn.setConnectTimeout(%d);" % _HTTPS_CONNECT_TIMEOUT_MS)
    lines.append("            conn.setReadTimeout(readTimeoutMs);")
    lines.append("            _apkpyTagJsonBody(conn, data);")
    lines.append("            if (data != null) {")
    lines.append("                conn.setDoOutput(true);")
    lines.append("                java.io.OutputStream os = conn.getOutputStream();")
    lines.append("                os.write(data.getBytes(\"UTF-8\"));")
    lines.append("                os.flush();")
    lines.append("                os.close();")
    lines.append("            }")
    lines.append("            int responseCode = conn.getResponseCode();")
    lines.append("            boolean success = (responseCode >= 200 && responseCode < 300);")
    lines.append("            java.io.InputStream is = success ? conn.getInputStream() : conn.getErrorStream();")
    lines.append("            String body = _apkpyReadBody(is);")
    lines.append("            return new String[]{ String.valueOf(success), body };")
    lines.append("        } catch (Exception e) {")
    lines.append("            return new String[]{ \"false\", String.valueOf(e.getMessage()) };")
    lines.append("        }")
    lines.append("    }")

    _emit_json_build_helpers(lines, ctx="getApplicationContext().")

    lines.append("")
    lines.append("    private String _jsonGet(String jsonStr, String path) {")
    lines.append("        try {")
    lines.append('            String[] parts = path.split("\\\\.");')
    lines.append("            Object current;")
    lines.append("            if (jsonStr.trim().startsWith(\"[\")) {")
    lines.append("                current = new org.json.JSONArray(jsonStr);")
    lines.append("            } else {")
    lines.append("                current = new org.json.JSONObject(jsonStr);")
    lines.append("            }")
    lines.append("            for (String part : parts) {")
    lines.append("                if (current instanceof org.json.JSONArray) {")
    lines.append("                    org.json.JSONArray arr = (org.json.JSONArray) current;")
    lines.append("                    int i = Integer.parseInt(part.trim());")
    lines.append("                    if (i < 0) i += arr.length();")
    lines.append("                    if (i < 0 || i >= arr.length()) {")
    lines.append("                        if (ApkpyValues.strict()) throw new ApkpyValues.Raised(\"IndexError\", \"list index out of range\");")
    lines.append("                        return \"\";")
    lines.append("                    }")
    lines.append("                    current = arr.opt(i);")
    lines.append("                } else if (current instanceof org.json.JSONObject) {")
    lines.append("                    org.json.JSONObject obj = (org.json.JSONObject) current;")
    lines.append("                    if (!obj.has(part)) {")
    lines.append("                        if (ApkpyValues.strict()) throw new ApkpyValues.Raised(\"KeyError\", _apkpyRepr(part));")
    lines.append("                        return \"\";")
    lines.append("                    }")
    lines.append("                    current = obj.opt(part);")
    lines.append("                } else {")
    lines.append("                    return \"\";")
    lines.append("                }")
    lines.append("            }")
    lines.append("            return current != null ? _apkpyFromJson(current) : \"\";")
    lines.append("        } catch (ApkpyValues.Raised r) {")
    lines.append("            throw r;")
    lines.append("        } catch (Exception e) {")
    lines.append("            return \"\";")
    lines.append("        }")
    lines.append("    }")
    lines.append("")

    # len(x): comprimento de uma lista/JSON-array ou de uma string
    lines.append("")
    # len() of a value whose kind the source does not say: a JSON list counts
    # items, a JSON object keys (it counted the letters of its text), and text
    # its characters as Python counts them -- an emoji is one, not two.
    lines.append("    private int _apkpyLen(String s) {")
    lines.append("        if (s == null) return 0;")
    lines.append("        int shape = _apkpyJsonShape(s);")
    lines.append("        try {")
    lines.append("            if (shape == 91) return new org.json.JSONArray(s.trim()).length();")
    lines.append("            if (shape == 123) return new org.json.JSONObject(s.trim()).length();")
    lines.append("        } catch (Exception e) { }")
    lines.append("        return _apkpyTextLen(s);")
    lines.append("    }")
    lines.append("")
    lines.append("    private int _apkpyTextLen(String s) {")
    lines.append("        return s == null ? 0 : s.codePointCount(0, s.length());")
    lines.append("    }")
    lines.append("")
    # random.randint(a, b) → inteiro aleatório no intervalo [a, b]
    lines.append("    private String _apkpyRandInt(String a, String b) {")
    lines.append("        int lo = (int) Math.round(Double.parseDouble(a.trim()));")
    lines.append("        int hi = (int) Math.round(Double.parseDouble(b.trim()));")
    lines.append("        if (hi < lo) { int _t = lo; lo = hi; hi = _t; }")
    lines.append("        return String.valueOf(lo + new java.util.Random().nextInt(hi - lo + 1));")
    lines.append("    }")
    lines.append("")
    # random.choice(lista) → elemento aleatório de um JSONArray
    lines.append("    private String _apkpyChoice(String jsonArr) {")
    lines.append("        try {")
    lines.append("            org.json.JSONArray _arr = new org.json.JSONArray(jsonArr);")
    lines.append("            if (_arr.length() == 0) return \"\";")
    lines.append("            return String.valueOf(_arr.get(new java.util.Random().nextInt(_arr.length())));")
    lines.append("        } catch (Exception e) { return \"\"; }")
    lines.append("    }")
    lines.append("")

    _emit_crypto_helpers(lines, ctx="getApplicationContext().")
    lines.append("")

    # pythonCallback_X — gera os handlers (on_response, funções auxiliares, ...)
    # referenciados a partir do corpo do worker, de forma recursiva.
    emitted_callbacks = set()

    def _collect_callback_names(cmds_list, found):
        for c in cmds_list:
            if not isinstance(c, dict):
                continue
            if c['type'] in ('https_get', 'https_post', 'files_download') and c.get('callback'):
                found.add(c['callback'])
            elif c['type'] in data_feature.COMMAND_TYPES:
                # on_result / on_error de uma operacao de dados; o corpo de uma
                # transacao e escrito em linha, mas o que ele chama tem de existir.
                for _key in ('on_result', 'on_error'):
                    if c.get(_key):
                        found.add(c[_key])
                if c['type'] == 'data_transaction' and c.get('run') in functions_map:
                    _collect_callback_names(functions_map[c['run']]['cmds'], found)
            elif c['type'] == 'function_call':
                if native_feature.function_for(c['name']) is not None:
                    native_feature.refuse_in_job(c)
                found.add(c['name'])
            # Funções chamadas INLINE numa expressão (ex.: y = f(x), return f(x))
            for _vn in (c.get('val_node'), c.get('value_node'), c.get('msg_node')):
                if _vn is not None:
                    for _n in ast.walk(_vn):
                        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) and _n.func.id in functions_map:
                            found.add(_n.func.id)
            for body_key in _BODY_KEYS:
                if c.get(body_key):
                    _collect_callback_names(c[body_key], found)

    def _emit_callback(f_name):
        if f_name in emitted_callbacks or f_name not in functions_map:
            return
        emitted_callbacks.add(f_name)
        f_info = functions_map[f_name]
        _bool_first = f_name in _bool_callbacks
        _bool_arg_names_cb = {arg for i, arg in enumerate(f_info['args']) if i == 0 and _bool_first}
        _bool_arg_names_cb |= {arg for arg in f_info['args'] if arg in ('granted', 'is_granted', 'is_checked', 'success')}
        _cur_bool_args[0] = _bool_arg_names_cb
        _str_args_cb = f_info.get('string_args', set())
        args_str = ", ".join(
            f"boolean {arg}" if (arg in ('granted', 'is_granted', 'is_checked', 'success') or (i == 0 and _bool_first)) else
            f"String {arg}" if arg in _str_args_cb else
            f"Object {arg}"
            for i, arg in enumerate(f_info['args'])
        )
        lines.append("")
        _ret_type = "String" if f_info.get('returns_value') else "void"
        lines.append(f"    private {_ret_type} pythonCallback_{f_name}({args_str}) {{")
        _in_do_work[0] = False
        _RETURNS_VALUE[0] = bool(f_info.get('returns_value'))
        _gen_cmds(f_info['cmds'], "        ", params=tuple(f_info['args']),
                  list_params=tuple(f_info.get('list_params') or ()),
                  param_kinds=dict(f_info.get('param_kinds') or {}))
        _RETURNS_VALUE[0] = False
        _in_do_work[0] = True
        if f_info.get('returns_value') and not _cmds_definitely_return(f_info['cmds']):
            # Python returns None when it falls off the end.
            lines.append('        return ApkpyValues.NONE;')
        lines.append("    }")

        nested = set()
        _collect_callback_names(f_info['cmds'], nested)
        for n in nested:
            _emit_callback(n)

    pending_callbacks = set()
    _collect_callback_names(cmds, pending_callbacks)
    for cb in pending_callbacks:
        _emit_callback(cb)
    _cur_bool_args[0] = set()  # reset — button-handler code não tem boolean args de callback

    # Depois dos callbacks: um download pedido dentro de um on_result tambem
    # conta, e so se sabe depois de os escrever.
    if _uses_download[0]:
        lines.append("")
        lines.extend(_files_download_now_java())

    lines.append("}")
    return "\n".join(_drop_unused_struct_fields(lines))
