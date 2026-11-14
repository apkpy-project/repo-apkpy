"""The Game and Test sections of the Studio: play inside the window, start with any team, try fights, see the balance, the world, and what you forgot."""
import json
import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

import map_tool
import studio_data
from studio_ui import ACCENT, BAD, GOOD, LINE, MUTED, PANEL, Scrolling, px

SETUP_FILE = os.path.join("build", "studio_test.json")


def ask_lab(root, command, question):
    """A process that answers later: read it with lab_answer."""
    process = subprocess.Popen([sys.executable, os.path.join(root, "tools", "lab.py"), command], cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
    process.stdin.write(json.dumps(question))
    process.stdin.close()
    return process


def lab_answer(process):
    """(answer, "") or (None, what went wrong)."""
    said = process.stdout.read()
    if process.wait():
        lines = process.stderr.read().strip().splitlines()
        return None, lines[-1] if lines else "It stopped without saying why."
    return json.loads(said), ""
from apkpy_lib.game.studio.play import GameScreen as _GameScreen


class GameScreen(_GameScreen):
    """The real game, inside this window, from its title."""

    HINT = "Arrow keys or the on-screen buttons walk. Space is the A button, Esc is the phone's Back."
    PLAYING = "Playing. Click the game first if the keys do nothing. Space is the A button, Esc is the phone's Back."

    def build_buttons(self, top):
        tk.Button(top, text="Play from the title", command=self.play_from_title).pack(side="left", padx=1)
        tk.Button(top, text="Stop", command=self.stop).pack(side="left", padx=1)

    def play_from_title(self):
        self.start("title")

    def play_from_start(self):
        self.start("title")

    def reload(self):
        pass


class TeamRows(tk.Frame):
    """Monsters and levels."""

    def __init__(self, parent, project, rows, changed=None):
        tk.Frame.__init__(self, parent)
        self.project, self.rows, self.on_change = project, rows, changed
        self.draw()

    def draw(self):
        for child in self.winfo_children():
            child.destroy()
        kinds = self.project.table("Species").ids()
        for r, row in enumerate(self.rows):
            box = ttk.Combobox(self, values=kinds, state="readonly", width=14)
            box.set(row[0])
            box.grid(row=r, column=0, pady=1)
            box.bind("<<ComboboxSelected>>", lambda e, it=row, b=box: self.set(it, 0, b.get()))
            level = tk.Spinbox(self, from_=1, to=100, width=4)
            level.delete(0, "end")
            level.insert(0, str(row[1]))
            level.configure(command=lambda it=row, b=level: self.set_level(it, b))
            level.bind("<KeyRelease>", lambda e, it=row, b=level: self.set_level(it, b))
            level.grid(row=r, column=1, padx=px(self, 4))
            tk.Button(self, text="x", width=2, command=lambda at=r: self.remove(at)).grid(row=r, column=2)
        if len(self.rows) < 6:
            tk.Button(self, text="+ Add", command=self.add).grid(row=len(self.rows), column=0, sticky="w", pady=(px(self, 3), 0))

    def set(self, row, at, value):
        row[at] = value
        self.changed()

    def set_level(self, row, box):
        if box.get().isdigit() and int(box.get()) > 0:
            row[1] = int(box.get())
            self.changed()

    def add(self):
        kinds = self.project.table("Species").ids()
        self.rows.append([kinds[0] if kinds else "", 5])
        self.draw()
        self.changed()

    def remove(self, at):
        self.rows.pop(at)
        self.draw()
        self.changed()

    def changed(self):
        if self.on_change:
            self.on_change()


class TestScreen(tk.Frame):
    def __init__(self, parent, shell):
        tk.Frame.__init__(self, parent)
        self.shell, self.project = shell, shell.project
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=px(self, 6), pady=px(self, 6))
        self.start_tab = tk.Frame(self.notebook, padx=px(self, 12), pady=px(self, 10))
        self.fight_tab = tk.Frame(self.notebook, padx=px(self, 12), pady=px(self, 10))
        self.balance_tab = tk.Frame(self.notebook, padx=px(self, 12), pady=px(self, 10))
        self.world_tab = tk.Frame(self.notebook)
        self.forgot_tab = tk.Frame(self.notebook, padx=px(self, 12), pady=px(self, 10))
        for tab, text in ((self.start_tab, "Start a test"), (self.fight_tab, "Try a fight"), (self.balance_tab, "Balance"), (self.world_tab, "World"), (self.forgot_tab, "Forgotten")):
            self.notebook.add(tab, text=text)
        self.setup = self.load_setup()
        self.build_start()
        self.build_fight()
        self.build_balance()
        self.build_world()
        self.build_forgotten()
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.tab_changed())

    def tab_changed(self):
        chosen = self.notebook.select()
        if chosen == str(self.world_tab):
            self.draw_world()
        elif chosen == str(self.forgot_tab):
            self.show_forgotten()

    def reload(self):
        self.refresh_lists()

    def refresh(self):
        self.refresh_lists()
        self.tab_changed()

    def clean_setup(self):
        """A monster, item or map may have been renamed or deleted since it was chosen: what no longer exists goes."""
        kinds = self.project.table("Species").ids()
        info = self.project.table("GameInfo").rows[0]
        first = next((k for k in info.get("starters", []) if k in kinds), kinds[0] if kinds else "")
        for team in (self.setup.setdefault("team", []), self.fight_team):
            for row in team:
                if row[0] not in kinds:
                    row[0] = first
        known = self.project.table("Item").ids()
        for item in [i for i in self.setup.get("items", {}) if i not in known]:
            self.setup["items"].pop(item)
        if self.setup.get("map") not in self.project.map_names():
            self.setup["map"] = info.get("start_map", "")
            self.setup["marker"] = info.get("start_at", "")
        elif self.setup.get("marker") not in self.project.markers_of_map(self.setup["map"]):
            markers = self.project.markers_of_map(self.setup["map"])
            self.setup["marker"] = markers[0] if markers else ""
        self.save_setup()

    def refresh_lists(self):
        self.clean_setup()
        self.map_box.configure(values=self.project.map_names())
        self.map_box.set(self.setup.get("map", ""))
        self.marker_box.configure(values=self.project.markers_of_map(self.setup.get("map", "")))
        self.marker_box.set(self.setup.get("marker", ""))
        self.draw_items()
        self.team_rows.draw()
        self.fight_team_rows.draw()
        self.wild_kind.configure(values=self.project.table("Species").ids())
        self.trainer_box.configure(values=self.project.table("Trainer").ids())
        self.flag_box.configure(values=self.known_flags())
        self.item_box.configure(values=self.project.table("Item").ids())

    # ── start a test ──

    def load_setup(self):
        info = self.project.table("GameInfo").rows[0]
        setup = {"map": info.get("start_map", ""), "marker": info.get("start_at", ""), "team": [[info.get("starters", [""])[0], max(5, info.get("starter_level", 5))]], "items": {}, "flags": [], "money": info.get("money", 500)}
        path = os.path.join(self.project.root, SETUP_FILE)
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    setup.update(json.load(fh))
            except ValueError:
                pass
        return setup

    def save_setup(self):
        path = os.path.join(self.project.root, SETUP_FILE)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self.setup, fh)
        except OSError:
            pass

    def known_flags(self):
        import map_editor
        return map_editor.known_flags()

    def build_start(self):
        tab = self.start_tab
        tk.Label(tab, text="Start the game anywhere, with what you choose", font=("", 12, "bold")).pack(anchor="w")
        tk.Label(tab, text="The same team, items and flags are used when you right click a cell in a map, or test an event.", fg=MUTED).pack(anchor="w", pady=(0, px(self, 8)))
        where = tk.Frame(tab)
        where.pack(anchor="w")
        tk.Label(where, text="Map").grid(row=0, column=0, sticky="w")
        self.map_box = ttk.Combobox(where, values=self.project.map_names(), state="readonly", width=16)
        self.map_box.set(self.setup.get("map", ""))
        self.map_box.grid(row=0, column=1, padx=px(self, 6))
        self.map_box.bind("<<ComboboxSelected>>", lambda e: self.map_chosen())
        tk.Label(where, text="At").grid(row=0, column=2, sticky="w")
        self.marker_box = ttk.Combobox(where, values=self.project.markers_of_map(self.setup.get("map", "")), state="readonly", width=18)
        self.marker_box.set(self.setup.get("marker", ""))
        self.marker_box.grid(row=0, column=3, padx=px(self, 6))
        self.marker_box.bind("<<ComboboxSelected>>", lambda e: self.remember("marker", self.marker_box.get()))
        columns = tk.Frame(tab)
        columns.pack(anchor="w", pady=px(self, 10))
        team = tk.Frame(columns)
        team.grid(row=0, column=0, sticky="nw", padx=(0, px(self, 24)))
        tk.Label(team, text="Team", font=("", 10, "bold")).pack(anchor="w")
        self.team_rows = TeamRows(team, self.project, self.setup["team"], self.save_setup)
        self.team_rows.pack(anchor="w")
        items = tk.Frame(columns)
        items.grid(row=0, column=1, sticky="nw", padx=(0, px(self, 24)))
        tk.Label(items, text="Items", font=("", 10, "bold")).pack(anchor="w")
        self.item_lines = tk.Frame(items)
        self.item_lines.pack(anchor="w")
        row = tk.Frame(items)
        row.pack(anchor="w", pady=(px(self, 3), 0))
        self.item_box = ttk.Combobox(row, values=self.project.table("Item").ids(), state="readonly", width=14)
        self.item_box.set("add...")
        self.item_box.pack(side="left")
        self.item_box.bind("<<ComboboxSelected>>", lambda e: self.add_item())
        self.draw_items()
        flags = tk.Frame(columns)
        flags.grid(row=0, column=2, sticky="nw")
        tk.Label(flags, text="Flags already set", font=("", 10, "bold")).pack(anchor="w")
        self.flag_lines = tk.Frame(flags)
        self.flag_lines.pack(anchor="w")
        self.flag_box = ttk.Combobox(flags, values=self.known_flags(), state="readonly", width=18)
        self.flag_box.set("add...")
        self.flag_box.pack(anchor="w", pady=(px(self, 3), 0))
        self.flag_box.bind("<<ComboboxSelected>>", lambda e: self.add_flag())
        self.draw_flags()
        money = tk.Frame(tab)
        money.pack(anchor="w")
        tk.Label(money, text="Money").pack(side="left")
        self.money_box = tk.Spinbox(money, from_=0, to=999999, width=8, command=self.money_changed)
        self.money_box.delete(0, "end")
        self.money_box.insert(0, str(self.setup.get("money", 0)))
        self.money_box.bind("<KeyRelease>", lambda e: self.money_changed())
        self.money_box.pack(side="left", padx=px(self, 6))
        tk.Button(tab, text="Start here", command=self.start_here).pack(anchor="w", pady=px(self, 12))
        self.start_note = tk.Label(tab, text="", fg=MUTED)
        self.start_note.pack(anchor="w")

    def remember(self, key, value):
        self.setup[key] = value
        self.save_setup()

    def map_chosen(self):
        name = self.map_box.get()
        self.setup["map"] = name
        markers = self.project.markers_of_map(name)
        self.marker_box.configure(values=markers)
        self.marker_box.set(markers[0] if markers else "")
        self.setup["marker"] = self.marker_box.get()
        self.save_setup()

    def money_changed(self):
        if self.money_box.get().isdigit():
            self.remember("money", int(self.money_box.get()))

    def draw_items(self):
        for child in self.item_lines.winfo_children():
            child.destroy()
        items = self.setup.setdefault("items", {})
        for r, (name, count) in enumerate(sorted(items.items())):
            tk.Label(self.item_lines, text=name).grid(row=r, column=0, sticky="w")
            box = tk.Spinbox(self.item_lines, from_=1, to=99, width=4)
            box.delete(0, "end")
            box.insert(0, str(count))
            box.configure(command=lambda n=name, b=box: self.item_count(n, b))
            box.bind("<KeyRelease>", lambda e, n=name, b=box: self.item_count(n, b))
            box.grid(row=r, column=1, padx=px(self, 4))
            tk.Button(self.item_lines, text="x", width=2, command=lambda n=name: self.drop_item(n)).grid(row=r, column=2)

    def add_item(self):
        self.setup.setdefault("items", {}).setdefault(self.item_box.get(), 1)
        self.item_box.set("add...")
        self.draw_items()
        self.save_setup()

    def item_count(self, name, box):
        if box.get().isdigit():
            self.setup["items"][name] = int(box.get())
            self.save_setup()

    def drop_item(self, name):
        self.setup["items"].pop(name, None)
        self.draw_items()
        self.save_setup()

    def draw_flags(self):
        for child in self.flag_lines.winfo_children():
            child.destroy()
        for r, name in enumerate(self.setup.setdefault("flags", [])):
            tk.Label(self.flag_lines, text=name).grid(row=r, column=0, sticky="w")
            tk.Button(self.flag_lines, text="x", width=2, command=lambda n=name: self.drop_flag(n)).grid(row=r, column=1, padx=px(self, 4))

    def add_flag(self):
        flags = self.setup.setdefault("flags", [])
        if self.flag_box.get() and self.flag_box.get() not in flags:
            flags.append(self.flag_box.get())
        self.flag_box.set("add...")
        self.draw_flags()
        self.save_setup()

    def drop_flag(self, name):
        self.setup["flags"].remove(name)
        self.draw_flags()
        self.save_setup()

    def start_here(self):
        name = self.setup.get("map", "")
        spot = self.project.marker_cell(name, self.setup.get("marker", ""))
        if spot is None:
            self.start_note.config(text="Pick a map and a place on it.", fg=BAD)
            return
        self.shell.start_test(name, spot[0], spot[1])

    # ── try a fight ──

    def build_fight(self):
        tab = self.fight_tab
        tk.Label(tab, text="Play a fight many times, always with the strongest move and no items", font=("", 12, "bold")).pack(anchor="w")
        tk.Label(tab, text="It uses your saved files.", fg=MUTED).pack(anchor="w", pady=(0, px(self, 8)))
        columns = tk.Frame(tab)
        columns.pack(anchor="w")
        left = tk.Frame(columns)
        left.grid(row=0, column=0, sticky="nw", padx=(0, px(self, 30)))
        tk.Label(left, text="Your team", font=("", 10, "bold")).pack(anchor="w")
        self.fight_team = [list(self.setup["team"][0])] if self.setup.get("team") else []
        self.fight_team_rows = TeamRows(left, self.project, self.fight_team)
        self.fight_team_rows.pack(anchor="w")
        right = tk.Frame(columns)
        right.grid(row=0, column=1, sticky="nw")
        tk.Label(right, text="Against", font=("", 10, "bold")).pack(anchor="w")
        self.against = tk.StringVar(value="wild")
        row = tk.Frame(right)
        row.pack(anchor="w")
        tk.Radiobutton(row, text="A wild", variable=self.against, value="wild").pack(side="left")
        kinds = self.project.table("Species").ids()
        self.wild_kind = ttk.Combobox(row, values=kinds, state="readonly", width=14)
        self.wild_kind.set(kinds[0] if kinds else "")
        self.wild_kind.pack(side="left", padx=px(self, 4))
        self.wild_level = tk.Spinbox(row, from_=1, to=100, width=4)
        self.wild_level.delete(0, "end")
        self.wild_level.insert(0, "5")
        self.wild_level.pack(side="left")
        row = tk.Frame(right)
        row.pack(anchor="w", pady=(px(self, 3), 0))
        tk.Radiobutton(row, text="A trainer", variable=self.against, value="trainer").pack(side="left")
        trainers = self.project.table("Trainer").ids()
        self.trainer_box = ttk.Combobox(row, values=trainers, state="readonly", width=14)
        self.trainer_box.set(trainers[0] if trainers else "")
        self.trainer_box.pack(side="left", padx=px(self, 4))
        tk.Button(tab, text="Play it 200 times", command=self.run_fight).pack(anchor="w", pady=px(self, 10))
        self.fight_result = tk.Label(tab, text="", font=("", 11, "bold"), anchor="w")
        self.fight_result.pack(anchor="w")
        tk.Label(tab, text="One of them, as it happened", fg=MUTED).pack(anchor="w", pady=(px(self, 6), 0))
        self.fight_log = tk.Text(tab, height=14, wrap="word")
        self.fight_log.pack(fill="both", expand=True)
        self.fight_process = None

    def run_fight(self):
        if self.fight_process is not None or not self.fight_team:
            return
        self.shell.save_all()
        self.refresh_lists()
        question = {"team": self.fight_team, "plays": 200}
        if self.against.get() == "trainer":
            question["trainer"] = self.trainer_box.get()
        else:
            question["wild"] = [self.wild_kind.get(), int(self.wild_level.get() or 5)]
        self.fight_result.config(text="Playing...", fg=MUTED)
        self.fight_process = ask_lab(self.project.root, "fight", question)
        self.after(100, self.watch_fight)

    def watch_fight(self):
        if self.fight_process.poll() is None:
            self.after(100, self.watch_fight)
            return
        answer, problem = lab_answer(self.fight_process)
        self.fight_process = None
        if answer is None:
            self.fight_result.config(text=problem[:140], fg=BAD)
            return
        share = answer["wins"] / max(1, answer["plays"])
        self.fight_result.config(text="Your team wins %d%% of the time, with %d%% of its HP left, in about %s turns." % (share * 100, answer["hp_left"] * 100, answer["turns"]),
                                 fg=GOOD if share >= 0.8 else "#b07010" if share >= 0.4 else BAD)
        self.fight_log.delete("1.0", "end")
        self.fight_log.insert("1.0", "\n".join(answer["sample"]))

    # ── balance ──

    def build_balance(self):
        tab = self.balance_tab
        tk.Label(tab, text="Every wild monster and trainer, against every starter", font=("", 12, "bold")).pack(anchor="w")
        tk.Label(tab, text="Each cell: how often that starter wins, at the level you expect by then. Fights marked * are in the first fights, which the tests check. Click a line to change it.", fg=MUTED, wraplength=px(self, 760), justify="left").pack(anchor="w")
        row = tk.Frame(tab)
        row.pack(anchor="w", pady=px(self, 6))
        tk.Button(row, text="Work it out", command=self.run_balance).pack(side="left")
        self.balance_note = tk.Label(row, text="", fg=MUTED)
        self.balance_note.pack(side="left", padx=px(self, 8))
        holder = Scrolling(tab)
        holder.pack(fill="both", expand=True)
        self.balance_table = holder.inner
        self.balance_process = None

    def run_balance(self):
        if self.balance_process is not None:
            return
        self.shell.save_all()
        self.balance_note.config(text="Playing them all...")
        self.balance_process = ask_lab(self.project.root, "balance", {"plays": 60})
        self.after(150, self.watch_balance)

    def watch_balance(self):
        if self.balance_process.poll() is None:
            self.after(150, self.watch_balance)
            return
        answer, problem = lab_answer(self.balance_process)
        self.balance_process = None
        if answer is None:
            self.balance_note.config(text=problem[:140])
            return
        self.balance_note.config(text="")
        self.show_balance(answer)

    @staticmethod
    def shade(won):
        if won >= 0.8:
            return "#bfe3c9"
        if won >= 0.5:
            return "#f4e2a8"
        return "#f0b8b0"

    def show_balance(self, answer):
        table = self.balance_table
        for child in table.winfo_children():
            child.destroy()
        for c, name in enumerate(answer["starters"]):
            tk.Label(table, text=name, font=("", 9, "bold"), padx=px(self, 8)).grid(row=0, column=c + 1)
        for r, row in enumerate(answer["rows"], 1):
            mark = " *" if row["fair"] else ""
            name = tk.Label(table, text=row["name"] + mark, anchor="w", fg=ACCENT, cursor="hand2")
            name.grid(row=r, column=0, sticky="w", padx=(0, px(self, 14)))
            name.bind("<Button-1>", lambda e, s=row["section"], t=row["target"]: self.shell.go(s, t))
            for c, result in enumerate(row["results"]):
                tk.Label(table, text="%d%%" % (result["won"] * 100), bg=self.shade(result["won"]), width=8).grid(row=r, column=c + 1, padx=1, pady=1)

    # ── the world ──

    def build_world(self):
        self.world = tk.Canvas(self.world_tab, bg="#2b2f38", highlightthickness=0)
        bar_y = ttk.Scrollbar(self.world_tab, command=self.world.yview)
        bar_x = ttk.Scrollbar(self.world_tab, orient="horizontal", command=self.world.xview)
        self.world.configure(yscrollcommand=bar_y.set, xscrollcommand=bar_x.set)
        bar_y.pack(side="right", fill="y")
        bar_x.pack(side="bottom", fill="x")
        self.world.pack(fill="both", expand=True)

    def draw_world(self):
        c = self.world
        c.delete("all")
        data = self.project.world()
        if data is None:
            c.create_text(px(self, 300), px(self, 80), text="Fix the problem in the maps first.", fill="#ffffff")
            return
        self.world_photos = []
        unit = px(self, 190)
        boxes = {}
        for name, (gx, gy) in data["places"].items():
            x, y = gx * unit + px(self, 110), gy * unit + px(self, 90)
            boxes[name] = (x, y)
        for a, b in data["links"]:
            if a in boxes and b in boxes:
                c.create_line(boxes[a][0], boxes[a][1], boxes[b][0], boxes[b][1], fill="#9aa3b5", width=2)
        for name, (x, y) in boxes.items():
            picture = self.thumbnail(data["maps"][name])
            photo = ImageTk.PhotoImage(picture)
            self.world_photos.append(photo)
            item = c.create_image(x, y, image=photo)
            colour = "#ffd84a" if name == data["start"] else BAD if name in data["lost"] else "#ffffff"
            c.create_rectangle(x - photo.width() / 2 - 1, y - photo.height() / 2 - 1, x + photo.width() / 2 + 1, y + photo.height() / 2 + 1, outline=colour, width=2)
            words = name + (" (start)" if name == data["start"] else " (no way in)" if name in data["lost"] else "")
            label = c.create_text(x, y + photo.height() / 2 + px(self, 10), text=words, fill=colour, font=("", 9, "bold"))
            for thing in (item, label):
                c.tag_bind(thing, "<Button-1>", lambda e, n=name: self.open_place(n))
        region = c.bbox("all")
        if region:
            c.configure(scrollregion=(region[0] - 20, region[1] - 20, region[2] + 20, region[3] + 20))

    def open_place(self, name):
        self.shell.show("maps")
        self.shell.editor.open_map(name)

    def thumbnail(self, m):
        """A small picture of a map: one colour per cell, from its tile."""
        colours = {}
        cell = max(1, min(px(self, 140) // max(1, m.cols), px(self, 110) // max(1, len(m.rows))))
        img = Image.new("RGB", (m.cols * cell, len(m.rows) * cell))
        pen = ImageDraw.Draw(img)
        for r, row in enumerate(m.rows):
            for col, letter in enumerate(row):
                tile = m.legend[letter]["tile"]
                if tile not in colours:
                    with Image.open(os.path.join(map_tool.TILES, tile + ".png")) as t:
                        colours[tile] = t.convert("RGB").resize((1, 1), Image.BOX).getpixel((0, 0))
                shade = colours[tile]
                if (col, r) in m.extra_solid:
                    shade = tuple(v * 2 // 3 for v in shade)
                pen.rectangle([col * cell, r * cell, (col + 1) * cell - 1, (r + 1) * cell - 1], fill=shade)
        return img

    # ── forgotten ──

    def build_forgotten(self):
        tab = self.forgot_tab
        tk.Label(tab, text="What may have been forgotten", font=("", 12, "bold")).pack(anchor="w")
        tk.Label(tab, text="None of these stops the game. Click one to go there. It uses your saved files.", fg=MUTED).pack(anchor="w", pady=(0, px(self, 6)))
        self.forgot_box = tk.Listbox(tab, activestyle="none", exportselection=False)
        self.forgot_box.pack(fill="both", expand=True)
        self.forgot_box.bind("<<ListboxSelect>>", lambda e: self.open_forgotten())
        self.forgotten = []

    def show_forgotten(self):
        self.forgotten = self.project.forgotten()
        self.forgot_box.delete(0, "end")
        if not self.forgotten:
            self.forgot_box.insert("end", "Nothing: everything is used, and everything can be reached.")
        for use in self.forgotten:
            self.forgot_box.insert("end", use.text)

    def open_forgotten(self):
        chosen = self.forgot_box.curselection()
        if chosen and chosen[0] < len(self.forgotten):
            self.shell.go_use(self.forgotten[chosen[0]])
