"""The script translator: the code of game/ (Script classes, @dataclass classes, plain functions,
module state), to typed Java.

Read, never run (the ApkPy rule): the classes' AST is checked and written out
as Java classes extending apkpygame.core.Script, compiled into the game's
jar/AAR. The Python kept is small and typed:

- types: int, float, bool, str, Entity, Body, Sprite, Text, Animator, Canvas, Sound,
  Image (an assets.image(...) of the game, by its name), Prefab, list[T], dict[str, T], Optional[T] (T | None), and the game's own
  @dataclass classes;
- each file of game/ is a module: game/main.py is the Java class GameModule,
  game/battle/engine.py is M_battle__engine (plain functions and module state
  as static members); Script and @dataclass classes are top-level classes,
  so their names are unique in the game;
- a local's type comes from what it is assigned (int and float mixed: float);
  fields and parameters are annotated;
- Python's meaning is kept where Java differs (// % / round str() negative
  indexes), through apkpygame.core.Py;
- truthiness is not guessed: `if count:` is refused, `if count != 0:` is not.

Anything else stops the build with a G2xxx error at the line.
"""
import ast
import difflib
import re

from ..errors import GameError
from .._pycompat import subscript_slice

JAVA_WORDS = set("""abstract assert boolean break byte case catch char class const continue default do double else
enum extends final finally float for goto if implements import instanceof int interface long native new package
private protected public return short static strictfp super switch synchronized this throw throws transient try void
volatile while true false null var record""".split())
RESERVED = {"Game", "Scene", "Entity", "Script", "Clip", "Panel", "Button", "Bar", "Shape", "ScrollList", "Tabs", "Toggle", "Slider",
            "Keyboard", "Boxed", "Clicker", "ScriptState", "Data", "Table", "FileSaves", "Py", "Json", "Body", "Sprite", "Text", "Animator", "Billboard",
            "GridController", "Canvas", "Map", "List",
            "ArrayList", "LinkedHashMap", "Math", "StrictMath", "String", "Object", "GameScripts", "GameModule"}

NUM = ("int", "float")
BOX = {"int": "Integer", "float": "Double", "bool": "Boolean"}
JAVA = {"int": "int", "float": "double", "bool": "boolean", "str": "String", "Entity": "Entity", "Body": "Body",
        "Sprite": "Sprite", "Text": "Text", "Animator": "Animator", "Billboard": "Billboard",
        "GridController": "GridController", "Sound": "String", "Image": "String", "Props": "Props", "Shape": "Shape",
        "Panel": "Panel", "Button": "Button", "Bar": "Bar", "ScrollList": "ScrollList", "Tabs": "Tabs",
        "Toggle": "Toggle", "Slider": "Slider", "Keyboard": "Keyboard", "Canvas": "Canvas",
        "Prefab": "Map<String, Object>", "void": "void"}
DEFAULT = {"int": "0", "float": "0", "bool": "false"}
# what a declaration (Ship(speed=3)) may set: the field types the bundle can carry
SETTABLE = {"int", "float", "bool", "str", "Sound", "Prefab"}
LIFECYCLE = {"on_start": ("onStart", [], "void"), "update": ("onUpdate", ["float"], "void"),
             "on_collide": ("onCollide", ["Entity", "str"], "void"), "on_tap": ("onTap", [], "void"),
             "on_destroy": ("onDestroy", [], "void"), "on_back": ("onBack", [], "bool"),
             "on_row": ("onRow", ["Entity", "int"], "void")}

# ── the API scripts can use: (receiver type, name) -> (args, result, Java template) ──
# {o} is the receiver, {0} {1}... the arguments. "rw" properties can be assigned.
PROPS = {
    "Entity": {"x": ("{o}.transform.x", "float", "rw"), "y": ("{o}.transform.y", "float", "rw"),
               "rotation": ("{o}.transform.rotation", "float", "rw"), "scale": ("{o}.transform.scaleX", "float", "rw"),
               "name": ("{o}.name", "str", "r"), "active": ("{o}.active", "bool", "rw"),
               "elevation": ("{o}.transform.elevation", "float", "rw"),
               "props": ("{o}.props", "Props", "r"),
               "shape": ('Py.notNone({o}.get(Shape.class), "shape (the entity has no Shape)")', "Shape", "r"),
               "panel": ('Py.notNone({o}.get(Panel.class), "panel (the entity has no Panel)")', "Panel", "r"),
               "button": ('Py.notNone({o}.get(Button.class), "button (the entity has no Button)")', "Button", "r"),
               "bar": ('Py.notNone({o}.get(Bar.class), "bar (the entity has no Bar)")', "Bar", "r"),
               "list": ('Py.notNone({o}.get(ScrollList.class), "list (the entity has no ScrollList)")', "ScrollList", "r"),
               "tabs": ('Py.notNone({o}.get(Tabs.class), "tabs (the entity has no Tabs)")', "Tabs", "r"),
               "toggle": ('Py.notNone({o}.get(Toggle.class), "toggle (the entity has no Toggle)")', "Toggle", "r"),
               "slider": ('Py.notNone({o}.get(Slider.class), "slider (the entity has no Slider)")', "Slider", "r"),
               "keyboard": ('Py.notNone({o}.get(Keyboard.class), "keyboard (the entity has no Keyboard)")', "Keyboard", "r"),
               "billboard": ('Py.notNone({o}.get(Billboard.class), "billboard (the entity has no Billboard)")',
                             "Billboard", "r"),
               "grid": ('Py.notNone({o}.get(GridController.class), "grid (the entity has no GridController)")',
                        "GridController", "r"),
               "body": ('Py.notNone({o}.get(Body.class), "body (the entity has no Body)")', "Body", "r"),
               "sprite": ('Py.notNone({o}.get(Sprite.class), "sprite (the entity has no Sprite)")', "Sprite", "r"),
               "text": ('Py.notNone({o}.get(Text.class), "text (the entity has no Text)")', "Text", "r"),
               "animator": ('Py.notNone({o}.get(Animator.class), "animator (the entity has no Animator)")',
                            "Animator", "r"),
               "canvas": ('Py.notNone({o}.get(Canvas.class), "canvas (the entity has no Canvas)")', "Canvas", "r")},
    "Body": {"vx": ("{o}.vx", "float", "rw"), "vy": ("{o}.vy", "float", "rw"), "gravity": ("{o}.gravity", "float", "rw"),
             "on_floor": ("{o}.onFloor", "bool", "r"), "on_ceiling": ("{o}.onCeiling", "bool", "r"),
             "on_wall": ("({o}.onWallLeft || {o}.onWallRight)", "bool", "r")},
    "Sprite": {"flip_x": ("{o}.flipX", "bool", "rw"), "flip_y": ("{o}.flipY", "bool", "rw"),
               "alpha": ("{o}.alpha", "float", "rw"), "visible": ("{o}.visible", "bool", "rw")},
    "Text": {"text": ("{o}.text", "str", "rw"), "alpha": ("{o}.alpha", "float", "rw"),
             "visible": ("{o}.visible", "bool", "rw"), "size": ("{o}.size", "float", "rw"),
             "max_width": ("{o}.maxWidth", "float", "rw"), "page": ("{o}.page", "int", "rw"),
             "pages": ("{o}.pages()", "int", "r"), "lines": ("{o}.lineCount()", "int", "r"),
             "visible_chars": ("{o}.visibleChars", "int", "rw"), "page_chars": ("{o}.pageChars()", "int", "r"),
             "width": ("{o}.width()", "float", "r"), "line_height": ("{o}.lineHeight()", "float", "r")},
    "Animator": {"current": ("{o}.current", "str", "r")},
    "Shape": {"width": ("{o}.width", "float", "rw"), "height": ("{o}.height", "float", "rw"),
              "alpha": ("{o}.alpha", "float", "rw"), "visible": ("{o}.visible", "bool", "rw")},
    "Panel": {"width": ("{o}.width", "float", "rw"), "height": ("{o}.height", "float", "rw"),
              "alpha": ("{o}.alpha", "float", "rw"), "visible": ("{o}.visible", "bool", "rw"),
              "modal": ("{o}.modal", "bool", "rw")},
    "Button": {"label": ("{o}.label", "str", "rw"), "enabled": ("{o}.enabled", "bool", "rw"),
               "visible": ("{o}.visible", "bool", "rw"), "alpha": ("{o}.alpha", "float", "rw"),
               "clicked": ("{o}.clicked", "bool", "r"), "text": ("{o}.text", "Text", "r")},
    "ScrollList": {"count": ("{o}.count", "int", "rw"), "scroll": ("{o}.scroll", "float", "rw"),
                   "max_scroll": ("{o}.maxScroll()", "float", "r"), "tapped": ("{o}.tapped", "int", "r"),
                   "visible": ("{o}.visible", "bool", "rw")},
    "Tabs": {"selected": ("{o}.selected", "int", "rw"), "changed": ("{o}.changed", "bool", "r")},
    "Toggle": {"value": ("{o}.value", "bool", "rw"), "changed": ("{o}.changed", "bool", "r"),
               "enabled": ("{o}.enabled", "bool", "rw"), "visible": ("{o}.visible", "bool", "rw"),
               "label": ("{o}.label", "str", "rw")},
    "Slider": {"value": ("{o}.value", "float", "rw"), "changed": ("{o}.changed", "bool", "r"),
               "enabled": ("{o}.enabled", "bool", "rw"), "visible": ("{o}.visible", "bool", "rw")},
    "Keyboard": {"text": ("{o}.text", "str", "rw"), "changed": ("{o}.changed", "bool", "r"),
                 "done": ("{o}.done", "bool", "r"), "max_length": ("{o}.maxLength", "int", "rw")},
    "Bar": {"value": ("{o}.value", "float", "rw"), "max": ("{o}.max", "float", "rw"),
            "shown": ("{o}.shown", "float", "r"), "moving": ("{o}.moving()", "bool", "r"),
            "visible": ("{o}.visible", "bool", "rw")},
    "Billboard": {"facing": ("{o}.facing", "float", "rw"), "auto_facing": ("{o}.autoFacing", "bool", "rw"),
                  "moving": ("{o}.moving()", "bool", "r"), "visible": ("{o}.visible", "bool", "rw")},
    "Canvas": {"width": ("{o}.width", "int", "r"), "height": ("{o}.height", "int", "r"),
               "visible": ("{o}.visible", "bool", "rw"), "alpha": ("{o}.alpha", "float", "rw"),
               "brush": ("{o}.brushText()", "str", "r"), "brush_size": ("{o}.brushSize", "int", "rw"),
               "pointer_x": ("{o}.pointerX()", "int", "r"), "pointer_y": ("{o}.pointerY()", "int", "r"),
               "changed": ("{o}.changed", "bool", "r")},
    "GridController": {"arrivals": ("{o}.arrivals", "int", "r"), "walking": ("{o}.walking()", "bool", "r"), "speed": ("{o}.speed", "float", "rw")},
    "scene": {"camera_yaw": ('Py.notNone(sceneNow().camera3d, "camera_yaw (a 2.5D scene)").yaw', "float", "rw"),
              "camera_pitch": ('Py.notNone(sceneNow().camera3d, "camera_pitch (a 2.5D scene)").pitch', "float", "rw"),
              "camera_distance": ('Py.notNone(sceneNow().camera3d, "camera_distance (a 2.5D scene)").distance',
                                  "float", "rw")},
    "game": {"width": ("game().viewport.designWidth", "float", "r"),
             "height": ("game().viewport.designHeight", "float", "r"),
             "view_width": ("game().viewport.width", "float", "r"),
             "view_height": ("game().viewport.height", "float", "r"),
             "arrival": ("game().arrival", "str", "r"),
             "time": ("(game().steps() * game().stepSeconds)", "float", "r"),
             "steps": ("((int) game().steps())", "int", "r")},
    "math": {"pi": ("Math.PI", "float", "r"), "e": ("Math.E", "float", "r"), "inf": ("Double.POSITIVE_INFINITY", "float", "r")},
}
METHODS = {
    ("Entity", "destroy"): ([], "void", "{o}.destroy()"),
    ("Entity", "has_tag"): (["str"], "bool", "{o}.hasTag({0})"),
    ("Animator", "play"): (["str"], "void", "{o}.play({0})"),
    ("Text", "measure"): (["str"], "float", "{o}.measure({0})"),
    ("game", "get"): (["str"], "float", "game().var({0})"),
    ("game", "set"): (["str", "float"], "void", "game().setVar({0}, {1})"),
    ("game", "add"): (["str", "float"], "void", "game().setVar({0}, game().var({0}) + ({1}))"),
    ("game", "open_app"): (["str"], "void", "game().openApp({0}, null)"),
    ("game", "goto"): (["str", "str?", "float?"], "void", "game().gotoScene({0}, {1|null}, {2|0.0})"),
    ("Entity", "child"): (["str"], "Entity", 'Py.notNone({o}.child({0}), "child (no entity of that name below this one)")'),
    ("ScrollList", "refresh"): ([], "void", "{o}.refresh()"),
    ("ScrollList", "scroll_to"): (["int"], "void", "{o}.scrollTo({0})"),
    ("Shape", "set_color"): (["str"], "void", "{o}.setColor({0})"),
    ("Text", "set_color"): (["str"], "void", "{o}.setColor({0})"),
    ("Sprite", "set_tint"): (["str"], "void", "{o}.setTint({0})"),
    ("Sprite", "set_frame"): (["int"], "void", "{o}.setFrame({0})"),
    ("Sprite", "set_image"): (["str"], "void", "{o}.setImage({0})"),
    ("Billboard", "set_image"): (["str"], "void", "{o}.setImage({0})"),
    ("GridController", "stop"): ([], "void", "{o}.stop()"),
    ("Canvas", "set"): (["int", "int", "str"], "void", "{o}.set({0}, {1}, {2})"),
    ("Canvas", "get"): (["int", "int"], "str", "{o}.get({0}, {1})"),
    ("Canvas", "fill"): (["str"], "void", "{o}.fill({0})"),
    ("Canvas", "clear"): ([], "void", "{o}.clear()"),
    ("Canvas", "rect"): (["int", "int", "int", "int", "str"], "void", "{o}.rect({0}, {1}, {2}, {3}, {4})"),
    ("Canvas", "line"): (["int", "int", "int", "int", "str"], "void", "{o}.line({0}, {1}, {2}, {3}, {4})"),
    ("Canvas", "circle"): (["int", "int", "int", "str"], "void", "{o}.circle({0}, {1}, {2}, {3})"),
    ("Canvas", "flood"): (["int", "int", "str"], "void", "{o}.flood({0}, {1}, {2})"),
    ("Canvas", "count"): (["str"], "int", "{o}.count({0})"),
    ("Canvas", "stamp"): (["Image", "int", "int"], "void", "{o}.stamp({0}, {1}, {2})"),
    ("Canvas", "set_brush"): (["str"], "void", "{o}.setBrush({0})"),
    ("Billboard", "set_frame"): (["int"], "void", "{o}.setFrame({0})"),
    ("audio", "set_music"): (["bool"], "void", "game().setMusicOn({0})"),
    ("audio", "set_sound_volume"): (["float"], "void", "game().soundVolume = {0}"),
    ("scene", "pause"): (["str"], "void", "sceneNow().pause({0})"),
    ("scene", "resume"): (["str"], "void", "sceneNow().resume({0})"),
    ("scene", "is_paused"): (["str"], "bool", "sceneNow().isPaused({0})"),
    ("input", "pointer_on_ui"): ([], "bool", "game().input.pointerOnUi()"),
    ("game", "store_get"): (["str"], "str", "game().store().get({0})"),
    ("game", "store_set"): (["str", "str"], "void", "game().store().set({0}, {1})"),
    ("game", "text"): (["str"], "str", "game().text({0}, {0})"),
    ("input", "axis_x"): ([], "float", "game().input.axisX()"),
    ("input", "axis_y"): ([], "float", "game().input.axisY()"),
    ("input", "key_down"): (["str"], "bool", "game().input.isKeyDown({0})"),
    ("input", "key_pressed"): (["str"], "bool", "game().input.wasKeyPressed({0})"),
    ("input", "pointer_down"): ([], "bool", "game().input.pointerDown()"),
    ("input", "pointer_pressed"): ([], "bool", "game().input.pointerPressed()"),
    ("input", "pointer_x"): ([], "float", "pointerX()"),
    ("input", "pointer_y"): ([], "float", "pointerY()"),
    ("audio", "play"): (["Sound", "float?"], "void", "game().playSound({0}, {1|1.0})"),
    ("scene", "spawn"): (["Prefab", "float", "float"], "Entity", "sceneNow().spawnTemplate({0}, {1}, {2})"),
    ("scene", "find"): (["str"], "Entity?", "sceneNow().find({0})"),
    ("scene", "count"): (["str"], "int", "sceneNow().count({0})"),
    ("scene", "with_tag"): (["str"], "list[Entity]", "listOf(sceneNow().withTag({0}))"),
    ("scene", "tile_tag"): (["float", "float", "str"], "str", "sceneNow().tileTag({0}, {1}, {2})"),
    ("Props", "get_str"): (["str", "str?"], "str", '{o}.getStr({0}, {1|""})'),
    ("Props", "get_int"): (["str", "int?"], "int", "{o}.getInt({0}, {1|0})"),
    ("Props", "get_float"): (["str", "float?"], "float", "{o}.getFloat({0}, {1|0.0})"),
    ("Props", "get_bool"): (["str", "bool?"], "bool", "{o}.getBool({0}, {1|false})"),
    ("Props", "has"): (["str"], "bool", "{o}.has({0})"),
    ("saves", "write"): (["str", "str"], "void", "game().saves().write({0}, {1})"),
    ("saves", "read"): (["str"], "str?", "game().saves().read({0})"),
    ("saves", "exists"): (["str"], "bool", "(game().saves().read({0}) != null)"),
    ("saves", "delete"): (["str"], "void", "game().saves().delete({0})"),
    ("random", "random"): ([], "float", "game().random.next()"),
    ("random", "uniform"): (["float", "float"], "float", "game().random.range({0}, {1})"),
    ("random", "randint"): (["int", "int"], "int", "(({0}) + game().random.nextInt(({1}) - ({0}) + 1))"),
}
MATH1 = {"sqrt": "StrictMath.sqrt", "sin": "StrictMath.sin", "cos": "StrictMath.cos", "tan": "StrictMath.tan",
         "asin": "StrictMath.asin", "acos": "StrictMath.acos", "atan": "StrictMath.atan", "exp": "StrictMath.exp",
         "log": "StrictMath.log", "radians": "Math.toRadians", "degrees": "Math.toDegrees", "fabs": "Math.abs"}
