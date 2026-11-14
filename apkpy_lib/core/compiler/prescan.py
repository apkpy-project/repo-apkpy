"""The module's own names, read first: globals, constants, functions as values."""
import ast
import json

from .. import unsupported

from .state import _GLOBALS, _MUTATED_LISTS, _SINGLETON_CONSTS
from .expressions import _escape_java_literal, _mutated_list_key, _mutated_list_read
from .numeric import _numeric_arg_kind


def _global_key(name):
    """The key of a `global` name in the shared store. A module list the app
    also appends to keeps the key it already had, so both write one list."""
    if name in _MUTATED_LISTS[0]:
        return _mutated_list_key(name)
    return "__apkpy_global_" + name


class _SingletonSeed(str):
    """The starting value of a global that is None, True or False.

    Read back as ApkpyValues.NONE / TRUE / FALSE, not as the words: the words
    "False" are not empty, and `if ON:` would be true on the first tap.
    """


def _singleton_name(value):
    if value is None:
        return "NONE"
    return "TRUE" if value else "FALSE"


def _imported_names(tree):
    found = set()
    for node in getattr(tree, 'body', []):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                found.add((alias.asname or alias.name).split('.')[0])
    return found


def _bound_names(tree):
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            found.add(node.id)
        elif isinstance(node, ast.arg):
            found.add(node.arg)
    return found


def _functions_used_as_values(tree):
    """Functions of the module whose call is used as a value somewhere.

    str(log(x)) uses the answer of a function that never says return: Python
    gives None. The Java method was void and the call could not compile.
    A call on its own line, or as the body of a lambda handed to a button,
    does not count: nothing reads it.
    """
    defs = {node.name for node in getattr(tree, 'body', []) if isinstance(node, ast.FunctionDef)}
    ignored = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr):
            ignored.add(id(node.value))
        elif isinstance(node, ast.Lambda):
            ignored.add(id(node.body))
    return {node.func.id for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in defs and id(node) not in ignored}


def _module_singletons(tree):
    """Module-level names whose every value is None, True or False."""
    found, other = {}, set()
    for node in getattr(tree, 'body', []):
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        for target in targets:
            if not isinstance(target, ast.Name):
                continue
            if isinstance(value, ast.Constant) and (value.value is None
                                                    or isinstance(value.value, bool)):
                found[target.id] = _singleton_name(value.value)
            else:
                other.add(target.id)
    return {name: kind for name, kind in found.items() if name not in other}


def _singleton_fields():
    return ['    private static final String %s = ApkpyValues.%s;' % (name, kind)
            for name, kind in _SINGLETON_CONSTS[0].items()]


def _global_read(name):
    """Read a `global` name, starting from its module-level value."""
    if name in _MUTATED_LISTS[0]:
        return _mutated_list_read(name)
    seed = _GLOBALS[0][name][0]
    if isinstance(seed, _SingletonSeed):
        return 'ApkpyReactiveState.get("%s", ApkpyValues.%s)' % (_global_key(name), seed)
    return 'ApkpyReactiveState.get("%s", "%s")' % (
        _global_key(name), _escape_java_literal(seed))


def _queue_global_write(cmds, since, stmt):
    """After NAME = ... in a function that said `global NAME`, store the value.

    Only when the statement wrote the name as a local (a command with that
    'var'): the Java local holds the new value, and the store gets it next.
    """
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
            and isinstance(stmt.targets[0], ast.Name):
        name = stmt.targets[0].id
    elif isinstance(stmt, (ast.AugAssign, ast.AnnAssign)) \
            and isinstance(stmt.target, ast.Name):
        name = stmt.target.id
    else:
        return
    if name not in _GLOBALS[0]:
        return
    if any(isinstance(c, dict) and c.get('var') == name and c.get('type') != 'for_loop'
           for c in cmds[since:]):
        cmds.append({'type': 'global_sync', 'name': name})


def _global_sync_java(name):
    return 'ApkpyReactiveState.set("%s", String.valueOf(%s));' % (_global_key(name), name)


def _own_nodes(fn):
    """The nodes of a function's own body, without the functions inside it."""
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.Lambda, ast.ClassDef)):
                stack.append(child)


