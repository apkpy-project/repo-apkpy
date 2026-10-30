# -*- coding: utf-8 -*-
"""One list or dict under two names, which the phone does not keep.

    l2 = l1                l2.reverse()         CPython reverses l1 too
    row = rows[0]          row["done"] = True   CPython changes rows
    for row in grid:       row.append(0)        CPython changes grid
    def add(x, tags=[]):   tags.append(x)       CPython keeps one list for every call
    def add(cart, x):      cart.append(x)       CPython: add(CART, "tea") changes CART

On the phone a list or a dict is a value, the JSON text of one: a second
name holds a copy, and a change made through it stays in the copy. Each
case above built, ran, and showed something CPython would not. They stop
the build here instead (U2033), on the code as it was written, with the way
to write it that gives the same answer on both.

Not refused, because both give the same answer: a second name that is only
read, a default list the function only reads, a copy made on purpose
(list(l1), row.copy()), and a function that changes a list it is given when
the caller takes the answer back (CART = add(CART, "tea")).

``only_read`` is used by the compiler too: a module list of numbers that
nothing changes or hands on has items it knows to be numbers.
"""

import ast
import re

CODE = "U2033"

# The methods that change a list, a dict or a set in place.
CHANGERS = frozenset((
    'append', 'extend', 'insert', 'pop', 'remove', 'sort', 'reverse', 'clear',
    'update', 'setdefault', 'popitem', 'add', 'discard'))

# Calls that read the list or dict they are given and keep nothing of it.
_READERS = frozenset((
    'len', 'sum', 'max', 'min', 'sorted', 'list', 'tuple', 'set', 'frozenset',
    'str', 'repr', 'print', 'enumerate', 'reversed', 'any', 'all', 'zip', 'bool'))
# ... of which these keep nothing of the items either.
_SHALLOW_READERS = frozenset(('len', 'str', 'repr', 'print', 'bool', 'any', 'all', 'sum'))
_READING_METHODS = frozenset(('count', 'index', 'get', 'keys', 'values', 'items', 'copy'))
_SHALLOW_METHODS = frozenset(('count', 'index', 'keys'))
_HOLDER = re.compile(r'_apkpy_s\d+$')      # sort_key.py's _HOLDER + a number


def _parents(roots):
    up = {}
    for root in roots:
        for node in ast.walk(root):
            for child in ast.iter_child_nodes(node):
                up[child] = node
    return up


def _in_a_test(node, up):
    """`if tags and x:` -- the truth of the value, and not the value itself."""
    parent = up.get(node)
    while isinstance(parent, ast.BoolOp):
        node, parent = parent, up.get(parent)
    if isinstance(parent, (ast.If, ast.While, ast.Assert, ast.IfExp)) and parent.test is node:
        return True
    return isinstance(parent, ast.UnaryOp) and isinstance(parent.op, ast.Not)


def _a_read(node, up, deep, readers=None):
    """Whether this use of a name only reads the object. *deep*: the object
    holds lists or dicts, so handing on one of its items shares that too.
    *readers*: the app's functions and the parameters each only reads
    (function_readers), so evens(NUMS) reads NUMS."""
    parent = up.get(node)
    if readers and not deep:
        call, slot = parent, None
        if isinstance(parent, ast.keyword):
            call, slot = up.get(parent), parent.arg
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) \
                and call.func.id in readers:
            params, read = readers[call.func.id]
            if slot is None and node in call.args:
                index = call.args.index(node)
                slot = params[index] if index < len(params) else None
            return slot in read
    if isinstance(parent, ast.Assign) and parent.value is node \
            and len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Name) \
            and _HOLDER.match(parent.targets[0].id):
        # sort_key.py's own name for the list of sorted(NUMS, key=abs): it is
        # walked and sorted, never changed. Counted as a second name, it made
        # max(NUMS) text in every function of the app.
        return not deep
    if isinstance(parent, ast.Subscript) and parent.value is node:
        return not deep and isinstance(parent.ctx, ast.Load)
    if isinstance(parent, (ast.For, ast.comprehension)) and parent.iter is node:
        return not deep
    if isinstance(parent, (ast.Compare, ast.FormattedValue)):
        return True
    if isinstance(parent, ast.BinOp):
        return not deep            # l + [x] is a new list, of the same items
    if isinstance(parent, ast.BoolOp) or isinstance(parent, ast.UnaryOp):
        return _in_a_test(node, up)
    if isinstance(parent, (ast.If, ast.While, ast.Assert, ast.IfExp)) and parent.test is node:
        return True
    if isinstance(parent, ast.Call) and node in parent.args:
        func = parent.func
        if isinstance(func, ast.Name) and func.id in _READERS:
            return not deep or func.id in _SHALLOW_READERS
        return isinstance(func, ast.Attribute) and func.attr in ('dumps', 'join')
    if isinstance(parent, ast.Attribute) and parent.value is node:
        grand = up.get(parent)
        return (isinstance(grand, ast.Call) and grand.func is parent
                and parent.attr in (_SHALLOW_METHODS if deep else _READING_METHODS))
    return False


