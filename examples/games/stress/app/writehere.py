from apkpy_lib import *

# The first ApkPyGame example: an ApkPy menu that opens the engine (500 / 2000 rotating sprites)
# and checks that the phone computes the same game as the PC.
home = Screen(id="home", scroll=True)
results = Screen(id="results")

enable_game()

label("ApkPyGame 0.1", id="title", screen=home)
status = label("Tap a button", id="status", screen=home)
result_info = label("", id="result_info", screen=results)


def on_game(ok, value):
    result_info.set_value(value)
    on_click_navigate(results)


def play_500():
    game_play("main", "{}", on_result=on_game)


def play_2000():
    game_play("heavy", "{}", on_result=on_game)


def play_5000():
    game_play("huge", "{}", on_result=on_game)

def play_50000():
    game_play("huge10x", "{}", on_result=on_game)


def parity():
    status.set_value("state after 600 steps (main): " + game_snapshot("main", "{}", "600"))


button("Play: 500 sprites", command=play_500, screen=home)
button("Play: 2000 sprites", command=play_2000, screen=home)
button("Play: 5000 sprites", command=play_5000, screen=home)
button("Play: 50000 sprites", command=play_50000, screen=home)
button("Parity check", command=parity, screen=home)
button("Home", command=lambda: on_click_navigate(home), screen=results)

run(start_screen=home, theme=Theme(mode="dark"))
