"""The map editor: paint maps with the mouse, with each map in its own tab.

    python tools/map_editor.py              the list of maps is on the left: click one to open it
    python tools/map_editor.py village      opens that map too

It reads and writes maps_src/<name>.map, so you can go back and forth with a text editor.

    B  brush       F  fill          R  rectangle       V  select and move objects      A  select an area
    Ctrl+C, Ctrl+X, Ctrl+V     copy, cut and paste an area, between maps too
    Height                     pick a tile and a height to paint 3D blocks
    Right click                a menu: use this tile, add an object, test the game from here
    Double click a door        opens the map it leads to
    Ctrl+Z, Ctrl+Y             undo, redo (each tab has its own)
    Ctrl+S, Ctrl+Shift+S       save this map, save all
    Ctrl+D, Delete             copy, delete the selected object
    Ctrl+wheel, + and -        zoom.  Wheel: scroll.  Middle button: drag the map.
"""
import copy
import io
import json
import os
import re
import subprocess
import sys
import tkinter as tk
from tkinter import colorchooser, messagebox, simpledialog, ttk

from PIL import Image, ImageTk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import map_tool  # noqa: E402
import story_editor  # noqa: E402
import studio_ui  # noqa: E402
from studio_ui import px  # noqa: E402

TILE = map_tool.TILE
SESSION_FILE = os.path.join(ROOT, "build", "map_editor_session.json")
FACING = ["down", "left", "up", "right"]
# what each kind of object usually says: the editor offers these as fields
FIELDS = {
    "person": ["look", "event", "facing", "hide_if"], "trainer": ["look", "facing", "sight"], "link": ["width", "height"],
    "exit": ["width", "height", "to", "at"], "trigger": ["event", "unless", "width", "height"], "warp": ["to", "at", "width", "height"],
    "door": ["to", "at", "event"], "sign": ["event"], "knot": ["event", "hide_if"],
}
BUILDING_FIELDS = ["inside", "event"]
NAME_HINT = {"link": "the map it goes to", "trainer": "who, from data/trainers.json", "marker": "its name", "person": "any name", "trigger": "any name"}
HELP = {
    "person": "Someone to talk to. event: what happens. look: a picture from assets/people/.",
    "trainer": "Sees you along their line and fights. Write what they say in a story file, in a  trainer NAME  block.",
    "link": "Stepping here goes to another map, which needs a link back here. width repeats it over several cells.",
    "exit": "The way out of a room that a building leads to. You walk against it.",
    "trigger": "An event when you step here. unless: with that flag set, it is as if it were not there.",
    "marker": "A named spot for arriving at. Links and buildings make their own.",
    "warp": "Stepping here goes to to=map, at=marker. A link is usually simpler.",
    "door": "Walk against it to go to to=map, at=marker, or to play event=. A building makes its own.",
    "sign": "Something to read: an event.",
    "knot": "Something to pick up: an event. hide_if: gone once that flag is set.",
    "tree": "Scenery.",
    "lighthouse": "Scenery.",
}
BUILDING_HELP = "A building, by its top left corner. inside: the map you enter, or event: what its door plays. Its door is the cell in the middle of its front."


