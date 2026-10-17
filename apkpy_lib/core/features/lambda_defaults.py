# -*- coding: utf-8 -*-
"""A lambda's default values, bound where Python binds them.

    for target, name in [(insta, "Camera"), (chat, "Chat")]:
        button(name, command=lambda t=target: on_click_navigate(t), screen=home)

``t=target`` is how Python gives each button its own screen: a default is
read once, when the lambda is made, so every button keeps the screen of its
own turn of the loop. The Previewer runs that as Python and it works.

The compiler read a lambda's parameters and never its defaults. ``t`` reached
the Java as a name nothing declared: ``on_click_navigate(t)`` was dropped
without a word -- six menu buttons that did nothing on a phone -- and
``toast(t)`` became ``String.valueOf(t)``, which javac refused with an error
about generated code.

So before anything is translated, each parameter that has a default is
replaced, inside the lambda's body, by the default itself, and leaves the
parameter list. After the loop has been unrolled the default is the value of
that turn (``insta``, ``"Camera"``), and what is left is the lambda the person
would have written for one button.

That is exact when the default cannot change between the moment the lambda is
made and the moment it runs: a literal, or a name bound once. A name the
program binds again -- a loop variable of a loop that stays a loop, a counter
-- is refused with ``U2039``: Python would keep the value it had when the
lambda was made, and the phone would read the one it has at the tap.
"""

import ast
import copy

CODE = "U2039"
DOCS = "https://repo-apkpy.pages.dev/friendly-errors/"

# A binding inside a loop runs once per turn: it is never "bound once".
_LOOPS = (ast.For, ast.AsyncFor, ast.While)
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _fail(lam, param, default, reason):
    from ...diagnostics import ApkpyError
    from ..unsupported import describe
    shown = describe(default)
    raise ApkpyError(
        "lambda %s=%s: the value of %s can change before the tap" % (param, shown, shown),
        code=CODE,
        title="This lambda keeps a value ApkPy cannot keep",
        cause=(
            "A default like %s=%s is read once, when the lambda is made. On a "
            "phone the lambda's body reads the value when it runs, so ApkPy "
            "can only keep that promise for a value that cannot change in "
            "between -- %s." % (param, shown, reason)),
        expected="a default that is a literal, or a name bound once",
        received="lambda %s=%s" % (param, shown),
        suggestions=[
            "Write the value itself: lambda: toast(\"12.4K\").",
            "Or keep it in state() or the database, and read it in the callback.",
        ],
        docs=DOCS,
        line=getattr(lam, "lineno", 0),
        path=getattr(lam, "_apkpy_file", ""),
    )


def _names_in_target(target):
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            yield from _names_in_target(element)
    elif isinstance(target, ast.Starred):
        yield from _names_in_target(target.value)


def _binding_counts(scope):
    """How many times each name is bound in `scope`'s own body.

    Nested functions, lambdas and classes are their own scopes and are not
    entered. A binding inside a loop counts twice: it happens on every turn.
    """
    counts = {}

    def bind(name, times=1):
        counts[name] = counts.get(name, 0) + times

    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        arguments = scope.args
        for arg in (arguments.posonlyargs + arguments.args
                    + arguments.kwonlyargs):
            bind(arg.arg)
        for arg in (arguments.vararg, arguments.kwarg):
            if arg is not None:
                bind(arg.arg)

    def walk(node, in_loop):
        times = 2 if in_loop else 1
        if isinstance(node, (ast.Assign,)):
            for target in node.targets:
                for name in _names_in_target(target):
                    bind(name, times)
        elif isinstance(node, (ast.AnnAssign,)) and node.value is not None:
            for name in _names_in_target(node.target):
                bind(name, times)
        elif isinstance(node, ast.AugAssign):
            for name in _names_in_target(node.target):
                bind(name, 2)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            for name in _names_in_target(node.target):
                bind(name, 2)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    for name in _names_in_target(item.optional_vars):
                        bind(name, times)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bind((alias.asname or alias.name).split(".")[0], times)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bind(node.name, 2)
        elif isinstance(node, ast.NamedExpr):
            for name in _names_in_target(node.target):
                bind(name, 2)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            bind(node.name, times)
            return
        if isinstance(node, ast.Lambda):
            return
        inside = in_loop or isinstance(node, _LOOPS)
        for child in ast.iter_child_nodes(node):
            walk(child, inside)

    for statement in scope.body:
        walk(statement, False)
    return counts


def _global_writes(tree):
    """Names a function rebinds at module level through `global`."""
    written = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            declared = set()
            for inner in ast.walk(node):
                if isinstance(inner, ast.Global):
                    declared.update(inner.names)
            if declared:
                written.update(name for name, _ in _binding_counts(node).items()
                               if name in declared)
    return written


