"""The Art, Look and Sound sections of the monster RPG's Studio. Drawing pixels and importing pictures is ApkPy's own
now (apkpy_lib.game.studio.art); this adds the monster RPG's kinds of pictures (monsters, people, tiles), their
previews, New person and New tile, the title's word, the icon, the font and the sounds.
"""
import os
import re
import shutil
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageDraw, ImageTk

from apkpy_lib.game.studio import art as _art
from apkpy_lib.game.studio.art import PixelDoc, checker, to_hex  # noqa: F401
import studio_data
from studio_ui import ACCENT, BAD, GOOD, LINE, MUTED, PANEL, Scrolling, px

KINDS = {
    "monsters": ("Monsters", "assets/monsters", (64, 64), ["Front", "Back"]),
    "people": ("People", "assets/people", (16, 24), None),
    "tiles": ("Tiles", "assets/tiles", (16, 16), None),
}
SKIP_OTHERS = ("monster_blank.png", "pixel.png")
DIRECTIONS = ["down", "left", "up", "right"]
STEPS = ["standing", "a step", "standing", "other step"]


def art_files(root):
    """{kind: [(label, path)]}."""
    return _art.art_files(root, KINDS, deep=False)


class ArtScreen(_art.ArtScreen):
    DEEP = False

    def kinds(self):
        return KINDS

    def new_buttons(self):
        return (("New person...", self.new_person), ("New tile...", self.new_tile))

    def sheet_cell(self, path):
        return None

    def animated(self):
        return getattr(self, "kind", "") == "people"

    def cell_words(self, cell):
        if self.kind == "people":
            return DIRECTIONS[cell // self.doc.columns] if cell % self.doc.columns == 0 and cell // self.doc.columns < 4 else ""
        return self.doc.label(cell)

    # ── the preview ──
    def draw_preview(self):
        canvas = self.preview
        canvas.delete("all")
        if self.doc is None:
            return
        wide, tall = int(canvas.cget("width")), int(canvas.cget("height"))
        if self.kind == "people" and self.doc.columns >= 4 and self.doc.rows >= 4:
            return self.draw_walking()
        if self.kind == "tiles":
            picture = self.doc.cell_image(0)
            sheet = Image.new("RGBA", (picture.width * 3, picture.height * 3))
            for y in range(3):
                for x in range(3):
                    sheet.paste(picture, (x * picture.width, y * picture.height))
            self.preview_text.config(text="As it looks repeated on a map.")
        elif self.kind == "monsters":
            sheet = Image.new("RGBA", (self.doc.cell_size[0] * 2 + 4, self.doc.cell_size[1]))
            sheet.paste(self.doc.cell_image(0), (0, 0))
            if self.doc.count > 1:
                sheet.paste(self.doc.cell_image(1), (self.doc.cell_size[0] + 4, 0))
            self.preview_text.config(text="Front and back, at the size of a battle.")
        else:
            sheet = self.doc.image
            self.preview_text.config(text="The whole picture.")
        self.show_in_preview(sheet)

    def draw_walking(self):
        """Walking in all four directions, as in the game."""
        doc = self.doc
        step = self.frame_index % doc.columns
        w, h = doc.cell_size
        sheet = Image.new("RGBA", (w * 2 + 4, h * 2 + 4))
        for row in range(4):
            sheet.paste(doc.cell_image(row * doc.columns + step), ((row % 2) * (w + 4), (row // 2) * (h + 4)))
        self.preview_text.config(text="Walking: down, left, up, right.")
        self.show_in_preview(sheet)

    # ── new ones, saving ──
    def new_person(self):
        name = simpledialog.askstring("New person", "A name for this look, such as sam:", parent=self)
        if name:
            self.make_person(name.strip())

    def make_person(self, name):
        import new
        try:
            new.person(name)
        except SystemExit as e:
            messagebox.showinfo("New person", str(e), parent=self)
            return
        self.fill_tree()
        self.go_to("people/" + name)
        self.tree.item("people", open=True)

    def new_tile(self):
        name = simpledialog.askstring("New tile", "A name for this tile, such as snow:", parent=self)
        if name:
            self.make_tile(name.strip())

    def make_tile(self, name):
        """A blank tile, and a letter for it in the legend."""
        import map_editor
        import map_tool
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            messagebox.showinfo("New tile", "A name is lowercase letters, numbers and _.", parent=self)
            return
        path = os.path.join(map_tool.TILES, name + ".png")
        if os.path.exists(path):
            messagebox.showinfo("New tile", "There is already a tile called %s." % name, parent=self)
            return
        base = self.doc.cell_image(self.cell) if self.doc is not None and self.kind == "tiles" else Image.new("RGBA", (16, 16), (120, 170, 120, 255))
        base.save(path)
        legend = map_tool.read_legend(map_tool.tile_names())
        letter = map_editor.free_letter(legend)
        with open(os.path.join(map_tool.SOURCE, "legend.txt"), "a", encoding="utf-8") as fh:
            fh.write("%s = %s\n" % (letter, name))
        editor = getattr(self.shell, "editor", None)
        if editor is not None:
            entry = map_tool.read_legend(map_tool.tile_names())[letter]
            for tab in editor.tabs:
                tab.doc.names = map_tool.tile_names()
                tab.doc.base_legend[letter] = entry
                tab.doc.legend[letter] = entry
            editor.build_palette()
        self.fill_tree()
        self.tree.item("tiles", open=True)
        self.go_to("tiles/" + name)


class LookScreen(Scrolling):
    """The title's word, the icon, the font."""

    def __init__(self, parent, shell):
        Scrolling.__init__(self, parent)
        self.shell, self.project = shell, shell.project
        self.body = tk.Frame(self.inner, padx=px(self, 14), pady=px(self, 10))
        self.body.pack(fill="x", expand=True)
        self.build()

    def heading(self, text, hint=""):
        tk.Label(self.body, text=text, font=("", 12, "bold")).pack(anchor="w", pady=(px(self, 10), 0))
        if hint:
            tk.Label(self.body, text=hint, fg=MUTED, justify="left", wraplength=px(self, 700)).pack(anchor="w")

    def picture_label(self, parent, path, limit):
        label = tk.Label(parent, bg="#102448")
        label.pack(anchor="w", pady=px(self, 4))
        return label

    def build(self):
        self.heading("The title", "The word on the title screen. It is a picture, drawn with the game's pixel font.")
        row = tk.Frame(self.body)
        row.pack(anchor="w", pady=px(self, 4))
        self.word = tk.Entry(row, width=24)
        self.word.pack(side="left", ipady=px(self, 2))
        self.word.insert(0, self.project.app.values.get("name", "").upper())
        tk.Button(row, text="Draw it", command=self.draw_word).pack(side="left", padx=px(self, 6))
        tk.Button(row, text="Import a picture...", command=self.import_logo).pack(side="left")
        self.logo_label = tk.Label(self.body, bg="#2d4f7c")
        self.logo_label.pack(anchor="w", pady=px(self, 4))
        self.show_logo()

        self.heading("The icon", "What the phone shows. A square picture, best at 512 x 512.")
        row = tk.Frame(self.body)
        row.pack(anchor="w", pady=px(self, 4))
        tk.Button(row, text="Import a picture...", command=self.import_icon).pack(side="left")
        tk.Label(row, text="or from a monster:").pack(side="left", padx=(px(self, 10), px(self, 4)))
        self.icon_monster = ttk.Combobox(row, values=self.project.table("Species").ids(), state="readonly", width=16)
        self.icon_monster.pack(side="left")
        self.icon_monster.bind("<<ComboboxSelected>>", lambda e: self.icon_from_monster())
        tk.Button(row, text="Use the default icon", command=self.clear_icon).pack(side="left", padx=px(self, 8))
        self.icon_label = tk.Label(self.body)
        self.icon_label.pack(anchor="w", pady=px(self, 4))
        self.show_icon()

        self.heading("The font", "The letters of the whole game. The screens were made for the pixel font, so check them after changing it.")
        row = tk.Frame(self.body)
        row.pack(anchor="w", pady=px(self, 4))
        tk.Button(row, text="Use a font file...", command=self.pick_font).pack(side="left")
        tk.Button(row, text="Back to the pixel font", command=self.pixel_font).pack(side="left", padx=px(self, 6))
        sizes = tk.Frame(self.body)
        sizes.pack(anchor="w")
        tk.Label(sizes, text="Text size").pack(side="left")
        self.size_box = tk.Spinbox(sizes, from_=6, to=32, width=4, command=self.sizes_changed)
        self.size_box.pack(side="left", padx=px(self, 4))
        tk.Label(sizes, text="Big text size").pack(side="left", padx=(px(self, 8), 0))
        self.big_box = tk.Spinbox(sizes, from_=8, to=64, width=4, command=self.sizes_changed)
        self.big_box.pack(side="left", padx=px(self, 4))
        for box, value in ((self.size_box, self.project.look.size), (self.big_box, self.project.look.big)):
            box.delete(0, "end")
            box.insert(0, str(value))
            box.bind("<KeyRelease>", lambda e: self.sizes_changed())
        self.font_name = tk.Label(self.body, text="", fg=MUTED)
        self.font_name.pack(anchor="w")
        self.font_sample = tk.Label(self.body, bg=PANEL)
        self.font_sample.pack(anchor="w", pady=px(self, 4))
        self.show_font()

    def show_logo(self):
        path = self.project.logo_path()
        if os.path.isfile(path):
            with Image.open(path) as img:
                self.logo_photo = ImageTk.PhotoImage(img.convert("RGBA"))
            self.logo_label.configure(image=self.logo_photo)

    def draw_word(self):
        word = self.word.get().strip()
        if word:
            studio_data.make_backup("before title", self.project.root)
            self.project.draw_logo(word)
            self.show_logo()
            self.shell.art_changed()

    def import_logo(self):
        path = filedialog.askopenfilename(parent=self, title="The title", filetypes=[("Pictures", "*.png *.gif *.bmp *.webp"), ("All files", "*.*")])
        if path:
            studio_data.make_backup("before title", self.project.root)
            with Image.open(path) as img:
                img.convert("RGBA").save(self.project.logo_path())
            self.show_logo()
            self.shell.art_changed()

    def show_icon(self):
        path = self.project.icon_path()
        size = px(self, 96)
        if path and os.path.isfile(path):
            with Image.open(path) as img:
                self.icon_photo = ImageTk.PhotoImage(img.convert("RGBA").resize((size, size), Image.NEAREST))
            self.icon_label.configure(image=self.icon_photo, text="")
        else:
            self.icon_photo = None
            self.icon_label.configure(image="", text="The default icon.", fg=MUTED)

    def import_icon(self):
        path = filedialog.askopenfilename(parent=self, title="The icon", filetypes=[("Pictures", "*.png *.gif *.bmp *.webp"), ("All files", "*.*")])
        if path:
            try:
                self.project.set_icon(path)
            except ValueError as e:
                messagebox.showinfo("That picture does not fit", str(e), parent=self)
                return
            self.show_icon()
            self.shell.content_changed()

    def icon_from_monster(self):
        self.project.icon_from_monster(self.icon_monster.get())
        self.show_icon()
        self.shell.content_changed()

    def clear_icon(self):
        self.project.app.values["icon"] = ""
        self.show_icon()
        self.shell.content_changed()

    def pick_font(self):
        path = filedialog.askopenfilename(parent=self, title="A font", filetypes=[("Fonts", "*.ttf *.otf"), ("All files", "*.*")])
        if path:
            self.use_font(path)

    def use_font(self, path):
        studio_data.make_backup("before font", self.project.root)
        try:
            self.project.look.use_font(path)
        except ValueError as e:
            messagebox.showinfo("That font cannot be used", str(e), parent=self)
            return
        self.show_font()
        self.shell.content_changed()

    def pixel_font(self):
        self.project.look.use_pixel_font()
        self.show_font()
        self.shell.content_changed()

    def sizes_changed(self):
        look = self.project.look
        if self.size_box.get().isdigit() and self.big_box.get().isdigit():
            look.size, look.big = int(self.size_box.get()), int(self.big_box.get())
            self.show_font()
            self.shell.content_changed()

    def show_font(self):
        look = self.project.look
        self.font_name.config(text=look.font.replace("assets/", ""))
        for box, value in ((self.size_box, look.size), (self.big_box, look.big)):
            if box.get() != str(value):
                box.delete(0, "end")
                box.insert(0, str(value))
        sample = look.sample("A coal that learned to walk. 0123456789!")
        self.font_photo = ImageTk.PhotoImage(sample)
        self.font_sample.configure(image=self.font_photo)

    def reload(self):
        self.show_logo()
        self.show_icon()
        self.show_font()


class SoundScreen(Scrolling):
    """Music for each map, its background, and every sound: listen, and replace."""

    def __init__(self, parent, shell):
        Scrolling.__init__(self, parent)
        self.shell, self.project = shell, shell.project
        self.body = tk.Frame(self.inner, padx=px(self, 14), pady=px(self, 10))
        self.body.pack(fill="x", expand=True)
        self.draw_all()

    def draw_all(self):
        for child in self.body.winfo_children():
            child.destroy()
        main = self.project.main
        tk.Label(self.body, text="Each place", font=("", 12, "bold")).pack(anchor="w")
        grid = tk.Frame(self.body)
        grid.pack(anchor="w", pady=(px(self, 4), px(self, 12)))
        for c, text in enumerate(("", "Music", "Volume", "Background")):
            tk.Label(grid, text=text, fg=MUTED).grid(row=0, column=c, sticky="w", padx=(0, px(self, 8)))
        tracks = ["(none)"] + [t[0] for t in main.tracks()]
        for r, scene in enumerate(main.scenes(), 1):
            tk.Label(grid, text=scene).grid(row=r, column=0, sticky="w", padx=(0, px(self, 12)))
            box = ttk.Combobox(grid, values=tracks, state="readonly", width=18)
            box.set(main.get(scene, "music") or "(none)")
            box.grid(row=r, column=1, padx=(0, px(self, 8)), pady=1)
            box.bind("<<ComboboxSelected>>", lambda e, s=scene, b=box: self.set_music(s, b.get()))
            volume = tk.Spinbox(grid, from_=0, to=1, increment=0.1, width=5)
            volume.delete(0, "end")
            volume.insert(0, main.get(scene, "music_volume") or "1.0")
            volume.configure(command=lambda s=scene, v=volume: self.set_volume(s, v))
            volume.bind("<KeyRelease>", lambda e, s=scene, v=volume: self.set_volume(s, v))
            volume.grid(row=r, column=2, padx=(0, px(self, 8)))
            colour = (main.get(scene, "background") or "#7cb4d8").strip('"')
            swatch = tk.Button(grid, text=colour, bg=colour, fg="#ffffff", width=9)
            swatch.configure(command=lambda s=scene, b=swatch: self.pick_background(s, b))
            swatch.grid(row=r, column=3)

        tk.Label(self.body, text="Music", font=("", 12, "bold")).pack(anchor="w")
        grid = tk.Frame(self.body)
        grid.pack(anchor="w", pady=(px(self, 4), px(self, 4)))
        for r, (name, path) in enumerate(main.tracks()):
            self.sound_row(grid, r, name, path, lambda p, n=name: self.replace_track(n, p))
        tk.Button(self.body, text="Add a piece of music...", command=self.add_track).pack(anchor="w", pady=(0, px(self, 12)))

        tk.Label(self.body, text="Sounds", font=("", 12, "bold")).pack(anchor="w")
        grid = tk.Frame(self.body)
        grid.pack(anchor="w", pady=px(self, 4))
        for r, (name, path) in enumerate(self.project.look.sounds()):
            self.sound_row(grid, r, name, path, lambda p, n=name: self.replace_sound(n, p))
        self.note = tk.Label(self.body, text="WAV, OGG and MP3 all work in the game. Here, only WAV plays with a click: the others open in your computer's player.", fg=MUTED, wraplength=px(self, 700), justify="left")
        self.note.pack(anchor="w", pady=(px(self, 6), 0))

    def sound_row(self, grid, r, name, path, replace):
        tk.Label(grid, text=name.replace("_music", "").replace("_sound", "")).grid(row=r, column=0, sticky="w", padx=(0, px(self, 12)))
        tk.Label(grid, text=os.path.basename(path), fg=MUTED).grid(row=r, column=1, sticky="w", padx=(0, px(self, 12)))
        tk.Button(grid, text="Play", command=lambda: self.play(path)).grid(row=r, column=2, padx=1, pady=1)
        tk.Button(grid, text="Stop", command=self.stop).grid(row=r, column=3, padx=1)
        tk.Button(grid, text="Replace...", command=lambda: self.pick_sound(replace)).grid(row=r, column=4, padx=1)

    def play(self, path):
        full = os.path.join(self.project.root, path)
        try:
            import winsound
            if full.lower().endswith(".wav"):
                winsound.PlaySound(full, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            os.startfile(full)
        except (ImportError, OSError, RuntimeError, AttributeError) as e:
            self.note.config(text="It cannot be played here: %s" % e)

    def stop(self):
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except (ImportError, RuntimeError):
            pass

    def pick_sound(self, replace):
        path = filedialog.askopenfilename(parent=self, title="A sound", filetypes=[("Sounds", "*.wav *.ogg *.mp3"), ("All files", "*.*")])
        if path:
            replace(path)

    def replace_track(self, name, path):
        self.safely(lambda: self.project.main.replace_track(name, path))

    def replace_sound(self, name, path):
        self.safely(lambda: self.project.look.replace_sound(name, path))

    def safely(self, action):
        self.stop()
        studio_data.make_backup("before sound", self.project.root)
        try:
            action()
        except (ValueError, OSError) as e:
            messagebox.showinfo("That sound cannot be used", str(e), parent=self)
            return
        self.draw_all()
        self.shell.content_changed()

    def add_track(self):
        path = filedialog.askopenfilename(parent=self, title="A piece of music", filetypes=[("Sounds", "*.wav *.ogg *.mp3"), ("All files", "*.*")])
        if path:
            self.safely(lambda: self.project.main.add_track(path))

    def set_music(self, scene, value):
        self.project.main.set(scene, "music", None if value == "(none)" else value)
        self.shell.content_changed()

    def set_volume(self, scene, box):
        try:
            value = float(box.get())
        except ValueError:
            return
        if 0 <= value <= 1:
            self.project.main.set(scene, "music_volume", box.get())
            self.shell.content_changed()

    def pick_background(self, scene, button):
        _, chosen = colorchooser.askcolor(color=button.cget("bg"), parent=self, title="The background of %s" % scene)
        if chosen:
            self.project.main.set(scene, "background", '"%s"' % chosen)
            button.configure(bg=chosen, text=chosen)
            self.shell.content_changed()

    def reload(self):
        self.draw_all()
