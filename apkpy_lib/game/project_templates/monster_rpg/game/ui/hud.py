"""What is always there on a map: the movement pad, the A and Menu buttons, the dialog box, and the Hud script that
opens the screens and stops the world while anything else is going on.
"""
from apkpy_lib.game import *

from game.state.store import RUN, SESSION, UI
from game.ui.kit import ButtonWord, SIZE, box, tap_sound
from game.ui.screens import (bag_screen, dex_screen, menu_screen, options_screen, save_screen, shop_screen, starter_screen,
                             team_screen)
from game.world.events import EventRunner


class Hud(Script):
    menu: Prefab = menu_screen()
    team: Prefab = team_screen()
    bag: Prefab = bag_screen()
    dex: Prefab = dex_screen()
    shop: Prefab = shop_screen()
    options: Prefab = options_screen()
    saving: Prefab = save_screen()
    starter: Prefab = starter_screen()
    opened: str = ""

    def update(self, dt: float):
        if UI.screen != self.opened:
            self.open_screen(UI.screen)
        busy = RUN.active or UI.screen != "" or UI.say != ""
        if busy and not scene.is_paused("world"):
            scene.pause("world")
        elif not busy and scene.is_paused("world"):
            scene.resume("world")
        self.entity.child("pad").active = not busy
        self.entity.child("menu").active = not busy
        self.entity.child("a").active = not busy
        if self.entity.child("menu").button.clicked:
            UI.screen = "menu"
        UI.press_a = input.key_pressed("space") or self.entity.child("a").button.clicked

    def open_screen(self, name: str):
        old = scene.find("screen")
        if old is not None:
            old.destroy()
        self.opened = name
        if name == "menu":
            scene.spawn(self.menu, 0, 0)
        elif name == "team":
            scene.spawn(self.team, 0, 0)
        elif name == "bag":
            scene.spawn(self.bag, 0, 0)
        elif name == "dex":
            scene.spawn(self.dex, 0, 0)
        elif name == "shop":
            scene.spawn(self.shop, 0, 0)
        elif name == "options":
            scene.spawn(self.options, 0, 0)
        elif name == "save":
            scene.spawn(self.saving, 0, 0)
        elif name == "starter":
            scene.spawn(self.starter, 0, 0)

    def on_back(self) -> bool:
        """The phone's Back: closes what is open, or opens the menu. It never leaves the game from a map."""
        if UI.say == "" and not RUN.active:
            UI.screen = "" if UI.screen != "" else "menu"
        return True


class Dialog(Script):
    """Shows UI.say, letter by letter, page by page. A tap (or A) hurries it, then goes on."""
    showing: str = ""
    letters: float = 0.0

    def update(self, dt: float):
        words = self.entity.child("words").text
        if UI.say != self.showing:
            self.showing = UI.say
            self.letters = 0.0
            words.text = UI.say
            words.page = 0
            words.visible_chars = 0
        box_open = UI.say != ""
        self.entity.child("frame").panel.visible = box_open
        words.visible = box_open
        yes = self.entity.child("yes")
        no = self.entity.child("no")
        yes.active = False
        no.active = False
        if not box_open:
            return
        self.letters += SESSION.save.options.text_speed
        words.visible_chars = int(self.letters / 2)
        done = words.visible_chars >= words.page_chars
        if done and UI.asking and words.page + 1 >= words.pages:
            yes.active = True
            no.active = True
            if yes.button.clicked or no.button.clicked:
                UI.answer = yes.button.clicked
                UI.asking = False
                UI.say = ""
            return
        if input.pointer_pressed() or input.key_pressed("space"):
            if not done:
                self.letters = 100000.0
            elif words.page + 1 < words.pages:
                words.page += 1
                self.letters = 0.0
            else:
                UI.say = ""


@prefab
def pad_key(key: str = "up", x: float = 0, y: float = 0, label: str = "^"):
    return Entity("key", Button(label, size=(36, 36), image=box, text_size=SIZE), TouchButton(key=key), ui=True, at=(x, y))


@prefab
def hud():
    return Entity("hud", EventRunner(), Hud(), ui=True, children=[
        Entity("pad", ui=True, anchor="bottom-left", at=(94, 196), children=[
            pad_key("up", 0, -38, "^"), pad_key("down", 0, 38, "v"), pad_key("left", -38, 0, "<"), pad_key("right", 38, 0, ">"),
        ]),
        Entity("a", Button("A", size=(50, 50), image=box, sound=tap_sound, text_size=16), ui=True, anchor="bottom-right", at=(406, 208)),
        Entity("menu", Button("Menu", size=(60, 26), image=box, text_size=SIZE, sound=tap_sound), ButtonWord(key="menu"), ui=True, anchor="top-right", at=(418, 30)),
        Entity("dialog", Dialog(), ui=True, anchor="bottom", at=(240, 225), children=[
            Entity("frame", Panel(box, size=(450, 80)), ui=True),
            Entity("words", Text("", size=SIZE, max_width=420, max_lines=4, line_spacing=1.3), ui=True, at=(-210, -20)),
            Entity("yes", Button("Yes", size=(50, 24), image=box, text_size=SIZE, sound=tap_sound), ButtonWord(key="yes"), ui=True, at=(145, -56), active=False),
            Entity("no", Button("No", size=(50, 24), image=box, text_size=SIZE, sound=tap_sound), ButtonWord(key="no"), ui=True, at=(200, -56), active=False),
        ]),
    ])