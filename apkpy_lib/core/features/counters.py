# -*- coding: utf-8 -*-
"""Counter and defaultdict (collections): a dict that answers for a missing key.

    counts = Counter(words)          counts["tea"] is 2, counts["cake"] is 0
    counts.most_common(2)            [('tea', 2), ('jam', 1)]
    groups = defaultdict(list)
    groups[kind].append(name)        the [] goes in first
    totals = defaultdict(int)
    totals[kind] += price

On the phone both are the JSON object a dict is, so d[k] = v, len(d), k in d,
for k in d, d.items(), d.get() and sorted(d) read them as they read a dict.
What is their own is written here as dict code, before translating:

    Counter(xs)                  _apkpy_counter_of(xs)
    Counter(), defaultdict(f)    {}
    c[k]                         c.get(k, 0)              a Counter adds nothing
    c[k] += n                    c[k] = c.get(k, 0) + n
    d[k], d[k] += 1, d[k].append(x)
                                 if k not in d: d[k] = []    on the line before
    c.update(xs), c.subtract(xs) c = _apkpy_counter_update(c, xs, 1 or -1)
    c.most_common(n)             _apkpy_counter_most_common(c, n)
    c.total()                    sum(c.values())
    str(c), str(d)               _apkpy_counter_show(c)       Counter({'tea': 2})
                                 _apkpy_default_show(d, "<class 'int'>")

A defaultdict adds the key when it is read, so the line before the read adds
it: when the read may not run (after `and`, in one branch of `x if c else y`,
in a comprehension or a lambda) or runs again and again (a while's test),
the build stops rather than add a key CPython would not.

Which names hold one is read from the source, as for sets: Counter(...),
defaultdict(...), and the names, fields, parameters and functions that only
ever hold or give one.
"""

import ast
import copy

from .. import unsupported
from .sets import _bindings

PREFIX = "_apkpy_counter_"

DICT_RESULTS = {'of', 'update'}
TEXT_RESULTS = {'show', 'default_show'}
LIST_RESULTS = {'most_common'}

# defaultdict(f): what f() gives, and how str() names f.
_FACTORIES = {
    'int': ('0', "<class 'int'>"),
    'float': ('0.0', "<class 'float'>"),
    'str': ('""', "<class 'str'>"),
    'bool': ('False', "<class 'bool'>"),
    'list': ('[]', "<class 'list'>"),
    'dict': ('{}', "<class 'dict'>"),
}
_SHOWN_BY = {'str', 'repr', 'print', 'toast'}


def op_of(node):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id.startswith(PREFIX):
        return node.func.id[len(PREFIX):]
    return None


def _loc(node, like):
    return ast.copy_location(node, like)


def _call(op, args, like):
    return _loc(ast.Call(func=_loc(ast.Name(id=PREFIX + op, ctx=ast.Load()), like),
                         args=list(args), keywords=[]), like)


