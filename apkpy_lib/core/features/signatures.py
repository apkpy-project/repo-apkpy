# -*- coding: utf-8 -*-
"""The parameters of the app's own functions, in the one shape Java has.

    def sub(a, b, /):          positional-only
        ...
    def box(w, *, h=2):        keyword-only
        ...

A Java method has one list of parameters. In a program that runs on CPython
the calls already pass a positional-only or keyword-only parameter the way
its mark asks, so each is an ordinary parameter from here on: they are moved
into the plain list before the defaults are filled in (call_defaults.py).
They used to stop the build pointing at the body ("cannot translate a - b"),
because the names were never declared.

*args and **kwargs that the body reads, and a call that spreads a list or a
dict into one of the app's functions (``f(*items)``, ``f(**options)``), are
not translated yet. They used to pass and give Java that javac refused; they
stop here, at their line, with what to write instead. A ``*args`` the body
never reads (``def on_tap(*_):``) is dropped, as it gives the body nothing,
and so are the values a call passes to it (``many(1, 2, 3)`` is
``many(1)``): javac refused the call with the method left with one parameter.
A value that calls something is refused, as Python would still run it.
"""

import ast

from .. import unsupported

# The functions whose unread *args or **kwargs was dropped: a call through a
# value (features/function_values.py) checks how many values it gets, and
# these take any number.
DROPPED = set()


def _reads(fn, name):
    return any(isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load)
               for n in ast.walk(fn))


def _plain(fn):
    """The parameters a call fills by position, as the person wrote them."""
    a = fn.args
    return [p.arg for p in list(getattr(a, "posonlyargs", [])) + list(a.args)]


def flatten(fn):
    """posonly and kwonly parameters moved into the one plain list (classes.py
    calls it for a method, before the method becomes a function)."""
    a = fn.args
    params = list(getattr(a, "posonlyargs", [])) + list(a.args)
    defaults = list(a.defaults)
    if a.kwonlyargs:
        has = [False] * (len(params) - len(defaults)) + [True] * len(defaults)
        has += [d is not None for d in a.kw_defaults]
        first = next((i for i, h in enumerate(has) if h), len(has))
        if not all(has[first:]):
            required = [k.arg for k, d in zip(a.kwonlyargs, a.kw_defaults) if d is None]
            unsupported.raise_unsupported(
                fn, cause="A keyword-only parameter without a default after one with a "
                          "default is not translated yet: %s." % ", ".join(required),
                suggestions=["Give %s a default, or put it before the ones that have one."
                             % required[0]])
        defaults += [d for d in a.kw_defaults if d is not None]
        params += list(a.kwonlyargs)
    a.posonlyargs = []
    a.args = params
    a.defaults = defaults
    a.kwonlyargs = []
    a.kw_defaults = []


def normalise(tree):
    """Plain parameter lists for the module's functions; refuse what Java cannot hold."""
    DROPPED.clear()
    takes = {}          # name -> (positional count, parameter names, star, stars)
    defined = {}
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef):
            defined[fn.name] = defined.get(fn.name, 0) + 1
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        a = fn.args
        name = fn.name
        star_dropped = stars_dropped = False
        if a.vararg is not None:
            star = a.vararg.arg
            if _reads(fn, star):
                params = _plain(fn)
                unsupported.raise_unsupported(
                    fn, cause="def %s(*%s) is not translated yet: a Java method takes a "
                              "fixed number of values." % (name, star),
                    suggestions=["Take a list instead: def %s(%s) and call %s(%s)."
                                 % (name, ", ".join(params + [star]), name,
                                    ", ".join(params + ["[1, 2, 3]"]))])
            a.vararg = None
            star_dropped = True
        if a.kwarg is not None:
            stars = a.kwarg.arg
            if _reads(fn, stars):
                params = _plain(fn) + [p.arg for p in a.kwonlyargs]
                unsupported.raise_unsupported(
                    fn, cause="def %s(**%s) is not translated yet: a Java method takes "
                              "named values only as its own parameters." % (name, stars),
                    suggestions=["Take a dict instead: def %s(%s) and call %s(%s)."
                                 % (name, ", ".join(params + [stars]), name,
                                    ", ".join(params + ['{"a": 1}']))])
            a.kwarg = None
            stars_dropped = True
        if getattr(a, "posonlyargs", None) or a.kwonlyargs:
            flatten(fn)
        if star_dropped or stars_dropped:
            DROPPED.add(name)
            if defined.get(name) == 1:
                takes[name] = (len(a.args), {p.arg for p in a.args},
                               star_dropped, stars_dropped)
    if takes:
        _trim_calls(tree, takes)
    return tree


def _has_effect(node):
    return any(isinstance(n, (ast.Call, ast.NamedExpr, ast.Await, ast.Yield, ast.YieldFrom))
               for n in ast.walk(node))


def _trim_calls(tree, takes):
    """many(1, 2, 3) of def many(x, *_): many(1), the values the body never reads
    left out. One that calls something stops the build: Python works it out."""
    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id in takes):
            continue
        count, names, star, stars = takes[call.func.id]
        extra = call.args[count:] if star else []
        unknown = [k for k in call.keywords if stars and k.arg is not None and k.arg not in names]
        for value in extra + [k.value for k in unknown]:
            if _has_effect(value):
                unsupported.raise_unsupported(
                    value, cause="%s() never reads this value: ApkPy leaves it out of the "
                                 "call, and Python would still work it out, calling what "
                                 "it calls." % call.func.id,
                    suggestions=["Work it out on the line before, if it has to run: "
                                 "value = ..., then %s(...)." % call.func.id])
        if extra:
            call.args = call.args[:count]
        if unknown:
            call.keywords = [k for k in call.keywords if k not in unknown]


def refuse_spread(tree):
    """f(*items) and f(**options) on the app's own functions and methods.

    Read before the classes become functions, so the message names
    cart.add and not the function it becomes.
    """
    functions = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    methods = {m.name for c in tree.body if isinstance(c, ast.ClassDef)
               for m in c.body if isinstance(m, ast.FunctionDef)}
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        if isinstance(call.func, ast.Name) and call.func.id in functions:
            name = call.func.id
        elif isinstance(call.func, ast.Attribute) and call.func.attr in methods                 and isinstance(call.func.value, ast.Name):
            name = "%s.%s" % (call.func.value.id, call.func.attr)
        else:
            continue
        spread = [x for x in call.args if isinstance(x, ast.Starred)]
        spread += [k for k in call.keywords if k.arg is None]
        if spread:
            unsupported.raise_unsupported(
                call, cause="%s(*...) and %s(**...) are not translated yet: each value "
                            "has to go to its parameter by itself." % (name, name),
                suggestions=["Pass the values one by one: %s(items[0], items[1])." % name])
