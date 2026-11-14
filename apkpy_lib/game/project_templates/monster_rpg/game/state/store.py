"""Everything that lasts: what is saved (Save), and what scripts tell each other (Ui, EventRun, BattleRun).

SESSION.save is the save file (game/state/new_game.py makes a new one). The rest is rebuilt when a game starts. Scripts change these; they never hold
state of their own that another scene needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Stats:
    hp: int = 0
    attack: int = 0
    defense: int = 0
    special: int = 0
    speed: int = 0


@dataclass
class MoveSlot:
    move: str
    pp: int


@dataclass
class Monster:
    species: str
    level: int
    exp: int = 0
    hp: int = 1
    nickname: str = ""
    nature: str = "steady"
    status: str = ""
    sleep_turns: int = 0
    iv: Stats = field(default_factory=Stats)
    ev: Stats = field(default_factory=Stats)
    moves: list[MoveSlot] = field(default_factory=list)
    variant: str = ""             # its look (data/species: variants); empty is the usual one


@dataclass
class Options:
    music: bool = True
    sound: float = 1.0
    text_speed: float = 2.0


@dataclass
class Save:
    version: int = 1
    player: str = "Player"
    money: int = 0
    map: str = ""
    x: float = 0.0
    y: float = 0.0
    steps: int = 0
    heal_map: str = ""
    heal_at: str = ""
    team: list[Monster] = field(default_factory=list)
    box: list[Monster] = field(default_factory=list)
    bag: dict[str, int] = field(default_factory=dict)
    flags: dict[str, int] = field(default_factory=dict)
    seen: dict[str, int] = field(default_factory=dict)
    caught: dict[str, int] = field(default_factory=dict)
    options: Options = field(default_factory=Options)


@dataclass
class Session:
    save: Save = field(default_factory=Save)


@dataclass
class Ui:
    """The world's interface, between scripts."""
    say: str = ""                 # the dialog box shows this; it empties it when read
    asking: bool = False          # with Yes / No
    answer: bool = False
    screen: str = ""              # the open screen (team, bag, shop...): the world waits
    shop: str = ""
    press_a: bool = False         # the A button was pressed
    restore_position: bool = False       # the hero goes back to save.x, save.y
    step_back: bool = False
    autosave: bool = False        # a warp: the hero saves where it arrives


@dataclass
class EventRun:
    """The event being played. It lives here so it goes on after a battle or a warp."""
    active: bool = False
    event: str = ""
    at: int = 0
    waiting: str = ""


@dataclass
class BattleLine:
    """What the presenter shows next. kind: say, hp, faint, send, shake, caught, level, evolve, end."""
    kind: str
    text: str = ""
    foe: bool = False
    value: int = 0
    name: str = ""


@dataclass
class BattleRun:
    foes: list[Monster] = field(default_factory=list)
    foe_at: int = 0
    ally_at: int = 0
    trainer: str = ""
    wild: bool = True
    lines: list[BattleLine] = field(default_factory=list)
    ally_attack: int = 0
    ally_defense: int = 0
    ally_special: int = 0
    ally_speed: int = 0
    foe_attack: int = 0
    foe_defense: int = 0
    foe_special: int = 0
    foe_speed: int = 0
    won: bool = False
    over: bool = False
    must_switch: bool = False
    flee_tries: int = 0
    used_item: str = ""


SESSION = Session()
UI = Ui()
RUN = EventRun()
BATTLE = BattleRun()


def has_flag(name: str) -> bool:
    return SESSION.save.flags.get(name, 0) != 0


def set_flag(name: str) -> None:
    SESSION.save.flags[name] = 1


def add_item(item: str, count: int) -> None:
    bag = SESSION.save.bag
    left = bag.get(item, 0) + count
    if left <= 0:
        if item in bag:
            bag.pop(item)
    else:
        bag[item] = left
