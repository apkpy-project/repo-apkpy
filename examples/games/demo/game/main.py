"""demo: the game, described for ApkPyGame.

This file is READ by the build (apkpy game build / play / run), never run:
write declarations with literal values, as in ApkPy's writehere.py.
"""
from apkpy_lib.game import *

game = Game("demo", size=(360, 640), scale="fit", orientation="portrait", background="#0b0e1a")

star = assets.image("assets/star.png")
pop = assets.sound("assets/pop.wav")
theme = assets.music("assets/theme.wav")


@prefab
def coin(tint: str = "#ffd45c", speed: float = 120):
    return Entity("coin",
                  Sprite(star, tint=tint),
                  Spin(speed),
                  Mover((speed / 2, speed / 3), bounce=True),
                  OnTap(sound(pop), store_add("coins", 1), destroy()),
                  tags=["coin"])


main = game.scene("main", start=True, music=theme, music_volume=0.5)
main.add(Entity("hint", Text("Tap the stars", size=20, align="center")), at=(180, 70))
main.add(coin(), at=(90, 200))
main.add(coin(tint="#5cd6ff", speed=-160), at=(270, 260))
main.add(coin(tint="#ff5c8a", speed=200), at=(180, 380), scale=1.4)
main.add(coin(tint="#8aff5c"), at=(110, 470), rotation=30)
main.add(coin(tint="#c45cff", speed=-90), at=(250, 520))
main.add(Entity("done",
                Shape(size=(140, 44), color="#2a2f45", layer=5),
                OnTap(exit_game({"reason": "button"})),
                children=[Entity("label", Text("Done", size=18, align="center", layer=6), at=(0, 6))]),
         at=(180, 600))
