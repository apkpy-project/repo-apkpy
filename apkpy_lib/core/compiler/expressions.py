"""A Python expression, written as a Java one."""
import ast
import json
import re

from ..features import field as field_feature
from ..features import flashlight as flashlight_feature
from ..features import draw_pad as draw_pad_feature
from ..features import wallpaper as wallpaper_feature
from ..features import sensors as sensors_feature
from ..features import regex as regex_feature
from ..features import tuples as tuples_feature
from ..features import sort_key as sort_key_feature
from ..features import item_assignment as item_feature
from ..features import classes as classes_feature
from ..features import sets as sets_feature
from ..features import counters as counters_feature
from ..features import notifications as notifications_feature
from ..features import camera as camera_feature
from .. import unsupported
from .. import i18n as i18n_feature

from .state import (
    _CUR_LIST_ARGS, _ELSEWHERE_EMPTY, _GLOBALS, _I18N, _MODULE_LISTS, _MODULE_STRUCT_TEXT,
    _MUTATED_LISTS, _NUMBERISH_NAMES, _NUMERIC_CONST_TEXT, _NUMERIC_RETURNS, _RAW_LOOP_VARS,
)
from .kinds import (
    _DICT_VALUE_METHODS, _dict_receiver, _int_literal, _is_split_call, _json_call, _kind_from,
    _number_item_java, _static_kind,
)


# ── math ─────────────────────────────────────────────────────────────────────
# Só entram nomes onde a resposta do Java é a resposta do Python. O que não
# está aqui cai na guarda do U2033 e é dito em voz alta, que é melhor do que
# uma aproximação que discorda de vez em quando.
#
# Fora de propósito, e porquê:
#   log2   — o Java não o tem, e log(x)/log(2) discorda do math.log2 em 8 das
#            60 primeiras potências de dois (2**29 dá 29.000000000000004).
#   inf/nan — o Python escreve "inf", o Java escreve "Infinity".
#
# nome: (número de argumentos, molde)
_MATH_CALLS = {
    'sqrt':    (1, 'Math.sqrt(%s)'),
    'exp':     (1, 'Math.exp(%s)'),
    'log':     (1, 'Math.log(%s)'),
    'log10':   (1, 'Math.log10(%s)'),
    'fabs':    (1, 'Math.abs(%s)'),
    'sin':     (1, 'Math.sin(%s)'),
    'cos':     (1, 'Math.cos(%s)'),
    'tan':     (1, 'Math.tan(%s)'),
    'asin':    (1, 'Math.asin(%s)'),
    'acos':    (1, 'Math.acos(%s)'),
    'atan':    (1, 'Math.atan(%s)'),
    'degrees': (1, 'Math.toDegrees(%s)'),
    'radians': (1, 'Math.toRadians(%s)'),
    'pow':     (2, 'Math.pow(%s, %s)'),
    'atan2':   (2, 'Math.atan2(%s, %s)'),
    'hypot':   (2, 'Math.hypot(%s, %s)'),
}

# Estes devolvem um **int** em Python 3 e um double em Java: sem o molde,
# math.floor(2.7) mostrava "2" no Previewer e "2.0" no telemóvel.
_MATH_INT_CALLS = {
    'floor': '(long) Math.floor(%s)',
    'ceil':  '(long) Math.ceil(%s)',
    'trunc': '(long) (%s)',
}

_MATH_CONSTANTS = {
    'pi':  'Math.PI',
    'e':   'Math.E',
    'tau': '(2 * Math.PI)',
}


def _json_dumps_value(node, val_to_java):
    """(Java, mode) for what json.dumps writes: mode 1 when the source says what
    it is, 0 when the helper has to decide from the value (_apkpyJsonGuess)."""
    if isinstance(node, (ast.Dict, ast.List, ast.Tuple, ast.Constant)) or (
            isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd))
            and isinstance(node.operand, ast.Constant)):
        return _json_node_to_java(node, val_to_java), 1
    numeric = getattr(val_to_java, 'numeric', None)
    known = numeric(node) if numeric is not None else None
    if known is not None:
        return ("Double.valueOf(%s)" if known[1] else "Long.valueOf(%s)") % known[0], 1
    kind = _kind_from(val_to_java, node)
    if kind in ('list', 'dict'):
        return "_apkpyJsonVal(String.valueOf(%s))" % val_to_java(node), 1
    if kind == 'text':
        return "String.valueOf(%s)" % val_to_java(node), 1
    typed = _typed_json_java(node, val_to_java)
    if typed is not None:
        return typed, 1
    raw = _raw_item_java(node, val_to_java)
    if raw is not None:
        return raw, 1
    return "String.valueOf(%s)" % val_to_java(node), 0


def _json_module_java(node, val_to_java):
    """json.loads(text) and json.dumps(value, ...), or None for anything else.

    features/json_module.py has spelled them json.loads/json.dumps, worked out
    the ones written out in the source and refused what is not translated.
    """
    which = _json_call(node)
    if which is None or len(node.args) != 1:
        return None
    if which == 'loads':
        return "_apkpyJsonLoads(String.valueOf(%s))" % val_to_java(node.args[0])
    value, mode = _json_dumps_value(node.args[0], val_to_java)
    options = {kw.arg: kw.value for kw in node.keywords}
    indent = options.get('indent')
    if indent is None or (isinstance(indent, ast.Constant) and indent.value is None):
        indent_java = "null"
    elif isinstance(indent, ast.Constant) and isinstance(indent.value, str):
        indent_java = "(Object) %s" % val_to_java(indent)
    else:
        numeric = getattr(val_to_java, 'numeric', None)
        known = numeric(indent) if numeric is not None else None
        if known is None or known[1]:
            unsupported.raise_unsupported(
                node, cause='indent= is a whole number of spaces, a text or None, and '
                            'ApkPy cannot tell which this is.',
                suggestions=['Write it out, json.dumps(data, indent=2), or say it is a '
                             'number: indent=int(spaces).'])
        indent_java = "(Object) Long.valueOf(%s)" % known[0]
    separators = options.get('separators')
    item_sep = key_sep = "null"
    if separators is not None and not (isinstance(separators, ast.Constant)
                                       and separators.value is None):
        pair = ast.literal_eval(separators)
        item_sep = '"%s"' % _escape_java_literal(pair[0])
        key_sep = '"%s"' % _escape_java_literal(pair[1])

    def flag(name, default):
        return _java_truth(options[name], val_to_java) if name in options else default
    return "_apkpyJsonDumps(%s, %d, %s, %s, %s, %s, %s, %s)" % (
        value, mode, indent_java, flag('sort_keys', 'false'), flag('ensure_ascii', 'true'),
        item_sep, key_sep, flag('allow_nan', 'true'))


def _math_java(node, val_to_java):
    """``math.sqrt(x)`` -> Java, ou None se não for connosco.

    O resultado passa pelo ``_apkpyMathCheck`` porque o Python **levanta** onde
    o Java devolve NaN: ``math.sqrt(-1)`` é um ValueError no Previewer e era a
    palavra "NaN" a chegar ao ecrã do telemóvel. Levantar nos dois lados junta
    os runtimes outra vez, e agora o ``try/except`` apanha-o em ambos.
    """
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
            and node.value.id == 'math':
        const = _MATH_CONSTANTS.get(node.attr)
        return None if const is None else '_apkpyFloat(%s)' % const

    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == 'math'):
        return None

    name = node.func.attr
    numbers = ['Double.parseDouble(String.valueOf(%s))' % val_to_java(a)
               for a in node.args]

    if name in _MATH_INT_CALLS:
        if len(node.args) != 1:
            return None
        return _MATH_INT_CALLS[name] % numbers[0]

    entry = _MATH_CALLS.get(name)
    if entry is None or len(node.args) != entry[0] or node.keywords:
        return None
    return '_apkpyFloat(_apkpyMathCheck(%s))' % (entry[1] % tuple(numbers))


def _translation_mark(node):
    """``t("save")`` -> a mark the layout writer turns into a resource.

    Returns None for anything else, so every caller keeps its old behaviour.
    The generator reads your module rather than running it, so this is where
    a translation call stops being syntax and starts being a placeholder.
    """
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == 't' and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)):
        return None
    key = node.args[0].value
    if not i18n_feature.KEY_PATTERN.match(key):
        unsupported.raise_unsupported(
            node,
            cause=('A translation key becomes an Android resource name, which '
                   'only allows letters, digits and underscore, and cannot '
                   'start with a digit.'),
            suggestions=['Rename the key, for example to %s.'
                         % re.sub(r'[^A-Za-z0-9_]', '_', key).lstrip('0123456789')],
            received='t(%r)' % key,
        )
    _check_translation_key(key, node)
    return i18n_feature.mark(key)


def _check_translation_key(key, node):
    """A key that is not in the default language, said now rather than by aapt.

    Android answers ``@string/x`` from ``res/values/`` when the device has no
    translation of its own, so a key missing there is a resource-not-found at
    build time -- reported against generated XML, in a file nobody wrote.
    """
    default = _I18N[0]['default']
    if not default:
        unsupported.raise_unsupported(
            node,
            cause=('t() looks a word up in the table that translations() '
                   'declares, and this module never called it.'),
            suggestions=['Add translations({"en": {"%s": "..."}}) above.' % key],
            received='t(%r)' % key,
        )
    if key not in _I18N[0]['table'].get(default, {}):
        unsupported.raise_unsupported(
            node,
            cause=('%s is the default language, which is what the phone falls '
                   'back to when it has no translation of its own -- so every '
                   'key has to exist in it.' % default),
            suggestions=['Add "%s" to the %s dictionary.' % (key, default)],
            received='t(%r)' % key,
        )


def _mutated_list_key(name):
    """A chave desta lista no estado partilhado do processo."""
    return "__apkpy_list_" + name


def _mutated_list_read(name):
    """Ler a lista partilhada, semeando-a com o literal do módulo à primeira."""
    seed = _MUTATED_LISTS[0].get(name, "[]")
    return 'ApkpyReactiveState.get("%s", "%s")' % (
        _mutated_list_key(name), _escape_java_literal(seed))


def _dict_method_java(node, val_to_java):
    """d.get(k, padrao), d.keys(), d.values(), d.items(), x.copy() -- or None."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and not node.keywords and _dict_receiver(node.func.value)):
        return None
    attr, args = node.func.attr, node.args
    if attr == 'get' and 1 <= len(args) <= 2:
        fallback = _text_value_java(args[1], val_to_java) if len(args) > 1 else "ApkpyValues.NONE"
        return "_apkpyDictGetOr(String.valueOf(%s), String.valueOf(%s), %s)" % (
            val_to_java(node.func.value), val_to_java(args[0]), fallback)
    if attr in _DICT_VALUE_METHODS and not args:
        helper = {'keys': '_apkpyKeyList', 'values': '_apkpyValues', 'items': '_apkpyPairs'}[attr]
        return "%s(String.valueOf(%s))" % (helper, val_to_java(node.func.value))
    if attr == 'copy' and not args:
        # The text is the value: a copy is the same text, and the two can no
        # longer reach each other.
        return "String.valueOf(%s)" % val_to_java(node.func.value)
    return None


# Nomes de variáveis que o transpilador tipa como `boolean` (primitivo) em Java
# — ex: parâmetros de callbacks como on_response(success, response). `if var:`
# sobre estes nomes deve gerar `if (var)`, nunca `var != null && !var.isEmpty()`
# (que não compila para um primitivo).
_BOOL_VAR_NAMES = ('granted', 'is_granted', 'is_checked', 'success')


def _text_value_java(node, val_to_java):
    """A value as the text the phone keeps it as.

    None, True and False are ApkpyValues.NONE / TRUE / FALSE: they read like
    Python's str() of them, and they are not the same object as the words a
    person typed, so `is None` and `if flag:` can tell them apart.
    """
    if isinstance(node, ast.Constant):
        if node.value is None:
            return "ApkpyValues.NONE"
        if isinstance(node.value, bool):
            return "ApkpyValues.TRUE" if node.value else "ApkpyValues.FALSE"
    return "String.valueOf(%s)" % val_to_java(node)


def _may_be_singleton(node):
    """True when *node* can hold the app's True, False, None or JSON 0."""
    if isinstance(node, (ast.Name, ast.Subscript, ast.Compare, ast.BoolOp, ast.IfExp,
                         ast.Attribute)):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return True
    # A method too: str(t.startswith("p")) put the app's True in a list,
    # and " | ".join() of it wrote "true".
    return isinstance(node, ast.Call)


def _truthy_java(node, val_to_java):
    """Python's `if x:` for a value, as a Java condition.

    A number the source proves is false at zero. A list or dict is false when
    empty. Anything else is false when it is None, False or empty text -- the
    one thing every value on the phone can be asked. The text "0" or "[]" a
    person typed stays true, as in CPython.
    """
    numeric = getattr(val_to_java, 'numeric', None)
    known = numeric(node) if numeric is not None else None
    if known is not None:
        return "((%s) != 0)" % known[0]
    if isinstance(node, ast.Name) and node.id in _RAW_LOOP_VARS[0]:
        # An item of a list, as the JSON holds it: an empty list or dict in
        # the list is false. Read as its text, "[]" was true.
        return "_apkpyTruthy(%s)" % _RAW_LOOP_VARS[0][node.id]
    if _kind_from(val_to_java, node) in ('list', 'dict'):
        return "(_apkpyLen(String.valueOf(%s)) > 0)" % val_to_java(node)
    return "_apkpyTruthy(%s)" % val_to_java(node)


# isinstance(x, T): answered when the app is built where the source says what
# x is, and by ApkpyValues.isInstance when it does not -- the type the rest of
# the app reads the value as.
_ISINSTANCE_NAMES = ('bool', 'int', 'float', 'str', 'list', 'dict', 'tuple')


def _is_isinstance(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == 'isinstance')


def _isinstance_types(node):
    """The types isinstance(x, ...) asks about, by Python's names."""
    if len(node.args) != 2 or node.keywords or any(isinstance(a, ast.Starred) for a in node.args):
        unsupported.raise_unsupported(
            node, cause='isinstance() takes a value and a type, or a tuple of types.',
            suggestions=['isinstance(value, (int, float))'])
    spec = node.args[1]
    items = spec.elts if isinstance(spec, ast.Tuple) else [spec]
    names = []
    for item in items:
        if isinstance(item, ast.Name) and item.id in _ISINSTANCE_NAMES:
            names.append(item.id)
        elif (isinstance(item, ast.Call) and isinstance(item.func, ast.Name)
              and item.func.id == 'type' and len(item.args) == 1 and not item.keywords
              and isinstance(item.args[0], ast.Constant) and item.args[0].value is None):
            names.append('NoneType')
        else:
            unsupported.raise_unsupported(
                item,
                cause=('isinstance() is translated for str, int, float, bool, list, '
                       'dict, tuple and type(None). %s is none of them.'
                       % unsupported.describe(item)),
                suggestions=['Ask about one of those types, or test the value itself: '
                             'if value is None:'])
    return names


