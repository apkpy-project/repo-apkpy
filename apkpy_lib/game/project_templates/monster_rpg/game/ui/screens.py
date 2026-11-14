"""The screens opened over the world: menu, team, bag, shop, encyclopedia, options, save, first partner.

Each is a @prefab (what it looks like) and a Script (what it does). The Hud opens the one UI.screen names; a screen
closes by emptying UI.screen, or opens another by changing it. To add a screen: a prefab and a script here, its
name in Hud.open_screen (game/ui/hud.py), and a button in the menu.
"""

from __future__ import annotations

from apkpy_lib.game import *

from game.data.defs import ITEMS, MOVES, SHOPS, SPECIES, STATUSES, TYPES, fill, game_info, named, word
from game.rules.items import apply, evolve_with, evolves_with, helps
from game.rules.monsters import display_name, exp_progress, exp_to_next, look, make_monster, max_hp, stat, variant_name
from game.state.store import SESSION, UI, Monster, add_item
from game.ui.kit import ButtonWord, TextWord, BIG, FRONT, show_monster, EXP_BACK, EXP_COLOR, LIFE_BACK, LIFE_LOW, SCREEN_H, SCREEN_W, SIZE, box, heal_sound, monster_sheet, tap_sound

SLOT = "slot1"


def save_game_text() -> str:
    return to_json(SESSION.save)


class CloseButton(Script):
    def update(self, dt: float):
        if self.button.clicked:
            UI.screen = ""


class OpenButton(Script):
    """On a menu button: opens that screen."""
    screen: str = "team"

    def update(self, dt: float):
        if self.button.clicked:
            UI.screen = self.screen


@prefab
def close_button():
    return Entity("close", Button("Close", size=(60, 24), image=box, text_size=SIZE, sound=tap_sound), ButtonWord(key="close"), CloseButton(), ui=True,
                  at=(SCREEN_W / 2 - 40, SCREEN_H / 2 - 22))


@prefab
def menu_button(label: str = "", screen: str = "team", y: float = 0, key: str = "team"):
    return Entity("item", Button(label, size=(170, 30), image=box, text_size=SIZE, sound=tap_sound), OpenButton(screen=screen), ButtonWord(key=key),
                  ui=True, at=(0, y))


class Menu(Script):
    """The pause menu: the buttons do it all."""

    def on_start(self):
        s = SESSION.save
        self.entity.child("who").text.text = s.player + "   " + str(s.money) + " " + game_info().currency


@prefab
def menu_screen():
    return Entity("screen", Panel(box, size=(200, 256), modal=True), Menu(), ui=True, anchor="center", at=(240, 135), children=[
        Entity("who", Text("", size=SIZE, align="center"), ui=True, at=(0, -110)),
        menu_button("Team", "team", -90, "team"), menu_button("Bag", "bag", -56, "bag"), menu_button("Encyclopedia", "dex", -22, "encyclopedia"),
        menu_button("Save", "save", 12, "save"), menu_button("Options", "options", 46, "options"),
        Entity("close", Button("Back", size=(170, 30), image=box, text_size=SIZE, sound=tap_sound), ButtonWord(key="back"), CloseButton(), ui=True, at=(0, 90)),
    ])


# ── team and box ─────────────────────────────────────────────────────────


