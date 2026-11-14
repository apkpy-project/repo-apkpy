"""Draws the template's placeholder art (all of it original, made by this script) into assets/.

    python tools/make_art.py

It only draws files that are missing, so your own art is safe: replace any PNG in assets/. Delete a file to get its
placeholder back. The build runs this for you, so a new species gets a placeholder at assets/monsters/<id>.png by itself.
"""
import json
import os
import random

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")
CELL = 64

# 5 x 7, one line per row of each character, in printable ASCII order; drawn for this template
FONT = {
    " ": "00000 00000 00000 00000 00000 00000 00000", "!": "00100 00100 00100 00100 00100 00000 00100",
    '"': "01010 01010 00000 00000 00000 00000 00000", "#": "01010 11111 01010 01010 11111 01010 00000",
    "%": "11001 11010 00010 00100 01000 01011 10011", "'": "00100 00100 00000 00000 00000 00000 00000",
    "(": "00010 00100 01000 01000 01000 00100 00010", ")": "01000 00100 00010 00010 00010 00100 01000",
    "+": "00000 00100 00100 11111 00100 00100 00000", ",": "00000 00000 00000 00000 00110 00100 01000",
    "-": "00000 00000 00000 11111 00000 00000 00000", ".": "00000 00000 00000 00000 00000 00110 00110",
    "/": "00001 00010 00010 00100 01000 01000 10000", ":": "00000 00110 00110 00000 00110 00110 00000",
    "<": "00010 00100 01000 10000 01000 00100 00010", ">": "01000 00100 00010 00001 00010 00100 01000",
    "^": "00100 01010 10001 00000 00000 00000 00000", "_": "00000 00000 00000 00000 00000 00000 11111",
    "?": "01110 10001 00001 00110 00100 00000 00100", "=": "00000 00000 11111 00000 11111 00000 00000",
    "0": "01110 10011 10101 10101 10101 11001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00110 01000 10000 11111", "3": "11110 00001 00001 01110 00001 00001 11110",
    "4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00010 01100",
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110", "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 11001 10101 10011 10001 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 11011 10001", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    "a": "00000 00000 01110 00001 01111 10001 01111", "b": "10000 10000 11110 10001 10001 10001 11110",
    "c": "00000 00000 01110 10000 10000 10001 01110", "d": "00001 00001 01111 10001 10001 10001 01111",
    "e": "00000 00000 01110 10001 11111 10000 01110", "f": "00110 01001 01000 11100 01000 01000 01000",
    "g": "00000 01111 10001 10001 01111 00001 01110", "h": "10000 10000 11110 10001 10001 10001 10001",
    "i": "00100 00000 01100 00100 00100 00100 01110", "j": "00010 00000 00110 00010 00010 10010 01100",
    "k": "10000 10000 10010 10100 11000 10100 10010", "l": "01100 00100 00100 00100 00100 00100 01110",
    "m": "00000 00000 11010 10101 10101 10101 10101", "n": "00000 00000 11110 10001 10001 10001 10001",
    "o": "00000 00000 01110 10001 10001 10001 01110", "p": "00000 11110 10001 10001 11110 10000 10000",
    "q": "00000 01111 10001 10001 01111 00001 00001", "r": "00000 00000 10110 11001 10000 10000 10000",
    "s": "00000 00000 01111 10000 01110 00001 11110", "t": "01000 01000 11100 01000 01000 01001 00110",
    "u": "00000 00000 10001 10001 10001 10011 01101", "v": "00000 00000 10001 10001 10001 01010 00100",
    "w": "00000 00000 10001 10001 10101 10101 01010", "x": "00000 00000 10001 01010 00100 01010 10001",
    "y": "00000 10001 10001 10001 01111 00001 01110", "z": "00000 00000 11111 00010 00100 01000 11111",
}

TILES = {  # name: (base colour, speck colour, how many specks)
    "grass": ((104, 172, 92), (84, 150, 76), 18), "path": ((206, 182, 132), (186, 162, 114), 14),
    "reeds": ((62, 128, 88), (150, 196, 96), 40), "water": ((64, 128, 196), (120, 176, 228), 16),
    "sand": ((232, 214, 164), (212, 192, 142), 12), "floor": ((176, 132, 92), (150, 110, 74), 10),
    "wall": ((120, 112, 124), (96, 90, 102), 16), "rug": ((168, 72, 84), (196, 104, 104), 20),
    "stone": ((150, 150, 142), (120, 120, 114), 24), "dark": ((40, 44, 60), (52, 56, 74), 8),
    "arena": ((120, 160, 110), (104, 142, 96), 14), "cliff": ((132, 110, 84), (104, 86, 66), 22),
}


