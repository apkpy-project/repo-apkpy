"""Shared icon geometry for the Previewer and the Android compiler.

Like :mod:`apkpy_lib.theme`, this module deliberately has no Tkinter, Pillow or
Android-build dependencies.  Both rendering backends consume the same path data
from here, which is what stops preview/device drift: an icon is *data*, and
there is only one copy of it.

Before this module existed there were two unrelated icon systems -- a hand-drawn
Tk one in ``ui.py`` and a vector one in ``compiler.py`` -- that shared only 29 of
their 48 names.  ``person`` had no drawing in the Previewer and rendered as a
ring with a dot; ``skip_next`` had none on Android and rendered as a solid disc.

Geometry conventions:

* every path is authored in a 24x24 viewport, the Material Icons grid;
* the fill rule is **nonZero**, which is what ``<vector>`` uses when no
  ``android:fillType`` is given.  Even-odd would punch false holes wherever two
  subpaths overlap in the same direction -- ``library_music`` is exactly that
  case, its back card overlaps its front card.
"""

import math
import os
import re

__all__ = [
    "ICON_VIEWPORT", "names", "all_names", "search", "resolve", "path_for", "suggest",
    "has_outlined", "OUTLINED_STYLE", "FILLED_STYLE",
    "flatten", "rasterize", "to_path_data", "is_file_reference", "load_svg",
]

ICON_VIEWPORT = 24.0

# --- Catalogue --------------------------------------------------------------
# Material Icons (filled), 24x24.  Filled is the style Android already shipped,
# so no compiled app changes appearance; only the Previewer starts agreeing.

