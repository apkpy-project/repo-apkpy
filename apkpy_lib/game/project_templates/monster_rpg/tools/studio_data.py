"""What the Studio knows about the monster RPG, with no window: its data (from game/data/defs.py), where things are
used, the story's events, game/main.py's places and music, game/ui/kit.py's font and sounds, and copies of the
project.

The general part (tables, rows, forms' words, copies) is ApkPy's own now: apkpy_lib.game.studio.data. This is what
only this game has.
"""
import copy
import json
import os
import re
import shutil

from apkpy_lib.game.studio import data as _data
from apkpy_lib.game.studio.data import (BACKUPS, KEEP_BACKUPS, AppFile, BackupPlan, DataProject, Field, RecordClass,  # noqa: F401
                                        Spec, Table, Use, annotation_text, backup_label, blank_value, copy_sound,
                                        parse_type, slug, write_json)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_FOLDERS = ("data", "story", "maps_src")
BACKUP_FILES = ("game/main.py", "game/ui/kit.py", "apkpy.toml", "icon.png")
IMAGE_FOLDER = "assets"
PLAN = BackupPlan(whole=BACKUP_FOLDERS, assets=IMAGE_FOLDER, endings=(".png", ".fnt", ".ttf", ".otf"), files=BACKUP_FILES, largest=0)

# Fields of plain text that have a known list of values. You can still write something else.
CHOICES = {
    ("Move", "kind"): ["physical", "special", "status"],
    ("Effect", "stat"): ["", "attack", "defense", "special", "speed"],
    ("Effect", "target"): ["foe", "self"],
    ("Species", "ev_stat"): ["hp", "attack", "defense", "special", "speed"],
    ("Item", "kind"): ["heal", "cure", "capture", "key"],
    ("Nature", "up"): ["", "attack", "defense", "special", "speed"],
    ("Nature", "down"): ["", "attack", "defense", "special", "speed"],
}

HELP = {
    ("Species", "name"): "What the player reads.",
    ("Species", "types"): "One or two.",
    ("Species", "base"): "Its stats. Weak is about 30, strong is about 110.",
    ("Species", "learnset"): "The moves it learns, and at which level. Level 1 is what it starts with.",
    ("Species", "catch_rate"): "From 1 (very hard) to 255 (very easy).",
    ("Species", "exp_yield"): "The experience it gives when beaten. About 50 for a weak one.",
    ("Species", "ev_stat"): "The stat that grows a little in whoever beats it.",
    ("Species", "evolves_to"): "Optional: what it becomes.",
    ("Species", "evolve_level"): "The level at which it does.",
    ("Move", "kind"): "physical uses attack and defense, special uses special on both sides, status does no damage.",
    ("Move", "power"): "0 for a move that does no damage. About 40 is weak, about 100 is strong.",
    ("Move", "accuracy"): "From 1 to 100: the chance to hit.",
    ("Move", "pp"): "How many times it can be used before resting.",
    ("Move", "effect"): "What else it does: one of the Effects.",
    ("Move", "chance"): "The chance of the effect, from 0 to 100. Use 100 for a move that only does that.",
    ("Item", "kind"): "The pocket of the bag it goes in: heal and cure go in Items, capture in Knots, key in Key. What it does is in the fields below.",
    ("Item", "heal"): "The HP it gives back.",
    ("Item", "cures"): "The statuses it takes away.",
    ("Item", "cures_all"): "It takes away any status.",
    ("Item", "revive"): "It works on a monster that fainted: with heal, that much HP, or else half.",
    ("Item", "capture"): "How well it catches a monster: 10 is normal, more is better. 0 if it does not.",
    ("Species", "evolve_item"): "Instead of a level: it evolves when this item is used on it, in the bag.",
    ("Species", "evolve_flag"): "It only evolves once this flag is set in the story.",
    ("Species", "variants"): "Other looks of it, and only its looks. A wild one has a variant 1 time in the number you give (4096 is very rare, 0 is never: only trainers). Each has its own drawing in Art.",
    ("TrainerMonster", "variant"): "Its look: default, or one of its variants.",
    ("Status", "name"): "What the player reads beside a monster that has it.",
    ("Status", "apply_text"): "When it starts. {name} is the monster.",
    ("Status", "turn_share"): "It loses this part of its HP each turn: 8 is an eighth. 0 for none.",
    ("Status", "turn_text"): "Each turn it loses HP.",
    ("Status", "attack_factor"): "Its physical moves hit this much: 0.5 is half, 1 is as usual.",
    ("Status", "min_turns"): "It misses at least this many turns, and then it is over. 0 if it does not stop it from moving.",
    ("Status", "max_turns"): "And at most this many.",
    ("Status", "still_text"): "On a turn it misses.",
    ("Status", "wake_text"): "When it is over.",
    ("Status", "capture_bonus"): "A monster with it is this much easier to catch: 1.5 is half as easy again.",
    ("Effect", "status"): "A status it gives, if any.",
    ("Effect", "stat"): "A stat it moves up or down for the rest of the battle, if any.",
    ("Effect", "amount"): "How many steps: 1 up, -1 down. Each step is about half as much again.",
    ("Effect", "target"): "foe is the one it hits, self is the one who uses it.",
    ("Effect", "heal_percent"): "HP it gives back, as a part of the whole: 50 is half.",
    ("Effect", "text"): "What it says. {name} is the monster it changed.",
    ("Words", "text"): "{name}, {count} and the like are filled in by the game: keep them. {currency} is the money's name.",
    ("Item", "price"): "What a shop asks for it.",
    ("Nature", "up"): "This stat is 10% higher.",
    ("Nature", "down"): "This stat is 10% lower.",
    ("Trainer", "reward"): "The money you get for winning.",
    ("Trainer", "lose_text"): "What they say when they lose.",
    ("Trainer", "expect_level"): "How strong your partner should be by this fight, for tools/balance.py and the tests. 0 means the level it starts at.",
    ("EncounterTable", "rate"): "The chance of a fight on each step in that zone, from 0 to 100. About 10 is normal.",
    ("EncounterRow", "weight"): "How common, compared with the others.",
    ("GameInfo", "start_map"): "Where a new journey starts.",
    ("GameInfo", "start_at"): "The marker on that map.",
    ("GameInfo", "first_event"): "What happens as it starts.",
    ("GameInfo", "money"): "What the player starts with.",
    ("GameInfo", "heal_map"): "Where you wake up after losing a fight.",
    ("GameInfo", "heal_at"): "The marker on that map.",
    ("GameInfo", "starters"): "The ones to choose from, 1 to 3. The tests use them.",
    ("GameInfo", "starter_level"): "The level they start at.",
    ("GameInfo", "title_giant"): "The shape behind the title.",
    ("GameInfo", "title_visitors"): "Who crosses the sky on the title screen.",
    ("GameInfo", "fair_fights"): "The first fights of your game. The tests fail if a starter wins less than 80% of these.",
    ("GameInfo", "currency"): "The name of the money.",
    ("GameInfo", "no_flee_text"): "When you try to run from a trainer.",
    ("GameInfo", "owned_text"): "When you try to catch a trainer's monster.",
    ("GameInfo", "lost_text"): "When you lose a fight. {money} and {currency} are filled in.",
}

