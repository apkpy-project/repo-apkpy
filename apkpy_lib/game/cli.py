"""What ApkPy's commands do for games (apkpy_lib/cli.py calls these):

    apkpy start NAME --game [menus|blank|monster-rpg|tutorial|GENRE]   a new project: an app with a game
          GENRE: platformer, shooter, runner, bricks, adventure, tap, puzzle, world (a whole short game of that kind)
    apkpy game init                 adds a game to the ApkPy project in this folder
    apkpy game play [--scene S]     the game alone, in a window (the same engine as the phone)
    apkpy game studio               the Studio: one window to change the game (in a folder with no project: a new game)
    apkpy game build                only the game: game/ read and translated (the Java in build/apkpygame/java/)

The rest is ApkPy's own: `python writehere.py` shows the game inside the Previewer, and `apkpy run`, `build`
and `release` build it with the app whenever writehere.py calls enable_game().
"""
import os
import subprocess

from . import ENGINE_VERSION, engine, glue, templates
from .errors import GameError
from .project import Project

GENRES = templates.GENRES
TEMPLATES =("menus", "blank", "monster-rpg", "tutorial") + GENRES
# Templates that are a whole project (apkpy_lib/game/project_templates/), and what to read first in each.
WHOLE_GAMES = dict({"monster-rpg": "its README.md", "tutorial": "tutorial/01-before-you-start.md"},
                   **{genre: "its README.md (apkpy game studio opens it in the Studio)" for genre in GENRES})


def new(name, template="menus", app_id=None, say=print, title=None):
    """A new project in the folder `name`. The game is called as its folder, or `title` (the Studio's New game)."""
    folder = os.path.abspath(name)
    if os.path.exists(folder):
        raise GameError("G1008", "%s already exists" % folder,
                        fix="Choose another name, or run  apkpy game init  inside it.")
    if template not in TEMPLATES:
        raise GameError("G1008", "there is no game template '%s'" % template, fix="Templates: " + ", ".join(TEMPLATES))
    name = title or os.path.basename(folder)
    app_id = app_id or "com.example." + templates.slug(name)
    if template in WHOLE_GAMES:
        templates.copy_project_template(folder, name, app_id, template)
        say("Created %s: read %s first." % (folder, WHOLE_GAMES[template]))
        return folder
    templates.new_project(folder, name, app_id, "enable_game()\n", template)
    say("Created %s" % folder)
    say("  writehere.py   the app (its screens)\n  game/main.py   the game\n")
    say("Next:\n  cd %s\n  python writehere.py      (the Previewer: press Play)\n"
        "  apkpy run --usb          (on the phone)" % os.path.basename(folder))
    return folder


def init(say=print):
    project = Project.find()
    if not os.path.isfile(project.writehere):
        raise GameError("G1009", "there is no writehere.py here", fix="apkpy start NAME --game   (a new project)")
    templates.add_game(project.root, project.name)
    with open(project.writehere, encoding="utf-8") as fh:
        text = fh.read()
    if glue.status(text) != "enabled":
        with open(project.writehere, "w", encoding="utf-8") as fh:
            fh.write(glue.enable(text))
    say("Game added: game/main.py, assets/, and enable_game() in writehere.py.")
    say('Open the game from the app with:  game_play("main", "{}", on_result=your_function)')


def build_game(say=print):
    from .build import build
    return build(Project.find(), log=say)


def play(scene="", args="{}", say=print):
    from .build import bundle_only
    from . import desktop
    project = Project.find()
    info = bundle_only(project)
    for w in info["warnings"]:
        say("  warning: " + w)
    desktop._config["project"] = project
    cmd = desktop.command(scene, args)
    say("Game: %s (close the window to end; Esc is the phone's Back)" % (scene or "start scene"))
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)      # stdin: this terminal
    for line in process.stdout:
        if line.startswith("APKPYGAME_RESULT "):
            value = line[len("APKPYGAME_RESULT "):].strip()
            say("result: " + value)
            if '"suspended":true' in value:
                say("The game opened an app screen (in the app it would show now).\n"
                    "Type  resume  and Enter to continue it, or just Enter to end.")
        else:
            say(line.rstrip("\n"))
    return process.wait()


def studio(say=print):
    """The Studio, for the game of the project this folder is in. No project here: it opens on a new game."""
    try:
        project = Project.find()
    except GameError:
        from .studio import open_new_game
        say("No project here: the Studio opens on a new game, made in a folder of this one (close the window to end)")
        return open_new_game(os.getcwd())
    if not os.path.isfile(project.main):
        raise GameError("G1001", "there is no game/main.py in %s" % project.root, cause="The Studio opens a project's game.",
                        fix=["apkpy game init   (adds a game to this project)", "apkpy start NAME --game   (a new project)"])
    from .studio import open_studio
    say("Studio: %s (close the window to end)" % project.root)
    open_studio(project.root)


def doctor_lines():
    """[(ok, text)] for `apkpy doctor`, in a project with a game (game/main.py)."""
    out = []
    try:
        engine.folder()
        out.append((True, "game engine %s" % ENGINE_VERSION))
    except GameError as e:
        out.append((False, e.message))
    try:
        project = Project.find()
    except GameError:
        return out
    if not os.path.isfile(project.main):
        return out
    if os.path.isfile(project.writehere):
        with open(project.writehere, encoding="utf-8") as fh:
            state = glue.status(fh.read())
        out.append((state == "enabled", "writehere.py turns the game on (enable_game())" if state == "enabled" else
                    "writehere.py: %s -- apkpy game init" % ("the old block of declarations" if state == "old"
                                                            else "no enable_game()")))
    return out