_ICON_PATHS = {
    'local_shipping': 'M20,8h-3V4H2v13h2a3,3 0,0 0,6,0h5a3,3 0,0 0,6,0h2v-5zM4,6h11v9H4zM17,10h2l2,3h-4zM7,16a1,1 0,1 1,0,2a1,1 0,1 1,0,-2zM18,16a1,1 0,1 1,0,2a1,1 0,1 1,0,-2z',
    # Carried over unchanged from the Android table these two
    # backends used to duplicate.
    'add': 'M19,13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z',
    'arrow_back': 'M20,11H7.83l5.59,-5.59L12,4l-8,8 8,8 1.41,-1.41L7.83,13H20v-2z',
    'arrow_forward': 'M12,4l-1.41,1.41L16.17,11H4v2h12.17l-5.58,5.59L12,20l8,-8z',
    'bell': 'M12,22c1.1,0 2,-0.9 2,-2h-4c0,1.1 0.9,2 2,2zm6,-6v-5c0,-3.07 -1.64,-5.64 -4.5,-6.32V4c0,-0.83 -0.67,-1.5 -1.5,-1.5s-1.5,0.67 -1.5,1.5v0.68C7.63,5.36 6,7.92 6,11v5l-2,2v1h16v-1l-2,-2z',
    'camera': 'M12,15.2c-1.77,0 -3.2,-1.43 -3.2,-3.2s1.43,-3.2 3.2,-3.2 3.2,1.43 3.2,3.2 -1.43,3.2 -3.2,3.2zM9,2L7.17,4H4C2.9,4 2,4.9 2,6v12c0,1.1 0.9,2 2,2h16c1.1,0 2,-0.9 2,-2V6c0,-1.1 -0.9,-2 -2,-2h-3.17L15,2H9z',
    'chart': 'M5,9.2h3V19H5zM10.6,5h2.8v14h-2.8zm5.6,8H19v6h-2.8z',
    'check': 'M9,16.17L4.83,12l-1.42,1.41L9,19 21,7l-1.41,-1.41z',
    'circle': 'M12,2C6.48,2 2,6.48 2,12s4.48,10 10,10 10,-4.48 10,-10S17.52,2 12,2z',
    # A aparencia da app: escuro, claro, e o que o telemovel disser.
    'contrast': 'M12,2C6.48,2 2,6.48 2,12s4.48,10 10,10 10,-4.48 10,-10S17.52,2 12,2zM12,20V4c4.41,0 8,3.59 8,8s-3.59,8 -8,8z',
    'dark_mode': 'M12,3c-4.97,0 -9,4.03 -9,9s4.03,9 9,9 9,-4.03 9,-9c0,-0.46 -0.04,-0.92 -0.1,-1.36 -0.98,1.37 -2.58,2.26 -4.4,2.26 -2.98,0 -5.4,-2.42 -5.4,-5.4 0,-1.81 0.89,-3.42 2.26,-4.4C12.92,3.04 12.46,3 12,3z',
    'light_mode': 'M12,7c-2.76,0 -5,2.24 -5,5s2.24,5 5,5 5,-2.24 5,-5 -2.24,-5 -5,-5zM2,13h2c0.55,0 1,-0.45 1,-1s-0.45,-1 -1,-1H2c-0.55,0 -1,0.45 -1,1s0.45,1 1,1zM20,13h2c0.55,0 1,-0.45 1,-1s-0.45,-1 -1,-1h-2c-0.55,0 -1,0.45 -1,1s0.45,1 1,1zM11,2v2c0,0.55 0.45,1 1,1s1,-0.45 1,-1V2c0,-0.55 -0.45,-1 -1,-1s-1,0.45 -1,1zM11,20v2c0,0.55 0.45,1 1,1s1,-0.45 1,-1v-2c0,-0.55 -0.45,-1 -1,-1s-1,0.45 -1,1zM5.99,4.58c-0.39,-0.39 -1.03,-0.39 -1.41,0 -0.39,0.39 -0.39,1.03 0,1.41l1.06,1.06c0.39,0.39 1.03,0.39 1.41,0s0.39,-1.03 0,-1.41L5.99,4.58zM18.36,16.95c-0.39,-0.39 -1.03,-0.39 -1.41,0 -0.39,0.39 -0.39,1.03 0,1.41l1.06,1.06c0.39,0.39 1.03,0.39 1.41,0 0.39,-0.39 0.39,-1.03 0,-1.41l-1.06,-1.06zM19.42,5.99c0.39,-0.39 0.39,-1.03 0,-1.41 -0.39,-0.39 -1.03,-0.39 -1.41,0l-1.06,1.06c-0.39,0.39 -0.39,1.03 0,1.41s1.03,0.39 1.41,0l1.06,-1.06zM7.05,18.36c0.39,-0.39 0.39,-1.03 0,-1.41 -0.39,-0.39 -1.03,-0.39 -1.41,0l-1.06,1.06c-0.39,0.39 -0.39,1.03 0,1.41s1.03,0.39 1.41,0l1.06,-1.06z',
    'close': 'M18.3,5.71L16.89,4.29 12,9.17 7.11,4.29 5.7,5.71 10.59,10.59 5.7,15.48 7.11,16.89 12,12 16.89,16.89 18.3,15.48 13.41,10.59z',
    'create_new_folder': 'M20,6h-8l-2,-2H4C2.9,4 2.01,4.9 2.01,6L2,18c0,1.1 0.9,2 2,2h16c1.1,0 2,-0.9 2,-2V8c0,-1.1 -0.9,-2 -2,-2zM19,14h-3v3h-2v-3h-3v-2h3V9h2v3h3v2z',
    'delete': 'M6,19c0,1.1 0.9,2 2,2h8c1.1,0 2,-0.9 2,-2V7H6v12zM8,9h8v10H8V9zm7.5,-5l-1,-1h-5l-1,1H5v2h14V4z',
    'description': 'M14,2H6C4.9,2 4,2.9 4,4v16c0,1.1 0.9,2 2,2h12c1.1,0 2,-0.9 2,-2V8l-6,-6zM16,18H8v-2h8v2zM16,14H8v-2h8v2zM13,9V3.5L18.5,9H13z',
    'download': 'M19,9h-4V3H9v6H5l7,7 7,-7zM5,18v2h14v-2H5z',
    'edit': 'M3,17.25V21h3.75L17.81,9.94l-3.75,-3.75L3,17.25zM20.71,7.04c0.39,-0.39 0.39,-1.02 0,-1.41l-2.34,-2.34c-0.39,-0.39 -1.02,-0.39 -1.41,0l-1.83,1.83 3.75,3.75 1.83,-1.83z',
    'error_outline': 'M11,15h2v2h-2v-2zm0,-8h2v6h-2V7zm0.99,-5C6.47,2 2,6.48 2,12s4.47,10 9.99,10C17.52,22 22,17.52 22,12S17.52,2 11.99,2zM12,20c-4.42,0 -8,-3.58 -8,-8s3.58,-8 8,-8 8,3.58 8,8 -3.58,8 -8,8z',
    'folder': 'M10,4H2C0.9,4 0,4.9 0,6v12c0,1.1 0.9,2 2,2h20c1.1,0 2,-0.9 2,-2V8c0,-1.1 -0.9,-2 -2,-2H12l-2,-2z',
    'folder_open': 'M20,6h-8l-2,-2H4C2.9,4 2,4.9 2,6v12c0,1.1 0.9,2 2,2h16c0.85,0 1.61,-0.54 1.89,-1.34L24,12c0.37,-1.12 -0.46,-2.28 -1.64,-2.28H6.5L5.7,12H22l-2,6H4V6h16z',
    'heart': 'M12,21.35l-1.45,-1.32C5.4,15.36 2,12.28 2,8.5 2,5.42 4.42,3 7.5,3c1.74,0 3.41,0.81 4.5,2.09C13.09,3.81 14.76,3 16.5,3 19.58,3 22,5.42 22,8.5c0,3.78 -3.4,6.86 -8.55,11.54L12,21.35z',
    'home': 'M10,20v-6h4v6h5v-8h3L12,3 2,12h3v8z',
    'image': 'M21,19V5c0,-1.1 -0.9,-2 -2,-2H5C3.9,3 3,3.9 3,5v14c0,1.1 0.9,2 2,2h14c1.1,0 2,-0.9 2,-2zM8.5,11.5 11,14.51 14.5,10 19,16H5l3.5,-4.5z',
    'inbox': 'M19,3H4.99c-1.1,0 -1.98,0.9 -1.98,2L3,19c0,1.1 0.89,2 1.99,2H19c1.1,0 2,-0.9 2,-2V5c0,-1.1 -0.9,-2 -2,-2zm0,12h-4c0,1.66 -1.35,3 -3,3s-3,-1.34 -3,-3H5V5h14v10z',
    'info': 'M12,2C6.48,2 2,6.48 2,12s4.48,10 10,10 10,-4.48 10,-10S17.52,2 12,2zm1,15h-2v-6h2v6zm0,-8h-2V7h2v2z',
    'list': 'M3,13h2v-2H3v2zm0,4h2v-2H3v2zm0,-8h2V7H3v2zm4,4h14v-2H7v2zm0,4h14v-2H7v2zM7,7v2h14V7H7z',
    'menu': 'M3,18h18v-2H3v2zm0,-5h18v-2H3v2zm0,-7v2h18V6H3z',
    'message': 'M20,2H4c-1.1,0 -1.99,0.9 -1.99,2L2,22l4,-4h14c1.1,0 2,-0.9 2,-2V4c0,-1.1 -0.9,-2 -2,-2zm-2,12H6v-2h12v2zm0,-3H6V9h12v2zm0,-3H6V6h12v2z',
    'more_vert': 'M12,8c1.1,0 2,-0.9 2,-2s-0.9,-2 -2,-2 -2,0.9 -2,2 0.9,2 2,2zm0,2c-1.1,0 -2,0.9 -2,2s0.9,2 2,2 2,-0.9 2,-2 -0.9,-2 -2,-2zm0,6c-1.1,0 -2,0.9 -2,2s0.9,2 2,2 2,-0.9 2,-2 -0.9,-2 -2,-2z',
    'music_off': 'M4.27,3 3,4.27 12.73,14H8v3.27C7.71,17.1 7.37,17 7,17c-1.1,0 -2,0.67 -2,1.5S5.9,20 7,20s2,-0.67 2,-1.5V16h5v-0.73L19.73,21 21,19.73 4.27,3zM14,8.18V6h5V4h-7v2.18L14,8.18z',
    'pause': 'M6,19h4V5H6v14zm8,-14v14h4V5h-4z',
    'person': 'M12,12c2.21,0 4,-1.79 4,-4s-1.79,-4 -4,-4 -4,1.79 -4,4 1.79,4 4,4zm0,2c-2.67,0 -8,1.34 -8,4v2h16v-2c0,-2.66 -5.33,-4 -8,-4z',
    'play_arrow': 'M8,5v14l11,-7z',
    'refresh': 'M12,4V1L8,5l4,4V6c3.31,0 6,2.69 6,6 0,1.01 -0.25,1.97 -0.69,2.8l1.46,1.46C19.54,15.03 20,13.57 20,12c0,-4.42 -3.58,-8 -8,-8zM12,18c-3.31,0 -6,-2.69 -6,-6 0,-1.01 0.25,-1.97 0.69,-2.8L5.23,7.74C4.46,8.97 4,10.43 4,12c0,4.42 3.58,8 8,8v3l4,-4 -4,-4v3z',
    'save': 'M17,3H5c-1.11,0 -2,0.9 -2,2v14c0,1.1 0.89,2 2,2h14c1.1,0 2,-0.9 2,-2V7l-4,-4zM12,19c-1.66,0 -3,-1.34 -3,-3s1.34,-3 3,-3 3,1.34 3,3 -1.34,3 -3,3zm3,-10H5V5h10v4z',
    'search': 'M15.5,14h-0.79l-0.28,-0.27C15.41,12.59 16,11.11 16,9.5 16,5.91 13.09,3 9.5,3S3,5.91 3,9.5 5.91,16 9.5,16c1.61,0 3.09,-0.59 4.23,-1.57l0.27,0.28v0.79l5,4.99L20.49,19l-4.99,-5zM9.5,14C7.01,14 5,11.99 5,9.5S7.01,5 9.5,5 14,7.01 14,9.5 11.99,14 9.5,14z',
    'settings': 'M19.14,12.94c0.04,-0.3 0.06,-0.61 0.06,-0.94 0,-0.32 -0.02,-0.64 -0.07,-0.94l2.03,-1.58c0.18,-0.14 0.23,-0.41 0.12,-0.61l-1.92,-3.32c-0.12,-0.22 -0.37,-0.29 -0.59,-0.22l-2.39,0.96c-0.5,-0.38 -1.03,-0.7 -1.62,-0.94L14.4,2.81c-0.04,-0.24 -0.24,-0.41 -0.48,-0.41h-3.84c-0.24,0 -0.43,0.17 -0.47,0.41L9.25,5.35C8.66,5.59 8.12,5.92 7.63,6.29L5.24,5.33c-0.22,-0.08 -0.47,0 -0.59,0.22L2.74,8.87C2.62,9.08 2.66,9.34 2.86,9.48l2.03,1.58C4.84,11.36 4.8,11.69 4.8,12s0.02,0.64 0.07,0.94l-2.03,1.58c-0.18,0.14 -0.23,0.41 -0.12,0.61l1.92,3.32c0.12,0.22 0.37,0.29 0.59,0.22l2.39,-0.96c0.5,0.38 1.03,0.7 1.62,0.94l0.36,2.54c0.05,0.24 0.24,0.41 0.48,0.41h3.84c0.24,0 0.44,-0.17 0.47,-0.41l0.36,-2.54c0.59,-0.24 1.13,-0.56 1.62,-0.94l2.39,0.96c0.22,0.08 0.47,0 0.59,-0.22l1.92,-3.32c0.12,-0.22 0.07,-0.47 -0.12,-0.61l-2.01,-1.58zM12,15.6c-1.98,0 -3.6,-1.62 -3.6,-3.6s1.62,-3.6 3.6,-3.6 3.6,1.62 3.6,3.6 -1.62,3.6 -3.6,3.6z',
    'star': 'M12,17.27L18.18,21l-1.64,-7.03L22,9.24l-7.19,-0.61L12,2 9.19,8.63 2,9.24l5.46,4.73L5.82,21z',
    'upload': 'M9,16h6v-6h4l-7,-7 -7,7h4v6zm-4,2v2h14v-2H5z',
    # Added when the two tables were merged: names that existed in only one
    # backend, plus the nine used by ApkPy's own examples and docs that had no
    # drawing anywhere and silently rendered as a circle.
    'attach_file': 'M16.5,6v11.5c0,2.21 -1.79,4 -4,4s-4,-1.79 -4,-4V5c0,-1.38 1.12,-2.5 2.5,-2.5s2.5,1.12 2.5,2.5v10.5c0,0.55 -0.45,1 -1,1s-1,-0.45 -1,-1V6H10v9.5c0,1.38 1.12,2.5 2.5,2.5s2.5,-1.12 2.5,-2.5V5c0,-2.21 -1.79,-4 -4,-4S7,2.79 7,5v12.5c0,3.04 2.46,5.5 5.5,5.5s5.5,-2.46 5.5,-5.5V6h-1.5z',
    'checklist': 'M22,7h-9v2h9V7zm0,8h-9v2h9v-2zM5.54,11L2,7.46l1.41,-1.41 2.12,2.12 4.24,-4.24 1.41,1.41L5.54,11zm0,8L2,15.46l1.41,-1.41 2.12,2.12 4.24,-4.24 1.41,1.41L5.54,19z',
    'delete_sweep': 'M15,16h4v2h-4v-2zm0,-8h7v2h-7V8zm0,4h6v2h-6v-2zM3,18c0,1.1 0.9,2 2,2h6c1.1,0 2,-0.9 2,-2V8H3v10zM14,5h-3l-1,-1H6L5,5H2v2h12V5z',
    'done_all': 'M18,7l-1.41,-1.41 -6.34,6.34 1.41,1.41L18,7zm4.24,-1.41L11.66,16.17 7.48,12l-1.41,1.41L11.66,19 23.66,7l-1.42,-1.41zM0.41,13.41L6,19l1.41,-1.41L1.83,12 0.41,13.41z',
    'error': 'M12,2C6.48,2 2,6.48 2,12s4.48,10 10,10 10,-4.48 10,-10S17.52,2 12,2zm1,15h-2v-2h2v2zm0,-4h-2V7h2v6z',
    'forward_media': 'M12,5V1l5,5 -5,5V7c-3.31,0 -6,2.69 -6,6s2.69,6 6,6 6,-2.69 6,-6h2c0,4.42 -3.58,8 -8,8s-8,-3.58 -8,-8 3.58,-8 8,-8z',
    'inventory': 'M19,2h-4.18C14.4,0.84 13.3,0 12,0c-1.3,0 -2.4,0.84 -2.82,2H5C3.9,2 3,2.9 3,4v16c0,1.1 0.9,2 2,2h14c1.1,0 2,-0.9 2,-2V4c0,-1.1 -0.9,-2 -2,-2zM12,2c0.55,0 1,0.45 1,1s-0.45,1 -1,1 -1,-0.45 -1,-1 0.45,-1 1,-1zM7,7h10v2H7V7zm0,4h10v2H7v-2zm0,4h7v2H7v-2z',
    'inventory_2': 'M20,2H4C3,2 2,2.9 2,4v3.01C2,7.73 2.43,8.35 3,8.7V20c0,1.1 1.1,2 2,2h14c0.9,0 2,-0.9 2,-2V8.7c0.57,-0.35 1,-0.97 1,-1.69V4c0,-1.1 -1,-2 -2,-2zM15,14H9v-2h6v2zm5,-8H4V4h16v2z',
    'library_music': 'M20,2H8C6.9,2 6,2.9 6,4v12c0,1.1 0.9,2 2,2h12c1.1,0 2,-0.9 2,-2V4c0,-1.1 -0.9,-2 -2,-2zm-2,5h-3v5.5c0,1.38 -1.12,2.5 -2.5,2.5S10,13.88 10,12.5s1.12,-2.5 2.5,-2.5c0.57,0 1.08,0.19 1.5,0.51V5h4v2zM4,6H2v14c0,1.1 0.9,2 2,2h14v-2H4V6z',
    'note_add': 'M14,2H6C4.9,2 4.01,2.9 4.01,4L4,20c0,1.1 0.89,2 1.99,2H18c1.1,0 2,-0.9 2,-2V8l-6,-6zm2,14h-3v3h-2v-3H8v-2h3v-3h2v3h3v2zm-3,-7V3.5L18.5,9H13z',
    'repeat': 'M7,7h10v3l4,-4 -4,-4v3H5v6h2V7zm10,10H7v-3l-4,4 4,4v-3h12v-6h-2v4z',
    'replay': 'M12,5V1L7,6l5,5V7c3.31,0 6,2.69 6,6s-2.69,6 -6,6 -6,-2.69 -6,-6H4c0,4.42 3.58,8 8,8s8,-3.58 8,-8 -3.58,-8 -8,-8z',
    'shuffle': 'M10.59,9.17L5.41,4 4,5.41l5.17,5.17 1.42,-1.41zM14.5,4l2.04,2.04L4,18.59 5.41,20 17.96,7.46 20,9.5V4h-5.5zm0.33,9.41l-1.41,1.41 3.13,3.13L14.5,20H20v-5.5l-2.04,2.04 -3.13,-3.13z',
    'skip_next': 'M6,18l8.5,-6L6,6v12zM16,6v12h2V6h-2z',
    'skip_previous': 'M6,6h2v12H6V6zm3.5,6l8.5,6V6l-8.5,6z',
    'volume_off': 'M16.5,12c0,-1.77 -1.02,-3.29 -2.5,-4.03v2.21l2.45,2.45c0.03,-0.2 0.05,-0.41 0.05,-0.63zm2.5,0c0,0.94 -0.2,1.82 -0.54,2.64l1.51,1.51C20.63,14.91 21,13.5 21,12c0,-4.28 -2.99,-7.86 -7,-8.77v2.06c2.89,0.86 5,3.54 5,6.71zM4.27,3L3,4.27 7.73,9H3v6h4l5,5v-6.73l4.25,4.25c-0.67,0.52 -1.42,0.93 -2.25,1.18v2.06c1.38,-0.31 2.63,-0.95 3.69,-1.81L19.73,21 21,19.73l-9,-9L4.27,3zM12,4L9.91,6.09 12,8.18V4z',
    'warning': 'M1,21h22L12,2 1,21zm12,-3h-2v-2h2v2zm0,-4h-2v-4h2v4z',

    # Composer: the controls a chat-style input bar needs -- record, send,
    # stop, the mode chip, the disclosure chevrons and copy-to-clipboard.
    'mic': 'M12,14c1.66,0 3,-1.34 3,-3V5c0,-1.66 -1.34,-3 -3,-3S9,3.34 9,5v6c0,1.66 1.34,3 3,3zm5,-3c0,2.76 -2.24,5 -5,5s-5,-2.24 -5,-5H5c0,3.53 2.61,6.43 6,6.92V22h2v-3.08c3.39,-0.49 6,-3.39 6,-6.92h-2z',
    'send': 'M2.01,21L23,12 2.01,3 2,10l15,2 -15,2z',
    'stop': 'M8,6h8c1.1,0 2,0.9 2,2v8c0,1.1 -0.9,2 -2,2H8c-1.1,0 -2,-0.9 -2,-2V8c0,-1.1 0.9,-2 2,-2z',
    'bolt': 'M11,21h-1l1,-7H7.5c-0.58,0 -0.57,-0.32 -0.38,-0.66c0.19,-0.34 0.05,-0.08 0.07,-0.12C8.48,10.94 10.42,7.54 13,3h1l-1,7h3.5c0.49,0 0.56,0.33 0.47,0.51l-0.07,0.15C12.96,17.55 11,21 11,21z',
    'expand_more': 'M16.59,8.59L12,13.17 7.41,8.59 6,10l6,6 6,-6z',
    'expand_less': 'M12,8l-6,6 1.41,1.41L12,10.83l4.59,4.58L18,14z',
    # The sideways pair. chevron_right is what tells a settings row that
    # tapping it opens something, and nothing else in the catalogue says it.
    'chevron_right': 'M10,6L8.59,7.41 13.17,12l-4.58,4.59L10,18l6,-6z',
    'chevron_left': 'M15.41,7.41L14,6l-6,6 6,6 1.41,-1.41L10.83,12z',
    # Radio and links: the pair an app that talks to hardware reaches for.
    'bluetooth': 'M17.71,7.71L12,2h-1v7.59L6.41,5 5,6.41 10.59,12 5,17.59 6.41,19 11,14.41V22h1l5.71,-5.71 -4.3,-4.29 4.3,-4.29zM13,5.83l1.88,1.88L13,9.59V5.83zm1.88,10.46L13,18.17v-3.76l1.88,1.88z',
    'link': 'M3.9,12c0,-1.71 1.39,-3.1 3.1,-3.1h4V7H7c-2.76,0 -5,2.24 -5,5s2.24,5 5,5h4v-1.9H7c-1.71,0 -3.1,-1.39 -3.1,-3.1zM8,13h8v-2H8v2zm9,-6h-4v1.9h4c1.71,0 3.1,1.39 3.1,3.1s-1.39,3.1 -3.1,3.1h-4V17h4c2.76,0 5,-2.24 5,-5s-2.24,-5 -5,-5z',
    # Identity: the fingerprint the biometric prompt draws, and the pair a
    # locked screen needs. `fingerprint` is a stroke glyph on purpose --
    # Material draws it as line work at every size, and a filled blob at
    # 48dp reads as a smudge.
    'fingerprint': 'M17.81,4.47c-0.08,0 -0.16,-0.02 -0.23,-0.06C15.66,3.42 14,3 12.01,3c-1.98,0 -3.86,0.47 -5.57,1.41 -0.24,0.13 -0.54,0.04 -0.68,-0.2 -0.13,-0.24 -0.04,-0.55 0.2,-0.68C7.82,2.52 9.86,2 12.01,2c2.13,0 3.99,0.47 6.03,1.52 0.25,0.13 0.34,0.43 0.21,0.67 -0.09,0.18 -0.26,0.28 -0.44,0.28zM3.5,9.72c-0.1,0 -0.2,-0.03 -0.29,-0.09 -0.23,-0.16 -0.28,-0.47 -0.12,-0.7 0.99,-1.4 2.25,-2.5 3.75,-3.27C10,4.05 14,4.04 17.15,5.65c1.5,0.77 2.76,1.86 3.75,3.25 0.16,0.22 0.11,0.54 -0.12,0.7 -0.23,0.16 -0.54,0.11 -0.7,-0.12 -0.9,-1.26 -2.04,-2.25 -3.39,-2.94 -2.87,-1.47 -6.54,-1.47 -9.4,0.01 -1.36,0.7 -2.5,1.7 -3.4,2.96 -0.08,0.14 -0.23,0.21 -0.39,0.21zM9.75,21.79c-0.13,0 -0.26,-0.05 -0.35,-0.15 -0.87,-0.87 -1.34,-1.43 -2.01,-2.64 -0.69,-1.23 -1.05,-2.73 -1.05,-4.34 0,-2.97 2.54,-5.39 5.66,-5.39s5.66,2.42 5.66,5.39c0,0.28 -0.22,0.5 -0.5,0.5s-0.5,-0.22 -0.5,-0.5c0,-2.42 -2.09,-4.39 -4.66,-4.39 -2.57,0 -4.66,1.97 -4.66,4.39 0,1.44 0.32,2.77 0.93,3.85 0.64,1.15 1.08,1.64 1.85,2.42 0.19,0.2 0.19,0.51 0,0.71 -0.11,0.1 -0.24,0.15 -0.37,0.15zM16.92,19.94c-1.19,0 -2.24,-0.3 -3.1,-0.89 -1.49,-1.01 -2.38,-2.65 -2.38,-4.39 0,-0.28 0.22,-0.5 0.5,-0.5s0.5,0.22 0.5,0.5c0,1.41 0.72,2.74 1.94,3.56 0.71,0.48 1.54,0.71 2.54,0.71 0.24,0 0.64,-0.03 1.04,-0.1 0.27,-0.05 0.53,0.13 0.58,0.41 0.05,0.27 -0.13,0.53 -0.41,0.58 -0.57,0.11 -1.07,0.12 -1.21,0.12zM14.91,22c-0.04,0 -0.09,-0.01 -0.13,-0.02 -1.59,-0.44 -2.63,-1.03 -3.72,-2.1 -1.4,-1.39 -2.17,-3.24 -2.17,-5.22 0,-1.62 1.38,-2.94 3.08,-2.94 1.7,0 3.08,1.32 3.08,2.94 0,1.07 0.93,1.94 2.08,1.94s2.08,-0.87 2.08,-1.94c0,-3.77 -3.25,-6.83 -7.25,-6.83 -2.84,0 -5.44,1.58 -6.61,4.03 -0.39,0.81 -0.59,1.76 -0.59,2.8 0,0.78 0.07,2.01 0.67,3.61 0.1,0.26 -0.03,0.55 -0.29,0.64 -0.26,0.1 -0.55,-0.04 -0.64,-0.29 -0.49,-1.31 -0.73,-2.61 -0.73,-3.96 0,-1.2 0.23,-2.29 0.68,-3.24 1.33,-2.79 4.28,-4.6 7.51,-4.6 4.55,0 8.25,3.51 8.25,7.83 0,1.62 -1.38,2.94 -3.08,2.94s-3.08,-1.32 -3.08,-2.94c0,-1.07 -0.93,-1.94 -2.08,-1.94s-2.08,0.87 -2.08,1.94c0,1.71 0.66,3.31 1.87,4.51 0.95,0.94 1.86,1.46 3.27,1.85 0.27,0.07 0.42,0.35 0.35,0.61 -0.05,0.23 -0.26,0.38 -0.47,0.38z',
    'lock': 'M18,8h-1V6c0,-2.76 -2.24,-5 -5,-5S7,3.24 7,6v2H6c-1.1,0 -2,0.9 -2,2v10c0,1.1 0.9,2 2,2h12c1.1,0 2,-0.9 2,-2V10c0,-1.1 -0.9,-2 -2,-2zM12,17c-1.1,0 -2,-0.9 -2,-2s0.9,-2 2,-2 2,0.9 2,2 -0.9,2 -2,2zM15.1,8H8.9V6c0,-1.71 1.39,-3.1 3.1,-3.1 1.71,0 3.1,1.39 3.1,3.1v2z',
    'lock_open': 'M18,8h-1V6c0,-2.76 -2.24,-5 -5,-5S7,3.24 7,6h1.9c0,-1.71 1.39,-3.1 3.1,-3.1 1.71,0 3.1,1.39 3.1,3.1v2H6c-1.1,0 -2,0.9 -2,2v10c0,1.1 0.9,2 2,2h12c1.1,0 2,-0.9 2,-2V10c0,-1.1 -0.9,-2 -2,-2zM12,17c-1.1,0 -2,-0.9 -2,-2s0.9,-2 2,-2 2,0.9 2,2 -0.9,2 -2,2z',
    'content_copy': 'M16,1H4C2.9,1 2,1.9 2,3v14h2V3h12V1zm3,4H8C6.9,5 6,5.9 6,7v14c0,1.1 0.9,2 2,2h11c1.1,0 2,-0.9 2,-2V7c0,-1.1 -0.9,-2 -2,-2zm0,16H8V7h11v14z',
}


