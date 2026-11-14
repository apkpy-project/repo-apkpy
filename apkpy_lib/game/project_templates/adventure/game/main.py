"""Keys of the Keep: walk the rooms of the keep, take the keys, open the doors, find the gems, and take the stairs
down. Two floors. Touch where to go (or use the arrow keys); the slimes cost a life.

Made of components only: open it in the Studio (apkpy game studio) to change any of it, or change it here.
The floors are levels/level1.tmj and levels/level2.tmj: walls on the solid layer "walls", and the things (keys,
doors, chests, slimes, the stairs) on the object layer. Paint and place them in the Studio's Levels, or in Tiled.
"""
from apkpy_lib.game import *

game = Game("Keys of the Keep", size=(320, 180), scale="fit", orientation="landscape", background="#1b1e26",
            pixel_scale=True, vars={"keys": 0, "gems": 0, "lives": 3})

level1 = assets.tilemap("levels/level1.tmj")
level2 = assets.tilemap("levels/level2.tmj")
hero_img = assets.sheet("assets/hero.png", frame=(16, 16))
slime_img = assets.sheet("assets/slime.png", frame=(16, 16))
key_img = assets.image("assets/key.png")
door_img = assets.image("assets/door.png")
chest_img = assets.image("assets/chest.png")
gem_img = assets.image("assets/gem.png")
stairs_img = assets.image("assets/stairs.png")
pick = assets.sound("assets/key.wav")
opens = assets.sound("assets/door.wav")
shine = assets.sound("assets/gem.wav")
hurt = assets.sound("assets/hit.wav")
win = assets.sound("assets/win.wav")
music = assets.music("assets/theme.wav")


@prefab
def hero():
    return Entity("hero",
                  Sprite(hero_img, frame=0, filter="nearest"),
                  Animator({"walk": {"frames": [0, 1], "fps": 4}}, play="walk", auto=False),
                  Collider(size=(10, 10), offset=(0, 2)),
                  Body(),
                  TopDownController(speed=80, clamp=False),
                  tags=["hero"])


@prefab
def key():
    return Entity("key",
                  Sprite(key_img, filter="nearest"),
                  Collider(size=(12, 10), trigger=True),
                  OnCollide("hero", var_add("keys"), sound(pick), destroy()))


@prefab
def door():
    return Entity("door",
                  Sprite(door_img, filter="nearest"),
                  Collider(size=(16, 16), solid=True),
                  OnCollide("hero", only_if("keys >= 1", var_add("keys", -1), sound(opens), destroy())),
                  tags=["door"])


@prefab
def sparkle():
    return Entity("sparkle", Sprite(gem_img, filter="nearest", layer=5), Mover((0, -30)), Lifetime(0.6))


@prefab
def chest():
    return Entity("chest",
                  Sprite(chest_img, filter="nearest"),
                  Collider(size=(14, 12), trigger=True),
                  OnCollide("hero", var_add("gems"), sound(shine), spawn(sparkle()), destroy()))


@prefab
def slime():
    return Entity("slime",
                  Sprite(slime_img, frame=0, filter="nearest"),
                  Animator({"wobble": {"frames": [0, 1], "fps": 3}}, play="wobble", auto=False),
                  Collider(size=(12, 8), offset=(0, 4)),
                  Body(),
                  Patrol(speed=24, distance=40, edges=False),
                  OnCollide("hero", var_add("lives", -1), sound(hurt), respawn("other")),
                  tags=["slime"])


@prefab
def stairs():
    return Entity("stairs",
                  Sprite(stairs_img, filter="nearest", layer=-1),
                  Collider(size=(10, 10), trigger=True),
                  OnCollide("hero", sound(win), goto_scene("level2", fade=0.5)))


@prefab
def last_stairs():
    return Entity("stairs",
                  Sprite(stairs_img, filter="nearest", layer=-1),
                  Collider(size=(10, 10), trigger=True),
                  OnCollide("hero", sound(win), store_set("score", "{gems}"), exit_game({"result": "win"})))


@prefab
def hud():
    return Entity("hud", Text(t("hud"), size=10, layer=30))


@prefab
def pause():
    return Entity("pause", Shape(shape="circle", radius=12, color="#2a2f45", alpha=0.8, layer=30),
                  OnTap(open_app("pause_menu")),
                  children=[Entity("bars", Text("II", size=10, align="center", layer=31), at=(0, 4))])


main = game.scene("main", start=True, music=music, music_volume=0.35, on_back=open_app("pause_menu"),
                  camera={"follow": "hero", "bounds": "map"},
                  rules=[when("lives <= 0", store_set("score", "{gems}"), exit_game({"result": "lose"}))])

main.add(Entity("map", Tilemap(level1, solid=["walls"], objects={
    "hero": hero(), "key": key(), "door": door(), "chest": chest(), "slime": slime(), "stairs": stairs()})))
main.add(hud(), at=(8, 12), ui=True)
main.add(pause(), at=(300, 16), ui=True)

floor_two = game.scene("level2", music=music, music_volume=0.35, on_back=open_app("pause_menu"),
                       camera={"follow": "hero", "bounds": "map"},
                       rules=[when("lives <= 0", store_set("score", "{gems}"), exit_game({"result": "lose"}))])

floor_two.add(Entity("map", Tilemap(level2, solid=["walls"], objects={
    "hero": hero(), "key": key(), "door": door(), "chest": chest(), "slime": slime(), "stairs": last_stairs()})))
floor_two.add(hud(), at=(8, 12), ui=True)
floor_two.add(pause(), at=(300, 16), ui=True)