def _maker(node):
    """'Counter', 'defaultdict' or None for a call that makes one."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    name = func.id if isinstance(func, ast.Name) else (
        func.attr if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
        and func.value.id == 'collections' else None)
    return name if name in ('Counter', 'defaultdict') else None


def _factory(call):
    """('0', "<class 'int'>") for defaultdict(int), or refuse."""
    if call.keywords or len(call.args) > 1:
        unsupported.raise_unsupported(
            call, cause='defaultdict(factory, items) and keyword arguments are not '
                        'translated yet.',
            suggestions=['Make it empty and fill it: d = defaultdict(list), then d[k] = v.'])
    if not call.args:
        unsupported.raise_unsupported(
            call, cause='defaultdict() with no factory is a plain dict that raises '
                        'KeyError; write {} instead.',
            suggestions=['d = {}'])
    f = call.args[0]
    if isinstance(f, ast.Name) and f.id in _FACTORIES:
        return _FACTORIES[f.id]
    if isinstance(f, ast.Lambda) and not f.args.args and isinstance(f.body, ast.Constant) \
            and isinstance(f.body.value, (int, float, str, bool, type(None))):
        return (repr(f.body.value), None)
    if isinstance(f, ast.Name) and f.id == 'set':
        unsupported.raise_unsupported(
            call, cause='defaultdict(set) keeps a set inside a dict, and a set inside a '
                        'dict is not translated yet.',
            suggestions=['Use defaultdict(list) and check with `in` before appending.'])
    unsupported.raise_unsupported(
        call, cause='defaultdict is translated with int, float, str, bool, list or '
                    'dict, or a lambda that gives a constant: lambda: 0.',
        suggestions=['defaultdict(int), defaultdict(list), defaultdict(lambda: "none")'])


class _Kinds(object):
    """What the source says holds a Counter or a defaultdict.

    A kind is 'counter' or ('default', value source, shown name)."""

    def __init__(self, tree):
        self.tree = tree
        self.functions = [n for n in ast.walk(tree)
                          if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self.globals_of = {fn: {n for s in ast.walk(fn) if isinstance(s, ast.Global)
                                for n in s.names} for fn in self.functions}
        self.owner = {}
        for fn in self.functions:
            for node in ast.walk(fn):
                self.owner[id(node)] = fn
        self.module, self.scopes, self.returns, self.fields, self.params = {}, {}, {}, {}, {}
        self._settle()

    def kind(self, node, scope):
        made = _maker(node)
        if made == 'Counter':
            return 'counter'
        if made == 'defaultdict':
            value, shown = _factory(node)
            return ('default', value, shown)
        if isinstance(node, ast.Name):
            return scope.get(node.id)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            return self.fields.get(node.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return self.returns.get(node.func.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == 'copy' and not node.args:
            return self.kind(node.func.value, scope)
        if op_of(node) in DICT_RESULTS:
            return 'counter'
        return None

    def _agree(self, values, scope):
        kinds = {repr(self.kind(v, scope)) if v is not None else None for v in values}
        if len(kinds) == 1 and None not in kinds:
            return self.kind(values[0], scope)
        return None

    def _names(self, values, base):
        names = {}
        for _ in range(4):
            scope = {k: v for k, v in base.items() if k not in values}
            scope.update(names)
            fresh = {}
            for name, vs in values.items():
                if vs and all(v is not None for v in vs):
                    found = self._agree(vs, scope)
                    if found is not None:
                        fresh[name] = found
            if fresh == names:
                break
            names = fresh
        out = {k: v for k, v in base.items() if k not in values}
        out.update(names)
        return out

    def scope_of(self, fn):
        return self.scopes.get(fn, self.module)

    def _settle(self):
        module_values = _bindings(list(self.tree.body))
        for _ in range(5):
            before = repr((self.module, self.returns, self.fields,
                           sorted((id(k), v) for k, v in self.params.items())))
            values = {k: list(v) for k, v in module_values.items()}
            for fn in self.functions:
                inner = _bindings(fn.body)
                for name in self.globals_of[fn]:
                    if name in inner:
                        values.setdefault(name, []).extend(inner[name])
            self.module = self._names(values, {})
            for fn in self.functions:
                inner = _bindings(fn.body)
                local = {n: v for n, v in inner.items() if n not in self.globals_of[fn]}
                args = [a.arg for a in fn.args.args + fn.args.kwonlyargs]
                outer = {k: v for k, v in self.module.items() if k not in args and k not in local}
                outer.update(self.params.get(fn, {}))
                self.scopes[fn] = self._names(local, outer)
            self.returns = {}
            for fn in self.functions:
                values = [n.value for n in ast.walk(fn) if isinstance(n, ast.Return)]
                if values and all(v is not None for v in values):
                    found = self._agree(values, self.scopes[fn])
                    if found is not None:
                        self.returns[fn.name] = found
            stores = {}
            for node in ast.walk(self.tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Attribute):
                            stores.setdefault(target.attr, []).append(node)
            self.fields = {}
            for attr, given in stores.items():
                kinds = {repr(self.kind(n.value, self._scope_at(n))) for n in given}
                if len(kinds) == 1:
                    found = self.kind(given[0].value, self._scope_at(given[0]))
                    if found is not None:
                        self.fields[attr] = found
            calls = {}
            for node in ast.walk(self.tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    calls.setdefault(node.func.id, []).append(node)
            self.params = {}
            for fn in self.functions:
                found = calls.get(fn.name)
                if not found:
                    continue
                kinds = {}
                for i, a in enumerate(fn.args.args):
                    seen = set()
                    for c in found:
                        if len(c.args) <= i or c.keywords:
                            seen.add(None)
                        else:
                            seen.add(repr(self.kind(c.args[i], self._scope_at(c))))
                    if len(seen) == 1 and None not in seen and seen != {'None'}:
                        c = found[0]
                        kinds[a.arg] = self.kind(c.args[i], self._scope_at(c))
                if kinds:
                    self.params[fn] = kinds
            after = repr((self.module, self.returns, self.fields,
                          sorted((id(k), v) for k, v in self.params.items())))
            if after == before:
                break

    def _scope_at(self, node):
        fn = self.owner.get(id(node))
        return self.scopes.get(fn, self.module) if fn is not None else self.module


_SIMPLE = (ast.Name, ast.Constant, ast.Attribute, ast.Subscript, ast.BinOp, ast.UnaryOp,
           ast.JoinedStr, ast.FormattedValue, ast.Tuple) + (
    (ast.Slice,) if isinstance(ast.Slice, type) and issubclass(ast.Slice, ast.expr) else ())
# Calls that answer the same when the key is read a second time.
_PURE_FUNCTIONS = {'str', 'len', 'int', 'float', 'abs', 'round', 'min', 'max', 'ord', 'chr',
                   'bool'}
_PURE_METHODS = {'lower', 'upper', 'strip', 'lstrip', 'rstrip', 'title', 'capitalize',
                 'casefold', 'replace', 'zfill', 'get', 'get_value'}


def _simple_key(node):
    """A key that reads the same twice: names, constants, arithmetic on them,
    and calls that change nothing (w.lower(), len(w))."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            if not (isinstance(func, ast.Name) and func.id in _PURE_FUNCTIONS
                    or isinstance(func, ast.Attribute) and func.attr in _PURE_METHODS):
                return False
        elif isinstance(sub, ast.expr) and not isinstance(sub, _SIMPLE):
            return False
    return True


