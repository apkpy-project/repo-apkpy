# -*- coding: utf-8 -*-
"""Values at the top of the file, worked out at build as Python works them out at start.

    NAMES = ["ana", "rui"]
    N = len(NAMES)
    SQUARES = [i * i for i in range(5)]
    TOTAL = sum(PRICES.values())
    WORDS = "red green blue".split()

Python runs these lines once, when the app starts, from the values written
above them. The generators knew a module-level literal, a string built with
+, and the calls that make components; anything else fell through. The name
reached the Java without ever being declared and javac stopped far from the
line (a comprehension was refused with U2033).

The build now runs the line with the same Python, and puts the answer in its
place as a literal, which the rest of the pipeline already knows. Only what
can be worked out from literals and module names given before it: builtins
such as len(), sum(), sorted() and range(), the methods of str, list and dict
that change nothing, and math. A function of the app, a component, storage,
anything that reads the phone, is left as it was.

A name that is changed in place anywhere (xs.append(), d[k] = v, global in a
function) is not read by a later line: what it holds when that line runs is
not known here. Its own first value is still worked out.
"""

import ast
import builtins
import copy
import math

_BUILTINS = (
    'abs', 'all', 'any', 'bin', 'bool', 'chr', 'dict', 'divmod', 'enumerate',
    'filter', 'float', 'format', 'frozenset', 'hex', 'int', 'isinstance', 'len',
    'list', 'map', 'max', 'min', 'oct', 'ord', 'pow', 'range', 'repr', 'reversed',
    'round', 'set', 'sorted', 'str', 'sum', 'tuple', 'zip',
)

# Methods that read a value and change nothing.
_READING_METHODS = {
    # str
    'capitalize', 'casefold', 'center', 'count', 'endswith', 'expandtabs', 'find',
    'format', 'index', 'isalnum', 'isalpha', 'isdecimal', 'isdigit', 'islower',
    'isnumeric', 'isspace', 'istitle', 'isupper', 'join', 'ljust', 'lower', 'lstrip',
    'partition', 'removeprefix', 'removesuffix', 'replace', 'rfind', 'rindex',
    'rjust', 'rpartition', 'rsplit', 'rstrip', 'split', 'splitlines', 'startswith',
    'strip', 'swapcase', 'title', 'upper', 'zfill',
    # list, tuple, dict
    'copy', 'get', 'items', 'keys', 'values',
    # set
    'difference', 'intersection', 'isdisjoint', 'issubset', 'issuperset',
    'symmetric_difference', 'union',
}

_CHANGING_METHODS = {
    'append', 'extend', 'insert', 'remove', 'pop', 'clear', 'update', 'add',
    'discard', 'sort', 'reverse', 'setdefault', 'popitem', 'difference_update',
    'intersection_update', 'symmetric_difference_update',
}

# Past this, the literal would be bigger than the line that makes it is worth.
_MAX_TEXT = 100000
_MAX_RANGE = 100000


def _range(*args):
    r = range(*args)
    if len(r) > _MAX_RANGE:
        raise ValueError("range too long to work out at build")
    return r