def keep(img, name):
    """Art is yours once it exists: this script only draws files that are missing. Delete one to get its placeholder back."""
    path = os.path.join(OUT, name)
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.save(path)
        print("drew a placeholder:", os.path.relpath(path, ROOT).replace("\\", "/"))


def noise_tile(name, rng):
    base, speck, count = TILES[name]
    tile = Image.new("RGBA", (16, 16), base + (255,))
    for _ in range(count):
        tile.putpixel((rng.randrange(16), rng.randrange(16)), speck + (255,))
    if name == "reeds":
        for x in range(1, 16, 3):
            for y in range(rng.randrange(2, 6), 16):
                tile.putpixel((x, y), (40, 104, 70, 255))
    return tile


def tileset():
    for name in TILES:
        keep(noise_tile(name, random.Random(name)), "tiles/%s.png" % name)


def block_image(name, base, dark):
    img = Image.new("RGBA", (16, 16), base + (255,))
    for y in range(0, 16, 4):
        for x in range(16):
            img.putpixel((x, y), dark + (255,))
    keep(img, name)


def person(skin, shirt, trousers, hair):
    """A sheet of 16 x 24 cells: rows down, left, up, right; columns: standing, step, standing, the other step."""
    sheet = Image.new("RGBA", (64, 96), (0, 0, 0, 0))

    def rect(ox, oy, x0, y0, x1, y1, colour):
        sheet.paste(colour + (255,), (ox + x0, oy + y0, ox + x1, oy + y1))

    for row in range(4):
        for col in range(4):
            ox, oy = col * 16, row * 24
            # standing, then each foot lifted in turn; the body bobs up on a step
            lift_left, lift_right = (3, 0) if col == 1 else (0, 3) if col == 3 else (0, 0)
            bob = -1 if col in (1, 3) else 0
            rect(ox, oy, 5, 19, 7, 23 - lift_left, trousers)
            rect(ox, oy, 9, 19, 11, 23 - lift_right, trousers)
            oy += bob
            arm = -1 if col == 1 else 1 if col == 3 else 0
            rect(ox, oy, 4, 11, 12, 20, shirt)
            rect(ox, oy, 2, 12 + arm, 4, 18 + arm, skin)
            rect(ox, oy, 12, 12 - arm, 14, 18 - arm, skin)
            rect(ox, oy, 4, 3, 12, 11, skin)
            rect(ox, oy, 4, 2, 12, 5, hair)
            if row == 0:
                rect(ox, oy, 6, 7, 7, 9, (30, 30, 40))
                rect(ox, oy, 9, 7, 10, 9, (30, 30, 40))
            elif row == 1:
                rect(ox, oy, 5, 7, 6, 9, (30, 30, 40))
                rect(ox, oy, 4, 5, 6, 6, hair)
            elif row == 2:
                rect(ox, oy, 4, 3, 12, 10, hair)
            else:
                rect(ox, oy, 10, 7, 11, 9, (30, 30, 40))
                rect(ox, oy, 10, 5, 12, 6, hair)
    return sheet


def people():
    cast = {"hero": ((240, 200, 160), (60, 110, 190), (50, 56, 84), (90, 54, 30)),
            "keeper": ((222, 180, 140), (120, 84, 150), (70, 60, 80), (210, 210, 210)),
            "rival": ((240, 206, 170), (190, 70, 60), (44, 44, 60), (30, 30, 34)),
            "vendor": ((200, 150, 110), (70, 150, 110), (90, 70, 50), (60, 40, 30)),
            "villager": ((236, 196, 150), (210, 170, 70), (80, 80, 110), (150, 90, 40))}
    for name, colours in cast.items():
        keep(person(*colours), "people/%s.png" % name)


