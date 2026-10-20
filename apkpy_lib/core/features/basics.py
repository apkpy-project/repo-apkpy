# -*- coding: utf-8 -*-
"""``divmod()``, ``pow()`` and ``assert``, written the ways ApkPy already
translates.

    q, r = divmod(total, 60)        q = total // 60
                                    r = total % 60

    pow(2, n)                       2 ** n

    assert n > 0, "empty"           if not n > 0:
                                        raise AssertionError("empty")

``divmod`` on its own line becomes the two operations, so ``q`` and ``r``
are numbers to the rest of the translation, as they are to Python: kept in a
pair, they would come back as text, and ``f"{r:02d}"`` would stop. When an
operand is one of the names being assigned (``a, b = divmod(a, b)``) or more
than a name or a number, it is read once first, because Python works out
both answers before assigning either.

``pow(a, b, m)`` is left to the compiler (an exact modular power).

A name the app defines itself -- its own ``divmod``, ``pow`` -- is left alone.
"""

import ast


def _loc(node, like):
    return ast.copy_location(node, like)


def _simple(node):
    return isinstance(node, ast.Constant) or (
        isinstance(node, ast.UnaryOp) and isinstance(node.operand, ast.Constant))


def _own_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split('.')[0] for alias in node.names)
    return names


class _Basics(ast.NodeTransformer):

    def __init__(self, own):
        self.own = own
        self.count = 0

    def _is(self, node, name, args):
        return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == name and name not in self.own
                and len(node.args) in args and not node.keywords
                and not any(isinstance(a, ast.Starred) for a in node.args))

    def visit_Call(self, node):
        self.generic_visit(node)
        if self._is(node, 'pow', (2,)):
            return _loc(ast.BinOp(left=node.args[0], op=ast.Pow(), right=node.args[1]), node)
        if self._is(node, 'divmod', (2,)):
            a, b = node.args
            if not all(isinstance(x, ast.Name) or _simple(x) for x in (a, b)):
                from ..unsupported import raise_unsupported
                raise_unsupported(
                    node,
                    cause=('divmod() of something worked out in the same line would '
                           'work it out twice here.'),
                    suggestions=['Give it a line of its own: q, r = divmod(total, 60).'],
                )
            return _loc(ast.List(elts=[_loc(ast.BinOp(left=a, op=ast.FloorDiv(), right=b), node),
                                       _loc(ast.BinOp(left=a, op=ast.Mod(), right=b), node)],
                                 ctx=ast.Load()), node)
        return node

    def visit_Assign(self, node):
        value = node.value
        target = node.targets[0] if len(node.targets) == 1 else None
        if (isinstance(target, (ast.Tuple, ast.List)) and len(target.elts) == 2
                and all(isinstance(t, ast.Name) for t in target.elts)
                and self._is(value, 'divmod', (2,))):
            out = []
            operands = []
            assigned = {t.id for t in target.elts}
            for operand in value.args:
                operand = self.visit(operand)
                if _simple(operand) or (isinstance(operand, ast.Name) and operand.id not in assigned):
                    operands.append(operand)
                    continue
                self.count += 1
                temp = '_apkpy_d%d' % self.count
                out.append(_loc(ast.Assign(targets=[_loc(ast.Name(id=temp, ctx=ast.Store()), node)],
                                           value=operand, type_comment=None), node))
                operands.append(_loc(ast.Name(id=temp, ctx=ast.Load()), node))
            a, b = operands
            for name, op in zip(target.elts, (ast.FloorDiv(), ast.Mod())):
                out.append(_loc(ast.Assign(
                    targets=[_loc(ast.Name(id=name.id, ctx=ast.Store()), name)],
                    value=_loc(ast.BinOp(left=a, op=op, right=b), node),
                    type_comment=None), node))
            return out
        self.generic_visit(node)
        return node

    def visit_Assert(self, node):
        self.generic_visit(node)
        error = _loc(ast.Call(func=_loc(ast.Name(id='AssertionError', ctx=ast.Load()), node),
                              args=[node.msg] if node.msg is not None else [], keywords=[]), node)
        return _loc(ast.If(test=_loc(ast.UnaryOp(op=ast.Not(), operand=node.test), node),
                           body=[_loc(ast.Raise(exc=error, cause=None), node)],
                           orelse=[]), node)


def desugar(tree):
    """Rewrite divmod(), two-argument pow() and assert in *tree*."""
    wanted = any(isinstance(node, ast.Assert)
                 or isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                 and node.func.id in ('divmod', 'pow')
                 for node in ast.walk(tree))
    if not wanted:
        return tree
    tree = _Basics(_own_names(tree)).visit(tree)
    ast.fix_missing_locations(tree)
    return tree
