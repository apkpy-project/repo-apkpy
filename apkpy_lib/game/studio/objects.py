"""Objects: the game's @prefab functions, each an Entity made of components. A component is a card with its fields;
components and the game's own Scripts (behaviours) are added from a menu and taken away with a click.

Everything is written into the game's Python as the examples write it; an object written as code (not one
return Entity(...)) shows as the code it is.
"""
import os
import tkinter as tk
from tkinter import messagebox, simpledialog

from PIL import Image, ImageDraw, ImageTk

from .code import ENTITY_FIELDS, GROUPS, SCRIPT_TYPES, component_spec, doc_of, slug
from .fields import CODE_FONT, CallForm, line
from .source import Call, prefab_text
from .ui import BAD, LINE, MUTED, PANEL, Scrolling, px

PREVIEW = 96
NAME_FIELD = {"name": {"type": "string", "required": True, "doc": "the entity's name: scene.find(\"name\"), a camera's follow"}}


def script_fields(piece):
    """A Script's typed fields as the fields of a component form."""
    out = {}
    for f in piece.fields:
        spec = {"type": SCRIPT_TYPES.get(f.annotation, "code")}
        if f.default is not None:
            spec["shown_default"] = f.default.text
        else:
            spec["required"] = True
        out[f.name] = spec
    return out


class EntityEditor(tk.Frame):
    """One Entity(...) call: its name, its tags, and a card for each component."""

    def __init__(self, parent, screen, source, path, names=(), section="objects"):
        tk.Frame.__init__(self, parent, bg=parent.cget("bg"))
        self.screen, self.code = screen, screen.code
        self.source, self.path, self.names, self.section = source, path, list(names), section
        entity = source.at(path)
        bg = self.cget("bg")
        CallForm(self, screen, source, path, dict(NAME_FIELD, **ENTITY_FIELDS), ["name"], names=names,
                 section=section).pack(anchor="w", fill="x")
        scripts = self.code.scripts()
        for n, value in enumerate(entity.args):
            if n == 0:
                continue
            self.card(value, scripts)
        bar = tk.Frame(self, bg=bg)
        bar.pack(anchor="w", pady=(px(self, 8), 0))
        menu_button = tk.Menubutton(bar, text="Add a component  ▾", relief="flat", bg="#e9ebef", padx=px(self, 8),
                                    pady=px(self, 3), cursor="hand2")
        menu_button.pack(side="left")
        menu = tk.Menu(menu_button, tearoff=False)
        for group, names_in in GROUPS:
            sub = tk.Menu(menu, tearoff=False)
            for name in names_in:
                sub.add_command(label=name, command=lambda c=name: self.add(c))
            menu.add_cascade(label=group, menu=sub)
        if scripts:
            sub = tk.Menu(menu, tearoff=False)
            for name in sorted(scripts):
                sub.add_command(label=name, command=lambda c=name: self.add(c))
            menu.add_cascade(label="Your behaviours (Script)", menu=sub)
        menu_button.configure(menu=menu)
        self.note = tk.Label(bar, text="", fg=BAD, bg=bg)
        self.note.pack(side="left", padx=px(self, 8))

    def card(self, value, scripts):
        card = tk.Frame(self, bg=PANEL, highlightthickness=1, highlightbackground=LINE, padx=px(self, 10), pady=px(self, 6))
        card.pack(fill="x", pady=(px(self, 8), 0))
        head = tk.Frame(card, bg=PANEL)
        head.pack(fill="x")
        name = value.func if isinstance(value, Call) else ""
        spec = component_spec(name) if name else None
        script = scripts.get(name) if name else None
        tk.Label(head, text=name or "code", font=("", 11, "bold"), bg=PANEL).pack(side="left")
        if script is not None:
            tk.Label(head, text="your behaviour", fg=MUTED, bg=PANEL).pack(side="left", padx=px(self, 8))
        remove = tk.Label(head, text="remove", fg=MUTED, bg=PANEL, cursor="hand2")
        remove.pack(side="right")
        remove.bind("<Button-1>", lambda e, v=value: self.remove(v))
        doc = doc_of(name) if spec else (script[1].doc or "" if script else "")
        if doc:
            tk.Label(card, text=doc, fg=MUTED, bg=PANEL, anchor="w", justify="left",
                     wraplength=px(self, 560)).pack(anchor="w", fill="x")
        if spec is not None:
            CallForm(card, self.screen, self.source, value.path, spec["fields"], spec["args"], names=self.names,
                     section=self.section, fold=True).pack(anchor="w", fill="x", pady=(px(self, 4), 0))
        elif script is not None:
            CallForm(card, self.screen, self.source, value.path, script_fields(script[1]), [], names=self.names,
                     section=self.section).pack(anchor="w", fill="x", pady=(px(self, 4), 0))
        else:
            tk.Label(card, text=value.text, font=CODE_FONT, bg=PANEL, anchor="w", justify="left").pack(anchor="w")
            tk.Label(card, text="This is code: change it in a text editor.", fg=MUTED, bg=PANEL).pack(anchor="w")

    def add(self, name):
        text, why = self.code.new_component(self.source, name)
        if text is None:
            self.note.config(text=why)
            return
        self.source.insert(self.source.at(self.path), text)
        self.screen.touched(self.section)
        self.screen.redraw()

    def remove(self, value):
        self.source.remove_arg(self.source.at(self.path), value.path[-1])
        self.screen.touched(self.section)
        self.screen.redraw()