def function_readers(tree):
    """name -> (parameters, the ones the body only reads), for the module's
    own functions: a list handed to one of them that only reads it is read."""
    found = {}
    for fn in getattr(tree, 'body', []):
        if isinstance(fn, ast.FunctionDef) and not fn.args.vararg and not fn.args.kwarg:
            params = [a.arg for a in fn.args.args]
            found[fn.name] = (params, {p for p in params if only_read(p, fn.body)})
    return found


def only_read(name, roots, skip=(), deep=False, readers=None):
    """Whether *name* is only read in these statements.

    Read: walked, indexed, measured, compared, shown, tested, or handed to a
    call that keeps nothing of it. Not: given a new value, changed, kept
    under another name, returned, put in a list, or passed to a function of
    the app -- after any of those CPython and the phone can hold two
    different things under the name. *skip* holds nodes not to count (the
    assignment that makes a module list).
    """
    up = _parents(roots)
    for root in roots:
        for node in ast.walk(root):
            if node in skip:
                continue
            if isinstance(node, ast.Name) and node.id == name:
                if not isinstance(node.ctx, ast.Load) or not _a_read(node, up, deep, readers):
                    return False
            elif isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names:
                return False
            elif isinstance(node, ast.arg) and node.arg == name:
                return False
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                    and node.name == name:
                return False
    return True


# ── what is refused ─────────────────────────────────────────────────────────

def _refuse(node, cause, suggestions, received):
    from ..unsupported import raise_unsupported
    raise_unsupported(node, cause=cause, suggestions=suggestions, received=received)


