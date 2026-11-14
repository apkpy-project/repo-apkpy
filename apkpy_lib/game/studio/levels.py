"""Levels: maps of tiles in the .tmj files Tiled makes and opens, so a level can be changed here, in Tiled, or both.

Paint tiles on a layer, place the game's objects on an object layer, mark a layer solid, make a new level (with a
starter set of tiles when there is none). The build reads them: Tilemap(level, solid=[...], objects={...}), where
each object's class is the name of an entry of objects.
"""
import copy
import glob
import json
import os
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from PIL import Image, ImageDraw, ImageTk

from .code import slug
from .objects import object_picture
from .source import Call, literal
from .ui import ACCENT, BAD, LINE, MUTED, PANEL, px

LEVEL_FOLDERS = ("levels", "maps", "assets")
TOOLS = (("paint", "Paint"), ("erase", "Erase"), ("fill", "Fill"), ("pick", "Pick"))
STARTER_COLOURS = (("grass", (94, 170, 70), (70, 130, 52)), ("dirt", (150, 102, 62), (120, 80, 48)),
                   ("stone", (128, 132, 142), (98, 102, 112)), ("brick", (176, 84, 64), (138, 62, 48)),
                   ("water", (64, 132, 210), (48, 104, 176)), ("wood", (176, 128, 74), (140, 98, 56)),
                   ("sand", (226, 204, 136), (198, 176, 110)), ("dark", (52, 56, 70), (36, 38, 50)))


def level_files(root):
    out = []
    for folder in LEVEL_FOLDERS:
        for path in sorted(glob.glob(os.path.join(root, folder, "**", "*.tmj"), recursive=True)):
            out.append(os.path.relpath(path, root).replace(os.sep, "/"))
    return out


def dump(value, indent=0):
    """JSON as Tiled writes it: a key on each line, and a list of numbers (a layer's tiles) on one line."""
    pad = " " * indent
    if isinstance(value, dict):
        if not value:
            return "{}"
        inner = ",\n".join("%s %s:%s" % (pad, json.dumps(k), dump(v, indent + 1)) for k, v in value.items())
        return "{\n%s\n%s}" % (inner, pad)
    if isinstance(value, list):
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value):
            return "[" + ", ".join(json.dumps(v) for v in value) + "]"
        if not value:
            return "[]"
        inner = ",\n".join("%s %s" % (pad, dump(v, indent + 1)) for v in value)
        return "[\n%s\n%s]" % (inner, pad)
    return json.dumps(value, ensure_ascii=False)