def _static_pytype(node, val_to_java, bool_names=()):
    """The Python type of *node* when the source says it, else None."""
    if isinstance(node, ast.Constant):
        value = node.value
        if value is None:
            return 'NoneType'
        for name, kind in (('bool', bool), ('int', int), ('float', float), ('str', str)):
            if isinstance(value, kind):
                return name
        return None
    if tuples_feature.is_tuple(node):
        return 'tuple'
    if isinstance(node, ast.Compare) or _is_isinstance(node) \
            or (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not)) \
            or (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'bool'):
        return 'bool'
    if isinstance(node, ast.Name) and (node.id in _BOOL_VAR_NAMES or node.id in bool_names):
        return 'bool'
    numeric = getattr(val_to_java, 'numeric', None)
    known = numeric(node) if numeric is not None else None
    if known is not None:
        return 'float' if known[1] else 'int'
    return {'list': 'list', 'dict': 'dict', 'text': 'str'}.get(_kind_from(val_to_java, node))


def _isinstance_java(node, val_to_java, bool_names=()):
    """isinstance(x, T) as a Java boolean."""
    names = _isinstance_types(node)
    value = node.args[0]
    known = _static_pytype(value, val_to_java, bool_names)
    if known is not None:
        # bool is a kind of int in Python: isinstance(True, int) is True.
        hit = known in names or (known == 'bool' and 'int' in names)
        if _reads_the_same_twice(value):
            return 'true' if hit else 'false'
        # A call is still made, as Python makes it, for what else it does.
        seen = "ApkpyValues.evaluated(%s)" % val_to_java(value)
        return seen if hit else "!" + seen
    raw = _raw_item_java(value, val_to_java)
    if raw is not None:
        # An item, or the name of a for over a list: the JSON says what it is.
        # By its digits, CODES[0] = "10" was an int.
        return '_apkpyIsA(%s, "%s")' % (raw, ",".join(names))
    return 'ApkpyValues.isInstance(String.valueOf(%s), "%s")' % (
        val_to_java(value), ",".join(names))


_SINGLETONS = (type(None), bool)


def _identity_java(left, right, negate, val_to_java, bool_names=()):
    """`x is None`, `x is True`, `x == False`: compared by identity."""
    value = right.value
    if isinstance(left, ast.Name) and (left.id in _BOOL_VAR_NAMES or left.id in bool_names) \
            and isinstance(value, bool):
        # A boolean the generator types as a Java boolean (success, granted).
        test = left.id if value else "!" + left.id
        return ("!(%s)" % test) if negate else "(%s)" % test
    ref = val_to_java(left)
    if value is None:
        test = "_apkpyIsNone(%s)" % ref
    else:
        test = "(%s == %s)" % (ref, "ApkpyValues.TRUE" if value else "ApkpyValues.FALSE")
    return ("!" + test) if negate else test


def _parenthesized(cond):
    """cond with one pair of parentheses around it, for `if (...)`.

    `(success)` stays as it is; `_apkpyTruthy(x)` gains them.
    """
    if cond.startswith("(") and cond.endswith(")"):
        depth = 0
        for i, ch in enumerate(cond):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0 and i < len(cond) - 1:
                break
        else:
            return cond
    return "(%s)" % cond


# Operadores de comparação suportados em `if`. `in` é tratado à parte (if_in).
_CMP_OPS = {
    ast.Eq: '==', ast.NotEq: '!=',
    ast.Lt: '<', ast.Gt: '>', ast.LtE: '<=', ast.GtE: '>=',
}


def _written_comparand(node):
    """Whether the right side of a comparison is a value written in the
    source -- text, a number, True or False -- which is all if_compare reads."""
    # True and False are compared as the app's own values (_identity_java),
    # not as the words "true"/"false".
    return isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float)) \
        and not isinstance(node.value, bool)


def _if_compare_cond(c, val_to_java):
    """
    Constrói a condição Java de um `if_compare`. Fonte única usada por todos os
    sítios de codegen (atividade, corpos de funções e workers) — evita drift.

    Suporta ==, !=, <, >, <=, >= :
      - right é string + ==/!=        → left.equals(...) / !left.equals(...)
      - right é string + relacional   → left.compareTo(...) <op> 0  (lexicográfico, como em Python)
      - right é número (int ou float) → Double.parseDouble(left) <op> right
        (Double cobre preços decimais; o antigo Integer.parseInt rebentava em "1.20")
    """
    left_node = c.get('left_node')
    if left_node is not None \
            and not (isinstance(left_node, ast.Constant) and left_node.value == "") \
            and not unsupported.reaches_other_runtime(left_node) \
            and val_to_java(left_node) == '""' \
            and id(left_node) not in _ELSEWHERE_EMPTY[0]:
        # Same trap as in _compare_node_to_java: an expression that translated
        # to nothing would be parsed as a number and crash at run time.
        unsupported.raise_untranslated_condition(left_node)
    left_j = f"String.valueOf({val_to_java(c['left_node'])})" if c.get('left_node') is not None else c['left']
    op = c['op']
    right = c['right']
    if isinstance(right, bool):
        expected = 'true' if right else 'false'
        parsed = f"Boolean.parseBoolean(String.valueOf({left_j}))"
        if op == '==':
            return f"{parsed} == {expected}"
        if op == '!=':
            return f"{parsed} != {expected}"
        return "false"
    if isinstance(right, str):
        right_val = '"' + _escape_java_literal(right) + '"'
        if op == '==':
            return f"{left_j}.equals({right_val})"
        if op == '!=':
            return f"!{left_j}.equals({right_val})"
        return f"String.valueOf({left_j}).compareTo({right_val}) {op} 0"
    return f"Double.parseDouble(String.valueOf({left_j})) {op} {right}"


def _membership_java(needle, haystack, val_to_java):
    """Python's `in`, which asks three different questions.

    - of a list, tuple, set or dict written in the source, or of a split()
      call: is it one of these elements, or one of these keys?
    - of a module-level list: the same question. A list the app appends to
      lives in the shared store and is asked at run time; one nobody changes
      has no Java field of its own, so it is answered from its literal.
    - of anything else: text, and `in` searches it.

    Decided from the source and never from the value. A search box holding
    "[a" is text, and guessing from its first character would turn somebody's
    typing into a list -- the mistake _apkpyJsonVal made once.

    Everything on the phone is text, so an element is compared by its text:
    "1" in [1, 2] is True here and False in Python. That is the model the rest
    of the generated app already follows.
    """
    want = "String.valueOf(%s)" % val_to_java(needle)

    def literal(elements):
        if not elements:
            return "false"
        items = ", ".join("String.valueOf(%s)" % val_to_java(e) for e in elements)
        return "java.util.Arrays.asList(%s).contains(%s)" % (items, want)

    if isinstance(haystack, (ast.List, ast.Tuple, ast.Set)):
        return literal(haystack.elts)
    if isinstance(haystack, ast.Dict):
        return literal([k for k in haystack.keys if k is not None])
    if isinstance(haystack, ast.Name):
        if haystack.id in _MUTATED_LISTS[0]:
            return "_apkpyListHas(String.valueOf(%s), %s)" % (
                _mutated_list_read(haystack.id), want)
        module_list = _MODULE_LISTS[0].get(haystack.id)
        if isinstance(module_list, ast.List) and haystack.id not in _GLOBALS[0]:
            return literal(module_list.elts)
    if _is_split_call(haystack):
        return "_apkpyListHas(%s, %s)" % (val_to_java(haystack), want)
    if isinstance(haystack, ast.Name) and haystack.id in _CUR_LIST_ARGS[0]:
        return "_apkpyListHas(String.valueOf(%s), %s)" % (haystack.id, want)
    # A dict or a list the source names: "x" in PRICES searched the JSON text,
    # and found values and pieces of keys as well.
    kind = _kind_from(val_to_java, haystack)
    if kind == 'dict':
        return "_apkpyHasKey(String.valueOf(%s), %s)" % (val_to_java(haystack), want)
    if kind == 'list':
        return "_apkpyListHas(String.valueOf(%s), %s)" % (val_to_java(haystack), want)
    return "String.valueOf(%s).contains(%s)" % (val_to_java(haystack), want)


def _list_call_java(node, val_to_java):
    """``list(x)`` as Python makes it.

    A list is JSON text, which nothing can change in place, so its copy is the
    value itself. Text gives its letters and a dict its keys: ``list("ab7")``
    used to give back "ab7", and ``str()`` of it showed the word, not
    ``['a', 'b', '7']``. A value the source does not type is read the way
    ``for x in value`` reads it (_apkpyItems).
    """
    if not node.args:
        return '"[]"'
    arg = node.args[0]
    value = val_to_java(arg)
    kind = _kind_from(val_to_java, arg)
    if kind == 'list' or getattr(node, classes_feature.LIST_READ, False):
        return value
    if kind == 'text':
        return f"_apkpyChars(String.valueOf({value})).toString()"
    if kind == 'dict':
        return f"_apkpyKeys(String.valueOf({value})).toString()"
    return f"_apkpyItems(String.valueOf({value})).toString()"


def _slice_java(node, val_to_java):
    """``value[a:b]``: a slice of text, or of a list, with Python's edges.

    A list is JSON text on the phone, and slicing it as text cut the JSON
    itself: ``items[1:]`` gave ``"a","b"]``. The source says which it is where
    it can; otherwise _apkpySliceAny looks at the JSON shape.
    """
    slice_node = node.slice
    lo = val_to_java(slice_node.lower) if slice_node.lower is not None else '""'
    hi = val_to_java(slice_node.upper) if slice_node.upper is not None else '""'
    kind = _kind_from(val_to_java, node.value)
    if kind == 'dict':
        unsupported.raise_unsupported(
            node, cause='A dict has no order to slice, and Python stops with TypeError here.')
    if slice_node.step is not None:
        # text[::-1], items[::2]: Python's slice.indices, then every k-th.
        return "_apkpySliceStep(String.valueOf(%s), %s, %s, %s, %d)" % (
            val_to_java(node.value), _bound_java(slice_node.lower, val_to_java),
            _bound_java(slice_node.upper, val_to_java), _bound_java(slice_node.step, val_to_java),
            {'text': 3, 'list': 1}.get(kind, 0))
    helper = {'text': '_apkpySlice', 'list': '_apkpyListSlice'}.get(kind, '_apkpySliceAny')
    return "%s(String.valueOf(%s), String.valueOf(%s), String.valueOf(%s))" % (
        helper, val_to_java(node.value), lo, hi)


def _index_java(node, val_to_java):
    """``value[i]`` where i is not a key written out as text.

    A list's item, a dict's value or a character, by what the source says the
    value is. ``text[0]`` was read as a list and gave an empty value, and
    ``PRICES[item]`` -- a dict with the key in a name -- did the same.
    """
    base = val_to_java(node.value)
    index = val_to_java(node.slice)
    kind = _kind_from(val_to_java, node.value)
    helper = {'text': '_apkpyCharAt', 'list': '_apkpyListGet',
              'dict': '_apkpyDictGet'}.get(kind, '_apkpyItemAt')
    return f"{helper}(String.valueOf({base}), String.valueOf({index}))"


def _json_value_java(node, val_to_java):
    """A value going into a list or a dict, keeping its JSON type.

    A number stays a number and a list stays a list, so the JSON that leaves
    the app (a request body, a file) reads as Python's json.dumps would write it.
    """
    if isinstance(node, (ast.Dict, ast.List, ast.Tuple, ast.Constant)) or (
            isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd))
            and isinstance(node.operand, ast.Constant)):
        return _json_node_to_java(node, val_to_java)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)             and node.func.id in (item_feature.SETITEM, item_feature.DELITEM):
        # d["a"]["b"] = v: the inner dict goes back in as a dict.
        return "_apkpyJsonVal(String.valueOf(%s))" % val_to_java(node)
    numeric = getattr(val_to_java, 'numeric', None)
    known = numeric(node) if numeric is not None else None
    if known is not None:
        return ("Double.valueOf(%s)" if known[1] else "Long.valueOf(%s)") % known[0]
    if _kind_from(val_to_java, node) in ('list', 'dict'):
        return "_apkpyJsonVal(String.valueOf(%s))" % val_to_java(node)
    typed = _typed_json_java(node, val_to_java)
    if typed is not None:
        return typed
    raw = _raw_item_java(node, val_to_java)
    if raw is not None:
        return raw
    return "_apkpyJsonOut(String.valueOf(%s))" % val_to_java(node)


def _raw_item_java(node, val_to_java):
    """d[k], row[i] or d.get(k) going into a list or a dict, as the JSON holds it.

    The keys of sorted(rows, key=lambda r: r["price"]), or [r["price"] for r in
    rows]: the source does not say what the item is, and the JSON it is read
    from does. It used to go in as text, and then 10 sorted before 9.
    None when *node* is not such a read. The name of a for over a list is one
    too, while its body is written (_RAW_LOOP_VARS).
    """
    if isinstance(node, ast.Name) and node.id in _RAW_LOOP_VARS[0]:
        return _RAW_LOOP_VARS[0][node.id]
    item = _item_read(node)
    if item is not None:
        if _kind_from(val_to_java, item[0]) == 'text':
            return None                      # a letter of a text
        return "_apkpyStored(%s)" % _raw_side_java(node, val_to_java)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr == 'get' and 1 <= len(node.args) <= 2 and not node.keywords \
            and not any(isinstance(a, ast.Starred) for a in node.args) \
            and _dict_receiver(node.func.value) \
            and _kind_from(val_to_java, node.func.value) not in ('list', 'text'):
        fallback = _json_value_java(node.args[1], val_to_java) if len(node.args) > 1 \
            else "org.json.JSONObject.NULL"
        return "_apkpyRawGet(String.valueOf(%s), String.valueOf(%s), %s)" % (
            val_to_java(node.func.value), val_to_java(node.args[0]), fallback)
    popped = _popped_item(node)
    if popped is not None:
        args = popped.args[2:]
        fallback = ("%s, true" % _json_value_java(args[1], val_to_java)) if len(args) > 1 \
            else "null, false"
        return "_apkpyRawPop(String.valueOf(%s), String.valueOf(%s), %s)" % (
            val_to_java(popped.args[1]), val_to_java(args[0]), fallback)
    return None


def _container_code(val_to_java, node):
    """1 for a list, 2 for a dict, 0 when the source does not say."""
    return {'list': 1, 'dict': 2}.get(_kind_from(val_to_java, node), 0)


