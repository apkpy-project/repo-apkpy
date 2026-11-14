"""The game's code as the Studio sees it: the files of game/ read in pieces (source.py), what each component and
action takes (components.json, the same file the build reads), and the names a field can choose from.

A picture or a sound that is in assets/ but not yet in the code can be chosen too: choosing it writes its line,
name = assets.image("assets/..."), with the others.
"""
import glob
import os
import re

from .. import schema
from .source import Source, literal

PICTURES = (".png", ".jpg", ".jpeg", ".webp")
SOUNDS = (".wav", ".ogg", ".mp3")

# The kinds of asset a field takes, by the field's type in components.json.
ASSET_KINDS = {"image": ("image", "sheet", "atlas"), "sound": ("sound", "music"), "font": ("font",),
               "tilemap": ("tilemap",)}

# A Script's typed fields, as the fields of a component.
SCRIPT_TYPES = {"float": "number", "int": "int", "str": "string", "bool": "bool", "Sound": "sound", "Image": "image",
                "Prefab": "entity"}

GROUPS = (("Look", ("Sprite", "Shape", "Text", "Canvas", "Animator", "Emitter", "Panel", "Bar", "Tween")),
          ("Move", ("Body", "Collider", "PlatformerController", "TopDownController", "GridController", "Patrol",
                    "Follow", "Mover", "Spin")),
          ("Do", ("OnCollide", "OnTap", "Timer", "Lifetime", "Spawner", "TouchButton")),
          ("Interface", ("Button", "Toggle", "Slider", "Tabs", "Keyboard", "ScrollList")),
          ("2.5D", ("Billboard", "Block", "Plane")),
          ("Map", ("Tilemap",)))

GAME_FIELDS = {
    "name": {"type": "string", "doc": "the game's name (the one on the phone is in My game, above)"},
    "size": {"type": "pair", "default": [360, 640], "doc": "the size the game is made for, in its own units"},
    "orientation": {"type": "enum", "values": ["portrait", "landscape", "any"], "default": "portrait"},
    "scale": {"type": "enum", "values": ["fit", "fill", "expand"], "default": "fit",
              "doc": "fit: all of it shows, with bands; fill: no bands, the edges may be cut; expand: more shows"},
    "background": {"type": "color", "default": "#000000"},
    "pixel_scale": {"type": "bool", "default": False, "doc": "pixel art: the game is scaled up by whole steps, sharp"},
    "font": {"type": "font", "doc": "the font of every text"},
    "seed": {"type": "int", "doc": "the same random numbers in every game, for tests"},
}

SCENE_FIELDS = {
    "name": {"type": "string", "required": True, "doc": "a word: goto_scene(\"name\") goes here"},
    "start": {"type": "bool", "default": False, "doc": "the game starts in this scene"},
    "kind": {"type": "enum", "values": ["2d", "2.5d"], "default": "2d", "doc": "2.5d: a world seen from above at an angle"},
    "background": {"type": "color", "doc": "by default the game's"},
    "music": {"type": "sound"},
    "music_volume": {"type": "number", "default": 1},
    "on_back": {"type": "actions", "default": [], "doc": "what the phone's Back does here"},
}

CAMERA_FIELDS = {
    "follow": {"type": "string", "doc": "the name of an entity, such as \"player\""},
    "bounds": {"type": "enum", "values": ["", "map"], "doc": "map: it stops at the edges of the scene's map"},
    "zoom": {"type": "number", "default": 1},
    "pitch": {"type": "number", "doc": "2.5D: degrees looking down"},
    "distance": {"type": "number", "doc": "2.5D: how far the camera is"},
    "fov": {"type": "number", "doc": "2.5D: how wide it sees, in degrees"},
}

ADD_FIELDS = {
    "at": {"type": "pair", "doc": "where, in the scene"},
    "ui": {"type": "bool", "default": False, "doc": "on the screen, not in the world: it does not move with the camera"},
}

ENTITY_FIELDS = {
    "tags": {"type": "strings", "default": [], "doc": "words other things find it by: OnCollide(\"coin\", ...)"},
}

CONDITION = re.compile(r"^\s*(?:count\(\s*(\w+)\s*\)|(\w+))\s*(==|!=|<=|>=|<|>)\s*(-?\d+(?:\.\d+)?)\s*$")
OPERATORS = ("==", "!=", "<", "<=", ">", ">=")


def component_spec(name):
    return schema.component(name)


def action_spec(name):
    return schema.action(name)


def action_names():
    return [a["name"] for a in schema.load()["actions"]]


def doc_of(name):
    spec = schema.component(name) or schema.action(name)
    return spec.get("doc", "") if spec else ""


def slug(text):
    word = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "thing"
    return "_" + word if word[0].isdigit() else word


