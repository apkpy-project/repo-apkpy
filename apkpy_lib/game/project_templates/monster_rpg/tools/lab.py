"""What the Studio asks the game's rules, on plain Python and your saved files: no game window. It reads JSON and writes JSON.

    python tools/lab.py save    < {"team": [["cindlet", 5]], "items": {"tonic": 3}, "flags": ["got_partner"], "money": 500, "map": "route"}
    python tools/lab.py fight   < {"team": [["cindlet", 5]], "wild": ["pebblit", 3], "plays": 200}
    python tools/lab.py fight   < {"team": [["cindlet", 5]], "trainer": "bram", "plays": 200}
    python tools/lab.py balance < {"plays": 100}
"""
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ["APKPYGAME_PROJECT"] = ROOT
sys.dont_write_bytecode = True

from apkpy_lib.game._data import to_json  # noqa: E402

import balance  # noqa: E402
from game.battle.engine import ally, begin_trainer, begin_wild, fight, first_able, switch_to  # noqa: E402
from game.data.defs import ENCOUNTERS, TRAINERS, game_info  # noqa: E402
from game.rules.monsters import make_monster, max_hp  # noqa: E402
from game.state.new_game import new_save  # noqa: E402
from game.state.store import BATTLE, SESSION, Save  # noqa: E402


def team_of(rows):
    return [make_monster(kind, int(level)) for kind, level in rows]


def make_save(q):
    """A game as a test should start it. The text is what the game reads: from_json(text, Save)."""
    save = new_save()
    save.team = team_of(q.get("team") or [[game_info().starters[0], game_info().starter_level]])
    for m in save.team:
        save.seen[m.species] = 1
        save.caught[m.species] = 1
    for item, count in (q.get("items") or {}).items():
        if int(count) > 0:
            save.bag[item] = int(count)
    for flag in q.get("flags") or []:
        save.flags[flag] = 1
    if q.get("money") is not None:
        save.money = int(q["money"])
    if q.get("map"):
        save.map = q["map"]
    return {"save": to_json(save)}


def play_once(team, begin):
    """One fight, always with the strongest move, no items: (won, share of HP left, turns, what happened)."""
    SESSION.save = Save()
    SESSION.save.team = team_of(team)
    begin()
    turns = 0
    for _ in range(300):
        if BATTLE.over:
            break
        if BATTLE.must_switch:
            switch_to(first_able())
            continue
        balance_move = balance.strongest(ally(), BATTLE.foes[BATTLE.foe_at])
        fight(balance_move)
        turns += 1
    left = sum(m.hp for m in SESSION.save.team)
    whole = sum(max_hp(m) for m in SESSION.save.team) or 1
    return BATTLE.won, left / whole, turns, [l.text for l in BATTLE.lines if l.text]


def run_fight(q):
    if q.get("trainer"):
        begin = lambda: begin_trainer(q["trainer"])
    else:
        kind, level = q["wild"]
        begin = lambda: begin_wild(kind, int(level))
    random.seed(q.get("seed", 1))
    plays = int(q.get("plays", 200))
    wins, left, turns, sample = 0, 0.0, 0, []
    for i in range(plays):
        won, hp, count, lines = play_once(q["team"], begin)
        wins += 1 if won else 0
        left += hp
        turns += count
        if i == 0:
            sample = lines
    return {"plays": plays, "wins": wins, "hp_left": round(left / plays, 3), "turns": round(turns / plays, 1), "sample": sample}


def run_balance(q):
    """Every wild monster and trainer against every starter."""
    balance.PLAYS = int(q.get("plays", 100))
    random.seed(1)
    info = game_info()
    fair = set(info.fair_fights)
    rows = []
    for table in ENCOUNTERS:
        for row in table.rows:
            rows.append({"name": "%s: %s L%d" % (table.id, row.species, row.max), "section": "wild", "target": table.id, "fair": table.id in fair, "level": info.starter_level,
                         "begin": ("wild", row.species, row.max)})
    for t in TRAINERS:
        rows.append({"name": t.name, "section": "trainers", "target": t.id, "fair": t.id in fair, "level": t.expect_level or info.starter_level, "begin": ("trainer", t.id)})
    starters = list(info.starters)
    for row in rows:
        kind = row.pop("begin")
        begin = (lambda k=kind: begin_wild(k[1], k[2])) if kind[0] == "wild" else (lambda k=kind: begin_trainer(k[1]))
        row["results"] = []
        for s in starters:
            won, hp = balance.rate(s, row["level"], begin)
            row["results"].append({"won": round(won, 3), "hp": round(hp, 3)})
    return {"starters": starters, "rows": rows}


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    work = {"save": make_save, "fight": run_fight, "balance": run_balance}.get(command)
    if work is None:
        sys.exit(__doc__)
    question = json.loads(sys.stdin.read() or "{}")
    sys.stdout.write(json.dumps(work(question)))


if __name__ == "__main__":
    main()