class ObjectsScreen(tk.Frame):
    """The list of objects on the left, the chosen one on the right."""

    section = "objects"

    def __init__(self, parent, shell):
        tk.Frame.__init__(self, parent)
        self.shell, self.code = shell, shell.code
        self.chosen = None
        self.expanded = set()            # the components showing all their settings
        left = tk.Frame(self, padx=px(self, 10), pady=px(self, 10))
        left.pack(side="left", fill="y")
        tk.Label(left, text="Objects", font=("", 15, "bold")).pack(anchor="w")
        tk.Label(left, text="Each one is a @prefab in your code.", fg=MUTED).pack(anchor="w", pady=(0, px(self, 6)))
        self.items = tk.Listbox(left, activestyle="none", exportselection=False, width=24, height=24)
        self.items.pack(fill="y", expand=True)
        self.items.bind("<<ListboxSelect>>", lambda e: self.pick())
        tk.Button(left, text="New object...", command=self.new).pack(fill="x", pady=(px(self, 6), 0))
        tk.Button(left, text="Delete", command=self.delete).pack(fill="x", pady=(px(self, 4), 0))
        tk.Frame(self, bg=LINE, width=1).pack(side="left", fill="y")
        self.detail = Scrolling(self)
        self.detail.pack(side="left", fill="both", expand=True)
        self.fill_list()

    # ── what fields call ──

    def touched(self, section):
        self.code.touch(section or self.section)
        self.shell.content_changed()

    def redraw(self):
        self.after_idle(self.show_chosen)

    # ── the list ──

    def fill_list(self):
        self.objects = self.code.prefabs()
        self.items.delete(0, "end")
        for source, piece in self.objects:
            where = "" if source.rel == "game/main.py" else "   (%s)" % source.rel[len("game/"):]
            self.items.insert("end", piece.name + where)
        names = [p.name for _, p in self.objects]
        if self.chosen not in names:
            self.chosen = names[0] if names else None
        if self.chosen:
            at = names.index(self.chosen)
            self.items.selection_clear(0, "end")
            self.items.selection_set(at)
            self.items.see(at)
        self.show_chosen()

    def pick(self):
        chosen = self.items.curselection()
        if chosen:
            self.chosen = self.objects[chosen[0]][1].name
            self.show_chosen()
            self.detail.to_top()

    def go_to(self, name):
        self.chosen = name
        self.fill_list()

    def show_chosen(self):
        inner = self.detail.inner
        for child in inner.winfo_children():
            child.destroy()
        body = tk.Frame(inner, padx=px(self, 14), pady=px(self, 10))
        body.pack(fill="both", expand=True)
        source, piece = self.code.prefab(self.chosen) if self.chosen else (None, None)
        if piece is None:
            tk.Label(body, text="No objects yet: make one with New object.", fg=MUTED).pack(anchor="w")
            return
        top = tk.Frame(body)
        top.pack(fill="x")
        words = tk.Frame(top)
        words.pack(side="left", fill="x", expand=True, anchor="n")
        tk.Label(words, text=piece.name, font=("", 15, "bold")).pack(anchor="w")
        tk.Label(words, text="%s() in %s, line %d" % (piece.name, source.rel, source.lines.line_number(piece.start)),
                 fg=MUTED).pack(anchor="w")
        if piece.doc:
            tk.Label(words, text=piece.doc, fg=MUTED, justify="left", wraplength=px(self, 460)).pack(anchor="w")
        if piece.params:
            given = ", ".join(f.name + ("=" + f.default.text if f.default is not None else "") for f in piece.params)
            tk.Label(words, text="Each use can change: %s" % given, fg=MUTED, justify="left",
                     wraplength=px(self, 460)).pack(anchor="w", pady=(px(self, 4), 0))
        self.preview = tk.Label(top, bg="#e9ebef")
        self.preview.pack(side="right", anchor="n")
        self.draw_preview(source, piece)
        line(body)
        if piece.entity is None:
            tk.Label(body, text="This object is written as code, so the Studio shows it as it is:", fg=MUTED).pack(anchor="w")
            tk.Label(body, text=piece.text, font=CODE_FONT, justify="left", anchor="w").pack(anchor="w")
            return
        EntityEditor(body, self, source, piece.entity.path, names=[f.name for f in piece.params]).pack(fill="x")

    def draw_preview(self, source, piece):
        size = px(self, PREVIEW)
        picture = Image.new("RGBA", (PREVIEW, PREVIEW), (233, 235, 239, 255))
        try:
            picture = object_picture(self.code, source, piece.entity, PREVIEW, piece.params) or picture
        except (OSError, ValueError):
            pass
        self.preview_photo = ImageTk.PhotoImage(picture.resize((size, size), Image.NEAREST))
        self.preview.configure(image=self.preview_photo)

    # ── new, delete ──

    def new(self):
        main = self.code.main
        if main is None:
            return
        name = simpledialog.askstring("New object", "What is it called? (a coin, a rock, an enemy...)", parent=self)
        if not name:
            return
        word = slug(name)
        taken = {p.name for s in self.code.files() for p in s.pieces if p.name}
        if word in taken:
            messagebox.showinfo("That name is taken", "There is already something called %s in the code." % word, parent=self)
            return
        images = self.code.asset_names(main, "image")
        look = "Sprite(%s)" % images[0] if images else 'Shape(size=(16, 16), color="#ffd45c")'
        text = prefab_text(word, word, [look, "Collider(size=(16, 16))"], tags=[word])
        anchor = (main.find("prefab") or main.find("script") or main.find("function") or main.find("asset")
                  or main.find("constant") or main.find("game") or main.find("import"))
        main.add_statement(text, after=anchor[-1] if anchor else None)
        self.code.touch(self.section)
        self.chosen = word
        self.shell.content_changed()
        self.fill_list()

    def delete(self):
        source, piece = self.code.prefab(self.chosen) if self.chosen else (None, None)
        if piece is None:
            return
        uses = self.uses(piece.name)
        if uses:
            messagebox.showinfo("It is used", "%s() is used in %s. Take it out there first." % (piece.name, ", ".join(uses)), parent=self)
            return
        if not messagebox.askyesno("Delete", "Delete the object %s?" % piece.name, parent=self):
            return
        source.remove_piece(piece)
        self.code.touch(self.section)
        self.chosen = None
        self.shell.content_changed()
        self.fill_list()

    def uses(self, name):
        import re
        out = []
        pattern = re.compile(r"\b%s\s*\(" % re.escape(name))
        for source in self.code.files():
            own = source.first("prefab", name)
            for m in pattern.finditer(source.text):
                if own is not None and own.start <= m.start() < own.end:
                    continue
                out.append("%s line %d" % (source.rel, source.lines.line_number(m.start())))
        return out

    # ── the Shell ──

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


