"""The declaration reader: game/main.py is read, never run.

Like ApkPy reading writehere.py, the build parses the file (ast.parse) and
understands a small set of forms: imports from apkpy_lib.game, assignments of
literal values and API calls, method calls on declared objects
(scene.add(...)), and @prefab functions whose body is one return of an
Entity. Literal arithmetic and prefab parameters are folded as the reader
goes. Anything else (a loop, an if, a call to an unknown function) is a
G1xxx error at the line, with what to do instead. Nothing is imported or
executed.
"""
import ast
import difflib
import glob
import os
import re

from .. import schema
from ..errors import GameError
from .._pycompat import source_text
from ..model import (ActionValue, AssetRef, AtlasRef, ComponentValue, EntityModel, GameModel, RuleModel,
                     SceneModel, SheetRef, TextRef, TilemapRef)

COLOR = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CONDITION = re.compile(r"^\s*(?:count\(\s*([A-Za-z_]\w*)\s*\)|([A-Za-z_]\w*))\s*(==|!=|<=|>=|<|>)\s*(-?\d+(?:\.\d+)?)\s*$")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
SOUND_EXT = (".wav", ".ogg", ".mp3")
FONT_EXT = (".ttf", ".otf", ".fnt")
ANCHORS = {"top-left": [0, 0], "top": [0.5, 0], "top-right": [1, 0], "left": [0, 0.5], "center": [0.5, 0.5],
           "right": [1, 0.5], "bottom-left": [0, 1], "bottom": [0.5, 1], "bottom-right": [1, 1]}
_REQUIRED = object()          # a script field with no starting value: the declaration has to give it
PHASE5 = "Code that runs in the game goes in Script classes; @scene.build is not translated."


# Where a game file takes the API from. "apkpygame" is the name ApkPyGame had before it was part of ApkPy: games
# written then still read.
API_MODULES = ("apkpy_lib.game", "apkpygame")

# camera keys of 2.5D scenes (kind="2.5d")
CAMERA_3D = {"pitch", "yaw", "distance", "fov", "elevation", "fog"}

class _Api:
    """A name of the API, before it is called."""

    def __init__(self, kind, name, owner=None):
        self.kind, self.name, self.owner = kind, name, owner


class _Assets:
    pass


class _GameDecl:
    def __init__(self, model):
        self.model = model


class _SceneDecl:
    def __init__(self, model):
        self.model = model


class _Prefab:
    def __init__(self, node, params, defaults, env):
        self.node, self.params, self.defaults, self.env = node, params, defaults, env     # env: its file's names


