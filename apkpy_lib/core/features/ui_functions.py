# -*- coding: utf-8 -*-
"""Functions that build UI, written once and called on several screens.

    def header(title, screen):
        label(title, id="title", screen=screen)
        button("Back", id="back", screen=screen, command=go_home)

    header("Home", home)
    header("Profile", profile)

The Previewer runs this as Python and it simply works. The compiler used to
refuse it (``U2033`` on the ``label()`` inside the function): Android declares
every screen as XML before the app runs, and a function body was read as code
that runs later, on a tap. So every header, card or bar that appeared on five
screens had to be written five times.

A call like this is not "code that runs later" -- it is a template, and the
compiler now treats it as one. Before anything is translated, each call on its
own line at module level is replaced by the function's body, with the
arguments put where the parameters were and the function's own names made
unique to that call. What is left is the module the person would have written
by hand, and the rest of the compiler reads it as it always did. It is the same
thing Python does when the Previewer runs the function.

Three things follow:

* ``t = header("Home", home)`` binds ``t`` to what the function returns -- a
  component the function created -- so ``t.set_value(...)`` works later.
* ``for title in ["A", "B", "C"]: card(title, home)`` at module level is
  unrolled when what it walks over is written in the file.
* A function that builds UI can only be called on its own line at module
  level. Called from a tap, or passed as a callback, it would build screens
  after they exist; that stops the build with ``U2038`` instead of vanishing.
"""

import ast
import copy

# What builds a screen. A function whose body calls one of these -- or calls a
# function that does -- is a UI function. Deliberately not here: row() and
# column(), which only describe an arrangement for responsive(); action() and
# card_action(), which are arguments; and the date and time pickers, which open
# a dialog while the app runs and belong in callbacks.
UI_FACTORIES = frozenset({
    "button", "inputs", "input_field", "label", "container", "card", "image",
    "video", "camera_view", "map_view", "avatar", "list_row", "list_view",
    "virtual_collection", "markdown", "rich_text", "tree_view", "carousel",
    "grid", "spinner", "skeleton", "empty_state", "error_state",
    "upload_button", "app_bar", "sliver_app_bar", "bottom_nav", "drawer",
    "mini_player", "responsive", "tooltip", "modal", "bottom_sheet", "menu",
    "popup_menu", "context_menu", "pager", "tab", "chart",
})

MAX_DEPTH = 20
CODE = "U2038"
# What the compiler reads as "the row of a virtual_collection": a container
# that belongs to no screen. Only the expansion below writes it.
ROW_FACTORY = "__apkpy_row__"
DOCS = "https://repo-apkpy.pages.dev/guides/modules/"


def _fail(message, node, cause, suggestions, received=""):
    from ...diagnostics import ApkpyError
    raise ApkpyError(
        message,
        code=CODE,
        title="This function builds UI, and ApkPy cannot place it here",
        cause=cause,
        expected="a UI function called on its own line at module level",
        received=received or message,
        suggestions=list(suggestions),
        docs=DOCS,
        line=getattr(node, "lineno", 0),
        path=getattr(node, "_apkpy_file", ""),
    )


def _called_name(node):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id
    return None


def ui_functions(tree):
    """Names of the module-level functions that build UI (a fixed point: a
    function that calls a UI function builds UI too)."""
    defs = {node.name: node for node in tree.body
            if isinstance(node, ast.FunctionDef)}
    found = set()
    changed = True
    while changed:
        changed = False
        for name, function in defs.items():
            if name in found:
                continue
            for node in ast.walk(function):
                called = _called_name(node)
                if called in UI_FACTORIES or called in found:
                    found.add(name)
                    changed = True
                    break
    return {name: defs[name] for name in found}


def _first_ui_call(function, functions):
    """What makes *function* a UI function, for the message."""
    for node in ast.walk(function):
        called = _called_name(node)
        if called in UI_FACTORIES or (called in functions and called != function.name):
            return called
    return "a component"


def _screens(tree):
    """``home = Screen(id="home")`` -> {"home": "home"}, for ``screen.id``."""
    screens = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and _called_name(node.value) == "Screen":
            call = node.value
            value = call.args[0] if call.args else next(
                (k.value for k in call.keywords if k.arg == "id"), None)
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                screens[node.targets[0].id] = value.value
    return screens