class TeamScreen(Script):
    picked: int = 0

    def on_start(self):
        self.show()

    def members(self) -> list[Monster]:
        return SESSION.save.box if self.tabs_at() == 1 else SESSION.save.team

    def tabs_at(self) -> int:
        return self.entity.child("tabs").tabs.selected

    def show(self):
        self.list.count = len(self.members())
        self.list.refresh()
        self.detail()

    def detail(self):
        who = self.members()
        words = word("nobody_here")
        if self.picked < len(who):
            m = who[self.picked]
            words = (display_name(m) + "  " + word("level_short") + " " + str(m.level) + "  " + m.nature + "\n" + word("hp_short") + " " + str(m.hp) + "/" + str(max_hp(m))
                     + " " + word("attack_short") + " " + str(stat(m, "attack")) + " " + word("defense_short") + " " + str(stat(m, "defense"))
                     + "\n" + word("special_short") + " " + str(stat(m, "special")) + " " + word("speed_short") + " " + str(stat(m, "speed"))
                     + (" " + STATUSES.get(m.status).name if m.status != "" else "")
                     + "\n" + fill(word("next_level"), "count", str(exp_to_next(m)))
                     + "\n" + named("variant_is", variant_name(m)) + "\n")
            for slot in m.moves:
                move = MOVES.get(slot.move)
                words = words + "\n[c=" + TYPES.get(move.type).color + "]" + move.name + "[/c] " + str(slot.pp) + "/" + str(move.pp)
        self.entity.child("detail").text.text = words

    def on_row(self, row: Entity, index: int):
        who = self.members()
        if index >= len(who):
            return
        m = who[index]
        show_monster(row.child("icon").sprite, look(m), FRONT)
        row.child("name").text.text = display_name(m)
        row.child("level").text.text = word("level_short") + " " + str(m.level)
        bar = row.child("life").bar
        bar.max = float(max_hp(m))
        bar.value = float(m.hp)
        row.child("exp").bar.value = float(exp_progress(m))

    def update(self, dt: float):
        if self.entity.child("tabs").tabs.changed:
            self.picked = 0
            self.show()
        tapped = self.list.tapped
        if tapped >= 0:
            self.picked = tapped
            self.detail()
        s = SESSION.save
        if self.entity.child("lead").button.clicked and self.tabs_at() == 0 and self.picked < len(s.team):
            first = s.team.pop(self.picked)
            s.team.insert(0, first)
            self.picked = 0
            self.show()
        if self.entity.child("move").button.clicked:
            self.move_one()

    def move_one(self):
        s = SESSION.save
        if self.tabs_at() == 0 and self.picked < len(s.team) and len(s.team) > 1:
            s.box.append(s.team.pop(self.picked))
        elif self.tabs_at() == 1 and self.picked < len(s.box) and len(s.team) < 6:
            s.team.append(s.box.pop(self.picked))
        self.picked = 0
        self.show()


@prefab
def team_row():
    return Entity("row", Panel(box, size=(222, 40)), children=[
        Entity("icon", Sprite(monster_sheet, frame=0, filter="nearest"), ui=True, at=(-92, 0), scale=0.5),
        Entity("name", Text("", size=SIZE), ui=True, at=(-66, -4)),
        Entity("level", Text("", size=SIZE, align="right"), ui=True, at=(102, -4)),
        Entity("life", Bar(1, size=(120, 5), speed=0, back=LIFE_BACK, low_color=LIFE_LOW), ui=True, at=(-66, 5)),
        Entity("exp", Bar(0, max=1000, size=(120, 3), speed=0, color=EXP_COLOR, mid_color=EXP_COLOR, low_color=EXP_COLOR, back=EXP_BACK), ui=True, at=(-66, 11)),
    ])


@prefab
def team_screen():
    return Entity("screen", Panel(box, size=(SCREEN_W, SCREEN_H), modal=True), ScrollList(team_row(), size=(225, 200), item_size=(225, 42), gap=2, pivot=(0.9867, 0.45)), TeamScreen(), ui=True,
                  anchor="center", at=(240, 135), children=[
        Entity("tabs", Tabs(["Team", "Box"], size=(225, 24), image=box, text_size=SIZE), ui=True, at=(-222, -118)),
        Entity("detail", Text("", size=SIZE, max_width=205, line_spacing=1.3), ui=True, at=(15, -100)),
        Entity("lead", Button("Lead", size=(70, 26), image=box, text_size=SIZE, sound=tap_sound), ButtonWord(key="lead"), ui=True, at=(50, 75)),
        Entity("move", Button("Team <> Box", size=(110, 26), image=box, text_size=SIZE, sound=tap_sound), ButtonWord(key="team_box"), ui=True, at=(150, 75)),
        close_button(),
    ])


# ── bag ──────────────────────────────────────────────────────────────────


def bag_kind(tab: int) -> str:
    return "heal" if tab == 0 else "capture" if tab == 1 else "key"


def bag_keys(tab: int) -> list[str]:
    keys: list[str] = []
    for k in SESSION.save.bag:
        kind = ITEMS.get(k).kind
        if kind == bag_kind(tab) or (tab == 0 and kind == "cure"):
            keys.append(k)
    return keys


