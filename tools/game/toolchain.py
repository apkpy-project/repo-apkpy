"""Where the JDK and android.jar are, for the game engine's tools (working on ApkPy itself)."""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # ApkPy's repository
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def find(android=True):
    """The tools; android=False when nothing is compiled against android.jar (the engine's own tests)."""
    from apkpy_lib.game._host import toolchain
    from apkpy_lib.game.errors import GameError
    try:
        tools = toolchain()
    except GameError as e:
        sys.exit(str(e))
    if android and not os.path.isfile(tools.android_jar):
        sys.exit("android.jar not found (%s): run  apkpy setup" % tools.android_jar)
    return tools


def engine_version(java_root):
    with open(os.path.join(java_root, "core", "apkpygame", "core", "Game.java"), encoding="utf-8") as fh:
        return re.search(r'VERSION = "([^"]+)"', fh.read()).group(1)
