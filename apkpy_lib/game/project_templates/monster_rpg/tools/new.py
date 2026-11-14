"""Starts something new, so you have a file to change instead of a blank page.

    python tools/new.py monster spark_toad ember     a monster of that type: data/species/spark_toad.json and its sprites
    python tools/new.py person sam                   a look for people on maps: assets/people/sam.png  (look=sam)
    python tools/new.py map cave                     a small map: maps_src/cave.map
    python tools/new.py wild cave reeds pebblit gustlet       what comes out of a zone of a map: data/encounters.json
    python tools/new.py trainer tess pebblit:3 gustlet:4      a trainer and their team: data/trainers.json

Nothing is ever overwritten.
"""
import difflib
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import make_art  # noqa: E402


def load(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        return json.load(fh)


def save(path, data):
    with open(os.path.join(ROOT, path), "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
        fh.write("\n")


def fail(text):
    sys.exit(text)


def check_new(path):
    if os.path.exists(os.path.join(ROOT, path)):
        fail("%s already exists: open that one." % path)


def check_name(name):
    if not name.replace("_", "").isalnum() or not name[0].isalpha() or name != name.lower():
        fail("%r: a name here is lowercase letters, numbers and _, such as spark_toad" % name)


def species_ids():
    return sorted(n[:-5] for n in os.listdir(os.path.join(ROOT, "data", "species")) if n.endswith(".json"))


def check_species(name):
    known = species_ids()
    if name not in known:
        close = difflib.get_close_matches(name, known, 1)
        fail("there is no monster %r.%s" % (name, " Did you mean %r?" % close[0] if close else ""))


def monster(name, kind="plain"):
    check_name(name)
    path = "data/species/%s.json" % name
    check_new(path)
    types = [t["id"] for t in load("data/types.json")]
    if kind not in types:
        close = difflib.get_close_matches(kind, types, 1)
        fail("there is no type %r.%s" % (kind, " Did you mean %r?" % close[0] if close else ""))
    moves = load("data/moves.json")
    own = [m["id"] for m in moves if m["type"] == kind and m["power"] > 0][:1]
    plain = [m["id"] for m in moves if m["kind"] != "status" and m["id"] not in own][:1]
    row = {"id": name, "name": name.replace("_", " ").title(), "types": [kind],
           "base": {"hp": 40, "attack": 45, "defense": 40, "special": 45, "speed": 45},
           "learnset": [{"level": 1, "move": m} for m in plain] + [{"level": 5, "move": m} for m in own],
           "catch_rate": 120, "exp_yield": 50, "ev_stat": "hp", "description": "Write what it is like here."}
    save(path, row)
    print(path)
    make_art.monsters()


def person(name):
    check_name(name)
    path = "assets/people/%s.png" % name
    check_new(path)
    # colours from the name: the same name always looks the same
    h = hashlib.sha256(name.encode("utf-8")).digest()
    make_art.keep(make_art.person((236, 196, 150), (h[0], h[1], h[2]), (h[3] // 2, h[4] // 2, h[5] // 2), (h[6] // 2, h[7] // 2, h[8] // 2)), "people/%s.png" % name)
    print("On a map:  person 3 2 %s look=%s event=somewhere.%s" % (name, name, name))


def new_map(name):
    check_name(name)
    path = "maps_src/%s.map" % name
    check_new(path)
    with open(os.path.join(ROOT, path), "w", encoding="utf-8") as fh:
        fh.write("# Describe this place here.\ntiles:\n" + "c" * 10 + "\n" + ("c" + "." * 8 + "c\n") * 6 + "c" * 10 + "\nobjects:\n")
    print(path)
    print("To reach it: a building with inside=%s, or  link <column> <row> %s  here and in the other map." % (name, name))


def wild(name, zone, kinds):
    if not kinds:
        fail("which monsters? python tools/new.py wild %s %s pebblit gustlet" % (name, zone))
    table_id = "%s.%s" % (name, zone)
    rows = load("data/encounters.json")
    if table_id in [r["id"] for r in rows]:
        fail("data/encounters.json already has %s: change it there." % table_id)
    for k in kinds:
        check_species(k)
    rows.append({"id": table_id, "rate": 10, "rows": [{"species": k, "min": 2, "max": 4, "weight": 10} for k in kinds]})
    save("data/encounters.json", rows)
    print("data/encounters.json: %s (rate: the chance, in %%, on each step)" % table_id)


def trainer(name, team):
    check_name(name)
    if not team:
        fail("who is in the team? python tools/new.py trainer %s pebblit:3" % name)
    rows = load("data/trainers.json")
    if name in [r["id"] for r in rows]:
        fail("data/trainers.json already has %s: change it there." % name)
    members = []
    for member in team:
        kind, _, level = member.partition(":")
        check_species(kind)
        if not level.isdigit():
            fail("%r: write monster:level, such as pebblit:3" % member)
        members.append({"species": kind, "level": int(level)})
    rows.append({"id": name, "name": name.replace("_", " ").title(), "reward": 100, "team": members, "lose_text": "You win."})
    save("data/trainers.json", rows)
    print("data/trainers.json: %s" % name)
    print("On a map:  trainer 5 5 %s look=villager facing=down" % name)
    print("In a story file:  trainer %s  with before:, won: and after: blocks" % name)


def main():
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "monster" and len(args) <= 3:
        monster(*args[1:])
    elif len(args) == 2 and args[0] == "person":
        person(args[1])
    elif len(args) == 2 and args[0] == "map":
        new_map(args[1])
    elif len(args) >= 3 and args[0] == "wild":
        wild(args[1], args[2], args[3:])
    elif len(args) >= 2 and args[0] == "trainer":
        trainer(args[1], args[2:])
    else:
        fail(__doc__)


if __name__ == "__main__":
    main()
