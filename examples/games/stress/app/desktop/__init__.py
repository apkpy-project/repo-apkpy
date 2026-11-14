"""Previewer shim (desktop only, never translated): points apkpy_lib.game.desktop at this example's bundle.

The other examples need no shim: enable_game() finds their game/ by itself.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", "..", ".."))      # ApkPy's repository
sys.path.insert(0, _ROOT)

from apkpy_lib.game import desktop as game  # noqa: E402

game.configure(os.path.join(_HERE, "..", "..", "bundle"))
