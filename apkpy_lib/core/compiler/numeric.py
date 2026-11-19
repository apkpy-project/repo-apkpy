"""Numbers that stay numbers: an int or a float, and the calls the build refuses."""
import ast

from ..features import native as native_feature
from ..features import item_assignment as item_feature
from ..features import classes as classes_feature
from ..features import sets as sets_feature
from ..features import counters as counters_feature
from ..features import int_keys as int_keys_feature
from .. import unsupported

from .kinds import _body_kinds, _int_literal, _kind_from, _static_kind
from .expressions import _arith_result, _cond_shape_supported, _numberish


def _refuse_call(message, command, cause, suggestions):
    """Stop the build naming the call, instead of writing Java that will not
    compile and letting javac complain about generated code."""
    from ...diagnostics import ApkpyError
    raise ApkpyError(
        message,
        code='U2037',
        title='This call does not match the function',
        cause=cause,
        expected='every parameter filled exactly once',
        received=command.get('name', '') + '(...)',
        suggestions=list(suggestions),
        docs='https://repo-apkpy.pages.dev/compatibility/',
        line=command.get('lineno', 0) or 0,
    )


def _line_up_keywords(transpiler):
    """Put `f(b=2, a=1)` back in the order `f(a, b)` declares.

    The parser kept the positional arguments and threw the keywords away, so
    two parameters were declared and zero were passed. Done here, after the
    whole module is parsed, because a function may be called above the line
    that defines it.
    """
    functions = getattr(transpiler, 'functions', {}) or {}

    bodies = [info.get('cmds') for info in functions.values()]
    bodies.append(getattr(transpiler, 'module_init_cmds', None))

    for body in bodies:
        for command in _function_calls_in(body):
            keywords = command.get('keywords_nodes') or {}
            name = command.get('name')
            if not keywords or name not in functions:
                continue
            if native_feature.function_for(name) is not None:
                continue                       # o on_result= de um bloco native

            parameters = list(functions[name].get('args') or [])
            positional = list(command.get('args_nodes') or [])
            if len(positional) > len(parameters):
                continue                       # nao e este o problema a tratar

            filled = list(positional) + [None] * (len(parameters) - len(positional))
            for key, node in keywords.items():
                if key not in parameters:
                    _refuse_call(
                        '%s() has no parameter called %s.' % (name, key),
                        command,
                        'ApkPy lines a call up with the parameters the function '
                        'declares, and this name is not one of them.',
                        ['Check the spelling against def %s(%s).'
                         % (name, ', '.join(parameters) or '')])
                index = parameters.index(key)
                if index < len(positional):
                    _refuse_call(
                        '%s() was given %s twice.' % (name, key),
                        command,
                        'It arrives once by position and once by name, and '
                        'ApkPy will not choose between them.',
                        ['Pass it either by position or by name, not both.'])
                filled[index] = node

            missing = [parameters[i] for i, node in enumerate(filled) if node is None]
            if missing:
                _refuse_call(
                    '%s() needs %s.' % (name, ', '.join(missing)),
                    command,
                    'ApkPy does not read default values, so every parameter has '
                    'to be given.',
                    ['Pass %s in the call.' % ', '.join(missing)])

            command['args_nodes'] = filled
            command['keywords_nodes'] = {}


def _function_calls_in(cmds):
    """Every `function_call` command under *cmds*, including nested bodies."""
    for command in cmds or []:
        if not isinstance(command, dict):
            continue
        if command.get('type') == 'function_call':
            yield command
        for value in command.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                for inner in _function_calls_in(value):
                    yield inner


def _spread_boolean_first(transpiler, rounds=4):
    """A boolean handed straight to another function stays a boolean.

    Only the callback named in the API call used to be marked. Written as
    ``on_result=lambda ok, value: result(ok, value)`` the lambda was marked and
    ``result`` was not, so its first parameter stayed a String: ``false``
    arrived as the text "false", which is not empty, and ``if ok:`` ran the
    success branch on a cancelled camera. It said nothing, which is the part
    that matters.

    This settles rather than reading once, because a callback may forward to a
    function that forwards again.
    """
    functions = getattr(transpiler, 'functions', {}) or {}
    marked = set(getattr(transpiler, 'boolean_first_arg_callbacks', ()) or ())

    for _ in range(max(1, rounds)):
        grown = set(marked)
        for name in list(marked):
            info = functions.get(name)
            if not info or not info.get('args'):
                continue
            first = info['args'][0]
            for call in _function_calls_in(info.get('cmds')):
                target = call.get('name')
                arguments = call.get('args_nodes') or []
                if (target in functions and arguments
                        and isinstance(arguments[0], ast.Name)
                        and arguments[0].id == first):
                    grown.add(target)
        if grown == marked:
            break
        marked = grown

    transpiler.boolean_first_arg_callbacks = marked


