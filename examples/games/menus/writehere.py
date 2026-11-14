from apkpy_lib import *

# menus: the app (ApkPy) around the game (ApkPyGame, game/main.py).
# Screens first (an ApkPy rule: a button that opens a screen declared below it does nothing).
home = Screen(id="home")
shop = Screen(id="shop")
pause_menu = Screen(id="pause_menu")
results = Screen(id="results")

# One table of words for the app AND the game (the game's t("key") reads it too).
translations({
    "en": {"title": "menus", "play": "Play", "shop": "Shop", "coins": "Coins", "continue": "Continue",
            "quit": "Quit to menu", "home": "Menu", "paused": "Paused", "results": "Well played!",
            "buy": "Buy a golden star (5 coins)", "bought": "Golden star: yours", "poor": "Not enough coins",
            "tap_hint": "Tap the stars", "done": "Done"},
    "pt": {"title": "menus", "play": "Jogar", "shop": "Loja", "coins": "Moedas", "continue": "Continuar",
            "quit": "Sair para o menu", "home": "Menu", "paused": "Em pausa", "results": "Muito bem!",
            "buy": "Comprar estrela dourada (5 moedas)", "bought": "Estrela dourada: tua",
            "poor": "Moedas insuficientes", "tap_hint": "Toca nas estrelas", "done": "Feito"},
}, default="en")

enable_game()

label(t("title"), id="title", screen=home)
label(t("coins"), id="coins_caption", screen=home)
home_coins = label("0", id="home_coins", screen=home)
label(t("shop"), id="shop_title", screen=shop)
shop_coins = label("0", id="shop_coins", screen=shop)
shop_info = label("", id="shop_info", screen=shop)
label(t("paused"), id="paused", screen=pause_menu)
label(t("results"), id="results_title", screen=results)
results_coins = label("0", id="results_coins", screen=results)


def coins():
    value = game_get("coins")
    if value == "":
        return "0"
    return value


def finished(ok, value):
    game_last_result()                      # handled here: on_resume needs not pick it up again
    if '"action":"open"' in value:
        on_click_navigate(pause_menu)
    elif '"action":"exit"' in value:
        results_coins.set_value(coins())
        on_click_navigate(results)


def play():
    game_play("main", "{}", on_result=finished)


def resume():
    game_resume(on_result=finished)


def home_shown():
    home_coins.set_value(coins())
    missed = game_last_result()             # an answer that came while this screen was gone
    if '"action":"open"' in missed:
        on_click_navigate(pause_menu)


def shop_shown():
    shop_coins.set_value(coins())


def buy():
    have = int(coins())
    if have < 5:
        shop_info.set_value(t("poor"))
        return
    game_set("coins", str(have - 5))
    game_set("golden", "1")
    shop_coins.set_value(coins())
    shop_info.set_value(t("bought"))


lifecycle(home, on_resume=home_shown)
lifecycle(shop, on_resume=shop_shown)

button(t("play"), id="play", command=play, screen=home)
button(t("shop"), id="open_shop", command=lambda: on_click_navigate(shop), screen=home)
button(t("buy"), id="buy", command=buy, screen=shop)
button(t("home"), id="shop_home", command=lambda: on_click_navigate(home), screen=shop)
button(t("continue"), id="continue", command=resume, screen=pause_menu)
button(t("quit"), id="quit", command=lambda: on_click_navigate(home), screen=pause_menu)
button(t("home"), id="results_home", command=lambda: on_click_navigate(home), screen=results)

style = """
title { font-size: 28px; font-weight: bold; }
home_coins { font-size: 32px; }
shop_coins { font-size: 32px; }
results_coins { font-size: 32px; }
"""

run(start_screen=home, theme=Theme(mode="dark"))
