"""The screens of the monster RPG's tables: monsters, moves, types... The list and the form that any table uses are
ApkPy's own now (apkpy_lib.game.studio.forms); this adds what only this game needs.
"""
import copy
import os
import re
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk

from apkpy_lib.game.studio import forms as _forms
import studio_data
from studio_ui import ACCENT, BAD, BG, LINE, MUTED, PANEL, Scrolling, px

WORDS = studio_data.WORDS


def readable(name):
    return WORDS.get(name) or name.replace("_", " ").capitalize()


class Form(_forms.Form):
    """A form, with the variant of a trainer's monster as a list of that monster's variants."""

    def special_value(self, holder, cls, name, spec, value, store, key, item):
        if (cls, name) == ("TrainerMonster", "variant") and item is not None:
            return self.variant_choice(holder, item, value, store)
        return None

    def variant_choice(self, holder, item, value, store):
        """default, or one of the variants of the monster in that line (asked again each time the list opens)."""
        box = ttk.Combobox(holder, state="readonly", width=12)

        def options():
            species = self.project.table("Species").get(item.get("species", "")) or {}
            box.configure(values=["default"] + [v.get("id", "") for v in species.get("variants", [])])

        box.configure(postcommand=options)
        options()
        box.set(value if value and value != "default" else "default")
        box.pack(anchor="w")
        box.bind("<<ComboboxSelected>>", lambda e: store("" if box.get() == "default" else box.get()))
        return box


class TableScreen(_forms.TableScreen):
    form_class = Form


class SimpleScreen(_forms.SimpleScreen):
    form_class = Form


class OneRowScreen(_forms.OneRowScreen):
    form_class = Form


