# -*- coding: utf-8 -*-
"""Python names that Java cannot take, given another name before translating.

    default = "tea"          # a Java keyword
    R = 6371                 # the app's R.id..., R.drawable...
    org = form.get_value()   # org.json.JSONArray in the generated code

A local or a module value becomes a Java variable of the same name. `new`,
`default`, `case`, `final` are Java keywords, and javac stopped on the line
the generator wrote. `R`, `View`, `Log`, `org`, `java` are names the
generated Java uses itself: a variable called org hid org.json, and every
JSONArray after it failed to compile. Each such name gets a trailing _ here
(new_), everywhere it is the same name: its uses, the parameters, the
keyword arguments of the app's own functions, global and nonlocal.

What keeps its name: the app's functions and classes (they become
pythonCallback_x and strings), names imported (apkpy_lib's API, modules),
the fields of a class (their names are shown in a dataclass's repr), and
the keyword arguments of any call that is not one of the app's own
functions -- storage.get("k", default="") keeps its default=.
"""

import ast
import builtins

JAVA_KEYWORDS = {
    'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch', 'char',
    'class', 'const', 'continue', 'default', 'do', 'double', 'else', 'enum',
    'extends', 'final', 'finally', 'float', 'for', 'goto', 'if', 'implements',
    'import', 'instanceof', 'int', 'interface', 'long', 'native', 'new',
    'package', 'private', 'protected', 'public', 'return', 'short', 'static',
    'strictfp', 'super', 'switch', 'synchronized', 'this', 'throw', 'throws',
    'transient', 'try', 'void', 'volatile', 'while', 'true', 'false', 'null',
    'var', 'record', 'yield',
}

# Names the generated Java uses for itself.
JAVA_USED = {
    'R', 'View', 'Log', 'String', 'Math', 'Long', 'Double', 'Integer', 'Boolean',
    'Object', 'Character', 'Float', 'Short', 'Byte', 'Number', 'System', 'Thread',
    'Runnable', 'Exception', 'Override', 'Intent', 'Bundle', 'Context', 'Toast',
    'Result', 'StringBuilder', 'Runtime', 'Class',
    'java', 'javax', 'android', 'androidx', 'org', 'com',
}

CLASHES = JAVA_KEYWORDS | JAVA_USED


def rename(tree):
    imported = set()
    defined = set()
    class_fields = set()
    params = {}                 # function name -> its parameter names
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imported.update((a.asname or a.name).split('.')[0] for a in node.names)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(node.name)
            a = node.args
            params[node.name] = {p.arg for p in list(getattr(a, 'posonlyargs', [])) + a.args
                                 + a.kwonlyargs}
        elif isinstance(node, ast.ClassDef):
            defined.add(node.name)
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store) \
                            and not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        class_fields.add(id(sub))
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and stmt.name == '__init__':
                    a = stmt.args
                    params[node.name] = {p.arg for p in a.args + a.kwonlyargs}
    methods = {}                # method name -> parameter names, for obj.m(new=1)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.setdefault(stmt.name, set()).update(
                        p.arg for p in stmt.args.args + stmt.args.kwonlyargs)

    # Only the names the app gives a value itself. int(x) and super() are
    # Python's own: renaming every `int` would break them.
    taken = set(imported) | defined
    bound = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            taken.add(node.id)
            if isinstance(node.ctx, (ast.Store, ast.Del)) and id(node) not in class_fields:
                bound.add(node.id)
        elif isinstance(node, ast.arg):
            taken.add(node.arg)
            bound.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            taken.add(node.name)
            bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
    # double = lambda n: n * 2 becomes a function (nested_functions.py), as
    # pythonCallback_go__double: a name only ever given a lambda keeps it.
    lambdas, other = set(), set()
    from_lambda = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Lambda) \
                and all(isinstance(t, ast.Name) for t in node.targets):
            for target in node.targets:
                lambdas.add(target.id)
                from_lambda.add(id(target))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) \
                and id(node) not in from_lambda:
            other.add(node.id)
        elif isinstance(node, ast.arg):
            other.add(node.arg)
    keep = lambdas - other
    mapping = {}
    for name in sorted(bound & CLASHES - imported - defined - keep - set(dir(builtins))):
        fresh = name + '_'
        while fresh in taken:
            fresh += '_'
        taken.add(fresh)
        mapping[name] = fresh
    if not mapping:
        return tree

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in mapping and id(node) not in class_fields:
            node.id = mapping[node.id]
        elif isinstance(node, ast.arg) and node.arg in mapping:
            node.arg = mapping[node.arg]
        elif isinstance(node, ast.ExceptHandler) and node.name in mapping:
            node.name = mapping[node.name]
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            node.names = [mapping.get(n, n) for n in node.names]
        elif isinstance(node, ast.Call):
            func = node.func
            own = set()
            if isinstance(func, ast.Name) and func.id in params:
                own = params[func.id]
            elif isinstance(func, ast.Attribute) and func.attr in methods \
                    and not (isinstance(func.value, ast.Name) and func.value.id in imported):
                own = methods[func.attr]
            for keyword in node.keywords:
                if keyword.arg in mapping and keyword.arg in own:
                    keyword.arg = mapping[keyword.arg]
    return tree