# Labels of fields, where the name of the field says too little.
WORDS = {"hp": "HP", "pp": "PP", "ev_stat": "Grows in the winner", "exp_yield": "Experience given", "learnset": "Moves it learns", "species": "Monster",
         "rows": "Monsters", "rate": "Chance per step", "min": "From level", "max": "To level", "lose_text": "Words on losing", "expect_level": "Partner's level by then",
         "color": "Colour", "evolves_to": "Evolves into", "evolve_level": "At level", "title_giant": "Giant on the title", "title_visitors": "Visitors on the title",
         "no_flee_text": "Words: cannot run", "owned_text": "Words: already owned", "lost_text": "Words on losing"}


def read_schema(root=ROOT):
    """({class name: RecordClass}, {class name: data path}) from game/data/defs.py, and only from there."""
    return _data.read_schema(root, [os.path.join(root, "game", "data", "defs.py")])


class StoryEvents:
    """The events, read-only: most are written in story/, and you change them there."""
    dirty = False
    cls = "Event"
    rows = []

    def __init__(self, root):
        self.root = root

    def ids(self):
        found = set()
        folder = os.path.join(self.root, "story")
        if os.path.isdir(folder):
            for name in os.listdir(folder):
                if name.endswith(".story"):
                    with open(os.path.join(folder, name), encoding="utf-8") as fh:
                        for line in fh:
                            m = re.match(r"(event|trainer) +(\S+)", line)
                            if m:
                                found.add(m.group(2) if m.group(1) == "event" else "trainer." + m.group(2))
        folder = os.path.join(self.root, "data", "events")
        if os.path.isdir(folder):
            for name in os.listdir(folder):
                if name.endswith(".json") and not name.startswith("_"):
                    try:
                        with open(os.path.join(folder, name), encoding="utf-8") as fh:
                            found.update(e["id"] for e in json.load(fh))
                    except (ValueError, KeyError, TypeError):
                        pass
        return sorted(found)

    def get(self, row_id):
        return None

    def save(self):
        pass


