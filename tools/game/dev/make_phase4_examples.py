"""Creates the two phase-4 example games (dev machine only), with their own art and sound.

    python src/dev/make_phase4_examples.py

src/examples/ships       portrait: a ship shoots falling rocks (touch to move; it fires by itself)
src/examples/platformer  landscape: a Tiled level, run/jump, coins, slimes to stomp, a flag

Both are games made only of components (no code), inside the "menus" ApkPy app
(home, shop, pause, results): coins earned in the game are spent in the shop.
"""
import json
import math
import os
import random
import shutil
import struct
import sys
import wave

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))      # ApkPy's repository
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import where  # noqa: E402
TOOLS = os.path.join(ROOT, "tools", "game")
SRC = ROOT
sys.path.insert(0, ROOT)
from apkpy_lib.game import glue, templates  # noqa: E402

RATE = 22050


# ── sound ────────────────────────────────────────────────────────────────

def write_wav(path, samples):
    with wave.open(path, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32000)) for s in samples))


def sweep(f0, f1, seconds, volume=0.6, noise=0.0, seed=1):
    rng = random.Random(seed)
    n = int(RATE * seconds)
    phase = 0.0
    out = []
    for i in range(n):
        u = i / n
        phase += 2 * math.pi * (f0 + (f1 - f0) * u) / RATE
        tone = math.sin(phase) * (1 - noise) + rng.uniform(-1, 1) * noise
        out.append(tone * volume * (1 - u) ** 1.5)
    return out


def tune(notes, beat, volume=0.22):
    out = []
    n = int(RATE * beat)
    for f in notes:
        for i in range(n):
            t = i / RATE
            env = min(1, i / 300) * (1 - i / n) ** 0.6
            v = 0 if f == 0 else (math.sin(2 * math.pi * f * t) + 0.35 * math.sin(4 * math.pi * f * t)
                                  + 0.15 * math.sin(6 * math.pi * f * t))
            out.append(v * env * volume)
    return out


# ── art ──────────────────────────────────────────────────────────────────

def ship_png(path):
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(16, 1), (29, 29), (16, 23), (3, 29)], fill=(92, 214, 255, 255))
    d.polygon([(16, 8), (21, 22), (16, 19), (11, 22)], fill=(230, 250, 255, 255))
    img.save(path)


def rock_png(path, seed):
    rng = random.Random(seed)
    img = Image.new("RGBA", (36, 36), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pts = []
    for i in range(9):
        a = i * 2 * math.pi / 9
        r = rng.uniform(12, 17)
        pts.append((18 + r * math.cos(a), 18 + r * math.sin(a)))
    d.polygon(pts, fill=(150, 120, 105, 255))
    for _ in range(4):
        x, y = rng.uniform(9, 25), rng.uniform(9, 25)
        d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(110, 88, 78, 255))
    img.save(path)


