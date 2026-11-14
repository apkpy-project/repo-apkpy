"""The battle on the screen: shows the lines the engine wrote, one at a time, and asks the player what to do.
No rules here: game/battle/engine.py decides everything.
"""

from __future__ import annotations

from apkpy_lib.game import *

from game.battle.engine import ally, fight, first_able, foe, run_away, switch_to, use_item
from game.data.defs import ITEMS, MOVES, STATUSES, TYPES, named, word
from game.rules.items import usable_in_battle
from game.state.store import Monster
from game.rules.monsters import display_name, exp_progress, heal_fully, look, max_hp
from game.state.store import BATTLE, BattleLine, SESSION, UI
from game.ui.kit import ButtonWord, BACK, FRONT, stand_monster, EXP_BACK, EXP_COLOR, LIFE_BACK, LIFE_LOW, SIZE, box, catch_sound, heal_sound, hit_sound, monster_sheet, tap_sound


class Presenter(Script):
    mode: str = "lines"              # lines, menu, moves, list
    listing: str = ""                # bag or team
    keys: list[str] = []
    wait: float = 0.0
    letters: float = 0.0
    typing: bool = False
    shake: float = 0.0
    flash: float = 0.0
    last_foe_hp: int = 0
    last_ally_hp: int = 0
    foe_home: float = 0.0
    panels_shown: bool = False

    def on_start(self):
        audio.set_music(SESSION.save.options.music)
        foe_e = scene.find("foe")
        ally_e = scene.find("ally")
        if foe_e is not None and ally_e is not None:
            self.foe_home = foe_e.x
            foe_e.billboard.visible = False
            ally_e.billboard.visible = False
            stand_monster(foe_e.billboard, look(foe()), FRONT)
            stand_monster(ally_e.billboard, look(ally()), BACK)
        panel = self.entity.child("foe_panel")
        panel.y = panel.y - (game.view_height - game.height)        # at the top of any screen; the rest is at the bottom
        panel.active = False
        self.entity.child("ally_panel").active = False
        self.show_buttons()

    # ── what is on the screen ────────────────────────────────────────────

    def show_buttons(self):
        menu = self.mode == "menu"
        moves = self.mode == "moves"
        self.entity.child("fight").active = menu
        self.entity.child("bag").active = menu
        self.entity.child("team").active = menu
        self.entity.child("run").active = menu
        self.entity.child("m0").active = moves
        self.entity.child("m1").active = moves
        self.entity.child("m2").active = moves
        self.entity.child("m3").active = moves
        self.entity.child("back").active = moves or self.mode == "list"
        self.list.visible = self.mode == "list"
        self.entity.child("ally_panel").active = self.mode != "list" and self.panels_shown
        if self.mode != "list":
            self.list.count = 0
        if menu:
            self.say_now(named("what_will", display_name(ally())))
        if moves:
            self.fill_moves()

    def say_now(self, words: str):
        t = self.entity.child("words").text
        t.text = words
        t.visible_chars = -1

    def fill_moves(self):
        a = ally()
        i = 0
        while i < 4:
            e = self.entity.child("m" + str(i))
            if i < len(a.moves):
                slot = a.moves[i]
                move = MOVES.get(slot.move)
                e.button.label = move.name + " " + str(slot.pp)
                e.button.enabled = slot.pp > 0
                e.button.text.set_color(TYPES.get(move.type).color)
            else:
                e.button.label = "-"
                e.button.enabled = False
            i += 1

    def refresh_panels(self):
        a = ally()
        f = foe()
        self.panels_shown = True
        p = self.entity.child("ally_panel")
        p.active = self.mode != "list"
        p.child("name").text.text = display_name(a) + " " + word("level_short") + " " + str(a.level)
        p.child("hp").text.text = str(a.hp) + "/" + str(max_hp(a)) + " " + status_name(a)
        p.child("life").bar.max = float(max_hp(a))
        q = self.entity.child("foe_panel")
        q.active = True
        q.child("name").text.text = display_name(f) + " " + word("level_short") + " " + str(f.level) + " " + status_name(f)
        q.child("life").bar.max = float(max_hp(f))

    # ── playing the lines ────────────────────────────────────────────────

    def update(self, dt: float):
        self.animate(dt)
        if self.mode == "lines":
            self.play_lines(dt)
        elif self.mode == "menu":
            self.update_menu()
        elif self.mode == "moves":
            self.update_moves()
        elif self.mode == "list":
            self.update_list()

    def animate(self, dt: float):
        f = scene.find("foe")
        if f is None:
            return
        if self.shake > 0:
            self.shake -= dt
            f.x = self.foe_home + (2 if int(self.shake * 30) % 2 == 0 else -2)
        else:
            f.x = self.foe_home
        a = scene.find("ally")
        if self.flash > 0 and a is not None:
            self.flash -= dt
            a.billboard.visible = int(self.flash * 12) % 2 == 0 or self.flash <= 0

    def play_lines(self, dt: float):
        words = self.entity.child("words").text
        if self.typing:
            self.letters += SESSION.save.options.text_speed
            words.visible_chars = int(self.letters / 2)
            if input.pointer_pressed():
                words.visible_chars = words.page_chars
            if words.visible_chars >= words.page_chars:
                self.typing = False
                self.wait = 0.55
            return
        if self.wait > 0:
            self.wait -= dt
            if not input.pointer_pressed():
                return
            self.wait = 0.0
        if self.bars_moving():
            return
        if len(BATTLE.lines) > 0:
            self.show_line(BATTLE.lines.pop(0))
        elif BATTLE.over:
            self.leave()
        elif BATTLE.must_switch:
            self.open_list("team")
        else:
            self.mode = "menu"
            self.show_buttons()

    def bars_moving(self) -> bool:
        return (self.entity.child("foe_panel").child("life").bar.moving
                or self.entity.child("ally_panel").child("life").bar.moving
                or self.entity.child("ally_panel").child("exp").bar.moving)

    def type_out(self, words: str):
        t = self.entity.child("words").text
        t.text = words
        t.visible_chars = 0
        self.letters = 0.0
        self.typing = True

    def show_line(self, l: BattleLine):
        foe_e = scene.find("foe")
        ally_e = scene.find("ally")
        if foe_e is None or ally_e is None:
            return
        if l.text != "":
            self.type_out(l.text)
        k = l.kind
        if k == "hp":
            who = self.entity.child("foe_panel" if l.foe else "ally_panel")
            who.child("life").bar.value = float(l.value)
            audio.play(hit_sound)
            self.refresh_panels()
            self.shake = 0.3 if l.foe else 0.0
            self.flash = 0.0 if l.foe else 0.4
        elif k == "send":
            if l.foe:
                stand_monster(foe_e.billboard, l.name, FRONT)
                foe_e.billboard.visible = True
                f = foe()
                self.refresh_panels()
                bar = self.entity.child("foe_panel").child("life").bar
                bar.max = float(max_hp(f))
                bar.value = float(f.hp)
            else:
                a = ally()
                stand_monster(ally_e.billboard, l.name, BACK)
                ally_e.billboard.visible = True
                self.refresh_panels()
                bar = self.entity.child("ally_panel").child("life").bar
                bar.value = float(a.hp)
                self.entity.child("ally_panel").child("exp").bar.value = float(exp_progress(a))
            audio.play(tap_sound)
        elif k == "faint":
            (foe_e if l.foe else ally_e).billboard.visible = False
        elif k == "shake":
            foe_e.billboard.visible = False
            self.shake = 0.5
            self.wait = 0.6
            audio.play(tap_sound)
        elif k == "caught":
            foe_e.billboard.visible = False
            audio.play(catch_sound)
        elif k == "xp":
            self.entity.child("ally_panel").child("exp").bar.value = float(l.value)
        elif k == "level":
            audio.play(heal_sound)
            if l.value >= 0:
                self.entity.child("ally_panel").child("life").bar.value = float(l.value)
            self.refresh_panels()
        elif k == "evolve":
            stand_monster(ally_e.billboard, l.name, BACK)
            self.flash = 1.5
            audio.play(heal_sound)
        elif k == "end":
            self.wait = 0.3

    def leave(self):
        save = SESSION.save
        if BATTLE.won or first_able() >= 0:
            UI.restore_position = True
            BATTLE.won = BATTLE.won or BATTLE.wild
            game.goto(save.map, "", 0.5)
            return
        for m in save.team:
            heal_fully(m)
        UI.restore_position = False                 # lost: back at the Keeper's
        save.map = save.heal_map
        game.goto(save.heal_map, save.heal_at, 0.8)

    # ── asking the player ────────────────────────────────────────────────

    def update_menu(self):
        if self.entity.child("fight").button.clicked:
            self.mode = "moves"
            self.show_buttons()
        elif self.entity.child("bag").button.clicked:
            self.open_list("bag")
        elif self.entity.child("team").button.clicked:
            self.open_list("team")
        elif self.entity.child("run").button.clicked:
            self.begin_turn()
            run_away()

    def begin_turn(self):
        self.mode = "lines"
        self.show_buttons()

    def update_moves(self):
        if self.entity.child("back").button.clicked:
            self.mode = "menu"
            self.show_buttons()
            return
        a = ally()
        i = 0
        while i < len(a.moves):
            if self.entity.child("m" + str(i)).button.clicked:
                move = a.moves[i].move
                self.begin_turn()
                fight(move)
                return
            i += 1

    def open_list(self, what: str):
        self.mode = "list"
        self.listing = what
        self.keys.clear()
        if what == "bag":
            for k in SESSION.save.bag:
                if usable_in_battle(ITEMS.get(k)):
                    self.keys.append(k)
            self.list.count = len(self.keys)
            self.say_now(word("which_one"))
        else:
            self.list.count = len(SESSION.save.team)
            self.say_now(word("who_goes") if BATTLE.must_switch else word("team_list"))
        self.list.refresh()
        self.show_buttons()
        self.entity.child("back").active = not BATTLE.must_switch

    def on_row(self, row: Entity, index: int):
        if self.listing == "bag":
            if index < len(self.keys):
                key = self.keys[index]
                row.child("name").text.text = ITEMS.get(key).name
                row.child("detail").text.text = "x" + str(SESSION.save.bag.get(key, 0))
        elif index < len(SESSION.save.team):
            m = SESSION.save.team[index]
            row.child("name").text.text = display_name(m) + " " + word("level_short") + " " + str(m.level)
            row.child("detail").text.text = str(m.hp) + "/" + str(max_hp(m))

    def update_list(self):
        if self.entity.child("back").active and self.entity.child("back").button.clicked:
            self.mode = "menu"
            self.show_buttons()
            return
        tapped = self.list.tapped
        if tapped < 0:
            return
        if self.listing == "bag":
            if tapped < len(self.keys):
                key = self.keys[tapped]
                self.begin_turn()
                use_item(key, BATTLE.ally_at)
        elif tapped < len(SESSION.save.team):
            m = SESSION.save.team[tapped]
            if m.hp > 0 and (tapped != BATTLE.ally_at or BATTLE.must_switch):
                self.begin_turn()
                switch_to(tapped)