class BagScreen(Script):
    keys: list[str] = []

    def on_start(self):
        self.show()

    def tab(self) -> int:
        return self.entity.child("tabs").tabs.selected

    def show(self):
        self.keys = bag_keys(self.tab())
        self.list.count = len(self.keys)
        self.list.refresh()

    def on_row(self, row: Entity, index: int):
        if index < len(self.keys):
            key = self.keys[index]
            row.child("name").text.text = ITEMS.get(key).name
            row.child("count").text.text = "x" + str(SESSION.save.bag.get(key, 0))

    def update(self, dt: float):
        if self.entity.child("tabs").tabs.changed:
            self.show()
        tapped = self.list.tapped
        if tapped >= 0 and tapped < len(self.keys):
            self.use(self.keys[tapped])

    def use(self, key: str):
        """On the first in the team it helps: an item that heals or cures, or one that makes a monster evolve."""
        item = ITEMS.get(key)
        words = item.description
        for m in SESSION.save.team:
            if evolves_with(key, m) != "":
                old = display_name(m)
                target = evolves_with(key, m)
                evolve_with(key, m)
                add_item(key, -1)
                audio.play(heal_sound)
                words = fill(named("became", old), "monster", SPECIES.get(target).name)
                self.show()
                break
            if helps(item, m):
                apply(item, m)
                add_item(key, -1)
                audio.play(heal_sound)
                words = named("feels_better", display_name(m))
                self.show()
                break
        self.entity.child("detail").text.text = words


@prefab
def bag_row():
    return Entity("row", Panel(box, size=(222, 30)), children=[
        Entity("name", Text("", size=SIZE), ui=True, at=(-100, 3)),
        Entity("count", Text("", size=SIZE, align="right"), ui=True, at=(100, 3)),
    ])


@prefab
def bag_screen():
    return Entity("screen", Panel(box, size=(SCREEN_W, SCREEN_H), modal=True), ScrollList(bag_row(), size=(225, 200), item_size=(225, 32), gap=2, pivot=(0.9867, 0.45)), BagScreen(), ui=True,
                  anchor="center", at=(240, 135), children=[
        Entity("tabs", Tabs(["Items", "Knots", "Key"], size=(225, 24), image=box, text_size=SIZE), ui=True, at=(-222, -118)),
        Entity("detail", Text("Tap an item to use it.", size=SIZE, max_width=205, line_spacing=1.3), TextWord(key="tap_to_use"), ui=True, at=(15, -100)),
        close_button(),
    ])


# ── shop ─────────────────────────────────────────────────────────────────


class ShopScreen(Script):
    """Tap an item to read about it; the Buy button is beside the description."""
    keys: list[str] = []
    picked: str = ""

    def on_start(self):
        for key in SHOPS.get(UI.shop).items:
            self.keys.append(key)
        self.list.count = len(self.keys)
        self.entity.child("title").text.text = SHOPS.get(UI.shop).name
        self.entity.child("buy").active = False
        self.money()

    def money(self):
        self.entity.child("money").text.text = str(SESSION.save.money) + " " + game_info().currency

    def on_row(self, row: Entity, index: int):
        if index < len(self.keys):
            item = ITEMS.get(self.keys[index])
            row.child("name").text.text = item.name
            row.child("name").text.set_color("#ffd84a" if self.keys[index] == self.picked else "#ffffff")
            row.child("count").text.text = str(item.price)

    def describe(self, said: str):
        item = ITEMS.get(self.picked)
        s = SESSION.save
        if s.money < item.price and said == "":
            said = word("not_enough")
        self.entity.child("detail").text.text = (item.name + "\n\n" + item.description + "\n\n" + fill(word("price"), "count", str(item.price))
                                                 + "\n" + fill(word("in_bag"), "count", str(s.bag.get(self.picked, 0))) + "\n\n" + said)
        buy = self.entity.child("buy")
        buy.active = True
        buy.button.enabled = s.money >= item.price

    def update(self, dt: float):
        tapped = self.list.tapped
        if tapped >= 0 and tapped < len(self.keys):
            self.picked = self.keys[tapped]
            self.list.refresh()
            audio.play(tap_sound)
            self.describe("")
        if self.entity.child("buy").active and self.entity.child("buy").button.clicked:
            s = SESSION.save
            s.money -= ITEMS.get(self.picked).price
            add_item(self.picked, 1)
            self.money()
            self.describe(word("thanks"))


