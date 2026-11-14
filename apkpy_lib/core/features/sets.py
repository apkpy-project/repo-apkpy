# -*- coding: utf-8 -*-
"""set: a list without repeats, in the order CPython keeps it.

    seen = set()
    for w in words:
        seen.add(w)
    tags = {"tea", "jam"} | other
    if a <= b: ...
    label.set_value(str(seen))          # {'jam', 'tea'}

On the phone a set is the JSON list of its items, as a list is, so `for x in
s`, `x in s`, `len(s)`, `sorted(s)` and `list(s)` read it as they read a list.
What only a set does is written here as calls the generators translate
(PREFIX + the operation):

    s.add(x)               s = _apkpy_set_add(s, x)
    s |= t, s.update(t)    s = _apkpy_set_union(s, t)
    a - b, a.difference(b) _apkpy_set_difference(a, b)
    a <= b, a == b         _apkpy_set_issubset(a, b), _apkpy_set_eq(a, b)
    x = s.pop()            x = _apkpy_set_popvalue(s); s = _apkpy_set_rest(s)
    {1, 2}, set(xs), {f(x) for x in xs}
                           _apkpy_set_of([...])
    str(s), f"{s}"         _apkpy_set_show(s)    {1, 2}, set()

Which values are sets is read from the source: set(), {..}, a set
comprehension, the operators and methods that answer one, and the names,
parameters, fields (obj.x) and functions that only ever hold or give one.

Order. CPython keeps a set in a hash table and walks the table: {3, 1, 2}
shows {1, 2, 3}, {100, 5} shows {100, 5}. An int's hash is fixed, so the same
table is built here, in the order the items were added (cpython_order and
_apkpySetOrder in the Java). Text is hashed differently on every run of
CPython, so a set of text keeps the order its items were added in.

A set at the top of the file is translated when its items are written out
(or worked out by module_constants.py); a module set changed in a function is
read as `global`, as a module list is.
"""

import ast
import copy

from .. import unsupported

PREFIX = "_apkpy_set_"

# What each internal call answers.
SET_RESULTS = {'of', 'fixed', 'add', 'discard', 'remove', 'union', 'intersection',
               'difference', 'without', 'symmetric_difference', 'rest', 'clear'}
BOOL_RESULTS = {'issubset', 'issuperset', 'isdisjoint', 'eq', 'ne', 'lt', 'gt'}

# s.method(...) that changes s, and the operation that gives its new value.
_CHANGERS = {
    'add': 'add', 'discard': 'discard', 'remove': 'remove', 'update': 'union',
    'clear': 'clear', 'difference_update': 'without',
    'intersection_update': 'intersection',
    'symmetric_difference_update': 'symmetric_difference',
}
# s.method(...) that answers a new set (or a bool) and changes nothing.
_READERS = {'union', 'intersection', 'difference', 'symmetric_difference',
            'issubset', 'issuperset', 'isdisjoint', 'copy'}
_OPERATORS = {ast.BitOr: 'union', ast.BitAnd: 'intersection', ast.Sub: 'difference',
              ast.BitXor: 'symmetric_difference'}
_COMPARE = {ast.Eq: 'eq', ast.NotEq: 'ne', ast.LtE: 'issubset', ast.Lt: 'lt',
            ast.GtE: 'issuperset', ast.Gt: 'gt'}
# Calls that show a value as text.
_SHOWN_BY = {'str', 'repr', 'print', 'toast'}


def op_of(node):
    """The operation of an internal call, or None."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id.startswith(PREFIX):
        return node.func.id[len(PREFIX):]
    return None


def makes_set(node):
    return op_of(node) in SET_RESULTS


# --- CPython's order ---------------------------------------------------------

_P = (1 << 61) - 1


def _py_hash(value):
    """CPython's hash of a number, or None for what is hashed per run."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return hash(value)
    if isinstance(value, float) and value == value:
        return hash(value)
    return None


def _probe(table, mask, h):
    """The empty slot CPython's set_insert_clean puts a hash in."""
    perturb = h & 0xFFFFFFFFFFFFFFFF
    i = h & mask
    while True:
        if table[i] is None:
            return i
        if i + 9 <= mask:
            for j in range(1, 10):
                if table[i + j] is None:
                    return i + j
        perturb >>= 5
        i = (i * 5 + 1 + perturb) & mask


