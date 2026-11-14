"""The Studio's window: the sections on the left, the chosen one on the right, and at the bottom what the game's build
says about the saved files.

This one opens any game. A kit (tools/studio_kit.py in the project, such as the monster-rpg template's) subclasses
Shell to add its own sections. It only reads and writes the project's own files, so they can also be changed by hand,
and built with plain ApkPy: nothing in the game depends on the Studio.

By Ruben Rego (the monster-rpg template's Studio), opened to every game.
"""
import os
import re
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from . import data as studio_data
from .art import ArtScreen
from .code import GAME_FIELDS, GameCode
from .fields import CallForm, line
from .forms import SimpleScreen
from .levels import LevelsScreen
from .objects import ObjectsScreen
from .play import GameScreen
from .publish import HelpScreen, PublishScreen
from .scenes import ScenesScreen, VariablesEditor
from .sound import SoundsScreen
from .source import literal
from .ui import ACCENT, BAD, GOOD, LINE, MUTED, SIDE, SIDE_TEXT, Scrolling, px


class CopiesScreen(tk.Frame):
    """The automatic copies of the project, to go back to."""

    def __init__(self, parent, shell):
        tk.Frame.__init__(self, parent, padx=px(parent, 14), pady=px(parent, 12))
        self.shell = shell
        tk.Label(self, text="Copies of your project", font=("", 15, "bold")).pack(anchor="w")
        tk.Label(self, fg=MUTED, justify="left", anchor="w", wraplength=px(self, 620),
                 text="A copy is made when the Studio opens, before the first save, and before anything big such as renaming or restoring. The last %d are kept, in the folder %s. %s" % (studio_data.KEEP_BACKUPS, studio_data.BACKUPS, shell.copies_hold())).pack(anchor="w", pady=(px(self, 2), px(self, 8)))
        self.items = tk.Listbox(self, activestyle="none", exportselection=False, height=14, width=52)
        self.items.pack(anchor="w")
        buttons = tk.Frame(self)
        buttons.pack(anchor="w", pady=px(self, 6))
        tk.Button(buttons, text="Make a copy now", command=self.make).pack(side="left", padx=(0, px(self, 6)))
        tk.Button(buttons, text="Go back to this copy...", command=self.restore).pack(side="left")
        self.note = tk.Label(self, text="", fg=MUTED)
        self.note.pack(anchor="w")
        self.reload()

    def reload(self):
        self.names = studio_data.list_backups(self.shell.project.root)
        self.items.delete(0, "end")
        for name in self.names:
            self.items.insert("end", studio_data.backup_label(name))

    def make(self):
        self.shell.save_all()
        made = self.shell.backup("by hand")
        self.note.config(text="Made." if made else "Nothing changed since the last copy.")
        self.reload()

    def restore(self):
        chosen = self.items.curselection()
        if not chosen:
            self.note.config(text="Pick a copy first.")
            return
        name = self.names[chosen[0]]
        if messagebox.askyesno("Go back", "Go back to the copy of %s?\n\nYour project as it is now is copied first, so you can come back." % studio_data.backup_label(name), parent=self):
            self.shell.restore(name)


