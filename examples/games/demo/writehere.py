from apkpy_lib import *

# demo: the app (ApkPy). The game itself is game/main.py (ApkPyGame).
home = Screen(id="home")
results = Screen(id="results")

enable_game()

title = label("demo", id="title", screen=home)
coins = label("Coins: 0", id="coins", screen=home)
result_info = label("", id="result_info", screen=results)


def show_coins():
    value = game_get("coins")
    if value == "":
        value = "0"
    coins.set_value("Coins: " + value)


def finished(ok, value):
    result_info.set_value("The game ended: " + value)
    on_click_navigate(results)


def play():
    game_play("main", "{}", on_result=finished)


lifecycle(home, on_resume=show_coins)

button("Play", command=play, screen=home)
button("Home", command=lambda: on_click_navigate(home), screen=results)

style = """
title { font-size: 28px; font-weight: bold; }
coins { font-size: 20px; }
"""

run(start_screen=home, theme=Theme(mode="dark"))