def _numeric_arg_kind(node, numeric_names, returns=None):
    """True for a float, False for an int, None when it is not certainly one.

    Deliberately narrow. Everything this answers for becomes arithmetic in the
    generated Java, and a wrong yes turns a sum into glued text without saying
    so -- the exact failure 1.6.0 and 1.8.0 spent their time removing.
    """
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return None
        if isinstance(node.value, int):
            return False
        if isinstance(node.value, float):
            return True
        return None
    if isinstance(node, ast.Name):
        if node.id in numeric_names:
            return numeric_names[node.id]
        return None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _numeric_arg_kind(node.operand, numeric_names, returns)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Invert):
        return False if _numeric_arg_kind(node.operand, numeric_names, returns) is False else None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == 'float':
            return True
        if node.func.id in ('int', 'len'):
            return False
        if node.func.id == 'pow' and len(node.args) == 3 and all(
                _numeric_arg_kind(arg, numeric_names, returns) is False for arg in node.args):
            return False
        # A function of the app's own whose every return is a number: this is
        # what lets one helper feed another, euros(with_vat(cents)).
        if returns and node.func.id in returns:
            return returns[node.func.id]
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, _ARITH_OPS):
        left = _numeric_arg_kind(node.left, numeric_names, returns)
        right = _numeric_arg_kind(node.right, numeric_names, returns)
        if left is None or right is None:
            return None
        if isinstance(node.op, _BIT_OPS):
            return None if (left or right) else False
        if isinstance(node.op, ast.Div):
            return True                       # Python's / is always a float
        if isinstance(node.op, ast.Pow) and not (left or right):
            exponent = _int_literal(node.right)
            return exponent is not None and exponent < 0    # 2 ** -1 == 0.5
        return bool(left or right)
    if isinstance(node, ast.IfExp):
        # n if n < 2 else fib(n - 1): a number when both sides are the same
        # kind. 1 if c else 2.5 is not claimed: Python keeps the 1 an int,
        # and one Java expression would make it 1.0.
        yes = _numeric_arg_kind(node.body, numeric_names, returns)
        no = _numeric_arg_kind(node.orelse, numeric_names, returns)
        if yes is None or no is None or yes != no or not _cond_shape_supported(node.test):
            return None
        return yes
    return None


# Python's operators on the bits of an int. A float on either side is
# Python's TypeError, so they only translate between two ints.
_BIT_OPS = (ast.BitAnd, ast.BitOr, ast.BitXor, ast.LShift, ast.RShift)

# The arithmetic ApkPy translates between two numbers. The bit operators used
# to be left out, and `n & 3` or `x <<= 2` came back as "" with no word.
_ARITH_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.FloorDiv, ast.Pow) + _BIT_OPS


def _int_call_java(node, numeric, val_to_java):
    """``int(x)`` as a Java long, with Python's answer for each kind of x.

    - text: parsed, after the spaces Python ignores (``int(" 42 ")`` is 42 and
      Long.parseLong rejected it);
    - a decimal: cut towards zero, as Python does. ``int(float(price) * 2)``
      used to read "5.0" back as an int and stop;
    - an int: itself.

    ``int(text, base)`` reads the text in that base. Text that is not a
    whole number is Python's ValueError, message and all (ApkpyValues.toInt).
    """
    if not node.args:
        return "0L"
    arg = node.args[0]
    if len(node.args) == 1:
        known = numeric(arg)
        if known is not None:
            return f"_apkpyTrunc({known[0]})" if known[1] else f"((long)({known[0]}))"
    text = f"String.valueOf({val_to_java(arg)})"
    if getattr(node, classes_feature.READ_BACK, False):
        return f"Long.parseLong({text}.trim())"      # a field's own number
    if len(node.args) == 1 and (_numberish(arg, numeric) or _arith_result(arg)):
        # int(sum(prices)), int(a - b), int(row["price"] * row["qty"]): a
        # number in Python, so 6.75 is cut to 6. Read as text it was
        # int("6.75"), Python's ValueError.
        return f"_apkpyIntOfNumber({text})"
    if len(node.args) > 1:
        base = f"ApkpyValues.toInt(String.valueOf({val_to_java(node.args[1])}), 10)"
        return f"ApkpyValues.toInt({text}, {base})"
    return f"ApkpyValues.toInt({text}, 10)"


def _float_call_java(node, numeric, val_to_java):
    """``float(x)`` as a Java double: a number converted, text read as
    Python reads it (ApkpyValues.toFloat)."""
    if not node.args:
        return "0d"
    known = numeric(node.args[0])
    if known is not None:
        return f"((double)({known[0]}))"
    if getattr(node, classes_feature.READ_BACK, False):
        return f"Double.parseDouble(String.valueOf({val_to_java(node.args[0])}))"
    return f"ApkpyValues.toFloat(String.valueOf({val_to_java(node.args[0])}))"