class _Rewriter(ast.NodeTransformer):
    """One scope's statements, with the names that hold a Counter or a defaultdict."""

    def __init__(self, kinds, scope, at_module):
        self.kinds = kinds
        self.scope = scope
        self.at_module = at_module
        self.module_changed = set()
        self.scope_locals = set()
        self.literals = {}          # module names -> the value written for them

    def kind(self, node):
        return self.kinds.kind(node, self.scope)

    # --- statements --------------------------------------------------------

    def body(self, statements):
        out = []
        for stmt in statements:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.append(stmt)
                continue
            for name in ('body', 'orelse', 'finalbody'):
                if isinstance(getattr(stmt, name, None), list) and getattr(stmt, name) \
                        and isinstance(getattr(stmt, name)[0], ast.stmt):
                    setattr(stmt, name, self.body(getattr(stmt, name)))
            for handler in getattr(stmt, 'handlers', []) or []:
                handler.body = self.body(handler.body)
            out.extend(self._before(stmt))
            # The blocks in it were done above: only its own parts here.
            saved = {name: getattr(stmt, name) for name in ('body', 'orelse', 'finalbody',
                                                             'handlers')
                     if isinstance(getattr(stmt, name, None), list)}
            for name in saved:
                setattr(stmt, name, [])
            done = self.visit(stmt)
            for name, value in saved.items():
                setattr(stmt, name, value)
            out.extend(done if isinstance(done, list) else [done])
        return out

    def _own_parts(self, stmt):
        """The expressions *stmt* runs itself (not those of the blocks in it)."""
        if isinstance(stmt, (ast.If, ast.While)):
            return [stmt.test]
        if isinstance(stmt, (ast.For, ast.AsyncFor)):
            return [stmt.iter]
        if isinstance(stmt, (ast.With, ast.AsyncWith)):
            return [i.context_expr for i in stmt.items]
        if isinstance(stmt, ast.Try) or (hasattr(ast, 'TryStar') and isinstance(stmt, ast.TryStar)):
            return []
        return [stmt]

    def _before(self, stmt):
        """`if k not in d: d[k] = <default>` for each read of a defaultdict."""
        lines, done = [], set()
        for part in self._own_parts(stmt):
            for read, guarded in self._reads(part, False):
                kind = self.kind(read.value)
                if isinstance(stmt, ast.While):
                    _refuse_read(read, 'a while\'s test runs again on each turn')
                if guarded:
                    _refuse_read(read, 'it may not run here (after and/or, in one branch of '
                                       'x if c else y, in a comprehension or a lambda)')
                key = read.slice.value if hasattr(ast, 'Index') and isinstance(
                    read.slice, getattr(ast, 'Index')) else read.slice
                if not _simple_key(key):
                    _refuse_read(read, 'its key is worked out by a call, which the line '
                                       'before it would run a second time')
                mark = ast.dump(read.value) + '|' + ast.dump(key)
                if mark in done:
                    continue
                done.add(mark)
                default = ast.parse(kind[1], mode='eval').body
                target = _loc(ast.Subscript(value=_as_load(read.value), slice=copy.deepcopy(key),
                                            ctx=ast.Store()), stmt)
                test = _loc(ast.Compare(left=copy.deepcopy(key), ops=[ast.NotIn()],
                                        comparators=[_as_load(read.value)]), stmt)
                line = _loc(ast.If(test=test, body=[_loc(ast.Assign(targets=[target],
                                                                    value=default), stmt)],
                                   orelse=[]), stmt)
                lines.append(ast.fix_missing_locations(line))
        return lines

    def _reads(self, node, guarded):
        """(subscript, guarded) for each d[k] of a defaultdict that reads it."""
        if isinstance(node, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp,
                             ast.GeneratorExp)):
            guarded = True
        if isinstance(node, ast.Subscript) and not isinstance(node.ctx, ast.Del) \
                and _is_default(self.kind(node.value)):
            if isinstance(node.ctx, ast.Load):
                yield node, guarded
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Subscript) \
                and _is_default(self.kind(node.target.value)):
            yield node.target, guarded
        if isinstance(node, ast.BoolOp):
            for i, value in enumerate(node.values):
                yield from self._reads(value, guarded or i > 0)
            return
        if isinstance(node, ast.IfExp):
            yield from self._reads(node.test, guarded)
            yield from self._reads(node.body, True)
            yield from self._reads(node.orelse, True)
            return
        for child in ast.iter_child_nodes(node):
            yield from self._reads(child, guarded)

    def _note_change(self, receiver):
        if isinstance(receiver, ast.Name) and receiver.id in self.kinds.module \
                and not self.at_module and receiver.id not in self.scope_locals:
            self.module_changed.add(receiver.id)

    # Nested functions and classes are rewritten with scopes of their own.
    def visit_FunctionDef(self, node):
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        return node

    def visit_Assign(self, node):
        if self.at_module and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in self.kinds.module:
            node.value = _module_value(node.value, self.literals)
            self.literals.pop(node.targets[0].id, None)
            return node
        if self.at_module and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in self.changed:
                self.literals.pop(node.targets[0].id, None)
            else:
                self.literals[node.targets[0].id] = node.value
        if any(isinstance(t, ast.Subscript) for t in node.targets) and self.kind(node.value):
            _refuse_inside(node)
        return self.generic_visit(node)

    def visit_AugAssign(self, node):
        target = node.target
        if isinstance(target, ast.Subscript) and self.kind(target.value) == 'counter':
            # c[k] += n: c[k] = c.get(k, 0) + n
            value = self.visit(node.value)
            read = self._counter_get(target, node)
            return _loc(ast.Assign(targets=[_store_copy(target)],
                                   value=_loc(ast.BinOp(left=read, op=node.op, right=value),
                                              node)), node)
        if isinstance(target, ast.Name) and self.kind(target):
            _refuse_math(node)
        return self.generic_visit(node)

    def visit_Expr(self, node):
        call = node.value
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) \
                and call.func.attr in ('update', 'subtract') \
                and self.kind(call.func.value) == 'counter':
            if self.at_module:
                _refuse_module_change(node)
            if call.keywords or len(call.args) != 1:
                unsupported.raise_unsupported(
                    call, cause='Counter.%s() is translated with one argument.' % call.func.attr,
                    suggestions=['c.%s(items)' % call.func.attr])
            receiver = call.func.value
            sign = 1 if call.func.attr == 'update' else -1
            value = _call('update', [_as_load(receiver), self.visit(call.args[0]),
                                     _loc(ast.Constant(value=sign), node)], node)
            self._note_change(receiver)
            return _loc(ast.Assign(targets=[_store_copy(receiver)], value=value), node)
        return self.generic_visit(node)

    # --- values ------------------------------------------------------------

    def _counter_get(self, sub, like):
        key = sub.slice.value if hasattr(ast, 'Index') and isinstance(
            sub.slice, getattr(ast, 'Index')) else sub.slice
        return _loc(ast.Call(func=_loc(ast.Attribute(value=self.visit(_as_load(sub.value)),
                                                     attr='get', ctx=ast.Load()), like),
                             args=[self.visit(copy.deepcopy(key)), _loc(ast.Constant(value=0), like)],
                             keywords=[]), like)

    def visit_Subscript(self, node):
        if isinstance(node.ctx, ast.Load) and self.kind(node.value) == 'counter':
            return self._counter_get(node, node)
        return self.generic_visit(node)

    def visit_BinOp(self, node):
        if self.kind(node.left) or self.kind(node.right):
            _refuse_math(node)
        return self.generic_visit(node)

    def visit_UnaryOp(self, node):
        if self.kind(node.operand):
            _refuse_math(node)
        return self.generic_visit(node)

    def _holds(self, node):
        return node is not None and self.kind(node) is not None

    def _not_inside(self, values, like):
        if any(self._holds(v) for v in values):
            _refuse_inside(like)

    def visit_List(self, node):
        self._not_inside(node.elts, node)
        return self.generic_visit(node)

    visit_Set = visit_List

    def visit_Tuple(self, node):
        if isinstance(node.ctx, ast.Load):
            self._not_inside(node.elts, node)
        return self.generic_visit(node)

    def visit_Dict(self, node):
        self._not_inside(list(node.values), node)
        return self.generic_visit(node)

    def visit_ListComp(self, node):
        self._not_inside([node.elt], node)
        return self.generic_visit(node)

    def visit_Call(self, node):
        func = node.func
        made = _maker(node)
        if made == 'defaultdict':
            _factory(node)
            return _loc(ast.Dict(keys=[], values=[]), node)
        if made == 'Counter':
            if node.keywords or len(node.args) > 1:
                unsupported.raise_unsupported(
                    node, cause='Counter(a=1) and keyword arguments are not translated yet.',
                    suggestions=['Counter({"a": 1}) or Counter(items)'])
            if not node.args:
                return _loc(ast.Dict(keys=[], values=[]), node)
            return _call('of', [self.visit(node.args[0])], node)
        if isinstance(func, ast.Name) and func.id == 'isinstance' and len(node.args) == 2 \
                and isinstance(node.args[1], ast.Name) \
                and node.args[1].id in ('Counter', 'defaultdict'):
            unsupported.raise_unsupported(
                node, cause='isinstance(x, %s) is not translated: on the phone it is the '
                            'dict it reads like.' % node.args[1].id,
                suggestions=['isinstance(x, dict)'])
        if isinstance(func, ast.Attribute) and func.attr in ('append', 'insert', 'setdefault'):
            self._not_inside(node.args, node)
        if isinstance(func, ast.Attribute) and self.kind(func.value) == 'counter':
            if func.attr == 'most_common':
                if node.keywords or len(node.args) > 1:
                    unsupported.raise_unsupported(
                        node, cause='most_common() takes one number.',
                        suggestions=['c.most_common(3)'])
                n = [self.visit(node.args[0])] if node.args else []
                return _call('most_common', [self.visit(func.value)] + n, node)
            if func.attr == 'total' and not node.args:
                values = _loc(ast.Call(func=_loc(ast.Attribute(value=self.visit(func.value),
                                                               attr='values', ctx=ast.Load()),
                                                 node), args=[], keywords=[]), node)
                return _loc(ast.Call(func=_loc(ast.Name(id='sum', ctx=ast.Load()), node),
                                     args=[values], keywords=[]), node)
            if func.attr in ('elements', 'update', 'subtract'):
                unsupported.raise_unsupported(
                    node, cause='Counter.%s() is translated on a line of its own, not as '
                                'a value.' % func.attr if func.attr != 'elements'
                    else 'Counter.elements() is not translated yet.',
                    suggestions=['for k, n in c.items(): ... n times'] if func.attr == 'elements'
                    else ['c.%s(items) on its own line' % func.attr])
        shows = (isinstance(func, ast.Name) and func.id in _SHOWN_BY) or (
            isinstance(func, ast.Attribute) and func.attr == 'set_value')
        # What each argument is, read before Counter() becomes {}.
        kinds = [self._shown_kind(a) for a in node.args] if shows else []
        node = self.generic_visit(node)
        if shows:
            node.args = [self._shown(a, k) for a, k in zip(node.args, kinds)]
        return node

    def visit_FormattedValue(self, node):
        kind = self._shown_kind(node.value)
        node = self.generic_visit(node)
        node.value = self._shown(node.value, kind)
        return node

    def _shown_kind(self, node):
        if op_of(node):
            return 'counter' if op_of(node) in DICT_RESULTS else None
        return self.kind(node)

    def _shown(self, node, kind):
        if kind == 'counter':
            return _call('show', [node], node)
        if _is_default(kind):
            if kind[2] is None:
                unsupported.raise_unsupported(
                    node, cause='str() of a defaultdict made with a lambda shows where the '
                                'lambda is in memory, defaultdict(<function <lambda> at '
                                '0x...>, ...), which changes on every run.',
                    suggestions=['Show dict(d) instead.'])
            return _call('default_show', [node, _loc(ast.Constant(value=kind[2]), node)], node)
        return node