def _setitem_java(node, val_to_java):
    container, key, value = node.args[:3]
    aug = len(node.args) > 3 and bool(node.args[3].value)
    return "_apkpySetItem(String.valueOf(%s), String.valueOf(%s), %s, %d, %s)" % (
        val_to_java(container), val_to_java(key), _json_value_java(value, val_to_java),
        _container_code(val_to_java, container), 'true' if aug else 'false')


def _delitem_java(node, val_to_java):
    container, key = node.args[:2]
    return "_apkpyDelItem(String.valueOf(%s), String.valueOf(%s), %d)" % (
        val_to_java(container), val_to_java(key), _container_code(val_to_java, container))


_TEXT_PREDICATES = ('isdigit', 'isalpha', 'isalnum', 'isdecimal', 'isnumeric',
                    'isspace', 'isupper', 'islower', 'isascii')


def _bound_java(node, val_to_java):
    """A slice bound or an optional argument: "" when left out or None."""
    if node is None or (isinstance(node, ast.Constant) and node.value is None):
        return '""'
    return "String.valueOf(%s)" % val_to_java(node)


def _text_method_java(node, val_to_java):
    """The text methods of phase 1, group 8 -- or None for the others.

    Each counts in code points, as Python does: an emoji is one character.
    """
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)) \
            or node.keywords:
        return None
    attr, args = node.func.attr, node.args
    base = "String.valueOf(%s)" % val_to_java(node.func.value)
    if attr in ('strip', 'lstrip', 'rstrip') and len(args) <= 1:
        chars = 'null' if not args or (isinstance(args[0], ast.Constant) and args[0].value is None) \
            else "String.valueOf(%s)" % val_to_java(args[0])
        return "_apkpyStrip(%s, %s, %d)" % (base, chars, ('strip', 'lstrip', 'rstrip').index(attr))
    if attr in ('find', 'rfind') and len(args) == 1:
        return "_apkpyFind(%s, String.valueOf(%s), %s)" % (
            base, val_to_java(args[0]), 'true' if attr == 'rfind' else 'false')
    if attr == 'zfill' and len(args) == 1:
        return "_apkpyZfill(%s, Long.parseLong(String.valueOf(%s).trim()))" % (base, val_to_java(args[0]))
    if attr in ('ljust', 'rjust', 'center') and 1 <= len(args) <= 2:
        fill = "String.valueOf(%s)" % val_to_java(args[1]) if len(args) > 1 else '" "'
        return "_apkpyPad(%s, Long.parseLong(String.valueOf(%s).trim()), %s, %d)" % (
            base, val_to_java(args[0]), fill, ('ljust', 'rjust', 'center').index(attr))
    if attr in ('capitalize', 'swapcase') and not args:
        return "_apkpy%s(%s)" % (attr.capitalize(), base)
    if attr == 'splitlines' and len(args) <= 1:
        keep = _java_truth(args[0], val_to_java) if args else 'false'
        return "_apkpySplitLines(%s, %s)" % (base, keep)
    if attr in _TEXT_PREDICATES and not args:
        return '_apkpyBool(_apkpyStrIs(%s, "%s"))' % (base, attr[2:])
    if attr == 'replace' and len(args) == 3:
        return "_apkpyReplaceN(%s, String.valueOf(%s), String.valueOf(%s), Long.parseLong(String.valueOf(%s).trim()))" % (
            base, val_to_java(args[0]), val_to_java(args[1]), val_to_java(args[2]))
    return None


def _repeat_java(node, val_to_java, numeric):
    """"-" * 10 and [0] * 3: the text, or the list, n times -- or None."""
    if not isinstance(node.op, ast.Mult):
        return None
    for seq, times in ((node.left, node.right), (node.right, node.left)):
        kind = _kind_from(val_to_java, seq)
        count = numeric(times)
        if kind in ('text', 'list') and count is not None and not count[1]:
            return "_apkpyRepeat(String.valueOf(%s), %s, %s)" % (
                val_to_java(seq), count[0], 'true' if kind == 'list' else 'false')
    return None


def _listop_java(node, val_to_java):
    """A method that changes a list, as the changed list (features/item_assignment.py).

    ``popvalue`` is the item pop() answers; ``pop`` is the list without it.
    """
    op = node.args[0].value
    container = "String.valueOf(%s)" % val_to_java(node.args[1])
    args = node.args[2:]
    if op == 'append':
        return "_apkpyListAppend(%s, %s)" % (container, _json_value_java(args[0], val_to_java))
    if op == 'insert':
        return "_apkpyInsert(%s, String.valueOf(%s), %s)" % (
            container, val_to_java(args[0]), _json_value_java(args[1], val_to_java))
    if op == 'remove':
        return "_apkpyRemove(%s, %s)" % (container, _json_value_java(args[0], val_to_java))
    if op == 'extend':
        return "_apkpyExtend(%s, String.valueOf(%s))" % (container, val_to_java(args[0]))
    if op == 'sort' and len(args) > 1:
        # xs.sort(key=...): the keys features/sort_key.py worked out.
        return '_apkpySortBy(_apkpyListArg(%s, "sort"), String.valueOf(%s), %s)' % (
            container, val_to_java(args[1]), _java_truth(args[0], val_to_java))
    if op == 'sort':
        return "_apkpySort(%s, %s)" % (container, _java_truth(args[0], val_to_java))
    if op == 'reverse':
        return "_apkpyReverse(%s)" % container
    if op == 'clear':
        return "_apkpyClear(%s)" % container
    if op == 'update':
        return "_apkpyUpdate(%s, String.valueOf(%s))" % (container, val_to_java(args[0]))
    fallback = ("%s, true" % _json_value_java(args[1], val_to_java)) if len(args) > 1 \
        else "null, false"
    return "_apkpyPop(%s, String.valueOf(%s), %s, %s)" % (
        container, val_to_java(args[0]), 'true' if op == 'popvalue' else 'false', fallback)


def _java_truth(node, val_to_java):
    """A Java boolean for an argument like reverse=True."""
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return 'true' if node.value else 'false'
    return _truthy_java(node, val_to_java)


def _sorted_java(node, val_to_java):
    """sorted(x, key=..., reverse=...) and reversed(x): a new list, of any list, text or dict.

    key= arrives as _apkpy_keys, the list of keys features/sort_key.py had
    worked out on the line before.
    """
    items = "_apkpyItems(String.valueOf(%s))" % val_to_java(node.args[0])
    if node.func.id == 'reversed':
        return "_apkpyReverse(%s.toString())" % items
    reverse = 'false'
    keys = None
    for kw in node.keywords:
        if kw.arg == sort_key_feature.KEYS:
            keys = kw.value
            continue
        if kw.arg == 'key' and isinstance(kw.value, ast.Constant) and kw.value.value is None:
            continue
        if kw.arg != 'reverse':
            unsupported.raise_unsupported(
                node,
                cause=('sorted(..., %s=...) is not translated here. sorted() takes key= '
                       'and reverse=, and the keys are worked out on a line of a def.'
                       % kw.arg),
                suggestions=['sorted(rows, key=lambda r: r["price"], reverse=True), '
                             'inside a def.'],
            )
        reverse = _java_truth(kw.value, val_to_java)
    if keys is not None:
        return "_apkpySortBy(%s, String.valueOf(%s), %s)" % (items, val_to_java(keys), reverse)
    return "_apkpySort(%s.toString(), %s)" % (items, reverse)


def _extreme_by_java(node, val_to_java):
    """min/max(items, key=..., default=...): the first item with the smallest or largest key."""
    keys = default = None
    for kw in node.keywords:
        if kw.arg == sort_key_feature.KEYS:
            keys = kw.value
        elif kw.arg == 'default':
            default = kw.value
        else:
            unsupported.raise_unsupported(
                node, cause='%s() takes key= and default=, not %s=.' % (node.func.id, kw.arg))
    fallback = ("String.valueOf(%s), true" % val_to_java(default)) if default is not None \
        else "null, false"
    return '_apkpyExtremeBy(_apkpyItems(String.valueOf(%s)), String.valueOf(%s), "%s", %s)' % (
        val_to_java(node.args[0]), val_to_java(keys), node.func.id, fallback)


def _has_sort_keys(node):
    """min(...)/max(...) whose key= features/sort_key.py has worked out."""
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
        and node.func.id in ('min', 'max') and len(node.args) == 1 \
        and any(kw.arg == sort_key_feature.KEYS for kw in node.keywords)


def _logic_value_java(node, val_to_java):
    """A comparison, `not x`, or `a or b` used as a value.

    `same = a == b` is ApkpyValues.TRUE or FALSE. `name = typed or "nobody"` is
    one of the two values, as in Python, and the second is only worked out
    when the first is false: the first goes through the _apkpyOrT field, read
    right after it is written, so nothing runs twice.
    """
    if isinstance(node, ast.Compare) or (
            isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not)):
        cond = _cond_to_java(node, val_to_java)
        if cond is None:
            unsupported.raise_untranslated_condition(node)
        return "_apkpyBool(%s)" % cond
    # BoolOp: right-nested, a or b or c == a or (b or c)
    values = node.values
    out = _text_value_java(values[-1], val_to_java)
    for value in reversed(values[:-1]):
        holder = "_apkpyOrT"
        first = _text_value_java(value, val_to_java)
        numeric = getattr(val_to_java, 'numeric', None)
        known = numeric(value) if numeric is not None else None
        if known is not None:
            truth = "(Double.parseDouble(%s = %s) != 0)" % (holder, first)
        elif _kind_from(val_to_java, value) in ('list', 'dict'):
            truth = "(_apkpyLen(%s = %s) > 0)" % (holder, first)
        else:
            truth = "_apkpyTruthy(%s = %s)" % (holder, first)
        if isinstance(node.op, ast.Or):
            out = "(%s ? %s : %s)" % (truth, holder, out)
        else:
            out = "(!%s ? %s : %s)" % (truth, holder, out)
    return out


def _unpack_java(node, val_to_java):
    """``a, b = value`` after unpacking.desugar: the items of *value* as a JSON
    list, after checking that there are as many as the names (CPython's
    "too many values to unpack")."""
    source = node.args[0]
    before, after, star = (arg.value for arg in node.args[1:4])
    kind = _kind_from(val_to_java, source)
    walk = {'dict': '_apkpyKeys', 'text': '_apkpyChars'}.get(kind, '_apkpyItems')
    return "_apkpyUnpack(%s(String.valueOf(%s)), %d, %d, %s)" % (
        walk, val_to_java(source), before, after, 'true' if star else 'false')


def _len_int_java(node, val_to_java):
    """``len(x)`` as a Java int: characters of text, items of a list, keys of
    a dict."""
    inner = val_to_java(node.args[0]) if node.args else '""'
    kind = _kind_from(val_to_java, node.args[0]) if node.args else 'text'
    if kind == 'text':
        return f"_apkpyTextLen(String.valueOf({inner}))"
    return f"_apkpyLen(String.valueOf({inner}))"


def _len_java(node, val_to_java):
    """``len(x)`` as text."""
    return f"String.valueOf({_len_int_java(node, val_to_java)})"


def _round_parts(node, val_to_java, numeric):
    """``round(x)`` / ``round(x, n)`` as (Java, is_float), or None.

    Python answers an int for round(x) and for round(an int, n); a decimal
    only for round(a decimal, n). None when the digits are not written out:
    the old translation ignored them and rounded to a whole number.
    """
    arg = node.args[0] if node.args else ast.Constant(0)
    known = numeric(arg)
    whole = known is not None and not known[1]
    if known is not None:
        x = f"((double)({known[0]}))"
    else:
        x = f"Double.parseDouble(String.valueOf({val_to_java(arg)}).trim())"
    digits_node = node.args[1] if len(node.args) > 1 else None
    if digits_node is None or (isinstance(digits_node, ast.Constant)
                               and digits_node.value is None):
        if whole:
            return (known[0], False)                 # round(7) is 7
        # Math.rint rounds a half to the even neighbour, as Python does;
        # _apkpyTrunc refuses nan and inf, as round() does.
        return (f"_apkpyTrunc(Math.rint({x}))", False)
    digits = _int_literal(digits_node)
    if digits is None:
        return None
    if whole:
        if digits >= 0:
            return (known[0], False)                 # round(7, 2) is 7
        # round(1234, -2) is 1200: the factor used to come out as "0.01.0",
        # which javac refused.
        return (f"_apkpyRoundL((long)({known[0]}), {digits})", False)
    # The exact value of the double, rounded half to even: what CPython does.
    # Math.rint(x * 100) / 100 rounded the product first, and disagreed in
    # about one case in a hundred (round(-0.025, 2)).
    return (f"_apkpyRoundTo({x}, {digits})", True)


def _round_java(node, val_to_java, numeric):
    """``round(...)`` as a value."""
    parts = _round_parts(node, val_to_java, numeric)
    if parts is None:
        unsupported.raise_unsupported(
            node,
            cause=('round() with the number of digits in a name is not '
                   'translated: the phone would have rounded to a whole '
                   'number.'),
            suggestions=['Write the digits out: round(price, 2).'],
        )
    return f"_apkpyFloat({parts[0]})" if parts[1] else f"String.valueOf({parts[0]})"


def _numberish(node, numeric):
    """Whether *node* is a number whatever the source leaves unsaid: one the
    source proves, sum()/abs()/round(), or a sum with such a number on one
    side (str + int is CPython's TypeError, so the other side is a number too).
    `*` needs both sides ("ab" * 3 is text) and `%` its left ("%d" % n is text).
    """
    if numeric(node) is not None:
        return True
    if isinstance(node, ast.Name) and node.id in _NUMBERISH_NAMES[0]:
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in _ALWAYS_NUMBERS and not node.keywords:
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in ('max', 'min') and len(node.args) >= 2 and not node.keywords \
            and any(_numberish(arg, numeric) for arg in node.args):
        return True                  # max("a", 1) is CPython's TypeError
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _numberish(node.operand, numeric)
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, (ast.Sub, ast.Div, ast.FloorDiv, ast.Pow)):
            # A number whenever Python does not stop (str - str is its
            # TypeError; a set's - would be the exception, and sets are not
            # translated). item["a"] - item["b"] + other: the sum, not text.
            return True
        if isinstance(node.op, ast.Add):
            return _numberish(node.left, numeric) or _numberish(node.right, numeric)
        if isinstance(node.op, ast.Mult):
            return _numberish(node.left, numeric) and _numberish(node.right, numeric)
        if isinstance(node.op, ast.Mod):
            return _numberish(node.left, numeric)
    return False