class MonsterScreen(TableScreen):
    cls = "Species"
    noun = "monster"

    def list_image(self, row):
        path = self.project.sprite(row["id"])
        if not os.path.isfile(path):
            return None
        key = ("list", row["id"], os.path.getmtime(path))
        if key not in self.images:
            with Image.open(path) as img:
                cell = img.convert("RGBA").crop((0, 0, 64, 64))
            size = px(self, 24)
            self.images[key] = ImageTk.PhotoImage(cell.resize((size, size), Image.NEAREST))
        return self.images[key]

    def picture(self, parent, row_id, column):
        path = self.project.sprite(row_id)
        size = px(self, 128)
        canvas = tk.Canvas(parent, width=size, height=size, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        if os.path.isfile(path):
            key = ("big", row_id, column, os.path.getmtime(path))
            if key not in self.images:
                with Image.open(path) as img:
                    cell = img.convert("RGBA").crop((column * 64, 0, column * 64 + 64, 64))
                self.images[key] = ImageTk.PhotoImage(cell.resize((size, size), Image.NEAREST))
            canvas.create_image(size // 2, size // 2, image=self.images[key])
        else:
            canvas.create_text(size // 2, size // 2, text="It gets a drawing\nwhen you save,\nor in Art", fill=MUTED, justify="center")
        return canvas

    def top_part(self, parent, row):
        pictures = tk.Frame(parent)
        pictures.pack(side="left")
        for column, text in ((0, "Front"), (1, "Back")):
            cell = tk.Frame(pictures)
            cell.pack(side="left", padx=(0, px(self, 6)))
            self.picture(cell, row["id"], column).pack()
            tk.Label(cell, text=text, fg=MUTED).pack()
        words = tk.Frame(parent)
        words.pack(side="left", fill="both", expand=True, padx=(px(self, 8), 0))
        self.title_label = tk.Label(words, text=row.get("name") or row["id"], font=("", 15, "bold"))
        self.title_label.pack(anchor="w")
        self.chain_frame = tk.Frame(words)
        self.chain_frame.pack(anchor="w", pady=(px(self, 2), 0))
        self.draw_chain(row)
        buttons = tk.Frame(words)
        buttons.pack(anchor="w", pady=(px(self, 6), 0))
        tk.Button(buttons, text="Draw it in Art", command=lambda: self.shell.draw_monster(row["id"])).pack(side="left")
        tk.Button(buttons, text="Import a picture...", command=self.import_picture).pack(side="left", padx=(px(self, 6), 0))
        tk.Label(words, text="Two cells of 64 x 64: its front, then its back.", fg=MUTED).pack(anchor="w")

    def draw_chain(self, row):
        for child in self.chain_frame.winfo_children():
            child.destroy()
        table = self.table()
        first = row
        seen = {row["id"]}
        while True:
            before = next((r for r in table.rows if r.get("evolves_to") == first["id"] and r["id"] not in seen), None)
            if before is None:
                break
            seen.add(before["id"])
            first = before
        chain = [first]
        seen = {first["id"]}
        while chain[-1].get("evolves_to") and table.get(chain[-1]["evolves_to"]) and chain[-1]["evolves_to"] not in seen:
            seen.add(chain[-1]["evolves_to"])
            chain.append(table.get(chain[-1]["evolves_to"]))
        if len(chain) < 2:
            tk.Label(self.chain_frame, text="It does not evolve.", fg=MUTED).pack(side="left")
            return
        for i, r in enumerate(chain):
            if i:
                tk.Label(self.chain_frame, text=" > L%s > " % chain[i - 1].get("evolve_level", "?"), fg=MUTED).pack(side="left")
            label = tk.Label(self.chain_frame, text=r.get("name") or r["id"], fg=ACCENT if r is not row else "#22252b", cursor="hand2", font=("", 9, "bold" if r is row else "normal"))
            label.pack(side="left")
            label.bind("<Button-1>", lambda e, target=r["id"]: self.select(target))

    def special_fields(self):
        return {"base": self.stat_bars, "variants": self.variant_rows}

    def variant_rows(self, holder, row, form):
        """Its other looks: a picture of each, its name, how rare it is in the wild, and a way to draw it."""
        variants = row.get("variants") or []          # only written in the row when one is added: looking changes nothing
        frame = tk.Frame(holder)
        frame.pack(anchor="w", fill="x")
        size = px(self, 40)
        key = "Species.variants"

        def draw():
            for child in frame.winfo_children():
                child.destroy()
            if variants:
                for c, text in enumerate(("", "Id", "Name", "Wild: 1 in")):
                    tk.Label(frame, text=text, fg=MUTED).grid(row=0, column=c, sticky="w", padx=(0, px(self, 6)))
            for r, v in enumerate(variants, 1):
                path = self.project.sprite(row["id"], v.get("id", ""))
                picture = tk.Label(frame, width=size, height=size, bg=PANEL)
                if v.get("id") and os.path.isfile(path):
                    image_key = ("variant", row["id"], v["id"], os.path.getmtime(path))
                    if image_key not in self.images:
                        with Image.open(path) as img:
                            self.images[image_key] = ImageTk.PhotoImage(img.convert("RGBA").crop((0, 0, 64, 64)).resize((size, size), Image.NEAREST))
                    picture.configure(image=self.images[image_key], width=0, height=0)
                else:
                    picture.configure(text="?", fg=MUTED, width=4, height=2)
                picture.grid(row=r, column=0, sticky="w", padx=(0, px(self, 6)), pady=1)
                tk.Label(frame, text=v.get("id", "")).grid(row=r, column=1, sticky="w", padx=(0, px(self, 6)))
                name = tk.Frame(frame)
                name.grid(row=r, column=2, sticky="w", padx=(0, px(self, 6)))

                def store_name(text, it=v):
                    it["name"] = text
                    self.field_changed(key + ".name." + it["id"])

                form.text(name, v.get("name", ""), store_name).configure(width=16)
                chance = tk.Frame(frame)
                chance.grid(row=r, column=3, sticky="w", padx=(0, px(self, 6)))

                def store_chance(n, it=v):
                    it["one_in"] = n
                    self.field_changed(key + ".one_in." + it["id"])

                form.number(chance, v.get("one_in", 0), store_chance)
                tk.Button(frame, text="Draw it in Art", command=lambda it=v: self.shell.draw_monster(row["id"], it["id"])).grid(row=r, column=4, padx=(0, px(self, 4)))
                tk.Button(frame, text="x", width=2, command=lambda at=r - 1: remove(at)).grid(row=r, column=5)
            tk.Button(frame, text="+ Add a variant", command=add).grid(row=len(variants) + 1, column=0, columnspan=3, sticky="w", pady=(px(self, 3), 0))

        def add():
            name = simpledialog.askstring("New variant", "An id for this look, such as shiny or gold (lowercase letters, numbers and _):", parent=self)
            if not name:
                return
            name = name.strip()
            if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or name == "default":
                messagebox.showinfo("New variant", "An id is lowercase letters, numbers and _, and not default.", parent=self)
                return
            if any(v.get("id") == name for v in variants):
                messagebox.showinfo("New variant", "%s already has a variant called %s." % (row.get("name") or row["id"], name), parent=self)
                return
            row["variants"] = variants
            self.add_variant(row, name)
            draw()

        def remove(at):
            gone = variants.pop(at)
            self.shell.after_save_forget.append("%s.%s" % (row["id"], gone.get("id", "")))
            self.field_changed(key + ".remove")
            draw()

        draw()
        self.redraw_variants = draw

    def add_variant(self, row, name):
        """A new look, rare in the wild: Shiny, 1 in 4096."""
        row.setdefault("variants", []).append({"id": name, "name": name.replace("_", " ").title(), "one_in": 4096})
        self.project.draw_sprite(row["id"], name)          # a recoloured placeholder, to draw over in Art
        art = self.shell.screens.get("art")
        if art is not None:
            art.refresh()
        self.field_changed("Species.variants.add")

    def stat_bars(self, holder, row, form):
        """The stats as numbers and bars, with their total."""
        stats = row.setdefault("base", self.project.blank_row("BaseStats"))
        fields = self.project.classes["BaseStats"].fields
        width = px(self, 220)
        high = px(self, 12)
        bars = {}

        def draw():
            for name, canvas in bars.items():
                canvas.delete("all")
                value = stats.get(name, 0)
                share = min(1.0, value / 150.0)
                colour = "#d05050" if value < 40 else "#d0a030" if value < 70 else "#40a060"
                canvas.create_rectangle(0, 0, width, high, fill="#e4e7ec", width=0)
                canvas.create_rectangle(0, 0, width * share, high, fill=colour, width=0)
            total.config(text="Total %d" % sum(stats.get(f.name, 0) for f in fields))

        for i, f in enumerate(fields):
            tk.Label(holder, text=readable(f.name), width=8, anchor="w").grid(row=i, column=0, sticky="w")
            cell = tk.Frame(holder)
            cell.grid(row=i, column=1, sticky="w")

            def store(v, name=f.name):
                stats[name] = v
                draw()
                self.field_changed("Species.base." + name)

            self.form_number(cell, stats.get(f.name, 0), store)
            bars[f.name] = tk.Canvas(holder, width=width, height=high, bg=BG, highlightthickness=0)
            bars[f.name].grid(row=i, column=2, padx=px(self, 8))
        total = tk.Label(holder, text="", fg=MUTED)
        total.grid(row=len(fields), column=0, columnspan=2, sticky="w")
        draw()

    def form_number(self, holder, value, store):
        box = tk.Spinbox(holder, from_=1, to=255, width=5)
        box.delete(0, "end")
        box.insert(0, str(value))
        box.pack()

        def read(event=None):
            if box.get().strip().isdigit():
                store(int(box.get().strip()))

        box.configure(command=read)
        box.bind("<KeyRelease>", read)

    def after_change(self):
        row = self.selected
        self.title_label.config(text=row.get("name") or row["id"])
        self.draw_chain(row)
        if self.tree.exists(row["id"]):
            self.tree.item(row["id"], text=" " + self.list_label(row))

    def after_delete(self, row):
        self.shell.after_save_forget.append(row["id"])
        for v in row.get("variants", []):
            self.shell.after_save_forget.append("%s.%s" % (row["id"], v.get("id", "")))

    def import_picture(self):
        path = filedialog.askopenfilename(parent=self, title="A picture of this monster", filetypes=[("Pictures", "*.png *.gif *.bmp"), ("All files", "*.*")])
        if not path:
            return
        try:
            studio_data.make_backup("before picture", self.project.root)
            self.project.import_sprite(self.selected["id"], path)
        except (OSError, ValueError) as e:
            messagebox.showinfo("That picture does not fit", str(e), parent=self)
            return
        self.images = {}
        self.fill_list()
        self.show_row()


class MoveScreen(TableScreen):
    cls = "Move"
    noun = "move"

    def list_image(self, row):
        kinds = self.project.tables.get("Type")
        kind = kinds.get(row.get("type")) if kinds else None
        colour = kind.get("color") if kind else None
        if not colour:
            return None
        key = ("dot", colour)
        if key not in self.images:
            size = px(self, 14)
            self.images[key] = ImageTk.PhotoImage(Image.new("RGB", (size, size), colour))
        return self.images[key]

    def top_part(self, parent, row):
        self.title_label = tk.Label(parent, text=row.get("name") or row["id"], font=("", 15, "bold"))
        self.title_label.pack(anchor="w")
        self.summary = tk.Label(parent, text="", fg=MUTED)
        self.summary.pack(anchor="w")
        self.show_summary(row)

    def show_summary(self, row):
        power = row.get("power", 0)
        words = "%s, %s" % (row.get("type", "?"), row.get("kind", "?"))
        if power:
            words += ", power %s" % power
        if row.get("effect"):
            words += ", %s%% chance of %s" % (row.get("chance", 0), row["effect"].replace("_", " "))
        self.summary.config(text=words)

    def after_change(self):
        row = self.selected
        self.title_label.config(text=row.get("name") or row["id"])
        self.show_summary(row)
        if self.tree.exists(row["id"]):
            image = self.list_image(row)
            self.tree.item(row["id"], text=" " + self.list_label(row), **({"image": image} if image else {}))


class ItemScreen(SimpleScreen):
    cls = "Item"
    noun = "item"


class NatureScreen(SimpleScreen):
    cls = "Nature"
    noun = "nature"


class ShopScreen(SimpleScreen):
    cls = "Shop"
    noun = "shop"

    def bottom_part(self, parent, row):
        tk.Label(parent, text="What it sells", font=("", 10, "bold")).pack(anchor="w")
        self.prices = tk.Label(parent, text="", fg=MUTED, justify="left", anchor="w")
        self.prices.pack(anchor="w", pady=(px(self, 2), px(self, 10)))
        self.show_prices(row)

    def show_prices(self, row):
        table = self.project.table("Item")
        lines = []
        for item_id in row.get("items", []):
            item = table.get(item_id)
            if item:
                lines.append("%s: %s %s" % (item.get("name", item_id), item.get("price", 0), self.project.table("GameInfo").rows[0].get("currency", "")))
        self.prices.config(text="\n".join(lines) or "Nothing yet.")

    def after_change(self):
        SimpleScreen.after_change(self)
        self.show_prices(self.selected)


class TrainerScreen(SimpleScreen):
    cls = "Trainer"
    noun = "trainer"

    def top_part(self, parent, row):
        SimpleScreen.top_part(self, parent, row)
        self.pictures = tk.Frame(parent)
        self.pictures.pack(anchor="w", pady=(px(self, 4), 0))
        self.show_team(row)
        buttons = tk.Frame(parent)
        buttons.pack(anchor="w", pady=(px(self, 6), 0))
        tk.Button(buttons, text="Write what they say...", command=self.write_story).pack(side="left")
        has = "trainer.%s" % row["id"] in self.project.table("Event").ids()
        tk.Label(buttons, text="" if has else "They have nothing to say yet.", fg=MUTED).pack(side="left", padx=px(self, 8))

    def show_team(self, row):
        for child in self.pictures.winfo_children():
            child.destroy()
        size = px(self, 48)
        for member in row.get("team", []):
            path = self.project.sprite(member.get("species", ""), member.get("variant", ""))
            if not os.path.isfile(path):
                path = self.project.sprite(member.get("species", ""))
            cell = tk.Frame(self.pictures)
            cell.pack(side="left", padx=(0, px(self, 6)))
            if os.path.isfile(path):
                key = ("team", path, os.path.getmtime(path))
                if key not in self.images:
                    with Image.open(path) as img:
                        self.images[key] = ImageTk.PhotoImage(img.convert("RGBA").crop((0, 0, 64, 64)).resize((size, size), Image.NEAREST))
                tk.Label(cell, image=self.images[key]).pack()
            tk.Label(cell, text="L%s" % member.get("level", "?"), fg=MUTED).pack()

    def write_story(self):
        self.shell.show("story").open_event("trainer." + self.selected["id"])

    def after_change(self):
        SimpleScreen.after_change(self)
        self.show_team(self.selected)

    def bottom_part(self, parent, row):
        tk.Label(parent, text="To put them on a map, add a trainer in the map editor, with the name %s." % row["id"], fg=MUTED).pack(anchor="w", pady=(0, px(self, 8)))


class WildDialog(simpledialog.Dialog):
    """Which map, and which zone of it."""

    def __init__(self, parent, project):
        self.project = project
        self.result = None
        simpledialog.Dialog.__init__(self, parent, "New wild monsters")

    def body(self, frame):
        tk.Label(frame, text="Map").grid(row=0, column=0, sticky="w")
        self.map = ttk.Combobox(frame, values=self.project.map_names(), state="readonly")
        self.map.grid(row=0, column=1, sticky="ew")
        tk.Label(frame, text="Zone").grid(row=1, column=0, sticky="w")
        self.zone = ttk.Combobox(frame, values=[])
        self.zone.grid(row=1, column=1, sticky="ew")
        self.map.bind("<<ComboboxSelected>>", lambda e: self.pick_map())
        return self.map

    def pick_map(self):
        zones = self.project.zones_of_map(self.map.get())
        self.zone.configure(values=zones)
        self.zone.set(zones[0] if zones else "")

    def validate(self):
        return bool(self.map.get() and self.zone.get().strip())

    def apply(self):
        self.result = "%s.%s" % (self.map.get(), self.zone.get().strip())


class WildScreen(SimpleScreen):
    cls = "EncounterTable"
    noun = "wild monsters"

    def list_label(self, row):
        return row["id"].replace(".", ": ")

    def heading(self, row):
        name, _, zone = row["id"].partition(".")
        return "The %s of %s" % (zone, name)

    def new_row(self):
        dialog = WildDialog(self, self.project)
        if dialog.result:
            self.add(dialog.result)

    def add(self, row_id):
        if self.table().get(row_id) is not None:
            self.select(row_id)
            return
        self.remember_all()
        self.refresh_to(self.project.new_row(self.cls, "", row_id)["id"])

    def special_fields(self):
        return {"rows": self.rows_with_chance}

    @staticmethod
    def chances(rows):
        total = sum(r.get("weight", 0) for r in rows) or 1
        return ["%d%%" % round(r.get("weight", 0) * 100 / total) for r in rows]

    def rows_with_chance(self, holder, row, form):
        form.record_list(holder, "EncounterRow", row.setdefault("rows", []), "EncounterTable.rows", extra=self.chances)

    def bottom_part(self, parent, row):
        name, _, zone = row["id"].partition(".")
        if name not in self.project.map_names():
            text = "There is no map called %s." % name
        elif zone not in self.project.zones_of_map(name):
            text = "The map %s has no ground with the zone %s, so nothing comes out yet. In the map editor, paint it with a tile marked *." % (name, zone)
        else:
            text = "Monsters come out of the ground with the zone %s, on the map %s." % (zone, name)
        tk.Label(parent, text=text, fg=MUTED, wraplength=px(self, 560), justify="left").pack(anchor="w", pady=(0, px(self, 8)))


class TypeScreen(SimpleScreen):
    cls = "Type"
    noun = "type"
    MARKS = (("strong", "2", "#3f9d5f"), ("weak", "1/2", "#d08a30"), ("immune", "0", "#3a3f4a"))

    def list_image(self, row):
        colour = row.get("color")
        if not isinstance(colour, str) or not colour.startswith("#"):
            return None
        key = ("dot", colour)
        if key not in self.images:
            size = px(self, 14)
            try:
                self.images[key] = ImageTk.PhotoImage(Image.new("RGB", (size, size), colour))
            except ValueError:
                return None
        return self.images[key]

    def special_fields(self):
        return {"color": self.colour_field}

    def skip_fields(self):
        return ("id", "strong", "weak", "immune")          # in the table below

    def colour_field(self, holder, row, form):
        self.swatch = tk.Button(holder, text="  %s  " % row.get("color", ""), bg=row.get("color", "#909090"), fg="#ffffff", command=lambda: self.pick_colour(row))
        self.swatch.pack(anchor="w")

    def pick_colour(self, row):
        _, chosen = colorchooser.askcolor(color=row.get("color") or "#909090", parent=self, title="The colour of this type")
        if chosen:
            self.set_colour(row, chosen)

    def set_colour(self, row, colour):
        row["color"] = colour
        self.swatch.configure(text="  %s  " % colour, bg=colour)
        self.field_changed("Type.color")
        self.images = {}
        self.fill_list()
        self.draw_chart()

    def bottom_part(self, parent, row):
        tk.Label(parent, text="What each type does to the others", font=("", 10, "bold")).pack(anchor="w")
        tk.Label(parent, text="Rows attack, columns defend. Click a cell to go through: normal, 2 times, half, none.", fg=MUTED).pack(anchor="w")
        self.chart = tk.Frame(parent)
        self.chart.pack(anchor="w", pady=(px(self, 4), px(self, 12)))
        self.draw_chart()

    def value_at(self, attacker, defender):
        for key, _, _ in self.MARKS:
            if defender["id"] in attacker.get(key, []):
                return key
        return ""

    def cycle(self, attacker, defender):
        """normal, strong, weak, immune, normal."""
        order = ["", "strong", "weak", "immune"]
        now = self.value_at(attacker, defender)
        for key, _, _ in self.MARKS:
            if defender["id"] in attacker.get(key, []):
                attacker[key].remove(defender["id"])
        after = order[(order.index(now) + 1) % len(order)]
        if after:
            attacker.setdefault(after, []).append(defender["id"])
        self.field_changed("Type.chart.%s.%s" % (attacker["id"], defender["id"]))
        self.draw_chart()

    def draw_chart(self):
        for child in self.chart.winfo_children():
            child.destroy()
        rows = self.table().rows
        cell = px(self, 44)
        for c, defender in enumerate(rows):
            tk.Label(self.chart, text=defender.get("name", defender["id"])[:6], bg=defender.get("color", "#909090"), fg="#ffffff", font=("", 8)).grid(row=0, column=c + 1, sticky="nsew", padx=1, pady=1)
        for r, attacker in enumerate(rows):
            name = tk.Label(self.chart, text=attacker.get("name", attacker["id"]), bg=attacker.get("color", "#909090"), fg="#ffffff", anchor="w", padx=px(self, 6), cursor="hand2")
            name.grid(row=r + 1, column=0, sticky="nsew", padx=1, pady=1)
            name.bind("<Button-1>", lambda e, i=attacker["id"]: self.select(i))
            for c, defender in enumerate(rows):
                now = self.value_at(attacker, defender)
                text, colour = "", "#ffffff"
                for key, mark, shade in self.MARKS:
                    if key == now:
                        text, colour = mark, shade
                label = tk.Label(self.chart, text=text, bg=colour, fg="#ffffff" if now else "#22252b", width=4, cursor="hand2")
                label.grid(row=r + 1, column=c + 1, sticky="nsew", padx=1, pady=1)
                label.bind("<Button-1>", lambda e, a=attacker, d=defender: self.cycle(a, d))
        self.chart.columnconfigure(0, minsize=cell * 2)

    def after_change(self):
        SimpleScreen.after_change(self)


class EffectScreen(SimpleScreen):
    cls = "Effect"
    noun = "effect"

    def bottom_part(self, parent, row):
        moves = [m for m in self.project.table("Move").rows if m.get("effect") == row["id"]]
        tk.Label(parent, text="Moves with it: " + (", ".join("%s (%s%%)" % (m["name"], m.get("chance", 0)) for m in moves) or "none yet. Choose it in a move's effect."),
                 fg=MUTED, wraplength=px(self, 560), justify="left").pack(anchor="w", pady=(0, px(self, 8)))


class StatusScreen(SimpleScreen):
    cls = "Status"
    noun = "status"


class WordsScreen(SimpleScreen):
    """The words the game says: the id is how the code asks for them, so only the words change here."""
    cls = "Words"
    noun = "words"

    def list_label(self, row):
        text = row.get("text", "").replace("\n", " ")
        return "%s: %s" % (row["id"], text[:40])

    def heading(self, row):
        return row["id"]

    def new_row(self):
        name = simpledialog.askstring("New words", "Their id, as your own code will ask for them, such as my_hello:", parent=self)
        if name and name.strip():
            self.remember_all()
            row = self.project.new_row(self.cls, name.strip(), studio_data.slug(name.strip()))
            self.refresh_to(row["id"])

    def bottom_part(self, parent, row):
        tk.Label(parent, text="In code: word(\"%s\"), or named(\"%s\", a_name) to fill in {name}." % (row["id"], row["id"]), fg=MUTED).pack(anchor="w", pady=(0, px(self, 8)))


class RulesScreen(OneRowScreen):
    cls = "Rules"
    noun = "rules"
    title_text = "Rules"
    hint_text = "The numbers of the battles and of growing. The tests and the Balance tab show what a change does."


class GameScreen(TableScreen):
    """How the game starts, and the words of the story that the rules say: one row, so no list."""
    cls = "GameInfo"
    noun = "game"

    def build(self):
        self.page = Scrolling(self)
        self.page.pack(fill="both", expand=True, pady=px(self, 8))
        self.tree = None

    def fill_list(self):
        pass

    def select(self, row_id):
        self.selected = self.table().get(row_id)
        self.last_key = None
        self.show_row()

    def tree_selected(self):
        pass

    def show_row(self):
        for child in self.page.inner.winfo_children():
            child.destroy()
        row = self.selected
        body = tk.Frame(self.page.inner, padx=px(self, 14))
        body.pack(fill="x", expand=True)
        tk.Label(body, text="My game", font=("", 15, "bold")).pack(anchor="w")
        app = self.project.app
        names = tk.Frame(body)
        names.pack(fill="x", pady=(px(self, 6), px(self, 10)))
        names.columnconfigure(1, weight=1)
        at = 0
        for key, label, hint in (("name", "Name", "What the phone shows under the icon. The word on the title screen is a picture: it is not changed by this."),
                                 ("application_id", "App id", "Unique to your game, such as com.yourname.mygame. Two apps with the same id replace each other on a phone. Changing it makes it a new app, with a new signing key."),
                                 ("version_name", "Version", "What people read, such as 1.2.0."),
                                 ("version_code", "Version number", "A whole number that goes up with each version you publish.")):
            tk.Label(names, text=label, anchor="w").grid(row=at, column=0, sticky="w", padx=(0, px(self, 12)))
            entry = tk.Entry(names)
            entry.insert(0, app.values.get(key, ""))
            entry.grid(row=at, column=1, sticky="ew", ipady=px(self, 2), pady=(px(self, 3), 0))
            entry.bind("<KeyRelease>", lambda e, k=key, w=entry: self.app_changed(k, w))
            tk.Label(names, text=hint, fg=MUTED, anchor="w", justify="left", wraplength=px(self, 620)).grid(row=at + 1, column=1, sticky="w")
            at += 2
        self.problems = tk.Label(body, text="", fg=BAD, justify="left", anchor="w")
        self.problems.pack(fill="x")
        tk.Label(body, text="How it starts", font=("", 10, "bold")).pack(anchor="w")
        self.form = Form(body, self.project, self.cls, row, self.field_changed, special=self.special_fields())
        self.form.pack(fill="x", pady=(px(self, 4), px(self, 14)))
        self.show_problems()

    def app_changed(self, key, widget):
        self.project.app.values[key] = widget.get().strip()
        self.shell.name_changed()
        self.shell.content_changed()

    def special_fields(self):
        return {"start_map": lambda h, r, f: self.map_field(h, r, f, "start_map", "start_at"), "heal_map": lambda h, r, f: self.map_field(h, r, f, "heal_map", "heal_at"),
                "start_at": lambda h, r, f: self.marker_field(h, r, f, "start_map", "start_at"), "heal_at": lambda h, r, f: self.marker_field(h, r, f, "heal_map", "heal_at"),
                "fair_fights": self.fights_field}

    def map_field(self, holder, row, form, key, marker):
        def store(v):
            row[key] = v
            box = getattr(self, "markers", {}).get(marker)
            if box is not None:
                box.configure(values=self.project.markers_of_map(v))
            self.field_changed("GameInfo." + key)

        form.choice(holder, self.project.map_names(), row.get(key, ""), store, strict=True)

    def marker_field(self, holder, row, form, map_key, key):
        def store(v):
            row[key] = v
            self.field_changed("GameInfo." + key)

        box = form.choice(holder, self.project.markers_of_map(row.get(map_key, "")), row.get(key, ""), store)
        if not hasattr(self, "markers"):
            self.markers = {}
        self.markers[key] = box

    def fights_field(self, holder, row, form):
        names = self.project.table("EncounterTable").ids() + self.project.table("Trainer").ids()
        form.ref_list(holder, "", row.setdefault("fair_fights", []), "GameInfo.fair_fights", options=names)

    def after_change(self):
        pass

    def reload(self):
        rows = self.table().rows
        self.selected = rows[0] if rows else None
        self.undo_steps, self.redo_steps = [], []
        self._before = copy.deepcopy(rows)
        self.show_row()

    def refresh(self):
        self.show_row()
