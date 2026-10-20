# -*- coding: utf-8 -*-
"""Tuples: kept as the list they read like, shown and guarded as tuples.

On the phone a tuple is the JSON list a list is, and reading one is the same:
``pair[0]``, ``len(pair)``, ``for x in pair``, ``x in pair`` and ``a, b = pair``.
Two things are not, and this pass finds the names they apply to:

* ``str()`` of a tuple is ``(1, 2)``, and ``(1,)`` with one item, where a list
  shows ``[1, 2]``. The nodes that read a tuple are marked, and the compiler
  shows them with ``_apkpyShowTuple``.
* A tuple cannot change. CPython stops ``pair[0] = 5`` with a TypeError and
  ``pair.append(3)`` with an AttributeError; here either would quietly change
  the text, so the build stops with the same words.

A value is a tuple when the source says so: a tuple written out, ``tuple(...)``,
a name every assignment of which gives one, a call of a function whose every
``return`` gives one, the variable of a ``for`` over a list of tuples written
out (``PAIRS = [(1, 2), (3, 4)]``), and an item of such a list. ``tuple(x)``
becomes ``list(x)``, marked: the same copy, shown with round brackets.

A tuple inside a list or another tuple is shown with square brackets: the JSON
does not say which inner lists were tuples.
"""

import ast

TUPLE = "_apkpy_tuple"

_MUTATORS = ('append', 'extend', 'insert', 'pop', 'remove', 'sort',
             'reverse', 'clear')


def is_tuple(node):
    """True when the source proves *node* is a tuple."""
    return isinstance(node, ast.Tuple) or bool(getattr(node, TUPLE, False))


def _scopes(tree):
    """(name, statements, params) for the top of the file and each function."""
    out = [(None, [s for s in tree.body
                   if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))], set())]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            params = {a.arg for a in args.args + args.kwonlyargs
                      + getattr(args, 'posonlyargs', [])}
            if args.vararg:
                params.add(args.vararg.arg)
            if args.kwarg:
                params.add(args.kwarg.arg)
            out.append((node.name, node.body, params))
    return out


def _walk_scope(statements):
    """Every node of *statements*, without going into nested functions."""
    stack = list(reversed(statements))
    while stack:
        node = stack.pop()
        yield node
        for child in reversed(list(ast.iter_child_nodes(node))):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.Lambda, ast.ClassDef)):
                stack.append(child)


class _Loop:
    """The binding of a for loop's variable: one item of *it* at a time."""

    def __init__(self, it):
        self.it = it


def _bindings(statements):
    """{name: [value]} for every way *statements* bind a name.

    The value is the assigned node, a _Loop for a for loop's variable, or None
    for a binding that says nothing: an unpacking, ``+=``, ``with ... as``,
    ``except ... as``."""
    found = {}

    def bind(target, value):
        if isinstance(target, ast.Name):
            found.setdefault(target.id, []).append(value)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                bind(elt.value if isinstance(elt, ast.Starred) else elt, None)

    for node in _walk_scope(statements):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                bind(target, node.value if isinstance(target, ast.Name) else None)
        elif isinstance(node, ast.AugAssign):
            bind(node.target, None)
        elif isinstance(node, ast.AnnAssign):
            bind(node.target, node.value)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            bind(node.target, _Loop(node.iter) if isinstance(node.target, ast.Name) else None)
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            bind(node.optional_vars, None)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            found.setdefault(node.name, []).append(None)
        elif isinstance(node, ast.NamedExpr):
            bind(node.target, node.value)
    return found


def _tuples_written_out(node):
    """[(1, 2), (3, 4)]: a list or tuple written out, every item a tuple."""
    return (isinstance(node, (ast.List, ast.Tuple)) and bool(node.elts)
            and all(isinstance(e, ast.Tuple) for e in node.elts))


