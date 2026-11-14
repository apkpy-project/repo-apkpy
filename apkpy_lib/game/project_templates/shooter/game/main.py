"""Star Guard: the ship at the bottom fires by itself; slide it to break the falling rocks. Wave 2 brings saucers
that fire back. A heart now and then gives a life.

Made of components only: open it in the Studio (apkpy game studio) to change any of it, or change it here.
"""
from apkpy_lib.game import *

game = Game("Star Guard", size=(360, 640), scale="fit", orientation="portrait", background="#05060d",
            vars={"score": 0, "lives": 3})

ship_img = assets.image("assets/ship.png")
rock1 = assets.image("assets/rock1.png")
rock2 = assets.image("assets/rock2.png")
saucer_img = assets.image("assets/saucer.png")
heart_img = assets.image("assets/heart.png")
shoot = assets.sound("assets/shoot.wav")
boom = assets.sound("assets/boom.wav")
hit = assets.sound("assets/hit.wav")
life = assets.sound("assets/life.wav")
music = assets.music("assets/theme.wav")


@prefab
def explosion(color: str = "#ffd45c"):
    return Entity("explosion",
                  Emitter(burst=26, lifetime=(0.3, 0.7), speed=(60, 200), size=(7, 1), color=color, color_end="#ff5c8a"),
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
                  Collider(shape="circle", radius=14),
                  Lifetime(7),
                  OnCollide("bullet", destroy(), destroy("other"), var_add("score"), sound(boom), spawn(explosion())),
                  tags=["rock"])


@prefab
def shot():
    return Entity("shot",
                  Shape(shape="circle", radius=4, color="#ff5c8a"),
                  Mover((0, 260)),
                  Collider(shape="circle", radius=4, trigger=True),
                  Lifetime(3),
                  tags=["shot"])


@prefab
def saucer():
    return Entity("saucer",
                  Sprite(saucer_img),
                  Mover((90, 25), bounce=True),
                  Collider(size=(28, 14)),
                  Timer(1.6, spawn(shot(), offset=(0, 12)), delay=0.8),
                  Lifetime(14),
                  OnCollide("bullet", destroy(), destroy("other"), var_add("score", 3), sound(boom),
                            spawn(explosion("#5cd6ff"))),
                  tags=["saucer"])


@prefab
def heart():
    return Entity("heart",
                  Sprite(heart_img),
                  Mover((0, 90)),
                  Collider(size=(18, 16), trigger=True),
                  Lifetime(8),
                  OnCollide("ship", var_add("lives"), sound(life), destroy()))


@prefab
def star(speed: float = 80):
    return Entity("star", Shape(size=(2, 2), color="#8890b0", layer=-5), Mover((0, speed)), Lifetime(9))


@prefab
def ship():
    return Entity("ship",
                  Sprite(ship_img),
                  Collider(shape="circle", radius=12),
                  TopDownController(speed=340, axis="x"),
                  Timer(0.25, spawn(bullet(), offset=(0, -20)), sound(shoot, 0.25)),
                  OnCollide("rock", var_add("lives", -1), destroy("other"), sound(hit), spawn(explosion("#ff5c8a"))),
                  OnCollide("shot", var_add("lives", -1), destroy("other"), sound(hit)),
                  OnCollide("saucer", var_add("lives", -1), destroy("other"), sound(hit), spawn(explosion("#ff5c8a"))),
                  Emitter(rate=40, lifetime=(0.2, 0.4), speed=(60, 120), angle=(80, 100), size=(4, 1), color="#5cd6ff",
                          color_end="#2a2f45", layer=-1),
                  tags=["ship"])


@prefab
def pause():
    return Entity("pause", Shape(shape="circle", radius=20, color="#2a2f45", layer=20), OnTap(open_app("pause_menu")),
                  children=[Entity("bars", Text("II", size=16, align="center", layer=21), at=(0, 6))])


main = game.scene("main", start=True, music=music, music_volume=0.4, on_back=open_app("pause_menu"), rules=[
    when("lives <= 0", store_set("score", "{score}"), exit_game({"result": "lose"})),
    when("score >= 15", goto_scene("wave2", fade=0.5)),
])

main.add(Entity("stars", Spawner(star(), every=0.15, area=(0, 0, 360, 0))), at=(0, -10))
main.add(Entity("rocks", Spawner(rock(), every=1.1, jitter=0.3, area=(20, 0, 320, 0), delay=1)), at=(0, -30))
main.add(Entity("hearts", Spawner(heart(), every=11, jitter=3, area=(30, 0, 300, 0), delay=8)), at=(0, -20))
main.add(ship(), at=(180, 570))
main.add(Entity("score", Text("{score}", size=34, align="center", layer=20)), at=(180, 52), ui=True)
main.add(Entity("lives", Text(t("hud"), size=16, layer=20)), at=(14, 30), ui=True)
main.add(pause(), at=(330, 30), ui=True)

wave2 = game.scene("wave2", music=music, music_volume=0.4, on_back=open_app("pause_menu"), rules=[
    when("lives <= 0", store_set("score", "{score}"), exit_game({"result": "lose"})),
    when("score >= 45", store_set("score", "{score}"), exit_game({"result": "win"})),
])

wave2.add(Entity("stars", Spawner(star(140), every=0.12, area=(0, 0, 360, 0))), at=(0, -10))
wave2.add(Entity("rocks", Spawner(rock(rock2, 180, -140), every=1.3, jitter=0.4, area=(20, 0, 320, 0), delay=1)),
          at=(0, -30))
wave2.add(Entity("saucers", Spawner(saucer(), every=3.5, jitter=1, area=(40, 0, 280, 0), delay=2)), at=(0, 40))
wave2.add(Entity("hearts", Spawner(heart(), every=12, jitter=3, area=(30, 0, 300, 0), delay=10)), at=(0, -20))
wave2.add(ship(), at=(180, 570))
wave2.add(Entity("title", Text(t("wave2"), size=26, align="center", layer=20), Lifetime(2)), at=(180, 300), ui=True)
wave2.add(Entity("score", Text("{score}", size=34, align="center", layer=20)), at=(180, 52), ui=True)
wave2.add(Entity("lives", Text(t("hud"), size=16, layer=20)), at=(14, 30), ui=True)
wave2.add(pause(), at=(330, 30), ui=True)