def _module_lists(tree):
    lists = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, (ast.List, ast.Tuple)):
            lists[node.targets[0].id] = node.value
    return lists


# ── binding the arguments ───────────────────────────────────────────────────

def _bind(function, call):
    """{parameter: argument node}, the way Python would bind them."""
    spec = function.args
    if spec.vararg or spec.kwarg or spec.kwonlyargs or spec.posonlyargs:
        _fail("%s() takes *args, **kwargs or keyword-only parameters"
              % function.name, function,
              cause="A function that builds UI is expanded where it is "
                    "called, and ApkPy binds plain parameters only.",
              suggestions=["Give %s() plain parameters: def %s(title, screen)."
                           % (function.name, function.name)])
    names = [arg.arg for arg in spec.args]
    defaults = dict(zip(names[len(names) - len(spec.defaults):], spec.defaults))
    if len(call.args) > len(names):
        _fail("%s() takes %d arguments, got %d"
              % (function.name, len(names), len(call.args)), call,
              cause="The call passes more arguments than the function has "
                    "parameters.",
              suggestions=["Check the call against def %s(%s)."
                           % (function.name, ", ".join(names))])
    bound = dict(zip(names, call.args))
    for keyword in call.keywords:
        if keyword.arg is None or keyword.arg not in names or keyword.arg in bound:
            _fail("%s() got an unexpected or repeated argument %s"
                  % (function.name, keyword.arg), call,
                  cause="Every parameter is filled once, by position or by name.",
                  suggestions=["Check the call against def %s(%s)."
                               % (function.name, ", ".join(names))])
        bound[keyword.arg] = keyword.value
    for name in names:
        if name not in bound:
            if name not in defaults:
                _fail("%s() is missing the argument %s" % (function.name, name),
                      call, cause="Every parameter without a default has to be "
                                  "given.",
                      suggestions=["Pass %s in the call." % name])
            bound[name] = defaults[name]
    return bound


# ── the function's own names ────────────────────────────────────────────────

def _assigned_names(statements):
    names = []
    for statement in statements:
        for node in ast.walk(statement):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) \
                    and node.id not in names:
                names.append(node.id)
    return names


class _Substitute(ast.NodeTransformer):
    """Parameters become their arguments; the function's own names become
    names of this call. A lambda's own parameters shadow both."""

    def __init__(self, bound, renamed):
        self.bound = bound
        self.renamed = renamed
        self.shadowed = [set()]

    def visit_Lambda(self, node):
        self.shadowed.append({arg.arg for arg in node.args.args})
        node.body = self.visit(node.body)
        node.args.defaults = [self.visit(d) for d in node.args.defaults]
        self.shadowed.pop()
        return node

    def visit_Name(self, node):
        if node.id in self.shadowed[-1]:
            return node
        if node.id in self.bound:
            if not isinstance(node.ctx, ast.Load):
                _fail("a UI function assigns to its parameter %s" % node.id, node,
                      cause="Parameters are replaced by the arguments of each "
                            "call, so there is nothing to assign to.",
                      suggestions=["Use a new name: text = %s + \"...\"." % node.id])
            return ast.copy_location(copy.deepcopy(self.bound[node.id]), node)
        if node.id in self.renamed:
            return ast.copy_location(
                ast.Name(id=self.renamed[node.id], ctx=node.ctx), node)
        return node


