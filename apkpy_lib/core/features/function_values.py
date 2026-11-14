# -*- coding: utf-8 -*-
"""Functions as values: f = double, [double, inc], {"add": add}, apply(double, 3).

    steps = [double, inc]                  steps = [_apkpy_fn("double"), _apkpy_fn("inc")]
    for f in steps:                        for f in steps:
        n = f(n)                               n = _apkpy_call(f, n)
    actions = {"add": add, "sub": sub}     actions = {"add": _apkpy_fn("add"), ...}
    actions[op](a, b)                      _apkpy_call(actions[op], a, b)
    apply(double, 3)                       apply(_apkpy_fn("double"), 3)

A function handed on as data is kept as its name, the text "double". A call of
a value -- a parameter, a name that holds one, an item, the answer of another
call -- goes through _apkpy_call, which the compiler writes as a switch over the
functions handed on (_apkpyCall), with Python's TypeError when the number of
arguments is wrong. The calls that go through it count as calls of each of
those functions when the compiler decides which parameters are numbers.

Only where a value is data: the right of `=`, a list, a tuple or a dict
written out, `return`, `==`, and the arguments of the app's own functions. A
function given to ApkPy (command=go, timer.every(1, tick), key=len) keeps its
name, as it did.

What is refused, and why:
- str(f), print(f), f"{f}": CPython shows where the function is in memory,
  <function double at 0x...>, which changes on every run;
- a value called with keyword arguments (f(x=1)): which function it is, and so
  which parameter x is, is known only when the app runs;
- a function with a default value that is not a number or text, handed on.
"""

import ast
import builtins

from .. import unsupported
from . import signatures

FN = "_apkpy_fn"
# Not _apkpy_call: the classes pass has _apkpy_call_<method> of its own.
CALL = "_apkpy_fncall"

_SHOWN_BY = {'str', 'repr', 'print', 'toast'}
# Python's own calls: a list of functions given to them is still data.
_PYTHON_CALLS = {'len', 'list', 'tuple', 'reversed', 'sorted', 'enumerate', 'zip', 'str',
                 'repr', 'print', 'any', 'all', 'min', 'max', 'dict'}


def _loc(node, like):
    return ast.copy_location(node, like)


TARGETS = "_apkpy_fn_targets"


def targets(tree):
    """The names of the functions handed on as values."""
    found = set(getattr(tree, TARGETS, ()))
    found.update(n.args[0].value for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == FN
                 and n.args and isinstance(n.args[0], ast.Constant))
    return found


def _bound(statements, params):
    """Names given a value in these statements (not the ones of inner defs)."""
    out = set(params)
    stack = list(statements)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            out.add(node.id)
        stack.extend(ast.iter_child_nodes(node))
    return out


def _generated(name):
    """A name another pass of ApkPy wrote (a native block, a class's helper)."""
    return name.startswith('_apkpy') or name.startswith('__apkpy')


def _callables(statements, params, defs, outer):
    """Names a call of which can be a call of a function kept in a value: the
    parameters, and the names given a function, an item of a list or dict of
    them, the answer of one of the app's functions, or a for over them."""
    found = {p for p in params if not _generated(p)}

    def may_be(node):
        if isinstance(node, ast.Name):
            return node.id in defs and not _generated(node.id) or node.id in found \
                or node.id in outer
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return any(may_be(e) for e in node.elts)
        if isinstance(node, ast.Dict):
            return any(may_be(v) for v in node.values)
        if isinstance(node, ast.Subscript):
            return may_be(node.value)
        if isinstance(node, ast.IfExp):
            return may_be(node.body) or may_be(node.orelse)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return node.func.id in defs and not _generated(node.func.id)
        return False

    for _ in range(3):
        for node in _own(statements):
            if isinstance(node, ast.Assign) and may_be(node.value):
                found.update(t.id for t in node.targets
                             if isinstance(t, ast.Name) and not _generated(t.id))
            elif isinstance(node, (ast.For, ast.comprehension)) \
                    and isinstance(node.target, ast.Name) and may_be(node.iter):
                found.add(node.target.id)
    return found


