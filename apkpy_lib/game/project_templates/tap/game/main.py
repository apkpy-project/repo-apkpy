"""Quick Pop: stars pop up all over; tap each before it goes. Not the bombs! 40 seconds; eight stars missed or three
bombs and it ends early.

Made of components only: open it in the Studio (apkpy game studio) to change any of it, or change it here.
"""
from apkpy_lib.game import *

game = Game("Quick Pop", size=(360, 640), scale="fit", orientation="portrait", background="#141833",
            vars={"score": 0, "time": 40, "missed": 0, "lives": 3})

star_img = assets.image("assets/star.png")
bomb_img = assets.image("assets/bomb.png")
pop = assets.sound("assets/pop.wav")
boom = assets.sound("assets/boom.wav")
miss = assets.sound("assets/miss.wav")
music = assets.music("assets/theme.wav")


@prefab
def burst(color: str = "#ffd45c"):
    return Entity("burst", Emitter(burst=18, lifetime=(0.2, 0.5), speed=(60, 180), size=(6, 1), color=color), Lifetime(0.6))


@prefab
def target(tint: str = "#ffd45c", points: int = 1, seconds: float = 1.6):
    return Entity("star",
                  Sprite(star_img, tint=tint),
                  Spin(120),
                  Tween("scale", 1.2, 0.3, mode="pingpong"),
                  OnTap(var_add("score", points), sound(pop), spawn(burst(tint)), destroy(), radius=26),
                  Lifetime(seconds, var_add("missed"), sound(miss)),
                  tags=["star"])


@prefab
def bomb():
    return Entity("bomb",
                  Sprite(bomb_img),
                  Tween("rotation", 15, 0.2, mode="pingpong"),
                  OnTap(var_add("lives", -1), sound(boom), spawn(burst("#ff5c3a")), destroy(), radius=22),
                  Lifetime(1.8),
                  tags=["bomb"])


@prefab
def pause():
    return Entity("pause", Shape(shape="circle", radius=20, color="#2a2f45", layer=20), OnTap(open_app("pause_menu")),
                  children=[Entity("bars", Text("II", size=16, align="center", layer=21), at=(0, 6))])


main = game.scene("main", start=True, music=music, music_volume=0.4, on_back=open_app("pause_menu"), rules=[
    when("time <= 0", store_set("score", "{score}"), exit_game({"result": "win"})),
    when("missed >= 8", store_set("score", "{score}"), exit_game({"result": "lose"})),
    when("lives <= 0", store_set("score", "{score}"), exit_game({"result": "lose"})),
])

main.add(Entity("stars", Spawner(target(), every=0.75, jitter=0.25, area=(40, 140, 280, 420), delay=0.5)))
main.add(Entity("blue stars", Spawner(target("#5cd6ff", 3, 1.1), every=3.5, jitter=1, area=(40, 140, 280, 420), delay=4)))
main.add(Entity("bombs", Spawner(bomb(), every=2.2, jitter=0.8, area=(40, 140, 280, 420), delay=3)))
main.add(Entity("clock", Timer(1, var_add("time", -1))))
main.add(Entity("score", Text(t("hud"), size=40, align="center", layer=20)), at=(180, 70), ui=True)
main.add(Entity("clock text", Text(t("clock"), size=16, align="center", color="#9aa3c8", layer=20)), at=(180, 104),
         ui=True)
main.add(pause(), at=(330, 34), ui=True)