def _is_default(kind):
    return isinstance(kind, tuple) and kind[0] == 'default'


def _as_load(node):
    node = copy.deepcopy(node)
    for sub in ast.walk(node):
        if hasattr(sub, 'ctx'):
            sub.ctx = ast.Load()
    return node


def _store_copy(node):
    node = _as_load(node)
    node.ctx = ast.Store()
    return node


def _refuse_read(node, why):
    unsupported.raise_unsupported(
        node, cause='Reading a missing key of a defaultdict adds it, and here the line '
                    'that adds it cannot go before the read: %s.' % why,
        suggestions=['Read it on a line of its own first: value = d[k].',
                     'Or read it without adding it: d.get(k, 0).'])


def _refuse_inside(node):
    unsupported.raise_unsupported(
        node, cause='A Counter or a defaultdict inside a list, a tuple or a dict is not '
                    'translated yet: on the phone it is the dict it reads like, and '
                    'inside another value it would show and read as one.',
        suggestions=['Keep it in a name of its own, or put dict(c) in the list.'])


def _refuse_math(node):
    unsupported.raise_unsupported(
        node, cause='Adding, taking away and joining Counters (c + d, c - d, c | d, '
                    'c & d) is not translated yet.',
        suggestions=['c.update(d) adds d to c; c.subtract(d) takes it away.'])


