"""python -m apkpy_lib.game.studio [FOLDER]: the Studio of the game in FOLDER (or this one), or a new game there."""
import os
import sys

from . import open_new_game, open_studio

folder = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
if os.path.isfile(os.path.join(folder, "game", "main.py")):
    open_studio(folder)
else:
    open_new_game(folder)
