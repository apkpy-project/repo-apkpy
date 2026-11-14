"""Hop Hills: run and jump through two levels to the flag. Coins to take, slimes to jump on.

Made of components only: open it in the Studio (apkpy game studio) to change any of it, or change it here.
The levels are levels/level1.tmj and levels/level2.tmj: paint them in the Studio's Levels, or in Tiled.
"""
from apkpy_lib.game import *

game = Game("Hop Hills", size=(320, 180), scale="fit", orientation="landscape", background="#8fd3ff",
            pixel_scale=True, vars={"coins": 0, "lives": 3})

level1 = assets.tilemap("levels/level1.tmj")
level2 = assets.tilemap("levels/level2.tmj")
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
                  Animator({"spin": {"frames": [0, 1, 2, 3], "fps": 8}}),
                  Collider(size=(10, 12), trigger=True),
                  OnCollide("player", destroy(), var_add("coins"), sound(ding)),
                  tags=["coin"])


@prefab
def enemy():
    return Entity("slime",
                  Sprite(slime, frame=0, filter="nearest"),
                  Animator({"walk": {"frames": [0, 1], "fps": 4}}, play="walk", auto=False),
                  Collider(size=(12, 8), offset=(0, 4)),
                  Body(gravity=900),
                  Patrol(speed=30, distance=48),
                  OnCollide("player", destroy(), sound(stomp), impulse((0, -230), "other", keep_x=True), side="top"),
                  OnCollide("player", var_add("lives", -1), sound(hurt), respawn("other"), side="sides"),
                  tags=["enemy"])


@prefab
def goal():
    return Entity("flag",
                  Sprite(flag, filter="nearest"),
                  Collider(size=(10, 30), trigger=True),
                  OnCollide("player", sound(win), goto_scene("level2", fade=0.4)))


@prefab
def finish():
    return Entity("flag",
                  Sprite(flag, filter="nearest"),
                  Collider(size=(10, 30), trigger=True),
                  OnCollide("player", sound(win), store_set("score", "{coins}"), exit_game({"result": "win"})))


@prefab
def pit():
    return Entity("pit", Collider(size=(4000, 16), trigger=True),
                  OnCollide("player", var_add("lives", -1), sound(hurt), respawn("other")))


@prefab
def hud():
    return Entity("hud", Text(t("hud"), size=11, color="#14213d", layer=30))


@prefab
def pad(image=left, key: str = "left"):
    return Entity("pad-" + key, Sprite(image, alpha=0.8, layer=30), TouchButton(key, radius=22))


@prefab
def pause():
    return Entity("pause", Shape(shape="circle", radius=12, color="#14213d", alpha=0.6, layer=30),
                  OnTap(open_app("pause_menu")),
                  children=[Entity("bars", Text("II", size=10, align="center", layer=31), at=(0, 4))])


main = game.scene("main", start=True, music=music, music_volume=0.4, on_back=open_app("pause_menu"),
                  camera={"follow": "player", "bounds": "map"},
                  rules=[when("lives <= 0", store_set("score", "{coins}"), exit_game({"result": "lose"}))])

main.add(Entity("map", Tilemap(level1, solid=["ground"],
                               objects={"player": player(), "coin": coin(), "slime": enemy(), "flag": goal()})))
main.add(pit(), at=(1000, 260))
main.add(hud(), at=(8, 14), ui=True)
main.add(pause(), at=(300, 16), ui=True)
main.add(pad(left, "left"), at=(28, 152), ui=True)
main.add(pad(right, "right"), at=(76, 152), ui=True)
main.add(pad(up, "jump"), at=(292, 152), ui=True)

level_two = game.scene("level2", music=music, music_volume=0.4, on_back=open_app("pause_menu"),
                       camera={"follow": "player", "bounds": "map"},
                       rules=[when("lives <= 0", store_set("score", "{coins}"), exit_game({"result": "lose"}))])

level_two.add(Entity("map", Tilemap(level2, solid=["ground"],
                                    objects={"player": player(), "coin": coin(), "slime": enemy(), "flag": finish()})))
level_two.add(pit(), at=(1000, 260))
level_two.add(hud(), at=(8, 14), ui=True)
level_two.add(pause(), at=(300, 16), ui=True)
level_two.add(pad(left, "left"), at=(28, 152), ui=True)
level_two.add(pad(right, "right"), at=(76, 152), ui=True)
level_two.add(pad(up, "jump"), at=(292, 152), ui=True)
