"""enable_game(): one line in writehere.py gives the app game_play, game_resume, game_get, game_set,
game_last_result and game_suspended. It comes with `from apkpy_lib import *`.

    from apkpy_lib import *

    enable_game()

This code runs only in Python (the Previewer). For the phone, ApkPy never runs writehere.py: it reads its text,
and glue.prepare_for_apkpy puts the same declarations on that line.
"""
import sys

__all__ = ["enable_game"]


def enable_game():
    """Gives this app the functions that open and talk to its game (game/main.py)."""
    from . import glue
    names = sys._getframe(1).f_globals
    if "game_play" in names:                # defined already (a second call, or written out by hand)
        return
    exec(glue.render(), names)