@prefab
def shop_screen():
    return Entity("screen", Panel(box, size=(SCREEN_W, SCREEN_H), modal=True), ScrollList(bag_row(), size=(225, 200), item_size=(225, 32), gap=2, pivot=(0.9867, 0.45)), ShopScreen(), ui=True,
                  anchor="center", at=(240, 135), children=[
        Entity("title", Text("", size=SIZE), ui=True, at=(-218, -105)),
        Entity("money", Text("", size=SIZE, align="right"), ui=True, at=(215, -105)),
        Entity("detail", Text("Tap an item to read about it.", size=SIZE, max_width=205, line_spacing=1.3), TextWord(key="tap_to_read"), ui=True, at=(15, -80)),
        Entity("buy", Button("Buy", size=(100, 30), image=box, text_size=SIZE, sound=heal_sound), ButtonWord(key="buy"), ui=True, at=(65, 75)),
        close_button(),
    ])


# ── encyclopedia ─────────────────────────────────────────────────────────


class DexScreen(Script):
    def on_start(self):
        s = SESSION.save
        self.list.count = len(SPECIES)
        self.entity.child("count").text.text = (fill(word("seen_count"), "count", str(len(s.seen))) + "   " + fill(word("bonded_count"), "count", str(len(s.caught)))
                                                + "   " + fill(word("of_count"), "count", str(len(SPECIES))))

    def on_row(self, row: Entity, index: int):
        s = SPECIES.all()[index]
        seen = s.id in SESSION.save.seen
        show_monster(row.sprite, s.id, FRONT)
        row.sprite.set_tint("#ffffff" if seen else "#101018")

    def update(self, dt: float):
        tapped = self.list.tapped
        if tapped < 0:
            return
        s = SPECIES.all()[tapped]
        words = word("not_seen")
        if s.id in SESSION.save.seen:
            kinds = ""
            for t in s.types:
                kinds = kinds + TYPES.get(t).name + " "
            words = s.name + "   " + kinds + "\n" + s.description
        self.entity.child("detail").text.text = words


@prefab
def dex_screen():
    return Entity("screen", Panel(box, size=(SCREEN_W, SCREEN_H), modal=True),
                  ScrollList(Entity("cell", Sprite(monster_sheet, frame=0, filter="nearest")), size=(225, 236), item_size=(68, 68), columns=3, gap=6,
                             pivot=(0.9867, 0.5)), DexScreen(), ui=True, anchor="center", at=(240, 135), children=[
        Entity("count", Text("", size=SIZE, max_width=205), ui=True, at=(15, -105)),
        Entity("detail", Text("Tap one to read about it.", size=SIZE, max_width=205, line_spacing=1.3), TextWord(key="tap_one"), ui=True, at=(15, -75)),
        close_button(),
    ])


# ── options and saving ───────────────────────────────────────────────────


class OptionsScreen(Script):
    def on_start(self):
        o = SESSION.save.options
        self.entity.child("music").toggle.value = o.music
        self.entity.child("sound").slider.value = o.sound
        self.entity.child("speed").slider.value = o.text_speed

    def update(self, dt: float):
        o = SESSION.save.options
        music = self.entity.child("music").toggle
        if music.changed:
            o.music = music.value
            audio.set_music(o.music)
        sound = self.entity.child("sound").slider
        if sound.changed:
            o.sound = sound.value
            audio.set_sound_volume(o.sound)
        speed = self.entity.child("speed").slider
        if speed.changed:
            o.text_speed = speed.value


@prefab
def options_screen():
    return Entity("screen", Panel(box, size=(220, 220), modal=True), OptionsScreen(), ui=True, anchor="center", at=(240, 135), children=[
        Entity("music", Toggle("Music", size=(150, 24), image=box, text_size=SIZE), ui=True, at=(-90, -70)),
        Entity("t1", Text("Sound", size=SIZE), TextWord(key="sound"), ui=True, at=(-90, -30)),
        Entity("sound", Slider(1, max=1, step=0.1, size=(180, 24)), ui=True, at=(-90, -12)),
        Entity("t2", Text("Text speed", size=SIZE), TextWord(key="text_speed"), ui=True, at=(-90, 20)),
        Entity("speed", Slider(2, min=1, max=6, step=1, size=(180, 24)), ui=True, at=(-90, 38)),
        Entity("close", Button("Close", size=(60, 24), image=box, text_size=SIZE), ButtonWord(key="close"), CloseButton(), ui=True, at=(60, 85)),
    ])


class SaveScreen(Script):
    def update(self, dt: float):
        if self.entity.child("write").button.clicked:
            saves.write(SLOT, save_game_text())
            audio.play(tap_sound)
            self.entity.child("said").text.text = word("saved")


