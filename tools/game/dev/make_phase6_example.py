"""Creates src/examples/sunbeam (dev machine only): an original light puzzle.

    python src/dev/make_phase6_example.py

A beam of light enters the board from the left. Tapping a mirror turns it
("/" <-> "\\"); stones stop the light. A level is solved when the beam passes
through every flower. Fewer taps is better: each level has a "par", the
fewest taps that solve it.

The levels are made here, on the developer's PC: a random path of mirrors,
flowers on the path, stones off it, then the mirrors are scrambled; a brute
force solver checks that the level is solvable, that it does not start solved,
and finds its par. The game only gets the finished levels, as text constants.
"""
import itertools
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

COLS, ROWS = 5, 7
MIRRORS = "/\\"


# ── levels ───────────────────────────────────────────────────────────────

def trace(cells, row):
    """The cells the beam goes through (in order), entering at the left of ``row``."""
    x, y, dx, dy = -1, row, 1, 0
    path = []
    for _ in range(COLS * ROWS * 4):
        x, y = x + dx, y + dy
        if not (0 <= x < COLS and 0 <= y < ROWS):
            break
        i = y * COLS + x
        ch = cells[i]
        if ch == "#":
            break
        path.append(i)
        if ch == "/":
            dx, dy = -dy, -dx
        elif ch == "\\":
            dx, dy = dy, dx
    return path


def solved(cells, row):
    lit = set(trace(cells, row))
    return all(i in lit for i, ch in enumerate(cells) if ch == "*")


def solve(cells, row):
    """The fewest mirrors to turn to solve the level (brute force over the mirrors), or None."""
    mirrors = [i for i, ch in enumerate(cells) if ch in MIRRORS]
    for k in range(len(mirrors) + 1):
        for turned in itertools.combinations(mirrors, k):
            c = list(cells)
            for i in turned:
                c[i] = "\\" if c[i] == "/" else "/"
            if solved(c, row):
                return list(turned)
    return None


def make_level(rng, mirrors, flowers, stones, min_par):
    while True:
        cells = ["."] * (COLS * ROWS)
        for i in rng.sample(range(COLS * ROWS), mirrors):
            cells[i] = rng.choice(MIRRORS)
        row = rng.randrange(ROWS)
        path = trace(cells, row)
        on_path = [i for i in path if cells[i] == "."]
        turns = [i for i in path if cells[i] in MIRRORS]
        if len(path) < 10 or len(turns) < 3 or len(on_path) < flowers:
            continue
        for i in rng.sample(on_path, flowers):
            cells[i] = "*"
        free = [i for i in range(COLS * ROWS) if cells[i] == "." and i not in path]
        for i in rng.sample(free, min(stones, len(free))):
            cells[i] = "#"
        start = list(cells)
        for i in turns:
            if rng.random() < 0.7:
                start[i] = "\\" if start[i] == "/" else "/"
        turns = solve(start, row)
        if turns is not None and len(turns) >= min_par and not solved(start, row):
            return "".join(start), row, len(turns), turns