def _bool_operand(node):
    """True or False written out as an operand of arithmetic: 1 and 0, as in
    Python, where a bool is an int. ``True + True`` was written as Java's
    ``true + true``, which javac refuses. Only here: ``flag = True`` alone
    stays the app's True."""
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return ("1L" if node.value else "0L", False)
    return None


def _arith_java(op, left, right, right_node=None):
    """Python arithmetic between two numbers, written as Java with Python's answers.

    *left* and *right* are the (java, is_float) pairs of _numeric_java_expr;
    the result is another one. Java's operators disagree with Python's in
    ways nothing on the screen announces, and each one below is a place where
    the phone used to show a different number from the Previewer:

    - ``//`` and ``**`` had no translation and gave an empty value.
    - ``%`` and ``//`` round towards minus infinity in Python and towards zero
      in Java: ``-7 % 3`` is 2 in one and -1 in the other.
    - a zero divisor stops Python with ZeroDivisionError; Java's ``/`` between
      doubles gave Infinity or NaN and carried on.
    - an int outgrowing 32 bits wrapped round to a negative number. Python's
      ints do not overflow; here the sum is done in 64 bits with
      Math.addExact and friends, which stop rather than wrap.

    ``int ** int`` is an int, as in Python, unless the exponent is a negative
    number written out (``2 ** -1`` is 0.5). An exponent that only turns out
    negative while the app runs stops with a message, because the type of the
    answer would depend on it.
    """
    le, lf = left
    re_, rf = right
    decimal = bool(lf or rf)
    if isinstance(op, _BIT_OPS):
        # Python's TypeError between a float and an int: not a number here,
        # so the caller stops the build with the untranslated-arithmetic
        # message. Java's << would wrap at 64 bits and mask the count; the
        # helpers stop or answer as Python does.
        if decimal:
            return None
        if isinstance(op, ast.LShift):
            return (f"_apkpyShiftL((long)({le}), (long)({re_}))", False)
        if isinstance(op, ast.RShift):
            return (f"_apkpyShiftR((long)({le}), (long)({re_}))", False)
        symbol = {ast.BitAnd: '&', ast.BitOr: '|', ast.BitXor: '^'}[type(op)]
        return (f"((long)({le}) {symbol} (long)({re_}))", False)
    if isinstance(op, ast.Div):
        return (f"_apkpyDiv((double)({le}), (double)({re_}))", True)
    if isinstance(op, ast.Pow):
        exponent = _int_literal(right_node) if right_node is not None else None
        if decimal or (exponent is not None and exponent < 0):
            return (f"_apkpyPowF((double)({le}), (double)({re_}))", True)
        return (f"_apkpyPowL((long)({le}), (long)({re_}))", False)
    if decimal:
        if isinstance(op, ast.Mod):
            return (f"_apkpyModF((double)({le}), (double)({re_}))", True)
        if isinstance(op, ast.FloorDiv):
            return (f"_apkpyFloorDivF((double)({le}), (double)({re_}))", True)
        symbol = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*'}[type(op)]
        return (f"({le} {symbol} {re_})", True)
    if isinstance(op, ast.Mod):
        return (f"Math.floorMod((long)({le}), (long)({re_}))", False)
    if isinstance(op, ast.FloorDiv):
        return (f"Math.floorDiv((long)({le}), (long)({re_}))", False)
    exact = {ast.Add: 'addExact', ast.Sub: 'subtractExact', ast.Mult: 'multiplyExact'}[type(op)]
    return (f"Math.{exact}((long)({le}), (long)({re_}))", False)


def _numeric_params(call_sites, arg_names):
    """The parameters every recorded call fills with a number.

    One call that passes something else, one call with a keyword argument, or
    no calls at all, and nothing is claimed: the parameter stays text.
    """
    call_sites = call_sites or []
    usable = [c for c in call_sites if c is not None
              and len(c) == len(arg_names)]
    if not usable or len(usable) != len(call_sites):
        return {}
    numeric = {}
    for index, arg in enumerate(arg_names):
        kinds = [call[index] for call in usable]
        if any(kind is None for kind in kinds):
            continue
        numeric[arg] = any(kinds)      # float wins over int
    return numeric


