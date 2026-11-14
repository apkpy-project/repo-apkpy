"""The Art section of the Studio: draw pixels and import pictures, for any picture of a game.

A game's pictures are the PNGs of its assets folder. A picture its code cuts in frames (assets.sheet with frame=)
shows those frames, and its preview plays them.

By Ruben Rego (the monster-rpg template's Studio), shared by every game's Studio. The monster-rpg template's
tools/studio_art.py adds its kinds of pictures (monsters, people, tiles), their previews, and its title and sound
screens.
"""
import os
import re
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageDraw, ImageTk

from .ui import ACCENT, LINE, MUTED, PANEL, px

SKIP_OTHERS = ("monster_blank.png", "pixel.png")
SHEET = re.compile(r'assets\.sheet\(\s*["\']([^"\']+)["\']\s*(?:,\s*frame\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*\))?')


class PixelDoc:
    """A picture being changed, cut in cells. No window here."""

    def __init__(self, path, cell=None, labels=None):
        self.path = path
        with Image.open(path) as img:
            self.image = img.convert("RGBA")
        self.cell_size = cell or self.image.size
        self.labels = labels
        self.saved = self.image.tobytes()
        self.undo_steps, self.redo_steps = [], []
        self.clip = None

    @property
    def columns(self):
        return max(1, self.image.width // self.cell_size[0])

    @property
    def rows(self):
        return max(1, self.image.height // self.cell_size[1])

    @property
    def count(self):
        return self.columns * self.rows

    @property
    def dirty(self):
        return self.image.tobytes() != self.saved

    def box(self, cell):
        w, h = self.cell_size
        x, y = (cell % self.columns) * w, (cell // self.columns) * h
        return x, y, x + w, y + h

    def cell_image(self, cell):
        return self.image.crop(self.box(cell))

    def label(self, cell):
        if self.labels and cell < len(self.labels):
            return self.labels[cell]
        if self.count == 1:
            return ""
        return str(cell + 1)

    def remember(self):
        self.undo_steps.append(self.image.copy())
        del self.undo_steps[:-60]
        self.redo_steps = []

    def forget_if_same(self):
        """A stroke that changed nothing leaves no step of undo."""
        if self.undo_steps and self.undo_steps[-1].tobytes() == self.image.tobytes():
            self.undo_steps.pop()

    def do_undo(self):
        return self._swap(self.undo_steps, self.redo_steps)

    def do_redo(self):
        return self._swap(self.redo_steps, self.undo_steps)

    def _swap(self, source, target):
        if not source:
            return False
        target.append(self.image)
        self.image = source.pop()
        return True

    def inside(self, cell, x, y):
        return 0 <= x < self.cell_size[0] and 0 <= y < self.cell_size[1]

    def get(self, cell, x, y):
        left, top, _, _ = self.box(cell)
        return self.image.getpixel((left + x, top + y))

    def put(self, cell, x, y, colour):
        if not self.inside(cell, x, y):
            return False
        left, top, _, _ = self.box(cell)
        if self.image.getpixel((left + x, top + y)) == colour:
            return False
        self.image.putpixel((left + x, top + y), colour)
        return True

    def line(self, cell, x0, y0, x1, y1, colour):
        """Between two mouse positions, so a fast stroke has no holes."""
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        changed = False
        for i in range(steps + 1):
            changed = self.put(cell, x0 + (x1 - x0) * i // steps, y0 + (y1 - y0) * i // steps, colour) or changed
        return changed

    def fill(self, cell, x, y, colour):
        if not self.inside(cell, x, y):
            return False
        old = self.get(cell, x, y)
        if old == colour:
            return False
        todo = [(x, y)]
        while todo:
            px_, py_ = todo.pop()
            if self.inside(cell, px_, py_) and self.get(cell, px_, py_) == old:
                self.put(cell, px_, py_, colour)
                todo += [(px_ + 1, py_), (px_ - 1, py_), (px_, py_ + 1), (px_, py_ - 1)]
        return True

    def flip(self, cell):
        """Left to right."""
        box = self.box(cell)
        self.image.paste(self.cell_image(cell).transpose(Image.FLIP_LEFT_RIGHT), box[:2])

    def clear(self, cell):
        self.image.paste(Image.new("RGBA", self.cell_size, (0, 0, 0, 0)), self.box(cell)[:2])

    def copy_cell(self, cell):
        self.clip = self.cell_image(cell)

    def paste_cell(self, cell, clip=None):
        clip = clip or self.clip
        if clip is None or clip.size != self.cell_size:
            return False
        self.image.paste(clip, self.box(cell)[:2])
        return True

    def palette(self, limit=40):
        """The colours in this picture, most used first."""
        counts = self.image.getcolors(maxcolors=100000) or []
        solid = sorted(((n, c) for n, c in counts if c[3] == 255), key=lambda v: (-v[0], v[1]))
        return [c for _, c in solid[:limit]]

    def import_picture(self, path, cell):
        """A picture of the whole sheet replaces it. Anything else goes in this cell, made to fit."""
        with Image.open(path) as img:
            picture = img.convert("RGBA")
        if picture.size == self.image.size:
            self.image = picture
            return "whole"
        if picture.size != self.cell_size:
            ratio = min(self.cell_size[0] / picture.width, self.cell_size[1] / picture.height)
            size = (max(1, int(picture.width * ratio)), max(1, int(picture.height * ratio)))
            scaled = picture.resize(size, Image.NEAREST)
            canvas = Image.new("RGBA", self.cell_size, (0, 0, 0, 0))
            canvas.paste(scaled, ((self.cell_size[0] - size[0]) // 2, (self.cell_size[1] - size[1]) // 2))
            picture = canvas
        self.image.paste(picture, self.box(cell)[:2])
        return "cell"

    def save(self):
        if self.dirty:
            self.image.save(self.path)
            self.saved = self.image.tobytes()


def art_files(root, kinds=None, deep=True):
    """{kind: [(label, path)]}. "other" is every other PNG of assets/ (its sub-folders too, unless deep is False),
    named by its path."""
    kinds = kinds or {}
    out = {}
    taken = set()
    for kind, (_, folder, _, _) in kinds.items():
        full = os.path.join(root, *folder.split("/"))
        taken.add(os.path.normcase(os.path.abspath(full)))
        names = sorted(os.listdir(full), key=lambda n: (n[:-4].split(".")[0], n[:-4])) if os.path.isdir(full) else []   # a monster, then its variants
        out[kind] = [(n[:-4], os.path.join(full, n)) for n in names if n.endswith(".png")]
    assets = os.path.join(root, "assets")
    other = []
    for d, dirs, names in os.walk(assets):
        dirs[:] = sorted(x for x in dirs if deep and os.path.normcase(os.path.abspath(os.path.join(d, x))) not in taken)
        for n in sorted(names):
            if n.endswith(".png") and n not in SKIP_OTHERS:
                rel = os.path.relpath(os.path.join(d, n), assets).replace(os.sep, "/")
                other.append((rel[:-4], os.path.join(d, n)))
    out["other"] = sorted(other)
    return out


def sheet_frames(root):
    """{picture's path: (width, height) of a frame} for the pictures the game's code cuts in frames."""
    found = {}
    for d, dirs, names in os.walk(os.path.join(root, "game")):
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        for n in names:
            if n.endswith(".py"):
                with open(os.path.join(d, n), encoding="utf-8") as fh:
                    for m in SHEET.finditer(fh.read()):
                        size = (int(m.group(2)), int(m.group(3))) if m.group(2) else (16, 16)
                        found[os.path.normcase(os.path.abspath(os.path.join(root, *m.group(1).split("/"))))] = size
    return found


def checker(size, square):
    """The squares that mean transparent."""
    img = Image.new("RGB", size, (236, 238, 242))
    draw = ImageDraw.Draw(img)
    for y in range(0, size[1], square):
        for x in range(0, size[0], square):
            if (x // square + y // square) % 2:
                draw.rectangle([x, y, x + square - 1, y + square - 1], fill=(214, 217, 223))
    return img


def to_hex(colour):
    return "#%02x%02x%02x" % tuple(colour[:3])


class ArtScreen(tk.Frame):
    DEEP = True          # the pictures of sub-folders of assets/ too
    TOOLS = (("pencil", "Pencil (P)"), ("eraser", "Eraser (E)"), ("fill", "Fill (G)"), ("pick", "Pick colour (I)"))

    def __init__(self, parent, shell):
        tk.Frame.__init__(self, parent)
        self.shell, self.project = shell, shell.project
        self.docs = {}
        self.doc = None
        self.cell = 0
        self.tool = "pencil"
        self.colour = (40, 44, 60, 255)
        self.zoom = 8
        self.show_grid = tk.BooleanVar(value=True)
        self.last = None
        self.frame_index = 0
        self.thumbs = {}
        self.build()
        self.fill_tree()
        if not self.kinds():
            self.open_first()
        self.animate()

    def open_first(self):
        """A game with no kit opens on its first picture."""
        for kind in self.tree.get_children(""):
            items = self.tree.get_children(kind)
            if items:
                self.tree.selection_set(items[0])
                self.tree.see(items[0])
                self.tree_selected()
                return

    # ── the window ──

    def build(self):
        left = tk.Frame(self, width=px(self, 220))
        left.pack(side="left", fill="y", padx=px(self, 8), pady=px(self, 8))
        left.pack_propagate(False)
        buttons = tk.Frame(left)
        buttons.pack(side="bottom", fill="x", pady=(px(self, 6), 0))
        for words, command in self.new_buttons():
            tk.Button(buttons, text=words, command=command).pack(fill="x", pady=1)
        box = tk.Frame(left)
        box.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(box, show="tree", selectmode="browse")
        bar = ttk.Scrollbar(box, command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.tree_selected())

        self.right = tk.Frame(self, width=px(self, 250))
        self.right.pack(side="right", fill="y", padx=px(self, 8), pady=px(self, 8))
        self.right.pack_propagate(False)
        tk.Label(self.right, text="Colour", font=("", 10, "bold")).pack(anchor="w")
        row = tk.Frame(self.right)
        row.pack(anchor="w", pady=(px(self, 2), px(self, 6)))
        self.swatch = tk.Label(row, bg=to_hex(self.colour), width=6, height=2, relief="flat", cursor="hand2", highlightthickness=1, highlightbackground=LINE)
        self.swatch.pack(side="left")
        self.swatch.bind("<Button-1>", lambda e: self.choose_colour())
        tk.Button(row, text="Choose...", command=self.choose_colour).pack(side="left", padx=px(self, 6))
        tk.Label(self.right, text="In this picture", fg=MUTED).pack(anchor="w")
        self.palette_frame = tk.Frame(self.right)
        self.palette_frame.pack(anchor="w", pady=(px(self, 2), px(self, 10)))
        tk.Label(self.right, text="Preview", font=("", 10, "bold")).pack(anchor="w")
        self.preview_text = tk.Label(self.right, text="", fg=MUTED, justify="left", wraplength=px(self, 230))
        self.preview_text.pack(anchor="w")
        self.preview = tk.Canvas(self.right, width=px(self, 230), height=px(self, 180), bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        self.preview.pack(anchor="w", pady=px(self, 2))

        middle = tk.Frame(self)
        middle.pack(side="left", fill="both", expand=True, pady=px(self, 8))
        top = tk.Frame(middle)
        top.pack(fill="x")
        self.tool_buttons = {}
        for tool, text in self.TOOLS:
            button = tk.Button(top, text=text, command=lambda t=tool: self.set_tool(t))
            button.pack(side="left", padx=1)
            self.tool_buttons[tool] = button
        tk.Button(top, text="Undo", command=self.do_undo).pack(side="left", padx=(px(self, 10), 1))
        tk.Button(top, text="Redo", command=self.do_redo).pack(side="left", padx=1)
        tk.Button(top, text="-", width=2, command=lambda: self.set_zoom(self.zoom - 1)).pack(side="left", padx=(px(self, 10), 1))
        tk.Button(top, text="+", width=2, command=lambda: self.set_zoom(self.zoom + 1)).pack(side="left", padx=1)
        tk.Checkbutton(top, text="Grid", variable=self.show_grid, command=self.draw).pack(side="left", padx=px(self, 6))
        second = tk.Frame(middle)
        second.pack(fill="x", pady=(px(self, 3), 0))
        for text, command in (("Flip", self.flip), ("Copy", self.copy_cell), ("Paste", self.paste_cell), ("Clear", self.clear_cell), ("Import a picture...", self.import_picture)):
            tk.Button(second, text=text, command=command).pack(side="left", padx=1)
        self.title_label = tk.Label(second, text="", fg=MUTED)
        self.title_label.pack(side="left", padx=px(self, 8))
        self.strip = tk.Frame(middle)
        self.strip.pack(fill="x", pady=(px(self, 4), 0))
        area = tk.Frame(middle)
        area.pack(fill="both", expand=True, pady=(px(self, 4), 0))
        self.canvas = tk.Canvas(area, bg="#3a3f4a", highlightthickness=0)
        bar_y = ttk.Scrollbar(area, command=self.canvas.yview)
        bar_x = ttk.Scrollbar(area, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=bar_y.set, xscrollcommand=bar_x.set)
        bar_y.pack(side="right", fill="y")
        bar_x.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.canvas.bind("<Button-3>", self.pick_at)
        self.canvas.bind("<Motion>", self.hover)
        self.canvas.bind("<Control-MouseWheel>", lambda e: self.set_zoom(self.zoom + (1 if e.delta > 0 else -1)))
        self.position = tk.Label(middle, text="", fg=MUTED, anchor="w")
        self.position.pack(fill="x")
        self.set_tool("pencil")

    # ── what a game's pictures are: a kit can say more ──

    def kinds(self):
        """{kind: (its name in the list, its folder, the size of a cell, the names of the cells)}, in order. A kit
        (the monster RPG) has its own; any other game has only its assets folder."""
        return {}

    def new_buttons(self):
        return (("New picture...", self.new_picture),)

    def sheet_cell(self, path):
        """The size of a frame when the game's code cuts this picture in frames (assets.sheet), or None."""
        if not hasattr(self, "sheets"):
            self.sheets = sheet_frames(self.project.root)
        return self.sheets.get(os.path.normcase(os.path.abspath(path)))

    def fill_tree(self):
        keep = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        self.thumbs = {}
        self.sheets = sheet_frames(self.project.root)
        kinds = self.kinds()
        files = art_files(self.project.root, kinds, self.DEEP)
        self.path_of = {}
        names = dict((k, v[0]) for k, v in kinds.items())
        names["other"] = "Everything else" if kinds else "Pictures"
        first = (list(kinds) or ["other"])[0]
        for kind in list(kinds) + ["other"]:
            self.tree.insert("", "end", iid=kind, text=names[kind], open=kind == first)
            for label, path in files[kind]:
                iid = "%s/%s" % (kind, label)
                self.path_of[iid] = (kind, path)
                image = self.list_image(kind, path)
                mark = " *" if path in self.docs and self.docs[path].dirty else ""
                self.tree.insert(kind, "end", iid=iid, text=" " + label + mark, **({"image": image} if image else {}))
        if keep and self.tree.exists(keep[0]):
            self.tree.selection_set(keep[0])

    def list_image(self, kind, path):
        try:
            with Image.open(path) as img:
                kinds = self.kinds()
                cell = kinds[kind][2] if kind in kinds else self.sheet_cell(path) or img.size
                picture = img.convert("RGBA").crop((0, 0, cell[0], cell[1]))
        except OSError:
            return None
        size = px(self, 22)
        ratio = min(size / picture.width, size / picture.height)
        photo = ImageTk.PhotoImage(picture.resize((max(1, int(picture.width * ratio)), max(1, int(picture.height * ratio))), Image.NEAREST))
        self.thumbs[path] = photo
        return photo

    def tree_selected(self):
        chosen = self.tree.selection()
        if chosen and chosen[0] in self.path_of:
            self.open_file(*self.path_of[chosen[0]])

    def open_file(self, kind, path):
        if path not in self.docs:
            kinds = self.kinds()
            cell, labels = (kinds[kind][2], kinds[kind][3]) if kind in kinds else (self.sheet_cell(path), None)
            self.docs[path] = PixelDoc(path, cell, labels)
        self.doc = self.docs[path]
        self.kind = kind
        self.cell = 0
        big = max(self.doc.cell_size)
        self.zoom = max(1, min(16, px(self, 440) // big))
        self.title_label.config(text=self.describe())
        self.show_strip()
        self.show_palette()
        self.draw()

    def go_to(self, target):
        """target: a kind and a picture, such as other/hero (or monsters/cindlet in the monster RPG)."""
        if self.tree.exists(target):
            self.tree.item(target.split("/")[0], open=True)
            self.tree.selection_set(target)
            self.tree.see(target)
            self.tree_selected()

    def describe(self):
        w, h = self.doc.image.size
        cw, ch = self.doc.cell_size
        return "%d x %d" % (w, h) + ("" if (cw, ch) == (w, h) else ", in cells of %d x %d" % (cw, ch))

    def show_strip(self):
        """One small picture for each cell, to pick from."""
        for child in self.strip.winfo_children():
            child.destroy()
        self.strip_photos = []
        self.strip_cells = []
        if self.doc.count < 2:
            return
        size = px(self, 40)
        per_row = self.doc.columns
        for cell in range(self.doc.count):
            box = tk.Frame(self.strip, highlightthickness=2, highlightbackground=LINE)
            box.grid(row=cell // per_row, column=cell % per_row, padx=1, pady=1)
            label = tk.Label(box, bg=PANEL, cursor="hand2")
            label.pack()
            label.bind("<Button-1>", lambda e, c=cell: self.pick_cell(c))
            self.strip_cells.append((box, label))
            words = self.cell_words(cell)
            if words:
                tk.Label(box, text=words, font=("", 7), fg=MUTED).pack()
        self.update_strip()

    def cell_words(self, cell):
        return self.doc.label(cell)

    def update_strip(self):
        if not self.doc or self.doc.count < 2 or not getattr(self, "strip_cells", None):
            return
        size = px(self, 36)
        self.strip_photos = []
        for cell, (box, label) in enumerate(self.strip_cells):
            picture = self.doc.cell_image(cell)
            ratio = min(size / picture.width, size / picture.height)
            shown = picture.resize((max(1, int(picture.width * ratio)), max(1, int(picture.height * ratio))), Image.NEAREST)
            photo = ImageTk.PhotoImage(shown)
            self.strip_photos.append(photo)
            label.configure(image=photo)
            box.configure(highlightbackground=ACCENT if cell == self.cell else LINE)

    def pick_cell(self, cell):
        self.cell = cell
        self.update_strip()
        self.draw()

    def show_palette(self):
        for child in self.palette_frame.winfo_children():
            child.destroy()
        for i, colour in enumerate(self.doc.palette(40)):
            spot = tk.Label(self.palette_frame, bg=to_hex(colour), width=2, cursor="hand2", highlightthickness=1, highlightbackground=LINE)
            spot.grid(row=i // 8, column=i % 8, padx=1, pady=1)
            spot.bind("<Button-1>", lambda e, c=colour: self.set_colour(c))

    def set_tool(self, tool):
        self.tool = tool
        for name, button in self.tool_buttons.items():
            button.configure(bg="#ffe680" if name == tool else "#e9ebef")
        self.canvas.configure(cursor={"pencil": "pencil", "eraser": "dotbox", "fill": "spraycan", "pick": "crosshair"}[tool])

    def set_colour(self, colour):
        self.colour = tuple(colour)
        self.swatch.configure(bg=to_hex(colour))
        if self.tool in ("eraser", "pick"):
            self.set_tool("pencil")

    def choose_colour(self):
        rgb, _ = colorchooser.askcolor(color=to_hex(self.colour), parent=self, title="A colour")
        if rgb:
            self.set_colour((int(rgb[0]), int(rgb[1]), int(rgb[2]), 255))

    def set_zoom(self, zoom):
        self.zoom = max(1, min(32, zoom))
        self.draw()

    # ── drawing the picture ──

    def draw(self):
        self.canvas.delete("all")
        if self.doc is None:
            self.canvas.create_text(px(self, 300), px(self, 120), text="Pick a picture on the left.", fill="#c8ccd6")
            return
        picture = self.doc.cell_image(self.cell)
        size = (picture.width * self.zoom, picture.height * self.zoom)
        out = checker(size, max(4, self.zoom)).convert("RGBA")
        out.alpha_composite(picture.resize(size, Image.NEAREST))
        if self.show_grid.get() and self.zoom >= 6:
            pen = ImageDraw.Draw(out)
            for x in range(0, size[0], self.zoom):
                pen.line([(x, 0), (x, size[1])], fill=(0, 0, 0, 40))
            for y in range(0, size[1], self.zoom):
                pen.line([(0, y), (size[0], y)], fill=(0, 0, 0, 40))
        self.photo = ImageTk.PhotoImage(out)
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.canvas.configure(scrollregion=(0, 0, size[0], size[1]))
        self.draw_preview()

    def spot(self, event):
        return int(self.canvas.canvasx(event.x) // self.zoom), int(self.canvas.canvasy(event.y) // self.zoom)

    def hover(self, event):
        if self.doc is not None:
            x, y = self.spot(event)
            self.position.config(text="x %d, y %d" % (x, y) if self.doc.inside(self.cell, x, y) else "")

    def press(self, event):
        if self.doc is None:
            return
        x, y = self.spot(event)
        if self.tool == "pick":
            self.pick_at(event)
            return
        self.doc.remember()
        self.last = (x, y)
        if self.tool == "fill":
            self.doc.fill(self.cell, x, y, self.colour)
            self.finish()
        else:
            self.doc.put(self.cell, x, y, self.stroke_colour())
            self.draw()

    def stroke_colour(self):
        return (0, 0, 0, 0) if self.tool == "eraser" else self.colour

    def drag(self, event):
        if self.doc is None or self.last is None or self.tool not in ("pencil", "eraser"):
            return
        x, y = self.spot(event)
        if self.doc.line(self.cell, self.last[0], self.last[1], x, y, self.stroke_colour()):
            self.draw()
        self.last = (x, y)

    def release(self, event):
        if self.last is not None and self.doc is not None and self.tool in ("pencil", "eraser"):
            self.finish()
        self.last = None

    def finish(self):
        self.doc.forget_if_same()
        self.after_change()

    def after_change(self):
        self.draw()
        self.update_strip()
        self.show_palette()
        self.update_mark()
        self.shell.content_changed()

    def update_mark(self):
        chosen = self.tree.selection()
        if chosen and chosen[0] in self.path_of:
            self.tree.item(chosen[0], text=" " + chosen[0].partition("/")[2] + (" *" if self.doc.dirty else ""))

    def pick_at(self, event):
        if self.doc is None:
            return
        x, y = self.spot(event)
        if self.doc.inside(self.cell, x, y):
            colour = self.doc.get(self.cell, x, y)
            if colour[3]:
                self.set_colour(colour)

    # ── what a whole cell does ──

    def do_undo(self):
        if self.doc and self.doc.do_undo():
            self.after_change()

    def do_redo(self):
        if self.doc and self.doc.do_redo():
            self.after_change()

    def change_cell(self, action):
        if self.doc is None:
            return
        self.doc.remember()
        action()
        self.doc.forget_if_same()
        self.after_change()

    def flip(self):
        self.change_cell(lambda: self.doc.flip(self.cell))

    def clear_cell(self):
        self.change_cell(lambda: self.doc.clear(self.cell))

    def copy_cell(self):
        if self.doc is not None:
            self.shell_clip = self.doc.cell_image(self.cell)

    def paste_cell(self):
        clip = getattr(self, "shell_clip", None)
        if clip is not None:
            self.change_cell(lambda: self.doc.paste_cell(self.cell, clip))

    def import_picture(self):
        if self.doc is None:
            return
        path = filedialog.askopenfilename(parent=self, title="A picture", filetypes=[("Pictures", "*.png *.gif *.bmp *.jpg *.jpeg *.webp"), ("All files", "*.*")])
        if path:
            self.bring_in(path)

    def bring_in(self, path):
        try:
            self.doc.remember()
            where = self.doc.import_picture(path, self.cell)
        except OSError as e:
            self.doc.undo_steps.pop()
            messagebox.showinfo("That picture cannot be read", str(e), parent=self)
            return
        self.after_change()
        return where

    # ── the preview ──

    def draw_preview(self):
        canvas = self.preview
        canvas.delete("all")
        if self.doc is None:
            return
        if self.doc.count > 1:
            sheet = self.doc.cell_image(self.frame_index % self.doc.count)
            self.preview_text.config(text="Its frames, one after another, as an Animator can play them.")
        else:
            sheet = self.doc.image
            self.preview_text.config(text="The whole picture.")
        self.show_in_preview(sheet)

    def show_in_preview(self, sheet):
        canvas = self.preview
        wide, tall = int(canvas.cget("width")), int(canvas.cget("height"))
        ratio = min(wide / sheet.width, tall / sheet.height)
        ratio = int(ratio) if ratio >= 1 else ratio
        size = (max(1, int(sheet.width * ratio)), max(1, int(sheet.height * ratio)))
        out = checker((wide, tall), 8).convert("RGBA")
        out.alpha_composite(sheet.resize(size, Image.NEAREST), ((wide - size[0]) // 2, (tall - size[1]) // 2))
        self.preview_photo = ImageTk.PhotoImage(out)
        canvas.delete("all")
        canvas.create_image(0, 0, image=self.preview_photo, anchor="nw")

    def animated(self):
        """The preview moves: a picture cut in frames."""
        return self.doc.count > 1

    def animate(self):
        if not self.winfo_exists():
            return
        self.frame_index += 1
        if self.doc is not None and self.winfo_ismapped() and self.animated():
            self.draw_preview()
        self.after(180, self.animate)

    # ── new ones, saving ──

    def new_picture(self):
        """A blank picture in assets/: one cell, or a sheet of frames (16x16 frames, 4 of them: 16x16x4)."""
        name = simpledialog.askstring("New picture", "A name for it, such as hero or coin:", parent=self)
        if not name:
            return
        size = simpledialog.askstring("New picture", "Its size, such as 16x16. A sheet of frames: the size of one, x how many (16x16x4).",
                                      parent=self, initialvalue="16x16")
        if size:
            try:
                self.make_picture(name.strip(), size.strip())
            except ValueError as e:
                messagebox.showinfo("New picture", str(e), parent=self)

    def make_picture(self, name, size):
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            raise ValueError("A name is lowercase letters, numbers and _.")
        m = re.fullmatch(r"(\d+)\s*x\s*(\d+)(?:\s*x\s*(\d+))?", size)
        if not m or not 1 <= int(m.group(1)) <= 1024 or not 1 <= int(m.group(2)) <= 1024 or int(m.group(3) or 1) > 64:
            raise ValueError("A size is like 16x16, or 16x16x4 for 4 frames of 16x16.")
        path = os.path.join(self.project.root, "assets", name + ".png")
        if os.path.exists(path):
            raise ValueError("There is already a picture called %s." % name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        w, h, frames = int(m.group(1)), int(m.group(2)), int(m.group(3) or 1)
        Image.new("RGBA", (w * frames, h), (0, 0, 0, 0)).save(path)
        self.fill_tree()
        self.tree.item("other", open=True)
        self.go_to("other/" + name)
        return path

    def dirty(self):
        return any(d.dirty for d in self.docs.values())

    def save(self):
        changed = False
        for doc in self.docs.values():
            if doc.dirty:
                doc.save()
                changed = True
        if changed:
            self.fill_tree()
        return changed

    def refresh(self):
        """Pictures made elsewhere (a new monster, the build's placeholders) join the list."""
        files = art_files(self.project.root, self.kinds(), self.DEEP)
        known = set(path for _, path in self.path_of.values())
        if set(path for kind in files.values() for _, path in kind) != known:
            self.fill_tree()

    def reload(self):
        self.docs = {}
        self.doc = None
        self.fill_tree()
        for child in self.strip.winfo_children():
            child.destroy()
        self.draw()
