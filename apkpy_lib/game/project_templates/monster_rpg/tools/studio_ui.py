"""The look shared by the Studio and the editors: sharp on a scaled screen, and one set of colours.

It is ApkPy's own now (apkpy_lib.game.studio.ui), so every game's Studio looks the same. This name stays for the
template's tools: the map and story editors import it.
"""
from apkpy_lib.game.studio.ui import (ACCENT, BAD, BG, GOOD, LINE, MUTED, PANEL, SIDE, SIDE_TEXT, TEXT, Scrolling,  # noqa: F401
                                      apply_theme, make_root, px)
