# -*- coding: utf-8 -*-
"""Comprehensions, any() and all(), written out as the loops they stand for.

    names = [p.upper() for p in parts if p]      names = []
                                                 for _apkpy_c1 in parts:
                                                     if _apkpy_c1:
                                                         names.append(_apkpy_c1.upper())
    ages = {n: 0 for n in names}                 ages = {}
                                                 for _apkpy_c2 in names:
                                                     ages[_apkpy_c2] = 0
    ok = any(x > 3 for x in xs)                  ok = False
                                                 for _apkpy_c3 in xs:
                                                     if _apkpy_c3 > 3:
                                                         ok = True
                                                         break

A comprehension elsewhere in a line -- ``", ".join([...])`` -- is worked out on
the line before, into a name of its own, and the line reads that name.

Python gives the loop variable of a comprehension a scope of its own: after
the line it is not there, and a name of the function spelled the same is not
touched. So each one is renamed (``_apkpy_cN``). any() and all() stop at the
first answer, as CPython's do.

What is refused, with U2033, and why:
- a comprehension in the test of a ``while`` (it would be worked out once);
- one on the right of ``and``/``or`` or in a branch of ``x if c else y``
  (Python only works it out when that side is reached);
- a set comprehension (there are no sets on the phone).

Only function bodies are rewritten; the module level has its own refusal.
Runs before features/unpacking.py, so ``for k, v in`` inside a comprehension
becomes the unpacking that pass already knows, and before
features/item_assignment.py, which writes the ``d[k] = v`` of a dict one.
"""

import ast
import copy

_PREFIX = "_apkpy_c"


def _loc(node, like):
    return ast.copy_location(node, like)


def _name(name, like, ctx=None):
    return _loc(ast.Name(id=name, ctx=ctx or ast.Load()), like)


def _assign(name, value, like):
    return _loc(ast.Assign(targets=[_name(name, like, ast.Store())], value=value), like)


def _refuse(node, cause, tip):
    from ..unsupported import raise_unsupported
    raise_unsupported(node, cause=cause, suggestions=[tip])


class _Rename(ast.NodeTransformer):
    """The comprehension's own names, given names of their own."""

    def __init__(self, names):
        self.names = names

    def visit_Name(self, node):
        if node.id in self.names:
            return _loc(ast.Name(id=self.names[node.id], ctx=node.ctx), node)
        return node

    def visit_Lambda(self, node):
        return node                 # its own scope; lambdas are refused elsewhere


_COMPS = (ast.ListComp, ast.DictComp, ast.GeneratorExp, ast.SetComp)


def _any_all(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in ('any', 'all') and len(node.args) == 1
            and not node.keywords and not isinstance(node.args[0], ast.Starred))


