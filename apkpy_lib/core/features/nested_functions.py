# -*- coding: utf-8 -*-
"""A function inside a function, and a lambda kept in a name, moved out to the
module.

    def total(prices):                     def total__add(rate, n):
        rate = 0.23                            return n * (1 + rate)
        def add(n):
            return n * (1 + rate)          def total(prices):
        return add(prices[0])                  rate = 0.23
                                               return total__add(rate, prices[0])

    double = lambda n: n * 2               def go__double(n):
                                               return n * 2
                                           ...
                                           go__double(2)

Every function of the app is a method of the screen's class, and Java has no
function inside a method that ApkPy could write. So the inner one becomes a
module function of its own, and the names of the outer functions it reads go
in as arguments, first, at each call. Python's inner function sees those
names as they are when it is called; an argument written at the call is that
same value. An inner function that calls a sibling which reads ``rate``
needs ``rate`` too, so it gets it as well.

What is refused, with U2033, and why:
- ``nonlocal``: the inner function would change the outer one's name, and an
  argument cannot be changed from inside;
- changing a list or dict of the outer function (``items.append(x)``,
  ``totals[k] = v``) from inside: Python changes the outer one, the moved
  function would change the text it was handed;
- handing the inner function over (``command=inner``, ``on_response=inner``)
  when it reads names of the outer one: whoever calls it later does not have
  them to pass;
- a default value that reads a name of the outer function, which Python
  works out once, when the ``def`` line runs.

Runs before features/call_defaults.py and features/comprehensions.py, so the
moved functions get their defaults filled and a lambda kept in a name and used
in a comprehension is already a call by then.
"""

import ast

_SEP = "__"

# Methods that change the list or dict they are called on.
_MUTATORS = frozenset((
    'append', 'insert', 'remove', 'extend', 'sort', 'reverse', 'clear',
    'pop', 'popitem', 'update', 'setdefault', 'add', 'discard'))


def _loc(node, like):
    return ast.copy_location(node, like)


def _refuse(node, cause, tip):
    from ..unsupported import raise_unsupported
    raise_unsupported(node, cause=cause, suggestions=[tip])


def _arg_list(args):
    return list(getattr(args, 'posonlyargs', [])) + list(args.args) + list(args.kwonlyargs) + [
        a for a in (args.vararg, args.kwarg) if a is not None]


def _own_walk(fn, into_lambdas=False):
    """The nodes of *fn*'s body. A function inside it is yielded, not entered."""
    stack = list(fn.body) if isinstance(fn.body, list) else [fn.body]
    stops = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef) + (
        () if into_lambdas else (ast.Lambda,))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, stops):
            continue
        stack.extend(ast.iter_child_nodes(node))


def _lambdas_to_defs(fn):
    """name = lambda a: expr  ->  def name(a): return expr, in *fn*'s body."""
    def block(statements):
        out = []
        for stmt in statements:
            if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for field in ('body', 'orelse', 'finalbody'):
                    inner = getattr(stmt, field, None)
                    if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt):
                        setattr(stmt, field, block(inner))
                for handler in getattr(stmt, 'handlers', []) or []:
                    handler.body = block(handler.body)
            if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(stmt.value, ast.Lambda)
                    and not stmt.value.args.vararg and not stmt.value.args.kwarg):
                lam = stmt.value
                out.append(_loc(ast.FunctionDef(
                    name=stmt.targets[0].id, args=lam.args,
                    body=[_loc(ast.Return(value=lam.body), lam)],
                    decorator_list=[], returns=None, type_comment=None), stmt))
                continue
            out.append(stmt)
        return out
    fn.body = block(fn.body)


class _Scope:
    """One function: what it binds, the functions written inside it, and,
    once worked out, the names of the functions around it that it needs."""

    def __init__(self, node, parent):
        self.node = node
        self.parent = parent
        self.children = []
        self.defs = {}          # name -> _Scope, for the defs written directly inside
        self.bound = set()      # every other name it binds (parameters too)
        self.globals = set()
        self.captured = {}      # name -> the _Scope that binds it
        self.refs = []          # (Name node, _Scope of a def it names)
        self.new_name = None

    def walk(self):
        """The functions inside, innermost first."""
        for child in self.children:
            for deeper in child.walk():
                yield deeper
            yield child