_ICON_PATHS_OUTLINED = {
    # Outlined variants, for the inactive state of a navigation item.
    # Only the names a bottom bar realistically uses: anything without a
    # variant falls back to the filled path, so the active indicator still
    # carries the state on its own.
    'bell': 'M12,6.5c2.49,0 4,2.02 4,4.5v6H8v-6c0,-2.48 1.51,-4.5 4,-4.5M12,2c-0.83,0 -1.5,0.67 -1.5,1.5v0.68C7.63,4.86 6,7.29 6,11v6l-2,2v1h16v-1l-2,-2v-6c0,-3.71 -1.63,-6.14 -4.5,-6.82V3.5C13.5,2.67 12.83,2 12,2zM12,22c1.1,0 2,-0.9 2,-2h-4c0,1.1 0.9,2 2,2z',
    'camera': 'M20,4h-3.17l-1.24,-1.35C15.22,2.24 14.68,2 14.12,2H9.88c-0.56,0 -1.1,0.24 -1.48,0.65L7.17,4H4C2.9,4 2,4.9 2,6v12c0,1.1 0.9,2 2,2h16c1.1,0 2,-0.9 2,-2V6c0,-1.1 -0.9,-2 -2,-2zm0,14H4V6h4.05l1.83,-2h4.24l1.83,2H20v12zM12,7c-2.76,0 -5,2.24 -5,5s2.24,5 5,5 5,-2.24 5,-5 -2.24,-5 -5,-5zm0,8c-1.65,0 -3,-1.35 -3,-3s1.35,-3 3,-3 3,1.35 3,3 -1.35,3 -3,3z',
    'description': 'M14,2H6C4.9,2 4,2.9 4,4v16c0,1.1 0.89,2 1.99,2H18c1.1,0 2,-0.9 2,-2V8l-6,-6zM6,20V4h7v5h5v11H6zM8,16h8v2H8v-2zm0,-4h8v2H8v-2z',
    'folder': 'M9.17,6l2,2H20v10H4V6h5.17M10,4H4C2.9,4 2.01,4.9 2.01,6L2,18c0,1.1 0.9,2 2,2h16c1.1,0 2,-0.9 2,-2V8c0,-1.1 -0.9,-2 -2,-2h-8l-2,-2z',
    'heart': 'M16.5,5c1.54,0 3,1.24 3,3.5 0,2.89 -2.94,5.63 -7.5,9.71C7.94,14.13 5,11.39 5,8.5 5,6.24 6.46,5 8,5c1.13,0 2.23,0.72 2.62,1.72h1.77C12.77,5.72 13.87,5 15,5h1.5m0,-2c-1.74,0 -3.41,0.81 -4.5,2.09C10.91,3.81 9.24,3 7.5,3 4.42,3 2,5.42 2,8.5c0,3.78 3.4,6.86 8.55,11.54L12,21.35l1.45,-1.32C18.6,15.36 22,12.28 22,8.5 22,5.42 19.58,3 16.5,3z',
    'home': 'M12,5.69l5,4.5V18h-2v-6H9v6H7v-7.81l5,-4.5M12,3L2,12h3v8h6v-6h2v6h6v-8h3L12,3z',
    'image': 'M19,5v14H5V5h14m0,-2H5C3.9,3 3,3.9 3,5v14c0,1.1 0.9,2 2,2h14c1.1,0 2,-0.9 2,-2V5c0,-1.1 -0.9,-2 -2,-2zm-4.86,8.86l-3,3.87L9,13.14 6,17h12l-3.86,-5.14z',
    'inventory_2': 'M20,2H4C3,2 2,2.9 2,4v3.01C2,7.73 2.43,8.35 3,8.7V20c0,1.1 1.1,2 2,2h14c0.9,0 2,-0.9 2,-2V8.7c0.57,-0.35 1,-0.97 1,-1.69V4C22,2.9 21,2 20,2zM19,20H5V9h14V20zM20,7H4V4h16V7z M9,12h6v2H9V12z',
    'library_music': 'M20,2H8C6.9,2 6,2.9 6,4v12c0,1.1 0.9,2 2,2h12c1.1,0 2,-0.9 2,-2V4C22,2.9 21.1,2 20,2zM20,16H8V4h12V16zM4,6H2v14c0,1.1 0.9,2 2,2h14v-2H4V6zM14,15c1.1,0 2,-0.9 2,-2V7h2V5h-4v6.5C13.71,11.19 13.13,11 12.5,11c-1.38,0 -2.5,0.9 -2.5,2s1.12,2 2.5,2H14z',
    'message': 'M20,4v13.17L18.83,16H4V4h16m0,-2H4C2.9,2 2.01,2.9 2.01,4L2,22l4,-4h14c1.1,0 2,-0.9 2,-2V4c0,-1.1 -0.9,-2 -2,-2zM6,12h12v2H6v-2zm0,-3h12v2H6V9zm0,-3h12v2H6V6z',
    'person': 'M12,6c1.1,0 2,0.9 2,2s-0.9,2 -2,2 -2,-0.9 -2,-2 0.9,-2 2,-2m0,10c2.7,0 5.8,1.29 6,2H6c0.23,-0.72 3.31,-2 6,-2m0,-12C9.79,4 8,5.79 8,8s1.79,4 4,4 4,-1.79 4,-4 -1.79,-4 -4,-4zm0,10c-2.67,0 -8,1.34 -8,4v2h16v-2c0,-2.66 -5.33,-4 -8,-4z',
    'settings': 'M19.43,12.98c0.04,-0.32 0.07,-0.64 0.07,-0.98s-0.03,-0.66 -0.07,-0.98l2.11,-1.65c0.19,-0.15 0.24,-0.42 0.12,-0.64l-2,-3.46c-0.09,-0.16 -0.26,-0.25 -0.44,-0.25 -0.06,0 -0.12,0.01 -0.17,0.03l-2.49,1c-0.52,-0.4 -1.08,-0.73 -1.69,-0.98l-0.38,-2.65C14.46,2.18 14.25,2 14,2h-4c-0.25,0 -0.46,0.18 -0.49,0.42l-0.38,2.65c-0.61,0.25 -1.17,0.59 -1.69,0.98l-2.49,-1c-0.06,-0.02 -0.12,-0.03 -0.18,-0.03 -0.17,0 -0.34,0.09 -0.43,0.25l-2,3.46c-0.13,0.22 -0.07,0.49 0.12,0.64l2.11,1.65c-0.04,0.32 -0.07,0.65 -0.07,0.98s0.03,0.66 0.07,0.98l-2.11,1.65c-0.19,0.15 -0.24,0.42 -0.12,0.64l2,3.46c0.09,0.16 0.26,0.25 0.44,0.25 0.06,0 0.12,-0.01 0.17,-0.03l2.49,-1c0.52,0.4 1.08,0.73 1.69,0.98l0.38,2.65c0.03,0.24 0.24,0.42 0.49,0.42h4c0.25,0 0.46,-0.18 0.49,-0.42l0.38,-2.65c0.61,-0.25 1.17,-0.59 1.69,-0.98l2.49,1c0.06,0.02 0.12,0.03 0.18,0.03 0.17,0 0.34,-0.09 0.43,-0.25l2,-3.46c0.12,-0.22 0.07,-0.49 -0.12,-0.64l-2.11,-1.65zM17.45,11.27c0.04,0.31 0.05,0.52 0.05,0.73 0,0.21 -0.02,0.43 -0.05,0.73l-0.14,1.13 0.89,0.7 1.08,0.84 -0.7,1.21 -1.27,-0.51 -1.04,-0.42 -0.9,0.68c-0.43,0.32 -0.84,0.56 -1.25,0.73l-1.06,0.43 -0.16,1.13 -0.2,1.35h-1.4l-0.19,-1.35 -0.16,-1.13 -1.06,-0.43c-0.43,-0.18 -0.83,-0.41 -1.23,-0.71l-0.91,-0.7 -1.06,0.43 -1.27,0.51 -0.7,-1.21 1.08,-0.84 0.89,-0.7 -0.14,-1.13c-0.03,-0.31 -0.05,-0.54 -0.05,-0.74s0.02,-0.43 0.05,-0.73l0.14,-1.13 -0.89,-0.7 -1.08,-0.84 0.7,-1.21 1.27,0.51 1.04,0.42 0.9,-0.68c0.43,-0.32 0.84,-0.56 1.25,-0.73l1.06,-0.43 0.16,-1.13 0.2,-1.35h1.39l0.19,1.35 0.16,1.13 1.06,0.43c0.43,0.18 0.83,0.41 1.23,0.71l0.91,0.7 1.06,-0.43 1.27,-0.51 0.7,1.21 -1.07,0.85 -0.89,0.7 0.14,1.13zM12,8c-2.21,0 -4,1.79 -4,4s1.79,4 4,4 4,-1.79 4,-4 -1.79,-4 -4,-4zm0,6c-1.1,0 -2,-0.9 -2,-2s0.9,-2 2,-2 2,0.9 2,2 -0.9,2 -2,2z',
    'star': 'M22,9.24l-7.19,-0.62L12,2 9.19,8.63 2,9.24l5.46,4.73L5.82,21 12,17.27 18.18,21l-1.63,-7.03L22,9.24zM12,15.4l-3.76,2.27 1,-4.28 -3.32,-2.88 4.38,-0.38L12,6.1l1.71,4.04 4.38,0.38 -3.32,2.88 1,4.28L12,15.4z',
}

