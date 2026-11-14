"""The rules run on plain Python, with your own data files: no game, no phone. They name no monster of the placeholder
story, so you can replace the story and they still tell you if something is wrong.

    python -m pytest tests
"""
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ["APKPYGAME_PROJECT"] = ROOT

from game.data.defs import ENCOUNTERS, ITEMS, MOVES, SPECIES, TYPES, game_info  # noqa: E402
from game.rules.combat import capture_shakes, damage, effectiveness, stage_factor, type_factor  # noqa: E402
from game.rules.monsters import evolves_now, exp_for_level, learn, make_monster, max_hp, stat  # noqa: E402
from game.state.store import MoveSlot  # noqa: E402
from game.world.encounters import pick_row  # noqa: E402
import validate_data  # noqa: E402


def any_species():
    return game_info().starters[0]


def test_the_content_holds_together():
    assert validate_data.check() == []


def test_type_chart_is_what_the_data_says():
    for t in TYPES:
        for other in t.strong:
            assert type_factor(t.id, other) == 2.0
        for other in t.weak:
            assert type_factor(t.id, other) == 0.5
        for other in t.immune:
            assert type_factor(t.id, other) == 0.0


def test_two_types_multiply():
    move = next(iter(MOVES))
    for s in SPECIES:
        if len(s.types) == 2:
            expected = type_factor(move.type, s.types[0]) * type_factor(move.type, s.types[1])
            assert effectiveness(move, make_monster(s.id, 10)) == expected


def test_a_new_monster():
    random.seed(1)
    m = make_monster(any_species(), 5)
    known = [row.move for row in SPECIES.get(m.species).learnset if row.level <= 5][-4:]
    assert m.hp == max_hp(m) > 10
    assert [s.move for s in m.moves] == known
    assert m.exp == exp_for_level(5)
    assert all(0 <= v <= 31 for v in (m.iv.hp, m.iv.attack, m.iv.defense, m.iv.special, m.iv.speed))


def test_levels_raise_stats_and_evolution_has_its_level():
    random.seed(2)
    for s in SPECIES:
        if s.evolves_to:
            m = make_monster(s.id, max(1, s.evolve_level - 1))
            assert evolves_now(m) == ""
            low = stat(m, "special")
            m.level = s.evolve_level
            assert evolves_now(m) == s.evolves_to
            m.level = 50
            assert stat(m, "special") > low


def test_a_fifth_move_pushes_the_oldest_out():
    names = [move.id for move in MOVES]
    m = make_monster(any_species(), 5)
    m.moves = [MoveSlot(name, 1) for name in names[:4]]
    assert learn(m, names[4]) is True
    assert [s.move for s in m.moves] == names[1:5]
    assert learn(m, names[4]) is False


def test_damage_grows_with_what_it_should():
    base = damage(10, 40, 20, 20, 1.0, False, False, 100)
    assert damage(10, 80, 20, 20, 1.0, False, False, 100) > base
    assert damage(10, 40, 20, 20, 2.0, False, False, 100) > base
    assert damage(10, 40, 20, 20, 1.0, True, False, 100) > base
    assert damage(10, 40, 20, 20, 0.0, False, False, 100) == 0
    assert damage(1, 1, 1, 200, 0.5, False, False, 85) == 1
    assert stage_factor(2) == 2.0 and stage_factor(-2) == 0.5


def test_a_tired_monster_is_easier_to_bond():
    random.seed(3)

    def caught(hp, status=""):
        return sum(capture_shakes(100, hp, 45, 10, status) == 3 for _ in range(2000))

    assert caught(1) > caught(100)
    assert caught(50, "sleep") > caught(50)
    assert capture_shakes(100, 1, 255, 40, "sleep") == 3


def test_encounters_respect_their_weights():
    random.seed(4)
    for table in ENCOUNTERS:
        picks = [pick_row(table).species for _ in range(3000)]
        heavy = max(table.rows, key=lambda r: r.weight)
        light = min(table.rows, key=lambda r: r.weight)
        if heavy.weight >= light.weight * 2 and heavy.species != light.species:
            assert picks.count(heavy.species) > picks.count(light.species)


def test_the_first_fights_are_fair():
    import balance
    balance.PLAYS = 60
    random.seed(5)
    for name, level, begin in balance.fights(only_fair=True):
        for starter in balance.starters():
            won, _ = balance.rate(starter, level, begin)
            assert won >= 0.8, "%s against %s: %d%% of wins" % (starter, name, won * 100)


def test_losing_a_battle():
    from game.battle.engine import begin_wild, fight
    from game.state.store import BATTLE, SESSION, Save
    SESSION.save = Save(money=500)
    m = make_monster(any_species(), 5)
    m.hp = 1
    SESSION.save.team.append(m)
    begin_wild(any_species(), 50)
    for _ in range(20):
        if not BATTLE.over:
            fight(m.moves[0].move)
    assert BATTLE.over and not BATTLE.won and SESSION.save.money == 250


def test_every_capture_item_holds_something():
    assert all(i.capture > 0 for i in ITEMS if i.kind == "capture")
