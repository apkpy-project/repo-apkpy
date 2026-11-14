"""Scenes: each game.scene(...) of game/main.py, with its settings, its camera, its rules (when("lives <= 0", ...))
and the things added to it (scene.add(...)): objects, texts on the screen, shapes, a level made in Tiled.

Also the variables of Game(...) (score, lives...), which My game shows: texts show them as {name}, rules test them.
"""
import re
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .code import ADD_FIELDS, CAMERA_FIELDS, CONDITION, OPERATORS, SCENE_FIELDS, condition_parts, condition_text, slug
from .fields import CODE_FONT, NUMBER, CallForm, line
from .objects import EntityEditor
from .source import Call, Sequence, literal
from .ui import BAD, LINE, MUTED, PANEL, TEXT, Scrolling, px

WORD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class CameraForm(tk.Frame):
    """camera={"follow": "player", "bounds": "map", ...}: one field for each key; the dictionary is written again."""

    def __init__(self, parent, editor, source, path, kind):
        tk.Frame.__init__(self, parent)
        self.editor, self.source, self.path = editor, source, path
        call = source.at(path)
        camera = call.get("camera")
        if camera is not None and camera.kind != "literal":
            CallForm(self, editor, source, path, {"camera": {"type": "camera"}}, ["name"], section="scenes").pack(anchor="w", fill="x")
            return
        self.values = dict(camera.value) if camera is not None else {}
        self.columnconfigure(1, weight=1)
        at = 0
        for key, spec in CAMERA_FIELDS.items():
            if key in ("pitch", "distance", "fov") and kind != "2.5d":
                continue
            tk.Label(self, text=key.capitalize(), anchor="w").grid(row=at, column=0, sticky="w", padx=(0, px(self, 10)), pady=(px(self, 3), 0))
            holder = tk.Frame(self)
            holder.grid(row=at, column=1, sticky="w", pady=(px(self, 3), 0))
            shown = self.values.get(key, "")
            if key == "bounds" and not isinstance(shown, str):
                shown = literal(tuple(shown))
            if spec["type"] == "enum":
                box = ttk.Combobox(holder, values=spec["values"], width=10)
                box.set(shown)
                box.pack(side="left")
                box.bind("<<ComboboxSelected>>", lambda e, k=key, w=box: self.changed(k, w.get()))
                box.bind("<KeyRelease>", lambda e, k=key, w=box: self.changed(k, w.get()))
            else:
                entry = tk.Entry(holder, width=14 if spec["type"] == "string" else 8)
                entry.insert(0, literal(shown) if not isinstance(shown, str) else shown)
                entry.pack(side="left")
                entry.bind("<KeyRelease>", lambda e, k=key, w=entry, t=spec["type"]: self.changed(k, w.get(), t, w))
            tk.Label(holder, text=spec.get("doc", ""), fg=MUTED).pack(side="left", padx=px(self, 8))
            at += 1

    def changed(self, key, text, kind="string", widget=None):
        text = text.strip()
        if kind == "number" and text and not NUMBER.match(text):
            widget.configure(fg=BAD)
            return
        if widget is not None:
            widget.configure(fg=TEXT)
        if not text:
            self.values.pop(key, None)
        elif kind == "number":
            self.values[key] = float(text) if "." in text else int(text)
        elif key == "bounds" and text.startswith("("):
            try:
                self.values[key] = tuple(float(v) if "." in v else int(v) for v in text.strip("()").split(","))
            except ValueError:
                return
        else:
            self.values[key] = text
        call = self.source.at(self.path)
        if self.values:
            self.source.set_arg(call, "camera", literal(self.values), merge=(self.path, "camera"))
        else:
            self.source.remove_arg(call, "camera")
        self.editor.touched("scenes")


