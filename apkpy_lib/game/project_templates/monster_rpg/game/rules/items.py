"""What an item does to a monster: pure rules, used in battles and in the bag."""
from game.data.defs import ITEMS, SPECIES, Item
from game.rules.monsters import become, max_hp
from game.state.store import Monster


def cures(item: Item, m: Monster) -> bool:
    return m.status != "" and (item.cures_all or m.status in item.cures)


def helps(item: Item, m: Monster) -> bool:
    """Would it do anything to this one now?"""
    if m.hp <= 0:
        return item.revive
    return (item.heal > 0 and m.hp < max_hp(m)) or cures(item, m)


def usable_in_battle(item: Item) -> bool:
    return item.heal > 0 or item.capture > 0 or item.cures_all or len(item.cures) > 0


def apply(item: Item, m: Monster) -> None:
    if m.hp <= 0 and item.revive:
        m.hp = max(1, item.heal if item.heal > 0 else max_hp(m) // 2)
    elif item.heal > 0:
        m.hp = min(max_hp(m), m.hp + item.heal)
    if cures(item, m):
        m.status = ""
        m.sleep_turns = 0


def evolves_with(item_id: str, m: Monster) -> str:
    """The species it becomes with this item, or empty."""
    s = SPECIES.get(m.species)
    if s.evolve_item is not None and s.evolve_item == item_id and s.evolves_to is not None:
        return s.evolves_to
    return ""


def evolve_with(item_id: str, m: Monster) -> None:
    become(m, evolves_with(item_id, m))
