"""The fields of a component, an action, Game(...) or a scene, as widgets that write Python.

A field shows the value written in the code, or its default in grey when there is none. Changing it rewrites that one
argument (Source.set_arg); emptying it takes the argument away, back to the default. A value the form cannot show as a
widget (a name, a sum, t("key")) shows as the Python it is, and is changed as Python.
"""
import re
import tkinter as tk
from tkinter import colorchooser, ttk

from .code import ASSET_KINDS, CONDITION, action_names, action_spec
from .source import Call, Sequence, bind, check_expression, literal
from .ui import BAD, LINE, MUTED, PANEL, TEXT, px

WORD_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
COLOR = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
NUMBER = re.compile(r"^-?(\d+\.?\d*|\.\d+)$")
WHOLE = re.compile(r"^-?\d+$")
CODE_FONT = ("Consolas", 10)


def readable(name):
    return name.replace("_", " ").capitalize()


def default_text(spec):
    if "shown_default" in spec:
        return spec["shown_default"]
    if "default" not in spec:
        return ""
    value = spec["default"]
    if spec["type"] in ("pair", "box", "rect") and isinstance(value, list):
        value = tuple(value)
    if spec["type"] in ("string", "text", "enum", "color") and isinstance(value, str):
        return value or '""'
    if spec["type"] == "bool":
        return "yes" if value else "no"
    return literal(value)