def _text(node):
    """The code a message quotes. Python 3.8 has no ast.unparse(), and
    describe() then names only the kind of node: "Subscript" for rows[0]."""
    from ..unsupported import describe
    if getattr(ast, 'unparse', None) is not None:
        return describe(node)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Attribute):
        return '%s.%s' % (_text(node.value), node.attr)
    if isinstance(node, ast.Subscript):
        return '%s[%s]' % (_text(node.value), _text(node.slice))
    if isinstance(node, ast.Call):
        parts = [_text(a) for a in node.args]
        parts += ['%s=%s' % (k.arg, _text(k.value)) for k in node.keywords if k.arg]
        return '%s(%s)' % (_text(node.func), ', '.join(parts))
    if isinstance(node, ast.List):
        return '[%s]' % ', '.join(_text(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return '{%s}' % ', '.join('%s: %s' % (_text(k), _text(v))
                                  for k, v in zip(node.keys, node.values) if k is not None)
    if isinstance(node, ast.Expr):
        return _text(node.value)
    if isinstance(node, ast.Assign):
        return '%s = %s' % (' = '.join(_text(t) for t in node.targets), _text(node.value))
    if isinstance(node, ast.AugAssign):
        sign = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*'}.get(type(node.op), '?')
        return '%s %s= %s' % (_text(node.target), sign, _text(node.value))
    if isinstance(node, ast.Delete):
        return 'del ' + ', '.join(_text(t) for t in node.targets)
    return describe(node)


def _container_word(node):
    """'list', 'dict' or 'set' for a value that makes a new one, else None."""
    for kind, word in ((ast.List, 'list'), (ast.ListComp, 'list'), (ast.Dict, 'dict'),
                       (ast.DictComp, 'dict'), (ast.Set, 'set'), (ast.SetComp, 'set')):
        if isinstance(node, kind):
            return word
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in ('list', 'dict', 'set'):
        return node.func.id
    return None


_EMPTY = {'list': '[]', 'dict': '{}', 'set': 'set()'}


def _shown(node):
    """A default as it was written; [] and {} also where unparse is missing."""
    word = _container_word(node)
    if isinstance(node, (ast.List, ast.Dict, ast.Set)) and not getattr(node, 'elts', None) \
            and not getattr(node, 'keys', None):
        return _EMPTY.get(word, _text(node))
    return _text(node)


def _defaults(tree):
    """def add(x, tags=[]) whose body does more than read tags."""
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = fn.args
        positional = list(getattr(args, 'posonlyargs', [])) + list(args.args)
        pairs = list(zip(positional[len(positional) - len(args.defaults):], args.defaults))
        pairs += [(a, d) for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None]
        for arg, default in pairs:
            word = _container_word(default)
            if word is None:
                continue
            deep = any(_container_word(n) for n in ast.walk(default) if n is not default)
            if only_read(arg.arg, fn.body, deep=deep):
                continue
            p, f = arg.arg, fn.name
            _refuse(
                default,
                cause=('%s=%s is made once, when Python runs the def, and every call '
                       'to %s() that leaves %s out gets that same %s. %s() changes '
                       'it or hands it on, so in CPython what one call leaves in it the '
                       'next call finds there. On the phone each call starts from a '
                       'new %s.' % (p, _shown(default), f, p, word, f, word)),
                suggestions=[
                    'Write %s=None and make the %s in the body: if %s is None: %s = %s. '
                    'Each call then gets its own, in CPython and on the phone.'
                    % (p, word, p, p, _EMPTY[word]),
                ],
                received='def %s(..., %s=%s)' % (f, p, _shown(default)),
            )


def _root(node):
    """The name under x, x[i][k], x.get(k): (name, the value) or None."""
    start = node
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in ('get', 'setdefault'):
        node = node.func.value
    while isinstance(node, ast.Subscript):
        if isinstance(node.slice, ast.Slice):
            return None                      # a slice is a new list
        node = node.value
    if isinstance(node, ast.Name):
        return node.id, start
    return None


def _statements(fn):
    """Every node of *fn*'s body, nested functions left out (their own scope)."""
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.ClassDef, ast.Lambda)):
                stack.append(child)


def _changes(nodes):
    """(name, node) for each change in place: x.append(v), x[k] = v, del x[k],
    x[k] += v, x += [v]."""
    found = []
    for node in nodes:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in CHANGERS:
            root = _root(node.func.value)
            if root:
                found.append((root[0], node))
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.Delete)):
            targets = [node.target] if isinstance(node, ast.AugAssign) else node.targets
        for target in targets:
            if isinstance(target, ast.Subscript):
                root = _root(target)
                if root:
                    found.append((root[0], node))
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) \
                and isinstance(node.value, (ast.List, ast.ListComp, ast.Tuple)):
            found.append((node.target.id, node))
    return found


def _line(node):
    return getattr(node, 'lineno', 0) or 0


def _last_binding(bindings, line):
    """The assignment of a name that the code at *line* sees (by line), or None."""
    before = [b for b in bindings if _line(b[0]) < line]
    return max(before, key=lambda b: _line(b[0])) if before else None


def _read_after(name, node, nodes, end=False):
    """Whether *name* is read after *node* runs (by line; after its last line
    when *end*), or anywhere in a loop around it, which runs it again."""
    line = (getattr(node, 'end_lineno', None) or _line(node)) if end else _line(node)
    around = [loop for loop in nodes
              if loop is not node and isinstance(loop, (ast.For, ast.AsyncFor, ast.While))
              and _line(loop) <= _line(node) and (getattr(loop, 'end_lineno', 0) or 0) >= line]
    for n in nodes:
        if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load):
            at = _line(n)
            if at > line or any(_line(loop) <= at <= loop.end_lineno for loop in around):
                return True
    return False


def _walked(it):
    """The name whose items a for walks: grid in grid, sorted(grid), enumerate(grid)."""
    while isinstance(it, ast.Call) and isinstance(it.func, ast.Name) \
            and it.func.id in ('sorted', 'list', 'reversed', 'tuple', 'enumerate') and it.args:
        it = it.args[0]
    return _root(it)


