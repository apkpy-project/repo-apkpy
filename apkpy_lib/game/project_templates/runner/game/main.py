"""Rooftop Run: the runner never stops. A tap (or Space) is a hop over a crate; held, it is a high jump, for the
coins up there. The birds fly high: a hop goes under them, a high jump does not. After 120 m it gets faster; at 300 m
you win.

Made of components only: open it in the Studio (apkpy game studio) to change any of it, or change it here.
The runner stays where it is: the crates, the birds, the coins and the clouds come to it.
"""
from apkpy_lib.game import *

game = Game("Rooftop Run", size=(320, 180), scale="fit", orientation="landscape", background="#8fd3ff",
            pixel_scale=True, vars={"distance": 0, "coins": 0, "lives": 3})

runner_img = assets.sheet("assets/runner.png", frame=(16, 16))
crate_img = assets.image("assets/crate.png")
bird_img = assets.sheet("assets/bird.png", frame=(16, 12))
coin_img = assets.sheet("assets/coin.png", frame=(12, 12))
cloud_img = assets.image("assets/cloud.png")
jump = assets.sound("assets/jump.wav")
ding = assets.sound("assets/coin.wav")
hit = assets.sound("assets/hit.wav")
music = assets.music("assets/theme.wav")


@prefab
def runner():
    return Entity("player",
                  Sprite(runner_img, frame=0, filter="nearest"),
                  Collider(size=(10, 14), offset=(0, 1)),
                  Body(gravity=900, max_fall=420),
                  PlatformerController(speed=0, jump=320),
                  Animator({"idle": {"frames": [0, 1, 2, 3], "fps": 12}, "run": {"frames": [0, 1, 2, 3], "fps": 12},
                            "jump": {"frames": [4]}, "fall": {"frames": [5]}}),
                  OnCollide("crate", var_add("lives", -1), destroy("other"), sound(hit)),
                  OnCollide("bird", var_add("lives", -1), destroy("other"), sound(hit)),
                  tags=["player"])


@prefab
def crate(speed: float = 150):
    return Entity("crate",
                  Sprite(crate_img, filter="nearest"),
                  Mover((-speed, 0)),
                  Collider(size=(12, 14), trigger=True),
                  Lifetime(4),
                  tags=["crate"])


@prefab
def bird(speed: float = 190):
    return Entity("bird",
                  Sprite(bird_img, frame=0, filter="nearest"),
                  Animator({"fly": {"frames": [0, 1], "fps": 6}}, play="fly", auto=False),
                  Mover((-speed, 0)),
                  Collider(size=(12, 10), trigger=True),
                  Lifetime(4),
                  tags=["bird"])


@prefab
def coin(speed: float = 150):
    return Entity("coin",
                  Sprite(coin_img, frame=0, filter="nearest"),
                  Animator({"spin": {"frames": [0, 1, 2, 3], "fps": 8}}),
                  Mover((-speed, 0)),
                  Collider(size=(10, 12), trigger=True),
                  Lifetime(4),
                  OnCollide("player", destroy(), var_add("coins"), sound(ding)))


@prefab
def cloud(speed: float = 20):
    return Entity("cloud", Sprite(cloud_img, alpha=0.9, layer=-5, filter="nearest"), Mover((-speed, 0)), Lifetime(20))


@prefab
def ground():
    return Entity("ground",
                  Shape(size=(400, 26), color="#6a5248"),
                  Collider(size=(400, 26), solid=True),
                  children=[Entity("edge", Shape(size=(400, 3), color="#9c7a6a"), at=(0, -12))])


@prefab
def clock():
    return Entity("clock", Timer(0.25, var_add("distance")))


@prefab
def hud():
    return Entity("hud", Text(t("hud"), size=11, color="#14213d", layer=30))


@prefab
def tap_to_jump():
    return Entity("tap", TouchButton("jump", size=(270, 160)))


@prefab
def pause():
    return Entity("pause", Shape(shape="circle", radius=12, color="#14213d", alpha=0.6, layer=30),
                  OnTap(open_app("pause_menu")),
                  children=[Entity("bars", Text("II", size=10, align="center", layer=31), at=(0, 4))])


main = game.scene("main", start=True, music=music, music_volume=0.4, on_back=open_app("pause_menu"), rules=[
    when("lives <= 0", store_set("score", "{distance}"), exit_game({"result": "lose"})),
    when("distance >= 120", goto_scene("fast", fade=0.3)),
])

main.add(ground(), at=(160, 168))
main.add(runner(), at=(60, 140))
main.add(Entity("crates", Spawner(crate(), every=1.7, jitter=0.6, delay=1.5)), at=(340, 148))
main.add(Entity("birds", Spawner(bird(), every=5, jitter=1.5, delay=7)), at=(340, 92))
main.add(Entity("coins", Spawner(coin(), every=2.3, jitter=0.8, area=(0, 0, 0, 34), delay=2)), at=(340, 90))
main.add(Entity("clouds", Spawner(cloud(), every=3, jitter=1, area=(0, 0, 0, 50))), at=(340, 14))
main.add(clock())
main.add(hud(), at=(8, 14), ui=True)
main.add(tap_to_jump(), at=(135, 100), ui=True)
main.add(pause(), at=(300, 16), ui=True)

fast = game.scene("fast", music=music, music_volume=0.4, on_back=open_app("pause_menu"), rules=[
    when("lives <= 0", store_set("score", "{distance}"), exit_game({"result": "lose"})),
    when("distance >= 300", store_set("score", "{distance}"), exit_game({"result": "win"})),
])

fast.add(ground(), at=(160, 168))
fast.add(runner(), at=(60, 140))
fast.add(Entity("crates", Spawner(crate(200), every=1.3, jitter=0.5, delay=1.5)), at=(340, 148))
fast.add(Entity("birds", Spawner(bird(240), every=4, jitter=1.2, delay=4)), at=(340, 92))
fast.add(Entity("coins", Spawner(coin(200), every=2, jitter=0.7, area=(0, 0, 0, 34), delay=2)), at=(340, 90))
fast.add(Entity("clouds", Spawner(cloud(30), every=2.5, jitter=1, area=(0, 0, 0, 50))), at=(340, 14))
fast.add(clock())
fast.add(Entity("faster", Text(t("faster"), size=16, align="center", color="#14213d", layer=30), Lifetime(1.5)),
         at=(160, 60), ui=True)
fast.add(hud(), at=(8, 14), ui=True)
fast.add(tap_to_jump(), at=(135, 100), ui=True)
fast.add(pause(), at=(300, 16), ui=True)