def _note_numberish(var, value, numeric, known):
    """var = value, in the function being written: keep *var* among the names
    that are surely numbers when the value is one whose kind is not known
    (*known* is what numeric() said of it).

    ('arith', var) marks a name given what _apkpyArith answers when it is not
    surely a number (row["p"] * row["q"] is text if the data holds text), so
    its sums are decided when the app runs too (_apkpyAddAny)."""
    _NUMBERISH_NAMES[0].discard(var)
    _NUMBERISH_NAMES[0].discard(('arith', var))
    if known is None and _numberish(value, numeric):
        _NUMBERISH_NAMES[0].add(var)
    elif known is None and _arith_result(value):
        _NUMBERISH_NAMES[0].add(('arith', var))


def _arith_result(node):
    """Whether *node* is what _apkpyArith answers -- a number or, from *, a
    repeated text or list -- or a name that holds one."""
    if isinstance(node, ast.Name):
        return ('arith', node.id) in _NUMBERISH_NAMES[0]
    return isinstance(node, ast.BinOp) and type(node.op) in _RUNTIME_ARITH \
        and (_item_read(node.left) is not None or _item_read(node.right) is not None
             or _raw_loop_name(node.left) or _raw_loop_name(node.right)
             or _arith_result(node.left) or _arith_result(node.right))


def _raw_loop_name(node):
    """The name of a for over a list, read while its item is at hand."""
    return isinstance(node, ast.Name) and node.id in _RAW_LOOP_VARS[0]


def _forget_numberish(command):
    """Any other command that gives a name a value (storage.get(), a field's
    get_value(), ...) makes it something else."""
    if isinstance(command, dict) and command.get('var') \
            and command.get('type') != 'local_string_assign':
        _NUMBERISH_NAMES[0].discard(command['var'])
        _NUMBERISH_NAMES[0].discard(('arith', command['var']))


def _typed_json_java(node, val_to_java):
    """A value going into a list, a dict or dumps() whose type the source does
    not name but which is still sure, or None.

    A number by _numberish: json.dumps(sum(prices)) wrote "22.25" and
    xs.append(sum(xs)) put '28' in the list. `a if c else b`: each branch as
    itself -- [n if ok else 0] held '1'.
    """
    numeric = getattr(val_to_java, 'numeric', None)
    if numeric is not None and _numberish(node, numeric):
        return "_apkpyNumberOf(String.valueOf(%s))" % val_to_java(node)
    if _arith_result(node):
        # row["price"] * row["qty"]: the number it is, or the repeated text.
        return "_apkpyArithValue(String.valueOf(%s))" % val_to_java(node)
    if isinstance(node, ast.IfExp) and _cond_shape_supported(node.test):
        names = getattr(val_to_java, 'bool_names', None)
        cond = _cond_to_java(node.test, val_to_java, names() if names is not None else ())
        if cond:
            return "(%s ? (Object) %s : (Object) %s)" % (
                cond, _json_node_to_java(node.body, val_to_java),
                _json_node_to_java(node.orelse, val_to_java))
    return None


def _add_java(node, val_to_java, numeric):
    """``a + b`` that is not a sum of two numbers the source proves.

    Two lists join as one list; gluing their JSON gave '["a"]["b"]'. Text
    glues to text. A number on one side and, on the other, something the
    source does not say (a parameter, a value from a dict) is added when the
    app runs: CPython would add two numbers or raise TypeError, and gluing
    them as text, as the phone did, matched neither. Text the source writes
    out plus a number is CPython's TypeError, so it stops the build.
    """
    kinds = (_kind_from(val_to_java, node.left), _kind_from(val_to_java, node.right))
    if 'list' in kinds:
        return (f"_apkpyListConcat(String.valueOf({val_to_java(node.left)}), "
                f"String.valueOf({val_to_java(node.right)}))")
    # sum(prices) + 30.5 was glued as text, "22.2530.5": a side that is surely
    # a number makes it a sum (_numberish), not only one the source proves.
    if _numberish(node.left, numeric) or _numberish(node.right, numeric):
        if 'text' in kinds:
            unsupported.raise_mixed_sum(node)
        return (f"_apkpyAdd(String.valueOf({val_to_java(node.left)}), "
                f"String.valueOf({val_to_java(node.right)}))")
    # rows[0]["n"] + rows[1]["n"]: an item keeps its JSON type, so the sum is
    # decided by what the list or dict holds -- 10 + 7 is 17, "10" + "7" is
    # "107". Both used to be glued as text.
    if 'text' not in kinds and any(_item_read(side) is not None
                                   for side in (node.left, node.right)):
        return "_apkpyAddRaw(%s, %s)" % (_raw_side_java(node.left, val_to_java),
                                         _raw_side_java(node.right, val_to_java))
    # row["tag"] * row["n"] + "|" and a["p"] * a["q"] + b["p"] * b["q"]: what
    # _apkpyArith answers is a number or a repeated text, known when the app runs.
    if any(_arith_result(side) for side in (node.left, node.right)):
        return "_apkpyAddAny(String.valueOf(%s), %s, String.valueOf(%s), %s)" % (
            val_to_java(node.left), 'true' if kinds[0] == 'text' else 'false',
            val_to_java(node.right), 'true' if kinds[1] == 'text' else 'false')
    return f'{val_to_java(node.left)} + {val_to_java(node.right)}'


def _item_read(node):
    """(container, key) for d[k] / rows[i] read the same however often, or None."""
    if not isinstance(node, ast.Subscript):
        return None
    key = node.slice.value if isinstance(node.slice, ast.Index) else node.slice  # 3.8
    if isinstance(key, ast.Slice) or not _reads_the_same_twice(node):
        return None
    return node.value, key


def _raw_side_java(node, val_to_java):
    """One side of _apkpyAddRaw: an item as JSON holds it, anything else as text."""
    item = _item_read(node)
    if item is None:
        return "String.valueOf(%s)" % val_to_java(node)
    container, key = item
    return "_apkpyRawOr(String.valueOf(%s), String.valueOf(%s), String.valueOf(%s))" % (
        val_to_java(container), val_to_java(key), val_to_java(node))


# The operators _apkpyArith answers when the app runs.
_RUNTIME_ARITH = {ast.Sub: '-', ast.Mult: '*', ast.Div: '/', ast.FloorDiv: '//',
                  ast.Mod: '%', ast.Pow: '**'}


def _arith_side_java(node, val_to_java):
    """One operand of _apkpyArith: the value and what the source says it is.

    0 a value the source does not type (a parameter, a name read from
    somewhere): read as the number its text writes, or as text; 1 an item of a
    list or a dict, as the JSON holds it (10, 2.5, "10", [..]); 2 text the
    source says is a str; 3 a list the source says is one. None when the
    source says it is something no arithmetic takes.
    """
    kind = _kind_from(val_to_java, node)
    if kind == 'text':
        return "String.valueOf(%s), 2" % val_to_java(node)
    if kind == 'list':
        return "String.valueOf(%s), 3" % val_to_java(node)
    if kind == 'dict':
        return None
    if _item_read(node) is not None:
        return "%s, 1" % _raw_side_java(node, val_to_java)
    if isinstance(node, ast.Name) and node.id in _RAW_LOOP_VARS[0]:
        # for x in xs: x * 2 -- the item as the JSON holds it, as xs[i] is.
        return "%s, 1" % _RAW_LOOP_VARS[0][node.id]
    return "String.valueOf(%s), 0" % val_to_java(node)


def _arith_any_java(node, val_to_java):
    """a - b, a * b, a / b, a // b, a % b and a ** b when a side is not a
    number the source proves, or None.

    item["price"] * item["qty"] stopped the build: the items of a list of
    dicts, the answer of an API, a parameter, are values whose type only the
    running app knows. _apkpyArith works it out there, with CPython's answers
    -- 2 * 2.5 is 5.0, 7 // 2 is 3, "ab" * 2 is "abab" -- and its TypeError,
    message and all, for a str, a list or None where Python stops.

    Text the source writes out, or a list, with anything but * is CPython's
    TypeError (or % formatting): None, so the build says so.
    """
    symbol = _RUNTIME_ARITH.get(type(node.op))
    if symbol is None:
        return None
    if symbol != '*' and {_kind_from(val_to_java, node.left),
                          _kind_from(val_to_java, node.right)} & {'text', 'list'}:
        return None
    if symbol == '*' and (_ambiguous_factor(node.left, node.right, val_to_java)
                          or _ambiguous_factor(node.right, node.left, val_to_java)):
        return None
    left = _arith_side_java(node.left, val_to_java)
    right = _arith_side_java(node.right, val_to_java)
    if left is None or right is None:
        return None
    return '_apkpyArith("%s", %s, %s)' % (symbol, left, right)


def _ambiguous_factor(side, other, val_to_java):
    """Whether side * other could be text repeated or a product, with no way
    to tell from what the app holds.

    *side* is a value whose kind nobody says (a parameter, a letter of a
    text, a name read from somewhere): its text "5" may be the number or the
    str. Times something that may be an int, Python repeats a str and
    multiplies a number. Against a float, a str is Python's TypeError, so it
    is a number; against text or a list, it is the count.
    """
    numeric = getattr(val_to_java, 'numeric', None)
    if _kind_from(val_to_java, side) is not None or _item_read(side) is not None:
        return False
    if isinstance(side, ast.Name) and side.id in _RAW_LOOP_VARS[0]:
        # The name of a for over a list: its item says whether it is 5 or "5".
        # for x in xs: total += x * 2 stopped the build, the very loop the
        # message about arithmetic on a list told people to write.
        return False
    if numeric is not None and _numberish(side, numeric):
        return False
    if _arith_result(side):
        return False
    if _kind_from(val_to_java, other) in ('text', 'list'):
        return False
    known = numeric(other) if numeric is not None else None
    return not (known is not None and known[1])


def _typed_operand(node, val_to_java):
    """'text', 'list' or 'dict' when the source says a side of *node* is one."""
    for side in (node.left, node.right):
        kind = _kind_from(val_to_java, side)
        if kind in ('text', 'list', 'dict'):
            return kind
    return None


def _negate_any_java(node, val_to_java):
    """-x of a value the source does not type (-item["delta"]), or None."""
    if not isinstance(node.op, ast.USub) or _kind_from(val_to_java, node.operand) in (
            'text', 'list', 'dict'):
        return None
    side = _arith_side_java(node.operand, val_to_java)
    return '_apkpyArith("neg", %s, "0", 0)' % side if side is not None else None


