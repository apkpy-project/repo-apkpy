"""What the Studio knows about a project, with no window: the shape of its data, the data, where things are used, and
copies of the project.

The shape comes from the game's @dataclass records (game/data/defs.py, or any module of game/ that has them), read
but not run, so a new field shows up in the forms by itself, and a broken data file does not stop the Studio from
opening. A field's help is the comment at the end of its line.

By Ruben Rego (the monster-rpg template's Studio), shared by every game's Studio. The monster-rpg template adds what
only it needs in its tools/studio_data.py.
"""
import ast
import copy
import hashlib
import json
import os
import re
import shutil
import time

BACKUPS = ".studio_backups"
KEEP_BACKUPS = 20
SCHEMA = os.path.join("game", "data", "defs.py")


class Spec:
    """A field's kind: str, int, float, bool, ref (to a table's row), list, optional, or record (another class)."""

    def __init__(self, kind, target=None, item=None):
        self.kind, self.target, self.item = kind, target, item


def parse_type(text):
    text = text.strip().strip('"')
    m = re.fullmatch(r"(?:list|List)\[(.*)\]", text)
    if m:
        return Spec("list", item=parse_type(m.group(1)))
    m = re.fullmatch(r"Optional\[(.*)\]", text)
    if m:
        return Spec("optional", item=parse_type(m.group(1)))
    m = re.fullmatch(r"Ref\[(.*)\]", text)
    if m:
        return Spec("ref", target=m.group(1).strip().strip('"'))
    if text in ("str", "int", "float", "bool"):
        return Spec(text)
    return Spec("record", target=text)


class Field:
    def __init__(self, name, spec, required, default, help=""):
        self.name, self.spec, self.required, self.default, self.help = name, spec, required, default, help


class RecordClass:
    def __init__(self, name, doc, fields):
        self.name, self.doc, self.fields = name, doc, fields

    def field(self, name):
        return next(f for f in self.fields if f.name == name)


def annotation_text(node, source):
    """A type as written in the file, such as list[Ref[Move]]. Python 3.8 has no ast.unparse: then it is the text of the file."""
    if hasattr(ast, "unparse"):
        return ast.unparse(node)
    return " ".join(ast.get_source_segment(source, node).split())


def line_comment(line):
    """The words after # at the end of a line of code (a # inside quotes is not one)."""
    quote = None
    for i, c in enumerate(line):
        if quote:
            if c == quote:
                quote = None
        elif c in "'\"":
            quote = c
        elif c == "#":
            return line[i + 1:].strip()
    return ""


def schema_files(root):
    """game/data/defs.py first (the monster-rpg template keeps every record there), then the other modules of game/."""
    first = os.path.join(root, SCHEMA)
    out = [first] if os.path.isfile(first) else []
    folder = os.path.join(root, "game")
    for d, dirs, names in os.walk(folder):
        dirs[:] = sorted(x for x in dirs if x not in ("__pycache__", "tests"))
        for name in sorted(names):
            path = os.path.join(d, name)
            if name.endswith(".py") and os.path.normcase(path) != os.path.normcase(first):
                out.append(path)
    return out


def _is_record(node, whole_file):
    """A record is a @dataclass. In game/data/defs.py every class is one (the template's rule)."""
    if whole_file:
        return True
    for d in node.decorator_list:
        name = d.func if isinstance(d, ast.Call) else d
        if getattr(name, "id", "") == "dataclass" or getattr(name, "attr", "") == "dataclass":
            return True
    return False