def solution_replay(made):
    """The levels solved with par taps, as a replay script (STEP:tap:X:Y): the game must end won."""
    out, step = [], 30
    for _, _, _, turns in made:
        for i in turns:
            out.append("%d:tap:%d:%d" % (step, 30 + (i % COLS) * 60 + 30, 150 + (i // COLS) * 60 + 30))
            step += 12
        step += 100                                     # the level's chime, then the next one
    return ",".join(out), step


def levels():
    rng = random.Random(2026)
    spec = [(4, 1, 2, 1), (5, 2, 2, 2), (6, 2, 3, 3), (7, 3, 3, 3), (8, 3, 4, 4), (9, 4, 4, 5)]
    return [make_level(rng, *s) for s in spec]


# ── the game ─────────────────────────────────────────────────────────────

MAIN = '''"""Sunbeam: an original light puzzle.

A beam of light enters the board from the left. Tap a mirror to turn it; stones stop the light.
Light every flower with as few taps as you can. The levels (made by src/dev/make_phase6_example.py,
which also checks they can be solved) are text: "." empty, "/" and "\\\\" mirrors, "#" stone, "*" flower.

Read by the build, never run: the declarations become the bundle, the Script classes become Java.
"""
from apkpy_lib.game import *

game = Game("Sunbeam", size=(360, 640), scale="fit", orientation="portrait", background="#0b1020",
            vars={{"level": 1, "taps": 0, "total": 0, "par": 0}})

click = assets.sound("assets/click.wav")
chime = assets.sound("assets/chime.wav")
theme = assets.music("assets/theme.wav")
flower_img = assets.image("assets/flower.png")
bud_img = assets.image("assets/bud.png")

COLS = 5
ROWS = 7
CELL = 60.0
LEFT = 30.0
TOP = 150.0
COUNT = {count}
LEVELS = {levels}
ROWS_IN = "{rows}"
PARS = "{pars}"


def cell_x(i: int) -> float:
    return LEFT + (i % COLS) * CELL + CELL / 2


def cell_y(i: int) -> float:
    return TOP + (i // COLS) * CELL + CELL / 2


@prefab
def tile():
    return Entity("tile", Shape(size=(56, 56), color="#141b33", layer=-2), tags=["piece"])


@prefab
def mirror():
    return Entity("mirror", Shape(size=(50, 7), color="#dfe9ff", layer=2), tags=["piece"])


@prefab
def stone():
    return Entity("stone", Shape(size=(44, 44), color="#4a4f66", layer=1), tags=["piece"])


@prefab
def bud():
    return Entity("bud", Sprite(bud_img, layer=1), tags=["piece"])


@prefab
def bloom():
    return Entity("bloom", Sprite(flower_img, layer=4), tags=["piece"])


@prefab
def ray():
    return Entity("ray", Shape(size=(60, 6), color="#ffe27a", layer=3), tags=["beam"])


@prefab
def half_ray():
    return Entity("half_ray", Shape(size=(30, 6), color="#ffe27a", layer=3), tags=["beam"])


@prefab
def lamp():
    return Entity("lamp", Shape(shape="circle", radius=12, color="#ffe27a", layer=3), tags=["piece"])


class Board(Script):
    """Builds a level from its text, turns mirrors on tap, traces the beam, and moves on when it is solved."""
    tile: Prefab = tile()
    mirror: Prefab = mirror()
    stone: Prefab = stone()
    bud: Prefab = bud()
    bloom: Prefab = bloom()
    ray: Prefab = ray()
    half_ray: Prefab = half_ray()
    lamp: Prefab = lamp()
    click: Sound = click
    chime: Sound = chime
    cells: list[str] = []
    mirrors: list[Entity] = []
    blooms: list[Entity] = []
    bloom_cells: list[int] = []
    level: int = 0
    row: int = 0
    wait: float = -1.0

    def on_start(self):
        self.build()

    def build(self):
        for e in scene.with_tag("piece"):
            e.destroy()
        self.cells = []
        self.mirrors = []
        self.blooms = []
        self.bloom_cells = []
        self.row = int(ROWS_IN[self.level])
        game.set("level", self.level + 1)
        game.set("taps", 0)
        game.set("par", int(PARS[self.level]))
        for i in range(COLS * ROWS):
            ch = LEVELS[self.level * COLS * ROWS + i]
            self.cells.append(ch)
            x = cell_x(i)
            y = cell_y(i)
            under = scene.spawn(self.tile, x, y)
            if ch == "/" or ch == "\\\\":
                m = scene.spawn(self.mirror, x, y)
                m.rotation = self.angle(ch)
                self.mirrors.append(m)
            else:
                self.mirrors.append(under)              # one entry per cell: only mirrors are turned
            if ch == "#":
                scene.spawn(self.stone, x, y)
            if ch == "*":
                scene.spawn(self.bud, x, y)
                b = scene.spawn(self.bloom, x, y)
                b.active = False
                self.blooms.append(b)
                self.bloom_cells.append(i)
        scene.spawn(self.lamp, LEFT - 14, TOP + self.row * CELL + CELL / 2)
        self.trace()

    def angle(self, ch: str) -> float:
        if ch == "/":
            return -45.0
        return 45.0

    def segment(self, i: int, dx: int, dy: int, half: bool, outgoing: bool):
        x = cell_x(i)
        y = cell_y(i)
        if half:
            sign = 1.0 if outgoing else -1.0
            e = scene.spawn(self.half_ray, x + dx * 15.0 * sign, y + dy * 15.0 * sign)
        else:
            e = scene.spawn(self.ray, x, y)
        if dy != 0:
            e.rotation = 90.0

    def trace(self) -> bool:
        """Draws the beam again; answers whether every flower is lit."""
        for e in scene.with_tag("beam"):
            e.destroy()
        for b in self.blooms:
            b.active = False
        lit = 0
        x = -1
        y = self.row
        dx = 1
        dy = 0
        for step in range(COLS * ROWS * 4):
            x += dx
            y += dy
            if x < 0 or x >= COLS or y < 0 or y >= ROWS:
                break
            i = y * COLS + x
            ch = self.cells[i]
            if ch == "#":
                self.segment(i, dx, dy, True, False)
                break
            if ch == "/" or ch == "\\\\":
                self.segment(i, dx, dy, True, False)
                if ch == "/":
                    turn = dx
                    dx = -dy
                    dy = -turn
                else:
                    turn = dx
                    dx = dy
                    dy = turn
                self.segment(i, dx, dy, True, True)
            else:
                self.segment(i, dx, dy, False, False)
            if ch == "*":
                for k in range(len(self.bloom_cells)):
                    if self.bloom_cells[k] == i and not self.blooms[k].active:
                        self.blooms[k].active = True
                        lit += 1
        return lit == len(self.blooms)

    def update(self, dt: float):
        if self.wait >= 0:
            self.wait -= dt
            if self.wait < 0:
                self.next_level()
            return
        if not input.pointer_pressed():
            return
        col = int((input.pointer_x() - LEFT) // CELL)
        line = int((input.pointer_y() - TOP) // CELL)
        if col < 0 or col >= COLS or line < 0 or line >= ROWS:
            return
        i = line * COLS + col
        ch = self.cells[i]
        if ch != "/" and ch != "\\\\":
            return
        ch = "\\\\" if ch == "/" else "/"
        self.cells[i] = ch
        self.mirrors[i].rotation = self.angle(ch)
        game.add("taps", 1)
        game.add("total", 1)
        audio.play(self.click, 0.6)
        if self.trace():
            audio.play(self.chime)
            self.wait = 1.2

    def next_level(self):
        if self.level + 1 < COUNT:
            self.level += 1
            self.build()
            return
        total = int(game.get("total"))
        best = game.store_get("sunbeam_best")
        if best == "" or total < int(best):
            game.store_set("sunbeam_best", str(total))
        game.exit({{"result": "win", "taps": total}})


play = game.scene("main", start=True, music=theme, music_volume=0.35, on_back=open_app("pause_menu"))
play.add(Entity("board", Board()))
play.add(Entity("title", Text(t("level"), size=22, align="center", layer=10)), at=(180, 70), ui=True)
play.add(Entity("taps", Text(t("taps"), size=16, align="center", layer=10)), at=(180, 104), ui=True)
play.add(Entity("hint", Text(t("hint"), size=14, align="center", layer=10)), at=(180, 600), ui=True)
play.add(Entity("pause", Shape(shape="circle", radius=20, color="#232b4a", layer=10), OnTap(open_app("pause_menu")),
                children=[Entity("bars", Text("II", size=16, align="center", layer=11), at=(0, 6))]),
         at=(330, 34), ui=True)
'''

WRITEHERE = '''from apkpy_lib import *

# Sunbeam: the app (ApkPy) around the game (ApkPyGame, game/main.py).
# Screens first (an ApkPy rule: a button that opens a screen declared below it does nothing).
home = Screen(id="home")
pause_menu = Screen(id="pause_menu")
results = Screen(id="results")

# One table of words for the app AND the game (the game's t("key") reads it too).
translations({{
    "en": {{"title": "Sunbeam", "play": "Play", "best": "Best (fewest taps)", "continue": "Continue",
            "quit": "Quit to menu", "home": "Menu", "paused": "Paused", "results": "All flowers in bloom!",
            "taps_used": "Taps", "level": "Level {{level}}", "taps": "Taps: {{taps}}  (par {{par}})",
            "hint": "Tap a mirror to turn it"}},
    "pt": {{"title": "Sunbeam", "play": "Jogar", "best": "Recorde (menos toques)", "continue": "Continuar",
            "quit": "Sair para o menu", "home": "Menu", "paused": "Em pausa", "results": "Todas as flores abriram!",
            "taps_used": "Toques", "level": "Nível {{level}}", "taps": "Toques: {{taps}}  (par {{par}})",
            "hint": "Toca num espelho para o rodar"}},
}}, default="en")

{glue}
label(t("title"), id="title", screen=home)
label(t("best"), id="best_caption", screen=home)
home_best = label("-", id="home_best", screen=home)
label(t("paused"), id="paused", screen=pause_menu)
label(t("results"), id="results_title", screen=results)
label(t("taps_used"), id="results_caption", screen=results)
results_taps = label("0", id="results_taps", screen=results)


def best():
    value = game_get("sunbeam_best")
    if value == "":
        return "-"
    return value


def finished(ok, value):
    game_last_result()                      # handled here: on_resume needs not pick it up again
    if '"action":"open"' in value:
        on_click_navigate(pause_menu)
    elif '"action":"exit"' in value and '"taps":' in value:
        results_taps.set_value(value.split('"taps":')[1].split("}}")[0].split(",")[0].split(".")[0])
        on_click_navigate(results)


def play():
    game_play("main", "{{}}", on_result=finished)


def resume():
    game_resume(on_result=finished)


def home_shown():
    home_best.set_value(best())
    missed = game_last_result()             # an answer that came while this screen was gone
    if '"action":"open"' in missed:
        on_click_navigate(pause_menu)


lifecycle(home, on_resume=home_shown)

button(t("play"), id="play", command=play, screen=home)
button(t("continue"), id="continue", command=resume, screen=pause_menu)
button(t("quit"), id="quit", command=lambda: on_click_navigate(home), screen=pause_menu)
button(t("home"), id="results_home", command=lambda: on_click_navigate(home), screen=results)

style = """
title {{ font-size: 32px; font-weight: bold; }}
home_best {{ font-size: 32px; }}
results_taps {{ font-size: 40px; }}
"""

run(start_screen=home, theme=Theme(mode="dark"))
'''


# ── art and sound ────────────────────────────────────────────────────────

def flower_png(path, open_):
    img = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if open_:
        import math
        for k in range(6):
            a = k * math.pi / 3
            cx, cy = 20 + 10 * math.cos(a), 20 + 10 * math.sin(a)
            d.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=(255, 140, 190, 255))
        d.ellipse((13, 13, 27, 27), fill=(255, 214, 92, 255))
    else:
        d.ellipse((12, 12, 28, 28), fill=(98, 64, 110, 255))
        d.ellipse((16, 16, 24, 24), fill=(130, 90, 140, 255))
    img.save(path)


def assets(folder):
    os.makedirs(folder)
    flower_png(os.path.join(folder, "flower.png"), True)
    flower_png(os.path.join(folder, "bud.png"), False)
    write_wav(os.path.join(folder, "click.wav"), sweep(900, 600, 0.06, volume=0.5))
    write_wav(os.path.join(folder, "chime.wav"), tune([784, 988, 1175, 1568], 0.12, volume=0.35))
    melody = [392, 0, 494, 587, 0, 494, 440, 0, 392, 0, 330, 392, 0, 440, 494, 0] * 2
    write_wav(os.path.join(folder, "theme.wav"), tune(melody, 0.3, volume=0.12))


def main():
    made = levels()
    for n, (cells, row, p, _) in enumerate(made, 1):
        print("level %d: lamp on row %d, par %d" % (n, row, p))
        for r in range(ROWS):
            print("   ", cells[r * COLS:(r + 1) * COLS])
    folder = where.examples("sunbeam")
    os.makedirs(folder, exist_ok=True)
    for name in os.listdir(folder):                     # the contents, not the folder (it may be the cwd)
        path = os.path.join(folder, name)
        shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
    os.makedirs(os.path.join(folder, "game"))
    assets(os.path.join(folder, "assets"))
    text = "".join(c for c, _, _, _ in made)
    with open(os.path.join(folder, "game", "main.py"), "w", encoding="utf-8") as fh:
        fh.write(MAIN.format(count=len(made), levels=repr(text), rows="".join(str(r) for _, r, _, _ in made),
                             pars="".join(str(p) for _, _, p, _ in made)))
    script, steps = solution_replay(made)
    with open(os.path.join(folder, "solution_replay.txt"), "w", encoding="utf-8") as fh:
        fh.write(script)
    print("solution: %d taps in %d steps (solution_replay.txt)" % (sum(p for _, _, p, _ in made), steps))
    app_id = "com.apkpygame.sunbeam"
    with open(os.path.join(folder, "apkpy.toml"), "w", encoding="utf-8") as fh:
        fh.write(templates.TOML.format(name="Sunbeam", app_id=app_id))
    with open(os.path.join(folder, "writehere.py"), "w", encoding="utf-8") as fh:
        fh.write(WRITEHERE.format(glue="enable_game()\n"))
    print("created", folder)


if __name__ == "__main__":
    main()
