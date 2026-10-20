# -*- coding: utf-8 -*-
"""Unpacking, written out as the statements ApkPy already translates.

    a, b = parts                 _u1 = <parts, checked to hold 2>
                                 a = _u1[0]
                                 b = _u1[1]
    first, *rest = parts         _u1 = <parts, checked to hold at least 1>
                                 first = _u1[0]
                                 rest = _u1[1:]
    a, b = b, a                  _u1 = b
                                 _u2 = a
                                 a = _u1
                                 b = _u2
    for k, v in d.items():       for k in d:
                                     v = d[k]
    for i, x in enumerate(xs):   for i in range(len(xs)):
                                     x = xs[i]
    for a, b in zip(xs, ys):     for _i in range(min(len(xs), len(ys))):
                                     a = xs[_i]
                                     b = ys[_i]
    for a, b in pairs:           for _p in pairs:
                                     a, b = _p        (and then as above)
    for i in reversed(range(n)): for i in range(n - 1, -1, -1):
    a = b = 0                    a = 0
                                 b = 0
    a = b = total(xs)            _u1 = total(xs)
                                 a = _u1
                                 b = _u1

Every value on the phone is text, a list is JSON text, and these shapes were
refused with U2033. Rewriting them here, before anything is translated, means
both generators (the Activity and the Worker) read only shapes they already
know, and the Previewer keeps running the code as it was written.

The count is checked as CPython checks it: ``a, b = "x,y,z".split(",")`` stops
with "too many values to unpack (expected 2)", instead of leaving the third
part out. A value that is evaluated once in Python is evaluated once here: it
goes into a name of its own first.

Only function bodies are rewritten. The module level is read as the app's
layout by other passes, and a name made up here would become part of it.
"""

import ast
import copy

UNPACK = "__apkpy_unpack__"
_PREFIX = "_apkpy_u"


def _loc(node, like):
    return ast.copy_location(node, like)


def _name(name, like, ctx=None):
    return _loc(ast.Name(id=name, ctx=ctx or ast.Load()), like)


def _index(value_name, index, like):
    return _loc(ast.Subscript(value=_name(value_name, like),
                              slice=_loc(ast.Constant(value=index), like),
                              ctx=ast.Load()), like)


def _call(func, args, like):
    return _loc(ast.Call(func=_name(func, like), args=args, keywords=[]), like)


def _assign(target, value, like):
    return _loc(ast.Assign(targets=[target], value=value), like)


def _plain_names(target):
    """True for a target made of names, one level of tuples deep."""
    if isinstance(target, ast.Name):
        return True
    if isinstance(target, (ast.Tuple, ast.List)):
        starred = [e for e in target.elts if isinstance(e, ast.Starred)]
        if len(starred) > 1:
            return False
        for elt in target.elts:
            inner = elt.value if isinstance(elt, ast.Starred) else elt
            if not (isinstance(inner, ast.Name)
                    or (isinstance(inner, (ast.Tuple, ast.List)) and _plain_names(inner))):
                return False
        return True
    return False