class _Fold(ast.NodeTransformer):
    """``screen.id`` of a known screen, and text joined from constants, become
    the text itself -- an ``id=`` has to be written out for the layout."""

    def __init__(self, screens):
        self.screens = screens

    def visit_Attribute(self, node):
        self.generic_visit(node)
        if node.attr == "id" and isinstance(node.value, ast.Name) \
                and node.value.id in self.screens and isinstance(node.ctx, ast.Load):
            return ast.copy_location(ast.Constant(self.screens[node.value.id]), node)
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Add) and isinstance(node.left, ast.Constant) \
                and isinstance(node.right, ast.Constant) \
                and isinstance(node.left.value, str) and isinstance(node.right.value, str):
            return ast.copy_location(ast.Constant(node.left.value + node.right.value), node)
        return node

    def visit_Subscript(self, node):
        # for card in [{"title": "A"}, ...]: tile(card["title"], home)
        self.generic_visit(node)
        key = node.slice
        if isinstance(node.value, ast.Dict) and isinstance(key, ast.Constant) \
                and isinstance(node.ctx, ast.Load):
            for dict_key, dict_value in zip(node.value.keys, node.value.values):
                if isinstance(dict_key, ast.Constant) and dict_key.value == key.value:
                    return ast.copy_location(copy.deepcopy(dict_value), node)
        return node

    def visit_Call(self, node):
        # label("Item " + str(i)) inside an unrolled range()
        self.generic_visit(node)
        if _called_name(node) == "str" and len(node.args) == 1 and not node.keywords \
                and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, (str, int)) \
                and not isinstance(node.args[0].value, bool):
            return ast.copy_location(ast.Constant(str(node.args[0].value)), node)
        return node

    def visit_JoinedStr(self, node):
        self.generic_visit(node)
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue) and value.conversion == -1 \
                    and value.format_spec is None and isinstance(value.value, ast.Constant) \
                    and isinstance(value.value.value, (str, int)) \
                    and not isinstance(value.value.value, bool):
                parts.append(str(value.value.value))
            else:
                return node
        return ast.copy_location(ast.Constant("".join(parts)), node)


# ── expanding ───────────────────────────────────────────────────────────────

