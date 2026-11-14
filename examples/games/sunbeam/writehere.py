from apkpy_lib import *

# Sunbeam: the app (ApkPy) around the game (ApkPyGame, game/main.py).
# Screens first (an ApkPy rule: a button that opens a screen declared below it does nothing).
home = Screen(id="home")
pause_menu = Screen(id="pause_menu")
results = Screen(id="results")

# One table of words for the app AND the game (the game's t("key") reads it too).
translations({
    "en": {"title": "Sunbeam", "play": "Play", "best": "Best (fewest taps)", "continue": "Continue",
            "quit": "Quit to menu", "home": "Menu", "paused": "Paused", "results": "All flowers in bloom!",
            "taps_used": "Taps", "level": "Level {level}", "taps": "Taps: {taps}  (par {par})",
            "hint": "Tap a mirror to turn it"},
    "pt": {"title": "Sunbeam", "play": "Jogar", "best": "Recorde (menos toques)", "continue": "Continuar",
            "quit": "Sair para o menu", "home": "Menu", "paused": "Em pausa", "results": "Todas as flores abriram!",
            "taps_used": "Toques", "level": "Nível {level}", "taps": "Toques: {taps}  (par {par})",
            "hint": "Toca num espelho para o rodar"},
}, default="en")

enable_game()

label(t("title"), id="title", screen=home)
label(t("best"), id="best_caption", screen=home)
home_best = label("-", id="home_best", screen=home)
label(t("paused"), id="paused", screen=pause_menu)
label(t("results"), id="results_title", screen=results)
label(t("taps_used"), id="results_caption", screen=results)
results_taps = label("0", id="results_taps", screen=results)


def best():
    value = game_get("sunbeam_best")
    if value == "":
        return "-"
    return value


def finished(ok, value):
    game_last_result()                      # handled here: on_resume needs not pick it up again
    if '"action":"open"' in value:
        on_click_navigate(pause_menu)
    elif '"action":"exit"' in value and '"taps":' in value:
        results_taps.set_value(value.split('"taps":')[1].split("}")[0].split(",")[0].split(".")[0])
        on_click_navigate(results)


def play():
    game_play("main", "{}", on_result=finished)


def resume():
    game_resume(on_result=finished)


def home_shown():
    home_best.set_value(best())
    missed = game_last_result()             # an answer that came while this screen was gone
    if '"action":"open"' in missed:
        on_click_navigate(pause_menu)


lifecycle(home, on_resume=home_shown)

button(t("play"), id="play", command=play, screen=home)
button(t("continue"), id="continue", command=resume, screen=pause_menu)
button(t("quit"), id="quit", command=lambda: on_click_navigate(home), screen=pause_menu)
button(t("home"), id="results_home", command=lambda: on_click_navigate(home), screen=results)

style = """
title { font-size: 32px; font-weight: bold; }
home_best { font-size: 32px; }
results_taps { font-size: 40px; }
"""

run(start_screen=home, theme=Theme(mode="dark"))
