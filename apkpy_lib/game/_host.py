"""Where the game package meets the rest of ApkPy. The only module of apkpy_lib.game that reaches outside it
(tests/game/test_apkpy_boundary.py fails if another one does), so the engine stays apart from the app's build.

The points where the two meet:

  E1 toolchain()       the JDK and the Android SDK that `apkpy run` builds with
  E2 (apkpy_lib.cli)   `apkpy run/build/release` read enable_game() in writehere.py: cli._read_writehere() calls
                       glue.prepare_for_apkpy(), which builds the game and writes the native.* declarations there
  E3 preview_window()  the Previewer's window, where the game is drawn
  E4 preview_keys()    the Previewer's Back and turn keys, which the game takes while it is on show
  E5 (apkpy_lib.reload) the hot reload looks at every .py under game/, however deep (reload.DEEP_FOLDERS)
  E6 (none here)       translations() and the Screen ids of writehere.py: the build reads them by AST
                       (compiler/app.py)
  E7 keystores_dir(), find_adb()
                       the Studio's Publish: where `apkpy release` keeps a game's signing key, and the adb of the
                       Android SDK that ApkPy found
"""
import os
from collections import namedtuple

Tools = namedtuple("Tools", "javac jar java android_jar")


def toolchain():
    """E1: javac, jar, java and android.jar, from the JDK and the SDK that ApkPy uses."""
    from .. import config, native_build
    from .errors import GameError
    found = native_build.discover_toolchain()
    jdk, sdk = found.get("jdk_home"), found.get("sdk")
    if not jdk or not sdk:
        raise GameError("G1006", "JDK or Android SDK not found", fix=["apkpy doctor", "apkpy setup"])
    exe = ".exe" if os.name == "nt" else ""
    bin_dir = os.path.join(jdk, "bin")
    return Tools(os.path.join(bin_dir, "javac" + exe), os.path.join(bin_dir, "jar" + exe),
                 os.path.join(bin_dir, "java" + exe),
                 os.path.join(sdk, "platforms", "android-%d" % config.COMPILE_SDK, "android.jar"))


def keystores_dir():
    """E7: the folder where `apkpy release` keeps the signing keys, one per app id."""
    from .. import native_build
    return native_build.keystores_dir()


def find_adb():
    """E7: adb, from the Android SDK that ApkPy found; None if there is none."""
    from .. import native_build
    from ..logs import find_adb as find
    return find(native_build.discover_toolchain().get("sdk"))


# The Previewer's keys (AppPreview binds them with bind_all, so a widget with the focus sees them first and can
# stop them with "break").
PREVIEW_BACK_KEYS = ("<Alt-Left>",)
PREVIEW_TURN_KEYS = ("<Control-Left>", "<Control-Right>")


def preview_keys():
    """E4: the Previewer's Back and turn keys, as Tk events: {"back": (...), "turn": (...)}."""
    return {"back": PREVIEW_BACK_KEYS, "turn": PREVIEW_TURN_KEYS}


def preview_window():
    """E3: the Previewer's Tk window, or None when no Previewer is open (a script, a test without Tk). It never
    opens one: asking the lazy app for its root would."""
    root = None
    try:
        from .. import ui
        root = ui.live_preview_root()
    except ImportError:
        pass
    if root is None:
        # Any other Tk loop of this Python (a tool, a test): its first window. Reading it opens nothing.
        try:
            import tkinter
            root = getattr(tkinter, "_default_root", None)
        except ImportError:
            return None
    if root is None:
        return None
    try:
        return root if root.winfo_exists() else None
    except Exception:
        return None


def window_shape(root, shape=None):
    """The window's (width, height); with ``shape``, gives the window that shape
    first (the Previewer turns the device the same way: root.geometry)."""
    if shape is not None:
        root.geometry("%dx%d" % shape)
        root.update_idletasks()
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    if w <= 1 or h <= 1:                    # not mapped yet: what was asked for
        try:
            w, h = (int(v) for v in root.geometry().split("+")[0].split("x"))
        except ValueError:
            w = h = 1
    if w <= 1 or h <= 1:
        w, h = 411, 914                     # the Previewer's phone (Pixel 9, in dp)
    return w, h