def _emit_function_dispatch(lines, functions_map, names, bool_callbacks):
    """_apkpyCall(name, args...): f(x) of a function kept in a value."""
    lines.append("")
    lines.append("    /** f(x) of a function kept in a value: the one its name says, with")
    lines.append("     *  Python's TypeError when the number of arguments is wrong. */")
    lines.append("    private String _apkpyCall(String fn, String... args) {")
    lines.append('        switch (fn == null ? "" : fn) {')
    for name in names:
        info = functions_map[name]
        params = list(info['args'])
        defaults = info.get('defaults') or {}
        required = [p for p in params if p not in defaults]
        quoted = ", ".join('"%s"' % p for p in params)
        lines.append('            case "%s": {' % name)
        lines.append('                _apkpyArity("%s", %d, %d, args.length, new String[]{%s});'
                     % (name, len(required), len(params), quoted))
        values = []
        for i, p in enumerate(params):
            value = "args[%d]" % i
            if p in defaults:
                d = defaults[p]
                literal = '"%s"' % _escape_java_literal(d.value) if isinstance(d.value, str) \
                    else '"%s"' % repr(d.value)
                value = "(args.length > %d ? args[%d] : %s)" % (i, i, literal)
            if p in ('granted', 'is_granted', 'is_checked', 'success') \
                    or (i == 0 and name in bool_callbacks):
                value = "Boolean.parseBoolean(%s)" % value
            values.append(value)
        call = "pythonCallback_%s(%s)" % (name, ", ".join(values))
        if info.get('returns_value'):
            lines.append("                return String.valueOf(%s);" % call)
        else:
            lines.append("                %s;" % call)
            lines.append("                return ApkpyValues.NONE;")
        lines.append("            }")
    lines.append("            default:")
    lines.append('                throw new ApkpyValues.Raised("TypeError", "\'str\' object is not callable");')
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    private void _apkpyArity(String fn, int least, int most, int given, String[] names) {")
    lines.append("        if (given > most) {")
    lines.append('            String takes = least == most')
    lines.append('                ? most + " positional argument" + (most == 1 ? "" : "s")')
    lines.append('                : "from " + least + " to " + most + " positional arguments";')
    lines.append('            throw new ApkpyValues.Raised("TypeError", fn + "() takes " + takes + " but "')
    lines.append('                + given + (given == 1 ? " was" : " were") + " given");')
    lines.append("        }")
    lines.append("        if (given < least) {")
    lines.append("            int missing = least - given;")
    lines.append("            StringBuilder which = new StringBuilder();")
    lines.append("            for (int i = given; i < least; i++) {")
    lines.append('                if (i > given) which.append(i == least - 1 ? (missing == 2 ? " and " : ", and ") : ", ");')
    lines.append("                which.append('\\'').append(names[i]).append('\\'');")
    lines.append("            }")
    lines.append('            throw new ApkpyValues.Raised("TypeError", fn + "() missing " + missing')
    lines.append('                + " required positional argument" + (missing == 1 ? "" : "s") + ": " + which);')
    lines.append("        }")
    lines.append("    }")


def _counter_call_java(node, val_to_java):
    """A Counter's or a defaultdict's operation (features/counters.py) as its helper."""
    op = counters_feature.op_of(node)
    args = node.args

    def text(arg):
        return "String.valueOf(%s)" % val_to_java(arg)

    def source(arg):
        # Counter(mapping) adds its counts; anything else is counted item by
        # item, as a for over it walks it: text by its letters.
        if _kind_from(val_to_java, arg) == 'dict':
            return text(arg), 'true'
        listed = ast.copy_location(ast.Call(func=ast.Name(id='list', ctx=ast.Load()),
                                            args=[arg], keywords=[]), arg)
        return _list_call_java(listed, val_to_java), 'false'

    if op == 'of':
        return "_apkpyCounterOf(%s, %s)" % source(args[0])
    if op == 'update':
        src, mapping = source(args[1])
        return "_apkpyCounterUpdate(%s, %s, %s, %d)" % (text(args[0]), src, mapping,
                                                       args[2].value)
    if op == 'most_common':
        if len(args) < 2:
            n = "Long.MIN_VALUE"
        else:
            numeric = getattr(val_to_java, 'numeric', None)
            known = numeric(args[1]) if numeric is not None else None
            n = ("(long) (%s)" % known[0]) if known is not None and not known[1] else \
                "(long) Double.parseDouble(String.valueOf(%s))" % val_to_java(args[1])
            n = "Math.max(0L, %s)" % n
        return "_apkpyCounterMostCommon(%s, %s)" % (text(args[0]), n)
    if op == 'show':
        return "_apkpyCounterShow(%s)" % text(args[0])
    if op == 'default_show':
        return '_apkpyDefaultShow(%s, "%s")' % (text(args[0]),
                                               _escape_java_literal(args[1].value))
    raise ValueError("unknown Counter operation: %s" % op)


def _set_call_java(node, val_to_java):
    """A set's operation (features/sets.py) as the Java helper that does it."""
    op = sets_feature.op_of(node)
    args = node.args

    def text(arg):
        return "String.valueOf(%s)" % val_to_java(arg)

    def items(arg):
        # Any iterable as the JSON list a for over it walks: a set or a list
        # is itself, text its letters, a dict its keys.
        listed = ast.copy_location(ast.Call(func=ast.Name(id='list', ctx=ast.Load()),
                                            args=[arg], keywords=[]), arg)
        return _list_call_java(listed, val_to_java)

    if op == 'of':
        return "_apkpySetOf(%s)" % items(args[0])
    if op == 'fixed':
        # A literal of constants, in the order CPython gives it (sets.py).
        return items(args[0])
    if op == 'add':
        return "_apkpySetAdd(%s, %s)" % (text(args[0]), _json_value_java(args[1], val_to_java))
    if op in ('discard', 'remove'):
        return "_apkpySetRemove(%s, %s, %s)" % (
            text(args[0]), _json_value_java(args[1], val_to_java),
            'true' if op == 'remove' else 'false')
    if op == 'intersection':
        both_sets = len(args) > 2 and isinstance(args[2], ast.Constant) and args[2].value
        return "_apkpySetInter(%s, %s, %s)" % (text(args[0]), items(args[1]),
                                              'true' if both_sets else 'false')
    if op in ('union', 'difference', 'without', 'symmetric_difference'):
        name = {'union': 'Union', 'difference': 'Diff', 'without': 'Without',
                'symmetric_difference': 'SymDiff'}[op]
        return "_apkpySet%s(%s, %s)" % (name, text(args[0]), items(args[1]))
    if op in sets_feature.BOOL_RESULTS:
        return '_apkpyBool(_apkpySetCompare("%s", %s, %s))' % (op, text(args[0]), items(args[1]))
    if op == 'show':
        return "_apkpySetShow(%s)" % text(args[0])
    if op == 'popvalue':
        return "_apkpySetPopValue(%s)" % text(args[0])
    if op == 'rest':
        return "_apkpySetRest(%s)" % text(args[0])
    if op == 'clear':
        return '"[]"'
    raise ValueError("unknown set operation: %s" % op)


def _numeric_call_java(node, numeric, val_to_java):
    """(Java, is_float) for a call that answers a number, or None.

    The value translations of these calls answer text, and a sum with text on
    one side glued the two: len(name) + 1 showed "31" for "abc", abs(n) + 1
    "51" for 5.
    """
    item = _number_item_java(node, val_to_java)
    if item is not None:
        return item
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in ('find', 'rfind', 'count', 'index') and len(node.args) == 1 \
            and not node.keywords:
        # Always a whole number, as text: xs.count(a) + xs.count(b) glued them.
        return (f"Long.parseLong(String.valueOf({val_to_java(node)}))", False)
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name))             or node.keywords:
        return None
    name, args = node.func.id, node.args
    if name == 'pow' and len(args) == 3:
        # pow(a, b, m): exact (BigInteger), with Python's sign and its inverse
        # for a negative b. Whole numbers only, as in Python.
        parts = [numeric(arg) for arg in args]
        if any(part is None or part[1] for part in parts):
            return None
        return (f"_apkpyPowMod((long)({parts[0][0]}), (long)({parts[1][0]}), (long)({parts[2][0]}))", False)
    if name == 'ord' and len(args) == 1:
        return (f"_apkpyOrd(String.valueOf({val_to_java(args[0])}))", False)
    if name == 'len' and len(args) == 1:
        return (f"((long) {_len_int_java(node, val_to_java)})", False)
    if name == 'abs' and len(args) == 1:
        inner = numeric(args[0])
        if inner is None:
            return None
        if inner[1]:
            return (f"Math.abs({inner[0]})", True)
        return (f"_apkpyAbsL({inner[0]})", False)
    if name == 'round' and 1 <= len(args) <= 2:
        return _round_parts(node, val_to_java, numeric)
    if name in ('max', 'min') and len(args) >= 2:
        parts = [numeric(arg) for arg in args]
        if any(part is None for part in parts):
            return None
        if any(part[1] for part in parts):
            if not all(part[1] for part in parts):
                return None          # max(3, 2.5) is the int 3: not a float
            return (f"Double.parseDouble({val_to_java(node)})", True)
        java = parts[0][0]
        fn = "Math.max" if name == 'max' else "Math.min"
        for part in parts[1:]:
            java = f"{fn}((long)({java}), (long)({part[0]}))"
        return (java, False)
    if name in _NUMERIC_RETURNS[0]:
        if _NUMERIC_RETURNS[0][name]:
            return (f"Double.parseDouble(String.valueOf({val_to_java(node)}))", True)
        return (f"Long.parseLong(String.valueOf({val_to_java(node)}))", False)
    return None


def _drop_unused_struct_fields(lines):
    """Keep a module list's field only in the classes that read it.

    Every class gets the fields while it is being written, before its code
    is known; a catalogue that only the list on one screen shows would
    otherwise be copied into every screen of the app.
    """
    names = set(_MODULE_STRUCT_TEXT[0])
    if not names:
        return lines
    prefix = '    private static final String '

    def field_name(line):
        if isinstance(line, str) and line.startswith(prefix):
            name = line[len(prefix):].split(' ', 1)[0]
            if name in names:
                return name
        return None

    body = "\n".join(line for line in lines if field_name(line) is None)
    return [line for line in lines
            if field_name(line) is None
            or re.search(r'\b%s\b' % re.escape(field_name(line)), body)]


def _rich_set_value_java(indent, ctype, jv, val_java, node=None):
    """set_value() on a markdown, a rich_text or a tree_view, as Java.

    The view is an ApkpyRichContentView (a LinearLayout), not a TextView: the
    cast this used to write compiled and threw ClassCastException on the
    phone. A markdown takes its new text through setMarkdown(); the other two
    are drawn from what the source writes out, so changing them stops the
    build instead.
    """
    if ctype == 'markdown':
        return (f'{indent}((ApkpyRichContentView) findViewById(R.id.{jv}))'
                f'.setMarkdown(String.valueOf({val_java}));')
    unsupported.raise_unsupported(
        node,
        cause=('A %s is drawn from what the source writes out, and has no text '
               'to replace while the app runs.' % ctype),
        suggestions=['Use a markdown() and set_value() on it: markdown("", id="body") '
                     'then body.set_value("**new** text").',
                     'Or keep the %s as written, and show the changing part in a '
                     'label next to it.' % ctype],
        received='%s.set_value(...)' % ctype)


def _written_out(node):
    """Whether this value is written out to the last item: ast.literal_eval()
    can read it. True for [1, "a", {"k": 2}], False for [{"k": name}]."""
    try:
        ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return False
    return True


def _navigate_data_pairs(node):
    """(key, value node) for each entry of the data of on_click_navigate().

    The data has to be a dict written in the call, with its keys written out:
    those are the extras the next screen's get_param() reads, and they are
    put on the Intent one by one. Anything else -- a name holding a dict, a
    key worked out -- was dropped without a word, and the next screen opened
    empty; now it stops the build and says what to write.
    """
    if node is None or (isinstance(node, ast.Constant) and node.value is None):
        return []
    if isinstance(node, ast.Dict) and all(
            isinstance(k, ast.Constant) and isinstance(k.value, (str, int))
            and not isinstance(k.value, bool) for k in node.keys):
        return list(zip([k.value for k in node.keys], node.values))
    unsupported.raise_unsupported(
        node,
        cause=('The data of on_click_navigate() becomes the extras of the '
               'Android Intent, one per key, so the build has to see each key. '
               'Here it cannot, and the next screen would open with '
               'get_param() at its default.'),
        suggestions=['Write the data as a dict in the call, with each key '
                     'written out: on_click_navigate(detail, {"id": item["id"]})',
                     'The values can be anything: only the keys have to be '
                     'written out.'])


def _storage_key_java(c, val_to_java):
    """The key of a storage command, as Java.

    A key written out stays the literal it always was. Any other key -- a
    name, a sum, an f-string -- is worked out while the app runs: it used to
    be the empty key "", so storage.set(name, v) saved every value in one
    place and each one overwrote the last.
    """
    node = c.get('key_node')
    if node is None or (isinstance(node, ast.Constant) and not isinstance(node.value, bool)):
        return '"%s"' % _escape_java_literal(str(c.get('key', '')))
    return 'String.valueOf(%s)' % val_to_java(node)


def _storage_default_java(c, val_to_java):
    """The default of name = storage.get(key, default), as Java: a default
    written out as before, and a name or an expression read while the app
    runs (it was "")."""
    node = c.get('default_node')
    if node is None or isinstance(node, ast.Constant):
        return c['default']
    return 'String.valueOf(%s)' % val_to_java(node)


# The class file keeps a string constant in at most 65535 bytes of modified
# UTF-8; a piece stays well under it.
_JAVA_PIECE_BYTES = 60000


def _java_constant_bytes(ch):
    """The bytes one character takes in a class file's modified UTF-8."""
    point = ord(ch)
    if point == 0:
        return 2
    if point < 0x80:
        return 1
    if point < 0x800:
        return 2
    if point < 0x10000:
        return 3
    return 6            # a surrogate pair, three bytes each


def _java_string_field(name, text):
    """A module constant as a Java field: a literal, or -- when the text is
    more than a string constant can hold -- built at class load from pieces
    that each fit. A literal that big stopped javac with "constant string
    too long"; a list or a dict that big was left out, and every use of it
    stopped javac with "cannot find symbol". StringBuilder, because javac
    would join "a" + "b" back into one constant.
    """
    text = str(text)
    if sum(_java_constant_bytes(ch) for ch in text) <= _JAVA_PIECE_BYTES:
        return f'    private static final String {name} = "{_escape_java_literal(text)}";'
    pieces, current, size = [], [], 0
    for ch in text:
        step = _java_constant_bytes(ch)
        if size + step > _JAVA_PIECE_BYTES:
            pieces.append("".join(current))
            current, size = [], 0
        current.append(ch)
        size += step
    if current:
        pieces.append("".join(current))
    appends = "".join('.append("%s")' % _escape_java_literal(piece) for piece in pieces)
    return (f'    private static final String {name} = '
            f'new StringBuilder({len(text)}){appends}.toString();')


def _module_struct_fields(string_constants=None):
    """The Java fields of the module-level lists, tuples and dicts.

    A text bigger than a Java string constant can hold is built from pieces
    (_java_string_field).
    """
    fields = []
    for name, text in _MODULE_STRUCT_TEXT[0].items():
        if name in (string_constants or {}) or name in _NUMERIC_CONST_TEXT[0]:
            continue
        fields.append(_java_string_field(name, text))
    return fields


def _split_java(node, val_to_java):
    """text.split(sep, maxsplit), with Python's rules, as JSON text.

    Java's String.split gave a String[], and String.valueOf of that is
    "[Ljava.lang.String;@1b6d3586": a for loop over it ran no times, len()
    counted its characters, and a label showed the address. It also read the
    separator as a regular expression -- "." matched every character -- and
    dropped the empty parts at the end. _apkpySplit reads the separator as
    text and keeps them, as Python does.
    """
    if not _is_split_call(node):
        unsupported.raise_unsupported(node)
    keywords = {k.arg: k.value for k in node.keywords}
    if len(node.args) > 2 or set(keywords) - {'sep', 'maxsplit'} \
            or ('sep' in keywords and node.args) \
            or ('maxsplit' in keywords and len(node.args) > 1):
        unsupported.raise_unsupported(node)
    sep = keywords.get('sep', node.args[0] if node.args else None)
    maxsplit = keywords.get('maxsplit', node.args[1] if len(node.args) > 1 else None)
    if isinstance(sep, ast.Constant) and sep.value == "":
        unsupported.raise_unsupported(
            node,
            cause=('An empty separator has no meaning, and Python itself stops '
                   'with ValueError: empty separator.'),
            suggestions=['Pass the separator you mean, such as "," or " ".',
                         'To split on runs of spaces, call split() with nothing.'])
    text = "String.valueOf(%s)" % val_to_java(node.func.value)
    if sep is None or (isinstance(sep, ast.Constant) and sep.value is None):
        sep_java = "null"
    else:
        sep_java = "String.valueOf(%s)" % val_to_java(sep)
    limit = ('"-1"' if maxsplit is None
             else "String.valueOf(%s)" % val_to_java(maxsplit))
    return "_apkpySplit(%s, %s, %s)" % (text, sep_java, limit)



def _compare_side_java(node, val_to_java):
    """One side of _apkpyCompare, and whether it is the item as the JSON holds it."""
    raw = _raw_item_java(node, val_to_java)
    if raw is not None:
        return raw, True
    return "String.valueOf(%s)" % val_to_java(node), False


