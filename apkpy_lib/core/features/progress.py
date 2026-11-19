# -*- coding: utf-8 -*-
"""progress(value, max=100, id=, screen=, parent=): a bar, drawn as a chart.

In the Previewer progress() is chart(kind="progress", ...), and here it is
written as that call before the compiler reads the module, so the bar is an
ApkpyChart on the phone: the same colours, set_value() and CSS as a ring,
from the same chart_rules.

An app that has a progress of its own -- a function, a variable, or a name
imported from somewhere other than apkpy_lib -- keeps it.
"""

import ast

from .. import style_parser

NAME = 'progress'
PARAMETERS = ('value', 'max', 'id', 'screen', 'parent')


def _own(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                and node.name == NAME:
            return True
        if isinstance(node, ast.Name) and node.id == NAME and isinstance(node.ctx, ast.Store):
            return True
        if isinstance(node, ast.arg) and node.arg == NAME:
            return True
        if isinstance(node, ast.ImportFrom) and not (node.module or '').startswith('apkpy_lib'):
            if any((alias.asname or alias.name) == NAME for alias in node.names):
                return True
    return False


def expand(tree):
    """Each progress(...) of apkpy_lib written as chart(kind="progress", ...), in place."""
    if _own(tree):
        return
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == NAME) or len(node.args) > len(PARAMETERS):
            continue
        if any(isinstance(a, ast.Starred) for a in node.args) \
                or any(k.arg is None for k in node.keywords):
            continue
        style_parser.report_unknown_arguments(
            NAME, [k.arg for k in node.keywords], getattr(node, 'lineno', 0))
        given = [ast.keyword(arg=name, value=arg) for name, arg in zip(PARAMETERS, node.args)]
        kind = ast.keyword(arg='kind', value=ast.Constant(value='progress'))
        kept = [k for k in node.keywords if k.arg in PARAMETERS]
        node.func = ast.copy_location(ast.Name(id='chart', ctx=ast.Load()), node.func)
        node.args = []
        node.keywords = [kind] + given + kept
        ast.fix_missing_locations(node)
