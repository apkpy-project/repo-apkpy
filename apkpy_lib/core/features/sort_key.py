# -*- coding: utf-8 -*-
"""sorted(..., key=...), list.sort(key=...), min() and max() with key=: the keys first.

    top = sorted(rows, key=lambda r: r["score"], reverse=True)

becomes

    _apkpy_s1 = rows
    top = sorted(_apkpy_s1, _apkpy_keys=[__apkpy_sortkey__(r["score"])
                                         for r in _apkpy_s1], reverse=True)

and features/comprehensions.py works the keys out on the line before, as it
does for any comprehension. The compiler then orders the items by those keys
(_apkpySortBy, _apkpyExtremeBy): the items never pass through a list of
Python, so a number stays a number and a dict stays a dict.

A key is a lambda of one parameter, the name of a function (len, str, a def
of the app, a lambda kept in a name), a method of str (str.lower), or a
bound method such as d.get. key=None is no key at all.

Python works the key out once per item, and so does this: the keys are one
list, built once. The list is put in a name of its own first (_apkpy_sN), so
sorted(load(), key=f) calls load() once, and the keys and the items are read at
the same moment.

slots = max(groups, key=len) if groups else [] (or return ... if ... else ...)
is first split into an if and an else of a line each, so only the branch
Python reaches works its keys out.

What is refused, with U2033, and why:
- at the top of the file or of a class, and inside a lambda: the keys are a
  loop, and loops are translated in a def;
- a key that is worked out by a call (key=make_key()), or a lambda that does
  not take exactly one parameter;
- on the right of and/or, in a branch of x if c else y inside a larger
  expression, and in the test of a while, where a line before would run it
  at the wrong time; and a list worked out by a call inside a comprehension;
- max(a, b, key=f, default=x): CPython refuses it too (TypeError).

Runs before features/classes.py, so obj.price in a key is read like the
field of any item of the list, and before features/comprehensions.py.
"""

import ast
import copy

# The keyword the compiler reads (_sorted_java, _extreme_by_java) and
# features/item_assignment.py passes on for list.sort().
KEYS = "_apkpy_keys"
# Around each key in that list: the compiler appends it keeping its type, a
# float as a number too (_emit_list_append), since keys are compared and never
# shown.
SORTKEY = "__apkpy_sortkey__"

_HOLDER = "_apkpy_s"
_ITEM = "_apkpy_k"
_BUILTINS = ('sorted', 'min', 'max')
_VIEWS = ('items', 'keys', 'values')

# Where a line before is not possible, as the message says it.
_RIGHT_OF_AND_OR = 'On the right of and/or, which Python reaches only sometimes'
_IF_ELSE_BRANCH = 'In a branch of x if c else y, which Python reaches only sometimes'
_WHILE_TEST = 'In the test of a while, asked again on every turn'
_IN_COMPREHENSION = 'Inside a comprehension, worked out once per item'
_GUARDED = (_RIGHT_OF_AND_OR, _IF_ELSE_BRANCH, _WHILE_TEST)


def _loc(node, like):
    return ast.copy_location(node, like)


def _name(name, like, ctx=None):
    return _loc(ast.Name(id=name, ctx=ctx or ast.Load()), like)


def _refuse(node, cause, tip):
    from ..unsupported import raise_unsupported
    raise_unsupported(node, cause=cause, suggestions=[tip])


def _keyword(call, name):
    for kw in call.keywords:
        if kw.arg == name:
            return kw
    return None


def _slice(node):
    """The index of a subscript, also as Python 3.8 wraps it (ast.Index)."""
    s = node.slice
    return s.value if type(s).__name__ == 'Index' else s


def _pure(node):
    """Whether reading *node* twice gives the same: a name, a field, an item."""
    if isinstance(node, (ast.Name, ast.Constant)):
        return True
    if isinstance(node, ast.Attribute):
        return _pure(node.value)
    if isinstance(node, ast.Subscript):
        s = _slice(node)
        if isinstance(s, ast.Slice):
            parts = [p for p in (s.lower, s.upper, s.step) if p is not None]
            return _pure(node.value) and all(_pure(p) for p in parts)
        return _pure(node.value) and _pure(s)
    if isinstance(node, (ast.Tuple, ast.List)):
        return all(_pure(e) for e in node.elts)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return _pure(node.operand)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in _VIEWS and not node.args and not node.keywords:
        return _pure(node.func.value)
    return False


def _outside_defs(node):
    """*node* and what is under it, without going into a def or a class (they have their turn)."""
    stack = [node]
    while stack:
        sub = stack.pop()
        if sub is not node and isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                ast.ClassDef)):
            continue
        stack.extend(ast.iter_child_nodes(sub))
        yield sub


