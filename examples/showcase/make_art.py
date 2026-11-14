"""The pictures of the four showcase apps, drawn here: nothing is downloaded.

    python make_art.py

Covers and orbs are soft gradients with blurred light and a little grain;
the travel pictures are layered landscapes at a given hour; Onda's waves are
layered sine curves; the category tiles are Material icons (the same
catalogue the apps use) on a colour; the faces are initials on a gradient.
Everything lands in art/. It needs Pillow and NumPy.
"""
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "art")
os.makedirs(ART, exist_ok=True)
random.seed(11)
RNG = np.random.default_rng(11)

FONTS = ("C:/Windows/Fonts/segoeuisb.ttf", "C:/Windows/Fonts/segoeuib.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf")


def hexrgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def font(size):
    for name in FONTS:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def linear(size, stops, angle=135):
    """A CSS-like linear gradient: stops = [(t, "#hex"), ...]."""
    w, h = size
    a = math.radians(angle - 90)
    dx, dy = math.cos(a), math.sin(a)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    proj = (xs - w / 2) * dx + (ys - h / 2) * dy
    span = abs(w / 2 * dx) + abs(h / 2 * dy)
    t = np.clip((proj + span) / (2 * span), 0, 1)
    out = np.zeros((h, w, 3), np.float32)
    pos = [s[0] for s in stops]
    cols = [np.array(hexrgb(s[1]), np.float32) for s in stops]
    for c in range(3):
        out[..., c] = np.interp(t, pos, [col[c] for col in cols])
    return out


def glow(arr, x, y, r, colour, strength=0.9):
    """Add a soft round light at (x, y) of radius r (fractions of the width)."""
    h, w, _ = arr.shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((xs - x * w) ** 2 + (ys - y * h) ** 2) / (r * w)
    k = np.clip(1 - d, 0, 1) ** 2 * strength
    col = np.array(hexrgb(colour), np.float32)
    return arr * (1 - k[..., None]) + col * k[..., None]


def grain(arr, amount=7):
    noise = RNG.normal(0, amount, arr.shape[:2]).astype(np.float32)
    return arr + noise[..., None]


def to_image(arr):
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def save(img, name, quality=88):
    path = os.path.join(ART, name)
    if name.endswith(".jpg"):
        img.convert("RGB").save(path, quality=quality, optimize=True, progressive=True)
    else:
        img.save(path, optimize=True)
    return path


# ── Afterglow: album covers ──────────────────────────────────────────────────

COVERS = {
    "cover_neon_tides": ("#140A2E", "#3B1B7A", ["#FF4FD8", "#6C5CFF", "#00E5FF"]),
    "cover_soft_static": ("#1A0B12", "#5A1636", ["#FF7A59", "#FF3D7F", "#FFD166"]),
    "cover_low_orbit": ("#04121F", "#0B3B5B", ["#2EE6D6", "#3D8BFF", "#C8F7FF"]),
    "cover_paper_moon": ("#1B1206", "#5B3A10", ["#FFB347", "#FFE29A", "#FF6A3D"]),
    "cover_glass_garden": ("#06150E", "#0E4A33", ["#4BE38B", "#B6FF6E", "#00C2A8"]),
    "cover_velvet_hour": ("#12061E", "#40115E", ["#C86BFA", "#FF6FB5", "#7A5CFF"]),
    "cover_city_lights": ("#0A0A14", "#24244A", ["#FFC857", "#FF5E78", "#5C7CFF"]),
    "cover_after_rain": ("#071018", "#1C3A4F", ["#7FD3FF", "#B8A9FF", "#E0F7FF"]),
}


