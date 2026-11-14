"""Writes what the eight genre templates make rather than write: the app around each game (writehere.py),
apkpy.toml, the pictures, the levels, and the recipe of its sounds (sounds.json: `apkpy start` makes the WAV files
from it with the Studio's synthesiser, so the package carries no sound files). Each game/main.py and README.md are
written by hand, next to what this makes.

    python tools/game/make_starters.py [genre ...]

Every picture here is drawn here, from numbers: nothing is copied from another game.
"""
import json
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # ApkPy's repository
sys.path.insert(0, ROOT)
from apkpy_lib.game.studio.levels import dump  # noqa: E402

TEMPLATES = os.path.join(ROOT, "apkpy_lib", "game", "project_templates")
GENRES = ("platformer", "shooter", "runner", "bricks", "adventure", "tap", "puzzle", "world")


# ── the app around every game ───────────────────────────────────────────

APP = '''from apkpy_lib import *

# @TITLE@: the app (ApkPy) around the game (game/main.py): a start screen, the pause screen the game opens with
# Back, and the results. Screens first (an ApkPy rule: a button that opens a screen declared below it does nothing).
home = Screen(id="home")
pause_menu = Screen(id="pause_menu")
results = Screen(id="results")

# One table of words for the app AND the game: the game's t("key") reads it too.
translations({
    "en": {@EN@},
    "pt": {@PT@},
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
'''

COMMON = {
    "en": {"play": "Play", "best": "Best", "continue": "Continue", "quit": "Quit to menu", "paused": "Paused",
           "won": "You won!", "lost": "Try again", "score": "Score", "again": "Play again", "home": "Menu"},
    "pt": {"play": "Jogar", "best": "Recorde", "continue": "Continuar", "quit": "Sair para o menu",
           "paused": "Em pausa", "won": "Ganhaste!", "lost": "Tenta outra vez", "score": "Pontos",
           "again": "Jogar outra vez", "home": "Menu"},
}

# title, how to play (home screen), and the game's own words: en, pt
WORDS = {
    "platformer": {"title": ("Hop Hills", "Hop Hills"),
                   "how": ("Run and jump to the flag. Jump on the slimes!", "Corre e salta até à bandeira. Salta em cima das gosmas!"),
                   "hud": ("Coins {coins}   Lives {lives}", "Moedas {coins}   Vidas {lives}")},
    "shooter": {"title": ("Star Guard", "Star Guard"),
                "how": ("Slide to move: the ship fires by itself.", "Arrasta para mover: a nave dispara sozinha."),
                "hud": ("Lives {lives}", "Vidas {lives}"), "wave2": ("Wave 2", "Vaga 2")},
    "runner": {"title": ("Rooftop Run", "Rooftop Run"),
               "how": ("Tap to hop over the crates. Hold to jump high for the coins, but not into a bird!",
                       "Toca para saltar as caixas. Mantém para saltar alto às moedas, mas não contra um pássaro!"),
               "hud": ("{distance} m   Coins {coins}   Lives {lives}", "{distance} m   Moedas {coins}   Vidas {lives}"),
               "faster": ("Faster!", "Mais rápido!")},
    "bricks": {"title": ("Brickfall", "Brickfall"),
               "how": ("Slide the paddle and break every brick. Its ends send the ball to the sides: aim!",
                       "Arrasta a raquete e parte todos os tijolos. As pontas mandam a bola para os lados: aponta!"),
               "hud": ("Score {score}   Lives {lives}", "Pontos {score}   Vidas {lives}")},
    "adventure": {"title": ("Keys of the Keep", "Keys of the Keep"),
                  "how": ("Find the keys, open the doors, take the stairs.", "Encontra as chaves, abre as portas, desce as escadas."),
                  "hud": ("Keys {keys}   Gems {gems}   Lives {lives}", "Chaves {keys}   Gemas {gems}   Vidas {lives}")},
    "tap": {"title": ("Quick Pop", "Quick Pop"),
            "how": ("Tap the stars before they go. Not the bombs!", "Toca nas estrelas antes que fujam. Nas bombas não!"),
            "hud": ("{score}", "{score}"), "clock": ("Time {time}   Missed {missed}/8", "Tempo {time}   Falhadas {missed}/8")},
    "puzzle": {"title": ("Lights Off", "Lights Off"),
               "how": ("A tap turns a light and its neighbours. Turn them all off.", "Um toque muda uma luz e as vizinhas. Apaga todas."),
               "hud": ("Level {level}   Moves {moves}", "Nível {level}   Jogadas {moves}")},
    "world": {"title": ("Gem Valley", "Gem Valley"),
              "how": ("Walk the valley and find the four lanterns.", "Anda pelo vale e encontra as quatro lanternas."),
              "hud": ("Lanterns {lanterns}/4", "Lanternas {lanterns}/4"),
              "hint": ("Tap a place to walk there", "Toca num sítio para andar até lá")},
}

def words_text(genre, lang):
    out = {"title": WORDS[genre]["title"][0 if lang == "en" else 1], "how": WORDS[genre]["how"][0 if lang == "en" else 1]}
    out.update(COMMON[lang])
    for key, pair in WORDS[genre].items():
        if key not in ("title", "how"):
            out[key] = pair[0 if lang == "en" else 1]
    lines, line = [], ""
    for k, v in out.items():
        part = "%s: %s" % (json.dumps(k), json.dumps(v, ensure_ascii=False))
        if line and len(line) + len(part) + 2 > 100:
            lines.append(line + ",")
            line = part
        else:
            line = part if not line else line + ", " + part
    lines.append(line)
    return ("\n" + " " * 11).join(lines)


