"""shimmer, in the Previewer: the band of light drawn over a box's Canvas.

Tk paints an image's alpha onto a canvas, so the band is a picture, one per
frame of the sweep, with the box's rounded corners cut out of it, moved
across by swapping the picture (shimmer_rules.offset says where it is).
"""

import time
import tkinter as tk

from .. import shimmer_rules as rules

_FRAMES = 36
_TAG = "apkpy_shimmer"


def _colour(value):
    raw = str(value or "").lstrip("#")
    if len(raw) == 6:
        raw = "FF" + raw
    try:
        return tuple(int(raw[i:i + 2], 16) for i in (2, 4, 6)), int(raw[0:2], 16)
    except ValueError:
        return (255, 255, 255), 89


def _pictures(width, height, radius, colour):
    from PIL import Image, ImageDraw, ImageTk
    rgb, alpha = _colour(colour)
    mask = Image.new("L", (width, height), 0)
    # A pixel inside the box's own edge: its anti-aliased rim is half track.
    ImageDraw.Draw(mask).rounded_rectangle((1, 1, width - 2, height - 2),
                                           radius=max(0, int(radius) - 1), fill=255)
    shape = mask.load()
    frames = []
    for index in range(_FRAMES):
        where = rules.offset(rules.SWEEP * index / float(_FRAMES))
        band = Image.new("RGBA", (width, height), rgb + (0,))
        pixels = band.load()
        for x in range(width):
            a = int(round(alpha * rules.strength(x / float(width) - where)))
            if a:
                for y in range(height):
                    pixels[x, y] = rgb + (a * shape[x, y] // 255,)
        frames.append(ImageTk.PhotoImage(band))
    return frames


def attach(canvas, value, radius=0, empty=False):
    """Run the band over ``canvas`` until it is destroyed."""
    spec = rules.parse(value)
    if spec is None or canvas is None:
        return False
    period, colour = spec
    cache = {}
    start = time.time()

    def tick():
        try:
            if not canvas.winfo_exists():
                return
            width, height = canvas.winfo_width(), canvas.winfo_height()
            if width > 1 and height > 1:
                if empty:
                    # A window item is always drawn over a canvas's pictures:
                    # an empty box's inner frame would cut a line through it.
                    for item in canvas.find_all():
                        if canvas.type(item) == "window":
                            canvas.itemconfigure(item, state="hidden")
                key = (width, height)
                if key not in cache:
                    cache.clear()
                    cache[key] = _pictures(width, height, radius, colour)
                phase = ((time.time() - start) * 1000.0 / period) % 1.0
                canvas.delete(_TAG)
                if phase < rules.SWEEP:
                    frame = cache[key][min(_FRAMES - 1, int(phase / rules.SWEEP * _FRAMES))]
                    canvas.create_image(0, 0, image=frame, anchor="nw", tags=_TAG)
                    canvas.tag_raise(_TAG)
            canvas.after(40, tick)
        except (tk.TclError, ImportError):
            return

    canvas.after(40, tick)
    return True