@prefab
def save_screen():
    return Entity("screen", Panel(box, size=(220, 120), modal=True), SaveScreen(), ui=True, anchor="center", at=(240, 135), children=[
        Entity("said", Text("Save your journey?", size=SIZE, align="center"), TextWord(key="save_question"), ui=True, at=(0, -28)),
        Entity("write", Button("Save", size=(100, 30), image=box, text_size=SIZE), ButtonWord(key="save"), ui=True, at=(-40, 25)),
        Entity("close", Button("Close", size=(60, 30), image=box, text_size=SIZE), ButtonWord(key="close"), CloseButton(), ui=True, at=(60, 25)),
    ])


# ── the first partner ────────────────────────────────────────────────────

class StarterScreen(Script):
    """Tap one to read about it; then take it, or go back and look at the others. The three come from data/game.json."""
    looking: str = ""

    def on_start(self):
        self.show_choice("one", 0)
        self.show_choice("two", 1)
        self.show_choice("three", 2)
        self.show_page()

    def show_choice(self, name: str, at: int):
        kinds = game_info().starters
        if at < len(kinds):
            e = self.entity.child(name)
            show_monster(e.child("picture").sprite, kinds[at], FRONT)
            e.child("label").text.text = SPECIES.get(kinds[at]).name

    def show_page(self):
        reading = self.looking != ""
        count = len(game_info().starters)
        self.entity.child("page").active = reading
        self.entity.child("ask").active = not reading
        self.entity.child("one").active = not reading and count > 0
        self.entity.child("two").active = not reading and count > 1
        self.entity.child("three").active = not reading and count > 2

    def look_at(self, species: str):
        self.looking = species
        s = SPECIES.get(species)
        kinds = ""
        for t in s.types:
            kinds = kinds + ("" if kinds == "" else " " + word("and") + " ") + TYPES.get(t).name
        page = self.entity.child("page")
        show_monster(page.child("picture").sprite, species, FRONT)
        page.child("name").text.text = s.name
        page.child("kind").text.text = named("of_type", "[c=" + TYPES.get(s.types[0]).color + "]" + kinds + "[/c]")
        page.child("entry").text.text = s.description
        self.show_page()

    def update(self, dt: float):
        if self.looking == "":
            kinds = game_info().starters
            if self.entity.child("one").button.clicked:
                self.look_at(kinds[0])
            elif self.entity.child("two").button.clicked:
                self.look_at(kinds[1])
            elif self.entity.child("three").button.clicked:
                self.look_at(kinds[2])
            return
        page = self.entity.child("page")
        if page.child("take").button.clicked:
            self.take(self.looking)
        elif page.child("other").button.clicked:
            self.looking = ""
            self.show_page()

    def take(self, species: str):
        s = SESSION.save
        s.team.append(make_monster(species, game_info().starter_level))
        s.seen[species] = 1
        s.caught[species] = 1
        audio.play(heal_sound)
        UI.screen = ""


@prefab
def starter_choice(name: str = "one", x: float = 0):
    return Entity(name, Button("", size=(125, 120), image=box), ui=True, at=(x, 10), children=[
        Entity("picture", Sprite(monster_sheet, frame=0, filter="nearest"), ui=True, at=(0, -14)),
        Entity("label", Text("", size=SIZE, align="center"), ui=True, at=(0, 42)),
    ])


@prefab
def starter_screen():
    return Entity("screen", Panel(box, size=(420, 200), modal=True), StarterScreen(), ui=True, anchor="center", at=(240, 135), children=[
        Entity("ask", Text("Choose your partner", size=SIZE, align="center"), TextWord(key="choose_partner"), ui=True, at=(0, -78)),
        starter_choice("one", -135), starter_choice("two", 0), starter_choice("three", 135),
        Entity("page", ui=True, children=[
            Entity("picture", Sprite(monster_sheet, frame=0, filter="nearest"), ui=True, at=(-133, -24), scale=2),
            Entity("name", Text("", size=BIG), ui=True, at=(-60, -62)),
            Entity("kind", Text("", size=SIZE), ui=True, at=(-60, -42)),
            Entity("entry", Text("", size=SIZE, max_width=255, line_spacing=1.3), ui=True, at=(-60, -20)),
            Entity("take", Button("Take this one", size=(120, 30), image=box, text_size=SIZE, sound=tap_sound), ButtonWord(key="take_this"), ui=True, at=(30, 72)),
            Entity("other", Button("Look at another", size=(130, 30), image=box, text_size=SIZE, sound=tap_sound), ButtonWord(key="look_another"), ui=True, at=(-110, 72)),
        ]),
    ])