def _changed_names(tree):
    """Names some code changes in place: an append, an item set, a +=."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in _MUTATORS and isinstance(node.func.value, ast.Name):
            out.add(node.func.value.id)
        elif isinstance(node, (ast.Assign, ast.AugAssign, ast.Delete)):
            targets = node.targets if isinstance(node, (ast.Assign, ast.Delete)) else [node.target]
            for target in targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
                    out.add(target.value.id)
                if isinstance(node, ast.AugAssign) and isinstance(target, ast.Name):
                    out.add(target.id)
    return out


class _Facts:
    def __init__(self, tree):
        self.scopes = _scopes(tree)
        self.functions = set()               # every return gives a tuple
        self.names = {}                      # scope -> names that hold a tuple
        self.lists = {}                      # scope -> names that hold tuples only
        self.globals = {}                    # scope -> names declared global
        self.changed = _changed_names(tree)
        for name, statements, _params in self.scopes:
            self.globals[name] = {n for node in _walk_scope(statements)
                                  if isinstance(node, ast.Global) for n in node.names}
        rebound = {n for scope, statements, _p in self.scopes if scope is not None
                   for n in self.globals.get(scope, set()) if n in _bindings(statements)}
        for name, statements, params in self.scopes:
            bindings = _bindings(statements)
            self.lists[name] = {n for n, values in bindings.items()
                                if n not in params and n not in self.changed and values
                                and all(_tuples_written_out(v) for v in values)}
        self.lists[None] -= rebound
        self.rebound = rebound

    def from_module(self, scope, bindings, names):
        """*names* of the top of the file a function reads and never binds."""
        if scope is None:
            return set()
        return {n for n in names if n not in bindings}

    def visible_lists(self, scope, bindings):
        return self.lists.get(scope, set()) | self.from_module(scope, bindings, self.lists[None])

    def tuple_items(self, node, lists):
        """True when every item of *node* is a tuple."""
        return _tuples_written_out(node) or (isinstance(node, ast.Name) and node.id in lists)

    def valued(self, node, local, lists):
        if isinstance(node, _Loop):
            return self.tuple_items(node.it, lists)
        if isinstance(node, ast.Tuple):
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            if node.func.id == 'tuple' and len(node.args) <= 1:
                return True
            return node.func.id in self.functions
        if isinstance(node, ast.Name):
            return node.id in local
        if isinstance(node, ast.Subscript) and not isinstance(node.slice, ast.Slice):
            return self.tuple_items(node.value, lists)
        return False

    def solve(self):
        for _ in range(8):
            before = (set(self.functions), {k: set(v) for k, v in self.names.items()})
            for name, statements, params in self.scopes:
                bindings = _bindings(statements)
                lists = self.visible_lists(name, bindings)
                inherited = self.from_module(name, bindings, self.names.get(None, set()))
                local = set()
                for _ in range(4):
                    grown = {n for n, values in bindings.items()
                             if n not in params and values
                             and all(v is not None and self.valued(v, local | inherited, lists)
                                     for v in values)}
                    if grown == local:
                        break
                    local = grown
                if name is None:
                    # A function that rebinds one with `global` may give it
                    # anything: not a tuple any more.
                    local -= self.rebound
                self.names[name] = local
            for name, statements, _params in self.scopes:
                if name is None:
                    continue
                bindings = _bindings(statements)
                visible = self.names[name] | self.from_module(name, bindings, self.names[None])
                lists = self.visible_lists(name, bindings)
                returns = [n.value for n in _walk_scope(statements) if isinstance(n, ast.Return)]
                if returns and all(v is not None and self.valued(v, visible, lists) for v in returns):
                    self.functions.add(name)
                else:
                    self.functions.discard(name)
            if before == (self.functions, self.names):
                break


def _refuse(node, cause):
    from ..unsupported import raise_unsupported
    raise_unsupported(
        node, cause=cause,
        suggestions=['For values that change, use a list: pair = [1, 2].'])


def mark(tree):
    """Mark the nodes that read a tuple, and stop on a change to one."""
    if not any(isinstance(n, ast.Tuple) and isinstance(getattr(n, 'ctx', None), ast.Load)
               or isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'tuple'
               for n in ast.walk(tree)):
        return tree
    facts = _Facts(tree)
    facts.solve()
    for name, statements, params in facts.scopes:
        bindings = _bindings(statements)
        held = (facts.names.get(name, set())
                | facts.from_module(name, bindings, facts.names[None])) - params
        lists = facts.visible_lists(name, bindings)
        for node in _walk_scope(statements):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
                if node.func.id == 'tuple' and len(node.args) <= 1:
                    node.func.id = 'list'
                    setattr(node, TUPLE, True)
                elif node.func.id in facts.functions:
                    setattr(node, TUPLE, True)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in held:
                setattr(node, TUPLE, True)
            elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load) \
                    and not isinstance(node.slice, ast.Slice) and facts.tuple_items(node.value, lists):
                setattr(node, TUPLE, True)
        for node in _walk_scope(statements):
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.Delete)):
                targets = node.targets if isinstance(node, (ast.Assign, ast.Delete)) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) \
                            and target.value.id in held:
                        _refuse(node, ("'tuple' object does not support item %s: a tuple "
                                       "cannot change, and CPython stops here with a TypeError."
                                       % ('deletion' if isinstance(node, ast.Delete) else 'assignment')))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in _MUTATORS and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id in held:
                _refuse(node, ("'tuple' object has no attribute '%s': a tuple cannot change, "
                               "and CPython stops here with an AttributeError." % node.func.attr))
    return tree


__all__ = ["mark", "is_tuple", "TUPLE"]
