"""What the data files look like. Each @dataclass is the schema of a table: the build checks every row against it.

To add a field: add it here (with a default) and use it; old rows keep working.
"""
from __future__ import annotations

from apkpy_lib.game import *
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Type:
    """data/types.json. strong, weak, immune: what its moves do to those types (x2, x0.5, x0)."""
    id: str
    name: str
    color: str
    strong: list[Ref[Type]] = field(default_factory=list)
    weak: list[Ref[Type]] = field(default_factory=list)
    immune: list[Ref[Type]] = field(default_factory=list)


@dataclass
class Status:
    """data/statuses.json: what a monster can suffer from until it is cured. The texts can say {name}."""
    id: str
    name: str
    apply_text: str = ""
    turn_share: int = 0            # it loses 1/turn_share of its HP each turn (0: none)
    turn_text: str = ""
    attack_factor: float = 1.0     # its physical moves hit this much
    min_turns: int = 0             # it misses between min_turns and max_turns turns, then it is over (0: never)
    max_turns: int = 0
    still_text: str = ""
    wake_text: str = ""
    capture_bonus: float = 1.5     # easier to catch


@dataclass
class Effect:
    """data/effects.json: what a move does besides its damage. target: foe or self. text can say {name}."""
    id: str
    name: str
    status: Optional[Ref[Status]] = None
    stat: str = ""                 # attack, defense, special or speed
    amount: int = 0                # how many steps it goes up (or down, below 0)
    target: str = "foe"
    heal_percent: int = 0          # of its whole HP
    text: str = ""


@dataclass
class Move:
    """data/moves.json. kind: physical, special or status. effect: one of data/effects.json, with chance its % of happening."""
    id: str
    name: str
    type: Ref[Type]
    kind: str
    power: int
    accuracy: int
    pp: int
    effect: Optional[Ref[Effect]] = None
    chance: int = 0
    description: str = ""


@dataclass
class Item:
    """data/items.json. kind: the pocket of the bag it goes in (heal, cure, capture or key). What it does is in its other fields."""
    id: str
    name: str
    kind: str
    heal: int = 0                  # HP it gives back
    cures: list[Ref[Status]] = field(default_factory=list)
    cures_all: bool = False
    revive: bool = False           # it works on a monster that fainted
    capture: int = 0               # how well it catches: 10 is normal, more is better
    price: int = 0
    description: str = ""


@dataclass
class BaseStats:
    hp: int
    attack: int
    defense: int
    special: int
    speed: int


@dataclass
class Learned:
    level: int
    move: Ref[Move]


@dataclass
class Variant:
    """Another look of a species, and only its look: its sprites are assets/monsters/<species>.<id>.png.
    one_in: a wild one has it 1 time in this many (0: never in the wild; a trainer can still have it)."""
    id: str
    name: str
    one_in: int = 0


@dataclass
class Species:
    """data/species/<id>.json, one per file. Its sprites are assets/monsters/<id>.png, and its variants' beside them."""
    id: str
    name: str
    types: list[Ref[Type]]
    base: BaseStats
    learnset: list[Learned]
    catch_rate: int
    exp_yield: int
    ev_stat: str = "hp"
    description: str = ""
    evolves_to: Optional[Ref[Species]] = None
    evolve_level: int = 0
    evolve_item: Optional[Ref[Item]] = None     # it evolves when this item is used on it, instead of by level
    evolve_flag: str = ""                       # and only once this flag is set
    variants: list[Variant] = field(default_factory=list)


@dataclass
class Nature:
    """data/natures.json. up and down: a stat (+10% and -10%), or empty."""
    id: str
    name: str
    up: str = ""
    down: str = ""


@dataclass
class EncounterRow:
    species: Ref[Species]
    min: int
    max: int
    weight: int


@dataclass
class EncounterTable:
    """data/encounters.json. id: <map>.<zone> (a tile's "zone"). rate: % per step on that tile."""
    id: str
    rate: int
    rows: list[EncounterRow]


@dataclass
class TrainerMonster:
    """variant: one of its species' variants, or "default" (or empty) for its usual look."""
    species: Ref[Species]
    level: int
    variant: str = ""


@dataclass
class Trainer:
    """data/trainers.json. expect_level: how strong your partner should be by then (tools/balance.py; 0 is its first level)."""
    id: str
    name: str
    team: list[TrainerMonster]
    reward: int = 0
    lose_text: str = ""
    expect_level: int = 0


@dataclass
class Shop:
    """data/shops.json."""
    id: str
    name: str
    items: list[Ref[Item]]


@dataclass
class Step:
    """One step of an event. do: what to do (the list is in game/world/events.py and README.md)."""
    do: str
    text: str = ""
    flag: str = ""
    to: str = ""
    at: str = ""
    item: str = ""
    count: int = 1
    trainer: str = ""
    shop: str = ""
    screen: str = ""
    species: str = ""
    level: int = 5


@dataclass
class Event:
    """data/events/*.json: a file holds a list of events. Named by the "event" property of map objects."""
    id: str
    steps: list[Step]


@dataclass
class GameInfo:
    """data/game.json: how the game starts, and the words of your story that the rules say."""
    id: str
    start_map: str
    start_at: str
    first_event: Ref[Event]
    money: int
    heal_map: str
    heal_at: str
    starters: list[Ref[Species]]
    starter_level: int
    title_giant: Ref[Species]
    title_visitors: list[Ref[Species]]
    fair_fights: list[str]
    currency: str
    no_flee_text: str
    owned_text: str
    lost_text: str


@dataclass
class Rules:
    """data/rules.json: the numbers of the rules."""
    id: str
    critical_percent: int = 6
    critical_factor: float = 1.5
    same_type_factor: float = 1.5          # a move of one of the user's own types
    max_moves: int = 4
    max_level: int = 100
    team_size: int = 6
    stage_limit: int = 4                   # how far a stat can go up or down in a battle
    exp_factor: float = 1.0                # the experience of a level: level x level x level x this
    exp_share_percent: int = 50            # what the others in the team get
    ev_gain: int = 2
    lost_money_percent: int = 50
    flee_speed_factor: int = 2
    flee_per_try: int = 30
    nature_percent: int = 10
    status_damage_minimum: int = 1


@dataclass
class Words:
    """data/texts.json: the words the game says. {name}, {count} and the like are filled in. {currency} is from data/game.json."""
    id: str
    text: str


TYPES = table("data/types", Type)
STATUSES = table("data/statuses", Status)
EFFECTS = table("data/effects", Effect)
MOVES = table("data/moves", Move)
SPECIES = table("data/species", Species)
ITEMS = table("data/items", Item)
NATURES = table("data/natures", Nature)
ENCOUNTERS = table("data/encounters", EncounterTable)
TRAINERS = table("data/trainers", Trainer)
SHOPS = table("data/shops", Shop)
EVENTS = table("data/events", Event)
GAME_INFO = table("data/game", GameInfo)
RULES = table("data/rules", Rules)
TEXTS = table("data/texts", Words)


def game_info() -> GameInfo:
    return GAME_INFO.get("main")


def rules() -> Rules:
    return RULES.get("main")


def word(key: str) -> str:
    """The words of data/texts.json for that id, with the name of the money filled in."""
    if key not in TEXTS:
        return key
    return TEXTS.get(key).text.replace("{currency}", game_info().currency)


def fill(text: str, key: str, value: str) -> str:
    """fill(word("uses"), "move", "Bump"): {move} becomes Bump."""
    return text.replace("{" + key + "}", value)


def named(key: str, name: str) -> str:
    """The words, with {name} filled in."""
    return fill(word(key), "name", name)
