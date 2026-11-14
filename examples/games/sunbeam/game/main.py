"""Sunbeam: an original light puzzle.

A beam of light enters the board from the left. Tap a mirror to turn it; stones stop the light.
Light every flower with as few taps as you can. The levels (made by src/dev/make_phase6_example.py,
which also checks they can be solved) are text: "." empty, "/" and "\\" mirrors, "#" stone, "*" flower.

Read by the build, never run: the declarations become the bundle, the Script classes become Java.
"""
from apkpy_lib.game import *

game = Game("Sunbeam", size=(360, 640), scale="fit", orientation="portrait", background="#0b1020",
            vars={"level": 1, "taps": 0, "total": 0, "par": 0})

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
COUNT = 6
LEVELS = '/.../.#...*............/.\\.......#....*/./#.......\\*..\\.#...\\................\\..\\.../..\\.*\\..#....#*..#.///..#*/./**.....#.....\\../..\\.#....**/......\\.*./#../\\#.....#...#.\\//..**/.#....//.\\.#/.*//##.....\\\\...*.'
ROWS_IN = "504000"
PARS = "123346"


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
            if ch == "/" or ch == "\\":
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
            if ch == "/" or ch == "\\":
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
        if ch != "/" and ch != "\\":
            return
        ch = "\\" if ch == "/" else "/"
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
        game.exit({"result": "win", "taps": total})


play = game.scene("main", start=True, music=theme, music_volume=0.35, on_back=open_app("pause_menu"))
play.add(Entity("board", Board()))
play.add(Entity("title", Text(t("level"), size=22, align="center", layer=10)), at=(180, 70), ui=True)
play.add(Entity("taps", Text(t("taps"), size=16, align="center", layer=10)), at=(180, 104), ui=True)
play.add(Entity("hint", Text(t("hint"), size=14, align="center", layer=10)), at=(180, 600), ui=True)
play.add(Entity("pause", Shape(shape="circle", radius=20, color="#232b4a", layer=10), OnTap(open_app("pause_menu")),
                children=[Entity("bars", Text("II", size=16, align="center", layer=11), at=(0, 6))]),
         at=(330, 34), ui=True)
