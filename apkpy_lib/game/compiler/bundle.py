"""The model of the game to the bundle the engine reads (format 1).

    build/apkpygame/bundle/
        game.json
        scenes/<name>.json
        tilemaps/<name>.json                 Tiled maps, converted (compiler/tiled.py)
        texts.json                           the app's translations()
        <the project's asset paths>          images, sounds, music (as in the project)
        atlas/<name>.png                     packed atlases
        audio-desktop/<path>.wav             WAV copies for the desktop runner (not packed in the APK)
"""
import json
import os
import shutil

from .. import schema
from ..model import ActionValue, AssetRef, AtlasRef, EntityModel, SheetRef, TextRef, TilemapRef
from . import assets as pipeline
from . import tiled

FORMAT = 1


class _Writer:
    def __init__(self, out, regions, words):
        self.out, self.regions, self.words = out, regions, words

    def dump(self, rel, data):
        path = os.path.join(self.out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))

    # ── scenes and entities ──────────────────────────────────────────────

    def scene(self, s):
        out = {"format": FORMAT, "kind": s.kind}
        if s.on_back:
            out["on_back"] = [self.action(a) for a in s.on_back]
        if s.background:
            out["background"] = s.background
        if s.music:
            out["music"] = {"path": s.music.path, "volume": s.music_volume, "loop": True}
        if s.camera:
            out["camera"] = s.camera
        if s.vars:
            out["vars"] = s.vars
        if s.rules:
            out["rules"] = [self.rule(r) for r in s.rules]
        out["entities"] = [self.entity(e) for e in s.entities]
        return out

    def rule(self, r):
        out = {"var": r.var} if r.var else {"count": r.count}
        out.update({"op": r.op, "value": r.value, "actions": [self.action(a) for a in r.actions]})
        return out

    def entity(self, e):
        out = {"name": e.name}
        if e.tags:
            out["tags"] = e.tags
        if not e.active:
            out["active"] = False
        if e.ui:
            out["ui"] = True
        if e.props:
            out["props"] = e.props
        if e.marker:
            out["marker"] = e.marker
        if e.group:
            out["group"] = e.group
        if e.persistent:
            out["persistent"] = True
        if e.anchor:
            out["anchor"] = e.anchor
        transform = {"x": e.x, "y": e.y}
        if e.rotation:
            transform["rotation"] = e.rotation
        if e.elevation:
            transform["elevation"] = e.elevation
        if e.scale != 1:
            transform["scale"] = e.scale
        out["transform"] = transform
        sprite = next((c.values.get("image") for c in e.components if c.type == "Sprite"), None)
        out["components"] = [self.component(c, sprite) for c in e.components]
        if e.children:
            out["children"] = [self.entity(c) for c in e.children]
        return out

    def component(self, c, sprite_image):
        spec = schema.component(c.type)
        out = {"type": c.type}
        if spec is None:                                  # a script: its fields as they are
            for name, value in c.values.items():
                out[name] = self.value(value)
            return out
        for name, value in c.values.items():
            field = spec["fields"][name]
            if field.get("python_only"):
                continue
            key = field.get("json", name)
            if isinstance(value, TextRef):
                out["key"] = value.key                   # the engine looks it up in texts.json
                out[key] = self.words.get(value.key, value.key)
            elif field["type"] == "image" and isinstance(value, (AtlasRef, SheetRef)):
                out[key] = self.image_path(value)
                if c.type in ("Sprite", "Canvas"):
                    out["region"] = self.frame(value, c.values.get("frame", 0))
                if c.type == "Billboard" and isinstance(value, SheetRef):
                    out["frame_size"] = [value.frame_w, value.frame_h]
            elif field["type"] == "tilemap":
                out[key] = self.tilemap(value, c.values.get("solid"))
            elif field["type"] == "animations":
                out[key] = {n: {"frames": [self.frame(sprite_image, f) for f in a["frames"]],
                                "fps": a.get("fps", 8), "loop": a.get("loop", True)} for n, a in value.items()}
            else:
                out[key] = self.value(value)
        return out

    def image_path(self, ref):
        if isinstance(ref, AtlasRef):
            return "atlas/%s.png" % ref.name
        return ref.path

    def frame(self, ref, f):
        if isinstance(ref, SheetRef):
            return ref.region(f)
        return self.regions[ref.pattern][ref.frame_index(f)]

    def tilemap(self, ref, solid):
        data, _ = tiled.engine_json(ref.data, solid)
        rel = "tilemaps/%s.json" % ref.name
        self.dump(rel, data)
        return rel

    def value(self, v):
        if isinstance(v, AssetRef):
            return v.path
        if isinstance(v, (AtlasRef, SheetRef)):
            return self.image_path(v)
        if isinstance(v, EntityModel):
            return self.entity(v)
        if isinstance(v, ActionValue):
            return self.action(v)
        if isinstance(v, (list, tuple)):
            return [self.value(x) for x in v]
        if isinstance(v, dict):
            return {k: self.value(x) for k, x in v.items()}
        return v

    def action(self, a):
        spec = schema.action(a.name)
        out = {"do": a.do}
        for name, value in a.values.items():
            out[spec["fields"][name].get("json", name)] = self.value(value)
        return out


def write(model, project, app=None):
    """app: what compiler.app read from writehere.py (texts), or None."""
    out = project.bundle_dir
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "scenes"))
    regions = {}
    warnings = []
    for ref in model.assets:
        if isinstance(ref, AtlasRef):
            regions[ref.pattern] = pipeline.pack_atlas(project.root, ref, os.path.join(out, "atlas", ref.name + ".png"))
            continue
        if isinstance(ref, TilemapRef):
            continue                                  # written with the Tilemap component (its solid layers)
        src = os.path.join(project.root, ref.path)
        dst = os.path.join(out, ref.path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        if ref.kind in ("sound", "music") and not ref.path.lower().endswith(".wav"):   # WAV is read as it is
            wav = pipeline.desktop_wav(src, project.cache_dir, ref.path)
            if wav:
                target = os.path.join(out, "audio-desktop", ref.path + ".wav")
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(wav, target)
            else:
                warnings.append("no desktop copy of %s (ffmpeg missing?): silent on the PC only" % ref.path)

    words = {}
    if app is not None and app.languages:
        words = app.languages.get(app.default, {})
    w = _Writer(out, regions, words)
    start = next(s.name for s in model.scenes if s.start)
    game = {"format": FORMAT, "name": model.name, "size": list(model.size), "scale": model.scale,
            "orientation": model.orientation, "background": model.background, "start_scene": start,
            "fixed_hz": model.fixed_hz, "debug": model.debug, "seed": model.seed, "renderer": model.renderer,
            "scenes": [s.name for s in model.scenes]}
    if model.vars:
        game["vars"] = model.vars
    if model.font is not None:
        game["font"] = model.font.path
    if model.pixel_scale:
        game["pixel_scale"] = True
    w.dump("game.json", game)
    for path, measures in model.fonts.items():
        w.dump(path + ".json", measures)
    for v, rows in model.tables:
        w.dump("tables/%s.json" % v.path, rows)
    if app is not None and app.languages:
        w.dump("texts.json", {"default": app.default, "languages": app.languages})
    for scene in model.scenes:
        w.dump("scenes/%s.json" % scene.name, w.scene(scene))
    return {"bundle": out, "scenes": [s.name for s in model.scenes], "assets": len(model.assets),
            "entities": sum(_count(e) for s in model.scenes for e in s.entities), "warnings": warnings}


def _count(e):
    return 1 + sum(_count(c) for c in e.children)