_ALIASES = {
    'account': 'person',
    'alert': 'warning',
    'apps': 'list',
    'arrow_drop_down': 'expand_more',
    'arrow_drop_up': 'expand_less',
    'build': 'settings',
    'chevron_down': 'expand_more',
    'chevron_up': 'expand_less',
    'navigate_next': 'chevron_right',
    'navigate_before': 'chevron_left',
    'disclosure': 'chevron_right',
    'copy': 'content_copy',
    'favorite': 'heart',
    'biometrics': 'fingerprint',
    'serial': 'bluetooth',
    'pair': 'bluetooth',
    'touch_id': 'fingerprint',
    'unlock': 'lock_open',
    'flash': 'bolt',
    'lightning': 'bolt',
    'microphone': 'mic',
    'forward_10': 'forward_media',
    'forward_15': 'forward_media',
    'forward_30': 'forward_media',
    'library': 'list',
    'notifications': 'bell',
    'photo': 'image',
    'play': 'play_arrow',
    'profile': 'person',
    'replay_10': 'replay',
    'replay_5': 'replay',
    'retry': 'refresh',
    'submit': 'send',
    'trash': 'delete',
    'user': 'person',
    'voice': 'mic',
}

FALLBACK_ICON = 'circle'
FILLED_STYLE = 'filled'
OUTLINED_STYLE = 'outlined'


