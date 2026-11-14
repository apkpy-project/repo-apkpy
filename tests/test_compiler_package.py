"""The compiler is a package (apkpy_lib/core/compiler/): modules that only need the ones listed before them.

Three mistakes here give no error at all, only an app built wrong, so they are checked by reading the modules:
a value of state.py bound again instead of changed in place, one name defined in two modules, and one method
written in two of the classes that the reader, or a screen's Activity, is made of.
"""
import ast
import os
import re
import symtable
import unittest

import apkpy_lib.core.compiler as compiler

FOLDER = os.path.dirname(compiler.__file__)


def listed():
    """The modules, in the order the package's docstring gives them."""
    return re.findall(r"^    (\w+)  +\S", compiler.__doc__, re.M)


def files_of(name):
    """The files of a module of the package: its own, or every one of the folder it is."""
    path = os.path.join(FOLDER, name)
    if os.path.isdir(path):
        return sorted(os.path.join(path, found) for found in os.listdir(path) if found.endswith(".py"))
    return [path + ".py"]


def source(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def defined(tree):
    """The names a module gives a value to at its own level, imports aside."""
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif not isinstance(node, (ast.Import, ast.ImportFrom)):
            names += [sub.id for sub in ast.walk(node)
                      if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store)]
    return names


def scopes(table):
    yield table
    for child in table.get_children():
        for scope in scopes(child):
            yield scope


class TheCompilerPackage(unittest.TestCase):

    def test_the_docstring_lists_every_module(self):
        found = []
        for name in os.listdir(FOLDER):
            if name.endswith(".py") and name != "__init__.py":
                found.append(name[:-3])
            elif os.path.isfile(os.path.join(FOLDER, name, "__init__.py")):
                found.append(name)
        self.assertEqual(sorted(listed()), sorted(found))
        self.assertEqual(listed()[0], "state")
        self.assertEqual(listed()[-1], "translate")

    def test_a_module_only_imports_from_the_ones_listed_before_it(self):
        order = listed()
        for position, name in enumerate(order):
            folder = os.path.isdir(os.path.join(FOLDER, name))
            for path in files_of(name):
                for node in ast.walk(ast.parse(source(path))):
                    # from a file of a folder, `..x` is the compiler's module x and `.x` is its neighbour
                    if not isinstance(node, ast.ImportFrom) or node.level != (2 if folder else 1):
                        continue
                    asked = [node.module.split(".")[0]] if node.module else [a.name for a in node.names]
                    for other in asked:
                        self.assertIn(other, order[:position], "%s imports from %s, which is not above %s"
                                      % (os.path.relpath(path, FOLDER), other, name))

    def test_no_name_is_defined_in_two_modules(self):
        where = {}
        for name in listed():
            for path in files_of(name):
                here = os.path.relpath(path, FOLDER)
                for found in defined(ast.parse(source(path))):
                    self.assertNotIn(found, where, "%s is in %s and in %s" % (found, where.get(found), here))
                    where[found] = here

    def test_what_state_holds_is_changed_in_place_and_never_bound_again(self):
        """`from .state import X` gives a module its own name for the one container: after `X = ...`
        somewhere, that module would go on with a container nobody else reads."""
        held = set(defined(ast.parse(source(files_of("state")[0]))))
        self.assertIn("_APP_THEME", held)
        for name in listed():
            if name == "state":
                continue
            for path in files_of(name):
                here = os.path.relpath(path, FOLDER)
                for scope in scopes(symtable.symtable(source(path), here, "exec")):
                    for symbol in scope.get_symbols():
                        if symbol.get_name() in held:
                            self.assertFalse(symbol.is_assigned(), "%s binds %s again in %s"
                                             % (here, symbol.get_name(), scope.get_name()))

    def test_the_names_others_take_still_come_from_the_package(self):
        for name in ("translate_python_to_android", "translate_python_to_java", "MultiScreenTranspiler",
                     "_prepare_android_analysis", "_generate_layout_xml", "_generate_manifest",
                     "_APP_THEME", "_ASSET_BASE_DIR", "_PY_ERRORS", "_ERROR_ALIASES", "_MATH_CALLS"):
            self.assertTrue(hasattr(compiler, name), name)
        from apkpy_lib.core.compiler import state
        self.assertIs(compiler._APP_THEME, state._APP_THEME)


