"""The numbers of a monster: stats, levels, experience, how one is made. Pure rules: also run by pytest."""
import random

from game.data.defs import MOVES, NATURES, SPECIES, BaseStats, Species, rules, word
from game.state.store import SESSION, MoveSlot, Monster, Stats, has_flag


def display_name(m: Monster) -> str:
    return m.nickname if m.nickname != "" else SPECIES.get(m.species).name


def look(m: Monster) -> str:
    """The name of its sheet in assets/monsters: its species, or <species>.<variant>."""
    if m.variant == "":
        return m.species
    return m.species + "." + m.variant


def has_variant(species: str, variant: str) -> bool:
    for v in SPECIES.get(species).variants:
        if v.id == variant:
            return True
    return False


def variant_name(m: Monster) -> str:
    """What the player reads: the variant's name, or "default"."""
    for v in SPECIES.get(m.species).variants:
        if v.id == m.variant:
            return v.name
    return word("default_variant")


def wild_variant(species: str) -> str:
    """A wild one's look: each variant has its chance, in its order. A species with no variants rolls nothing."""
    for v in SPECIES.get(species).variants:
        if v.one_in > 0 and random.randint(1, v.one_in) == 1:
            return v.id
    return ""


def nature_factor(nature: str, stat: str) -> float:
    n = NATURES.get(nature)
    if n.up == stat:
        return (100 + rules().nature_percent) / 100.0
    if n.down == stat:
        return (100 - rules().nature_percent) / 100.0
    return 1.0


def base_of(base: BaseStats, stat: str) -> int:
    if stat == "attack":
        return base.attack
    if stat == "defense":
        return base.defense
    if stat == "special":
        return base.special
    if stat == "speed":
        return base.speed
    return base.hp


def stats_get(s: Stats, stat: str) -> int:
    if stat == "attack":
        return s.attack
    if stat == "defense":
        return s.defense
    if stat == "special":
        return s.special
    if stat == "speed":
        return s.speed
    return s.hp


def max_hp(m: Monster) -> int:
    base = SPECIES.get(m.species).base.hp
    return (2 * base + m.iv.hp + m.ev.hp // 4) * m.level // 100 + m.level + 10


def stat(m: Monster, name: str) -> int:
    base = base_of(SPECIES.get(m.species).base, name)
    raw = (2 * base + stats_get(m.iv, name) + stats_get(m.ev, name) // 4) * m.level // 100 + 5
    return int(raw * nature_factor(m.nature, name))


def exp_for_level(level: int) -> int:
    """The experience a monster has at the start of a level (everyone grows alike here; add curves if you want)."""
    return int(level * level * level * rules().exp_factor)


def exp_to_next(m: Monster) -> int:
    return exp_for_level(m.level + 1) - m.exp


def exp_progress(m: Monster) -> int:
    """How far through its level, from 0 to 1000 (for a bar)."""
    start = exp_for_level(m.level)
    return (m.exp - start) * 1000 // max(1, exp_for_level(m.level + 1) - start)


def learn(m: Monster, move: str) -> bool:
    """False when it already knows it. Over the limit, the oldest move goes."""
    for slot in m.moves:
        if slot.move == move:
            return False
    if len(m.moves) >= rules().max_moves:
        m.moves.pop(0)
    m.moves.append(MoveSlot(move, MOVES.get(move).pp))
    return True


def make_monster(species: str, level: int) -> Monster:
    """A new one: random individual values and nature; the last moves it would have learned by now."""
    s = SPECIES.get(species)
    natures = NATURES.all()
    iv = Stats(random.randint(0, 31), random.randint(0, 31), random.randint(0, 31), random.randint(0, 31), random.randint(0, 31))
    m = Monster(species, level, exp=exp_for_level(level), nature=random.choice(natures).id, iv=iv)
    for entry in s.learnset:
        if entry.level <= level:
            learn(m, entry.move)
    m.hp = max_hp(m)
    return m


def heal_fully(m: Monster) -> None:
    m.hp = max_hp(m)
    m.status = ""
    for slot in m.moves:
        slot.pp = MOVES.get(slot.move).pp


def add_ev(m: Monster, stat_name: str, amount: int) -> None:  # noqa: C901
    if stat_name == "attack":
        m.ev.attack = min(252, m.ev.attack + amount)
    elif stat_name == "defense":
        m.ev.defense = min(252, m.ev.defense + amount)
    elif stat_name == "special":
        m.ev.special = min(252, m.ev.special + amount)
    elif stat_name == "speed":
        m.ev.speed = min(252, m.ev.speed + amount)
    else:
        m.ev.hp = min(252, m.ev.hp + amount)


def evolves_now(m: Monster) -> str:
    """The species it becomes now, by its level, or empty. One that evolves with an item waits for it (game/rules/items.py)."""
    s: Species = SPECIES.get(m.species)
    target = s.evolves_to
    if target is None or s.evolve_item is not None:
        return ""
    if s.evolve_flag != "" and not has_flag(s.evolve_flag):
        return ""
    if s.evolve_level > 0 and m.level >= s.evolve_level:
        return target
    return ""


def become(m: Monster, target: str) -> None:
    """It evolves: full HP, and now seen and bonded. It keeps its variant if the new species has one with the same id."""
    m.species = target
    if m.variant != "" and not has_variant(target, m.variant):
        m.variant = ""
    m.hp = max_hp(m)
    SESSION.save.seen[target] = 1
    SESSION.save.caught[target] = 1