class _Substitute(ast.NodeTransformer):
    """Put `values[name]` where the body reads `name`, leaving alone the
    places where a nested lambda or a comprehension binds the same name."""

    def __init__(self, values):
        self.values = values

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.values:
            return ast.copy_location(copy.deepcopy(self.values[node.id]), node)
        return node

    def visit_Lambda(self, node):
        own = {a.arg for a in (node.args.posonlyargs + node.args.args
                               + node.args.kwonlyargs)}
        for arg in (node.args.vararg, node.args.kwarg):
            if arg is not None:
                own.add(arg.arg)
        node.args = self.visit(node.args)
        kept = {k: v for k, v in self.values.items() if k not in own}
        node.body = _Substitute(kept).visit(node.body) if kept else node.body
        return node

    def _comprehension(self, node):
        bound = set()
        for generator in node.generators:
            bound.update(_names_in_target(generator.target))
        kept = {k: v for k, v in self.values.items() if k not in bound}
        inner = _Substitute(kept)
        for generator in node.generators:
            generator.iter = self.visit(generator.iter)
            generator.ifs = [inner.visit(test) for test in generator.ifs]
        for field in ("elt", "key", "value"):
            if getattr(node, field, None) is not None:
                setattr(node, field, inner.visit(getattr(node, field)))
        return node

    visit_ListComp = visit_SetComp = visit_GeneratorExp = _comprehension
    visit_DictComp = _comprehension


def _stable(default, scopes, counts, written):
    """'' when `default` cannot change before the lambda runs, else why."""
    if isinstance(default, ast.Constant):
        return ""
    if (isinstance(default, ast.UnaryOp) and isinstance(default.op, (ast.USub, ast.UAdd))
            and isinstance(default.operand, ast.Constant)):
        return ""
    if isinstance(default, (ast.Tuple, ast.List)):
        for element in default.elts:
            reason = _stable(element, scopes, counts, written)
            if reason:
                return reason
        return ""
    if isinstance(default, ast.Dict):
        for part in list(default.keys) + list(default.values):
            if part is None:
                return "a dict unpacked with ** is read when it runs"
            reason = _stable(part, scopes, counts, written)
            if reason:
                return reason
        return ""
    if isinstance(default, ast.Name):
        # The innermost scope that binds the name owns it.
        for scope in reversed(scopes):
            times = counts[id(scope)].get(default.id, 0)
            if times:
                if isinstance(scope, ast.Module) and default.id in written:
                    return "%s is changed by a function (global)" % default.id
                if times > 1:
                    return ("%s is bound more than once (in a loop, or "
                            "assigned again)" % default.id)
                return ""
        return ""   # a builtin, or an import ApkPy resolves by name
    from ..unsupported import describe
    return "%s is computed, not a name or a literal" % describe(default)


def bind(tree):
    """Replace every lambda default by its value inside the lambda. In place;
    returns the tree."""
    written = _global_writes(tree)
    counts = {}

    def visit(node, scopes):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)):
            counts[id(node)] = _binding_counts(node)
            scopes = scopes + [node]
        if isinstance(node, ast.Lambda):
            _bind_one(node, scopes, counts, written)
        for child in ast.iter_child_nodes(node):
            visit(child, scopes)

    visit(tree, [])
    return tree


def _bind_one(lam, scopes, counts, written):
    arguments = lam.args
    positional = arguments.posonlyargs + arguments.args
    defaults = arguments.defaults
    with_default = positional[len(positional) - len(defaults):] if defaults else []
    values = {}
    for arg, default in zip(with_default, defaults):
        values[arg.arg] = default
    for arg, default in zip(arguments.kwonlyargs, arguments.kw_defaults):
        if default is not None:
            values[arg.arg] = default
    if not values:
        return
    for name, default in values.items():
        reason = _stable(default, scopes, counts, written)
        if reason:
            _fail(lam, name, default, reason)
    for node in ast.walk(lam.body):
        if isinstance(node, ast.NamedExpr):
            for name in _names_in_target(node.target):
                if name in values:
                    _fail(lam, name, values[name],
                          "%s is assigned again inside the lambda" % name)
    lam.body = _Substitute(values).visit(lam.body)
    # Defaults are always the trailing positionals, so what remains has none.
    arguments.posonlyargs = [a for a in arguments.posonlyargs if a.arg not in values]
    arguments.args = [a for a in arguments.args if a.arg not in values]
    arguments.defaults = []
    kept_kw = [(a, d) for a, d in zip(arguments.kwonlyargs, arguments.kw_defaults)
               if a.arg not in values]
    arguments.kwonlyargs = [a for a, _ in kept_kw]
    arguments.kw_defaults = [d for _, d in kept_kw]
    ast.fix_missing_locations(lam)
