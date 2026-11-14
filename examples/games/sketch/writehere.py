from apkpy_lib import *

# Sketchbook: the app (ApkPy). The game itself is game/main.py (ApkPyGame).
home = Screen(id="home")

enable_game()

label("Sketchbook", id="title", screen=home)
label("Paint with a finger. Done brings you back here.", id="hint", screen=home)


def play():
    game_play("main", "{}")


button("Open the page", command=play, screen=home)

style = """
title { font-size: 28px; font-weight: bold; }
hint { font-size: 16px; }
"""

run(start_screen=home, theme=Theme(mode="dark"))