def methods_of(folder):
    """{method: the file it is in} for the classes of a folder; None for one written in two of them."""
    where = {}
    for path in files_of(folder):
        here = os.path.basename(path)
        for node in ast.parse(source(path)).body:
            if isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, ast.FunctionDef):
                        where[method.name] = None if method.name in where else here
    return where


class TheReader(unittest.TestCase):
    """compiler/reader/: one class, MultiScreenTranspiler, whose methods are written in several modules."""

    def test_no_method_is_written_in_two_of_its_classes(self):
        """The second would take the place of the first without a word."""
        where = methods_of("reader")
        self.assertEqual(sorted(name for name, here in where.items() if here is None), [])
        self.assertEqual(where["_parse_statements"], "statements.py")
        self.assertEqual(where["visit_Expr"], "module_level.py")

    def test_a_call_asks_every_family_once(self):
        """_call_statement asks each family whether the call is one of its own; one it forgot would be
        a call the app makes and the phone never gets."""
        where = methods_of("reader")
        families = sorted(name for name, here in where.items()
                          if here in ("calls.py", "view_calls.py") and name != "_call_statement")
        tree = ast.parse(source(os.path.join(FOLDER, "reader", "calls.py")))
        asked = [node.func.attr for method in ast.walk(tree)
                 if isinstance(method, ast.FunctionDef) and method.name == "_call_statement"
                 for node in ast.walk(method)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                 and isinstance(node.func.value, ast.Name) and node.func.value.id == "self"
                 and node.func.attr.endswith("_call")]
        self.assertEqual(sorted(asked), families)
        self.assertGreater(len(families), 8)

    def test_it_reads_a_file_as_before(self):
        from apkpy_lib.core import ast_compat
        from apkpy_lib.core.compiler import MultiScreenTranspiler
        reader = MultiScreenTranspiler()
        reader.visit(ast_compat.parse("\n".join([
            "from apkpy_lib import Screen, button, toast, run",
            "home = Screen(id='home')",
            "def hello():",
            "    toast('hi')",
            "button('Go', command=hello, screen=home)",
            "run(start_screen=home)",
        ])))
        self.assertEqual(list(reader.screens.values()), ["home"])
        self.assertEqual([c["type"] for c in reader.functions["hello"]["cmds"]], ["toast"])


class TheActivityWriter(unittest.TestCase):
    """compiler/activity_java/: one class, ActivityJava, whose methods are written in several modules."""

    def test_no_method_is_written_in_two_of_its_classes(self):
        """The second would take the place of the first without a word."""
        where = methods_of("activity_java")
        self.assertEqual(sorted(name for name, here in where.items() if here is None), [])
        self.assertIn("_val_to_java", where)
        self.assertIn("write", where)

    def test_write_calls_every_part_once(self):
        from apkpy_lib.core.compiler.activity_java import ActivityJava
        tree = ast.parse(source(os.path.join(FOLDER, "activity_java", "__init__.py")))
        cls = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ActivityJava"][0]
        write = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "write"][0]
        called = [n.func.attr for n in ast.walk(write)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and isinstance(n.func.value, ast.Name) and n.func.value.id == "self"]
        self.assertEqual(len(called), len(set(called)))
        parts = [name for name in dir(ActivityJava)
                 if name.startswith(("_write_", "_open_", "_close_", "_number_", "_see_", "_collect_imports"))]
        self.assertEqual(sorted(called), sorted(parts))

    def test_it_is_the_function_the_build_calls(self):
        from apkpy_lib.core.compiler import translate
        from apkpy_lib.core.compiler.activity_java import _generate_activity_java
        self.assertIs(translate._generate_activity_java, _generate_activity_java)


if __name__ == "__main__":
    unittest.main()