def names():
    """The curated names, sorted -- the short list the docs and AGENTS.md
    show. Every Material icon resolves too: see :func:`all_names`."""
    return tuple(sorted(_ICON_PATHS))


# --- The Material Icons set --------------------------------------------------
# The 71 names above were all an app could draw; a like button, a share or a
# chat bubble came out as a circle. icon_data/material_icons.json.gz holds the
# Material Icons, filled and outlined (Apache 2.0, see icon_data/NOTICE.txt),
# built by tools/build_icon_data.py. The curated table wins where both have a
# name, so no existing app changes.

_MATERIAL = [None]


def _material():
    if _MATERIAL[0] is None:
        import gzip
        import json
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'icon_data', 'material_icons.json.gz')
        try:
            with gzip.open(path, 'rb') as fh:
                _MATERIAL[0] = json.loads(fh.read().decode('utf-8'))
        except (OSError, ValueError):
            _MATERIAL[0] = {'f': {}, 'o': {}, 'tags': {}}
    return _MATERIAL[0]


def all_names():
    """Every name an ``icon=`` accepts: the curated ones and all of Material."""
    return tuple(sorted(set(_ICON_PATHS) | set(_material()['f'])))


def search(words, limit=12):
    """Material icon names whose name or tags contain every word."""
    wanted = [w.lower() for w in str(words or '').split() if w]
    tags = _material()['tags']
    found = []
    for name in all_names():
        text = name + ' ' + ' '.join(tags.get(name, ()))
        if all(w in text for w in wanted):
            found.append(name)
        if len(found) >= limit:
            break
    return found


