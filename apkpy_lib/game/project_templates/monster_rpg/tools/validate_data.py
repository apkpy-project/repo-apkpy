"""Checks what the build cannot know about the content. The build already checks every field and Ref[...];
this checks the meaning: events, maps and objects that point at each other.

    python tools/validate_data.py
"""
import difflib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STEPS = {"say": ["text"], "ask": ["text", "to"], "label": ["to"], "jump_if": ["flag", "to"], "jump_unless": ["flag", "to"], "end": [],
         "set_flag": ["flag"], "clear_flag": ["flag"], "give_item": ["item"], "give_money": ["count"], "give_monster": ["species"],
         "jump": ["to"], "heal": [], "open": ["screen"], "shop": ["shop"], "battle": ["trainer"], "warp": ["to", "at"], "step_back": []}
SCREENS = {"menu", "team", "bag", "dex", "shop", "options", "save", "starter"}


def close(word, options):
    found = difflib.get_close_matches(str(word), [str(o) for o in options], 1)
    return ". Did you mean %r?" % found[0] if found else ""


def load(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except ValueError as e:
            sys.exit("%s, line %d: this is not valid JSON: %s. Look for a comma too many or too few on that line or just above it."
                     % (path.replace("\\", "/"), e.lineno, e.msg))


def rows(folder):
    out = []
    for name in sorted(os.listdir(os.path.join(ROOT, folder))):
        if name.endswith(".json"):
            row = load(os.path.join(folder, name))
            out += row if isinstance(row, list) else [row]
    return out


def read_maps():
    """{map: {marker names}, and its objects as (class, name, props)}."""
    maps = {}
    for name in sorted(os.listdir(os.path.join(ROOT, "maps"))):
        if not name.endswith(".tmj"):
            continue
        data = load(os.path.join("maps", name))
        objects = []
        for layer in data["layers"]:
            for o in layer.get("objects", []):
                objects.append((o.get("type") or o.get("class") or "", o.get("name", ""), {p["name"]: p["value"] for p in o.get("properties", [])}))
        maps[name[:-4]] = objects
    return maps


def check_json_files():
    """A file that cannot be read stops everything, with a message a person can use."""
    for folder, _, names in os.walk(os.path.join(ROOT, "data")):
        for name in sorted(names):
            if name.endswith(".json"):
                load(os.path.relpath(os.path.join(folder, name), ROOT))


def check():
    problems = []
    species = {s["id"] for s in rows("data/species")}
    items = {i["id"] for i in load("data/items.json")}
    trainers = {t["id"] for t in load("data/trainers.json")}
    shops = {s["id"] for s in load("data/shops.json")}
    events = {e["id"]: e for e in rows("data/events")}
    maps = read_maps()
    types = load("data/types.json")
    with open(os.path.join(ROOT, "game", "main.py"), encoding="utf-8") as fh:
        main = fh.read()
    scenes = set(re.findall(r'game\.scene\("(\w+)"', main))

    for t in types:
        if not t["color"].startswith("#"):
            problems.append("types.json: %s: color" % t["id"])
    flags_set = set()
    for e in events.values():
        for s in e["steps"]:
            if s["do"] == "set_flag":
                flags_set.add(s["flag"])
    for e in events.values():
        where = "event %s" % e["id"]
        labels = {s.get("to") for s in e["steps"] if s["do"] == "label"}
        for i, s in enumerate(e["steps"]):
            do = s["do"]
            if do not in STEPS:
                problems.append("%s, step %d: there is no step %r%s" % (where, i + 1, do, close(do, STEPS)))
                continue
            for key in STEPS[do]:
                if key not in s:
                    problems.append("%s, step %d: %s needs %r" % (where, i + 1, do, key))
            if do in ("ask", "jump", "jump_if", "jump_unless") and s.get("to") not in labels:
                problems.append("%s, step %d: no label %r%s" % (where, i + 1, s.get("to"), close(s.get("to"), [l for l in labels if l])))
            if do in ("jump_if", "jump_unless") and s.get("flag") not in flags_set:
                problems.append("%s, step %d: no event ever sets the flag %r%s" % (where, i + 1, s.get("flag"), close(s.get("flag"), flags_set)))
            if do == "give_item" and s.get("item") not in items:
                problems.append("%s, step %d: no item %r" % (where, i, s.get("item")))
            if do == "give_monster" and s.get("species") not in species:
                problems.append("%s, step %d: no species %r" % (where, i, s.get("species")))
            if do == "battle" and s.get("trainer") not in trainers:
                problems.append("%s, step %d: no trainer %r" % (where, i, s.get("trainer")))
            if do == "shop" and s.get("shop") not in shops:
                problems.append("%s, step %d: no shop %r" % (where, i, s.get("shop")))
            if do == "open" and s.get("screen") not in SCREENS:
                problems.append("%s, step %d: no screen %r" % (where, i, s.get("screen")))
            if do == "warp" and s.get("to") not in maps:
                problems.append("%s, step %d: no map %r" % (where, i, s.get("to")))

    for name, objects in maps.items():
        if name != "arena" and name not in scenes:
            problems.append("maps/%s.tmj: no game.scene(\"%s\") in game/main.py" % (name, name))
        for kind, obj, props in objects:
            where = "maps/%s.tmj, object %s" % (name, obj or kind)
            event = props.get("event")
            if event is not None and event not in events:
                problems.append("%s: no event %r%s" % (where, event, close(event, events)))
            for key in ("hide_if", "unless", "flag"):
                if key in props and props[key] not in flags_set:
                    problems.append("%s: %s=%s, but no event ever sets that flag%s" % (where, key, props[key], close(props[key], flags_set)))
            look = props.get("look")
            if look is not None and not os.path.isfile(os.path.join(ROOT, "assets", "people", "%s.png" % look)):
                problems.append("%s: look=%s, but there is no assets/people/%s.png" % (where, look, look))
            if kind in ("door", "exit") and "to" not in props and "event" not in props:
                problems.append("%s: a door needs to= and at=, or event=" % where)
            if kind == "warp" or ((kind == "door" or kind == "exit") and "to" in props):
                target = props.get("to")
                if target not in maps:
                    problems.append("%s: no map %r%s" % (where, target, close(target, maps)))
                elif props.get("at") not in {o[1] for o in maps[target]}:
                    problems.append("%s: map %s has nothing called %r%s" % (where, target, props.get("at"), close(props.get("at"), {o[1] for o in maps[target] if o[1]})))
            if kind.startswith("trainer") and (props.get("flag") is None or "event" not in props):
                problems.append("%s: a trainer needs event= and flag=" % where)
    for s in rows("data/species"):
        path = os.path.join(ROOT, "assets", "monsters", s["id"] + ".png")
        if not os.path.isfile(path):
            problems.append("assets/monsters/%s.png: the species %s has no sprites (tools/make_art.py draws a placeholder)" % (s["id"], s["id"]))
        else:
            from PIL import Image
            with Image.open(path) as img:
                if img.size[0] < 128 or img.size[1] < 64 or img.size[0] % 64 or img.size[1] % 64:
                    problems.append("assets/monsters/%s.png is %dx%d: it is cells of 64 x 64, front then back" % (s["id"], img.size[0], img.size[1]))
        seen_variants = set()
        for v in s.get("variants", []):
            vid = v.get("id", "")
            where = "data/species/%s.json: variant %r" % (s["id"], vid)
            if not re.fullmatch(r"[a-z][a-z0-9_]*", vid):
                problems.append("%s: an id is lowercase letters, numbers and _, such as shiny" % where)
            elif vid == "default":
                problems.append("%s: default is the usual look; give the variant another id" % where)
            elif vid in seen_variants:
                problems.append("%s: there are two with this id" % where)
            elif not os.path.isfile(os.path.join(ROOT, "assets", "monsters", "%s.%s.png" % (s["id"], vid))):
                problems.append("assets/monsters/%s.%s.png: the variant has no sprites (tools/make_art.py draws a placeholder)" % (s["id"], vid))
            if v.get("one_in", 0) < 0:
                problems.append("%s: one_in is 0 (never in the wild) or more" % where)
            seen_variants.add(vid)
    variants_of = {s["id"]: {v.get("id") for v in s.get("variants", [])} for s in rows("data/species")}
    for t in load("data/trainers.json"):
        for member in t.get("team", []):
            chosen = member.get("variant", "")
            if chosen not in ("", "default") and chosen not in variants_of.get(member.get("species"), set()):
                problems.append("trainers.json: %s: %s has no variant %r%s" % (t["id"], member.get("species"), chosen, close(chosen, variants_of.get(member.get("species"), set()) | {"default"})))
    texts = {t["id"] for t in load("data/texts.json")}
    effects = {e["id"] for e in load("data/effects.json")}
    statuses = {s["id"] for s in load("data/statuses.json")}
    for e in load("data/effects.json"):
        if e.get("stat", "") not in ("", "attack", "defense", "special", "speed"):
            problems.append("effects.json: %s: stat is attack, defense, special or speed, not %r" % (e["id"], e["stat"]))
        if e.get("target", "foe") not in ("foe", "self"):
            problems.append("effects.json: %s: target is foe or self, not %r" % (e["id"], e["target"]))
    for s in load("data/statuses.json"):
        if s.get("min_turns", 0) > s.get("max_turns", 0):
            problems.append("statuses.json: %s: min_turns is more than max_turns" % s["id"])
    info = load("data/game.json")[0]
    for key, at in (("start_map", "start_at"), ("heal_map", "heal_at")):
        if info[key] not in maps:
            problems.append("data/game.json: %s: no map %r%s" % (key, info[key], close(info[key], maps)))
        elif info[at] not in {o[1] for o in maps[info[key]]}:
            problems.append("data/game.json: %s: map %s has nothing called %r%s" % (at, info[key], info[at], close(info[at], {o[1] for o in maps[info[key]] if o[1]})))
    fights = {t["id"] for t in load("data/encounters.json")} | trainers
    for name in info["fair_fights"]:
        if name not in fights:
            problems.append("data/game.json: fair_fights: there is no table or trainer %r%s" % (name, close(name, fights)))
    if not 1 <= len(info["starters"]) <= 3:
        problems.append("data/game.json: starters: there is room for 1 to 3 on the screen, and it lists %d" % len(info["starters"]))
    for table in load("data/encounters.json"):
        if table["id"].split(".")[0] not in maps:
            problems.append("encounters.json: %s: no such map%s" % (table["id"], close(table["id"].split(".")[0], maps)))
    return problems


def notes():
    """Not errors, but probably not what you meant."""
    out = []
    tables = {t["id"] for t in load("data/encounters.json")}
    for name in sorted(os.listdir(os.path.join(ROOT, "maps"))):
        if not name.endswith(".tmj"):
            continue
        data = load(os.path.join("maps", name))
        ground = next(l for l in data["layers"] if l["name"] == "ground")["data"]
        solid = next(l for l in data["layers"] if l["name"] == "solid")["data"]
        zones = {t["id"] + 1: p["value"] for t in data["tilesets"][0].get("tiles", []) for p in t.get("properties", []) if p["name"] == "zone"}
        walked = {zones[g] for g, s in zip(ground, solid) if g in zones and not s}
        for zone in sorted(walked):
            if "%s.%s" % (name[:-4], zone) not in tables:
                out.append("maps/%s: nothing comes out of its %s: there is no row %s.%s in data/encounters.json" % (name, zone, name[:-4], zone))
    return out


if __name__ == "__main__":
    found = check()
    for p in found:
        print(p)
    for n in notes():
        print("note: " + n)
    if found:
        sys.exit("%d problem(s)." % len(found))
    print("The content holds together.")