class MapDoc:
    """A .map file as something to change: no window here."""

    def __init__(self, name, text=None):
        self.name = name
        self.path = os.path.join(map_tool.SOURCE, name + ".map")
        self.names = map_tool.tile_names()
        self.base_legend = map_tool.read_legend(self.names)
        if text is None:
            with open(self.path, encoding="utf-8") as fh:
                text = fh.read()
        self.load_text(text)

    def load_text(self, text):
        self.legend = dict(self.base_legend)
        self.header, self.rows, self.objects = [], [], []
        part = "head"
        for raw in io.StringIO(text):
            line = raw.rstrip("\n")
            stripped = line.strip()
            if stripped == "tiles:":
                part = "tiles"
            elif stripped == "objects:":
                part = "objects"
            elif part == "head":
                if stripped.startswith("size:"):
                    continue
                self.header.append(line)
                if " = " in line and not stripped.startswith("#"):
                    letter, entry = map_tool.legend_line(line, self.name, self.names)
                    self.legend[letter] = entry
            elif part == "tiles":
                if stripped:
                    self.rows.append(list(stripped))
            elif stripped:
                self.objects.append(self.parse_object(stripped))
        if not self.rows:
            raise map_tool.MapError("%s.map has no drawing under 'tiles:'" % self.name)
        for number, row in enumerate(self.rows):
            if len(row) != len(self.rows[0]):
                raise map_tool.MapError("%s.map: row %d has %d letters, and the first has %d. Fix it in a text editor first." % (self.name, number, len(row), len(self.rows[0])))
            for letter in row:
                if letter not in self.legend:
                    raise map_tool.MapError("%s.map: the letter %r is not in maps_src/legend.txt" % (self.name, letter))

    @staticmethod
    def parse_object(text):
        words = text.split(" #")[0].split()
        if text.startswith("#") or len(words) < 3:
            return {"comment": text}
        try:
            o = {"kind": words[0], "col": float(words[1]), "row": float(words[2]), "name": "", "props": {}}
        except ValueError:
            return {"comment": text}
        for word in words[3:]:
            if "=" in word:
                k, v = word.split("=", 1)
                o["props"][k] = v
            else:
                o["name"] = word
        return o

    @staticmethod
    def object_line(o):
        if "comment" in o:
            return o["comment"]
        number = lambda v: str(int(v)) if float(v).is_integer() else str(v)
        words = [o["kind"], number(o["col"]), number(o["row"])]
        if o["name"]:
            words.append(o["name"])
        words += ["%s=%s" % (k, v) for k, v in o["props"].items() if v != ""]
        return " ".join(words)

    @property
    def cols(self):
        return len(self.rows[0])

    def inside(self, col, row):
        return 0 <= row < len(self.rows) and 0 <= col < self.cols

    def paint(self, col, row, letter):
        if self.inside(col, row) and self.rows[row][col] != letter:
            self.rows[row][col] = letter
            return True
        return False

    def fill(self, col, row, letter):
        """Every connected cell with the same letter. Gives back the cells that changed."""
        if not self.inside(col, row) or self.rows[row][col] == letter:
            return []
        old = self.rows[row][col]
        changed, todo = [], [(col, row)]
        while todo:
            c, r = todo.pop()
            if self.inside(c, r) and self.rows[r][c] == old:
                self.rows[r][c] = letter
                changed.append((c, r))
                todo += [(c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)]
        return changed

    def rectangle(self, c0, r0, c1, r1, letter):
        changed = []
        for r in range(min(r0, r1), max(r0, r1) + 1):
            for c in range(min(c0, c1), max(c0, c1) + 1):
                if self.paint(c, r, letter):
                    changed.append((c, r))
        return changed

    def grow(self, side, letter):
        """One more row or column on that side: top, bottom, left or right. Objects stay where they are on the map."""
        if side == "bottom":
            self.rows.append([letter] * self.cols)
        elif side == "top":
            self.rows.insert(0, [letter] * self.cols)
            self.shift(0, 1)
        elif side == "right":
            for row in self.rows:
                row.append(letter)
        else:
            for row in self.rows:
                row.insert(0, letter)
            self.shift(1, 0)

    def shrink(self, side):
        """One row or column less on that side. Gives back the objects that were on it, which are gone."""
        tall, wide = len(self.rows), self.cols
        if (side in ("top", "bottom") and tall < 2) or (side in ("left", "right") and wide < 2):
            return []
        gone = []
        for o in self.objects:
            if "comment" in o:
                continue
            if (side == "top" and o["row"] < 1) or (side == "bottom" and o["row"] >= tall - 1) or (side == "left" and o["col"] < 1) or (side == "right" and o["col"] >= wide - 1):
                gone.append(o)
        self.objects = [o for o in self.objects if not any(o is g for g in gone)]
        if side == "bottom":
            self.rows.pop()
        elif side == "top":
            self.rows.pop(0)
            self.shift(0, -1)
        elif side == "right":
            for row in self.rows:
                row.pop()
        else:
            for row in self.rows:
                row.pop(0)
            self.shift(-1, 0)
        return gone

    def shift(self, dc, dr):
        for o in self.objects:
            if "comment" not in o:
                o["col"] += dc
                o["row"] += dr

    def add_object(self, kind, col, row):
        o = {"kind": kind, "col": col, "row": row, "name": "", "props": {}}
        self.objects.append(o)
        return o

    def copy_object(self, o):
        new = copy.deepcopy(o)
        new["col"] += 1
        self.objects.append(new)
        return new

    def copy_area(self, c0, r0, c1, r1):
        """A piece of the map, to paste anywhere: its letters and the objects whose corner is in it."""
        c0, c1, r0, r1 = min(c0, c1), max(c0, c1), min(r0, r1), max(r0, r1)
        rows = [row[c0:c1 + 1] for row in self.rows[r0:r1 + 1]]
        used = {letter for row in rows for letter in row}
        objects = []
        for o in self.objects:
            if "comment" not in o and c0 <= o["col"] <= c1 and r0 <= o["row"] <= r1:
                piece = copy.deepcopy(o)
                piece["col"] -= c0
                piece["row"] -= r0
                objects.append(piece)
        return {"rows": rows, "legend": {k: dict(self.legend[k]) for k in used}, "objects": objects}

    def clear_area(self, c0, r0, c1, r1, letter):
        """Paints it over, and takes away the objects whose corner is in it."""
        c0, c1, r0, r1 = min(c0, c1), max(c0, c1), min(r0, r1), max(r0, r1)
        self.objects = [o for o in self.objects if "comment" in o or not (c0 <= o["col"] <= c1 and r0 <= o["row"] <= r1)]
        return self.rectangle(c0, r0, c1, r1, letter)

    def paste_area(self, piece, col, row):
        """A letter this map does not have gets a line above its "tiles:". Gives back the cells that changed."""
        letters = {}
        for letter, entry in piece["legend"].items():
            mine = next((k for k, v in self.legend.items() if v == entry), None)
            if mine is None:
                mine = letter if letter not in self.legend else free_letter(self.legend)
                self.legend[mine] = dict(entry)
                self.header.append(entry_line(mine, entry))
            letters[letter] = mine
        changed = []
        for r, cells in enumerate(piece["rows"]):
            for c, letter in enumerate(cells):
                if self.paint(col + c, row + r, letters[letter]):
                    changed.append((col + c, row + r))
        for o in piece["objects"]:
            if self.inside(int(col + o["col"]), int(row + o["row"])):
                new = copy.deepcopy(o)
                new["col"] += col
                new["row"] += row
                self.objects.append(new)
        return changed

    def object_at(self, col, row, sizes):
        """The last object drawn over this cell."""
        for o in reversed(self.objects):
            if "comment" in o:
                continue
            width, depth = sizes.get(o["kind"]) or (1, 1)
            if o["col"] <= col < o["col"] + width and o["row"] <= row < o["row"] + depth:
                return o
        return None

    def object_on_line(self, number):
        """The object written on this line of the file (1 is the first)."""
        at = number - (len(self.header) + 1 + len(self.rows) + 1) - 1
        if 0 <= at < len(self.objects) and "comment" not in self.objects[at]:
            return self.objects[at]
        return None

    def text(self):
        lines = list(self.header) + ["tiles:"] + ["".join(r) for r in self.rows] + ["objects:"] + [self.object_line(o) for o in self.objects]
        return "\n".join(lines) + "\n"

    def save(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(self.text())

    def snapshot(self):
        return copy.deepcopy((self.header, self.rows, self.objects, self.legend))

    def restore(self, snap):
        self.header, self.rows, self.objects, self.legend = copy.deepcopy(snap)

    def problem(self, others=None):
        """What the map tool thinks of all the maps, with this one as it is now: "" when fine. Nothing is written."""
        return find_problem(dict(others or {}, **{self.name: self.text()}))


def entry_line(letter, entry):
    """The line of a legend for this letter."""
    words = [letter, "=", entry["tile"]]
    if entry["solid"]:
        words.append("solid")
    if entry["height"]:
        words.append("height=%d" % entry["height"])
    if entry["zone"]:
        words.append("zone=" + entry["zone"])
    if entry["edges"]:
        words.append("edges")
    return " ".join(words)


def free_letter(legend):
    for letter in "ABCDEFGHIJKLMNOPQTUVWXYZbdeghijklmnopqtvxyz0123456789!$%&*+-/;<>?@":
        if letter not in legend:
            return letter
    raise map_tool.MapError("There are no free letters left in the legend.")


def find_problem(texts):
    try:
        maps, _ = map_tool.load_all(texts)
        map_tool.expand(maps, map_tool.read_objects_table())
        return ""
    except map_tool.MapError as e:
        return str(e)


def create_map(name, width, height, ground, wall):
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise map_tool.MapError("%r: a map's name is lowercase letters, numbers and _, such as old_cave" % name)
    path = os.path.join(map_tool.SOURCE, name + ".map")
    if os.path.exists(path):
        raise map_tool.MapError("There is already a map called %s." % name)
    rows = [wall * width] + [wall + ground * (width - 2) + wall] * (height - 2) + [wall * width]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Describe this place here.\ntiles:\n" + "\n".join(rows) + "\nobjects:\n")


def all_maps():
    return sorted(n[:-4] for n in os.listdir(map_tool.SOURCE) if n.endswith(".map"))


def known_events():
    """The events of the story files and of data/events/, without building anything."""
    found = set()
    folder = os.path.join(ROOT, "story")
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            if name.endswith(".story"):
                with open(os.path.join(folder, name), encoding="utf-8") as fh:
                    for line in fh:
                        m = re.match(r"(event|trainer) +(\S+)", line)
                        if m:
                            found.add(m.group(2) if m.group(1) == "event" else "trainer." + m.group(2))
    folder = os.path.join(ROOT, "data", "events")
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            if name.endswith(".json") and not name.startswith("_"):
                try:
                    with open(os.path.join(folder, name), encoding="utf-8") as fh:
                        found.update(e["id"] for e in json.load(fh))
                except (ValueError, KeyError, TypeError):
                    pass
    return sorted(found)


def known_flags():
    found = set()
    folder = os.path.join(ROOT, "story")
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            if name.endswith(".story"):
                with open(os.path.join(folder, name), encoding="utf-8") as fh:
                    for line in fh:
                        m = re.match(r"\s*(set|once) +([\w]+)", line)
                        if m:
                            found.add(m.group(2))
                        m = re.match(r"trainer +(\S+)", line)
                        if m:
                            found.add("beat_" + m.group(1))
    return sorted(found)


def known_trainers():
    try:
        with open(os.path.join(ROOT, "data", "trainers.json"), encoding="utf-8") as fh:
            return sorted(t["id"] for t in json.load(fh))
    except (OSError, ValueError, KeyError, TypeError):
        return []


def known_looks():
    folder = os.path.join(ROOT, "assets", "people")
    return sorted(n[:-4] for n in os.listdir(folder) if n.endswith(".png")) if os.path.isdir(folder) else []


def start_test_here(map_name, col, row, save="", event=""):
    """The game reads this when the hero appears (Hero.on_start), and forgets it."""
    store = os.path.join(ROOT, "build", "apkpygame", "store.json")
    data = {}
    if os.path.isfile(store):
        try:
            with open(store, encoding="utf-8") as fh:
                data = json.load(fh)
        except ValueError:
            data = {}
    data.update({"editor_map": map_name, "editor_col": str(col), "editor_row": str(row), "editor_save": save, "editor_event": event})
    os.makedirs(os.path.dirname(store), exist_ok=True)
    with open(store, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


class Tab:
    """One open map."""
    area = None

    def __init__(self, editor, doc):
        self.doc = doc
        self.frame = tk.Frame(editor.notebook)
        self.canvas = tk.Canvas(self.frame, bg="#3a3f4a", highlightthickness=0)
        bar_y = tk.Scrollbar(self.frame, command=self.canvas.yview)
        bar_x = tk.Scrollbar(self.frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=bar_y.set, xscrollcommand=bar_x.set)
        bar_y.pack(side="right", fill="y")
        bar_x.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.saved = doc.text()
        self.undo = []
        self.redo = []
        self.selected = None
        self.items = {}
        self.mtime = os.path.getmtime(doc.path)

    @property
    def dirty(self):
        return self.doc.text() != self.saved


class Editor:
    def __init__(self, root, names=(), parent=None, shell=None):
        self.root = root
        self.parent = parent if parent is not None else root
        self.shell = shell
        self.tabs = []
        self.tool = "paint"
        self.place_kind = ""
        self.letter = None
        self.zoom = max(2, round(2 * px(root, 100) / 100))
        self.show_grid = tk.BooleanVar(value=True)
        self.show_solid = tk.BooleanVar(value=False)
        self.show_heights = tk.BooleanVar(value=True)
        self.height_var = tk.IntVar(value=0)
        self.solid_var = tk.BooleanVar(value=False)
        self.clip = None
        self.pasting = False
        self.area_start = None
        self.story = None
        self.preview = None
        self.images = {}
        self.fields = {}
        self.stroke = None
        self.rect_start = None
        self.check_job = None
        self.problem_at = None
        self.game = None
        self.table = map_tool.read_objects_table()
        self.sizes = {k: v for k, v in self.table.items() if v}
        if shell is None:
            root.title("Map editor")
            root.geometry("%dx%d" % (px(root, 1180), px(root, 720)))
            root.protocol("WM_DELETE_WINDOW", self.quit)
        self.build_window()
        self.bind_keys()
        root.bind("<FocusIn>", self.outside_changes, add="+")
        self.refresh_map_list()
        for name in names:
            self.open_map(name)
        if not self.tabs:
            for name in self.last_session():
                self.open_map(name, quiet=True)
        self.set_tool("paint")
        self.update_all()

    # ── the window ──

    def build_window(self):
        top = tk.Frame(self.parent, padx=4, pady=3)
        top.pack(side="top", fill="x")
        self.tool_buttons = {}
        for tool, text in (("paint", "Brush (B)"), ("fill", "Fill (F)"), ("rect", "Rectangle (R)"), ("select", "Select (V)"), ("area", "Area (A)")):
            button = tk.Button(top, text=text, relief="raised", command=lambda t=tool: self.set_tool(t))
            button.pack(side="left", padx=1)
            self.tool_buttons[tool] = button
        self.separator(top)
        tk.Button(top, text="Undo", command=self.do_undo).pack(side="left", padx=1)
        tk.Button(top, text="Redo", command=self.do_redo).pack(side="left", padx=1)
        self.separator(top)
        tk.Button(top, text="-", width=2, command=lambda: self.set_zoom(self.zoom - 1)).pack(side="left", padx=1)
        self.zoom_label = tk.Label(top, text="%d%%" % (self.zoom * 100), width=5)
        self.zoom_label.pack(side="left")
        tk.Button(top, text="+", width=2, command=lambda: self.set_zoom(self.zoom + 1)).pack(side="left", padx=1)
        tk.Checkbutton(top, text="Grid", variable=self.show_grid, command=self.redraw).pack(side="left", padx=(8, 0))
        tk.Checkbutton(top, text="Heights", variable=self.show_heights, command=self.redraw).pack(side="left")
        tk.Checkbutton(top, text="Solid", variable=self.show_solid, command=self.redraw).pack(side="left")
        if self.shell is None:
            tk.Button(top, text="Play the game", command=self.play_game).pack(side="right", padx=1)
        tk.Button(top, text="See in 3D", command=self.preview_center).pack(side="right", padx=1)
        if self.shell is None:
            tk.Button(top, text="Story", command=self.open_story).pack(side="right", padx=(1, 10))
            tk.Button(top, text="Save all", command=self.save_all).pack(side="right", padx=1)
            tk.Button(top, text="Save", command=self.save_tab).pack(side="right", padx=1)

        bottom = tk.Frame(self.parent)
        bottom.pack(side="bottom", fill="x")
        self.status = tk.Label(bottom, text="", anchor="w")
        self.status.pack(side="right", padx=6)
        self.problem_label = tk.Label(bottom, text="", anchor="w", justify="left", wraplength=px(self.root, 760), cursor="hand2")
        self.problem_label.pack(side="left", fill="x", expand=True, padx=6, pady=2)
        self.problem_label.bind("<Button-1>", lambda e: self.go_to_problem())

        left = tk.Frame(self.parent, padx=5, pady=4, width=px(self.root, 212))
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text="Maps", font=("", 10, "bold")).pack(anchor="w")
        self.map_list = tk.Listbox(left, height=5, exportselection=False, activestyle="none")
        self.map_list.pack(fill="x")
        self.map_list.bind("<<ListboxSelect>>", lambda e: self.open_selected())
        tk.Button(left, text="New map...", command=self.new_map).pack(fill="x", pady=(2, 0))
        map_buttons = tk.Frame(left)
        map_buttons.pack(fill="x", pady=(1, 8))
        tk.Button(map_buttons, text="Rename...", command=self.rename_map).pack(side="left", fill="x", expand=True)
        tk.Button(map_buttons, text="Delete...", command=self.delete_map).pack(side="left", fill="x", expand=True, padx=(1, 0))

        tk.Label(left, text="Tiles", font=("", 10, "bold")).pack(anchor="w")
        self.palette_frame = tk.Frame(left)
        self.palette_frame.pack(fill="x")
        tk.Label(left, text="# solid   * monsters   ^ a 3D block", fg="#555555", font=("", 8)).pack(anchor="w")
        heights = tk.Frame(left)
        heights.pack(anchor="w")
        tk.Label(heights, text="Height").pack(side="left")
        for h in range(4):
            tk.Radiobutton(heights, text=str(h), value=h, variable=self.height_var, indicatoron=False, width=2, command=self.height_changed).pack(side="left")
        tk.Checkbutton(heights, text="Solid", variable=self.solid_var, command=self.height_changed).pack(side="left", padx=(4, 0))
        tk.Button(left, text="New tile letter...", command=self.new_letter).pack(fill="x", pady=(2, 8))

        tk.Label(left, text="Objects", font=("", 10, "bold")).pack(anchor="w")
        box = tk.Frame(left)
        box.pack(fill="both", expand=True)
        self.object_list = tk.Listbox(box, exportselection=False, activestyle="none")
        scroll = tk.Scrollbar(box, command=self.object_list.yview)
        self.object_list.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.object_list.pack(side="left", fill="both", expand=True)
        self.kinds = sorted(set(self.table) | {"link"})
        for kind in self.kinds:
            self.object_list.insert("end", kind)
        self.object_list.bind("<<ListboxSelect>>", lambda e: self.pick_object_kind())

        self.right = tk.Frame(self.parent, padx=6, pady=6, width=px(self.root, 226))
        self.right.pack(side="right", fill="y")
        self.right.pack_propagate(False)

        self.middle = tk.Frame(self.parent)
        self.middle.pack(side="left", fill="both", expand=True)
        self.notebook = ttk.Notebook(self.middle)
        self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.tab_changed())
        self.notebook.bind("<Button-2>", self.close_clicked_tab)
        self.welcome = tk.Label(self.middle, text="Pick a map on the left, or make a new one.", font=("", 12), fg="#666666")

    @staticmethod
    def separator(parent):
        ttk.Separator(parent, orient="vertical").pack(side="left", fill="y", padx=6, pady=2)

    def active(self):
        """Inside the Studio, only while the maps are showing."""
        return self.shell is None or self.shell.maps_active()

    def bind_keys(self):
        r = self.root
        if self.shell is None:
            r.bind("<Control-s>", lambda e: self.save_tab())
            r.bind("<Control-S>", lambda e: self.save_all())
        r.bind("<Control-z>", lambda e: self.active() and self.do_undo(), add="+")
        r.bind("<Control-y>", lambda e: self.active() and self.do_redo(), add="+")
        r.bind("<Control-w>", lambda e: self.active() and self.close_tab())
        r.bind("<Control-d>", lambda e: self.active() and self.copy_selected())
        r.bind("<Control-c>", lambda e: self.typing() or self.copy_area())
        r.bind("<Control-x>", lambda e: self.typing() or self.cut_area())
        r.bind("<Control-v>", lambda e: self.typing() or self.start_paste())
        r.bind("<Control-Tab>", lambda e: self.next_tab() if self.active() else None)
        r.bind("<Delete>", lambda e: self.typing() or self.delete_key())
        r.bind("<Escape>", lambda e: self.active() and self.set_tool(self.tool))
        for key, tool in (("b", "paint"), ("f", "fill"), ("r", "rect"), ("v", "select"), ("a", "area")):
            r.bind("<KeyPress-%s>" % key, lambda e, t=tool: self.typing() or self.set_tool(t))
        r.bind("<KeyPress-plus>", lambda e: self.typing() or self.set_zoom(self.zoom + 1))
        r.bind("<KeyPress-equal>", lambda e: self.typing() or self.set_zoom(self.zoom + 1))
        r.bind("<KeyPress-minus>", lambda e: self.typing() or self.set_zoom(self.zoom - 1))
        for key, (dc, dr) in (("Left", (-1, 0)), ("Right", (1, 0)), ("Up", (0, -1)), ("Down", (0, 1))):
            r.bind("<KeyPress-%s>" % key, lambda e, a=dc, b=dr: self.typing() or self.nudge(a, b))

    def typing(self):
        """True while a text field has the keyboard, so letters go there, or another part of the Studio is showing."""
        if not self.active():
            return True
        try:
            widget = self.root.focus_get()
        except KeyError:
            return False
        return isinstance(widget, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Spinbox, tk.Text))

    # ── maps and tabs ──

    def tab(self):
        if not self.tabs:
            return None
        try:
            selected = self.notebook.select()
        except tk.TclError:
            return self.tabs[0]
        for t in self.tabs:
            if str(t.frame) == selected:
                return t
        return self.tabs[0]

    def refresh_map_list(self):
        names = all_maps()
        self.map_names = names
        self.map_list.delete(0, "end")
        for name in names:
            self.map_list.insert("end", name)
        self.mark_map_list()

    def mark_map_list(self):
        current = self.tab()
        self.map_list.selection_clear(0, "end")
        if current is not None and current.doc.name in self.map_names:
            at = self.map_names.index(current.doc.name)
            self.map_list.selection_set(at)
            self.map_list.see(at)

    def open_selected(self):
        chosen = self.map_list.curselection()
        if chosen:
            self.open_map(self.map_names[chosen[0]])

    def open_map(self, name, quiet=False):
        for t in self.tabs:
            if t.doc.name == name:
                self.notebook.select(t.frame)
                return t
        try:
            doc = MapDoc(name)
        except (OSError, map_tool.MapError) as e:
            if not quiet:
                self.tell("This map cannot be opened", str(e))
            return None
        tab = Tab(self, doc)
        self.tabs.append(tab)
        self.notebook.add(tab.frame, text=name)
        self.bind_canvas(tab)
        self.notebook.select(tab.frame)
        self.update_all()
        return tab

    def bind_canvas(self, tab):
        c = tab.canvas
        c.bind("<Button-1>", self.press)
        c.bind("<B1-Motion>", self.drag)
        c.bind("<ButtonRelease-1>", self.release)
        c.bind("<Double-Button-1>", self.double_click)
        c.bind("<Button-3>", self.context_menu)
        c.bind("<Button-2>", lambda e: c.scan_mark(e.x, e.y))
        c.bind("<B2-Motion>", lambda e: c.scan_dragto(e.x, e.y, gain=1))
        c.bind("<Motion>", self.hover)
        c.bind("<Leave>", lambda e: c.delete("hover"))
        c.bind("<MouseWheel>", lambda e: c.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        c.bind("<Shift-MouseWheel>", lambda e: c.xview_scroll(-1 if e.delta > 0 else 1, "units"))
        c.bind("<Control-MouseWheel>", lambda e: self.set_zoom(self.zoom + (1 if e.delta > 0 else -1)))

    def close_clicked_tab(self, event):
        try:
            at = self.notebook.index("@%d,%d" % (event.x, event.y))
        except tk.TclError:
            return
        self.close_tab(self.tabs[at])

    def close_tab(self, tab=None):
        tab = tab or self.tab()
        if tab is None or not self.ask_about_changes(tab):
            return
        self.notebook.forget(tab.frame)
        tab.frame.destroy()
        self.tabs.remove(tab)
        self.update_all()

    def next_tab(self):
        if len(self.tabs) > 1:
            self.notebook.select(self.tabs[(self.tabs.index(self.tab()) + 1) % len(self.tabs)].frame)
        return "break"

    def tab_changed(self):
        self.mark_map_list()
        self.show_fields()
        self.redraw()
        self.update_status()

    def ask_about_changes(self, tab):
        """False when the person changed their mind."""
        if not tab.dirty:
            return True
        answer = messagebox.askyesnocancel("Save changes?", "Save the changes to %s?" % tab.doc.name, parent=self.root)
        if answer is None:
            return False
        if answer:
            self.save_tab(tab)
        return True

    def quit(self):
        if self.story is not None and self.story.winfo_exists() and not self.story.close():
            return
        for tab in list(self.tabs):
            if tab.dirty:
                self.notebook.select(tab.frame)
                if not self.ask_about_changes(tab):
                    return
        self.remember_session()
        self.root.destroy()

    def remember_session(self):
        try:
            os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
            with open(SESSION_FILE, "w", encoding="utf-8") as fh:
                json.dump([t.doc.name for t in self.tabs], fh)
        except OSError:
            pass

    @staticmethod
    def last_session():
        try:
            with open(SESSION_FILE, encoding="utf-8") as fh:
                return [n for n in json.load(fh) if n in all_maps()]
        except (OSError, ValueError, TypeError):
            return []

    def outside_changes(self, event=None):
        """A map changed in a text editor while this window was away."""
        if event is not None and event.widget is not self.root:
            return
        for tab in self.tabs:
            if not os.path.isfile(tab.doc.path):
                continue
            stamp = os.path.getmtime(tab.doc.path)
            if stamp != tab.mtime:
                tab.mtime = stamp
                if not tab.dirty or messagebox.askyesno("Changed outside", "%s was changed outside the editor. Load that and lose the changes here?" % tab.doc.name, parent=self.root):
                    self.reload(tab)

    def reload_all(self):
        """The files changed underneath (the Studio restored a copy, or renamed something)."""
        for tab in list(self.tabs):
            if not os.path.isfile(tab.doc.path):
                self.notebook.forget(tab.frame)
                tab.frame.destroy()
                self.tabs.remove(tab)
            else:
                tab.mtime = os.path.getmtime(tab.doc.path)
                self.reload(tab)
        self.table = map_tool.read_objects_table()
        self.refresh_map_list()
        self.update_all()

    def reload(self, tab):
        try:
            tab.doc = MapDoc(tab.doc.name)
        except (OSError, map_tool.MapError) as e:
            self.tell("This map cannot be read now", str(e))
            return
        tab.saved = tab.doc.text()
        tab.undo, tab.redo = [], []
        tab.selected = None
        self.update_all()

    def new_map(self):
        dialog = NewMapDialog(self.root, self.current_legend())
        if not dialog.result:
            return
        name, width, height, ground, wall = dialog.result
        try:
            create_map(name, width, height, ground, wall)
        except map_tool.MapError as e:
            self.tell("This map cannot be made", str(e))
            return
        self.refresh_map_list()
        self.open_map(name)
        self.say_status("New map. To reach it: a building with inside=%s, or a link to it." % name)

    # ── renaming and deleting a map (tools/map_files.py does the work) ──

    def chosen_map(self):
        """The map picked in the list, or else the open one."""
        picked = self.map_list.curselection()
        if picked:
            return self.map_names[picked[0]]
        tab = self.tab()
        return tab.doc.name if tab else None

    def files_will_change(self, why):
        """Renaming and deleting work on the files: everything open is saved first, and a copy is kept."""
        if self.shell is not None:
            self.shell.save_all()
        else:
            self.save_all()
            if self.story is not None and self.story.winfo_exists() and self.story.dirty():
                self.story.save()
        try:
            import studio_data
            studio_data.make_backup(why, ROOT)
        except Exception:         # a copy is a help, not a must
            pass

    def files_changed(self, open_name=None):
        if self.shell is not None:
            self.shell.reload_everything()
        else:
            self.reload_all()
            if self.story is not None and self.story.winfo_exists():
                self.story.reload_files()
        if open_name:
            self.open_map(open_name)

    @staticmethod
    def published_warning():
        if os.path.isfile(os.path.join(ROOT, ".studio_release.json")):
            return ("\n\nYour game is already published. A game saved on this map, on someone's phone, cannot go on there after this: "
                    "they would have to start again.")
        return ""

    def rename_map(self, new=None):
        import map_files
        old = self.chosen_map()
        if old is None:
            return
        if new is None:
            new = simpledialog.askstring("Rename a map", "A new name for %s (lowercase letters, numbers and _).\nDoors, links, the story, "
                                         "its wild monsters and its events (%s.something) change with it.%s" % (old, old, self.published_warning()),
                                         initialvalue=old, parent=self.root)
        if not new or new.strip() == old:
            return
        self.files_will_change("before renaming the map %s" % old)
        try:
            map_files.rename(old, new.strip())
        except map_files.MapFileError as e:
            self.tell("This map cannot be renamed", str(e))
            return
        self.files_changed(new.strip())
        self.say_status("%s is now %s, everywhere." % (old, new.strip()))

    def delete_map(self, sure=False):
        import map_files
        name = self.chosen_map()
        if name is None:
            return
        try:
            map_files.check_name(name)
        except map_files.MapFileError as e:
            self.tell("This map cannot be deleted", str(e))
            return
        stop = map_files.blockers(name)
        if stop:
            self.tell("First, a change", "The game still needs %s:\n\n%s" % (name, "\n".join(stop)))
            return
        goes = [text for path, line, text in map_files.uses(name) if path.startswith("maps_src/")]
        lines = ["maps_src/%s.map and its scene in game/main.py" % name]
        lines += ["in another map: " + text for text in goes]
        lines += ["its wild monsters: " + text.split()[-1] for path, line, text in map_files.uses(name) if path == "data/encounters.json"]
        if not sure and not messagebox.askyesno("Delete %s?" % name, "This goes:\n\n%s\n\nIts story stays, in case you want it. A copy is kept "
                                                "first: Copies in the Studio brings it all back.%s" % ("\n".join("- " + l for l in lines), self.published_warning()),
                                                icon="warning", parent=self.root):
            return
        self.files_will_change("before deleting the map %s" % name)
        try:
            map_files.delete(name)
        except map_files.MapFileError as e:
            self.tell("This map cannot be deleted", str(e))
            return
        self.files_changed()
        self.say_status("%s is deleted." % name)

    def tell(self, title, text):
        messagebox.showinfo(title, text, parent=self.root)

    # ── tiles ──

    def current_legend(self):
        tab = self.tab()
        return tab.doc.legend if tab else map_tool.read_legend(map_tool.tile_names())

    def build_palette(self):
        for child in self.palette_frame.winfo_children():
            child.destroy()
        legend = self.current_legend()
        if self.letter not in legend:
            self.letter = next(iter(legend), None)
        self.palette_buttons = {}
        for i, (letter, entry) in enumerate(legend.items()):
            photo = self.tile_photo(entry["tile"], 1)
            marks = ("^%d" % entry["height"] if entry["height"] else "") + ("#" if entry["solid"] else "") + ("*" if entry["zone"] else "")
            button = tk.Button(self.palette_frame, image=photo, text=" %s%s" % (entry["tile"][:6], marks), compound="left", anchor="w", width=px(self.root, 92),
                               font=("", 8), command=lambda l=letter: self.pick_tile(l))
            button.grid(row=i // 2, column=i % 2, sticky="ew")
            tip = entry["tile"] + (", solid" if entry["solid"] else "") + (", monsters: %s" % entry["zone"] if entry["zone"] else "") + (", height %d" % entry["height"] if entry["height"] else "")
            button.bind("<Enter>", lambda e, t=tip, l=letter: self.say_status("Letter %s: %s" % (l, t)))
            self.palette_buttons[letter] = button
        self.mark_palette()

    def mark_palette(self):
        for letter, button in self.palette_buttons.items():
            button.configure(relief="sunken" if letter == self.letter and self.tool != "select" else "raised",
                             bg="#ffe680" if letter == self.letter and self.tool != "select" else self.root.cget("bg"))

    def pick_tile(self, letter):
        self.letter = letter
        entry = self.current_legend()[letter]
        self.height_var.set(entry["height"])
        self.solid_var.set(entry["solid"])
        if self.tool in ("select", "area"):
            self.set_tool("paint")
        self.mark_palette()
        self.say_status("Painting with %s. %s" % (entry["tile"], "It rises %d, as a 3D block." % entry["height"] if entry["height"] else "To paint it as a 3D block, pick a height."))

    def height_changed(self):
        """The same tile at another height: uses the letter that is that, or adds one to the legend."""
        legend = self.current_legend()
        if self.letter not in legend:
            return
        height = self.height_var.get()
        was = legend[self.letter]
        solid = self.solid_var.get()
        if height and not was["height"] and not solid:
            solid = True                    # a block is a wall, until you say it can be walked on
            self.solid_var.set(True)
        wanted = dict(was, height=height, solid=solid, edges=was["edges"] and not height, zone="" if height else was["zone"])
        mine = next((k for k, v in legend.items() if v == wanted), None)
        if mine is None:
            mine = free_letter(legend)
            self.add_letter(entry_line(mine, wanted))
        self.letter = mine
        self.build_palette()
        if self.tool in ("select", "area"):
            self.set_tool("paint")
        self.say_status("Painting with %s%s." % (wanted["tile"], ", %d high" % height if height else "") + (" You can walk on it." if height and not solid else ""))

    def add_letter(self, line):
        path = os.path.join(map_tool.SOURCE, "legend.txt")
        with open(path, encoding="utf-8") as fh:
            old = fh.read()
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(("" if old.endswith("\n") else "\n") + line + "\n")
        letter, entry = map_tool.legend_line(line, "legend", map_tool.tile_names())
        for tab in self.tabs:
            tab.doc.base_legend[letter] = entry
            tab.doc.legend[letter] = entry
        return letter

    def new_letter(self):
        dialog = NewLetterDialog(self.root, self.current_legend())
        if not dialog.result:
            return
        self.letter = self.add_letter(dialog.result)
        self.build_palette()

    def art_photo(self, art, scale):
        """A cell's picture, with its edges cut."""
        if not art[2]:
            return self.tile_photo(art[0], scale)
        key = (art, scale)
        if key not in self.images:
            self.images[key] = ImageTk.PhotoImage(map_tool.edge_tile(*art).resize((TILE * scale, TILE * scale), Image.NEAREST))
        return self.images[key]

    def tile_photo(self, tile, scale):
        key = (tile, scale)
        if key not in self.images:
            with Image.open(os.path.join(map_tool.TILES, tile + ".png")) as img:
                self.images[key] = ImageTk.PhotoImage(img.convert("RGBA").resize((TILE * scale, TILE * scale), Image.NEAREST))
        return self.images[key]

    def object_photo(self, o):
        """A picture for an object that has one."""
        path, box = None, None
        if o["kind"] in ("person", "trainer"):
            look = o["props"].get("look", "")
            path = os.path.join(ROOT, "assets", "people", "%s.png" % look)
            box = (0, 0, 16, 24)
        elif o["kind"] in ("tree", "knot"):
            path = os.path.join(ROOT, "assets", "%s.png" % o["kind"])
        if path is None or not os.path.isfile(path):
            return None
        key = (path, self.zoom)
        if key not in self.images:
            with Image.open(path) as img:
                img = img.convert("RGBA")
                if box:
                    img = img.crop(box)
                cell = TILE * self.zoom
                scale = cell / max(img.size)
                self.images[key] = ImageTk.PhotoImage(img.resize((max(1, int(img.size[0] * scale)), max(1, int(img.size[1] * scale))), Image.NEAREST))
        return self.images[key]

    # ── tools ──

    def set_tool(self, tool):
        self.tool = tool
        self.place_kind = ""
        self.pasting = False
        self.area_start = None
        for t in self.tabs:
            if tool != "area":
                t.area = None
            t.canvas.delete("hover")
            t.canvas.delete("area")
        self.object_list.selection_clear(0, "end")
        for name, button in self.tool_buttons.items():
            button.configure(relief="sunken" if name == tool else "raised", bg="#ffe680" if name == tool else self.root.cget("bg"))
        tab = self.tab()
        if tab is not None and tool != "select" and tab.selected is not None:
            tab.selected = None
            self.show_fields()
            self.draw_objects(tab)
        if self.tabs:
            self.mark_palette()
        cursor = {"paint": "pencil", "fill": "spraycan", "rect": "crosshair", "select": "arrow", "area": "tcross"}[tool]
        for t in self.tabs:
            t.canvas.configure(cursor=cursor)
        self.say_status({"paint": "Brush: drag to paint. Right click for more.", "fill": "Fill: click an area to change all of it.",
                         "rect": "Rectangle: drag a box.", "select": "Select: click an object to change it, drag it to move it. Arrow keys move it too.",
                         "area": "Area: drag a box, then Ctrl+C or Ctrl+X, and Ctrl+V to paste it. It works between maps."}[tool])

    def pick_object_kind(self):
        chosen = self.object_list.curselection()
        if not chosen:
            return
        self.place_kind = self.kinds[chosen[0]]
        tab = self.tab()
        if tab is not None:
            tab.selected = None
            self.show_fields()
            self.draw_objects(tab)
        for t in self.tabs:
            t.canvas.configure(cursor="plus")
        self.say_status("Click where the %s goes. %s" % (self.place_kind, BUILDING_HELP if self.place_kind in self.sizes else HELP.get(self.place_kind, "")))

    def cell(self, event, tab=None):
        tab = tab or self.tab()
        size = TILE * self.zoom
        return int(tab.canvas.canvasx(event.x) // size), int(tab.canvas.canvasy(event.y) // size)

    def remember(self, tab):
        """Before a change: one step of undo."""
        tab.undo.append(tab.doc.snapshot())
        del tab.undo[:-200]
        tab.redo = []

    def press(self, event):
        tab = self.tab()
        tab.canvas.focus_set()
        col, row = self.cell(event, tab)
        if not tab.doc.inside(col, row):
            return
        if self.pasting:
            self.remember(tab)
            size_before = len(tab.doc.legend)
            tab.doc.paste_area(self.clip, col, row)
            if len(tab.doc.legend) != size_before:
                self.build_palette()
            self.changed(tab)
            self.redraw()
            self.say_status("Pasted. Click to paste again, or press Esc.")
            return
        if self.tool == "area":
            self.area_start = (col, row)
            tab.area = (col, row, col, row)
            self.draw_area(tab)
            return
        if self.place_kind:
            self.remember(tab)
            kind = self.place_kind
            tab.selected = tab.doc.add_object(kind, float(col), float(row))
            self.set_tool("select")
            tab.selected = tab.doc.objects[-1]
            self.show_fields()
            self.changed(tab)
            self.say_status("Placed. Fill in what it needs on the right.")
            if self.fields:
                next(iter(self.fields.values())).focus_set()
            return
        if self.tool == "select":
            hit = tab.doc.object_at(col, row, self.sizes)
            tab.selected = hit
            self.show_fields()
            self.draw_objects(tab)
            self.stroke = (col, row, False) if hit is not None else None
            return
        if self.letter is None:
            return
        self.remember(tab)
        if self.tool == "fill":
            self.draw_cells(tab, tab.doc.fill(col, row, self.letter))
            self.finish_stroke(tab)
        elif self.tool == "rect":
            self.rect_start = (col, row)
        else:
            if tab.doc.paint(col, row, self.letter):
                self.draw_cells(tab, [(col, row)])

    def drag(self, event):
        tab = self.tab()
        col, row = self.cell(event, tab)
        self.hover(event)
        if self.tool == "area":
            if self.area_start:
                col = max(0, min(tab.doc.cols - 1, col))
                row = max(0, min(len(tab.doc.rows) - 1, row))
                tab.area = self.area_start + (col, row)
                self.draw_area(tab)
            return
        if self.tool == "select":
            if self.stroke is None or tab.selected is None:
                return
            c0, r0, moved = self.stroke
            if (col, row) != (c0, r0) and tab.doc.inside(col, row):
                if not moved:
                    self.remember(tab)
                tab.selected["col"] += col - c0
                tab.selected["row"] += row - r0
                self.stroke = (col, row, True)
                self.show_fields_position()
                self.draw_objects(tab)
        elif self.tool == "rect" and self.rect_start:
            tab.canvas.delete("rubber")
            size = TILE * self.zoom
            c0, r0 = self.rect_start
            tab.canvas.create_rectangle(min(c0, col) * size, min(r0, row) * size, (max(c0, col) + 1) * size, (max(r0, row) + 1) * size,
                                        outline="#ffd84a", width=2, tags="rubber")
        elif self.tool == "paint" and tab.doc.inside(col, row) and self.letter is not None:
            if tab.doc.paint(col, row, self.letter):
                self.draw_cells(tab, [(col, row)])

    def release(self, event):
        tab = self.tab()
        if self.tool == "area" or self.pasting:
            self.area_start = None
            return
        if self.tool == "select":
            if self.stroke is not None and self.stroke[2]:
                self.changed(tab)
            self.stroke = None
            return
        if self.tool == "rect" and self.rect_start:
            col, row = self.cell(event, tab)
            col = max(0, min(tab.doc.cols - 1, col))
            row = max(0, min(len(tab.doc.rows) - 1, row))
            tab.canvas.delete("rubber")
            c0, r0 = self.rect_start
            self.rect_start = None
            self.draw_cells(tab, tab.doc.rectangle(c0, r0, col, row, self.letter))
        if self.tool in ("paint", "rect"):
            self.finish_stroke(tab)

    def finish_stroke(self, tab):
        """A press that changed nothing leaves no step of undo."""
        if tab.undo and tab.undo[-1][1] == tab.doc.rows and tab.undo[-1][2] == tab.doc.objects:
            tab.undo.pop()
        self.changed(tab)

    def double_click(self, event):
        tab = self.tab()
        col, row = self.cell(event, tab)
        hit = tab.doc.object_at(col, row, self.sizes)
        target = self.leads_to(hit) if hit else None
        if target:
            self.open_map(target)
            return
        self.press(event)           # two quick clicks are also two clicks: painting, or picking up an object

    @staticmethod
    def leads_to(o):
        if o["kind"] == "link":
            return o["name"] or o["props"].get("to", "")
        return o["props"].get("inside") or o["props"].get("to") or ""

    def context_menu(self, event):
        tab = self.tab()
        col, row = self.cell(event, tab)
        if not tab.doc.inside(col, row):
            return
        menu = tk.Menu(self.root, tearoff=False)
        letter = tab.doc.rows[row][col]
        menu.add_command(label="Use this tile (%s)" % tab.doc.legend[letter]["tile"], command=lambda: self.pick_tile(letter))
        hit = tab.doc.object_at(col, row, self.sizes)
        if hit is not None:
            def select():
                self.set_tool("select")
                tab.selected = hit
                self.show_fields()
                self.draw_objects(tab)

            menu.add_command(label="Change this %s" % hit["kind"], command=select)
            target = self.leads_to(hit)
            if target:
                menu.add_command(label="Open the map %s" % target, command=lambda: self.open_map(target))

            def delete():
                self.remember(tab)
                tab.doc.objects.remove(hit)
                tab.selected = None
                self.show_fields()
                self.changed(tab)

            menu.add_command(label="Delete this %s" % hit["kind"], command=delete)
        menu.add_separator()
        add = tk.Menu(menu, tearoff=False)
        for kind in self.kinds:
            add.add_command(label=kind, command=lambda k=kind: self.add_here(tab, k, col, row))
        menu.add_cascade(label="Add an object here", menu=add)
        menu.add_separator()
        menu.add_command(label="Test the game from here", command=lambda: self.test_here(tab, col, row))
        menu.add_command(label="See in 3D from here", command=lambda: self.preview_at(tab, col, row))
        if self.clip is not None:
            menu.add_command(label="Paste here", command=lambda: self.paste_at(tab, col, row))
        menu.tk_popup(event.x_root, event.y_root)

    def paste_at(self, tab, col, row):
        self.remember(tab)
        before = len(tab.doc.legend)
        tab.doc.paste_area(self.clip, col, row)
        if len(tab.doc.legend) != before:
            self.build_palette()
        self.changed(tab)
        self.redraw()

    def add_here(self, tab, kind, col, row):
        self.remember(tab)
        o = tab.doc.add_object(kind, float(col), float(row))
        self.set_tool("select")
        tab.selected = o
        self.show_fields()
        self.changed(tab)

    def nudge(self, dc, dr):
        tab = self.tab()
        if tab is None or tab.selected is None:
            return
        o = tab.selected
        if tab.doc.inside(int(o["col"] + dc), int(o["row"] + dr)):
            self.remember(tab)
            o["col"] += dc
            o["row"] += dr
            self.show_fields_position()
            self.changed(tab)

    def copy_selected(self):
        tab = self.tab()
        if tab is None or tab.selected is None:
            return
        self.remember(tab)
        tab.selected = tab.doc.copy_object(tab.selected)
        self.show_fields()
        self.changed(tab)

    def delete_selected(self):
        tab = self.tab()
        if tab is None or tab.selected is None:
            return
        self.remember(tab)
        tab.doc.objects.remove(tab.selected)
        tab.selected = None
        self.show_fields()
        self.changed(tab)

    def resize(self, side, grow):
        tab = self.tab()
        if tab is None:
            return
        self.remember(tab)
        gone = []
        selected_at = tab.doc.objects.index(tab.selected) if tab.selected in tab.doc.objects else -1
        if grow:
            tab.doc.grow(side, self.letter)
        else:
            gone = tab.doc.shrink(side)
        tab.selected = tab.doc.objects[selected_at] if 0 <= selected_at < len(tab.doc.objects) and not gone else None
        self.show_fields()
        self.changed(tab)
        self.redraw()
        if gone:
            self.say_status("Removed with that edge: %s. Undo brings them back." % ", ".join(o["name"] or o["kind"] for o in gone))

    def draw_area(self, tab):
        c = tab.canvas
        c.delete("area")
        if getattr(tab, "area", None):
            size = TILE * self.zoom
            c0, r0, c1, r1 = tab.area
            c.create_rectangle(min(c0, c1) * size, min(r0, r1) * size, (max(c0, c1) + 1) * size, (max(r0, r1) + 1) * size,
                               outline="#ffffff", dash=(4, 3), width=2, tags="area")

    def copy_area(self):
        tab = self.tab()
        if tab is None or not getattr(tab, "area", None):
            return False
        self.clip = tab.doc.copy_area(*tab.area)
        self.say_status("Copied. Ctrl+V to paste it, in this map or another.")
        return True

    def cut_area(self):
        if self.copy_area():
            tab = self.tab()
            self.remember(tab)
            tab.doc.clear_area(*tab.area, self.letter)
            self.changed(tab)
            self.redraw()
            self.draw_area(tab)
            self.say_status("Cut. Ctrl+V to paste it. What is left was painted with the chosen tile.")

    def start_paste(self):
        if self.clip is None:
            self.say_status("Nothing to paste yet: drag a box with the Area tool, and press Ctrl+C.")
            return
        self.pasting = True
        for t in self.tabs:
            t.area = None
            t.canvas.delete("area")
        self.say_status("Click where its top left corner goes. Esc stops.")

    def delete_key(self):
        tab = self.tab()
        if tab is not None and getattr(tab, "area", None) and self.tool == "area":
            self.remember(tab)
            tab.doc.clear_area(*tab.area, self.letter)
            self.changed(tab)
            self.redraw()
            self.draw_area(tab)
        else:
            self.delete_selected()

    def do_undo(self):
        self.swap_history("undo", "redo")

    def do_redo(self):
        self.swap_history("redo", "undo")

    def swap_history(self, source, target):
        tab = self.tab()
        if tab is None or not getattr(tab, source):
            return
        getattr(tab, target).append(tab.doc.snapshot())
        tab.doc.restore(getattr(tab, source).pop())
        tab.selected = None
        self.field_snapshot = False
        self.show_fields()
        self.changed(tab)
        self.redraw()

    def set_zoom(self, zoom):
        zoom = max(1, min(4, zoom))
        if zoom != self.zoom:
            self.zoom = zoom
            self.zoom_label.config(text="%d%%" % (zoom * 100))
            self.redraw()

    # ── drawing ──

    def redraw(self):
        tab = self.tab()
        if tab is None:
            return
        c = tab.canvas
        c.delete("all")
        tab.items = {}
        size = TILE * self.zoom
        for r, row in enumerate(tab.doc.rows):
            for col in range(len(row)):
                tab.items[(col, r)] = c.create_image(col * size, r * size, anchor="nw", image=self.art_photo(map_tool.cell_art(tab.doc.rows, tab.doc.legend, col, r), self.zoom))
        c.configure(scrollregion=(0, 0, tab.doc.cols * size, len(tab.doc.rows) * size))
        self.draw_overlays(tab)
        self.draw_objects(tab)
        self.draw_area(tab)

    def draw_cells(self, tab, cells):
        around = set()
        for col, row in cells:                      # a cell's edges depend on the cells next to it
            around.update(((col, row), (col + 1, row), (col - 1, row), (col, row + 1), (col, row - 1)))
        for col, row in around:
            if tab.doc.inside(col, row):
                tab.canvas.itemconfigure(tab.items[(col, row)], image=self.art_photo(map_tool.cell_art(tab.doc.rows, tab.doc.legend, col, row), self.zoom))
        if cells:
            self.draw_overlays(tab)
            self.draw_objects(tab)

    def draw_overlays(self, tab):
        c = tab.canvas
        c.delete("overlay")
        size = TILE * self.zoom
        wide, tall = tab.doc.cols * size, len(tab.doc.rows) * size
        if self.show_solid.get():
            for r, row in enumerate(tab.doc.rows):
                for col, letter in enumerate(row):
                    if tab.doc.legend[letter]["solid"]:
                        c.create_rectangle(col * size, r * size, (col + 1) * size, (r + 1) * size, fill="#ff2020", stipple="gray25", width=0, tags="overlay")
        if self.show_heights.get():
            for r, row in enumerate(tab.doc.rows):
                for col, letter in enumerate(row):
                    height = tab.doc.legend[letter]["height"]
                    if height:
                        x, y = col * size, r * size
                        c.create_line(x, y + size - 1, x, y, x + size - 1, y, fill="#ffffff", tags="overlay")
                        c.create_line(x + size - 1, y, x + size - 1, y + size - 1, x, y + size - 1, fill="#202020", tags="overlay")
                        c.create_text(x + size / 2, y + size / 2, text=str(height), fill="#ffffff", font=("", 8, "bold"), tags="overlay")
        if self.show_grid.get() and self.zoom > 1:
            for col in range(tab.doc.cols + 1):
                c.create_line(col * size, 0, col * size, tall, fill="#000000", stipple="gray25", tags="overlay")
            for row in range(len(tab.doc.rows) + 1):
                c.create_line(0, row * size, wide, row * size, fill="#000000", stipple="gray25", tags="overlay")

    def draw_objects(self, tab):
        c = tab.canvas
        c.delete("object")
        size = TILE * self.zoom
        for o in tab.doc.objects:
            if "comment" in o:
                continue
            width, depth = self.sizes.get(o["kind"]) or (1, 1)
            x0, y0 = o["col"] * size, o["row"] * size
            is_selected = o is tab.selected
            colour = "#ffd84a" if is_selected else "#e02020"
            if o["kind"] in self.sizes:
                c.create_rectangle(x0, y0, x0 + width * size, y0 + depth * size, fill="#c0a080", stipple="gray50", outline=colour, width=2, tags="object")
                door = o["col"] + width // 2
                if o["props"].get("inside") or o["props"].get("event"):
                    c.create_rectangle(door * size + 2, (o["row"] + depth - 1) * size + 2, (door + 1) * size - 2, (o["row"] + depth) * size - 2, fill="#6a3a18", outline="#ffffff", tags="object")
                c.create_text(x0 + 4, y0 + 3, text=o["props"].get("inside") or o["kind"], anchor="nw", fill="white", font=("", 8, "bold"), tags="object")
                continue
            photo = self.object_photo(o)
            if photo is not None:
                c.create_image(x0 + size / 2, y0 + size / 2, image=photo, tags="object")
            repeat_w = self.number(o["props"].get("width", 1))
            repeat_h = self.number(o["props"].get("height", 1))
            c.create_rectangle(x0 + 1, y0 + 1, x0 + repeat_w * size - 1, y0 + repeat_h * size - 1, outline=colour, width=2, tags="object")
            label = self.object_label(o)
            if label:
                c.create_text(x0 + 3, y0 + 2, text=label, anchor="nw", fill="white", font=("", 7, "bold"), tags="object")

    @staticmethod
    def number(value):
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def object_label(o):
        if o["kind"] == "link":
            return "> " + (o["name"] or o["props"].get("to", "?"))
        if o["kind"] in ("exit", "door", "warp"):
            return o["kind"]
        if o["kind"] in ("tree", "knot"):
            return ""
        return o["name"] or o["kind"]

    def hover(self, event):
        tab = self.tab()
        if tab is None:
            return
        col, row = self.cell(event, tab)
        c = tab.canvas
        c.delete("hover")
        if not tab.doc.inside(col, row):
            self.status.config(text="")
            return
        size = TILE * self.zoom
        if self.pasting and self.clip:
            for r, cells in enumerate(self.clip["rows"]):
                for k, letter in enumerate(cells):
                    c.create_image((col + k) * size, (row + r) * size, anchor="nw", tags="hover", image=self.tile_photo(self.clip["legend"][letter]["tile"], self.zoom))
            c.create_rectangle(col * size, row * size, (col + len(self.clip["rows"][0])) * size, (row + len(self.clip["rows"])) * size, outline="#ffd84a", width=2, tags="hover")
        else:
            c.create_rectangle(col * size, row * size, (col + 1) * size, (row + 1) * size, outline="#ffffff", width=1, tags="hover")
        hit = tab.doc.object_at(col, row, self.sizes)
        entry = tab.doc.legend[tab.doc.rows[row][col]]
        words = "column %d, row %d: %s%s" % (col, row, entry["tile"], ", %d high" % entry["height"] if entry["height"] else "")
        if hit is not None:
            words += "  |  " + MapDoc.object_line(hit)[:60]
        self.status.config(text=words)

    # ── what an object says ──

    def options_for(self, key, kind):
        if key == "":
            return {"link": self.map_names, "trainer": known_trainers()}.get(kind)
        if key == "look":
            return known_looks()
        if key == "event":
            return known_events()
        if key == "facing":
            return FACING
        if key in ("inside", "to"):
            return self.map_names
        if key in ("hide_if", "unless", "flag"):
            return known_flags()
        return None

    def show_fields(self):
        for child in self.right.winfo_children():
            child.destroy()
        self.fields = {}
        self.warnings = {}
        self.position_label = None
        self.field_snapshot = False
        tab = self.tab()
        o = tab.selected if tab else None
        if tab is None:
            return
        if o is None:
            self.show_map_panel(tab)
            return
        is_building = o["kind"] in self.sizes
        tk.Label(self.right, text=o["kind"], font=("", 12, "bold")).pack(anchor="w")
        tk.Label(self.right, text=BUILDING_HELP if is_building else HELP.get(o["kind"], ""), wraplength=px(self.root, 206), justify="left", fg="#555555").pack(anchor="w")
        self.position_label = tk.Label(self.right, text="")
        self.position_label.pack(anchor="w", pady=(8, 0))
        moves = tk.Frame(self.right)
        moves.pack(anchor="w")
        for i, (text, dc, dr) in enumerate((("<", -1, 0), ("^", 0, -1), ("v", 0, 1), (">", 1, 0))):
            tk.Button(moves, text=text, width=2, command=lambda a=dc, b=dr: self.nudge(a, b)).grid(row=0, column=i)
        self.show_fields_position()
        keys = list(BUILDING_FIELDS if is_building else FIELDS.get(o["kind"], []))
        keys += [k for k in o["props"] if k not in keys]
        if not is_building:
            self.add_field(o, "", "name" + (" (%s)" % NAME_HINT[o["kind"]] if o["kind"] in NAME_HINT else ""), o["name"])
        for key in keys:
            self.add_field(o, key, key, str(o["props"].get(key, "")))
        target = self.leads_to(o)
        if target:
            tk.Button(self.right, text="Open the map %s" % target, command=lambda: self.open_map(target)).pack(fill="x", pady=(10, 0))
        if o["kind"] in ("person", "trigger", "sign", "knot", "trainer") or (is_building and not o["props"].get("inside")):
            tk.Button(self.right, text="Write what happens...", command=lambda: self.edit_event(tab, o)).pack(fill="x", pady=(6, 0))
        row = tk.Frame(self.right)
        row.pack(anchor="w", pady=(12, 0))
        tk.Button(row, text="Copy", command=self.copy_selected).pack(side="left")
        tk.Button(row, text="Delete", command=self.delete_selected).pack(side="left", padx=4)
        self.check_fields()

    def show_map_panel(self, tab):
        tk.Label(self.right, text=tab.doc.name, font=("", 12, "bold")).pack(anchor="w")
        tk.Label(self.right, text="%d columns, %d rows" % (tab.doc.cols, len(tab.doc.rows))).pack(anchor="w")
        tk.Label(self.right, text="Click an object with the Select tool to change it.", wraplength=px(self.root, 206), justify="left", fg="#555555").pack(anchor="w", pady=(4, 10))
        if self.shell is not None and tab.doc.name in self.shell.project.main.scenes():
            self.scene_settings(tab.doc.name)
        tk.Label(self.right, text="Grow or shrink the map", font=("", 10, "bold")).pack(anchor="w")
        tk.Label(self.right, text="New cells use the chosen tile.", fg="#555555").pack(anchor="w")
        grid = tk.Frame(self.right)
        grid.pack(anchor="w", pady=2)
        for r, (side, label) in enumerate((("top", "Top"), ("bottom", "Bottom"), ("left", "Left"), ("right", "Right"))):
            tk.Label(grid, text=label, width=7, anchor="w").grid(row=r, column=0)
            tk.Button(grid, text="+", width=3, command=lambda s=side: self.resize(s, True)).grid(row=r, column=1)
            tk.Button(grid, text="-", width=3, command=lambda s=side: self.resize(s, False)).grid(row=r, column=2)
        tk.Label(self.right, text="Keys", font=("", 10, "bold")).pack(anchor="w", pady=(12, 0))
        tk.Label(self.right, justify="left", fg="#555555", wraplength=px(self.root, 206),
                 text="Right click: a menu, including Test the game and See in 3D from here.\nDouble click a door or link: opens that map.\n3D blocks: pick a tile, then a Height.\nArea (A): Ctrl+C, Ctrl+X, Ctrl+V.\nCtrl+wheel: zoom. Middle button: drag.\nCtrl+Z, Ctrl+Y: undo, redo.\nCtrl+S: save.").pack(anchor="w")

    def scene_settings(self, scene):
        """Its music and background: inside the Studio, which keeps them."""
        main = self.shell.project.main
        grid = tk.Frame(self.right)
        grid.pack(anchor="w", pady=(0, px(self.root, 10)))
        tk.Label(grid, text="Music").grid(row=0, column=0, sticky="w")
        box = ttk.Combobox(grid, values=["(none)"] + [t[0] for t in main.tracks()], state="readonly", width=14)
        box.set(main.get(scene, "music") or "(none)")
        box.grid(row=0, column=1, padx=px(self.root, 4))

        def music(event=None):
            main.set(scene, "music", None if box.get() == "(none)" else box.get())
            self.shell.update_marks()

        box.bind("<<ComboboxSelected>>", music)
        tk.Label(grid, text="Background").grid(row=1, column=0, sticky="w")
        colour = (main.get(scene, "background") or "#7cb4d8").strip('"')
        swatch = tk.Button(grid, text=colour, bg=colour, fg="#ffffff", width=9)

        def background():
            _, chosen = colorchooser.askcolor(color=swatch.cget("bg"), parent=self.root, title="Behind the map")
            if chosen:
                main.set(scene, "background", '"%s"' % chosen)
                swatch.configure(bg=chosen, text=chosen)
                self.shell.update_marks()

        swatch.configure(command=background)
        swatch.grid(row=1, column=1, padx=px(self.root, 4), pady=px(self.root, 2), sticky="w")

    def show_fields_position(self):
        tab = self.tab()
        if tab is not None and tab.selected is not None and self.position_label is not None:
            self.position_label.config(text="Column %g, row %g" % (tab.selected["col"], tab.selected["row"]))

    def add_field(self, o, key, label, value):
        tk.Label(self.right, text=label).pack(anchor="w", pady=(6, 0))
        options = self.options_for(key, o["kind"])
        entry = ttk.Combobox(self.right, values=options) if options is not None else ttk.Entry(self.right)
        entry.insert(0, value)
        entry.pack(fill="x")
        entry.bind("<KeyRelease>", lambda e: self.read_fields())
        entry.bind("<<ComboboxSelected>>", lambda e: self.read_fields())
        self.fields[key] = entry
        warning = tk.Label(self.right, text="", fg="#b02020", wraplength=px(self.root, 206), justify="left")
        warning.pack(anchor="w")
        self.warnings[key] = (warning, options)

    def edit_event(self, tab, o):
        """Opens the story on this object's event. With no event yet, gives it one named after the map and the object."""
        if o["kind"] == "trainer":
            if not o["name"]:
                self.say_status("Give the trainer a name first.")
                return
            event = o["props"].get("event") or "trainer." + o["name"]
        else:
            event = o["props"].get("event", "")
            if not event:
                event = "%s.%s" % (tab.doc.name, o["name"] or o["kind"])
                self.remember(tab)
                o["props"]["event"] = event
                self.show_fields()
                self.changed(tab)
        self.open_story().open_event(event)

    def open_story(self):
        if self.shell is not None:
            self.story = self.shell.open_story()
            return self.story
        if self.story is None or not self.story.winfo_exists():
            self.story = story_editor.open_window(self.root, on_saved=self.show_fields)
        self.story.winfo_toplevel().lift()
        return self.story

    def preview_center(self):
        tab = self.tab()
        if tab is None:
            return
        size = TILE * self.zoom
        canvas = tab.canvas
        col = int(canvas.canvasx(canvas.winfo_width() / 2) // size)
        row = int(canvas.canvasy(canvas.winfo_height() / 2) // size)
        self.preview_at(tab, max(0, min(tab.doc.cols - 1, col)), max(0, min(len(tab.doc.rows) - 1, row)))

    def preview_at(self, tab, col, row):
        self.save_all()
        if self.preview is None or not self.preview.winfo_exists():
            self.preview = PreviewWindow(self.root)
        self.preview.show(tab.doc.name, col, row, (tab.doc.cols, len(tab.doc.rows)))

    def read_fields(self):
        tab = self.tab()
        o = tab.selected if tab else None
        if o is None:
            return
        if not self.field_snapshot:
            self.remember(tab)
            self.field_snapshot = True
        if "" in self.fields:
            o["name"] = self.fields[""].get().strip()
        for key, entry in self.fields.items():
            if key:
                o["props"][key] = entry.get().strip()
        self.check_fields()
        self.changed(tab)

    def check_fields(self):
        for key, (label, options) in self.warnings.items():
            value = self.fields[key].get().strip()
            label.config(text="" if options is None or value == "" or value in options else "Not found yet: this name does not exist.")

    # ── saving, checking, playing ──

    def changed(self, tab):
        self.draw_objects(tab)
        self.update_title(tab)
        if self.check_job is not None:
            self.root.after_cancel(self.check_job)
        self.check_job = self.root.after(350, self.check_problems)

    def update_title(self, tab):
        self.notebook.tab(tab.frame, text=tab.doc.name + (" *" if tab.dirty else ""))
        if self.shell is not None:
            self.shell.update_marks()

    def update_all(self):
        """After tabs come or go."""
        if self.tabs:
            self.welcome.place_forget()
        else:
            self.welcome.place(relx=0.5, rely=0.4, anchor="center")
        self.build_palette()
        for tab in self.tabs:
            self.update_title(tab)
        self.mark_map_list()
        self.show_fields()
        self.redraw()
        self.check_problems()

    def say_status(self, text):
        self.status.config(text=text)

    def update_status(self):
        tab = self.tab()
        if tab is not None:
            self.status.config(text="%s: %d x %d" % (tab.doc.name, tab.doc.cols, len(tab.doc.rows)))

    def open_texts(self):
        return {t.doc.name: t.doc.text() for t in self.tabs}

    def check_problems(self):
        """The maps as they are in the tabs, saved or not. Runs by itself after each change."""
        self.check_job = None
        self.problem_at = None
        problem = find_problem(self.open_texts())
        if not problem:
            self.problem_label.config(text="No problems in the maps." if self.tabs else "", fg="#208040")
            return
        self.problem_label.config(text=problem.split("\n")[0], fg="#c02020")
        m = re.match(r"maps_src/(\w+)\.map:(\d+)", problem)
        if m:
            self.problem_at = (m.group(1), int(m.group(2)))

    def go_to_problem(self):
        if not self.problem_at:
            return
        name, line = self.problem_at
        tab = self.open_map(name)
        if tab is None:
            return
        hit = tab.doc.object_on_line(line)
        if hit is not None:
            self.set_tool("select")
            tab.selected = hit
            self.show_fields()
            self.draw_objects(tab)

    def save_tab(self, tab=None):
        tab = tab or self.tab()
        if tab is None:
            return
        tab.doc.save()
        tab.saved = tab.doc.text()
        tab.mtime = os.path.getmtime(tab.doc.path)
        self.update_title(tab)
        self.check_problems()
        self.say_status("Saved %s." % tab.doc.name)

    def save_all(self):
        for tab in self.tabs:
            if tab.dirty:
                self.save_tab(tab)
        self.say_status("All saved.")

    def run_game(self, *extra):
        if self.game is not None and self.game.poll() is None:
            self.say_status("The game is already open.")
            return
        self.save_all()
        problem = find_problem({})
        if problem:
            self.tell("Fix this first", problem)
            return
        self.say_status("Building and opening the game...")
        self.game = subprocess.Popen([sys.executable, "-m", "apkpygame", "play"] + list(extra), cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        self.root.after(500, self.watch_game)

    def watch_game(self):
        if self.game is None:
            return
        if self.game.poll() is None:
            self.root.after(500, self.watch_game)
            return
        said = self.game.stdout.read()
        if self.game.returncode:
            self.tell("The game did not open", said.strip()[-1200:])
        else:
            self.say_status("The game was closed.")
        self.game = None

    def play_game(self):
        self.run_game()

    def test_here(self, tab, col, row):
        if self.shell is not None:
            self.shell.start_test(tab.doc.name, col, row)
            return
        self.save_all()
        start_test_here(tab.doc.name, col, row)
        self.run_game("--scene", tab.doc.name)


class PreviewWindow(tk.Toplevel):
    """The map as the game draws it, from the real engine: it takes a moment, and saves your maps first."""

    def __init__(self, parent):
        tk.Toplevel.__init__(self, parent)
        self.title("See in 3D")
        self.geometry("%dx%d" % (px(parent, 640), px(parent, 400)))
        self.minsize(px(parent, 320), px(parent, 220))
        self.shot = None
        self.process = None
        self.again = False
        self.picture = os.path.join(ROOT, "build", "map_preview.png")
        self.photo = None
        self.place_now = None
        self.built_for = None
        top = tk.Frame(self)
        top.pack(side="top", fill="x")
        for text, dc, dr in (("<", -3, 0), ("^", 0, -3), ("v", 0, 3), (">", 3, 0)):
            tk.Button(top, text=text, width=3, command=lambda a=dc, b=dr: self.look(a, b)).pack(side="left", padx=1, pady=2)
        tk.Button(top, text="Refresh", command=self.refresh).pack(side="left", padx=8)
        self.info = tk.Label(top, text="")
        self.info.pack(side="left")
        self.view = tk.Canvas(self, bg="#222222", highlightthickness=0)
        self.view.pack(fill="both", expand=True)
        self.view.bind("<Configure>", lambda e: self.draw_shot())

    def draw_shot(self):
        """The picture at the size of the window, whatever size you make it."""
        if self.shot is None:
            return
        wide, tall = self.view.winfo_width(), self.view.winfo_height()
        scale = min(wide / self.shot.width, tall / self.shot.height)
        size = (max(1, int(self.shot.width * scale)), max(1, int(self.shot.height * scale)))
        self.photo = ImageTk.PhotoImage(self.shot.resize(size, Image.BILINEAR if scale < 1 else Image.NEAREST))
        self.view.delete("all")
        self.view.create_image(wide // 2, tall // 2, image=self.photo)

    def show(self, name, col, row, size):
        self.place_now = [name, col, row, size]
        self.built_for = None
        self.refresh()
        self.lift()

    def look(self, dc, dr):
        if self.place_now:
            name, col, row, size = self.place_now
            self.place_now = [name, max(0, min(size[0] - 1, col + dc)), max(0, min(size[1] - 1, row + dr)), size]
            self.refresh(build=False)

    def refresh(self, build=True):
        if self.process is not None and self.process.poll() is None:
            self.again = True
            return
        name, col, row, _ = self.place_now
        self.info.config(text="Drawing %s, around column %d, row %d..." % (name, col, row))
        if os.path.isfile(self.picture):
            os.remove(self.picture)
        os.makedirs(os.path.dirname(self.picture), exist_ok=True)
        command = [sys.executable, os.path.join(ROOT, "tools", "map_preview.py"), name, str(col), str(row), self.picture]
        if not build and self.built_for is not None:
            command.append("--no-build")
        self.built_for = name
        self.process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        self.after(100, self.watch)

    def watch(self):
        if not self.winfo_exists():
            return
        if self.process.poll() is None:
            self.after(100, self.watch)
            return
        said = self.process.stdout.read().strip()
        if os.path.isfile(self.picture):
            with Image.open(self.picture) as img:
                self.shot = img.convert("RGB")
            self.draw_shot()
            name, col, row, _ = self.place_now
            self.info.config(text="%s, around column %d, row %d" % (name, col, row))
        else:
            self.info.config(text=(said.splitlines() or ["It could not be drawn."])[-1][:120])
        if self.again:
            self.again = False
            self.refresh(build=False)


class NewMapDialog(simpledialog.Dialog):
    def __init__(self, parent, legend):
        self.legend = legend
        self.result = None
        simpledialog.Dialog.__init__(self, parent, "New map")

    def letter_values(self):
        return ["%s  %s%s" % (k, v["tile"], " (solid)" if v["solid"] else "") for k, v in self.legend.items()]

    def body(self, frame):
        tk.Label(frame, text="Name").grid(row=0, column=0, sticky="w")
        self.name = tk.Entry(frame)
        self.name.grid(row=0, column=1, sticky="ew")
        tk.Label(frame, text="Columns").grid(row=1, column=0, sticky="w")
        self.width = tk.Spinbox(frame, from_=3, to=200)
        self.width.delete(0, "end")
        self.width.insert(0, "16")
        self.width.grid(row=1, column=1, sticky="ew")
        tk.Label(frame, text="Rows").grid(row=2, column=0, sticky="w")
        self.height = tk.Spinbox(frame, from_=3, to=200)
        self.height.delete(0, "end")
        self.height.insert(0, "12")
        self.height.grid(row=2, column=1, sticky="ew")
        values = self.letter_values()
        tk.Label(frame, text="Ground").grid(row=3, column=0, sticky="w")
        self.ground = ttk.Combobox(frame, values=values, state="readonly")
        self.ground.grid(row=3, column=1, sticky="ew")
        tk.Label(frame, text="Edge").grid(row=4, column=0, sticky="w")
        self.wall = ttk.Combobox(frame, values=values, state="readonly")
        self.wall.grid(row=4, column=1, sticky="ew")
        keys = list(self.legend)
        self.ground.current(next((i for i, k in enumerate(keys) if not self.legend[k]["solid"]), 0))
        self.wall.current(next((i for i, k in enumerate(keys) if self.legend[k]["solid"]), 0))
        return self.name

    def validate(self):
        try:
            self.size = int(self.width.get()), int(self.height.get())
        except ValueError:
            messagebox.showinfo("New map", "Columns and rows are numbers.", parent=self)
            return False
        if self.size[0] < 3 or self.size[1] < 3:
            messagebox.showinfo("New map", "A map is at least 3 by 3.", parent=self)
            return False
        return bool(self.name.get().strip())

    def apply(self):
        self.result = (self.name.get().strip(), self.size[0], self.size[1], self.ground.get()[0], self.wall.get()[0])


class NewLetterDialog(simpledialog.Dialog):
    """A line for maps_src/legend.txt."""

    def __init__(self, parent, legend):
        self.legend = legend
        self.result = None
        simpledialog.Dialog.__init__(self, parent, "New tile letter")

    def body(self, frame):
        tk.Label(frame, text="Letter").grid(row=0, column=0, sticky="w")
        self.letter = tk.Entry(frame, width=4)
        self.letter.grid(row=0, column=1, sticky="w")
        tk.Label(frame, text="Tile (a picture in assets/tiles/)").grid(row=1, column=0, sticky="w")
        self.tile = ttk.Combobox(frame, values=map_tool.tile_names(), state="readonly")
        self.tile.current(0)
        self.tile.grid(row=1, column=1, sticky="ew")
        self.solid = tk.BooleanVar()
        tk.Checkbutton(frame, text="Solid: it cannot be walked on", variable=self.solid).grid(row=2, column=0, columnspan=2, sticky="w")
        tk.Label(frame, text="Height (blocks, 0 is flat)").grid(row=3, column=0, sticky="w")
        self.height = tk.Spinbox(frame, from_=0, to=9, width=4)
        self.height.grid(row=3, column=1, sticky="w")
        tk.Label(frame, text="Zone (monsters come out, or empty)").grid(row=4, column=0, sticky="w")
        self.zone = tk.Entry(frame)
        self.zone.grid(row=4, column=1, sticky="ew")
        self.edges = tk.BooleanVar()
        tk.Checkbutton(frame, text="Edges: cut its corners where it meets other ground", variable=self.edges).grid(row=5, column=0, columnspan=2, sticky="w")
        return self.letter

    def validate(self):
        letter = self.letter.get().strip()
        if len(letter) != 1 or letter in self.legend or letter == "#":
            messagebox.showinfo("New tile letter", "Write one character that is not used yet. Used: " + " ".join(self.legend), parent=self)
            return False
        if not self.height.get().isdigit():
            messagebox.showinfo("New tile letter", "The height is a number.", parent=self)
            return False
        return True

    def apply(self):
        line = "%s = %s" % (self.letter.get().strip(), self.tile.get())
        if self.solid.get():
            line += " solid"
        if int(self.height.get()):
            line += " height=%d" % int(self.height.get())
        if self.zone.get().strip():
            line += " zone=" + self.zone.get().strip()
        if self.edges.get():
            line += " edges"
        self.result = line


def main():
    names = sys.argv[1:]
    known = all_maps()
    for name in names:
        if name not in known:
            sys.exit("there is no maps_src/%s.map. Maps: %s. To make one, open the editor and press New map." % (name, ", ".join(known)))
    root = studio_ui.make_root("Map editor")
    Editor(root, names)
    root.mainloop()


if __name__ == "__main__":
    main()
