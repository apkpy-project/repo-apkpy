"""The look of the interface: the art it uses, in one place. To restyle the game, change this file (and assets/)."""
from apkpy_lib.game import *

from game.data.defs import word


class ButtonWord(Script):
    """Its button says the words of data/texts.json with this id."""
    key: str = ""

    def on_start(self):
        if self.key != "":
            self.button.label = word(self.key)


class TextWord(Script):
    """Its text says the words of data/texts.json with this id."""
    key: str = ""

    def on_start(self):
        if self.key != "":
            self.text.text = word(self.key)


pixel = assets.font("assets/pixel.fnt")          # the game's font: a TTF works too (assets.font("assets/any.ttf"))
box = assets.image("assets/box.png")             # every panel and button: cut in nine
monster_files = assets.folder("assets/monsters")   # one sheet per species: <id>.png, its front then its back
monster_sheet = assets.sheet("assets/monster_blank.png", frame=(64, 64))    # what a monster's Sprite starts as
tap_sound = assets.sound("assets/sfx_tap.wav")
hit_sound = assets.sound("assets/sfx_hit.wav")
heal_sound = assets.sound("assets/sfx_heal.wav")
catch_sound = assets.sound("assets/sfx_catch.wav")

FRONT = 0
BACK = 1


def monster_image(species: str) -> str:
    return "assets/monsters/" + species + ".png"


def show_monster(sprite: Sprite, species: str, view: int) -> None:
    """In the interface: this species, FRONT or BACK."""
    sprite.set_image(monster_image(species))
    sprite.set_frame(view)


def stand_monster(picture: Billboard, species: str, view: int) -> None:
    """In the battle's world."""
    picture.set_image(monster_image(species))
    picture.set_frame(view)


SIZE = 8                                         # text: the font's own size...
BIG = 16                                         # ...and twice that: bitmap fonts look best at whole multiples
SCREEN_W = 460                                   # the big screens; they sit at the centre of the design area (480 x 270)
SCREEN_H = 254
LIFE_BACK = "#a82020"                            # life bars: what is missing shows red...
LIFE_LOW = "#f08030"                             # ...so a low bar is orange, not red on red
EXP_COLOR = "#58a8f0"                            # the experience bars
EXP_BACK = "#34507c"