MATH2 = {"atan2": "StrictMath.atan2", "hypot": "StrictMath.hypot", "pow": "StrictMath.pow"}
MODULE_OBJECTS = {"game", "input", "audio", "scene", "math", "random", "saves"}
CMP = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="}


class ScriptClass:
    """What the reader found: fields (name -> (type, default value, line)) and methods (AST)."""

    def __init__(self, node, fields, methods):
        self.node, self.name, self.fields, self.methods = node, node.name, fields, methods


class Function:
    def __init__(self, node):
        self.node, self.name = node, node.name


class RecordClass:
    """A @dataclass: fields (name -> (type, default AST or None, line)), in order, and methods (AST)."""

    def __init__(self, node, fields, methods):
        self.node, self.name, self.fields, self.methods = node, node.name, fields, methods


class StateVar:
    """Module state: NAME = GameState() / NAME: list[str] = [] at the top of a game/ module."""

    def __init__(self, name, annotation, value, line):
        self.name, self.annotation, self.value, self.line = name, annotation, value, line


class TableVar:
    """SPECIES = table("data/species", Species): the rows of data/species(.json), checked by the build."""

    def __init__(self, name, path, record, line):
        self.name, self.path, self.record, self.line = name, path, record, line


class ModuleCode:
    """One file of game/ as the translator sees it."""

    def __init__(self, source, java):
        self.source, self.java = source, java
        self.scripts, self.records, self.functions = [], [], []
        self.constants, self.state, self.tables = {}, {}, {}
        self.declared = {}         # assets.* and @prefab: the reader's, for declarations in other files
        self.imported = {}         # local name -> (ModuleCode, its name there)
        self.aliases = {}          # local name -> ModuleCode (import game.x as y, from game import x)
        self.dataclass_names = {}  # local name -> "dataclass" / "field" / "replace"
        self.game_var = "game"

    def own(self, name):
        """(kind, owner java class, object) for a name defined in this file, or None."""
        for kind, items in (("script", self.scripts), ("record", self.records), ("function", self.functions)):
            for x in items:
                if x.name == name:
                    return kind, self.java, x
        if name in self.constants:
            return "constant", self.java, self.constants[name]
        if name in self.state:
            return "state", self.java, self.state[name]
        if name in self.tables:
            return "table", self.java, self.tables[name]
        if name in self.declared:
            return "declared", self.java, self.declared[name]
        return None

    def lookup(self, name, seen=()):
        """Like own(), following from-imports (a name another module imported can be imported again)."""
        hit = self.own(name)
        if hit is not None or name not in self.imported or self.source in seen:
            return hit
        other, there = self.imported[name]
        return other.lookup(there, seen + (self.source,))


def java_module_name(source):
    """game/main.py -> GameModule; game/battle/engine.py -> M_battle__engine."""
    path = source.replace("\\", "/")
    if path.endswith("/main.py") and path.count("/") <= 1 or path == "main.py":
        return "GameModule"
    if path.startswith("game/"):
        path = path[5:]
    return "M_" + path[:-3].replace("/", "__") if path.endswith(".py") else "M_" + path.replace("/", "__")