class RulesEditor(tk.Frame):
    """rules=[when("lives <= 0", ...), ...]: a condition and its actions for each."""

    def __init__(self, parent, editor, source, path):
        tk.Frame.__init__(self, parent)
        self.editor, self.code, self.source, self.path = editor, editor.code, source, path
        call = source.at(path)
        rules = call.get("rules")
        if rules is not None and not isinstance(rules, Sequence):
            CallForm(self, editor, source, path, {"rules": {"type": "rules"}}, ["name"], section="scenes").pack(anchor="w", fill="x")
            return
        for n, rule in enumerate(rules.args if rules is not None else []):
            self.rule(n, rule)
        bar = tk.Frame(self)
        bar.pack(anchor="w", pady=(px(self, 6), 0))
        tk.Button(bar, text="Add a rule", command=self.add).pack(side="left")

    def rule(self, n, rule):
        card = tk.Frame(self, bg=PANEL, highlightthickness=1, highlightbackground=LINE, padx=px(self, 10), pady=px(self, 6))
        card.pack(fill="x", pady=(px(self, 6), 0))
        head = tk.Frame(card, bg=PANEL)
        head.pack(fill="x")
        remove = tk.Label(head, text="remove", fg=MUTED, bg=PANEL, cursor="hand2")
        remove.pack(side="right")
        remove.bind("<Button-1>", lambda e: self.remove(n))
        condition = rule.get(0) if isinstance(rule, Call) and rule.func == "when" else None
        parts = condition_parts(condition.value) if condition is not None and condition.kind == "literal" else None
        if parts is None:
            tk.Label(head, text=rule.text, font=CODE_FONT, bg=PANEL).pack(side="left")
            return
        tk.Label(head, text="When", font=("", 10, "bold"), bg=PANEL).pack(side="left", padx=(0, px(self, 6)))
        subjects = self.code.variables() + ["count(%s)" % t for t in self.code.tags()]
        subject = ttk.Combobox(head, values=subjects, width=16)
        subject.set("count(%s)" % parts[0] if parts[1] else parts[0])
        subject.pack(side="left")
        op = ttk.Combobox(head, values=OPERATORS, state="readonly", width=4)
        op.set(parts[2])
        op.pack(side="left", padx=px(self, 4))
        number = tk.Entry(head, width=7)
        number.insert(0, parts[3])
        number.pack(side="left")

        def changed(event=None):
            text = "%s %s %s" % (subject.get().strip(), op.get(), number.get().strip())
            good = CONDITION.match(text) is not None
            number.configure(fg=TEXT if good else BAD)
            if good:
                self.source.set_arg(self.source.at(rule.path), 0, literal(text), merge=(rule.path, "when"))
                self.editor.touched("scenes")

        for widget in (subject, number):
            widget.bind("<KeyRelease>", changed)
        subject.bind("<<ComboboxSelected>>", changed)
        op.bind("<<ComboboxSelected>>", changed)
        CallForm(card, self.editor, self.source, rule.path, {"actions": {"type": "actions"}}, ["condition", "*actions"],
                 section="scenes").pack(anchor="w", fill="x")

    def add(self):
        names = self.code.variables()
        condition = condition_text(names[0], False, ">=", "10") if names else condition_text("coin", True, "==", "0")
        text = 'when(%s, exit_game({"result": "win"}))' % literal(condition)
        call = self.source.at(self.path)
        rules = call.get("rules")
        if rules is None:
            self.source.set_arg(call, "rules", "[%s]" % text)
        else:
            self.source.insert(rules, text, len(rules.items))
        self.editor.touched("scenes")
        self.editor.redraw()

    def remove(self, n):
        call = self.source.at(self.path)
        rules = call.get("rules")
        if len(rules.items) == 1:
            self.source.remove_arg(call, "rules")
        else:
            self.source.remove_arg(rules, n)
        self.editor.touched("scenes")
        self.editor.redraw()