class _Unstar(ast.NodeTransformer):
    """[*a, b, *c] as list(a) + [b] + list(c); a tuple and a set the same,
    inside tuple() and set().

    No generator knew a starred item in a list written out: [*q] showed
    [''], (*xs, 3) ('', 3), with no word. {**d, "b": 2} lost d the same way,
    and stops the build.
    """

    def _joined(self, elts, like):
        parts, run = [], []
        for e in elts:
            if isinstance(e, ast.Starred):
                if run:
                    parts.append(ast.List(elts=run, ctx=ast.Load()))
                    run = []
                parts.append(ast.Call(func=ast.Name(id='list', ctx=ast.Load()),
                                      args=[e.value], keywords=[]))
            else:
                run.append(e)
        if run:
            parts.append(ast.List(elts=run, ctx=ast.Load()))
        value = parts[0]
        for part in parts[1:]:
            value = ast.BinOp(left=value, op=ast.Add(), right=part)
        return ast.fix_missing_locations(ast.copy_location(value, like))

    def _starred(self, node):
        return isinstance(getattr(node, 'ctx', ast.Load()), ast.Load) \
            and any(isinstance(e, ast.Starred) for e in node.elts)

    def _wrapped(self, name, node):
        call = ast.Call(func=ast.Name(id=name, ctx=ast.Load()),
                        args=[self._joined(node.elts, node)], keywords=[])
        return ast.fix_missing_locations(ast.copy_location(call, node))

    def visit_List(self, node):
        node = self.generic_visit(node)
        return self._joined(node.elts, node) if self._starred(node) else node

    def visit_Tuple(self, node):
        node = self.generic_visit(node)
        return self._wrapped('tuple', node) if self._starred(node) else node

    def visit_Set(self, node):
        node = self.generic_visit(node)
        return self._wrapped('set', node) if self._starred(node) else node

    def visit_Call(self, node):
        node = self.generic_visit(node)
        # dict() and dict(a=1, b=2): the dict they make, written out.
        if isinstance(node.func, ast.Name) and node.func.id == 'dict' and not node.args \
                and all(k.arg is not None for k in node.keywords):
            made = ast.Dict(keys=[ast.Constant(value=k.arg) for k in node.keywords],
                            values=[k.value for k in node.keywords])
            return ast.fix_missing_locations(ast.copy_location(made, node))
        return node

    def visit_Dict(self, node):
        if any(k is None for k in node.keys):
            unsupported.raise_unsupported(
                node, cause='{**d} is not translated yet: no generator knew it, and the '
                            'dict it came from was lost.',
                suggestions=['Copy it and add to the copy: e = dict(d), then e["b"] = 2.'])
        return self.generic_visit(node)


def _dict_copy_call(node, val_to_java):
    """dict(d) of a value the source says is a dict."""
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
        and node.func.id == 'dict' and len(node.args) == 1 and not node.keywords \
        and not isinstance(node.args[0], ast.Starred) \
        and _kind_from(val_to_java, node.args[0]) == 'dict'


_KEYS_READ_BY = ('list', 'sorted', 'tuple', 'set', 'max', 'min', 'sum', 'enumerate', 'zip',
                 'str', 'repr', 'print', 'toast')


def _lists_numbers(node):
    """A list or a tuple written out with a number among its items."""
    return isinstance(node, (ast.List, ast.Tuple)) and any(
        isinstance(e, ast.Constant) and isinstance(e.value, (int, float))
        and not isinstance(e.value, bool) for e in node.elts)


def _lists_whole_numbers(node):
    """A list or a tuple written out, every item of it a whole number."""
    return isinstance(node, (ast.List, ast.Tuple)) and bool(node.elts) and all(
        isinstance(e, ast.Constant) and isinstance(e.value, int)
        and not isinstance(e.value, bool) for e in node.elts)


