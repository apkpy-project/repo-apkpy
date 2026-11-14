"""Writes the phase-1 example bundle (dev machine only): 500 / 2000 rotating sprites.

    python tools/game/dev/make_stress_example.py

The bundle is written by hand-rolled data here because the Python authoring
side (apkpygame build) is phase 2. Output: examples/games/stress/bundle/.
"""
import json
import math
import os
import sys
import random

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))      # ApkPy's repository
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import where  # noqa: E402
TOOLS = os.path.join(ROOT, "tools", "game")
SRC = ROOT
BUNDLE = where.examples("stress", "bundle")
COLORS = ["#ff5c8a", "#5cd6ff", "#ffd45c", "#8aff5c", "#c45cff", "#ff9b5c"]


def star(path, size=32):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = size / 2
    points = []
    for i in range(10):
        r = c - 1 if i % 2 == 0 else c * 0.42
        a = math.pi / 2 + i * math.pi / 5
        points.append((c + r * math.cos(a), c - r * math.sin(a)))
    d.polygon(points, fill=(255, 255, 255, 255))
    img.save(path)


def scene(count, seed):
    rng = random.Random(seed)
    entities = []
    for i in range(count):
        entities.append({
            "name": "star%d" % i,
            "tags": ["star"],
            "transform": {"x": round(rng.uniform(0, 360), 3), "y": round(rng.uniform(0, 640), 3),
                          "rotation": round(rng.uniform(0, 360), 3), "scale": round(rng.uniform(0.5, 1.2), 3)},
            "components": [
                {"type": "Sprite", "image": "images/star.png", "tint": COLORS[i % len(COLORS)]},
                {"type": "Spin", "speed": round(rng.uniform(-240, 240), 3)},
                {"type": "Mover", "velocity": [round(rng.uniform(-90, 90), 3), round(rng.uniform(-90, 90), 3)],
                 "bounce": True},
            ],
        })
    entities.append({"name": "title", "transform": {"x": 180, "y": 600},
                     "components": [{"type": "Shape", "size": [300, 44], "color": "#000000", "alpha": 0.6,
                                     "layer": 9},
                                    {"type": "Text", "text": "ApkPyGame 0.1 - %d sprites" % count, "size": 18,
                                     "align": "center", "layer": 10}],
                     "children": [{"name": "dot", "transform": {"x": -140, "y": -5},
                                   "components": [{"type": "Shape", "shape": "circle", "radius": 5,
                                                   "color": "#5cd6ff", "layer": 10},
                                                  {"type": "Spin", "speed": 180}]}]})
    return {"format": 1, "kind": "2d", "background": "#0b0e1a", "entities": entities}


def main():
    os.makedirs(os.path.join(BUNDLE, "images"), exist_ok=True)
    os.makedirs(os.path.join(BUNDLE, "scenes"), exist_ok=True)
    star(os.path.join(BUNDLE, "images", "star.png"))
    game = {"format": 1, "name": "Stress", "size": [360, 640], "scale": "fit", "orientation": "portrait",
            "background": "#000000", "start_scene": "main", "fixed_hz": 60, "debug": True, "seed": 1}
    with open(os.path.join(BUNDLE, "game.json"), "w", encoding="utf-8") as fh:
        json.dump(game, fh, indent=1)
    for name, count in (("main", 500), ("heavy", 2000), ("huge", 5000)):
        with open(os.path.join(BUNDLE, "scenes", name + ".json"), "w", encoding="utf-8") as fh:
            json.dump(scene(count, 11), fh, separators=(",", ":"))
    print("bundle:", BUNDLE)


if __name__ == "__main__":
    main()