class VariablesEditor(tk.Frame):
    """vars={"score": 0, "lives": 3}: a name and a starting number on each line."""

    def __init__(self, parent, editor, source, path):
        tk.Frame.__init__(self, parent)
        self.editor, self.source, self.path = editor, source, path
        found = source.at(path).get("vars")
        if found is not None and found.kind != "literal":
            CallForm(self, editor, source, path, {"vars": {"type": "dict"}}, ["name"], section="game").pack(anchor="w", fill="x")
            return
        self.rows = []
        self.list = tk.Frame(self)
        self.list.pack(anchor="w")
        for name, number in (found.value.items() if found is not None else []):
            self.row(name, literal(number))
        bar = tk.Frame(self)
        bar.pack(anchor="w", pady=(px(self, 4), 0))
        tk.Button(bar, text="Add a variable", command=lambda: (self.row("", "0"), self.rows[-1][0].focus_set())).pack(side="left")
        self.note = tk.Label(bar, text="", fg=BAD)
        self.note.pack(side="left", padx=px(self, 8))

    def row(self, name, number):
        line_ = tk.Frame(self.list)
        line_.pack(anchor="w", pady=(px(self, 2), 0))
        a = tk.Entry(line_, width=16)
        a.insert(0, name)
        a.pack(side="left")
        tk.Label(line_, text="starts at").pack(side="left", padx=px(self, 6))
        b = tk.Entry(line_, width=8)
        b.insert(0, number)
        b.pack(side="left")
        x = tk.Label(line_, text="  remove", fg=MUTED, cursor="hand2")
        x.pack(side="left")
        entry = (a, b, line_)
        self.rows.append(entry)
        x.bind("<Button-1>", lambda e: self.remove(entry))
        for w in (a, b):
            w.bind("<KeyRelease>", lambda e: self.write())

    def remove(self, entry):
        self.rows.remove(entry)
        entry[2].destroy()
        self.write()

    def write(self):
        values = {}
        good = True
        for a, b, _ in self.rows:
            name, number = a.get().strip(), b.get().strip()
            a.configure(fg=TEXT if WORD.match(name) else BAD)
            b.configure(fg=TEXT if NUMBER.match(number) else BAD)
            if not (WORD.match(name) and NUMBER.match(number)) or name in values:
                good = False
                continue
            values[name] = float(number) if "." in number else int(number)
        self.note.config(text="" if good else "A name is one word; a number like 3 or 0.5; no name twice.")
        if not good:
            return
        call = self.source.at(self.path)
        if values:
            self.source.set_arg(call, "vars", literal(values), merge=(self.path, "vars"))
        else:
            self.source.remove_arg(call, "vars")
        self.editor.touched("game")