def _refuse_number_keys_read_back(tree):
    """A dict the source shows has number keys, where its keys are read back.

    On the phone the keys of a dict are kept as text, the JSON way: {1: 'a'}
    is {"1": "a"}. d[1], 1 in d and d.get(1) find it, as the key they look
    for is written the same way; what reads the keys back gets the text, and
    said nothing: str(d) showed {'1': 'a'}, list(d) ['1'], sorted(d) put
    '10' before '9', Counter([1, 2, 1]).most_common() [('1', 2), ...].

    A dict every key of which is a whole number, wherever it is given one,
    is read back with its keys as numbers (features/int_keys.py, 1.15.1).
    Any other stops the build where its keys are read back.
    """
    int_keys_feature.reset()
    numbers = _numeric_body_names(tree)
    scopes = [(None, list(getattr(tree, 'body', [])))]
    scopes += [(fn, fn.body) for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef)]

    def own_nodes(statements):
        stack = list(statements)
        while stack:
            node = stack.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            yield node
            stack.extend(ast.iter_child_nodes(node))

    module_dicts, module_known_dicts = {}, set()
    module_lists = []
    contexts = []
    tupled = set()
    for fn, statements in scopes:
        nodes = list(own_nodes(statements))
        local = dict(numbers)
        if fn is not None:
            local.update(_local_numeric_names(fn, numbers))
        # for i in range(n), for i, x in enumerate(xs): whole numbers.
        counted = set()
        # xs = [3, 1, 2] here or at the top of the file: for x in xs, and
        # {x: x * 2 for x in xs}, give the dict number keys too.
        listed = {name for name, value in module_lists if fn is not None}
        for node in nodes:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name) \
                    and _lists_numbers(node.value):
                listed.add(node.targets[0].id)
        if fn is None:
            module_lists = [(node.targets[0].id, node.value) for node in nodes
                            if isinstance(node, ast.Assign) and len(node.targets) == 1
                            and isinstance(node.targets[0], ast.Name)
                            and _lists_numbers(node.value)]
        for node in nodes:
            if isinstance(node, (ast.For, ast.comprehension)) and isinstance(node.target, ast.Name) \
                    and (_lists_numbers(node.iter)
                         or isinstance(node.iter, ast.Name) and node.iter.id in listed):
                counted.add(node.target.id)
            if isinstance(node, (ast.For, ast.comprehension)) and isinstance(node.iter, ast.Call) \
                    and isinstance(node.iter.func, ast.Name):
                if node.iter.func.id == 'range' and isinstance(node.target, ast.Name):
                    counted.add(node.target.id)
                elif node.iter.func.id == 'enumerate' and isinstance(node.target, ast.Tuple) \
                        and node.target.elts and isinstance(node.target.elts[0], ast.Name):
                    counted.add(node.target.elts[0].id)
        # The loop names that are certainly whole numbers: range(), the count
        # of enumerate(), and a list of whole numbers written out.
        whole_lists = {name for name, value in module_lists
                       if fn is not None and _lists_whole_numbers(value)}
        for node in nodes:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name) \
                    and _lists_whole_numbers(node.value):
                whole_lists.add(node.targets[0].id)
        whole = set()
        for node in nodes:
            if not isinstance(node, (ast.For, ast.comprehension)):
                continue
            it = node.iter
            if isinstance(node.target, ast.Name) and (
                    _lists_whole_numbers(it) or isinstance(it, ast.Name) and it.id in whole_lists
                    or isinstance(it, ast.Call) and isinstance(it.func, ast.Name)
                    and it.func.id == 'range'):
                whole.add(node.target.id)
            elif isinstance(it, ast.Call) and isinstance(it.func, ast.Name) \
                    and it.func.id == 'enumerate' and isinstance(node.target, ast.Tuple) \
                    and node.target.elts and isinstance(node.target.elts[0], ast.Name):
                whole.add(node.target.elts[0].id)

        def whole_number(node, whole=whole, local=local):
            if isinstance(node, ast.Constant):
                return isinstance(node.value, int) and not isinstance(node.value, bool)
            if isinstance(node, ast.Name) and node.id in whole:
                return True
            return _numeric_arg_kind(node, local) is False

        def number(node, counted=counted, local=local):
            if isinstance(node, ast.Constant):
                return not isinstance(node.value, str)
            if isinstance(node, ast.Name) and node.id in counted:
                return True
            return _numeric_arg_kind(node, local) is not None

        def numbers_listed(node):
            if isinstance(node, (ast.List, ast.Tuple)):
                return any(number(e) for e in node.elts)
            return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'range'

        found = dict(module_dicts) if fn is not None else {}
        # The names that hold a dict here: d[0] = 5 on a tuple or a list is
        # not a key.
        dicts = set(module_known_dicts) if fn is not None else set()
        for node in nodes:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name) \
                    and (isinstance(node.value, (ast.Dict, ast.DictComp))
                         or counters_feature.op_of(node.value) in counters_feature.DICT_RESULTS
                         or isinstance(node.value, ast.Call)
                         and isinstance(node.value.func, ast.Name)
                         and node.value.func.id == 'dict'):
                dicts.add(node.targets[0].id)
        for node in nodes:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name):
                value, name = node.value, node.targets[0].id
                if isinstance(value, ast.Dict) and any(k is not None and number(k)
                                                       for k in value.keys):
                    found[name] = node
                elif isinstance(value, ast.Dict) and any(isinstance(k, ast.Tuple)
                                                         for k in value.keys):
                    # {(1, 2): 'a'} is kept as {"[1,2]": "a"}: str(d) showed
                    # {'[1,2]': 'a'}.
                    found[name] = node
                    tupled.add(name)
                elif isinstance(value, ast.DictComp) and number(value.key):
                    found[name] = node
                elif counters_feature.op_of(value) == 'of' and value.args \
                        and numbers_listed(value.args[0]):
                    found[name] = node
            target = node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                else node.target if isinstance(node, ast.AugAssign) else None
            if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) \
                    and target.value.id in dicts:
                key = target.slice.value if hasattr(ast, 'Index') and isinstance(
                    target.slice, getattr(ast, 'Index')) else target.slice
                if not isinstance(key, ast.Slice) and number(key):
                    found.setdefault(target.value.id, node)
                elif isinstance(key, ast.Tuple):
                    found.setdefault(target.value.id, node)
                    tupled.add(target.value.id)
        if fn is None:
            module_dicts = found
            module_known_dicts = dicts
        contexts.append((fn, nodes, number, whole_number, found))

    # A dict that is ever given a key that is not certainly a whole number,
    # or is filled another way, keeps the refusal; the others are read back
    # with their keys as numbers (features/int_keys.py).
    mixed = _not_whole_keyed(contexts) | tupled
    for fn, nodes, number, whole_number, found in contexts:

        def held(node):
            return isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) \
                and node.id in found

        def literal_keys(node):
            # {1: "a"}, {i: i * i for i in range(n)} read back where they are.
            if isinstance(node, ast.Dict):
                return any(k is not None and number(k) for k in node.keys)
            return isinstance(node, ast.DictComp) and number(node.key)

        def keys_of(node):
            """(name, line) of the dict whose keys *node* reads back, or None."""
            if held(node):
                return node.id, found[node.id].lineno
            if literal_keys(node):
                return 'this dict', node.lineno
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in ('keys', 'items') and not node.args:
                return keys_of(node.func.value)
            return None

        for node in nodes:
            read = None
            if isinstance(node, (ast.For, ast.comprehension)):
                read = keys_of(node.iter)
            elif isinstance(node, ast.FormattedValue):
                read = keys_of(node.value)
            elif isinstance(node, ast.Call):
                func = node.func
                shows = isinstance(func, ast.Name) and func.id in _KEYS_READ_BY or (
                    isinstance(func, ast.Attribute) and func.attr in ('set_value', 'join'))
                internal = counters_feature.op_of(node) in ('most_common', 'show', 'default_show')
                if (shows or internal) and node.args:
                    read = keys_of(node.args[0])
            if read is None:
                continue
            name, line = read
            if name != 'this dict' and name not in mixed and _rewrite_whole_keys(node):
                continue
            op = counters_feature.op_of(node)
            if op is not None:
                # As written: c.most_common(1), str(c).
                shown = ast.Call(func=ast.Attribute(value=node.args[0], attr='most_common',
                                                    ctx=ast.Load()),
                                 args=node.args[1:], keywords=[]) if op == 'most_common' \
                    else ast.Call(func=ast.Name(id='str', ctx=ast.Load()), args=node.args[:1],
                                  keywords=[])
                node = ast.copy_location(shown, node)
            if name in tupled:
                unsupported.raise_unsupported(
                    node, cause='%s has tuples for keys (line %d). On the phone a tuple key is '
                                "kept as text, (1, 2) as '[1,2]', so reading the keys back "
                                "gives the text: str(d) would show {'[1,2]': ...}. Looking a "
                                'key up -- d[(1, 2)], (1, 2) in d -- works.' % (name, line),
                    suggestions=['Keep the pairs in a list instead: rows.append([1, 2, value]).'])
            unsupported.raise_unsupported(
                node, cause='%s has numbers for keys (line %d). On the phone the keys of a '
                            'dict are kept as text, the JSON way, so reading them back gives '
                            "'1' where Python gives 1: str(d) would show {'1': ...} and "
                            "sorted(d) put '10' before '9'. Looking a key up -- d[1], "
                            '1 in d, d.get(1) -- works.' % ('This dict' if name == 'this dict' else name, line),
                suggestions=['Use text keys: d[str(n)] = ..., and int(k) where you read '
                             'them back.',
                             'Or keep the numbers in a list of pairs: rows.append([n, value]).'])


