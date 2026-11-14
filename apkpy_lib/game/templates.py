"""What `apkpy start NAME --game` and `apkpy game init` write: a small playable game, with its own art and sound."""
import json
import math
import os
import re
import shutil
import struct
import wave

# The genre templates: a whole short game of each kind (project_templates/<genre>).
GENRES = ("platformer", "shooter", "runner", "bricks", "adventure", "tap", "puzzle", "world")

MAIN_BLANK = '''"""{name}: the game, described for ApkPyGame.

This file is READ by the build (apkpy game build / play / run), never run:
write declarations with literal values, as in ApkPy's writehere.py.
"""
from apkpy_lib.game import *

game = Game("{name}", size=(360, 640), scale="fit", orientation="portrait", background="#0b0e1a")

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
                OnTap(exit_game({{"reason": "button"}})),
                children=[Entity("label", Text("Done", size=18, align="center", layer=6), at=(0, 6))]),
         at=(180, 600))
'''

WRITEHERE_BLANK = '''from apkpy_lib import *

# {name}: the app (ApkPy). The game itself is game/main.py (ApkPyGame).
home = Screen(id="home")
results = Screen(id="results")

{glue}
title = label("{name}", id="title", screen=home)
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
    game_play("main", "{{}}", on_result=finished)


lifecycle(home, on_resume=show_coins)

button("Play", command=play, screen=home)
button("Home", command=lambda: on_click_navigate(home), screen=results)

style = """
title {{ font-size: 28px; font-weight: bold; }}
coins {{ font-size: 20px; }}
"""

run(start_screen=home, theme=Theme(mode="dark"))
'''

MAIN_MENUS = """\"\"\"{name}: the game, described for ApkPyGame.

This file is READ by the build (apkpy game build / play / run), never run:
write declarations with literal values, as in ApkPy's writehere.py.
Words come from the app: t("key") is a key of translations({{...}}) in writehere.py.
\"\"\"
from apkpy_lib.game import *

game = Game("{name}", size=(360, 640), scale="fit", orientation="portrait", background="#0b0e1a")

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


@prefab
def button(label: str = "done", width: float = 140):
    return Entity("button",
                  Shape(size=(width, 44), color="#2a2f45", layer=5),
                  children=[Entity("label", Text(t(label), size=18, align="center", layer=6), at=(0, 6))])


# Back (phone) / Esc (PC) opens the app's pause screen; the game waits there (game_resume continues it).
main = game.scene("main", start=True, music=theme, music_volume=0.5, on_back=open_app("pause_menu"))
main.add(Entity("hint", Text(t("tap_hint"), size=20, align="center")), at=(180, 70))
main.add(coin(), at=(90, 200))
main.add(coin(tint="#5cd6ff", speed=-160), at=(270, 260))
main.add(coin(tint="#ff5c8a", speed=200), at=(180, 380), scale=1.4)
main.add(coin(tint="#8aff5c"), at=(110, 470), rotation=30)
main.add(coin(tint="#c45cff", speed=-90), at=(250, 520))
main.add(Entity("pause", Shape(shape="circle", radius=22, color="#2a2f45", layer=5),
                OnTap(open_app("pause_menu")),
                children=[Entity("bars", Text("II", size=18, align="center", layer=6), at=(0, 6))]),
         at=(326, 34))
main.add(Entity("done", OnTap(exit_game({{"reason": "done"}}), size=(140, 44)),
                children=[button("done")]),
         at=(180, 600))
"""

WRITEHERE_MENUS = """from apkpy_lib import *

# {name}: the app (ApkPy) around the game (ApkPyGame, game/main.py).
# Screens first (an ApkPy rule: a button that opens a screen declared below it does nothing).
home = Screen(id="home")
shop = Screen(id="shop")
pause_menu = Screen(id="pause_menu")
results = Screen(id="results")

# One table of words for the app AND the game (the game's t("key") reads it too).
translations({{
    "en": {{"title": "{name}", "play": "Play", "shop": "Shop", "coins": "Coins", "continue": "Continue",
            "quit": "Quit to menu", "home": "Menu", "paused": "Paused", "results": "Well played!",
            "buy": "Buy a golden star (5 coins)", "bought": "Golden star: yours", "poor": "Not enough coins",
            "tap_hint": "Tap the stars", "done": "Done"}},
    "pt": {{"title": "{name}", "play": "Jogar", "shop": "Loja", "coins": "Moedas", "continue": "Continuar",
            "quit": "Sair para o menu", "home": "Menu", "paused": "Em pausa", "results": "Muito bem!",
            "buy": "Comprar estrela dourada (5 moedas)", "bought": "Estrela dourada: tua",
            "poor": "Moedas insuficientes", "tap_hint": "Toca nas estrelas", "done": "Feito"}},
}}, default="en")

{glue}
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
    game_play("main", "{{}}", on_result=finished)


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

style = \"\"\"
title {{ font-size: 28px; font-weight: bold; }}
home_coins {{ font-size: 32px; }}
shop_coins {{ font-size: 32px; }}
results_coins {{ font-size: 32px; }}
\"\"\"

run(start_screen=home, theme=Theme(mode="dark"))
"""