class _Rewriter:
    def __init__(self, own_sort):
        self.count = 0
        self.changed = False
        # A class of the file with a method called sort: obj.sort(key=...)
        # could be that one, so list.sort(key=...) is left alone.
        self.own_sort = own_sort

    def fresh(self):
        self.count += 1
        return "%s%d" % (_HOLDER, self.count)

    def kind(self, call):
        """'sorted', 'min', 'max' or 'sort' for a call with key=, else None."""
        if not isinstance(call, ast.Call) or _keyword(call, 'key') is None:
            return None
        if isinstance(call.func, ast.Name) and call.func.id in _BUILTINS:
            return call.func.id
        if isinstance(call.func, ast.Attribute) and call.func.attr == 'sort' \
                and not self.own_sort:
            return 'sort'
        return None

    # the keys ------------------------------------------------------------------

    def keys(self, key, items, like):
        """[the key of each item for each item of *items*]."""
        if isinstance(key, ast.Lambda):
            a = key.args
            params = list(getattr(a, 'posonlyargs', [])) + list(a.args)
            if len(params) != 1 or a.vararg or a.kwarg or a.kwonlyargs or a.defaults:
                _refuse(key, 'The key of a sort is called with one item at a time, so '
                             'its lambda takes exactly one parameter.',
                        'key=lambda item: item["price"]')
            target, element = params[0].arg, copy.deepcopy(key.body)
        elif isinstance(key, ast.Attribute) and isinstance(key.value, ast.Name) \
                and key.value.id == 'str':
            # key=str.lower: each item's own method.
            target = _ITEM
            element = _loc(ast.Call(func=_loc(ast.Attribute(
                value=_name(_ITEM, key), attr=key.attr, ctx=ast.Load()), key),
                args=[], keywords=[]), key)
        elif isinstance(key, (ast.Name, ast.Attribute)) and _pure(key):
            target = _ITEM
            element = _loc(ast.Call(func=copy.deepcopy(key), args=[_name(_ITEM, key)],
                                    keywords=[]), key)
        else:
            _refuse(key, 'This key is worked out by an expression, and a function made '
                         'while the app runs is not translated. A key is a lambda, the '
                         'name of a function, or a method of str such as str.lower.',
                    'Write the key as a lambda: key=lambda item: item["price"].')
        element = _loc(ast.Call(func=_name(SORTKEY, like), args=[element], keywords=[]), like)
        return _loc(ast.ListComp(elt=element, generators=[ast.comprehension(
            target=_name(target, like, ast.Store()), iter=copy.deepcopy(items),
            ifs=[], is_async=0)]), like)

    def rewrite(self, call, before, where):
        """*call* with _apkpy_keys=[...] in place of key=; a list worked out goes to *before*."""
        kind = self.kind(call)
        key = _keyword(call, 'key')
        others = [kw for kw in call.keywords if kw is not key]
        self.changed = True
        if isinstance(key.value, ast.Constant) and key.value.value is None:
            call.keywords = others          # key=None: no key
            return call
        if kind == 'sort':
            items = call.func.value
            if not _pure(items) or call.args:
                _refuse(call, 'sort() with key= sorts a list kept in a name, a field or '
                              'an item; this one is worked out on the spot.',
                        'Keep the list in a name first: rows = load(), then '
                        'rows.sort(key=...).')
        else:
            if any(isinstance(a, ast.Starred) for a in call.args) or not call.args \
                    or (kind == 'sorted' and len(call.args) != 1):
                return call                 # the compiler says what is wrong
            if len(call.args) > 1:
                if _keyword(call, 'default') is not None:
                    _refuse(call, 'Python does not take default= when the items are '
                                  'given one by one (TypeError).',
                            'Give a list instead: %s([a, b], key=..., default=...).' % kind)
                call.args = [_loc(ast.List(elts=call.args, ctx=ast.Load()), call)]
            items = call.args[0]
            if where is not None and (where in _GUARDED or not _pure(items)):
                _refuse(call, 'The keys of %s() are worked out first, on the line before. '
                              '%s, a line before would run it at the wrong time.'
                        % (kind, where),
                        'Work it out inside the loop and break: while True: ... '
                        'if not ordered: break.' if where == _WHILE_TEST else
                        'Work it out on a line of its own first: '
                        'ordered = %s(rows, key=...), then use ordered.' % kind)
            if where is None:
                # The items are read where the keys are worked out: a call
                # earlier in the line (shelf.by_qty()) could reorder them
                # in between, and each key would go to another item.
                holder = self.fresh()
                before.append(_loc(ast.Assign(targets=[_name(holder, call, ast.Store())],
                                              value=items), call))
                items = _name(holder, call)
                call.args = [items]
        call.keywords = [_loc(ast.keyword(arg=KEYS, value=self.keys(key.value, items, call)),
                              call)] + others
        return call

    # finding them -----------------------------------------------------------------

    def refuse_inside(self, node, place, tip):
        for sub in _outside_defs(node):
            if self.kind(sub):
                key = _keyword(sub, 'key').value
                if isinstance(key, ast.Constant) and key.value is None:
                    continue
                _refuse(sub, '%s() with key= works the key out for each item, a loop that '
                             'is translated inside a def; here it is %s.'
                        % (self.kind(sub), place), tip)

    def hoist(self, node, before, where=None):
        """Rewrite the calls under *node*, inner ones first."""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return node
        if isinstance(node, ast.Lambda):
            self.refuse_inside(node, 'inside a lambda',
                               'Sort in a def and call it from the lambda: '
                               'def by_price(): return sorted(items, key=...).')
            return node
        if isinstance(node, ast.BoolOp):
            node.values = [self.hoist(node.values[0], before, where)] + [
                self.hoist(v, before, where or _RIGHT_OF_AND_OR)
                for v in node.values[1:]]
        elif isinstance(node, ast.IfExp):
            node.test = self.hoist(node.test, before, where)
            node.body = self.hoist(node.body, before, where or _IF_ELSE_BRANCH)
            node.orelse = self.hoist(node.orelse, before, where or _IF_ELSE_BRANCH)
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            # Only the first list is read before the loop; the rest is per item.
            inner = where or _IN_COMPREHENSION
            for i, gen in enumerate(node.generators):
                gen.iter = self.hoist(gen.iter, before, where if i == 0 else inner)
                gen.ifs = [self.hoist(t, before, inner) for t in gen.ifs]
            for field in ('elt', 'key', 'value'):
                if getattr(node, field, None) is not None:
                    setattr(node, field, self.hoist(getattr(node, field), before, inner))
            return node
        else:
            for field, value in ast.iter_fields(node):
                if isinstance(value, ast.AST) and not isinstance(value, ast.stmt):
                    setattr(node, field, self.hoist(value, before, where))
                elif isinstance(value, list):
                    setattr(node, field, [
                        self.hoist(v, before, where)
                        if isinstance(v, ast.AST) and not isinstance(v, ast.stmt) else v
                        for v in value])
        if self.kind(node):
            return self.rewrite(node, before, where)
        return node

    def statement(self, stmt):
        before = []
        if isinstance(stmt, ast.While):
            stmt.test = self.hoist(stmt.test, before, _WHILE_TEST)
        elif isinstance(stmt, (ast.For, ast.AsyncFor)):
            stmt.iter = self.hoist(stmt.iter, before)
        elif isinstance(stmt, ast.If):
            stmt.test = self.hoist(stmt.test, before)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            for item in stmt.items:
                item.context_expr = self.hoist(item.context_expr, before)
        elif not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                   ast.Try)) and type(stmt).__name__ != 'TryStar':
            for field, value in ast.iter_fields(stmt):
                if isinstance(value, ast.expr):
                    setattr(stmt, field, self.hoist(value, before))
                elif isinstance(value, list):
                    setattr(stmt, field, [self.hoist(v, before)
                                          if isinstance(v, ast.expr) else v for v in value])
        return before + [stmt]

    def has_key(self, node):
        for sub in _outside_defs(node):
            if self.kind(sub):
                key = _keyword(sub, 'key').value
                if not (isinstance(key, ast.Constant) and key.value is None):
                    return True
        return False

    def split_if_else(self, stmt):
        """slots = max(groups, key=len) if groups else []: an if and an else of a line each.

        Only the branch Python reaches works its keys out, as in CPython; on a
        line of its own each one has a line before for them.
        """
        if not isinstance(stmt, (ast.Assign, ast.Return)) \
                or not isinstance(stmt.value, ast.IfExp) \
                or not (self.has_key(stmt.value.body) or self.has_key(stmt.value.orelse)):
            return None

        def line(value):
            new = copy.copy(stmt)
            if isinstance(stmt, ast.Assign):
                new.targets = copy.deepcopy(stmt.targets)
            new.value = value
            return new
        return _loc(ast.If(test=stmt.value.test, body=[line(stmt.value.body)],
                           orelse=[line(stmt.value.orelse)]), stmt)

    def block(self, statements):
        out = []
        for stmt in statements:
            split = self.split_if_else(stmt)
            if split is not None:
                out.extend(self.block([split]))
                continue
            if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for field in ('body', 'orelse', 'finalbody'):
                    inner = getattr(stmt, field, None)
                    if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt):
                        setattr(stmt, field, self.block(inner))
                for handler in getattr(stmt, 'handlers', []) or []:
                    handler.body = self.block(handler.body)
            out.extend(self.statement(stmt))
        return out

    def outside(self, statements, place):
        """The top of the file or of a class: keys are refused, defs go on."""
        for stmt in statements:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(stmt, ast.ClassDef):
                self.outside(stmt.body, 'at the top of a class')
                continue
            for node in _outside_defs(stmt):
                if isinstance(node, ast.Lambda):
                    self.refuse_inside(node, 'inside a lambda',
                                       'Sort in a def and call it from the lambda: '
                                       'def by_price(): return sorted(items, key=...).')
            self.refuse_inside(stmt, place,
                               'Sort in a function that runs when the screen opens -- '
                               'lifecycle(home, on_mount=load) -- and show the result '
                               'from there.')


def desugar(tree):
    """Rewrite sorted/sort/min/max with key= in every function body."""
    own_sort = any(isinstance(node, ast.ClassDef) and any(
        isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == 'sort'
        for item in node.body) for node in ast.walk(tree))
    rewriter = _Rewriter(own_sort)
    rewriter.outside(tree.body, 'at the top of the file')
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node.body = rewriter.block(node.body)
    if rewriter.changed:
        ast.fix_missing_locations(tree)
    return tree