def _rewrite_whole_keys(node):
    """A read of a whole-number-keyed dict's keys, rewritten in place: False
    when it is a shape features/int_keys.py does not write."""
    if isinstance(node, ast.For):
        return int_keys_feature.rewrite_for(node)
    if isinstance(node, ast.comprehension):
        return int_keys_feature.rewrite_comprehension(node)
    if isinstance(node, ast.FormattedValue):
        return int_keys_feature.rewrite_formatted(node)
    if isinstance(node, ast.Call) and counters_feature.op_of(node) is None:
        return int_keys_feature.rewrite_call(node)
    return False


def _not_whole_keyed(contexts):
    """The names that may hold a dict with a key that is not a whole number:
    given one anywhere, filled another way, or bound some other way."""
    mixed = set()

    def names_in(target):
        return [sub.id for sub in ast.walk(target) if isinstance(sub, ast.Name)]

    for fn, nodes, number, whole_number, found in contexts:
        if fn is not None:
            args = fn.args
            mixed.update(a.arg for a in (list(getattr(args, 'posonlyargs', [])) + list(args.args)
                                         + list(args.kwonlyargs)
                                         + [a for a in (args.vararg, args.kwarg) if a]))
        for node in nodes:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                value = node.value
                for target in targets:
                    if isinstance(target, ast.Name):
                        if isinstance(value, ast.Dict):
                            if len(targets) != 1 or any(
                                    k is None or not whole_number(k) for k in value.keys):
                                mixed.add(target.id)
                        elif isinstance(value, ast.DictComp):
                            if not whole_number(value.key):
                                mixed.add(target.id)
                        else:
                            mixed.add(target.id)
                    elif not isinstance(target, (ast.Subscript, ast.Attribute)):
                        mixed.update(names_in(target))
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
                        key = target.slice.value if hasattr(ast, 'Index') and isinstance(
                            target.slice, getattr(ast, 'Index')) else target.slice
                        if isinstance(key, ast.Slice) or not whole_number(key):
                            mixed.add(target.value.id)
                    elif isinstance(node, ast.AugAssign) and isinstance(target, ast.Name):
                        mixed.add(target.id)
            elif isinstance(node, (ast.For, ast.comprehension)):
                mixed.update(names_in(node.target))
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    if item.optional_vars is not None:
                        mixed.update(names_in(item.optional_vars))
            elif isinstance(node, ast.ExceptHandler) and node.name:
                mixed.add(node.name)
            elif isinstance(node, getattr(ast, 'NamedExpr', ())):
                mixed.add(node.target.id)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and isinstance(node.func.value, ast.Name):
                attr, owner = node.func.attr, node.func.value.id
                if attr == 'setdefault':
                    if not node.args or not whole_number(node.args[0]):
                        mixed.add(owner)
                elif attr in ('update', 'fromkeys', '__setitem__', '__ior__'):
                    mixed.add(owner)
    return mixed