def write_app(folder, genre):
    title = WORDS[genre]["title"][0]
    text = APP.replace("@TITLE@", title).replace("@EN@", words_text(genre, "en")).replace("@PT@", words_text(genre, "pt"))
    with open(os.path.join(folder, "writehere.py"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    with open(os.path.join(folder, "apkpy.toml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write('[app]\nname = "%s"\napplication_id = "com.example.%s"\nversion_name = "0.1.0"\nversion_code = 1\n'
                 % (title, title.lower().replace(" ", "")))


# ── pictures, drawn here ────────────────────────────────────────────────


def sprite(rows, colours, scale=1):
    """A picture from rows of letters: each letter is a colour of colours, '.' is clear."""
    h, w = len(rows), max(len(r) for r in rows)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                img.putpixel((x, y), colours[ch])
    return img.resize((w * scale, h * scale), Image.NEAREST) if scale > 1 else img


def strip(frames):
    w, h = frames[0].size
    out = Image.new("RGBA", (w * len(frames), h), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        out.paste(f, (i * w, 0))
    return out


def rgb(text):
    return tuple(int(text[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


PEOPLE = {"k": rgb("#1b1e26"), "s": rgb("#f2c09a"), "h": rgb("#6b3e26"), "r": rgb("#e0503c"), "b": rgb("#3a6fd8"),
          "d": rgb("#25407e"), "w": rgb("#ffffff"), "y": rgb("#ffd45c"), "g": rgb("#58b848"), "G": rgb("#2f7a35"),
          "o": rgb("#e08a2c"), "n": rgb("#8a5a32"), "N": rgb("#5e3a1e"), "e": rgb("#9aa3b5"), "E": rgb("#5b6378"),
          "p": rgb("#c45cff"), "c": rgb("#5cd6ff"), "R": rgb("#9c2a2a"), "a": rgb("#cfd6e4")}

HERO_TOP = ["......hhhh......",
            ".....hhhhhh.....",
            ".....hsssss.....",
            ".....sskssk.....",
            ".....ssssss.....",
            "......ssss......",
            ".....rrrrrr.....",
            "....srrrrrrs....",
            "....srrrrrrs....",
            ".....bbbbbb....."]
RUN_LEGS = (["....bb...bb.....", "...bb.....bb....", "...kk......kk...", "................", "................", "................"],
            [".....bb.bb......", ".....bb.bb......", "....kk..kk......", "................", "................", "................"],
            ["......bbbb......", "......bb.bb.....", "......kk..kk....", "................", "................", "................"],
            [".....bb.bb......", "....bb...bb.....", "....kk....kk....", "................", "................", "................"])


def runner_sheet():
    """6 frames of 16x16: run (0-3), jump (4), fall (5)."""
    frames = []
    for legs in RUN_LEGS:
        frames.append(sprite(HERO_TOP + legs, PEOPLE))
    frames.append(sprite(HERO_TOP[:7] + ["...srrrrrrrs....", "....rrrrrr......", ".....bbbbbb.....", "....bb....bb....",
                                         "...kk......kk...", "................", "................", "................",
                                         "................"], PEOPLE))
    frames.append(sprite(HERO_TOP + [".....bb..bb.....", ".....bb..bb.....", ".....kk..kk.....", "................",
                                     "................", "................"], PEOPLE))
    return strip(frames)


def hero_top_down():
    """2 frames of 16x16, seen from above at an angle: an adventurer with a green hood."""
    body = ["......GGGG......", ".....GggggG.....", "....GgssssgG....", "....gskssksg....", "....gssssssg....",
            ".....gssssg.....", "....nnGGGGnn....", "...snGggggGns...", "...s.GggggG.s...", ".....GggggG.....",
            ".....nnnnnn....."]
    a = sprite(body + [".....dd..dd.....", ".....dd..dd.....", ".....kk..kk.....", "................", "................"], PEOPLE)
    b = sprite(body + [".....dd..dd.....", "....dd....dd....", "....kk....kk....", "................", "................"], PEOPLE)
    return strip([a, b])


def crate():
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 15, 15), fill=rgb("#b07a42"), outline=rgb("#5e3a1e"))
    d.rectangle((2, 2, 13, 13), outline=rgb("#8a5a32"))
    d.line((2, 2, 13, 13), fill=rgb("#8a5a32"), width=2)
    d.line((13, 2, 2, 13), fill=rgb("#8a5a32"), width=2)
    return img


def bird():
    up = ["k.............k.", "kk...........kk.", ".kk.........kk..", "..kkk.ooo..kkk..", "....kkoooookk...",
          ".....ooookoo....", "......ooooooyy..", ".......oooo.....", "................", "................",
          "................", "................"]
    down = ["................", "................", "................", "......ooo.......", ".....oooooo.....",
            "..kkkoooookoo...", ".kk...ooooooyy..", "kk.....oooo.kk..", "k...........kk..", "..............k.",
            "................", "................"]
    return strip([sprite(up, PEOPLE), sprite(down, PEOPLE)])


def coin_sheet():
    shapes = [(1, 11), (2, 10), (4, 8), (2, 10)]
    frames = []
    for left, right in shapes:
        img = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((left, 0, right, 11), fill=rgb("#ffd45c"), outline=rgb("#c08a1c"))
        if right - left > 4:
            d.line(((left + right) // 2, 3, (left + right) // 2, 8), fill=rgb("#fff0a8"))
        frames.append(img)
    return strip(frames)


def cloud():
    img = Image.new("RGBA", (40, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for box in ((2, 6, 18, 15), (10, 1, 28, 15), (22, 5, 38, 15)):
        d.ellipse(box, fill=(255, 255, 255, 220))
    return img


def ship():
    rows = ["...............aa...............", "..............aaaa..............", "..............acca..............",
            ".............accca a.............".replace(" ", "a"), ".............acccca.............",
            "............aaccccaa............", "............aaaaaaaa............", "...........aeeaaaaeea...........",
            "..........aeeeaaaaeeea..........", ".........aeeeeaaaaeeeea.........", "........aeeeeeaaaaeeeeea........",
            ".......aaeeeeeaaaaeeeeeaa.......", "......aaaeeeeaaaaaaeeeeaaa......", ".....rraaaeeaaaaaaaaeeaaarr.....",
            "....rrr.aaaaaaaaaaaaaaaa.rrr....", "....rr...aaaaaaaaaaaaaa...rr....", "..........eeee....eeee..........",
            "..........oyyo....oyyo..........", "...........oo......oo...........", "................................"]
    rows = [r[:32].ljust(32, ".") for r in rows]
    return sprite(rows, PEOPLE)


def rock(seed, size=34):
    import random
    rng = random.Random(seed)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    import math
    points = []
    for i in range(10):
        angle = i / 10 * 2 * math.pi
        r = size / 2 - 1 - rng.uniform(0, size / 6)
        points.append((size / 2 + math.cos(angle) * r, size / 2 + math.sin(angle) * r))
    d.polygon(points, fill=rgb("#8a7a6a"), outline=rgb("#4e4338"))
    for i in range(4):
        x, y = rng.uniform(8, size - 10), rng.uniform(8, size - 10)
        d.ellipse((x, y, x + 5, y + 4), fill=rgb("#6e6052"))
    return img


def saucer():
    img = Image.new("RGBA", (32, 18), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((9, 1, 23, 12), fill=rgb("#5cd6ff"), outline=rgb("#2a7a9a"))
    d.ellipse((1, 7, 31, 16), fill=rgb("#9aa3b5"), outline=rgb("#4e5566"))
    for x in (7, 13, 19, 25):
        d.point((x, 11), fill=rgb("#ffd45c"))
    return img


def heart():
    rows = [".rr...rr.", "rrrr.rrrr", "rrrrrrrrr", "rrrrrrrrr", ".rrrrrrr.", "..rrrrr..", "...rrr...", "....r...."]
    return sprite(rows, {"r": rgb("#ff5c8a")}, scale=2)


def bomb():
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((3, 7, 28, 31), fill=rgb("#2a2f45"), outline=rgb("#11131c"))
    d.ellipse((8, 11, 13, 16), fill=rgb("#5b6378"))
    d.rectangle((13, 4, 18, 8), fill=rgb("#5b6378"))
    d.line((16, 4, 20, 0), fill=rgb("#c08a1c"), width=2)
    d.ellipse((19, 0, 24, 5), fill=rgb("#ff5c3a"))
    return img


def star():
    import math
    size = 40
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pts = []
    for i in range(10):
        r = size / 2 - 1 if i % 2 == 0 else size * 0.22
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((size / 2 + math.cos(a) * r, size / 2 + math.sin(a) * r))
    d.polygon(pts, fill=(255, 255, 255, 255), outline=(200, 200, 200, 255))
    return img


def adventure_tiles():
    """8 tiles of 16: floor, grass, wall, water, wood, rug, wall top, dark."""
    img = Image.new("RGBA", (16 * 8, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def tile(n, base, dots=None, lines=None):
        x = n * 16
        d.rectangle((x, 0, x + 15, 15), fill=rgb(base))
        for (px_, py_) in dots or ():
            d.point((x + px_, py_), fill=rgb(dots_colour[n]))
        for (a, b, c, e, col) in lines or ():
            d.line((x + a, b, x + c, e), fill=rgb(col))
    dots_colour = {0: "#8d8f99", 1: "#3f8f3a", 3: "#9fd0ff"}
    tile(0, "#a3a5ae", dots=[(3, 4), (11, 2), (7, 9), (13, 12), (2, 13)], lines=[(0, 15, 15, 15, "#8d8f99"), (15, 0, 15, 15, "#8d8f99")])
    tile(1, "#58a848", dots=[(2, 3), (9, 5), (5, 11), (13, 9), (11, 14)])
    tile(2, "#6a5248", lines=[(0, 4, 15, 4, "#4a3832"), (0, 9, 15, 9, "#4a3832"), (0, 14, 15, 14, "#4a3832"),
                              (5, 0, 5, 4, "#4a3832"), (11, 4, 11, 9, "#4a3832"), (4, 9, 4, 14, "#4a3832")])
    tile(3, "#3c78c8", dots=[(3, 4), (10, 7), (5, 12)], lines=[(2, 9, 6, 9, "#9fd0ff"), (9, 3, 13, 3, "#9fd0ff")])
    tile(4, "#a8743c", lines=[(0, 5, 15, 5, "#7e5428"), (0, 10, 15, 10, "#7e5428"), (8, 0, 8, 5, "#7e5428"), (3, 5, 3, 10, "#7e5428")])
    tile(5, "#9c2a2a", lines=[(1, 1, 14, 1, "#ffd45c"), (1, 14, 14, 14, "#ffd45c"), (1, 1, 1, 14, "#ffd45c"), (14, 1, 14, 14, "#ffd45c")])
    tile(6, "#8a7064", lines=[(0, 12, 15, 12, "#4a3832"), (0, 15, 15, 15, "#4a3832")])
    tile(7, "#1b1e26")
    return img


def key_picture():
    rows = ["................", "................", "....yyy.........", "...yy.yy........", "...y...y........",
            "...yy.yy........", "....yyyyyyyyyy..", "............yy..", "..........yy.y..", "..........y.....",
            "................", "................", "................", "................", "................",
            "................"]
    return sprite(rows, PEOPLE)


def door_picture():
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 15, 15), fill=rgb("#7e5428"), outline=rgb("#3e2a14"))
    for x in (4, 8, 12):
        d.line((x, 1, x, 14), fill=rgb("#5e3a1e"))
    d.rectangle((6, 6, 9, 10), fill=rgb("#c08a1c"))
    d.point((7, 8), fill=rgb("#1b1e26"))
    return img


def chest_picture():
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((1, 4, 14, 14), fill=rgb("#a8743c"), outline=rgb("#5e3a1e"))
    d.rectangle((1, 4, 14, 7), fill=rgb("#c48a4a"), outline=rgb("#5e3a1e"))
    d.rectangle((6, 6, 9, 9), fill=rgb("#ffd45c"))
    return img


def slime_sheet():
    a = ["................", "................", "................", "................", "................",
         "................", "......gggg......", "....gggggggg....", "...ggwkggwkgg...", "...ggkkggkkgg...",
         "..gggggggggggg..", "..gggggggggggg..", "..GgggggggggggG.", "...GGGGGGGGGGG..", "................",
         "................"]
    b = ["................", "................", "................", "................", "................",
         "................", "................", "......gggg......", "....gggggggg....", "...ggwkggwkgg...",
         "..gggkkggkkgggg.", ".gggggggggggggg.", ".GgggggggggggggG", "..GGGGGGGGGGGGG.", "................",
         "................"]
    return strip([sprite(a, PEOPLE), sprite(b, PEOPLE)])


def stairs_picture():
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 15, 15), fill=rgb("#1b1e26"))
    for i, y in enumerate((2, 6, 10)):
        d.rectangle((0, y, 15 - i * 2, y + 3), fill=rgb("#8d8f99"), outline=rgb("#5b6378"))
    return img


def gem_picture():
    rows = ["...pppp...", "..pPPPPp..", ".pPPwPPPp.", "pPPPwPPPPp", ".pPPPPPPp.", "..pPPPPp..", "...pPPp...", "....pp...."]
    return sprite(rows, {"p": rgb("#7a2ab8"), "P": rgb("#c45cff"), "w": rgb("#f0d8ff")})


def pad(kind):
    img = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((1, 1, 38, 38), fill=(255, 255, 255, 70), outline=(255, 255, 255, 160), width=2)
    arrow = {"left": [(25, 10), (12, 20), (25, 30)], "right": [(15, 10), (28, 20), (15, 30)],
             "jump": [(10, 26), (20, 12), (30, 26)]}[kind]
    d.polygon(arrow, fill=(255, 255, 255, 220))
    return img


def platform_tiles():
    """8 tiles of 16: grass top, earth, brick, stone; then (decor) tuft, flower, bush, sign."""
    img = Image.new("RGBA", (16 * 8, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 15, 15), fill=rgb("#9a6a3c"))
    d.rectangle((0, 0, 15, 4), fill=rgb("#5cb848"))
    for x in range(0, 16, 3):
        d.point((x, 5), fill=rgb("#3f8f3a"))
    d.rectangle((16, 0, 31, 15), fill=rgb("#9a6a3c"))
    for (x, y) in ((19, 3), (26, 6), (22, 11), (29, 13), (17, 9)):
        d.point((x, y), fill=rgb("#7a4e28"))
    d.rectangle((32, 0, 47, 15), fill=rgb("#c0583c"))
    for y in (0, 5, 10, 15):
        d.line((32, y, 47, y), fill=rgb("#7e3424"))
    for x, y0 in ((36, 0), (44, 0), (40, 5), (36, 10), (44, 10)):
        d.line((x, y0, x, y0 + 5), fill=rgb("#7e3424"))
    d.rectangle((48, 0, 63, 15), fill=rgb("#8d929e"), outline=rgb("#5b6378"))
    d.rectangle((51, 3, 60, 12), outline=rgb("#a9adb8"))
    for x in (66, 70, 74, 77):
        d.line((x, 15, x + 1, 9), fill=rgb("#3f8f3a"))
    d.line((88, 15, 88, 9), fill=rgb("#3f8f3a"))
    d.ellipse((85, 5, 91, 10), fill=rgb("#ffd45c"))
    d.point((88, 7), fill=rgb("#e0503c"))
    d.ellipse((97, 6, 110, 15), fill=rgb("#3f8f3a"))
    d.ellipse((100, 4, 108, 12), fill=rgb("#58a848"))
    d.rectangle((119, 9, 120, 15), fill=rgb("#7a4e28"))
    d.rectangle((114, 4, 125, 9), fill=rgb("#a8743c"), outline=rgb("#5e3a1e"))
    return img


def flag_picture():
    img = Image.new("RGBA", (16, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((3, 2, 4, 31), fill=rgb("#cfd6e4"))
    d.polygon([(5, 3), (15, 7), (5, 11)], fill=rgb("#e0503c"))
    d.ellipse((2, 0, 5, 3), fill=rgb("#ffd45c"))
    return img


def hopper_sheet():
    """The platformer's hero: 8 frames of 16: idle 0-1, run 2-5, jump 6, fall 7."""
    head = ["................", ".....cccccc.....", "....cccccccc....", "....ssssssss....", "....sskssks.....",
            "....ssssssss....", ".....ssssss.....", "....ccccccc.....", "...sccccccccs...", "...sccccccccs...",
            "....ccccccc....."]
    legs = {"stand": ["....dd...dd.....", "....dd...dd.....", "....kk...kk.....", "................", "................"],
            "a": ["...dd.....dd....", "..dd.......dd...", "..kk........kk..", "................", "................"],
            "b": ["....dd..dd......", "....dd..dd......", "...kk..kk.......", "................", "................"],
            "c": [".....dddd.......", ".....dd.dd......", ".....kk..kk.....", "................", "................"],
            "jump": ["...dd....dd.....", "..dd......dd....", "..kk.......kk...", "................", "................"],
            "fall": ["....dd..dd......", "....dd..dd......", "....kk..kk......", "................", "................"]}
    blink = head[:4] + ["....ssssssss...."] + head[5:]
    frames = [sprite(head + legs["stand"], PEOPLE), sprite(blink + legs["stand"], PEOPLE)]
    frames += [sprite(head + legs[k], PEOPLE) for k in ("a", "b", "c", "b")]
    frames += [sprite(head + legs["jump"], PEOPLE), sprite(head + legs["fall"], PEOPLE)]
    return strip(frames)


def world_tiles():
    """9 tiles of 16 for the 2.5D valley: grass, grass 2, path, stone, earth, flowers, water, wood, hedge."""
    img = Image.new("RGBA", (16 * 9, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    colours = ("#5aa84a", "#66b452", "#d8b878", "#9a9ca6", "#8a6a44", "#5aa84a", "#3c78c8", "#a8743c", "#2f7a35")
    for n, c in enumerate(colours):
        d.rectangle((n * 16, 0, n * 16 + 15, 15), fill=rgb(c))
    for (x, y) in ((3, 4), (10, 9), (6, 13), (13, 2)):
        d.point((x, y), fill=rgb("#3f8f3a"))
        d.point((16 + x, y), fill=rgb("#4e9a3e"))
        d.point((32 + x, y), fill=rgb("#b8985a"))
    for (x, y, col) in ((83, 4, "#ffd45c"), (88, 10, "#ff5c8a"), (92, 5, "#ffffff"), (85, 12, "#c45cff")):
        d.ellipse((x - 1, y - 1, x + 1, y + 1), fill=rgb(col))
    d.line((98, 6, 104, 6), fill=rgb("#9fd0ff"))
    d.line((102, 11, 108, 11), fill=rgb("#9fd0ff"))
    for y in (4, 9, 14):
        d.line((112, y, 127, y), fill=rgb("#7e5428"))
    for (x, y) in ((131, 4), (137, 9), (141, 3), (134, 12)):
        d.ellipse((x - 2, y - 2, x + 2, y + 2), fill=rgb("#4a9a44"))
    return img


def villager_sheet(cloth, hair):
    """3 walking frames x 4 directions (down, left, up, right), 16x24 each: a Billboard sheet."""
    colours = dict(PEOPLE, C=rgb(cloth), H=rgb(hair))
    out = Image.new("RGBA", (48, 96), (0, 0, 0, 0))
    for row, facing in enumerate(("down", "left", "up", "right")):
        for col in range(3):
            face = {"down": "..HsssssH..", "left": "..HsksssH..", "up": "..HHHHHHH..", "right": "..HsssksH.."}[facing]
            eyes = {"down": "..HskssksH.", "left": "..Hssssss..", "up": "..HHHHHHH..", "right": "...ssssssH."}[facing]
            step = ("...CC..CC..", "..CC....CC.", "...CC.CC...")[col]
            feet = ("...kk..kk..", "..kk....kk.", "...kk.kk...")[col]
            rows = ["...........", "...HHHHH...", "..HHHHHHH..", face, eyes, "...sssss...", "....sss....",
                    "...CCCCC...", "..CCCCCCC..", ".sCCCCCCCs.", ".sCCCCCCCs.", "..CCCCCCC..", "..CCCCCCC..",
                    "...ddddd...", "...dd.dd...", step, step, feet, "...........", "...........", "...........",
                    "...........", "...........", "..........."]
            img = sprite([r.ljust(16, ".")[:16] for r in rows], colours)
            out.paste(img, (col * 16 + 0, row * 24))
    return out


def lantern_picture():
    rows = ["....kk....", "...k..k...", "..kkkkkk..", ".kyyyyyyk.", ".kyowwoyk.", ".kyowwoyk.", ".kyyoooyk.",
            ".kyyyyyyk.", "..kkkkkk..", "...kkkk..."]
    return sprite(rows, PEOPLE)


def tree_picture():
    img = Image.new("RGBA", (28, 44), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((12, 28, 15, 43), fill=rgb("#6b4a2c"))
    for box, col in (((2, 10, 25, 32), "#2f7a35"), ((5, 2, 22, 24), "#3f9a44"), ((8, 6, 16, 14), "#58b858")):
        d.ellipse(box, fill=rgb(col))
    return img


def roof_picture(colour):
    img = Image.new("RGBA", (32, 32), rgb(colour))
    d = ImageDraw.Draw(img)
    for y in range(0, 32, 6):
        d.line((0, y, 31, y), fill=tuple(max(0, c - 50) for c in rgb(colour)[:3]) + (255,))
    return img


def wall_picture():
    img = Image.new("RGBA", (32, 24), rgb("#e8dcc4"))
    d = ImageDraw.Draw(img)
    d.rectangle((12, 10, 19, 23), fill=rgb("#7e5428"))
    d.rectangle((3, 6, 8, 11), fill=rgb("#5cd6ff"), outline=rgb("#6b4a2c"))
    d.rectangle((23, 6, 28, 11), fill=rgb("#5cd6ff"), outline=rgb("#6b4a2c"))
    return img


def save(img, folder, name):
    os.makedirs(os.path.join(folder, "assets"), exist_ok=True)
    img.save(os.path.join(folder, "assets", name), optimize=True)


# ── levels ──────────────────────────────────────────────────────────────


def tileset_entry(image_rel_from_level, image, tile, extra=None):
    w, h = image.size
    entry = {"firstgid": 1, "name": "tiles", "image": image_rel_from_level, "imagewidth": w, "imageheight": h,
             "tilewidth": tile, "tileheight": tile, "columns": w // tile, "tilecount": (w // tile) * (h // tile),
             "margin": 0, "spacing": 0}
    if extra:
        entry.update(extra)
    return entry


def tmj(cols, rows, tile, tileset, layers, objects):
    out_layers = []
    for n, (name, data, props) in enumerate(layers, 1):
        layer = {"id": n, "type": "tilelayer", "name": name, "width": cols, "height": rows, "data": data,
                 "visible": True, "opacity": 1, "x": 0, "y": 0}
        if props:
            layer["properties"] = props
        out_layers.append(layer)
    objs = []
    for i, (kind, x, y, w, h) in enumerate(objects, 1):
        objs.append({"id": i, "name": "", "class": kind, "x": x, "y": y, "width": w, "height": h, "rotation": 0,
                     "visible": True})
    out_layers.append({"id": len(layers) + 1, "type": "objectgroup", "name": "things", "objects": objs, "visible": True,
                       "opacity": 1, "x": 0, "y": 0})
    return {"type": "map", "version": "1.10", "orientation": "orthogonal", "renderorder": "right-down",
            "width": cols, "height": rows, "tilewidth": tile, "tileheight": tile, "infinite": False,
            "nextlayerid": len(layers) + 2, "nextobjectid": len(objs) + 1, "tilesets": [tileset], "layers": out_layers}


SOLID = [{"name": "solid", "type": "bool", "value": True}]


def ascii_level(rows, tiles, decor, objects, tile=16, sizes=None):
    """Rows of letters: tiles (letter: gid) on the solid layer, decor (letter: gid) on the decor layer, objects
    (letter: class) placed in their cell (sizes: class -> (w, h), standing on the cell's bottom)."""
    cols, n = max(len(r) for r in rows), len(rows)
    ground, deco, things = [0] * (cols * n), [0] * (cols * n), []
    for y, row in enumerate(rows):
        for x, ch in enumerate(row.ljust(cols, ".")):
            if ch in tiles:
                ground[y * cols + x] = tiles[ch]
            elif ch in decor:
                deco[y * cols + x] = decor[ch]
            elif ch in objects:
                w, h = (sizes or {}).get(objects[ch], (tile, tile))
                things.append((objects[ch], x * tile + (tile - w) // 2, (y + 1) * tile - h, w, h))
    return cols, n, ground, deco, things


def write_level(folder, name, data):
    os.makedirs(os.path.join(folder, "levels"), exist_ok=True)
    with open(os.path.join(folder, "levels", name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dump(data) + "\n")


PLATFORM_1 = [
    "................................................",
    "................................................",
    "................................................",
    "................................................",
    "................................................",
    "......................c.c.c.....................",
    ".....................BBBBBBB.............c......",
    "..........c.c...........................BBB.....",
    ".........BBBBB.................c..c.............",
    "..............................SSSSSS..........F.",
    "..P....*.\"..s....\"...b..s.....\".........\"..b....",
    "==============..============..=======...========",
    "##############..############..#######...########",
    "##############..############..#######...########",
    "................................................"]

PLATFORM_2 = [
    "........................................................",
    "........................................................",
    "........................................................",
    "..............c.c.c.....................................",
    ".............BBBBBBB...............c.c..................",
    "..................................BBBBB.......c.c.c.....",
    "........c.c..........c.....................BBBBBBB......",
    ".......BBBB.........BBB..c.c............................",
    "........................SSSSS.......................F...",
    "..................................................SSSS..",
    "..P.\"..s....b...s..\"....s..........\"..SS...s..*..SSSSS..",
    "=========...=========...=======...=======..==========...",
    "#########...#########...#######...#######..##########...",
    "#########...#########...#######...#######..##########...",
    "........................................................"]


def make_platformer(folder):
    tiles = platform_tiles()
    save(tiles, folder, "tiles.png")
    save(hopper_sheet(), folder, "hero.png")
    save(slime_sheet(), folder, "slime.png")
    save(coin_sheet(), folder, "coin.png")
    save(flag_picture(), folder, "flag.png")
    for kind in ("left", "right", "jump"):
        save(pad(kind), folder, kind + ".png")
    for name, rows in (("level1.tmj", PLATFORM_1), ("level2.tmj", PLATFORM_2)):
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                assert ch not in "sP" or rows[y + 1][x] in "=#BS", "%s: nothing under the %s at %d, %d" % (name, ch, x, y)
        cols, n, ground, deco, things = ascii_level(rows, {"=": 1, "#": 2, "B": 3, "S": 4}, {'"': 5, "*": 6, "b": 7},
                                                    {"P": "player", "c": "coin", "s": "slime", "F": "flag"},
                                                    sizes={"flag": (16, 32)})
        write_level(folder, name, tmj(cols, n, 16, tileset_entry("../assets/tiles.png", tiles, 16),
                                      [("ground", ground, SOLID), ("decor", deco, None)], things))
    return {"assets/jump.wav": {"sound": "jump"}, "assets/coin.wav": {"sound": "coin"},
            "assets/stomp.wav": {"sound": "hit", "seed": 2}, "assets/hurt.wav": {"sound": "hit", "pitch": 0.7},
            "assets/win.wav": {"sound": "win"}, "assets/theme.wav": {"music": "happy", "seed": 1}}


def make_shooter(folder):
    save(ship(), folder, "ship.png")
    save(rock(1), folder, "rock1.png")
    save(rock(7, 26), folder, "rock2.png")
    save(saucer(), folder, "saucer.png")
    save(heart(), folder, "heart.png")
    return {"assets/shoot.wav": {"sound": "laser"}, "assets/boom.wav": {"sound": "explosion"},
            "assets/hit.wav": {"sound": "hit"}, "assets/life.wav": {"sound": "power up"},
            "assets/theme.wav": {"music": "adventure", "seed": 3}}


def make_runner(folder):
    save(runner_sheet(), folder, "runner.png")
    save(crate(), folder, "crate.png")
    save(bird(), folder, "bird.png")
    save(coin_sheet(), folder, "coin.png")
    save(cloud(), folder, "cloud.png")
    return {"assets/jump.wav": {"sound": "jump", "seed": 4}, "assets/coin.wav": {"sound": "coin", "seed": 1},
            "assets/hit.wav": {"sound": "hit", "seed": 3}, "assets/theme.wav": {"music": "happy", "seed": 5, "speed": 1.2}}


BRICKS_1 = [".........", "RRRRRRRR", "OOOOOOOO", "YYYYYYYY", "GGGGGGGG", "BBBBBBBB"]
BRICKS_2 = [".........", "R.RRRR.R", "OOO..OOO", "Y.YYYY.Y", "GGG..GGG", "B.BBBB.B", "PPPPPPPP"]


def make_bricks(folder):
    tiles = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    save(tiles, folder, "blank.png")
    names = {"R": "red", "O": "orange", "Y": "yellow", "G": "green", "B": "blue", "P": "purple"}
    for name, rows in (("level1.tmj", BRICKS_1), ("level2.tmj", BRICKS_2)):
        things = []
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch in names:
                    things.append((names[ch], 4 + x * 44, 70 + y * 20, 44, 20))
        write_level(folder, name, tmj(15, 16, 24, tileset_entry("../assets/blank.png", tiles, 24),
                                      [("back", [0] * (15 * 16), None)], things))
    return {"assets/paddle.wav": {"sound": "click", "pitch": 0.8}, "assets/brick.wav": {"sound": "coin", "seed": 2, "length": 0.6},
            "assets/lost.wav": {"sound": "lose"}, "assets/theme.wav": {"music": "calm", "seed": 2}}


KEEP_1 = [
    "##############################",
    "#............#...............#",
    "#..P.........#....s..........#",
    "#............#...........c...#",
    "#.....~~~....D...............#",
    "#.....~~~....#...............#",
    "#............#######D#########",
    "#...k........#...............#",
    "#............#.......s.......#",
    "######.#######...............#",
    "#............#....k......c...#",
    "#.....s......#...............#",
    "#............D...........>...#",
    "#.....c......#...............#",
    "##############################"]

KEEP_2 = [
    "##############################",
    "#.......#.........#..........#",
    "#..P....#....c....#....s.....#",
    "#.......D.........D..........#",
    "#.......#....s....#.....k....#",
    "####.#######.##########.######",
    "#........~~~~~~~.............#",
    "#..k.....~~~~~~~......s......#",
    "#............................#",
    "######D#############.#########",
    "#..........#.................#",
    "#...c......#.....s......k....#",
    "#..........D.................#",
    "#....>.....#.......c.........#",
    "##############################"]


def make_adventure(folder):
    tiles = adventure_tiles()
    save(tiles, folder, "tiles.png")
    save(hero_top_down(), folder, "hero.png")
    save(key_picture(), folder, "key.png")
    save(door_picture(), folder, "door.png")
    save(chest_picture(), folder, "chest.png")
    save(slime_sheet(), folder, "slime.png")
    save(stairs_picture(), folder, "stairs.png")
    save(gem_picture(), folder, "gem.png")
    for name, rows in (("level1.tmj", KEEP_1), ("level2.tmj", KEEP_2)):
        cols, n = len(rows[0]), len(rows)
        assert all(len(row) == cols for row in rows), name
        floor = [1] * (cols * n)
        walls = [0] * (cols * n)
        things = []
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                i = y * cols + x
                if ch == "#":
                    walls[i] = 3
                elif ch == "~":
                    walls[i] = 4
                kind = {"P": "hero", "k": "key", "D": "door", "c": "chest", "s": "slime", ">": "stairs"}.get(ch)
                if kind:
                    things.append((kind, x * 16, y * 16, 16, 16))
        write_level(folder, name, tmj(cols, n, 16, tileset_entry("../assets/tiles.png", tiles, 16),
                                      [("floor", floor, None), ("walls", walls, SOLID)], things))
    return {"assets/key.wav": {"sound": "coin", "seed": 3}, "assets/door.wav": {"sound": "power up", "seed": 2},
            "assets/gem.wav": {"sound": "coin", "pitch": 1.3}, "assets/hit.wav": {"sound": "hit", "seed": 1},
            "assets/win.wav": {"sound": "win", "seed": 1}, "assets/theme.wav": {"music": "adventure", "seed": 8, "speed": 0.9}}


def make_tap(folder):
    save(star(), folder, "star.png")
    save(bomb(), folder, "bomb.png")
    return {"assets/pop.wav": {"sound": "coin", "seed": 5, "length": 0.7}, "assets/boom.wav": {"sound": "explosion", "seed": 2},
            "assets/miss.wav": {"sound": "click", "pitch": 0.6}, "assets/theme.wav": {"music": "happy", "seed": 9, "speed": 1.15}}


def make_puzzle(folder):
    return {"assets/click.wav": {"sound": "click"}, "assets/solved.wav": {"sound": "win", "seed": 2},
            "assets/theme.wav": {"music": "calm", "seed": 4}}


VALLEY = [
    "hhhhhhhhhhhhhhhhhhhhhh",
    "h......T.......T.....h",
    "h.T..==========....T.h",
    "h....=........=......h",
    "h....=..H0....=..~~~.h",
    "h.T..=........=..~~~.h",
    "h....=....L...=..~~~.h",
    "h....====P=====......h",
    "h.........=..........h",
    "h..T......=.....H1...h",
    "h.....*...=.......T..h",
    "h.........=......L...h",
    "hT.L......=..........h",
    "h.........========...h",
    "h...H2....=......=...h",
    "h.........=...T..=.T.h",
    "h..e......=......=...h",
    "h......T..=..L...=...h",
    "h.........=..........h",
    "hhhhhhhhhhhhhhhhhhhhhh"]


def make_world(folder):
    tiles = world_tiles()
    save(tiles, folder, "tiles.png")
    save(villager_sheet("#3a6fd8", "#6b3e26"), folder, "hero.png")
    save(villager_sheet("#9c2a2a", "#cfd6e4"), folder, "elder.png")
    save(lantern_picture(), folder, "lantern.png")
    save(tree_picture(), folder, "tree.png")
    save(roof_picture("#c0503c"), folder, "roof_red.png")
    save(roof_picture("#3a6fd8"), folder, "roof_blue.png")
    save(wall_picture(), folder, "wall.png")
    cols, n = len(VALLEY[0]), len(VALLEY)
    assert all(len(row) == cols for row in VALLEY)
    ground, walls = [1] * (cols * n), [0] * (cols * n)
    things = []
    for y, row in enumerate(VALLEY):
        x = 0
        while x < len(row):
            ch = row[x]
            i = y * cols + x
            ground[i] = {"=": 3, "*": 6}.get(ch, 2 if (x * 7 + y * 3) % 5 == 0 else 1)
            walls[i] = {"h": 9, "~": 7}.get(ch, 0)
            if ch == "H":
                things.append(("house" + row[x + 1], x * 16, y * 16, 16, 16))
                ground[i + 1] = 1
                x += 2
                continue
            kind = {"T": "tree", "L": "lantern", "P": "hero", "e": "elder"}.get(ch)
            if kind:
                things.append((kind, x * 16, y * 16, 16, 16))
            x += 1
    extra = {"tiles": [{"id": 8, "properties": [{"name": "height", "type": "float", "value": 1}]}]}
    write_level(folder, "valley.tmj", tmj(cols, n, 16, tileset_entry("../assets/tiles.png", tiles, 16, extra),
                                          [("ground", ground, None), ("walls", walls, SOLID)], things))
    return {"assets/chime.wav": {"sound": "power up", "seed": 4}, "assets/step.wav": {"sound": "step"},
            "assets/win.wav": {"sound": "win", "seed": 3}, "assets/theme.wav": {"music": "calm", "seed": 7, "speed": 0.95}}


MAKERS = {"platformer": make_platformer, "shooter": make_shooter, "runner": make_runner, "bricks": make_bricks,
          "adventure": make_adventure, "tap": make_tap, "puzzle": make_puzzle, "world": make_world}


def make(genre):
    folder = os.path.join(TEMPLATES, genre)
    os.makedirs(os.path.join(folder, "game"), exist_ok=True)
    write_app(folder, genre)
    sounds = MAKERS[genre](folder)
    with open(os.path.join(folder, "sounds.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(sounds, indent=1) + "\n")
    return folder


def main():
    for genre in sys.argv[1:] or GENRES:
        if genre not in MAKERS:
            sys.exit("no genre %r: %s" % (genre, ", ".join(GENRES)))
        print("made", make(genre))


if __name__ == "__main__":
    main()
