"""Generates game_engine/docs/reference.md (the games' reference) from the sources of truth.

    python tools/game/gen_docs.py [--check]

Components and actions come from apkpy_lib/game/schema/components.json (the same
schema the build reads and the Java is checked against); what scripts can
use comes from the translator's own tables (apkpy_lib/game/compiler/scripts.py).
So the reference cannot say something the framework does not do. --check
fails if the file is out of date (used by the tests).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # ApkPy's repository
TOOLS = os.path.join(ROOT, "tools", "game")
SRC = ROOT
sys.path.insert(0, ROOT)
from apkpy_lib.game.compiler import scripts  # noqa: E402

PKG = os.path.join(ROOT, "apkpy_lib", "game")
OUT = os.path.join(ROOT, "game_engine", "docs", "reference.md")


def _default(f):
    if f.get("required"):
        return "required"
    d = f.get("default")
    if d is None:
        return "-"
    if isinstance(d, list):
        return "(%s)" % ", ".join(str(v) for v in d)
    return repr(d) if isinstance(d, str) else str(d).replace("True", "True").replace("False", "False")


def _cell(text):
    return text.replace("|", "\\|").replace("\n", " ")


def _call(spec):
    parts = []
    for a in spec["args"]:
        parts.append(a if not a.startswith("*") else "*" + a[1:])
    return "%s(%s)" % (spec["name"], ", ".join(parts))


def _fields(spec):
    out = ["| Parameter | Type | Default | |", "|---|---|---|---|"]
    for name, f in spec["fields"].items():
        kind = f["type"] + (" (%s)" % ", ".join(f["values"]) if f.get("values") else "")
        out.append("| `%s` | %s | %s | %s |" % (name, _cell(kind), _cell(_default(f)), _cell(f.get("doc", ""))))
    return out


# A default as the Java template writes it ({1|null}), as a game file would write it.
_PYTHON_DEFAULT = {"null": "None", "true": "True", "false": "False"}


def _signature(args, result, template=""):
    """(str, str = None, float = 0.0) -> void: each optional argument with the default its Java template gives."""
    import re
    defaults = {int(i): v for i, v in re.findall(r"\{(\d+)\|([^}]*)\}", template)}
    shown = []
    for i, a in enumerate(args):
        if a.endswith("?") and i in defaults:
            value = defaults[i]
            shown.append("%s = %s" % (a[:-1], _PYTHON_DEFAULT.get(value, value)))
        else:
            shown.append(a)
    return "(%s) -> %s" % (", ".join(shown), result)

# Every error of a game's build and of the engine: the code, the file and line, why, and how to fix it.
ERRORS = [
    ("G10xx", "Project and tools", "G1001 no `game/main.py`, G1003 outside a project, G1004 no `application_id`, "
     "G1006 JDK or Android SDK not found, G1007 the engine is missing, G1008 the project folder exists, "
     "G1010 a `before_build` step of `apkpy.toml` failed"),
    ("G11xx", "The app", "G1101 `writehere.py` does not call `enable_game()` (or has the block of declarations "
     "ApkPyGame used to write: `apkpy game init` mends it); G1102 `open_app(\"x\")` with no `Screen(id=\"x\")`; "
     "G1103 `t(\"k\")` with no such key in `translations`"),
    ("G12xx", "Reading `game/`", "G1201 not a declaration (for/if...), G1202 value that cannot be read, "
     "G1203 unknown name, G1204 unknown parameter, G1205 wrong type, G1206 missing, G1207 import, "
     "G1208 classes/`build`, G1209 `Game`, G1210 scenes, G1211 asset file, G1212 `@prefab`, G1214 atlas frame, "
     "G1215 atlas too big, G1216 Tiled map (format, tileset, layer), G1217 Tiled object with no entity, "
     "G1218 no such module (game/x.py), G1219 import cycle, G1220 not allowed at the top of a module, "
     "G1221 font file"),
    ("G13xx", "Data tables", "G1301 no table file/folder, G1302 not valid JSON, G1303 wrong type, "
     "G1304 unknown or missing field, G1305 id used twice, G1306 table setup (`id: str`, one table per class, "
     "`Ref` to a class with no table), G1307 `Ref` to an id that does not exist"),
    ("G20xx", "Scripts, translated to Java", "G2001 statement, G2002 expression, G2003 types, G2004 name, "
     "G2005 attribute/method, G2006 missing type, G2007 undeclared field, G2008 truthiness "
     "(`if x:` -> `if x != 0:`), G2009 arguments, G2010 may be None, G2011 return, G2012 name taken, "
     "G2999 a bug of the translator"),
    ("G3100", "A script at run time", "An exception in a script, with `main.py:line` and the error in Python terms "
     "(IndexError, ZeroDivisionError...)"),
    ("G30xx", "The engine at run time", "G3001 format too new, G3002 no such scene, G3005 unknown component "
     "(warning), G3021 asset missing, G3022 unreadable image, G3024 nothing to arrive at (`game.goto(scene, at)`), "
     "G3025 a Canvas's image is not a PNG it can read (or the canvas is too big), "
     "G3030 a suspended game could not be brought back exactly, G3031 a journal from another engine version, "
     "G3040 OpenGL ES did not start (with \"auto\", the game falls back to the Canvas), G3041 a 2.5D scene "
     "drawn with the Canvas, G3998 the desktop runner gave no answer"),
]


def generate():
    with open(os.path.join(PKG, "schema", "components.json"), encoding="utf-8") as fh:
        schema = json.load(fh)
    out = ["# Games: reference",
           "",
           "> GENERATED by `tools/game/gen_docs.py` from `schema/components.json` and the script translator: "
           "do not edit. Engine %s." % schema.get("engine", ""),
           "",
           "The guide is [Your first game](index.md). Everything here is written in `game/main.py`, which the build "
           "**reads** and never runs.",
           "",
           "## Contents",
           "",
           "- [Components](#components)",
           "- [Actions](#actions) (for `OnTap`, `OnCollide`, `Timer`, `Lifetime`, `when(...)`, `on_back=`)",
           "- [Scripts](#scripts): what a `class X(Script)` can use",
           "- [Errors](#errors): every code",
           "",
           "## Components",
           ""]
    for c in schema["components"]:
        out += ["### %s" % c["name"], "", "`%s`" % _call(c), "", c.get("doc", ""), ""] + _fields(c) + [""]
    out += ["## Actions", ""]
    for a in schema["actions"]:
        out += ["### %s" % a["name"], "", "`%s`" % _call(a), "", a.get("doc", ""), ""]
        if a["fields"]:
            out += _fields(a) + [""]
    out += ["## Scripts",
            "",
            "A `class Name(Script)` in `game/main.py` is translated to Java by the build (never run). Fields are "
            "annotated (`speed: float = 200.0`) and can be set where the script is used (`Ship(speed=240.0)`). "
            "Methods: `on_start(self)`, `update(self, dt: float)`, `on_collide(self, other: Entity, side: str)`, "
            "`on_tap(self)`, `on_destroy(self)`, and your own (annotated).",
            "",
            "Types: %s, and the game's own `@dataclass` classes." % ", ".join("`%s`" % t for t in sorted(scripts.JAVA)),
            "",
            "Python built-ins: `len`, `abs`, `min`, `max`, `round`, `int`, `float`, `str`, `range`, `print`; "
            "lists (`append`, `pop`, `insert`, `remove`, `clear`, `[i]`, `[-1]`, `len`), dicts with `str` keys "
            "(`[k]`, `get`, `keys`, `values`, `pop`, `clear`, `in`, `for k in d`, in insertion order), f-strings, "
            "`math` and `random` (seeded: the same game every run).",
            "",
            "### Many files",
            "",
            "Every `.py` file under `game/` is a module: `from game.x.y import name` or `import game.x.y as y`. "
            "A module holds imports, constants, module state (`STATE = Store()`: a list, a dict or a data class, "
            "reset for each new game and part of the state hash), plain functions, `@dataclass` classes and "
            "`Script` classes; the declarations stay in `game/main.py`. From `dataclasses`: `dataclass`, "
            "`field(default_factory=...)` and `replace(obj, field=value)`. Plain functions and data class methods "
            "can use `math` and `random`, not `game`, `scene`, `input` or `audio`.",
            "",
            "### Data, JSON and saves",
            "",
            "- `SPECIES = table(\"data/species\", Species)` at the top of a module: the rows of `data/species.json` "
            "(a list) or `data/species/*.json` (a row per file), checked at build time against the `@dataclass` "
            "(which needs `id: str`). `SPECIES.get(id)`, `SPECIES.has(id)`, `SPECIES.all()`, `len(SPECIES)`, "
            "`for s in SPECIES`, `id in SPECIES`. A field `Ref[Move]` (or `list[Ref[Move]]`...) holds ids of the "
            "Move table, checked too. Treat rows as read-only.",
            "- `to_json(value)` and `from_json(text, Type)`: a `@dataclass` (with lists, dicts and other data "
            "classes inside) to JSON text and back, the same text as CPython's "
            "`json.dumps(..., separators=(\",\", \":\"))`. Unknown keys are ignored; missing ones take the default.",
            "- `saves.write(slot, text)`, `saves.read(slot)` (`None` when empty), `saves.exists(slot)`, "
            "`saves.delete(slot)`, in Script methods. Writes are atomic; a read is recorded in the journal, so a "
            "game brought back plays with the text it read.",
            "- Tiled: an object's custom properties are `self.props.get_str(key)` / `get_int` / `get_float` / "
            "`get_bool` / `has`; a tile's custom properties are `scene.tile_tag(x, y, key)` (\"\" when no tile "
            "there has it; hidden layers count).",
            "",
            "### Properties",
            "",
            "| On | Name | Type | |",
            "|---|---|---|---|"]
    for owner, props in scripts.PROPS.items():
        where = owner if owner in scripts.MODULE_OBJECTS else "`%s` (and `self`)" % owner if owner == "Entity" \
            else "`%s`" % owner
        for name, (_, kind, mode) in props.items():
            out.append("| %s | `%s` | %s | %s |" % (where, name, kind, "read and write" if mode == "rw" else "read"))
    out += ["", "### Functions and methods", "", "| Call | Signature |", "|---|---|"]
    for (owner, name), (args, result, template) in scripts.METHODS.items():
        call = ("%s.%s" % (owner, name)) if owner in scripts.MODULE_OBJECTS else "%s.%s" % (owner.lower(), name)
        out.append("| `%s` | `%s` |" % (call, _signature(args, result, template)))
    for name in sorted(scripts.MATH1):
        out.append("| `math.%s` | `(float) -> float` |" % name)
    for name in sorted(scripts.MATH2):
        out.append("| `math.%s` | `(float, float) -> float` |" % name)
    out += ["",
            "Anything else gives a G2xxx error at build time, with the line and how to write it instead "
            "([Errors](#errors)).",
            "",
            "## Errors",
            "",
            "Each one names the file and the line, says why, and how to fix it: `APKPY G1201  game/main.py:49`.",
            "",
            "| Codes | Where | |",
            "|---|---|---|"]
    for codes, where, what in ERRORS:
        out.append("| %s | %s | %s |" % (codes, where, what))
    out.append("")
    return "\n".join(out)


def main():
    text = generate()
    if "--check" in sys.argv:
        try:
            with open(OUT, encoding="utf-8") as fh:
                if fh.read() == text:
                    return
        except OSError:
            pass
        sys.exit("game_engine/docs/reference.md is out of date: python tools/game/gen_docs.py")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("written", OUT)


if __name__ == "__main__":
    main()
