"""Sounds: every sound and piece of music of the game, to listen to, bring in, and make.

"Make a sound" synthesises the usual game sounds (jump, coin, laser, explosion...) and short tunes, here, from
nothing: original WAV files, small, made with numbers. "Another one" makes a different one of the same kind.
"""
import glob
import os
import shutil
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from ..synth import KINDS, MOODS, RATE, make_music, make_sound, write_wav  # noqa: F401 (the Studio's names)
from .code import SOUNDS, slug
from .ui import BAD, GOOD, LINE, MUTED, PANEL, Scrolling, px


def sound_files(root):
    out = []
    for path in sorted(glob.glob(os.path.join(root, "assets", "**", "*"), recursive=True)):
        if path.lower().endswith(SOUNDS) and os.path.isfile(path):
            out.append(os.path.relpath(path, root).replace(os.sep, "/"))
    return out


def play_file(path):
    """Plays a WAV here (Windows); other files open in the computer's player. False when it cannot."""
    try:
        import winsound
        if path.lower().endswith(".wav"):
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return True
        os.startfile(path)
        return True
    except (ImportError, OSError, RuntimeError, AttributeError):
        return False


def stop():
    try:
        import winsound
        winsound.PlaySound(None, winsound.SND_PURGE)
    except (ImportError, RuntimeError):
        pass


# ── the screen ──────────────────────────────────────────────────────────