def tiles_png(path):
    """8 tiles of 16x16 in a row: 1 grass, 2 dirt, 3 brick, 4 stone, 5 tuft, 6 flower, 7 bush, 8 sign."""
    img = Image.new("RGBA", (128, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rng = random.Random(3)
    # grass top
    d.rectangle([0, 0, 15, 15], fill=(120, 80, 50, 255))
    d.rectangle([0, 0, 15, 4], fill=(90, 190, 80, 255))
    # dirt
    d.rectangle([16, 0, 31, 15], fill=(120, 80, 50, 255))
    for _ in range(6):
        x, y = rng.randint(17, 30), rng.randint(1, 14)
        d.point((x, y), fill=(95, 62, 40, 255))
    # brick
    d.rectangle([32, 0, 47, 15], fill=(170, 80, 60, 255))
    for y in (4, 9, 14):
        d.line([32, y, 47, y], fill=(120, 55, 45, 255))
    d.line([39, 0, 39, 4], fill=(120, 55, 45, 255))
    d.line([35, 5, 35, 9], fill=(120, 55, 45, 255))
    d.line([43, 5, 43, 9], fill=(120, 55, 45, 255))
    # stone
    d.rectangle([48, 0, 63, 15], fill=(110, 115, 130, 255))
    d.rectangle([49, 1, 62, 14], outline=(80, 85, 100, 255))
    # tuft
    d.polygon([(66, 15), (68, 9), (70, 15)], fill=(90, 190, 80, 255))
    d.polygon([(70, 15), (73, 7), (75, 15)], fill=(110, 210, 90, 255))
    # flower
    d.line([88, 15, 88, 9], fill=(90, 160, 70, 255))
    d.ellipse([85, 5, 91, 11], fill=(255, 210, 90, 255))
    # bush
    d.ellipse([97, 6, 110, 16], fill=(70, 150, 70, 255))
    # sign
    d.rectangle([118, 8, 120, 15], fill=(120, 80, 50, 255))
    d.rectangle([114, 3, 124, 9], fill=(180, 130, 80, 255))
    img.save(path)


def hero_png(path):
    """16x16 frames: 0-1 idle, 2-5 run, 6 jump, 7 fall."""
    img = Image.new("RGBA", (128, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for f in range(8):
        ox = f * 16
        bob = 1 if f in (1, 3, 5) else 0
        d.rectangle([ox + 4, 3 + bob, ox + 11, 11 + bob], fill=(255, 140, 90, 255))       # body
        d.rectangle([ox + 4, 1 + bob, ox + 11, 4 + bob], fill=(60, 70, 160, 255))         # cap
        d.point((ox + 9, 6 + bob), fill=(20, 20, 30, 255))                               # eye
        if f in (2, 3, 4, 5):
            step = [(-2, 2), (2, -2), (-2, 2), (2, -2)][f - 2]
            d.line([ox + 6, 12, ox + 6 + step[0], 15], fill=(40, 40, 60, 255), width=2)
            d.line([ox + 9, 12, ox + 9 + step[1], 15], fill=(40, 40, 60, 255), width=2)
        elif f == 6:
            d.line([ox + 5, 12, ox + 4, 14], fill=(40, 40, 60, 255), width=2)
            d.line([ox + 10, 12, ox + 11, 14], fill=(40, 40, 60, 255), width=2)
        else:
            d.line([ox + 6, 12 + bob, ox + 6, 15], fill=(40, 40, 60, 255), width=2)
            d.line([ox + 9, 12 + bob, ox + 9, 15], fill=(40, 40, 60, 255), width=2)
    img.save(path)


def slime_png(path):
    img = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for f in range(2):
        ox = f * 16
        top = 5 if f == 0 else 7
        d.ellipse([ox + 1, top, ox + 14, 15], fill=(140, 90, 220, 255))
        d.point((ox + 5, top + 4), fill=(255, 255, 255, 255))
        d.point((ox + 10, top + 4), fill=(255, 255, 255, 255))
    img.save(path)


def coin_png(path):
    img = Image.new("RGBA", (48, 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for f, w in enumerate((5, 3, 1, 3)):
        cx = f * 12 + 6
        d.ellipse([cx - w, 1, cx + w, 11], fill=(255, 212, 92, 255))
        if w > 2:
            d.ellipse([cx - w + 2, 3, cx + w - 2, 9], outline=(220, 160, 40, 255))
    img.save(path)


def flag_png(path):
    img = Image.new("RGBA", (16, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([2, 0, 3, 31], fill=(220, 220, 230, 255))
    d.polygon([(4, 1), (15, 5), (4, 10)], fill=(255, 92, 138, 255))
    img.save(path)


def button_png(path, kind):
    img = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, 39, 39], fill=(255, 255, 255, 70))
    if kind == "left":
        d.polygon([(26, 10), (12, 20), (26, 30)], fill=(255, 255, 255, 220))
    elif kind == "right":
        d.polygon([(14, 10), (28, 20), (14, 30)], fill=(255, 255, 255, 220))
    else:
        d.polygon([(10, 26), (20, 12), (30, 26)], fill=(255, 255, 255, 220))
    img.save(path)


# ── the Tiled level ──────────────────────────────────────────────────────

def level_tmj(path):
    cols, rows = 64, 15
    ground = [0] * (cols * rows)
    decor = [0] * (cols * rows)

    def put(layer, c, r, gid):
        if 0 <= c < cols and 0 <= r < rows:
            layer[r * cols + c] = gid

    floor = 12
    gaps = {14, 15, 31, 32, 33, 47, 48}
    for c in range(cols):
        if c in gaps:
            continue
        put(ground, c, floor, 1)
        for r in range(floor + 1, rows):
            put(ground, c, r, 2)
    for c0, c1, r in ((8, 11, 9), (18, 21, 8), (24, 27, 6), (36, 40, 9), (43, 45, 7), (52, 55, 8)):
        for c in range(c0, c1 + 1):
            put(ground, c, r, 3)
    for c in (28, 29):                      # a stone step
        for r in range(floor - 2, floor):
            put(ground, c, r, 4)
    rng = random.Random(7)
    for c in range(cols):
        if c not in gaps and rng.random() < 0.3:
            put(decor, c, floor - 1, rng.choice((5, 6, 7)))
    put(decor, 3, floor - 1, 8)
    objects = []

    def obj(cls, c, r, w=16, h=16):
        objects.append({"id": len(objects) + 1, "name": "", "class": cls, "x": c * 16, "y": r * 16,
                        "width": w, "height": h, "rotation": 0, "visible": True})

    obj("player", 2, floor - 1)
    for c, r in ((9, 8), (10, 8), (19, 7), (20, 7), (25, 5), (26, 5), (37, 8), (39, 8), (44, 6), (53, 7), (54, 7),
                 (22, 11), (35, 11), (50, 11), (58, 11)):
        obj("coin", c, r)
    for c in (20, 37, 42, 56):
        obj("slime", c, floor - 1)
    obj("flag", 61, floor - 2, 16, 32)
    tmj = {
        "type": "map", "version": "1.10", "orientation": "orthogonal", "renderorder": "right-down",
        "width": cols, "height": rows, "tilewidth": 16, "tileheight": 16, "infinite": False,
        "tilesets": [{"firstgid": 1, "name": "tiles", "image": "../assets/tiles.png", "imagewidth": 128,
                      "imageheight": 16, "tilewidth": 16, "tileheight": 16, "columns": 8, "tilecount": 8,
                      "margin": 0, "spacing": 0}],
        "layers": [
            {"type": "tilelayer", "name": "ground", "width": cols, "height": rows, "data": ground, "visible": True,
             "opacity": 1, "x": 0, "y": 0, "properties": [{"name": "solid", "type": "bool", "value": True}]},
            {"type": "tilelayer", "name": "decor", "width": cols, "height": rows, "data": decor, "visible": True,
             "opacity": 1, "x": 0, "y": 0},
            {"type": "objectgroup", "name": "things", "objects": objects, "visible": True, "opacity": 1,
             "x": 0, "y": 0},
        ],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(tmj, fh, indent=1)
    return cols * 16, rows * 16


# ── the games ────────────────────────────────────────────────────────────

SHIPS_MAIN = '''"""Rock Rain: a ship at the bottom shoots falling rocks. Components only.

Read by the build (python -m apkpygame build / play / run), never run.
"""
from apkpy_lib.game import *

game = Game("Rock Rain", size=(360, 640), scale="fit", orientation="portrait", background="#05060d",
            vars={"score": 0, "lives": 3})

ship_img = assets.image("assets/ship.png")
rock1 = assets.image("assets/rock1.png")
rock2 = assets.image("assets/rock2.png")
shoot = assets.sound("assets/shoot.wav")
boom = assets.sound("assets/boom.wav")
hit = assets.sound("assets/hit.wav")
music = assets.music("assets/theme.wav")


@prefab
def explosion(color: str = "#ffd45c"):
    return Entity("explosion",
                  Emitter(burst=26, lifetime=(0.3, 0.7), speed=(60, 200), size=(7, 1), color=color,
                          color_end="#ff5c8a"),
                  Lifetime(0.8))


@prefab
def bullet():
    return Entity("bullet",
                  Shape(size=(4, 14), color="#5cd6ff"),
                  Mover((0, -520)),
                  Collider(size=(4, 14), trigger=True),
                  Lifetime(1.4),
                  tags=["bullet"])


@prefab
def rock(image=rock1, fall: float = 130, spin: float = 90):
    return Entity("rock",
                  Sprite(image),
                  Spin(spin),
                  Mover((0, fall)),
                  Collider(shape="circle", radius=15),
                  Lifetime(7),
                  OnCollide("bullet", destroy(), destroy("other"), var_add("score"), sound(boom),
                            spawn(explosion())),
                  tags=["rock"])


@prefab
def star(speed: float = 80):
    return Entity("star", Shape(size=(2, 2), color="#8890b0", layer=-5), Mover((0, speed)), Lifetime(9))


play = game.scene("main", start=True, music=music, music_volume=0.4, on_back=open_app("pause_menu"), rules=[
    when("lives <= 0", store_add("coins", var="score"), exit_game({"result": "lose", "score": "{score}"})),
    when("score >= 25", store_add("coins", var="score"), exit_game({"result": "win", "score": "{score}"})),
])

play.add(Entity("stars", Spawner(star(), every=0.15, area=(0, 0, 360, 0))), at=(0, -10))
play.add(Entity("stars2", Spawner(star(140), every=0.4, area=(0, 0, 360, 0))), at=(0, -10))
play.add(Entity("rocks", Spawner(rock(), every=1.1, jitter=0.3, area=(20, 0, 320, 0), delay=1)), at=(0, -30))
play.add(Entity("rocks2", Spawner(rock(rock2, 190, -140), every=2.3, jitter=0.5, area=(20, 0, 320, 0), delay=4)),
         at=(0, -30))
play.add(Entity("ship",
                Sprite(ship_img),
                Collider(shape="circle", radius=12),
                TopDownController(speed=340, axis="x"),
                Timer(0.25, spawn(bullet(), offset=(0, -20)), sound(shoot, 0.25)),
                OnCollide("rock", var_add("lives", -1), destroy("other"), sound(hit), spawn(explosion("#ff5c8a"))),
                Emitter(rate=40, lifetime=(0.2, 0.4), speed=(60, 120), angle=(80, 100), size=(4, 1),
                        color="#5cd6ff", color_end="#2a2f45", layer=-1),
                tags=["ship"]),
         at=(180, 570))

play.add(Entity("score", Text("{score}", size=34, align="center", layer=20)), at=(180, 52), ui=True)
play.add(Entity("lives", Text("Lives {lives}", size=16, layer=20)), at=(14, 30), ui=True)
play.add(Entity("pause", Shape(shape="circle", radius=20, color="#2a2f45", layer=20), OnTap(open_app("pause_menu")),
                children=[Entity("bars", Text("II", size=16, align="center", layer=21), at=(0, 6))]),
         at=(330, 30), ui=True)
'''

PLATFORMER_MAIN = '''"""Meadow Run: a Tiled level, run and jump, coins, slimes to stomp, a flag. Components only.

Read by the build (python -m apkpygame build / play / run), never run.
The level is levels/meadow.tmj: open it in Tiled to change it (one tileset, CSV layers).
"""
from apkpy_lib.game import *

game = Game("Meadow Run", size=(320, 180), scale="fit", orientation="landscape", background="#7ec8ff",
            vars={"coins": 0, "lives": 3})

level = assets.tilemap("levels/meadow.tmj")
hero = assets.sheet("assets/hero.png", frame=(16, 16))
slime = assets.sheet("assets/slime.png", frame=(16, 16))
coin_img = assets.sheet("assets/coin.png", frame=(12, 12))
flag = assets.image("assets/flag.png")
left = assets.image("assets/left.png")
right = assets.image("assets/right.png")
up = assets.image("assets/jump.png")
jump = assets.sound("assets/jump.wav")
ding = assets.sound("assets/coin.wav")
stomp = assets.sound("assets/stomp.wav")
hurt = assets.sound("assets/hurt.wav")
win = assets.sound("assets/win.wav")
music = assets.music("assets/theme.wav")


@prefab
def player():
    return Entity("player",
                  Sprite(hero, frame=0, filter="nearest"),
                  Collider(size=(10, 14), offset=(0, 1)),
                  Body(gravity=900, max_fall=420),
                  PlatformerController(speed=110, jump=300),
                  Animator({"idle": {"frames": [0, 1], "fps": 2}, "run": {"frames": [2, 3, 4, 5], "fps": 12},
                            "jump": {"frames": [6]}, "fall": {"frames": [7]}}),
                  tags=["player"])


@prefab
def coin():
    return Entity("coin",
                  Sprite(coin_img, frame=0, filter="nearest"),
                  Animator({"spin": {"frames": [0, 1, 2, 3, 2, 1], "fps": 8}}),
                  Collider(size=(10, 12), trigger=True),
                  OnCollide("player", destroy(), var_add("coins"), sound(ding)),
                  tags=["coin"])


@prefab
def enemy():
    return Entity("slime",
                  Sprite(slime, frame=0, filter="nearest"),
                  Animator({"walk": {"frames": [0, 1], "fps": 4}}, play="walk", auto=False),
                  Collider(size=(12, 9), offset=(0, 3)),
                  Body(gravity=900),
                  Patrol(speed=30),
                  OnCollide("player", destroy(), sound(stomp), impulse((0, -230), "other", keep_x=True),
                            side="top"),
                  OnCollide("player", var_add("lives", -1), sound(hurt), respawn("other"), side="sides"),
                  tags=["enemy"])


@prefab
def goal():
    return Entity("flag",
                  Sprite(flag, filter="nearest"),
                  Collider(size=(10, 30), trigger=True),
                  OnCollide("player", sound(win), store_add("coins", var="coins"),
                            exit_game({"result": "win", "coins": "{coins}"})))


@prefab
def pad(image=left, key: str = "left"):
    return Entity("pad-" + key,
                  Sprite(image, alpha=0.8, layer=30),
                  TouchButton(key, radius=22))


meadow = game.scene("main", start=True, music=music, music_volume=0.4, on_back=open_app("pause_menu"),
                    camera={"follow": "player", "bounds": "map"},
                    rules=[when("lives <= 0", store_add("coins", var="coins"),
                                exit_game({"result": "lose", "coins": "{coins}"}))])

meadow.add(Entity("map", Tilemap(level, solid=["ground"],
                                 objects={"player": player(), "coin": coin(), "slime": enemy(), "flag": goal()})))
meadow.add(Entity("pit", Collider(size=(2000, 16), trigger=True),
                  OnCollide("player", var_add("lives", -1), sound(hurt), respawn("other"))), at=(512, 236))

meadow.add(Entity("hud", Text("Coins {coins}   Lives {lives}", size=11, color="#14213d", layer=30)), at=(8, 14),
           ui=True)
meadow.add(pad(left, "left"), at=(28, 152), ui=True)
meadow.add(pad(right, "right"), at=(76, 152), ui=True)
meadow.add(pad(up, "jump"), at=(292, 152), ui=True)
'''


def app(folder, name, app_id):
    with open(os.path.join(folder, "apkpy.toml"), "w", encoding="utf-8") as fh:
        fh.write(templates.TOML.format(name=name, app_id=app_id))
    with open(os.path.join(folder, "writehere.py"), "w", encoding="utf-8") as fh:
        fh.write(templates.WRITEHERE_MENUS.format(name=name, glue="enable_game()\n"))


def fresh(folder):
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    for sub in ("game", "assets"):
        os.makedirs(os.path.join(folder, sub))


def ships():
    folder = where.examples("ships")
    fresh(folder)
    a = os.path.join(folder, "assets")
    ship_png(os.path.join(a, "ship.png"))
    rock_png(os.path.join(a, "rock1.png"), 1)
    rock_png(os.path.join(a, "rock2.png"), 2)
    write_wav(os.path.join(a, "shoot.wav"), sweep(1400, 500, 0.08, 0.35))
    write_wav(os.path.join(a, "boom.wav"), sweep(220, 40, 0.35, 0.7, noise=0.7, seed=2))
    write_wav(os.path.join(a, "hit.wav"), sweep(500, 90, 0.4, 0.7, noise=0.4, seed=3))
    write_wav(os.path.join(a, "theme.wav"), tune([220, 0, 261.6, 0, 329.6, 293.7, 261.6, 196] * 2, 0.22))
    with open(os.path.join(folder, "game", "main.py"), "w", encoding="utf-8") as fh:
        fh.write(SHIPS_MAIN)
    app(folder, "Rock Rain", "com.apkpygame.ships")
    return folder


def platformer():
    folder = where.examples("platformer")
    fresh(folder)
    os.makedirs(os.path.join(folder, "levels"))
    a = os.path.join(folder, "assets")
    tiles_png(os.path.join(a, "tiles.png"))
    hero_png(os.path.join(a, "hero.png"))
    slime_png(os.path.join(a, "slime.png"))
    coin_png(os.path.join(a, "coin.png"))
    flag_png(os.path.join(a, "flag.png"))
    for kind in ("left", "right", "jump"):
        button_png(os.path.join(a, kind + ".png"), kind)
    write_wav(os.path.join(a, "jump.wav"), sweep(300, 700, 0.12, 0.4))
    write_wav(os.path.join(a, "coin.wav"), sweep(1300, 1800, 0.1, 0.4))
    write_wav(os.path.join(a, "stomp.wav"), sweep(400, 120, 0.15, 0.6, noise=0.3, seed=4))
    write_wav(os.path.join(a, "hurt.wav"), sweep(600, 150, 0.3, 0.6, noise=0.2, seed=5))
    write_wav(os.path.join(a, "win.wav"), tune([523.3, 659.3, 784, 1046.5], 0.12, 0.35))
    write_wav(os.path.join(a, "theme.wav"), tune([392, 330, 392, 440, 392, 330, 294, 330,
                                                  349, 294, 349, 392, 349, 294, 262, 294], 0.2))
    level_tmj(os.path.join(folder, "levels", "meadow.tmj"))
    with open(os.path.join(folder, "game", "main.py"), "w", encoding="utf-8") as fh:
        fh.write(PLATFORMER_MAIN)
    app(folder, "Meadow Run", "com.apkpygame.platformer")
    return folder


if __name__ == "__main__":
    for f in (ships(), platformer()):
        print("created", f)
