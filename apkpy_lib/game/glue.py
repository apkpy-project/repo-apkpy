"""The glue: the native.* declarations that give an app game_play, game_get and the rest.

An app asks for them with one line in writehere.py:

    enable_game()

- In the Previewer (python writehere.py), enable_game() runs: it defines the functions, whose preview= side
  runs the game on the desktop engine.
- For the phone, ApkPy never runs writehere.py: it reads its text. `apkpy run`, `build` and `release` read it
  through cli._read_writehere(), which calls prepare_for_apkpy(): the game is built, and the same declarations
  are written on that line, on ONE line, so every other line keeps its number.

The two AARs the declarations name (the engine's and the game's) are copied by the build into the Android
project's app/libs/ (android_libs()).
"""
import os
import re
import sys

from ._pycompat import statements_on_one_line
from .errors import GameError

VERSION = 1
CALL = re.compile(r"^enable_game\(\)[ \t]*(#[^\n]*)?$", re.M)
# Written by ApkPyGame before it was part of ApkPy: the import (enable_game now comes with apkpy_lib) and the
# block of declarations it could write out, whose Gradle lines name files outside the project.
OLD_IMPORT = re.compile(r"^from apkpygame\.app import enable_game[ \t]*\n", re.M)
OLD_BLOCK = re.compile(r"^# >>> apkpygame:glue v(\d+).*?^# <<< apkpygame:glue v\d+ <<<[^\n]*\n?", re.M | re.S)

ENGINE_LIB = "libs/apkpygame-engine.aar"
GAME_LIB = "libs/apkpygame-game.aar"

TEMPLATE = '''native.gradle("implementation files('{engine_lib}')")
native.gradle("implementation files('{game_lib}')")

# game_play(scene, args_json, on_result=f): opens the game; f(ok, json) gets how it ended
game_play = native.java_async(
    "apkpygamePlay",
    args=("scene", "argsJson"),
    imports=["android.app.Activity", "apkpygame.android.Host"],
    code="""
        Host.play((Activity) context, scene, argsJson, new Host.Listener() {{
            @Override public void onResult(boolean ok, String json) {{ done.run(ok, json); }}
        }});
    """,
    preview=lambda scene, args_json, done: __import__("apkpy_lib.game.desktop", fromlist=["play"]).play(scene, args_json, done),
)

# game_resume(on_result=f): continues a game that opened an ApkPy screen (open_app)
game_resume = native.java_async(
    "apkpygameResume",
    imports=["android.app.Activity", "apkpygame.android.Host"],
    code="""
        Host.resume((Activity) context, new Host.Listener() {{
            @Override public void onResult(boolean ok, String json) {{ done.run(ok, json); }}
        }});
    """,
    preview=lambda done: __import__("apkpy_lib.game.desktop", fromlist=["resume"]).resume(done),
)

# game_get(key) / game_set(key, value): the store shared with the game (store_add, store_set)
game_get = native.java(
    "apkpygameGet", args=("key",), imports=["apkpygame.android.Host"],
    code="return Host.get(context, key);",
    preview=lambda key: __import__("apkpy_lib.game.desktop", fromlist=["get"]).get(key),
)
game_set = native.java(
    "apkpygameSet", args=("key", "value"), imports=["apkpygame.android.Host"],
    code="return Host.set(context, key, value);",
    preview=lambda key, value: __import__("apkpy_lib.game.desktop", fromlist=["put"]).put(key, value),
)

# game_last_result(): the last ending, once ("" if none); read it in lifecycle(on_resume=...)
game_last_result = native.java(
    "apkpygameLastResult", imports=["apkpygame.android.Host"],
    code="return Host.lastResult(context);",
    preview=lambda: __import__("apkpy_lib.game.desktop", fromlist=["last_result"]).last_result(),
)

# game_suspended(): "true" while a game waits for game_resume() (it opened an ApkPy screen)
game_suspended = native.java(
    "apkpygameSuspended", imports=["apkpygame.android.Host"],
    code="return Host.isSuspended(context);",
    preview=lambda: __import__("apkpy_lib.game.desktop", fromlist=["suspended"]).suspended(),
)

# game_embed(slot, scene, height_dp) EXPERIMENTAL: runs a scene inside a container of the current screen,
# marked with label("apkpygame:slot:<slot>", parent=that_container). Phone only.
game_embed = native.java(
    "apkpygameEmbed", args=("slot", "scene", "heightDp"), imports=["android.app.Activity", "apkpygame.android.Host"],
    code="return Host.embed((Activity) context, slot, scene, heightDp);",
    preview=lambda slot, scene, height_dp: "preview: game_embed runs on the phone only",
)
'''


