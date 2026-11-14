"""The prebuilt engine (Java), shipped inside this package: the AAR that goes into the APK of an app with a game,
and the desktop JAR that the Previewer and `apkpy game play` run.

Both are built from game_engine/ in ApkPy's repository (tools/game/build_engine.py). A build copies the AAR into
the Android project it generates (app/libs/), so nothing is kept outside the project.
"""
import os

from . import ENGINE_VERSION
from .errors import GameError

HERE = os.path.dirname(os.path.abspath(__file__))
FOLDER = os.path.join(HERE, "engine")
AAR = "apkpygame-engine.aar"
DESKTOP_JAR = "apkpygame-desktop.jar"
FILES = (AAR, DESKTOP_JAR)


def folder():
    """The engine's folder; G1007 when a file of it is missing."""
    missing = [f for f in FILES if not os.path.isfile(os.path.join(FOLDER, f))]
    if missing:
        raise GameError("G1007", "the game engine %s is missing from this ApkPy (%s)"
                        % (ENGINE_VERSION, ", ".join(missing)),
                        fix=["pip install --force-reinstall apkpy",
                             "Working on ApkPy itself: python tools/game/build_engine.py"])
    return FOLDER


def aar():
    return os.path.join(folder(), AAR)


def desktop_jar():
    return os.path.join(folder(), DESKTOP_JAR)
