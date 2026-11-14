"""Tiled maps (.tmj, JSON) to the engine's tilemap format, at build time.

Supported: orthogonal maps, one tileset (embedded or an external .tsj), tile
layers stored as plain arrays (Tiled: Map > Map Properties > Tile Layer
Format = CSV), object layers, groups (flattened). Tile flip flags are
dropped. Anything else is a G1216 error saying what to change in Tiled.
"""
import json
import os

from ..errors import GameError


class TiledMap:
    def __init__(self):
        self.cols = self.rows = self.tile_w = self.tile_h = 0
        self.tileset = {}           # image (project-relative), columns, margin, spacing, firstgid, image_w, image_h
        self.layers = []            # (name, data, visible, properties)
        self.objects = []           # (key, x, y, w, h, props, name): key is the class/type, else the name
        self.tile_props = {}        # local tile id -> its Tiled properties (2.5D: "height", "side")


def _props(item):
    return {p.get("name"): p.get("value") for p in item.get("properties", []) or []}


def read(path, project_root, display, line=None):
    def fail(message, fix=()):
        raise GameError("G1216", "%s: %s" % (display, message), None, line, fix=fix)

    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError) as e:
        fail("not a Tiled JSON map (%s)" % e, "In Tiled: File > Export As... > JSON map files (*.tmj)")
    if raw.get("orientation", "orthogonal") != "orthogonal":
        fail("only orthogonal maps are supported")
    if raw.get("infinite"):
        fail("infinite maps are not supported", "In Tiled: Map > Map Properties > uncheck Infinite")
    m = TiledMap()
    m.cols, m.rows = raw["width"], raw["height"]
    m.tile_w, m.tile_h = raw["tilewidth"], raw["tileheight"]
    tilesets = raw.get("tilesets", [])
    if len(tilesets) != 1:
        fail("the map uses %d tilesets; one is supported" % len(tilesets), "Put all the tiles in one tileset image.")
    ts = tilesets[0]
    base = os.path.dirname(path)
    firstgid = ts.get("firstgid", 1)
    if "source" in ts:
        ts_path = os.path.normpath(os.path.join(base, ts["source"]))
        try:
            with open(ts_path, encoding="utf-8") as fh:
                ts = json.load(fh)
        except (OSError, ValueError):
            fail("cannot read the tileset %s (save it as JSON, .tsj)" % ts["source"])
        base = os.path.dirname(ts_path)
    if "image" not in ts:
        fail("the tileset is a collection of images; use one image", "Tileset > based on Tileset Image")
    image = os.path.normpath(os.path.join(base, ts["image"]))
    rel = os.path.relpath(image, project_root).replace("\\", "/")
    if rel.startswith("..") or not os.path.isfile(image):
        fail("the tileset image %s is not inside the project" % ts["image"])
    for tile in ts.get("tiles", []) or []:
        props = _props(tile)
        if props:
            m.tile_props[tile.get("id", 0)] = props
    m.tileset = {"image": rel, "columns": ts.get("columns") or 1, "margin": ts.get("margin", 0),
                 "spacing": ts.get("spacing", 0), "firstgid": firstgid,
                 "tile_w": ts.get("tilewidth", m.tile_w), "tile_h": ts.get("tileheight", m.tile_h)}

    def walk(layers, ox=0.0, oy=0.0):
        for layer in layers:
            kind = layer.get("type")
            lx, ly = ox + layer.get("offsetx", 0), oy + layer.get("offsety", 0)
            if kind == "group":
                walk(layer.get("layers", []), lx, ly)
            elif kind == "tilelayer":
                data = layer.get("data")
                if not isinstance(data, list):
                    fail("the layer %r is compressed/encoded" % layer.get("name"),
                         "In Tiled: Map > Map Properties > Tile Layer Format = CSV")
                m.layers.append((layer.get("name", ""), [d & 0x1FFFFFFF for d in data],
                                 layer.get("visible", True), _props(layer)))
            elif kind == "objectgroup":
                for o in layer.get("objects", []):
                    key = o.get("class") or o.get("type") or o.get("name") or ""
                    w, h = o.get("width", 0), o.get("height", 0)
                    x, y = o.get("x", 0) + lx, o.get("y", 0) + ly
                    if "gid" in o:              # a tile object: (x, y) is its bottom-left
                        y -= h
                    m.objects.append((key, x + w / 2, y + h / 2, w, h, _props(o), o.get("name") or None))
    walk(raw.get("layers", []))
    return m


def engine_json(m, solid_layers):
    """The tilemap as the engine reads it (tilemaps/NAME.json)."""
    names = [name for name, _, _, _ in m.layers]
    if solid_layers is None:
        solid_layers = [name for name, _, _, props in m.layers if props.get("solid") is True or name == "solid"]
    solid = [0] * (m.cols * m.rows)
    for name, data, _, _ in m.layers:
        if name in solid_layers:
            for i, gid in enumerate(data):
                if gid:
                    solid[i] = 1
    ts = m.tileset
    extra = _heights(m)
    return dict({"format": 1, "tile_w": m.tile_w, "tile_h": m.tile_h, "cols": m.cols, "rows": m.rows,
            "image": ts["image"], "columns": ts["columns"], "margin": ts["margin"], "spacing": ts["spacing"],
            "firstgid": ts["firstgid"],
            "layers": [{"name": name, "data": data, "visible": visible} for name, data, visible, _ in m.layers],
            "solid": solid}, **extra), names


def _number(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _heights(m):
    """2.5D: the height of each cell, in tiles (the highest of its tiles' "height" property, or of a layer's
    "height" property where that layer has a tile), and the tile used for the walls of a tile ("side").
    Nothing for a map without heights, so 2D maps convert exactly as before."""
    first = m.tileset.get("firstgid", 1)
    heights = [0.0] * (m.cols * m.rows)
    for _, data, _, props in m.layers:
        layer_h = _number(props.get("height"))
        for i, gid in enumerate(data):
            if not gid:
                continue
            tile_h = _number(m.tile_props.get(gid - first, {}).get("height"))
            heights[i] = max(heights[i], layer_h, tile_h)
    sides = {str(t): int(p["side"]) for t, p in m.tile_props.items()
             if isinstance(p.get("side"), int) and not isinstance(p.get("side"), bool)}
    out = {}
    if any(heights):
        out["heights"] = [int(h) if h == int(h) else h for h in heights]
    if sides:
        out["sides"] = sides
    tags = {str(t): {k: v for k, v in p.items() if k not in ("height", "side")} for t, p in m.tile_props.items()}
    tags = {t: p for t, p in tags.items() if p}
    if tags:
        out["tile_tags"] = tags                             # scene.tile_tag(x, y, "zone") in scripts
    return out