def cover(name, base, mid, lights, size=480):
    arr = linear((size, size), [(0, base), (1, mid)], angle=150)
    for i, colour in enumerate(lights):
        arr = glow(arr, random.uniform(0.15, 0.85), random.uniform(0.15, 0.85),
                   random.uniform(0.35, 0.6), colour, strength=0.85)
    img = to_image(arr).filter(ImageFilter.GaussianBlur(size // 40))
    # one quiet shape, so a cover is a cover and not only a gradient
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    kind = sum(map(ord, name)) % 3
    c = hexrgb(lights[0]) + (70,)
    if kind == 0:
        r = size * 0.22
        d.ellipse((size / 2 - r, size / 2 - r, size / 2 + r, size / 2 + r), outline=(255, 255, 255, 120), width=3)
    elif kind == 1:
        for i in range(7):
            y = size * (0.3 + i * 0.06)
            d.line((size * 0.18, y, size * 0.82, y), fill=(255, 255, 255, 60 + i * 12), width=2)
    else:
        d.polygon([(size * 0.5, size * 0.24), (size * 0.78, size * 0.74), (size * 0.22, size * 0.74)],
                  outline=(255, 255, 255, 110), width=3)
    img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    save(to_image(grain(np.asarray(img, np.float32), 6)), name + ".jpg")


for key, (base, mid, lights) in COVERS.items():
    cover(key, base, mid, lights)


# ── Northline: places at an hour of the day ─────────────────────────────────

def ridge(w, h, base, amp, freq, seed):
    rng = random.Random(seed)
    phases = [rng.uniform(0, 6.28) for _ in range(3)]
    pts = []
    for x in range(0, w + 8, 8):
        y = base
        for k, ph in enumerate(phases):
            y += amp / (k + 1) * math.sin(x / w * math.pi * freq * (k + 1) + ph)
        pts.append((x, y))
    return pts + [(w, h), (0, h)]


def place(name, sky, sun, layers, size=(960, 640), sun_at=(0.68, 0.42), water=None, stars=False):
    w, h = size
    arr = linear(size, sky, angle=180)
    arr = glow(arr, sun_at[0], sun_at[1] * h / w, 0.55, sun[1], strength=0.55)
    img = to_image(arr).convert("RGBA")
    d = ImageDraw.Draw(img)
    if stars:
        rng = random.Random(name)
        for _ in range(90):
            x, y = rng.uniform(0, w), rng.uniform(0, h * 0.45)
            r = rng.choice((1, 1, 1.5, 2))
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, rng.randint(90, 220)))
    sx, sy = sun_at[0] * w, sun_at[1] * h
    r = w * 0.07
    d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=hexrgb(sun[0]) + (255,))
    for i, (colour, base, amp, freq) in enumerate(layers):
        layer = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).polygon(ridge(w, h, base * h, amp * h, freq, name + str(i)),
                                      fill=hexrgb(colour) + (255,))
        img = Image.alpha_composite(img, layer)
    if water:
        top = int(water[0] * h)
        band = linear((w, h - top), [(0, water[1]), (1, water[2])], angle=180)
        band = glow(band, sun_at[0], 0.0, 0.25, sun[1], strength=0.45)
        wimg = to_image(band).convert("RGBA")
        wd = ImageDraw.Draw(wimg)
        rng = random.Random(name + "w")
        for _ in range(26):   # glints under the sun
            y = rng.uniform(4, (h - top) * 0.9)
            half = rng.uniform(8, 50) * (1 - y / (h - top))
            x = sx + rng.uniform(-60, 60)
            wd.line((x - half, y, x + half, y), fill=hexrgb(sun[0]) + (rng.randint(90, 180),), width=2)
        img.paste(wimg, (0, top))
    out = np.asarray(img.convert("RGB"), np.float32)
    save(to_image(grain(out, 5)), name + ".jpg", quality=86)


place("place_copenhagen",
      sky=[(0, "#1E2A5A"), (0.55, "#E97C6A"), (1, "#FFD3A1")], sun=("#FFF1D6", "#FFB58A"),
      layers=[("#7E5A8C", 0.60, 0.035, 2.5), ("#4B3A6B", 0.66, 0.03, 4), ("#2A2347", 0.71, 0.02, 7)],
      sun_at=(0.70, 0.50), water=(0.74, "#3A2F5E", "#1B1733"))
place("place_kyoto",
      sky=[(0, "#FDE7C8"), (0.6, "#F7B3A0"), (1, "#E58C8A")], sun=("#FFF6E8", "#FFD9B8"),
      layers=[("#D98C8C", 0.55, 0.08, 1.4), ("#B5677A", 0.64, 0.07, 2.2), ("#7A3F5E", 0.74, 0.06, 3),
              ("#4A2440", 0.84, 0.04, 5)], sun_at=(0.30, 0.38))