def _changed_somewhere(tree):
    """Names changed in place, or given a value from inside a function."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in _CHANGING_METHODS:
            base = node.func.value
            while isinstance(base, (ast.Subscript, ast.Attribute)):
                base = base.value
            if isinstance(base, ast.Name):
                found.add(base.id)
        elif isinstance(node, (ast.Subscript, ast.Attribute)) \
                and isinstance(node.ctx, (ast.Store, ast.Del)):
            base = node.value
            while isinstance(base, (ast.Subscript, ast.Attribute)):
                base = base.value
            if isinstance(base, ast.Name):
                found.add(base.id)
        elif isinstance(node, ast.Global):
            found.update(node.names)
    return found


def _math_names(tree):
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'math':
                    names.add(alias.asname or 'math')
    return names


def _allowed(node, math_names):
    """Only literals, operators, builtins, reading methods and math."""
    called = {id(sub.func) for sub in ast.walk(node) if isinstance(sub, ast.Call)}
    for sub in ast.walk(node):
        if isinstance(sub, (ast.Await, ast.Yield, ast.YieldFrom, ast.NamedExpr)):
            return False
        if isinstance(sub, ast.Attribute):
            if sub.attr.startswith('_'):
                return False
        if isinstance(sub, ast.Call):
            func = sub.func
            if isinstance(func, ast.Name):
                if func.id not in _BUILTINS:
                    return False
            elif isinstance(func, ast.Attribute):
                if isinstance(func.value, ast.Name) and func.value.id in math_names:
                    continue
                if func.attr not in _READING_METHODS:
                    return False
            else:
                return False
        if isinstance(sub, ast.Attribute) and id(sub) not in called:
            # A bare attribute: math.pi, and nothing else.
            if not (isinstance(sub.value, ast.Name) and sub.value.id in math_names):
                return False
    return True


def _plain(node):
    """A literal as written: the generators already read it."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return isinstance(node.operand, ast.Constant)
    if isinstance(node, (ast.List, ast.Tuple)):
        return all(_plain(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all(k is not None and _plain(k) for k in node.keys) \
            and all(_plain(v) for v in node.values)
    return False


def _containers(value, out):
    """The ids of every list, dict and set in *value*."""
    if isinstance(value, (list, dict, set)):
        if id(value) in out:
            return
        out.add(id(value))
        for item in (value.values() if isinstance(value, dict) else value):
            _containers(item, out)
    elif isinstance(value, tuple):
        for item in value:
            _containers(item, out)


def _literal(value, like):
    """*value* written as the literal that makes it, or None."""
    def made(node):
        return ast.copy_location(node, like)

    if value is None or isinstance(value, (bool, int, str)):
        return made(ast.Constant(value=value))
    if isinstance(value, float):
        return made(ast.Constant(value=value)) if math.isfinite(value) else None
    if isinstance(value, (list, tuple)):
        items = [_literal(v, like) for v in value]
        if any(i is None for i in items):
            return None
        kind = ast.List if isinstance(value, list) else ast.Tuple
        return made(kind(elts=items, ctx=ast.Load()))
    if isinstance(value, _OrderedSet):
        # Its items in CPython's order (sets.py); an empty one is set().
        if not value.items:
            return made(ast.Call(func=made(ast.Name(id='set', ctx=ast.Load())), args=[],
                                 keywords=[]))
        items = [_literal(v, like) for v in value.items]
        if any(i is None for i in items):
            return None
        if value.literal:
            return made(ast.Set(elts=items))
        # set([...]) and not {...}: {16, 1, 2, 3, 4} of constants is put in
        # another order by CPython (sets.py), and these went in one by one.
        return made(ast.Call(func=made(ast.Name(id='set', ctx=ast.Load())),
                             args=[made(ast.List(elts=items, ctx=ast.Load()))], keywords=[]))
    if isinstance(value, dict):
        keys = [_literal(k, like) for k in value]
        values = [_literal(v, like) for v in value.values()]
        if any(i is None for i in keys + values):
            return None
        return made(ast.Dict(keys=keys, values=values))
    return None


class _OrderedSet(object):
    """A set worked out here, with its items in the order they went in."""

    def __init__(self, items, literal=False):
        from .sets import cpython_order
        unique = []
        for item in items:
            if not any(item == seen and hash(item) == hash(seen) for seen in unique):
                unique.append(item)
        self.literal = literal
        self.items = cpython_order(unique, literal=literal)


def _as_items(node):
    """set(x), {a, b} and {f(x) for ...} as the list of what goes in, in order:
    a set of text has no order CPython keeps across runs, so the order the
    items went in is the one kept (sets.py)."""
    if isinstance(node, ast.Set):
        return ast.List(elts=node.elts, ctx=ast.Load())
    if isinstance(node, ast.SetComp):
        return ast.ListComp(elt=node.elt, generators=node.generators)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'set' \
            and not node.keywords and len(node.args) <= 1:
        return ast.Call(func=ast.Name(id='list', ctx=ast.Load()), args=node.args, keywords=[])
    return None


def _work_out(node, env, math_names):
    """(True, value) for *node* run with *env*, or (False, None)."""
    listed = _as_items(node)
    if listed is not None:
        ok, items = _work_out(ast.copy_location(listed, node), env, math_names)
        if not ok:
            return False, None
        try:
            hash(tuple(items))
        except TypeError:
            return False, None
        from .sets import is_constant_literal
        return True, _OrderedSet(items, literal=is_constant_literal(node))
    if not _allowed(node, math_names):
        return False, None
    scope = copy.deepcopy(env)
    shared = set()
    for value in scope.values():
        _containers(value, shared)
    names = {name: getattr(builtins, name) for name in _BUILTINS}
    names['range'] = _range
    scope['__builtins__'] = names
    for name in math_names:
        scope[name] = math
    try:
        value = eval(compile(ast.fix_missing_locations(ast.Expression(body=copy.deepcopy(node))),
                             '<module value>', 'eval'), scope)
    except Exception:
        return False, None
    if isinstance(value, (range, map, filter, zip, enumerate, reversed)) \
            or type(value).__name__.endswith('iterator'):
        return False, None
    mine = set()
    _containers(value, mine)
    if mine & shared:
        # B = A, ROW = ROWS[0]: the same list under two names in Python. A
        # copy here would part them; features/shared_containers.py decides.
        return False, None
    try:
        if len(repr(value)) > _MAX_TEXT:
            return False, None
    except Exception:
        return False, None
    return True, value


def fold(tree):
    changed = _changed_somewhere(tree)
    math_names = _math_names(tree)
    env = {}
    for stmt in getattr(tree, 'body', []):
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                and isinstance(stmt.targets[0], ast.Name):
            name = stmt.targets[0].id
            ok, value = _work_out(stmt.value, env, math_names)
            literal = _literal(value, stmt.value) if ok else None
            if literal is None:
                env.pop(name, None)
                continue
            if not _plain(stmt.value):
                stmt.value = literal
            if name in changed:
                env.pop(name, None)
            else:
                env[name] = value
            continue
        # Anything else that gives a name a value -- a for, a def, an import,
        # x += 1 -- makes it something this pass does not follow.
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
                env.pop(sub.id, None)
            elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                env.pop(sub.name, None)
            elif isinstance(sub, (ast.Import, ast.ImportFrom)):
                for alias in sub.names:
                    env.pop((alias.asname or alias.name).split('.')[0], None)
    return tree
