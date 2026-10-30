# -*- coding: utf-8 -*-
"""Changing an item, written out as giving the name a new value.

    d["k"] = v            d = <d with "k" set to v>
    lista[i] = v          lista = <lista with item i set to v>
    d["k"] += 1           d = <d with "k" set to d["k"] + 1, a number if it was one>
    d["a"]["b"] = v       d = <d with "a" set to <d["a"] with "b" set to v>>
    del lista[0]          lista = <lista without item 0>

On the phone a list or a dict is JSON text, so there is no object to change in
place: the name is given the changed text instead. That is the same thing for
a name of the function. A list or dict of the module is different: Python
changes the one object every function sees, so the function is read as if it
said ``global NAME`` -- the module name then lives in the app's shared store,
which is what ``global`` already does (see _prescan_globals in compiler.py).

A missing key or a position past the end stops the app, as KeyError and
IndexError stop CPython; a slice (``lista[1:3] = ...``) and an attribute
(``obj.x = ...``) are left to the diagnostics, which say they are not
translated.

The methods that change a list are the same thing (phase 1, group 5):

    lista.insert(0, v)    lista = <lista with v in front>
    lista.sort()          lista = <lista sorted>
    item = lista.pop()    item = <the last item>; lista = <lista without it>

They are rewritten only for a name the function itself gives a value to, or a
list or dict of the module -- ``storage.remove(key)`` and ``db.insert(...)``
are the app's own calls and are left alone.
"""

import ast

from .sort_key import KEYS

SETITEM = "__apkpy_setitem__"
DELITEM = "__apkpy_delitem__"
LISTOP = "__apkpy_listop__"

# Methods that change a list (clear and pop a dict too, and update only a
# dict), with how many
# arguments each takes. append on a plain name keeps its own path in the
# compiler (module lists in the shared store, list_view items); here it is
# the append to an item: rows[0]["tags"].append(t).
_MUTATORS = {
    'append': (1, 1), 'insert': (2, 2), 'remove': (1, 1), 'extend': (1, 1),
    'sort': (0, 0), 'reverse': (0, 0), 'clear': (0, 0), 'pop': (0, 2),
    'update': (1, 1),
}
# The ones no object of the app has (tx.insert(), sensors.remove(), ... do):
# on a parameter they can only be a list's, and the parameter is refused.
_ONLY_LISTS = ('sort', 'reverse', 'extend', 'pop')


def _loc(node, like):
    return ast.copy_location(node, like)


def _chain(target):
    """(root name, [key nodes]) for name[k1][k2]..., or None."""
    keys = []
    node = target
    while isinstance(node, ast.Subscript):
        if isinstance(node.slice, ast.Slice):
            return None
        keys.append(node.slice)
        node = node.value
    if not isinstance(node, ast.Name) or not keys:
        return None
    return node.id, list(reversed(keys))


def _read(root, keys, like):
    """name[k1]...[kn] as a value."""
    node = _loc(ast.Name(id=root, ctx=ast.Load()), like)
    for key in keys:
        node = _loc(ast.Subscript(value=node, slice=key, ctx=ast.Load()), like)
    return node


def _set(root, keys, value, like, aug=False):
    """The new value of *root* after root[k1]...[kn] = value."""
    container = _read(root, keys[:-1], like)
    if len(keys) > 1:
        inner = _call(SETITEM, [container, keys[-1], value,
                                _loc(ast.Constant(value=aug), like)], like)
        return _set(root, keys[:-1], inner, like)
    return _call(SETITEM, [container, keys[-1], value,
                           _loc(ast.Constant(value=aug), like)], like)


def _call(func, args, like):
    return _loc(ast.Call(func=_loc(ast.Name(id=func, ctx=ast.Load()), like),
                         args=args, keywords=[]), like)


def _module_containers(tree):
    found = set()
    for node in getattr(tree, 'body', []):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, (ast.List, ast.Dict, ast.Tuple))):
            found.add(node.targets[0].id)
    return found


def _locals(fn):
    """Names *fn* binds itself (parameters and assignments), minus globals."""
    names = {a.arg for a in fn.args.args + fn.args.kwonlyargs
             + getattr(fn.args, 'posonlyargs', [])}
    declared = set()
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            declared.update(node.names)
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.Lambda, ast.ClassDef)):
                stack.append(child)
    return names - declared, declared