def _refuse_module_change(node):
    unsupported.raise_unsupported(
        node, cause='Changing a Counter at the top of the file is not translated: it '
                    'runs once, when the app starts.',
        suggestions=['Count the items into it: COUNTS = Counter(items), or change it '
                     'inside a function.'])


def _module_value(value, literals):
    """A Counter or a defaultdict at the top of the file, as the dict it starts as."""
    made = _maker(value)
    if made == 'defaultdict':
        _factory(value)
        return _loc(ast.Dict(keys=[], values=[]), value)
    if made == 'Counter' and not value.keywords:
        if not value.args:
            return _loc(ast.Dict(keys=[], values=[]), value)
        arg = value.args[0]
        if isinstance(arg, ast.Name) and arg.id in literals:
            # WORDS = "a b a".split() above it, which module_constants.py
            # wrote out as the list it gives.
            arg = literals[arg.id]
        try:
            import collections
            counted = collections.Counter(ast.literal_eval(arg))
        except Exception:
            counted = None
        if counted is not None:
            keys, values = [], []
            for k, n in counted.items():
                keys.append(_loc(ast.Constant(value=k), value))
                values.append(_loc(ast.Constant(value=n), value))
            return _loc(ast.Dict(keys=keys, values=values), value)
    unsupported.raise_unsupported(
        value, cause='A Counter at the top of the file is translated when what it counts '
                     'is written out, or worked out from values above it.',
        suggestions=['COUNTS = Counter(["tea", "jam", "tea"]), or count inside a function.'])


def uses(tree):
    return any(isinstance(n, ast.Name) and n.id in ('Counter', 'defaultdict')
               or isinstance(n, ast.Attribute) and n.attr in ('Counter', 'defaultdict')
               for n in ast.walk(tree))


def rewrite(tree):
    if not uses(tree):
        return tree
    kinds = _Kinds(tree)
    top = _Rewriter(kinds, kinds.module, at_module=True)
    from .module_constants import _changed_somewhere
    top.changed = _changed_somewhere(tree)
    tree.body = top.body(tree.body)
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        scope = kinds.scope_of(fn)
        rewriter = _Rewriter(kinds, scope, at_module=False)
        args = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
        rewriter.scope_locals = (set(_bindings(fn.body)) | args) - kinds.globals_of.get(fn, set())
        fn.body = rewriter.body(fn.body)
        changed = sorted(rewriter.module_changed - kinds.globals_of.get(fn, set()))
        if changed:
            fn.body.insert(0, _loc(ast.Global(names=changed), fn.body[0]))
    ast.fix_missing_locations(tree)
    return tree
