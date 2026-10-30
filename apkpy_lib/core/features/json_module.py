# -*- coding: utf-8 -*-
"""import json: json.loads() and json.dumps(), and what is refused around them.

The compiler translates the two calls (_json_module_java): loads() with a
parser that reads what CPython's reads and stops with the same message
(json.JSONDecodeError, a ValueError), dumps() with CPython's separators,
indent=, sort_keys=, ensure_ascii=, separators= and allow_nan=.

This pass, before that:
- gives every other spelling one name: ``import json as j`` and
  ``from json import loads, dumps, JSONDecodeError`` become json.loads,
  json.dumps and json.JSONDecodeError;
- works a call with arguments written out in the source out now, with
  CPython's own json: ``CONFIG = json.loads('{"theme": "dark"}')`` is the
  dict itself, at the top of the file too, and ``json.dumps([1, 2.0])`` the
  text "[1, 2.0]";
- refuses a call at the top of the file it could not work out (a text only
  known while the app runs, or one that raises): the Java has nowhere to run it;
- refuses, with U2033, json.load() and json.dump() (they read and write a file
  object, and open() is not translated: files.read() and files.write() with
  loads() and dumps() do the same), the other names of the module, and the
  keywords that hand over a function (default=, cls=, object_hook=, ...).

STATE['used'] says whether a call is left for the compiler, which then writes
the Java helpers into the app.
"""

import ast
import json
import math

STATE = {'used': False}

_CALLS = ('loads', 'dumps')
_DUMPS_KEYWORDS = ('indent', 'sort_keys', 'ensure_ascii', 'separators', 'allow_nan')
_INT_LIMIT = 2 ** 63


def _loc(node, like):
    return ast.copy_location(node, like)


def _refuse(node, cause, tip):
    from ..unsupported import raise_unsupported
    raise_unsupported(node, cause=cause, suggestions=[tip])


def _aliases(tree):
    """{name in the source: name in json} -- 'json' for the module itself."""
    names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'json':
                    names[alias.asname or 'json'] = 'json'
        elif isinstance(node, ast.ImportFrom) and node.module == 'json' and not node.level:
            for alias in node.names:
                if alias.name == '*':
                    _refuse(node, 'from json import * hides which names come from json.',
                            'import json, then json.loads(...) and json.dumps(...).')
                names[alias.asname or alias.name] = alias.name
    return names


class _Spell(ast.NodeTransformer):
    """j.loads -> json.loads, loads -> json.loads (from json import loads)."""

    def __init__(self, names):
        self.modules = {k for k, v in names.items() if v == 'json' and k != 'json'}
        self.members = {k: v for k, v in names.items() if v != 'json'}

    def visit_Attribute(self, node):
        self.generic_visit(node)
        if isinstance(node.value, ast.Name) and node.value.id in self.modules:
            node.value = _loc(ast.Name(id='json', ctx=ast.Load()), node.value)
        return node

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.members:
            return _loc(ast.Attribute(value=_loc(ast.Name(id='json', ctx=ast.Load()), node),
                                      attr=self.members[node.id], ctx=ast.Load()), node)
        return node


def _is_json(node, attr=None):
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
        and node.value.id == 'json' and (attr is None or node.attr == attr)


def _literal(node):
    """(True, value) for a value written out in the source; (False, None) otherwise."""
    try:
        return True, ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return False, None


def _plain(value):
    """Whether a value from json.loads can be written back as a literal ApkPy reads."""
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, int):
        return -_INT_LIMIT <= value < _INT_LIMIT
    if isinstance(value, list):
        return all(_plain(v) for v in value)
    if isinstance(value, dict):
        return all(_plain(v) for v in value.values())
    return False


def _as_node(value, like):
    """A Python value from json.loads, as the literal that writes it."""
    if isinstance(value, dict):
        return _loc(ast.Dict(keys=[_loc(ast.Constant(value=k), like) for k in value],
                             values=[_as_node(v, like) for v in value.values()]), like)
    if isinstance(value, list):
        return _loc(ast.List(elts=[_as_node(v, like) for v in value], ctx=ast.Load()), like)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value < 0:
        return _loc(ast.UnaryOp(op=ast.USub(), operand=_loc(ast.Constant(value=-value), like)),
                    like)
    return _loc(ast.Constant(value=value), like)