def _normalise(name):
    key = str(name or '').strip().lower()
    return _ALIASES.get(key, key)


def has_outlined(name):
    """True when this icon ships an outlined variant."""
    key = _normalise(name)
    if key in _ICON_PATHS:
        return key in _ICON_PATHS_OUTLINED
    return key in _material()['o']


def resolve(name, style="filled"):
    """Path data for ``name``, or ``None`` when the catalogue has no such icon.

    ``style="outlined"`` returns the outline where one exists and the filled
    path otherwise -- a missing variant must not turn into a missing icon.

    Callers that need to *know* the name was wrong use this; callers that just
    need something to draw use :func:`path_for`.
    """
    key = _normalise(name)
    if key in _ICON_PATHS:
        if style == "outlined" and key in _ICON_PATHS_OUTLINED:
            return _ICON_PATHS_OUTLINED[key]
        return _ICON_PATHS[key]
    material = _material()
    if style == "outlined" and key in material['o']:
        return material['o'][key]
    return material['f'].get(key)


def path_for(name, style="filled"):
    """Path data for ``name``, falling back to ``circle`` like the old tables."""
    resolved = resolve(name, style)
    return resolved if resolved is not None else _ICON_PATHS[FALLBACK_ICON]


def suggest(name):
    """Closest catalogue name, or ``None`` when nothing is close enough."""
    import difflib
    matches = difflib.get_close_matches(
        _normalise(name), list(all_names()), n=1, cutoff=0.55,
    )
    return matches[0] if matches else None


# --- Path data -> geometry --------------------------------------------------

_COMMANDS = 'MmLlHhVvCcSsQqTtAaZz'
_ARG_COUNT = {'M': 2, 'L': 2, 'H': 1, 'V': 1, 'C': 6, 'S': 4,
              'Q': 4, 'T': 2, 'A': 7, 'Z': 0}


def _tokenise(data):
    out = []
    index = 0
    total = len(data)
    while index < total:
        char = data[index]
        if char in _COMMANDS:
            out.append(char)
            index += 1
        elif char in ' ,\t\r\n':
            index += 1
        else:
            end = index
            if data[end] in '+-':
                end += 1
            seen_dot = seen_exp = False
            while end < total:
                current = data[end]
                if current.isdigit():
                    end += 1
                elif current == '.' and not seen_dot and not seen_exp:
                    seen_dot = True
                    end += 1
                elif current in 'eE' and not seen_exp and end > index:
                    seen_exp = True
                    end += 1
                    if end < total and data[end] in '+-':
                        end += 1
                else:
                    break
            if end == index:
                raise ValueError(
                    "icon path data has an unexpected character %r" % char)
            out.append(float(data[index:end]))
            index = end
    return out


def _cubic(p0, p1, p2, p3, segments):
    points = []
    for step in range(1, segments + 1):
        t = float(step) / segments
        mt = 1.0 - t
        a, b = mt * mt * mt, 3.0 * mt * mt * t
        c, d = 3.0 * mt * t * t, t * t * t
        points.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                       a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return points


def _elliptical_arc(x0, y0, rx, ry, phi, large, sweep, x1, y1, segments):
    """SVG ``A`` command, endpoint -> centre parameterisation (spec F.6.5).

    Arcs never appear in the built-in catalogue, but SVG exported from Figma or
    Illustrator uses them constantly, so ``load_svg`` needs them.
    """
    if rx == 0 or ry == 0 or (x0 == x1 and y0 == y1):
        return [(x1, y1)]
    rx, ry = abs(rx), abs(ry)
    radians = math.radians(phi)
    cos_phi, sin_phi = math.cos(radians), math.sin(radians)
    dx, dy = (x0 - x1) / 2.0, (y0 - y1) / 2.0
    x1p = cos_phi * dx + sin_phi * dy
    y1p = -sin_phi * dx + cos_phi * dy
    scale_check = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if scale_check > 1:
        stretch = math.sqrt(scale_check)
        rx *= stretch
        ry *= stretch
    numerator = (rx * rx * ry * ry - rx * rx * y1p * y1p
                 - ry * ry * x1p * x1p)
    denominator = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    factor = math.sqrt(max(0.0, numerator / denominator)) if denominator else 0.0
    if large == sweep:
        factor = -factor
    cxp = factor * rx * y1p / ry
    cyp = -factor * ry * x1p / rx
    cx = cos_phi * cxp - sin_phi * cyp + (x0 + x1) / 2.0
    cy = sin_phi * cxp + cos_phi * cyp + (y0 + y1) / 2.0
    theta1 = math.atan2((y1p - cyp) / ry, (x1p - cxp) / rx)
    theta2 = math.atan2((-y1p - cyp) / ry, (-x1p - cxp) / rx)
    delta = theta2 - theta1
    if not sweep and delta > 0:
        delta -= 2 * math.pi
    elif sweep and delta < 0:
        delta += 2 * math.pi
    steps = max(2, int(segments * abs(delta) / math.pi))
    points = []
    for step in range(1, steps + 1):
        angle = theta1 + delta * step / steps
        ex, ey = math.cos(angle) * rx, math.sin(angle) * ry
        points.append((cos_phi * ex - sin_phi * ey + cx,
                       sin_phi * ex + cos_phi * ey + cy))
    return points