class _Rewriter:
    def __init__(self):
        self.count = 0

    def fresh(self):
        self.count += 1
        return "%s%d" % (_PREFIX, self.count)

    # a, b = value ----------------------------------------------------------

    def assign(self, target, value, like):
        """The statements that bind *target* to *value*, as Python would."""
        if isinstance(target, ast.Name):
            return [_assign(_name(target.id, like, ast.Store()), value, like)]
        elts = target.elts
        star = next((i for i, e in enumerate(elts) if isinstance(e, ast.Starred)), None)
        if (isinstance(value, (ast.Tuple, ast.List)) and star is None
                and not any(isinstance(e, ast.Starred) for e in value.elts)
                and len(value.elts) == len(elts)):
            # a, b = b, a: every value is read before any name changes.
            temps = [self.fresh() for _ in elts]
            out = [_assign(_name(t, like, ast.Store()), v, like)
                   for t, v in zip(temps, value.elts)]
            for elt, temp in zip(elts, temps):
                out.extend(self.assign(elt, _name(temp, like), like))
            return out
        holder = self.fresh()
        if star is None:
            before, after = len(elts), 0
        else:
            before, after = star, len(elts) - star - 1
        checked = _call(UNPACK, [value,
                                 _loc(ast.Constant(value=before), like),
                                 _loc(ast.Constant(value=after), like),
                                 _loc(ast.Constant(value=star is not None), like)], like)
        out = [_assign(_name(holder, like, ast.Store()), checked, like)]
        for i, elt in enumerate(elts):
            if star is not None and i == star:
                upper = _loc(ast.UnaryOp(op=ast.USub(), operand=_loc(ast.Constant(value=after), like)), like) \
                    if after else None
                part = _loc(ast.Subscript(
                    value=_name(holder, like),
                    slice=_loc(ast.Slice(lower=_loc(ast.Constant(value=star), like),
                                         upper=upper, step=None), like),
                    ctx=ast.Load()), like)
                out.extend(self.assign(elt.value, part, like))
                continue
            position = i if star is None or i < star else i - len(elts)
            if position < 0:
                part = _loc(ast.Subscript(
                    value=_name(holder, like),
                    slice=_loc(ast.UnaryOp(op=ast.USub(), operand=_loc(ast.Constant(value=-position), like)), like),
                    ctx=ast.Load()), like)
            else:
                part = _index(holder, position, like)
            out.extend(self.assign(elt, part, like))
        return out

    # a = b = value -----------------------------------------------------------

    def chain(self, stmt):
        """a = b = value: the value is read once, then each target gets it,
        left to right, as in Python."""
        value = stmt.value
        if isinstance(value, (ast.List, ast.Dict, ast.Set,
                              ast.ListComp, ast.DictComp, ast.SetComp)):
            from ..unsupported import raise_unsupported
            kind = 'dict' if isinstance(value, (ast.Dict, ast.DictComp)) else 'list'
            raise_unsupported(
                stmt,
                cause=('In CPython every name here holds the same %s, and a change '
                       'made through one shows in the others. On the phone a list '
                       'or a dict is text, so each name would get a copy of its own.'
                       % kind),
                suggestions=['For one %s per name, give each its own line: '
                             'a = [] and then b = [].' % kind],
            )
        out = []
        if isinstance(value, (ast.Constant, ast.Name)) or (
                isinstance(value, ast.UnaryOp) and isinstance(value.operand, ast.Constant)):
            # Reading it twice gives the same thing: no name of its own needed.
            def source():
                return _loc(copy.deepcopy(value), stmt)
        else:
            holder = self.fresh()
            out.append(_assign(_name(holder, stmt, ast.Store()), value, stmt))

            def source():
                return _name(holder, stmt)
        for target in stmt.targets:
            if isinstance(target, (ast.Tuple, ast.List)) and _plain_names(target):
                out.extend(self.assign(target, source(), stmt))
            else:
                out.append(_assign(target, source(), stmt))
        return out

    def once(self, value, like, before):
        """*value* as a name, evaluated once: a name stays a name."""
        if isinstance(value, ast.Name):
            return value.id
        holder = self.fresh()
        before.append(_assign(_name(holder, like, ast.Store()), value, like))
        return holder

    # for a, b in ... ---------------------------------------------------------

    def loop(self, stmt):
        target, it = stmt.target, stmt.iter
        before = []
        if len(target.elts) == 2 and not any(isinstance(e, ast.Starred) for e in target.elts):
            key, val = target.elts
            if (isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute)
                    and it.func.attr == 'items' and not it.args and not it.keywords
                    and isinstance(key, ast.Name)):
                source = self.once(it.func.value, stmt, before)
                body = self.assign(val, _loc(ast.Subscript(
                    value=_name(source, stmt), slice=_name(key.id, stmt), ctx=ast.Load()), stmt), stmt)
                return before + [self._for(stmt, key, _name(source, stmt), body)]
            if (isinstance(it, ast.Call) and isinstance(it.func, ast.Name)
                    and it.func.id == 'enumerate' and isinstance(key, ast.Name)
                    and 1 <= len(it.args) + len(it.keywords) <= 2
                    and all(k.arg == 'start' for k in it.keywords) and it.args):
                start = it.args[1] if len(it.args) > 1 else (
                    it.keywords[0].value if it.keywords else None)
                source = self.once(it.args[0], stmt, before)
                length = _call('len', [_name(source, stmt)], stmt)
                if start is None:
                    rng = _call('range', [length], stmt)
                    at = _name(key.id, stmt)
                else:
                    first = self.once(start, stmt, before)
                    rng = _call('range', [_name(first, stmt), _loc(ast.BinOp(
                        left=length, op=ast.Add(), right=_name(first, stmt)), stmt)], stmt)
                    at = _loc(ast.BinOp(left=_name(key.id, stmt), op=ast.Sub(),
                                        right=_name(first, stmt)), stmt)
                body = self.assign(val, _loc(ast.Subscript(
                    value=_name(source, stmt), slice=at, ctx=ast.Load()), stmt), stmt)
                return before + [self._for(stmt, key, rng, body)]
        if (isinstance(it, ast.Call) and isinstance(it.func, ast.Name)
                and it.func.id == 'zip' and not it.keywords and len(it.args) >= 2
                and len(it.args) == len(target.elts)
                and not any(isinstance(a, ast.Starred) for a in it.args)
                and not any(isinstance(e, ast.Starred) for e in target.elts)):
            sources = [self.once(a, stmt, before) for a in it.args]
            counter = self.fresh()
            lengths = [_call('len', [_name(s, stmt)], stmt) for s in sources]
            rng = _call('range', [_call('min', lengths, stmt)], stmt)
            body = []
            for elt, source in zip(target.elts, sources):
                body.extend(self.assign(elt, _loc(ast.Subscript(
                    value=_name(source, stmt), slice=_name(counter, stmt),
                    ctx=ast.Load()), stmt), stmt))
            return before + [self._for(stmt, _name(counter, stmt, ast.Store()), rng, body)]
        # Anything else: walk the items, and unpack each one.
        item = self.fresh()
        body = self.assign(target, _name(item, stmt), stmt)
        return [self._for(stmt, _name(item, stmt, ast.Store()), it, body)]

    @staticmethod
    def _for(stmt, target, it, prefix):
        if isinstance(target, ast.Name) and isinstance(target.ctx, ast.Load):
            target = _loc(ast.Name(id=target.id, ctx=ast.Store()), target)
        return _loc(ast.For(target=target, iter=it, body=prefix + stmt.body,
                            orelse=stmt.orelse, type_comment=None), stmt)

    # blocks ----------------------------------------------------------------

    def block(self, statements):
        out = []
        for stmt in statements:
            for field in ('body', 'orelse', 'finalbody'):
                inner = getattr(stmt, field, None)
                if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt):
                    setattr(stmt, field, self.block(inner))
            for handler in getattr(stmt, 'handlers', []) or []:
                handler.body = self.block(handler.body)
            out.extend(self.statement(stmt))
        return out

    def reversed_range(self, stmt):
        """for i in reversed(range(a, b)) is range(b - 1, a - 1, -1)."""
        call = stmt.iter
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id == 'reversed' and len(call.args) == 1 and not call.keywords):
            return None
        inner = call.args[0]
        if not (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
                and inner.func.id == 'range' and 1 <= len(inner.args) <= 2
                and not inner.keywords
                and not any(isinstance(a, ast.Starred) for a in inner.args)):
            return None        # a step: left to the generic reversed()
        before = []
        def once(node):
            # Read once, as Python does; a value written out needs no name.
            return node if isinstance(node, ast.Constant) else _name(self.once(node, stmt, before), stmt)

        if len(inner.args) == 1:
            start, stop = _loc(ast.Constant(value=0), stmt), once(inner.args[0])
        else:
            start, stop = once(inner.args[0]), once(inner.args[1])

        def minus_one(node):
            return _loc(ast.BinOp(left=node, op=ast.Sub(),
                                  right=_loc(ast.Constant(value=1), stmt)), stmt)

        rng = _call('range', [minus_one(stop), minus_one(start),
                              _loc(ast.UnaryOp(op=ast.USub(),
                                               operand=_loc(ast.Constant(value=1), stmt)), stmt)],
                    stmt)
        return before + [_loc(ast.For(target=stmt.target, iter=rng, body=stmt.body,
                                      orelse=stmt.orelse, type_comment=None), stmt)]

    def statement(self, stmt):
        if isinstance(stmt, ast.For) and isinstance(stmt.target, ast.Name):
            done = self.reversed_range(stmt)
            if done is not None:
                return done
        if isinstance(stmt, ast.Assign) and len(stmt.targets) > 1:
            return self.chain(stmt)
        if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], (ast.Tuple, ast.List))
                and _plain_names(stmt.targets[0])):
            return self.assign(stmt.targets[0], stmt.value, stmt)
        if (isinstance(stmt, ast.For) and not stmt.orelse
                and isinstance(stmt.target, (ast.Tuple, ast.List))
                and _plain_names(stmt.target)):
            return self.loop(stmt)
        return [stmt]


def desugar(tree):
    """Rewrite the unpacking in every function body of *tree*."""
    rewriter = _Rewriter()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node.body = rewriter.block(node.body)
    if rewriter.count:
        ast.fix_missing_locations(tree)
    return tree


__all__ = ["desugar", "UNPACK"]