place("place_reykjavik",
      sky=[(0, "#04121F"), (0.5, "#0B3B5B"), (1, "#2A9D8F")], sun=("#E8FFF6", "#5EF2C2"),
      layers=[("#123B4A", 0.58, 0.10, 1.6), ("#0B2A36", 0.68, 0.08, 2.4), ("#06161E", 0.80, 0.05, 4)],
      sun_at=(0.78, 0.22), stars=True)
place("place_porto",
      sky=[(0, "#3B2C85"), (0.5, "#F2709C"), (1, "#FFC371")], sun=("#FFF0C9", "#FF9966"),
      layers=[("#C0587E", 0.62, 0.04, 3), ("#7C3A6D", 0.68, 0.03, 5)],
      sun_at=(0.50, 0.56), water=(0.70, "#5A3375", "#26163F"))
place("place_lisbon",
      sky=[(0, "#9FD3F5"), (0.7, "#FFE3B3"), (1, "#FFC48A")], sun=("#FFFBEA", "#FFE7A8"),
      layers=[("#E6A57E", 0.60, 0.05, 3), ("#C7795F", 0.67, 0.04, 6), ("#8E4F45", 0.76, 0.03, 9)],
      sun_at=(0.25, 0.30), water=(0.80, "#4F8FB8", "#1F4F70"))
place("place_santorini",
      sky=[(0, "#5BB4F0"), (0.7, "#BFE6FF"), (1, "#E8F6FF")], sun=("#FFFFFF", "#FFF6D8"),
      layers=[("#F2EDE4", 0.58, 0.05, 2), ("#D9CFC0", 0.66, 0.03, 4)],
      sun_at=(0.80, 0.20), water=(0.70, "#1E7FC8", "#0B3F6E"))
place("place_banff",
      sky=[(0, "#FFD7B5"), (0.5, "#FFB89A"), (1, "#C9D9F0")], sun=("#FFF4E0", "#FFD0A8"),
      layers=[("#8FA6C4", 0.40, 0.16, 1.2), ("#5E7A9E", 0.52, 0.12, 2), ("#2F4B5E", 0.64, 0.06, 4)],
      sun_at=(0.22, 0.26), water=(0.72, "#4E8C9E", "#1D4250"))
place("place_marrakech",
      sky=[(0, "#F6C177"), (0.6, "#F49D5C"), (1, "#E26D4B")], sun=("#FFF0D0", "#FFC27A"),
      layers=[("#E89A5E", 0.62, 0.06, 1.3), ("#C97541", 0.72, 0.05, 1.8), ("#9C4F2A", 0.82, 0.04, 2.6)],
      sun_at=(0.62, 0.40))


# ── Faces: initials on a gradient ───────────────────────────────────────────

FACES = {
    "face_maya": ("MS", "#7C5CFF", "#FF7AB6"),
    "face_leo": ("LR", "#00B4D8", "#7CF2C3"),
    "face_kai": ("KO", "#FF8A3D", "#FFD166"),
    "face_zoe": ("ZB", "#F04470", "#FF9A8B"),
    "face_ines": ("IA", "#3D5AFE", "#00E5FF"),
}


def face(name, letters, a, b, size=192):
    arr = linear((size, size), [(0, a), (1, b)], angle=135)
    arr = glow(arr, 0.3, 0.25, 0.6, "#FFFFFF", strength=0.25)
    img = to_image(arr)
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    f = font(int(size * 0.36))
    box = d.textbbox((0, 0), letters, font=f)
    d.text(((size - box[2] - box[0]) / 2, (size - box[3] - box[1]) / 2 - size * 0.02), letters,
           font=f, fill=(255, 255, 255))
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    save(out, name + ".png")


for key, (letters, a, b) in FACES.items():
    face(key, letters, a, b)


# ── Lumen: category tiles (a Material icon on a soft colour) ────────────────

from apkpy_lib import icons as _icons  # noqa: E402  (pip install apkpy)

TILES = {
    "tile_food": ("restaurant", "#FFF1E6", "#FF7A1A"),
    "tile_shop": ("shopping_bag", "#FDEAF4", "#E2368F"),
    "tile_salary": ("payments", "#E6F8EF", "#12A05C"),
    "tile_train": ("train", "#F0ECFF", "#6A4DF5"),
    "tile_coffee": ("local_cafe", "#F7EFE6", "#9A5B24"),
}


