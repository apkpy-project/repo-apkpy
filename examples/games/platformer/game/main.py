"""Meadow Run: a Tiled level, run and jump, coins, slimes to stomp, a flag. Components only.

Read by the build (apkpy game build / play / run), never run.
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