class MainFile:
    """What game/main.py says about each place: its music, volume and background, and the pieces of music."""

    def __init__(self, root):
        self.path = os.path.join(root, "game", "main.py")
        self.root = root
        self.load()

    def load(self):
        with open(self.path, encoding="utf-8") as fh:
            self.text = fh.read()
        self.saved = self.text

    @property
    def dirty(self):
        return self.text != self.saved

    def save(self):
        if self.dirty:
            with open(self.path, "w", encoding="utf-8") as fh:
                fh.write(self.text)
            self.saved = self.text

    def scenes(self):
        return re.findall(r'game\.scene\("(\w+)"', self.text)

    def _span(self, scene):
        """Where the words of that scene are."""
        m = re.search(r'game\.scene\("%s"' % re.escape(scene), self.text)
        if not m:
            return None
        depth, at = 0, m.start() + len("game.scene")
        quoted = False
        for i in range(at, len(self.text)):
            c = self.text[i]
            if c == '"':
                quoted = not quoted
            elif not quoted and c in "({[":
                depth += 1
            elif not quoted and c in ")}]":
                depth -= 1
                if depth == 0:
                    return at, i
        return None

    def get(self, scene, key):
        span = self._span(scene)
        if span is None:
            return ""
        m = re.search(r'\b%s=("[^"]*"|[\w.]+)' % key, self.text[span[0]:span[1]])
        return m.group(1) if m else ""

    def set(self, scene, key, value):
        """value None takes it away."""
        span = self._span(scene)
        if span is None:
            return
        words = self.text[span[0]:span[1]]
        found = re.search(r',?\s*\b%s=("[^"]*"|[\w.]+)' % key, words)
        if value is None:
            words = words[:found.start()] + words[found.end():] if found else words
        elif found:
            inner = re.search(r'\b%s=("[^"]*"|[\w.]+)' % key, words)
            words = words[:inner.start()] + "%s=%s" % (key, value) + words[inner.end():]
        else:
            words = words + ", %s=%s" % (key, value)
        self.text = self.text[:span[0]] + words + self.text[span[1]:]

    def tracks(self):
        """[(name, path)] of the pieces of music."""
        return re.findall(r'^(\w+)\s*=\s*assets\.music\("([^"]+)"\)', self.text, re.M)

    def replace_track(self, name, source):
        path = dict(self.tracks())[name]
        new = copy_sound(self.root, source, path)
        self.text = re.sub(r'^(%s\s*=\s*assets\.music\(")[^"]+' % re.escape(name), lambda m: m.group(1) + new, self.text, flags=re.M)

    def add_track(self, source):
        base = slug(os.path.splitext(os.path.basename(source))[0]) or "music"
        name, n = base + "_music", 2
        names = dict(self.tracks())
        while name in names:
            name, n = "%s_%d_music" % (base, n), n + 1
        target = "assets/music_%s%s" % (name[:-6], os.path.splitext(source)[1].lower())
        new = copy_sound(self.root, source, target)
        line = '%s = assets.music("%s")\n' % (name, new)
        last = list(re.finditer(r'^\w+\s*=\s*assets\.music\(.*\n', self.text, re.M))
        at = last[-1].end() if last else 0
        self.text = self.text[:at] + line + self.text[at:]
        return name


class LookFile:
    """The font, its sizes and the sounds, in game/ui/kit.py."""

    def __init__(self, root):
        self.root = root
        self.path = os.path.join(root, "game", "ui", "kit.py")
        self.load()

    def load(self):
        with open(self.path, encoding="utf-8") as fh:
            self.text = fh.read()
        self.saved = self.text

    @property
    def dirty(self):
        return self.text != self.saved

    def save(self):
        if self.dirty:
            with open(self.path, "w", encoding="utf-8") as fh:
                fh.write(self.text)
            self.saved = self.text

    @property
    def font(self):
        m = re.search(r'^\w+\s*=\s*assets\.font\("([^"]+)"\)', self.text, re.M)
        return m.group(1) if m else ""

    def _number(self, name):
        m = re.search(r"^%s\s*=\s*(\d+)" % name, self.text, re.M)
        return int(m.group(1)) if m else 0

    def _set_number(self, name, value):
        self.text = re.sub(r"^(%s\s*=\s*)\d+" % name, lambda m: m.group(1) + str(value), self.text, count=1, flags=re.M)

    size = property(lambda self: self._number("SIZE"), lambda self, v: self._set_number("SIZE", v))
    big = property(lambda self: self._number("BIG"), lambda self, v: self._set_number("BIG", v))

    def _set_font(self, path):
        self.text = re.sub(r'^(\w+\s*=\s*assets\.font\(")[^"]+', lambda m: m.group(1) + path, self.text, count=1, flags=re.M)

    def use_font(self, source):
        ending = os.path.splitext(source)[1].lower()
        if ending not in (".ttf", ".otf"):
            raise ValueError("A font file ends in .ttf or .otf.")
        name = "assets/" + slug(os.path.splitext(os.path.basename(source))[0]) + ending
        target = os.path.join(self.root, *name.split("/"))
        if os.path.abspath(source) != os.path.abspath(target):
            shutil.copyfile(source, target)
        self._set_font(name)
        self.size, self.big = max(self.size, 10), max(self.big, 16)

    def use_pixel_font(self):
        self._set_font("assets/pixel.fnt")
        self.size, self.big = 8, 16

    def sample(self, words):
        """A picture of these words in the font."""
        from PIL import Image, ImageDraw, ImageFont
        path = os.path.join(self.root, *self.font.split("/"))
        if path.endswith(".fnt"):
            return self._bitmap_sample(path, words)
        font = ImageFont.truetype(path, max(self.size, 1) * 2)
        wide = int(font.getlength(words)) + 12
        img = Image.new("RGB", (wide, max(self.size, 1) * 3 + 8), "white")
        ImageDraw.Draw(img).text((6, 4), words, fill=(34, 37, 43), font=font)
        return img

    def _bitmap_sample(self, path, words):
        from PIL import Image
        chars = {}
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("char "):
                    v = dict(re.findall(r"(\w+)=(-?\d+)", line))
                    chars[chr(int(v["id"]))] = v
        with Image.open(os.path.join(os.path.dirname(path), "pixel.png")) as img:
            sheet = img.convert("RGBA")
        scale = 2
        wide = sum(int(chars[c]["xadvance"]) if c in chars else 6 for c in words)
        out = Image.new("RGBA", (wide + 4, 12), (255, 255, 255, 255))
        x = 2
        for c in words:
            v = chars.get(c)
            if v:
                x0, y0 = int(v["x"]), int(v["y"])
                glyph = sheet.crop((x0, y0, x0 + int(v["width"]), y0 + int(v["height"])))
                dark = Image.new("RGBA", glyph.size, (34, 37, 43, 255))
                out.paste(dark, (x, 2 + int(v["yoffset"])), glyph)
                x += int(v["xadvance"])
            else:
                x += 6
        return out.resize((out.width * scale, out.height * scale), Image.NEAREST).convert("RGB")

    def sounds(self):
        return re.findall(r'^(\w+)\s*=\s*assets\.sound\("([^"]+)"\)', self.text, re.M)

    def replace_sound(self, name, source):
        path = dict(self.sounds())[name]
        new = copy_sound(self.root, source, path)
        self.text = re.sub(r'^(%s\s*=\s*assets\.sound\(")[^"]+' % re.escape(name), lambda m: m.group(1) + new, self.text, flags=re.M)