@prefab
def battle_row():
    return Entity("row", Panel(box, size=(222, 28)), children=[
        Entity("name", Text("", size=SIZE), ui=True, at=(-103, 3)),
        Entity("detail", Text("", size=SIZE, align="right"), ui=True, at=(103, 3)),
    ])


def status_name(m: Monster) -> str:
    return STATUSES.get(m.status).name if m.status != "" else ""


@prefab
def choice(name: str = "fight", label: str = "Fight", x: float = 0, y: float = 0, key: str = ""):
    return Entity(name, Button(label, size=(110, 34), image=box, text_size=SIZE, sound=tap_sound), ButtonWord(key=key), ui=True, at=(x, y))


@prefab
def battle_ui():
    return Entity("battle_ui", ScrollList(battle_row(), size=(226, 150), item_size=(226, 30), gap=2, pivot=(-0.0354, 0.7467)), Presenter(), ui=True,
                  anchor="bottom", at=(240, 228), children=[
        Entity("frame", Panel(box, size=(232, 76)), ui=True, at=(-122, 0)),
        Entity("words", Text("", size=SIZE, max_width=210, line_spacing=1.3), ui=True, at=(-228, -18)),
        choice("fight", "Fight", 64, -18, "fight"), choice("bag", "Bag", 178, -18, "bag"), choice("team", "Team", 64, 20, "team"), choice("run", "Run", 178, 20, "run"),
        choice("m0", "", 64, -18), choice("m1", "", 178, -18), choice("m2", "", 64, 20), choice("m3", "", 178, 20),
        Entity("back", Button("Back", size=(210, 22), image=box, text_size=SIZE, sound=tap_sound), ButtonWord(key="back"), ui=True, at=(-122, 22)),
        Entity("foe_panel", Panel(box, size=(160, 34), pivot=(0, 0)), ui=True, at=(-230, -220), children=[
            Entity("name", Text("", size=SIZE), ui=True, at=(8, 13)),
            Entity("life", Bar(1, size=(140, 6), back=LIFE_BACK, low_color=LIFE_LOW), ui=True, at=(8, 24)),
        ]),
        Entity("ally_panel", Panel(box, size=(160, 50), pivot=(0, 0)), ui=True, at=(70, -96), children=[
            Entity("name", Text("", size=SIZE), ui=True, at=(8, 13)),
            Entity("life", Bar(1, size=(140, 6), back=LIFE_BACK, low_color=LIFE_LOW), ui=True, at=(8, 21)),
            Entity("exp", Bar(0, max=1000, size=(140, 3), speed=0.8, color=EXP_COLOR, mid_color=EXP_COLOR, low_color=EXP_COLOR, back=EXP_BACK), ui=True, at=(8, 27)),
            Entity("hp", Text("", size=SIZE), ui=True, at=(8, 43)),
        ]),
    ])


@prefab
def foe_sprite():
    return Entity("foe", Billboard(monster_sheet))


@prefab
def ally_sprite():
    return Entity("ally", Billboard(monster_sheet))