class _Expander:

    def __init__(self, tree):
        self.functions = ui_functions(tree)
        self.screens = _screens(tree)
        self.lists = _module_lists(tree)
        self.counter = {}

    def _suffix(self, name):
        self.counter[name] = self.counter.get(name, 0) + 1
        return "%s%d" % (name, self.counter[name])

    def expand_call(self, function, call, target, stack):
        if function.name in stack:
            _fail("%s() calls itself while building UI" % function.name, call,
                  cause="A UI function is expanded where it is called; one that "
                        "calls itself would never finish.",
                  suggestions=["Build the repeated part with a loop over a "
                               "list written in the file."])
        if len(stack) >= MAX_DEPTH:
            _fail("UI functions nested more than %d deep" % MAX_DEPTH, call,
                  cause="Each call is expanded into the next.",
                  suggestions=["Flatten the chain of functions."])
        bound = _bind(function, call)
        body = copy.deepcopy(function.body)
        if body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            body = body[1:]                                   # docstring

        returned = None
        for index, statement in enumerate(body):
            for node in ast.walk(statement):
                if isinstance(node, (ast.Global, ast.Nonlocal, ast.FunctionDef,
                                     ast.ClassDef, ast.Yield, ast.YieldFrom)):
                    _fail("%s() uses %s" % (function.name, type(node).__name__),
                          node, cause="A UI function is expanded where it is "
                                      "called; this has no place in that.",
                          suggestions=["Keep the function to statements that "
                                       "build the UI."])
                if isinstance(node, ast.Return) and not (
                        index == len(body) - 1 and node is statement):
                    _fail("%s() returns before its end" % function.name, node,
                          cause="A UI function is expanded where it is called, "
                                "so every line of it becomes part of the "
                                "screen; a return in the middle would drop the "
                                "rest.",
                          suggestions=["Return once, on the last line."])
        if body and isinstance(body[-1], ast.Return):
            returned = body.pop().value
        gives_back = returned is not None

        suffix = self._suffix(function.name)
        own = [name for name in _assigned_names(body) if name not in bound]
        renamed = {name: "%s__%s" % (name, suffix) for name in own}
        if target and isinstance(returned, ast.Name) and returned.id in renamed:
            renamed[returned.id] = target                     # t = header(...)
            returned = None
        body = [_Substitute(bound, renamed).visit(statement) for statement in body]
        if returned is not None:
            value = _Substitute(bound, renamed).visit(returned)
            if target:
                body.append(ast.copy_location(ast.Assign(
                    targets=[ast.Name(id=target, ctx=ast.Store())], value=value,
                    lineno=returned.lineno), returned))
            elif not isinstance(value, ast.Name):
                body.append(ast.copy_location(ast.Expr(value=value), returned))
        elif target and not gives_back:
            _fail("%s = %s(...) but %s() returns nothing"
                  % (target, function.name, function.name), call,
                  cause="The name would be bound to None, and nothing on the "
                        "screen would answer to it.",
                  suggestions=["End %s() with return <the component>, or call "
                               "it on its own line." % function.name])
        body = [_Fold(self.screens).visit(statement) for statement in body]
        for statement in body:
            ast.fix_missing_locations(statement)
        return self.expand_block(body, stack + (function.name,))

    def unroll(self, loop, stack):
        items = self._iterable(loop.iter)
        if items is None:
            _fail("a loop builds UI from something that is not written in the file",
                  loop,
                  cause="Screens are declared before the app runs, so a loop "
                        "that builds UI is unrolled while compiling -- which "
                        "needs its list written in the file, or range(N).",
                  suggestions=[
                      "Loop over a list literal, a list defined at the top of "
                      "the file, or range(N).",
                      "For rows that arrive while the app runs, use list_view() "
                      "or virtual_collection() and set_items().",
                  ])
        if loop.orelse:
            _fail("a loop that builds UI has an else", loop,
                  cause="ApkPy unrolls a `for` that builds UI; an else on it "
                        "has nothing to run after.",
                  suggestions=["Move the else lines below the loop."])
        targets = self._target_names(loop.target)
        expanded = []
        for item in items:
            bound = self._bind_item(loop, targets, item)
            suffix = self._suffix("for")
            body = copy.deepcopy(loop.body)
            own = [name for name in _assigned_names(body) if name not in bound]
            renamed = {name: "%s__%s" % (name, suffix) for name in own}
            body = [_Substitute(bound, renamed).visit(statement)
                    for statement in body]
            body = [_Fold(self.screens).visit(statement) for statement in body]
            for statement in body:
                ast.fix_missing_locations(statement)
            expanded.extend(self.expand_block(body, stack))
        return expanded

    @staticmethod
    def _target_names(target):
        """`for page` or `for page, title, copy` -- names only."""
        if isinstance(target, ast.Name):
            return target.id
        if isinstance(target, (ast.Tuple, ast.List)) and target.elts \
                and all(isinstance(e, ast.Name) for e in target.elts):
            return [e.id for e in target.elts]
        _fail("a loop that builds UI unpacks into something other than names",
              target, cause="ApkPy unrolls `for a, b in [...]` into plain names.",
              suggestions=["Write the loop as for a, b in [(x, y), ...]:."])

    @staticmethod
    def _bind_item(loop, targets, item):
        if isinstance(targets, str):
            return {targets: item}
        if not isinstance(item, (ast.Tuple, ast.List)) or len(item.elts) != len(targets):
            _fail("a loop unpacks %d names from an item that does not have %d"
                  % (len(targets), len(targets)), item,
                  cause="Each item of the list has to be written as a tuple "
                        "with one value per name.",
                  suggestions=["Write every item as (%s)." % ", ".join(targets)])
        return dict(zip(targets, item.elts))

    def _iterable(self, node):
        if isinstance(node, (ast.List, ast.Tuple)):
            return list(node.elts)
        if isinstance(node, ast.Name) and node.id in self.lists:
            return list(self.lists[node.id].elts)
        if _called_name(node) == "range" and node.args and not node.keywords \
                and all(isinstance(a, ast.Constant) and isinstance(a.value, int)
                        and not isinstance(a.value, bool) for a in node.args):
            return [ast.Constant(value) for value in range(*[a.value for a in node.args])]
        return None

    def _builds_ui(self, statements):
        for statement in statements:
            for node in ast.walk(statement):
                called = _called_name(node)
                if called in self.functions or called in UI_FACTORIES:
                    return True
        return False

    def expand_row(self, statement, call, stack):
        """``virtual_collection(..., row=post_row)``: the function builds one
        row. It is expanded once, with its parameter bound to a template
        container that belongs to no screen, and the collection gets that
        container instead of the function -- the same thing the Previewer does
        when it calls post_row(row) once."""
        for keyword in call.keywords:
            if keyword.arg != "row" or not isinstance(keyword.value, ast.Name):
                continue
            function = self.functions.get(keyword.value.id)
            if function is None:
                continue
            spec = function.args
            if len(spec.args) != 1 or spec.vararg or spec.kwarg or spec.kwonlyargs:
                _fail("%s() builds a row and takes %d parameters"
                      % (function.name, len(spec.args)), keyword.value,
                      cause="virtual_collection(row=...) calls the function once, "
                            "with the row to build into as its only argument.",
                      suggestions=["Write it as def %s(row): ... parent=row ..."
                                   % function.name])
            template = "__row_%s" % self._suffix("row")
            collection_id = next(
                (k.value.value for k in call.keywords
                 if k.arg == "id" and isinstance(k.value, ast.Constant)
                 and isinstance(k.value.value, str)), None)
            factory = ast.Call(
                func=ast.Name(id=ROW_FACTORY, ctx=ast.Load()), args=[],
                keywords=([ast.keyword(arg="id", value=ast.Constant(collection_id + "_row"))]
                          if collection_id else []))
            made = [ast.copy_location(ast.Assign(
                targets=[ast.Name(id=template, ctx=ast.Store())], value=factory,
                lineno=statement.lineno), statement)]
            build = ast.copy_location(ast.Call(
                func=ast.Name(id=function.name, ctx=ast.Load()),
                args=[ast.Name(id=template, ctx=ast.Load())], keywords=[]), call)
            made.extend(self.expand_call(function, build, None, stack))
            keyword.value = ast.copy_location(ast.Name(id=template, ctx=ast.Load()),
                                              keyword.value)
            for node in made:
                ast.fix_missing_locations(node)
            return made
        return []

    def expand_block(self, statements, stack=()):
        result = []
        for statement in statements:
            call, target = None, None
            if isinstance(statement, ast.Expr):
                call = statement.value
            elif isinstance(statement, ast.Assign) and len(statement.targets) == 1 \
                    and isinstance(statement.targets[0], ast.Name):
                call, target = statement.value, statement.targets[0].id
            name = _called_name(call)
            if name == "virtual_collection":
                result.extend(self.expand_row(statement, call, stack))
            if name in self.functions:
                result.extend(self.expand_call(self.functions[name], call, target, stack))
            elif isinstance(statement, ast.For) and self._builds_ui(statement.body):
                result.extend(self.unroll(statement, stack))
            else:
                result.append(statement)
        return result