def read_schema(root, paths=None):
    """({class name: RecordClass}, {class name: data path}) from the game's records. Empty if the game has none.
    paths: only these files (the monster RPG reads only game/data/defs.py)."""
    classes, tables = {}, {}
    defs = os.path.normcase(os.path.join(root, SCHEMA))
    for path in schema_files(root) if paths is None else paths:
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        if os.path.normcase(path) != defs and "dataclass" not in source and "table(" not in source:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        lines = source.splitlines()
        whole = os.path.normcase(path) == defs
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and _is_record(node, whole):
                fields = []
                for stmt in node.body:
                    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                        required, default = stmt.value is None, None
                        if isinstance(stmt.value, ast.Constant):
                            default = stmt.value.value
                        elif isinstance(stmt.value, ast.Call):
                            default = []        # field(default_factory=list)
                        end = getattr(stmt, "end_lineno", stmt.lineno)
                        fields.append(Field(stmt.target.id, parse_type(annotation_text(stmt.annotation, source)), required, default,
                                            line_comment(lines[end - 1]) if end <= len(lines) else ""))
                classes.setdefault(node.name, RecordClass(node.name, ast.get_docstring(node) or "", fields))
            elif (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and getattr(node.value.func, "id", "") == "table"
                  and len(node.value.args) == 2 and isinstance(node.value.args[0], ast.Constant) and isinstance(node.value.args[1], ast.Name)):
                tables.setdefault(node.value.args[1].id, node.value.args[0].value)
    return classes, tables


def blank_value(project, spec):
    if spec.kind == "int":
        return 0
    if spec.kind == "float":
        return 0.0
    if spec.kind == "bool":
        return False
    if spec.kind == "list":
        return []
    if spec.kind == "optional":
        return None
    if spec.kind == "record":
        return project.blank_row(spec.target)
    return ""


class Table:
    """A data table, as the game's build reads it: a file holding a list, or a folder with one row per file."""

    def __init__(self, root, path, cls):
        self.root, self.path, self.cls = root, path, cls
        self.rows = []
        self.files = {}
        self.load()

    def load(self):
        self.rows, self.files = [], {}
        folder = os.path.join(self.root, self.path)
        self.is_folder = os.path.isdir(folder)
        if self.is_folder:
            for name in sorted(os.listdir(folder)):
                if name.endswith(".json") and not name.startswith("_"):
                    with open(os.path.join(folder, name), encoding="utf-8") as fh:
                        row = json.load(fh)
                    self.rows.append(row)
                    self.files[row["id"]] = os.path.join(folder, name)
        else:
            with open(folder + ".json", encoding="utf-8") as fh:
                self.rows = json.load(fh)
        self.saved = copy.deepcopy(self.rows)

    def ids(self):
        return [r["id"] for r in self.rows]

    def get(self, row_id):
        return next((r for r in self.rows if r["id"] == row_id), None)

    @property
    def dirty(self):
        return self.rows != self.saved

    def save(self):
        """Writes only what changed."""
        if not self.dirty:
            return
        if self.is_folder:
            old = {r["id"]: r for r in self.saved}
            now = {r["id"] for r in self.rows}
            for row in self.rows:
                if old.get(row["id"]) != row:
                    path = self.files.get(row["id"]) or os.path.join(self.root, self.path, row["id"] + ".json")
                    self.files[row["id"]] = path
                    write_json(path, row)
            for row_id in old:
                if row_id not in now:
                    path = self.files.pop(row_id, None)
                    if path and os.path.isfile(path):
                        os.remove(path)
        else:
            write_json(os.path.join(self.root, self.path + ".json"), self.rows)
        self.saved = copy.deepcopy(self.rows)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def readable(name):
    return name.replace("_", " ").capitalize()


class Use:
    """A place where a row is named."""

    def __init__(self, text, section="", target=""):
        self.text, self.section, self.target = text, section, target


