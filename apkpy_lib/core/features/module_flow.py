# -*- coding: utf-8 -*-
"""A name the top of the file gives a new value inside if, for or while.

    N = 7
    res = ""
    if N % 2:
        res = "odd"          # the top of the file runs in onCreate
    def go():
        out.set_value(res)   # a click, later

The code at the top of the file runs when the screen opens, in onCreate, and
the name it sets there was a local of onCreate. A function that read it got
either the local, which javac refuses inside a click listener ("local
variables referenced from an inner class must be final or effectively
final"), or the module's starting value, with no word said. Both are refused
here, before any Java is written, with the line and what to write instead.

A name the top of the file sets and only the top of the file reads is fine:
`saved = storage.get("k")` then `if saved == "": saved = "Guest"` and
`field.set_value(saved)` all run in onCreate, one after the other.
"""

import ast

from .. import unsupported

_FLOW = (ast.If, ast.For, ast.While)


def _stores(statements):
    """(name, node) for each name a list of statements binds, in the order
    they are written, nested functions and classes left out."""
    stack = list(reversed(statements))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            yield node.id, node
        stack.extend(reversed(list(ast.iter_child_nodes(node))))


def _main_guard(node):
    test = getattr(node, 'test', None)
    return (isinstance(node, ast.If) and isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name) and test.left.id == '__name__')


def _own(fn):
    """The nodes of a function or lambda's own body."""
    stack = [fn.body] if isinstance(fn, ast.Lambda) else list(fn.body)
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.Lambda, ast.ClassDef)):
                stack.append(child)


def _params(fn):
    args = fn.args
    return {a.arg for a in (list(getattr(args, 'posonlyargs', [])) + list(args.args)
                            + list(args.kwonlyargs)
                            + [a for a in (args.vararg, args.kwarg) if a])}


def _free_reads(tree):
    """{name: first node} for names a function or lambda reads from the module."""
    found = {}
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        nodes = list(_own(fn))
        declared = set()
        for node in nodes:
            if isinstance(node, (ast.Global, ast.Nonlocal)):
                declared.update(node.names)
        local = _params(fn) | {node.id for node in nodes
                               if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
        local -= declared
        for node in nodes:
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) \
                    and node.id not in local:
                found.setdefault(node.id, node)
    return found


def _storage_get(node):
    func = getattr(node, 'func', None)
    return (isinstance(node, ast.Call) and isinstance(func, ast.Attribute)
            and func.attr == 'get' and isinstance(func.value, ast.Name)
            and func.value.id == 'storage')


def refuse_mixed_storage_reads(tree):
    """`x = storage.get("k") + "!"` at the top of the file.

    A saved value is read at the top of the file as a line of its own,
    `x = storage.get("k")`, which runs in onCreate. Anything around the read
    -- `+ "!"`, `or "none"`, `len(...)`, `a if storage.get("k") else b` --
    left the name undeclared: the Previewer showed the value and the Gradle
    build stopped with "cannot find symbol" on every line that used it.
    """
    for stmt in getattr(tree, 'body', []):
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                and isinstance(stmt.targets[0], ast.Name):
            name, value = stmt.targets[0].id, stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) \
                and stmt.value is not None:
            name, value = stmt.target.id, stmt.value
        else:
            continue
        if _storage_get(value):
            continue
        read = next((node for node in ast.walk(value) if _storage_get(node)), None)
        if read is None:
            continue
        unsupported.raise_unsupported(
            stmt,
            cause=('At the top of the file a saved value is read on a line of its '
                   'own, %s = storage.get(...). Here the read is part of a bigger '
                   'expression, which the phone would never have worked out.' % name),
            suggestions=[
                'Read it on its own line, saved = storage.get(...), and work the '
                'rest out where %s is used, or in a function.' % name,
            ],
            received='%s = %s' % (name, unsupported.describe(value)),
        )


def refuse_rebound_reads(tree):
    """Refuse a name set inside if/for/while at the top of the file that a
    function reads."""
    flow = []
    for stmt in getattr(tree, 'body', []):
        if isinstance(stmt, _FLOW) and not _main_guard(stmt):
            flow.append(stmt)
    if not flow:
        return
    reads = None
    for stmt in flow:
        for name, node in _stores([stmt]):
            if reads is None:
                reads = _free_reads(tree)
            if name not in reads:
                continue
            word = {ast.If: 'if', ast.For: 'for loop', ast.While: 'while loop'}[type(stmt)]
            kind = ('an ' if word == 'if' else 'a ') + word
            unsupported.raise_unsupported(
                node,
                cause=('%s gets its value inside %s at the top of the file, and a '
                       'function reads it. The top of the file runs when the screen '
                       'opens, and what it sets inside if, for and while stays there: '
                       'the function cannot see it.' % (name, kind)),
                suggestions=[
                    'Move the %s into the function that reads %s, or into a small '
                    'function that returns the value.' % (word, name),
                ],
                received='%s = ... inside %s' % (name, kind),
            )