class CallForm(tk.Frame):
    """The fields of one call at path in source: fields is {name: spec} (components.json's), args the positional
    ones in order. on_structure is called when something is added or removed (the screen draws itself again)."""

    def __init__(self, parent, editor, source, path, fields, args=(), names=(), skip=(), compact=False,
                 on_structure=None, section="", fold=False):
        tk.Frame.__init__(self, parent, bg=parent.cget("bg"))
        self.editor, self.code = editor, editor.code
        self.source, self.path, self.fields, self.args = source, path, fields, list(args)
        self.names = list(names)                 # names that can be values here too (a @prefab's parameters)
        self.compact, self.section = compact, section
        self.on_structure = on_structure or editor.redraw
        self.bg = parent.cget("bg")
        self.columnconfigure(1, weight=1)
        at = 0
        expanded = getattr(editor, "expanded", set())
        hidden = []
        if fold:
            hidden = [n for n, spec in fields.items() if n not in skip and not spec.get("required")
                      and self.key_of(n) is None]
        shown_all = fold and path in expanded
        for name, spec in fields.items():
            if name in skip or (name in hidden and not shown_all):
                continue
            if compact:
                cell = tk.Frame(self, bg=self.bg)
                cell.grid(row=0, column=at, sticky="w", padx=(0, px(self, 8)))
                tk.Label(cell, text=name.replace("_", " "), fg=MUTED, bg=self.bg).pack(side="left", padx=(0, px(self, 3)))
                holder = tk.Frame(cell, bg=self.bg)
                holder.pack(side="left")
                self.field(holder, name, spec)
                at += 1
                continue
            tk.Label(self, text=readable(name), anchor="nw", bg=self.bg).grid(
                row=at, column=0, sticky="nw", padx=(0, px(self, 10)), pady=(px(self, 5), 0))
            holder = tk.Frame(self, bg=self.bg)
            holder.grid(row=at, column=1, sticky="ew", pady=(px(self, 3), 0))
            self.field(holder, name, spec)
            at += 1
            if spec.get("doc"):
                tk.Label(self, text=spec["doc"], fg=MUTED, bg=self.bg, anchor="w", justify="left",
                         wraplength=px(self, 520)).grid(row=at, column=1, sticky="w")
                at += 1
        if hidden:
            words = "Fewer settings" if shown_all else "All settings (%d more)" % len(hidden)
            more = tk.Label(self, text=words, fg="#2f6fdb", bg=self.bg, cursor="hand2")
            more.grid(row=at, column=0, columnspan=2, sticky="w", pady=(px(self, 4), 0))
            more.bind("<Button-1>", lambda e: self.unfold())

    def unfold(self):
        expanded = self.editor.expanded
        if self.path in expanded:
            expanded.discard(self.path)
        else:
            expanded.add(self.path)
        self.editor.redraw()

    # ── reading and writing ──

    def call(self):
        return self.source.at(self.path)

    def key_of(self, name):
        call = self.call()
        if not isinstance(call, Call):
            return None
        return bind(call, self.args).get(name)

    def current(self, name):
        key = self.key_of(name)
        if key is None or isinstance(key, tuple):
            return None
        return self.call().get(key)

    def commit(self, name, text, spec=None, merge=True):
        """The field becomes text (Python), or None: back to its default."""
        call = self.call()
        key = self.key_of(name)
        if text is None:
            if key is None:
                return
            positional = [i.key for i in call.items if isinstance(i.key, int)]
            if isinstance(key, int) and key != positional[-1]:
                default = (spec or {}).get("default")
                if default is None:
                    return
                self.source.set_arg(call, key, literal(tuple(default) if isinstance(default, list) and spec["type"] in ("pair", "box", "rect") else default))
            else:
                self.source.remove_arg(call, key)
        else:
            self.source.set_arg(call, key if key is not None else name, text, merge=(self.path, name) if merge else None)
        self.editor.touched(self.section)

    # ── the widgets ──

    def field(self, holder, name, spec):
        t = spec["type"]
        value = self.current(name)
        if t == "actions":
            ActionsEditor(holder, self, name, spec).pack(anchor="w", fill="x")
            return
        if t == "animations" and (value is None or value.kind == "literal"):
            AnimationsEditor(holder, self, name, spec, value.value if value is not None else {}).pack(anchor="w", fill="x")
            return
        named = value is not None and value.kind == "name"
        if value is not None and value.kind not in ("literal",) and not (named and t in ASSET_KINDS) \
                and not (t == "entity" and value.kind == "call"):
            return self.code_entry(holder, name, spec, value)
        if t in ("number", "int"):
            return self.number(holder, name, spec, value, whole=(t == "int"))
        if t == "frame" and (value is None or isinstance(value.value, int)):
            return self.number(holder, name, spec, value, whole=True)          # a sheet's frame: its number
        if t == "condition" and (value is None or isinstance(value.value, str)):
            return self.condition(holder, name, spec, value)
        if t == "bool":
            return self.yes_no(holder, name, spec, value)
        if t == "enum":
            return self.enum(holder, name, spec, value)
        if t == "color":
            return self.color(holder, name, spec, value)
        if t == "pair":
            return self.pair(holder, name, spec, value)
        if t in ("string", "text"):
            if value is not None and not isinstance(value.value, str):
                return self.code_entry(holder, name, spec, value)
            return self.words(holder, name, spec, value)
        if t == "strings":
            return self.word_list(holder, name, spec, value)
        if t in ASSET_KINDS:
            return self.asset(holder, name, spec, value)
        if t == "entity":
            return self.entity(holder, name, spec, value)
        return self.code_entry(holder, name, spec, value)

    def hint(self, holder, spec):
        text = default_text(spec)
        if text:
            tk.Label(holder, text="default %s" % text, fg=MUTED, bg=self.bg).pack(side="left", padx=px(self, 6))

    def entry(self, holder, width, text):
        entry = tk.Entry(holder, width=width)
        entry.insert(0, text)
        entry.pack(side="left", ipady=px(self, 1))
        return entry

    def number(self, holder, name, spec, value, whole):
        entry = self.entry(holder, 9, value.text if value is not None else "")
        pattern = WHOLE if whole else NUMBER

        def read(event=None):
            text = entry.get().strip()
            if not text:
                entry.configure(fg=TEXT)
                self.commit(name, None, spec)
            elif pattern.match(text):
                entry.configure(fg=TEXT)
                self.commit(name, text, spec)
            else:
                entry.configure(fg=BAD)

        entry.bind("<KeyRelease>", read)
        entry.typed = read                   # what a key does: tests call it on a hidden window
        if value is None:
            self.hint(holder, spec)
        return entry

    def words(self, holder, name, spec, value):
        entry = self.entry(holder, 14 if self.compact else 32, value.value if value is not None else "")

        def read(event=None):
            text = entry.get()
            if not text and not spec.get("required"):
                self.commit(name, None, spec)
            else:
                self.commit(name, literal(text), spec)

        entry.bind("<KeyRelease>", read)
        entry.typed = read                   # what a key does: tests call it on a hidden window
        if value is None:
            self.hint(holder, spec)
        return entry

    def condition(self, holder, name, spec, value):
        """ "keys >= 1" or "count(coin) == 0": red until it is one."""
        entry = self.entry(holder, 18, value.value if value is not None else "")

        def read(event=None):
            text = entry.get().strip()
            good = CONDITION.match(text) is not None
            entry.configure(fg=TEXT if good else BAD)
            if good:
                self.commit(name, literal(text), spec)

        entry.bind("<KeyRelease>", read)
        entry.typed = read
        return entry

    def word_list(self, holder, name, spec, value):
        shown = ", ".join(value.value) if value is not None and isinstance(value.value, (list, tuple)) else ""
        entry = self.entry(holder, 28, shown)

        def read(event=None):
            words = [w.strip() for w in entry.get().split(",") if w.strip()]
            self.commit(name, literal(words) if words else None, spec)

        entry.bind("<KeyRelease>", read)
        entry.typed = read                   # what a key does: tests call it on a hidden window
        tk.Label(holder, text="separated by commas", fg=MUTED, bg=self.bg).pack(side="left", padx=px(self, 6))
        return entry

    def yes_no(self, holder, name, spec, value):
        on = tk.BooleanVar(value=bool(value.value) if value is not None else bool(spec.get("default", False)))

        def read():
            if on.get() == bool(spec.get("default", False)) and self.key_of(name) is not None \
                    and not isinstance(self.key_of(name), int):
                self.commit(name, None, spec, merge=False)
            else:
                self.commit(name, "True" if on.get() else "False", spec, merge=False)

        box = tk.Checkbutton(holder, variable=on, command=read, bg=self.bg, activebackground=self.bg)
        box.pack(side="left")
        box.variable = on
        return box

    def enum(self, holder, name, spec, value):
        values = [v for v in spec["values"]]
        box = ttk.Combobox(holder, values=values, state="readonly", width=max(8, max(len(v) for v in values) + 2))
        box.set(value.value if value is not None else spec.get("default", ""))
        box.pack(side="left")

        def read(event=None):
            chosen = box.get()
            if chosen == spec.get("default") and not isinstance(self.key_of(name), int):
                self.commit(name, None, spec, merge=False)
            elif chosen == "" and spec.get("default") is None:
                self.commit(name, None, spec, merge=False)
            else:
                self.commit(name, literal(chosen), spec, merge=False)

        box.bind("<<ComboboxSelected>>", read)
        return box

    def color(self, holder, name, spec, value):
        text = value.value if value is not None else ""
        swatch = tk.Label(holder, width=3, relief="solid", borderwidth=1, cursor="hand2",
                          bg=self.shown_color(text or spec.get("default", "#ffffff")))
        swatch.pack(side="left", padx=(0, px(self, 4)))
        entry = self.entry(holder, 10, text)

        def read(event=None):
            t = entry.get().strip()
            if not t:
                entry.configure(fg=TEXT)
                self.commit(name, None, spec)
            elif COLOR.match(t):
                entry.configure(fg=TEXT)
                swatch.configure(bg=self.shown_color(t))
                self.commit(name, literal(t), spec)
            else:
                entry.configure(fg=BAD)

        def pick(event=None):
            chosen = colorchooser.askcolor(color=self.shown_color(entry.get().strip() or spec.get("default", "#ffffff")),
                                           parent=self)
            if chosen and chosen[1]:
                entry.delete(0, "end")
                entry.insert(0, chosen[1])
                read()

        entry.bind("<KeyRelease>", read)
        entry.typed = read                   # what a key does: tests call it on a hidden window
        swatch.bind("<Button-1>", pick)
        if value is None:
            self.hint(holder, spec)
        return entry

    @staticmethod
    def shown_color(text):
        if not COLOR.match(text or ""):
            return PANEL
        h = text[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return "#" + h[:6]

    def pair(self, holder, name, spec, value):
        numbers = value.value if value is not None else None
        if numbers is not None and not (isinstance(numbers, (list, tuple)) and len(numbers) == 2):
            return self.code_entry(holder, name, spec, value)
        a = self.entry(holder, 6, literal(numbers[0]) if numbers else "")
        tk.Label(holder, text=",", bg=self.bg).pack(side="left")
        b = self.entry(holder, 6, literal(numbers[1]) if numbers else "")

        def read(event=None):
            x, y = a.get().strip(), b.get().strip()
            good = True
            for entry, t in ((a, x), (b, y)):
                ok = NUMBER.match(t) is not None
                entry.configure(fg=TEXT if ok or not t else BAD)
                good = good and ok
            if not x and not y:
                self.commit(name, None, spec)
            elif good:
                self.commit(name, "(%s, %s)" % (x, y), spec)

        a.bind("<KeyRelease>", read)
        b.bind("<KeyRelease>", read)
        if value is None:
            self.hint(holder, spec)
        return a

    def asset(self, holder, name, spec, value):
        t = spec["type"]
        names = self.code.asset_names(self.source, t) + [n for n in self.names if n not in ("self",)]
        free = ["+ " + rel for rel in self.code.free_files(self.source, t)]
        current = value.text if value is not None else ""
        box = ttk.Combobox(holder, values=([""] if not spec.get("required") else []) + names + free, state="readonly",
                           width=18 if self.compact else 24)
        box.set(current)
        box.pack(side="left")

        def read(event=None):
            chosen = box.get()
            if chosen.startswith("+ "):
                chosen = self.code.declare(self.source, chosen[2:], t)
                self.commit(name, chosen, spec, merge=False)
                self.on_structure()
                return
            self.commit(name, chosen or None, spec, merge=False)

        box.bind("<<ComboboxSelected>>", read)
        if value is None and not spec.get("required"):
            words = "default %s" % spec["shown_default"] if spec.get("shown_default") else "none"
            tk.Label(holder, text=words, fg=MUTED, bg=self.bg).pack(side="left", padx=px(self, 6))
        return box

    def entity(self, holder, name, spec, value):
        names = ["%s()" % p.name for _, p in self.code.prefabs()]
        box = ttk.Combobox(holder, values=names, width=24)
        box.set(value.text if value is not None else "")
        box.pack(side="left")

        def read(event=None):
            text = box.get().strip()
            try:
                check_expression(text)
            except ValueError:
                box.configure(foreground=BAD)
                return
            box.configure(foreground=TEXT)
            self.commit(name, text, spec, merge=event is None or event.type != tk.EventType.VirtualEvent)

        box.bind("<<ComboboxSelected>>", read)
        box.bind("<KeyRelease>", read)
        return box

    def code_entry(self, holder, name, spec, value):
        """The value as the Python it is: a name, a sum, a dictionary..."""
        entry = tk.Entry(holder, font=CODE_FONT, width=30 if self.compact else 48)
        entry.insert(0, value.text if value is not None else "")
        entry.pack(side="left", ipady=px(self, 1), fill="x", expand=not self.compact)

        def read(event=None):
            text = entry.get().strip()
            if not text:
                entry.configure(fg=TEXT)
                self.commit(name, None, spec)
                return
            try:
                check_expression(text)
            except ValueError:
                entry.configure(fg=BAD)
                return
            entry.configure(fg=TEXT)
            self.commit(name, text, spec)

        entry.bind("<KeyRelease>", read)
        entry.typed = read                   # what a key does: tests call it on a hidden window
        if value is None:
            self.hint(holder, spec)
        return entry


class AnimationsEditor(tk.Frame):
    """Animator({"run": {"frames": [2, 3, 4, 5], "fps": 12}, ...}): a line for each animation, playing beside it
    in the frames of the entity's sheet."""

    def __init__(self, parent, form, name, spec, animations):
        tk.Frame.__init__(self, parent, bg=parent.cget("bg"))
        self.form, self.name, self.spec = form, name, spec
        self.rows = []
        self.frames = self.sheet_frames()
        self.list = tk.Frame(self, bg=self.cget("bg"))
        self.list.pack(anchor="w")
        self.next_row = 1
        for column, text in enumerate(("name", "frames", "per second", "loops")):
            tk.Label(self.list, text=text, fg=MUTED, bg=self.cget("bg"), anchor="w").grid(row=0, column=column, sticky="w")
        for key, anim in animations.items():
            self.row(key, anim)
        bar = tk.Frame(self, bg=self.cget("bg"))
        bar.pack(anchor="w", pady=(px(self, 3), 0))
        tk.Button(bar, text="Add an animation", command=self.add).pack(side="left")
        if self.frames:
            tk.Label(bar, text="frames of the sheet: 0 to %d" % (len(self.frames) - 1), fg=MUTED,
                     bg=self.cget("bg")).pack(side="left", padx=px(self, 8))
        self.note = tk.Label(bar, text="", fg=BAD, bg=self.cget("bg"))
        self.note.pack(side="left", padx=px(self, 8))
        self.tick = 0
        self.after(120, self.play)

    def sheet_frames(self):
        """The pictures of the entity's Sprite sheet, in order: [PIL image]."""
        try:
            from PIL import Image
            import os
            source, code = self.form.source, self.form.code
            entity = source.at(self.form.path[:-1])
            sprite = next((v for v in getattr(entity, "args", [])[1:] if isinstance(v, Call) and v.func == "Sprite"), None)
            image = sprite.get(0) or sprite.get("image") if sprite is not None else None
            if image is None or image.kind != "name":
                return []
            frame = code.sheet_frame(source, image.name)
            kind, path = code.asset_path(source, image.name)
            if not frame or not path:
                return []
            with Image.open(os.path.join(code.root, *path.split("/"))) as img:
                img = img.convert("RGBA")
                w, h = frame
                return [img.crop((x, y, x + w, y + h)) for y in range(0, img.height - h + 1, h)
                        for x in range(0, img.width - w + 1, w)]
        except (OSError, ValueError, AttributeError):
            return []

    def row(self, key, anim):
        bg = self.cget("bg")
        n = self.next_row
        self.next_row += 1
        name = tk.Entry(self.list, width=12)
        name.insert(0, key)
        frames = tk.Entry(self.list, width=18)
        frames.insert(0, ", ".join(str(f) for f in anim.get("frames", [])))
        fps = tk.Entry(self.list, width=7)
        fps.insert(0, literal(anim["fps"]) if "fps" in anim else "")
        loops = tk.BooleanVar(value=anim.get("loop", True))
        box = tk.Checkbutton(self.list, variable=loops, bg=bg, command=self.write)
        shown = tk.Label(self.list, bg="#e9ebef")
        x = tk.Label(self.list, text="remove", fg=MUTED, bg=bg, cursor="hand2")
        widgets = (name, frames, fps, box, shown, x)
        for column, w in enumerate(widgets):
            w.grid(row=n, column=column, sticky="w", padx=(0, px(self, 6)), pady=(px(self, 2), 0))
        entry = {"name": name, "frames": frames, "fps": fps, "loops": loops, "widgets": widgets, "shown": shown}
        self.rows.append(entry)
        x.bind("<Button-1>", lambda e: self.remove(entry))
        for w in (name, frames, fps):
            w.bind("<KeyRelease>", lambda e: self.write())
        return entry

    def add(self):
        taken = {r["name"].get().strip() for r in self.rows}
        key = next(k for k in ("idle", "run", "jump", "fall", "walk", "hit") + tuple("anim%d" % n for n in range(2, 99)) if k not in taken)
        self.row(key, {"frames": [0], "fps": 8})
        self.write()

    def remove(self, entry):
        self.rows.remove(entry)
        for w in entry["widgets"]:
            w.destroy()
        self.write()

    def read(self):
        out = {}
        for r in self.rows:
            key = r["name"].get().strip()
            if not WORD_KEY.match(key) or key in out:
                return None, "A name is one word, and no name twice."
            try:
                frames = [int(f) for f in r["frames"].get().replace(" ", "").split(",") if f]
            except ValueError:
                return None, "Frames are numbers: 0, 1, 2"
            if not frames:
                return None, "Each animation needs a frame."
            if self.frames and max(frames) >= len(self.frames):
                return None, "The sheet has frames 0 to %d." % (len(self.frames) - 1)
            anim = {"frames": frames}
            speed = r["fps"].get().strip()
            if speed:
                if not NUMBER.match(speed):
                    return None, "Per second is a number."
                anim["fps"] = float(speed) if "." in speed else int(speed)
            if not r["loops"].get():
                anim["loop"] = False
            out[key] = anim
        return out, ""

    def write(self):
        value, why = self.read()
        self.note.config(text=why)
        if value is None:
            return
        if not value:
            self.note.config(text="An Animator needs one animation.")
            return
        self.form.commit(self.name, literal(value), self.spec)

    def play(self):
        if not self.winfo_exists():
            return
        self.tick += 1
        for r in self.rows:
            try:
                frames = [int(f) for f in r["frames"].get().replace(" ", "").split(",") if f]
                fps = float(r["fps"].get().strip() or 8)
            except ValueError:
                continue
            if not frames or not self.frames or max(frames) >= len(self.frames) or fps <= 0:
                continue
            step = int(self.tick * 0.06 * fps) % len(frames)
            key = (frames[step], id(r))
            if r.get("at") == key:
                continue
            from PIL import Image, ImageTk
            pic = self.frames[frames[step]]
            side = px(self, 32)
            scale = max(1, side // max(pic.size))
            r["photo"] = ImageTk.PhotoImage(pic.resize((pic.width * scale, pic.height * scale), Image.NEAREST))
            r["shown"].configure(image=r["photo"])
            r["at"] = key
        self.after(60, self.play)


class ActionsEditor(tk.Frame):
    """The actions of OnTap, OnCollide, Timer, a rule or Back: one row each, its fields beside it."""

    def __init__(self, parent, form, name, spec):
        tk.Frame.__init__(self, parent, bg=parent.cget("bg"))
        self.form, self.name, self.spec = form, name, spec
        self.source = form.source
        self.draw()

    def place(self):
        """(mode, value): "rest" (the positional arguments from the *actions on), "list" (name=[...]), "one"
        (name=action()), or "none"."""
        call = self.form.call()
        key = self.form.key_of(self.name)
        if isinstance(key, tuple):
            return "rest", key[0]
        if key is None:
            return "none", None
        value = call.get(key)
        if isinstance(value, Sequence):
            return "list", value
        if isinstance(value, Call):
            return "one", value
        return "code", value

    def action_calls(self):
        mode, where = self.place()
        call = self.form.call()
        if mode == "rest":
            return [v for v in call.args[where:] if isinstance(v, Call)], mode
        if mode == "list":
            return [v for v in where.args], mode
        if mode == "one":
            return [where], mode
        return [], mode

    def draw(self):
        for child in self.winfo_children():
            child.destroy()
        calls, mode = self.action_calls()
        if mode == "code":
            self.form.code_entry(self, self.name, self.spec, self.place()[1])
            return
        bg = self.cget("bg")
        for n, action in enumerate(calls):
            row = tk.Frame(self, bg=bg)
            row.pack(anchor="w", fill="x", pady=(0, px(self, 2)))
            spec = action_spec(action.func) if isinstance(action, Call) else None
            tk.Label(row, text="%s" % action.func, font=("", 9, "bold"), bg=bg, width=10, anchor="w").pack(side="left")
            if spec is None:
                tk.Label(row, text=action.text, font=CODE_FONT, fg=MUTED, bg=bg).pack(side="left")
            else:
                CallForm(row, self.form.editor, self.source, action.path, spec["fields"], spec["args"],
                         names=self.form.names, compact=True, on_structure=self.form.on_structure,
                         section=self.form.section).pack(side="left")
            x = tk.Label(row, text="  remove", fg=MUTED, bg=bg, cursor="hand2")
            x.pack(side="left")
            x.bind("<Button-1>", lambda e, at=n: self.remove(at))
        add = ttk.Combobox(self, values=action_names(), state="readonly", width=16)
        add.set("add an action...")
        add.pack(anchor="w", pady=(px(self, 2), 0))
        add.bind("<<ComboboxSelected>>", lambda e: self.add(add.get()))
        self.note = tk.Label(self, text="", fg=BAD, bg=bg)

    def add(self, action):
        text, why = self.form.code.new_action(self.source, action)
        if text is None:
            self.note.config(text=why)
            self.note.pack(anchor="w")
            return
        mode, where = self.place()
        call = self.form.call()
        if mode == "rest" or (mode == "none" and self.star_index() is not None
                              and len([i for i in call.items if isinstance(i.key, int)]) >= self.star_index()):
            self.source.insert(call, text)
        elif mode == "list":
            self.source.insert(where, text, len(where.items))
        elif mode == "one":
            self.source.set(where, "[%s, %s]" % (where.text, text))
        else:
            self.source.set_arg(call, self.name, text if self.spec["type"] == "actions" and self.single() else "[%s]" % text)
        self.form.editor.touched(self.form.section)
        self.form.on_structure()

    def star_index(self):
        return next((i for i, a in enumerate(self.form.args) if a == "*" + self.name), None)

    def single(self):
        """Back (on_back=) is written as one action when it is one."""
        return self.name == "on_back"

    def remove(self, n):
        mode, where = self.place()
        call = self.form.call()
        if mode == "rest":
            self.source.remove_arg(call, where + n)
        elif mode == "list":
            if len(where.items) == 1:
                self.source.remove_arg(call, self.form.key_of(self.name))
            else:
                self.source.remove_arg(where, n)
        elif mode == "one":
            self.source.remove_arg(call, self.form.key_of(self.name))
        self.form.editor.touched(self.form.section)
        self.form.on_structure()


def line(parent):
    tk.Frame(parent, bg=LINE, height=1).pack(fill="x", pady=px(parent, 6))