class AppFile:
    """The game's name and version, in apkpy.toml, and the name in game/main.py."""

    def __init__(self, root):
        self.root = root
        self.rename_game = True          # the Studio of a kit writes the name into Game("...") itself here
        self.load()

    def load(self):
        with open(os.path.join(self.root, "apkpy.toml"), encoding="utf-8") as fh:
            text = fh.read()
        self.values = {}
        for key in ("name", "application_id", "version_name", "version_code", "icon"):
            m = re.search(r'^%s\s*=\s*"?([^"\n]*)"?\s*$' % key, text, re.M)
            self.values[key] = m.group(1) if m else ""
        self.saved = dict(self.values)

    @property
    def dirty(self):
        return self.values != self.saved

    def save(self):
        if not self.dirty:
            return
        path = os.path.join(self.root, "apkpy.toml")
        with open(path, encoding="utf-8", newline="") as fh:
            text = fh.read()
        newline = "\r\n" if "\r\n" in text else "\n"
        text = text.replace("\r\n", "\n")
        for key, value in self.values.items():
            quoted = value if key == "version_code" else '"%s"' % value.replace('"', "")
            if key == "icon" and not value:
                text = re.sub(r'^icon\s*=.*\n?', "", text, count=1, flags=re.M)
            elif re.search(r'^%s\s*=' % key, text, re.M):
                text = re.sub(r'^%s\s*=.*$' % key, lambda m: "%s = %s" % (key, quoted), text, count=1, flags=re.M)
            elif value:
                text = re.sub(r'^(\[app\]\s*\n)', lambda m: m.group(1) + "%s = %s\n" % (key, quoted), text, count=1, flags=re.M)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text.replace("\n", newline))
        if self.rename_game and self.values["name"] != self.saved["name"]:
            path = os.path.join(self.root, "game", "main.py")
            with open(path, encoding="utf-8", newline="") as fh:
                text = fh.read()
            text = re.sub(r'Game\("[^"]*"', lambda m: 'Game("%s"' % self.values["name"].replace('"', ""), text, count=1)
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
        self.saved = dict(self.values)


def copy_sound(root, source, path):
    """Puts a sound where path says, with its own kind of ending. Gives back the path it ended up at."""
    ending = os.path.splitext(source)[1].lower()
    if ending not in (".wav", ".ogg", ".mp3"):
        raise ValueError("The game plays WAV, OGG and MP3. This is %s." % (ending or "something else"))
    new = os.path.splitext(path)[0] + ending
    target = os.path.join(root, *new.split("/"))
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if os.path.abspath(source) != os.path.abspath(target):
        shutil.copyfile(source, target)
    if new != path and os.path.isfile(os.path.join(root, *path.split("/"))):
        os.remove(os.path.join(root, *path.split("/")))
    return new