class Project(DataProject):
    """The monster RPG's data, and what only it has: the story, the maps, the monsters' pictures, the font."""

    CHOICES = CHOICES
    HELP = HELP
    WORDS = WORDS
    NO_USES = ("GameInfo",)
    ID_EXAMPLE = "spark_toad"
    WHO = {"Species": "the monster", "Move": "the move", "Trainer": "the trainer", "EncounterTable": "the wild monsters", "Shop": "the shop", "GameInfo": "the start of the game (data/game.json)"}
    STORY_WORDS = {"Species": [r"^(\s*give\s+monster\s+)%s\b"], "Item": [r"^(\s*give\s+)%s\b"],
                   "Trainer": [r"^(\s*battle\s+)%s\b", r"^(trainer\s+)%s\b"], "Shop": [r"^(\s*shop\s+)%s\b"]}

    def __init__(self, root=ROOT):
        self.main = MainFile(root)
        self.look = LookFile(root)
        DataProject.__init__(self, root)

    def read_schema(self):
        return read_schema(self.root)

    def make_table(self, cls, path):
        return StoryEvents(self.root) if cls == "Event" else Table(self.root, path, cls)

    def reload(self):
        self.main.load()
        self.look.load()
        DataProject.reload(self)

    def id_pattern(self, cls):
        return r"[a-z][a-z0-9_.]*" if cls == "EncounterTable" else r"[a-z][a-z0-9_]*"

    def fill_new_row(self, cls, row, name):
        moves = self.tables.get("Move")
        species = self.tables["Species"].ids() if "Species" in self.tables else []
        if cls == "Species":
            kinds = self.table("Type").ids()
            row["types"] = kinds[:1]
            row["base"] = {"hp": 40, "attack": 45, "defense": 40, "special": 45, "speed": 45}
            damage = [m["id"] for m in moves.rows if m.get("kind") != "status"]
            row["learnset"] = [{"level": 1, "move": damage[0]}] if damage else []
            row["catch_rate"], row["exp_yield"], row["ev_stat"] = 120, 50, "hp"
        elif cls == "Move":
            row["type"] = self.table("Type").ids()[0]
            row["kind"], row["power"], row["accuracy"], row["pp"] = "physical", 40, 100, 20
        elif cls == "Type":
            row["color"] = "#909090"
        elif cls == "Item":
            row["kind"], row["heal"], row["price"] = "heal", 20, 100
        elif cls == "Effect":
            row["target"], row["stat"], row["amount"], row["text"] = "foe", "attack", -1, "{name} loses heart."
        elif cls == "Status":
            row["apply_text"], row["capture_bonus"] = "{name} is %s!" % name.lower(), 1.5
        elif cls == "Words":
            row["text"] = name
        elif cls == "Trainer":
            row["team"] = [{"species": species[0], "level": 3}] if species else []
            row["reward"], row["lose_text"] = 100, "You win."
        elif cls == "EncounterTable":
            row["rate"] = 10
            row["rows"] = [{"species": species[0], "min": 2, "max": 4, "weight": 10}] if species else []

    def use_text(self, cls, what, row):
        return Use(what if cls == "GameInfo" else "%s: %s" % (what, row.get("name") or row["id"]), cls, row["id"])

    def more_uses(self, cls, row_id, out):
        if cls in ("Trainer", "EncounterTable") and "GameInfo" in self.tables:
            for r in self.table("GameInfo").rows:
                if row_id in r.get("fair_fights", []):
                    out.append(Use("the fights checked by the tests (data/game.json)", "GameInfo", r["id"]))
        for name, number, line in self._story_lines():
            for pattern in self.STORY_WORDS.get(cls, []):
                if re.match(pattern % re.escape(row_id), line):
                    out.append(Use("story/%s, line %d: %s" % (name, number, line.strip()), "story", "%s:%d" % (name, number)))
        if cls == "Words":
            for path, number, line in self._code_lines():
                if re.search(r'"%s"' % re.escape(row_id), line):
                    out.append(Use("the game's code: %s, line %d" % (path, number), "code", path))
        if cls == "Type":
            for r in self.table("Type").rows:
                if r["id"] != row_id and any(row_id in r.get(k, []) for k in ("strong", "weak", "immune")) and not any(u.target == r["id"] and u.section == "Type" for u in out):
                    out.append(Use("the type: %s" % r.get("name", r["id"]), "Type", r["id"]))
        if cls == "Trainer":
            folder = os.path.join(self.root, "maps_src")
            for name in sorted(os.listdir(folder)):
                if name.endswith(".map"):
                    with open(os.path.join(folder, name), encoding="utf-8") as fh:
                        for line in fh:
                            if re.match(r"trainer\s+\S+\s+\S+\s+%s\b" % re.escape(row_id), line):
                                out.append(Use("map %s: %s" % (name[:-4], line.strip()), "maps", name[:-4]))

    def rename_in_rows(self, cls, old, new):
        if cls in ("Trainer", "EncounterTable") and "GameInfo" in self.tables:
            for r in self.table("GameInfo").rows:
                r["fair_fights"] = [new if x == old else x for x in r.get("fair_fights", [])]

    def after_rename(self, cls, old, new, row):
        self._rename_in_story(cls, old, new)
        if cls == "Trainer":
            self._rename_trainer_on_maps(old, new)
        if cls == "Species":
            for v in [""] + [x.get("id", "") for x in row.get("variants", [])]:
                if os.path.isfile(self.sprite(old, v)):
                    os.replace(self.sprite(old, v), self.sprite(new, v))

    def logo_path(self):
        return os.path.join(self.root, "assets", "title_logo.png")

    def draw_logo(self, word):
        import make_art
        make_art.draw_logo(word).save(self.logo_path())

    def icon_path(self):
        value = self.app.values.get("icon", "")
        return os.path.join(self.root, *value.split("/")) if value else ""

    def set_icon(self, source):
        """Your picture becomes icon.png, beside apkpy.toml. It has to be square, for the phone."""
        from PIL import Image
        with Image.open(source) as img:
            if img.width != img.height:
                raise ValueError("That picture is %d x %d. An icon is square." % img.size)
            img.convert("RGBA").save(os.path.join(self.root, "icon.png"))
        self.app.values["icon"] = "icon.png"

    def icon_from_monster(self, row_id):
        """A monster's front, big and sharp, on a plain colour."""
        from PIL import Image
        with Image.open(self.sprite(row_id)) as img:
            cell = img.convert("RGBA").crop((0, 0, 64, 64))
        species = self.table("Species").get(row_id)
        kind = self.table("Type").get(species["types"][0]) if species and species.get("types") else None
        out = Image.new("RGBA", (512, 512), (kind or {}).get("color", "#2d4f7c"))
        big = cell.resize((448, 448), Image.NEAREST)
        out.alpha_composite(big, (32, 32))
        out.save(os.path.join(self.root, "icon.png"))
        self.app.values["icon"] = "icon.png"

    def map_names(self):
        folder = os.path.join(self.root, "maps_src")
        return sorted(n[:-4] for n in os.listdir(folder) if n.endswith(".map"))

    @property
    def dirty(self):
        return self.app.dirty or self.main.dirty or self.look.dirty or any(t.dirty for t in self.tables.values())

    def save(self):
        self.main.save()
        self.look.save()
        self.app.save()
        self.main.load()            # the game's name is in that file too
        for table in self.tables.values():
            table.save()

    def _code_lines(self):
        """The game's own code, where words are asked for by their id."""
        folder = os.path.join(self.root, "game")
        for d, _, names in os.walk(folder):
            for name in sorted(names):
                if name.endswith(".py"):
                    path = os.path.join(d, name)
                    with open(path, encoding="utf-8") as fh:
                        for number, line in enumerate(fh, 1):
                            if "word(" in line or "named(" in line or "Word(key=" in line or "menu_button(" in line or "choice(" in line:
                                yield os.path.relpath(path, self.root).replace("\\", "/"), number, line

    def words_in_code(self):
        """The ids of words the code asks for."""
        found = set()
        for _, _, line in self._code_lines():
            found |= set(re.findall(r'(?:word|named)\("(\w+)"', line))
            found |= set(re.findall(r'Word\(key="(\w+)"\)', line))
            found |= set(re.findall(r'menu_button\("[^"]*", "\w+", -?\d+, "(\w+)"\)', line))
            found |= set(re.findall(r'choice\("\w+", "[^"]+", -?\d+, -?\d+, "(\w+)"\)', line))
        return found

    def _story_lines(self):
        folder = os.path.join(self.root, "story")
        if not os.path.isdir(folder):
            return
        for name in sorted(os.listdir(folder)):
            if name.endswith(".story"):
                with open(os.path.join(folder, name), encoding="utf-8") as fh:
                    for number, line in enumerate(fh, 1):
                        yield name, number, line.rstrip("\n")

    def sprite(self, row_id, variant=""):
        """A species' sheet, or one of its variants' (<species>.<variant>.png)."""
        name = row_id + ("." + variant if variant and variant != "default" else "")
        return os.path.join(self.root, "assets", "monsters", name + ".png")

    def _rename_trainer_on_maps(self, old, new):
        """Their object on a map, and the flag that says they were beaten."""
        folder = os.path.join(self.root, "maps_src")
        for name in os.listdir(folder):
            if name.endswith(".map"):
                self._rewrite(os.path.join(folder, name), lambda text: re.sub(r"^(trainer\s+\S+\s+\S+\s+)%s\b" % re.escape(old), lambda m: m.group(1) + new, text, flags=re.M))
        word = r"\bbeat_%s\b" % re.escape(old)
        for name in os.listdir(folder):
            if name.endswith(".map"):
                self._rewrite(os.path.join(folder, name), lambda text: re.sub(word, "beat_" + new, text))
        story = os.path.join(self.root, "story")
        if os.path.isdir(story):
            for name in os.listdir(story):
                if name.endswith(".story"):
                    self._rewrite(os.path.join(story, name), lambda text: re.sub(word, "beat_" + new, text))

    def zones_of_map(self, name):
        """The zones a map's ground has, with the letters that are read from its legend."""
        try:
            import map_tool
            maps, _ = map_tool.load_all()
            m = maps[name]
        except (KeyError, ImportError, OSError, ValueError) as e:
            return []
        except Exception:
            return []
        return sorted({m.legend[letter]["zone"] for row in m.rows for letter in row if m.legend[letter]["zone"]})

    def marker_cell(self, name, marker):
        """Where a marker is: (column, row), or None."""
        try:
            import map_tool
            maps, _ = map_tool.load_all()
            map_tool.expand(maps, map_tool.read_objects_table())
            for o in maps[name].objects:
                if o["kind"] == "marker" and o["name"] == marker:
                    return int(o["col"]), int(o["row"])
        except Exception:
            pass
        return None

    def event_place(self, event):
        """Where an event's object stands: (map, column, row beside it), or None."""
        try:
            import map_tool
            maps, _ = map_tool.load_all()
            map_tool.expand(maps, map_tool.read_objects_table())
        except Exception:
            return None
        for name, m in maps.items():
            for o in m.objects:
                if o["props"].get("event") == event:
                    col, row = int(o["col"]), int(o["row"])
                    if o["kind"] == "trigger" and not m.solid_at(col, row):
                        return name, col, row
                    return (name,) + m.free_next_to(col, row, o["line"])       # beside it, not on top of it
        return None

    def playable_maps(self):
        """The maps with a hero: not the title, nor the backdrop of a battle."""
        text = self.main.text
        names = []
        for var, scene in re.findall(r'^(\w+)\s*=\s*game\.scene\("(\w+)"', text, re.M):
            if re.search(r"^%s\.add\(hero\(\)" % re.escape(var), text, re.M):
                names.append(scene)
        return names

    def world(self):
        """The maps and how they connect: {"maps", "places": {name: (x, y)}, "links", "start", "lost"}. None if a map is broken."""
        try:
            import map_tool
            maps, _ = map_tool.load_all()
            map_tool.expand(maps, map_tool.read_objects_table())
        except Exception:
            return None
        playable = [n for n in self.playable_maps() if n in maps] or sorted(maps)
        start = self.table("GameInfo").rows[0].get("start_map", "")
        if start not in playable:
            start = playable[0] if playable else ""
        links, side = [], {}
        for name in playable:
            m = maps[name]
            for o in m.objects:
                target = o["props"].get("to")
                if o["kind"] in ("warp", "door", "exit") and target in playable and target != name:
                    if (target, name) not in links and (name, target) not in links:
                        links.append((name, target))
                    side.setdefault((name, target), self._direction(m, o))
        for story_name, _, line in self._story_lines():
            hit = re.match(r"\s*warp\s+(\w+)\s", line)
            if hit and hit.group(1) in playable and start and (start, hit.group(1)) not in links:
                side.setdefault((start, hit.group(1)), (1, 1))
        reached, order, places = {start}, [start], {start: (0, 0)} if start else {}
        at = 0
        taken = set(places.values())
        while at < len(order):
            here = order[at]
            at += 1
            for a, b in links + [(y, x) for x, y in links]:
                if a == here and b not in reached:
                    reached.add(b)
                    order.append(b)
                    dx, dy = side.get((a, b), (1, 1))
                    x, y = places[a][0] + dx, places[a][1] + dy
                    while (x, y) in taken:
                        x += 1
                    places[b] = (x, y)
                    taken.add((x, y))
        lost = [n for n in playable if n not in reached]
        low = max((p[1] for p in places.values()), default=0) + 1
        for i, name in enumerate(lost):
            places[name] = (min((p[0] for p in places.values()), default=0) + i, low)
        return {"maps": maps, "places": places, "links": links, "start": start, "lost": lost}

    @staticmethod
    def _direction(m, o):
        """Which way the link leads, from where it is on the map."""
        col, row = o["col"], o["row"]
        if o["kind"] == "door":
            return 1, 1
        distances = [(row, (0, -1)), (len(m.rows) - 1 - row, (0, 1)), (col, (-1, 0)), (m.cols - 1 - col, (1, 0))]
        return min(distances, key=lambda d: d[0])[1]

    def forgotten(self):
        """What is probably a mistake, though nothing breaks: each with where to go."""
        out = []
        learned = {r.get("move") for s in self.table("Species").rows for r in s.get("learnset", [])}
        for m in self.table("Move").rows:
            if m["id"] not in learned:
                out.append(Use("Move %s: no monster learns it." % m["name"], "Move", m["id"]))
        story = list(self._story_lines())
        said = "\n".join(line for _, _, line in story)
        sold = {i for s in self.table("Shop").rows for i in s.get("items", [])}
        for i in self.table("Item").rows:
            if i["id"] not in sold and not re.search(r"^\s*give\s+%s\b" % re.escape(i["id"]), said, re.M):
                out.append(Use("Item %s: no shop sells it, and nobody gives it." % i["name"], "Item", i["id"]))
        info = self.table("GameInfo").rows[0]
        met = set(info.get("starters", []))
        met |= {r.get("species") for t in self.table("EncounterTable").rows for r in t.get("rows", [])}
        met |= {r.get("species") for t in self.table("Trainer").rows for r in t.get("team", [])}
        met |= {s.get("evolves_to") for s in self.table("Species").rows}
        for s in self.table("Species").rows:
            if s["id"] not in met and not re.search(r"^\s*give\s+monster\s+%s\b" % re.escape(s["id"]), said, re.M):
                out.append(Use("Monster %s: it never appears in the game." % s["name"], "Species", s["id"]))
            starts = [r for r in s.get("learnset", []) if r.get("level", 99) <= 1]
            if not starts and s.get("learnset"):
                out.append(Use("Monster %s: it knows no move at level 1, so at a low level it cannot fight." % s["name"], "Species", s["id"]))
            if not s.get("learnset"):
                out.append(Use("Monster %s: it has no moves." % s["name"], "Species", s["id"]))
            if s.get("evolves_to") and not s.get("evolve_level"):
                out.append(Use("Monster %s: it evolves into %s, but at no level." % (s["name"], s["evolves_to"]), "Species", s["id"]))
            given = {r.get("variant") for t in self.table("Trainer").rows for r in t.get("team", []) if r.get("species") == s["id"]}
            for v in s.get("variants", []):
                if not v.get("one_in") and v.get("id") not in given:
                    out.append(Use("Monster %s: its variant %s is never wild, and no trainer has it." % (s["name"], v.get("name") or v.get("id")), "Species", s["id"]))
        for t in self.table("Type").rows:
            if not any(t["id"] in s.get("types", []) for s in self.table("Species").rows):
                out.append(Use("Type %s: no monster has it." % t["name"], "Type", t["id"]))
        folder = os.path.join(self.root, "maps_src")
        map_text = ""
        for name in sorted(os.listdir(folder)):
            if name.endswith(".map"):
                with open(os.path.join(folder, name), encoding="utf-8") as fh:
                    map_text += fh.read()
        events = set(self.table("Event").ids())
        used = set(re.findall(r"\bevent=(\S+)", map_text)) | {info.get("first_event")}
        for t in self.table("Trainer").rows:
            on_map = re.search(r"^trainer\s+\S+\s+\S+\s+%s\b" % re.escape(t["id"]), map_text, re.M)
            if on_map:
                used.add("trainer." + t["id"])
            else:
                out.append(Use("Trainer %s: not on any map." % t["name"], "Trainer", t["id"]))
            if "trainer.%s" % t["id"] not in events:
                out.append(Use("Trainer %s: nothing in the story says what they do." % t["name"], "Trainer", t["id"]))
        for event in sorted(events - used):
            out.append(Use("Event %s: nothing on any map starts it." % event, "story_event", event))
        for s in self.table("Shop").rows:
            if not re.search(r"^\s*shop\s+%s\b" % re.escape(s["id"]), said, re.M):
                out.append(Use("Shop %s: no event opens it." % s["name"], "Shop", s["id"]))
        flags_read = set(re.findall(r"^\s*if\s+(?:not\s+)?(\w+)\s*:", said, re.M))
        flags_read |= set(re.findall(r"\b(?:hide_if|unless|flag)=(\S+)", map_text))
        flags_read |= set(re.findall(r"^\s*once\s+(\w+)\s*:", said, re.M))
        for flag in sorted(set(re.findall(r"^\s*set\s+(\w+)", said, re.M)) - flags_read):
            out.append(Use("Flag %s: it is set, but nothing ever asks about it." % flag, "story_flag", flag))
        world = self.world()
        if world is not None:
            for name in world["lost"]:
                out.append(Use("Map %s: there is no way to get there." % name, "maps", name))
        for row in self.table("EncounterTable").rows:
            name, _, zone = row["id"].partition(".")
            if name not in self.map_names() or zone not in self.zones_of_map(name):
                out.append(Use("Wild monsters %s: there is no such ground." % row["id"], "EncounterTable", row["id"]))
        used_effects = {m.get("effect") for m in self.table("Move").rows}
        for e in self.table("Effect").rows:
            if e["id"] not in used_effects:
                out.append(Use("Effect %s: no move has it." % e["name"], "Effect", e["id"]))
        caused = {e.get("status") for e in self.table("Effect").rows}
        for st in self.table("Status").rows:
            if st["id"] not in caused:
                out.append(Use("Status %s: no effect gives it." % st["name"], "Status", st["id"]))
        texts = set(self.table("Words").ids())
        for key in sorted(self.words_in_code() - texts):
            out.append(Use("Words %s: the game asks for them, and data/texts.json does not have them, so the id itself is shown." % key, "Words", ""))
        return out

    def markers_of_map(self, name):
        try:
            import map_tool
            maps, _ = map_tool.load_all()
            map_tool.expand(maps, map_tool.read_objects_table())
            return sorted({o["name"] for o in maps[name].objects if o["kind"] == "marker" and o["name"]})
        except Exception:
            return []

    def _rename_in_story(self, cls, old, new):
        folder = os.path.join(self.root, "story")
        patterns = self.STORY_WORDS.get(cls, [])
        if not patterns or not os.path.isdir(folder):
            return
        for name in os.listdir(folder):
            if name.endswith(".story"):
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
                changed = text
                for pattern in patterns:
                    changed = re.sub(pattern % re.escape(old), lambda m: m.group(1) + new, changed, flags=re.M)
                if changed != text:
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(changed)

    def forget_sprite(self, row_id):
        if os.path.isfile(self.sprite(row_id)):
            os.remove(self.sprite(row_id))

    # ── images ──
    def draw_sprite(self, row_id, variant=""):
        """A placeholder for a monster (or one of its variants) that has no picture yet, the same one the build would draw.
        Your picture is never replaced."""
        path = self.sprite(row_id, variant)
        if os.path.isfile(path):
            return path
        import make_art
        from PIL import Image
        if variant and variant != "default":
            with Image.open(self.draw_sprite(row_id)) as img:
                make_art.variant_sheet(img, variant).save(path)
            return path
        row = self.table("Species").get(row_id) or {}
        kind = self.table("Type").get((row.get("types") or [""])[0]) or {}
        hex_colour = (kind.get("color") or "#909090").lstrip("#")
        colour = tuple(int(hex_colour[i:i + 2], 16) for i in (0, 2, 4))
        sheet = Image.new("RGBA", (128, 64), (0, 0, 0, 0))
        sheet.paste(make_art.monster(row_id, colour, False), (0, 0))
        sheet.paste(make_art.monster(row_id, colour, True), (64, 0))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        sheet.save(path)
        return path

    def import_sprite(self, row_id, path):
        """Your picture becomes this monster's sheet: 64 x 64 cells, front then back."""
        from PIL import Image
        with Image.open(path) as img:
            size = img.size
            if size[0] < 128 or size[1] < 64 or size[0] % 64 or size[1] % 64:
                raise ValueError("That picture is %d x %d. It has to be made of cells of 64 x 64: at least its front and its back, so 128 x 64." % size)
            img.convert("RGBA").save(self.sprite(row_id))