class Reader:
    def __init__(self, path, project_root, display=None, program=None, model=None):
        from .modules import Program, new_code
        self.path = path
        self.root = project_root
        self.display = display or os.path.relpath(path, project_root).replace("\\", "/")
        self.model = model or GameModel(source=self.display)
        self.program = program or Program(project_root)
        self.code = new_code(self.display)          # what the translator gets from this file
        self.env = {}
        self.imported = set()
        self.game = None
        self._assets = self.program.assets            # shared: a file named in two modules is packed once

    # ── errors ───────────────────────────────────────────────────────────

    def fail(self, code, message, node=None, cause="", fix=(), received=""):
        raise GameError(code, message, self.display, getattr(node, "lineno", None), cause, fix, received)

    # ── statements ───────────────────────────────────────────────────────

    def read(self):
        if not os.path.isfile(self.path):
            raise GameError("G1001", "there is no %s" % self.display, cause="The game is described in that file.",
                            fix="Create it, or run  apkpy game init  in the project folder.")
        self.code.java = "GameModule"
        self.program.main = self.code
        self.program.loading.append(("game.main", self.display))
        try:
            for node in self.parse().body:
                self.statement(node)
        finally:
            self.program.loading.pop()
        self.finish()
        self.code.game_var = self.model.game_var
        self.model.modules = self.program.all_modules()
        from .data import check_tables
        self.model.tables = check_tables(self.program)
        return self.model

    def parse(self):
        with open(self.path, encoding="utf-8") as fh:
            source = fh.read()
        self.source = source                        # to quote a line in a message (_pycompat.source_text)
        try:
            return ast.parse(source, self.display)
        except SyntaxError as e:
            raise GameError("G1002", "Python syntax error: %s" % e.msg, self.display, e.lineno,
                            fix="Fix the line; the file has to be valid Python.")

    def statement(self, node):
        if isinstance(node, ast.ImportFrom):
            return self.import_from(node)
        if isinstance(node, ast.Import):
            if all(a.name in ("math", "random") and a.asname is None for a in node.names):
                return                       # for scripts: math and random are translated (StrictMath, the seeded Rng)
            if all(a.name.startswith("game.") for a in node.names):
                return self.import_modules(node)
            self.fail("G1207", "write  from apkpy_lib.game import *", node,
                      cause="A game file can only use the ApkPyGame API (and math / random in scripts): the build "
                            "reads it, it never runs it, so no other module is there on the phone.",
                      received="import " + ", ".join(a.name for a in node.names))
        if isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return                                            # a docstring
            if isinstance(node.value, ast.Call):
                self.evaluate(node.value, self.env)
                return
            self.fail("G1201", "this line does nothing the build can read", node)
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            return self.assign(node)
        if isinstance(node, ast.FunctionDef):
            return self.function(node)
        if isinstance(node, ast.Pass):
            return
        if isinstance(node, ast.ClassDef):
            return self.record_class(node) if node.decorator_list else self.script_class(node)
        kind = type(node).__name__.lower().replace("asyncfor", "for")
        self.fail("G1201", "'%s' is not a declaration" % kind, node,
                  cause="The build reads %s, it never runs it: only declarations with literal values "
                        "can be read here (the ApkPy rule)." % self.display,
                  fix=["Write the entities out one by one (scene.add(...) for each).",
                       "Code that runs in the game goes in a Script class (class Spawner(Script): ... def update(self, dt: float): ...)."])

    def import_from(self, node):
        if node.module == "__future__":
            return
        if node.level:
            self.fail("G1207", "write the whole path: from game.<path> import ...", node,
                      received="from %s%s import ..." % ("." * node.level, node.module or ""))
        if node.module == "dataclasses":
            for alias in node.names:
                if alias.name not in ("dataclass", "field", "replace"):
                    self.fail("G1203", "from dataclasses: dataclass, field and replace are translated", node)
                self.code.dataclass_names[alias.asname or alias.name] = alias.name
            return
        if node.module == "typing":
            for alias in node.names:
                if alias.name != "Optional":
                    self.fail("G1203", "from typing: Optional (lists and dicts are list[T], dict[str, T])", node)
            return
        if node.module == "game" or node.module.startswith("game."):
            return self.import_game(node)
        if node.module not in API_MODULES:
            self.fail("G1207", "a game file can only import from apkpy_lib.game, dataclasses and game.<path>", node,
                      cause="The build reads this file, it never runs it; on the phone there is no Python "
                            "and no other module.",
                      received="from %s import ..." % node.module,
                      fix="from apkpy_lib.game import *")
        from .. import api
        for alias in node.names:
            if alias.name == "*":
                for name in api.__all__:
                    self.env[name] = self.api_value(name)
            elif alias.name in api.__all__:
                self.env[alias.asname or alias.name] = self.api_value(alias.name)
            else:
                self.fail("G1203", "apkpy_lib.game has no '%s'" % alias.name, node, fix=self.close(alias.name, api.__all__))

    def import_game(self, node):
        """from game.battle.engine import BattleEngine, resolve_turn / from game.rules import damage"""
        module = self.program.load(node.module, node, self) if node.module != "game" else None
        for alias in node.names:
            local = alias.asname or alias.name
            if alias.name == "*":
                self.fail("G1207", "name what you import from %s" % node.module, node,
                          cause="A reader of the file sees where each name comes from.")
            hit = module.lookup(alias.name) if module is not None else None
            if hit is not None:
                self.code.imported[local] = (module, alias.name)
                self.env[local] = self.imported_value(hit)
                continue
            dotted = node.module + "." + alias.name
            if os.path.isfile(self.program.path_of(dotted)):
                self.code.aliases[local] = self.program.load(dotted, node, self)
                self.env[local] = _Api("module", local)
                continue
            where = module.source if module is not None else node.module.replace(".", "/") + "/"
            self.fail("G1203", "%s has no '%s'" % (where, alias.name), node)

    def import_modules(self, node):
        """import game.rules.damage as damage"""
        for alias in node.names:
            if alias.asname is None:
                self.fail("G1207", "import %s as <name>" % alias.name, node,
                          cause="'game' is the running game in scripts; the module gets a short name of its own.",
                          fix="import %s as %s" % (alias.name, alias.name.rsplit(".", 1)[-1]))
            module = self.program.load(alias.name, node, self)
            if module is None:
                self.fail("G1218", "%s is a folder: import a file from it" % alias.name.replace(".", "/"), node)
            self.code.aliases[alias.asname] = module
            self.env[alias.asname] = _Api("module", alias.asname)

    @staticmethod
    def imported_value(hit):
        kind, _, obj = hit
        if kind in ("constant", "declared"):
            return obj
        if kind == "script":
            return _Api("script", obj.name, obj)
        return _Api(kind, getattr(obj, "name", ""), obj)

    def api_value(self, name):
        if name == "assets":
            return _Assets()
        if schema.component(name):
            return _Api("component", name)
        if schema.action(name):
            return _Api("action", name)
        return _Api("builtin", name)

    def assign(self, node):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if len(targets) != 1 or not isinstance(targets[0], ast.Name):
            self.fail("G1213", "assign to one name", node, fix="name = value")
        if node.value is None:
            self.fail("G1201", "a name needs a value here", node)
        name = targets[0].id
        if name in self.env and isinstance(self.env[name], _Api):
            self.fail("G1213", "'%s' is a name of the API" % name, node, fix="Choose another name.")
        value = self.evaluate(node.value, self.env)
        self.env[name] = value
        if isinstance(value, _GameDecl):
            self.model.game_var = name                      # in scripts, this name is the running game
        if isinstance(value, (int, float, str, bool)):
            self.model.constants[name] = value              # scripts can use it (written into the Java)
            self.code.constants[name] = value
        if isinstance(value, AssetRef):
            self.code.declared[name] = value                # scripts here can name it, as in the other modules

    # ── code that runs in the game (translated, compiler/scripts.py) ──

    def script_class(self, node):
        from .modules import check_unique
        from .scripts import ScriptClass, parse_type, SETTABLE, RESERVED, base as tbase
        if (len(node.bases) != 1 or not isinstance(node.bases[0], ast.Name) or node.bases[0].id != "Script"
                or node.keywords or node.decorator_list):
            self.fail("G2001", "class %s: a game class is  class %s(Script):  or a @dataclass" % (node.name, node.name),
                      node, cause="Classes in the game are scripts (components written in Python) or data classes.")
        if node.name in self.env or node.name in RESERVED or not NAME.match(node.name):
            self.fail("G2012", "the name %s is taken" % node.name, node, fix="Choose another class name.")
        check_unique(self.program, node.name, self.display, self, node)
        known = self.known_records()
        fields, methods = {}, []

        def fail(code, message, where=None, cause="", fix=()):
            self.fail(code, message, where, cause, fix)

        for item in node.body:
            if isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                continue
            if isinstance(item, ast.Pass):
                continue
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                t = parse_type(item.annotation, fail, known)
                default = self.field_default(item, t) if item.value is not None else _REQUIRED
                if default is _REQUIRED and tbase(t) not in SETTABLE:
                    self.fail("G2006", "%s: a %s field needs a starting value" % (item.target.id, t), item)
                fields[item.target.id] = (t, default, item.lineno)
            elif isinstance(item, ast.FunctionDef):
                if item.decorator_list:
                    self.fail("G2001", "methods have no decorators here", item)
                methods.append(item)
            elif isinstance(item, ast.Assign):
                self.fail("G2006", "a field has a type: %s: float = ..." % getattr(item.targets[0], "id", "x"), item)
            else:
                self.fail("G2001", "a script class holds fields (name: type = value) and methods", item)
        cls = ScriptClass(node, fields, methods)
        self.model.scripts.append(cls)
        self.code.scripts.append(cls)
        self.env[node.name] = _Api("script", node.name, cls)

    def known_records(self):
        return self.program.record_names() | {r.name for r in self.code.records}

    def record_class(self, node):
        """@dataclass class Monster: typed fields (defaults last, as Python wants) and methods."""
        from .modules import check_unique
        from .scripts import RecordClass, parse_type, RESERVED
        deco = node.decorator_list
        if (len(deco) != 1 or not isinstance(deco[0], ast.Name)
                or self.code.dataclass_names.get(deco[0].id) != "dataclass"):
            self.fail("G2001", "class %s: the decorator is @dataclass (from dataclasses import dataclass)" % node.name,
                      node, fix="@dataclass\nclass %s:\n    name: str" % node.name)
        if node.bases or node.keywords:
            self.fail("G2001", "class %s: a @dataclass has no base class here" % node.name, node,
                      cause="Composition (a field holding another @dataclass) keeps the translation simple.")
        if node.name in self.env or node.name in RESERVED or not NAME.match(node.name):
            self.fail("G2012", "the name %s is taken" % node.name, node, fix="Choose another class name.")
        check_unique(self.program, node.name, self.display, self, node)
        known = self.known_records() | {node.name}

        def fail(code, message, where=None, cause="", fix=()):
            self.fail(code, message, where, cause, fix)

        fields, methods, seen_default = {}, [], None
        for item in node.body:
            if isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                continue
            if isinstance(item, ast.Pass):
                continue
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                name = item.target.id
                t = parse_type(item.annotation, fail, known)
                if item.value is None and seen_default:
                    self.fail("G2006", "%s: fields without a default come before %s (which has one)"
                              % (name, seen_default), item, cause="Python's @dataclass has the same rule.")
                if isinstance(item.value, (ast.List, ast.Dict)):
                    kind = "list" if isinstance(item.value, ast.List) else "dict"
                    self.fail("G2006", "%s: a list or dict default is shared in Python" % name, item,
                              fix="%s: %s = field(default_factory=%s)" % (name, source_text(item.annotation, getattr(self, "source", None)), kind))
                if item.value is not None:
                    seen_default = name
                fields[name] = (t, item.value, item.lineno)
            elif isinstance(item, ast.FunctionDef):
                if item.decorator_list:
                    self.fail("G2001", "methods have no decorators here", item)
                methods.append(item)
            else:
                self.fail("G2001", "a @dataclass holds fields (name: type = value) and methods", item)
        record = RecordClass(node, fields, methods)
        record.module = self.code
        from .data import ref_target
        record.refs = {}
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                target = ref_target(item.annotation)
                if target is not None:
                    if target not in known:
                        self.fail("G2006", "Ref[%s]: %s is not a @dataclass of the game" % (target, target), item)
                    record.refs[item.target.id] = target
        self.code.records.append(record)
        self.env[node.name] = _Api("record", node.name, record)

    def field_default(self, item, t):
        from .scripts import base as tbase
        value = self.evaluate(item.value, self.env)
        b = tbase(t)
        ok = {"int": isinstance(value, int) and not isinstance(value, bool),
              "float": _is_number(value), "bool": isinstance(value, bool), "str": isinstance(value, str),
              "Sound": isinstance(value, AssetRef) and value.kind in ("sound", "music"),
              "Prefab": isinstance(value, EntityModel)}.get(b)
        if value is None and t.endswith("?"):
            return None
        if b.startswith("list[") and value == []:
            return []
        if b.startswith("dict[") and value == {}:
            return {}
        if not ok:
            self.fail("G2003", "%s: the starting value is not a %s" % (item.target.id, t), item,
                      received=_shown(value), fix="Lists start as [], optional values as None.")
        return float(value) if b == "float" else value

    def script_component(self, func, node, args, kwargs):
        from .scripts import SETTABLE, base as tbase
        cls = func.owner
        if args:
            self.fail("G1204", "%s(...) takes its fields by name: %s(speed=2.0)" % (cls.name, cls.name), node)
        values = {}
        for key, (value, where) in kwargs.items():
            if key not in cls.fields:
                self.fail("G1204", "%s has no field '%s'" % (cls.name, key), where,
                          fix=self.close(key, cls.fields) or "Fields: %s" % ", ".join(cls.fields))
            t = cls.fields[key][0]
            if tbase(t) not in SETTABLE:
                self.fail("G1205", "%s.%s is set by the script itself, not in the declaration" % (cls.name, key), where)
            values[key] = self.check_field_value(cls, key, t, value, where)
        for key, (t, default, line) in cls.fields.items():
            if key in values or tbase(t) not in SETTABLE:
                continue
            if default is _REQUIRED:
                self.fail("G1206", "%s needs %s=..." % (cls.name, key), node)
            if default is not None:
                values[key] = default
        return ComponentValue(cls.name, values)

    def check_field_value(self, cls, key, t, value, where):
        from .scripts import base as tbase
        b = tbase(t)
        ok = {"int": isinstance(value, int) and not isinstance(value, bool), "float": _is_number(value),
              "bool": isinstance(value, bool), "str": isinstance(value, str),
              "Sound": isinstance(value, AssetRef) and value.kind in ("sound", "music"),
              "Prefab": isinstance(value, EntityModel)}[b]
        if value is None and t.endswith("?"):
            return None
        if not ok:
            self.fail("G1205", "%s.%s is %s" % (cls.name, key, t), where, received=_shown(value))
        if b == "float":
            return float(value)
        if b == "Prefab":
            return value.clone()
        return value

    def function(self, node):
        if not node.decorator_list:
            from .scripts import Function
            if node.name in self.env:
                self.fail("G2012", "the name %s is taken" % node.name, node)
            f = Function(node)
            self.model.functions.append(f)
            self.code.functions.append(f)
            self.env[node.name] = _Api("function", node.name)
            return
        if len(node.decorator_list) != 1:
            self.fail("G1212", "def %s: one decorator (@prefab), or none for a function used by scripts" % node.name,
                      node)
        deco = node.decorator_list[0]
        if isinstance(deco, ast.Attribute) and deco.attr == "build":
            self.fail("G1208", "@%s.build is not translated yet" % getattr(deco.value, "id", "scene"), node,
                      cause=PHASE5, fix="Write the entities out with scene.add(...) for now.")
        if not (isinstance(deco, ast.Name) and isinstance(self.env.get(deco.id), _Api)
                and self.env[deco.id].name == "prefab"):
            self.fail("G1212", "def %s: only @prefab functions are read" % node.name, node)
        body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
        if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
            self.fail("G1212", "a @prefab has one line: return Entity(...)", node,
                      cause="Its parameters are filled in by the build for each use; the body is a "
                            "description, not code.",
                      fix="@prefab\ndef coin(x: float = 0):\n    return Entity(\"coin\", Sprite(star), ...)")
        args = node.args
        if args.vararg or args.kwarg or args.kwonlyargs or args.posonlyargs:
            self.fail("G1212", "a @prefab takes plain parameters with defaults", node)
        params = [a.arg for a in args.args]
        defaults = {}
        for name, default in zip(params[len(params) - len(args.defaults):], args.defaults):
            defaults[name] = self.evaluate(default, self.env)
        self.env[node.name] = _Prefab(node, params, defaults, self.env)
        self.code.declared[node.name] = self.env[node.name]

    # ── expressions ──────────────────────────────────────────────────────

    def evaluate(self, node, env):
        if isinstance(node, ast.Constant):
            if node.value is None or isinstance(node.value, (bool, int, float, str)):
                return node.value
            self.fail("G1202", "this value cannot be read", node)
        if isinstance(node, (ast.Tuple, ast.List)):
            items = [self.evaluate(e, env) for e in node.elts]
            return tuple(items) if isinstance(node, ast.Tuple) else items
        if isinstance(node, ast.Dict):
            out = {}
            for k, v in zip(node.keys, node.values):
                if k is None:
                    self.fail("G1202", "**unpacking is not read", node)
                key = self.evaluate(k, env)
                if not isinstance(key, str):
                    self.fail("G1205", "dictionary keys are text here", k)
                out[key] = self.evaluate(v, env)
            return out
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = self.evaluate(node.operand, env)
            if not _is_number(value):
                self.fail("G1205", "- and + go before numbers", node)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            return self.binop(node, env)
        if isinstance(node, ast.JoinedStr):
            parts = []
            for v in node.values:
                if isinstance(v, ast.Constant):
                    parts.append(str(v.value))
                else:
                    value = self.evaluate(v.value, env)
                    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
                        self.fail("G1202", "an f-string here can only hold numbers and text", v)
                    parts.append(format(value, self.evaluate(v.format_spec, env) if v.format_spec else ""))
            return "".join(parts)
        if isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            if node.id in ("True", "False", "None"):
                return {"True": True, "False": False, "None": None}[node.id]
            self.fail("G1203", "'%s' is not declared" % node.id, node,
                      cause="Names are the ones imported from apkpy_lib.game or assigned above this line.",
                      fix=self.close(node.id, env))
        if isinstance(node, ast.Attribute):
            return self.attribute(node, env)
        if isinstance(node, ast.Call):
            return self.call(node, env)
        what = {"ListComp": "a list comprehension", "Lambda": "a lambda", "IfExp": "an inline if",
                "Compare": "a comparison", "BoolOp": "and/or", "Subscript": "an index [...]",
                "GeneratorExp": "a generator", "DictComp": "a dict comprehension"}.get(type(node).__name__,
                                                                                    type(node).__name__)
        self.fail("G1202", "%s cannot be read at build time" % what, node,
                  cause="Values here are literals, names declared above, and API calls: the build reads the "
                        "file, it never runs it.")

    def binop(self, node, env):
        a, b = self.evaluate(node.left, env), self.evaluate(node.right, env)
        if isinstance(a, str) and isinstance(b, str) and isinstance(node.op, ast.Add):
            return a + b
        if not (_is_number(a) and _is_number(b)):
            self.fail("G1205", "arithmetic here works on numbers (and + on texts)", node)
        ops = {ast.Add: lambda: a + b, ast.Sub: lambda: a - b, ast.Mult: lambda: a * b,
               ast.Div: lambda: a / b, ast.FloorDiv: lambda: a // b, ast.Mod: lambda: a % b,
               ast.Pow: lambda: a ** b}
        op = ops.get(type(node.op))
        if op is None:
            self.fail("G1202", "this operator is not read", node)
        try:
            return op()
        except ZeroDivisionError:
            self.fail("G1205", "division by zero", node)

    def attribute(self, node, env):
        base = self.evaluate(node.value, env)
        name = node.attr
        if isinstance(base, _Assets) and name in ("image", "sound", "music", "atlas", "sheet", "tilemap", "font", "folder"):
            return _Api("asset", name)
        if isinstance(base, _GameDecl) and name == "scene":
            return _Api("game.scene", name, base)
        if isinstance(base, _SceneDecl) and name == "add":
            return _Api("scene.add", name, base)
        options = {_Assets: ["image", "sound", "music", "atlas", "sheet", "tilemap", "font", "folder"], _GameDecl: ["scene"], _SceneDecl: ["add"]}
        self.fail("G1203", "'%s' has nothing called '%s'" % (getattr(node.value, "id", "this"), name), node,
                  fix=self.close(name, options.get(type(base), [])))

    # ── calls ────────────────────────────────────────────────────────────

    def call(self, node, env):
        func = self.evaluate(node.func, env)
        args = []
        for a in node.args:
            if isinstance(a, ast.Starred):
                self.fail("G1202", "*unpacking is not read", a)
            args.append(self.evaluate(a, env))
        kwargs = {}
        for k in node.keywords:
            if k.arg is None:
                self.fail("G1202", "**unpacking is not read", k.value)
            kwargs[k.arg] = (self.evaluate(k.value, env), k.value)
        if isinstance(func, _Prefab):
            return self.prefab_call(func, node, args, kwargs)
        if not isinstance(func, _Api):
            self.fail("G1202", "this is not something that can be called", node)
        handler = {"component": self.component, "action": self.action, "asset": self.asset,
                   "game.scene": self.scene, "scene.add": self.scene_add,
                   "script": self.script_component}.get(func.kind)
        if func.kind == "function":
            self.fail("G1202", "%s() runs in the game, not in the declarations" % func.name, node,
                      cause="Plain functions are translated for scripts; the declarations are read, never run.")
        if handler:
            return handler(func, node, args, kwargs)
        if func.name == "Game":
            return self.game_call(node, args, kwargs)
        if func.name == "Entity":
            return self.entity(node, args, kwargs)
        if func.name == "when":
            return self.when(node, args, kwargs)
        if func.name == "t":
            if kwargs or len(args) != 1 or not isinstance(args[0], str):
                self.fail("G1204", 't() takes one key, written out', node, fix='Text(t("score"))')
            return TextRef(args[0], node.lineno)
        if func.name == "prefab":
            self.fail("G1212", "prefab goes above a def, as @prefab", node)
        self.fail("G1202", "%s cannot be called here" % func.name, node)

    def bind(self, node, what, spec_args, fields, args, kwargs):
        """Positional and keyword arguments to {field: (value, node)}."""
        out = {}
        positional = list(spec_args)
        for i, value in enumerate(args):
            if positional and positional[0].startswith("*"):
                out.setdefault(positional[0][1:], ([], node))[0].append(value)
                continue
            if not positional:
                self.fail("G1204", "%s takes %d positional value(s)" % (what, len(spec_args)), node,
                          fix="Name the others: %s" % ", ".join("%s=..." % f for f in fields))
            out[positional.pop(0)] = (value, node.args[i])
        for key, value in kwargs.items():
            if key not in fields:
                self.fail("G1204", "%s has no parameter '%s'" % (what, key), value[1],
                          fix=self.close(key, fields) or "It takes: %s" % ", ".join(fields))
            if key in out:
                self.fail("G1204", "%s got '%s' twice" % (what, key), value[1])
            out[key] = value
        return out

    def component(self, func, node, args, kwargs):
        spec = schema.component(func.name)
        bound = self.bind(node, func.name, spec["args"], spec["fields"], args, kwargs)
        values = self.check_fields(func.name, spec["fields"], bound, node)
        if func.name == "Sprite":
            self.sprite_frame(values, node)
        if func.name == "Canvas":
            self.canvas_values(values, node)
        return ComponentValue(func.name, values)

    def action(self, func, node, args, kwargs):
        spec = schema.action(func.name)
        bound = self.bind(node, func.name + "()", spec["args"], spec["fields"], args, kwargs)
        return ActionValue(func.name, spec["do"], self.check_fields(func.name + "()", spec["fields"], bound, node),
                           node.lineno)

    def check_fields(self, what, fields, bound, node):
        values = {}
        for name, spec in fields.items():
            if name not in bound:
                if spec.get("required"):
                    self.fail("G1206", "%s needs %s" % (what, name), node)
                continue
            value, where = bound[name]
            values[name] = self.check_type(what, name, spec, value, where)
        return values

    def check_type(self, what, name, spec, value, node):
        t = spec["type"]

        def wrong(expected):
            self.fail("G1205", "%s: %s has to be %s" % (what, name, expected), node, received=_shown(value))

        if t == "number":
            if not _is_number(value):
                wrong("a number")
        elif t == "int":
            if not isinstance(value, int) or isinstance(value, bool):
                wrong("a whole number")
        elif t == "string":
            if not isinstance(value, str):
                wrong("a text")
        elif t == "text":
            if not isinstance(value, (str, TextRef)):
                wrong('a text, or t("key")')
        elif t == "bool":
            if not isinstance(value, bool):
                wrong("True or False")
        elif t == "color":
            if not isinstance(value, str) or not COLOR.match(value):
                wrong('a colour like "#ff8800"')
        elif t == "pair":
            if _is_number(value):
                return value
            if not (isinstance(value, (tuple, list)) and len(value) == 2 and all(map(_is_number, value))):
                wrong("a number or (a, b)")
            return list(value)
        elif t == "rect":
            if not (isinstance(value, (tuple, list)) and len(value) == 4
                    and all(isinstance(v, int) and not isinstance(v, bool) for v in value)):
                wrong("(x, y, width, height) in whole numbers")
            return list(value)
        elif t == "enum":
            if value not in spec["values"]:
                wrong("one of %s" % ", ".join('"%s"' % v for v in spec["values"]))
        elif t == "image":
            if not (isinstance(value, (AtlasRef, SheetRef)) or (isinstance(value, AssetRef) and value.kind == "image")):
                wrong("an image: assets.image(...), assets.sheet(...) or assets.atlas(...)")
        elif t == "font":
            if not (isinstance(value, AssetRef) and value.kind == "font"):
                wrong('a font: assets.font("fonts/body.ttf")')
        elif t == "sound":
            if not (isinstance(value, AssetRef) and value.kind in ("sound", "music")):
                wrong("a sound: assets.sound(...)")
        elif t == "frame":
            if not isinstance(value, (int, str)) or isinstance(value, bool):
                wrong("a frame name or number")
        elif t == "actions":
            if not isinstance(value, list) or not all(isinstance(a, ActionValue) for a in value):
                wrong("actions like sound(...), destroy(), exit_game(...)")
        elif t == "dict":
            if not isinstance(value, dict) or not _jsonable(value):
                wrong("a dictionary of numbers, texts, True/False, lists and dictionaries")
        elif t == "entity":
            if not isinstance(value, EntityModel):
                wrong("an Entity(...) or a prefab call")
            return value.clone()
        elif t == "box":
            if not (isinstance(value, (tuple, list)) and len(value) == 4 and all(map(_is_number, value))):
                wrong("(x, y, width, height)")
            return list(value)
        elif t == "tilemap":
            if not isinstance(value, TilemapRef):
                wrong('a map: assets.tilemap("levels/one.tmj")')
        elif t == "strings":
            if not isinstance(value, (list, tuple)) or not all(isinstance(v, str) for v in value):
                wrong("a list of texts")
            return list(value)
        elif t == "objects":
            if not isinstance(value, dict) or not all(isinstance(v, EntityModel) for v in value.values()):
                wrong('{"coin": coin(), "enemy": Entity(...)}: a Tiled object name/class to an entity')
        elif t == "animations":
            self.check_animations(value, node, wrong)
        elif t == "condition":
            return self.condition(value, node)
        return value

    def check_animations(self, value, node, wrong):
        if not isinstance(value, dict) or not value:
            wrong('{"run": {"frames": [0, 1, 2], "fps": 10}}')
        for name, anim in value.items():
            if not isinstance(anim, dict) or not isinstance(anim.get("frames"), (list, tuple)) or not anim["frames"]:
                wrong('{"%s": {"frames": [0, 1, 2], "fps": 10, "loop": True}}' % name)
            extra = set(anim) - {"frames", "fps", "loop"}
            if extra:
                self.fail("G1204", "animation %r: unknown key %s" % (name, ", ".join(sorted(extra))), node,
                          fix="An animation has frames, fps and loop.")
            if not all(isinstance(f, (int, str)) and not isinstance(f, bool) for f in anim["frames"]):
                wrong("frames: numbers (sheet) or names (atlas)")
            if "fps" in anim and not _is_number(anim["fps"]):
                wrong("fps: a number")
            if "loop" in anim and not isinstance(anim["loop"], bool):
                wrong("loop: True or False")

    def check_frames(self, image, frames, what, node):
        """Every frame exists in the sprite's sheet / atlas."""
        for f in frames:
            if isinstance(image, SheetRef):
                if not isinstance(f, int) or not 0 <= f < image.cols * image.rows:
                    self.fail("G1214", "%s: the sheet %s has frames 0 to %d" % (what, image.path,
                                                                             image.cols * image.rows - 1), node,
                              received=repr(f))
            elif isinstance(image, AtlasRef):
                if image.frame_index(f) is None:
                    self.fail("G1214", "%s: the atlas %s has no frame %r" % (what, image.pattern, f), node)
            else:
                self.fail("G1205", "%s: frames need a Sprite with assets.sheet(...) or assets.atlas(...)" % what,
                          node)

    def sprite_frame(self, values, node, what="Sprite"):
        image = values.get("image")
        if "frame" in values and not isinstance(image, (AtlasRef, SheetRef)):
            self.fail("G1205", "%s: frame= goes with an atlas or a sheet" % what, node,
                      fix='%s(%sassets.sheet("assets/hero.png", frame=(16, 16)), frame=0)'
                      % (what, "" if what == "Sprite" else "image="))
        if isinstance(image, SheetRef):
            self.check_frames(image, [values.get("frame", 0)], what, node)
        if isinstance(image, AtlasRef):
            frame = values.get("frame", 0)
            if image.frame_index(frame) is None:
                names = [f.rsplit("/", 1)[-1].rsplit(".", 1)[0] for f in image.files]
                self.fail("G1214", "the atlas %s has no frame %r" % (image.pattern, frame), node,
                          fix="Frames: %s (or a number from 0 to %d)" % (", ".join(names), len(names) - 1))

    def canvas_values(self, values, node):
        """A Canvas: a size it can have, and an image it can start from. The engine reads that image's pixels
        itself (the same numbers on every platform), so it is a PNG, and not an interlaced one."""
        self.sprite_frame(values, node, "Canvas")
        for side in ("width", "height"):
            if side in values and values[side] < 1:
                self.fail("G1205", "Canvas: %s has to be 1 or more" % side, node, received=repr(values[side]))
        if values.get("width", 64) * values.get("height", 64) > 4096 * 4096:
            self.fail("G1205", "Canvas: at most 4096 x 4096 pixels", node,
                      received="%d x %d" % (values.get("width", 64), values.get("height", 64)))
        image = values.get("image")
        if isinstance(image, (AssetRef, SheetRef)):          # an atlas is a PNG the build makes
            problem = _png_problem(os.path.join(self.root, image.path))
            if problem:
                self.fail("G1205", "Canvas: %s %s" % (image.path, problem), node,
                          fix="Save it as a PNG, not interlaced: a Canvas reads the pixels of its image itself.")

    # ── assets ───────────────────────────────────────────────────────────

    def asset(self, func, node, args, kwargs):
        allowed_kw = ["frame"] if func.name == "sheet" else []
        if set(kwargs) - set(allowed_kw) or len(args) != 1 or not isinstance(args[0], str):
            self.fail("G1204", 'assets.%s takes one path, written out' % func.name, node,
                      fix={"sheet": 'assets.sheet("assets/hero.png", frame=(16, 16))',
                           "tilemap": 'assets.tilemap("levels/one.tmj")'}.get(
                          func.name, 'assets.%s("assets/file%s")' % (func.name,
                                                                   ".png" if func.name == "image" else ".wav")))
        path = args[0].replace("\\", "/").strip("/")
        if os.path.isabs(args[0]) or ".." in path.split("/"):
            self.fail("G1211", "asset paths are relative to the project folder", node, received=args[0])
        if func.name == "folder":
            return self.asset_folder(path, node)
        frame = None
        if func.name == "sheet":
            if "frame" not in kwargs:
                self.fail("G1206", "assets.sheet needs frame=(width, height)", node)
            frame = self.check_type("assets.sheet", "frame", {"type": "pair"}, *kwargs["frame"])
            if not isinstance(frame, list) or not all(isinstance(v, int) and v > 0 for v in frame):
                self.fail("G1205", "assets.sheet: frame is (width, height) in whole pixels", node)
        key = (func.name, path, tuple(frame or ()))
        if key in self._assets:
            return self._assets[key]
        if func.name == "tilemap":
            from . import tiled
            full = os.path.join(self.root, path)
            if not os.path.isfile(full):
                self.fail("G1211", "the file %s does not exist" % path, node)
            data = tiled.read(full, self.root, path, node.lineno)
            name = re.sub(r"[^a-z0-9_]+", "_", path.rsplit(".", 1)[0].lower()).strip("_")
            ref = TilemapRef(path, name, data)
            self._assets[key] = ref
            self.model.assets.append(ref)
            image = AssetRef("image", data.tileset["image"])
            if ("image", image.path, ()) not in self._assets:
                self._assets[("image", image.path, ())] = image
                self.model.assets.append(image)
            return ref
        if func.name == "atlas":
            files = sorted(f for f in glob.glob(os.path.join(self.root, path)) if f.lower().endswith(IMAGE_EXT))
            if not files:
                self.fail("G1211", "no images match %s" % path, node,
                          fix='A pattern like "assets/coins/*.png", relative to the project folder.')
            rel = [os.path.relpath(f, self.root).replace("\\", "/") for f in files]
            name = re.sub(r"[^a-z0-9_]+", "_", path.rsplit("/", 1)[0].lower()).strip("_") or "atlas"
            ref = AtlasRef(path, name, rel)
        else:
            full = os.path.join(self.root, path)
            if not os.path.isfile(full):
                self.fail("G1211", "the file %s does not exist" % path, node,
                          cause="Paths are relative to the project folder (where apkpy.toml is).")
            ext = os.path.splitext(path)[1].lower()
            allowed = IMAGE_EXT if func.name in ("image", "sheet") else FONT_EXT if func.name == "font" else SOUND_EXT
            if ext not in allowed:
                self.fail("G1211", "%s is not a %s file" % (path, func.name), node,
                          fix="Use %s." % ", ".join(allowed))
            if func.name == "sheet":
                from PIL import Image
                with Image.open(full) as img:
                    w, h = img.size
                cols, rows = w // frame[0], h // frame[1]
                if cols < 1 or rows < 1:
                    self.fail("G1205", "%s is %dx%d: smaller than one frame %dx%d" % (path, w, h, frame[0], frame[1]),
                              node)
                ref = SheetRef(path, frame[0], frame[1], cols, rows)
                image = AssetRef("image", path)
                if ("image", path, ()) not in self._assets:
                    self._assets[("image", path, ())] = image
                    self.model.assets.append(image)
                self._assets[key] = ref
                return ref
            if func.name == "font":
                from . import fonts
                try:
                    self.model.fonts[path] = fonts.read(full, path, self.root)
                except fonts.FontError as e:
                    self.fail("G1221", "%s: %s" % (path, e), node, fix=e.fix)
                image = self.model.fonts[path].get("image")
                if image and ("image", image, ()) not in self._assets:
                    self._assets[("image", image, ())] = AssetRef("image", image)
                    self.model.assets.append(self._assets[("image", image, ())])
            ref = AssetRef(func.name, path)
        self._assets[key] = ref
        self.model.assets.append(ref)
        return ref

    def asset_folder(self, path, node):
        """assets.folder("assets/monsters"): every image in it goes in the bundle, for scripts to name (set_image)."""
        files = sorted(f for f in glob.glob(os.path.join(self.root, path, "*")) if f.lower().endswith(IMAGE_EXT))
        if not files:
            self.fail("G1211", "there are no images in the folder %s" % path, node,
                      cause="Paths are relative to the project folder (where apkpy.toml is).")
        for f in files:
            rel = os.path.relpath(f, self.root).replace("\\", "/")
            if ("image", rel, ()) not in self._assets:
                self._assets[("image", rel, ())] = AssetRef("image", rel)
                self.model.assets.append(self._assets[("image", rel, ())])
        return path

    # ── game, scenes, entities, prefabs ──────────────────────────────────

    def game_call(self, node, args, kwargs):
        if self.game is not None:
            self.fail("G1209", "Game(...) is declared twice", node, fix="One Game per project.")
        bound = self.bind(node, "Game", ["name"], ["name", "size", "scale", "orientation", "background",
                                                  "fixed_hz", "debug", "seed", "vars", "renderer", "font",
                                                  "pixel_scale"], args, kwargs)
        m = self.model
        specs = {"name": {"type": "string"}, "size": {"type": "pair"},
                 "scale": {"type": "enum", "values": ["fit", "fill", "expand"]},
                 "orientation": {"type": "enum", "values": ["portrait", "landscape", "any"]},
                 "background": {"type": "color"}, "fixed_hz": {"type": "int"}, "debug": {"type": "bool"},
                 "seed": {"type": "int"}, "vars": {"type": "dict"},
                 "renderer": {"type": "enum", "values": ["auto", "gles", "canvas"]},
                 "font": {"type": "font"}, "pixel_scale": {"type": "bool"}}
        for key, (value, where) in bound.items():
            value = self.check_type("Game", key, specs[key], value, where)
            if key == "vars":
                value = self.numbers(value, where)
            if key == "size" and not isinstance(value, list):
                self.fail("G1205", "Game: size is (width, height)", where)
            setattr(m, key, value)
        self.game = _GameDecl(m)
        return self.game

    def scene(self, func, node, args, kwargs):
        bound = self.bind(node, "game.scene", ["name"], ["name", "start", "background", "music", "music_volume",
                                                         "camera", "on_back", "vars", "rules", "kind"], args, kwargs)
        if "name" not in bound:
            self.fail("G1206", "a scene needs a name", node, fix='game.scene("main", start=True)')
        name = bound["name"][0]
        if not isinstance(name, str) or not NAME.match(name):
            self.fail("G1205", "a scene name is a word (letters, digits, _)", node, received=_shown(name))
        if any(s.name == name for s in self.model.scenes):
            self.fail("G1210", "there are two scenes called %r" % name, node)
        s = SceneModel(name=name, line=node.lineno)
        specs = {"start": {"type": "bool"}, "background": {"type": "color"}, "music": {"type": "sound"},
                 "music_volume": {"type": "number"}, "camera": {"type": "camera"}, "on_back": {"type": "actions"},
                 "vars": {"type": "dict"}, "rules": {"type": "rules"},
                 "kind": {"type": "enum", "values": ["2d", "2.5d"]}}
        if "on_back" in bound and isinstance(bound["on_back"][0], ActionValue):
            bound["on_back"] = ([bound["on_back"][0]], bound["on_back"][1])
        for key, (value, where) in bound.items():
            if key == "name":
                continue
            if key == "camera":
                value = self.camera(value, where)
            elif key == "vars":
                value = self.numbers(self.check_type("game.scene", key, specs[key], value, where), where)
            elif key == "rules":
                if not isinstance(value, list) or not all(isinstance(r, RuleModel) for r in value):
                    self.fail("G1205", 'game.scene: rules is a list of when("...", actions)', where)
            else:
                value = self.check_type("game.scene", key, specs[key], value, where)
            setattr(s, key, value)
        if s.camera and s.kind != "2.5d" and set(s.camera) & CAMERA_3D:
            self.fail("G1205", "camera: %s are for 2.5D scenes" % ", ".join(sorted(set(s.camera) & CAMERA_3D)),
                      bound["camera"][1], fix='game.scene("%s", kind="2.5d", camera={...})' % name)
        self.model.scenes.append(s)
        return _SceneDecl(s)

    def numbers(self, value, node):
        if not all(isinstance(k, str) and NAME.match(k) and _is_number(v) for k, v in value.items()):
            self.fail("G1205", 'variables are {"name": number}', node, received=_shown(value))
        return dict(value)

    def camera(self, value, node):
        keys = {"x", "y", "zoom", "rotation", "follow", "bounds"} | CAMERA_3D
        if not isinstance(value, dict) or set(value) - keys:
            self.fail("G1205", "camera is a dictionary with %s" % ", ".join(sorted(keys)), node,
                      received=_shown(value))
        fog = value.get("fog")
        if fog is not None and not (isinstance(fog, (list, tuple)) and len(fog) == 2 and all(map(_is_number, fog))):
            self.fail("G1205", "camera: fog is (start, end), distances from the camera", node)
        for k in ("x", "y", "zoom", "rotation", "pitch", "yaw", "distance", "fov", "elevation"):
            if k in value and not _is_number(value[k]):
                self.fail("G1205", "camera: %s has to be a number" % k, node)
        if "follow" in value and not isinstance(value["follow"], str):
            self.fail("G1205", 'camera: follow is the name of an entity ("player")', node)
        b = value.get("bounds")
        if b is not None and b != "map" and not (isinstance(b, (list, tuple)) and len(b) == 4
                                                 and all(map(_is_number, b))):
            self.fail("G1205", 'camera: bounds is (x, y, width, height) or "map"', node)
        out = dict(value)
        if isinstance(b, tuple):
            out["bounds"] = list(b)
        if isinstance(fog, tuple):
            out["fog"] = list(fog)
        return out

    def condition(self, text, node, what="only_if"):
        """ "keys >= 1" / "count(coin) == 0": {"var" or "count", "op", "value"}, as the engine tests it."""
        m = CONDITION.match(text) if isinstance(text, str) else None
        if not m:
            self.fail("G1205", "%s: the condition is  name op number  or  count(tag) op number" % what, node,
                      received=repr(text), fix=['%s("lives <= 0", ...)' % what, '%s("count(coin) == 0", ...)' % what])
        out = {"count": m.group(1)} if m.group(1) else {"var": m.group(2)}
        out.update({"op": m.group(3), "value": float(m.group(4))})
        return out

    def when(self, node, args, kwargs):
        """when("lives <= 0", actions...) / when("count(coin) == 0", ...): a scene rule."""
        if kwargs or not args or not isinstance(args[0], str):
            self.fail("G1204", 'when("lives <= 0", exit_game(...)): a condition, then actions', node)
        m = CONDITION.match(args[0])
        if not m:
            self.fail("G1205", "when: the condition is  name op number  or  count(tag) op number", node,
                      received=repr(args[0]), fix=['when("lives <= 0", ...)', 'when("count(coin) == 0", ...)'])
        actions = list(args[1:])
        if not actions or not all(isinstance(a, ActionValue) for a in actions):
            self.fail("G1205", "when: after the condition come actions", node,
                      fix='when("score >= 30", exit_game({"result": "win"}))')
        return RuleModel(m.group(2), m.group(1), m.group(3), float(m.group(4)), actions, node.lineno)

    def scene_add(self, func, node, args, kwargs):
        bound = self.bind(node, "scene.add", ["entity"], ["entity", "at", "rotation", "scale", "name", "ui"],
                          args, kwargs)
        if "entity" not in bound or not isinstance(bound["entity"][0], EntityModel):
            self.fail("G1205", "scene.add takes an Entity(...) or a prefab", node)
        e = bound["entity"][0].clone()
        self.place(e, bound)
        if "ui" in bound:
            e.ui = self.check_type("scene.add", "ui", {"type": "bool"}, *bound["ui"])
        scene = func.owner.model
        scene.entities.append(e)
        for c in e.components:
            if c.type == "Tilemap":
                self.tilemap_objects(scene, e, c, node)

    def tilemap_objects(self, scene, map_entity, c, node):
        """The map's Tiled objects become entities of the scene, from the objects={...} templates."""
        data = c.values["map"].data
        templates = c.values.get("objects", {})
        unknown = sorted({o[0] for o in data.objects if o[0] not in templates})
        if unknown:
            self.fail("G1217", "the map %s has objects with no entity: %s" % (c.values["map"].path, ", ".join(unknown)),
                      node, cause="Each Tiled object becomes an entity; nothing is dropped without a word.",
                      fix='Tilemap(level, objects={%s})' % ", ".join('"%s": ...' % k for k in unknown))
        names = [n for n, _, _, _ in data.layers]
        for layer in c.values.get("solid") or []:
            if layer not in names:
                self.fail("G1216", "the map %s has no tile layer %r" % (c.values["map"].path, layer), node,
                          fix="Tile layers: %s" % ", ".join(names))
        for key, x, y, _, _, props, marker in data.objects:
            e = templates[key].clone()
            e.marker = marker
            e.x += map_entity.x + x
            e.y += map_entity.y + y
            if props:
                e.props = dict(props)                       # self.props.get_str("event") in scripts
            scene.entities.append(e)
        if scene.camera and scene.camera.get("bounds") == "map":
            scene.camera["bounds"] = [map_entity.x, map_entity.y, data.cols * data.tile_w, data.rows * data.tile_h]

    def place(self, e, bound):
        if "at" in bound:
            raw, where = bound["at"]
            if isinstance(raw, (tuple, list)) and len(raw) == 3 and all(map(_is_number, raw)):
                e.x, e.y, e.elevation = raw                     # 2.5D: (x, y, elevation)
            else:
                at = self.check_type("position", "at", {"type": "pair"}, raw, where)
                if not isinstance(at, list):
                    self.fail("G1205", "at is (x, y), or (x, y, elevation) in a 2.5D scene", where)
                e.x, e.y = at
        if "rotation" in bound:
            e.rotation = self.check_type("position", "rotation", {"type": "number"}, *bound["rotation"])
        if "scale" in bound:
            e.scale = self.check_type("position", "scale", {"type": "pair"}, *bound["scale"])
        if "name" in bound:
            e.name = self.check_type("position", "name", {"type": "string"}, *bound["name"])

    def entity(self, node, args, kwargs):
        if not args or not isinstance(args[0], str):
            self.fail("G1206", "Entity(...) starts with its name", node, fix='Entity("player", Sprite(ship))')
        e = EntityModel(name=args[0], line=node.lineno)
        for i, c in enumerate(args[1:], 1):
            if not isinstance(c, ComponentValue):
                self.fail("G1205", "after the name, an Entity takes components", node.args[i],
                          received=_shown(c), fix="Sprite(...), Shape(...), Text(...), Spin(...)...")
            e.components.append(c)
        sprite = next((c for c in e.components if c.type == "Sprite"), None)
        for c in e.components:
            if c.type == "Animator":
                if sprite is None:
                    self.fail("G1205", "Animator animates the entity's Sprite: add a Sprite(sheet...)", node)
                for name, anim in c.values["animations"].items():
                    self.check_frames(sprite.values["image"], anim["frames"], "Animator %r" % name, node)
        bound = {k: v for k, v in kwargs.items()}
        allowed = ("tags", "children", "at", "rotation", "scale", "active", "ui", "group", "persistent", "anchor")
        for key in bound:
            if key not in allowed:
                self.fail("G1204", "Entity has no parameter '%s'" % key, bound[key][1],
                          fix=self.close(key, allowed))
        if "ui" in bound:
            e.ui = self.check_type("Entity", "ui", {"type": "bool"}, *bound["ui"])
        if "tags" in bound:
            tags = bound["tags"][0]
            if not isinstance(tags, (list, tuple)) or not all(isinstance(t, str) for t in tags):
                self.fail("G1205", "tags is a list of texts", bound["tags"][1])
            e.tags = list(tags)
        if "children" in bound:
            children = bound["children"][0]
            if not isinstance(children, (list, tuple)) or not all(isinstance(c, EntityModel) for c in children):
                self.fail("G1205", "children is a list of Entity(...)", bound["children"][1])
            e.children = [c.clone() for c in children]
        if "active" in bound:
            e.active = self.check_type("Entity", "active", {"type": "bool"}, *bound["active"])
        if "group" in bound:
            e.group = self.check_type("Entity", "group", {"type": "string"}, *bound["group"])
        if "anchor" in bound:
            name = self.check_type("Entity", "anchor", {"type": "enum", "values": list(ANCHORS)}, *bound["anchor"])
            if not e.ui:
                self.fail("G1205", "anchor is for interface entities (ui=True)", bound["anchor"][1])
            e.anchor = ANCHORS[name]
        if "persistent" in bound:
            e.persistent = self.check_type("Entity", "persistent", {"type": "bool"}, *bound["persistent"])
            if e.persistent and _has_physics(e):
                self.fail("G1205", "a persistent entity cannot have a Body or a Collider", bound["persistent"][1],
                          cause="The physics belongs to each scene; persistent entities are for fades, text boxes "
                                "and the interface. Put the player in each scene and use game.goto(scene, at).")
        self.place(e, bound)
        return e

    def prefab_call(self, prefab, node, args, kwargs):
        name = prefab.node.name
        if len(args) > len(prefab.params):
            self.fail("G1204", "%s() takes %d value(s)" % (name, len(prefab.params)), node)
        values = dict(prefab.defaults)
        for param, value in zip(prefab.params, args):
            values[param] = value
        for key, (value, where) in kwargs.items():
            if key not in prefab.params:
                self.fail("G1204", "%s() has no parameter '%s'" % (name, key), where,
                          fix=self.close(key, prefab.params))
            values[key] = value
        missing = [p for p in prefab.params if p not in values]
        if missing:
            self.fail("G1206", "%s() needs %s" % (name, ", ".join(missing)), node)
        env = dict(prefab.env)
        env.update(values)
        result = self.evaluate(prefab.node.body[-1].value, env)
        if not isinstance(result, EntityModel):
            self.fail("G1212", "@prefab %s has to return an Entity(...)" % name, prefab.node)
        return result

    # ── the end ──────────────────────────────────────────────────────────

    def finish(self):
        if self.game is None:
            self.fail("G1209", "there is no Game(...)", None,
                      fix='game = Game("My game", size=(360, 640))')
        scenes = self.model.scenes
        if not scenes:
            self.fail("G1210", "the game has no scene", None, fix='main = game.scene("main", start=True)')
        starts = [s for s in scenes if s.start]
        if len(starts) > 1:
            raise GameError("G1210", "two scenes have start=True: %s and %s" % (starts[0].name, starts[1].name),
                            self.display, starts[1].line)
        if not starts:
            scenes[0].start = True
        for s in scenes:
            cam = s.camera or {}
            if cam.get("bounds") == "map":
                raise GameError("G1210", 'scene %s: camera bounds "map" needs a Tilemap in the scene' % s.name,
                                self.display, s.line)
            follow = cam.get("follow")
            if follow and not any(_has_name(e, follow) for e in s.entities):
                raise GameError("G1210", "scene %s: the camera follows %r, but no entity has that name"
                                % (s.name, follow), self.display, s.line)

    @staticmethod
    def close(name, options):
        hits = difflib.get_close_matches(name, list(options), n=3, cutoff=0.6)
        return ["Did you mean %s?" % " or ".join(hits)] if hits else []