class DataProject:
    """A game's data tables and its apkpy.toml. A kit (tools/studio_kit.py) extends it with what only its game has."""

    CHOICES = {}          # (class, field): values a text field usually has
    HELP = {}             # (class, field): words under a field, instead of the comment of its line
    WORDS = {}            # field name: its label
    WHO = {}              # class: how a row of it is named in "Where it is used"
    NO_USES = ()          # classes whose rows are not named anywhere (no "Where it is used")
    ID_EXAMPLE = "big_slime"

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.classes, self.paths = self.read_schema()
        self.tables = {}
        self.broken = {}
        self.app = AppFile(self.root)
        for cls, path in self.paths.items():
            self.load_table(cls, path)

    def read_schema(self):
        return read_schema(self.root)

    def make_table(self, cls, path):
        return Table(self.root, path, cls)

    def load_table(self, cls, path):
        try:
            self.tables[cls] = self.make_table(cls, path)
            self.broken.pop(cls, None)
        except (OSError, ValueError, KeyError, TypeError) as e:
            self.broken[cls] = "%s: %s" % (path, e)

    def reload(self):
        self.classes, self.paths = self.read_schema()
        self.app.load()
        for cls, path in self.paths.items():
            self.load_table(cls, path)

    # ── words for the forms ──

    def label(self, name):
        return self.WORDS.get(name) or readable(name)

    def help(self, cls, name):
        if (cls, name) in self.HELP:
            return self.HELP[(cls, name)]
        record = self.classes.get(cls)
        f = next((x for x in record.fields if x.name == name), None) if record else None
        return f.help if f else ""

    def choices(self, cls, name):
        return self.CHOICES.get((cls, name))

    def id_pattern(self, cls):
        return r"[a-z][a-z0-9_]*"

    # ── the icon ──

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

    # ── rows ──

    def table(self, cls):
        return self.tables[cls]

    def blank_row(self, cls):
        row = {}
        for f in self.classes[cls].fields:
            row[f.name] = f.default if not f.required else blank_value(self, f.spec)
            if isinstance(row[f.name], list):
                row[f.name] = []
        return row

    def new_row(self, cls, name, row_id=None):
        """A row that works from the start. The id comes from the name, and is unique."""
        table = self.table(cls)
        base = row_id or slug(name) or cls.lower()
        row_id, n = base, 2
        while row_id in table.ids():
            row_id, n = "%s_%d" % (base, n), n + 1
        row = self.blank_row(cls)
        row["id"] = row_id
        if "name" in row:
            row["name"] = name
        self.fill_new_row(cls, row, name)
        table.rows.append(row)
        return row

    def fill_new_row(self, cls, row, name):
        """Good starting values for a new row: here, a reference names the first row it can. A kit has its own."""
        for f in self.classes[cls].fields:
            if f.spec.kind == "ref" and not row.get(f.name) and f.spec.target in self.tables:
                ids = self.tables[f.spec.target].ids()
                row[f.name] = ids[0] if ids else ""

    def copy_row(self, cls, row):
        table = self.table(cls)
        new = copy.deepcopy(row)
        base, n = row["id"] + "_copy", 2
        new["id"] = base
        while new["id"] in table.ids():
            new["id"], n = "%s_%d" % (base, n), n + 1
        table.rows.insert(table.rows.index(row) + 1, new)
        return new

    @property
    def dirty(self):
        return self.app.dirty or any(t.dirty for t in self.tables.values())

    def save(self):
        self.app.save()
        for table in self.tables.values():
            table.save()

    # ── is a row right? ──

    def row_problems(self, cls, row):
        out = []
        self._check(self.classes[cls], row, "", out)
        return out

    def _check(self, cls, row, where, out):
        for f in cls.fields:
            label = where + f.name
            value = row.get(f.name)
            if f.name not in row:
                if f.required:
                    out.append("%s is missing." % label)
                continue
            self._check_value(f.spec, value, label, out)

    def _check_value(self, spec, value, label, out):
        if spec.kind == "optional":
            if value is not None:
                self._check_value(spec.item, value, label, out)
        elif spec.kind == "ref":
            table = self.tables.get(spec.target)
            if table is not None and value not in table.ids():
                out.append("%s: there is no %r." % (label, value))
        elif spec.kind == "int" and not isinstance(value, int):
            out.append("%s has to be a whole number." % label)
        elif spec.kind == "list" and isinstance(value, list):
            for i, item in enumerate(value):
                self._check_value(spec.item, item, "%s %d" % (label, i + 1), out)
        elif spec.kind == "record" and isinstance(value, dict):
            self._check(self.classes[spec.target], value, label + " ", out)

    # ── where is it used? ──

    def _refs(self, spec, value, target, path=""):
        """The values inside a value that name a row of target."""
        found = []
        if spec.kind == "optional" and value is not None:
            return self._refs(spec.item, value, target)
        if spec.kind == "ref" and spec.target == target:
            found.append(value)
        elif spec.kind == "list" and isinstance(value, list):
            for item in value:
                found += self._refs(spec.item, item, target)
        elif spec.kind == "record" and isinstance(value, dict):
            for f in self.classes[spec.target].fields:
                found += self._refs(f.spec, value.get(f.name), target)
        return found

    def _replace(self, spec, value, target, old, new):
        if spec.kind == "optional":
            return None if value is None else self._replace(spec.item, value, target, old, new)
        if spec.kind == "ref":
            return new if spec.target == target and value == old else value
        if spec.kind == "list" and isinstance(value, list):
            return [self._replace(spec.item, item, target, old, new) for item in value]
        if spec.kind == "record" and isinstance(value, dict):
            for f in self.classes[spec.target].fields:
                if f.name in value:
                    value[f.name] = self._replace(f.spec, value[f.name], target, old, new)
        return value

    def uses(self, cls, row_id):
        """Everywhere this row is named, apart from its own row."""
        out = []
        for other, table in self.tables.items():
            if other not in self.classes:
                continue
            for row in table.rows:
                if other == cls and row["id"] == row_id:
                    continue
                count = 0
                for f in self.classes[other].fields:
                    count += sum(1 for v in self._refs(f.spec, row.get(f.name), cls) if v == row_id)
                if count:
                    what = self.WHO.get(other, self.label(other).lower())
                    out.append(self.use_text(other, what, row))
        self.more_uses(cls, row_id, out)
        return out

    def use_text(self, cls, what, row):
        return Use("%s: %s" % (what, row.get("name") or row["id"]), cls, row["id"])

    def more_uses(self, cls, row_id, out):
        """A kit's other places where a row is named (its story, its maps...)."""

    def rename(self, cls, old, new):
        """Changes an id everywhere. Save everything first: this works on the files."""
        if not re.fullmatch(self.id_pattern(cls), new):
            raise ValueError("An id is lowercase letters, numbers and _, such as %s." % self.ID_EXAMPLE)
        table = self.table(cls)
        if new in table.ids():
            raise ValueError("There is already a %s called %s." % (cls.lower(), new))
        row = table.get(old)
        row["id"] = new
        for other, t in self.tables.items():
            if other not in self.classes:
                continue
            for r in t.rows:
                for f in self.classes[other].fields:
                    if f.name in r:
                        r[f.name] = self._replace(f.spec, r[f.name], cls, old, new)
        self.rename_in_rows(cls, old, new)
        if table.is_folder and old in table.files:
            path = table.files.pop(old)
            table.files[new] = os.path.join(os.path.dirname(path), new + ".json")
            write_json(table.files[new], row)
            os.remove(path)
            for saved in table.saved:
                if saved["id"] == old:
                    saved["id"] = new
        self.save()
        self.after_rename(cls, old, new, row)

    def rename_in_rows(self, cls, old, new):
        """A kit's own lists of ids, changed before saving."""

    def after_rename(self, cls, old, new, row):
        """A kit's own files that name the row (its story, maps, pictures), changed after saving."""

    @staticmethod
    def _rewrite(path, change):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        new = change(text)
        if new != text:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new)

    def delete(self, cls, row_id):
        """Takes the row away, unless something uses it: then gives back what does."""
        used = self.uses(cls, row_id)
        if used:
            return used
        table = self.table(cls)
        table.rows.remove(table.get(row_id))
        return []