def tile(name, icon, bg, fg, size=144):
    big = size * 4
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, big - 1, big - 1), radius=big * 0.30,
                                          fill=hexrgb(bg) + (255,))
    img = img.resize((size, size), Image.LANCZOS)
    glyph = int(size * 0.50)
    cover_ = _icons.rasterize(_icons.flatten(_icons.path_for(icon)), glyph)
    alpha = Image.frombytes("L", (glyph, glyph), bytes(cover_))
    ink = Image.new("RGBA", (glyph, glyph), hexrgb(fg) + (255,))
    ink.putalpha(alpha)
    img.alpha_composite(ink, ((size - glyph) // 2, (size - glyph) // 2))
    save(img, name + ".png")


for key, (icon, bg, fg) in TILES.items():
    tile(key, icon, bg, fg)


# ── Onda: waves (onda is Portuguese for wave) ───────────────────────────────

WAVES = {
    # sky top, sky bottom, light (colour, x, y), bands from back to front
    "wave_dawn": ("#FFE7D1", "#FFC4A3", ("#FFF6EA", 0.72, 0.30),
                  ["#FFAD8A", "#F98B7A", "#E86F74", "#C4566E"]),
    "wave_sea": ("#E3F6F1", "#B5E6DC", ("#FFFFFF", 0.28, 0.28),
                 ["#8FD5C8", "#5DB8AC", "#2F9488", "#1F6F68"]),
    "wave_night": ("#151A42", "#2F2C70", ("#F3F0FF", 0.74, 0.26),
                   ["#6F63D6", "#5248B0", "#3A3388", "#231F5C"]),
    "wave_mint": ("#ECFAF1", "#C9F0D9", ("#FFFFFF", 0.30, 0.30),
                  ["#A6E6C2", "#78D1A5", "#4DB487", "#2E8F6A"]),
    "wave_lilac": ("#F1ECFF", "#DCD2FF", ("#FFFFFF", 0.70, 0.28),
                   ["#C4B5FF", "#A894F5", "#8C76E6", "#6E58CC"]),
}


def wave_band(w, h, top, amp, length, phase):
    pts = []
    for x in range(0, w + 6, 6):
        y = top + amp * math.sin(x / length * 2 * math.pi + phase) \
            + amp * 0.35 * math.sin(x / length * 4.6 * math.pi + phase * 1.7)
        pts.append((x, y))
    return pts + [(w, h), (0, h)]


def waves(name, top, bottom, light, bands, size=(960, 640)):
    w, h = size
    arr = linear(size, [(0, top), (1, bottom)], angle=180)
    colour, lx, ly = light
    arr = glow(arr, lx, ly * h / w, 0.38, colour, strength=0.7)
    img = to_image(arr).convert("RGBA")
    d = ImageDraw.Draw(img)
    if name == "wave_night":
        rng = random.Random(name)
        for _ in range(70):
            x, y = rng.uniform(0, w), rng.uniform(0, h * 0.5)
            r = rng.choice((1, 1, 1.5, 2))
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, rng.randint(80, 200)))
    r = w * 0.06
    d.ellipse((lx * w - r, ly * h - r, lx * w + r, ly * h + r), fill=hexrgb(colour) + (235,))
    rng = random.Random(name + "b")
    for i, band in enumerate(bands):
        layer = Image.new("RGBA", size, (0, 0, 0, 0))
        top_y = h * (0.46 + i * 0.12)
        ImageDraw.Draw(layer).polygon(
            wave_band(w, h, top_y, h * (0.05 - i * 0.006), w * rng.uniform(0.55, 0.9), rng.uniform(0, 6.28)),
            fill=hexrgb(band) + (255,))
        layer = layer.filter(ImageFilter.GaussianBlur(1.2))
        img = Image.alpha_composite(img, layer)
    out = np.asarray(img.convert("RGB"), np.float32)
    save(to_image(grain(out, 3)), name + ".jpg", quality=86)


for key, (top, bottom, light, bands) in WAVES.items():
    waves(key, top, bottom, light, bands)

print("\n".join(sorted(os.listdir(ART))))