def _refuse_matmul(tree):
    """a @ b went out as "" with no word: no generator knew the operator."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.BinOp, ast.AugAssign)) and isinstance(node.op, ast.MatMult):
            unsupported.raise_unsupported(
                node, cause='The @ operator is not translated. Python gives it no meaning '
                            'of its own for numbers, text, lists or dicts: a class says what '
                            'it means with __matmul__, and that is not translated either.',
                suggestions=['Write the sum out with a for loop, or call a function: '
                             'dot(a, b).'])


def _held_use(fn, name):
    """Where *fn* puts its parameter *name* inside a list, a tuple, a set or a
    dict (or into JSON), or None."""
    def it(node):
        return isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load)

    for node in ast.walk(fn):
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)) and any(it(e) for e in node.elts):
            return node
        if isinstance(node, ast.Dict) and any(it(e) for e in list(node.keys) + node.values
                                              if e is not None):
            return node
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in ('append', 'add', 'insert',
                                                              'setdefault', 'dumps', 'dump') \
                and any(it(a) for a in node.args):
            return node
        if isinstance(func, ast.Name) and (
                func.id in (item_feature.SETITEM, item_feature.LISTOP)
                or func.id.startswith(sets_feature.PREFIX)) \
                and any(it(a) for a in node.args[1:]):
            return node
    return None


def _refuse_mixed_params(tree):
    """A parameter one call gives a number and another text, put in a list.

    Values cross into a function as text, and the calls say what a parameter
    holds (prescan_numeric_args, _param_kinds). made(2) and made("2") both
    hand over "2"; in a list Python keeps 2 and '2', and the phone would keep
    whichever the function was written for: [n] showed ['2'] for made(2). A
    function given both kinds, that puts the value where its kind shows,
    stops the build.
    """
    defs = {n.name: n for n in getattr(tree, 'body', []) if isinstance(n, ast.FunctionDef)}
    if not defs:
        return
    numbers = _numeric_body_names(tree)
    owner_of = {}
    for fn in defs.values():
        for sub in ast.walk(fn):
            owner_of[id(sub)] = fn
    local_numbers, local_kinds = {}, {}
    seen = {}
    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id in defs):
            continue
        fn = defs[call.func.id]
        params = [a.arg for a in fn.args.args]
        owner = owner_of.get(id(call))
        scope = dict(numbers)
        kinds = None
        if owner is not None:
            if owner.name not in local_numbers:
                local_numbers[owner.name] = _local_numeric_names(owner, numbers)
                local_kinds[owner.name] = _body_kinds(owner)[0]
            scope.update(local_numbers[owner.name])
            kinds = local_kinds[owner.name]
        filled = list(zip(params, call.args))
        filled += [(k.arg, k.value) for k in call.keywords if k.arg in params]
        for param, arg in filled:
            if isinstance(arg, ast.Starred):
                break
            if _numeric_arg_kind(arg, scope) is not None:
                kind = 'a number'
            elif _static_kind(arg, kinds) == 'text':
                kind = 'text'
            else:
                continue
            seen.setdefault((fn.name, param), {}).setdefault(kind, arg)
    for (name, param), found in seen.items():
        if len(found) < 2:
            continue
        use = _held_use(defs[name], param)
        if use is None:
            continue
        number, text = found['a number'], found['text']
        unsupported.raise_unsupported(
            use, cause='%s() is given a number as %s (line %d) and text (line %d), and '
                       'puts %s here. A value goes into a function as text, so on the '
                       'phone %s(2) and %s("2") hand over the same "2", and here '
                       'Python keeps 2 and \'2\' apart.'
                       % (name, param, number.lineno, text.lineno, param, name, name),
            suggestions=['Give it one kind: %s(str(x)) where it takes a number, or '
                         'int(x) where it takes text.' % name,
                         'Or write two functions, one for each kind.'])


def _local_numeric_names(fn, known, returns=None):
    """Names *fn* gives a value itself, and only ever a number.

    _numeric_body_names reads the whole source as one scope, so the n of
    `def made(n)` made the n of another function's `n = len(text)` text too,
    and made(n) passed made a parameter of no known kind: [n, 1] showed
    ['2', 1]. Here the function's own scope is read: a nested function, a
    lambda and a class have their own, and a name one of them declares
    nonlocal or global, or this function declares global, is left out.
    """
    own, skip, inner = [], set(), set()
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            for sub in ast.walk(node):
                if isinstance(sub, (ast.Nonlocal, ast.Global)):
                    inner.update(sub.names)
                elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    inner.add(sub.name)
            continue
        own.append(node)
        stack.extend(ast.iter_child_nodes(node))
    declared = {n for node in own if isinstance(node, ast.Global) for n in node.names}
    args = fn.args
    params = {a.arg for a in list(getattr(args, 'posonlyargs', [])) + args.args + args.kwonlyargs}
    params.update(a.arg for a in (args.vararg, args.kwarg) if a is not None)
    found = {}
    for _ in range(3):
        scope = dict(known)
        scope.update(found)
        kinds, rejected, skip = {}, set(), set()
        for node in own:
            if isinstance(node, ast.Assign) and all(isinstance(t, ast.Name) for t in node.targets):
                kind = _numeric_arg_kind(node.value, scope, returns)
                for target in node.targets:
                    skip.add(id(target))
                    if kind is None:
                        rejected.add(target.id)
                    else:
                        kinds[target.id] = kinds.get(target.id, False) or kind
        for node in own:
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) \
                    and id(node) not in skip:
                rejected.add(node.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                rejected.update((a.asname or a.name).split('.')[0] for a in node.names)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                rejected.add(node.name)
        fresh = {n: k for n, k in kinds.items()
                 if n not in rejected and n not in params and n not in declared and n not in inner}
        if fresh == found:
            break
        found = fresh
    return found


def _numeric_body_names(tree, rounds=3):
    """Names the module only ever binds to a number.

    A name is kept only if every binding of it anywhere in the source is a
    number: one `total = "sold out"` in any branch and the name is text again.
    Scopes are not separated, because a name that means a number here and text
    there is exactly the case worth refusing to guess about.
    """
    known = {}
    for _ in range(max(1, rounds)):
        kinds, rejected = {}, set()

        def _reject(target):
            for sub in ast.walk(target):
                if isinstance(sub, ast.Name):
                    rejected.add(sub.id)

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                kind = _numeric_arg_kind(node.value, known)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if kind is None:
                            rejected.add(target.id)
                        else:
                            kinds[target.id] = kinds.get(target.id, False) or kind
                    else:
                        _reject(target)
            elif isinstance(node, (ast.AugAssign, ast.For, ast.comprehension)):
                target = getattr(node, 'target', None)
                if target is not None:
                    _reject(target)
            elif isinstance(node, (ast.FunctionDef, ast.Lambda)):
                for arg in list(node.args.args) + list(node.args.kwonlyargs):
                    # A function moved out of another gets the outer names it
                    # reads as parameters (features/nested_functions.py), and
                    # every call passes that same name: still one value.
                    if not getattr(arg, '_apkpy_captured', False):
                        rejected.add(arg.arg)

        found = {n: k for n, k in kinds.items() if n not in rejected}
        if found == known:
            break
        known = found
    return known
