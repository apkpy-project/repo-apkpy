# -*- coding: utf-8 -*-
"""``try ... else`` and ``raise ... from``, rewritten before translating.

    try:                                   _apkpy_ok1 = False
        n = int(text)                      try:
    except ValueError:                         n = int(text)
        n = 0                                  _apkpy_ok1 = True
    else:                                  except ValueError:
        saved(n)                               n = 0
                                           if _apkpy_ok1:
                                               saved(n)

The ``else`` of a try runs when the body finished without an error, and an
error of its own is not caught by the handlers above it. A flag set on the
body's last line says exactly that: an error, a ``return``, a ``break`` or a
``continue`` leave before it, which are the cases Python skips the ``else``
in. With a ``finally``, the whole thing goes inside a try that keeps it, so
the ``finally`` still runs after the ``else``.

``raise X from Y`` only says, in a traceback, what caused X. Nothing on the
phone prints one, so it raises X.

The handlers and ``raise`` themselves are translated by the compiler
(``try_block`` / ``raise``), with Python's error types.
"""

import ast


def _loc(node, like):
    return ast.copy_location(node, like)


def _ends(statements):
    """True when *statements* never finish normally: the last one returns,
    raises, breaks or continues, on every path."""
    if not statements:
        return False
    last = statements[-1]
    if isinstance(last, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
        return True
    if isinstance(last, ast.If):
        return _ends(last.body) and _ends(last.orelse)
    if isinstance(last, ast.Try):
        if _ends(last.finalbody):
            return True
        body = _ends(last.orelse) if last.orelse else _ends(last.body)
        return body and all(_ends(h.body) for h in last.handlers)
    return False


class _Errors(ast.NodeTransformer):

    def __init__(self):
        self.count = 0

    def visit_Raise(self, node):
        self.generic_visit(node)
        node.cause = None
        return node

    def visit_Try(self, node):
        self.generic_visit(node)
        if not node.orelse:
            return node
        if _ends(node.body):
            # The body always leaves early: Python never reaches the else.
            node.orelse = []
            return node
        self.count += 1
        flag = '_apkpy_ok%d' % self.count

        def assign(value, like):
            return _loc(ast.Assign(targets=[_loc(ast.Name(id=flag, ctx=ast.Store()), like)],
                                   value=_loc(ast.Constant(value=value), like),
                                   type_comment=None), like)

        inner = _loc(ast.Try(body=list(node.body) + [assign(True, node.body[-1])],
                             handlers=node.handlers, orelse=[], finalbody=[]), node)
        check = _loc(ast.If(test=_loc(ast.Name(id=flag, ctx=ast.Load()), node),
                            body=node.orelse, orelse=[]), node.orelse[0])
        steps = [assign(False, node), inner, check]
        if node.finalbody:
            return _loc(ast.Try(body=steps, handlers=[], orelse=[],
                                finalbody=node.finalbody), node)
        return steps


def desugar(tree):
    """Rewrite every ``try ... else`` and ``raise ... from`` in *tree*."""
    if not any(isinstance(node, ast.Raise) and node.cause is not None
               or isinstance(node, ast.Try) and node.orelse
               for node in ast.walk(tree)):
        return tree
    tree = _Errors().visit(tree)
    ast.fix_missing_locations(tree)
    return tree