def flatten(path_data, segments=16):
    """Path data -> list of subpaths, each a list of ``(x, y)`` points.

    Curves become polylines.  Both backends consume the same output, so the
    Previewer and the phone are drawing the same geometry by construction.
    """
    tokens = _tokenise(str(path_data))
    subpaths = []
    current = []
    x = y = start_x = start_y = 0.0
    command = None
    last_cubic = last_quad = None
    index = 0
    while index < len(tokens):
        if isinstance(tokens[index], str):
            command = tokens[index]
            index += 1
            if command in 'Zz':
                if len(current) > 1:
                    current.append((start_x, start_y))
                    subpaths.append(current)
                current = []
                x, y = start_x, start_y
                last_cubic = last_quad = None
                continue
        elif command is None:
            raise ValueError("icon path data starts without a command")
        elif command == 'M':
            command = 'L'          # repeated M coordinates are implicit L
        elif command == 'm':
            command = 'l'
        upper = command.upper()
        relative = command.islower()
        needed = _ARG_COUNT[upper]
        args = tokens[index:index + needed]
        if len(args) < needed or any(isinstance(a, str) for a in args):
            raise ValueError(
                "icon path data is missing arguments for %r" % command)
        index += needed
        if upper == 'M':
            if len(current) > 1:
                subpaths.append(current)
            x = x + args[0] if relative else args[0]
            y = y + args[1] if relative else args[1]
            start_x, start_y = x, y
            current = [(x, y)]
            last_cubic = last_quad = None
        elif upper == 'L':
            x = x + args[0] if relative else args[0]
            y = y + args[1] if relative else args[1]
            current.append((x, y))
            last_cubic = last_quad = None
        elif upper == 'H':
            x = x + args[0] if relative else args[0]
            current.append((x, y))
            last_cubic = last_quad = None
        elif upper == 'V':
            y = y + args[0] if relative else args[0]
            current.append((x, y))
            last_cubic = last_quad = None
        elif upper in ('C', 'S'):
            if upper == 'C':
                c1 = (x + args[0], y + args[1]) if relative else (args[0], args[1])
                c2 = (x + args[2], y + args[3]) if relative else (args[2], args[3])
                end = (x + args[4], y + args[5]) if relative else (args[4], args[5])
            else:
                c1 = ((2 * x - last_cubic[0], 2 * y - last_cubic[1])
                      if last_cubic else (x, y))
                c2 = (x + args[0], y + args[1]) if relative else (args[0], args[1])
                end = (x + args[2], y + args[3]) if relative else (args[2], args[3])
            current.extend(_cubic((x, y), c1, c2, end, segments))
            x, y = end
            last_cubic, last_quad = c2, None
        elif upper in ('Q', 'T'):
            if upper == 'Q':
                control = (x + args[0], y + args[1]) if relative else (args[0], args[1])
                end = (x + args[2], y + args[3]) if relative else (args[2], args[3])
            else:
                control = ((2 * x - last_quad[0], 2 * y - last_quad[1])
                           if last_quad else (x, y))
                end = (x + args[0], y + args[1]) if relative else (args[0], args[1])
            # Quadratic -> cubic, so one flattener covers both.
            c1 = (x + 2.0 / 3.0 * (control[0] - x), y + 2.0 / 3.0 * (control[1] - y))
            c2 = (end[0] + 2.0 / 3.0 * (control[0] - end[0]),
                  end[1] + 2.0 / 3.0 * (control[1] - end[1]))
            current.extend(_cubic((x, y), c1, c2, end, segments))
            x, y = end
            last_quad, last_cubic = control, None
        elif upper == 'A':
            end_x = x + args[5] if relative else args[5]
            end_y = y + args[6] if relative else args[6]
            current.extend(_elliptical_arc(
                x, y, args[0], args[1], args[2],
                int(args[3]), int(args[4]), end_x, end_y, segments))
            x, y = end_x, end_y
            last_cubic = last_quad = None
    if len(current) > 1:
        subpaths.append(current)
    return [sub for sub in subpaths if len(sub) > 2]


def rasterize(subpaths, size, supersample=4, viewport=ICON_VIEWPORT):
    """Coverage mask: ``size * size`` alpha bytes, nonZero fill rule.

    Scanline with a winding number: a point is inside when the number of turns
    is not zero.  This is what Android does, and unlike even-odd it does not
    punch a false hole where two subpaths overlap in the same direction.

    Supersampling and box-averaging the result is what produces the antialiased
    edge; the Tk canvas polygons this replaced had none, which is why the old
    icons looked jagged whatever the geometry was.
    """
    size = int(size)
    supersample = max(1, int(supersample))
    if size <= 0:
        return bytearray()
    high = size * supersample
    scale = float(high) / float(viewport)

    edges = []
    for subpath in subpaths:
        points = [(px * scale, py * scale) for px, py in subpath]
        if points[0] != points[-1]:
            points.append(points[0])
        for i in range(len(points) - 1):
            x0, y0 = points[i]
            x1, y1 = points[i + 1]
            if y0 == y1:
                continue
            edges.append((min(y0, y1), max(y0, y1), y0, x0,
                          (x1 - x0) / (y1 - y0), 1 if y1 > y0 else -1))
    if not edges:
        return bytearray(size * size)

    coverage = [0] * (high * high)
    for row in range(high):
        centre = row + 0.5
        crossings = []
        for low, high_y, y0, x0, slope, winding in edges:
            if low <= centre < high_y:
                crossings.append((x0 + (centre - y0) * slope, winding))
        if not crossings:
            continue
        crossings.sort()
        winding_total = 0
        base = row * high
        for i in range(len(crossings) - 1):
            winding_total += crossings[i][1]
            if winding_total == 0:
                continue
            left = max(0, int(math.ceil(crossings[i][0] - 0.5)))
            right = min(high - 1, int(math.floor(crossings[i + 1][0] - 0.5)))
            for column in range(left, right + 1):
                coverage[base + column] = 255

    out = bytearray(size * size)
    area = supersample * supersample
    for oy in range(size):
        for ox in range(size):
            total = 0
            for dy in range(supersample):
                base = (oy * supersample + dy) * high + ox * supersample
                for dx in range(supersample):
                    total += coverage[base + dx]
            out[oy * size + ox] = total // area
    return out


def _number(value):
    text = '%.2f' % value
    if text.endswith('.00'):
        return text[:-3]
    return text.rstrip('0').rstrip('.') if '.' in text else text


def to_path_data(subpaths, epsilon=0.02):
    """Flattened geometry -> path data, dropping points on a straight run.

    User SVG is emitted to Android this way: the phone then draws exactly the
    points the Previewer drew, so parity holds by construction even when the
    source used arcs or a transform.
    """
    parts = []
    for subpath in subpaths:
        points = list(subpath)
        if len(points) > 2 and points[0] == points[-1]:
            points.pop()
        if len(points) < 3:
            continue
        kept = [points[0]]
        for index in range(1, len(points) - 1):
            ax, ay = kept[-1]
            bx, by = points[index]
            cx, cy = points[index + 1]
            cross = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
            if abs(cross) > epsilon:
                kept.append((bx, by))
        kept.append(points[-1])
        parts.append('M' + 'L'.join(
            '%s,%s' % (_number(px), _number(py)) for px, py in kept) + 'Z')
    return ''.join(parts)


# --- User supplied SVG ------------------------------------------------------

_SVG_NS = '{http://www.w3.org/2000/svg}'
_TRANSFORM_RE = re.compile(r'(\w+)\s*\(([^)]*)\)')
_STROKE_ONLY = re.compile(r'stroke\s*[:=]', re.IGNORECASE)


def is_file_reference(value):
    """True when ``icon=`` names a file rather than a catalogue entry."""
    text = str(value or '').strip()
    if not text:
        return False
    return text.lower().endswith('.svg') or '/' in text or '\\' in text


def _matrix_multiply(m, n):
    return (m[0] * n[0] + m[2] * n[1], m[1] * n[0] + m[3] * n[1],
            m[0] * n[2] + m[2] * n[3], m[1] * n[2] + m[3] * n[3],
            m[0] * n[4] + m[2] * n[5] + m[4],
            m[1] * n[4] + m[3] * n[5] + m[5])


def _parse_transform(text):
    matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for name, raw in _TRANSFORM_RE.findall(text or ''):
        values = [float(v) for v in re.split(r'[\s,]+', raw.strip()) if v]
        if name == 'translate':
            step = (1.0, 0.0, 0.0, 1.0, values[0],
                    values[1] if len(values) > 1 else 0.0)
        elif name == 'scale':
            sx = values[0]
            step = (sx, 0.0, 0.0, values[1] if len(values) > 1 else sx, 0.0, 0.0)
        elif name == 'rotate':
            angle = math.radians(values[0])
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            step = (cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0)
            if len(values) >= 3:
                cx, cy = values[1], values[2]
                step = _matrix_multiply(
                    (1.0, 0.0, 0.0, 1.0, cx, cy),
                    _matrix_multiply(step, (1.0, 0.0, 0.0, 1.0, -cx, -cy)))
        elif name == 'matrix' and len(values) >= 6:
            step = tuple(values[:6])
        elif name == 'skewX':
            step = (1.0, 0.0, math.tan(math.radians(values[0])), 1.0, 0.0, 0.0)
        elif name == 'skewY':
            step = (1.0, math.tan(math.radians(values[0])), 0.0, 1.0, 0.0, 0.0)
        else:
            continue
        matrix = _matrix_multiply(matrix, step)
    return matrix


