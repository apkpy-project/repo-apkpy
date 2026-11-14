"""The title: a scene that moves (sky, clouds, the sea, the light of the lighthouse, a creature) with the whole screen
as the button. After the first tap come New journey and Continue. To change the look: the art is in tools/make_art.py
(draw_title_*), and what moves is the prefab title_scenery below.
"""
from apkpy_lib.game import *

import math

from game.data.defs import game_info
from game.state.new_game import new_save
from game.state.store import SESSION, Save, UI
from game.ui.kit import ButtonWord, TextWord, FRONT, show_monster, SIZE, box, catch_sound, monster_sheet, tap_sound
from game.ui.screens import SLOT
from game.world.events import start_event

sky_image = assets.image("assets/title_sky.png")
cloud_image = assets.image("assets/title_cloud.png")
sea_image = assets.image("assets/title_sea.png")
rock_image = assets.image("assets/title_rock.png")
beam_image = assets.image("assets/title_beam.png")
logo_image = assets.image("assets/title_logo.png")


class Drift(Script):
    """Goes sideways for ever, and comes back in on the other side of whatever the screen shows."""
    speed: float = 8.0

    def update(self, dt: float):
        self.x -= self.speed * dt
        half = game.view_width / 2 + 90
        if self.x < 240 - half:
            self.x = 240 + half


class Swell(Script):
    """The sea: an image of waves, slid by one wave and back to the start."""
    wave: float = 32.0
    speed: float = 10.0
    home: float = 240.0

    def update(self, dt: float):
        self.x -= self.speed * dt
        if self.x < self.home - self.wave:
            self.x += self.wave


class Sweep(Script):
    """The lighthouse's light, turning slowly from side to side."""

    def update(self, dt: float):
        self.rotation = 180 + 28 * math.sin(game.time * 0.7)
        self.sprite.alpha = 0.5 + 0.2 * math.sin(game.time * 1.9)


class Giant(Script):
    """The shape behind the title, breathing."""
    home: float = 0.0

    def on_start(self):
        show_monster(self.sprite, game_info().title_giant, FRONT)
        self.home = self.y

    def update(self, dt: float):
        self.y = self.home + 5 * math.sin(game.time * 1.1)


class Visitor(Script):
    """A creature that crosses the sky now and then, a different one each time."""
    wait: float = 2.0
    goes: int = 0

    def on_start(self):
        self.sprite.visible = False

    def update(self, dt: float):
        if self.wait > 0:
            self.wait -= dt
            if self.wait <= 0:
                kinds = game_info().title_visitors
                show_monster(self.sprite, kinds[self.goes % len(kinds)], FRONT)
                self.goes += 1
                self.sprite.visible = True
                self.x = 240 + game.view_width / 2 + 40
            return
        self.x -= 60 * dt
        self.y = 150 + 14 * math.sin(game.time * 4)
        if self.x < 240 - game.view_width / 2 - 40:
            self.sprite.visible = False
            self.wait = 5.0


class LogoDrop(Script):
    """The title comes down and settles."""
    home: float = 62.0

    def on_start(self):
        self.y = -60.0

    def update(self, dt: float):
        self.y += (self.home - self.y) * min(1.0, 3.0 * dt)


@prefab
def cloud(speed: float = 8, x: float = 0, y: float = 0):
    return Entity("cloud", Sprite(cloud_image, filter="nearest", alpha=0.85), Drift(speed=speed), at=(x, y))


