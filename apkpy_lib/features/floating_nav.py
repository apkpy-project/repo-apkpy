"""The floating bottom bar, in the Previewer (theme.nav_look says when).

A rounded card held ``margin`` off the screen's edges, over the screen's own
colour, with the items in a frame inset enough to clear the corners. On the
phone the content runs on under the card; Tk cannot show through a frame, so
here the strip around the card is painted the screen's colour, which is what
a phone shows once the page has scrolled to its end.
"""

import math
import tkinter as tk

from ..core import css_colors
from ..theme import NAV_BAR_DP


def plain(colour, behind):
    seen = str(css_colors.over(css_colors.named(str(colour or "").strip()), behind) or behind)
    return seen if seen.startswith("#") and len(seen) in (4, 7) else behind


def build(ui, root, look, behind):
    """``(outer, inner, bar_colour)``: pack ``outer``; put the items in ``inner``."""
    margin = int(round(look["margin"]))
    radius = int(round(look["radius"]))
    bar = plain(look["bar"], behind)
    outer = tk.Frame(root, bg=behind, height=NAV_BAR_DP + margin)
    outer.pack(fill="x", side="bottom")
    outer.pack_propagate(False)
    canvas = tk.Canvas(outer, bg=behind, highlightthickness=0, bd=0, height=NAV_BAR_DP)
    canvas.pack(fill="x", padx=margin, pady=(0, margin))
    inner = tk.Frame(canvas, bg=bar)
    window = canvas.create_window(0, 0, window=inner, anchor="nw")
    top = 4
    side = 1
    if radius > top:
        side = int(math.ceil(radius - math.sqrt(max(0, radius * radius - (radius - top) ** 2))))
    border = plain(look["border"], bar) if look.get("border") else ""

    def draw(_event=None):
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 4 or height < 4:
            return
        canvas.delete("nav_shape")
        ui._create_rounded_rect(canvas, 0, 0, width - 1, height - 1, min(radius, height // 2),
                                fill=bar, outline=border or bar,
                                width=max(1, int(round(look.get("border_width") or 1))),
                                tags="nav_shape")
        canvas.tag_lower("nav_shape")
        canvas.coords(window, side, top)
        canvas.itemconfigure(window, width=max(1, width - 2 * side),
                             height=max(1, height - 2 * top))

    canvas.bind("<Configure>", draw)
    return outer, inner, bar