def _build(fn, parent):
    _lambdas_to_defs(fn)
    scope = _Scope(fn, parent)
    names, store = set(a.arg for a in _arg_list(fn.args)), set()
    for node in _own_walk(fn):
        if isinstance(node, ast.Global):
            scope.globals.update(node.names)
        elif isinstance(node, ast.Nonlocal):
            _refuse(node, 'nonlocal lets %s change a name of the function around it. Moved '
                          'out as its own function, the name arrives as an argument, and an '
                          'argument cannot be changed from inside.' % fn.name,
                    'Return the new value and assign it in the outer function: '
                    'count = bump(count).')
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            store.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in scope.defs:
                _refuse(node, '%s is written twice inside %s. Moved out to the top level, '
                              'only one of them could keep the name.' % (node.name, fn.name),
                        'Give each its own name, or keep one def and choose inside it.')
            child = _build(node, scope)
            scope.children.append(child)
            scope.defs[node.name] = child
    names |= store
    both = (names & set(scope.defs)) - scope.globals
    if both:
        name = sorted(both)[0]
        _refuse(scope.defs[name].node,
                '%s is both a function written inside %s and a value it assigns.'
                % (name, fn.name),
                'Give the function and the value different names.')
    scope.bound = names - scope.globals - set(scope.defs)
    return scope


def _resolve(scope, name):
    """Where *name*, read in *scope*, comes from: ('local', scope),
    ('free', the outer scope binding it), ('def', the scope of a def written
    in this or an outer function), or None for the module and builtins."""
    if name in scope.globals:
        return None
    current = scope
    while current is not None:
        if name in current.defs:
            return ('def', current.defs[name])
        if name in current.bound:
            return ('local' if current is scope else 'free', current)
        if current is not scope and name in current.globals:
            return None
        current = current.parent
    return None


def _reads(fn):
    """The names *fn*'s own body reads, lambdas inside it included (their
    parameters are theirs, not reads)."""
    lambda_params, found = set(), []
    for node in _own_walk(fn, into_lambdas=True):
        if isinstance(node, ast.Lambda):
            lambda_params.update(a.arg for a in _arg_list(node.args))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            found.append(node)
    return [node for node in found if node.id not in lambda_params]


def _call_of(fn):
    """id(Name node) -> the Call it is the function of, in *fn*'s own body."""
    return {id(node.func): node for node in _own_walk(fn, into_lambdas=True)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}


def _check_defaults(scope):
    args = scope.node.args
    for default in list(args.defaults) + [d for d in args.kw_defaults if d is not None]:
        for node in ast.walk(default):
            if isinstance(node, ast.Name) and _resolve(scope.parent, node.id) is not None:
                _refuse(node, 'The default value of %s reads %s of the function around it. '
                              'Python works that default out once, when the def line runs; '
                              'moved out to the top level, there is no %s there.'
                        % (scope.node.name, node.id, node.id),
                        'Use a literal default, or pass %s at each call.' % node.id)


def _check_changes(scope):
    """A list or dict of the outer function changed from inside."""
    for node in _own_walk(scope.node, into_lambdas=True):
        target = None
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in _MUTATORS and isinstance(node.func.value, ast.Name)):
            target = node.func.value
        elif (isinstance(node, ast.Subscript) and isinstance(node.ctx, (ast.Store, ast.Del))
                and isinstance(node.value, ast.Name)):
            target = node.value
        if target is not None and target.id in scope.captured:
            _refuse(node, '%s changes %s, which belongs to the function around it. Python '
                          'changes that same %s; moved out as its own function, %s gets a '
                          'copy, and the change would stay inside.'
                    % (scope.node.name, target.id, target.id, scope.node.name),
                    'Return the new value and assign it in the outer function: '
                    '%s = add_to(%s, x).' % (target.id, target.id))