def _function_bindings(fn):
    """(name, new value or None, statement) for each name *fn* binds.

    The value is None where the name is bound some other way than = and +=:
    a for loop, unpacking, with ... as, a parameter.
    """
    args = fn.args
    for arg in (list(getattr(args, 'posonlyargs', [])) + list(args.args)
                + list(args.kwonlyargs) + [a for a in (args.vararg, args.kwarg) if a]):
        yield arg.arg, None, fn
    for node in _own_nodes(fn):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and len(node.targets) == 1:
                    yield target.id, node.value, node
                    continue
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                        yield sub.id, None, node
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            yield node.target.id, ast.BinOp(
                left=ast.Name(id=node.target.id, ctx=ast.Load()),
                op=node.op, right=node.value), node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.value is not None:
            yield node.target.id, node.value, node
        else:
            targets = []
            if isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
                targets.append(node.target)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                targets.extend(item.optional_vars for item in node.items
                               if item.optional_vars is not None)
            elif isinstance(node, getattr(ast, 'NamedExpr', ())):
                targets.append(node.target)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                yield node.name, None, node
            for target in targets:
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Name):
                        yield sub.id, None, node


def _prescan_globals(tree, numeric_names, returns=None, numeric_params=None):
    """The module names a function rebinds after `global NAME`.

    Returns {name: (starting value as text, is_float or None)}. The kind is a
    number only when the start and every new value are numbers; one value
    that is not and the name is text, like any other name.
    """
    module_values = {}
    for node in getattr(tree, 'body', []):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            module_values[node.targets[0].id] = node
    functions = [node for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    declared = {}
    for fn in functions:
        names = set()
        for node in _own_nodes(fn):
            if isinstance(node, ast.Global):
                names.update(node.names)
        declared[fn] = names
    bindings = {fn: list(_function_bindings(fn)) for fn in functions}

    rebound = {name for fn in functions for name, _, stmt in bindings[fn]
               if name in declared[fn] and stmt is not fn}
    if not rebound:
        return {}

    found, values = {}, {}
    for name in sorted(rebound):
        for fn in functions:
            for bound, value, stmt in bindings[fn]:
                if bound != name:
                    continue
                if name not in declared[fn]:
                    unsupported.raise_unsupported(
                        stmt,
                        cause=('%s is a module variable that another function '
                               'changes with global %s. Here the same name is '
                               'a new local one, which ApkPy cannot keep apart '
                               'from the module variable.' % (name, name)),
                        suggestions=['Add global %s at the top of %s(), or give '
                                     'the local a different name.' % (name, fn.name)],
                        received='%s in %s()' % (name, fn.name),
                    )
                if value is None:
                    unsupported.raise_unsupported(
                        stmt,
                        cause=('After global %s, ApkPy translates %s = value and '
                               '%s += value. This statement gives it a new value '
                               'another way.' % (name, name, name)),
                        suggestions=['Assign it on a line of its own: %s = ...' % name],
                    )
                values.setdefault(name, []).append((fn, value))
        start = module_values.get(name)
        if start is None:
            seed, kind = "", None
        else:
            try:
                literal = ast.literal_eval(start.value)
            except (ValueError, TypeError, SyntaxError):
                literal = start
            if literal is None or isinstance(literal, bool):
                seed, kind = _SingletonSeed(_singleton_name(literal)), None
                literal = True    # written out: not refused below
            elif isinstance(literal, int):
                seed, kind = str(literal), False
            elif isinstance(literal, float):
                seed, kind = repr(literal), True
            elif isinstance(literal, str):
                seed, kind = literal, None
            elif isinstance(literal, (list, tuple, dict)):
                try:
                    seed = json.dumps(literal, ensure_ascii=False, allow_nan=False,
                                      separators=(',', ':'))
                except (TypeError, ValueError):
                    seed = None
                kind = None
                if seed is None:
                    literal = start
            if literal is start or literal is None:
                unsupported.raise_unsupported(
                    start,
                    cause=('%s changes inside a function (global %s), so its '
                           'starting value has to be written out: a number, '
                           'text, True or False, or a list or dict of those.'
                           % (name, name)),
                    suggestions=['Start it with a value: %s = 0, or %s = "".'
                                 % (name, name)],
                )
        found[name] = (seed, kind)

    # A new value can read another global (TOTAL = TOTAL + COUNT): settle.
    for _ in range(4):
        changed = False
        known = dict(numeric_names or {})
        known.update({n: k for n, (_, k) in found.items() if k is not None})
        for name, pairs in values.items():
            seed, kind = found[name]
            if kind is None:
                continue
            for fn, value in pairs:
                scope = dict(known)
                scope.update((numeric_params or {}).get(fn.name) or {})
                new = _numeric_arg_kind(value, scope, returns)
                if new is None:
                    kind = None
                    break
                kind = bool(kind or new)
            if kind != found[name][1]:
                found[name] = (seed, kind)
                changed = True
        if not changed:
            break
    return found