def cpython_order(items, literal=False):
    """*items* (no repeats, in the order added) in the order CPython walks them.

    Only when every item has a hash fixed across runs (numbers, bools);
    otherwise the order given. *literal*: {16, 1, 2, 3, 4}, three or more
    constants. CPython makes them a frozenset when it compiles the code,
    makes that frozenset again from its own order (merge_consts), and copies
    it into a new set when the line runs (set_merge): a table of another size.
    """
    hashes = [_py_hash(v) for v in items]
    if any(h is None for h in hashes):
        return list(items)

    def walk(seq):
        table, mask = _table([hashes[k] for k in seq])
        return [seq[j] for j in table if j is not None], mask

    order, mask = walk(list(range(len(items))))
    if literal and len(items) >= 3:
        order, mask = walk(order)
        size = 8
        if len(items) * 5 >= 7 * 3:
            while size <= len(items) * 2:
                size <<= 1
        if size - 1 != mask:
            fresh = [None] * size
            for k in order:
                fresh[_probe(fresh, size - 1, hashes[k])] = k
            order = [k for k in fresh if k is not None]
    return [items[k] for k in order]


def _table(hashes):
    """CPython's table for these hashes added one by one: (slots, mask)."""
    mask = 7
    table = [None] * 8
    fill = 0
    for k, h in enumerate(hashes):
        table[_probe(table, mask, h)] = k
        fill += 1
        if fill * 5 >= mask * 3:
            minused = fill * 2 if fill > 50000 else fill * 4
            size = 8
            while size <= minused:
                size <<= 1
            fresh = [None] * size
            for slot in table:
                if slot is not None:
                    fresh[_probe(fresh, size - 1, hashes[slot])] = slot
            table, mask = fresh, size - 1
    return table, mask


def is_constant_literal(node):
    """{16, 1, 2, 3, 4}: three or more constants, which CPython orders its way."""
    return isinstance(node, ast.Set) and len(node.elts) >= 3 \
        and all(_constant(e)[1] for e in node.elts)


def _constant(node):
    """The value of a constant CPython folds in a set literal, or (None, False)."""
    if isinstance(node, ast.Constant):
        return node.value, True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)) \
            and isinstance(node.operand, ast.Constant) \
            and type(node.operand.value) in (int, float):
        value = node.operand.value
        return (-value if isinstance(node.op, ast.USub) else value), True
    return None, False


# --- which values are sets ---------------------------------------------------

def _loc(node, like):
    return ast.copy_location(node, like)


def _call(op, args, like):
    return _loc(ast.Call(func=_loc(ast.Name(id=PREFIX + op, ctx=ast.Load()), like),
                         args=list(args), keywords=[]), like)