class ScenesScreen(tk.Frame):
    """The scenes on the left; the chosen one's settings, rules and things on the right."""

    section = "scenes"

    def __init__(self, parent, shell):
        tk.Frame.__init__(self, parent)
        self.shell, self.code = shell, shell.code
        self.chosen = None
        self.open_things = set()
        self.expanded = set()
        left = tk.Frame(self, padx=px(self, 10), pady=px(self, 10))
        left.pack(side="left", fill="y")
        tk.Label(left, text="Scenes", font=("", 15, "bold")).pack(anchor="w")
        tk.Label(left, text="The places of your game.", fg=MUTED).pack(anchor="w", pady=(0, px(self, 6)))
        self.items = tk.Listbox(left, activestyle="none", exportselection=False, width=24, height=16)
        self.items.pack(fill="y", expand=True)
        self.items.bind("<<ListboxSelect>>", lambda e: self.pick())
        tk.Button(left, text="New scene...", command=self.new).pack(fill="x", pady=(px(self, 6), 0))
        tk.Button(left, text="Delete", command=self.delete).pack(fill="x", pady=(px(self, 4), 0))
        tk.Frame(self, bg=LINE, width=1).pack(side="left", fill="y")
        self.detail = Scrolling(self)
        self.detail.pack(side="left", fill="both", expand=True)
        self.fill_list()

    def touched(self, section):
        self.code.touch(section or self.section)
        self.shell.content_changed()

    def redraw(self):
        self.after_idle(self.show_chosen)

    @property
    def main(self):
        return self.code.main

    def fill_list(self):
        self.scenes = self.code.scenes()
        self.items.delete(0, "end")
        names = []
        for piece in self.scenes:
            name = self.main.scene_names.get(piece.name, piece.name)
            start = piece.call.get("start")
            self.items.insert("end", name + ("   (start)" if start is not None and start.text == "True" else ""))
            names.append(piece.name)
        if self.chosen not in names:
            self.chosen = names[0] if names else None
        if self.chosen:
            at = names.index(self.chosen)
            self.items.selection_clear(0, "end")
            self.items.selection_set(at)
        self.show_chosen()

    def pick(self):
        chosen = self.items.curselection()
        if chosen:
            self.chosen = self.scenes[chosen[0]].name
            self.show_chosen()
            self.detail.to_top()

    def go_to(self, name):
        for piece in self.code.scenes():
            if name in (piece.name, self.main.scene_names.get(piece.name)):
                self.chosen = piece.name
        self.fill_list()

    def show_chosen(self):
        inner = self.detail.inner
        for child in inner.winfo_children():
            child.destroy()
        body = tk.Frame(inner, padx=px(self, 14), pady=px(self, 10))
        body.pack(fill="both", expand=True)
        main = self.main
        piece = main.first("scene", self.chosen) if main is not None and self.chosen else None
        if piece is None:
            tk.Label(body, text="No scenes yet: make one with New scene.", fg=MUTED).pack(anchor="w")
            return
        tk.Label(body, text="The scene %s" % main.scene_names.get(piece.name, piece.name), font=("", 15, "bold")).pack(anchor="w")
        tk.Label(body, text="%s = game.scene(...) in game/main.py, line %d" % (piece.name, main.lines.line_number(piece.start)),
                 fg=MUTED).pack(anchor="w")
        CallForm(body, self, main, piece.call.path, SCENE_FIELDS, ["name"], section="scenes").pack(anchor="w", fill="x", pady=(px(self, 6), 0))
        kind = piece.call.get("kind")
        self.heading(body, "Camera", "What the screen shows of the scene.")
        CameraForm(body, self, main, piece.call.path, kind.value if kind is not None and kind.kind == "literal" else "2d").pack(anchor="w", fill="x")
        self.heading(body, "Rules", "When something becomes true, these actions run: win, lose, go to another scene...")
        RulesEditor(body, self, main, piece.call.path).pack(anchor="w", fill="x")
        self.heading(body, "In the scene", "Objects, texts on the screen and levels, in the order they are added.")
        for n, add in enumerate(main.find("add", piece.name)):
            self.thing(body, add)
        self.add_menu(body, piece)

    def heading(self, body, title, words):
        line(body)
        tk.Label(body, text=title, font=("", 12, "bold")).pack(anchor="w")
        tk.Label(body, text=words, fg=MUTED).pack(anchor="w", pady=(0, px(self, 4)))

    def thing(self, body, add):
        main = self.main
        card = tk.Frame(body, bg=PANEL, highlightthickness=1, highlightbackground=LINE, padx=px(self, 10), pady=px(self, 6))
        card.pack(fill="x", pady=(px(self, 6), 0))
        head = tk.Frame(card, bg=PANEL)
        head.pack(fill="x")
        first = add.call.get(0)
        if add.entity is not None:
            name = add.entity.get(0)
            kinds = ", ".join(v.func for v in add.entity.args[1:] if isinstance(v, Call))
            tk.Label(head, text=name.value if name is not None and name.kind == "literal" else "Entity", font=("", 11, "bold"), bg=PANEL).pack(side="left")
            tk.Label(head, text=kinds, fg=MUTED, bg=PANEL).pack(side="left", padx=px(self, 8))
        elif isinstance(first, Call):
            tk.Label(head, text=first.func, font=("", 11, "bold"), bg=PANEL).pack(side="left")
            tk.Label(head, text="object", fg=MUTED, bg=PANEL).pack(side="left", padx=px(self, 8))
        else:
            tk.Label(head, text=add.text, font=CODE_FONT, bg=PANEL).pack(side="left")
        remove = tk.Label(head, text="remove", fg=MUTED, bg=PANEL, cursor="hand2")
        remove.pack(side="right")
        remove.bind("<Button-1>", lambda e: self.remove_thing(add))
        if add.entity is not None:
            opened = add.key in self.open_things
            toggle = tk.Label(head, text="close" if opened else "change", fg=MUTED, bg=PANEL, cursor="hand2")
            toggle.pack(side="right", padx=px(self, 10))
            toggle.bind("<Button-1>", lambda e: self.toggle(add.key))
        elif isinstance(first, Call):
            CallForm(card, self, main, add.call.path, {"entity": {"type": "entity", "doc": "the object, and what this one changes"}},
                     ["entity"], section="scenes").pack(anchor="w", fill="x")
        CallForm(card, self, main, add.call.path, ADD_FIELDS, ["entity"], section="scenes").pack(anchor="w", fill="x")
        if add.entity is not None and add.key in self.open_things:
            EntityEditor(card, self, main, add.entity.path, section="scenes").pack(fill="x", pady=(px(self, 6), 0))

    def toggle(self, key):
        self.open_things ^= {key}
        self.redraw()

    def add_menu(self, body, scene):
        bar = tk.Frame(body)
        bar.pack(anchor="w", pady=(px(self, 8), 0))
        button = tk.Menubutton(bar, text="Add to the scene  ▾", relief="flat", bg="#e9ebef", padx=px(self, 8),
                               pady=px(self, 3), cursor="hand2")
        button.pack(side="left")
        menu = tk.Menu(button, tearoff=False)
        objects = tk.Menu(menu, tearoff=False)
        for _, p in self.code.prefabs():
            objects.add_command(label=p.name, command=lambda n=p.name: self.add_thing(scene, "%s()" % n))
        menu.add_cascade(label="An object", menu=objects)
        menu.add_command(label="A text on the screen", command=lambda: self.add_thing(
            scene, 'Entity("label", Text("%s", size=16))' % self.text_sample(), ui=True))
        menu.add_command(label="A shape", command=lambda: self.add_thing(
            scene, 'Entity("block", Shape(size=(32, 32), color="#5cd6ff"))'))
        menu.add_command(label="A level made in Tiled (.tmj)", command=lambda: self.add_level(scene))
        button.configure(menu=menu)
        self.note = tk.Label(bar, text="", fg=BAD)
        self.note.pack(side="left", padx=px(self, 8))

    def text_sample(self):
        names = self.code.variables()
        return "%s {%s}" % (names[0].capitalize(), names[0]) if names else "Hello"

    def add_thing(self, scene, what, ui=False):
        w, h = self.code.game_size()
        at = (16, 32) if ui else (w // 2, h // 2)
        text = "%s.add(%s, at=(%d, %d)%s)" % (scene.name, what, at[0], at[1], ", ui=True" if ui else "")
        adds = self.main.find("add", scene.name)
        self.main.add_statement(text, after=adds[-1] if adds else scene, blank_lines=0 if adds else 1)
        self.touched("scenes")
        self.redraw()

    def add_level(self, scene):
        main = self.main
        names = self.code.asset_names(main, "tilemap")
        if not names:
            free = self.code.free_files(main, "tilemap")
            if not free:
                self.note.config(text="There is no level yet: make one in Tiled and save it in levels/ as .tmj.")
                return
            names = [self.code.declare(main, free[0], "tilemap")]
        adds = main.find("add", scene.name)
        text = '%s.add(Entity("map", Tilemap(%s, solid=["ground"])))' % (scene.name, names[0])
        main.add_statement(text, after=adds[-1] if adds else scene, blank_lines=0 if adds else 1)
        self.touched("scenes")
        self.redraw()

    def remove_thing(self, add):
        self.main.remove_piece(add)
        self.open_things.discard(add.key)
        self.touched("scenes")
        self.redraw()

    def new(self):
        main = self.main
        if main is None or main.first("game") is None:
            return
        name = simpledialog.askstring("New scene", "What is the scene called? (level2, shop, boss...)", parent=self)
        if not name:
            return
        word = slug(name)
        if word in main.scene_names.values():
            messagebox.showinfo("That name is taken", "There is already a scene called %s." % word, parent=self)
            return
        taken = {p.name for p in main.pieces if p.name}
        var = word if word not in taken else word + "_scene"
        game = main.first("game").name
        start = "" if self.code.scenes() else ", start=True"
        text = "%s = %s.scene(%s%s)" % (var, game, literal(word), start)
        anchor = (main.find("add") or main.find("scene") or main.find("prefab") or main.find("asset") or main.find("game"))
        main.add_statement(text, after=anchor[-1], blank_lines=2 if anchor[-1].kind == "prefab" else 1)
        self.touched("scenes")
        self.chosen = var
        self.fill_list()

    def delete(self):
        main = self.main
        piece = main.first("scene", self.chosen) if main is not None and self.chosen else None
        if piece is None:
            return
        adds = main.find("add", piece.name)
        if not messagebox.askyesno("Delete", "Delete the scene %s and the %d thing%s in it?" % (
                main.scene_names.get(piece.name, piece.name), len(adds), "" if len(adds) == 1 else "s"), parent=self):
            return
        for add in reversed(adds):
            main.remove_piece(add)
        main.remove_piece(main.first("scene", piece.name))
        self.touched("scenes")
        self.chosen = None
        self.fill_list()

    def refresh(self):
        self.fill_list()

    def reload(self):
        self.fill_list()

    def do_undo(self):
        if self.code.undo():
            self.shell.content_changed()
            self.fill_list()

    def do_redo(self):
        if self.code.redo():
            self.shell.content_changed()
            self.fill_list()