TOML = '''[app]
name = "{name}"
application_id = "{app_id}"
version_name = "0.1.0"
version_code = 1
'''


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "", name.lower())
    return s if s and s[0].isalpha() else "game" + s


def write_assets(folder):
    """A star (PNG), a pop (WAV) and a short looping tune (WAV), made here: no files to license."""
    from PIL import Image, ImageDraw
    os.makedirs(folder, exist_ok=True)
    size = 48
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = size / 2
    pts = []
    for i in range(10):
        r = c - 1 if i % 2 == 0 else c * 0.45
        a = math.pi / 2 + i * math.pi / 5
        pts.append((c + r * math.cos(a), c - r * math.sin(a)))
    d.polygon(pts, fill=(255, 255, 255, 255))
    img.save(os.path.join(folder, "star.png"))

    rate = 22050

    def write(path, samples):
        with wave.open(path, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(rate)
            out.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32000)) for s in samples))

    pop = []
    n = int(rate * 0.15)
    for i in range(n):
        t = i / rate
        f = 900 + 900 * (i / n)
        pop.append(math.sin(2 * math.pi * f * t) * (1 - i / n) ** 2 * 0.8)
    write(os.path.join(folder, "pop.wav"), pop)

    notes = [261.63, 329.63, 392.0, 523.25, 392.0, 329.63, 293.66, 349.23]
    tune = []
    beat = int(rate * 0.25)
    for f in notes * 2:
        for i in range(beat):
            t = i / rate
            env = min(1, i / 200) * (1 - i / beat) ** 0.5
            tune.append((math.sin(2 * math.pi * f * t) + 0.3 * math.sin(4 * math.pi * f * t)) * env * 0.25)
    write(os.path.join(folder, "theme.wav"), tune)


def new_project(folder, name, app_id, glue_block, template="menus"):
    os.makedirs(os.path.join(folder, "game"))
    with open(os.path.join(folder, "apkpy.toml"), "w", encoding="utf-8") as fh:
        fh.write(TOML.format(name=name, app_id=app_id))
    with open(os.path.join(folder, "writehere.py"), "w", encoding="utf-8") as fh:
        app = WRITEHERE_MENUS if template == "menus" else WRITEHERE_BLANK
        fh.write(app.format(name=name, glue=glue_block))
    add_game(folder, name, template)


PROJECT_TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "project_templates")
# What a template folder may hold that is not the template: made by building it, testing it, or opening the Studio in it.
NOT_TEMPLATE = ("build", "__pycache__", "*.pyc", "*.apk", "*.aab", ".pytest_cache", ".studio_backups", ".studio_release.json")


def project_template(template):
    """The folder of a whole game to build on, inside this package: project_templates/<name> (monster-rpg: monster_rpg)."""
    return os.path.join(PROJECT_TEMPLATES, template.replace("-", "_"))


def call_it(folder, was, name):
    """A genre's game takes the project's name: in Game("..."), and in the app's words (its title screen)."""
    said = json.dumps(name, ensure_ascii=False)[1:-1]
    for rel in (os.path.join("game", "main.py"), "writehere.py"):
        path = os.path.join(folder, rel)
        with open(path, encoding="utf-8", newline="") as fh:
            text = fh.read()
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text.replace(was, said))


def copy_project_template(folder, name, app_id, template):
    """A whole game to build on, copied from project_templates/ (see project_template)."""
    source = project_template(template)
    shutil.copytree(source, folder, ignore=shutil.ignore_patterns(*NOT_TEMPLATE))
    toml = os.path.join(folder, "apkpy.toml")
    with open(toml, encoding="utf-8") as fh:
        text = fh.read()
    if template in GENRES:
        call_it(folder, re.search(r'name = "(.*)"', text).group(1), name)
    name = name.replace("\\", "\\\\").replace('"', '\\"')
    text = re.sub(r'name = ".*"', lambda m: 'name = "%s"' % name, text, count=1)
    text = re.sub(r'application_id = ".*"', 'application_id = "%s"' % app_id, text, count=1)
    with open(toml, "w", encoding="utf-8") as fh:
        fh.write(text)
    from .synth import make_recipe
    make_recipe(folder)                     # the genre templates' sounds: made here, not carried in the package


def add_game(folder, name, template="blank"):
    """game/main.py and assets/ (does not overwrite)."""
    os.makedirs(os.path.join(folder, "game"), exist_ok=True)
    main = os.path.join(folder, "game", "main.py")
    if not os.path.exists(main):
        with open(main, "w", encoding="utf-8") as fh:
            fh.write((MAIN_MENUS if template == "menus" else MAIN_BLANK).format(name=name))
    assets = os.path.join(folder, "assets")
    if not all(os.path.exists(os.path.join(assets, f)) for f in ("star.png", "pop.wav", "theme.wav")):
        write_assets(assets)