class SoundsScreen(Scrolling):
    """Every sound of assets/, and a maker of new ones."""

    section = "sounds"

    def __init__(self, parent, shell):
        Scrolling.__init__(self, parent)
        self.shell, self.code = shell, shell.code
        self.root_folder = shell.folder
        self.seed = 0
        self.music_seed = 0
        self.preview = os.path.join(tempfile.gettempdir(), "apkpy-studio-sound-%d.wav" % os.getpid())
        self.body = tk.Frame(self.inner, padx=px(self, 14), pady=px(self, 10))
        self.body.pack(fill="x", expand=True)
        self.draw_all()

    def draw_all(self):
        for child in self.body.winfo_children():
            child.destroy()
        b = self.body
        tk.Label(b, text="Sounds", font=("", 15, "bold")).pack(anchor="w")
        tk.Label(b, text="WAV, OGG and MP3 all play in the game. Here a WAV plays with a click; the others open in "
                         "your computer's player.", fg=MUTED, wraplength=px(self, 700), justify="left").pack(anchor="w")
        self.maker(b)
        self.music_maker(b)
        tk.Frame(b, bg=LINE, height=1).pack(fill="x", pady=px(self, 10))
        tk.Label(b, text="In your game", font=("", 12, "bold")).pack(anchor="w")
        grid = tk.Frame(b)
        grid.pack(anchor="w", pady=px(self, 4))
        main = self.code.main if self.code is not None else None
        named = {path: name for name, kind, path in (main.assets("sound", "music") if main is not None else [])}
        files = sound_files(self.root_folder)
        if not files:
            tk.Label(grid, text="No sounds yet.", fg=MUTED).grid(row=0, column=0, sticky="w")
        for r, rel in enumerate(files):
            tk.Label(grid, text=rel.split("/", 1)[-1]).grid(row=r, column=0, sticky="w", padx=(0, px(self, 12)))
            tk.Button(grid, text="Play", command=lambda p=rel: self.play(p)).grid(row=r, column=1, padx=1, pady=1)
            tk.Button(grid, text="Stop", command=stop).grid(row=r, column=2, padx=1)
            if rel in named:
                tk.Label(grid, text="in the code as %s" % named[rel], fg=MUTED).grid(row=r, column=3, sticky="w", padx=px(self, 10))
            elif main is not None:
                use = tk.Label(grid, text="use it in the game", fg="#2f6fdb", cursor="hand2")
                use.grid(row=r, column=3, sticky="w", padx=px(self, 10))
                use.bind("<Button-1>", lambda e, p=rel: self.use(p))
        tk.Button(b, text="Bring in a sound...", command=self.bring_in).pack(anchor="w", pady=(px(self, 8), 0))
        self.note = tk.Label(b, text="", fg=MUTED)
        self.note.pack(anchor="w", pady=(px(self, 4), 0))

    def maker(self, b):
        box = tk.Frame(b, bg=PANEL, highlightthickness=1, highlightbackground=LINE, padx=px(self, 10), pady=px(self, 8))
        box.pack(fill="x", pady=(px(self, 10), 0))
        tk.Label(box, text="Make a sound", font=("", 12, "bold"), bg=PANEL).grid(row=0, column=0, columnspan=6, sticky="w")
        tk.Label(box, text="Kind", bg=PANEL).grid(row=1, column=0, sticky="w", pady=px(self, 4))
        self.kind = ttk.Combobox(box, values=KINDS, state="readonly", width=12)
        self.kind.set(getattr(self, "kind_value", "jump"))
        self.kind.grid(row=1, column=1, sticky="w", padx=px(self, 6))
        self.kind.bind("<<ComboboxSelected>>", lambda e: self.try_sound())
        tk.Label(box, text="Pitch", bg=PANEL).grid(row=1, column=2, sticky="w", padx=(px(self, 10), 0))
        self.pitch = tk.Scale(box, from_=0.5, to=2.0, resolution=0.05, orient="horizontal", length=px(self, 120),
                              bg=PANEL, highlightthickness=0, showvalue=False)
        self.pitch.set(getattr(self, "pitch_value", 1.0))
        self.pitch.grid(row=1, column=3, sticky="w")
        tk.Label(box, text="Length", bg=PANEL).grid(row=1, column=4, sticky="w", padx=(px(self, 10), 0))
        self.length = tk.Scale(box, from_=0.5, to=2.0, resolution=0.05, orient="horizontal", length=px(self, 120),
                               bg=PANEL, highlightthickness=0, showvalue=False)
        self.length.set(getattr(self, "length_value", 1.0))
        self.length.grid(row=1, column=5, sticky="w")
        row = tk.Frame(box, bg=PANEL)
        row.grid(row=2, column=0, columnspan=6, sticky="w", pady=(px(self, 4), 0))
        tk.Button(row, text="Play", command=self.try_sound).pack(side="left", padx=(0, 2))
        tk.Button(row, text="Another one", command=self.another).pack(side="left", padx=2)
        tk.Button(row, text="Keep it...", command=self.keep_sound).pack(side="left", padx=2)

    def music_maker(self, b):
        box = tk.Frame(b, bg=PANEL, highlightthickness=1, highlightbackground=LINE, padx=px(self, 10), pady=px(self, 8))
        box.pack(fill="x", pady=(px(self, 8), 0))
        tk.Label(box, text="Make a tune", font=("", 12, "bold"), bg=PANEL).grid(row=0, column=0, columnspan=4, sticky="w")
        tk.Label(box, text="Mood", bg=PANEL).grid(row=1, column=0, sticky="w", pady=px(self, 4))
        self.mood = ttk.Combobox(box, values=MOODS, state="readonly", width=12)
        self.mood.set(getattr(self, "mood_value", "happy"))
        self.mood.grid(row=1, column=1, sticky="w", padx=px(self, 6))
        tk.Label(box, text="Speed", bg=PANEL).grid(row=1, column=2, sticky="w", padx=(px(self, 10), 0))
        self.speed = tk.Scale(box, from_=0.6, to=1.6, resolution=0.05, orient="horizontal", length=px(self, 120),
                              bg=PANEL, highlightthickness=0, showvalue=False)
        self.speed.set(getattr(self, "speed_value", 1.0))
        self.speed.grid(row=1, column=3, sticky="w")
        row = tk.Frame(box, bg=PANEL)
        row.grid(row=2, column=0, columnspan=4, sticky="w", pady=(px(self, 4), 0))
        tk.Button(row, text="Play", command=self.try_music).pack(side="left", padx=(0, 2))
        tk.Button(row, text="Stop", command=stop).pack(side="left", padx=2)
        tk.Button(row, text="Another one", command=self.another_tune).pack(side="left", padx=2)
        tk.Button(row, text="Keep it...", command=self.keep_music).pack(side="left", padx=2)

    def remember(self):
        self.kind_value, self.pitch_value, self.length_value = self.kind.get(), self.pitch.get(), self.length.get()
        self.mood_value, self.speed_value = self.mood.get(), self.speed.get()

    def samples(self):
        return make_sound(self.kind.get(), float(self.pitch.get()), float(self.length.get()), self.seed)

    def try_sound(self):
        write_wav(self.preview, self.samples())
        play_file(self.preview)

    def another(self):
        self.seed += 1
        self.try_sound()

    def tune(self):
        return make_music(self.mood.get(), float(self.speed.get()), self.music_seed)

    def try_music(self):
        write_wav(self.preview, self.tune())
        play_file(self.preview)

    def another_tune(self):
        self.music_seed += 1
        self.try_music()

    def keep_sound(self):
        self.keep(self.kind.get().replace(" ", "_"), self.samples())

    def keep_music(self):
        self.keep("theme" if not os.path.exists(os.path.join(self.root_folder, "assets", "theme.wav")) else "music_" + self.mood.get(), self.tune())

    def keep(self, suggestion, samples):
        name = simpledialog.askstring("Keep it", "Its name:", initialvalue=suggestion, parent=self)
        if not name:
            return
        rel = "assets/%s.wav" % slug(name)
        path = os.path.join(self.root_folder, *rel.split("/"))
        if os.path.exists(path) and not messagebox.askyesno("Keep it", "%s is there already. Put this one in its place?" % rel, parent=self):
            return
        write_wav(path, samples)
        self.remember()
        if self.code is not None and self.code.main is not None and rel not in [p for _, _, p in self.code.main.assets()]:
            self.code.declare(self.code.main, rel, "sound")
            self.code.touch("sounds")
        self.shell.content_changed()
        self.draw_all()
        self.note.config(text="Made %s. Choose it in a sound(...) action or a scene's music." % rel, fg=GOOD)

    def use(self, rel):
        name = self.code.declare(self.code.main, rel, "sound")
        self.code.touch("sounds")
        self.shell.content_changed()
        self.remember()
        self.draw_all()
        self.note.config(text="It is %s in the code now: choose it in a sound(...) action or a scene's music." % name, fg=GOOD)

    def bring_in(self):
        path = filedialog.askopenfilename(parent=self, title="A sound", filetypes=[("Sounds", "*.wav *.ogg *.mp3"), ("All files", "*.*")])
        if not path:
            return
        if not path.lower().endswith(SOUNDS):
            messagebox.showinfo("That sound cannot be used", "The game plays WAV, OGG and MP3.", parent=self)
            return
        name = slug(os.path.splitext(os.path.basename(path))[0]) + os.path.splitext(path)[1].lower()
        target = os.path.join(self.root_folder, "assets", name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(path, target)
        self.remember()
        self.draw_all()
        self.note.config(text="Brought in assets/%s." % name, fg=GOOD)

    def play(self, rel):
        if not play_file(os.path.join(self.root_folder, *rel.split("/"))):
            self.note.config(text="It cannot be played here.", fg=BAD)

    # ── the Shell ──

    def refresh(self):
        self.remember()
        self.draw_all()

    def reload(self):
        self.refresh()

    def stop(self):
        stop()
