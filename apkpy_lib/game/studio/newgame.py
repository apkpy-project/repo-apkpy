"""A new game: choose what kind, give it a name, and it is made where you say, as `apkpy start NAME --game KIND`
makes it. The Studio opens with this when the folder it is started in has no project, and from "New game..." in its
side bar.
"""
import os
import re
import tkinter as tk
from tkinter import filedialog

from ..errors import GameError
from .ui import ACCENT, BAD, LINE, MUTED, PANEL, Scrolling, px

PICTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pictures")
# (the template, what the card says, what you get)
KINDS = (
    ("platformer", "Platformer", "Run, jump, coins, slimes and a flag. Two levels."),
    ("shooter", "Shooter", "A ship that fires, rocks that fall, a second wave."),
    ("runner", "Endless runner", "It never stops: hop the crates, jump for the coins."),
    ("bricks", "Brick breaker", "A paddle, a ball and two levels of bricks."),
    ("adventure", "Adventure", "Rooms from above: keys, doors, chests, stairs."),
    ("tap", "Tap game", "Tap what pops up before it goes. Not the bombs."),
    ("puzzle", "Grid puzzle", "A board and its rules, in a small script."),
    ("world", "2.5D world", "A valley to walk: houses, trees, lanterns to find."),
    ("monster-rpg", "Monster RPG", "A whole RPG to change: maps, story, monsters."),
    ("blank", "Empty", "One scene and a star. Start from nothing."),
)
NAME = re.compile(r"^[^\"\\{}\r\n]{1,40}$")


def folder_name(name):
    """A folder for a game's name: its letters and numbers, in small letters, with _ between the words."""
    words = re.findall(r"[a-z0-9]+", name.lower())
    return "_".join(words) or "my_game"


def app_id_of(name):
    from ..templates import slug
    return "com.example." + slug(name)