def _apply(matrix, point):
    x, y = point
    return (matrix[0] * x + matrix[2] * y + matrix[4],
            matrix[1] * x + matrix[3] * y + matrix[5])


def _signed_area(points):
    total = 0.0
    for index in range(len(points) - 1):
        x0, y0 = points[index]
        x1, y1 = points[index + 1]
        total += x0 * y1 - x1 * y0
    return total / 2.0


def _fill_from_style(style):
    found = re.search(r'fill\s*:\s*([^;]+)', style or '', re.IGNORECASE)
    return found.group(1).strip().lower() if found else ''


def _resolve_two_tone(entries):
    """Shapes painted in a second colour become cut-outs, not extra ink.

    An icon is a single-colour silhouette, but designers routinely fake a hole
    by painting a white shape *on top* of a dark one -- correct in a browser,
    which paints in order, and meaningless once everything collapses to one
    colour.  Merging them would swallow the detail: the ``+`` inside a shopping
    cart simply vanishes into the basket.

    So the first fill encountered is the ink, and every other fill is
    subtracted by forcing its winding opposite to the ink's.
    """
    if not entries:
        return []
    ink = entries[0][1]
    body = [points for points, fill in entries if fill == ink]
    reference = max(body, key=lambda pts: abs(_signed_area(pts))) if body else None
    ink_sign = _signed_area(reference) >= 0 if reference is not None else True

    resolved = []
    for points, fill in entries:
        if fill != ink and (_signed_area(points) >= 0) == ink_sign:
            points = list(reversed(points))
        resolved.append(points)
    return resolved


def _float_attr(element, name, default=0.0):
    raw = element.get(name)
    if raw is None:
        return default
    try:
        return float(re.sub(r'[a-zA-Z%]+$', '', raw.strip()) or default)
    except ValueError:
        return default


def _shape_to_path(element, tag):
    """The four shapes Figma and Illustrator actually emit, plus polygon."""
    if tag == 'rect':
        x, y = _float_attr(element, 'x'), _float_attr(element, 'y')
        width = _float_attr(element, 'width')
        height = _float_attr(element, 'height')
        if width <= 0 or height <= 0:
            return ''
        rx = _float_attr(element, 'rx', _float_attr(element, 'ry'))
        ry = _float_attr(element, 'ry', rx)
        rx, ry = min(rx, width / 2.0), min(ry, height / 2.0)
        if rx <= 0 or ry <= 0:
            return 'M%g,%gH%gV%gH%gZ' % (x, y, x + width, y + height, x)
        return ('M%g,%gH%gA%g,%g 0 0 1 %g,%gV%gA%g,%g 0 0 1 %g,%gH%g'
                'A%g,%g 0 0 1 %g,%gV%gA%g,%g 0 0 1 %g,%gZ' % (
                    x + rx, y, x + width - rx,
                    rx, ry, x + width, y + ry,
                    y + height - ry, rx, ry, x + width - rx, y + height,
                    x + rx, rx, ry, x, y + height - ry,
                    y + ry, rx, ry, x + rx, y))
    if tag in ('circle', 'ellipse'):
        cx, cy = _float_attr(element, 'cx'), _float_attr(element, 'cy')
        if tag == 'circle':
            rx = ry = _float_attr(element, 'r')
        else:
            rx, ry = _float_attr(element, 'rx'), _float_attr(element, 'ry')
        if rx <= 0 or ry <= 0:
            return ''
        return ('M%g,%gA%g,%g 0 1 0 %g,%gA%g,%g 0 1 0 %g,%gZ'
                % (cx - rx, cy, rx, ry, cx + rx, cy, rx, ry, cx - rx, cy))
    if tag == 'polygon':
        raw = (element.get('points') or '').strip()
        values = [v for v in re.split(r'[\s,]+', raw) if v]
        if len(values) < 6:
            return ''
        pairs = ['%s,%s' % (values[i], values[i + 1])
                 for i in range(0, len(values) - 1, 2)]
        return 'M' + 'L'.join(pairs) + 'Z'
    return ''


def load_svg(path, base_dir=None, segments=10):
    """Read a user ``.svg`` and normalise it to path data in a 24x24 viewport.

    The result is a single-colour silhouette: the icon is tinted by the theme
    (Android's ``itemIconTint`` forces one colour on the bottom bar anyway), so
    per-shape fills in the source are not preserved.
    """
    import xml.etree.ElementTree as ElementTree

    resolved = str(path)
    if base_dir and not os.path.isabs(resolved):
        resolved = os.path.join(str(base_dir), resolved)
    if not os.path.exists(resolved):
        raise ValueError("icon file not found: %s" % path)
    try:
        root = ElementTree.parse(resolved).getroot()
    except ElementTree.ParseError as error:
        raise ValueError("icon file is not valid SVG: %s (%s)" % (path, error))

    view_box = (root.get('viewBox') or '').strip()
    if view_box:
        parts = [float(v) for v in re.split(r'[\s,]+', view_box) if v]
        min_x, min_y, width, height = (parts + [0, 0, 24, 24])[:4]
    else:
        min_x = min_y = 0.0
        width = _float_attr(root, 'width', ICON_VIEWPORT)
        height = _float_attr(root, 'height', ICON_VIEWPORT)
    if width <= 0 or height <= 0:
        width = height = ICON_VIEWPORT

    # Fit the drawing into 24x24 without distorting it.
    ratio = min(ICON_VIEWPORT / width, ICON_VIEWPORT / height)
    offset_x = (ICON_VIEWPORT - width * ratio) / 2.0
    offset_y = (ICON_VIEWPORT - height * ratio) / 2.0
    fit = (ratio, 0.0, 0.0, ratio,
           offset_x - min_x * ratio, offset_y - min_y * ratio)

    subpaths = []
    saw_stroke_only = [False]      # list, so the nested walk can set it
    unsupported = set()

    def walk(element, matrix):
        group_matrix = _matrix_multiply(
            matrix, _parse_transform(element.get('transform')))
        for child in element:
            tag = child.tag
            if tag.startswith(_SVG_NS):
                tag = tag[len(_SVG_NS):]
            if tag in ('g', 'svg'):
                walk(child, group_matrix)
                continue
            if tag in ('defs', 'title', 'desc', 'metadata', 'style'):
                continue
            if tag in ('text', 'image', 'use', 'foreignObject'):
                unsupported.add(tag)
                continue
            data = child.get('d') if tag == 'path' else _shape_to_path(child, tag)
            if not data:
                if tag in ('line', 'polyline'):
                    unsupported.add(tag)
                continue
            fill = (child.get('fill') or '').strip().lower()
            style = child.get('style') or ''
            if fill == 'none' or 'fill:none' in style.replace(' ', ''):
                if child.get('stroke') or _STROKE_ONLY.search(style):
                    saw_stroke_only[0] = True
                continue
            child_matrix = _matrix_multiply(
                group_matrix, _parse_transform(child.get('transform')))
            combined = _matrix_multiply(fit, child_matrix)
            for sub in flatten(data, segments=segments):
                subpaths.append(([_apply(combined, point) for point in sub],
                                 fill or _fill_from_style(style)))

    walk(root, (1.0, 0.0, 0.0, 1.0, 0.0, 0.0))
    subpaths = _resolve_two_tone(subpaths)

    if not subpaths:
        if saw_stroke_only[0]:
            raise ValueError(
                "icon file %s draws with strokes and no fill; ApkPy renders "
                "filled shapes. Export it with the strokes outlined "
                "('Outline stroke' in Figma, 'Object > Path > Outline Stroke' "
                "in Illustrator)." % path)
        if unsupported:
            raise ValueError(
                "icon file %s uses <%s>, which ApkPy cannot convert to a "
                "vector icon" % (path, ">, <".join(sorted(unsupported))))
        raise ValueError("icon file %s has no filled shape to draw" % path)
    return to_path_data(subpaths)
