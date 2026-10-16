"""More than one file, so an app can be taken apart.

ApkPy reads one ``writehere.py`` and does not translate Python classes, so an
application that grows has nowhere to put anything: every screen, every
callback and every helper lands in the same file. This lets that file import
plain Python modules sitting next to it and share their functions and
constants across screens.

The merge happens on the AST, before any prescan runs: everything downstream
keeps seeing a single module, so the parser, the generators and the two copies
of ``_gen_cmds`` did not have to learn about files.

Only the whole-module form is accepted::

    import helpers                 # helpers.py, next to writehere.py
    import helpers as h

    reading.set_value(helpers.format_price(total))

``from helpers import format_price`` is refused on purpose. ApkPy merges every
definition in the file into one namespace, so the ``from`` form would import
names the Previewer's real Python would not -- the kind of quiet difference
between the desktop and the phone this project keeps removing.

A helper module holds **functions and constants**. Screens, themes, widgets and
CSS stay in ``writehere.py``, where the compiler can see them in order.
"""
import ast
import os

from ...diagnostics import ApkpyError

DOCS = "https://repo-apkpy.pages.dev/guides/modules/"

#: Imports the compiler already understands; they never name a local file.
KNOWN = frozenset({"math", "re", "apkpy_lib"})

#: Values a helper module may bind to a name. A ``Screen(...)`` or a
#: ``Theme(...)`` is a call, and calls are not on this list.
_CONSTANT_NODES = (ast.Constant, ast.List, ast.Tuple, ast.Dict, ast.Set,
                   ast.UnaryOp, ast.BinOp, ast.JoinedStr)

# The files merged into the last compilation, for callers that report them.
_MERGED = [[]]


def merged_files():
    """The helper modules pulled into the last transpilation, in order."""
    return list(_MERGED[0])


def _fail(message, *, node=None, cause="", suggestions=(), received="",
          path=""):
    raise ApkpyError(
        message,
        code="U2036",
        title="This module could not be merged",
        cause=cause,
        expected="import <file>, where <file>.py sits next to writehere.py "
                 "and holds functions and constants",
        received=received,
        suggestions=list(suggestions),
        docs=DOCS,
        line=getattr(node, "lineno", 0),
        path=path,
    )


def _stamp(tree, file_name):
    """Remember which file every node came from, so a refusal can say so."""
    for node in ast.walk(tree):
        if not getattr(node, "_apkpy_file", ""):
            node._apkpy_file = file_name


def source_file(node):
    """The helper file a node came from, or "" for the application itself."""
    return getattr(node, "_apkpy_file", "") or ""


