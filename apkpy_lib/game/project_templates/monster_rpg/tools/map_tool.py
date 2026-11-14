"""Turns the text maps of maps_src/ into the maps the game reads (maps/*.tmj). The build runs it for you (see tools/prepare.py).

    python tools/map_tool.py                  every map that changed
    python tools/map_tool.py --view village   a picture of the map with a ruler: build/map_views/village.png
    python tools/map_tool.py --force          also overwrite a map that was changed by hand

A map file:

    # a comment
    tiles:
    cccc,ccc
    c...,..c
    c.rr,..c
    cccccccc
    objects:
    link 4 0 route
    person 2 2 sam look=villager event=village.sam

The letters come from maps_src/legend.txt. A map can add its own above "tiles:", such as  x = snow solid.
An object is: <kind> <column> <row> [name] [key=value...]. Columns and rows count from 0, from the top left corner.

The kinds that are more than one thing (the rest are keys of OBJECTS in game/main.py):

    house_red 3 2 inside=house           a building: its top left corner. It makes the walls solid, puts a door in the
                                         middle of its front, and links it with the map called "house"
    house_blue 14 2 event=village.locked a building whose door plays an event instead
    exit 3 6 width=2                     the way out of the map a building leads to
    link 10 0 route width=2              walking here goes to the map "route", which has a link back here
    trainer 5 17 tess look=rival         by itself it plays the event trainer.tess and uses the flag beat_tess

width=N or height=N repeat an object over N cells. to= and at= still work on warp, door and exit for anything else.

A .tmj with no .map is left alone: to go on in Tiled, delete the .map (see README.md).
"""
import ast
import difflib
import hashlib
import io
import json
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "maps_src")
OUTPUT = os.path.join(ROOT, "maps")
TILES = os.path.join(ROOT, "assets", "tiles")
MAIN = os.path.join(ROOT, "game", "main.py")
TILE = 16
REPEATS = ("warp", "trigger", "exit", "door", "link")


class MapError(Exception):
    pass


def maybe(word, options):
    close = difflib.get_close_matches(word, list(options), 1)
    return " Did you mean %r?" % close[0] if close else ""


def value(text):
    if text in ("true", "false"):
        return text == "true"
    try:
        return int(text)
    except ValueError:
        return text


def prop(name, v):
    kind = "bool" if isinstance(v, bool) else "int" if isinstance(v, int) else "string"
    return {"name": name, "type": kind, "value": v}


def tile_names():
    if not os.path.isdir(TILES):
        return []
    return sorted(n[:-4] for n in os.listdir(TILES) if n.endswith(".png") and not n.endswith("_edges.png"))


def legend_line(text, where, names):
    """x = snow solid height=1 zone=reeds"""
    letter, what = text.split(" = ", 1)
    words = what.split()
    letter = letter.strip()
    if len(letter) != 1:
        raise MapError("%s: %r: a map's letter is one character" % (where, letter))
    if not words or words[0] not in names:
        name = words[0] if words else ""
        raise MapError("%s: there is no tile %r, so no file assets/tiles/%s.png.%s" % (where, name, name, maybe(name, names)))
    entry = {"tile": words[0], "solid": False, "height": 0, "zone": "", "edges": False}
    for word in words[1:]:
        if word == "solid":
            entry["solid"] = True
        elif word == "edges":
            entry["edges"] = True
        elif word.isdigit():
            entry["height"] = int(word)
        elif word.startswith("height="):
            entry["height"] = int(word[7:])
        elif word.startswith("zone="):
            entry["zone"] = word[5:]
        else:
            raise MapError("%s: I do not know %r. A letter can have: solid, height=N, zone=NAME, edges" % (where, word))
    return letter, entry


def read_legend(names):
    legend = {}
    path = os.path.join(SOURCE, "legend.txt")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            for number, raw in enumerate(fh, 1):
                line = raw.rstrip("\n")
                if line.strip() and not line.lstrip().startswith("#"):
                    letter, entry = legend_line(line, "maps_src/legend.txt:%d" % number, names)
                    legend[letter] = entry
    return legend