def _compare_node_to_java(cmp, val_to_java):
    """Java de um único `ast.Compare` (==, !=, <, >, <=, >=), a partir do nó cru.

    Espelha a lógica de `_if_compare_cond` mas trabalha sobre o AST, para poder
    ser reutilizado dentro de condições com and/or/not. Devolve None se a forma
    não for suportada (o chamador cai num fallback seguro).

      - right constante string + ==/!=     → left.equals(...) / !left.equals(...)
      - right constante string + relacional→ left.compareTo(...) <op> 0  (lexicográfico)
      - right constante número              → Double.parseDouble(left) <op> right
      - right é outra expressão (var, ...)  → números se um dos lados for um
        número conhecido; texto se um dos lados for texto conhecido; senão
        <, >, <=, >= pelo que cada lado tem (_apkpyCompare) e == / != texto
    """
    if not (cmp.ops and cmp.comparators):
        return None
    for side in (cmp.left, cmp.comparators[0]):
        # A side ApkPy could not write comes back as "". As a number that is
        # Double.parseDouble(""), which crashes the screen when it runs; as
        # text it quietly compares against nothing. It has to stop here.
        if not (isinstance(side, ast.Constant) and side.value == "") \
                and not unsupported.reaches_other_runtime(side) \
                and val_to_java(side) == '""' \
                and id(side) not in _ELSEWHERE_EMPTY[0]:
            unsupported.raise_untranslated_condition(cmp)
    if isinstance(cmp.ops[0], (ast.In, ast.NotIn)):
        expr = _membership_java(cmp.left, cmp.comparators[0], val_to_java)
        return ("!" + expr) if isinstance(cmp.ops[0], ast.NotIn) else expr
    op = _CMP_OPS.get(type(cmp.ops[0]))
    if op is None:
        return None
    left = cmp.left
    right_node = cmp.comparators[0]
    # A name goes through val_to_java too: a `global` name is read from the
    # shared store, not from a local of the same spelling.
    left_j = val_to_java(left) if isinstance(left, ast.Name) else f"String.valueOf({val_to_java(left)})"
    if isinstance(right_node, ast.Constant) and isinstance(right_node.value, str):
        rv = '"' + _escape_java_literal(right_node.value) + '"'
        if op == '==':
            return f"{left_j}.equals({rv})"
        if op == '!=':
            return f"!{left_j}.equals({rv})"
        return f"String.valueOf({left_j}).compareTo({rv}) {op} 0"
    if isinstance(right_node, ast.Constant) and isinstance(right_node.value, (int, float)) and not isinstance(right_node.value, bool):
        return f"Double.parseDouble(String.valueOf({left_j})) {op} {right_node.value}"
    # Neither side is written out, so what the two hold decides how they are
    # compared -- and that is read from the source, like everything else. A
    # side ApkPy knows is a number makes it a comparison of numbers. As text,
    # `while i < n` stopped at 2 when n was 12: "2" sorts after "12".
    numeric = getattr(val_to_java, 'numeric', None)
    if numeric is not None:
        left_n, right_n = numeric(left), numeric(right_node)
        if left_n is not None or right_n is not None:
            ln = left_n[0] if left_n is not None else \
                f"Double.parseDouble(String.valueOf({val_to_java(left)}))"
            rn = right_n[0] if right_n is not None else \
                f"Double.parseDouble(String.valueOf({val_to_java(right_node)}))"
            return f"({ln}) {op} ({rn})"
    rj = f"String.valueOf({val_to_java(right_node)})"
    if op == '==':
        return f"{left_j}.equals({rj})"
    if op == '!=':
        return f"!{left_j}.equals({rj})"
    if 'text' not in (_kind_from(val_to_java, left), _kind_from(val_to_java, right_node)):
        # Nor is either side said to be text: an item of a list, the name of
        # a for over one, a parameter. As text, the largest of [9, 12, 10]
        # found in a for was 9 ("9" sorts after "12"). What each side holds
        # decides, read as isinstance() reads it (_apkpyCompare).
        (lj, l_raw), (rj2, r_raw) = (_compare_side_java(left, val_to_java),
                                     _compare_side_java(right_node, val_to_java))
        return '_apkpyCompare(%s, %s, %d, "%s") %s 0' % (
            lj, rj2, (1 if l_raw else 0) | (2 if r_raw else 0), op, op)
    return f"String.valueOf({left_j}).compareTo({rj}) {op} 0"


# Métodos de string que devolvem booleano e que sabemos usar numa condição
# (`if x.isdigit():`, `if email.endswith("@gmail.com"):`, `if not x.startswith("PT"):`).
# Cada entrada: (nº de args, template Java) — {b}=base (texto à esquerda do ponto),
# {a}=1º argumento. startswith/endswith mapeiam DIRETO para os métodos Java homónimos
# (paridade exata com o Python). isdigit não leva argumento: str.isdigit() ≈
# matches("\\d+") (1+ dígitos; "" e "12a" dão False nos dois lados). NÃO incluímos
# `isalpha` de propósito (aceita letras Unicode á/ã/ç que "[a-zA-Z]+" rejeitaria).
_STR_BOOL_PREDICATES = {
    # \d in a Java regex is 0-9 only; Python's isdigit() takes ٣ and ² too.
    'isdigit':    (0, r'_apkpyStrIs(String.valueOf({b}), "digit")'),
    'isalpha':    (0, r'_apkpyStrIs(String.valueOf({b}), "alpha")'),
    'isalnum':    (0, r'_apkpyStrIs(String.valueOf({b}), "alnum")'),
    'isdecimal':  (0, r'_apkpyStrIs(String.valueOf({b}), "decimal")'),
    'isnumeric':  (0, r'_apkpyStrIs(String.valueOf({b}), "numeric")'),
    'isspace':    (0, r'_apkpyStrIs(String.valueOf({b}), "space")'),
    'isupper':    (0, r'_apkpyStrIs(String.valueOf({b}), "upper")'),
    'islower':    (0, r'_apkpyStrIs(String.valueOf({b}), "lower")'),
    'isascii':    (0, r'_apkpyStrIs(String.valueOf({b}), "ascii")'),
    'startswith': (1, r'String.valueOf({b}).startsWith(String.valueOf({a}))'),
    'endswith':   (1, r'String.valueOf({b}).endsWith(String.valueOf({a}))'),
}


def _affix_java(node, base, val_to_java):
    """``s.startswith(x)`` / ``s.endswith(x)`` as a Java boolean, as Python answers.

    A tuple is any of its items: ``s.endswith((".jpg", ".png"))`` was looked
    for as the JSON text '[".jpg",".png"]' and answered False, with no word.
    A start or an end (``s.startswith("b", 1)``) was dropped as silently, so
    it stops the build now.
    """
    name = node.func.attr
    java = 'startsWith' if name == 'startswith' else 'endsWith'
    if len(node.args) > 1 or node.keywords:
        unsupported.raise_unsupported(
            node, cause=f"{name}() with a start or an end is not translated yet.",
            suggestions=(f"slice the text first: text[start:end].{name}(...)",))
    text = f"String.valueOf({base})"
    arg = node.args[0]
    if isinstance(arg, ast.Tuple):
        parts = [f"{text}.{java}(String.valueOf({val_to_java(e)}))" for e in arg.elts]
        return "(" + (" || ".join(parts) if parts else "false") + ")"
    if tuples_feature.is_tuple(arg):
        flag = 'true' if java == 'startsWith' else 'false'
        return f"_apkpyAffixAny({text}, String.valueOf({val_to_java(arg)}), {flag})"
    return f"{text}.{java}(String.valueOf({val_to_java(arg)}))"


# Endpoints OAuth2 (authorization-code + PKCE) por provider. (auth_url, token_url,
# scopes-default). Usado por auth.login(provider=...). Para outro provider, passa
# auth_url=/token_url= directamente.
_OAUTH_PROVIDERS = {
    'google':  ('https://accounts.google.com/o/oauth2/v2/auth', 'https://oauth2.googleapis.com/token', 'openid email profile'),
    'spotify': ('https://accounts.spotify.com/authorize', 'https://accounts.spotify.com/api/token', 'user-read-email user-read-private'),
    'github':  ('https://github.com/login/oauth/authorize', 'https://github.com/login/oauth/access_token', 'read:user'),
}

# Perfil do utilizador (auth.user) por provider: endpoint + nomes dos campos do
# JSON, normalizados p/ {name, email, picture}. "__spotify_images__" = caso especial
# (o Spotify devolve images[0].url em vez de um campo simples).
_OAUTH_USERINFO = {
    'google':  {'url': 'https://www.googleapis.com/oauth2/v3/userinfo', 'name': 'name', 'email': 'email', 'picture': 'picture'},
    'spotify': {'url': 'https://api.spotify.com/v1/me', 'name': 'display_name', 'email': 'email', 'picture': '__spotify_images__'},
    'github':  {'url': 'https://api.github.com/user', 'name': 'name', 'email': 'email', 'picture': 'avatar_url'},
}


# Methods whose answer is text (or a list, for split), the same in the
# Previewer and on the phone, so its truth is the truth of that text. A kit
# call answering True or False is not here: each has its own arm.
_TRUTH_TEXT_METHODS = frozenset({
    'get_value', 'upper', 'lower', 'strip', 'lstrip', 'rstrip', 'title',
    'capitalize', 'casefold', 'replace', 'join', 'split', 'format',
})


def _is_text_method_call(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in _TRUTH_TEXT_METHODS)


