"""The Studio: one window to make a game, for any ApkPy project that has one (game/main.py).

    apkpy game studio

Started in a folder with no project, it opens on "A new game": the kind, the name, and the game is made.

It plays the game inside its window, edits the game's data tables, draws its pictures pixel by pixel, makes the
files for the phone and the Play Store, and keeps copies of the project to go back to. It only reads and writes the
project's own files: they can also be changed by hand, and built with plain ApkPy.

A project can add sections of its own with tools/studio_kit.py, a module that defines Studio, a subclass of
shell.Shell (the monster-rpg template's maps, story and monsters are one).

By Ruben Rego (the monster-rpg template's Studio, ApkPyGame), opened to every game.
"""
import importlib.util
import os
import sys

KIT = os.path.join("tools", "studio_kit.py")


def kit_path(folder):
    return os.path.join(folder, KIT)


def studio_class(folder):
    """The Studio for this project: its kit's, or the one for any game."""
    path = kit_path(folder)
    if os.path.isfile(path):
        tools = os.path.dirname(path)
        if tools not in sys.path:
            sys.path.insert(0, tools)              # a kit imports its other tools by their names
        spec = importlib.util.spec_from_file_location("studio_kit", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.Studio
    from .shell import Shell
    return Shell


def open_studio(folder="."):
    """Opens the window and waits until it is closed."""
    from .ui import make_root
    folder = os.path.abspath(folder)
    cls = studio_class(folder)
    window = make_root("Studio")
    cls(window, folder)
    window.mainloop()


def open_new_game(where="."):
    """Opens the window on "A new game", made in a folder of `where`; then it is the Studio of that game."""
    from .newgame import NewGame
    from .ui import make_root, px
    window = make_root("Studio: a new game")
    window.geometry("%dx%d" % (px(window, 960), px(window, 640)))

    def made(folder):
        screen.destroy()
        studio_class(folder)(window, folder)

    screen = NewGame(window, where, made)
    screen.pack(fill="both", expand=True)
    window.mainloop()


def start_another(folder):
    """The Studio of another project, in a window of its own (another Python, as each Studio is one project)."""
    import subprocess
    return subprocess.Popen([sys.executable, "-m", "apkpy_lib.game.studio", folder],
                            env=dict(os.environ, APKPY_RELOAD="0"))