def render():
    return TEMPLATE.format(engine_lib=ENGINE_LIB, game_lib=GAME_LIB)


def status(text):
    """'enabled' (enable_game() is called) | 'old' (the block ApkPyGame used to write) | 'missing'"""
    if OLD_BLOCK.search(text):
        return "old"
    return "enabled" if CALL.search(text) else "missing"


def enable(text):
    """The text with enable_game() added after the apkpy_lib import (the old block, if any, takes its place)."""
    if OLD_BLOCK.search(text):
        text = OLD_BLOCK.sub(lambda _: "enable_game()\n", text, count=1)
        return OLD_IMPORT.sub("", text, count=1)
    if CALL.search(text):
        return OLD_IMPORT.sub("", text, count=1)
    lines = text.splitlines(keepends=True)
    at = 0
    for i, line in enumerate(lines):
        if line.startswith("from apkpy_lib import") or line.startswith("import apkpy_lib"):
            at = i + 1
    return "".join(lines[:at]) + "\nenable_game()\n\n" + "".join(lines[at:])


def expand(text):
    """What ApkPy should read: enable_game() becomes the declarations, on ONE line, so that every other line keeps
    its number and what the file defines above it stays above it."""
    if not CALL.search(text):
        return text
    line = statements_on_one_line(render())
    text = OLD_IMPORT.sub(lambda m: "\n", text, count=1)      # a blank line keeps the numbers
    return CALL.sub(lambda _: line, text, count=1)


def wants_game(text):
    """True when writehere.py turns a game on (or has the block ApkPyGame used to write, to say what to do)."""
    return bool(CALL.search(text) or OLD_BLOCK.search(text))


def prepare_for_apkpy(text, start=None):
    """Called when `apkpy run`, `build` or `release` read writehere.py (cli._read_writehere): the game is built,
    then the text is expanded. A build that fails is reported here, and the answer is None: ApkPy stops, as it does
    when it cannot read the file."""
    if not CALL.search(text) and not OLD_BLOCK.search(text):
        return text
    from .build import build
    from .project import Project
    try:
        project = Project.find(start)
        check_text(text, project)
        build(project)
        return expand(text)
    except GameError as e:
        print(e, file=sys.stderr)
        return None


def android_libs(start=None):
    """{path in the Android project: file to copy there}: the two AARs that the declarations name."""
    from . import engine
    from .compiler.pack import AAR
    from .project import Project
    project = Project.find(start)
    return {"app/" + ENGINE_LIB: engine.aar(), "app/" + GAME_LIB: os.path.join(project.build_dir, AAR)}


def check_text(text, project):
    found = status(text)
    if found == "missing":
        raise GameError("G1101", "writehere.py does not turn the game on", project.rel(project.writehere),
                        cause="The app opens the game through game_play() and the other game_* functions, which "
                              "enable_game() gives it.",
                        fix="After  from apkpy_lib import *, add the line:  enable_game()")
    if found == "old":
        raise GameError("G1101", "writehere.py has the block of declarations ApkPyGame used to write",
                        project.rel(project.writehere),
                        cause="Its Gradle lines name files in ~/.apkpygame, which ApkPy no longer writes: the "
                              "engine now goes inside the Android project.",
                        fix=["Replace the block (from '# >>> apkpygame:glue' to '# <<< apkpygame:glue') with the "
                             "line  enable_game()", "Or: apkpy game init, which does it for you"])


def check(project):
    with open(project.writehere, encoding="utf-8") as fh:
        check_text(fh.read(), project)
