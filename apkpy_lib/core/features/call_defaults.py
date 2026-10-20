# -*- coding: utf-8 -*-
"""Default values of the app's own functions, filled in at each call.

    def greet(name, greeting="Hello"):
        return greeting + " " + name

    out.set_value(greet("Ana"))
    out.set_value(greet(greeting="Hi", name="Rui"))

Every Python function becomes a Java method with one parameter per name, and
Java has no default values. The call kept the arguments it was given, so
``greet("Ana")`` called a method of two parameters with one, and javac stopped
the build with an error about generated code. A call by name inside an
expression lost its keywords altogether.

So before anything is translated, each call to a function of the module is
rewritten into the call the person would have written in full: the keywords
moved to their places, and each parameter left out given its default.

A default is read once, when Python runs the ``def``. Writing it into each
call is the same thing for a value that cannot change in between: a literal,
which is all this accepts. Anything else stops the build with ``U2037``, as
does a call that leaves out a parameter without a default -- a TypeError in
CPython.
"""

import ast
import copy

CODE = "U2037"
DOCS = "https://repo-apkpy.pages.dev/compatibility/"


def _fail(call, message, cause, suggestions):
    from ...diagnostics import ApkpyError
    from ..unsupported import describe
    raise ApkpyError(
        message,
        code=CODE,
        title="This call does not match the function",
        cause=cause,
        expected="every parameter filled exactly once",
        received=describe(call),
        suggestions=list(suggestions),
        docs=DOCS,
        line=getattr(call, "lineno", 0) or 0,
        path=getattr(call, "_apkpy_file", ""),
    )


def _literal(node):
    """True for a default that is the same value every time it is read."""
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return False
    return True


def _signatures(tree):
    """name -> (parameters, defaults by name) for plain module functions.

    A function with *args, **kwargs or keyword-only parameters is left alone:
    the rest of the compiler does not take those either, and says so.
    """
    found = {}
    for node in getattr(tree, "body", []):
        if not isinstance(node, ast.FunctionDef):
            continue
        args = node.args
        if args.vararg or args.kwarg or args.kwonlyargs or getattr(args, "posonlyargs", []):
            continue
        names = [arg.arg for arg in args.args]
        defaults = dict(zip(names[len(names) - len(args.defaults):], args.defaults))
        found[node.name] = (names, defaults)
    return found


def fill(tree):
    """Rewrite the calls to the module's functions with every argument."""
    signatures = _signatures(tree)
    if not any(defaults for _, defaults in signatures.values()) and not any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in signatures and node.keywords
            for node in ast.walk(tree)):
        return tree

    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id in signatures):
            continue
        name = call.func.id
        params, defaults = signatures[name]
        if any(isinstance(arg, ast.Starred) for arg in call.args) \
                or any(kw.arg is None for kw in call.keywords):
            continue                         # f(*xs) / f(**d): not lined up here
        if len(call.args) > len(params):
            continue                         # the arity check elsewhere says so
        if len(call.args) == len(params) and not call.keywords:
            continue

        filled = list(call.args) + [None] * (len(params) - len(call.args))
        for kw in call.keywords:
            if kw.arg not in params:
                _fail(call, "%s() has no parameter called %s." % (name, kw.arg),
                      "ApkPy lines a call up with the parameters the function "
                      "declares, and this name is not one of them.",
                      ["Check the spelling against def %s(%s)."
                       % (name, ", ".join(params))])
            index = params.index(kw.arg)
            if filled[index] is not None:
                _fail(call, "%s() was given %s twice." % (name, kw.arg),
                      "It arrives once by position and once by name.",
                      ["Pass it either by position or by name, not both."])
            filled[index] = kw.value

        missing = []
        for index, node in enumerate(filled):
            if node is not None:
                continue
            param = params[index]
            default = defaults.get(param)
            if default is None:
                missing.append(param)
                continue
            if not _literal(default):
                _fail(call, "%s() leaves out %s, whose default ApkPy cannot copy."
                      % (name, param),
                      "A default is read once, when Python runs the def. ApkPy "
                      "writes it into each call instead, which is the same only "
                      "for a value written out: a number, text, True or False, "
                      "or a list or dict of those.",
                      ["Pass %s in the call." % param])
            filled[index] = ast.copy_location(copy.deepcopy(default), call)
        if missing:
            _fail(call, "%s() needs %s." % (name, ", ".join(missing)),
                  "Every parameter without a default has to be given, as in "
                  "CPython, where this call stops with a TypeError.",
                  ["Pass %s in the call." % ", ".join(missing)])
        call.args = filled
        call.keywords = []
    return tree
