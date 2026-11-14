"""Creates src/examples/mossbrook (dev machine only): an original 2.5D example, DS style.

    python src/dev/make_phase7_example.py

"Lanterns of Mossbrook": a small village seen in perspective (a Tiled map with
a hill, stairs and a pond; houses as Blocks, trees as crossed Planes), a hero
who walks cell by cell (tap a cell, or the arrows), three lost lanterns to
pick up, and two villagers who talk through an ApkPy screen. The elder, on
the hill, ends the game once the three lanterns are found. Map, art, sound and
story are made here.
"""
import json
import math
import os
import random
import shutil
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))      # ApkPy's repository
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import where  # noqa: E402
TOOLS = os.path.join(ROOT, "tools", "game")
SRC = ROOT
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(TOOLS, "dev"))
from apkpy_lib.game import glue, templates  # noqa: E402
from make_phase4_examples import sweep, tune, write_wav  # noqa: E402

T = 16                      # tile size (world units)
COLS, ROWS = 20, 22
# tileset (local ids)
GRASS, GRASS2, PATH, STONE, CLIFF, FLOWERS, WATER, STAIRS, BUSH = range(9)

# ── the map ──────────────────────────────────────────────────────────────

HILL = [(c, r) for r in range(2, 7) for c in range(11, 18)]
STAIRS_AT = (14, 7)
POND = [(c, r) for r in range(14, 17) for c in range(2, 6)]
HOUSES = [((4, 4), (3, 2)), ((5, 10), (2, 2)), ((16, 9), (3, 2))]       # (cell of the middle, size in cells)
TREES = [(1, 1), (3, 7), (8, 1), (18, 9), (12, 17), (16, 19), (1, 12), (18, 1), (7, 6), (11, 9)]
LANTERNS = [(2, 9), (17, 15), (6, 19)]
HERO = (9, 19)
ELDER = (14, 3)
MILLER = (8, 15)


