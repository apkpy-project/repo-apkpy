"""The formulas of a battle: type chart, damage, capture. Pure rules: also run by pytest."""

from __future__ import annotations

import math
import random

from game.data.defs import MOVES, SPECIES, STATUSES, TYPES, Move, rules
from game.state.store import Monster

CAPTURE_CHECKS = 3


def type_factor(move_type: str, defender: str) -> float:
    t = TYPES.get(move_type)
    if defender in t.immune:
        return 0.0
    if defender in t.strong:
        return 2.0
    if defender in t.weak:
        return 0.5
    return 1.0


def effectiveness(move: Move, target: Monster) -> float:
    factor = 1.0
    for t in SPECIES.get(target.species).types:
        factor = factor * type_factor(move.type, t)
    return factor


def stage_factor(stage: int) -> float:
    return (2.0 + stage) / 2.0 if stage >= 0 else 2.0 / (2.0 - stage)


def damage(level: int, power: int, attack: float, defense: float, factor: float, same_type: bool, critical: bool, roll: int) -> int:
    """roll: 85 to 100. At least 1, unless the type gives nothing at all."""
    if factor == 0.0:
        return 0
    base = (2 * level // 5 + 2) * power * attack / max(1.0, defense) / 50 + 2
    if same_type:
        base = base * rules().same_type_factor
    if critical:
        base = base * rules().critical_factor
    return max(1, int(base * factor * roll / 100))


def hit_damage(attacker: Monster, attack: float, defense: float, target: Monster, move: Move, critical: bool) -> int:
    same = move.type in SPECIES.get(attacker.species).types
    return damage(attacker.level, move.power, attack, defense, effectiveness(move, target), same, critical, random.randint(85, 100))


def capture_shakes(max_hp: int, hp: int, rate: int, knot: int, status: str) -> int:
    """How many checks pass (CAPTURE_CHECKS: caught). knot: the item's value (10 is the plain one)."""
    status_bonus = STATUSES.get(status).capture_bonus if status != "" else 1.0
    a = (3 * max_hp - 2 * hp) * rate * (knot / 10.0) / (3 * max_hp) * status_bonus
    if a >= 255:
        return CAPTURE_CHECKS
    chance = math.pow(a / 255.0, 0.25)
    shakes = 0
    for i in range(CAPTURE_CHECKS):
        if random.random() >= chance:
            return shakes
        shakes += 1
    return shakes


def best_move(foe: Monster, target: Monster) -> str:
    """The trainer's choice: what hits hardest, by a little guessing; wild monsters use random_move."""
    best = ""
    score = -1.0
    for slot in foe.moves:
        if slot.pp <= 0:
            continue
        m = MOVES.get(slot.move)
        value = m.power * effectiveness(m, target) if m.power > 0 else 15.0
        value = value * (0.9 + random.random() * 0.2)
        if value > score:
            score = value
            best = slot.move
    return best


def random_move(foe: Monster) -> str:
    usable: list[str] = []
    for slot in foe.moves:
        if slot.pp > 0:
            usable.append(slot.move)
    return random.choice(usable) if len(usable) > 0 else ""