class NewGame(tk.Frame):
    """done(folder) is called with the new project's folder."""

    def __init__(self, parent, where, done, cancel=None):
        tk.Frame.__init__(self, parent)
        self.where, self.done = os.path.abspath(where), done
        self.kind = KINDS[0][0]
        self.cards, self.images = {}, {}
        self.own_id = False                 # the id follows the name until it is typed
        pad = px(self, 18)
        tk.Label(self, text="A new game", font=("", 17, "bold"), anchor="w").pack(fill="x", padx=pad, pady=(pad, 0))
        tk.Label(self, text="Choose the kind to start from. It is a whole short game, and everything in it can be changed.",
                 fg=MUTED, anchor="w").pack(fill="x", padx=pad, pady=(0, px(self, 8)))

        form = tk.Frame(self)
        form.pack(side="bottom", fill="x", padx=pad, pady=(px(self, 6), pad))
        self.build_form(form, cancel)
        tk.Frame(self, bg=LINE, height=1).pack(side="bottom", fill="x")

        scroll = Scrolling(self)
        scroll.pack(fill="both", expand=True, padx=(pad - px(self, 6), 0))
        self.grid_of_cards(scroll.inner)
        self.choose(self.kind)

    # ── the kinds ──

    def picture(self, kind):
        """The kind's picture, at this screen's size, or None (the card draws a plain one)."""
        path = os.path.join(PICTURES, kind.replace("-", "_") + ".png")
        if not os.path.isfile(path):
            return None
        try:
            image = tk.PhotoImage(master=self, file=path)
        except tk.TclError:
            return None
        if px(self, 160) < 280:
            image = image.subsample(2)      # the files are twice the size, for screens at 200%
        self.images[kind] = image
        return image

    def grid_of_cards(self, parent):
        columns = 5
        for i, (kind, title, what) in enumerate(KINDS):
            card = tk.Frame(parent, bg=PANEL, highlightthickness=2, highlightbackground=LINE, cursor="hand2")
            card.grid(row=i // columns, column=i % columns, padx=px(self, 6), pady=px(self, 6), sticky="n")
            image = self.picture(kind)
            if image is not None:
                top = tk.Label(card, image=image, bd=0, bg=PANEL)
            else:
                big = px(self, 160) >= 280
                top = tk.Canvas(card, width=320 if big else 160, height=240 if big else 120, bg="#1b1f2e",
                                highlightthickness=0)
                mid_x, mid_y, arm = (160, 120, 26) if big else (80, 60, 13)
                top.create_line(mid_x - arm, mid_y, mid_x + arm, mid_y, fill="#8d96b3", width=3)
                top.create_line(mid_x, mid_y - arm, mid_x, mid_y + arm, fill="#8d96b3", width=3)
            top.pack()
            name = tk.Label(card, text=title, bg=PANEL, font=("", 10, "bold"), anchor="w")
            name.pack(fill="x", padx=px(self, 8), pady=(px(self, 6), 0))
            text = tk.Label(card, text=what, bg=PANEL, fg=MUTED, anchor="nw", justify="left", height=2,
                            wraplength=(320 if px(self, 160) >= 280 else 160) - px(self, 14), font=("", 9))
            text.pack(fill="x", padx=px(self, 8), pady=(0, px(self, 8)))
            for widget in (card, top, name, text):
                widget.bind("<Button-1>", lambda e, k=kind: self.choose(k))
                widget.bind("<Double-Button-1>", lambda e, k=kind: (self.choose(k), self.create()))
            self.cards[kind] = card

    def choose(self, kind):
        self.kind = kind
        for k, card in self.cards.items():
            card.configure(highlightbackground=ACCENT if k == kind else LINE, highlightcolor=ACCENT if k == kind else LINE)

    # ── its name and where ──

    def build_form(self, form, cancel):
        form.columnconfigure(1, weight=1)
        tk.Label(form, text="Its name", anchor="w").grid(row=0, column=0, sticky="w", pady=px(self, 3))
        self.name = tk.StringVar(value="My game")
        entry = tk.Entry(form, textvariable=self.name, width=30)
        entry.grid(row=0, column=1, sticky="w", padx=px(self, 8))
        entry.select_range(0, "end")
        entry.focus_set()
        entry.bind("<Return>", lambda e: self.create())
        tk.Label(form, text="Its id", anchor="w").grid(row=1, column=0, sticky="w", pady=px(self, 3))
        self.app_id = tk.StringVar(value=app_id_of("My game"))
        identity = tk.Entry(form, textvariable=self.app_id, width=30)
        identity.grid(row=1, column=1, sticky="w", padx=px(self, 8))
        identity.bind("<Key>", lambda e: setattr(self, "own_id", True))
        tk.Label(form, text="for the phone and the store: your name in place of example", fg=MUTED,
                 anchor="w").grid(row=1, column=2, sticky="w")
        tk.Label(form, text="Made in", anchor="w").grid(row=2, column=0, sticky="w", pady=px(self, 3))
        self.place = tk.Label(form, text="", anchor="w", fg=MUTED)
        self.place.grid(row=2, column=1, columnspan=2, sticky="w", padx=px(self, 8))
        buttons = tk.Frame(form)
        buttons.grid(row=0, column=3, rowspan=3, sticky="e")
        tk.Button(buttons, text="Create the game", command=self.create, bg=ACCENT, fg="#ffffff",
                  activebackground=ACCENT, activeforeground="#ffffff", padx=px(self, 14), pady=px(self, 5)).pack(fill="x")
        tk.Button(buttons, text="Another folder...", command=self.another_folder).pack(fill="x", pady=(px(self, 6), 0))
        if cancel is not None:
            tk.Button(buttons, text="Cancel", command=cancel).pack(fill="x", pady=(px(self, 6), 0))
        self.problem = tk.Label(form, text="", fg=BAD, anchor="w", justify="left", wraplength=px(self, 700))
        self.problem.grid(row=3, column=0, columnspan=4, sticky="w")
        self.name.trace_add("write", lambda *a: self.name_changed())
        self.name_changed()

    def name_changed(self):
        if not self.own_id:
            self.app_id.set(app_id_of(self.name.get()))
        where = self.target()
        self.place.config(text=where if len(where) < 80 else where[:30] + " ... " + where[-45:])
        self.problem.config(text="")

    def target(self):
        return os.path.join(self.where, folder_name(self.name.get()))

    def another_folder(self):
        chosen = filedialog.askdirectory(parent=self, initialdir=self.where, title="The folder to make the game's folder in")
        if chosen:
            self.where = os.path.abspath(chosen)
            self.name_changed()

    def create(self):
        from .. import cli
        name, app_id = self.name.get().strip(), self.app_id.get().strip()
        if not NAME.match(name):
            return self.say("A name of 1 to 40 letters, with no quotes, backslashes or braces.")
        if not re.match(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$", app_id):
            return self.say("The id is small letters and numbers in parts with dots between, as com.yourname.%s."
                            % folder_name(name).replace("_", ""))
        folder = self.target()
        if os.path.exists(folder):
            return self.say("%s is there already: another name, or another folder." % folder)
        self.say("Making it...", MUTED)
        self.update_idletasks()
        try:
            cli.new(folder, self.kind, app_id, say=lambda *a: None, title=name)
        except GameError as e:
            return self.say(str(e))
        except OSError as e:
            return self.say("It could not be made there: %s" % e)
        self.done(folder)

    def say(self, text, colour=BAD):
        self.problem.config(text=text, fg=colour)