class GameCode:
    """The Python files of the game, each a Source. The undo order is kept across them."""

    def __init__(self, root):
        self.root = root
        self.load()

    def load(self):
        self.sources = {}
        self.broken = {}
        self.history, self.future = [], []
        self.touched = set()
        folder = os.path.join(self.root, "game")
        for path in sorted(glob.glob(os.path.join(folder, "**", "*.py"), recursive=True)):
            rel = os.path.relpath(path, self.root).replace(os.sep, "/")
            if "__pycache__" in rel:
                continue
            try:
                source = Source(path)
            except (SyntaxError, ValueError, UnicodeDecodeError) as e:
                self.broken[rel] = str(e)
                continue
            source.rel = rel
            source.on_change = self.changed
            self.sources[rel] = source

    @property
    def main(self):
        return self.sources.get("game/main.py")

    def files(self):
        """The sources, game/main.py first."""
        rest = [s for rel, s in sorted(self.sources.items()) if rel != "game/main.py"]
        return ([self.main] if self.main is not None else []) + rest

    # ── changes, undo, saving ──

    def changed(self, source):
        self.history.append(source)
        self.future = []

    def undo(self):
        while self.history:
            source = self.history.pop()
            if source.undo():
                self.future.append(source)
                return True
        return False

    def redo(self):
        while self.future:
            source = self.future.pop()
            if source.redo():
                self.history.append(source)
                return True
        return False

    @property
    def dirty(self):
        return any(s.dirty for s in self.sources.values())

    def touch(self, section):
        self.touched.add(section)

    def dirty_sections(self):
        return set(self.touched) if self.dirty else set()

    def save(self):
        saved = [s.rel for s in self.sources.values() if s.save()]
        self.touched.clear()
        return saved

    def changed_on_disk(self):
        return any(s.changed_on_disk() for s in self.sources.values())

    def reload(self):
        self.load()

    # ── what is in the code ──

    def prefabs(self):
        """[(source, piece)] of every @prefab, game/main.py first."""
        return [(s, p) for s in self.files() for p in s.find("prefab")]

    def prefab(self, name):
        return next(((s, p) for s, p in self.prefabs() if p.name == name), (None, None))

    def scripts(self):
        """{name: (source, piece)} of the Script classes, whose typed fields a component form shows."""
        return {p.name: (s, p) for s in self.files() for p in s.find("script")}

    def scenes(self):
        main = self.main
        return [] if main is None else main.find("scene")

    def game_call(self):
        main = self.main
        piece = main.first("game") if main is not None else None
        return piece.call if piece is not None else None

    def game_size(self):
        call = self.game_call()
        size = call.get("size") if call is not None else None
        if size is not None and size.kind == "literal":
            return tuple(size.value)
        return (360, 640)

    def variables(self):
        """The game's variables, then each scene's: what a rule's condition can test."""
        names = []
        call = self.game_call()
        found = call.get("vars") if call is not None else None
        if found is not None and found.kind == "literal":
            names.extend(found.value)
        for scene in self.scenes():
            v = scene.call.get("vars")
            if v is not None and v.kind == "literal":
                names.extend(k for k in v.value if k not in names)
        return names

    def tags(self):
        """Every tag written in the code, for OnCollide and the rules."""
        found = []
        for source in self.files():
            for m in re.finditer(r"tags\s*=\s*\[([^\]]*)\]", source.text):
                for tag in re.findall(r"\"([^\"]+)\"|'([^']+)'", m.group(1)):
                    tag = tag[0] or tag[1]
                    if tag not in found:
                        found.append(tag)
        return found

    def scene_names(self):
        main = self.main
        return [] if main is None else list(main.scene_names.values())

    # ── names a field can choose ──

    def asset_names(self, source, field_type):
        """The names of the assets a field of this type takes, declared in source."""
        kinds = ASSET_KINDS.get(field_type, ())
        return [name for name, kind, _ in source.assets(*kinds)]

    def free_files(self, source, field_type):
        """Pictures or sounds in the project that no assets.<kind>(...) of source names yet."""
        used = {path for _, _, path in source.assets()}
        if field_type == "image":
            endings, folders = PICTURES, ("assets",)
        elif field_type == "sound":
            endings, folders = SOUNDS, ("assets",)
        elif field_type == "tilemap":
            endings, folders = (".tmj",), ("levels", "maps", "assets")
        elif field_type == "font":
            endings, folders = (".ttf", ".otf", ".fnt"), ("assets",)
        else:
            return []
        out = []
        for folder in folders:
            base = os.path.join(self.root, folder)
            for path in sorted(glob.glob(os.path.join(base, "**", "*"), recursive=True)):
                if path.lower().endswith(endings) and os.path.isfile(path):
                    rel = os.path.relpath(path, self.root).replace(os.sep, "/")
                    if rel not in used:
                        out.append(rel)
        return out

    def declare(self, source, rel, field_type):
        """Writes name = assets.<kind>("rel") under the other assets of source, and gives back the name."""
        stem = slug(os.path.splitext(os.path.basename(rel))[0])
        taken = {p.name for p in source.pieces if p.name}
        name = stem if stem not in taken else next("%s_%d" % (stem, n) for n in range(2, 999) if "%s_%d" % (stem, n) not in taken)
        if field_type == "image":
            kind, extra = "image", ""
            size = self.picture_size(rel)
            if size and size[0] > size[1] and size[0] % size[1] == 0 and 2 <= size[0] // size[1] <= 16:
                kind, extra = "sheet", ", frame=(%d, %d)" % (size[1], size[1])
        elif field_type == "sound":
            kind, extra = ("music" if "theme" in stem or "music" in stem else "sound"), ""
        else:
            kind, extra = field_type, ""
        line = "%s = assets.%s(%s%s)" % (name, kind, literal(rel), extra)
        last = source.find("asset") or source.find("game") or source.find("import")
        source.add_statement(line, after=last[-1] if last else None, blank_lines=0 if source.find("asset") else 1)
        return name

    def picture_size(self, rel):
        try:
            from PIL import Image
            with Image.open(os.path.join(self.root, *rel.split("/"))) as img:
                return img.size
        except (OSError, ImportError):
            return None

    def asset_path(self, source, name):
        for n, kind, path in source.assets():
            if n == name:
                return kind, path
        return None, None

    def sheet_frame(self, source, name):
        """The frame size of assets.sheet(..., frame=(w, h)), or None."""
        piece = source.first("asset", name)
        if piece is None:
            return None
        frame = piece.call.get("frame")
        if frame is not None and frame.kind == "literal":
            return tuple(frame.value)
        return None

    # ── new things ──

    def sample(self, source, spec, field=""):
        """A value to start a required field with, or None when there is nothing to choose yet."""
        t = spec["type"]
        if t in ASSET_KINDS:
            names = self.asset_names(source, t)
            return names[0] if names else None
        if t == "entity":
            names = [p.name for _, p in self.prefabs()]
            return names[0] + "()" if names else None
        if t == "text":
            return literal("OK" if field == "label" else "Text")
        if t == "string":
            return literal({"key": "left", "label": "OK", "var": (self.variables() or ["score"])[0],
                            "scene": (self.scene_names() or ["main"])[0], "screen": "pause_menu"}.get(field, ""))
        if t == "strings":
            return literal(["One", "Two"])
        if t == "animations":
            return literal({"idle": {"frames": [0]}})
        if t == "condition":
            names = self.variables()
            return literal(condition_text(names[0], False, ">=", "1") if names else condition_text("coin", True, "==", "0"))
        if t == "pair":
            return literal(tuple(spec.get("default", [0, 0])))
        if t == "number":
            return literal(spec.get("default", 0))
        if "default" in spec:
            value = spec["default"]
            return literal(tuple(value) if isinstance(value, list) and t in ("pair", "box", "rect") else value)
        return None

    def new_component(self, source, name):
        """The text of a new component (or Script) with its required fields, or (None, why)."""
        spec = component_spec(name)
        if spec is None:
            found = self.scripts().get(name)
            if found is None:
                return None, "There is no component %s." % name
            args = []
            for f in found[1].fields:
                if f.default is None:
                    value = self.sample(source, {"type": SCRIPT_TYPES.get(f.annotation, "code")}, f.name)
                    if value is None:
                        return None, "%s needs a %s first." % (name, f.annotation)
                    args.append("%s=%s" % (f.name, value))
            return "%s(%s)" % (name, ", ".join(args)), ""
        args = []
        for field in spec["args"]:
            if field.startswith("*"):
                break
            f = spec["fields"][field]
            if not f.get("required"):
                break
            value = self.sample(source, f, field)
            if value is None:
                what = {"image": "a picture (Art, or a .png in assets/)", "tilemap": "a level (.tmj)",
                        "entity": "an object", "sound": "a sound"}.get(f["type"], field)
                return None, "%s needs %s first." % (name, what)
            args.append(value)
        if name == "OnCollide":
            args = [literal((self.tags() or ["player"])[0]), "destroy()"]
        elif name == "OnTap":
            args = [literal_action(self, source)]
        elif name == "Timer":
            args = ["1", literal_action(self, source)]
        elif name == "Lifetime":
            args = ["1"]
        return "%s(%s)" % (name, ", ".join(args)), ""

    def new_action(self, source, name):
        spec = action_spec(name)
        args = []
        for field in spec["args"]:
            if field.startswith("*"):
                args.append(literal_action(self, source))         # only_if("keys >= 1", ...): one to start with
                break
            f = spec["fields"][field]
            if not f.get("required"):
                break
            value = literal("coins") if field == "key" else self.sample(source, f, field)
            if value is None:
                return None, "%s() needs %s first." % (name, "a sound" if f["type"] == "sound" else "an object" if f["type"] == "entity" else field)
            args.append(value)
        if name == "exit_game":
            args = [literal({"result": "win"})]
        return "%s(%s)" % (name, ", ".join(args)), ""


def literal_action(code, source):
    sounds = code.asset_names(source, "sound")
    return "sound(%s)" % sounds[0] if sounds else 'var_add("%s")' % (code.variables() or ["score"])[0]


def condition_parts(text):
    """when("lives <= 0", ...): ("lives", False, "<=", "0"); count(coin): ("coin", True, ...). None if not that."""
    m = CONDITION.match(text or "")
    if not m:
        return None
    return (m.group(1) or m.group(2), bool(m.group(1)), m.group(3), m.group(4))


def condition_text(name, counted, op, number):
    return "%s %s %s" % ("count(%s)" % name if counted else name, op, number)