def parse_type(node, fail, records=()):
    """An annotation to a type string (records: the names of the game's @dataclass classes)."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and node.value is None:
        return "None"
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in records:
        return node.value                                    # "Monster": a forward reference
    if isinstance(node, ast.Name):
        if node.id in JAVA or node.id == "None" or node.id in records:
            return node.id
        fail("G2006", "unknown type %r" % node.id, node,
             fix="Types: int, float, bool, str, Entity, Body, Sprite, Text, Animator, Billboard, GridController, Canvas, Sound, Image, "
                 "Prefab, list[T], "
                 "dict[str, T], Optional[T]")
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        base = node.value.id
        inside = subscript_slice(node)
        args = inside.elts if isinstance(inside, ast.Tuple) else [inside]
        if base == "list" and len(args) == 1:
            return "list[%s]" % parse_type(args[0], fail, records)
        if base == "dict" and len(args) == 2 and parse_type(args[0], fail, records) == "str":
            return "dict[%s]" % parse_type(args[1], fail, records)
        if base == "Optional" and len(args) == 1:
            return optional(parse_type(args[0], fail, records))
        if base == "Ref" and len(args) == 1 and isinstance(args[0], (ast.Name, ast.Constant)):
            return "str"                                     # the id of a row (checked by the build)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        a, b = parse_type(node.left, fail, records), parse_type(node.right, fail, records)
        if b == "None":
            return optional(a)
        if a == "None":
            return optional(b)
    fail("G2006", "this annotation is not a type ApkPyGame knows", node)


def optional(t):
    if t in ("int", "float", "bool", "str", "Sound"):
        return t + "?"
    return t if t.endswith("?") else t + "?"


def base(t):
    return t[:-1] if t and t.endswith("?") else t


def java_type(t, boxed=False):
    nullable = t.endswith("?")
    t = base(t)
    if t.startswith("list["):
        return "ArrayList<%s>" % java_type(t[5:-1], True)
    if t.startswith("dict["):
        return "LinkedHashMap<String, %s>" % java_type(t[5:-1], True)
    if t.startswith("table["):
        return "Table<%s>" % t[6:-1]
    if (boxed or nullable) and t in BOX:
        return BOX[t]
    return JAVA.get(t, t)                     # a @dataclass is its own Java class


def default_value(t):
    if t.endswith("?"):
        return "null"
    return DEFAULT.get(t, "null")


def jname(name):
    return name + "_" if name in JAVA_WORDS or name in RESERVED else name


def jstr(s):
    out = ['"']
    for ch in s:
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ord(ch) < 32 or ord(ch) > 126:
            out.append("\\u%04x" % ord(ch))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


class _Out:
    """Java text, with the Python line of each Java line."""

    def __init__(self):
        self.lines, self.py = [], []

    def add(self, text, py_line=0, indent=0):
        for part in text.split("\n"):
            self.lines.append("    " * indent + part)
            self.py.append(py_line)


def translate_program(modules):
    """Every module of the game to Java: {"File.java": text}, with one GameScripts registry."""
    records = {}
    for m in modules:
        for r in m.records:
            records[r.name] = r
    files, scripts, stateful = {}, [], []
    for m in modules:
        t = Translator(m.source, (), (), {}, module=m, records=records)
        files.update(t.translate_module())
        scripts += m.scripts
        if m.state:
            stateful.append(m)
    files["GameScripts.java"] = Translator.registry_for(modules[0].source, scripts, stateful)
    return files


class Translator:
    def __init__(self, source, classes, functions, constants, game_var="game", module=None, records=None):
        if module is None:                                   # one file (the corpus tests, older callers)
            module = ModuleCode(source, "GameModule")
            module.scripts, module.functions = list(classes), list(functions)
            module.constants, module.game_var = dict(constants), game_var
        self.mod = module
        self.source = module.source
        self.game_var = module.game_var
        self.records = records if records is not None else {r.name: r for r in module.records}
        self.scope = {}
        for name in list(module.imported) + [x.name for x in module.scripts + module.records + module.functions] \
                + list(module.constants) + list(module.state) + list(module.tables) \
                + [n for n, v in module.declared.items() if getattr(v, "kind", "") in ("image", "sound", "music")]:
            hit = module.lookup(name)
            if hit is not None:
                self.scope[name] = hit
        self.classes = {n: h[2] for n, h in self.scope.items() if h[0] == "script"}
        self.functions = {n: h[2] for n, h in self.scope.items() if h[0] == "function"}
        self.constants = {n: h[2] for n, h in self.scope.items() if h[0] == "constant"}
        self.cls, self.sigs, self.in_script, self.narrowed, self.lenient = None, {}, False, set(), False

    def fail(self, code, message, node=None, cause="", fix=()):
        raise GameError(code, message, self.source, getattr(node, "lineno", None), cause, fix)

    def ptype(self, node):
        return parse_type(node, self.fail, self.records)

    # ── signatures ───────────────────────────────────────────────────────

    def signature(self, fn, is_method):
        args = fn.args
        if args.vararg or args.kwarg or args.kwonlyargs or args.posonlyargs or args.defaults:
            self.fail("G2001", "def %s: plain parameters only (no defaults, *args, **kwargs)" % fn.name, fn)
        params = args.args[1:] if is_method else args.args
        if is_method and (not args.args or args.args[0].arg != "self"):
            self.fail("G2001", "def %s: a method's first parameter is self" % fn.name, fn)
        types = []
        for a in params:
            if a.annotation is None:
                if is_method and self.in_script and fn.name in LIFECYCLE:
                    types.append(LIFECYCLE[fn.name][1][len(types)] if len(types) < len(LIFECYCLE[fn.name][1])
                                 else "float")
                    continue
                self.fail("G2006", "def %s: parameter %s needs a type (%s: float)" % (fn.name, a.arg, a.arg), a)
            types.append(self.ptype(a.annotation))
        ret = self.ptype(fn.returns) if fn.returns is not None else "void"
        if ret == "None":
            ret = "void"
        return [a.arg for a in params], types, ret

    # ── classes ──────────────────────────────────────────────────────────

    def translate(self):
        files = self.translate_module()
        files["GameScripts.java"] = self.registry_for(self.source, list(self.mod.scripts),
                                                      [self.mod] if self.mod.state else [])
        return files

    def translate_module(self):
        """This module's own classes and its module class (no registry)."""
        files = {}
        for c in self.mod.scripts:
            files["%s.java" % c.name] = self.script_class(c)
        for r in self.mod.records:
            files["%s.java" % r.name] = self.record_class(r)
        files["%s.java" % self.mod.java] = self.module()
        return files

    def header(self, out):
        out.add("// GENERATED by ApkPy (the game's build) from %s: do not edit (edit the Python)." % self.source)
        out.add("package apkpygame.game;")
        out.add("")
        out.add("import apkpygame.core.*;")
        out.add("import apkpygame.core.components.*;")
        out.add("import apkpygame.core.physics2d.*;")
        out.add("import java.util.*;")
        out.add("")

    def script_class(self, c):
        out = _Out()
        self.header(out)
        out.add("public final class %s extends Script {" % c.name, c.node.lineno)
        for name, (t, _, line) in c.fields.items():
            init = " = new %s()" % java_type(t) if base(t).startswith(("list[", "dict[")) else ""
            out.add("public %s %s%s;" % (java_type(t), jname(name), init), line, 1)
        self.in_script = True
        sigs = {}
        for m in c.methods:
            sigs[m.name] = self.signature(m, True)
        self.cls, self.sigs = c, sigs
        if "on_tap" in sigs:
            out.add("")
            out.add("@Override protected boolean wantsTaps() { return true; }", 0, 1)
        for m in c.methods:
            out.add("")
            self.method(out, m, sigs[m.name], True)
        out.add("")
        out.add("@Override protected String pythonFile() { return %s; }" % jstr(self.source), 0, 1)
        out.add("@Override protected int[] pythonLines() { return PY_LINES; }", 0, 1)
        self.line_table(out)
        out.add("}")
        self.cls, self.in_script = None, False
        return "\n".join(out.lines) + "\n"

    @staticmethod
    def line_table(out):
        n = len(out.lines) + 2
        table = list(out.py) + [0] * 3
        out.add("private static final int[] PY_LINES = {0, %s};" % ", ".join(str(x) for x in table[:n]), 0, 1)

    def record_class(self, r):
        """A @dataclass: fields, a constructor with every field, copy (dataclasses.replace),
        Python's == and str(), and its part of the state hash."""
        out = _Out()
        self.header(out)
        out.add("public final class %s implements ScriptState.Value, Data.Record {" % r.name, r.node.lineno)
        fields = [(name, self.field_type(r, name)) for name in r.fields]
        for name, t in fields:
            out.add("public %s %s;" % (java_type(t), jname(name)), r.fields[name][2], 1)
        out.add("")
        params = ", ".join("%s %s" % (java_type(t), jname(n)) for n, t in fields)
        out.add("public %s(%s) {" % (r.name, params), r.node.lineno, 1)
        for name, _ in fields:
            out.add("this.%s = %s;" % (jname(name), jname(name)), 0, 2)
        out.add("}", 0, 1)
        out.add("")
        out.add("/** dataclasses.replace(x): a shallow copy, as in Python (lists are shared). */", 0, 1)
        out.add("public %s copy() {" % r.name, 0, 1)
        out.add("return new %s(%s);" % (r.name, ", ".join(jname(n) for n, _ in fields)), 0, 2)
        out.add("}", 0, 1)
        for name, t in fields:
            out.add("public %s set_%s(%s v) { this.%s = v; return this; }" % (r.name, name, java_type(t), jname(name)),
                    0, 1)
        out.add("")
        out.add("@Override public boolean equals(Object o) {", 0, 1)
        out.add("if (!(o instanceof %s)) return false;" % r.name, 0, 2)
        out.add("%s x = (%s) o;" % (r.name, r.name), 0, 2)
        same = ["Objects.equals(%s, x.%s)" % (jname(n), jname(n)) for n, _ in fields]
        out.add("return %s;" % (" && ".join(same) or "true"), 0, 2)
        out.add("}", 0, 1)
        out.add("")
        out.add("@Override public int hashCode() {", 0, 1)
        out.add("return Objects.hash(%s);" % ", ".join(jname(n) for n, _ in fields), 0, 2)
        out.add("}", 0, 1)
        out.add("")
        out.add("@Override public String toString() {", 0, 1)
        parts = ['"%s="' % n + " + Py.repr(%s)" % jname(n) for n, _ in fields]
        out.add('return "%s(" + %s + ")";' % (r.name, ' + ", " + '.join(parts) or '""'), 0, 2)
        out.add("}", 0, 1)
        out.add("")
        out.add("@Override public void writeJson(StringBuilder b) {", 0, 1)
        out.add("b.append('{');", 0, 2)
        for i, (name, _) in enumerate(fields):
            out.add("Data.field(b, %s, %s, %s);" % ("true" if i == 0 else "false", jstr(name), jname(name)), 0, 2)
        out.add("b.append('}');", 0, 2)
        out.add("}", 0, 1)
        out.add("")
        out.add("/** from_json / a table row: unknown keys are ignored, missing ones take the default. */", 0, 1)
        out.add("public static %s fromJson(Object json) {" % r.name, 0, 1)
        out.add("Map<String, Object> o = Data.object(json, %s);" % jstr(r.name), 0, 2)
        self.begin_body([], [])
        for name, t in fields:
            default = r.fields[name][1]
            out.add("%s %s;" % (java_type(t), jname(name)), 0, 2)
            out.add("if (o.containsKey(%s)) %s = %s;" % (jstr(name), jname(name),
                                                       self.from_json_code(t, "o.get(%s)" % jstr(name))), 0, 2)
            if default is not None:
                out.add("else %s = %s;" % (jname(name), self.field_default(r, name, t, default, r.node)), 0, 2)
            else:
                out.add("else throw Data.missing(%s, %s);" % (jstr(r.name), jstr(name)), 0, 2)
        out.add("return new %s(%s);" % (r.name, ", ".join(jname(n) for n, _ in fields)), 0, 2)
        out.add("}", 0, 1)
        out.add("")
        out.add("@Override public long mixState(long h) {", 0, 1)
        out.add("h = ScriptState.mix(h, %s);" % jstr(r.name), 0, 2)
        for name, _ in fields:
            out.add("h = ScriptState.mix(h, %s);" % jname(name), 0, 2)
        out.add("return h;", 0, 2)
        out.add("}", 0, 1)
        sigs = {m.name: self.signature(m, True) for m in r.methods}
        self.cls, self.sigs, self.in_script = r, sigs, False
        for m in r.methods:
            out.add("")
            self.method(out, m, sigs[m.name], True)
        self.cls = None
        out.add("}")
        return "\n".join(out.lines) + "\n"

    def from_json_code(self, t, e):
        """Java that makes a value of type t from the parsed JSON e (evaluated once)."""
        if t.endswith("?"):
            inner = self.from_json_code(base(t), "_v")
            jt = java_type(t)
            return ("Data.<%s>orNull(%s, new Data.Maker<%s>() { public %s make(Object _v) { return %s; } })"
                    % (jt, e, jt, jt, inner))
        if t == "int":
            return "Data.toInt(%s)" % e
        if t == "float":
            return "Data.toFloat(%s)" % e
        if t == "bool":
            return "Data.toBool(%s)" % e
        if t in ("str", "Sound"):
            return "Data.toStr(%s)" % e
        if t.startswith(("list[", "dict[")):
            inner_t = t[5:-1]
            jt = java_type(inner_t, True)
            maker = "new Data.Maker<%s>() { public %s make(Object _x) { return %s; } }" % (
                jt, jt, self.from_json_code(inner_t, "_x"))
            return "Data.%s(%s, %s)" % ("list" if t.startswith("list[") else "dict", e, maker)
        if t in self.records:
            return "%s.fromJson(%s)" % (t, e)
        self.fail("G2006", "a %s cannot come from JSON" % t, None,
                  cause="JSON holds numbers, texts, True/False, lists, dicts and @dataclass objects.")

    def field_type(self, r, name):
        t = r.fields[name][0]
        return t if isinstance(t, str) else self.ptype(t)

    def module(self):
        out = _Out()
        self.header(out)
        out.add("/** The plain functions and module state of %s. */" % self.source)
        out.add("public final class %s {" % self.mod.java)
        out.add("private %s() { }" % self.mod.java, 0, 1)
        self.cls, self.sigs, self.in_script = None, {}, False
        for v in self.mod.tables.values():
            out.add("")
            out.add("public static final Table<%s> %s = new Table<%s>(%s, new Data.Maker<%s>() {"
                    % (v.record, jname(v.name), v.record, jstr(v.path), v.record), v.line, 1)
            out.add("public %s make(Object o) { return %s.fromJson(o); }" % (v.record, v.record), v.line, 2)
            out.add("});", v.line, 1)
        if self.mod.state:
            out.add("")
            for v in self.mod.state.values():
                out.add("public static %s %s;" % (java_type(self.state_type(v)), jname(v.name)), v.line, 1)
            out.add("")
            out.add("static { resetState(); }", 0, 1)
            out.add("")
            out.add("/** The starting values (a new game, or before a journal is played again). */", 0, 1)
            out.add("public static void resetState() {", 0, 1)
            self.begin_body([], [])
            for v in self.mod.state.values():
                code, t = self.expr(v.value)
                out.add("%s = %s;" % (jname(v.name), self.convert(code, t, self.state_type(v), v.value)), v.line, 2)
            out.add("}", 0, 1)
            out.add("")
            out.add("public static long mixState(long h) {", 0, 1)
            for v in self.mod.state.values():
                out.add("h = ScriptState.mix(h, %s);" % jname(v.name), 0, 2)
            out.add("return h;", 0, 2)
            out.add("}", 0, 1)
        for f in self.mod.functions:
            out.add("")
            self.method(out, f.node, self.signature(f.node, False), False)
        out.add("}")
        return "\n".join(out.lines) + "\n"

    def state_type(self, v):
        if v.annotation is not None:
            return self.ptype(v.annotation)
        call = v.value
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id in self.records:
            return call.func.id
        self.fail("G2006", "%s: say what it holds (%s: list[str] = [])" % (v.name, v.name), v.value,
                  cause="Module state is typed like a field.")

    def begin_body(self, names, types):
        self.locals = dict(zip(names, types))
        self.params = set(names)
        self.temps = 0
        self.alias = {}
        self.narrowed = set()
        self.ret = "void"
        self.is_method = False

    @staticmethod
    def registry_for(source, scripts, stateful):
        out = _Out()
        out.add("// GENERATED by ApkPy (the game's build) from %s: do not edit (edit the Python)." % source)
        out.add("package apkpygame.game;")
        out.add("")
        out.add("import apkpygame.core.*;")
        out.add("import apkpygame.core.components.*;")
        out.add("import apkpygame.core.json.Json;")
        out.add("import java.util.*;")
        out.add("")
        out.add("/** Registers the scripts' readers and the module state (Game.load finds this class by name). */")
        out.add("public final class GameScripts {")
        out.add("private GameScripts() { }", 0, 1)
        out.add("")
        out.add("public static void register() {", 0, 1)
        for c in scripts:
            out.add('ComponentTypes.register("%s", new ComponentTypes.Reader() {' % c.name, 0, 2)
            out.add("@Override public Component read(Map<String, Object> o, Game game) {", 0, 3)
            out.add("%s s = new %s();" % (c.name, c.name), 0, 4)
            for name, (t, _, _) in c.fields.items():
                key = jstr(name)
                b = base(t)
                if b == "int":
                    expr = "(int) Json.num(o, %s, 0)" % key
                elif b == "float":
                    expr = "Json.num(o, %s, 0)" % key
                elif b == "bool":
                    expr = "Json.bool(o, %s, false)" % key
                elif b in ("str", "Sound"):
                    expr = "Json.str(o, %s, %s)" % (key, '""' if b == "str" else "null")
                elif b == "Prefab":
                    expr = "Json.obj(o, %s)" % key
                else:
                    continue
                out.add("if (o.containsKey(%s)) s.%s = %s;" % (key, jname(name), expr), 0, 4)
                if b == "Sound":
                    out.add("if (s.%s != null) game.assets.get(\"sound\", s.%s);" % (jname(name), jname(name)), 0, 4)
            out.add("return s;", 0, 4)
            out.add("}", 0, 3)
            out.add("});", 0, 2)
        for m in stateful:
            out.add("ScriptState.register(new ScriptState.Module() {", 0, 2)
            out.add("@Override public void reset() { %s.resetState(); }" % m.java, 0, 3)
            out.add("@Override public long mix(long h) { return %s.mixState(h); }" % m.java, 0, 3)
            out.add("});", 0, 2)
        out.add("}", 0, 1)
        out.add("}")
        return "\n".join(out.lines) + "\n"

    # ── methods ──────────────────────────────────────────────────────────

    def method(self, out, fn, sig, is_method):
        names, types, ret = sig
        self.ret = ret
        self.is_method = is_method
        self.locals = dict(zip(names, types))
        self.params = set(names)
        self.temps = 0
        self.narrowed = set()
        self.alias = {}
        body = [s for s in fn.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                                           and isinstance(s.value.value, str))]
        self.infer(body)
        if is_method and self.in_script and fn.name in LIFECYCLE:
            jn, want, result = LIFECYCLE[fn.name]
            if ret != result:
                self.fail("G2011", "%s does not return a value" % fn.name if result == "void"
                          else "write it as  def %s(self) -> %s:" % (fn.name, result), fn)
            jparams = ["double dt"] if jn == "onUpdate" else ["Entity other", "String side"] if jn == "onCollide" \
                else ["Entity row", "int index"] if jn == "onRow" else []
            renames = {}
            shapes = {"onUpdate": "update(self, dt: float)", "onCollide": "on_collide(self, other: Entity, side: str)",
                      "onRow": "on_row(self, row: Entity, index: int)"}
            for i, n in enumerate(names):
                if i >= len(want):
                    self.fail("G2009", "write it as %s" % shapes.get(jn, fn.name + "(self)"), fn)
                if types[i] != want[i]:
                    self.fail("G2003", "%s: parameter %s is %s" % (fn.name, n, want[i]), fn)
                renames[n] = jparams[i].split()[1]
            out.add("@Override protected %s %s(%s) {" % (java_type(result), jn, ", ".join(jparams)), fn.lineno, 1)
            self.alias = renames
        else:
            if fn.name in LIFECYCLE and not is_method:
                self.fail("G2001", "%s is a Script method name; a plain function cannot use it" % fn.name, fn)
            static = "" if is_method else "static "
            params = ", ".join("%s %s" % (java_type(t), jname(n)) for n, t in zip(names, types))
            out.add("public %s%s %s(%s) {" % (static, java_type(ret), jname(fn.name), params), fn.lineno, 1)
            self.alias = {}
        for name, t in self.locals.items():
            if name in self.params:
                continue
            if "?]" in t or t in ("None", "self"):
                self.fail("G2006", "%s: say what it holds (%s: list[float] = [])" % (name, name), fn,
                          cause="An empty list or None gives no type to translate.")
            out.add("%s %s = %s;" % (java_type(t), jname(name), default_value(t)), fn.lineno, 2)
        if is_method and self.in_script and fn.name in LIFECYCLE and ret == "bool":
            out.add("if (true) {", 0, 2)         # falling off the end is False, as Python's None would be
            self.block(out, body, 3)
            out.add("}", 0, 2)
            out.add("return false;", 0, 2)
        else:
            self.block(out, body, 2)
        out.add("}", 0, 1)

    def var(self, name):
        return self.alias.get(name, jname(name))

    # ── type inference of locals (two passes: an int later assigned a float is a float) ──

    def infer(self, body):
        self.lenient = True                  # types only: "this may be None" is checked when the code is written
        try:
            for _ in range(3):
                before = dict(self.locals)
                self.collect(body)
                if before == self.locals:
                    return
        finally:
            self.lenient = False

    def collect(self, body):
        for s in body:
            if isinstance(s, ast.Assign):
                for t in s.targets:
                    self.bind(t, s.value)
            elif isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                t = self.ptype(s.annotation)
                self.declare(s.target.id, t, s)
            elif isinstance(s, ast.AugAssign) and isinstance(s.target, ast.Name):
                if s.target.id in self.locals:
                    try:
                        t = self.binop_type(self.locals[s.target.id], self.quiet_type(s.value), s.op)
                        if t:
                            self.declare(s.target.id, t, s)
                    except GameError:
                        pass
            elif isinstance(s, ast.For) and isinstance(s.target, ast.Name):
                it = s.iter
                if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == "range":
                    self.declare(s.target.id, "int", s)
                else:
                    t = self.quiet_type(it)
                    if t and base(t).startswith("list["):
                        self.declare(s.target.id, base(t)[5:-1], s)
                    elif t and base(t).startswith("dict["):
                        self.declare(s.target.id, "str", s)
                    elif t and base(t).startswith("table["):
                        self.declare(s.target.id, base(t)[6:-1], s)
                self.collect(s.body)
            elif isinstance(s, (ast.If, ast.While)):
                self.collect(s.body)
                self.collect(s.orelse)

    def bind(self, target, value):
        if isinstance(target, ast.Name):
            t = self.quiet_type(value)
            if t:
                self.declare(target.id, t, target)
        elif isinstance(target, ast.Tuple) and isinstance(value, ast.Tuple) and len(target.elts) == len(value.elts):
            for a, b in zip(target.elts, value.elts):
                self.bind(a, b)

    def declare(self, name, t, node):
        if name in self.params and self.locals.get(name) == t:
            return
        old = self.locals.get(name)
        if old is None or old == t:
            self.locals[name] = t
        elif {base(old), base(t)} == {"int", "float"}:
            self.locals[name] = "float"
        elif t == "None" or old == "None":
            self.locals[name] = optional(old if t == "None" else t)
        elif base(old) == base(t):
            self.locals[name] = optional(base(t))

    def quiet_type(self, node):
        try:
            return self.expr(node)[1]
        except GameError:
            return None

    # ── statements ───────────────────────────────────────────────────────

    def block(self, out, body, ind):
        for s in body:
            self.statement(out, s, ind)

    def statement(self, out, s, ind):
        line = s.lineno
        if isinstance(s, ast.Expr):
            if isinstance(s.value, ast.Constant) and isinstance(s.value.value, str):
                return
            if not isinstance(s.value, ast.Call):
                self.fail("G2001", "this line does nothing", s)
            code, _ = self.expr(s.value)
            out.add(code + ";", line, ind)
        elif isinstance(s, ast.Assign):
            if len(s.targets) != 1:
                self.fail("G2001", "one assignment per line (a = b = 0 is not translated)", s)
            target = s.targets[0]
            if isinstance(target, ast.Tuple):
                self.tuple_assign(out, target, s.value, line, ind)
            else:
                code, t = self.expr(s.value)
                out.add(self.assign(target, code, t) + ";", line, ind)
        elif isinstance(s, ast.AnnAssign):
            if s.value is None:
                return
            code, t = self.expr(s.value)
            out.add(self.assign(s.target, code, t) + ";", line, ind)
        elif isinstance(s, ast.AugAssign):
            current, ct = self.expr(s.target)
            code, t = self.expr(s.value)
            new_code, nt = self.binop(current, ct, code, t, s.op, s)
            out.add(self.assign(s.target, new_code, nt) + ";", line, ind)
        elif isinstance(s, ast.If):
            first = s
            cond, _ = self.condition(s.test)
            out.add("if (%s) {" % cond, line, ind)
            self.narrowed_block(out, s.body, ind + 1, self.none_checks(s.test, False))
            while len(s.orelse) == 1 and isinstance(s.orelse[0], ast.If):
                s = s.orelse[0]
                cond, _ = self.condition(s.test)
                out.add("} else if (%s) {" % cond, s.lineno, ind)
                self.narrowed_block(out, s.body, ind + 1, self.none_checks(s.test, False))
            if s.orelse:
                out.add("} else {", 0, ind)
                self.narrowed_block(out, s.orelse, ind + 1, self.none_checks(s.test, True))
            out.add("}", 0, ind)
            if not first.orelse and first.body and isinstance(first.body[-1], (ast.Return, ast.Continue, ast.Break)):
                self.narrowed |= self.none_checks(first.test, True)     # if x is None: return  -> x is not None below
        elif isinstance(s, ast.While):
            if s.orelse:
                self.fail("G2001", "while ... else is not translated", s)
            cond, _ = self.condition(s.test)
            out.add("while (%s) {" % cond, line, ind)
            self.block(out, s.body, ind + 1)
            out.add("}", 0, ind)
        elif isinstance(s, ast.For):
            self.for_loop(out, s, ind)
        elif isinstance(s, ast.Return):
            if s.value is None:
                if self.ret != "void":
                    self.fail("G2011", "this function returns %s: return a value" % self.ret, s)
                out.add("return;", line, ind)
            else:
                if self.ret == "void":
                    self.fail("G2011", "a value is returned, but the function has no return type",
                              s, fix="def name(...) -> float:")
                code, t = self.expr(s.value)
                out.add("return %s;" % self.convert(code, t, self.ret, s), line, ind)
        elif isinstance(s, ast.Break):
            out.add("break;", line, ind)
        elif isinstance(s, ast.Continue):
            out.add("continue;", line, ind)
        elif isinstance(s, ast.Pass):
            pass
        elif isinstance(s, ast.Assert):
            cond, _ = self.condition(s.test)
            out.add('if (!(%s)) throw new Py.PyError("AssertionError: line %d");' % (cond, line), line, ind)
        else:
            what = type(s).__name__.lower()
            self.fail("G2001", "'%s' is not translated" % what, s,
                      cause="Scripts are a small typed Python: if, while, for, assignments, calls, return.")

    def narrowed_block(self, out, body, ind, names):
        before = set(self.narrowed)
        self.narrowed |= names
        self.block(out, body, ind)
        self.narrowed = before

    def none_checks(self, test, when_false):
        """The locals a condition proves are not None: when it is true (x is not None and ...),
        or when it is false (x is None or ...)."""
        def checked(n, op):
            if (isinstance(n, ast.Compare) and len(n.ops) == 1 and isinstance(n.ops[0], op)
                    and isinstance(n.left, ast.Name) and n.left.id in self.locals
                    and isinstance(n.comparators[0], ast.Constant) and n.comparators[0].value is None):
                return {n.left.id}
            return set()
        if not when_false:
            if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
                return set().union(*[checked(v, ast.IsNot) for v in test.values])
            return checked(test, ast.IsNot)
        if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or):
            return set().union(*[checked(v, ast.Is) for v in test.values])
        return checked(test, ast.Is)

    def tuple_assign(self, out, target, value, line, ind):
        if not isinstance(value, ast.Tuple) or len(value.elts) != len(target.elts):
            self.fail("G2001", "a, b = x, y needs as many values as names", target)
        temps = []
        for v in value.elts:
            code, t = self.expr(v)
            self.temps += 1
            name = "_t%d" % self.temps
            out.add("%s %s = %s;" % (java_type(t), name, code), line, ind)
            temps.append((name, t))
        for tg, (name, t) in zip(target.elts, temps):
            out.add(self.assign(tg, name, t) + ";", line, ind)

    def for_loop(self, out, s, ind):
        if s.orelse:
            self.fail("G2001", "for ... else is not translated", s)
        if not isinstance(s.target, ast.Name):
            self.fail("G2001", "for takes one name (for x in ...)", s)
        v = self.var(s.target.id)
        it = s.iter
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == "range":
            args = [self.expr(a) for a in it.args]
            if not 1 <= len(args) <= 3 or any(t != "int" for _, t in args):
                self.fail("G2009", "range takes 1 to 3 whole numbers", it)
            start, stop = ("0", args[0][0]) if len(args) == 1 else (args[0][0], args[1][0])
            step = args[2][0] if len(args) == 3 else "1"
            if len(args) == 3:
                lit = it.args[2]
                neg = isinstance(lit, ast.UnaryOp) and isinstance(lit.op, ast.USub)
                if not (isinstance(lit, ast.Constant) or neg):
                    self.fail("G2009", "range: the step is a number written out (its sign decides the loop)", it)
            else:
                neg = False
            self.temps += 1
            end = "_end%d" % self.temps
            out.add("{ int %s = %s;" % (end, stop), s.lineno, ind)       # the stop is evaluated once, as in Python
            out.add("for (%s = %s; %s %s %s; %s += %s) {" % (v, start, v, ">" if neg else "<", end, v, step),
                    s.lineno, ind)
            self.block(out, s.body, ind + 1)
            out.add("} }", 0, ind)
        else:
            code, t = self.expr(it)
            if base(t).startswith("dict["):
                code, t = "%s.keySet()" % code, "list[str]"
            elif base(t).startswith("table["):
                code, t = "%s.all()" % code, "list[%s]" % base(t)[6:-1]
            if not base(t).startswith("list["):
                self.fail("G2009", "for goes over range(...), a list or a dict", it,
                          fix="for e in scene.with_tag(\"rock\"):")
            et = base(t)[5:-1]
            self.temps += 1
            item = "_i%d" % self.temps
            out.add("for (%s %s : new ArrayList<%s>(%s)) {" % (java_type(et, True), item, java_type(et, True), code),
                    s.lineno, ind)
            out.add("%s = %s;" % (v, item), s.lineno, ind + 1)
            self.block(out, s.body, ind + 1)
            out.add("}", 0, ind)

    def assign(self, target, code, t):
        if isinstance(target, ast.Name):
            name = target.id
            if name in self.constants or name in MODULE_OBJECTS:
                self.fail("G2003", "%s cannot be assigned here" % name, target)
            if self.scope.get(name, ("",))[0] == "state":
                self.fail("G2003", "%s is module state: change what it holds (%s.x = ...), it is not replaced"
                          % (name, name), target)
            want = self.locals.get(name)
            if want is None:
                self.fail("G2004", "%s is not declared" % name, target)
            if t.endswith("?") or t == "None":
                self.narrowed.discard(name)
            return "%s = %s" % (self.var(name), self.convert(code, t, want, target))
        if isinstance(target, ast.Attribute):
            obj_code, obj_t, settable, want = self.attribute(target, store=True)
            if not settable:
                self.fail("G2003", "%s cannot be assigned" % target.attr, target)
            if target.attr == "scale" and settable.endswith(".transform.scaleX"):    # e.scale, self.scale: both sides
                owner = settable[:-len("scaleX")]
                return "%sscaleX = %sscaleY = %s" % (owner, owner, self.convert(code, t, want, target))
            return "%s = %s" % (settable, self.convert(code, t, want, target))
        if isinstance(target, ast.Subscript):
            obj, ot = self.expr(target.value)
            key, kt = self.expr(subscript_slice(target))
            b = base(ot)
            if b.startswith("list["):
                if kt != "int":
                    self.fail("G2003", "a list index is an int", target)
                return "Py.set(%s, %s, %s)" % (obj, key, self.convert(code, t, b[5:-1], target))
            if b.startswith("dict["):
                if kt != "str":
                    self.fail("G2003", "dict keys are str", target)
                return "%s.put(%s, %s)" % (obj, key, self.convert(code, t, b[5:-1], target))
        self.fail("G2001", "this cannot be assigned", target)

    def convert(self, code, t, want, node):
        """code of type t, used where want is expected."""
        if t == want or base(t) == want and want.endswith("?") or t == base(want) and want.endswith("?"):
            return code
        if t == "None" and want.endswith("?"):
            return "null"
        if base(t) == "int" and base(want) == "float":
            return "((double) %s)" % code
        if t.startswith("list[") and want.startswith("list[") and t == "list[?]":
            return code
        if t == "dict[?]" and want.startswith("dict["):
            return code
        if base(want) == base(t) and t.endswith("?") and not want.endswith("?"):
            return "Py.notNone(%s, \"value\")" % code
        if want == "Image":
            self.fail("G2003", "expected an image declared in the game, got %s" % self.shown(t), node,
                      fix='Declare it at the top: pic = assets.image("assets/pic.png"), and use pic')
        self.fail("G2003", "expected %s, got %s" % (self.shown(want), self.shown(t)), node,
                  fix="int(x) / float(x) / str(x) convert numbers and text")

    @staticmethod
    def shown(t):
        return base(t) + (" or None" if t.endswith("?") else "")

    # ── expressions: (java code, type) ───────────────────────────────────

    def condition(self, node):
        code, t = self.expr(node)
        if t != "bool":
            hint = "x != 0" if base(t) in NUM else "x is not None" if t.endswith("?") else "len(x) > 0"
            self.fail("G2008", "a condition has to be True/False, not %s" % self.shown(t), node,
                      cause="Python's 'truthiness' is not guessed in translated code.", fix="Write it out: %s" % hint)
        return code, t

    def expr(self, n):
        if isinstance(n, ast.Constant):
            v = n.value
            if isinstance(v, bool):
                return ("true" if v else "false"), "bool"
            if isinstance(v, int):
                if not -2 ** 31 <= v < 2 ** 31:
                    self.fail("G2003", "this whole number does not fit an int", n)
                return str(v), "int"
            if isinstance(v, float):
                return repr(v) if repr(v) not in ("inf", "nan") else "Double.POSITIVE_INFINITY", "float"
            if isinstance(v, str):
                return jstr(v), "str"
            if v is None:
                return "null", "None"
            self.fail("G2002", "this value is not translated", n)
        if isinstance(n, ast.Name):
            return self.name(n)
        if isinstance(n, ast.Attribute):
            code, t, _, _ = self.attribute(n)
            return code, t
        if isinstance(n, ast.BinOp):
            a, at = self.expr(n.left)
            b, bt = self.expr(n.right)
            return self.binop(a, at, b, bt, n.op, n)
        if isinstance(n, ast.UnaryOp):
            code, t = self.expr(n.operand)
            if isinstance(n.op, ast.Not):
                if t != "bool":
                    self.fail("G2008", "not works on True/False", n)
                return "(!%s)" % code, "bool"
            if isinstance(n.op, (ast.USub, ast.UAdd)) and base(t) in NUM:
                return ("(-%s)" % code if isinstance(n.op, ast.USub) else code), base(t)
            self.fail("G2002", "this operator is not translated", n)
        if isinstance(n, ast.BoolOp):
            parts = []
            before = set(self.narrowed)
            for i, v in enumerate(n.values):
                if i:                  # x is None or x.hp > 0 / x is not None and x.hp > 0: x is set on the right
                    self.narrowed |= self.none_checks(n.values[i - 1], isinstance(n.op, ast.Or))
                code, t = self.expr(v)
                if t != "bool":
                    self.fail("G2008", "and/or work on True/False here, not %s" % self.shown(t), v,
                              fix="Write the comparison out (x != 0, y is not None).")
                parts.append(code)
            self.narrowed = before
            op = " && " if isinstance(n.op, ast.And) else " || "
            return "(%s)" % op.join(parts), "bool"
        if isinstance(n, ast.Compare):
            return self.compare(n)
        if isinstance(n, ast.IfExp):
            cond, _ = self.condition(n.test)
            a, at = self.expr(n.body)
            b, bt = self.expr(n.orelse)
            t = self.unify(at, bt, n)
            return "(%s ? %s : %s)" % (cond, self.convert(a, at, t, n), self.convert(b, bt, t, n)), t
        if isinstance(n, ast.Call):
            return self.call(n)
        if isinstance(n, ast.JoinedStr):
            parts = []
            for v in n.values:
                if isinstance(v, ast.Constant):
                    parts.append(jstr(v.value))
                else:
                    code, t = self.expr(v.value)
                    spec = ""
                    if v.format_spec is not None:
                        if not all(isinstance(x, ast.Constant) for x in v.format_spec.values):
                            self.fail("G2002", "a format spec is written out", v)
                        spec = "".join(x.value for x in v.format_spec.values)
                    if spec:
                        if base(t) not in ("int", "float", "str"):
                            self.fail("G2002", "a format spec works on numbers and text", v)
                        parts.append("Py.format(%s, %s)" % (code, jstr(spec)))
                    else:
                        parts.append("Py.str(%s)" % code)
            return "(%s)" % " + ".join(parts or ['""']), "str"
        if isinstance(n, ast.List):
            if not n.elts:
                return "new ArrayList<>()", "list[?]"
            items = [self.expr(e) for e in n.elts]
            t = items[0][1]
            for _, it in items[1:]:
                t = self.unify(t, it, n)
            return "Py.list(%s)" % ", ".join(self.convert(c, it, t, n) for c, it in items), "list[%s]" % t
        if isinstance(n, ast.Dict):
            if not n.keys:
                return "new LinkedHashMap<>()", "dict[?]"
            self.fail("G2002", "dict literals are only for game.exit({...}); start with {} and set keys", n)
        if isinstance(n, ast.Subscript):
            obj, ot = self.expr(n.value)
            key, kt = self.expr(subscript_slice(n))
            b = base(ot)
            if b.startswith("list["):
                if kt != "int":
                    self.fail("G2003", "a list index is an int", n)
                return "Py.get(%s, %s)" % (obj, key), b[5:-1]
            if b.startswith("dict["):
                return "Py.get(%s, %s)" % (obj, key), b[5:-1]
            if b == "str":
                return "String.valueOf(%s.charAt(%s))" % (obj, key), "str"
            self.fail("G2002", "[...] works on lists and dicts", n)
        what = {"ListComp": "a list comprehension", "Lambda": "a lambda", "GeneratorExp": "a generator",
                "DictComp": "a dict comprehension", "Starred": "*unpacking", "Tuple": "a tuple",
                "Set": "a set", "Await": "await"}.get(type(n).__name__, type(n).__name__)
        self.fail("G2002", "%s is not translated" % what, n,
                  fix="Write it with a for loop and a list (append).")

    def unify(self, a, b, node):
        if a == b:
            return a
        if {base(a), base(b)} == {"int", "float"}:
            return "float"
        if b == "None":
            return optional(a)
        if a == "None":
            return optional(b)
        if base(a) == base(b):
            return optional(base(a))
        self.fail("G2003", "the two values have different types: %s and %s" % (self.shown(a), self.shown(b)), node)

    def name(self, n):
        i = n.id
        if i in self.locals:
            t = self.locals[i]
            return self.var(i), (base(t) if i in self.narrowed else t)
        if i in ("True", "False"):
            return ("true" if i == "True" else "false"), "bool"
        if i == "None":
            return "null", "None"
        if i in self.constants:
            v = self.constants[i]
            return self.expr(ast.copy_location(ast.Constant(value=v), n))
        sym = self.scope.get(i)
        if sym is not None and sym[0] == "state":
            return "%s.%s" % (sym[1], jname(i)), self.state_type(sym[2])
        if sym is not None and sym[0] == "declared" and getattr(sym[2], "kind", "") in ("sound", "music"):
            return jstr(sym[2].path), "Sound"            # assets.sound(...) declared in a module
        if sym is not None and sym[0] == "declared" and getattr(sym[2], "kind", "") == "image":
            return jstr(sym[2].path), "Image"            # assets.image(...): what a Canvas stamps
        if sym is not None and sym[0] == "table":
            return "%s.%s" % (sym[1], jname(i)), "table[%s]" % sym[2].record
        if i == "self":
            if not self.is_method:
                self.fail("G2004", "self is only in methods", n)
            return "this", "self"
        if i in self.mod.aliases:
            self.fail("G2002", "%s is a module: use what it has (%s.name)" % (i, i), n)
        if i == self.game_var:
            i = "game"
        elif i == "game" and self.game_var != "game":
            self.fail("G2004", "the game is called %s in this file" % self.game_var, n)
        if i in MODULE_OBJECTS:
            if not self.in_script and i not in ("math", "random"):
                self.fail("G2004", "%s is only for Script methods (a plain function gets values, not the game)" % i, n)
            return i, i
        hits = difflib.get_close_matches(i, list(self.locals) + list(self.constants), n=2)
        self.fail("G2004", "'%s' is not known here" % i, n,
                  fix=["Did you mean %s?" % " or ".join(hits)] if hits else
                  ["A local is assigned before use; fields are self.name; constants are written at the top."])

    def attribute(self, n, store=False):
        """(code, type, assignable code or None, type expected on assignment)"""
        module = self.module_of(n.value)
        if module is not None:
            return self.module_value(module, n)
        obj, ot = self.expr(n.value)
        name = n.attr
        if ot == "self":
            c = self.cls
            if name in c.fields:
                t = c.fields[name][0]
                return "this.%s" % jname(name), t, "this.%s" % jname(name), t
            if isinstance(c, RecordClass):
                if store:
                    self.fail("G2007", "self.%s is not a field of %s" % (name, c.name), n,
                              fix="Declare it in the class: %s: float = 0.0" % name)
                self.fail("G2005", "%s has no %r" % (c.name, name), n, fix=self.close(name, c.fields))
            props = PROPS["Entity"]
            if name in props:
                tpl, t, mode = props[name]
                code = tpl.format(o="entity()")
                return code, t, code if mode == "rw" else None, t
            if name == "entity":
                return "entity()", "Entity", None, "Entity"
            if store:
                self.fail("G2007", "self.%s is not a field of %s" % (name, c.name), n,
                          fix="Declare it in the class: %s: float = 0.0" % name)
            self.fail("G2005", "self has no %r" % name, n, fix=self.close(name, list(c.fields) + list(props)))
        b = base(ot)
        if ot.endswith("?") and not self.lenient:
            self.fail("G2010", "this may be None: check it first (if x is not None:)", n)
        if b in self.records:
            r = self.records[b]
            if name in r.fields:
                t = r.fields[name][0]
                code = "%s.%s" % (obj, jname(name))
                return code, t, code, t
            self.fail("G2005", "%s has no field %r" % (b, name), n, fix=self.close(name, r.fields))
        props = PROPS.get(b, {})
        if name in props:
            tpl, t, mode = props[name]
            code = tpl.format(o=obj)
            return code, t, code if mode == "rw" else None, t
        self.fail("G2005", "%s has no %r" % (b, name), n, fix=self.close(name, props))

    def module_of(self, node):
        """The module a name stands for (import game.rules.damage as damage), or None."""
        if isinstance(node, ast.Name) and node.id in self.mod.aliases and node.id not in self.locals:
            return self.mod.aliases[node.id]
        return None

    def module_value(self, module, n):
        hit = module.lookup(n.attr)
        if hit is None:
            names = [x.name for x in module.functions + module.records] + list(module.constants) + list(module.state)
            self.fail("G2005", "%s has no %r" % (module.source, n.attr), n, fix=self.close(n.attr, names))
        kind, owner, obj = hit
        if kind == "constant":
            code, t = self.expr(ast.copy_location(ast.Constant(value=obj), n))
            return code, t, None, t
        if kind == "state":
            t = self.state_type(obj)
            return "%s.%s" % (owner, jname(n.attr)), t, None, t
        if kind == "table":
            t = "table[%s]" % obj.record
            return "%s.%s" % (owner, jname(n.attr)), t, None, t
        self.fail("G2002", "%s.%s is a %s: call it" % (n.value.id, n.attr, "class" if kind != "function" else kind), n)

    def close(self, name, options):
        hits = difflib.get_close_matches(name, list(options), n=2)
        return ["Did you mean %s?" % " or ".join(hits)] if hits else []

    def binop(self, a, at, b, bt, op, node):
        at, bt = base(at) if at in ("int", "float") else at, base(bt) if bt in ("int", "float") else bt
        if isinstance(op, ast.Add) and at == "str" and bt == "str":
            return "(%s + %s)" % (a, b), "str"
        if isinstance(op, ast.Mult) and {at, bt} == {"str", "int"}:
            s, k = (a, b) if at == "str" else (b, a)
            return "Py.repeat(%s, %s)" % (s, k), "str"
        if at not in NUM or bt not in NUM:
            self.fail("G2003", "%s between %s and %s" % (type(op).__name__, self.shown(at), self.shown(bt)), node,
                      fix="str(x) turns a number into text; int(s) / float(s) the other way")
        t = "float" if "float" in (at, bt) else "int"
        if isinstance(op, ast.Add):
            return "(%s + %s)" % (a, b), t
        if isinstance(op, ast.Sub):
            return "(%s - %s)" % (a, b), t
        if isinstance(op, ast.Mult):
            return "(%s * %s)" % (a, b), t
        if isinstance(op, ast.Div):
            return "Py.div(%s, %s)" % (a, b), "float"
        if isinstance(op, ast.FloorDiv):
            return ("Py.floorDiv(%s, %s)" % (a, b) if t == "int" else
                    "Py.floorDiv((double) %s, (double) %s)" % (a, b)), t
        if isinstance(op, ast.Mod):
            return ("Py.mod(%s, %s)" % (a, b) if t == "int" else "Py.mod((double) %s, (double) %s)" % (a, b)), t
        if isinstance(op, ast.Pow):
            if t == "int":
                return "Py.ipow(%s, %s)" % (a, b), "int"
            return "StrictMath.pow(%s, %s)" % (a, b), "float"
        self.fail("G2002", "this operator is not translated", node)

    def binop_type(self, at, bt, op):
        if at is None or bt is None:
            return None
        if base(at) == "str":
            return "str"
        if isinstance(op, ast.Div):
            return "float"
        return "float" if "float" in (base(at), base(bt)) else "int"

    def compare(self, n):
        parts = []
        left, lt = self.expr(n.left)
        for op, right_node in zip(n.ops, n.comparators):
            right, rt = self.expr(right_node)
            if isinstance(op, (ast.Is, ast.IsNot)):
                sym = "==" if isinstance(op, ast.Is) else "!="
                if rt == "None":
                    parts.append("(%s %s null)" % (left, sym))
                elif base(lt) == base(rt) and base(lt) not in ("int", "float", "bool", "str"):
                    parts.append("(%s %s %s)" % (left, sym, right))              # the same object
                else:
                    self.fail("G2002", "'is' is for None and for objects (x is None, a is b); "
                                       "numbers and text are compared with ==", n)
            elif isinstance(op, (ast.In, ast.NotIn)):
                b = base(rt)
                if b.startswith("list["):
                    code = "%s.contains(%s)" % (right, left)
                elif b.startswith("dict["):
                    code = "%s.containsKey(%s)" % (right, left)
                elif b.startswith("table["):
                    code = "%s.has(%s)" % (right, left)
                elif b == "str" and base(lt) == "str":
                    code = "%s.contains(%s)" % (right, left)
                else:
                    self.fail("G2002", "'in' works on lists, dicts and text", n)
                parts.append(("!" if isinstance(op, ast.NotIn) else "") + code)
            else:
                sym = CMP[type(op)]
                if base(lt) in NUM and base(rt) in NUM:
                    parts.append("(%s %s %s)" % (left, sym, right))
                elif base(lt) == "str" and base(rt) == "str" or base(lt) == "bool" == base(rt):
                    if sym == "==":
                        parts.append("Objects.equals(%s, %s)" % (left, right))
                    elif sym == "!=":
                        parts.append("!Objects.equals(%s, %s)" % (left, right))
                    elif base(lt) == "str":
                        parts.append("(%s.compareTo(%s) %s 0)" % (left, right, sym))
                    else:
                        self.fail("G2002", "True/False are compared with == or !=", n)
                elif (base(lt) == base(rt) and (base(lt) in self.records or base(lt).startswith(("list[", "dict[")))
                      and sym in ("==", "!=")):
                    parts.append(("" if sym == "==" else "!") + "Objects.equals(%s, %s)" % (left, right))
                elif rt == "None" or lt == "None":
                    self.fail("G2002", "compare with None using 'is None' / 'is not None'", n)
                elif base(lt) == base(rt) and sym in ("==", "!="):
                    parts.append("(%s %s %s)" % (left, sym, right))
                else:
                    self.fail("G2003", "%s and %s cannot be compared" % (self.shown(lt), self.shown(rt)), n)
            left, lt = right, rt
        return "(%s)" % " && ".join(parts), "bool"

    # ── calls ────────────────────────────────────────────────────────────

    def call(self, n):
        f = n.func
        if n.keywords and not self.takes_keywords(f):
            self.fail("G2009", "keyword arguments are not translated in calls (write them in order)", n,
                      fix="Keywords work in @dataclass constructors and replace(x, field=value).")
        if isinstance(f, ast.Name):
            return self.builtin(f.id, n)
        if isinstance(f, ast.Attribute):
            recv = f.value
            module = self.module_of(recv)
            if module is not None:
                return self.module_call(module, f.attr, n)
            if isinstance(recv, ast.Name) and recv.id == "self":
                if f.attr in self.sigs:
                    names, types, ret = self.sigs[f.attr]
                    if f.attr in LIFECYCLE:
                        self.fail("G2009", "%s is called by the engine, not by the script" % f.attr, n)
                    return "this.%s(%s)" % (jname(f.attr), self.args(n, types)), ret
                if f.attr == "destroy":
                    self.no_args(n)
                    return "entity().destroy()", "void"
                if f.attr == "has_tag":
                    return "entity().hasTag(%s)" % self.args(n, ["str"]), "bool"
                self.fail("G2005", "self has no method %r" % f.attr, n, fix=self.close(f.attr, self.sigs))
            if isinstance(recv, ast.Name) and recv.id == "math" and "math" not in self.locals:
                return self.math(f.attr, n)
            if isinstance(recv, ast.Name) and recv.id == self.game_var and f.attr == "exit":
                return self.exit_call(n), "void"
            if isinstance(recv, ast.Name) and recv.id == "random" and f.attr == "choice":
                code, t = self.expr(n.args[0]) if len(n.args) == 1 else self.fail("G2009", "choice(list)", n)
                if not base(t).startswith("list["):
                    self.fail("G2003", "random.choice takes a list", n)
                g = "game()" if self.in_script else "Game.current()"
                return "Py.get(%s, %s.random.nextInt(%s.size()))" % (code, g, code), base(t)[5:-1]
            obj, ot = self.expr(recv)
            b = base(ot) if ot not in MODULE_OBJECTS else ot
            if ot.endswith("?") and not self.lenient:
                self.fail("G2010", "this may be None: check it first (if x is not None:)", n)
            if b in self.records:
                return self.record_method(obj, self.records[b], f.attr, n)
            if b.startswith("list["):
                return self.list_method(obj, b, f.attr, n)
            if b.startswith("dict["):
                return self.dict_method(obj, b, f.attr, n)
            if b.startswith("table["):
                return self.table_method(obj, b, f.attr, n)
            if b == "str":
                return self.str_method(obj, f.attr, n)
            key = (b, f.attr)
            if key not in METHODS:
                options = [m for (r, m) in METHODS if r == b]
                self.fail("G2005", "%s has no method %r" % (b, f.attr), n, fix=self.close(f.attr, options))
            want, ret, tpl = METHODS[key]
            return self.template(tpl, obj, want, n), ret
        self.fail("G2002", "this call is not translated", n)

    def takes_keywords(self, f):
        if isinstance(f, ast.Attribute):
            if f.attr == "exit":
                return True
            module = self.module_of(f.value)
            return module is not None and (module.lookup(f.attr) or ("",))[0] == "record"
        if isinstance(f, ast.Name):
            hit = self.scope.get(f.id)
            return (hit is not None and hit[0] == "record") or self.mod.dataclass_names.get(f.id) == "replace"
        return False

    def module_call(self, module, name, n):
        hit = module.lookup(name)
        if hit is None or hit[0] not in ("function", "record"):
            names = [x.name for x in module.functions + module.records]
            self.fail("G2005", "%s has no function %r" % (module.source, name), n, fix=self.close(name, names))
        kind, owner, obj = hit
        if kind == "record":
            return self.construct(obj, n)
        return self.function_call(owner, obj, n)

    def function_call(self, owner, f, n):
        names, types, ret = self.signature(f.node, False)
        return "%s.%s(%s)" % (owner, jname(f.name), self.args(n, types)), ret

    def construct(self, r, n):
        """Monster("x", 3) / Monster(species="x", level=3): every field in order, defaults filled in."""
        names = list(r.fields)
        if len(n.args) > len(names):
            self.fail("G2009", "%s takes %d field(s)" % (r.name, len(names)), n)
        given = dict(zip(names, n.args))
        for k in n.keywords:
            if k.arg is None or k.arg not in r.fields:
                self.fail("G2009", "%s has no field %r" % (r.name, k.arg), k,
                          fix=self.close(k.arg or "", names) or "Fields: %s" % ", ".join(names))
            if k.arg in given:
                self.fail("G2009", "%s: %s is given twice" % (r.name, k.arg), k)
            given[k.arg] = k.value
        codes = []
        for name in names:
            t, default, _ = r.fields[name]
            if name in given:
                code, at = self.expr(given[name])
                codes.append(self.convert(code, at, t, given[name]))
            elif default is not None:
                codes.append(self.field_default(r, name, t, default, n))
            else:
                self.fail("G2009", "%s needs %s" % (r.name, name), n, fix="%s(%s=...)" % (r.name, name))
        return "new %s(%s)" % (r.name, ", ".join(codes)), r.name

    def field_default(self, r, name, t, default, n):
        """A field's default, made again for each new object (as Python does with default_factory)."""
        if isinstance(default, ast.Call) and isinstance(default.func, ast.Name) and default.func.id == "field":
            kw = {k.arg: k.value for k in default.keywords}
            if "default" in kw:
                default = kw["default"]
            elif "default_factory" in kw:
                factory = kw["default_factory"]
                fid = getattr(factory, "id", None)
                if fid in ("list", "dict"):
                    return "new %s()" % java_type(t)
                if fid in self.records:
                    return self.construct(self.records[fid], ast.copy_location(
                        ast.Call(func=factory, args=[], keywords=[]), n))[0]
                self.fail("G2009", "%s.%s: default_factory is list, dict or a @dataclass" % (r.name, name), factory)
        code, at = self.expr(default)
        return self.convert(code, at, t, n)

    def record_method(self, obj, r, name, n):
        for m in r.methods:
            if m.name == name:
                saved = self.in_script
                self.in_script = False
                names, types, ret = self.signature(m, True)
                self.in_script = saved
                return "%s.%s(%s)" % (obj, jname(name), self.args(n, types)), ret
        self.fail("G2005", "%s has no method %r" % (r.name, name), n,
                  fix=self.close(name, [m.name for m in r.methods]))

    def table_method(self, obj, t, name, n):
        rt = t[6:-1]
        if name == "get":
            return "%s.get(%s)" % (obj, self.args(n, ["str"])), rt
        if name == "has":
            return "%s.has(%s)" % (obj, self.args(n, ["str"])), "bool"
        if name == "all":
            self.no_args(n)
            return "%s.all()" % obj, "list[%s]" % rt
        self.fail("G2005", "a table has get(id), has(id) and all() (and len(t), for row in t)", n)

    def dict_method(self, obj, t, name, n):
        vt = t[5:-1]
        if name == "get":
            if len(n.args) == 1:
                return "%s.get(%s)" % (obj, self.args(n, ["str"])), optional(vt)
            return "Py.getOr(%s, %s)" % (obj, self.args(n, ["str", vt])), vt
        if name == "keys":
            self.no_args(n)
            return "new ArrayList<String>(%s.keySet())" % obj, "list[str]"
        if name == "values":
            self.no_args(n)
            return "new ArrayList<%s>(%s.values())" % (java_type(vt, True), obj), "list[%s]" % vt
        if name == "pop":
            return "Py.pop(%s, %s)" % (obj, self.args(n, ["str"])), vt
        if name == "clear":
            self.no_args(n)
            return "%s.clear()" % obj, "void"
        self.fail("G2005", "dicts here have get, keys, values, pop, clear (and for k in d)", n)

    def template(self, tpl, obj, want, n):
        required = [w for w in want if not w.endswith("?")]
        if not len(required) <= len(n.args) <= len(want):
            self.fail("G2009", "takes %d argument(s)" % len(want), n)
        codes = []
        for i, w in enumerate(want):
            if i < len(n.args):
                code, t = self.expr(n.args[i])
                codes.append(self.convert(code, t, base(w), n.args[i]))
            else:
                codes.append(None)
        out = tpl.replace("{o}", obj)
        if not self.in_script:
            out = out.replace("game()", "Game.current()")
        for i, c in enumerate(codes):
            out = re.sub(r"\{%d\|([^}]*)\}" % i, lambda m: c if c is not None else m.group(1), out)
            out = out.replace("{%d}" % i, c or "")
        return out

    def args(self, n, types):
        if len(n.args) != len(types):
            self.fail("G2009", "takes %d argument(s), got %d" % (len(types), len(n.args)), n)
        out = []
        for a, t in zip(n.args, types):
            code, at = self.expr(a)
            out.append(self.convert(code, at, t, a))
        return ", ".join(out)

    def no_args(self, n):
        if n.args:
            self.fail("G2009", "takes no arguments", n)

    def exit_call(self, n):
        if n.keywords or len(n.args) > 1:
            self.fail("G2009", 'game.exit({"key": value, ...})', n)
        if not n.args:
            return "game().exit(null)"
        d = n.args[0]
        if not isinstance(d, ast.Dict):
            self.fail("G2009", "game.exit takes a dict written out: {\"score\": self.score}", n)
        kv = []
        for k, v in zip(d.keys, d.values):
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                self.fail("G2009", "game.exit: keys are texts written out", d)
            code, t = self.expr(v)
            if base(t) not in ("int", "float", "bool", "str"):
                self.fail("G2003", "game.exit: values are numbers, texts or True/False", v)
            kv += [jstr(k.value), code]
        return "game().exit(Py.map(%s))" % ", ".join(kv)

    def replace(self, n):
        """dataclasses.replace(x, hp=10): a copy with some fields changed."""
        if len(n.args) != 1:
            self.fail("G2009", "replace(obj, field=value, ...)", n)
        code, t = self.expr(n.args[0])
        if base(t) not in self.records or t.endswith("?"):
            self.fail("G2003", "replace takes a @dataclass object", n)
        r = self.records[t]
        out = "%s.copy()" % code
        for k in n.keywords:
            if k.arg not in r.fields:
                self.fail("G2009", "%s has no field %r" % (r.name, k.arg), k, fix=self.close(k.arg or "", r.fields))
            v, vt = self.expr(k.value)
            out += ".set_%s(%s)" % (k.arg, self.convert(v, vt, r.fields[k.arg][0], k.value))
        return out, t

    def math(self, name, n):
        if name in MATH1:
            return "%s(%s)" % (MATH1[name], self.args(n, ["float"])), "float"
        if name in MATH2:
            return "%s(%s)" % (MATH2[name], self.args(n, ["float", "float"])), "float"
        if name in ("floor", "ceil"):
            return "((int) Math.%s(%s))" % (name, self.args(n, ["float"])), "int"
        if name in PROPS["math"]:
            self.fail("G2002", "math.%s is a value, not a function" % name, n)
        self.fail("G2005", "math.%s is not translated" % name, n,
                  fix=self.close(name, list(MATH1) + list(MATH2) + ["floor", "ceil"]))

    def list_method(self, obj, t, name, n):
        et = t[5:-1]
        if name == "append":
            return "%s.add(%s)" % (obj, self.args(n, [et])), "void"
        if name == "pop":
            if not n.args:
                return "Py.pop(%s)" % obj, et
            return "Py.pop(%s, %s)" % (obj, self.args(n, ["int"])), et
        if name == "clear":
            self.no_args(n)
            return "%s.clear()" % obj, "void"
        if name == "insert":
            return "%s.add(%s)" % (obj, self.args(n, ["int", et])), "void"
        if name == "remove":
            return "%s.remove((Object) %s)" % (obj, self.args(n, [et])), "void"
        self.fail("G2005", "lists here have append, pop, insert, remove, clear", n)

    def str_method(self, obj, name, n):
        simple = {"upper": "toUpperCase()", "lower": "toLowerCase()", "strip": "trim()"}
        if name in simple:
            self.no_args(n)
            return "%s.%s" % (obj, simple[name]), "str"
        if name in ("startswith", "endswith"):
            return "%s.%s(%s)" % (obj, "startsWith" if name == "startswith" else "endsWith", self.args(n, ["str"])), "bool"
        if name == "replace":
            return "%s.replace(%s)" % (obj, self.args(n, ["str", "str"])), "str"
        self.fail("G2005", "text here has upper, lower, strip, startswith, endswith, replace", n)

    def builtin(self, name, n):
        args = n.args
        if name in self.functions:
            return self.function_call(self.scope[name][1], self.functions[name], n)
        hit = self.scope.get(name)
        if hit is not None and hit[0] == "record":
            return self.construct(hit[2], n)
        if self.mod.dataclass_names.get(name) == "replace":
            return self.replace(n)
        if name in self.classes:
            self.fail("G2002", "scripts are put on entities in the declarations, not made in code", n)
        if name == "to_json":
            if len(args) != 1:
                self.fail("G2009", "to_json(value)", n)
            code, t = self.expr(args[0])
            return "Data.json(%s)" % code, "str"
        if name == "from_json":
            if len(args) != 2 or not isinstance(args[1], ast.Name) or args[1].id not in self.records:
                self.fail("G2009", "from_json(text, Type): Type is a @dataclass", n,
                          fix="state = from_json(text, GameState)")
            code = self.args(ast.copy_location(ast.Call(func=n.func, args=[args[0]], keywords=[]), n), ["str"])
            return "%s.fromJson(Data.parse(%s))" % (args[1].id, code), args[1].id
        if name == "abs":
            code, t = self.expr(args[0])
            if base(t) not in NUM:
                self.fail("G2003", "abs takes a number", n)
            return "Math.abs(%s)" % code, base(t)
        if name in ("min", "max"):
            if len(args) < 2:
                self.fail("G2009", "%s(a, b, ...) takes two or more numbers" % name, n)
            items = [self.expr(a) for a in args]
            if any(base(t) not in NUM for _, t in items):
                self.fail("G2003", "%s takes numbers" % name, n)
            t = "float" if any(base(t) == "float" for _, t in items) else "int"
            code = self.convert(items[0][0], items[0][1], t, n)
            for c, it in items[1:]:
                code = "Math.%s(%s, %s)" % (name, code, self.convert(c, it, t, n))
            return code, t
        if name == "round":
            if not 1 <= len(args) <= 2:
                self.fail("G2009", "round(x) or round(x, digits)", n)
            code, t = self.expr(args[0])
            if base(t) not in NUM:
                self.fail("G2003", "round takes a number", n)
            if len(args) == 1:
                return "Py.round((double) %s)" % code, "int"
            digits, dt = self.expr(args[1])
            if dt != "int":
                self.fail("G2003", "round: the digits are an int", n)
            return "Py.round((double) %s, %s)" % (code, digits), "float"
        if name == "int":
            code, t = self.expr(args[0])
            b = base(t)
            return ({"int": code, "float": "Py.toInt(%s)" % code, "str": "Py.toInt(%s)" % code,
                     "bool": "(%s ? 1 : 0)" % code}.get(b) or self.fail("G2003", "int() of %s" % b, n)), "int"
        if name == "float":
            code, t = self.expr(args[0])
            b = base(t)
            return ({"int": "((double) %s)" % code, "float": code, "str": "Py.toFloat(%s)" % code}.get(b)
                    or self.fail("G2003", "float() of %s" % b, n)), "float"
        if name == "str":
            code, t = self.expr(args[0])
            return "Py.str(%s)" % code, "str"
        if name == "len":
            code, t = self.expr(args[0])
            b = base(t)
            if b == "str":
                return "%s.length()" % code, "int"
            if b.startswith(("list[", "dict[", "table[")):
                return "%s.size()" % code, "int"
            self.fail("G2003", "len() of %s" % b, n)
        if name == "print":
            if not self.in_script:
                self.fail("G2004", "print is for Script methods", n)
            parts = ["Py.str(%s)" % self.expr(a)[0] for a in args]
            return "Py.print(game(), %s)" % (' + " " + '.join(parts) or '""'), "void"
        if name == "range":
            self.fail("G2002", "range is used in for loops (for i in range(n):)", n)
        self.fail("G2004", "'%s' is not a function scripts can call" % name, n,
                  fix=self.close(name, ["abs", "min", "max", "round", "int", "float", "str", "len", "print"]
                                 + list(self.functions)))
