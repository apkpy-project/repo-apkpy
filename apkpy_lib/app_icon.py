# -*- coding: utf-8 -*-
"""The app's icon on the phone, from one square PNG (apkpy.toml: icon = "icon.png").

Android 8 and later draw a launcher icon as two layers, a background and a
foreground, and cut them to the phone's own shape (a circle, a squircle...).
An app with only a square picture gets it shrunk inside a white circle, which
is how an ApkPy app looked until 1.15.1. Now the build writes both:

- the square PNG at five densities (mipmap-*/ic_launcher.png), for Android 7;
- an adaptive icon (mipmap-anydpi-v26/ic_launcher.xml): the picture on a
  108 dp layer, inside the 72 dp the phone shows, over a colour.

Which colour, and how big the picture is, depends on the picture:

- one with a filled background (the middle of each edge opaque and of one
  colour) fills the 72 dp, and that colour is the background, so the phone's
  shape cuts the picture's own background;
- one with a transparent background (a logo, a glyph) sits inside the 66 dp
  circle every shape keeps, on `icon_background` from apkpy.toml, or white.

On Android 12 and later the screen shown while the app starts is this icon on
the app's background colour (the theme's windowBackground, light or dark), so
it follows too.
"""

import os

# 108 dp at each density: the adaptive layers.
LAYER = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}
# 48 dp: the square icon of Android 7 and older.
LEGACY = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
FULL = 72.0 / 108       # what the phone shows of the layer
SAFE = 60.0 / 108       # inside the 66 dp circle every shape keeps, with a little air

ADAPTIVE = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
    '    <background android:drawable="@color/apkpy_icon_background" />\n'
    '    <foreground android:drawable="@mipmap/ic_launcher_foreground" />\n'
    '</adaptive-icon>\n'
)


def _hex(colour):
    return "#%02X%02X%02X" % tuple(colour[:3])


def edge_colour(img):
    """The colour of the middle of the picture's edges when they are all
    opaque and of one colour, or None. The corners are left out: a picture
    with rounded corners has its background there too."""
    w, h = img.size
    px = img.load()
    points = []
    for i in range(w // 4, w - w // 4, max(1, w // 32)):
        points += [px[i, 0], px[i, h - 1]]
    for i in range(h // 4, h - h // 4, max(1, h // 32)):
        points += [px[0, i], px[w - 1, i]]
    if not points or any(p[3] < 250 for p in points):
        return None
    middle = [sorted(p[c] for p in points)[len(points) // 2] for c in range(3)]
    if any(abs(p[c] - middle[c]) > 12 for p in points for c in range(3)):
        return None
    return tuple(middle)


def plan(img, background=None):
    """(background colour as #RRGGBB, the part of the layer the picture takes)."""
    filled = edge_colour(img)
    if filled is not None:
        return _hex(filled), FULL
    return (background or "#FFFFFF").upper(), SAFE


def foreground(img, size, share):
    """The picture centred on a transparent size x size layer, share of it wide."""
    from PIL import Image
    side = max(1, int(round(size * share)))
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    picture = img.resize((side, side), Image.LANCZOS)
    at = (size - side) // 2
    layer.alpha_composite(picture, (at, at))
    return layer


def write(res_dir, icon_path, background=None):
    """Write the icon's files under res/. Returns the background colour used."""
    from PIL import Image
    img = Image.open(icon_path).convert("RGBA")
    if img.width != img.height:
        side = max(img.width, img.height)
        square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        square.alpha_composite(img, ((side - img.width) // 2, (side - img.height) // 2))
        img = square
    colour, share = plan(img, background)
    for density, size in LEGACY.items():
        folder = os.path.join(res_dir, "mipmap-" + density)
        os.makedirs(folder, exist_ok=True)
        resized = img.resize((size, size), Image.LANCZOS)
        resized.save(os.path.join(folder, "ic_launcher.png"))
        resized.save(os.path.join(folder, "ic_launcher_round.png"))
    for density, size in LAYER.items():
        folder = os.path.join(res_dir, "mipmap-" + density)
        foreground(img, size, share).save(os.path.join(folder, "ic_launcher_foreground.png"))
    anydpi = os.path.join(res_dir, "mipmap-anydpi-v26")
    os.makedirs(anydpi, exist_ok=True)
    for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
        with open(os.path.join(anydpi, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(ADAPTIVE)
    values = os.path.join(res_dir, "values")
    os.makedirs(values, exist_ok=True)
    with open(os.path.join(values, "apkpy_icon.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
                '    <color name="apkpy_icon_background">%s</color>\n</resources>\n' % colour)
    return colour


def preview(icon_path, size=216, background=None, shape="circle"):
    """The icon as a phone with that shape shows it: for looking at, and for tests."""
    from PIL import Image, ImageDraw
    img = Image.open(icon_path).convert("RGBA")
    colour, share = plan(img, background)
    layer = Image.new("RGBA", (size, size), colour)
    layer.alpha_composite(foreground(img, size, share))
    shown = int(round(size * FULL))
    at = (size - shown) // 2
    cut = layer.crop((at, at, at + shown, at + shown))
    mask = Image.new("L", (shown, shown), 0)
    draw = ImageDraw.Draw(mask)
    if shape == "circle":
        draw.ellipse((0, 0, shown - 1, shown - 1), fill=255)
    else:
        draw.rounded_rectangle((0, 0, shown - 1, shown - 1), shown // 4, fill=255)
    out = Image.new("RGBA", (shown, shown), (0, 0, 0, 0))
    out.paste(cut, (0, 0), mask)
    return out
