"""The other files of game/: code modules, imported from main.py and from each other.

`from game.battle.engine import BattleEngine` reads game/battle/engine.py (read,
never run, like main.py). A module holds: imports, constants, module state (STATE = GameState()), plain
functions, @dataclass classes, Script classes, and what main.py can declare with
(assets.* and @prefab functions). The game itself (Game, scenes) stays in main.py.

Each module is read once; an import cycle is an error that names the cycle.
"""
import ast
import os

from .scripts import ModuleCode, java_module_name


class Program:
    """Every module of the game, in dependency order (a module comes after what it imports)."""

    def __init__(self, root):
        self.root = root
        self.modules = {}        # "game.battle.engine" -> ModuleCode
        self.order = []          # ModuleCode, dependencies first (main.py is not in it)
        self.loading = []        # (dotted, display) of the files being read: the import chain
        self.names = {}          # class name -> display of its file (Script and @dataclass names are game-wide)
        self.main = None         # main.py's ModuleCode
        self.assets = {}         # what assets.* was asked for, in any file

    def record_names(self):
        codes = list(self.modules.values()) + ([self.main] if self.main is not None else [])
        return {r.name for m in codes for r in m.records}

    def all_modules(self):
        """main.py first, then the modules in dependency order."""
        return [self.main] + self.order

    def path_of(self, dotted):
        return os.path.join(self.root, *dotted.split(".")) + ".py"

    def is_package(self, dotted):
        return os.path.isdir(os.path.join(self.root, *dotted.split(".")))

    def load(self, dotted, node, reader):
        """The module for game.x.y (read now if it is the first time), or None if it is a folder."""
        if dotted in self.modules:
            return self.modules[dotted]
        path = self.path_of(dotted)
        display = os.path.relpath(path, self.root).replace("\\", "/")
        if not os.path.isfile(path):
            if self.is_package(dotted):
                return None
            reader.fail("G1218", "there is no %s" % display, node,
                        cause="from game.<path> import ... reads the file game/<path>.py.",
                        fix="Check the name, or create the file.")
        chain = [d for _, d in self.loading]
        if any(d == dotted for d, _ in self.loading):
            start = next(i for i, (d, _) in enumerate(self.loading) if d == dotted)
            cycle = " -> ".join(chain[start:] + [display])
            reader.fail("G1219", "import cycle: %s" % cycle, node,
                        cause="Each module is read before the ones that import it; a cycle has no first one.",
                        fix="Move what both files need into a third module that neither imports back.")
        from .reader import ModuleReader
        self.loading.append((dotted, display))
        try:
            code = ModuleReader(path, self.root, display, program=self, model=reader.model).read_module()
        finally:
            self.loading.pop()
        self.modules[dotted] = code
        self.order.append(code)
        return code


def new_code(display):
    return ModuleCode(display, java_module_name(display))


def is_state_value(node):
    """NAME = [...] / {...} / Record(...) at the top of a module: state, not a constant."""
    return isinstance(node, (ast.List, ast.Dict, ast.Call))


def check_unique(program, name, display, reader, node):
    if name in program.names and program.names[name] != display:
        reader.fail("G2012", "the class name %s is taken (by %s)" % (name, program.names[name]), node,
                    cause="Script and @dataclass classes are Java classes of the game: their names are game-wide.",
                    fix="Choose another class name.")
    program.names[name] = display