def _bindings(stmts):
    """name -> [value nodes] given in these statements (None: a for, an
    unpacking, a with -- a value that is not read here)."""
    values = {}
    stack = list(stmts)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
                             ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values.setdefault(target.id, []).append(node.value)
                else:
                    # d[k] = v and obj.x = v give d and obj no new value.
                    for sub in ast.walk(target):
                        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                            values.setdefault(sub.id, []).append(None)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            values.setdefault(node.target.id, []).append(
                _loc(ast.BinOp(left=ast.Name(id=node.target.id, ctx=ast.Load()),
                               op=node.op, right=node.value), node))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            values.setdefault(node.target.id, []).append(node.value)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.With, ast.AsyncWith,
                               ast.ExceptHandler, ast.NamedExpr)):
            for sub in ast.walk(node.target if isinstance(node, (ast.For, ast.AsyncFor))
                                else node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    values.setdefault(sub.id, []).append(None)
            if isinstance(node, ast.ExceptHandler) and node.name:
                values.setdefault(node.name, []).append(None)
        stack.extend(ast.iter_child_nodes(node))
    return values


class _Sets(object):
    """What the source says holds a set."""

    def __init__(self, tree):
        self.tree = tree
        self.functions = [n for n in ast.walk(tree)
                          if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self.module = set()
        self.returns = set()
        self.fields = set()
        self.params = {}            # function node -> set params
        self.scopes = {}            # function node -> its set names
        self.globals_of = {fn: {n for s in ast.walk(fn) if isinstance(s, ast.Global)
                                for n in s.names} for fn in self.functions}
        # The function each node is in (the innermost: ast.walk lists the
        # outer function first).
        self.owner = {}
        for fn in self.functions:
            for node in ast.walk(fn):
                self.owner[id(node)] = fn
        self._settle()

    # A value is a set when the source says so, given what is known so far.
    def is_set(self, node, scope):
        if isinstance(node, (ast.Set, ast.SetComp)):
            return True
        if isinstance(node, ast.Call):
            func = node.func
            if makes_set(node):
                return True
            if isinstance(func, ast.Name):
                if func.id == 'set' and len(node.args) <= 1 and not node.keywords:
                    return True
                return func.id in self.returns
            if isinstance(func, ast.Attribute) and func.attr in (
                    'union', 'intersection', 'difference', 'symmetric_difference', 'copy'):
                return self.is_set(func.value, scope)
            return False
        if isinstance(node, ast.Name):
            return node.id in scope
        if isinstance(node, ast.Attribute):
            return node.attr in self.fields
        if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
            return self.is_set(node.left, scope)
        if isinstance(node, ast.IfExp):
            return self.is_set(node.body, scope) and self.is_set(node.orelse, scope)
        return False

    def _names(self, values, base):
        """The names of *values* that only ever hold a set (the largest such
        set: s = set() then s = s | t is one)."""
        names = {n for n, vs in values.items() if vs and all(v is not None for v in vs)}
        while True:
            scope = (base - set(values)) | names
            keep = {n for n in names if all(self.is_set(v, scope) for v in values[n])}
            if keep == names:
                return (base - set(values)) | names
            names = keep

    def scope_of(self, fn):
        return self.scopes.get(fn, self.module)

    def _settle(self):
        module_values = _bindings([s for s in self.tree.body])
        for _ in range(6):
            before = (set(self.module), set(self.returns), set(self.fields),
                      {k: set(v) for k, v in self.params.items()})
            # Module names: their module values, and what functions give them
            # through `global`.
            values = {k: list(v) for k, v in module_values.items()}
            for fn in self.functions:
                inner = _bindings(fn.body)
                for name in self.globals_of[fn]:
                    if name in inner:
                        values.setdefault(name, []).extend(inner[name])
            self.module = self._names(values, set())
            for fn in self.functions:
                inner = _bindings(fn.body)
                local = {n: v for n, v in inner.items() if n not in self.globals_of[fn]}
                args = [a.arg for a in fn.args.args + fn.args.kwonlyargs]
                outer = (self.module - set(args) - set(local)) | self.params.get(fn, set())
                self.scopes[fn] = self._names(local, outer)
            # Functions that only ever answer a set.
            self.returns = set()
            for fn in self.functions:
                values = [n.value for n in ast.walk(fn) if isinstance(n, ast.Return)]
                if values and all(v is not None and self.is_set(v, self.scopes[fn])
                                  for v in values):
                    self.returns.add(fn.name)
            # Fields: every obj.x = ... gives a set.
            stores = {}
            for node in ast.walk(self.tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Attribute):
                            stores.setdefault(target.attr, []).append((node, node.value))
            self.fields = set()
            for attr, given in stores.items():
                if all(self.is_set(value, self._scope_at(node)) for node, value in given):
                    self.fields.add(attr)
            # Parameters every call fills with a set.
            calls = {}
            for fn in self.functions:
                for node in ast.walk(fn):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        calls.setdefault(node.func.id, []).append((fn, node))
            for stmt in self.tree.body:
                if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    for node in ast.walk(stmt):
                        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                            calls.setdefault(node.func.id, []).append((None, node))
            self.params = {}
            for fn in self.functions:
                found = calls.get(fn.name)
                if not found:
                    continue
                names = [a.arg for a in fn.args.args]
                sets = set()
                for i, name in enumerate(names):
                    if all(len(c.args) > i and not c.keywords
                           and self.is_set(c.args[i], self.scope_of(owner))
                           for owner, c in found):
                        sets.add(name)
                if sets:
                    self.params[fn] = sets
            after = (set(self.module), set(self.returns), set(self.fields),
                     {k: set(v) for k, v in self.params.items()})
            if after == before:
                break

    def _scope_at(self, node):
        fn = self.owner.get(id(node))
        return self.scopes.get(fn, self.module) if fn is not None else self.module


# --- the rewrite -------------------------------------------------------------

class _Rewriter(ast.NodeTransformer):
    """One scope's statements, with the names that hold a set there."""

    def __init__(self, sets, scope, at_module):
        self.sets = sets
        self.scope = scope
        self.at_module = at_module
        self.module_changed = set()     # module sets a function gives a new value

    def is_set(self, node):
        return self.sets.is_set(node, self.scope)

    def _op(self, op, left, right, like):
        """_apkpy_set_<op>(left, right); & also says whether right is a set
        (CPython walks the smaller of two sets, and a list in its order)."""
        args = [left, right]
        if op == 'intersection':
            both = bool(self.is_set(right) or makes_set(right))
            args.append(_loc(ast.Constant(value=both), like))
        return _call(op, args, like)

    def _holds_set(self, node):
        return node is not None and (self.is_set(node) or makes_set(node))

    def _not_inside(self, values, like):
        """A set put in a list, a tuple or a dict would show as a list there:
        on the phone a set is the list of its items, and the value it is in
        does not know it is a set."""
        if any(self._holds_set(v) for v in values):
            _refuse_inside(like)

    def visit_List(self, node):
        self._not_inside(node.elts, node)
        return self.generic_visit(node)

    def visit_Tuple(self, node):
        if isinstance(node.ctx, ast.Load) and not getattr(node, '_apkpy_unpacked', False):
            self._not_inside(node.elts, node)
        return self.generic_visit(node)

    def visit_Dict(self, node):
        self._not_inside(list(node.keys) + list(node.values), node)
        return self.generic_visit(node)

    def visit_ListComp(self, node):
        self._not_inside([node.elt], node)
        return self.generic_visit(node)

    visit_GeneratorExp = visit_ListComp

    def visit_DictComp(self, node):
        self._not_inside([node.key, node.value], node)
        return self.generic_visit(node)

    # Nested functions and classes have scopes of their own.
    def visit_FunctionDef(self, node):
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        return node

    def _assign(self, target, value, like):
        if isinstance(target, ast.Name) and target.id in self.sets.module \
                and not self.at_module and target.id not in self.scope_locals:
            self.module_changed.add(target.id)
        return _loc(ast.Assign(targets=[_as_store(target)], value=value), like)

    def visit_Expr(self, node):
        call = node.value
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) \
                and self.is_set(call.func.value):
            receiver = call.func.value
            method = call.func.attr
            if method in _CHANGERS or method == 'pop':
                if self.at_module:
                    _refuse_module_change(node)
                args = [self.visit(a) for a in call.args]
                current = _as_load(receiver)
                if method == 'pop':
                    value = _call('rest', [current], node)
                elif method == 'clear':
                    value = _call('clear', [current], node)
                elif method in ('update', 'difference_update', 'intersection_update',
                                'symmetric_difference_update'):
                    value = current
                    for arg in args or [_loc(ast.List(elts=[], ctx=ast.Load()), node)]:
                        value = self._op(_CHANGERS[method], value, arg, node)
                else:
                    value = _call(_CHANGERS[method], [current] + args, node)
                return self._assign(receiver, value, node)
        return self.generic_visit(node)

    def visit_Assign(self, node):
        value = node.value
        if isinstance(value, ast.Tuple) and len(node.targets) == 1 \
                and isinstance(node.targets[0], (ast.Tuple, ast.List)) \
                and len(node.targets[0].elts) == len(value.elts):
            value._apkpy_unpacked = True
        if any(isinstance(t, ast.Subscript) for t in node.targets) and self._holds_set(value):
            _refuse_inside(node)
        if len(node.targets) == 1 and isinstance(value, ast.Call) \
                and isinstance(value.func, ast.Attribute) and value.func.attr == 'pop' \
                and not value.args and self.is_set(value.func.value):
            if self.at_module:
                _refuse_module_change(node)
            receiver = value.func.value
            first = _loc(ast.Assign(targets=node.targets,
                                    value=_call('popvalue', [_as_load(receiver)], node)), node)
            rest = self._assign(receiver, _call('rest', [_as_load(receiver)], node), node)
            return [first, rest]
        node = self.generic_visit(node)
        if self.at_module and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in self.sets.module:
            node.value = _module_value(node.value)
        return node

    def visit_AugAssign(self, node):
        if type(node.op) in _OPERATORS and self.is_set(node.target):
            if self.at_module:
                _refuse_module_change(node)
            op = _OPERATORS[type(node.op)]
            # s -= t takes the items out where they are, as discard does;
            # a - b is a new set.
            value = self._op('without' if op == 'difference' else op, _as_load(node.target),
                             self.visit(node.value), node)
            return self._assign(node.target, value, node)
        return self.generic_visit(node)

    def visit_BinOp(self, node):
        if type(node.op) in _OPERATORS and self.is_set(node.left):
            left, right = self.visit(node.left), self.visit(node.right)
            return self._op(_OPERATORS[type(node.op)], left, right, node)
        return self.generic_visit(node)

    def visit_Compare(self, node):
        if len(node.ops) == 1 and type(node.ops[0]) in _COMPARE \
                and (self.is_set(node.left) or self.is_set(node.comparators[0])):
            if not (self._holds_set(node.left) and self._holds_set(node.comparators[0])):
                unsupported.raise_unsupported(
                    node, cause='A set compared with a value that is not a set is not '
                                'translated: in CPython {1, 2} == [1, 2] is False, and on '
                                'the phone both are kept as the same list.',
                    suggestions=['Make both sides sets: s == set(items).'])
            left, right = self.visit(node.left), self.visit(node.comparators[0])
            return _call(_COMPARE[type(node.ops[0])], [left, right], node)
        return self.generic_visit(node)

    def visit_Set(self, node):
        found = [_constant(e) for e in node.elts]
        if is_constant_literal(node):
            # {16, 1, 2, 3, 4}: CPython's order is worked out here, once.
            kept = []
            for e, (value, _) in zip(node.elts, found):
                if not any(_same(value, seen) for seen, _ in kept):
                    kept.append((value, e))
            ordered = cpython_order([v for v, _ in kept], literal=True)
            elts = [next(e for v, e in kept if v is o) for o in ordered]
            return _call('fixed', [_loc(ast.List(elts=elts, ctx=ast.Load()), node)], node)
        elts = [self.visit(e) for e in node.elts]
        return _call('of', [_loc(ast.List(elts=elts, ctx=ast.Load()), node)], node)

    def visit_SetComp(self, node):
        node = self.generic_visit(node)
        listed = _loc(ast.ListComp(elt=node.elt, generators=node.generators), node)
        return _call('of', [listed], node)

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in ('append', 'insert', 'setdefault') \
                and not self.is_set(func.value):
            self._not_inside(node.args, node)
        if isinstance(func, ast.Attribute) and func.attr in ('dumps', 'dump') \
                and isinstance(func.value, ast.Name) and func.value.id == 'json' \
                and node.args and self._holds_set(node.args[0]):
            unsupported.raise_unsupported(
                node, cause='json.dumps() of a set: CPython stops with TypeError, '
                            '"Object of type set is not JSON serializable".',
                suggestions=['Give it a list: json.dumps(sorted(s)).'])
        if isinstance(func, ast.Name) and func.id == 'frozenset':
            unsupported.raise_unsupported(
                node, cause='frozenset is not translated yet.',
                suggestions=['Use a set: set(items).'])
        if isinstance(func, ast.Name) and func.id == 'set' and not node.keywords \
                and len(node.args) <= 1:
            args = [self.visit(a) for a in node.args]
            return _call('of', args or [_loc(ast.List(elts=[], ctx=ast.Load()), node)], node)
        if isinstance(func, ast.Attribute) and func.attr in _READERS and self.is_set(func.value):
            receiver = self.visit(func.value)
            args = [self.visit(a) for a in node.args]
            if func.attr == 'copy':
                return _call('of', [receiver], node)
            if func.attr in ('issubset', 'issuperset', 'isdisjoint'):
                return _call(func.attr, [receiver] + args[:1], node)
            value = receiver
            for arg in args or [_loc(ast.List(elts=[], ctx=ast.Load()), node)]:
                value = self._op(func.attr, value, arg, node)
            return value
        node = self.generic_visit(node)
        # What shows a set as text: str(s), print(s), toast(s), x.set_value(s).
        shows = (isinstance(func, ast.Name) and func.id in _SHOWN_BY) or (
            isinstance(func, ast.Attribute) and func.attr == 'set_value')
        if shows:
            node.args = [self._shown(a) for a in node.args]
        return node

    def visit_FormattedValue(self, node):
        node = self.generic_visit(node)
        node.value = self._shown(node.value)
        return node

    def _shown(self, node):
        if self.is_set(node) or makes_set(node):
            return _call('show', [node], node)
        return node


def _as_store(node):
    node = _copy(node)
    node.ctx = ast.Store()
    return node


def _as_load(node):
    node = _copy(node)
    for sub in ast.walk(node):
        if hasattr(sub, 'ctx'):
            sub.ctx = ast.Load()
    return node


def _copy(node):
    return copy.deepcopy(node)


def _refuse_inside(node):
    unsupported.raise_unsupported(
        node, cause='A set inside a list, a tuple or a dict is not translated yet: on '
                    'the phone a set is kept as the list of its items, and inside '
                    'another value it would show as a list.',
        suggestions=['Keep the set in a name of its own, or put sorted(s) in the list.'])


def _refuse_module_change(node):
    unsupported.raise_unsupported(
        node, cause='Changing a set at the top of the file is not translated: it '
                    'runs once, when the app starts, and its items can be written '
                    'out instead.',
        suggestions=['Write the set with its items: TAGS = {"tea", "jam"}, or change '
                     'it inside a function.'])


def _module_value(value):
    """A set of the module, as the list literal it is kept as."""
    if op_of(value) == 'fixed':
        return value.args[0]
    if op_of(value) == 'of' and value.args and isinstance(value.args[0], ast.List) \
            and all(isinstance(e, ast.Constant) for e in value.args[0].elts):
        items = []
        for e in value.args[0].elts:
            if not any(_same(e.value, x.value) for x in items):
                items.append(e)
        ordered = cpython_order([e.value for e in items])
        elts = [next(e for e in items if e.value is v) for v in ordered]
        return _loc(ast.List(elts=elts, ctx=ast.Load()), value)
    unsupported.raise_unsupported(
        value, cause='A set at the top of the file is translated when its items are '
                     'written out, or worked out from values above it.',
        suggestions=['Write the items out: TAGS = {"tea", "jam"}, or make the set '
                     'inside a function.'])


def _same(a, b):
    try:
        return a == b and hash(a) == hash(b)
    except TypeError:
        return False


def rewrite(tree):
    sets = _Sets(tree)
    # The module's own statements.
    top = _Rewriter(sets, sets.module, at_module=True)
    top.scope_locals = set()
    new_body = []
    for stmt in tree.body:
        done = top.visit(stmt)
        new_body.extend(done if isinstance(done, list) else [done])
    tree.body = new_body
    # Each function, with its own names.
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        scope = sets.scope_of(fn)
        rewriter = _Rewriter(sets, scope, at_module=False)
        args = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
        rewriter.scope_locals = (set(_bindings(fn.body)) | args) - sets.globals_of.get(fn, set())
        body = []
        for stmt in fn.body:
            done = rewriter.visit(stmt)
            body.extend(done if isinstance(done, list) else [done])
        fn.body = body
        # A module set given a new value here: `global`, as Python's
        # s.add(x) changed the one object every function sees.
        changed = sorted(rewriter.module_changed - sets.globals_of.get(fn, set()))
        if changed:
            fn.body.insert(0, _loc(ast.Global(names=changed), fn.body[0]))
    ast.fix_missing_locations(tree)
    return tree