def _aliases(tree):
    """l2 = l1 / row = rows[0] / tags = d.get("tags"), and a change through
    either name that the other one would see in CPython."""
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        nodes = list(_statements(fn))
        params = {a.arg for a in list(getattr(fn.args, 'posonlyargs', [])) + fn.args.args
                  + fn.args.kwonlyargs}
        declared = {name for n in nodes if isinstance(n, (ast.Global, ast.Nonlocal))
                    for name in n.names}
        loops = {}                           # name -> the for loops that walk into it
        bindings = {}                        # name -> [(assign, source or None)]
        for node in nodes:
            if isinstance(node, (ast.For, ast.AsyncFor)):
                for target in ast.walk(node.target):
                    if isinstance(target, ast.Name):
                        loops.setdefault(target.id, []).append(node)
                        bindings.setdefault(target.id, []).append((node, None))
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        source = _root(node.value)
                        if source and source[0] == target.id:
                            source = None    # x = x[0]: the name moves on
                        bindings.setdefault(target.id, []).append((node, source))
                    else:
                        for name in ast.walk(target):
                            if isinstance(name, ast.Name) and isinstance(name.ctx, ast.Store):
                                bindings.setdefault(name.id, []).append((node, None))
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)) \
                    and isinstance(node.target, ast.Name) and getattr(node, 'value', None):
                if isinstance(node, ast.AnnAssign):
                    source = _root(node.value)
                    bindings.setdefault(node.target.id, []).append((node, source))

        def seen_elsewhere(root, node, end=False):
            """Whether the object under *root* is looked at again: read after
            *node*, or under a name the function does not own (a parameter, a
            name of the module), which its caller or another function reads."""
            return (root in params or root in declared or root not in bindings
                    or _read_after(root, node, nodes, end))

        for name, change in _changes(nodes):
            line = _line(change)
            seen = _last_binding(bindings.get(name, []), line)
            if seen is not None and isinstance(seen[0], (ast.For, ast.AsyncFor)) \
                    and isinstance(change, ast.Call) and change.func.attr == 'append' \
                    and isinstance(change.func.value, ast.Name) and name not in params \
                    and not _walks_positions(seen[0]) and _walked(seen[0].iter) \
                    and seen_elsewhere(_walked(seen[0].iter)[0], seen[0], end=True):
                # x[k] = v and the other changers of a loop variable are
                # refused in features/item_assignment.py; append is the
                # compiler's own and came through.
                _refuse(change,
                        cause=('%s is the variable of a for loop. CPython changes the '
                               'item of the list being walked; on the phone a list or '
                               'a dict is text, so only this copy would change.' % name),
                        suggestions=['Walk the positions and change the item where it '
                                     'lives: for i in range(len(%s)): %s[i].append(...).'
                                     % (_text(seen[0].iter), _text(seen[0].iter))],
                        received=_text(change))
            if seen is None or seen[1] is None or name in params \
                    or not seen_elsewhere(seen[1][0], change):
                pass                         # nobody looks at the first object again
            else:
                source = seen[1][1]
                _refuse(change,
                        cause=('%s = %s (line %d) makes %s another name for the same '
                               'object, so in CPython this change reaches %s too. On '
                               'the phone a list or a dict is a value of its own: only '
                               '%s would change.' % (name, _text(source), _line(seen[0]),
                                                     name, _text(source), name)),
                        suggestions=[
                            'Change it where it lives: write %s in place of %s here.'
                            % (_text(source), name),
                            'Or make %s a copy of its own: %s = %s.copy() for a dict, '
                            'list(%s) for a list. Then %s stays as it was, in CPython '
                            'too.' % (name, name, _text(source), _text(source),
                                      _text(source)),
                        ],
                        received=_text(change))
            # The other way round: l2 = l1, then l1 changes and l2 is read.
            for other, other_bindings in bindings.items():
                if other == name:
                    continue
                for assign, source in other_bindings:
                    if source is None or source[0] != name \
                            or not isinstance(source[1], ast.Name) or _line(assign) >= line:
                        continue
                    if _last_binding(other_bindings, line) != (assign, source):
                        continue
                    if any(isinstance(n, ast.Name) and n.id == other
                           and isinstance(n.ctx, ast.Load) and _line(n) > line
                           for n in nodes):
                        _refuse(change,
                                cause=('%s = %s (line %d) makes %s another name for '
                                       'this object, so in CPython %s sees this change '
                                       'too. On the phone %s kept what %s held then.'
                                       % (other, name, _line(assign), other, other,
                                          other, name)),
                                suggestions=[
                                    'If %s is meant to keep the old items, make it a '
                                    'copy: %s = list(%s), or %s.copy() for a dict.'
                                    % (other, other, name, name),
                                    'If it is meant to follow %s, read %s instead.'
                                    % (name, name),
                                ],
                                received=_text(change))