class _Rewriter:
    def __init__(self):
        self.count = 0
        self.changed = False

    def fresh(self):
        self.count += 1
        return "%s%d" % (_PREFIX, self.count)

    # the loops -------------------------------------------------------------

    def _loops(self, generators, inner, like):
        """for/if nesting for the generators of one comprehension, around *inner*."""
        renames = {}
        plan = []
        for gen in generators:
            if getattr(gen, 'is_async', 0):
                _refuse(like, 'async comprehensions are not translated.',
                        'Write the loop out.')
            # The iterable is read in the scope around it: earlier names only.
            iterable = _Rename(dict(renames)).visit(copy.deepcopy(gen.iter))
            for node in ast.walk(gen.target):
                if isinstance(node, ast.Name):
                    renames[node.id] = self.fresh()
            target = _Rename(renames).visit(copy.deepcopy(gen.target))
            ifs = [_Rename(dict(renames)).visit(copy.deepcopy(test)) for test in gen.ifs]
            plan.append((target, iterable, ifs))
        body = inner(renames)
        for target, iterable, ifs in reversed(plan):
            for test in reversed(ifs):
                body = [_loc(ast.If(test=test, body=body, orelse=[]), like)]
            body = [_loc(ast.For(target=target, iter=iterable, body=body, orelse=[],
                                 type_comment=None), like)]
        return body

    def build(self, comp, holder, like):
        """The statements that leave the value of *comp* in *holder*."""
        if isinstance(comp, ast.SetComp):
            _refuse(comp, 'A set comprehension builds a set, and there are no sets on '
                          'the phone.',
                    'Build a list, checking with in before appending: '
                    'if x not in seen: seen.append(x).')
        self.changed = True
        if isinstance(comp, ast.DictComp):
            start = _loc(ast.Dict(keys=[], values=[]), like)

            def inner(renames):
                key = _Rename(renames).visit(copy.deepcopy(comp.key))
                value = _Rename(renames).visit(copy.deepcopy(comp.value))
                return [_loc(ast.Assign(targets=[_loc(ast.Subscript(
                    value=_name(holder, like), slice=key, ctx=ast.Store()), like)],
                    value=value), like)]
        else:
            start = _loc(ast.List(elts=[], ctx=ast.Load()), like)

            def inner(renames):
                elt = _Rename(renames).visit(copy.deepcopy(comp.elt))
                call = _loc(ast.Call(func=_loc(ast.Attribute(
                    value=_name(holder, like), attr='append', ctx=ast.Load()), like),
                    args=[elt], keywords=[]), like)
                return [_loc(ast.Expr(value=call), like)]
        return [_assign(holder, start, like)] + self._loops(comp.generators, inner, like)

    def build_any_all(self, call, holder, like):
        """any(...)/all(...) into *holder*, stopping at the first answer."""
        self.changed = True
        is_any = call.func.id == 'any'
        source = call.args[0]
        if isinstance(source, (ast.GeneratorExp, ast.ListComp)):
            generators, element = source.generators, source.elt
        else:
            # any(flags): each item's own truth.
            item = "_apkpy_ci"
            generators = [ast.comprehension(target=_name(item, like, ast.Store()),
                                            iter=source, ifs=[], is_async=0)]
            element = _name(item, like)

        def inner(renames):
            test = _Rename(renames).visit(copy.deepcopy(element))
            if not is_any:
                test = _loc(ast.UnaryOp(op=ast.Not(), operand=test), like)
            return [_loc(ast.If(test=test, body=[
                _assign(holder, _loc(ast.Constant(value=is_any), like), like),
                _loc(ast.Break(), like)], orelse=[]), like)]
        start = _assign(holder, _loc(ast.Constant(value=not is_any), like), like)
        return [start] + self._loops(generators, inner, like)

    # finding them in a statement --------------------------------------------

    def hoist(self, stmt, node, before, guarded=False):
        """Replace the comprehensions under *node* by names; their loops go to *before*."""
        if isinstance(node, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return node
        if isinstance(node, _COMPS) or _any_all(node):
            if guarded:
                _refuse(node, 'Python works this out only when that side of the and, or '
                              'or if-else is reached. Written on the line before, it would '
                              'always be worked out.',
                        'Work it out on a line of its own first: found = [...], then use found.')
            # A comprehension inside this one is worked out per item: it stays
            # inside, and goes to the loop this one becomes.
            holder = self.fresh()
            if _any_all(node):
                before.extend(self.block(self.build_any_all(node, holder, stmt)))
            else:
                before.extend(self.block(self.build(node, holder, stmt)))
            return _name(holder, node)
        if isinstance(node, ast.BoolOp):
            node.values = [self.hoist(stmt, node.values[0], before, guarded)] + [
                self.hoist(stmt, v, before, True) for v in node.values[1:]]
            return node
        if isinstance(node, ast.IfExp):
            node.test = self.hoist(stmt, node.test, before, guarded)
            node.body = self.hoist(stmt, node.body, before, True)
            node.orelse = self.hoist(stmt, node.orelse, before, True)
            return node
        for field, value in ast.iter_fields(node):
            if isinstance(value, ast.AST) and not isinstance(value, ast.stmt):
                setattr(node, field, self.hoist(stmt, value, before, guarded))
            elif isinstance(value, list):
                setattr(node, field, [
                    self.hoist(stmt, v, before, guarded)
                    if isinstance(v, ast.AST) and not isinstance(v, ast.stmt) else v
                    for v in value])
        return node

    def statement(self, stmt):
        # names = [... for ...]: straight into the name, no holder in between.
        # Not when the name is read inside: names = [n for n in names if n]
        # reads the old list, which names = [] would have emptied.
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                and isinstance(stmt.targets[0], ast.Name) \
                and (isinstance(stmt.value, _COMPS) or _any_all(stmt.value)) \
                and not any(isinstance(n, ast.Name) and n.id == stmt.targets[0].id
                            for n in ast.walk(stmt.value)):
            name = stmt.targets[0].id
            if _any_all(stmt.value):
                return self.block(self.build_any_all(stmt.value, name, stmt))
            return self.block(self.build(stmt.value, name, stmt))
        if isinstance(stmt, ast.While):
            for node in ast.walk(stmt.test):
                if isinstance(node, _COMPS) or _any_all(node):
                    _refuse(node, 'The test of a while is asked again on every turn; '
                                  'worked out on the line before, it would be asked once.',
                            'Work it out inside the loop and break: while True: ... '
                            'if not any_left: break.')
            return [stmt]
        before = []
        if isinstance(stmt, (ast.For, ast.AsyncFor)):
            stmt.iter = self.hoist(stmt, stmt.iter, before)
        elif isinstance(stmt, ast.If):
            stmt.test = self.hoist(stmt, stmt.test, before)
        elif isinstance(stmt, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Expr,
                               ast.Return, ast.Delete)):
            for field, value in ast.iter_fields(stmt):
                if isinstance(value, ast.AST):
                    setattr(stmt, field, self.hoist(stmt, value, before))
                elif isinstance(value, list):
                    setattr(stmt, field, [self.hoist(stmt, v, before)
                                          if isinstance(v, ast.AST) else v for v in value])
        return before + [stmt]

    def block(self, statements):
        out = []
        for stmt in statements:
            for field in ('body', 'orelse', 'finalbody'):
                inner = getattr(stmt, field, None)
                if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt) \
                        and not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                  ast.ClassDef)):
                    setattr(stmt, field, self.block(inner))
            for handler in getattr(stmt, 'handlers', []) or []:
                handler.body = self.block(handler.body)
            out.extend(self.statement(stmt))
        return out


def desugar(tree):
    """Rewrite comprehensions, any() and all() in every function body."""
    rewriter = _Rewriter()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node.body = rewriter.block(node.body)
    if rewriter.changed:
        ast.fix_missing_locations(tree)
    return tree