def _cond_shape_supported(node):
    """True se o `if` é uma combinação de comparações/nomes com and/or/not que
    sabemos traduzir. Verificado no parsing (sem precisar de val_to_java)."""
    if regex_feature.condition(node, lambda n: "") is not None:
        return True
    if isinstance(node, ast.BoolOp):
        return bool(node.values) and all(_cond_shape_supported(v) for v in node.values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _cond_shape_supported(node.operand)
    if isinstance(node, ast.Compare):
        # A chain like 0 < x < 10 is each pair joined with && (it used to
        # compile as its first comparison and quietly lose the rest).
        if len(node.ops) > 1:
            return all(type(op) in _CMP_OPS for op in node.ops)
        return (type(node.ops[0]) in _CMP_OPS
                or isinstance(node.ops[0], (ast.In, ast.NotIn, ast.Is, ast.IsNot)))
    if isinstance(node, ast.Name):
        return True
    # if d["done"]:  |  if is_valid(x):  |  if q.strip():  -- the truth of a value.
    if isinstance(node, ast.Subscript):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return True
    if _is_text_method_call(node):
        return True
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _STR_BOOL_PREDICATES:
        return len(node.args) >= _STR_BOOL_PREDICATES[node.func.attr][0]
    # ReactiveState.get() in a condition. The value is stored as "true"/"false"
    # on Android and converted back to a boolean by _cond_to_java. A dict's
    # get() is the truth of the value.
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr == 'get' and (isinstance(node.func.value, ast.Name)
                                             or _dict_receiver(node.func.value)):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in _DICT_VALUE_METHODS + ('copy',) and not node.args \
            and _dict_receiver(node.func.value):
        return True
    # files.exists("nome") — ficheiro local já descarregado? (if offline)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and isinstance(node.func.value, ast.Name) and node.func.value.id == 'files' \
            and node.func.attr == 'exists':
        return len(node.args) >= 1
    # auth.is_logged_in() — há token guardado? (if proteger ecrã)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and isinstance(node.func.value, ast.Name) and node.func.value.id == 'auth' \
            and node.func.attr == 'is_logged_in':
        return True
    # flashlight.is_on() / available() — the torch, asked about rather
    # than remembered. Without this arm the `if` falls through to False
    # and the whole branch is dropped without a word.
    if draw_pad_feature.is_value_call(node):
        return True
    if flashlight_feature.is_value_call(node):
        return True
    if wallpaper_feature.is_value_call(node):
        return True
    if camera_feature.is_value_call(node):
        return True
    # sensors.available() / battery.charging() / battery.saver() -- the
    # same trap: without this arm the branch is dropped in silence.
    if sensors_feature.is_value_call(node):
        return True
    if notifications_feature.is_value_call(node):
        return True
    # validate(a, b) / a.validate() -- whether the form may be sent.
    if field_feature.is_check_call(node):
        return True
    return False


def _cond_to_java(node, val_to_java, bool_names=()):
    """Constrói a condição Java de um `if` com and/or/not (Tier 1 C do roadmap).

    `and`→`&&`, `or`→`||`, `not`→`!`. Cada operando é uma comparação
    (via `_compare_node_to_java`), um nome (truthiness, via `_truthy_java`,
    respeitando args boolean de callbacks) ou um literal booleano. Devolve None se
    algum operando não for suportado.
    """
    regex_condition = regex_feature.condition(node, val_to_java)
    if regex_condition is not None:
        return regex_condition
    if isinstance(node, ast.BoolOp):
        joiner = " && " if isinstance(node.op, ast.And) else " || "
        parts = []
        for v in node.values:
            p = _cond_to_java(v, val_to_java, bool_names)
            if p is None:
                return None
            parts.append(f"({p})")
        return joiner.join(parts)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        inner = _cond_to_java(node.operand, val_to_java, bool_names)
        return f"!({inner})" if inner is not None else None
    if isinstance(node, ast.Compare):
        return _compare_cond_java(node, val_to_java, bool_names)
    if isinstance(node, ast.Name):
        if node.id in _BOOL_VAR_NAMES or node.id in bool_names:
            return "(%s)" % node.id
        return _truthy_java(node, val_to_java)
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return 'true' if node.value else 'false'
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _STR_BOOL_PREDICATES:
        n_args, tmpl = _STR_BOOL_PREDICATES[node.func.attr]
        base = val_to_java(node.func.value)
        if n_args == 0:
            return tmpl.format(b=base)
        if node.func.attr in ('startswith', 'endswith') and node.args:
            return _affix_java(node, base, val_to_java)
        if node.args:
            return tmpl.format(b=base, a=val_to_java(node.args[0]))
        return None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in ('get',) + _DICT_VALUE_METHODS + ('copy',) \
            and _dict_method_java(node, val_to_java) is not None:
        # if d.get("done"): -- the truth of the value, as Python reads it.
        return _truthy_java(node, val_to_java)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and isinstance(node.func.value, ast.Name) and node.func.attr == 'get':
        return f"Boolean.parseBoolean(String.valueOf({val_to_java(node)}))"
    # files.exists("nome") → o ficheiro existe na pasta privada da app?
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and isinstance(node.func.value, ast.Name) and node.func.value.id == 'files' \
            and node.func.attr == 'exists' and node.args:
        _name = val_to_java(node.args[0])
        return f"new java.io.File(getApplicationContext().getFilesDir(), String.valueOf({_name})).exists()"
    if draw_pad_feature.is_value_call(node):
        # "True"/"False" from the screen's own pad (an empty one where there is none)
        return draw_pad_feature.condition_java(val_to_java(node))
    if flashlight_feature.is_value_call(node):
        return flashlight_feature.condition_java(node)
    if wallpaper_feature.is_value_call(node):
        return wallpaper_feature.condition_java(node)
    if camera_feature.is_value_call(node):
        return camera_feature.condition_java(node)
    if sensors_feature.is_value_call(node):
        return sensors_feature.condition_java(node)
    if notifications_feature.is_value_call(node):
        return 'ApkpyNotifications.allowed(getApplicationContext())'
    if field_feature.is_check_call(node):
        return field_feature.condition_java(node, val_to_java)
    # auth.is_logged_in() → há um access token guardado?
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and isinstance(node.func.value, ast.Name) and node.func.value.id == 'auth' \
            and node.func.attr == 'is_logged_in':
        return 'ApkpyAuth.loggedIn(getApplicationContext())'
    if _is_isinstance(node):
        return _isinstance_java(node, val_to_java, bool_names)
    # if d["done"]:  |  if is_valid(x):  |  if q.strip():  -- the value's
    # truth, as Python reads it.
    if isinstance(node, ast.Subscript) or _is_text_method_call(node) or (
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
        return _truthy_java(node, val_to_java)
    return None


# Builtins that answer the same however often they are asked.
_SAME_TWICE_CALLS = frozenset({'len', 'abs', 'int', 'float', 'str', 'round', 'min', 'max'})


def _reads_the_same_twice(node):
    """True when reading node twice gives what Python's one read gives.

    Names, values written out, items, arithmetic and len()-like builtins of
    those. A call to a function of the app could change something, or
    answer differently the second time.
    """
    if isinstance(node, (ast.Name, ast.Constant)):
        return True
    if isinstance(node, ast.Subscript):
        index = node.slice.value if isinstance(node.slice, ast.Index) else node.slice  # 3.8
        return _reads_the_same_twice(node.value) and _reads_the_same_twice(index)
    if isinstance(node, ast.BinOp):
        return _reads_the_same_twice(node.left) and _reads_the_same_twice(node.right)
    if isinstance(node, ast.UnaryOp):
        return _reads_the_same_twice(node.operand)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in _SAME_TWICE_CALLS and not node.keywords:
        return all(_reads_the_same_twice(arg) for arg in node.args)
    return False


def _compare_cond_java(node, val_to_java, bool_names=()):
    """A comparison in a condition: `is None`, chains, and the rest.

    ``0 < x < 10`` is each pair joined with &&, as Python reads it. A middle
    value is read twice that way, which is the same as Python's one read only
    when nothing in it can change or answer differently (_reads_the_same_twice).
    """
    if len(node.ops) > 1:
        sides = [node.left] + list(node.comparators)
        for middle in sides[1:-1]:
            if not _reads_the_same_twice(middle):
                unsupported.raise_unsupported(
                    node,
                    cause=('In a chain like 0 < x < 10 the middle value is read '
                           'twice on the phone, and a call to a function could '
                           'answer differently the second time. Python reads it '
                           'once.'),
                    suggestions=['Put the value in a name first: x = f(), '
                                 'then 0 < x < 10.'],
                )
        parts = []
        for left, op, right in zip(sides, node.ops, sides[1:]):
            pair = ast.copy_location(ast.Compare(left=left, ops=[op], comparators=[right]), node)
            part = _compare_cond_java(pair, val_to_java, bool_names)
            if part is None:
                return None
            parts.append("(%s)" % part)
        return " && ".join(parts)
    op = node.ops[0]
    right = node.comparators[0]
    left = node.left
    if isinstance(op, (ast.Is, ast.IsNot, ast.Eq, ast.NotEq)):
        for a, b in ((left, right), (right, left)):
            if isinstance(b, ast.Constant) and isinstance(b.value, _SINGLETONS):
                return _identity_java(a, b, isinstance(op, (ast.IsNot, ast.NotEq)),
                                      val_to_java, bool_names)
    if isinstance(op, (ast.Is, ast.IsNot)):
        unsupported.raise_unsupported(
            node,
            cause=('is compares objects. On the phone every value is text, so '
                   'only None, True and False can be compared with is.'),
            suggestions=['Use == to compare values: if a == b:'],
        )
    return _compare_node_to_java(node, val_to_java)


def _callback_call_args(name, nodes, val, functions_map, boolean_first=(), bool_names=()):
    """Forward callbacks without turning their typed boolean into a String."""
    target_args = functions_map.get(name, {}).get('args', [])
    result = []
    for i, node in enumerate(nodes):
        target = target_args[i] if i < len(target_args) else ''
        if (i == 0 and name in (boolean_first or ())) or target in ('granted', 'is_granted', 'is_checked', 'success'):
            expression = _cond_to_java(node, val, bool_names)
            if expression is None:
                unsupported.raise_untranslated_condition(node)
            result.append(expression)
        elif isinstance(node, ast.Constant) and (node.value is None
                                                 or isinstance(node.value, bool)):
            # None/True/False reach a text parameter as the app's own values,
            # which `if flag:` and `is None` recognise inside the function.
            result.append(_text_value_java(node, val))
        else:
            result.append(f"String.valueOf({val(node)})")
    return ", ".join(result)


def _ternary_to_java(node, val_to_java, bool_names=()):
    """Expressão ternária Python `A if cond else B` (ast.IfExp) → Java
    `(cond ? String.valueOf(A) : String.valueOf(B))`. Só quando a condição tem
    forma suportada (Name/comparação/and/or/not/predicados); caso contrário
    devolve None e o chamador cai no fallback "" (sem gerar Java inválido).
    Encaixa no modelo "tudo é String": ambos os ramos são valores-string."""
    if not _cond_shape_supported(node.test):
        return None
    cond = _cond_to_java(node.test, val_to_java, bool_names)
    if not cond:
        return None
    return f"({cond} ? String.valueOf({val_to_java(node.body)}) : String.valueOf({val_to_java(node.orelse)}))"


# Os `if` cujos dois ramos podem devolver. Servem aos dois geradores: o Worker
# passou a escrever `if permissions.has(...)` (antes deitava-o fora, e por isso
# tinha uma lista sua sem ele).
_IF_TYPES_THAT_RETURN = ('if_compare', 'if_var', 'if_cond', 'if_has_permission')


def _cmds_definitely_return(cmds, if_types=_IF_TYPES_THAT_RETURN):
    """True se a lista de cmds termina SEMPRE num `return` (em todos os caminhos).
    Serve para não emitir um `return "";` final INALCANÇÁVEL — em Java um statement
    inalcançável é erro de compilação. Cobre os casos comuns: último cmd é um
    return, é um if/else em que ambos os ramos devolvem, ou é um try/except em
    que o corpo E o handler devolvem (tudo recursivo)."""
    if not cmds:
        return False
    last = cmds[-1]
    if not isinstance(last, dict):
        return False
    t = last.get('type')
    if t == 'return':
        return True
    if t in if_types:
        return (_cmds_definitely_return(last.get('true_body') or [], if_types)
                and _cmds_definitely_return(last.get('false_body') or [], if_types))
    if t == 'try_block':
        # Um try/except em que os dois lados devolvem tambem nao termina
        # normalmente. Um `finally` que devolve basta sozinho; sem ele, tem de
        # devolver o corpo E o handler -- um `except` vazio deixa o codigo
        # seguinte alcancavel, e ai o return final faz mesmo falta.
        if _cmds_definitely_return(last.get('final') or [], if_types):
            return True
        # Each except is its own branch; one that no except names is thrown.
        return (_cmds_definitely_return(last.get('body') or [], if_types)
                and all(_cmds_definitely_return(clause.get('body') or [], if_types)
                        for clause in last.get('handler') or []))
    return False


def _escape_java_literal(s):
    """Escapa uma string Python para um literal de String Java (`\\` primeiro)."""
    return (str(s).replace('\\', '\\\\')
                  .replace('"', '\\"')
                  .replace('\n', '\\n')
                  .replace('\r', '\\r')
                  .replace('\t', '\\t'))


def _rich_item_java_literal(title, subtitle, image, src=''):
    """Literal Java de um item de list_view rico, em JSON (sem o problema do
    separador ' — ' colidir com texto que tenha esse traço). Ex.:
    `"{\\"title\\":\\"...\\",...}"`.
    `src` (opcional) é a fonte de áudio da faixa — só vai p/ o JSON quando
    existe, p/ o on_click poder fazer tap-to-play: item["src"]."""
    payload_dict = {'title': str(title), 'subtitle': str(subtitle), 'image': str(image)}
    if src:
        payload_dict['src'] = str(src)
    payload = json.dumps(payload_dict, ensure_ascii=False)
    return '"' + _escape_java_literal(payload) + '"'


def _list_row_java_literal(item, rich=False):
    """Java literal for one list_view row.

    A row written as a dict keeps every key it was written with, so the
    callback that receives it can read ``item["id"]`` as it does in the
    Previewer; ``title`` and ``subtitle`` (and ``image`` for a rich row) are
    always present, because the adapters draw from them. A row written as text
    stays text in a plain list.
    """
    if isinstance(item, dict):
        payload = {'title': str(item.get('title', '')),
                   'subtitle': str(item.get('subtitle', ''))}
        if rich:
            payload['image'] = str(item.get('image', ''))
        for key, value in item.items():
            # An empty extra key reads the same as a missing one (_jsonGet
            # answers ""), so it is not written: the parser fills "src": ""
            # into rows that never had one.
            if str(value) != '':
                payload.setdefault(str(key), str(value))
    elif rich:
        payload = {'title': str(item), 'subtitle': '', 'image': ''}
    else:
        return '"' + _escape_java_literal(str(item)) + '"'
    return '"' + _escape_java_literal(json.dumps(payload, ensure_ascii=False)) + '"'


def _collection_item_java_literal(item):
    """Java String literal containing one virtual-collection item as JSON."""
    if not isinstance(item, dict):
        item = {'title': str(item)}
    payload = json.dumps(item, ensure_ascii=False, separators=(',', ':'))
    return '"' + _escape_java_literal(payload) + '"'


def _emit_json_add_collection_items(
        lines, indent, target_java, src_java, sfx):
    """Append a JSON array to an arbitrary Java collection."""
    lines.append(f"{indent}try {{")
    lines.append(
        f"{indent}    org.json.JSONArray _vc_arr_{sfx} = "
        f"new org.json.JSONArray(String.valueOf({src_java}));"
    )
    lines.append(
        f"{indent}    for (int _vc_i_{sfx} = 0; "
        f"_vc_i_{sfx} < _vc_arr_{sfx}.length(); _vc_i_{sfx}++) {{"
    )
    lines.append(
        f"{indent}        Object _vc_item_{sfx} = "
        f"_vc_arr_{sfx}.get(_vc_i_{sfx});"
    )
    lines.append(
        f"{indent}        if (_vc_item_{sfx} instanceof org.json.JSONObject) {{"
    )
    lines.append(
        f"{indent}            {target_java}.add("
        f"((org.json.JSONObject) _vc_item_{sfx}).toString());"
    )
    lines.append(f"{indent}        }} else {{")
    lines.append(
        f"{indent}            org.json.JSONObject _vc_obj_{sfx} = "
        f"new org.json.JSONObject();"
    )
    lines.append(
        f'{indent}            _vc_obj_{sfx}.put("title", '
        f"String.valueOf(_vc_item_{sfx}));"
    )
    lines.append(
        f"{indent}            {target_java}.add(_vc_obj_{sfx}.toString());"
    )
    lines.append(f"{indent}        }}")
    lines.append(f"{indent}    }}")
    lines.append(f"{indent}}} catch (Exception _vc_error_{sfx}) {{ }}")


def _emit_json_set_collection_items(lines, indent, jv, src_java, sfx):
    """Preserve every JSON field when replacing a virtual collection dataset."""
    _emit_json_add_collection_items(
        lines, indent, f"{jv}_items", src_java, sfx
    )


def _fstring_format_spec(format_spec):
    """Devolve a format spec de um FormattedValue como string simples, ou None
    se for dinâmica/ausente (ex.: f"{x:{largura}}")."""
    if format_spec is None:
        return None
    if isinstance(format_spec, ast.JoinedStr):
        if len(format_spec.values) == 1 and isinstance(format_spec.values[0], ast.Constant):
            return format_spec.values[0].value
        return None
    if isinstance(format_spec, ast.Constant):
        return format_spec.value
    return None


def _format_kind(node, val_to_java):
    """1 for a number the source proves, 2 for text, 0 when it does not say."""
    numeric = getattr(val_to_java, 'numeric', None)
    if numeric is not None and numeric(node) is not None:
        return 1
    return 2 if _kind_from(val_to_java, node) == 'text' else 0


def _check_format_spec(node, spec):
    """A spec Python refuses for every kind of value stops the build here."""
    errors = []
    for sample in (0, 0.0, ""):
        try:
            format(sample, spec)
            return
        except (ValueError, TypeError) as exc:
            errors.append(str(exc))
    unsupported.raise_bad_format(node, spec, errors[0])


def _formatted_java(value_java, kind, spec_node, conversion, node, val_to_java):
    """One {value!c:spec}: Python's format() of it (_apkpyFormat)."""
    if conversion == ord('r') and kind == 2:
        value_java, kind = "_apkpyRepr(String.valueOf(%s))" % value_java, 2
    elif conversion in (ord('r'), ord('s'), ord('a')):
        kind = 2 if conversion != ord('r') else kind
    if spec_node is None or (isinstance(spec_node, ast.JoinedStr) and not spec_node.values):
        return "String.valueOf(%s)" % value_java
    literal = _fstring_format_spec(spec_node)
    if isinstance(literal, str):
        _check_format_spec(node, literal)
        spec_java = '"%s"' % _escape_java_literal(literal)
    else:
        # f"{x:{width}}": the spec is itself built when the app runs.
        spec_java = _fstring_node_to_java(spec_node, val_to_java)
    return "_apkpyFormat(String.valueOf(%s), %s, %d)" % (value_java, spec_java, kind)


def _shown_java(val, val_to_java):
    """{xs} of a list, a dict or a tuple the source proves, as str() shows it
    -- or None. Only without a spec: format() of a list with one is an error
    in CPython, and that path already says so."""
    spec = val.format_spec
    if spec is not None and not (isinstance(spec, ast.JoinedStr) and not spec.values):
        return None
    if val.conversion not in (-1, ord('s'), ord('r')):
        return None
    if tuples_feature.is_tuple(val.value):
        return "_apkpyShowTuple(String.valueOf(%s))" % val_to_java(val.value)
    if tuples_feature.holds_tuples(val.value):
        return "_apkpyShowTuples(String.valueOf(%s))" % val_to_java(val.value)
    if _kind_from(val_to_java, val.value) in ('list', 'dict'):
        return "_apkpyShow(String.valueOf(%s))" % val_to_java(val.value)
    return None


def _raw_shown_source(node, val_to_java):
    """The JSON Object behind a value read out of a list or a dict, or None:
    the name of a for over a list, d[k] or xs[i] read the same twice, and
    d.get(k) of names and constants."""
    if isinstance(node, ast.Name) and node.id in _RAW_LOOP_VARS[0]:
        return _RAW_LOOP_VARS[0][node.id]
    item = _item_read(node)
    if item is not None:
        if _kind_from(val_to_java, item[0]) == 'text':
            return None                      # a letter of a text
        return _raw_side_java(node, val_to_java)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr == 'get' and isinstance(node.func.value, ast.Name) \
            and all(isinstance(a, (ast.Name, ast.Constant)) for a in node.args):
        return _raw_item_java(node, val_to_java)
    return None


def _shown_raw_java(node, text_java, val_to_java):
    """str() of a value read out of a list or a dict: a list or a dict in it
    as Python shows it, anything else as *text_java* already says -- or None.

    str(d["a"]) of {"a": ["tea"]}, str(xs[0]) of a list of lists, f"{row}" in
    a for over one: the source does not say the item is a list, so it was
    shown as the JSON it is kept as, ["tea"] for ['tea'], without a word.
    """
    raw = _raw_shown_source(node, val_to_java)
    if raw is None:
        return None
    return "_apkpyStrRaw(%s, %s)" % (raw, text_java)


def _fstring_node_to_java(node, val_to_java):
    """Converte uma f-string (ast.JoinedStr) numa concatenação Java de Strings.

    - Partes literais são escapadas como literal Java (aspas, '\\', newline...).
    - {expr}        → String.valueOf(<expr>)
    - {expr:spec}   → _apkpyFormat: a mini-linguagem de formatação do Python
      inteira (largura, alinhamento, zeros, separadores, f/e/g/%/d/x/b/o/c),
      conferida com format() do CPython em ~48 000 casos. O String.format do
      Java que fazia o {x:.2f} arredondava o texto curto meio-para-cima, e o
      Python arredonda o valor binario exacto meio-para-par: 2.675 dava 2.68
      no telemovel e 2.67 no Previewer.
    - {expr!r} de um texto leva as aspas, como o repr do Python."""
    parts = []
    for val in node.values:
        if isinstance(val, ast.Constant) and isinstance(val.value, str):
            parts.append('"' + _escape_java_literal(val.value) + '"')
        elif isinstance(val, ast.FormattedValue):
            shown = _shown_java(val, val_to_java)
            if shown is not None:
                parts.append(shown)
                continue
            formatted = _formatted_java(
                val_to_java(val.value), _format_kind(val.value, val_to_java),
                val.format_spec, val.conversion, val, val_to_java)
            spec = val.format_spec
            if (spec is None or (isinstance(spec, ast.JoinedStr) and not spec.values)) \
                    and val.conversion in (-1, ord('s'), ord('r')):
                formatted = _shown_raw_java(val.value, formatted, val_to_java) or formatted
            parts.append(formatted)
        else:
            parts.append('""')
    return ' + '.join(parts) if parts else '""'


def _str_format_java(node, val_to_java):
    """"{} {:.2f}".format(a, b) with the template written out -- or None."""
    import string
    template = node.func.value.value
    try:
        pieces = list(string.Formatter().parse(template))
    except ValueError as exc:
        unsupported.raise_bad_format(node, template, str(exc))
    args, kwargs = list(node.args), {kw.arg: kw.value for kw in node.keywords if kw.arg}
    if any(isinstance(a, ast.Starred) for a in args) or any(kw.arg is None for kw in node.keywords):
        return None
    out, auto = [], 0
    for literal, field, spec, conversion in pieces:
        if literal:
            out.append('"%s"' % _escape_java_literal(literal))
        if field is None:
            continue
        if field == '':
            index, auto = auto, auto + 1
            value = args[index] if index < len(args) else None
        elif field.isdigit():
            value = args[int(field)] if int(field) < len(args) else None
        elif field.isidentifier():
            value = kwargs.get(field)
        else:
            unsupported.raise_unsupported(
                node, cause=('"{%s}" reads into the value (an item or an attribute). '
                             'Only {}, {0} and {name} are translated in format().' % field),
                suggestions=['Read it first: name = row["name"], then "{}".format(name).'])
        if value is None:
            unsupported.raise_bad_format(node, template, 'Replacement index %s out of range' % field)
        if spec and '{' in spec:
            unsupported.raise_unsupported(
                node, cause='A format spec built from other fields is not translated in format().',
                suggestions=['Use an f-string: f"{value:{width}}".'])
        spec_node = ast.Constant(value=spec) if spec else None
        out.append(_formatted_java(val_to_java(value), _format_kind(value, val_to_java),
                                   spec_node, ord(conversion) if conversion else -1, node, val_to_java))
    return ' + '.join(out) if out else '""'


_PERCENT = re.compile(r'%(?:\((?P<key>[^)]*)\))?(?P<flags>[-+ #0]*)(?P<width>\*|\d+)?'
                      r'(?:\.(?P<prec>\*|\d+))?(?P<type>[diouxXeEfFgGcrsa%])')


def _percent_java(node, val_to_java):
    """"%.2f %s" % (x, y) with the template written out: each conversion as the
    format spec it stands for. None when it cannot be read that way."""
    template = node.left.value
    values = list(node.right.elts) if isinstance(node.right, ast.Tuple) else [node.right]
    out, pos, used = [], 0, 0
    for m in _PERCENT.finditer(template):
        if m.start() > pos:
            out.append('"%s"' % _escape_java_literal(template[pos:m.start()]))
        pos = m.end()
        kind_char = m.group('type')
        if kind_char == '%':
            out.append('"%"')
            continue
        if m.group('key') is not None or m.group('width') == '*' or m.group('prec') == '*':
            unsupported.raise_unsupported(
                node, cause='"%(name)s" and "*" widths are not translated in % formatting.',
                suggestions=['Use an f-string: f"{name:>10}".'])
        if used >= len(values):
            unsupported.raise_bad_format(node, template, 'not enough arguments for format string')
        value = values[used]
        used += 1
        flags = m.group('flags')
        spec = ''
        if '-' in flags:
            spec += '<'
        if '+' in flags:
            spec += '+'
        elif ' ' in flags:
            spec += ' '
        if '#' in flags:
            spec += '#'
        if '0' in flags and '-' not in flags:
            spec += '0'
        spec += m.group('width') or ''
        if m.group('prec') is not None and kind_char not in 'diucrsa':
            spec += '.' + m.group('prec')
        java = val_to_java(value)
        kind = _format_kind(value, val_to_java)
        if kind_char in 'diu':
            # "%d" % 3.7 is "3": Python takes the whole part.
            java, kind, spec = "_apkpyWholePart(String.valueOf(%s))" % java, 1, spec + 'd'
        elif kind_char in 'rsa':
            if kind_char == 'r' and kind == 2:
                java = "_apkpyRepr(String.valueOf(%s))" % java
            if m.group('prec') is not None:
                spec += '.' + m.group('prec')
            kind = 2
        elif kind_char == 'c':
            java, kind = ("_apkpyChr(Long.parseLong(String.valueOf(%s).trim()))" % java, 2) \
                if kind == 1 else (java, 2)
        else:
            spec += kind_char
            kind = 1
        piece = ("_apkpyFormat(String.valueOf(%s), \"%s\", %d)" % (java, _escape_java_literal(spec), kind)
                 if spec else "String.valueOf(%s)" % java)
        if kind_char in 'sr' and not spec:
            # "%s" % xs and "%s" % d["a"]: a list or a dict as str() shows it,
            # not the JSON it is kept as.
            shown = _shown_java(ast.FormattedValue(value=value, conversion=-1, format_spec=None),
                                val_to_java)
            piece = shown or _shown_raw_java(value, piece, val_to_java) or piece
        out.append(piece)
    if pos < len(template):
        out.append('"%s"' % _escape_java_literal(template[pos:]))
    if used != len(values):
        unsupported.raise_bad_format(node, template, 'not all arguments converted during string formatting')
    return ' + '.join(out) if out else '""'


def _sql_params_java(params_node, val_to_java):
    """
    Converte o nó `[a, b]` de db.execute(sql, [a, b]) numa expressão Java
    `new String[]{String.valueOf(a), String.valueOf(b)}` para bind seguro
    (placeholders `?`). Devolve None se não houver params.
    """
    if isinstance(params_node, ast.List) and params_node.elts:
        args = ", ".join(f"String.valueOf({val_to_java(e)})" for e in params_node.elts)
        return f"new String[]{{{args}}}"
    return None


# datetime.now()/date()/time()/year()/... → padrão SimpleDateFormat equivalente.
# Os padrões batem certo com os strftime do Python usados no previewer (DatetimeAPI):
#   %Y→yyyy  %m→MM  %d→dd  %H→HH  %M→mm  %S→ss   (paridade de formato).
_DATETIME_PATTERNS = {
    'now': 'yyyy-MM-dd HH:mm:ss',
    'date': 'yyyy-MM-dd',
    'time': 'HH:mm:ss',
    'year': 'yyyy', 'month': 'MM', 'day': 'dd',
    'hour': 'HH', 'minute': 'mm', 'second': 'ss',
}


def _datetime_call_to_java(node):
    """Se for `datetime.X()` (X em _DATETIME_PATTERNS), devolve a expressão Java
    (SimpleDateFormat sobre `new Date()`); senão None. Locale.US para os dígitos
    serem sempre os mesmos. Tudo devolve String, como no previewer."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and isinstance(node.func.value, ast.Name) and node.func.value.id == 'datetime' \
            and node.func.attr in _DATETIME_PATTERNS:
        patt = _DATETIME_PATTERNS[node.func.attr]
        return f'new java.text.SimpleDateFormat("{patt}", java.util.Locale.US).format(new java.util.Date())'
    return None


def _popped_item(node):
    """The 'popvalue' of ``x = xs.pop(i)`` / ``x = d.pop(k, default)``, which
    features/item_assignment.py writes as a read of its own (the list is
    changed by the statement after it), or None."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id == item_feature.LISTOP and len(node.args) >= 3 \
            and isinstance(node.args[0], ast.Constant) and node.args[0].value == 'popvalue':
        return node
    return None


# Calls that answer a number whatever they are given (or stop the app), so a
# key worked out by one is compared as a number even when the source does
# not say whether it is a whole one: key=abs on the items of a list.
_ALWAYS_NUMBERS = ('abs', 'round', 'sum')

# Uma resposta de um modelo de linguagem não cabe em 10s, que era o valor
# cravado aqui: o pedido morria antes de a resposta chegar, sempre, e o erro
# que sobrava era um timeout genérico que não dizia porquê.
_HTTPS_CONNECT_TIMEOUT_MS = 15000
_HTTPS_READ_TIMEOUT_MS = 60000
_HTTPS_MAX_TIMEOUT_MS = 600000
_JSON_INT_MAX = 2 ** 31 - 1


def _https_timeout_java(node, val_to_java, default_ms=_HTTPS_READ_TIMEOUT_MS):
    """`timeout=` vem em segundos; o setReadTimeout quer milissegundos."""
    if node is None:
        return str(default_ms)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return str(max(1, min(int(node.value * 1000), _HTTPS_MAX_TIMEOUT_MS)))
    return "_apkpyTimeoutMs(String.valueOf(%s), %d)" % (
        val_to_java(node), default_ms)


def _json_node_to_java(node, val_to_java, struct_vars=()):
    """Um literal Python vira JSON a sério, com os tipos de pé.

    `{"max_tokens": 512}` tem de chegar ao fio como número: uma API que valida
    o que recebe rejeita `"512"`, e o corpo de um pedido só serve para o outro
    lado o ler. Por isso isto percorre o literal em vez de passar pelo modelo
    "tudo é String" que o resto do gerador usa — ints ficam ints, objetos
    aninhados ficam objetos.

    O que não é literal (um nome, uma chamada, uma f-string) é uma String em
    runtime e entra como tal, que é o certo para uma mensagem que o utilizador
    escreveu — e é também o que trata do escape, porque quem serializa é o
    org.json e não uma concatenação nossa. A exceção é um nome que o gerador
    viu receber um dict ou uma lista: esse guarda texto JSON, e volta a entrar
    como estrutura em vez de um bloco entre aspas.
    """
    if isinstance(node, ast.Dict):
        pairs = []
        for k_node, v_node in zip(node.keys, node.values):
            if k_node is None:
                continue  # {**outro} — não há nome por onde lhe pegar
            pairs.append(val_to_java(k_node))
            pairs.append(_json_node_to_java(v_node, val_to_java, struct_vars))
        return "_apkpyJsonObj(%s)" % ", ".join(pairs)

    if isinstance(node, (ast.List, ast.Tuple)):
        return "_apkpyJsonArr(%s)" % ", ".join(
            _json_node_to_java(e, val_to_java, struct_vars) for e in node.elts)

    if isinstance(node, ast.Constant):
        value = node.value
        if value is None:
            return "org.json.JSONObject.NULL"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return val_to_java(node)
        if isinstance(value, int):
            return "%dL" % value if abs(value) > _JSON_INT_MAX else str(value)
        if isinstance(value, float):
            return repr(value)

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        try:
            literal = ast.literal_eval(node)
        except (TypeError, ValueError, SyntaxError):
            literal = None
        if isinstance(literal, bool):
            pass
        elif isinstance(literal, int):
            return "%dL" % literal if abs(literal) > _JSON_INT_MAX else str(literal)
        elif isinstance(literal, float):
            return repr(literal)

    if isinstance(node, ast.Name) and node.id in struct_vars:
        return "_apkpyJsonVal(String.valueOf(%s))" % node.id

    if regex_feature.is_sequence(node):
        return "_apkpyJsonVal(String.valueOf(%s))" % val_to_java(node)

    # [word, len(word)] holds a number and [pair] a list, as in Python: str()
    # shows 3 and not '3', and a request body sends 3. Until 1.14 every value
    # worked out here went in as text.
    numeric = getattr(val_to_java, 'numeric', None)
    known = numeric(node) if numeric is not None else None
    if known is not None:
        return ("Double.valueOf(%s)" if known[1] else "Long.valueOf(%s)") % known[0]
    if _kind_from(val_to_java, node) in ('list', 'dict'):
        return "_apkpyJsonVal(String.valueOf(%s))" % val_to_java(node)
    typed = _typed_json_java(node, val_to_java)
    if typed is not None:
        return typed
    # (r["name"], r["price"]): each item as the JSON it is read from holds it.
    raw = _raw_item_java(node, val_to_java)
    if raw is not None:
        return raw

    return "_apkpyJsonOut(String.valueOf(%s))" % val_to_java(node)


def _https_body_java(node, val_to_java):
    """O corpo de um pedido, já como String pronta a enviar.

    Um literal nunca é null, e repetir a expressão nos dois ramos de um
    ternário construía o objeto JSON duas vezes. Só um nome merece a guarda.
    """
    if node is None:
        return "null"
    body = val_to_java(node)
    if isinstance(node, ast.Name):
        return f"{body} != null ? String.valueOf({body}) : null"
    return f"String.valueOf({body})"


def _track_json_struct(var, val_node, struct_vars, kinds=None, kind_of=None):
    """Regista (ou esquece) um nome que passou a guardar JSON estruturado.

    Esquecer importa tanto como registar: `x = {...}` seguido de `x = "olá"`
    deixa de ser estrutura, e reinjetá-lo como objeto daria um corpo partido.
    *kinds* guarda tambem o que o nome passou a ser (ver _static_kind).
    """
    if isinstance(val_node, (ast.Dict, ast.List, ast.Tuple)) or regex_feature.is_sequence(val_node):
        struct_vars.add(var)
    elif (isinstance(val_node, ast.Call) and isinstance(val_node.func, ast.Name)
          and val_node.func.id in (item_feature.SETITEM, item_feature.DELITEM)
          and val_node.args and isinstance(val_node.args[0], ast.Name)
          and val_node.args[0].id in struct_vars):
        pass
    else:
        struct_vars.discard(var)
    if kinds is not None:
        if regex_feature.is_sequence(val_node):
            kinds[var] = 'list'
        else:
            kind = kind_of(val_node) if kind_of is not None else _static_kind(val_node, kinds)
            kinds[var] = kind or 'other'