def _walks_positions(loop):
    it = loop.iter
    return isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range'


def _returns(fn, name):
    return any(isinstance(n, ast.Return) and isinstance(n.value, ast.Name)
               and n.value.id == name for n in _statements(fn))


def _handed_lists(tree):
    """def add(cart, x): cart.append(x) -- called with a list that has a name
    and does not take the answer back."""
    functions = {fn.name: fn for fn in getattr(tree, 'body', [])
                 if isinstance(fn, ast.FunctionDef)}
    changed = {}                             # function -> {param: the change}
    for name, fn in functions.items():
        params = [a.arg for a in fn.args.args]
        for root, change in _changes(_statements(fn)):
            if root in params and not any(
                    isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == root
                                                      for t in n.targets)
                    and _line(n) < _line(change) and _root(n.value) is None
                    and not _guarded_by_none(fn, n)
                    for n in _statements(fn)):
                changed.setdefault(name, {}).setdefault(root, change)
    if not changed:
        return
    module_names = {t.id for node in getattr(tree, 'body', []) if isinstance(node, ast.Assign)
                    for t in node.targets if isinstance(t, ast.Name)}
    up = _parents([tree])
    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id in changed):
            continue
        fn = functions[call.func.id]
        params = [a.arg for a in fn.args.args]
        for param, change in changed[call.func.id].items():
            index = params.index(param)
            given = call.args[index] if index < len(call.args) else next(
                (kw.value for kw in call.keywords if kw.arg == param), None)
            if given is None or isinstance(given, ast.Starred):
                continue
            if not (_root(given) or isinstance(given, ast.Attribute)):
                continue                     # a list written out, or a call's answer
            parent = up.get(call)
            taken_back = (isinstance(parent, ast.Assign) and len(parent.targets) == 1
                          and ast.dump(_loaded(parent.targets[0])) == ast.dump(_loaded(given))
                          and _returns(fn, param))
            if taken_back:
                continue
            arg = _text(given)
            back = '%s = %s' % (arg, _text(call))
            tip = ('Have %s() end with return %s, and take the answer back: %s.'
                   % (fn.name, param, back)) if not _returns(fn, param) \
                else 'Take the answer back: %s.' % back
            if isinstance(given, ast.Name) and given.id in module_names \
                    and _inside_a_function(call, up):
                tip += ' %s is a name of the module, so the function also needs global %s.' \
                       % (given.id, given.id)
            _refuse(call,
                    cause=('%s() changes %s, the list or dict it is given (line %d), and '
                           'here that is %s. In CPython %s changes with it; on the phone '
                           '%s() works on a copy, and %s stays as it was.'
                           % (fn.name, param, _line(change), arg, arg, fn.name, arg)),
                    suggestions=[tip],
                    received=_text(call))


def _guarded_by_none(fn, assign):
    """`if tags is None: tags = []`: the caller's list still arrives untouched."""
    for node in _statements(fn):
        if isinstance(node, ast.If) and assign in node.body:
            return True
    return False


def _loaded(node):
    """A copy of *node* with every ctx made Load, to compare a target with a value."""
    import copy
    node = copy.deepcopy(node)
    for n in ast.walk(node):
        if hasattr(n, 'ctx'):
            n.ctx = ast.Load()
    return node


def _inside_a_function(node, up):
    parent = up.get(node)
    while parent is not None:
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return True
        parent = up.get(parent)
    return False


def check(tree):
    """Stop the build where CPython would share one list or dict that the
    phone would copy. Run on the code as it was written."""
    _defaults(tree)
    _aliases(tree)
    _handed_lists(tree)
    return tree
