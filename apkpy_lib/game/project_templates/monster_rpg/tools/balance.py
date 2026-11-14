"""How hard are the first fights? Plays each one many times on the real rules, always with the strongest move, no items.

    python tools/balance.py

Prints how often the partner wins and how much HP it has left. Change levels in data/ and run it again.
"""
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["APKPYGAME_PROJECT"] = ROOT

from game.battle.engine import ally, begin_trainer, begin_wild, fight, first_able, switch_to  # noqa: E402
from game.data.defs import ENCOUNTERS, MOVES, TRAINERS, game_info  # noqa: E402
from game.rules.combat import effectiveness  # noqa: E402
from game.rules.monsters import make_monster, max_hp  # noqa: E402
from game.state.store import BATTLE, SESSION, Save  # noqa: E402

PLAYS = 400


def starters():
    return game_info().starters


def strongest(m, foe):
    best, score = m.moves[0].move, -1.0
    for slot in m.moves:
        move = MOVES.get(slot.move)
        value = move.power * effectiveness(move, foe)
        if slot.pp > 0 and value > score:
            best, score = slot.move, value
    return best


def play(starter, level, begin):
    """One fight from full HP: (won, fraction of HP left)."""
    SESSION.save = Save()
    SESSION.save.team.append(make_monster(starter, level))
    begin()
    for _ in range(200):
        if BATTLE.over:
            break
        if BATTLE.must_switch:
            switch_to(first_able())
            continue
        fight(strongest(ally(), BATTLE.foes[BATTLE.foe_at]))
    m = SESSION.save.team[0]
    return BATTLE.won, m.hp / max_hp(m)


def rate(starter, level, begin):
    wins, left = 0, 0.0
    for _ in range(PLAYS):
        won, hp = play(starter, level, begin)
        wins += 1 if won else 0
        left += hp
    return wins / PLAYS, left / PLAYS


def fights(only_fair=False):
    """(name, level of the partner by then, how it starts). only_fair: those in fair_fights in data/game.json, which the tests check."""
    fair = game_info().fair_fights
    out = []
    for table in ENCOUNTERS:
        if only_fair and table.id not in fair:
            continue
        for row in table.rows:
            out.append(("%s: %s L%d" % (table.id, row.species, row.max), game_info().starter_level,
                        lambda s=row.species, l=row.max: begin_wild(s, l)))
    for t in TRAINERS:
        if only_fair and t.id not in fair:
            continue
        out.append((t.name, t.expect_level or game_info().starter_level, lambda who=t.id: begin_trainer(who)))
    return out


def main():
    random.seed(1)
    print("%-32s %s" % ("", "  ".join("%-12s" % s for s in starters())))
    for name, level, begin in fights():
        cells = []
        for s in starters():
            won, left = rate(s, level, begin)
            cells.append("%3d%% hp %3d%% " % (won * 100, left * 100))
        print("%-32s %s" % (name, "  ".join(cells)))


if __name__ == "__main__":
    main()
