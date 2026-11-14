"""Creates src/examples/scripted (dev machine only): Rock Rain with its logic in Python scripts.

    python src/dev/make_phase4_examples.py      (first: the ships assets)
    python src/dev/make_phase5_example.py

The ship, the rocks (zig-zag with math.sin), the waves and the HUD are
Script classes, translated to Java by the build. A "selftest" scene runs the
semantics corpus inside the game (for the phone parity check).
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))      # ApkPy's repository
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import where  # noqa: E402
TOOLS = os.path.join(ROOT, "tools", "game")
SRC = ROOT
sys.path.insert(0, ROOT)
from apkpy_lib.game import glue, templates  # noqa: E402

MAIN = '''"""Rock Rain, scripted: the same game as src/examples/ships, with its logic in Python scripts.

Read by the build: the declarations become the bundle, the Script classes become Java.
"""
from apkpy_lib.game import *
import math
import random

game = Game("Rock Rain Scripted", size=(360, 640), scale="fit", orientation="portrait", background="#05060d",
            vars={"score": 0, "lives": 3, "wave": 1})

ship_img = assets.image("assets/ship.png")
rock_img = assets.image("assets/rock1.png")
shoot = assets.sound("assets/shoot.wav")
boom = assets.sound("assets/boom.wav")
hit = assets.sound("assets/hit.wav")
music = assets.music("assets/theme.wav")
WIN = 30


def wave_of(score: float) -> int:
    return 1 + int(score) // 10


@prefab
def explosion():
    return Entity("explosion", Emitter(burst=24, lifetime=(0.3, 0.6), speed=(60, 180), size=(6, 1), color="#ffd45c",
                                       color_end="#ff5c8a"), Lifetime(0.7))


@prefab
def bullet():
    return Entity("bullet", Shape(size=(4, 14), color="#5cd6ff"), Mover((0, -520)),
                  Collider(size=(4, 14), trigger=True), Lifetime(1.4), tags=["bullet"])


class Rock(Script):
    """Falls, zig-zags (math.sin), faster each wave; a bullet breaks it."""
    fall: float = 120.0
    swing: float = 40.0
    boom: Sound = boom
    sparks: Prefab = explosion()
    age: float = 0.0
    base_x: float = 0.0

    def on_start(self):
        self.base_x = self.x
        self.fall = self.fall + 25 * (game.get("wave") - 1)

    def update(self, dt: float):
        self.age += dt
        self.y += self.fall * dt
        self.x = self.base_x + math.sin(self.age * 2.5) * self.swing
        self.rotation += 90 * dt
        if self.y > game.height + 40:
            self.destroy()

    def on_collide(self, other: Entity, side: str):
        if other.has_tag("bullet"):
            other.destroy()
            self.destroy()
            audio.play(self.boom)
            scene.spawn(self.sparks, self.x, self.y)
            game.add("score", 1)
            game.set("wave", wave_of(game.get("score")))


@prefab
def rock():
    return Entity("rock", Sprite(rock_img), Collider(shape="circle", radius=15), Rock(), tags=["rock"])


class Waves(Script):
    """Drops rocks: more of them, and closer together, each wave."""
    rock: Prefab = rock()
    wait: float = 1.0

    def update(self, dt: float):
        self.wait -= dt
        if self.wait <= 0:
            wave = int(game.get("wave"))
            for i in range(min(wave, 3)):
                scene.spawn(self.rock, random.uniform(40, 320), -30.0 - i * 50)
            self.wait = max(0.5, 1.6 - wave * 0.2)


class Ship(Script):
    """Follows the finger (or the arrows), fires on its own, loses a life on a rock."""
    speed: float = 340.0
    shot: Prefab = bullet()
    pew: Sound = shoot
    ouch: Sound = hit
    cooldown: float = 0.0

    def update(self, dt: float):
        target = self.x
        if input.pointer_down():
            target = input.pointer_x()
        else:
            target = self.x + input.axis_x() * self.speed * dt
        step = self.speed * dt
        if abs(target - self.x) <= step:
            self.x = target
        elif target > self.x:
            self.x += step
        else:
            self.x -= step
        self.x = max(16.0, min(game.width - 16, self.x))
        self.cooldown -= dt
        if self.cooldown <= 0:
            scene.spawn(self.shot, self.x, self.y - 20)
            audio.play(self.pew, 0.25)
            self.cooldown = 0.3 - min(0.15, game.get("wave") * 0.03)
        if game.get("lives") <= 0 or game.get("score") >= WIN:
            result = "win" if game.get("score") >= WIN else "lose"
            game.store_set("last_result", result)
            game.exit({"result": result, "score": game.get("score"), "wave": int(game.get("wave"))})

    def on_collide(self, other: Entity, side: str):
        if other.has_tag("rock"):
            other.destroy()
            game.add("lives", -1)
            audio.play(self.ouch)


class Hud(Script):
    def update(self, dt: float):
        self.text.text = f"{int(game.get('score'))}   wave {int(game.get('wave'))}   lives {int(game.get('lives'))}"


play = game.scene("main", start=True, music=music, music_volume=0.4, on_back=open_app("pause_menu"))
play.add(Entity("stars", Spawner(Entity("star", Shape(size=(2, 2), color="#8890b0", layer=-5), Mover((0, 90)),
                                        Lifetime(8)), every=0.12, area=(0, 0, 360, 0))), at=(0, -10))
play.add(Entity("waves", Waves()))
play.add(Entity("ship", Sprite(ship_img), Collider(shape="circle", radius=12), Ship(), tags=["ship"]), at=(180, 570))
play.add(Entity("hud", Text("", size=18, align="center", layer=20), Hud()), at=(180, 40), ui=True)
play.add(Entity("pause", Shape(shape="circle", radius=20, color="#2a2f45", layer=20), OnTap(open_app("pause_menu")),
                children=[Entity("bars", Text("II", size=16, align="center", layer=21), at=(0, 6))]),
         at=(330, 30), ui=True)


# ── self-test: the semantics corpus, inside the game (the phone parity check) ──

def corpus() -> str:
    out = str(7 // 2) + " " + str(-7 // 2) + " " + str(-7 % 3) + " " + str(7.5 % -2.0) + " " + str(2 ** 10)
    out = out + " " + str(round(2.5)) + " " + str(round(-1.5)) + " " + str(round(2.675, 2)) + " " + str(int(-3.9))
    out = out + " " + str(0.1) + " " + str(1e16) + " " + str(1.5e-5) + " " + f"{3.14159:.2f}" + " " + f"{42:05d}"
    total = 0
    for i in range(5):
        total += i * 2.5
    xs: list[int] = []
    for i in range(6):
        xs.append(i * i)
    out = out + " " + str(total) + " " + str(xs[-1]) + " " + str(math.atan2(1.0, 2.0)) + " " + str(math.sqrt(2.0))
    return out


class SelfTest(Script):
    def update(self, dt: float):
        game.exit({"corpus": corpus(), "r": random.randint(1, 1000), "u": round(random.uniform(0, 1), 9)})


selftest = game.scene("selftest")
selftest.add(Entity("t", SelfTest()))
'''


def main():
    ships = where.examples("ships", "assets")
    if not os.path.isdir(ships):
        sys.exit("run src/dev/make_phase4_examples.py first (the ships assets)")
    folder = where.examples("scripted")
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    os.makedirs(os.path.join(folder, "game"))
    shutil.copytree(ships, os.path.join(folder, "assets"))
    with open(os.path.join(folder, "game", "main.py"), "w", encoding="utf-8") as fh:
        fh.write(MAIN)
    app_id = "com.apkpygame.scripted"
    with open(os.path.join(folder, "apkpy.toml"), "w", encoding="utf-8") as fh:
        fh.write(templates.TOML.format(name="Rock Rain Scripted", app_id=app_id))
    with open(os.path.join(folder, "writehere.py"), "w", encoding="utf-8") as fh:
        fh.write(templates.WRITEHERE_MENUS.format(name="Rock Rain Scripted", glue="enable_game()\n"))
    print("created", folder)


if __name__ == "__main__":
    main()