def _plain(node):
    """A value read the same however often: a name or one written out."""
    if isinstance(node, (ast.Name, ast.Constant)):
        return True
    return (isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd))
            and isinstance(node.operand, ast.Constant))


class _Rewriter:
    def __init__(self, containers):
        self.containers = containers
        self.changed = False
        self.temps = 0

    def function(self, fn):
        local, declared = _locals(fn)
        self.shared = set()
        self.local = local
        self.params = {a.arg for a in fn.args.args + fn.args.kwonlyargs
                       + getattr(fn.args, 'posonlyargs', [])}
        self.loop_vars = {n.id for loop in ast.walk(fn) if isinstance(loop, ast.For)
                          for n in ast.walk(loop.target) if isinstance(n, ast.Name)}
        fn.body = self.block(fn.body)
        shared = sorted(self.shared - declared)
        if shared:
            fn.body.insert(0, _loc(ast.Global(names=shared), fn.body[0]))

    def note(self, root, stmt):
        if root in self.params or root in self.loop_vars:
            # Python changes the caller's object, or the item of the list
            # being walked. Here a list or a dict is text, so only this copy
            # would change, and the other side would never know.
            from ..unsupported import raise_unsupported
            where = 'a parameter' if root in self.params else 'the variable of a for loop'
            raise_unsupported(
                stmt,
                cause=('%s is %s. CPython changes the original object; on the '
                       'phone a list or a dict is text, so only this copy would '
                       'change.' % (root, where)),
                suggestions=[
                    'Return the changed value and assign it where it came from: '
                    'cart = add_item(cart, name).',
                    'To change the items of a list as you walk it, walk the '
                    'positions: for i in range(len(rows)): rows[i]["done"] = "yes".',
                ],
            )
        if root in self.containers and root not in self.local:
            self.shared.add(root)

    def block(self, statements):
        out = []
        for stmt in statements:
            for field in ('body', 'orelse', 'finalbody'):
                inner = getattr(stmt, field, None)
                if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt) \
                        and not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    setattr(stmt, field, self.block(inner))
            for handler in getattr(stmt, 'handlers', []) or []:
                handler.body = self.block(handler.body)
            out.extend(self.statement(stmt))
        return out

    def _method(self, call):
        """(root, keys, method) for root[k]...method(...) that changes a list."""
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and call.func.attr in _MUTATORS):
            return None
        receiver = call.func.value
        if isinstance(receiver, ast.Name):
            root, keys = receiver.id, []
        else:
            found = _chain(receiver)
            if not found:
                return None
            root, keys = found
        if root not in self.local and root not in self.containers:
            return None        # storage.clear(), db.insert(...): the app's own calls
        if root in self.params and call.func.attr not in _ONLY_LISTS:
            return None        # tx.insert(...) in a Data Core callback: could be anything
        if call.func.attr == 'append' and not keys:
            return None        # the compiler's own append
        low, high = _MUTATORS[call.func.attr]
        if not low <= len(call.args) <= high \
                or any(isinstance(a, ast.Starred) for a in call.args):
            return None        # the wrong number of arguments: the diagnostics say so
        return root, keys, call.func.attr

    def _arguments(self, call, method, stmt):
        """The arguments the rewritten call takes, or None to leave it alone."""
        args = list(call.args)
        if method == 'sort':
            reverse = _loc(ast.Constant(value=False), stmt)
            keys = None
            for kw in call.keywords:
                if kw.arg == KEYS:
                    keys = kw.value          # key=, worked out by features/sort_key.py
                    continue
                if kw.arg == 'key' and isinstance(kw.value, ast.Constant) \
                        and kw.value.value is None:
                    continue
                if kw.arg != 'reverse':
                    from ..unsupported import raise_unsupported
                    raise_unsupported(
                        stmt,
                        cause=('sort(%s=...) is not translated here. sort() takes key= '
                               'and reverse=, and the keys are worked out on a line of '
                               'a def.' % kw.arg),
                        suggestions=['names.sort(key=str.lower, reverse=True), inside a def.'],
                    )
                reverse = kw.value
            return [reverse] + ([keys] if keys is not None else [])
        if call.keywords:
            return None
        if method == 'pop' and not args:
            args = [_loc(ast.Constant(value=-1), stmt)]
        return args

    def _assign(self, root, keys, value, like):
        """root = value, or root = <root with root[k]... set to value>."""
        new = _set(root, keys, value, like) if keys else value
        return _loc(ast.Assign(targets=[_loc(ast.Name(id=root, ctx=ast.Store()), like)],
                               value=new), like)

    def _pop_in_an_expression(self, stmt):
        """xs.pop() anywhere else changes xs and answers the item: one line each."""
        stack = [stmt]
        while stack:
            node = stack.pop()
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == 'pop' and self._method(node):
                from ..unsupported import raise_unsupported
                raise_unsupported(
                    node,
                    cause=('pop() changes the list and answers the item. On the phone '
                           'the changed list is a new value, given back to the name '
                           'on a line of its own, so pop() is translated as a line: '
                           'item = items.pop(), or items.pop().'),
                    suggestions=['Take it in a name first: item = items.pop(), then use item.'],
                )
            for child in ast.iter_child_nodes(node):
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                          ast.Lambda, ast.ClassDef, ast.stmt)):
                    stack.append(child)

    def statement(self, stmt):
        if isinstance(stmt, ast.Expr):
            found = self._method(stmt.value)
            if found:
                root, keys, method = found
                args = self._arguments(stmt.value, method, stmt)
                if args is not None:
                    self.note(root, stmt)
                    self.changed = True
                    op = _call(LISTOP, [_loc(ast.Constant(value=method), stmt),
                                        _read(root, keys, stmt)] + args, stmt)
                    return [self._assign(root, keys, op, stmt)]
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            found = self._method(stmt.value)
            if found and found[2] == 'pop':
                root, keys, _ = found
                args = self._arguments(stmt.value, 'pop', stmt)
                if args is not None:
                    self.note(root, stmt)
                    self.changed = True
                    out = []
                    if not _plain(args[0]):
                        # The position is worked out once, as Python does.
                        self.temps += 1
                        temp = "_apkpy_p%d" % self.temps
                        out.append(_loc(ast.Assign(
                            targets=[_loc(ast.Name(id=temp, ctx=ast.Store()), stmt)],
                            value=args[0]), stmt))
                        args[0] = _loc(ast.Name(id=temp, ctx=ast.Load()), stmt)
                    taken = _call(LISTOP, [_loc(ast.Constant(value='popvalue'), stmt),
                                           _read(root, keys, stmt)] + args, stmt)
                    out.extend(self.statement(_loc(ast.Assign(targets=stmt.targets,
                                                              value=taken), stmt)))
                    gone = _call(LISTOP, [_loc(ast.Constant(value='pop'), stmt),
                                          _read(root, keys, stmt)] + list(args), stmt)
                    out.append(self._assign(root, keys, gone, stmt))
                    return out
        self._pop_in_an_expression(stmt)
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            found = _chain(stmt.targets[0])
            if found:
                root, keys = found
                self.note(root, stmt)
                self.changed = True
                return [_loc(ast.Assign(targets=[_loc(ast.Name(id=root, ctx=ast.Store()), stmt)],
                                        value=_set(root, keys, stmt.value, stmt)), stmt)]
        if isinstance(stmt, ast.AugAssign):
            found = _chain(stmt.target)
            if found:
                root, keys = found
                self.note(root, stmt)
                self.changed = True
                new = _loc(ast.BinOp(left=_read(root, keys, stmt), op=stmt.op,
                                     right=stmt.value), stmt)
                return [_loc(ast.Assign(targets=[_loc(ast.Name(id=root, ctx=ast.Store()), stmt)],
                                        value=_set(root, keys, new, stmt, aug=True)), stmt)]
        if isinstance(stmt, ast.Delete) and stmt.targets:
            chains = [_chain(t) for t in stmt.targets]
            if all(chains):
                out = []
                for root, keys in chains:
                    self.note(root, stmt)
                    gone = _call(DELITEM, [_read(root, keys[:-1], stmt), keys[-1]], stmt)
                    value = _set(root, keys[:-1], gone, stmt) if len(keys) > 1 else gone
                    out.append(_loc(ast.Assign(
                        targets=[_loc(ast.Name(id=root, ctx=ast.Store()), stmt)],
                        value=value), stmt))
                self.changed = True
                return out
        return [stmt]


def desugar(tree):
    """Rewrite item assignment and ``del`` of items in every function body."""
    rewriter = _Rewriter(_module_containers(tree))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rewriter.function(node)
    if rewriter.changed:
        ast.fix_missing_locations(tree)
    return tree
