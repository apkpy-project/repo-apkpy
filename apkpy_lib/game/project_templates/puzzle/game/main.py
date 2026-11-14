"""Lights Off: a tap turns a light and the four next to it. Turn every light off. Five boards; fewer moves, more
points.

The board is a small Script (Board, below): its typed fields are settings in the Studio's Objects, the levels
among them. A level is 25 letters, the rows of the board one after the other: 1 a light on, 0 off. Each level here
is made by pressing a few lights of a dark board, so it can always be solved in that many moves.
"""
from apkpy_lib.game import *

game = Game("Lights Off", size=(360, 640), scale="fit", orientation="portrait", background="#0e1124",
            vars={"level": 1, "moves": 0})

click = assets.sound("assets/click.wav")
solved = assets.sound("assets/solved.wav")
music = assets.music("assets/theme.wav")

LEVELS = ("0011110010100000110001000" "0001101100011000110010000" "0010001111101011111110001"
          "1000010101000000101111101" "1001011110011110010101100")


@prefab
def tile():
    return Entity("tile", Shape(size=(54, 54), color="#1d2240", layer=-1), tags=["piece"])


@prefab
def lamp():
    return Entity("lamp", Shape(shape="circle", radius=20, color="#ffd45c", layer=1),
                  children=[Entity("glow", Shape(shape="circle", radius=26, color="#ffd45c", alpha=0.25))],
                  tags=["piece"])


class Board(Script):
    """Builds a board from its level, turns a light and its neighbours on a tap, and moves on when all are off."""
    levels: str = LEVELS
    count: int = 5
    size: int = 5
    cell: float = 60.0
    left: float = 30.0
    top: float = 170.0
    tile: Prefab = tile()
    lamp: Prefab = lamp()
    click: Sound = click
    solved: Sound = solved
    lights: list[Entity] = []
    level: int = 0
    wait: float = -1.0

    def on_start(self):
        self.build()

    def build(self):
        for e in scene.with_tag("piece"):
            e.destroy()
        self.lights = []
        game.set("level", self.level + 1)
        n = self.size * self.size
        for i in range(n):
            x = self.left + (i % self.size) * self.cell + self.cell / 2
            y = self.top + (i // self.size) * self.cell + self.cell / 2
            scene.spawn(self.tile, x, y)
            light = scene.spawn(self.lamp, x, y)
            light.active = self.levels[self.level * n + i] == "1"
            self.lights.append(light)

    def flip(self, col: int, row: int):
        if col < 0 or col >= self.size or row < 0 or row >= self.size:
            return
        light = self.lights[row * self.size + col]
        light.active = not light.active

    def all_off(self) -> bool:
        for light in self.lights:
            if light.active:
                return False
        return True

    def update(self, dt: float):
        if self.wait >= 0:
            self.wait -= dt
            if self.wait < 0:
                self.next_level()
            return
        if not input.pointer_pressed():
            return
        col = int((input.pointer_x() - self.left) // self.cell)
        row = int((input.pointer_y() - self.top) // self.cell)
        if col < 0 or col >= self.size or row < 0 or row >= self.size:
            return
        self.flip(col, row)
        self.flip(col - 1, row)
        self.flip(col + 1, row)
        self.flip(col, row - 1)
        self.flip(col, row + 1)
        game.add("moves", 1)
        audio.play(self.click, 0.6)
        if self.all_off():
            audio.play(self.solved)
            self.wait = 1.0

    def next_level(self):
        if self.level + 1 < self.count:
            self.level += 1
            self.build()
            return
        points = max(0, 500 - int(game.get("moves")) * 5)
        game.store_set("score", str(points))
        game.exit({"result": "win"})


@prefab
def pause():
    return Entity("pause", Shape(shape="circle", radius=20, color="#232b4a", layer=10), OnTap(open_app("pause_menu")),
                  children=[Entity("bars", Text("II", size=16, align="center", layer=11), at=(0, 6))])


main = game.scene("main", start=True, music=music, music_volume=0.35, on_back=open_app("pause_menu"))
main.add(Entity("board", Board()))
main.add(Entity("title", Text(t("hud"), size=20, align="center", layer=10)), at=(180, 90), ui=True)
main.add(Entity("hint", Text(t("how"), size=13, align="center", max_width=300, color="#9aa3c8", layer=10)),
         at=(180, 520), ui=True)
main.add(pause(), at=(330, 34), ui=True)