def _statement_calls(statements, functions, allowed):
    """The calls that stand on their own line -- at module level, inside a
    module-level for (which is unrolled), or inside another UI function."""
    for statement in statements:
        value = statement.value if isinstance(statement, (ast.Expr, ast.Assign)) else None
        if _called_name(value) in functions:
            allowed.add(id(value.func))
        if isinstance(statement, ast.For):
            _statement_calls(statement.body, functions, allowed)


def _misplaced_use(tree, functions):
    """A UI function named anywhere else than a call on its own line."""
    allowed = set()
    _statement_calls(tree.body, functions, allowed)
    for function in functions.values():
        _statement_calls(function.body, functions, allowed)
    # virtual_collection(row=post_row) passes the function on purpose.
    for node in ast.walk(tree):
        if _called_name(node) == "virtual_collection":
            for keyword in node.keywords:
                if keyword.arg == "row" and isinstance(keyword.value, ast.Name):
                    allowed.add(id(keyword.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in functions \
                and id(node) not in allowed:
            return node
    return None


def expand(tree):
    """Replace every module-level call of a UI function by its body."""
    expander = _Expander(tree)
    if not expander.functions:
        if any(isinstance(s, ast.For) and expander._builds_ui(s.body) for s in tree.body):
            tree.body = expander.expand_block(tree.body)
        return tree
    misplaced = _misplaced_use(tree, expander.functions)
    if misplaced is not None:
        _fail("%s() builds UI, and it is used here as a value or from "
              "inside another function" % misplaced.id, misplaced,
              cause="%s() builds UI: it calls %s(). Android lays out every "
                    "screen before the app runs, so a function that builds UI "
                    "is expanded where it is called at module level; called "
                    "later -- from a tap, a callback, a job -- it would build "
                    "a screen that already exists."
                    % (misplaced.id, _first_ui_call(expander.functions[misplaced.id],
                                                    expander.functions)),
              suggestions=[
                  "Call %s() on its own line at module level, once per "
                  "screen it builds." % misplaced.id,
                  "To change what a screen shows later, create the "
                  "component up front and use set_value(), show() or "
                  "hide().",
              ],
              received=misplaced.id)
    body = [s for s in tree.body
            if not (isinstance(s, ast.FunctionDef) and s.name in expander.functions)]
    tree.body = expander.expand_block(body)
    return tree


__all__ = ["UI_FACTORIES", "CODE", "ROW_FACTORY", "ui_functions", "expand"]
