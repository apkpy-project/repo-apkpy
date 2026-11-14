"""Events: the steps in data/events/*.json, played one at a time. You write most of them as text in story/, and
tools/story_tool.py turns that into these steps.

The steps ("do"):
    say text                 the dialog box
    ask text to              Yes / No: Yes jumps to the label "to"
    label to                 a place to jump to
    jump to                  jumps
    jump_if flag to          jumps when the flag is set
    jump_unless flag to      jumps when it is not
    end                      stops here
    set_flag flag / clear_flag flag
    give_item item count / give_money count / give_monster species level
    heal                     the whole team
    open screen              opens a screen, waits for it to close
    shop shop                opens that shop
    battle trainer           a fight; if you lose, the event stops
    warp to at               another map, at a marker
    step_back                the hero goes back one cell
To add one: a new "elif" in EventRunner.do, then use it in the data (tools/validate_data.py knows the list: add it there too).
"""

from __future__ import annotations

from apkpy_lib.game import *

from game.battle.engine import begin_trainer
from game.data.defs import EVENTS, ITEMS, Step, fill, game_info, named, word
from game.rules.monsters import display_name, heal_fully, make_monster
from game.state.store import BATTLE, RUN, SESSION, UI, add_item, has_flag, set_flag


def start_event(event: str) -> None:
    if event != "" and not RUN.active:
        RUN.active = True
        RUN.event = event
        RUN.at = 0
        RUN.waiting = ""


class EventRunner(Script):
    """On the Hud of every map. The event's place is kept in RUN, so it goes on after a battle or a warp."""

    def update(self, dt: float):
        guard = 0
        while RUN.active and guard < 64:
            guard += 1
            if not self.go_on():
                return

    def go_on(self) -> bool:
        """True: the next step can run now."""
        steps = EVENTS.get(RUN.event).steps
        if RUN.waiting == "say":
            if UI.say != "":
                return False
        elif RUN.waiting == "ask":
            if UI.asking:
                return False
            if UI.answer:
                self.jump(steps, steps[RUN.at - 1].to)
        elif RUN.waiting == "screen":
            if UI.screen != "":
                return False
        elif RUN.waiting == "battle":
            if not BATTLE.won:
                RUN.active = False
                return False
        RUN.waiting = ""
        if RUN.at >= len(steps):
            RUN.active = False
            return False
        step = steps[RUN.at]
        RUN.at += 1
        self.do(step, steps)
        return RUN.active and RUN.waiting == ""

    def jump(self, steps: list[Step], label: str):
        i = 0
        for s in steps:
            if s.do == "label" and s.to == label:
                RUN.at = i + 1
                return
            i += 1
        RUN.active = False

    def do(self, s: Step, steps: list[Step]):
        d = s.do
        save = SESSION.save
        if d == "say":
            UI.say = s.text
            RUN.waiting = "say"
        elif d == "ask":
            UI.say = s.text
            UI.asking = True
            RUN.waiting = "ask"
        elif d == "jump":
            self.jump(steps, s.to)
        elif d == "jump_if":
            if has_flag(s.flag):
                self.jump(steps, s.to)
        elif d == "jump_unless":
            if not has_flag(s.flag):
                self.jump(steps, s.to)
        elif d == "end":
            RUN.active = False
        elif d == "set_flag":
            set_flag(s.flag)
        elif d == "clear_flag":
            save.flags.pop(s.flag)
        elif d == "give_item":
            add_item(s.item, s.count)
            UI.say = fill(fill(word("got_item"), "item", ITEMS.get(s.item).name), "count", str(s.count))
            RUN.waiting = "say"
        elif d == "give_money":
            save.money += s.count
            UI.say = fill(word("got_money"), "count", str(s.count))
            RUN.waiting = "say"
        elif d == "give_monster":
            m = make_monster(s.species, s.level)
            save.team.append(m)
            save.seen[s.species] = 1
            save.caught[s.species] = 1
            UI.say = named("joins", display_name(m))
            RUN.waiting = "say"
        elif d == "heal":
            for m in save.team:
                heal_fully(m)
        elif d == "open":
            UI.screen = s.screen
            RUN.waiting = "screen"
        elif d == "shop":
            UI.shop = s.shop
            UI.screen = "shop"
            RUN.waiting = "screen"
        elif d == "battle":
            begin_trainer(s.trainer)
            UI.restore_position = True
            RUN.waiting = "battle"
            game.goto("battle", "", 0.5)
        elif d == "warp":
            save.map = s.to
            UI.autosave = True
            game.goto(s.to, s.at, 0.4)
        elif d == "step_back":
            UI.step_back = True
