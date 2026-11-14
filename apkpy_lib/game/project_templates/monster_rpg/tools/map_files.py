"""Renaming and deleting a map, and everything that names it. The map editor and the Studio use this; so can you:

    python tools/map_files.py uses route           what names the map route
    python tools/map_files.py rename route coast   rename it everywhere
    python tools/map_files.py delete coast         delete it (it says first what is in the way, if anything)

A map's name is in:
    maps_src/<name>.map and maps/<name>.tmj      the map itself (the .tmj is made from the .map)
    game/main.py                                 its scene: game.scene("<name>", ...) and assets.tilemap("maps/<name>.tmj")
    the other maps                               link ... <name>, inside=<name>, to=<name>
    story/*.story and data/events/*.json         warp <name> <marker>
    data/game.json                               start_map, heal_map, fair_fights
    data/encounters.json                         its wild monsters: <name>.<zone>
    the events of the map                        <name>.something, by habit (story/<name>.story)
"""
import ast
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "maps_src")
OUTPUT = os.path.join(ROOT, "maps")
MAIN = os.path.join(ROOT, "game", "main.py")
STORY = os.path.join(ROOT, "story")
EVENTS = os.path.join(ROOT, "data", "events")
GAME = os.path.join(ROOT, "data", "game.json")
ENCOUNTERS = os.path.join(ROOT, "data", "encounters.json")
SPECIAL = ("arena",)          # the battle's ground: game/main.py uses it by itself


