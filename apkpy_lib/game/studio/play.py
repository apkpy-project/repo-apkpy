"""The Play section of the Studio: the real game, built from the saved files and run inside the Studio's window,
the same engine as on the phone.

By Ruben Rego (the monster-rpg template's Studio), shared by every game's Studio.
"""
import os
import re
import subprocess
import sys
import tkinter as tk
from tkinter import ttk

from .ui import BAD, MUTED, px

FIRST = "(its first scene)"
BUILD = ("import sys; from apkpy_lib.game.build import bundle_only; from apkpy_lib.game.project import Project; "
         "bundle_only(Project('.'))")


def scene_names(root):
    """The scenes game/main.py declares, in its order."""
    try:
        with open(os.path.join(root, "game", "main.py"), encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return []
    return re.findall(r'\bgame\.scene\(\s*["\']([\w.-]+)["\']', text)


class GameScreen(tk.Frame):
    """The real game, inside this window."""

    HINT = "Click the game first. Arrow keys and space play, Esc is the phone's Back, the mouse is a finger."
    PLAYING = "Playing. " + HINT

    def __init__(self, parent, shell):
        tk.Frame.__init__(self, parent)
        self.shell = shell
        self.game = None
        self.builder = None
        self.pending = None
        top = tk.Frame(self, pady=px(self, 4), padx=px(self, 6))
        top.pack(fill="x")
        self.build_buttons(top)
        self.status = tk.Label(top, text=self.HINT, fg=MUTED, anchor="w")
        self.status.pack(side="left", padx=px(self, 8))
        self.area = tk.Frame(self, bg="#111318")
        self.area.pack(fill="both", expand=True)

    def build_buttons(self, top):
        tk.Button(top, text="Play", command=self.play_from_start).pack(side="left", padx=1)
        tk.Label(top, text="from", fg=MUTED).pack(side="left", padx=(px(self, 6), px(self, 2)))
        self.scene_box = ttk.Combobox(top, state="readonly", width=16, postcommand=self.fill_scenes)
        self.scene_box.pack(side="left")
        self.fill_scenes()
        self.scene_box.set(FIRST)
        tk.Button(top, text="Stop", command=self.stop).pack(side="left", padx=(px(self, 6), 1))

    def fill_scenes(self):
        self.scene_box.configure(values=[FIRST] + scene_names(self.shell.project.root))

    def play_from_start(self):
        chosen = self.scene_box.get() if hasattr(self, "scene_box") else FIRST
        self.start("" if chosen in ("", FIRST) else chosen)

    def start(self, scene):
        """Saves, builds in the background, and then opens the game here. scene "" is the game's first scene."""
        self.stop()
        self.shell.save_all()
        if self.shell.has_map_problem():
            self.status.config(text="Fix the problem at the bottom first.", fg=BAD)
            return
        self.status.config(text="Building...", fg=MUTED)
        self.pending = scene
        self.builder = subprocess.Popen([sys.executable, "-c", BUILD], cwd=self.shell.project.root, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, errors="replace")
        self.after(100, self.watch_build)

    def watch_build(self):
        if self.builder is None:
            return
        if self.builder.poll() is None:
            self.after(100, self.watch_build)
            return
        said = self.builder.stdout.read()
        code, self.builder = self.builder.returncode, None
        if code:
            lines = [l.strip() for l in said.strip().splitlines() if l.strip()]
            told = next((i for i, l in enumerate(lines) if l.startswith("APKPY ")), None)
            words = " ".join(lines[told:told + 2]) if told is not None else (lines[-1] if lines else "The build failed.")
            self.status.config(text=words[:160], fg=BAD)
            return
        self.open_game(self.pending)

    def open_game(self, scene):
        from apkpy_lib.game import desktop
        from apkpy_lib.game.embedded import EmbeddedGame
        from apkpy_lib.game.project import Project
        desktop._config.update({"bundle": None, "store": None, "project": Project(self.shell.project.root)})
        command = desktop.command(scene, "{}", "--parent-pipe")
        bundle = command[command.index("--bundle") + 1]
        self.update_idletasks()
        self.game = EmbeddedGame(self.area, lambda w, h: command + ["--embed", "%dx%d" % (w, h)], bundle, self.ended)
        self.status.config(text=self.PLAYING, fg=MUTED)

    def ended(self, value):
        self.status.config(text="The game ended.", fg=MUTED)

    def stop(self):
        self.pending = None
        if self.builder is not None and self.builder.poll() is None:
            self.builder.kill()
        self.builder = None
        if self.game is not None:
            game, self.game = self.game, None
            try:
                game.close()
            except (tk.TclError, OSError):
                pass
            if game.label.winfo_exists():
                game.label.destroy()

    def reload(self):
        if hasattr(self, "scene_box"):
            self.fill_scenes()