class Level:
    """One .tmj file: its layers, its tileset, its objects. Unknown keys are kept as they were."""

    def __init__(self, root, rel):
        self.root, self.rel = root, rel
        self.path = os.path.join(root, *rel.split("/"))
        with open(self.path, encoding="utf-8") as fh:
            self.raw = json.load(fh)
        self.saved = copy.deepcopy(self.raw)
        self.undo_stack, self.redo_stack = [], []
        self.read_tileset()

    @property
    def cols(self):
        return self.raw["width"]

    @property
    def rows(self):
        return self.raw["height"]

    @property
    def tile_w(self):
        return self.raw["tilewidth"]

    @property
    def tile_h(self):
        return self.raw["tileheight"]

    def read_tileset(self):
        self.tileset, self.tileset_image = None, None
        sets = self.raw.get("tilesets") or []
        if not sets:
            return
        ts = dict(sets[0])
        base = os.path.dirname(self.path)
        if "source" in ts:
            try:
                ts_path = os.path.normpath(os.path.join(base, ts["source"]))
                with open(ts_path, encoding="utf-8") as fh:
                    ts.update(json.load(fh))
                base = os.path.dirname(ts_path)
            except (OSError, ValueError):
                return
        if "image" not in ts:
            return
        image = os.path.normpath(os.path.join(base, ts["image"]))
        try:
            with Image.open(image) as img:
                self.tileset_image = img.convert("RGBA")
        except OSError:
            return
        tw, th = ts.get("tilewidth", self.tile_w), ts.get("tileheight", self.tile_h)
        margin, spacing = ts.get("margin", 0), ts.get("spacing", 0)
        columns = ts.get("columns") or max(1, (self.tileset_image.width - 2 * margin + spacing) // (tw + spacing))
        rows = max(1, (self.tileset_image.height - 2 * margin + spacing) // (th + spacing))
        self.tileset = {"firstgid": ts.get("firstgid", 1), "tile_w": tw, "tile_h": th, "columns": columns,
                        "count": ts.get("tilecount") or columns * rows, "margin": margin, "spacing": spacing,
                        "image": os.path.relpath(image, self.root).replace(os.sep, "/")}

    def tile_picture(self, gid):
        ts = self.tileset
        if ts is None or gid < ts["firstgid"] or gid >= ts["firstgid"] + ts["count"]:
            return None
        n = gid - ts["firstgid"]
        x = ts["margin"] + (n % ts["columns"]) * (ts["tile_w"] + ts["spacing"])
        y = ts["margin"] + (n // ts["columns"]) * (ts["tile_h"] + ts["spacing"])
        return self.tileset_image.crop((x, y, x + ts["tile_w"], y + ts["tile_h"]))

    def layers(self):
        """The top layers (groups are shown by Tiled; here their layers are listed after them)."""
        out = []

        def walk(layers):
            for layer in layers:
                if layer.get("type") == "group":
                    walk(layer.get("layers", []))
                elif layer.get("type") in ("tilelayer", "objectgroup"):
                    out.append(layer)
        walk(self.raw.get("layers", []))
        return out

    def layer(self, name):
        return next((l for l in self.layers() if l.get("name") == name), None)

    @staticmethod
    def solid(layer):
        return any(p.get("name") == "solid" and p.get("value") is True for p in layer.get("properties", []) or [])

    # ── changes ──

    def remember(self):
        self.undo_stack.append(copy.deepcopy(self.raw))
        self.redo_stack = []

    def undo(self):
        if not self.undo_stack:
            return False
        self.redo_stack.append(self.raw)
        self.raw = self.undo_stack.pop()
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        self.undo_stack.append(self.raw)
        self.raw = self.redo_stack.pop()
        return True

    def get(self, layer, col, row):
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return layer["data"][row * self.cols + col] & 0x1FFFFFFF
        return None

    def set(self, layer, col, row, gid):
        if 0 <= col < self.cols and 0 <= row < self.rows:
            i = row * self.cols + col
            if layer["data"][i] != gid:
                layer["data"][i] = gid
                return True
        return False

    def fill(self, layer, col, row, gid):
        old = self.get(layer, col, row)
        if old is None or old == gid:
            return 0
        todo, done = [(col, row)], 0
        while todo:
            c, r = todo.pop()
            if self.get(layer, c, r) != old:
                continue
            self.set(layer, c, r, gid)
            done += 1
            todo.extend(((c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)))
        return done

    def set_solid(self, layer, on):
        props = [p for p in layer.get("properties", []) or [] if p.get("name") != "solid"]
        if on:
            props.append({"name": "solid", "type": "bool", "value": True})
        if props:
            layer["properties"] = props
        else:
            layer.pop("properties", None)

    def object_at(self, layer, x, y):
        for o in reversed(layer.get("objects", [])):
            w, h = o.get("width", 0) or self.tile_w, o.get("height", 0) or self.tile_h
            top = o["y"] - h if "gid" in o else o["y"]
            if o["x"] <= x < o["x"] + w and top <= y < top + h:
                return o
        return None

    def add_object(self, layer, kind, col, row):
        next_id = self.raw.get("nextobjectid") or 1 + max([o.get("id", 0) for l in self.layers() for o in l.get("objects", [])] or [0])
        o = {"id": next_id, "name": "", "class": kind, "x": col * self.tile_w, "y": row * self.tile_h,
             "width": self.tile_w, "height": self.tile_h, "rotation": 0, "visible": True}
        layer.setdefault("objects", []).append(o)
        self.raw["nextobjectid"] = next_id + 1
        return o

    def add_layer(self, kind, name):
        if kind == "tilelayer":
            layer = {"type": "tilelayer", "name": name, "width": self.cols, "height": self.rows,
                     "data": [0] * (self.cols * self.rows), "visible": True, "opacity": 1, "x": 0, "y": 0}
        else:
            layer = {"type": "objectgroup", "name": name, "objects": [], "visible": True, "opacity": 1, "x": 0, "y": 0}
        next_id = self.raw.get("nextlayerid")
        if next_id:
            layer["id"] = next_id
            self.raw["nextlayerid"] = next_id + 1
        self.raw.setdefault("layers", []).append(layer)
        return layer

    def resize(self, cols, rows):
        """The level gets cols x rows tiles; what is outside goes, what is new is empty."""
        for layer in self.layers():
            if layer.get("type") != "tilelayer":
                continue
            old, data = layer["data"], [0] * (cols * rows)
            for r in range(min(rows, self.rows)):
                for c in range(min(cols, self.cols)):
                    data[r * cols + c] = old[r * self.cols + c]
            layer["data"], layer["width"], layer["height"] = data, cols, rows
        self.raw["width"], self.raw["height"] = cols, rows

    @property
    def dirty(self):
        return self.raw != self.saved

    def save(self):
        if not self.dirty:
            return False
        with open(self.path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(dump(self.raw) + "\n")
        self.saved = copy.deepcopy(self.raw)
        return True


def starter_tiles(path, tile=16):
    """A small set of plain tiles (grass, dirt, stone, brick, water, wood, sand, dark) to start a level with."""
    img = Image.new("RGBA", (tile * len(STARTER_COLOURS), tile), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for n, (name, light, dark) in enumerate(STARTER_COLOURS):
        x = n * tile
        draw.rectangle((x, 0, x + tile - 1, tile - 1), fill=light)
        if name == "grass":
            draw.rectangle((x, tile // 4, x + tile - 1, tile - 1), fill=(150, 102, 62))
            for i in range(0, tile, 3):
                draw.point((x + i, tile // 4), fill=dark)
        elif name == "brick":
            for r in range(0, tile, tile // 4):
                draw.line((x, r, x + tile - 1, r), fill=dark)
                shift = (tile // 4) if (r // (tile // 4)) % 2 else 0
                for c in range(shift, tile, tile // 2):
                    draw.line((x + c, r, x + c, r + tile // 4), fill=dark)
        elif name == "water":
            for r in range(tile // 4, tile, tile // 3):
                draw.line((x + 2, r, x + tile - 3, r), fill=(150, 200, 240))
        elif name == "wood":
            for c in range(0, tile, tile // 4):
                draw.line((x + c, 0, x + c, tile - 1), fill=dark)
        else:
            for i in range(tile // 2):
                draw.point((x + (i * 7) % tile, (i * 5) % tile), fill=dark)
        draw.rectangle((x, 0, x + tile - 1, tile - 1), outline=dark)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    return len(STARTER_COLOURS)


def new_level(root, name, cols, rows, tile, tileset_rel=None):
    """levels/NAME.tmj: a ground layer (solid), a decor layer and a things layer. Gives back its path."""
    rel = "levels/%s.tmj" % slug(name)
    path = os.path.join(root, *rel.split("/"))
    if os.path.exists(path):
        raise ValueError("There is already a level called %s." % slug(name))
    if tileset_rel is None:
        tileset_rel = "assets/tiles.png"
        if not os.path.isfile(os.path.join(root, *tileset_rel.split("/"))):
            starter_tiles(os.path.join(root, *tileset_rel.split("/")), tile)
    image_path = os.path.join(root, *tileset_rel.split("/"))
    with Image.open(image_path) as img:
        width, height = img.size
    columns = max(1, width // tile)
    raw = {"type": "map", "version": "1.10", "orientation": "orthogonal", "renderorder": "right-down",
           "width": cols, "height": rows, "tilewidth": tile, "tileheight": tile, "infinite": False,
           "nextlayerid": 4, "nextobjectid": 1,
           "tilesets": [{"firstgid": 1, "name": os.path.splitext(os.path.basename(tileset_rel))[0],
                         "image": os.path.relpath(image_path, os.path.dirname(path)).replace(os.sep, "/"),
                         "imagewidth": width, "imageheight": height, "tilewidth": tile, "tileheight": tile,
                         "columns": columns, "tilecount": columns * max(1, height // tile), "margin": 0, "spacing": 0}],
           "layers": [{"id": 1, "type": "tilelayer", "name": "ground", "width": cols, "height": rows,
                       "data": [1 if r == rows - 1 else 0 for r in range(rows) for _ in range(cols)],
                       "visible": True, "opacity": 1, "x": 0, "y": 0,
                       "properties": [{"name": "solid", "type": "bool", "value": True}]},
                      {"id": 2, "type": "tilelayer", "name": "decor", "width": cols, "height": rows,
                       "data": [0] * (cols * rows), "visible": True, "opacity": 1, "x": 0, "y": 0},
                      {"id": 3, "type": "objectgroup", "name": "things", "objects": [], "visible": True,
                       "opacity": 1, "x": 0, "y": 0}]}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dump(raw) + "\n")
    return rel


def tilemaps_of(code, rel):
    """[(source, Tilemap call)] of the code that uses the level rel."""
    out = []
    for source in code.files():
        names = {name for name, kind, path in source.assets("tilemap") if path == rel}
        if not names:
            continue
        for piece in source.pieces:
            for call in calls_in(piece):
                if call.func == "Tilemap":
                    first = call.get(0) or call.get("map")
                    if first is not None and first.name in names:
                        out.append((source, call))
    return out


def calls_in(piece):
    found = []

    def walk(value):
        if isinstance(value, Call):
            found.append(value)
        for item in getattr(value, "items", ()):
            walk(item.value)
    walk(piece.call if piece.call is not None else piece.entity)      # an add's entity is inside its call
    return found


class LevelsScreen(tk.Frame):
    """The levels on the left; the chosen one in the middle, to paint; tiles or objects on the right."""

    section = "levels"

    def __init__(self, parent, shell):
        tk.Frame.__init__(self, parent)
        self.shell, self.code = shell, shell.code
        self.root_folder = shell.folder
        self.levels = {}
        self.chosen = None
        self.layer_name = None
        self.tool = "paint"
        self.gid = 1
        self.kind = None
        self.zoom = 2
        self.dragging = None
        self.photos = {}
        self.build()
        self.fill_list()

    # ── the window ──

    def build(self):
        left = tk.Frame(self, padx=px(self, 10), pady=px(self, 10))
        left.pack(side="left", fill="y")
        tk.Label(left, text="Levels", font=("", 15, "bold")).pack(anchor="w")
        tk.Label(left, text="Maps of tiles: Tiled opens them too.", fg=MUTED).pack(anchor="w", pady=(0, px(self, 6)))
        self.items = tk.Listbox(left, activestyle="none", exportselection=False, width=24, height=14)
        self.items.pack(fill="y", expand=True)
        self.items.bind("<<ListboxSelect>>", lambda e: self.pick())
        tk.Button(left, text="New level...", command=self.new).pack(fill="x", pady=(px(self, 6), 0))
        tk.Button(left, text="Size...", command=self.resize).pack(fill="x", pady=(px(self, 4), 0))
        tk.Frame(self, bg=LINE, width=1).pack(side="left", fill="y")

        middle = tk.Frame(self)
        middle.pack(side="left", fill="both", expand=True)
        bar = tk.Frame(middle, padx=px(self, 8), pady=px(self, 6))
        bar.pack(fill="x")
        tk.Label(bar, text="Layer").pack(side="left")
        self.layer_box = ttk.Combobox(bar, state="readonly", width=16)
        self.layer_box.pack(side="left", padx=(px(self, 4), px(self, 10)))
        self.layer_box.bind("<<ComboboxSelected>>", lambda e: self.choose_layer(self.layer_box.get().split("  (")[0]))
        self.tool_buttons = {}
        for key, label in TOOLS:
            b = tk.Button(bar, text=label, command=lambda k=key: self.set_tool(k), padx=px(self, 6))
            b.pack(side="left", padx=1)
            self.tool_buttons[key] = b
        tk.Button(bar, text="-", width=2, command=lambda: self.set_zoom(-1)).pack(side="left", padx=(px(self, 10), 1))
        tk.Button(bar, text="+", width=2, command=lambda: self.set_zoom(1)).pack(side="left")
        self.solid = tk.BooleanVar(value=False)
        self.solid_box = tk.Checkbutton(bar, text="Solid: bodies stand on it", variable=self.solid, command=self.solid_changed)
        self.solid_box.pack(side="left", padx=px(self, 10))
        self.note = tk.Label(middle, text="", fg=MUTED, anchor="w", padx=px(self, 8))
        self.note.pack(fill="x")
        holder = tk.Frame(middle)
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, bg="#1b1e26", highlightthickness=0)
        ys = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
        xs = ttk.Scrollbar(middle, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=xs.set, yscrollcommand=ys.set)
        ys.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        xs.pack(fill="x")
        self.canvas.bind("<Button-1>", lambda e: self.press(e, False))
        self.canvas.bind("<B1-Motion>", lambda e: self.drag(e, False))
        self.canvas.bind("<ButtonRelease-1>", lambda e: self.release())
        self.canvas.bind("<Button-3>", lambda e: self.press(e, True))
        self.canvas.bind("<B3-Motion>", lambda e: self.drag(e, True))
        self.canvas.bind("<ButtonRelease-3>", lambda e: self.release())

        tk.Frame(self, bg=LINE, width=1).pack(side="left", fill="y")
        self.palette = tk.Frame(self, padx=px(self, 8), pady=px(self, 8), width=px(self, 220))
        self.palette.pack(side="left", fill="y")
        self.palette.pack_propagate(False)

    def set_tool(self, tool):
        self.tool = tool
        for key, b in self.tool_buttons.items():
            b.configure(bg=ACCENT if key == tool else "#e9ebef", fg="#ffffff" if key == tool else "#22252b")

    def set_zoom(self, step):
        self.zoom = max(1, min(6, self.zoom + step))
        self.photos = {}
        self.draw()
        self.draw_palette()

    # ── the list ──

    def fill_list(self):
        self.files = level_files(self.root_folder)
        self.items.delete(0, "end")
        for rel in self.files:
            mark = " *" if rel in self.levels and self.levels[rel].dirty else ""
            self.items.insert("end", rel.split("/", 1)[-1] + mark)
        if self.chosen not in self.files:
            self.chosen = self.files[0] if self.files else None
        if self.chosen:
            at = self.files.index(self.chosen)
            self.items.selection_clear(0, "end")
            self.items.selection_set(at)
        self.open_chosen()

    def pick(self):
        chosen = self.items.curselection()
        if chosen:
            self.chosen = self.files[chosen[0]]
            self.open_chosen()

    def go_to(self, rel):
        self.chosen = rel
        self.fill_list()

    def level(self):
        if not self.chosen:
            return None
        if self.chosen not in self.levels:
            try:
                self.levels[self.chosen] = Level(self.root_folder, self.chosen)
            except (OSError, ValueError, KeyError) as e:
                self.note.config(text="%s cannot be read: %s" % (self.chosen, e), fg=BAD)
                return None
        return self.levels[self.chosen]

    def open_chosen(self):
        level = self.level()
        self.photos = {}
        self.set_tool(self.tool)
        if level is None:
            self.layer_box.configure(values=[])
            self.canvas.delete("all")
            self.draw_palette()
            if not self.chosen:
                self.note.config(text="No levels yet: make one with New level.", fg=MUTED)
            return
        names = []
        for layer in level.layers():
            names.append(layer["name"] + ("  (objects)" if layer["type"] == "objectgroup" else ""))
        self.layer_box.configure(values=names)
        if level.layer(self.layer_name) is None:
            tiles = [l for l in level.layers() if l["type"] == "tilelayer"]
            self.layer_name = tiles[0]["name"] if tiles else (level.layers()[0]["name"] if level.layers() else None)
        self.choose_layer(self.layer_name)

    def choose_layer(self, name):
        level = self.level()
        self.layer_name = name
        layer = level.layer(name) if level else None
        if layer is not None:
            self.layer_box.set(name + ("  (objects)" if layer["type"] == "objectgroup" else ""))
            self.solid.set(Level.solid(layer))
            self.solid_box.configure(state="normal" if layer["type"] == "tilelayer" else "disabled")
        uses = tilemaps_of(self.code, self.chosen) if self.code is not None else []
        if level is not None:
            where = "Used by Tilemap(...) in %s." % ", ".join(sorted({s.rel for s, _ in uses})) if uses else \
                "No scene uses it yet: Scenes > Add to the scene > A level made in Tiled."
            self.note.config(text="%d x %d tiles of %d x %d. %s Left button: %s; right button: erase." % (
                level.cols, level.rows, level.tile_w, level.tile_h, where,
                "place" if layer is not None and layer["type"] == "objectgroup" else "paint"), fg=MUTED)
        self.draw()
        self.draw_palette()

    # ── drawing ──

    def draw(self):
        self.canvas.delete("all")
        level = self.level()
        if level is None:
            return
        z = self.zoom
        w, h = level.cols * level.tile_w, level.rows * level.tile_h
        picture = Image.new("RGBA", (w, h), (40, 44, 56, 255))
        for layer in level.layers():
            if layer["type"] != "tilelayer" or not layer.get("visible", True):
                continue
            faded = layer["name"] != self.layer_name and self.layer_kind() == "tilelayer"
            for i, gid in enumerate(layer["data"]):
                gid &= 0x1FFFFFFF
                if not gid:
                    continue
                tile = level.tile_picture(gid)
                if tile is None:
                    continue
                if faded:
                    tile = tile.copy()
                    tile.putalpha(tile.getchannel("A").point(lambda a: a // 2))
                picture.alpha_composite(tile, ((i % level.cols) * level.tile_w, (i // level.cols) * level.tile_h))
        self.map_photo = ImageTk.PhotoImage(picture.resize((w * z, h * z), Image.NEAREST))
        self.canvas.create_image(0, 0, image=self.map_photo, anchor="nw")
        for c in range(level.cols + 1):
            self.canvas.create_line(c * level.tile_w * z, 0, c * level.tile_w * z, h * z, fill="#ffffff", stipple="gray12")
        for r in range(level.rows + 1):
            self.canvas.create_line(0, r * level.tile_h * z, w * z, r * level.tile_h * z, fill="#ffffff", stipple="gray12")
        for layer in level.layers():
            if layer["type"] == "objectgroup" and layer.get("visible", True):
                for o in layer.get("objects", []):
                    self.draw_object(level, o, layer["name"] == self.layer_name)
        self.canvas.configure(scrollregion=(0, 0, w * z, h * z))

    def draw_object(self, level, o, current):
        z = self.zoom
        kind = o.get("class") or o.get("type") or o.get("name") or "?"
        w, h = (o.get("width") or level.tile_w), (o.get("height") or level.tile_h)
        top = o["y"] - h if "gid" in o else o["y"]
        x0, y0 = o["x"] * z, top * z
        photo = self.object_photo(kind, max(8, int(min(w, h) * z)))
        if photo is not None:
            self.canvas.create_image(x0 + w * z / 2, y0 + h * z / 2, image=photo)
        if current or photo is None:
            self.canvas.create_rectangle(x0, y0, x0 + w * z, y0 + h * z, outline="#ffd45c" if current else "#9aa3b5")
        if photo is None:
            self.canvas.create_text(x0 + 2, y0 + 1, text=kind, anchor="nw", fill="#ffffff", font=("", 8))

    def object_photo(self, kind, side):
        key = ("object", kind, side)
        if key in self.photos:
            return self.photos[key]
        photo = None
        prefab = self.prefab_for(kind)
        if prefab is not None:
            source, piece, call = prefab
            try:
                pic = object_picture(self.code, source, piece.entity, 64, piece.params, call, background=None)
            except (OSError, ValueError):
                pic = None
            if pic is not None:
                photo = ImageTk.PhotoImage(pic.resize((side, side), Image.NEAREST))
        self.photos[key] = photo
        return photo

    def prefab_for(self, kind):
        """The @prefab an object class stands for: objects={"coin": coin()} in the code, or a prefab of that name."""
        if self.code is None:
            return None
        for source, call in tilemaps_of(self.code, self.chosen):
            objects = call.get("objects")
            value = objects.get(kind) if objects is not None and hasattr(objects, "get") and hasattr(objects, "items") else None
            if isinstance(value, Call):
                found = self.code.prefab(value.func)
                if found[1] is not None:
                    return found + (value,)
        found = self.code.prefab(kind)
        return found + (None,) if found[1] is not None else None

    def object_kinds(self):
        kinds = []
        if self.code is not None:
            for source, call in tilemaps_of(self.code, self.chosen):
                objects = call.get("objects")
                for item in getattr(objects, "items", ()):
                    if isinstance(item.key, str) and item.key not in kinds:
                        kinds.append(item.key)
        level = self.level()
        for layer in level.layers() if level else []:
            for o in layer.get("objects", []):
                kind = o.get("class") or o.get("type") or o.get("name")
                if kind and kind not in kinds:
                    kinds.append(kind)
        return kinds

    def draw_palette(self):
        for child in self.palette.winfo_children():
            child.destroy()
        level = self.level()
        if level is None:
            return
        if self.layer_kind() == "objectgroup":
            tk.Label(self.palette, text="Objects", font=("", 11, "bold")).pack(anchor="w")
            tk.Label(self.palette, text="Click one, then click the level to place it. Drag to move it.", fg=MUTED,
                     wraplength=px(self, 200), justify="left").pack(anchor="w", pady=(0, px(self, 6)))
            kinds = self.object_kinds()
            if self.kind not in kinds:
                self.kind = kinds[0] if kinds else None
            for kind in kinds:
                b = tk.Button(self.palette, text=kind, anchor="w", command=lambda k=kind: self.choose_kind(k),
                              bg=ACCENT if kind == self.kind else "#e9ebef", fg="#ffffff" if kind == self.kind else "#22252b")
                b.pack(fill="x", pady=1)
            tk.Button(self.palette, text="Another object...", command=self.new_kind).pack(fill="x", pady=(px(self, 8), 0))
            return
        tk.Label(self.palette, text="Tiles", font=("", 11, "bold")).pack(anchor="w")
        if level.tileset is None:
            tk.Label(self.palette, text="This level has no tileset picture the Studio can read.", fg=BAD,
                     wraplength=px(self, 200), justify="left").pack(anchor="w")
            return
        tk.Label(self.palette, text=level.tileset["image"], fg=MUTED).pack(anchor="w", pady=(0, px(self, 6)))
        ts = level.tileset
        z = max(2, self.zoom)
        cols = max(1, min(ts["columns"], (px(self, 200)) // (ts["tile_w"] * z + 2)))
        grid = tk.Frame(self.palette)
        grid.pack(anchor="w")
        for n in range(ts["count"]):
            gid = ts["firstgid"] + n
            tile = level.tile_picture(gid)
            if tile is None:
                continue
            photo = ImageTk.PhotoImage(tile.resize((ts["tile_w"] * z, ts["tile_h"] * z), Image.NEAREST))
            self.photos[("palette", gid)] = photo
            cell = tk.Label(grid, image=photo, bd=2, relief="solid" if gid == self.gid else "flat",
                            bg=ACCENT if gid == self.gid else PANEL, cursor="hand2")
            cell.grid(row=n // cols, column=n % cols, padx=1, pady=1)
            cell.bind("<Button-1>", lambda e, g=gid: self.choose_tile(g))

    def choose_tile(self, gid):
        self.gid = gid
        if self.tool not in ("paint", "fill"):
            self.set_tool("paint")
        self.draw_palette()

    def choose_kind(self, kind):
        self.kind = kind
        self.draw_palette()

    def layer_kind(self):
        level = self.level()
        layer = level.layer(self.layer_name) if level else None
        return layer["type"] if layer else None

    # ── the mouse ──

    def cell(self, event):
        level = self.level()
        x, y = self.canvas.canvasx(event.x) / self.zoom, self.canvas.canvasy(event.y) / self.zoom
        return x, y, int(x // level.tile_w), int(y // level.tile_h)

    def press(self, event, erase):
        level = self.level()
        layer = level.layer(self.layer_name) if level else None
        if layer is None:
            return
        level.remember()
        x, y, col, row = self.cell(event)
        if layer["type"] == "objectgroup":
            found = level.object_at(layer, x, y)
            if erase:
                if found is not None:
                    layer["objects"].remove(found)
                self.changed()
                return
            if found is not None:
                self.dragging = (found, x - found["x"], y - found["y"])
                return
            if self.kind is None:
                self.note.config(text="Choose an object on the right first.", fg=BAD)
                return
            o = level.add_object(layer, self.kind, col, row)
            self.dragging = (o, x - o["x"], y - o["y"])
            self.changed()
            return
        tool = "erase" if erase else self.tool
        if tool == "pick":
            gid = level.get(layer, col, row)
            if gid:
                self.choose_tile(gid)
            return
        if tool == "fill":
            level.fill(layer, col, row, self.gid)
            self.changed()
            return
        self.paint(level, layer, col, row, 0 if tool == "erase" else self.gid)

    def drag(self, event, erase):
        level = self.level()
        layer = level.layer(self.layer_name) if level else None
        if layer is None:
            return
        x, y, col, row = self.cell(event)
        if layer["type"] == "objectgroup":
            if self.dragging is not None and not erase:
                o, dx, dy = self.dragging
                o["x"] = round((x - dx) / level.tile_w * 2) * level.tile_w / 2
                o["y"] = round((y - dy) / level.tile_h * 2) * level.tile_h / 2
                o["x"], o["y"] = int(o["x"]) if o["x"] == int(o["x"]) else o["x"], int(o["y"]) if o["y"] == int(o["y"]) else o["y"]
                self.draw()
            return
        tool = "erase" if erase else self.tool
        if tool in ("paint", "erase"):
            self.paint(level, layer, col, row, 0 if tool == "erase" else self.gid)

    def paint(self, level, layer, col, row, gid):
        if level.set(layer, col, row, gid):
            z = self.zoom
            x, y = col * level.tile_w * z, row * level.tile_h * z
            tile = level.tile_picture(gid) if gid else None
            if tile is not None:
                key = ("tile", gid, z)
                if key not in self.photos:
                    self.photos[key] = ImageTk.PhotoImage(tile.resize((level.tile_w * z, level.tile_h * z), Image.NEAREST))
                self.canvas.create_image(x, y, image=self.photos[key], anchor="nw")
            else:
                self.canvas.create_rectangle(x, y, x + level.tile_w * z, y + level.tile_h * z, fill="#282c38", outline="")

    def release(self):
        level = self.level()
        if level is not None and level.undo_stack and level.undo_stack[-1] == level.raw:
            level.undo_stack.pop()                    # a click that changed nothing
        self.dragging = None
        self.changed()

    def changed(self):
        self.draw()
        self.shell.content_changed()
        self.mark()

    def mark(self):
        for n, rel in enumerate(self.files):
            dirty = rel in self.levels and self.levels[rel].dirty
            text = rel.split("/", 1)[-1] + (" *" if dirty else "")
            if self.items.get(n) != text:
                selected = n in self.items.curselection()
                self.items.delete(n)
                self.items.insert(n, text)
                if selected:
                    self.items.selection_set(n)

    def solid_changed(self):
        level = self.level()
        layer = level.layer(self.layer_name) if level else None
        if layer is not None and layer["type"] == "tilelayer":
            level.remember()
            level.set_solid(layer, self.solid.get())
            self.changed()

    # ── new things ──

    def new(self):
        name = simpledialog.askstring("New level", "What is the level called? (level1, cave, sky...)", parent=self)
        if not name:
            return
        size = simpledialog.askstring("New level", "How many tiles across and down? (such as 40 x 12)", parent=self,
                                      initialvalue="40 x 12")
        try:
            cols, rows = [int(v) for v in (size or "").lower().replace("x", " ").split()]
        except ValueError:
            messagebox.showinfo("New level", "Write it as two numbers, such as 40 x 12.", parent=self)
            return
        tileset = "assets/tiles.png" if os.path.isfile(os.path.join(self.root_folder, "assets", "tiles.png")) else None
        try:
            rel = new_level(self.root_folder, name, max(4, min(cols, 500)), max(4, min(rows, 500)), 16, tileset)
        except (ValueError, OSError) as e:
            messagebox.showinfo("New level", str(e), parent=self)
            return
        self.chosen = rel
        self.fill_list()
        self.shell.art_changed()

    def resize(self):
        level = self.level()
        if level is None:
            return
        size = simpledialog.askstring("Size", "Tiles across and down:", parent=self, initialvalue="%d x %d" % (level.cols, level.rows))
        try:
            cols, rows = [int(v) for v in (size or "").lower().replace("x", " ").split()]
        except ValueError:
            return
        level.remember()
        level.resize(max(1, min(cols, 500)), max(1, min(rows, 500)))
        self.changed()

    def new_kind(self):
        """Another object for this level: a @prefab, written into objects={...} of its Tilemap(...)."""
        if self.code is None:
            return
        prefabs = [p.name for _, p in self.code.prefabs()]
        if not prefabs:
            self.note.config(text="Make an object first (Objects > New object).", fg=BAD)
            return
        name = simpledialog.askstring("Another object", "Which object? %s" % ", ".join(prefabs), parent=self)
        if not name or name.strip() not in prefabs:
            return
        name = name.strip()
        uses = tilemaps_of(self.code, self.chosen)
        for source, call in uses:
            objects = call.get("objects")
            if objects is None:
                source.set_arg(call, "objects", "{%s: %s()}" % (literal(name), name))
            elif name not in [i.key for i in getattr(objects, "items", ())]:
                source.insert(objects, "%s: %s()" % (literal(name), name), len(objects.items))
            self.code.touch("levels")
        self.kind = name
        self.shell.content_changed()
        self.draw_palette()

    # ── the Shell ──

    def dirty(self):
        return any(level.dirty for level in self.levels.values())

    def save(self):
        saved = [level.save() for level in self.levels.values()]
        self.mark()
        return any(saved)

    def refresh(self):
        self.photos = {}
        self.fill_list()

    def reload(self):
        self.levels = {}
        self.fill_list()

    def do_undo(self):
        level = self.level()
        if level is not None and level.undo():
            self.changed()

    def do_redo(self):
        level = self.level()
        if level is not None and level.redo():
            self.changed()
