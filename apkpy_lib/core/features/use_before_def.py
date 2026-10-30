"""A name used at the top of the file before the line that makes it.

Python runs a module from top to bottom, so ``button("Save", command=save)``
above ``def save():`` stops the app with NameError before its first screen:
in the Previewer and in any Python. The compiler reads the whole file before
it writes Java, so the build passed and the phone's app worked, while the
Previewer did not start. Stopped here, with the Previewer's own error (E1201).

Only what runs while the file is read is looked at: a function's body, a
lambda's body and a class body are left alone (they run later, or have their
own names), and a name the same statement gives itself (a for target) is
not reported. A name is reported only when the file makes it further down,
and not before -- a builtin, or one a star import may bring, never is.
"""

import ast
import builtins

from ...diagnostics import ApkpyError

DOCS = "https://repo-apkpy.pages.dev/friendly-errors/"
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _run_now(node):
    """The nodes of *node* that run as the module is read."""
    stack = [node]
    while stack:
        here = stack.pop()
        yield here
        if isinstance(here, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Decorators and defaults run when the def does; the body later.
            stack.extend(here.decorator_list)
            stack.extend(d for d in here.args.defaults if d is not None)
            stack.extend(d for d in here.args.kw_defaults if d is not None)
            continue
        if isinstance(here, ast.Lambda):
            stack.extend(d for d in here.args.defaults if d is not None)
            stack.extend(d for d in here.args.kw_defaults if d is not None)
            continue
        if isinstance(here, ast.ClassDef):
            stack.extend(here.decorator_list)
            stack.extend(here.bases)
            stack.extend(k.value for k in here.keywords)
            continue
        if isinstance(here, (ast.arg, ast.arguments)):
            continue        # annotations are left alone
        stack.extend(ast.iter_child_nodes(here))


def _made_by(stmt):
    """The names a module-level statement makes ('*' for a star import)."""
    names = set()
    for node in _run_now(stmt):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add('*' if alias.name == '*'
                          else (alias.asname or alias.name).split('.')[0])
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.comprehension):
            for target in ast.walk(node.target):
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _apkpy_names():
    import apkpy_lib
    return set(getattr(apkpy_lib, '__all__', None) or dir(apkpy_lib))


def check(tree, source_name="writehere.py"):
    """Raise E1201 for the first name read before the line that makes it."""
    body = list(getattr(tree, 'body', []) or [])
    made = [_made_by(stmt) for stmt in body]
    later = {}
    for i in range(len(body) - 1, -1, -1):
        for name in made[i]:
            later[name] = body[i]
    known = set(dir(builtins)) | {'__name__', '__file__', '__doc__', '__builtins__'}
    star = False
    for i, stmt in enumerate(body):
        own = made[i]
        for node in _run_now(stmt):
            if not (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)):
                continue
            name = node.id
            if name in known or name in own:
                continue
            maker = None
            for j in range(i + 1, len(body)):
                if name in made[j]:
                    maker = body[j]
                    break
            if maker is None:
                continue
            if star and name in _apkpy_names():
                continue
            raise _error(name, node, maker, stmt, source_name)
        known |= own
        star = star or '*' in own
    return tree


def _error(name, node, maker, stmt, source_name):
    line = getattr(node, 'lineno', 0)
    where = getattr(maker, 'lineno', 0)
    is_def = isinstance(maker, (ast.FunctionDef, ast.AsyncFunctionDef))
    suggestions = ["Move what makes '%s' (line %d) above line %d." % (name, where, line)]
    if is_def:
        suggestions.append(
            "Or write command=lambda: %s(): the lambda looks the name up when "
            "it runs, after the whole file has been read." % name)
    return ApkpyError(
        "name '%s' is not defined: line %d uses it, and line %d makes it."
        % (name, line, where),
        code="E1201",
        title="A name is used before it exists",
        cause=("Python runs the file from top to bottom, so a name used above "
               "the line that creates it (a function, a component, a value) "
               "does not exist yet. The Previewer stops here with NameError, "
               "and so would any Python."),
        expected="'%s' made above line %d" % (name, line),
        received=name,
        suggestions=suggestions,
        docs=DOCS,
        line=line,
        column=getattr(node, 'col_offset', 0) + 1,
        path=source_name,
    )
