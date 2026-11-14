"""Games for ApkPy apps: 2D and 2.5D, made with Python and run by a Java engine (the same on the phone and on the
PC). Written by Rúben Rego as ApkPyGame, and part of ApkPy since 1.15.0.

    from apkpy_lib.game import *        # in game/main.py: read by the build, never run

Everything in this package runs on the developer's PC (the build, the Previewer's side); nothing of it goes into
the APK, which only carries the Java engine and the game's bundle.
"""

ENGINE_VERSION = "1.0.0"

from .api import *  # noqa: E402,F401,F403
from .api import __all__  # noqa: E402,F401