class AppScreen(Scrolling):
    """My game: its name on the phone, its id, its version, and its icon (apkpy.toml); then Game(...) of
    game/main.py: its size, orientation, scaling, background and variables."""

    FIELDS = (("name", "Name", "What the phone shows under the icon."),
              ("application_id", "App id", "Unique to your game, such as com.yourname.mygame. Two apps with the same id replace each other on a phone. Changing it makes it a new app, with a new signing key."),
              ("version_name", "Version", "What people read, such as 1.2.0."),
              ("version_code", "Version number", "A whole number that goes up with each version you publish."))

    def __init__(self, parent, shell):
        Scrolling.__init__(self, parent)
        self.shell, self.project = shell, shell.project
        self.code = shell.code
        self.show_row()

    def show_row(self):
        for child in self.inner.winfo_children():
            child.destroy()
        body = tk.Frame(self.inner, padx=px(self, 14), pady=px(self, 8))
        body.pack(fill="x", expand=True)
        tk.Label(body, text="My game", font=("", 15, "bold")).pack(anchor="w")
        app = self.project.app
        names = tk.Frame(body)
        names.pack(fill="x", pady=(px(self, 6), px(self, 10)))
        names.columnconfigure(1, weight=1)
        at = 0
        for key, label, hint in self.FIELDS:
            tk.Label(names, text=label, anchor="w").grid(row=at, column=0, sticky="w", padx=(0, px(self, 12)))
            entry = tk.Entry(names)
            entry.insert(0, app.values.get(key, ""))
            entry.grid(row=at, column=1, sticky="ew", ipady=px(self, 2), pady=(px(self, 3), 0))
            entry.bind("<KeyRelease>", lambda e, k=key, w=entry: self.app_changed(k, w))
            tk.Label(names, text=hint, fg=MUTED, anchor="w", justify="left", wraplength=px(self, 620)).grid(row=at + 1, column=1, sticky="w")
            at += 2
        tk.Label(body, text="Icon", font=("", 10, "bold")).pack(anchor="w", pady=(px(self, 6), 0))
        row = tk.Frame(body)
        row.pack(anchor="w", pady=px(self, 4))
        self.icon_label = tk.Label(row, bg="#e9ebef")
        self.icon_label.pack(side="left")
        side = tk.Frame(row, padx=px(self, 10))
        side.pack(side="left", anchor="n")
        tk.Button(side, text="Choose a picture...", command=self.choose_icon).pack(anchor="w")
        self.icon_note = tk.Label(side, text="A square picture, such as 512 x 512. It becomes icon.png.", fg=MUTED, justify="left", wraplength=px(self, 360))
        self.icon_note.pack(anchor="w", pady=px(self, 4))
        self.show_icon()
        self.game_settings(body)

    def game_settings(self, body):
        """Game(...) of game/main.py, when the Studio edits the code."""
        main = self.code.main if self.code is not None else None
        piece = main.first("game") if main is not None else None
        if piece is None:
            return
        line(body)
        tk.Label(body, text="The game", font=("", 12, "bold")).pack(anchor="w")
        tk.Label(body, text="Game(...) in game/main.py, line %d." % main.lines.line_number(piece.start), fg=MUTED).pack(anchor="w", pady=(0, px(self, 4)))
        fields = {k: v for k, v in GAME_FIELDS.items() if k != "name"}
        CallForm(body, self, main, piece.call.path, fields, ["name"], section="game").pack(anchor="w", fill="x")
        line(body)
        tk.Label(body, text="Variables", font=("", 12, "bold")).pack(anchor="w")
        tk.Label(body, text="Numbers the whole game keeps, such as score or lives. A text shows one as {score}; var_add(\"score\") adds to it; a rule tests it.",
                 fg=MUTED, justify="left", wraplength=px(self, 620)).pack(anchor="w", pady=(0, px(self, 4)))
        VariablesEditor(body, self, main, piece.call.path).pack(anchor="w", fill="x")

    # what the fields call

    def touched(self, section):
        self.code.touch("game")
        self.shell.content_changed()

    def redraw(self):
        self.after_idle(self.show_row)

    def show_icon(self):
        path = self.project.icon_path()
        size = (px(self, 96), px(self, 96))
        if path and os.path.isfile(path):
            with Image.open(path) as img:
                shown = img.convert("RGBA").resize(size, Image.LANCZOS)
        else:
            shown = Image.new("RGBA", size, (222, 225, 231, 255))       # no icon of its own yet: ApkPy's is used
        self.icon_photo = ImageTk.PhotoImage(shown)
        self.icon_label.configure(image=self.icon_photo)

    def choose_icon(self):
        path = filedialog.askopenfilename(parent=self, title="The icon", filetypes=[("Pictures", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.project.set_icon(path)
        except (ValueError, OSError) as e:
            self.icon_note.config(text=str(e), fg=BAD)
            return
        self.icon_note.config(text="Your icon. Save to keep it.", fg=MUTED)
        self.show_icon()
        self.shell.content_changed()

    def app_changed(self, key, widget):
        self.project.app.values[key] = widget.get().strip()
        main = self.code.main if self.code is not None else None
        piece = main.first("game") if main is not None and key == "name" else None
        if piece is not None:
            name = piece.call.get(0)
            if name is not None and name.kind == "literal":
                main.set(name, literal(self.project.app.values["name"]), merge=("game", "name"))
                self.code.touch("game")
        self.shell.name_changed()
        self.shell.content_changed()

    def do_undo(self):
        if self.code is not None and self.code.undo():
            self.shell.content_changed()
            self.show_row()

    def do_redo(self):
        if self.code is not None and self.code.redo():
            self.shell.content_changed()
            self.show_row()

    def reload(self):
        self.show_row()

    def refresh(self):
        pass


class Shell:
    """The window, for any game. A kit subclasses it: its sections, its screens, what it checks and saves."""

    SECTIONS = (("play", "Play"), ("game", "My game"), ("objects", "Objects"), ("scenes", "Scenes"), ("levels", "Levels"), ("art", "Art"),
                ("sounds", "Sounds"), ("publish", "Publish"), ("backups", "Copies"), ("help", "Help"))
    FIRST = "play"
    CODE_SECTIONS = ("objects", "scenes", "levels", "sounds")
    WATCH_MS = 2000

    def __init__(self, root, folder):
        self.root = root
        self.folder = os.path.abspath(folder)
        self.project = self.make_project()
        self.code = GameCode(self.folder) if any(k in self.CODE_SECTIONS for k, _ in self.SECTIONS) else None
        if self.code is not None:
            self.project.app.rename_game = False         # the name in Game(...) is written with the code
        self.screens = {}
        self.current = None
        self.checker = None
        self.check_again = False
        self.problems = []
        self.real_problems = []
        self.list_open = False
        self.saved_once = False
        root.title("Studio: %s" % self.game_name())
        root.geometry("%dx%d" % (px(root, 1240), px(root, 760)))
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self.backup("opened")
        self.build()
        self.bind_keys()
        self.show(self.FIRST)
        self.run_check()
        if self.code is not None:
            self.root.after(self.WATCH_MS, self.watch_files)

    # ── what a kit changes ──

    def make_project(self):
        return studio_data.DataProject(self.folder)

    def backup(self, reason):
        return studio_data.make_backup(reason, self.folder)

    def restore_files(self, name):
        studio_data.restore_backup(name, self.folder)

    def copies_hold(self):
        return "They hold your game's code, data, levels, pictures, short sounds, apkpy.toml and icon."

    def sections(self):
        """[(key, name)], in the order of the list on the left: the data tables come after Levels (or My game)."""
        out = []
        keys = [k for k, _ in self.SECTIONS]
        after = next((k for k in ("levels", "scenes", "game") if k in keys), "game")
        for key, label in self.SECTIONS:
            out.append((key, label))
            if key == after:
                for cls in self.project.paths:
                    if cls in self.project.tables:
                        out.append(("table:" + cls, self.project.label(cls)))
        return out

    def make_screen(self, key):
        if key == "play":
            return GameScreen(self.area, self)
        if key == "game":
            return AppScreen(self.area, self)
        if key == "objects":
            return ObjectsScreen(self.area, self)
        if key == "scenes":
            return ScenesScreen(self.area, self)
        if key == "levels":
            return LevelsScreen(self.area, self)
        if key == "sounds":
            return SoundsScreen(self.area, self)
        if key.startswith("table:"):
            return type("TableOf" + key[6:], (SimpleScreen,), {"cls": key[6:], "noun": self.project.label(key[6:]).lower()})(self.area, self)
        if key == "art":
            return ArtScreen(self.area, self)
        if key == "publish":
            return PublishScreen(self.area, self)
        if key == "help":
            return HelpScreen(self.area, self)
        return CopiesScreen(self.area, self)

    def refreshes(self, key):
        """Shown again: it reads again what other sections may have changed."""
        return key.startswith("table:") or key in ("publish", "art", "objects", "scenes", "levels", "sounds")

    def check_command(self):
        return [sys.executable, "-m", "apkpy_lib.game.studio.check"]

    def has_map_problem(self):
        """Play waits for this to be fixed."""
        return False

    # ── the window ──

    def game_name(self):
        try:
            with open(os.path.join(self.folder, "apkpy.toml"), encoding="utf-8") as fh:
                m = re.search(r'^name\s*=\s*"(.*)"', fh.read(), re.M)
        except OSError:
            m = None
        return m.group(1) if m else os.path.basename(self.folder)

    def name_changed(self):
        name = self.project.app.values.get("name", "")
        self.root.title("Studio: %s" % name)
        self.name_label.config(text=name)

    def build(self):
        side = tk.Frame(self.root, bg=SIDE, width=px(self.root, 148))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        self.name_label = tk.Label(side, text=self.game_name(), bg=SIDE, fg="#ffffff", font=("", 12, "bold"), anchor="w", wraplength=px(self.root, 130), justify="left")
        self.name_label.pack(fill="x", padx=px(self.root, 12), pady=(px(self.root, 12), px(self.root, 10)))
        self.nav = {}
        for key, label in self.sections():
            item = tk.Label(side, text=label, bg=SIDE, fg=SIDE_TEXT, anchor="w", padx=px(self.root, 12), pady=px(self.root, 3), cursor="hand2", font=("", 10))
            item.pack(fill="x")
            item.bind("<Button-1>", lambda e, k=key: self.show(k))
            self.nav[key] = item
        another = tk.Label(side, text="New game...", bg=SIDE, fg=SIDE_TEXT, anchor="w", padx=px(self.root, 12), cursor="hand2", font=("", 9, "underline"))
        another.pack(side="bottom", fill="x", pady=(0, px(self.root, 8)))
        another.bind("<Button-1>", lambda e: self.new_game())
        for text, command in (("Play the game", self.play), ("Save all", self.save_all)):
            tk.Button(side, text=text, command=command).pack(side="bottom", fill="x", padx=px(self.root, 10), pady=(0, px(self.root, 8)))

        bottom = tk.Frame(self.root)
        bottom.pack(side="bottom", fill="x")
        tk.Frame(bottom, bg=LINE, height=1).pack(fill="x")
        self.summary = tk.Label(bottom, text="Checking...", anchor="w", cursor="hand2", padx=px(self.root, 10), pady=px(self.root, 4))
        self.summary.pack(fill="x")
        self.summary.bind("<Button-1>", lambda e: self.toggle_problems())
        self.problem_box = tk.Listbox(bottom, height=5, activestyle="none", exportselection=False)
        self.problem_box.bind("<<ListboxSelect>>", lambda e: self.open_problem())

        self.area = tk.Frame(self.root)
        self.area.pack(side="left", fill="both", expand=True)

    def new_game(self):
        """Another game, made beside this one: it opens in a Studio of its own, and this one stays."""
        from . import start_another
        from .newgame import NewGame
        box = tk.Toplevel(self.root)
        box.title("Studio: a new game")
        box.geometry("%dx%d" % (px(self.root, 960), px(self.root, 640)))
        box.transient(self.root)

        def made(folder):
            box.destroy()
            self.started = start_another(folder)

        NewGame(box, os.path.dirname(self.folder), made, cancel=box.destroy).pack(fill="both", expand=True)
        return box

    def bind_keys(self):
        r = self.root
        r.bind("<Control-s>", lambda e: self.save_all())
        r.bind("<Control-z>", lambda e: self.undo_key("do_undo"), add="+")
        r.bind("<Control-y>", lambda e: self.undo_key("do_redo"), add="+")
        for key, tool in (("p", "pencil"), ("e", "eraser"), ("g", "fill"), ("i", "pick")):
            r.bind("<KeyPress-%s>" % key, lambda e, t=tool: self.art_key(t), add="+")

    def undo_key(self, name):
        screen = self.screens.get(self.current)
        if screen is not None and hasattr(screen, name):
            getattr(screen, name)()

    def art_key(self, tool):
        if self.current == "art" and not isinstance(self.root.focus_get(), (tk.Entry, tk.Text, tk.Spinbox, ttk.Combobox)):
            self.screens["art"].set_tool(tool)

    def screen(self, key):
        if key not in self.screens:
            self.screens[key] = self.make_screen(key)
        return self.screens[key]

    def show(self, key):
        screen = self.screen(key)
        if self.current == key:
            return screen
        if self.current:
            self.screens[self.current].pack_forget()
            if self.current in ("play", "sounds"):
                self.screens[self.current].stop()    # its music stops too
        self.current = key
        screen.pack(fill="both", expand=True)
        for k, item in self.nav.items():
            item.configure(bg=ACCENT if k == key else SIDE, fg="#ffffff" if k == key else SIDE_TEXT)
        if self.refreshes(key):
            screen.refresh()
        self.update_marks()
        return screen

    def go(self, key, target):
        screen = self.show(key)
        if hasattr(screen, "go_to"):
            screen.go_to(target)
        return screen

    def go_use(self, use):
        """Goes to a place that uses a row."""
        if use.section == "code":
            self.summary.config(text="That is in %s: it is code, so change it in a text editor." % use.target, fg=MUTED)
        elif use.section in self.project.tables:
            self.go("table:" + use.section, use.target)

    # ── changes ──

    def content_changed(self):
        self.update_marks()

    def dirty_sections(self):
        out = set()
        for cls, table in self.project.tables.items():
            if table.dirty:
                out.add("table:" + cls)
        if self.project.app.dirty:
            out.add("game")
        art = self.screens.get("art")
        if art is not None and art.dirty():
            out.add("art")
        levels = self.screens.get("levels")
        if levels is not None and levels.dirty():
            out.add("levels")
        if self.code is not None:
            out |= self.code.dirty_sections()
        return out

    def update_marks(self):
        dirty = self.dirty_sections()
        for key, label in self.sections():
            if key in self.nav:
                self.nav[key].configure(text=label + (" *" if key in dirty else ""))

    def save_all(self):
        if self.dirty_sections() and not self.saved_once:
            self.backup("before saving")
            self.saved_once = True
        art = self.screens.get("art")
        art_changed = art is not None and art.save()
        levels = self.screens.get("levels")
        if levels is not None:
            levels.save()
        self.save_code()
        self.project.save()
        self.update_marks()
        self.name_changed()
        if art_changed:
            self.art_changed()
        self.run_check()

    def save_code(self):
        """The game's Python. A file changed by hand since it was read is not written over without asking."""
        if self.code is None:
            return
        self.sync_game_name()
        if not self.code.dirty:
            return
        if self.code.changed_on_disk() and not messagebox.askyesno(
                "Changed outside the Studio", "The game's code was changed outside the Studio since it was read.\n\n"
                "Write the Studio's changes over it? (No: keep the file as it is, and read it again.)", parent=self.root):
            self.code.reload()
            self.reload_code_screens()
            return
        self.code.save()

    def sync_game_name(self):
        """The name on the phone (apkpy.toml) changed: Game("...") says the same."""
        app = self.project.app
        main = self.code.main
        piece = main.first("game") if main is not None else None
        name = piece.call.get(0) if piece is not None else None
        if app.values["name"] != app.saved["name"] and name is not None and name.kind == "literal" \
                and name.value != app.values["name"]:
            main.set(name, literal(app.values["name"]))
            self.code.touch("game")

    def watch_files(self):
        """The code changed on disk (an editor, git): read it again, unless the Studio has changes not saved."""
        try:
            if not self.code.dirty and self.code.changed_on_disk():
                self.code.reload()
                self.reload_code_screens()
                self.run_check()
        finally:
            self.root.after(self.WATCH_MS, self.watch_files)

    def reload_code_screens(self):
        for key in ("game", "objects", "scenes", "levels", "sounds"):
            screen = self.screens.get(key)
            if screen is not None:
                screen.refresh() if key in ("levels", "sounds") else screen.reload()      # a level not saved stays
        self.update_marks()

    def art_changed(self):
        """Pictures changed: whoever shows them, see them again."""

    def rename(self, cls, old, new):
        self.save_all()
        self.backup("before renaming %s" % old)
        try:
            self.project.rename(cls, old, new)
        except ValueError as e:
            messagebox.showinfo("That name cannot be used", str(e), parent=self.root)
            self.project.reload()
        self.reload_everything(new)

    def restore(self, name):
        self.restore_files(name)
        self.reload_everything()

    def reload_everything(self, select=None):
        """The files changed underneath: read them again."""
        self.project.reload()
        if self.code is not None:
            self.code.reload()
        for key, screen in list(self.screens.items()):
            if hasattr(screen, "reload"):
                screen.reload()
            if select and key.startswith("table:") and key == self.current and screen.table().get(select) is not None:
                screen.select(select)
        self.art_changed()
        self.update_marks()
        self.run_check()

    # ── checking ──

    def run_check(self):
        """What the build would say about the saved files, in the background."""
        if self.checker is not None and self.checker.poll() is None:
            self.check_again = True
            return
        self.summary.config(text="Checking...", fg=MUTED)
        env = dict(os.environ, PYTHONIOENCODING="utf-8", APKPY_RELOAD="0")
        self.checker = subprocess.Popen(self.check_command(), cwd=self.folder, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                        encoding="utf-8", errors="replace", env=env)
        self.root.after(150, self.watch_check)

    def watch_check(self):
        if self.checker.poll() is None:
            self.root.after(150, self.watch_check)
            return
        said = self.checker.stdout.read()
        self.check_said(said)
        self.show_problems(self.read_check(said, self.checker.returncode))
        if self.check_again:
            self.check_again = False
            self.run_check()

    def check_said(self, said):
        """A kit reads more in what its check said."""

    @staticmethod
    def read_check(said, code):
        """(problems, notes) from what the check said."""
        problems, notes = [], []
        for line in said.splitlines():
            text = line.strip()
            if not text:
                continue
            if text.startswith("note: "):
                notes.append(text[6:])
            elif code:
                problems.append(text)
        return problems, notes

    def show_problems(self, found):
        problems, notes = found
        self.problems = problems + notes
        self.real_problems = problems
        self.problem_box.delete(0, "end")
        for text in problems:
            self.problem_box.insert("end", text)
        for text in notes:
            self.problem_box.insert("end", "note: " + text)
        if problems:
            self.summary.config(text="%d problem%s in the saved files. Click to see." % (len(problems), "" if len(problems) == 1 else "s"), fg=BAD)
            if not self.list_open:
                self.toggle_problems()
        elif notes:
            self.summary.config(text="No problems. %d note%s: click to see." % (len(notes), "" if len(notes) == 1 else "s"), fg=GOOD)
        else:
            self.summary.config(text="No problems in the saved files.", fg=GOOD)
            if self.list_open:
                self.toggle_problems()

    def toggle_problems(self):
        self.list_open = not self.list_open
        if self.list_open:
            self.problem_box.pack(fill="x", before=None)
        else:
            self.problem_box.pack_forget()

    def open_problem(self):
        """Goes to what a line talks about."""
        chosen = self.problem_box.curselection()
        if not chosen:
            return
        self.go_problem(self.problem_box.get(chosen[0]).replace("note: ", ""))

    def go_problem(self, text):
        m = re.match(r"(?:data/)?(\w+)(?:/\w+)?\.json", text)
        if m:
            for cls, path in self.project.paths.items():
                if path.split("/")[-1] == m.group(1) and cls in self.project.tables:
                    self.show("table:" + cls)
                    return
        m = re.match(r"(assets/[\w/.-]+)\.png", text)
        if m:
            self.go("art", "other/" + m.group(1)[len("assets/"):])
            return
        m = re.match(r"([\w/.-]+\.py)(?::(\d+))?", text)
        if m and m.group(2) and self.go_code(m.group(1), int(m.group(2))):
            return
        if m:
            self.summary.config(text="That is in %s%s: it is code, so change it in a text editor." % (m.group(1), ", line " + m.group(2) if m.group(2) else ""), fg=MUTED)

    def go_code(self, rel, number):
        """A problem in the game's code: the object, scene or setting on that line, when the Studio shows it."""
        source = self.code.sources.get(rel) if self.code is not None else None
        if source is None:
            return False
        for piece in source.pieces:
            first, last = source.lines.line_number(piece.start), source.lines.line_number(piece.end)
            if not first <= number <= last:
                continue
            if piece.kind == "prefab":
                self.go("objects", piece.name)
            elif piece.kind in ("scene", "add") and rel == "game/main.py":
                self.go("scenes", piece.name)
            elif piece.kind == "game":
                self.show("game")
            else:
                return False
            return True
        return False

    # ── playing, closing ──

    def play(self):
        self.show("play").play_from_start()

    def problems_only(self):
        return self.real_problems

    def quit(self):
        if self.dirty_sections():
            answer = messagebox.askyesnocancel("Save changes?", "Save your changes before closing?", parent=self.root)
            if answer is None:
                return
            if answer:
                self.save_all()
                if self.checker is not None:
                    self.checker.wait()
        self.close_screens()
        self.root.destroy()

    def close_screens(self):
        for key in ("play", "publish", "sounds"):
            screen = self.screens.get(key)
            if screen is not None:
                screen.stop()
