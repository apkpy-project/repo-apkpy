from apkpy_lib import *

# Lanterns of Mossbrook: the app (ApkPy) around the game (ApkPyGame, game/main.py).
# Screens first (an ApkPy rule: a button that opens a screen declared below it does nothing).
home = Screen(id="home")
dialog = Screen(id="dialog")
pause_menu = Screen(id="pause_menu")
results = Screen(id="results")

# One table of words for the app AND the game (the game's t("key") reads it too).
translations({
    "en": {"title": "Lanterns of Mossbrook", "play": "Play", "continue": "Continue", "quit": "Quit to menu",
            "home": "Menu", "paused": "Paused", "results": "The lanterns are home!", "lanterns_hud": "Lanterns {lanterns}/3",
            "hint": "Tap to walk or to talk", "done_before": "You already brought the lanterns home.",
            "elder0": "Elder: The wind took our three lanterns. Could you find them?",
            "elder1": "Elder: One lantern! Two more are still out there.",
            "elder2": "Elder: Two! The last one must be near the pond or the woods.",
            "miller0": "Miller: The elder lives up the stairs. Lanterns? I saw a glow by the old house.",
            "miller1": "Miller: Another one should be south, near the mill road.",
            "miller2": "Miller: Look east, past the blue houses.",
            "miller3": "Miller: All three! Go and see the elder."},
    "pt": {"title": "Lanterns of Mossbrook", "play": "Jogar", "continue": "Continuar", "quit": "Sair para o menu",
            "home": "Menu", "paused": "Em pausa", "results": "As lanternas voltaram!", "lanterns_hud": "Lanternas {lanterns}/3",
            "hint": "Toca para andar ou para falar",
            "done_before": "Já levaste as lanternas para casa.",
            "elder0": "Ancião: O vento levou as nossas três lanternas. Encontras-nas?",
            "elder1": "Ancião: Uma lanterna! Ainda faltam duas.",
            "elder2": "Ancião: Duas! A última deve estar perto do lago ou do bosque.",
            "miller0": "Moleiro: O ancião mora lá em cima, depois das escadas. Lanternas? Vi uma luz junto à casa velha.",
            "miller1": "Moleiro: Há outra a sul, perto do caminho do moinho.",
            "miller2": "Moleiro: Procura a leste, depois das casas azuis.",
            "miller3": "Moleiro: As três! Vai ter com o ancião."},
}, default="en")

enable_game()

label(t("title"), id="title", screen=home)
home_note = label("", id="home_note", screen=home)
said = label("", id="said", screen=dialog)
label(t("paused"), id="paused", screen=pause_menu)
label(t("results"), id="results_title", screen=results)


def finished(ok, value):
    game_last_result()                      # handled here: on_resume needs not pick it up again
    if '"screen":"dialog"' in value:
        on_click_navigate(dialog)
    elif '"action":"open"' in value:
        on_click_navigate(pause_menu)
    elif '"action":"exit"' in value:
        on_click_navigate(results)


def play():
    game_play("town", "{}", on_result=finished)


def resume():
    game_resume(on_result=finished)


def home_shown():
    home_note.set_value(t("done_before") if game_get("mossbrook_done") == "1" else "")
    missed = game_last_result()             # an answer that came while this screen was gone
    if '"screen":"dialog"' in missed:
        on_click_navigate(dialog)
    elif '"action":"open"' in missed:
        on_click_navigate(pause_menu)


def dialog_shown():
    key = game_get("mossbrook_talk")             # t() takes a written key (an ApkPy rule): one per line
    if key == "elder0":
        said.set_value(t("elder0"))
    elif key == "elder1":
        said.set_value(t("elder1"))
    elif key == "elder2":
        said.set_value(t("elder2"))
    elif key == "miller0":
        said.set_value(t("miller0"))
    elif key == "miller1":
        said.set_value(t("miller1"))
    elif key == "miller2":
        said.set_value(t("miller2"))
    elif key == "miller3":
        said.set_value(t("miller3"))


lifecycle(home, on_resume=home_shown)
lifecycle(dialog, on_resume=dialog_shown)

button(t("play"), id="play", command=play, screen=home)
button(t("continue"), id="talk_continue", command=resume, screen=dialog)
button(t("continue"), id="continue", command=resume, screen=pause_menu)
button(t("quit"), id="quit", command=lambda: on_click_navigate(home), screen=pause_menu)
button(t("home"), id="results_home", command=lambda: on_click_navigate(home), screen=results)

style = """
title { font-size: 28px; font-weight: bold; }
said { font-size: 20px; }
"""

run(start_screen=home, theme=Theme(mode="dark"))