# ── copies of the project ──

def backup_folder(root=ROOT):
    return _data.backup_folder(root)


def fingerprint(root=ROOT):
    return _data.fingerprint(root, PLAN)


def list_backups(root=ROOT):
    return _data.list_backups(root)


def make_backup(reason="", root=ROOT):
    """A copy of what you made, unless the newest copy is already the same. Keeps the last ones. Gives back its name, or ""."""
    return _data.make_backup(reason, root, PLAN)


def restore_backup(name, root=ROOT):
    """Puts that copy back, after making a copy of how things are now."""
    _data.restore_backup(name, root, PLAN, after=forget_made_maps)


def forget_made_maps(root=ROOT):
    """A maps/*.tmj that tools/map_tool.py made from a .map that is no longer there (a map renamed or deleted, then a copy put back).
    One made in Tiled, with no .map, stays."""
    folder = os.path.join(root, "maps")
    if not os.path.isdir(folder):
        return
    for name in os.listdir(folder):
        if name.endswith(".tmj") and not os.path.isfile(os.path.join(root, "maps_src", name[:-4] + ".map")):
            try:
                with open(os.path.join(folder, name), encoding="utf-8") as fh:
                    marks = {p["name"] for p in json.load(fh).get("properties", [])}
            except (OSError, ValueError, KeyError, TypeError):
                continue
            if "made_by_map_tool" in marks:
                os.remove(os.path.join(folder, name))