def _move(fn, taken):
    """Move the functions inside the module function *fn* out. Returns them,
    innermost first, in the order they were written."""
    root = _build(fn, None)
    inner = list(root.walk())
    if not inner:
        return []
    everyone = inner + [root]
    calls = {}
    for scope in everyone:
        calls[id(scope)] = _call_of(scope.node)
        for node in _reads(scope.node):
            where = _resolve(scope, node.id)
            if where is None:
                continue
            kind, target = where
            if kind == 'free':
                scope.captured.setdefault(node.id, target)
            elif kind == 'def':
                scope.refs.append((node, target))
    for scope in inner:
        _check_defaults(scope)

    # A function calling another that reads rate needs rate as well: settle.
    changed = True
    while changed:
        changed = False
        for scope in everyone:
            for node, target in scope.refs:
                for name, binder in list(target.captured.items()):
                    where = _resolve(scope, name)
                    if where is not None and where[0] == 'local' and where[1] is binder:
                        continue
                    if where is None or where[0] == 'def' or where[1] is not binder:
                        _refuse(node, '%s calls %s, which reads %s of an outer function, '
                                      'but in %s that name means something else.'
                                % (scope.node.name, target.node.name, name, scope.node.name),
                                'Rename %s in one of them.' % name)
                    if name not in scope.captured:
                        scope.captured[name] = binder
                        changed = True

    for scope in inner:
        _check_changes(scope)

    # New names, from the outside in: total__add, total__add__step.
    for scope in reversed(inner):
        base = (scope.parent.new_name or scope.parent.node.name) + _SEP + scope.node.name
        name, k = base, 2
        while name in taken:
            name = '%s%d' % (base, k)
            k += 1
        taken.add(name)
        scope.new_name = name

    for scope in everyone:
        for node, target in scope.refs:
            call = calls[id(scope)].get(id(node))
            needs = sorted(target.captured)
            if call is None and needs:
                _refuse(node, '%s is a function inside a function that reads %s of the '
                              'function around it. Handed over like this, whoever calls it '
                              'later has no %s to give it.'
                        % (target.node.name, ', '.join(needs), ', '.join(needs)),
                        'Move %s to the top level of the file and pass what it needs as a '
                        'parameter, or keep the value in a global.' % target.node.name)
            node.id = target.new_name
            if call is not None:
                call.args[:0] = [_loc(ast.Name(id=name, ctx=ast.Load()), call) for name in needs]

    for scope in inner:
        args = scope.node.args
        extra = []
        for name in sorted(scope.captured):
            arg = _loc(ast.arg(arg=name, annotation=None), scope.node)
            # The same value as the outer function's name, whatever the call:
            # a number there is a number here (_numeric_body_names).
            arg._apkpy_captured = True
            extra.append(arg)
        if getattr(args, 'posonlyargs', None):
            args.posonlyargs[:0] = extra
        else:
            args.args[:0] = extra
        scope.node.name = scope.new_name

    moved = set(id(scope.node) for scope in inner)
    for scope in everyone:
        _drop(scope.node, moved)
    return [scope.node for scope in inner]


def _drop(fn, moved):
    """Take the moved defs out of every block of *fn*."""
    def keep(statements):
        return [s for s in statements if id(s) not in moved]

    for node in [fn] + list(_own_walk(fn)):
        for field in ('body', 'orelse', 'finalbody'):
            block = getattr(node, field, None)
            if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
                kept = keep(block)
                if len(kept) != len(block):
                    setattr(node, field, kept or [_loc(ast.Pass(), node)])
        for handler in getattr(node, 'handlers', []) or []:
            kept = keep(handler.body)
            if len(kept) != len(handler.body):
                handler.body = kept or [_loc(ast.Pass(), handler)]


def desugar(tree):
    """Move every function inside a function (and lambda kept in a name inside
    a function) out to the module."""
    if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
               for top in tree.body if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef))
               for node in _own_walk(top)):
        return tree
    taken = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                         ast.ClassDef))}
    taken |= {t.id for n in tree.body if isinstance(n, ast.Assign)
              for t in n.targets if isinstance(t, ast.Name)}
    body, changed = [], False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            moved = _move(node, taken)
            if moved:
                body.extend(moved)
                changed = True
        body.append(node)
    if changed:
        tree.body = body
        ast.fix_missing_locations(tree)
    return tree