def monster(seed, colour, back):
    """A creature: a symmetric blob on a 16 x 16 grid, drawn at 4 pixels per cell (64 x 64). The back view has no face."""
    rng = random.Random(seed)
    grid = [[0] * 16 for _ in range(16)]
    for _ in range(3):
        cx, cy, r = rng.randrange(4, 8), rng.randrange(5, 11), rng.randrange(3, 5)
        for y in range(16):
            for x in range(8):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    grid[y][x] = 1
    for _ in range(14):                       # ears, spikes, feet: a bit of each
        x, y = rng.randrange(1, 8), rng.randrange(1, 15)
        if any(grid[min(15, y + dy)][min(7, x + dx)] for dx, dy in ((1, 0), (0, 1), (0, -1))):
            grid[y][x] = 1
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    shade = tuple(max(0, c - 50) for c in colour)
    light = tuple(min(255, c + 50) for c in colour)
    outline = tuple(max(0, c - 110) for c in colour)

    def cell(x, y, value):
        for px in (x, 15 - x):
            img.paste(value + (255,), (px * 4, y * 4, px * 4 + 4, y * 4 + 4))

    for y in range(16):
        for x in range(8):
            if grid[y][x]:
                edge = (y == 0 or not grid[y - 1][x] or y == 15 or not grid[y + 1][x]
                        or x == 0 or not grid[y][x - 1] or (x < 7 and not grid[y][x + 1]))
                cell(x, y, outline if edge else light if y < 6 else colour if y < 11 else shade)
    rows = [y for y in range(16) if any(grid[y])]
    if rows and not back:
        eye = rows[0] + max(2, len(rows) // 3)
        cell(5, eye, (250, 250, 250))
        cell(6, eye, (24, 24, 36))
    return img


def monsters():
    """One sheet per species, assets/monsters/<id>.png: 128 x 64, front then back. Only what is missing is drawn:
    your own art is never overwritten. To get a placeholder back, delete the file."""
    with open(os.path.join(ROOT, "data", "types.json"), encoding="utf-8") as fh:
        colours = {t["id"]: t["color"] for t in json.load(fh)}
    folder = os.path.join(ROOT, "data", "species")
    out = os.path.join(OUT, "monsters")
    os.makedirs(out, exist_ok=True)
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as fh:
            s = json.load(fh)
        path = os.path.join(out, s["id"] + ".png")
        if os.path.isfile(path):
            continue
        hex_colour = colours[s["types"][0]].lstrip("#")
        colour = tuple(int(hex_colour[i:i + 2], 16) for i in (0, 2, 4))
        sheet = Image.new("RGBA", (CELL * 2, CELL), (0, 0, 0, 0))
        sheet.paste(monster(s["id"], colour, False), (0, 0))
        sheet.paste(monster(s["id"], colour, True), (CELL, 0))
        keep(sheet, "monsters/%s.png" % s["id"])
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as fh:
            s = json.load(fh)
        for v in s.get("variants", []):
            good_id = str(v.get("id", "")).replace("_", "").isalnum() and str(v.get("id", "")).islower()
            if good_id and not os.path.isfile(os.path.join(out, "%s.%s.png" % (s["id"], v["id"]))):
                with Image.open(os.path.join(out, s["id"] + ".png")) as img:
                    keep(variant_sheet(img, v["id"]), "monsters/%s.%s.png" % (s["id"], v["id"]))
    keep(Image.new("RGBA", (CELL * 2, CELL), (0, 0, 0, 0)), "monster_blank.png")


def variant_sheet(img, variant):
    """A variant's placeholder: the species' own sheet in other colours (the same ones each time for that name)."""
    import colorsys
    turn = 0.2 + random.Random(variant).random() * 0.6
    out = img.convert("RGBA").copy()
    pixels = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = pixels[x, y]
            if a:
                h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
                r2, g2, b2 = colorsys.hsv_to_rgb((h + turn) % 1.0, min(1.0, s * 1.1), v)
                pixels[x, y] = (int(r2 * 255), int(g2 * 255), int(b2 * 255), a)
    return out


def frame():
    """The box of the interface: cut in nine, border 8."""
    img = Image.new("RGBA", (24, 24), (40, 44, 64, 255))
    img.paste((244, 236, 212, 255), (1, 1, 23, 3))
    img.paste((244, 236, 212, 255), (1, 21, 23, 23))
    img.paste((244, 236, 212, 255), (1, 1, 3, 23))
    img.paste((244, 236, 212, 255), (21, 1, 23, 23))
    img.paste((96, 104, 136, 255), (3, 3, 21, 4))
    img.paste((24, 26, 40, 255), (3, 20, 21, 21))
    keep(img, "box.png")
    knot = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y in range(16):
        for x in range(16):
            if (x - 8) ** 2 + (y - 8) ** 2 <= 36:
                knot.putpixel((x, y), (214, 96, 70, 255) if (x + y) % 4 < 2 else (246, 214, 150, 255))
    keep(knot, "knot.png")
    for name, top in (("roof_red.png", (170, 72, 62)), ("roof_blue.png", (72, 96, 170))):
        block_image(name, top, tuple(max(0, c - 34) for c in top))
    block_image("house_wall.png", (226, 214, 188), (196, 182, 156))
    door = Image.new("RGBA", (16, 24), (70, 46, 30, 255))
    door.paste((132, 86, 50, 255), (2, 2, 14, 24))
    for x in (5, 9):
        door.paste((108, 68, 38, 255), (x, 2, x + 1, 24))
    door.paste((96, 60, 34, 255), (2, 10, 14, 11))
    door.paste((244, 214, 120, 255), (11, 13, 13, 15))
    keep(door, "door.png")
    mat = Image.new("RGBA", (32, 16), (80, 56, 40, 255))
    mat.paste((184, 150, 96, 255), (2, 2, 30, 14))
    for x in range(4, 28, 4):
        mat.paste((150, 118, 72, 255), (x, 2, x + 1, 14))
    keep(mat, "doormat.png")
    tree = Image.new("RGBA", (28, 44), (0, 0, 0, 0))
    tree.paste((98, 70, 46, 255), (12, 30, 16, 44))
    for y in range(36):
        for x in range(28):
            if (x - 14) ** 2 + (y - 16) ** 2 <= 180:
                tree.putpixel((x, y), (56, 120, 70, 255) if (x * 3 + y * 5) % 7 else (88, 152, 88, 255))
    keep(tree, "tree.png")
    tower = Image.new("RGBA", (48, 112), (0, 0, 0, 0))
    for y in range(112):
        half = 12 + y // 12
        band = (214, 70, 60, 255) if (y // 16) % 2 else (240, 236, 224, 255)
        tower.paste(band, (24 - half, y, 24 + half, y + 1))
    tower.paste((40, 44, 60, 255), (16, 92, 32, 112))
    tower.paste((250, 220, 110, 255), (16, 2, 32, 12))
    keep(tower, "lighthouse.png")


def draw_logo(word):
    """A word for the title screen, from the pixel font. A long one gets smaller letters, to fit the screen."""
    word = "".join(ch for ch in word if ch in FONT) or "?"
    px = max(2, min(6, 440 // (len(word) * 6)))
    shadow = max(1, px // 2)
    logo = Image.new("RGBA", (len(word) * 6 * px + 16, 7 * px + 16), (0, 0, 0, 0))
    ink = (12, 28, 56, 255)

    def letters(offset_x, offset_y, colour_at):
        for i, ch in enumerate(word):
            for r, row in enumerate(FONT[ch].split()):
                for c, bit in enumerate(row):
                    if bit == "1":
                        x0, y0 = 8 + offset_x + (i * 6 + c) * px, 8 + offset_y + r * px
                        logo.paste(colour_at(r), (x0, y0, x0 + px, y0 + px))

    for dx, dy in ((-shadow, 0), (shadow, 0), (0, -shadow), (0, shadow), (-shadow, -shadow), (shadow, shadow), (-shadow, shadow), (shadow, -shadow), (shadow + 1, shadow + 2)):
        letters(dx, dy, lambda r: ink)
    letters(0, 0, lambda r: (250, 244, 214, 255) if r < 2 else (244, 214, 120, 255) if r < 5 else (226, 132, 80, 255))
    return logo


def draw_title_art():
    """The title's scene: a dusk sky in bands, clouds, the sea, the rock with the lighthouse, its beam, the logo."""
    w, h = 800, 300                                  # the sky; above it, the top colour fills any taller screen
    sky = Image.new("RGBA", (w, h))
    stops = [(0, (16, 36, 72)), (0.4, (28, 88, 112)), (0.72, (92, 156, 148)), (0.9, (232, 190, 140)), (1, (246, 214, 160))]
    for y in range(h):
        f = y / (h - 1)
        for (a, ca), (b, cb) in zip(stops, stops[1:]):
            if a <= f <= b:
                t = (f - a) / (b - a)
                t = round(t * 6) / 6                     # bands, not a smooth gradient: it is pixel art
                sky.paste(tuple(int(ca[i] + (cb[i] - ca[i]) * t) for i in range(3)) + (255,), (0, y, w, y + 1))
                break
    rng = random.Random(11)
    for _ in range(70):
        sky.putpixel((rng.randrange(w), rng.randrange(h // 3)), (230, 236, 250, 255))
    keep(sky, "title_sky.png")

    cloud = Image.new("RGBA", (96, 24), (0, 0, 0, 0))
    for cx, cy, r in ((22, 15, 8), (38, 11, 10), (56, 12, 9), (72, 16, 7)):
        for y in range(24):
            for x in range(96):
                if (x - cx) ** 2 + ((y - cy) * 1.5) ** 2 <= r * r:
                    cloud.putpixel((x, y), (214, 234, 232, 255) if y < cy else (150, 196, 200, 255))
    keep(cloud, "title_cloud.png")

    sea = Image.new("RGBA", (w + 64, 200), (30, 92, 132, 255))
    for y in range(0, 200, 8):
        if y > 44:
            break
        shade = (52 + y, 128 + y, 168, 255)
        for x in range(w + 64):
            if (x + y * 2) % 32 < 12:
                sea.putpixel((x, y + (2 if (x + y * 2) % 32 < 6 else 1)), shade)
    keep(sea, "title_sea.png")

    rock = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    for y in range(92, 120):
        half = 24 + (y - 92)
        rock.paste((34, 50, 64, 255), (60 - half, y, 60 + half, y + 1))
    for y in range(12, 92):
        half = 7 + y // 14
        band = (196, 76, 66, 255) if (y // 14) % 2 else (232, 228, 214, 255)
        rock.paste(band, (60 - half, y, 60 + half, y + 1))
    rock.paste((40, 44, 60, 255), (54, 2, 66, 12))
    rock.paste((255, 232, 140, 255), (55, 4, 65, 12))
    keep(rock, "title_rock.png")

    beam = Image.new("RGBA", (260, 40), (0, 0, 0, 0))
    for x in range(260):
        half = int(1 + x * 18 / 260)
        alpha = int(150 * (x / 260))
        for y in range(20 - half, 20 + half):
            if (x // 4 + y // 4) % 2 == 0 or alpha > 60:
                beam.putpixel((x, y), (255, 240, 170, alpha))
    keep(beam, "title_beam.png")

    keep(draw_logo("SALTMERE"), "title_logo.png")


def font():
    """A bitmap font in the BMFont text format: size 8, 5 x 7 glyphs."""
    chars = sorted(FONT)
    page = Image.new("RGBA", (6 * 16, 8 * (len(chars) // 16 + 1)), (0, 0, 0, 0))
    lines = ['info face="pixel" size=8', "common lineHeight=10 base=7 scaleW=%d scaleH=%d pages=1" % page.size,
             'page id=0 file="pixel.png"', "chars count=%d" % len(chars)]
    for i, ch in enumerate(chars):
        x, y = (i % 16) * 6, (i // 16) * 8
        for r, row in enumerate(FONT[ch].split()):
            for c, bit in enumerate(row):
                if bit == "1":
                    page.putpixel((x + c, y + r), (255, 255, 255, 255))
        drop = 1 if ch in "gpqy" else 0     # these hang below the line
        lines.append("char id=%d x=%d y=%d width=5 height=7 xoffset=0 yoffset=%d xadvance=6 page=0" % (ord(ch), x, y, drop))
    keep(page, "pixel.png")
    if not os.path.isfile(os.path.join(OUT, "pixel.fnt")):
        with open(os.path.join(OUT, "pixel.fnt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


def main():
    os.makedirs(OUT, exist_ok=True)
    tileset()
    people()
    monsters()
    frame()
    draw_title_art()
    font()


if __name__ == "__main__":
    main()
