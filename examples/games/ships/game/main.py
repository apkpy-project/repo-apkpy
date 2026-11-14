"""Rock Rain: a ship at the bottom shoots falling rocks. Components only.

Read by the build (apkpy game build / play / run), never run.
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