class MapFileError(Exception):
    pass


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, data):
    write(path, json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def map_names():
    return sorted(n[:-4] for n in os.listdir(SOURCE) if n.endswith(".map"))


def files(folder, ending):
    if not os.path.isdir(folder):
        return []
    return [os.path.join(folder, n) for n in sorted(os.listdir(folder)) if n.endswith(ending)]


def rel(path):
    return os.path.relpath(path, ROOT).replace("\\", "/")


# ── the other maps ──

def object_lines(text):
    """(index, line) of each object line of a .map: after "objects:", not a comment."""
    lines = text.split("\n")
    out = []
    inside = False
    for i, line in enumerate(lines):
        bare = line.strip()
        if bare == "objects:":
            inside = True
        elif bare == "tiles:":
            inside = False
        elif inside and bare and not bare.startswith("#"):
            out.append((i, line))
    return lines, out


def link_pattern(name):
    return re.compile(r"^(\s*link\s+\S+\s+\S+\s+)%s(?=\s|$)" % re.escape(name))


def prop_pattern(key, name):
    return re.compile(r"(?<!\S)%s=%s(?=\s|$)" % (key, re.escape(name)))


def event_pattern(name):
    return re.compile(r"(?<!\S)event=%s\." % re.escape(name))


def map_uses(name):
    """[(file, line number, text)] of what the other maps say about this one."""
    found = []
    for path in files(SOURCE, ".map"):
        if os.path.basename(path)[:-4] == name:
            continue
        _, objects = object_lines(read(path))
        for i, line in objects:
            if link_pattern(name).search(line) or prop_pattern("inside", name).search(line) or prop_pattern("to", name).search(line):
                found.append((rel(path), i + 1, line.strip()))
    return found


# ── the story and the events ──

def warp_pattern(name):
    return re.compile(r"^(\s*warp\s+)%s(?=\s)" % re.escape(name))


def story_warps(name):
    found = []
    for path in files(STORY, ".story"):
        for i, line in enumerate(read(path).split("\n")):
            if warp_pattern(name).search(line):
                found.append((rel(path), i + 1, line.strip()))
    return found


def event_files():
    """data/events/*.json written by hand: _story.json is made from the story, again at each build."""
    return [p for p in files(EVENTS, ".json") if not os.path.basename(p).startswith("_")]


def event_warps(name):
    found = []
    for path in event_files():
        for event in read_json(path):
            for i, step in enumerate(event.get("steps", [])):
                if step.get("do") == "warp" and step.get("to") == name:
                    found.append((rel(path), 0, "event %s, step %d: warp %s" % (event.get("id"), i + 1, name)))
    return found


def map_events(name):
    """The events named <name>.something, by habit the map's own."""
    prefix = name + "."
    found = set()
    for path in files(STORY, ".story"):
        found |= {m.group(1) for m in re.finditer(r"^event +(\S+)", read(path), re.M) if m.group(1).startswith(prefix)}
    for path in event_files():
        found |= {e.get("id", "") for e in read_json(path) if e.get("id", "").startswith(prefix)}
    return sorted(found)


# ── game/main.py ──

def scene_statements(name):
    """The lines of game/main.py that make this map's scene: [(first, last)], counted from 1."""
    text = read(MAIN)
    tree = ast.parse(text)
    var = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
            if (isinstance(call.func, ast.Attribute) and call.func.attr == "scene" and call.args
                    and isinstance(call.args[0], ast.Constant) and call.args[0].value == name):
                var = getattr(node.targets[0], "id", None)
    if var is None:
        return []
    out = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == var:
            out.append((node.lineno, node.end_lineno))
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == var:
                out.append((node.lineno, node.end_lineno))
    return out


# ── what names it ──

def uses(name):
    """Everything that names the map, as (file, line, text): line 0 when it is not about a line."""
    out = []
    if scene_statements(name):
        out.append(("game/main.py", scene_statements(name)[0][0], "its scene"))
    out += map_uses(name)
    out += story_warps(name)
    out += event_warps(name)
    info = read_json(GAME)[0]
    for key in ("start_map", "heal_map"):
        if info.get(key) == name:
            out.append(("data/game.json", 0, "%s: %s" % (key, name)))
    for table in read_json(ENCOUNTERS):
        if table["id"].split(".")[0] == name:
            out.append(("data/encounters.json", 0, "wild monsters %s" % table["id"]))
    for event in map_events(name):
        out.append(("story", 0, "event %s" % event))
    return out


def blockers(name):
    """What has to change before the map can go: the game would start or wake up there, or the story warps there."""
    out = []
    info = read_json(GAME)[0]
    for key in ("start_map", "heal_map"):
        if info.get(key) == name:
            out.append("data/game.json: %s is %s. Choose another map in My game first." % (key, name))
    for path, line, text in story_warps(name) + event_warps(name):
        out.append("%s%s: %s. Change or remove that first." % (path, ", line %d" % line if line else "", text))
    return out


def check_name(name):
    if name in SPECIAL:
        raise MapFileError("%s is the ground of every battle: game/main.py uses it by itself, so it keeps its name." % name)
    if not os.path.isfile(os.path.join(SOURCE, name + ".map")):
        raise MapFileError("There is no maps_src/%s.map." % name)


# ── rename ──

def rename(old, new):
    """Renames the map and everything that names it, its events (old.x becomes new.x) and its story file. Returns the files changed."""
    check_name(old)
    if not re.fullmatch(r"[a-z][a-z0-9_]*", new):
        raise MapFileError("%r: a map's name is lowercase letters, numbers and _, such as old_cave." % new)
    if new in map_names() or os.path.exists(os.path.join(OUTPUT, new + ".tmj")):
        raise MapFileError("There is already a map called %s." % new)
    main = read(MAIN)
    if re.search(r'game\.scene\("%s"' % re.escape(new), main):
        raise MapFileError("game/main.py already has a scene called %s." % new)
    changed = []
    events = map_events(old)

    def rename_event(text_id):
        return new + text_id[len(old):] if text_id in events else text_id

    # the map itself
    os.replace(os.path.join(SOURCE, old + ".map"), os.path.join(SOURCE, new + ".map"))
    changed.append("maps_src/%s.map" % new)
    tmj = os.path.join(OUTPUT, old + ".tmj")
    if os.path.isfile(tmj):
        os.remove(tmj)              # made again from the .map at the next build
    # its scene
    renamed = main.replace('game.scene("%s"' % old, 'game.scene("%s"' % new).replace('"maps/%s.tmj"' % old, '"maps/%s.tmj"' % new)
    if renamed != main:
        write(MAIN, renamed)
        changed.append("game/main.py")
    # every map: links, doors, buildings, and the events of this one
    for path in files(SOURCE, ".map"):
        text = read(path)
        lines, objects = object_lines(text)
        for i, line in objects:
            line = link_pattern(old).sub(lambda m: m.group(1) + new, line)
            line = prop_pattern("inside", old).sub("inside=" + new, line)
            line = prop_pattern("to", old).sub("to=" + new, line)
            line = re.sub(r"(?<!\S)event=(%s\.\S+)" % re.escape(old), lambda m: "event=" + rename_event(m.group(1)), line)
            lines[i] = line
        if "\n".join(lines) != text:
            write(path, "\n".join(lines))
            changed.append(rel(path))
    # the story
    for path in files(STORY, ".story"):
        text = read(path)
        out = []
        for line in text.split("\n"):
            line = warp_pattern(old).sub(lambda m: m.group(1) + new, line)
            line = re.sub(r"^(event +)(\S+)", lambda m: m.group(1) + rename_event(m.group(2)), line)
            out.append(line)
        if "\n".join(out) != text:
            write(path, "\n".join(out))
            changed.append(rel(path))
    story_file = os.path.join(STORY, old + ".story")
    if os.path.isfile(story_file) and not os.path.exists(os.path.join(STORY, new + ".story")):
        os.replace(story_file, os.path.join(STORY, new + ".story"))
        changed.append("story/%s.story" % new)
    # events written by hand
    for path in event_files():
        data = read_json(path)
        before = json.dumps(data)
        for event in data:
            event["id"] = rename_event(event.get("id", ""))
            for step in event.get("steps", []):
                if step.get("do") == "warp" and step.get("to") == old:
                    step["to"] = new
        if json.dumps(data) != before:
            write_json(path, data)
            changed.append(rel(path))
    # the game's data, changed in the text so it keeps the way it is written
    text = read(GAME)
    first = read_json(GAME)[0].get("first_event", "")
    renamed = re.sub(r'("(?:start_map|heal_map)"\s*:\s*)"%s"' % re.escape(old), lambda m: '%s"%s"' % (m.group(1), new), text)
    if rename_event(first) != first:
        renamed = re.sub(r'("first_event"\s*:\s*)"%s"' % re.escape(first), lambda m: '%s"%s"' % (m.group(1), rename_event(first)), renamed)
    renamed = re.sub(r'"%s\.(\w+)"' % re.escape(old), lambda m: '"%s.%s"' % (new, m.group(1)), renamed)    # fair_fights: <map>.<zone>
    if renamed != text:
        write(GAME, renamed)
        changed.append("data/game.json")
    tables = read_json(ENCOUNTERS)
    before = json.dumps(tables)
    for table in tables:
        if table["id"].startswith(old + "."):
            table["id"] = new + table["id"][len(old):]
    if json.dumps(tables) != before:
        write_json(ENCOUNTERS, tables)
        changed.append("data/encounters.json")
    return changed


# ── delete ──

def delete(name):
    """Deletes the map: its file, its scene, its wild monsters, and the links and doors of other maps that lead to it.
    Its story file stays (its events are then not used). Raises MapFileError if something has to change first."""
    check_name(name)
    stop = blockers(name)
    if stop:
        raise MapFileError("\n".join(stop))
    changed = []
    os.remove(os.path.join(SOURCE, name + ".map"))
    changed.append("maps_src/%s.map" % name)
    tmj = os.path.join(OUTPUT, name + ".tmj")
    if os.path.isfile(tmj):
        os.remove(tmj)
        changed.append("maps/%s.tmj" % name)
    gone = set()
    for first, last in scene_statements(name):
        gone |= set(range(first, last + 1))
    if gone:
        lines = read(MAIN).split("\n")
        kept = [line for i, line in enumerate(lines, 1) if i not in gone]
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(kept))
        write(MAIN, text)
        changed.append("game/main.py")
    for path in files(SOURCE, ".map"):
        text = read(path)
        lines, objects = object_lines(text)
        drop = set()
        for i, line in objects:
            if link_pattern(name).search(line) or prop_pattern("to", name).search(line):
                drop.add(i)
            else:
                lines[i] = re.sub(r"\s+inside=%s(?=\s|$)" % re.escape(name), "", line)
        new_text = "\n".join(line for i, line in enumerate(lines) if i not in drop)
        if new_text != text:
            write(path, new_text)
            changed.append(rel(path))
    tables = read_json(ENCOUNTERS)
    kept = [t for t in tables if t["id"].split(".")[0] != name]
    if len(kept) != len(tables):
        write_json(ENCOUNTERS, kept)
        changed.append("data/encounters.json")
    info_rows = read_json(GAME)
    fights = info_rows[0].get("fair_fights", [])
    left = [f for f in fights if f.split(".")[0] != name or "." not in f]
    if left != fights:
        info_rows[0]["fair_fights"] = left
        write_json(GAME, info_rows)
        changed.append("data/game.json")
    return changed


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(args) == 2 and args[0] == "uses":
            for path, line, text in uses(args[1]):
                print("%s%s: %s" % (path, ", line %d" % line if line else "", text))
        elif len(args) == 3 and args[0] == "rename":
            for path in rename(args[1], args[2]):
                print("changed:", path)
        elif len(args) == 2 and args[0] == "delete":
            for path in delete(args[1]):
                print("changed:", path)
        else:
            sys.exit(__doc__)
    except MapFileError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