class _Calls(ast.NodeTransformer):
    def visit_Call(self, node):
        self.generic_visit(node)
        if not _is_json(node.func):
            return node
        name = node.func.attr
        if name in ('load', 'dump'):
            other = 'loads' if name == 'load' else 'dumps'
            tip = ('data = json.loads(files.read("data.json"))' if name == 'load'
                   else 'files.write("data.json", json.dumps(data))')
            _refuse(node, 'json.%s() works on a file object, and open() is not translated. '
                          'json.%s() does the same with text, and files keeps the text.'
                    % (name, other), tip)
        if name not in _CALLS:
            _refuse(node, 'json.%s is not translated. ApkPy translates json.loads() and '
                          'json.dumps().' % name,
                    'text = json.dumps(data), then data = json.loads(text).')
        if len(node.args) != 1 or any(isinstance(a, ast.Starred) for a in node.args) \
                or any(kw.arg is None for kw in node.keywords):
            _refuse(node, 'json.%s() takes the value as its one argument.' % name,
                    'json.%s(value)' % name)
        allowed = _DUMPS_KEYWORDS if name == 'dumps' else ()
        for kw in node.keywords:
            if kw.arg not in allowed:
                hands_a_function = kw.arg in ('default', 'cls', 'object_hook', 'object_pairs_hook',
                                              'parse_float', 'parse_int', 'parse_constant')
                _refuse(node, 'json.%s(%s=...) is not translated%s. json.dumps() takes indent=, '
                              'sort_keys=, ensure_ascii=, separators= and allow_nan=; '
                              'json.loads() the text alone.'
                        % (name, kw.arg, ': it hands json a function, and a function made '
                           'while the app runs is not translated' if hands_a_function else ''),
                        'json.dumps(data, indent=2, sort_keys=True), json.loads(text)')
        keywords = {kw.arg: kw.value for kw in node.keywords}
        if name == 'dumps':
            self._check_dumps(node, keywords)
        folded = self._fold(node, name, keywords)
        if folded is not None:
            return folded
        STATE['used'] = True
        return node

    def _check_dumps(self, node, keywords):
        indent = keywords.get('indent')
        if indent is not None:
            ok, value = _literal(indent)
            if ok and not (value is None or isinstance(value, str)
                           or (isinstance(value, int) and not isinstance(value, bool))):
                _refuse(node, 'indent= is a whole number of spaces, a text or None.',
                        'json.dumps(data, indent=2)')
        separators = keywords.get('separators')
        if separators is not None:
            ok, value = _literal(separators)
            if not (ok and (value is None or (isinstance(value, (tuple, list)) and len(value) == 2
                                              and all(isinstance(v, str) for v in value)))):
                _refuse(node, 'separators= is translated when it is written out: two texts, '
                              'between items and between a key and its value.',
                        'json.dumps(data, separators=(",", ":"))')

    def _fold(self, node, name, keywords):
        """The call worked out now, when everything it is given is written out."""
        ok, value = _literal(node.args[0])
        if not ok:
            return None
        if name == 'loads':
            if not isinstance(value, str):
                return None
            try:
                result = json.loads(value)
            except ValueError:
                return None                  # it raises when the app runs, as in CPython
            return _as_node(result, node) if _plain(result) else None
        options = {}
        for key, expr in keywords.items():
            good, option = _literal(expr)
            if not good:
                return None
            options[key] = option
        try:
            return _loc(ast.Constant(value=json.dumps(value, **options)), node)
        except (TypeError, ValueError):
            return None


_LATER = ('Do it in a function that runs when the screen opens, '
          'lifecycle(home, on_mount=load), and start the name as None at the top: '
          'data = None, then in load(): global data; data = json.loads(files.read("data.json")).')


def _why_not_now(node):
    """Why a json call at the top of the file was not worked out while building."""
    ok, value = _literal(node.args[0])
    options = {}
    for kw in node.keywords:
        good, option = _literal(kw.value)
        ok = ok and good
        options[kw.arg] = option
    if not ok:
        return (', so what it reads has to be written out in the source. Here it is only '
                'known while the app runs', _LATER)
    try:
        if node.func.attr == 'loads':
            json.loads(value)
        else:
            json.dumps(value, **options)
    except (TypeError, ValueError) as error:
        name = 'json.JSONDecodeError' if isinstance(error, json.JSONDecodeError) \
            else type(error).__name__
        return (', and here it raises %s: %s' % (name, error),
                'Fix what is written out, or do it in a function, where an except can catch '
                'the error.')
    return (', and its answer holds a value ApkPy cannot write out (Infinity, NaN or a whole '
            'number past 64 bits)', _LATER)


def _refuse_at_the_top(statements, place):
    """json calls left at the top of the file or of a class: the Java has nowhere
    to run them, so they are refused here instead of failing in javac. A lambda
    runs later, from a function, and is left alone."""
    for stmt in statements:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(stmt, ast.ClassDef):
            _refuse_at_the_top(stmt.body, 'at the top of a class')
            continue
        stack = [stmt]
        while stack:
            sub = stack.pop()
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                ast.Lambda)):
                continue
            stack.extend(ast.iter_child_nodes(sub))
            if isinstance(sub, ast.Call) and _is_json(sub.func) and sub.func.attr in _CALLS:
                why, tip = _why_not_now(sub)
                _refuse(sub, 'json.%s() %s is worked out while ApkPy builds the app%s.'
                        % (sub.func.attr, place, why), tip)


class _Alone(ast.NodeTransformer):
    """json.loads(text) on a line of its own, to see whether it raises: given a
    name, so it is translated as the value it is (a call alone is a statement
    the compiler looks up by name)."""

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        node.body = self._block(node.body)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def _block(self, body):
        for stmt in body:
            for field in ('body', 'orelse', 'finalbody'):
                inner = getattr(stmt, field, None)
                if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt) \
                        and not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                  ast.ClassDef)):
                    setattr(stmt, field, self._block(inner))
            for handler in getattr(stmt, 'handlers', []) or []:
                handler.body = self._block(handler.body)
        return [self._name_it(stmt) for stmt in body]

    def _name_it(self, stmt):
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) \
                and _is_json(stmt.value.func) and stmt.value.func.attr in _CALLS:
            return _loc(ast.Assign(targets=[_loc(ast.Name(id='_apkpy_json', ctx=ast.Store()),
                                                 stmt)], value=stmt.value), stmt)
        return stmt


def desugar(tree):
    """Spell json the one way, work out what can be worked out, refuse the rest."""
    STATE['used'] = False
    names = _aliases(tree)
    if not names:
        return tree
    tree = _Spell(names).visit(tree)
    tree = _Calls().visit(tree)
    _refuse_at_the_top(tree.body, 'at the top of the file')
    tree = _Alone().visit(tree)
    ast.fix_missing_locations(tree)
    return tree
