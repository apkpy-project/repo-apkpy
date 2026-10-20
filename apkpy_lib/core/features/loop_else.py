# -*- coding: utf-8 -*-
"""``for ... else`` and ``while ... else``, rewritten before translating.

    for x in items:                        _apkpy_nb1 = True
        if x == wanted:                    for x in items:
            break                              if x == wanted:
    else:                                          _apkpy_nb1 = False
        missing()                                  break
                                           if _apkpy_nb1:
                                               missing()

The ``else`` of a loop runs when the loop ended without a ``break``: it ran out
of items, or its condition became false. A flag that every ``break`` of that
loop clears says exactly that. A ``return`` or an error leaves the function
before the check, which are the other cases Python skips the ``else`` in. A
loop with no ``break`` of its own always reaches its ``else``, so it simply
follows the loop.

Only the loop's own breaks count. A ``break`` inside a loop nested in the body
belongs to that loop; one in the ``else`` of a nested loop belongs to this one,
and the nested loop is rewritten first, which puts it where this pass finds it.

Until now the ``else`` of a ``for`` stopped the build, and the ``else`` of a
``while`` was left out of the app without a word.

Only function bodies are rewritten, as in ``unpacking``: the module level is
read as the app's layout.
"""

import ast

_PREFIX = "_apkpy_nb"


def _loc(node, like):
    return ast.copy_location(node, like)


def _set(flag, value, like):
    return _loc(ast.Assign(targets=[_loc(ast.Name(id=flag, ctx=ast.Store()), like)],
                           value=_loc(ast.Constant(value=value), like),
                           type_comment=None), like)


def _own_breaks(statements, flag):
    """Put ``flag = False`` before each break of this loop in *statements*.

    Returns True when there was at least one. Nested loops keep their bodies'
    breaks; their ``else`` is outside them and was already moved out."""
    found = False
    out = []
    for stmt in statements:
        if isinstance(stmt, ast.Break):
            out.append(_set(flag, False, stmt))
            out.append(stmt)
            found = True
            continue
        if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            out.append(stmt)
            continue
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.append(stmt)
            continue
        for field in ('body', 'orelse', 'finalbody'):
            inner = getattr(stmt, field, None)
            if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt):
                new, had = _own_breaks(inner, flag)
                setattr(stmt, field, new)
                found = found or had
        for handler in getattr(stmt, 'handlers', []) or []:
            new, had = _own_breaks(handler.body, flag)
            handler.body = new
            found = found or had
        for case in getattr(stmt, 'cases', []) or []:
            new, had = _own_breaks(case.body, flag)
            case.body = new
            found = found or had
        out.append(stmt)
    return out, found


class _Rewriter:
    def __init__(self):
        self.count = 0

    def block(self, statements):
        out = []
        for stmt in statements:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                stmt.body = self.block(stmt.body)
                out.append(stmt)
                continue
            for field in ('body', 'orelse', 'finalbody'):
                inner = getattr(stmt, field, None)
                if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt):
                    setattr(stmt, field, self.block(inner))
            for handler in getattr(stmt, 'handlers', []) or []:
                handler.body = self.block(handler.body)
            for case in getattr(stmt, 'cases', []) or []:
                case.body = self.block(case.body)
            if isinstance(stmt, (ast.For, ast.While)) and stmt.orelse:
                out.extend(self.loop(stmt))
            else:
                out.append(stmt)
        return out

    def loop(self, stmt):
        other = stmt.orelse
        stmt.orelse = []
        self.count += 1
        flag = "%s%d" % (_PREFIX, self.count)
        body, broke = _own_breaks(stmt.body, flag)
        if not broke:
            # Nothing leaves this loop early: Python always runs its else.
            return [stmt] + other
        stmt.body = body
        check = _loc(ast.If(test=_loc(ast.Name(id=flag, ctx=ast.Load()), other[0]),
                            body=other, orelse=[]), other[0])
        return [_set(flag, True, stmt), stmt, check]


def desugar(tree):
    """Rewrite the ``else`` of every loop in the function bodies of *tree*."""
    if not any(isinstance(node, (ast.For, ast.While)) and node.orelse
               for node in ast.walk(tree)):
        return tree
    rewriter = _Rewriter()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node.body = rewriter.block(node.body)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    item.body = rewriter.block(item.body)
    if rewriter.count:
        ast.fix_missing_locations(tree)
    return tree


__all__ = ["desugar"]