def _png_problem(path):
    """None for a PNG a Canvas can read; else what is wrong with the file."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(33)
    except OSError:
        return None                                   # the asset check says the file is missing
    if len(head) < 29 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return "is not a PNG"
    if head[28] != 0:
        return "is an interlaced PNG"
    return None


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _has_physics(e):
    return any(c.type in ("Body", "Collider") for c in e.components) or any(_has_physics(c) for c in e.children)


def _has_name(e, name):
    return e.name == name or any(_has_name(c, name) for c in e.children)


def _jsonable(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return True
    if isinstance(v, (list, tuple)):
        return all(_jsonable(x) for x in v)
    if isinstance(v, dict):
        return all(isinstance(k, str) and _jsonable(x) for k, x in v.items())
    return False


def _shown(v):
    if isinstance(v, AssetRef):
        return "assets.%s(%r)" % (v.kind, v.path)
    if isinstance(v, ComponentValue):
        return v.type + "(...)"
    if isinstance(v, EntityModel):
        return "Entity(%r)" % v.name
    if isinstance(v, TextRef):
        return "t(%r)" % v.key
    return repr(v)


def read(path, project_root):
    return Reader(path, project_root).read()


class ModuleReader(Reader):
    """A file of game/ other than main.py: code only (see compiler/modules.py)."""

    def read_module(self):
        for node in self.parse().body:
            self.statement(node)
        return self.code

    def statement(self, node):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef, ast.Pass)):
            return super().statement(node)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            return self.module_assign(node)
        kind = type(node).__name__.lower()
        self.fail("G1220", "'%s' is not allowed at the top of a module" % kind, node,
                  cause="A module under game/ holds code: imports, constants, module state, functions and classes. "
                        "The game's declarations (Game, scenes, entities) are in game/main.py.",
                  fix="Put the code in a function, and call it from a script.")

    def function(self, node):
        return super().function(node)

    def module_assign(self, node):
        from .modules import is_state_value
        from .scripts import StateVar
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if len(targets) != 1 or not isinstance(targets[0], ast.Name) or node.value is None:
            self.fail("G1213", "assign one name: NAME = value", node)
        name = targets[0].id
        if name in self.env or name in self.code.state:
            self.fail("G2012", "the name %s is taken" % name, node)
        annotation = node.annotation if isinstance(node, ast.AnnAssign) else None
        call = node.value
        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and isinstance(self.env.get(call.func.id), _Api) and self.env[call.func.id].name == "table"):
            return self.table_assign(name, call, node)
        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                and isinstance(self.env.get(call.func.value.id), _Assets)):
            self.env[name] = self.code.declared[name] = self.evaluate(call, self.env)      # assets.image(...)
            return
        if is_state_value(node.value):
            self.code.state[name] = StateVar(name, annotation, node.value, node.lineno)
            self.env[name] = _Api("state", name)
            return
        value = self.evaluate(node.value, self.env)
        if not isinstance(value, (int, float, str, bool)):
            self.fail("G1220", "%s: a module constant is a number, a text or True/False" % name, node,
                      fix="State the module keeps is a list, a dict or a @dataclass: %s = [] / GameState()" % name)
        self.code.constants[name] = value
        self.env[name] = value

    def table_assign(self, name, call, node):
        """SPECIES = table("data/species", Species)"""
        from .scripts import TableVar
        if (len(call.args) != 2 or call.keywords or not isinstance(call.args[0], ast.Constant)
                or not isinstance(call.args[0].value, str) or not isinstance(call.args[1], ast.Name)):
            self.fail("G1204", 'table("data/name", Record): the path written out and a @dataclass', node)
        path = call.args[0].value.strip("/")
        if path.endswith(".json"):
            path = path[:-5]
        if not re.match(r"^[A-Za-z0-9_\-]+(/[A-Za-z0-9_\-]+)*$", path):
            self.fail("G1204", "table: the path is folders and a name (data/species), relative to the project", node)
        record = self.env.get(call.args[1].id)
        if not (isinstance(record, _Api) and record.kind == "record"):
            self.fail("G1204", "table: %s is not a @dataclass" % call.args[1].id, node)
        self.code.tables[name] = TableVar(name, path, record.name, node.lineno)
        self.env[name] = _Api("table", name)