@prefab
def title_scenery():
    """Not interface: it is the scene's world, and shows more of itself on a wider screen."""
    return Entity("scenery", children=[
        Entity("sky", Sprite(sky_image, filter="nearest", layer=-10, pivot=(0.5, 1)), at=(240, 222)),
        cloud(5, 60, 30), cloud(9, 300, 58), cloud(4, 420, 22), cloud(14, 150, 96), cloud(11, 520, 110),
        Entity("giant", Sprite(monster_sheet, frame=0, filter="nearest", tint="#17404f", alpha=0.75, layer=-2), Giant(), at=(240, 112), scale=3),
        Entity("visitor", Sprite(monster_sheet, frame=0, filter="nearest", layer=1), Visitor(), at=(600, 150), scale=0.75),
        Entity("sea", Sprite(sea_image, filter="nearest", layer=2, pivot=(0.5, 0)), Swell(), at=(240, 219)),
        Entity("rock", Sprite(rock_image, filter="nearest", layer=3, pivot=(0.5, 1)), at=(70, 244)),
        Entity("beam", Sprite(beam_image, filter="nearest", pivot=(1, 0.5), layer=1, alpha=0.6), Sweep(), at=(70, 137)),
        Entity("logo", Sprite(logo_image, filter="nearest", layer=5), LogoDrop(), at=(240, -60)),
    ])


class Title(Script):
    """Tap anywhere; then the choices; then, for a new journey, your name. Back goes one step back."""
    step: str = "press"
    blink: float = 0.0
    touched: bool = False

    def on_start(self):
        self.entity.child("continue").button.enabled = saves.exists(SLOT)
        self.show()

    def show(self):
        self.entity.child("press").active = self.step == "press"
        self.entity.child("menu").active = self.step == "menu"
        self.entity.child("name_page").active = self.step == "name"
        scenery = scene.find("scenery")
        if scenery is not None:
            scenery.active = self.step != "name"          # the name page covers it all

    def update(self, dt: float):
        if self.step == "press":
            self.blink += dt
            self.entity.child("press").text.visible = self.blink % 1.2 < 0.8
            # a step after the finger is lifted: it must not also press the button that appears under it
            if (self.touched and not input.pointer_down()) or input.key_pressed("space"):
                self.touched = False
                audio.play(catch_sound)
                self.step = "menu"
                self.show()
            elif input.pointer_pressed():
                self.touched = True
        elif self.step == "menu":
            self.update_menu()
        else:
            self.update_name()

    def update_menu(self):
        if self.entity.child("new").button.clicked:
            SESSION.save = new_save()
            self.step = "name"
            self.show()
        elif self.entity.child("continue").button.clicked:
            text = saves.read(SLOT)
            if text is not None:
                SESSION.save = from_json(text, Save)
                audio.set_music(SESSION.save.options.music)
                audio.set_sound_volume(SESSION.save.options.sound)
                UI.restore_position = True
                game.goto(SESSION.save.map, "", 0.5)

    def update_name(self):
        typed = self.entity.child("keys").keyboard
        self.entity.child("name").text.text = typed.text + "_"
        if typed.done and typed.text != "":
            SESSION.save.player = typed.text
            start_event(game_info().first_event)
            game.goto(game_info().start_map, game_info().start_at, 0.6)

    def on_back(self) -> bool:
        if self.step == "press":
            return False
        self.step = "press" if self.step == "menu" else "menu"
        self.show()
        return True


@prefab
def title_screen():
    return Entity("title", Title(), ui=True, children=[
        Entity("press", Text("Touch the screen", size=SIZE, align="center", color="#f4ecd4"), TextWord(key="touch_screen"), ui=True, anchor="center", at=(240, 195)),
        Entity("menu", ui=True, anchor="center", at=(240, 150), children=[
            Entity("new", Button("New journey", size=(170, 34), image=box, text_size=SIZE, sound=tap_sound), ButtonWord(key="new_journey"), ui=True),
            Entity("continue", Button("Continue", size=(170, 34), image=box, text_size=SIZE, sound=tap_sound), ButtonWord(key="continue"), ui=True, at=(0, 40)),
        ]),
        Entity("name_page", Panel(box, size=(800, 500), modal=True), ui=True, anchor="center", at=(240, 135), children=[
            Entity("ask", Text("What is your name?", size=SIZE, align="center"), TextWord(key="your_name"), ui=True, at=(0, -115)),
            Entity("name", Text("_", size=SIZE, align="center"), ui=True, at=(0, -96)),
            Entity("keys", Keyboard(size=(360, 190), image=box, max_length=10, text_size=SIZE, sound=tap_sound), ui=True, at=(-180, -75)),
        ]),
    ])