class Map:
    def __init__(self, name):
        self.name = name
        self.rel = "maps_src/%s.map" % name
        self.rows = []
        self.legend = {}
        self.objects = []        # dicts: kind, col, row, name, props, line
        self.extra_solid = set()
        self.cols = 0

    def where(self, line):
        return "%s:%d" % (self.rel, line)

    def solid_at(self, col, row):
        if (col, row) in self.extra_solid:
            return True
        return self.legend[self.rows[row][col]]["solid"]

    def inside(self, col, row):
        return 0 <= col < self.cols and 0 <= row < len(self.rows)

    def free_next_to(self, col, row, line):
        """Where someone arriving through this cell stands."""
        col = int(col)
        row = int(row)
        for dc, dr in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            if self.inside(col + dc, row + dr) and not self.solid_at(col + dc, row + dr):
                return col + dc, row + dr
        raise MapError("%s: there is no free cell next to (%d, %d) for arriving at" % (self.where(line), col, row))

    def add(self, kind, col, row, name="", props=None, line=0):
        o = {"kind": kind, "col": col, "row": row, "name": name, "props": dict(props or {}), "line": line}
        self.objects.append(o)
        return o


def read_map(name, base_legend, names, text=None):
    """text: what the file would say (the map editor, before saving)."""
    m = Map(name)
    m.legend = dict(base_legend)
    size, part = None, "head"
    with (io.StringIO(text) if text is not None else open(os.path.join(SOURCE, name + ".map"), encoding="utf-8")) as fh:
        for number, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            text = line.strip()
            if text == "tiles:":
                part = "tiles"
            elif text == "objects:":
                part = "objects"
            elif part == "tiles":
                if text:
                    m.rows.append((text, number))
            elif not text or text.startswith("#"):
                continue
            elif part == "objects":
                words = text.split(" #")[0].split()
                if len(words) < 3:
                    raise MapError("%s: %r: an object is  <kind> <column> <row> [name] [key=value...]" % (m.where(number), text))
                try:
                    col, row = float(words[1]), float(words[2])
                except ValueError:
                    raise MapError("%s: %r: the column and the row are numbers" % (m.where(number), text))
                o = m.add(words[0], col, row, line=number)
                for word in words[3:]:
                    if "=" in word:
                        k, v = word.split("=", 1)
                        o["props"][k] = value(v)
                    else:
                        o["name"] = word
            elif text.startswith("size:"):
                size = [int(x) for x in text.split()[1:]]
            elif " = " in line:
                letter, entry = legend_line(line, m.where(number), names)
                m.legend[letter] = entry
            else:
                raise MapError("%s: %r: above 'tiles:' only letters and comments can go" % (m.where(number), text))
    if not m.rows:
        raise MapError("%s: it has no 'tiles:' part" % m.rel)
    m.cols = len(m.rows[0][0])
    for text, number in m.rows:
        if len(text) != m.cols:
            raise MapError("%s: this row has %d letters, and the first row has %d" % (m.where(number), len(text), m.cols))
        for letter in text:
            if letter not in m.legend:
                raise MapError("%s: the letter %r is not in maps_src/legend.txt or above 'tiles:' in this map" % (m.where(number), letter))
    m.rows_lines = [n for _, n in m.rows]
    m.rows = [t for t, _ in m.rows]
    if size is not None and size != [m.cols, len(m.rows)]:
        raise MapError("%s: size says %s, but the drawing is %d x %d (you can just delete the size line)" % (m.rel, size, m.cols, len(m.rows)))
    return m