def house_cells():
    out = set()
    for (cx, cy), (w, h) in HOUSES:
        for dx in range(w):
            for dy in range(h):
                out.add((cx - w // 2 + dx, cy - h // 2 + dy))
    return out


def build_map():
    ground, top, deco, solid = ([0] * (COLS * ROWS) for _ in range(4))
    rng = random.Random(7)
    houses = house_cells()
    for r in range(ROWS):
        for c in range(COLS):
            i = r * COLS + c
            ground[i] = 1 + (GRASS2 if rng.random() < 0.25 else GRASS)
            if c == 9 and 3 <= r <= 20 or r == 12 and 2 <= c <= 17 or (c == 14 and 8 <= r <= 11):
                ground[i] = 1 + PATH
            if c in (0, COLS - 1) or r in (0, ROWS - 1):
                solid[i] = 1
                deco[i] = 1 + BUSH
    for c, r in HILL:
        top[r * COLS + c] = 1 + STONE
    c, r = STAIRS_AT
    top[r * COLS + c] = 1 + STAIRS
    ring = {(c, r) for r in range(1, 8) for c in range(10, 19)} - set(HILL) - {STAIRS_AT}
    for c, r in ring:                                   # a hedge round the hill: the stairs are the way up
        solid[r * COLS + c] = 1
        deco[r * COLS + c] = 1 + BUSH
    for c, r in POND:
        ground[r * COLS + c] = 1 + WATER
        solid[r * COLS + c] = 1
    for c, r in houses | set(TREES):
        solid[r * COLS + c] = 1
    for c, r in [(3, 3), (6, 8), (12, 14), (16, 7), (2, 18), (10, 5), (13, 20), (7, 13)]:
        if not solid[r * COLS + c]:
            deco[r * COLS + c] = 1 + FLOWERS
    return ground, top, deco, solid


def tmj(ground, top, deco, solid):
    def layer(name, data, props=None, visible=True):
        out = {"type": "tilelayer", "name": name, "width": COLS, "height": ROWS, "data": data, "visible": visible,
               "opacity": 1, "x": 0, "y": 0}
        if props:
            out["properties"] = [{"name": k, "type": "bool" if isinstance(v, bool) else "int", "value": v}
                                 for k, v in props.items()]
        return out

    def obj(kind, cell, oid):
        return {"id": oid, "name": kind, "class": kind, "x": cell[0] * T + T / 2, "y": cell[1] * T + T / 2,
                "width": 0, "height": 0, "point": True, "rotation": 0, "visible": True}

    objects = [obj("house%d" % i, cell, i + 1) for i, (cell, _) in enumerate(HOUSES)]
    objects += [obj("tree", cell, 10 + i) for i, cell in enumerate(TREES)]
    objects += [obj("lantern", cell, 30 + i) for i, cell in enumerate(LANTERNS)]
    objects += [obj("hero", HERO, 40), obj("elder", ELDER, 41), obj("miller", MILLER, 42)]
    tiles = [{"id": STONE, "properties": [{"name": "height", "type": "int", "value": 1},
                                          {"name": "side", "type": "int", "value": CLIFF}]},
             {"id": STAIRS, "properties": [{"name": "height", "type": "float", "value": 0.5},
                                           {"name": "side", "type": "int", "value": CLIFF}]}]
    return {"type": "map", "orientation": "orthogonal", "infinite": False, "width": COLS, "height": ROWS,
            "tilewidth": T, "tileheight": T, "renderorder": "right-down", "version": "1.10", "tiledversion": "1.10.2",
            "tilesets": [{"firstgid": 1, "name": "village", "image": "tiles.png", "imagewidth": 9 * T,
                          "imageheight": T, "tilewidth": T, "tileheight": T, "tilecount": 9, "columns": 9,
                          "margin": 0, "spacing": 0, "tiles": tiles}],
            "layers": [layer("ground", ground), layer("hill", top), layer("deco", deco),
                       layer("solid", solid, {"solid": True}, visible=False),
                       {"type": "objectgroup", "name": "things", "objects": objects, "visible": True, "opacity": 1,
                        "x": 0, "y": 0}]}


# ── art ──────────────────────────────────────────────────────────────────

def tileset(path):
    img = Image.new("RGBA", (9 * T, T), (0, 0, 0, 0))
    rng = random.Random(3)
    def fill(i, base, speck, n=18):
        for x in range(T):
            for y in range(T):
                img.putpixel((i * T + x, y), base)
        for _ in range(n):
            img.putpixel((i * T + rng.randrange(T), rng.randrange(T)), speck)
    fill(GRASS, (96, 170, 78, 255), (78, 148, 64, 255))
    fill(GRASS2, (104, 178, 84, 255), (130, 196, 96, 255))
    fill(PATH, (214, 186, 132, 255), (190, 160, 110, 255), 24)
    fill(STONE, (150, 160, 120, 255), (124, 134, 98, 255), 28)
    fill(CLIFF, (132, 104, 78, 255), (104, 80, 58, 255), 30)
    d = ImageDraw.Draw(img)
    for y in (5, 11):
        d.line((CLIFF * T, y, CLIFF * T + T - 1, y), fill=(98, 74, 54, 255))
    for fx, fy, col in ((3, 4, (255, 120, 170)), (10, 6, (255, 220, 90)), (6, 11, (170, 140, 255)),
                        (12, 12, (255, 120, 170))):
        d.ellipse((FLOWERS * T + fx - 2, fy - 2, FLOWERS * T + fx + 2, fy + 2), fill=col + (255,))
    fill(WATER, (70, 140, 210, 255), (130, 190, 240, 255), 10)
    fill(STAIRS, (170, 160, 130, 255), (150, 140, 112, 255), 6)
    for y in (3, 8, 13):
        d.line((STAIRS * T, y, STAIRS * T + T - 1, y), fill=(120, 110, 90, 255))
    d.ellipse((BUSH * T + 1, 2, BUSH * T + 14, 15), fill=(50, 120, 62, 255))
    d.ellipse((BUSH * T + 4, 4, BUSH * T + 9, 9), fill=(72, 146, 80, 255))
    img.save(path)


def person(path, body, hair, hat=None):
    """4 directions (down, left, up, right) x 3 walking frames, 16x24 each."""
    img = Image.new("RGBA", (3 * 16, 4 * 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    skin = (240, 200, 160, 255)
    for row in range(4):
        for col in range(3):
            ox, oy = col * 16, row * 24
            step = (col - 1) * 2
            d.rectangle((ox + 4 + step, oy + 19, ox + 6 + step, oy + 23), fill=(50, 44, 60, 255))
            d.rectangle((ox + 9 - step, oy + 19, ox + 11 - step, oy + 23), fill=(50, 44, 60, 255))
            d.rectangle((ox + 3, oy + 11, ox + 12, oy + 19), fill=body)
            d.ellipse((ox + 3, oy + 2, ox + 12, oy + 11), fill=skin)
            if row == 2:                                    # seen from the back: all hair
                d.ellipse((ox + 3, oy + 2, ox + 12, oy + 10), fill=hair)
            else:
                d.rectangle((ox + 3, oy + 2, ox + 12, oy + 5), fill=hair)
                eyes = {0: (6, 9), 1: (5,), 3: (10,)}[row]
                for ex in eyes:
                    d.point((ox + ex, oy + 7), fill=(30, 30, 40, 255))
            if hat:
                d.polygon([(ox + 2, oy + 3), (ox + 13, oy + 3), (ox + 7, oy - 0)], fill=hat)
    img.save(path)


def lantern(path):
    img = Image.new("RGBA", (12, 18), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 4, 11, 17), fill=(255, 210, 90, 120))
    d.rectangle((3, 7, 8, 15), fill=(255, 226, 120, 255))
    d.rectangle((2, 5, 9, 6), fill=(90, 70, 50, 255))
    d.rectangle((2, 16, 9, 17), fill=(90, 70, 50, 255))
    d.line((5, 0, 5, 4), fill=(90, 70, 50, 255))
    img.save(path)


def tree(path):
    img = Image.new("RGBA", (28, 44), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((12, 28, 15, 43), fill=(110, 78, 52, 255))
    d.ellipse((1, 2, 27, 32), fill=(46, 120, 66, 255))
    d.ellipse((6, 5, 16, 15), fill=(70, 150, 86, 255))
    img.save(path)


def roof(path, color):
    img = Image.new("RGBA", (32, 32), color)
    d = ImageDraw.Draw(img)
    for y in range(0, 32, 6):
        d.line((0, y, 31, y), fill=tuple(int(v * 0.8) for v in color[:3]) + (255,))
    img.save(path)


def wall(path):
    img = Image.new("RGBA", (32, 24), (236, 226, 204, 255))
    d = ImageDraw.Draw(img)
    d.rectangle((12, 10, 19, 23), fill=(120, 82, 54, 255))
    d.rectangle((3, 8, 8, 13), fill=(120, 170, 220, 255))
    d.rectangle((23, 8, 28, 13), fill=(120, 170, 220, 255))
    img.save(path)


def art(folder):
    os.makedirs(folder)
    tileset(os.path.join(folder, "tiles.png"))
    person(os.path.join(folder, "hero.png"), (60, 110, 220, 255), (90, 60, 30, 255))
    person(os.path.join(folder, "elder.png"), (130, 90, 170, 255), (220, 220, 225, 255), hat=(110, 70, 150, 255))
    person(os.path.join(folder, "miller.png"), (90, 150, 80, 255), (200, 120, 50, 255))
    lantern(os.path.join(folder, "lantern.png"))
    tree(os.path.join(folder, "tree.png"))
    roof(os.path.join(folder, "roof_red.png"), (196, 82, 70, 255))
    roof(os.path.join(folder, "roof_blue.png"), (80, 110, 180, 255))
    wall(os.path.join(folder, "wall.png"))
    write_wav(os.path.join(folder, "chime.wav"), tune([880, 1175, 1568], 0.1, volume=0.35))
    write_wav(os.path.join(folder, "talk.wav"), sweep(500, 700, 0.08, volume=0.4))
    melody = [523, 0, 659, 784, 0, 659, 587, 0, 523, 0, 440, 523, 0, 587, 659, 0] * 2
    write_wav(os.path.join(folder, "theme.wav"), tune(melody, 0.34, volume=0.11))


# ── the game and the app ─────────────────────────────────────────────────

MAIN = '''"""Lanterns of Mossbrook: an original 2.5D example, in the style of the DS-era RPGs.

The village is a Tiled map (assets/village.tmj: a hill with stairs, a pond, hedges); houses are Blocks,
trees crossed Planes, people Billboards that walk cell by cell. Tap a cell to walk there (or use the arrows); tap a villager (or Space) to talk.
Find the three lanterns, then bring them to the elder on the hill. Talking opens the app's "dialog" screen.

Read by the build, never run: the declarations become the bundle, the Script classes become Java.
"""
from apkpy_lib.game import *

game = Game("Lanterns of Mossbrook", size=(360, 640), orientation="portrait", background="#9fd6ff",
            vars={{"lanterns": 0}})

village = assets.tilemap("assets/village.tmj")
hero_sheet = assets.sheet("assets/hero.png", frame=(16, 24))
elder_sheet = assets.sheet("assets/elder.png", frame=(16, 24))
miller_sheet = assets.sheet("assets/miller.png", frame=(16, 24))
lantern_img = assets.image("assets/lantern.png")
tree_img = assets.image("assets/tree.png")
roof_red = assets.image("assets/roof_red.png")
roof_blue = assets.image("assets/roof_blue.png")
wall_img = assets.image("assets/wall.png")
chime = assets.sound("assets/chime.wav")
talk = assets.sound("assets/talk.wav")
theme = assets.music("assets/theme.wav")
CELL = {cell}
LANTERNS = {lanterns}


class Talker(Script):
    """A villager: tapping them (next to the hero) talks. The elder ends the game with every lantern found."""
    who: str = "miller"
    voice: Sound = talk

    def update(self, dt: float):
        hero = scene.find("hero")
        if hero is not None:
            if self.next_to(hero) and (self.tapped() or self.asked(hero)):
                self.talk()

    def asked(self, hero: Entity) -> bool:
        """Space or Enter, next to the villager and facing them."""
        if not (input.key_pressed("space") or input.key_pressed("enter")):
            return False
        want = 0.0
        if self.x > hero.x:
            want = 90.0
        elif self.x < hero.x:
            want = 270.0
        elif self.y < hero.y:
            want = 180.0
        return abs(hero.billboard.facing - want) < 1

    def next_to(self, hero: Entity) -> bool:
        return abs(hero.x - self.x) + abs(hero.y - self.y) <= CELL * 1.1

    def tapped(self) -> bool:
        """The tap is on the villager: their cell, or the cells behind it where the picture stands."""
        if not input.pointer_pressed():
            return False
        dx = abs(input.pointer_x() - self.x)
        up = self.y - input.pointer_y()
        return dx <= CELL * 0.7 and up >= -CELL * 0.6 and up <= CELL * 2.2

    def talk(self):
        audio.play(self.voice)
        found = int(game.get("lanterns"))
        if self.who == "elder" and found >= LANTERNS:
            game.store_set("mossbrook_done", "1")
            game.exit({{"result": "done", "lanterns": found}})
            return
        game.store_set("mossbrook_talk", self.who + str(found))
        game.open_app("dialog")


@prefab
def villager(sheet=elder_sheet, who: str = "elder", facing: float = 0):
    return Entity("villager", Billboard(sheet, directions=4, facing=facing, auto_facing=False),
                  Talker(who=who), tags=["solid"])


@prefab
def house(roof=roof_red, width: float = 48, depth: float = 32):
    return Entity("house", Block((width, depth), 30, top=roof, side=wall_img))


@prefab
def tree():
    return Entity("tree", Plane(tree_img, size=(28, 44), cross=True))


@prefab
def lantern():
    return Entity("lantern", Billboard(lantern_img), Collider(shape="circle", radius=5, trigger=True),
                  OnCollide("hero", sound(chime), var_add("lanterns", 1), destroy()), tags=["lantern"])


@prefab
def hero():
    return Entity("hero", Billboard(hero_sheet, directions=4), GridController(tile=CELL, speed=4),
                  Collider(shape="circle", radius=5), tags=["hero"])


town = game.scene("town", start=True, kind="2.5d", music=theme, music_volume=0.35, on_back=open_app("pause_menu"),
                  camera={{"follow": "hero", "pitch": 50, "distance": 270, "fov": 40, "fog": (260, 520), "bounds": "map"}})
town.add(Entity("map", Tilemap(village, objects={{
    "hero": hero(), "elder": villager(), "miller": villager(miller_sheet, "miller", 270),
    "lantern": lantern(), "tree": tree(),
    "house0": house(), "house1": house(roof_blue, 32, 32), "house2": house(roof_blue)}})))
town.add(Entity("hud", Text(t("lanterns_hud"), size=20, align="center", layer=10)), at=(180, 44), ui=True)
town.add(Entity("hint", Text(t("hint"), size=14, align="center", layer=10)), at=(180, 612), ui=True)
town.add(Entity("pause", Shape(shape="circle", radius=20, color="#2a3a5a", layer=10), OnTap(open_app("pause_menu")),
                children=[Entity("bars", Text("II", size=16, align="center", layer=11), at=(0, 6))]),
         at=(330, 34), ui=True)
'''

WRITEHERE = '''from apkpy_lib import *

# Lanterns of Mossbrook: the app (ApkPy) around the game (ApkPyGame, game/main.py).
# Screens first (an ApkPy rule: a button that opens a screen declared below it does nothing).
home = Screen(id="home")
dialog = Screen(id="dialog")
pause_menu = Screen(id="pause_menu")
results = Screen(id="results")

# One table of words for the app AND the game (the game's t("key") reads it too).
translations({{
    "en": {{"title": "Lanterns of Mossbrook", "play": "Play", "continue": "Continue", "quit": "Quit to menu",
            "home": "Menu", "paused": "Paused", "results": "The lanterns are home!", "lanterns_hud": "Lanterns {{lanterns}}/3",
            "hint": "Tap to walk or to talk", "done_before": "You already brought the lanterns home.",
            "elder0": "Elder: The wind took our three lanterns. Could you find them?",
            "elder1": "Elder: One lantern! Two more are still out there.",
            "elder2": "Elder: Two! The last one must be near the pond or the woods.",
            "miller0": "Miller: The elder lives up the stairs. Lanterns? I saw a glow by the old house.",
            "miller1": "Miller: Another one should be south, near the mill road.",
            "miller2": "Miller: Look east, past the blue houses.",
            "miller3": "Miller: All three! Go and see the elder."}},
    "pt": {{"title": "Lanterns of Mossbrook", "play": "Jogar", "continue": "Continuar", "quit": "Sair para o menu",
            "home": "Menu", "paused": "Em pausa", "results": "As lanternas voltaram!", "lanterns_hud": "Lanternas {{lanterns}}/3",
            "hint": "Toca para andar ou para falar",
            "done_before": "Já levaste as lanternas para casa.",
            "elder0": "Ancião: O vento levou as nossas três lanternas. Encontras-nas?",
            "elder1": "Ancião: Uma lanterna! Ainda faltam duas.",
            "elder2": "Ancião: Duas! A última deve estar perto do lago ou do bosque.",
            "miller0": "Moleiro: O ancião mora lá em cima, depois das escadas. Lanternas? Vi uma luz junto à casa velha.",
            "miller1": "Moleiro: Há outra a sul, perto do caminho do moinho.",
            "miller2": "Moleiro: Procura a leste, depois das casas azuis.",
            "miller3": "Moleiro: As três! Vai ter com o ancião."}},
}}, default="en")

{glue}
label(t("title"), id="title", screen=home)
home_note = label("", id="home_note", screen=home)
said = label("", id="said", screen=dialog)
label(t("paused"), id="paused", screen=pause_menu)
label(t("results"), id="results_title", screen=results)


def finished(ok, value):
    game_last_result()                      # handled here: on_resume needs not pick it up again
    if '"screen":"dialog"' in value:
        on_click_navigate(dialog)
    elif '"action":"open"' in value:
        on_click_navigate(pause_menu)
    elif '"action":"exit"' in value:
        on_click_navigate(results)


def play():
    game_play("town", "{{}}", on_result=finished)


def resume():
    game_resume(on_result=finished)


def home_shown():
    home_note.set_value(t("done_before") if game_get("mossbrook_done") == "1" else "")
    missed = game_last_result()             # an answer that came while this screen was gone
    if '"screen":"dialog"' in missed:
        on_click_navigate(dialog)
    elif '"action":"open"' in missed:
        on_click_navigate(pause_menu)


def dialog_shown():
    key = game_get("mossbrook_talk")             # t() takes a written key (an ApkPy rule): one per line
    if key == "elder0":
        said.set_value(t("elder0"))
    elif key == "elder1":
        said.set_value(t("elder1"))
    elif key == "elder2":
        said.set_value(t("elder2"))
    elif key == "miller0":
        said.set_value(t("miller0"))
    elif key == "miller1":
        said.set_value(t("miller1"))
    elif key == "miller2":
        said.set_value(t("miller2"))
    elif key == "miller3":
        said.set_value(t("miller3"))


lifecycle(home, on_resume=home_shown)
lifecycle(dialog, on_resume=dialog_shown)

button(t("play"), id="play", command=play, screen=home)
button(t("continue"), id="talk_continue", command=resume, screen=dialog)
button(t("continue"), id="continue", command=resume, screen=pause_menu)
button(t("quit"), id="quit", command=lambda: on_click_navigate(home), screen=pause_menu)
button(t("home"), id="results_home", command=lambda: on_click_navigate(home), screen=results)

style = """
title {{ font-size: 28px; font-weight: bold; }}
said {{ font-size: 20px; }}
"""

run(start_screen=home, theme=Theme(mode="dark"))
'''


def main():
    folder = where.examples("mossbrook")
    os.makedirs(folder, exist_ok=True)
    for name in os.listdir(folder):                     # the contents, not the folder (it may be the cwd)
        path = os.path.join(folder, name)
        shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
    os.makedirs(os.path.join(folder, "game"))
    assets = os.path.join(folder, "assets")
    art(assets)
    with open(os.path.join(assets, "village.tmj"), "w", encoding="utf-8") as fh:
        json.dump(tmj(*build_map()), fh, indent=1)
    with open(os.path.join(folder, "game", "main.py"), "w", encoding="utf-8") as fh:
        fh.write(MAIN.format(cell=T, lanterns=len(LANTERNS)))
    app_id = "com.apkpygame.mossbrook"
    with open(os.path.join(folder, "apkpy.toml"), "w", encoding="utf-8") as fh:
        fh.write(templates.TOML.format(name="Lanterns of Mossbrook", app_id=app_id))
    with open(os.path.join(folder, "writehere.py"), "w", encoding="utf-8") as fh:
        fh.write(WRITEHERE.format(glue="enable_game()\n"))
    print("created", folder)


if __name__ == "__main__":
    main()