# ── copies of the project ──

class BackupPlan:
    """What a copy holds: whole folders, the files of the assets folder with these endings (no bigger than largest
    bytes, if given), and single files."""

    def __init__(self, whole=("game", "data", "levels", "maps", "maps_src", "story"), assets="assets",
                 endings=(".png", ".jpg", ".jpeg", ".webp", ".gif", ".fnt", ".ttf", ".otf", ".tmj", ".tsj", ".json", ".txt",
                          ".wav", ".ogg", ".mp3"),
                 files=("apkpy.toml", "icon.png", "writehere.py"), largest=1000000):
        self.whole, self.assets, self.endings, self.files, self.largest = tuple(whole), assets, tuple(endings), tuple(files), largest


EVERY_GAME = BackupPlan()


def backup_folder(root):
    return os.path.join(root, BACKUPS)


def project_files(root, plan=EVERY_GAME):
    for folder in plan.whole + ((plan.assets,) if plan.assets else ()):
        for d, dirs, names in os.walk(os.path.join(root, folder)):
            dirs[:] = sorted(x for x in dirs if x != "__pycache__")
            for name in sorted(names):
                path = os.path.join(d, name)
                if folder == plan.assets and folder not in plan.whole:
                    if not name.lower().endswith(plan.endings):
                        continue
                    if plan.largest and os.path.getsize(path) > plan.largest:
                        continue
                if name.endswith(".pyc"):
                    continue
                yield os.path.relpath(path, root)
    for name in plan.files:
        if os.path.isfile(os.path.join(root, name)):
            yield os.path.normpath(name)