GREY = (233, 235, 239, 255)


def object_picture(code, source, entity, side, params=(), call=None, background=GREY):
    """A small picture of an Entity(...): its Sprite or Billboard (the first frame of a sheet), its Shape, or its
    Text. A @prefab's parameter (Sprite(image)) is what the call gives it (villager(miller_sheet)), else its default
    (image=rock1). None when there is nothing to draw."""
    if entity is None:
        return None
    defaults = {f.name: f.default for f in params if f.default is not None}
    if call is not None:
        for n, f in enumerate(params):
            given = call.get(n) if call.get(n) is not None else call.get(f.name)
            if given is not None:
                defaults[f.name] = given
    for value in entity.args[1:]:
        if not isinstance(value, Call):
            continue
        if value.func in ("Sprite", "Billboard", "Plane", "Block"):
            image = value.get("top") if value.func == "Block" else value.get(0) or value.get("image")
            if image is not None and image.kind == "name" and image.name in defaults:
                image = defaults[image.name]
            if image is None or image.kind != "name":
                continue
            kind, path = code.asset_path(source, image.name)
            if not path:
                continue
            with Image.open(os.path.join(code.root, *path.split("/"))) as img:
                img = img.convert("RGBA")
                frame = code.sheet_frame(source, image.name)
                if frame:
                    img = img.crop((0, 0, frame[0], frame[1]))
                return fit(img, side, background)
        if value.func == "Shape":
            return shape_picture(value, side, background)
        if value.func == "Text":
            text = value.get(0)
            if text is not None and text.kind == "literal":
                pic = Image.new("RGBA", (side, side), (40, 44, 52, 255))
                ImageDraw.Draw(pic).text((6, side // 2 - 6), str(text.value)[:14], fill=(255, 255, 255, 255))
                return pic
    return None


def fit(img, side, background=GREY):
    w, h = img.size
    scale = max(1, min(side // max(w, 1), side // max(h, 1)))
    big = img.resize((w * scale, h * scale), Image.NEAREST) if scale > 1 else img.copy()
    big.thumbnail((side, side))
    out = Image.new("RGBA", (side, side), background or (0, 0, 0, 0))
    out.alpha_composite(big, ((side - big.width) // 2, (side - big.height) // 2))
    return out


def shape_picture(value, side, background=GREY):
    def got(key, default):
        v = value.get(key)
        return v.value if v is not None and v.kind == "literal" else default

    color = got("color", "#ffffff")
    rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) if len(color) >= 7 else (255, 255, 255)
    pic = Image.new("RGBA", (side, side), background or (0, 0, 0, 0))
    draw = ImageDraw.Draw(pic)
    if got("shape", "rect") == "circle":
        r = min(float(got("radius", 5)), side / 2 - 4)
        scale = (side / 2 - 4) / r if r else 1
        r = r * min(scale, 4)
        draw.ellipse((side / 2 - r, side / 2 - r, side / 2 + r, side / 2 + r), fill=rgb)
    else:
        w, h = got("size", (10, 10))
        scale = min((side - 8) / max(w, 1), (side - 8) / max(h, 1), 4)
        w, h = w * scale, h * scale
        draw.rectangle((side / 2 - w / 2, side / 2 - h / 2, side / 2 + w / 2, side / 2 + h / 2), fill=rgb)
    return pic
