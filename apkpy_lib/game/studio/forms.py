"""The screens of data tables: a list on the left and a form on the right. The form comes from the game's records
(@dataclass), so any table can use it, and a new field shows up by itself.

By Ruben Rego (the monster-rpg template's Studio), shared by every game's Studio. The monster-rpg template's
tools/studio_forms.py adds the screens only it needs (monsters, moves...).
"""
import copy
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .ui import ACCENT, BAD, MUTED, Scrolling, px


class Form(tk.Frame):
    """The fields of one row. Changing one writes it in the row, and calls on_change."""

    def __init__(self, parent, project, cls, row, on_change, skip=("id",), special=None):
        tk.Frame.__init__(self, parent)
        self.project, self.cls, self.row, self.on_change = project, cls, row, on_change
        self.special = special or {}
        self.widgets = {}
        self.columnconfigure(1, weight=1)
        at = 0
        for f in project.classes[cls].fields:
            if f.name in skip:
                continue
            tk.Label(self, text=project.label(f.name), anchor="nw").grid(row=at, column=0, sticky="nw", padx=(0, px(self, 12)), pady=(px(self, 6), 0))
            holder = tk.Frame(self)
            holder.grid(row=at, column=1, sticky="ew", pady=(px(self, 4), 0))
            if f.name in self.special:
                self.special[f.name](holder, row, self)
            else:
                self.field(holder, cls, f, row)
            at += 1
            text = project.help(cls, f.name)
            if text:
                tk.Label(self, text=text, fg=MUTED, anchor="w", justify="left", wraplength=px(self, 460)).grid(row=at, column=1, sticky="w")
                at += 1

    def changed(self, key):
        self.on_change(key)

    def field(self, holder, cls, f, row):
        spec, value = f.spec, row.get(f.name, f.default)
        key = "%s.%s" % (cls, f.name)

        def store(v):
            row[f.name] = v
            self.changed(key)

        self.widgets[f.name] = self.value_widget(holder, cls, f.name, spec, value, store, key)

    def value_widget(self, holder, cls, name, spec, value, store, key, item=None):
        choices = self.project.choices(cls, name)
        special = self.special_value(holder, cls, name, spec, value, store, key, item)
        if special is not None:
            return special
        if spec.kind == "int":
            return self.number(holder, value, store)
        if spec.kind == "bool":
            return self.yes_no(holder, bool(value), store)
        if spec.kind == "float":
            return self.decimal(holder, value if value is not None else 0.0, store)
        if spec.kind == "ref":
            return self.choice(holder, self.project.table(spec.target).ids(), value, store, strict=True)
        if spec.kind == "optional":
            inner = spec.item
            if inner.kind == "ref":
                return self.choice(holder, [""] + self.project.table(inner.target).ids(), value or "", lambda v: store(v or None), strict=True)
            return self.text(holder, value or "", lambda v: store(v or None))
        if spec.kind == "list":
            value = value if value is not None else []
            if spec.item.kind == "record":
                return self.record_list(holder, spec.item.target, value, key)
            if spec.item.kind == "ref":
                return self.ref_list(holder, spec.item.target, value, key)
            return self.text(holder, ", ".join(str(v) for v in value), lambda v: store([x.strip() for x in v.split(",") if x.strip()]))
        if spec.kind == "record":
            return self.record(holder, spec.target, value, key)
        if choices is not None:
            return self.choice(holder, choices, value or "", store)
        return self.text(holder, "" if value is None else str(value), store)

    def text(self, holder, value, store):
        entry = tk.Entry(holder)
        entry.insert(0, value)
        entry.pack(fill="x", ipady=px(self, 2))
        entry.bind("<KeyRelease>", lambda e: store(entry.get()))
        return entry

    def yes_no(self, holder, value, store):
        chosen = tk.BooleanVar(value=value)
        box = tk.Checkbutton(holder, variable=chosen, command=lambda: store(chosen.get()))
        box.pack(anchor="w")
        box.variable = chosen
        return box

    def decimal(self, holder, value, store):
        """A number that can have a point, such as 1.5."""
        entry = tk.Entry(holder, width=8)
        entry.insert(0, str(value))
        entry.pack(anchor="w", ipady=px(self, 2))

        def read(event=None):
            try:
                number = float(entry.get().strip())
            except ValueError:
                entry.configure(fg=BAD)
                return
            entry.configure(fg="#22252b")
            store(number)

        entry.bind("<KeyRelease>", read)
        return entry

    def number(self, holder, value, store):
        box = tk.Spinbox(holder, from_=0, to=99999, width=7)
        box.delete(0, "end")
        box.insert(0, str(value if value is not None else 0))
        box.pack(anchor="w", ipady=px(self, 1))

        def read(event=None):
            text = box.get().strip()
            if text.isdigit():
                box.configure(fg="#22252b")
                store(int(text))
            else:
                box.configure(fg=BAD)

        box.configure(command=read)
        box.bind("<KeyRelease>", read)
        return box

    def choice(self, holder, values, value, store, strict=False):
        box = ttk.Combobox(holder, values=values, state="readonly" if strict and value in values else "normal", width=24)
        box.set(value)
        box.pack(anchor="w")

        def read(event=None):
            store(box.get().strip())

        box.bind("<<ComboboxSelected>>", read)
        box.bind("<KeyRelease>", read)
        return box

    def special_value(self, holder, cls, name, spec, value, store, key, item):
        """A widget of a kit's own for this field (the monster RPG's variant of a trainer's monster), or None."""
        return None

    def record(self, holder, target, value, key):
        grid = tk.Frame(holder)
        grid.pack(anchor="w")
        for i, f in enumerate(self.project.classes[target].fields):
            tk.Label(grid, text=self.project.label(f.name)).grid(row=i, column=0, sticky="w")
            cell = tk.Frame(grid)
            cell.grid(row=i, column=1, sticky="w", padx=px(self, 6))
            def store(v, name=f.name):
                value[name] = v
                self.changed(key)
            self.value_widget(cell, target, f.name, f.spec, value.get(f.name, f.default), store, key)
        return grid

    def ref_list(self, holder, target, values, key, options=None):
        """Several rows of another table: each one a chip with an x, and a list to add from."""
        frame = tk.Frame(holder)
        frame.pack(anchor="w", fill="x")
        ids = options if options is not None else self.project.table(target).ids()

        def draw():
            for child in frame.winfo_children():
                child.destroy()
            for i, v in enumerate(values):
                chip = tk.Frame(frame, bg=self.chip_colour(target, v), padx=px(self, 5))
                chip.pack(side="left", padx=(0, px(self, 3)))
                tk.Label(chip, text=v, bg=chip.cget("bg"), fg="#ffffff").pack(side="left")
                x = tk.Label(chip, text=" x", bg=chip.cget("bg"), fg="#ffffff", cursor="hand2")
                x.pack(side="left")
                x.bind("<Button-1>", lambda e, at=i: remove(at))
            box = ttk.Combobox(frame, values=[i for i in ids if i not in values], state="readonly", width=14)
            box.set("add...")
            box.pack(side="left")
            box.bind("<<ComboboxSelected>>", lambda e: add(box.get()))

        def add(v):
            values.append(v)
            self.changed(key + ".add")
            draw()

        def remove(at):
            values.pop(at)
            self.changed(key + ".remove")
            draw()

        draw()
        return frame

    def chip_colour(self, target, row_id):
        table = self.project.tables.get(target)
        row = table.get(row_id) if table else None
        colour = row.get("color") if row else None
        return colour if isinstance(colour, str) and colour.startswith("#") else "#667080"

    def record_list(self, holder, target, rows, key, extra=None):
        """A table of records: a line for each, x to remove, and a button to add. extra(rows): more words for each line."""
        frame = tk.Frame(holder)
        frame.pack(anchor="w", fill="x")
        fields = self.project.classes[target].fields
        extra_labels = []

        def refresh():
            if extra:
                for label, text in zip(extra_labels, extra(rows)):
                    label.config(text=text)

        def draw():
            for child in frame.winfo_children():
                child.destroy()
            del extra_labels[:]
            for c, f in enumerate(fields):
                tk.Label(frame, text=self.project.label(f.name), fg=MUTED).grid(row=0, column=c, sticky="w", padx=(0, px(self, 6)))
            for r, item in enumerate(rows, 1):
                for c, f in enumerate(fields):
                    cell = tk.Frame(frame)
                    cell.grid(row=r, column=c, sticky="w", padx=(0, px(self, 6)), pady=1)
                    def store(v, it=item, name=f.name):
                        it[name] = v
                        refresh()
                        self.changed(key)
                    self.value_widget(cell, target, f.name, f.spec, item.get(f.name, f.default), store, key, item=item)
                tk.Button(frame, text="x", width=2, command=lambda at=r - 1: remove(at)).grid(row=r, column=len(fields))
                if extra:
                    label = tk.Label(frame, text="", fg=MUTED)
                    label.grid(row=r, column=len(fields) + 1, padx=px(self, 6), sticky="w")
                    extra_labels.append(label)
            tk.Button(frame, text="+ Add", command=add).grid(row=len(rows) + 1, column=0, sticky="w", pady=(px(self, 3), 0))
            refresh()

        def add():
            item = self.project.blank_row(target)
            for f in fields:
                if f.spec.kind == "ref":
                    ids = self.project.table(f.spec.target).ids()
                    item[f.name] = ids[0] if ids else ""
                elif f.name == "level" and rows:
                    item[f.name] = rows[-1].get("level", 1) + 1
                elif f.name == "level":
                    item[f.name] = 1
            rows.append(item)
            self.changed(key + ".add")
            draw()

        def remove(at):
            rows.pop(at)
            self.changed(key + ".remove")
            draw()

        draw()
        return frame


