from apkpy_lib import *

# Rooftop Run: the app (ApkPy) around the game (game/main.py): a start screen, the pause screen the game opens with
# Back, and the results. Screens first (an ApkPy rule: a button that opens a screen declared below it does nothing).
home = Screen(id="home")
pause_menu = Screen(id="pause_menu")
results = Screen(id="results")

# One table of words for the app AND the game: the game's t("key") reads it too.
translations({
    "en": {"title": "Rooftop Run",
           "how": "Tap to hop over the crates. Hold to jump high for the coins, but not into a bird!",
           "play": "Play", "best": "Best", "continue": "Continue", "quit": "Quit to menu", "paused": "Paused",
           "won": "You won!", "lost": "Try again", "score": "Score", "again": "Play again", "home": "Menu",
           "hud": "{distance} m   Coins {coins}   Lives {lives}", "faster": "Faster!"},
    "pt": {"title": "Rooftop Run",
           "how": "Toca para saltar as caixas. Mantém para saltar alto às moedas, mas não contra um pássaro!",
           "play": "Jogar", "best": "Recorde", "continue": "Continuar", "quit": "Sair para o menu",
           "paused": "Em pausa", "won": "Ganhaste!", "lost": "Tenta outra vez", "score": "Pontos",
           "again": "Jogar outra vez", "home": "Menu", "hud": "{distance} m   Moedas {coins}   Vidas {lives}",
           "faster": "Mais rápido!"},
}, default="en")

enable_game()

label(t("title"), id="title", screen=home)
label(t("how"), id="how", screen=home)
label(t("best"), id="best_caption", screen=home)
best = label("0", id="best", screen=home)
label(t("paused"), id="paused", screen=pause_menu)
outcome = label("", id="outcome", screen=results)
label(t("score"), id="score_caption", screen=results)
score = label("0", id="score", screen=results)


def stored(key):
    value = game_get(key)
    if value == "":
        return "0"
    return value


def finished(ok, value):
    game_last_result()                      # handled here: on_resume needs not pick it up again
    if '"action":"open"' in value:
        on_click_navigate(pause_menu)
    elif '"action":"exit"' in value:
        got = stored("score")
        if '"result":"win"' in value:
            outcome.set_value(t("won"))
        else:
            outcome.set_value(t("lost"))
        score.set_value(got)
        if int(got) > int(stored("best")):
            game_set("best", got)
        on_click_navigate(results)


def play():
    game_set("score", "0")
    game_play("main", "{}", on_result=finished)


def resume():
    game_resume(on_result=finished)


def home_shown():
    best.set_value(stored("best"))
    missed = game_last_result()             # an answer that came while this screen was gone
    if '"action":"open"' in missed:
        on_click_navigate(pause_menu)


lifecycle(home, on_resume=home_shown)

button(t("play"), id="play", command=play, screen=home)
button(t("continue"), id="continue", command=resume, screen=pause_menu)
button(t("quit"), id="quit", command=lambda: on_click_navigate(home), screen=pause_menu)
button(t("again"), id="again", command=play, screen=results)
button(t("home"), id="results_home", command=lambda: on_click_navigate(home), screen=results)

style = """
title {
    font-size: 30px;
    font-weight: bold;
}
best {
    font-size: 32px;
}
outcome {
    font-size: 28px;
    font-weight: bold;
}
score {
    font-size: 32px;
}
"""

run(start_screen=home, theme=Theme(mode="dark"))