def fingerprint(root, plan=EVERY_GAME):
    digest = hashlib.sha256()
    for rel in sorted(project_files(root, plan)):
        digest.update(rel.replace("\\", "/").encode("utf-8"))
        with open(os.path.join(root, rel), "rb") as fh:
            digest.update(fh.read())
    return digest.hexdigest()


def list_backups(root):
    folder = backup_folder(root)
    if not os.path.isdir(folder):
        return []
    return sorted((n for n in os.listdir(folder) if os.path.isdir(os.path.join(folder, n))), reverse=True)


def make_backup(reason, root, plan=EVERY_GAME):
    """A copy of what you made, unless the newest copy is already the same. Keeps the last ones. Gives back its name, or ""."""
    found = list_backups(root)
    print_now = fingerprint(root, plan)
    if found:
        mark = os.path.join(backup_folder(root), found[0], "fingerprint.txt")
        if os.path.isfile(mark):
            with open(mark, encoding="utf-8") as fh:
                if fh.read().strip() == print_now:
                    return ""
    now = time.time()
    name, n = time.strftime("%Y-%m-%d_%H%M%S", time.localtime(now)) + "%03d" % (int(now * 1000) % 1000), 2      # so names sort by time
    while os.path.isdir(backup_folder(root)) and any(x.startswith(name) for x in os.listdir(backup_folder(root))):
        now += 0.001
        name = time.strftime("%Y-%m-%d_%H%M%S", time.localtime(now)) + "%03d" % (int(now * 1000) % 1000)
    if reason:
        name += "_" + slug(reason)
    target, base = os.path.join(backup_folder(root), name), name
    while os.path.exists(target):
        name, n = "%s_%d" % (base, n), n + 1
        target = os.path.join(backup_folder(root), name)
    for rel in project_files(root, plan):
        out = os.path.join(target, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.copy2(os.path.join(root, rel), out)
    os.makedirs(target, exist_ok=True)
    with open(os.path.join(target, "fingerprint.txt"), "w", encoding="utf-8") as fh:
        fh.write(print_now)
    for old in list_backups(root)[KEEP_BACKUPS:]:
        shutil.rmtree(os.path.join(backup_folder(root), old), ignore_errors=True)
    return name


def backup_label(name):
    """2026-11-06_211424123_before_saving becomes 2026-11-06 21:14:24, before saving."""
    m = re.match(r"(\d{4}-\d\d-\d\d)_(\d\d)(\d\d)(\d\d)\d*_?(.*)", name)
    if not m:
        return name
    words = m.group(5).replace("_", " ")
    return "%s %s:%s:%s%s" % (m.group(1), m.group(2), m.group(3), m.group(4), ", " + words if words else "")


def restore_backup(name, root, plan=EVERY_GAME, after=None):
    """Puts that copy back, after making a copy of how things are now."""
    source = os.path.join(backup_folder(root), name)
    if not os.path.isdir(source):
        raise ValueError("There is no copy called %s." % name)
    make_backup("before restoring", root, plan)
    for folder in plan.whole:
        shutil.rmtree(os.path.join(root, folder), ignore_errors=True)
    for d, _, names in os.walk(source):
        for n in names:
            if n == "fingerprint.txt":
                continue
            rel = os.path.relpath(os.path.join(d, n), source)
            out = os.path.join(root, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            shutil.copy2(os.path.join(d, n), out)
    if after is not None:
        after(root)