class _Rewriter(ast.NodeTransformer):
    def __init__(self, defs, variables, module_variables, at_module=False, callables=()):
        self.callables = set(callables)
        self.at_module = at_module
        self.defs = defs
        self.variables = variables            # names that can hold a value here
        self.module_variables = module_variables
        self.holders = set()                  # names given a function here
        self.handed = set()                   # the functions written as text
        # Inside the arguments of a call that is not the app's own --
        # app_bar(actions=[("Save", save)]): what ApkPy reads there keeps
        # the function's name.
        self.api_depth = 0

    def _fn(self, node):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) \
                and node.id in self.defs and node.id not in self.variables \
                and not _generated(node.id):
            fn = self.defs[node.id]
            for default in fn.args.defaults:
                if not (isinstance(default, ast.Constant)
                        and isinstance(default.value, (int, float, str))
                        and not isinstance(default.value, bool)):
                    unsupported.raise_unsupported(
                        node, cause='%s() is handed on as a value, and its default values '
                                    'go in when the app runs, from the call: only a number '
                                    'or text can.' % node.id,
                        suggestions=['Give the call every argument, and take the default '
                                     'out.'])
            self.handed.add(node.id)
            call = ast.Call(func=ast.Name(id=FN, ctx=ast.Load()),
                            args=[ast.Constant(value=node.id)], keywords=[])
            return ast.fix_missing_locations(_loc(call, node))
        return None

    def _value(self, node):
        made = self._fn(node)
        return made if made is not None else self.visit(node)

    def _holds(self, node):
        return self._fn_value(node) or (isinstance(node, ast.Name) and node.id in self.holders)

    def _fn_value(self, node):
        if isinstance(node, ast.Name) and node.id in self.defs and node.id not in self.variables:
            return True
        if isinstance(node, (ast.List, ast.Tuple)):
            return any(self._fn_value(e) for e in node.elts)
        if isinstance(node, ast.Dict):
            return any(self._fn_value(v) for v in node.values)
        return False

    def _called_value(self, func):
        """f(x), steps[i](n), pick("x")(1): a call of a function kept in a value."""
        if isinstance(func, ast.Name):
            return func.id in self.callables and func.id not in self.defs
        if isinstance(func, ast.Subscript):
            root = func.value
            while isinstance(root, ast.Subscript):
                root = root.value
            return isinstance(root, ast.Name) and root.id in self.callables
        if isinstance(func, ast.Call) and isinstance(func.func, ast.Name):
            return func.func.id in self.defs and not _generated(func.func.id) \
                or is_call_name(func.func.id)
        return False

    def visit_FunctionDef(self, node):
        return node                     # rewritten with its own names

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        return node

    def visit_Assign(self, node):
        if self._holds(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.holders.add(target.id)
        node.value = self._value(node.value)
        node.targets = [self.visit(t) for t in node.targets]
        return node

    def visit_Return(self, node):
        if node.value is not None:
            node.value = self._value(node.value)
        return node

    def _item(self, node):
        # app_bar(actions=[("Save", save)]): ApkPy reads that list itself.
        return self.visit(node) if self.api_depth else self._value(node)

    def visit_List(self, node):
        node.elts = [self._item(e) for e in node.elts]
        return node

    visit_Tuple = visit_List
    visit_Set = visit_List

    def visit_Dict(self, node):
        node.keys = [self.visit(k) if k is not None else None for k in node.keys]
        node.values = [self._item(v) for v in node.values]
        return node

    def visit_Compare(self, node):
        node.left = self._value(node.left)
        node.comparators = [self._value(c) for c in node.comparators]
        return node

    def visit_FormattedValue(self, node):
        if self._holds(node.value):
            _refuse_shown(node)
        return self.generic_visit(node)

    def visit_Call(self, node):
        func = node.func
        shows = isinstance(func, ast.Name) and func.id in _SHOWN_BY and func.id not in self.defs \
            or isinstance(func, ast.Attribute) and func.attr == 'set_value'
        if shows and any(self._holds(a) for a in node.args):
            _refuse_shown(node)
        own = isinstance(func, ast.Name) and func.id in self.defs \
            and func.id not in self.variables
        called_value = self._called_value(func)
        depth = self.api_depth
        if own or called_value:
            self.api_depth = 0
            node.args = [self._value(a) for a in node.args]
            for keyword in node.keywords:
                keyword.value = self._value(keyword.value)
        else:
            builtin = isinstance(func, ast.Name) and func.id in _PYTHON_CALLS
            self.api_depth = 0 if builtin else depth + 1
            node.args = [self.visit(a) for a in node.args]
            for keyword in node.keywords:
                keyword.value = self.visit(keyword.value)
        self.api_depth = depth
        if isinstance(func, (ast.Subscript, ast.Call)):
            node.func = self.visit(func)
        if called_value:
            if any(isinstance(a, ast.Starred) for a in node.args) or node.keywords:
                unsupported.raise_unsupported(
                    node, cause='A function kept in a value, called with keyword arguments '
                                'or *items: which function it is, and so which parameter '
                                'each argument fills, is known only when the app runs.',
                    suggestions=['Pass the arguments in order: f(a, b).'])
            call = ast.Call(func=ast.Name(id=CALL, ctx=ast.Load()),
                            args=[node.func] + node.args, keywords=[])
            return ast.fix_missing_locations(_loc(call, node))
        return node


class _AsText(ast.NodeTransformer):
    def visit_Call(self, node):
        node = self.generic_visit(node)
        if internal(node) == FN:
            return _loc(ast.Constant(value=node.args[0].value), node)
        return node


def _refuse_shown(node):
    unsupported.raise_unsupported(
        node, cause='str() of a function shows where it is in memory, <function double at '
                    '0x...>, which changes on every run.',
        suggestions=['Show its name instead: keep the names in a list next to the functions.'])


def rewrite(tree):
    defs = {n.name: n for n in getattr(tree, 'body', []) if isinstance(n, ast.FunctionDef)}
    if not defs:
        return tree
    taken = set(dir(builtins))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            taken.update((a.asname or a.name).split('.')[0] for a in node.names)
        elif isinstance(node, ast.ClassDef):
            taken.add(node.name)
    module_variables = _bound([s for s in tree.body
                               if not isinstance(s, (ast.FunctionDef, ast.ClassDef))], ()) - taken
    # A name a function binds in one place and is a def elsewhere is a value
    # where it is bound.
    module_statements = [s for s in tree.body
                         if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef,
                                               ast.ClassDef))]
    module_callables = _callables(module_statements, (), defs, set())
    top = _Rewriter(defs, module_variables, module_variables, at_module=True,
                    callables=module_callables)
    for i, stmt in enumerate(tree.body):
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            tree.body[i] = top.visit(stmt)
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        a = fn.args
        params = [p.arg for p in list(getattr(a, 'posonlyargs', [])) + a.args + a.kwonlyargs]
        if _generated(fn.name):
            continue                    # written by ApkPy: no values of the app's
        local = _bound(fn.body, params) - taken
        variables = local | module_variables
        outer = module_callables - local
        rewriter = _Rewriter(defs, variables, module_variables,
                             callables=_callables(fn.body, params, defs, outer) | outer)
        rewriter.holders = set(top.holders) - local
        fn.body = [rewriter.visit(stmt) for stmt in fn.body]
    _mark_reach(tree, defs)
    # STEPS = [double, inc] at the top of the file: a list it writes out, of
    # the names (the generators know a list of text).
    for i, stmt in enumerate(tree.body):
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            tree.body[i] = _AsText().visit(stmt)
    setattr(tree, TARGETS, set(top.handed))
    found = targets(tree)
    for name in found:
        fn = defs.get(name)
        # signatures.py has made *_ and **_ plain lists by now: DROPPED says
        # which took them. Through a value, any number of values would reach
        # the one the method has, and _apkpyCall would raise a TypeError
        # Python does not.
        if fn is not None and (fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs
                               or name in signatures.DROPPED):
            unsupported.raise_unsupported(
                fn, cause='%s() is handed on as a value, and it has *args, **kwargs or '
                          'parameters after *: the call through the value fills them in '
                          'order only.' % name,
                suggestions=['Give it plain parameters: def %s(a, b).' % name])
    ast.fix_missing_locations(tree)
    return tree


