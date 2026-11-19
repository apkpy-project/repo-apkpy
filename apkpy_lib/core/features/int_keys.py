# -*- coding: utf-8 -*-
"""A dict whose keys are whole numbers, read back with the keys as numbers.

On the phone the keys of a dict are kept as text, the JSON way: {1: 'a'} is
{"1": "a"}. Looking a key up (d[1], 1 in d, d.get(1)) finds it, as the key it
looks for is written the same way. Reading the keys back gave the text:
str(d) showed {'1': 'a'}, sorted(d) put '10' before '9'. Until 1.15.1 that
stopped the build (numeric._refuse_number_keys_read_back).

When every key a dict is ever given is a whole number, the places that read
its keys back are written here in Python that turns each key into the number
again, which the compiler translates as it is:

    for k in d:                    for _apkpy_ik1 in d:
                                       k = int(_apkpy_ik1)
    for k, v in d.items():         for _apkpy_ik2 in d:
                                       k = int(_apkpy_ik2)
                                       v = d[_apkpy_ik2]
    sorted(d), max(d), list(d)     sorted([int(_apkpy_ik3) for _apkpy_ik3 in d]) ...
    [k * 2 for k in d]             [k * 2 for k in [int(_apkpy_ik4) for _apkpy_ik4 in d]]
    str(d), print(d), f"{d}"       "{" + ", ".join([str(int(x)) + ": " + str([d[x]])[1:-1]
                                                    for x in d]) + "}"

str([value])[1:-1] is the value as Python shows it inside a dict: 'a', 2.5,
None, [1, 'x']. The Previewer runs the Python as written, so it never sees
any of this.

A dict that is ever given a key that is not certainly a whole number -- text,
a float (2.0 and 2 are one key in Python, two on the phone), True -- or that
is filled some other way (update(), a copy, a function's answer), keeps the
refusal.
"""

import ast

_COUNT = [0]


def _fresh():
    _COUNT[0] += 1
    return "_apkpy_ik%d" % _COUNT[0]


def reset():
    _COUNT[0] = 0


def _placed(expr, like):
    for node in ast.walk(expr):
        ast.copy_location(node, like)
    return ast.fix_missing_locations(expr)


def keys_expr(name, like):
    """[int(x) for x in name]: the keys as numbers, in the dict's order."""
    x = _fresh()
    return _placed(ast.parse("[int(%s) for %s in %s]" % (x, x, name), mode="eval").body, like)


def shown_expr(name, like):
    """The text str(name) gives in Python, for a dict with whole-number keys."""
    x = _fresh()
    text = '"{" + ", ".join([str(int(%s)) + ": " + str([%s[%s]])[1:-1] for %s in %s]) + "}"' % (
        x, name, x, x, name)
    return _placed(ast.parse(text, mode="eval").body, like)


def _statement(text, like):
    stmt = ast.parse(text).body[0]
    return _placed(stmt, like)


def iter_name(node):
    """The dict name a loop or a call reads the keys of: d or d.keys()."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr == 'keys' and not node.args and not node.keywords \
            and isinstance(node.func.value, ast.Name):
        return node.func.value.id
    return None


def items_name(node):
    """d of d.items()."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr == 'items' and not node.args and not node.keywords \
            and isinstance(node.func.value, ast.Name):
        return node.func.value.id
    return None


def rewrite_for(node):
    """for k in d / for k, v in d.items(), in place. False when it is another shape."""
    target = node.target
    name = iter_name(node.iter)
    if name is not None and isinstance(target, ast.Name):
        x = _fresh()
        first = [_statement("%s = int(%s)" % (target.id, x), node)]
    else:
        name = items_name(node.iter)
        if name is None or not (isinstance(target, ast.Tuple) and len(target.elts) == 2
                                and all(isinstance(e, ast.Name) for e in target.elts)):
            return False
        x = _fresh()
        key, value = target.elts
        first = [_statement("%s = int(%s)" % (key.id, x), node),
                 _statement("%s = %s[%s]" % (value.id, name, x), node)]
    node.target = _placed(ast.Name(id=x, ctx=ast.Store()), target)
    node.iter = _placed(ast.Name(id=name, ctx=ast.Load()), node.iter)
    node.body[:0] = first
    return True


def rewrite_comprehension(node):
    """[... for k in d]: the loop goes over the keys as numbers."""
    name = iter_name(node.iter)
    if name is None or not isinstance(node.target, ast.Name):
        return False
    node.iter = keys_expr(name, node.iter)
    return True


# str(d) and the like show the dict; these take its keys as a list.
SHOWN_BY = ('str', 'repr', 'print', 'toast')
LISTED_BY = ('list', 'sorted', 'tuple', 'set', 'max', 'min', 'sum', 'enumerate', 'zip')


def rewrite_call(node):
    """str(d), print(d), x.set_value(d), sorted(d), max(d.keys())... in place."""
    if not node.args:
        return False
    arg = node.args[0]
    func = node.func
    called = func.id if isinstance(func, ast.Name) else None
    if (called in SHOWN_BY or isinstance(func, ast.Attribute) and func.attr == 'set_value') \
            and isinstance(arg, ast.Name):
        node.args[0] = shown_expr(arg.id, arg)
        if called == 'repr':
            node.func = _placed(ast.Name(id='str', ctx=ast.Load()), func)
        return True
    if called in LISTED_BY and iter_name(arg) is not None:
        node.args[0] = keys_expr(iter_name(arg), arg)
        return True
    return False


def rewrite_formatted(node):
    """f"{d}" and f"{d!r}": the dict as str(d) shows it."""
    if node.format_spec is not None or not isinstance(node.value, ast.Name) \
            or node.conversion not in (-1, ord('s'), ord('r')):
        return False
    node.value = shown_expr(node.value.id, node.value)
    node.conversion = -1
    return True