def read_objects_table():
    """{kind: (width, depth) in cells, or None}: the keys of OBJECTS in game/main.py, and the size of the buildings."""
    with open(MAIN, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    table = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "OBJECTS":
            for key, val in zip(node.value.keys, node.value.values):
                size = None
                if isinstance(val, ast.Call) and getattr(val.func, "id", "") == "house":
                    numbers = [a.value for a in val.args if isinstance(a, ast.Constant)]
                    size = (numbers[0], numbers[1]) if len(numbers) >= 2 else (5, 3)
                table[key.value] = size
    return table


def expand(maps, table):
    """Buildings, links, exits and repeats become the plain objects the game knows."""
    known = set(table) | {"link"}
    outer = {}                 # interior map: (building's map, door's column, the row in front of the door, line)
    for m in maps.values():
        plain = []
        for o in m.objects:
            if o["kind"] not in known:
                raise MapError("%s: there is no object %r (see OBJECTS in game/main.py).%s" % (m.where(o["line"]), o["kind"], maybe(o["kind"], known)))
            if not m.inside(int(o["col"]), int(o["row"])):
                raise MapError("%s: (%g, %g) is outside the map, which has columns 0-%d and rows 0-%d" % (m.where(o["line"]), o["col"], o["row"], m.cols - 1, len(m.rows) - 1))
            if o["kind"] == "link" and o["name"]:           # link 10 0 route
                o["props"]["to"] = o["name"]
                o["name"] = ""
            width = o["props"].pop("width", 1) if o["kind"] in REPEATS else 1
            height = o["props"].pop("height", 1) if o["kind"] in REPEATS else 1
            for w in range(width):
                for h in range(height):
                    copy = dict(o, props=dict(o["props"]), col=o["col"] + w, row=o["row"] + h, first=(w == 0 and h == 0))
                    if copy["name"] and (w or h):
                        copy["name"] = "%s_%d" % (o["name"], w + h + 1)
                    plain.append(copy)
        m.objects = plain
    for m in maps.values():
        for o in list(m.objects):
            size = table.get(o["kind"])
            if size:
                expand_building(m, o, size, maps, outer)
    for m in maps.values():
        for o in m.objects:
            if o["kind"] in ("exit", "door"):
                m.extra_solid.add((int(o["col"]), int(o["row"])))
    arrivals = {}
    for m in maps.values():
        for o in list(m.objects):
            if o["kind"] == "exit" and "to" not in o["props"] and "event" not in o["props"]:
                expand_exit(m, o, outer, arrivals)
    expand_links(maps, arrivals)
    for m in maps.values():
        for o in m.objects:
            if o["kind"] == "trainer":
                who = o["name"]
                if not who:
                    raise MapError("%s: a trainer needs its name: trainer 5 17 tess" % m.where(o["line"]))
                o["props"].setdefault("event", "trainer." + who)
                o["props"].setdefault("flag", "beat_" + who)
            if o["kind"] == "marker" and m.inside(int(o["col"]), int(o["row"])) and m.solid_at(int(o["col"]), int(o["row"])):
                raise MapError("%s: the marker %r is on a solid cell, so whoever arrives there is stuck" % (m.where(o["line"]), o["name"]))


def expand_building(m, o, size, maps, outer):
    width, depth = size
    col, row = int(o["col"]), int(o["row"])
    if col + width > m.cols or row + depth > len(m.rows):
        raise MapError("%s: this %s is %d x %d, so it does not fit at (%d, %d)" % (m.where(o["line"]), o["kind"], width, depth, col, row))
    for c in range(col, col + width):
        for r in range(row, row + depth):
            m.extra_solid.add((c, r))
    o["col"] = col + width / 2 - 0.5
    o["row"] = row + depth / 2 - 0.5
    inside = o["props"].pop("inside", None)
    event = o["props"].pop("event", None)
    door_col = col + width // 2
    front = row + depth
    if inside is not None:
        if inside not in maps:
            raise MapError("%s: inside=%s, but there is no maps_src/%s.map.%s" % (m.where(o["line"]), inside, inside, maybe(str(inside), maps)))
        if inside in outer:
            raise MapError("%s: another building already leads to the map %s, and its exit can only go back to one" % (m.where(o["line"]), inside))
        if not m.inside(door_col, front) or m.solid_at(door_col, front):
            raise MapError("%s: the cell in front of this building's door, (%d, %d), has to be free" % (m.where(o["line"]), door_col, front))
        outer[inside] = (m, door_col, front, o["line"])
        m.add("door", door_col, front - 1, "door_" + inside, {"to": inside, "at": "from_" + m.name}, o["line"])
        m.add("marker", door_col, front, "from_" + inside, line=o["line"])
    elif event is not None:
        m.add("door", door_col, front - 1, "door", {"event": event}, o["line"])


def expand_exit(m, o, outer, arrivals):
    if m.name not in outer:
        raise MapError("%s: this exit does not know where to go: no building says inside=%s. Add that to one, or write to= and at= here"
                       % (m.where(o["line"]), m.name))
    place = outer[m.name][0]
    o["props"]["to"] = place.name
    o["props"]["at"] = "from_" + m.name
    if o.get("first", True):
        col, row = m.free_next_to(o["col"], o["row"], o["line"])
        m.add("marker", col, row, "from_" + place.name, line=o["line"])


def expand_links(maps, arrivals):
    pending = {}
    for m in maps.values():
        for o in m.objects:
            if o["kind"] == "link" and o.get("first", True):
                target = o["props"].get("to", "")
                if target not in maps:
                    raise MapError("%s: link goes to the map %r, but there is no maps_src/%s.map.%s" % (m.where(o["line"]), target, target, maybe(str(target), maps)))
                pending.setdefault((m.name, target), []).append(o)
    for (a, b), links in pending.items():
        if len(pending.get((b, a), [])) != len(links):
            o = links[0]
            raise MapError("%s: this link goes to %s, so %s needs a link back to %s: link <column> <row> %s" % (maps[a].where(o["line"]), b, b, a, a))
    for m in maps.values():
        plain = []
        for o in m.objects:
            if o["kind"] != "link":
                plain.append(o)
                continue
            target = o["props"]["to"]
            o["kind"] = "warp"
            o["name"] = "to_" + target
            o["props"]["to"] = target
            o["props"]["at"] = "from_" + m.name
            plain.append(o)
            if o.get("first", True):
                col, row = m.free_next_to(o["col"], o["row"], o["line"])
                plain.append({"kind": "marker", "col": col, "row": row, "name": "from_" + target, "props": {}, "line": o["line"]})
        m.objects = plain


def to_tmj(m, names, variants=None):
    variants = variants or {}
    cols, nrows = m.cols, len(m.rows)
    gid = {n: i + 1 for i, n in enumerate(names)}
    count = len(names) + len(variants)
    ground, solid, high = [], [], {}
    for r, row in enumerate(m.rows):
        for c, letter in enumerate(row):
            spec = m.legend[letter]
            art = cell_art(m.rows, m.legend, c, r)
            ground.append(len(names) + 1 + variants[art] if art[2] else gid[spec["tile"]])
            solid.append(gid[spec["tile"]] if spec["solid"] or (c, r) in m.extra_solid else 0)
            if spec["height"]:
                high.setdefault(spec["height"], [0] * (cols * nrows))[r * cols + c] = gid[spec["tile"]]
    layers = [{"id": 1, "type": "tilelayer", "name": "ground", "width": cols, "height": nrows, "x": 0, "y": 0,
               "opacity": 1, "visible": True, "data": ground},
              {"id": 2, "type": "tilelayer", "name": "solid", "width": cols, "height": nrows, "x": 0, "y": 0,
               "opacity": 1, "visible": False, "data": solid}]
    for i, (h, data) in enumerate(sorted(high.items())):
        layers.append({"id": 3 + i, "type": "tilelayer", "name": "height%d" % h, "width": cols, "height": nrows, "x": 0,
                       "y": 0, "opacity": 1, "visible": False, "data": data, "properties": [prop("height", h)]})
    layers.append({"id": 90, "type": "objectgroup", "name": "objects", "x": 0, "y": 0, "opacity": 1, "visible": True,
                   "objects": [{"id": i + 1, "name": o["name"], "type": o["kind"], "x": o["col"] * TILE + TILE / 2,
                                "y": o["row"] * TILE + TILE / 2, "width": 0, "height": 0, "point": True, "rotation": 0,
                                "visible": True, "properties": [prop(k, v) for k, v in o["props"].items()]}
                               for i, o in enumerate(m.objects)]})
    zones = {}
    used = {letter for row in m.rows for letter in row}
    for letter in sorted(used):
        spec = m.legend[letter]
        if spec["zone"]:
            zones[spec["tile"]] = spec["zone"]
    tiles = [{"id": gid[t] - 1, "properties": [prop("zone", z)]} for t, z in sorted(zones.items())]
    tiles += [{"id": len(names) + i, "properties": [prop("zone", zones[art[0]])]} for art, i in sorted(variants.items(), key=lambda v: v[1]) if art[0] in zones]
    return {"type": "map", "version": "1.10", "orientation": "orthogonal", "renderorder": "right-down", "infinite": False,
            "width": cols, "height": nrows, "tilewidth": TILE, "tileheight": TILE, "nextobjectid": len(m.objects) + 1,
            "nextlayerid": 91, "layers": layers,
            "tilesets": [{"firstgid": 1, "name": "tiles", "image": "tiles.png", "imagewidth": TILE * count,
                          "imageheight": TILE, "tilewidth": TILE, "tileheight": TILE, "columns": count,
                          "tilecount": count, "margin": 0, "spacing": 0, "tiles": tiles}]}


def cell_art(rows, legend, col, row):
    """What a cell shows: (tile, the tile under its edges or None, which sides are cut: 1 up, 2 right, 4 down, 8 left).
    A letter with "edges" is cut where it meets flat ground of another kind, and that ground shows through."""
    entry = legend[rows[row][col]]
    if not entry["edges"] or entry["height"]:
        return entry["tile"], None, 0
    mask, seen = 0, []
    for bit, dc, dr in ((1, 0, -1), (2, 1, 0), (4, 0, 1), (8, -1, 0)):
        c, r = col + dc, row + dr
        if 0 <= r < len(rows) and 0 <= c < len(rows[r]):
            other = legend[rows[r][c]]
            if other["tile"] != entry["tile"] and not other["edges"] and not other["height"]:
                mask |= bit
                seen.append(other["tile"])
    if not mask:
        return entry["tile"], None, 0
    return entry["tile"], max(sorted(set(seen)), key=seen.count), mask


def edge_tile(tile, under, mask):
    """The picture of a cut cell. assets/tiles/<tile>_edges.png, if you drew one, gives the 16 cuts: 4 x 4 cells, in order of mask."""
    with Image.open(os.path.join(TILES, under + ".png")) as img:
        out = img.convert("RGBA")
    drawn = os.path.join(TILES, tile + "_edges.png")
    if os.path.isfile(drawn):
        with Image.open(drawn) as img:
            x, y = (mask % 4) * TILE, (mask // 4) * TILE
            cell = img.convert("RGBA").crop((x, y, x + TILE, y + TILE))
        out.alpha_composite(cell)
        return out
    with Image.open(os.path.join(TILES, tile + ".png")) as img:
        top = img.convert("RGBA")
    last = TILE - 1

    def kept(x, y):
        if not (0 <= x <= last and 0 <= y <= last):
            return True
        if (mask & 1 and y < 2) or (mask & 2 and x > last - 2) or (mask & 4 and y > last - 2) or (mask & 8 and x < 2):
            return False
        return not ((mask & 9 == 9 and x + y < 6) or (mask & 3 == 3 and last - x + y < 6)
                    or (mask & 12 == 12 and x + last - y < 6) or (mask & 6 == 6 and last - x + last - y < 6))

    for y in range(TILE):
        for x in range(TILE):
            if kept(x, y):
                r, g, b, a = top.getpixel((x, y))
                if not all(kept(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    r, g, b = r * 4 // 5, g * 4 // 5, b * 4 // 5        # a darker line along the cut
                out.putpixel((x, y), (r, g, b, a))
    return out


def all_variants(maps):
    """Every cut cell used by any map: {(tile, under, mask): its place after the plain tiles}."""
    found = set()
    for m in maps.values():
        for r in range(len(m.rows)):
            for c in range(m.cols):
                art = cell_art(m.rows, m.legend, c, r)
                if art[2]:
                    found.add(art)
    return {art: i for i, art in enumerate(sorted(found))}


def stamp_of(tmj):
    plain = {k: v for k, v in tmj.items() if k != "properties"}
    return hashlib.sha256(json.dumps(plain, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def changed_by_hand(path):
    try:
        with open(path, encoding="utf-8") as fh:
            old = json.load(fh)
        marks = {p["name"]: p["value"] for p in old.get("properties", [])}
        return marks.get("made_by_map_tool") != stamp_of(old)
    except (ValueError, KeyError, TypeError):
        return True


def write_tileset(names, variants=None):
    variants = variants or {}
    if not names:
        raise MapError("there are no tiles in assets/tiles/ (python tools/make_art.py draws placeholders)")
    sheet = Image.new("RGBA", (TILE * (len(names) + len(variants)), TILE))
    for art, i in variants.items():
        sheet.paste(edge_tile(*art), ((len(names) + i) * TILE, 0))
    for i, name in enumerate(names):
        with Image.open(os.path.join(TILES, name + ".png")) as img:
            if img.size != (TILE, TILE):
                raise MapError("assets/tiles/%s.png is %d x %d: a tile is %d x %d" % (name, img.size[0], img.size[1], TILE, TILE))
            sheet.paste(img.convert("RGBA"), (i * TILE, 0))
    path = os.path.join(OUTPUT, "tiles.png")
    if os.path.isfile(path):
        with Image.open(path) as old:
            if old.size == sheet.size and old.convert("RGBA").tobytes() == sheet.tobytes():
                return
    sheet.save(path)


def add_missing_scenes(names):
    """A map with no scene yet gets one at the end of game/main.py, to be changed there if you like."""
    with open(MAIN, encoding="utf-8") as fh:
        text = fh.read()
    added = []
    for name in names:
        if "maps/%s.tmj" % name not in text:
            var = name + "_map"
            added.append('\n%s = game.scene("%s", kind="2.5d", camera=CAMERA, music=town_music, music_volume=0.5, background="#7cb4d8")\n'
                         '%s.add(Entity("map", Tilemap(assets.tilemap("maps/%s.tmj"), solid=["solid"], objects=OBJECTS)))\n'
                         '%s.add(hero())\n%s.add(hud())\n' % (var, name, var, name, var, var))
            print("game/main.py: added a scene for the map %s" % name)
    if added:
        with open(MAIN, "a", encoding="utf-8") as fh:
            fh.write("".join(added))


def load_all(texts=None):
    names = tile_names()
    base = read_legend(names)
    found = sorted(n[:-4] for n in os.listdir(SOURCE) if n.endswith(".map"))
    return {n: read_map(n, base, names, (texts or {}).get(n)) for n in found}, names


def convert_all(only=None, force=False):
    os.makedirs(OUTPUT, exist_ok=True)
    maps, names = load_all()
    expand(maps, read_objects_table())
    variants = all_variants(maps)
    write_tileset(names, variants)
    for name, m in maps.items():
        if only and name not in only:
            continue
        tmj = to_tmj(m, names, variants)
        tmj["properties"] = [prop("made_by_map_tool", stamp_of(tmj)), prop("do_not_edit", "change %s instead" % m.rel)]
        path = os.path.join(OUTPUT, name + ".tmj")
        text = json.dumps(tmj, indent=1)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                if fh.read() == text:
                    continue
            if not force and changed_by_hand(path):
                raise MapError("maps/%s.tmj was changed by hand (in Tiled?), and building from %s would lose that.\n"
                               "  To keep the change: delete %s. Then the .tmj is the map, and you go on in Tiled.\n"
                               "  To lose it: python tools/map_tool.py --force" % (name, m.rel, m.rel))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("maps/%s.tmj" % name)
    add_missing_scenes(sorted(maps))
    return maps


def draw_view(m, names, scale=2):
    """The map with a ruler, its tiles and its objects."""
    cell = TILE * scale
    pad = cell
    img = Image.new("RGB", (pad + m.cols * cell, pad + len(m.rows) * cell), "white")
    draw = ImageDraw.Draw(img)
    tiles = {}
    for n in names:
        with Image.open(os.path.join(TILES, n + ".png")) as t:
            tiles[n] = t.convert("RGB").resize((cell, cell), Image.NEAREST)
    for r, row in enumerate(m.rows):
        draw.text((4, pad + r * cell + cell // 3), str(r), fill="black")
        for c, letter in enumerate(row):
            art = cell_art(m.rows, m.legend, c, r)
            picture = edge_tile(*art).convert("RGB").resize((cell, cell), Image.NEAREST) if art[2] else tiles[m.legend[letter]["tile"]]
            img.paste(picture, (pad + c * cell, pad + r * cell))
    for c in range(m.cols):
        draw.text((pad + c * cell + cell // 3, 8), str(c), fill="black")
    for (c, r) in m.extra_solid:
        draw.rectangle([pad + c * cell, pad + r * cell, pad + (c + 1) * cell - 1, pad + (r + 1) * cell - 1], outline="black")
    for o in m.objects:
        x, y = pad + o["col"] * cell, pad + o["row"] * cell
        draw.rectangle([x + 3, y + 3, x + cell - 4, y + cell - 4], outline="red", width=2)
        draw.text((x + 1, y + cell // 3), (o["name"] or o["kind"])[:7], fill="white", stroke_width=1, stroke_fill="black")
    return img


def view(name):
    maps, names = load_all()
    if name not in maps:
        raise MapError("there is no maps_src/%s.map.%s" % (name, maybe(name, maps)))
    expand(maps, read_objects_table())
    folder = os.path.join(ROOT, "build", "map_views")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name + ".png")
    draw_view(maps[name], names).save(path)
    print(os.path.relpath(path, ROOT).replace("\\", "/"))


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if "--view" in args:
            view(args[args.index("--view") + 1])
            return
        force = "--force" in args
        convert_all([a for a in args if a != "--force"] or None, force)
    except MapError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
