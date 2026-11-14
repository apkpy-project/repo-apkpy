"""Brickfall: slide the paddle to keep the ball up and break every brick. Two levels. The ball leaves the paddle
turned by where it touched it: the middle sends it straight up, the ends to the sides, so you aim.

Made of components only: open it in the Studio (apkpy game studio) to change any of it, or change it here.
The bricks are placed in levels/level1.tmj and levels/level2.tmj: move them, add some or take them away in the
Studio's Levels (each brick's class is its colour, as in objects={...} below).
"""
from apkpy_lib.game import *

game = Game("Brickfall", size=(360, 640), scale="fit", orientation="portrait", background="#10142a",
            vars={"score": 0, "lives": 3})

level1 = assets.tilemap("levels/level1.tmj")
level2 = assets.tilemap("levels/level2.tmj")
bounce = assets.sound("assets/paddle.wav")
crack = assets.sound("assets/brick.wav")
lost = assets.sound("assets/lost.wav")
music = assets.music("assets/theme.wav")


@prefab
def brick(color: str = "#ff5c8a", points: int = 10):
    return Entity("brick",
                  Shape(size=(42, 18), color=color),
                  Collider(size=(42, 18), solid=True),
                  OnCollide("ball", destroy(), var_add("score", points), sound(crack)),
                  tags=["brick"])


@prefab
def ball(speed: float = 300):
    return Entity("ball",
                  Shape(shape="circle", radius=6, color="#ffffff"),
                  Collider(size=(12, 12)),
                  Body(velocity=(speed / 2, -speed), bounce=1),
                  OnCollide("paddle", sound(bounce), deflect(55)),
                  tags=["ball"])


@prefab
def paddle():
    return Entity("paddle",
                  Shape(size=(72, 12), color="#5cd6ff"),
                  Collider(size=(72, 12), solid=True),
                  TopDownController(speed=480, axis="x", margin=36),
                  tags=["paddle"])


@prefab
def wall(width: float = 20, height: float = 640):
    return Entity("wall", Shape(size=(width, height), color="#1e2440"), Collider(size=(width, height), solid=True))


@prefab
def floor(speed: float = 300):
    return Entity("floor",
                  Collider(size=(400, 20), trigger=True),
                  OnCollide("ball", var_add("lives", -1), sound(lost), respawn("other"),
                            impulse((speed / 2, -speed), "other")))


@prefab
def hud():
    return Entity("hud", Text(t("hud"), size=16, layer=20))


@prefab
def pause():
    return Entity("pause", Shape(shape="circle", radius=18, color="#2a2f45", layer=20), OnTap(open_app("pause_menu")),
                  children=[Entity("bars", Text("II", size=14, align="center", layer=21), at=(0, 5))])


main = game.scene("main", start=True, music=music, music_volume=0.35, on_back=open_app("pause_menu"), rules=[
    when("count(brick) == 0", goto_scene("level2", fade=0.4)),
    when("lives <= 0", store_set("score", "{score}"), exit_game({"result": "lose"})),
])

main.add(Entity("bricks", Tilemap(level1, objects={
    "red": brick("#ff5c8a"), "orange": brick("#ff9a4a"), "yellow": brick("#ffd45c"),
    "green": brick("#7ad65c"), "blue": brick("#5c9aff", 20)})))
main.add(wall(), at=(-10, 320))
main.add(wall(), at=(370, 320))
main.add(wall(400, 20), at=(180, 34))
main.add(paddle(), at=(180, 590))
main.add(ball(), at=(180, 560))
main.add(floor(), at=(180, 660))
main.add(hud(), at=(14, 20), ui=True)
main.add(pause(), at=(334, 20), ui=True)

level_two = game.scene("level2", music=music, music_volume=0.35, on_back=open_app("pause_menu"), rules=[
    when("count(brick) == 0", store_set("score", "{score}"), exit_game({"result": "win"})),
    when("lives <= 0", store_set("score", "{score}"), exit_game({"result": "lose"})),
])

level_two.add(Entity("bricks", Tilemap(level2, objects={
    "red": brick("#ff5c8a"), "orange": brick("#ff9a4a"), "yellow": brick("#ffd45c"),
    "green": brick("#7ad65c"), "blue": brick("#5c9aff", 20), "purple": brick("#c45cff", 30)})))
level_two.add(wall(), at=(-10, 320))
level_two.add(wall(), at=(370, 320))
level_two.add(wall(400, 20), at=(180, 34))
level_two.add(paddle(), at=(180, 590))
level_two.add(ball(360), at=(180, 560))
level_two.add(floor(360), at=(180, 660))
level_two.add(hud(), at=(14, 20), ui=True)
level_two.add(pause(), at=(334, 20), ui=True)