def _module_level_names(body):
    """Names a module body binds at the top level."""
    names = set()
    for node in body:
        if isinstance(node, ast.FunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _local_import(node, base_dir):
    """(alias, module, path) when this import names a file next to the app."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name in KNOWN or "." in alias.name:
                continue
            path = os.path.join(base_dir, alias.name + ".py")
            if os.path.isfile(path):
                return (alias.asname or alias.name), alias.name, path
        return None
    if isinstance(node, ast.ImportFrom):
        if node.level or not node.module or node.module in KNOWN:
            return None
        if "." in node.module:
            return None
        path = os.path.join(base_dir, node.module + ".py")
        if os.path.isfile(path):
            names = ", ".join(a.name for a in node.names)
            _fail(
                'ApkPy cannot read "from %s import %s".' % (node.module, names),
                node=node,
                cause="ApkPy merges the whole helper file into one namespace, "
                      "so the from-import form would give your app names that "
                      "the Previewer's own Python would not have. Only the "
                      "whole-module form keeps the two runtimes saying the "
                      "same thing.",
                received="from %s import %s" % (node.module, names),
                suggestions=[
                    "Write: import %s" % node.module,
                    "Then call it as %s.%s(...)." % (
                        node.module, node.names[0].name),
                ],
            )
    return None


def _check_helper_body(body, file_name):
    """A helper holds functions and constants -- nothing that builds a screen."""
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue                                    # docstring
        if isinstance(node, ast.Assign):
            if isinstance(node.value, _CONSTANT_NODES) and all(
                    isinstance(t, ast.Name) for t in node.targets):
                continue
            received = "a call" if isinstance(node.value, ast.Call) else \
                type(node.value).__name__
            name = next((t.id for t in node.targets
                         if isinstance(t, ast.Name)), "that name")
            _fail(
                'ApkPy cannot merge "%s" from %s.' % (name, file_name),
                node=node,
                cause="A helper module holds functions and constants. This "
                      "line builds a value by calling something, and ApkPy "
                      "reads screens, themes and widgets in the order they "
                      "appear in writehere.py -- it cannot place this one.",
                received=received,
                suggestions=[
                    "Keep %s in writehere.py." % name,
                    "Leave functions and plain values (text, numbers, lists, "
                    "dicts) in %s." % file_name,
                ],
                path=file_name,
            )
            continue
        _fail(
            "ApkPy cannot merge %s from %s." % (
                type(node).__name__.lower(), file_name),
            node=node,
            cause="A helper module holds functions and constants, and this is "
                  "neither.",
            received=type(node).__name__,
            suggestions=["Move it to writehere.py, or turn it into a "
                         "function that writehere.py calls."],
            path=file_name,
        )


class _Dotted(ast.NodeTransformer):
    """``helpers.format_price(x)`` becomes ``format_price(x)`` after the merge."""

    def __init__(self, alias, module, names, file_name):
        self.alias = alias
        self.module = module
        self.names = names
        self.file_name = file_name
        self.used = set()

    def visit_Attribute(self, node):
        self.generic_visit(node)
        value = node.value
        if isinstance(value, ast.Name) and value.id == self.alias \
                and isinstance(node.ctx, ast.Load):
            if node.attr not in self.names:
                _fail(
                    "%s has no %s." % (self.file_name, node.attr),
                    node=node,
                    cause="ApkPy merged %s and did not find a function or "
                          "constant with that name in it." % self.file_name,
                    received="%s.%s" % (self.alias, node.attr),
                    suggestions=[
                        "Check the spelling, or define %s in %s."
                        % (node.attr, self.file_name),
                    ],
                )
            self.used.add(node.attr)
            replacement = ast.Name(id=node.attr, ctx=node.ctx)
            return ast.copy_location(replacement, node)
        return node


def _merge_into(tree, base_dir, taken, files, owner):
    """Merge this tree's local imports. Returns (definitions, rest, rewriters).

    *taken* and *files* are shared with every nested call, so a helper that
    collides with the application is caught with the same message as one that
    collides with another helper.
    """
    definitions, rest, rewriters = [], [], []

    for node in tree.body:
        found = _local_import(node, base_dir)
        if found is None:
            rest.append(node)
            continue
        alias, module, path = found
        file_name = os.path.basename(path)

        if file_name in files:
            _fail(
                "%s is imported twice." % file_name,
                node=node,
                cause="ApkPy merges each helper once; importing it again "
                      "would define everything in it a second time.",
                received="import %s" % module,
                suggestions=["Remove the second import."],
                path=owner,
            )

        try:
            with open(path, "r", encoding="utf-8") as handle:
                helper_source = handle.read()
        except OSError as exc:
            _fail(
                "ApkPy could not read %s." % file_name,
                node=node,
                cause=str(exc),
                suggestions=["Check the file is readable and saved as UTF-8."],
                path=owner,
            )
        try:
            helper_tree = ast.parse(helper_source, filename=path)
        except SyntaxError as exc:
            _fail(
                "%s has a syntax error on line %s." % (file_name, exc.lineno),
                node=node,
                cause=str(exc.msg),
                received=(exc.text or "").strip(),
                suggestions=["Fix %s and build again." % file_name],
                path=file_name,
            )

        _stamp(helper_tree, file_name)
        _check_helper_body(helper_tree.body, file_name)
        files.append(file_name)

        # A helper that imports another helper: that one is merged first, so
        # its definitions sit above the file that calls them.
        nested_defs, helper_rest, nested_rewriters = _merge_into(
            helper_tree, base_dir, taken, files, file_name)
        rewriters.extend(nested_rewriters)

        names = _module_level_names(helper_rest)
        for name in sorted(names):
            if name in taken:
                _fail(
                    '"%s" is defined twice.' % name,
                    node=node,
                    cause="%s defines %s, and so does %s. ApkPy merges every "
                          "helper into one namespace, so one of them has to "
                          "have another name." % (file_name, name, taken[name]),
                    received=name,
                    suggestions=["Rename %s in one of the two files." % name],
                    path=owner,
                )
            taken[name] = file_name

        definitions.extend(nested_defs)
        definitions.extend(
            n for n in helper_rest
            if not (isinstance(n, ast.Expr)
                    and isinstance(n.value, ast.Constant)))
        rewriters.append(_Dotted(alias, module, names, file_name))

    return definitions, rest, rewriters


def merge(tree, base_dir):
    """Splice every ``import <sibling>`` into *tree*, and return it.

    The helper definitions are prepended and the import statements removed, so
    the rest of the compiler still receives one module. An import ApkPy does
    not recognise is left exactly as it was found, which is why ``import math``
    and everything the compiler already reads keep working.
    """
    _MERGED[0] = []
    if not base_dir or not os.path.isdir(base_dir):
        return tree

    taken = {name: "writehere.py" for name in _module_level_names(tree.body)}
    files = []
    definitions, rest, rewriters = _merge_into(
        tree, base_dir, taken, files, "writehere.py")

    if not definitions:
        return tree

    # An import may sit above or below the code that uses it, so every part of
    # the merged module is rewritten once, after all of them are known.
    for rewriter in rewriters:
        rest = [rewriter.visit(node) for node in rest]
        definitions = [rewriter.visit(node) for node in definitions]

    tree.body = definitions + rest
    ast.fix_missing_locations(tree)
    _MERGED[0] = files
    return tree