REACH = "_apkpy_reach"


def _own(statements):
    stack = list(statements)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def _mark_reach(tree, defs):
    """Each f(x) of a value gets the functions that can reach it (REACH):
    those written where f got its value -- f = double, for f in STEPS, a
    parameter given apply(double, ...), the returns of pick() -- so that
    say("hi") does not count as a call of double with text."""
    functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    scopes = [(None, [s for s in tree.body if not isinstance(s, (ast.FunctionDef,
                                                                 ast.ClassDef))])]
    scopes += [(fn, fn.body) for fn in functions]
    nodes = {fn: list(_own(body)) for fn, body in scopes}
    names = {fn: {} for fn, _ in scopes}
    returns = {fn.name: set() for fn in functions}
    by_name = {fn.name: fn for fn in functions if fn.name in defs}

    def fns(node, scope):
        if internal(node) == FN:
            return {node.args[0].value}
        if isinstance(node, ast.Name):
            found = names[scope].get(node.id)
            if found is None and scope is not None:
                found = names[None].get(node.id)
            return set(found or ())
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return set().union(*[fns(e, scope) for e in node.elts]) if node.elts else set()
        if isinstance(node, ast.Dict):
            return set().union(*[fns(v, scope) for v in node.values]) if node.values else set()
        if isinstance(node, ast.Subscript):
            return fns(node.value, scope)
        if isinstance(node, ast.IfExp):
            return fns(node.body, scope) | fns(node.orelse, scope)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in returns:
                return set(returns[node.func.id])
            if is_call_name(node.func.id) and node.args:
                out = set()
                for target in fns(node.args[0], scope):
                    out |= returns.get(target, set())
                return out
        return set()

    def give(scope, name, found):
        if found:
            names[scope].setdefault(name, set()).update(found)

    for _ in range(6):
        before = repr(sorted((id(k) if k else 0, sorted((n, sorted(v)) for n, v in m.items()))
                             for k, m in names.items())) + repr(sorted(
                                 (k, sorted(v)) for k, v in returns.items()))
        for scope, _body in scopes:
            for node in nodes[scope]:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            give(scope, target.id, fns(node.value, scope))
                elif isinstance(node, (ast.For, ast.comprehension)) \
                        and isinstance(node.target, ast.Name):
                    give(scope, node.target.id, fns(node.iter, scope))
                elif isinstance(node, ast.Return) and scope is not None and node.value is not None:
                    returns[scope.name] |= fns(node.value, scope)
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    callees = [by_name[node.func.id]] if node.func.id in by_name else []
                    args = node.args
                    if is_call_name(node.func.id) and node.args:
                        callees = [by_name[t] for t in fns(node.args[0], scope) if t in by_name]
                        args = node.args[1:]
                    for callee in callees:
                        params = [a.arg for a in callee.args.args]
                        for param, arg in zip(params, args):
                            give(callee, param, fns(arg, scope))
                        for keyword in node.keywords:
                            if keyword.arg in params:
                                give(callee, keyword.arg, fns(keyword.value, scope))
        after = repr(sorted((id(k) if k else 0, sorted((n, sorted(v)) for n, v in m.items()))
                            for k, m in names.items())) + repr(sorted(
                                (k, sorted(v)) for k, v in returns.items()))
        if after == before:
            break
    groups = {}
    for scope, _body in scopes:
        for node in nodes[scope]:
            if internal(node) == CALL and node.args:
                found = fns(node.args[0], scope)
                if found:
                    setattr(node, REACH, found)
                    # One name per group of functions, so the compiler can
                    # say what a call of that group answers.
                    key = tuple(sorted(found))
                    groups.setdefault(key, "%s_%d" % (CALL, len(groups) + 1))
                    node.func.id = groups[key]


def reach(node, every):
    """The functions a call of a value can be: what _mark_reach found, or all."""
    return getattr(node, REACH, None) or every


def is_call_name(name):
    """CALL, or CALL_<n> for the calls one group of functions reaches."""
    return name == CALL or (name.startswith(CALL + "_") and name[len(CALL) + 1:].isdigit())


def internal(node):
    """FN or CALL for one of this pass's calls, else None."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == FN:
            return FN
        if is_call_name(node.func.id):
            return CALL
    return None
