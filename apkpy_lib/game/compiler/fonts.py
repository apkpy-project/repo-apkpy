"""Fonts at build time: the measures the engine breaks lines with, written beside the font (PATH.json).

Measures come from the file, here, once, so the game breaks its lines the same way on every
platform. All numbers are per unit of text size, except a bitmap font's glyphs (texels).
"""
import os
import re

# what a TTF is measured for; any other character uses the "fallback" width
RANGES = [(0x20, 0x7E), (0xA0, 0x17F), (0x2010, 0x2027), (0x20AC, 0x20AC)]


class FontError(Exception):
    def __init__(self, message, fix=""):
        super().__init__(message)
        self.fix = fix


def read(full, path, root):
    if path.lower().endswith(".fnt"):
        return _bitmap(full, root)
    return _truetype(full)


def _truetype(full):
    from PIL import ImageFont
    units = 1000
    try:
        font = ImageFont.truetype(full, units)
    except OSError as e:
        raise FontError("not a font Pillow can read (%s)" % e)
    ascent, descent = font.getmetrics()
    advances = {}
    for first, last in RANGES:
        for code in range(first, last + 1):
            advances[chr(code)] = round(font.getlength(chr(code))) / units
    fallback = advances.get("n", 0.5)
    return {"kind": "ttf", "ascent": ascent / units, "line": (ascent + descent) / units, "fallback": fallback,
            "advances": advances}


def _fields(line):
    """BMFont text format: tag key=value key="value"... to (tag, {key: value})."""
    tag, _, rest = line.strip().partition(" ")
    return tag, {k: (q if q else v) for k, q, v in re.findall(r'(\w+)=(?:"([^"]*)"|(\S+))', rest)}


def _bitmap(full, root):
    with open(full, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if not text.lstrip().startswith("info "):
        raise FontError("only the BMFont text format is read", "Export the font as text (.fnt), not XML or binary.")
    size = line_height = base = 0
    image = None
    pages = 0
    glyphs, advances = {}, {}
    for raw in text.splitlines():
        tag, f = _fields(raw)
        if tag == "info":
            size = abs(int(f.get("size", 0)))
        elif tag == "common":
            line_height, base = int(f.get("lineHeight", 0)), int(f.get("base", 0))
        elif tag == "page":
            pages += 1
            image = f.get("file")
        elif tag == "char":
            ch = chr(int(f["id"]))
            glyphs[ch] = [int(f[k]) for k in ("x", "y", "width", "height", "xoffset", "yoffset")]
            advances[ch] = int(f["xadvance"])
    if pages != 1 or not image:
        raise FontError("the font has %d pages; one is supported" % pages, "Export it on one texture.")
    if not size or not glyphs:
        raise FontError("no size or no characters in the file")
    picture = os.path.normpath(os.path.join(os.path.dirname(full), image))
    rel = os.path.relpath(picture, root).replace("\\", "/")
    if rel.startswith("..") or not os.path.isfile(picture):
        raise FontError("its image %s is not in the project" % image)
    return {"kind": "bitmap", "size": size, "base": base, "image": rel, "ascent": base / size,
            "line": line_height / size, "fallback": advances.get("n", size / 2) / size,
            "advances": {c: a / size for c, a in advances.items()}, "glyphs": glyphs}