class TableScreen(tk.Frame):
    """Any table: find a row, change it, copy it, rename it everywhere, delete it if nothing uses it."""
    cls = ""
    noun = "row"
    form_class = Form

    def __init__(self, parent, shell):
        tk.Frame.__init__(self, parent)
        self.shell, self.project = shell, shell.project
        self.selected = None
        self.undo_steps, self.redo_steps = [], []
        self.last_key = None
        self.images = {}
        self.build()
        self.fill_list()
        ids = self.table().ids()
        if ids:
            self.select(ids[0])

    def table(self):
        return self.project.table(self.cls)

    def build(self):
        left = tk.Frame(self, width=px(self, 250))
        left.pack(side="left", fill="y", padx=px(self, 8), pady=px(self, 8))
        left.pack_propagate(False)
        self.search = tk.Entry(left)
        self.search.pack(fill="x", ipady=px(self, 2))
        self.search.insert(0, "Find...")
        self.search.configure(fg=MUTED)
        self.search.bind("<FocusIn>", lambda e: self.clear_hint())
        self.search.bind("<KeyRelease>", lambda e: self.fill_list())
        buttons = tk.Frame(left)
        buttons.pack(side="bottom", fill="x", pady=(px(self, 6), 0))
        for text, command in (("New", self.new_row), ("Copy", self.copy_row), ("Delete", self.delete_row)):
            tk.Button(buttons, text=text, command=command).pack(side="left", expand=True, fill="x", padx=1)
        box = tk.Frame(left)
        box.pack(fill="both", expand=True, pady=(px(self, 6), 0))
        self.tree = ttk.Treeview(box, show="tree", selectmode="browse")
        bar = ttk.Scrollbar(box, command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.tree_selected())

        self.page = Scrolling(self)
        self.page.pack(side="left", fill="both", expand=True, pady=px(self, 8))

    def clear_hint(self):
        if self.search.get() == "Find...":
            self.search.delete(0, "end")
            self.search.configure(fg="#22252b")

    def search_text(self):
        text = self.search.get().strip().lower()
        return "" if text == "find..." else text

    def list_label(self, row):
        return row.get("name") or row["id"]

    def list_image(self, row):
        return None

    def fill_list(self):
        wanted = self.search_text()
        self.tree.delete(*self.tree.get_children())
        for row in self.table().rows:
            if wanted and wanted not in row["id"].lower() and wanted not in str(row.get("name", "")).lower():
                continue
            image = self.list_image(row)
            self.tree.insert("", "end", iid=row["id"], text=" " + self.list_label(row), **({"image": image} if image else {}))
        if self.selected and self.tree.exists(self.selected["id"]):
            self.tree.selection_set(self.selected["id"])

    def tree_selected(self):
        chosen = self.tree.selection()
        if chosen and (self.selected is None or chosen[0] != self.selected["id"]):
            self.select(chosen[0])

    def select(self, row_id):
        row = self.table().get(row_id)
        if row is None:
            return
        self.selected = row
        self.last_key = None
        if self.tree.exists(row_id):
            self.tree.selection_set(row_id)
            self.tree.see(row_id)
        self.show_row()
        self.page.to_top()

    def show_row(self):
        for child in self.page.inner.winfo_children():
            child.destroy()
        row = self.selected
        if row is None:
            return
        body = tk.Frame(self.page.inner, padx=px(self, 12))
        body.pack(fill="x", expand=True)
        top = tk.Frame(body)
        top.pack(fill="x", pady=(0, px(self, 8)))
        self.top_part(top, row)
        identity = tk.Frame(body)
        identity.pack(fill="x")
        tk.Label(identity, text="id: %s" % row["id"], fg=MUTED).pack(side="left")
        tk.Button(identity, text="Rename everywhere...", command=self.rename_row).pack(side="left", padx=px(self, 8))
        self.problems = tk.Label(body, text="", fg=BAD, justify="left", anchor="w", wraplength=px(self, 560))
        self.problems.pack(fill="x")
        self.form = self.form_class(body, self.project, self.cls, row, self.field_changed, skip=self.skip_fields(), special=self.special_fields())
        self.form.pack(fill="x", pady=(px(self, 4), px(self, 10)))
        self.bottom_part(body, row)
        self.used_by(body, row)
        self.show_problems()

    def top_part(self, parent, row):
        tk.Label(parent, text=row.get("name") or row["id"], font=("", 15, "bold")).pack(anchor="w")

    def bottom_part(self, parent, row):
        pass

    def special_fields(self):
        return {}

    def skip_fields(self):
        return ("id",)

    def used_by(self, parent, row):
        """Where this row is named, each a link. Rows that show this in their own way say so."""
        if self.cls in self.project.NO_USES:
            return
        used = self.project.uses(self.cls, row["id"])
        tk.Label(parent, text="Where it is used", font=("", 10, "bold")).pack(anchor="w", pady=(px(self, 4), 0))
        box = tk.Frame(parent)
        box.pack(anchor="w", pady=(px(self, 2), px(self, 12)))
        if not used:
            tk.Label(box, text="Nowhere yet.", fg=MUTED).pack(anchor="w")
        for use in used[:14]:
            label = tk.Label(box, text=use.text[:90], fg=ACCENT, cursor="hand2", anchor="w")
            label.pack(anchor="w")
            label.bind("<Button-1>", lambda e, u=use: self.shell.go_use(u))
        if len(used) > 14:
            tk.Label(box, text="and %d more" % (len(used) - 14), fg=MUTED).pack(anchor="w")

    def refresh(self):
        """Other sections may have changed what this one offers."""
        if self.selected is not None and self.table().get(self.selected["id"]) is self.selected:
            self.fill_list()
            self.show_row()

    def show_problems(self):
        found = self.project.row_problems(self.cls, self.selected)
        self.problems.config(text="\n".join(found))

    def field_changed(self, key):
        """A run of changes in one field is one step of undo."""
        if key != self.last_key or key.endswith((".add", ".remove")):
            self.undo_steps.append(self.before)
            del self.undo_steps[:-100]
            self.redo_steps = []
        self.last_key = key
        self.before = copy.deepcopy(self.table().rows)
        self.show_problems()
        self.after_change()
        self.shell.content_changed()

    def after_change(self):
        pass

    @property
    def before(self):
        if not hasattr(self, "_before"):
            self._before = copy.deepcopy(self.table().saved)
        return self._before

    @before.setter
    def before(self, value):
        self._before = value

    def remember_all(self):
        self.undo_steps.append(copy.deepcopy(self.table().rows))
        self.redo_steps = []
        self.last_key = None

    def do_undo(self):
        self.swap(self.undo_steps, self.redo_steps)

    def do_redo(self):
        self.swap(self.redo_steps, self.undo_steps)

    def swap(self, source, target):
        if not source:
            return
        table = self.table()
        target.append(copy.deepcopy(table.rows))
        table.rows[:] = source.pop()
        self._before = copy.deepcopy(table.rows)
        self.last_key = None
        keep = self.selected["id"] if self.selected else None
        self.selected = table.get(keep) or (table.rows[0] if table.rows else None)
        self.fill_list()
        self.show_row()
        self.shell.content_changed()

    def new_row(self):
        name = simpledialog.askstring("New " + self.noun, "Its name:", parent=self)
        if name and name.strip():
            self.remember_all()
            row = self.project.new_row(self.cls, name.strip())
            self.after_new(row)
            self.refresh_to(row["id"])

    def after_new(self, row):
        pass

    def refresh_to(self, row_id):
        self.fill_list()
        self.select(row_id)
        self._before = copy.deepcopy(self.table().rows)
        self.shell.content_changed()

    def copy_row(self):
        if self.selected is not None:
            self.remember_all()
            self.refresh_to(self.project.copy_row(self.cls, self.selected)["id"])

    def delete_row(self):
        row = self.selected
        if row is None:
            return
        used = self.project.uses(self.cls, row["id"])
        if used:
            messagebox.showinfo("It is in use", "%s cannot be deleted, because these use it:\n\n%s" % (row.get("name") or row["id"], "\n".join(u.text for u in used[:12])), parent=self)
            return
        if not messagebox.askyesno("Delete", "Delete %s?" % (row.get("name") or row["id"]), parent=self):
            return
        self.remember_all()
        at = self.table().rows.index(row)
        self.project.delete(self.cls, row["id"])
        self.after_delete(row)
        rows = self.table().rows
        self.selected = None
        self.fill_list()
        if rows:
            self.select(rows[min(at, len(rows) - 1)]["id"])
        else:
            self.show_row()
        self._before = copy.deepcopy(rows)
        self.shell.content_changed()

    def after_delete(self, row):
        pass

    def rename_row(self):
        row = self.selected
        new = simpledialog.askstring("Rename everywhere", "The new id of %s, such as big_slime.\n\nYour work is saved first, and a copy of the project is made." % row["id"], parent=self, initialvalue=row["id"])
        if new and new.strip() and new.strip() != row["id"]:
            self.shell.rename(self.cls, row["id"], new.strip())

    def reload(self):
        """The files changed: see them again."""
        keep = self.selected["id"] if self.selected else None
        self.selected = self.table().get(keep) or (self.table().rows[0] if self.table().rows else None)
        self.undo_steps, self.redo_steps = [], []
        self._before = copy.deepcopy(self.table().rows)
        self.images = {}
        self.fill_list()
        self.show_row()

    def go_to(self, row_id):
        self.select(row_id)


class SimpleScreen(TableScreen):
    """A table with no extras: the name in the list and at the top."""

    def top_part(self, parent, row):
        self.title_label = tk.Label(parent, text=self.heading(row), font=("", 15, "bold"))
        self.title_label.pack(anchor="w")

    def heading(self, row):
        return row.get("name") or row["id"]

    def after_change(self):
        row = self.selected
        self.title_label.config(text=self.heading(row))
        if self.tree.exists(row["id"]):
            self.tree.item(row["id"], text=" " + self.list_label(row))


class OneRowScreen(TableScreen):
    """A table of one row: no list."""

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

    def top_part(self, parent, row):
        tk.Label(parent, text=self.title_text, font=("", 15, "bold")).pack(anchor="w")
        tk.Label(parent, text=self.hint_text, fg=MUTED, wraplength=px(self, 640), justify="left").pack(anchor="w")

    def used_by(self, parent, row):
        pass

    def show_row(self):
        TableScreen.show_row(self)
        for child in self.page.inner.winfo_children()[0].winfo_children():
            if isinstance(child, tk.Frame) and any(isinstance(c, tk.Button) and c.cget("text").startswith("Rename") for c in child.winfo_children()):
                child.destroy()

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
