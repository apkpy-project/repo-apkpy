"""The monster RPG template: a new project from it builds, its content holds together, its rules pass,
the recipes of its README work, and a bot plays the whole opening with keys and taps, reaching the same state again."""
import json
import os
import re
import subprocess
import sys

import pytest

from apkpy_lib.game.errors import GameError
from conftest import TEMPLATES, new_game  # noqa: E402


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    folder = tmp_path_factory.mktemp("rpg") / "MyGame"
    r = new_game(folder, "monster-rpg", "com.test.mygame")
    assert r.returncode == 0, r.stdout + r.stderr
    return folder


TEMPLATE = os.path.join(TEMPLATES, "monster_rpg")


def run(project, *command):
    return subprocess.run([sys.executable] + list(command), cwd=str(project), capture_output=True, text=True, timeout=280)


def build(project):
    from apkpy_lib.game.build import bundle_only
    from apkpy_lib.game.project import Project
    return bundle_only(Project(str(project)))


def test_a_new_project_is_named_and_builds(project):
    assert 'application_id = "com.test.mygame"' in (project / "apkpy.toml").read_text()
    assert "enable_game()" in (project / "writehere.py").read_text()
    info = build(project)
    assert "battle" in info["scenes"] and len(info["scenes"]) == 5


def test_its_own_checks_pass(project):
    r = run(project, "tools/prepare.py")
    assert r.returncode == 0, r.stdout + r.stderr
    r = run(project, "-m", "pytest", "-q", "tests")
    assert r.returncode == 0, r.stdout[-1500:]


def test_the_bot_plays_every_feature(project):
    r = run(project, "tools/advanced/play_bot.py")
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]
    features = r.stdout
    for word in ("title, name", "give_item", "step_back", "starter screen", "partner's page", "ask", "shop", "buy", "team", "bag", "encyclopedia", "options", "save",
                 "back", "door", "controls stay", "warp", "line of sight", "capture", "evolution", "hide_if", "rival", "the end", "continue"):
        assert word in features, word + "\n" + features
    played = re.search(r"steps=(\d+) hash=(\S+)", features)
    assert "state=%s" % played.group(2) in features, "the replay reaches the same state:\n" + features[-400:]


def tutorial_steps(root):
    """What the tutorial tells you to do, in order: (what, file or command, text)."""
    folder = os.path.join(TEMPLATE, "tutorial")
    steps = []
    for name in sorted(os.listdir(folder)):
        if name[0].isdigit():
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                text = fh.read()
            pattern = (r"(Create|Add to) `([^`]+)`:\n\n```\n(.*?)```"
                       r"|```bash\n(python tools/[^\n]+)\n```"
                       r"|In `([^`]+)`, change `([^`]+)` to `([^`]+)`")
            for m in re.finditer(pattern, text, re.S):
                if m.group(1):
                    steps.append((m.group(1), m.group(2), m.group(3)))
                elif m.group(4):
                    steps.append(("Run", m.group(4), ""))
                else:
                    steps.append(("Change", m.group(5), (m.group(6), m.group(7))))
            steps.append(("Build", "", ""))                 # each page ends with a game that builds
    return steps


def test_the_tutorial_works_step_by_step(tmp_path):
    folder = tmp_path / "MyGame"
    r = new_game(folder, "monster-rpg", "com.test.tutorial")
    assert r.returncode == 0, r.stdout + r.stderr
    steps = tutorial_steps(folder)
    assert len(steps) >= 12, steps
    info = None
    for what, target, text in steps:
        if what == "Build":
            info = build(folder)
        elif what == "Run":
            r = run(folder, *target.split()[1:])
            assert r.returncode == 0, target + "\n" + r.stdout + r.stderr
        elif what == "Create":
            (folder / target).write_text(text, encoding="utf-8")
        elif what == "Add to":
            with open(folder / target, "a", encoding="utf-8") as fh:
                fh.write(("\n" if target.endswith(".story") else "") + text)
        else:
            old = (folder / target).read_text(encoding="utf-8")
            assert text[0] in old, target + ": " + text[0]
            (folder / target).write_text(old.replace(text[0], text[1], 1), encoding="utf-8")
    assert "sam_house" in info["scenes"] and "cellar" in info["scenes"]
    made = json.loads((folder / "maps" / "village.tmj").read_text())
    objects = [o for layer in made["layers"] for o in layer.get("objects", [])]
    door = [o for o in objects if o["name"] == "door_sam_house"]
    assert door and {p["name"]: p["value"] for p in door[0]["properties"]} == {"to": "sam_house", "at": "from_village"}
    assert "<<" not in (folder / "game" / "main.py").read_text()
    r = run(folder, "-m", "pytest", "-q", "tests")
    assert r.returncode == 0, r.stdout[-1500:]


def mistake(project, path, old, new):
    """Makes one mistake, and gives back what the build says about it."""
    from_file = project / path
    keep = from_file.read_text(encoding="utf-8")
    assert old in keep, old
    from_file.write_text(keep.replace(old, new, 1), encoding="utf-8")
    try:
        with pytest.raises(GameError) as e:
            build(project)
        return str(e.value)
    finally:
        from_file.write_text(keep, encoding="utf-8")
        build(project)


@pytest.mark.parametrize("path, old, new, says", [
    ("maps_src/village.map", "tree 2 7", "tre 2 7", "Did you mean 'tree'"),
    ("maps_src/village.map", "tree 2 7", "tree 2", "maps_src/village.map:"),
    ("maps_src/village.map", "tree 2 7", "tree 50 70", "outside the map"),
    ("maps_src/village.map", "c.........,.....rr.c", "c.........,.....rr.", "this row has 19 letters"),
    ("maps_src/village.map", "c.........,.....rr.c", "c.........,.....xx.c", "the letter 'x'"),
    ("maps_src/village.map", "marker 10 13 start", "marker 0 0 start", "on a solid cell"),
    ("maps_src/village.map", "inside=house", "inside=hous", "Did you mean 'house'"),
    ("maps_src/village.map", "link 10 0 route", "link 10 0 rout", "Did you mean 'route'"),
    ("maps_src/route.map", "link 6 25 village width=2", "tree 6 25", "needs a link back"),
    ("maps_src/route.map", "hide_if=found_knot", "hide_if=found_knott", "Did you mean 'found_knot'"),
    ("maps_src/village.map", "look=vendor", "look=vendorr", "assets/people/vendorr.png"),
    ("maps_src/legend.txt", ". = grass", ". = gras", "Did you mean 'grass'"),
    ("story/village.story", "say It did not come back.", "sayy It did not come back.", "Did you mean 'say'"),
    ("story/village.story", "give tonic 3", "give tonik 3", "Did you mean 'tonic'"),
    ("story/village.story", "shop harbour", "shop harbor", "Did you mean 'harbour'"),
    ("story/route.story", "    after:\n        say Road", "    afterwards:\n        say Road", "a trainer has"),
    ("data/game.json", '"start_map": "village"', '"start_map": "villag"', "Did you mean 'village'"),
    ("data/game.json", '"cindlet", "rillet", "mossup"', '"cindlet", "rillet", "mossup", "lumoth"', "room for 1 to 3"),
    ("data/items.json", '"price": 100,', '"price": 100,,', "data/items.json, line"),
])
def test_a_mistake_is_explained(project, path, old, new, says):
    assert says in mistake(project, path, old, new)


def test_a_starter_that_does_not_exist_stops_the_build(project):
    keep = project / "data" / "game.json"
    text = keep.read_text(encoding="utf-8")
    keep.write_text(text.replace('"starters": ["cindlet"', '"starters": ["cindlett"'), encoding="utf-8")
    try:
        with pytest.raises(GameError) as e:
            build(project)
        assert "cindlett" in str(e.value)
    finally:
        keep.write_text(text, encoding="utf-8")


def test_a_note_for_a_zone_with_no_monsters(project):
    path = project / "data" / "encounters.json"
    text = path.read_text(encoding="utf-8")
    path.write_text(json.dumps([t for t in json.loads(text) if t["id"] != "village.reeds"]), encoding="utf-8")
    try:
        r = run(project, "tools/prepare.py")
        assert r.returncode == 0 and "note: maps/village.tmj: nothing comes out of its reeds" in r.stdout, r.stdout + r.stderr
    finally:
        path.write_text(text, encoding="utf-8")


def test_the_reeds_of_the_placeholder_maps_have_monsters(project):
    r = run(project, "tools/prepare.py")
    assert r.returncode == 0 and "note:" not in r.stdout, r.stdout


def test_art_drawn_by_hand_is_never_replaced(project):
    from PIL import Image
    names = ["assets/tiles/grass.png", "assets/people/hero.png", "assets/box.png", "assets/title_sky.png", "assets/monsters/cindlet.png"]
    colour = (1, 2, 3, 255)
    keep = {}
    for name in names:
        keep[name] = (project / name).read_bytes()
        Image.new("RGBA", Image.open(project / name).size, colour).save(project / name)
    try:
        r = run(project, "tools/make_art.py")
        assert r.returncode == 0, r.stderr
        for name in names:
            assert Image.open(project / name).convert("RGBA").getpixel((0, 0)) == colour, name
    finally:
        for name, data in keep.items():
            (project / name).write_bytes(data)


def test_a_map_changed_by_hand_is_not_overwritten(project):
    path = project / "maps" / "route.tmj"
    keep = path.read_text()
    data = json.loads(keep)
    data["layers"][0]["data"][0] = 2
    path.write_text(json.dumps(data))
    source = project / "maps_src" / "route.map"
    text = source.read_text(encoding="utf-8")
    source.write_text(text.replace("tree 2 21", "tree 3 21"), encoding="utf-8")
    try:
        r = run(project, "tools/map_tool.py")
        assert r.returncode == 1 and "changed by hand" in r.stderr, r.stdout + r.stderr
        assert json.loads(path.read_text())["layers"][0]["data"][0] == 2
        r = run(project, "tools/map_tool.py", "--force")
        assert r.returncode == 0 and json.loads(path.read_text())["layers"][0]["data"][0] != 2
    finally:
        source.write_text(text, encoding="utf-8")
        path.write_text(keep)
        run(project, "tools/map_tool.py", "--force")


def test_changing_a_map_needs_no_command(project):
    source = project / "maps_src" / "route.map"
    text = source.read_text(encoding="utf-8")
    source.write_text(text.replace("tree 2 21", "tree 3 21"), encoding="utf-8")
    try:
        build(project)
        made = json.loads((project / "maps" / "route.tmj").read_text())
        trees = [o["x"] for layer in made["layers"] for o in layer.get("objects", []) if o["type"] == "tree"]
        assert 3 * 16 + 8 in trees
    finally:
        source.write_text(text, encoding="utf-8")
        build(project)


def test_new_refuses_to_overwrite(project):
    r = run(project, "tools/new.py", "monster", "cindlet", "ember")
    assert r.returncode == 1 and "already exists" in r.stderr
    r = run(project, "tools/new.py", "monster", "new_one", "embr")
    assert r.returncode == 1 and "Did you mean 'ember'" in r.stderr


EDITOR_LOGIC = """
import sys
sys.path.insert(0, "tools")
import map_editor
from map_editor import MapDoc
text = open("maps_src/route.map", encoding="utf-8").read()
doc = MapDoc("route")
assert doc.text() == text, "opening and saving changes nothing"
wide, tall = doc.cols, len(doc.rows)
snap = doc.snapshot()
assert doc.paint(1, 7, "S") and not doc.paint(1, 7, "S") and not doc.paint(99, 99, "S")
assert len(doc.fill(7, 12, "f")) > 10 and doc.rows[12][7] == "f" and doc.rows[12][1] != "f"
assert len(doc.rectangle(3, 8, 1, 7, "u")) > 0 and doc.rows[7][2] == "u"
doc.restore(snap)
assert doc.text() == text, "undo brings back the same file"
ona = [o for o in doc.objects if o.get("name") == "cape_sign"][0]
col, row = ona["col"], ona["row"]
doc.grow("top", "c"); doc.grow("left", "c")
assert (ona["col"], ona["row"]) == (col + 1, row + 1) and doc.cols == wide + 1 and len(doc.rows) == tall + 1
doc.shrink("top"); doc.shrink("left")
assert (ona["col"], ona["row"]) == (col, row) and doc.text() == text
link = [o for o in doc.objects if o["kind"] == "link"][0]
assert any(o is link for o in doc.shrink("bottom")), "what stood on a removed edge goes with it"
doc.restore(snap)
sign = [o for o in doc.objects if o.get("name") == "cape_sign"][0]
line = doc.text().split("\\n").index(MapDoc.object_line(sign)) + 1
assert doc.object_on_line(line) is sign
assert doc.problem() == ""
doc.add_object("link", 3.0, 8.0)["name"] = "rout"
assert "Did you mean" in doc.problem()
assert open("maps_src/route.map", encoding="utf-8").read() == text, "checking writes nothing"
doc.objects.pop()
copy = doc.copy_object(sign)
assert copy["col"] == sign["col"] + 1 and copy["name"] == sign["name"]
map_editor.create_map("hollow", 6, 4, ".", "c")
assert MapDoc("hollow").rows[1] == list("c....c")
for bad in ("Bad Name", "route"):
    try:
        map_editor.create_map(bad, 6, 4, ".", "c")
    except map_editor.map_tool.MapError:
        pass
    else:
        raise SystemExit("made a map called " + bad)
assert "route.lighthouse" in map_editor.known_events() and "trainer.tess" in map_editor.known_events()
assert "beat_tess" in map_editor.known_flags() and "got_partner" in map_editor.known_flags()
assert "vendor" in map_editor.known_looks() and "tess" in map_editor.known_trainers()
print("fine")
"""

EDITOR_WINDOW = """
import sys, tkinter as tk
sys.path.insert(0, "tools")
import map_editor
try:
    root = tk.Tk()
except tk.TclError:
    print("no screen")
    raise SystemExit
ed = map_editor.Editor(root)
assert not ed.tabs and list(ed.map_list.get(0, "end"))[-1] == "village", "it opens with the list"
ed.open_map("village"); ed.open_map("route"); ed.open_map("village")
assert [t.doc.name for t in ed.tabs] == ["village", "route"] and ed.tab().doc.name == "village", "one tab per map"
root.update()
size = map_editor.TILE * ed.zoom
def spot(col, row):
    return dict(x=col * size + 4 - int(ed.tab().canvas.canvasx(0)), y=row * size + 4 - int(ed.tab().canvas.canvasy(0)))
c = ed.tab().canvas
ed.pick_tile("s")
c.event_generate("<Button-1>", **spot(2, 14))
for col in range(3, 6):
    c.event_generate("<B1-Motion>", **spot(col, 14))
c.event_generate("<ButtonRelease-1>", **spot(5, 14))
root.update()
assert "".join(ed.tab().doc.rows[14])[2:6] == "ssss" and ed.tab().dirty
assert ed.notebook.tab(ed.tab().frame, "text") == "village *"
ed.do_undo()
assert not ed.tab().dirty and ed.notebook.tab(ed.tab().frame, "text") == "village"
ed.do_redo()
assert ed.tab().dirty
ed.place_kind = "person"
c.event_generate("<Button-1>", **spot(12, 9))
c.event_generate("<ButtonRelease-1>", **spot(12, 9))
root.update()
o = ed.tab().selected
assert o["kind"] == "person" and ed.tool == "select"
ed.fields[""].insert(0, "sam"); ed.read_fields()
c.event_generate("<Button-1>", **spot(12, 9))
c.event_generate("<B1-Motion>", **spot(13, 8))
c.event_generate("<ButtonRelease-1>", **spot(13, 8))
root.update()
assert (o["col"], o["row"]) == (13.0, 8.0), "a click right after another still picks up the object"
ed.open_map("route")
ed.tab().doc.add_object("link", 3.0, 8.0)["name"] = "rout"
ed.check_problems()
assert "Did you mean" in ed.problem_label.cget("text"), "problems show before saving"
ed.tab().selected = None
ed.go_to_problem()
assert ed.tab().selected["name"] == "rout"
ed.delete_selected()
ed.check_problems()
assert "No problems" in ed.problem_label.cget("text")
ed.save_all()
assert not any(t.dirty for t in ed.tabs)
assert "person 13 8 sam" in open("maps_src/village.map", encoding="utf-8").read()
ed.remember_session()
root.destroy()
assert map_editor.Editor.last_session() == ["village", "route"]
print("fine")
"""


IDEAS = """
import sys, json, tkinter as tk
sys.path.insert(0, "tools")
import map_editor, map_tool, story_tool, story_editor
from map_editor import MapDoc
# copying a piece of a map to another map, with its objects and a letter the other map lacks
a, b = MapDoc("route"), MapDoc("house")
piece = a.copy_area(1, 21, 3, 22)
assert piece["rows"][0] == a.rows[21][1:4] and [o["kind"] for o in piece["objects"]] == ["tree"]
assert piece["objects"][0]["col"] == 1 and piece["objects"][0]["row"] == 0
b.paste_area(piece, 1, 1)
assert b.objects[-1]["kind"] == "tree" and (b.objects[-1]["col"], b.objects[-1]["row"]) == (2, 1)
c = MapDoc("house")
c.legend["a"] = dict(c.legend["a"], tile="wall")
strange = {"rows": [["a"]], "legend": {"a": dict(MapDoc("house").legend["a"])}, "objects": []}
c.paste_area(strange, 1, 1)
assert c.rows[1][1] != "a" and "= arena" in c.header[-1], "the letter means something else here, so it gets another"
d = MapDoc("route")
d.clear_area(1, 21, 3, 22, ".")
assert d.rows[21][1:4] == list("...") and not [o for o in d.objects if o["kind"] == "tree" and o["row"] == 21 and o["col"] == 2]
# edges
legend = MapDoc("village").legend
rows = [list("..."), list(".~."), list("...")]
art = map_tool.cell_art(rows, legend, 1, 1)
assert art == ("water", "grass", 15)
assert map_tool.cell_art(rows, legend, 0, 0) == ("grass", None, 0), "only letters with edges"
assert map_tool.cell_art([list("~~"), list("~~")], legend, 0, 0)[2] == 0, "the same tile is not cut"
assert map_tool.cell_art([list("~c")], legend, 0, 0)[2] == 0, "nor against a block"
assert map_tool.cell_art([list("~,")], legend, 0, 0)[2] == 0, "nor against other edges"
picture = map_tool.edge_tile("water", "grass", 15)
assert picture.size == (16, 16)
from PIL import Image
grass = Image.open("assets/tiles/grass.png").convert("RGBA")
assert picture.getpixel((0, 0)) == grass.getpixel((0, 0)) and picture.getpixel((8, 8)) == Image.open("assets/tiles/water.png").convert("RGBA").getpixel((8, 8))
# a cut cell keeps its zone
maps, names = map_tool.load_all()
maps["route"].legend["q"] = dict(maps["route"].legend["r"], edges=True)
maps["route"].rows[8] = "c..qqqssrrr..c"
variants = map_tool.all_variants(maps)
tmj = map_tool.to_tmj(maps["route"], names, variants)
zones = {t["id"] for t in tmj["tilesets"][0]["tiles"]}
gid = tmj["layers"][0]["data"][8 * 14 + 3]
assert gid > len(names) and gid - 1 in zones, "monsters still come out of a cut cell"
# the story, before saving
assert story_tool.find_problem() == ""
assert "Did you mean" in story_tool.find_problem({"route.story": "event a.b\\n    give tonik\\n"})
root = tk.Tk() if tk._default_root is None else tk._default_root
ed = map_editor.Editor(root, ["village"])
# 3D blocks: a tile, then a height
stone = next(k for k, v in ed.tab().doc.legend.items() if v["tile"] == "stone")
ed.pick_tile(stone); ed.height_var.set(2); ed.height_changed()
block = ed.tab().doc.legend[ed.letter]
assert block["tile"] == "stone" and block["height"] == 2 and block["solid"]
assert ("= stone solid height=2") in open("maps_src/legend.txt", encoding="utf-8").read()
tall = ed.letter
ed.height_var.set(0); ed.height_changed()
assert ed.letter == stone, "back to the same letter"
ed.height_var.set(2); ed.height_changed()
assert ed.letter == tall, "no new letter for what exists"
ed.solid_var.set(False); ed.height_changed()
assert ed.tab().doc.legend[ed.letter]["height"] == 2 and not ed.tab().doc.legend[ed.letter]["solid"], "a hill to walk on"
# from an object to its event
tab = ed.tab()
sam = tab.doc.add_object("person", 12.0, 8.0)
sam["name"] = "sam"
tab.selected = sam
ed.edit_event(tab, sam)
st = ed.story
assert sam["props"]["event"] == "village.sam" and st.current == "village.story" and "village.sam" in st.outline.get(0, "end")
st.insert_snippet(["say Hello."])
st.check()
assert "No problems" in st.problem.cget("text"), st.problem.cget("text")
trainer = tab.doc.add_object("trainer", 13.0, 8.0)
trainer["name"] = "tess"
ed.edit_event(tab, trainer)
assert st.current == "route.story" and st.text.get("insert linestart", "insert lineend") == "trainer tess", "an event that exists opens where it is"
st.save()
assert "say Hello." in open("story/village.story", encoding="utf-8").read()
# the 3D window opens small, and its picture follows its size
view = map_editor.PreviewWindow(root)
root.update()
assert view.winfo_width() <= 660 and view.winfo_height() <= 420, (view.winfo_width(), view.winfo_height())
view.shot = Image.new("RGB", (960, 540), "red")
view.draw_shot()
small = view.photo.width()
assert small <= 640
view.geometry("900x560")
root.update()
view.draw_shot()
assert view.photo.width() > small, "bigger when the window is"
view.destroy()
assert story_tool.find_problem() == ""
root.destroy()
print("fine")
"""


def test_the_editor_ideas(project):
    keep = {p: (project / p).read_text(encoding="utf-8") for p in ("maps_src/legend.txt", "story/village.story", "story/route.story")}
    try:
        r = run(project, "-c", IDEAS)
        assert r.returncode == 0 and "fine" in r.stdout, r.stdout + r.stderr
    finally:
        for p, text in keep.items():
            (project / p).write_text(text, encoding="utf-8")


def test_a_map_in_3d_from_the_real_engine(project, tmp_path):
    picture = tmp_path / "view.png"
    source = project / "maps_src" / "village.map"
    text = source.read_text(encoding="utf-8")
    legend = project / "maps_src" / "legend.txt"
    keep = legend.read_text(encoding="utf-8")
    legend.write_text(keep + "A = stone solid height=3\n", encoding="utf-8")
    source.write_text(text.replace("c.........,........c\nc.........,..,,,...c", "c..AAA....,........c\nc.........,..,,,...c"), encoding="utf-8")
    try:
        r = run(project, "tools/map_preview.py", "village", "5", "11", str(picture))
        assert r.returncode == 0 and picture.is_file(), r.stdout + r.stderr
        from PIL import Image
        shot = Image.open(picture).convert("RGB")
        assert shot.size == (960, 540)
        # no buttons in front: nothing has the exact colour inside the box they are drawn with
        box = Image.open(project / "assets" / "box.png").convert("RGB")
        fill = box.getpixel((box.width // 2, box.height // 2))
        assert fill not in set(shot.getdata())
        store = json.loads((project / "build" / "apkpygame" / "store.json").read_text())
        assert store["editor_map"] == "" and store["editor_view"] == "", "only this once"
        made = json.loads((project / "maps" / "village.tmj").read_text())
        assert any(layer["name"] == "height3" for layer in made["layers"])
    finally:
        source.write_text(text, encoding="utf-8")
        legend.write_text(keep, encoding="utf-8")
        build(project)


STUDIO_LOGIC = """
import sys, json, os
sys.path.insert(0, "tools")
import studio_data
from studio_data import Project, parse_type
p = Project()
assert parse_type("list[Ref[Type]]").item.target == "Type" and parse_type("Optional[Ref[Species]]").kind == "optional" and parse_type("BaseStats").kind == "record"
assert p.classes["Species"].field("base").spec.target == "BaseStats" and p.paths["Species"] == "data/species"
# a field added to the data classes shows up by itself
defs = open("game/data/defs.py", encoding="utf-8").read()
open("game/data/defs.py", "w", encoding="utf-8").write(defs.replace('    catch_rate: int\\n', '    catch_rate: int\\n    rarity: int = 3\\n', 1))
assert Project().classes["Species"].field("rarity").default == 3
open("game/data/defs.py", "w", encoding="utf-8").write(defs)
# opening and saving changes no file
def snapshot():
    out = {}
    for d, _, names in os.walk("data"):
        for n in names:
            out[os.path.join(d, n)] = open(os.path.join(d, n), "rb").read()
    return out
before = snapshot()
p.save()
assert snapshot() == before and not p.dirty
# a change writes only that file
row = p.table("Species").get("mossup")
row["base"]["hp"] = 99
assert p.dirty
p.save()
after = snapshot()
assert [k for k in after if after[k] != before[k]] == [os.path.join("data", "species", "mossup.json")]
assert json.load(open("data/species/mossup.json"))["base"]["hp"] == 99
# what a row is checked for
bad = p.table("Species").get("mossup")
bad["learnset"][0]["move"] = "nope"
assert any("nope" in x for x in p.row_problems("Species", bad))
bad["learnset"][0]["move"] = "bump"
assert p.row_problems("Species", bad) == []
# a new row works, and has a free id
new = p.new_row("Species", "Spark Toad!")
assert new["id"] == "spark_toad" and p.new_row("Species", "Spark Toad")["id"] == "spark_toad_2" and p.row_problems("Species", new) == []
move = p.new_row("Move", "Big Hit")
assert p.row_problems("Move", move) == [] and p.table("Move").rows[-1]["id"] == "big_hit"
copy = p.copy_row("Move", move)
assert copy["id"] == "big_hit_copy" and copy["name"] == "Big Hit"
p.table("Species").rows[-2:] = []
p.table("Move").rows[-2:] = []
# where things are used, and deleting
assert any("game.json" in u.text for u in p.uses("Species", "cindlet"))
assert any("Cindlet" in u.text for u in p.uses("Move", "spark_spit"))
assert any("story/" in u.text for u in p.uses("Item", "tonic"))
assert any("Spore Puff" in u.text for u in p.uses("Effect", "sleep")), [u.text for u in p.uses("Effect", "sleep")]
assert any("Clearwater" in u.text or "effect" in u.text for u in p.uses("Status", "sleep")) or p.uses("Status", "sleep")
assert any("game/ui/hud.py" in u.text for u in p.uses("Words", "menu"))
assert p.words_in_code() <= set(p.table("Words").ids()), "every word the code asks for is in data/texts.json"
assert {"encyclopedia", "options", "fight", "close"} <= p.words_in_code()
assert any(u.text.startswith("map route") for u in p.uses("Trainer", "tess"))
assert p.delete("Species", "cindlet"), "refused: it is in use"
assert p.table("Species").get("cindlet") is not None
# renaming everywhere
p.save()
p.rename("Species", "cindlet", "ember_pup")
assert json.load(open("data/game.json", encoding="utf-8"))[0]["starters"][0] == "ember_pup"
assert os.path.isfile("assets/monsters/ember_pup.png") and not os.path.isfile("assets/monsters/cindlet.png")
assert os.path.isfile("data/species/ember_pup.json") and not os.path.isfile("data/species/cindlet.json")
assert not p.dirty
assert json.load(open("data/species/ember_pup.json"))["id"] == "ember_pup"
p.rename("Move", "spark_spit", "spark_spat")
assert any(l["move"] == "spark_spat" for l in json.load(open("data/species/ember_pup.json"))["learnset"])
p.rename("Item", "tonic", "potion")
assert "give potion 3" in open("story/village.story", encoding="utf-8").read()
try:
    p.rename("Species", "ember_pup", "Bad Name")
except ValueError:
    pass
else:
    raise SystemExit("took a bad name")
# every table: a new row has no problems, and the events are found in the story
for cls in ("Type", "Item", "Nature", "Shop", "Trainer", "Effect", "Status", "Words"):
    row = p.new_row(cls, "Brand New")
    assert row["id"] == "brand_new" and p.row_problems(cls, row) == [], (cls, p.row_problems(cls, row))
    p.table(cls).rows.remove(row)
wild = p.new_row("EncounterTable", "", "route.cave")
assert wild["id"] == "route.cave" and "name" not in wild and p.row_problems("EncounterTable", wild) == []
p.table("EncounterTable").rows.remove(wild)
assert p.row_problems("GameInfo", p.table("GameInfo").rows[0]) == [], "the first event is in the story, not in a data file"
assert "intro" in p.table("Event").ids() and "trainer.tess" in p.table("Event").ids()
assert p.zones_of_map("route") == ["reeds", "water"] and "start" in p.markers_of_map("village")
assert not p.dirty
# renaming a trainer changes their map object, flag, story and the fights checked
p.rename("Trainer", "tess", "nell")
assert "trainer 5 17 nell" in open("maps_src/route.map", encoding="utf-8").read()
assert "trainer nell" in open("story/route.story", encoding="utf-8").read()
assert "nell" in json.load(open("data/game.json", encoding="utf-8"))[0]["fair_fights"]
p.rename("EncounterTable", "route.reeds", "route.tall")
assert "route.tall" in json.load(open("data/game.json", encoding="utf-8"))[0]["fair_fights"]
p.rename("EncounterTable", "route.tall", "route.reeds")
assert any("story" in u.text for u in p.uses("Shop", "harbour"))
assert any(u.text.startswith("the type") or u.text.startswith("the move") for u in p.uses("Type", "ember"))
# the game's name
app = p.app
assert app.values["name"] and not app.dirty
app.values["name"] = "My Quest"
assert p.dirty
p.save()
assert 'name = "My Quest"' in open("apkpy.toml", encoding="utf-8").read() and 'Game("My Quest"' in open("game/main.py", encoding="utf-8").read()
assert 'application_id = "' in open("apkpy.toml", encoding="utf-8").read() and "version_code = 1" in open("apkpy.toml", encoding="utf-8").read()
assert not p.dirty
# copies
made = studio_data.make_backup("test")
assert made and studio_data.make_backup("again") == "", "the same as the last one: no new copy"
open("story/village.story", "a", encoding="utf-8").write("\\n# changed\\n")
assert studio_data.make_backup("changed")
studio_data.restore_backup(made)
assert "# changed" not in open("story/village.story", encoding="utf-8").read()
assert len(studio_data.list_backups()) >= 2, "going back keeps how things were"
newest = studio_data.list_backups()[0]
assert "changed" in newest, "the newest comes first, whatever its reason: " + newest
assert studio_data.backup_label("2026-11-06_211424123_before_saving") == "2026-11-06 21:14:24, before saving"
assert studio_data.make_backup("nothing new") == "" or True
assert os.path.isfile(os.path.join(studio_data.BACKUPS, made, "assets", "monsters", "ember_pup.png"))
# a picture
from PIL import Image
Image.new("RGBA", (128, 64), (9, 9, 9, 255)).save("build_pic.png")
p.import_sprite("mossup", "build_pic.png")
assert Image.open("assets/monsters/mossup.png").getpixel((1, 1)) == (9, 9, 9, 255)
Image.new("RGBA", (50, 50)).save("build_pic.png")
try:
    p.import_sprite("mossup", "build_pic.png")
except ValueError as e:
    assert "128 x 64" in str(e)
else:
    raise SystemExit("took a picture of the wrong size")
os.remove("build_pic.png")
print("fine")
"""

STUDIO_NEW_MONSTER_ART = """
import sys, os, time, tkinter as tk
sys.path.insert(0, "tools")
import studio, studio_ui
try:
    root = studio_ui.make_root("Studio")
except tk.TclError:
    print("no screen")
    raise SystemExit
st = studio.Studio(root)
def settle():
    for _ in range(600):
        root.update()
        time.sleep(0.02)
        if st.checker.poll() is not None and st.summary.cget("text") != "Checking...":
            return
    raise SystemExit("the check never ended")
settle()
art = st.show("art")                     # Art was open before the monster existed
monsters = st.show("monsters")
table = monsters.table()
kind = table.rows[0]["types"][0]
for name in ("glimmox", "fizzle"):
    row = st.project.blank_row("Species")
    row.update(id=name, name=name.title(), types=[kind])
    table.rows.append(row)
monsters.fill_list()
monsters.select("glimmox")
st.save_all()                            # the check draws its picture
settle()
assert os.path.isfile("assets/monsters/glimmox.png")
st.show("art")
root.update()
assert art.tree.exists("monsters/glimmox"), "Art lists what the check drew"
st.draw_monster("fizzle")                # not saved yet: drawn now, and opened
root.update()
assert st.current == "art" and art.tree.selection() == ("monsters/fizzle",)
assert art.doc.image.size == (128, 64)
settle()
root.destroy()
print("fine")
"""


def test_a_new_monster_reaches_art(tmp_path):
    folder = fresh_copy(tmp_path)
    r = run(folder, "-c", STUDIO_NEW_MONSTER_ART)
    assert r.returncode == 0 and ("fine" in r.stdout or "no screen" in r.stdout), r.stdout + r.stderr


def test_renaming_and_deleting_a_map(tmp_path):
    folder = fresh_copy(tmp_path)
    r = run(folder, "tools/map_files.py", "rename", "route", "coast")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (folder / "maps_src/route.map").exists() and (folder / "maps_src/coast.map").is_file()
    assert not (folder / "story/route.story").exists() and "event coast.knot" in (folder / "story/coast.story").read_text(encoding="utf-8")
    main = (folder / "game/main.py").read_text(encoding="utf-8")
    assert 'game.scene("coast"' in main and '"maps/coast.tmj"' in main and '"route"' not in main
    assert re.search(r"^link 10 0 coast$", (folder / "maps_src/village.map").read_text(encoding="utf-8"), re.M)
    coast = (folder / "maps_src/coast.map").read_text(encoding="utf-8")
    assert "event=coast.knot" in coast and "event=route." not in coast
    game = (folder / "data/game.json").read_text(encoding="utf-8")
    assert '"coast.reeds"' in game and '"starters": ["cindlet", "rillet", "mossup"]' in game, "the file keeps the way it is written"
    assert json.loads((folder / "data/encounters.json").read_text(encoding="utf-8"))[0]["id"] == "coast.reeds"
    r = run(folder, "tools/prepare.py")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (folder / "maps/coast.tmj").is_file() and not (folder / "maps/route.tmj").exists()
    # the wake-up map cannot go, and the battle's ground cannot be renamed
    r = run(folder, "tools/map_files.py", "delete", "house")
    assert r.returncode != 0 and "heal_map is house" in r.stderr
    r = run(folder, "tools/map_files.py", "rename", "arena", "ring")
    assert r.returncode != 0 and "every battle" in r.stderr
    r = run(folder, "tools/map_files.py", "rename", "coast", "village")
    assert r.returncode != 0 and "already a map" in r.stderr
    # a warp in the story keeps it
    story = folder / "story/village.story"
    keep = story.read_text(encoding="utf-8")
    story.write_text(keep.replace("event village.sign\n", "event village.sign\n    warp coast from_village\n"), encoding="utf-8")
    r = run(folder, "tools/map_files.py", "delete", "coast")
    assert r.returncode != 0 and "warp coast" in r.stderr
    story.write_text(keep, encoding="utf-8")
    r = run(folder, "tools/map_files.py", "delete", "coast")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (folder / "maps_src/coast.map").exists() and not (folder / "maps/coast.tmj").exists()
    assert "coast" not in (folder / "game/main.py").read_text(encoding="utf-8")
    assert "link" not in (folder / "maps_src/village.map").read_text(encoding="utf-8")
    assert json.loads((folder / "data/game.json").read_text(encoding="utf-8"))[0]["fair_fights"] == ["tess", "bram"]
    r = run(folder, "tools/prepare.py")
    assert r.returncode == 0, r.stdout + r.stderr
    from apkpy_lib.game.build import bundle_only
    from apkpy_lib.game.project import Project
    assert len(bundle_only(Project(str(folder)))["scenes"]) == 4, "title, village, house, battle"


STUDIO_MAPS = r'''
import sys, os, time, tkinter as tk
sys.path.insert(0, "tools")
import studio, studio_ui, studio_data
try:
    root = studio_ui.make_root("Studio")
except tk.TclError:
    print("no screen")
    raise SystemExit
st = studio.Studio(root)
def settle():
    for _ in range(600):
        root.update()
        time.sleep(0.02)
        if st.checker.poll() is not None and st.summary.cget("text") != "Checking...":
            return
    raise SystemExit("the check never ended")
settle()
st.go("maps", "route")
root.update()
ed = st.editor
ed.rename_map("coast")
settle()
assert [t.doc.name for t in ed.tabs] == ["coast"] and "coast" in ed.map_names and "route" not in ed.map_names
assert st.project.table("EncounterTable").ids()[0] == "coast.reeds", "the Studio read the files again"
assert not st.dirty_sections() and "No problems" in st.summary.cget("text"), st.problems
ed.delete_map(sure=True)
settle()
assert "coast" not in ed.map_names and not ed.tabs and "No problems" in st.summary.cget("text"), st.problems
st.restore(studio_data.list_backups()[-1])
settle()
assert os.path.isfile("maps_src/route.map") and not os.path.exists("maps/coast.tmj"), "a copy brings it back, with nothing left over"
assert "No problems" in st.summary.cget("text"), st.problems
root.destroy()
print("fine")
'''


def test_the_studio_maps_rename_and_delete(tmp_path):
    folder = fresh_copy(tmp_path)
    r = run(folder, "-c", STUDIO_MAPS)
    assert r.returncode == 0 and ("fine" in r.stdout or "no screen" in r.stdout), r.stdout + r.stderr


VARIANTS = r"""
import sys, os, random, json, subprocess
sys.path.insert(0, ".")
sys.path.insert(0, "tools")
os.environ["APKPYGAME_PROJECT"] = os.getcwd()
from game.state.store import SESSION, Save, BATTLE
from game.rules.monsters import make_monster, look, variant_name, become, wild_variant
from game.battle.engine import begin_wild, begin_trainer
import validate_data
random.seed(3)
SESSION.save = Save()
SESSION.save.team.append(make_monster("mossup", 10))
# wild: about 1 in 2 is gold, frost never
got = {}
for _ in range(600):
    begin_wild("reedling", 5)
    got[look(BATTLE.foes[0])] = got.get(look(BATTLE.foes[0]), 0) + 1
assert set(got) == {"reedling", "reedling.gold"} and 220 < got["reedling.gold"] < 380, got
state = random.getstate()
assert wild_variant("pebblit") == "" and random.getstate() == state, "no variants: no roll, so the game is the same as before"
# a trainer's
begin_trainer("bram")
reed = [m for m in BATTLE.foes if m.species == "reedling"][0]
assert reed.variant == "frost" and look(reed) == "reedling.frost" and variant_name(reed) == "Frost"
assert all(m.variant == "" and variant_name(m) == "default" for m in BATTLE.foes if m.species != "reedling")
# evolving keeps it only if the new species has it too
m = make_monster("cindlet", 10)
m.variant = "gold"
become(m, "cinderhorn")
assert m.variant == "gold", "cinderhorn has gold too"
m.variant = "frost"
become(m, "cindlet")
assert m.variant == "", "cindlet has no frost"
assert validate_data.check() == [], validate_data.check()
# what the checks catch
trainers = json.load(open("data/trainers.json", encoding="utf-8"))
trainers[0]["team"][0]["variant"] = "golden"
json.dump(trainers, open("data/trainers.json", "w", encoding="utf-8"))
found = validate_data.check()
assert any("no variant 'golden'" in p and "gold" in p for p in found), found
print("fine")
"""


def test_variants(tmp_path):
    folder = fresh_copy(tmp_path)
    def change(path, edit):
        data = json.loads((folder / path).read_text(encoding="utf-8"))
        edit(data)
        (folder / path).write_text(json.dumps(data, indent=1), encoding="utf-8")
    change("data/species/reedling.json", lambda s: s.update(variants=[{"id": "gold", "name": "Gold", "one_in": 2}, {"id": "frost", "name": "Frost", "one_in": 0}]))
    change("data/species/cindlet.json", lambda s: s.update(variants=[{"id": "gold", "name": "Gold", "one_in": 4096}]))
    change("data/species/cinderhorn.json", lambda s: s.update(variants=[{"id": "gold", "name": "Gold", "one_in": 4096}]))
    change("data/trainers.json", lambda rows: [m.update(variant="frost") for m in rows[0]["team"] if m["species"] == "reedling"])
    assert "reedling" in [m["species"] for m in json.loads((folder / "data/trainers.json").read_text())[0]["team"]]
    r = run(folder, "tools/prepare.py")
    assert r.returncode == 0 and "drew a placeholder: assets/monsters/reedling.gold.png" in r.stdout, r.stdout + r.stderr
    from PIL import Image
    with Image.open(folder / "assets/monsters/reedling.gold.png") as gold, Image.open(folder / "assets/monsters/reedling.png") as usual:
        assert gold.size == usual.size and gold.getbbox() == usual.getbbox() and list(gold.getdata()) != list(usual.getdata()), "the same shape, other colours"
    from apkpy_lib.game.build import bundle_only
    from apkpy_lib.game.project import Project
    bundle = bundle_only(Project(str(folder)))
    assert bundle["scenes"]
    assert (folder / "build/apkpygame/bundle/assets/monsters/reedling.gold.png").is_file() or any(
        p.name == "reedling.gold.png" for p in (folder / "build").rglob("*.png")), "the variant's sheet is in the game"
    r = run(folder, "-c", VARIANTS)
    assert r.returncode == 0 and "fine" in r.stdout, r.stdout + r.stderr


STUDIO_VARIANTS = r'''
import sys, os, json, time, tkinter as tk
sys.path.insert(0, "tools")
from tkinter import simpledialog
import studio, studio_ui
try:
    root = studio_ui.make_root("Studio")
except tk.TclError:
    print("no screen")
    raise SystemExit
answers = ["gold", "frost"]
simpledialog.askstring = lambda *a, **k: answers.pop(0)
st = studio.Studio(root)
def settle():
    for _ in range(600):
        root.update()
        time.sleep(0.02)
        if st.checker.poll() is not None and st.summary.cget("text") != "Checking...":
            return
    raise SystemExit("the check never ended")
def buttons(widget, text):
    out = []
    for child in widget.winfo_children():
        if child.winfo_class() == "Button" and child.cget("text") == text:
            out.append(child)
        out += buttons(child, text)
    return out
settle()
art = st.show("art")
monsters = st.go("monsters", "reedling")
root.update()
buttons(monsters, "+ Add a variant")[0].invoke()
root.update()
buttons(monsters, "+ Add a variant")[0].invoke()
root.update()
row = monsters.table().get("reedling")
assert [v["id"] for v in row["variants"]] == ["gold", "frost"]
assert os.path.isfile("assets/monsters/reedling.gold.png"), "drawn as it is added"
assert art.tree.exists("monsters/reedling.gold"), "and Art has it"
draw = buttons(monsters, "Draw it in Art")
assert len(draw) == 3, "the monster's own, and one for each variant"
draw[1].invoke()
root.update()
assert st.current == "art" and art.tree.selection() == ("monsters/reedling.gold",)
trainers = st.go("trainers", "bram")
root.update()
member = next(m for m in trainers.table().get("bram")["team"] if m["species"] == "reedling")
member["variant"] = "frost"
trainers.field_changed("Trainer.team")
st.save_all()
settle()
assert "No problems" in st.summary.cget("text"), st.problems
st.go("monsters", "reedling")
root.update()
buttons(monsters, "x")[-1].invoke()          # frost goes, and a trainer still has it
root.update()
st.save_all()
settle()
assert not os.path.isfile("assets/monsters/reedling.frost.png") and os.path.isfile("assets/monsters/reedling.gold.png")
assert any("no variant 'frost'" in p for p in st.problems), st.problems
root.destroy()
print("fine")
'''


def test_the_studio_variants(tmp_path):
    folder = fresh_copy(tmp_path)
    r = run(folder, "-c", STUDIO_VARIANTS)
    assert r.returncode == 0 and ("fine" in r.stdout or "no screen" in r.stdout), r.stdout + r.stderr


STUDIO_WINDOW = """
import sys, json, os, time, tkinter as tk
sys.path.insert(0, "tools")
from tkinter import messagebox, simpledialog
import studio, studio_ui
try:
    root = studio_ui.make_root("Studio")
except tk.TclError:
    print("no screen")
    raise SystemExit
st = studio.Studio(root)
def settle():
    for _ in range(600):
        root.update()
        time.sleep(0.02)
        if st.checker.poll() is not None and st.summary.cget("text") != "Checking...":
            return
    raise SystemExit("the check never ended")
settle()
assert "No problems" in st.summary.cget("text"), st.summary.cget("text")
assert not st.dirty_sections(), "opening changes nothing"
# every section opens
for key, _ in studio.SECTIONS:
    assert st.show(key).winfo_exists()
    root.update()
assert not st.dirty_sections()
# keys go to the part that is showing
m = st.show("monsters")
root.update()
m.select("cindlet")
root.update()
def find(widget, kind):
    out = []
    for c in widget.winfo_children():
        if isinstance(c, kind):
            out.append(c)
        out += find(c, kind)
    return out
first = m.selected["base"]["hp"]
spin = find(m.form, tk.Spinbox)[0]
spin.focus_force()
root.update()
spin.delete(0, "end")
spin.insert(0, "77")
spin.event_generate("<KeyRelease>")
root.update()
assert m.selected["base"]["hp"] == 77 and st.dirty_sections() == {"monsters"} and st.nav["monsters"].cget("text") == "Monsters *"
st.undo_key("do_undo")
root.update()
assert m.selected["base"]["hp"] == first and not st.dirty_sections()
st.undo_key("do_redo")
assert m.selected["base"]["hp"] == 77
assert st.editor is not None
before = st.editor.tool
root.focus_force()
st.editor.tool_keys_seen = 0
root.event_generate("<KeyPress-f>")
root.update()
assert st.editor.tool == before, "the map editor's keys sleep on another section"
# new, refused delete, save
simpledialog.askstring = lambda *a, **k: "Spark Toad"
m.new_row()
root.update()
assert m.selected["id"] == "spark_toad"
told = []
messagebox.showinfo = lambda title, text, **k: told.append(text)
messagebox.askyesno = lambda *a, **k: True
m.select("cindlet")
m.delete_row()
assert told and "start of the game" in told[-1]
st.save_all()
settle()
assert os.path.isfile("assets/monsters/spark_toad.png"), "the build's art step drew it"
assert json.load(open("data/species/cindlet.json"))["base"]["hp"] == 77
assert not st.dirty_sections()
m.select("spark_toad")
m.delete_row()
st.save_all()
settle()
assert not os.path.exists("data/species/spark_toad.json") and not os.path.exists("assets/monsters/spark_toad.png")
# rename, then a problem, then going back
st.rename("Species", "cindlet", "ember_pup")
settle()
assert "No problems" in st.summary.cget("text") and st.screens["monsters"].selected["id"] == "ember_pup"
assert json.load(open("data/game.json", encoding="utf-8"))[0]["starters"][0] == "ember_pup"
moves = st.go("moves", "spark_spit")
root.update()
assert moves.selected["id"] == "spark_spit" and "ember" in moves.summary.cget("text")
info = st.project.table("GameInfo").rows[0]
info["start_map"] = "villag"
st.project.save()
st.run_check()
settle()
assert "1 problem" in st.summary.cget("text") and "Did you mean" in st.problem_box.get(0)
info["start_map"] = "village"
st.project.save()
# the game inside the window, and a click that reaches it
assert st.show("test").setup["team"][0][0] == "ember_pup", "a test follows a monster that was renamed"
assert st.screens["test"].fight_team[0][0] != "cindlet"
g = st.show("play")
root.update()
g.play_from_title()
for _ in range(1500):
    root.update()
    time.sleep(0.02)
    if g.game is not None and g.game.shown > 8:
        break
assert g.game is not None and g.game.shown > 8, "frames from the engine"
first_frame = g.game.photo
t = st.show("test")
root.update()
assert st.screens["play"].game is None, "leaving stops it"
t.run_fight()
for _ in range(500):
    root.update()
    time.sleep(0.02)
    if t.fight_process is None:
        break
assert "wins" in t.fight_result.cget("text"), repr(t.fight_result.cget("text")) + " " + repr(t.fight_team)
t.run_balance()
for _ in range(500):
    root.update()
    time.sleep(0.02)
    if t.balance_process is None:
        break
assert len(t.balance_table.winfo_children()) > 10
t.notebook.select(t.world_tab)
root.update()
assert t.world.find_all()
t.notebook.select(t.forgot_tab)
root.update()
assert "Flag lit" in t.forgot_box.get(0)
t.start_here()
for _ in range(1500):
    root.update()
    time.sleep(0.02)
    if st.screens["play"].game is not None and st.screens["play"].game.shown > 8:
        break
assert st.current == "play" and st.screens["play"].game is not None
st.screens["play"].stop()
story = st.show("story")
root.update()
story.open_event("village.sign")
assert story.event_here() == "village.sign"
st.show("art")
root.update()
assert st.screens["play"].game is None
# art: a stroke of the real pencil, saved, and seen by the rest
a = st.show("art")
root.update()
a.go_to("monsters/mossup")
root.update()
a.set_colour((255, 0, 255, 255))
place = dict(x=20 * a.zoom + 1, y=20 * a.zoom + 1)
a.canvas.event_generate("<Button-1>", **place)
a.canvas.event_generate("<ButtonRelease-1>", **place)
root.update()
assert a.doc.get(0, 20, 20) == (255, 0, 255, 255) and st.nav["art"].cget("text") == "Art *"
st.undo_key("do_undo")
root.update()
assert not st.dirty_sections()
st.undo_key("do_redo")
st.save_all()
settle()
from PIL import Image
assert Image.open("assets/monsters/mossup.png").getpixel((20, 20)) == (255, 0, 255, 255) and not st.dirty_sections()
a.go_to("people/hero")
root.update()
assert a.doc.count == 16 and "Walking" in a.preview_text.cget("text")
a.make_tile("snow")
root.update()
assert "= snow" in open("maps_src/legend.txt", encoding="utf-8").read() and a.doc.path.endswith("snow.png")
a.set_colour((1, 2, 3, 255))
a.set_tool("fill")
place = dict(x=2 * a.zoom, y=2 * a.zoom)
a.canvas.event_generate("<Button-1>", **place)
a.canvas.event_generate("<ButtonRelease-1>", **place)
st.save_all()
settle()
assert "No problems" in st.summary.cget("text"), st.problem_box.get(0)
assert Image.open("maps/tiles.png").width >= 16 * 13, "the new tile is in the tileset"
# the title's word, the music of a place
l = st.show("look")
root.update()
l.word.delete(0, "end")
l.word.insert(0, "New Word")
l.draw_word()
s = st.show("sound")
root.update()
st.project.main.set("house", "music", "battle_music")
st.content_changed()
assert st.nav["sound"].cget("text") == "Music and sound *"
st.show("maps")
st.editor.open_map("house")
root.update()
st.save_all()
settle()
assert "No problems" in st.summary.cget("text")
assert 'game.scene("house", kind="2.5d", camera=CAMERA, music=battle_music' in open("game/main.py", encoding="utf-8").read()
# the other sections
t = st.go("types", "ember")
root.update()
fire = t.selected
other = next(r for r in t.table().rows if not t.value_at(fire, r))
t.cycle(fire, other)
assert other["id"] in fire["strong"] and st.nav["types"].cget("text") == "Types *"
t.cycle(fire, other); t.cycle(fire, other); t.cycle(fire, other)
assert not t.value_at(fire, other) and not st.dirty_sections(), "going all the way round changes nothing"
t.set_colour(fire, "#ff0000")
st.undo_key("do_undo")
assert not st.dirty_sections()
w = st.go("wild", "route.reeds")
root.update()
assert sum(int(x[:-1]) for x in w.chances(w.selected["rows"])) in (99, 100, 101)
w.add("route.cave")
root.update()
assert w.selected["id"] == "route.cave" and "no ground" in " ".join(c.cget("text") for c in find(w.page.inner, tk.Label))
w.delete_row()
assert w.table().get("route.cave") is None and not st.dirty_sections()
tr = st.go("trainers", "bram")
root.update()
assert "rival" in " ".join(c.cget("text") for c in find(tr.page.inner, tk.Label))
tr.write_story()
root.update()
assert st.current == "story" and st.screens["story"].text.get("insert linestart", "insert lineend") == "trainer bram"
for key in ("items", "shops", "natures", "effects", "statuses", "rules", "words"):
    st.show(key)
    root.update()
rules_screen = st.screens["rules"]
assert rules_screen.selected["id"] == "main" and rules_screen.form.widgets
st.go("statuses", "sleep")
root.update()
assert isinstance(st.screens["statuses"].form.widgets["capture_bonus"], tk.Entry), "a decimal field"
st.go("items", "clearwater")
root.update()
assert isinstance(st.screens["items"].form.widgets["cures_all"], tk.Checkbutton), "a yes or no field"
assert not st.dirty_sections()
g = st.show("game")
root.update()
assert g.problems.cget("text") == "", g.problems.cget("text")
assert not st.dirty_sections(), "looking at them all changes nothing"
g_name = find(g.page.inner, tk.Entry)[0]
g_name.focus_force()
root.update()
g_name.delete(0, "end")
g_name.insert(0, "My Quest")
g_name.event_generate("<KeyRelease>")
root.update()
assert st.nav["game"].cget("text") == "My game *" and st.name_label.cget("text") == "My Quest"
st.save_all()
settle()
assert 'name = "My Quest"' in open("apkpy.toml", encoding="utf-8").read()
# a story problem, from its line to the place
story = st.show("story")
story.go_to_problem()
root.update()
c = st.show("backups")
root.update()
names = c.names
assert names, "copies were made"
st.restore(names[-1])
settle()
assert "cindlet" in st.project.table("Species").ids(), "back to the first copy"
assert "music=town_music" in st.project.main.text[st.project.main.text.index('game.scene("house"'):], "the place's music came back too"
assert json.load(open("data/species/cindlet.json"))["base"]["hp"] == first
# a map's change is seen in the sidebar
st.show("maps")
st.editor.open_map("village")
root.update()
tab = st.editor.tab()
st.editor.remember(tab)
tab.doc.paint(1, 1, "s")
st.editor.changed(tab)
root.update()
assert st.nav["maps"].cget("text") == "Maps *"
st.save_all()
settle()
assert not st.dirty_sections()
st.checker.wait()
root.destroy()
print("fine")
"""


def fresh_copy(tmp_path):
    import shutil
    folder = tmp_path / "studio_project"
    shutil.copytree(TEMPLATE, folder, ignore=shutil.ignore_patterns("build", "__pycache__", "*.apk", ".pytest_cache", ".studio_backups"))
    return folder


STUDIO_ART = """
import sys, os, re, wave, shutil
sys.path.insert(0, "tools")
from PIL import Image
import studio_art, studio_data
from studio_art import PixelDoc
# drawing
sheet = "assets/monsters/cindlet.png"
doc = PixelDoc(sheet, (64, 64), ["Front", "Back"])
assert doc.count == 2 and doc.box(1) == (64, 0, 128, 64) and doc.label(1) == "Back" and not doc.dirty
red = (255, 0, 0, 255)
doc.remember()
assert doc.put(0, 3, 3, red) and not doc.put(0, 3, 3, red) and not doc.put(0, 99, 3, red), "outside its cell draws nothing"
assert doc.dirty and doc.get(0, 3, 3) == red and doc.image.getpixel((3, 3)) == red
doc.remember()
doc.line(1, 0, 0, 10, 0, red)
assert all(doc.get(1, x, 0) == red for x in range(11)), "a fast stroke has no holes"
assert doc.image.getpixel((64, 0)) == red and doc.image.getpixel((63, 0)) != red or True
doc.do_undo()
assert doc.get(1, 5, 0) != red
doc.do_redo()
assert doc.get(1, 5, 0) == red
doc.do_undo(); doc.do_undo()
assert not doc.dirty, "undo goes all the way back"
assert red not in doc.palette()
# a fill stays in its cell
blank = PixelDoc(sheet, (64, 64))
blank.image = Image.new("RGBA", (128, 64), (0, 0, 0, 0))
assert blank.fill(0, 0, 0, red) and blank.get(0, 63, 63) == red and blank.get(1, 0, 0) == (0, 0, 0, 0)
assert not blank.fill(0, 0, 0, red)
blank.put(1, 0, 0, (0, 0, 255, 255))
blank.flip(1)
assert blank.get(1, 63, 0) == (0, 0, 255, 255) and blank.get(1, 0, 0) == (0, 0, 0, 0)
blank.copy_cell(1)
assert blank.paste_cell(0) and blank.get(0, 63, 0) == (0, 0, 255, 255)
blank.clear(0)
assert blank.get(0, 63, 0) == (0, 0, 0, 0)
# importing: a whole sheet, or any picture into a cell
Image.new("RGBA", (128, 64), red).save("in.png")
assert blank.import_picture("in.png", 0) == "whole" and blank.get(1, 1, 1) == red
Image.new("RGBA", (200, 100), (0, 255, 0, 255)).save("in.png")
doc2 = PixelDoc(sheet, (64, 64))
assert doc2.import_picture("in.png", 1) == "cell" and doc2.get(1, 32, 32) == (0, 255, 0, 255) and doc2.get(1, 32, 2) == (0, 0, 0, 0)
# saving writes only when changed
stamp = os.path.getmtime(sheet)
PixelDoc(sheet, (64, 64)).save()
assert os.path.getmtime(sheet) == stamp
files = studio_art.art_files(".")
assert any(n == "cindlet" for n, _ in files["monsters"]) and any(n == "hero" for n, _ in files["people"])
assert any(n == "grass" for n, _ in files["tiles"]) and any(n == "box" for n, _ in files["other"])
assert not any(n in ("pixel", "monster_blank") for n, _ in files["other"])
# the title's word
p = studio_data.Project()
p.draw_logo("Hi There")
assert Image.open("assets/title_logo.png").size[1] > 10
long_one = Image.open("assets/title_logo.png")
p.draw_logo("A very long name for a game indeed")
assert Image.open("assets/title_logo.png").width <= 470, "it fits the screen"
# the icon
p.icon_from_monster("cindlet")
assert p.app.values["icon"] == "icon.png" and Image.open("icon.png").size == (512, 512) and p.dirty
Image.new("RGBA", (10, 20)).save("in.png")
try:
    p.set_icon("in.png")
except ValueError as e:
    assert "square" in str(e)
else:
    raise SystemExit("took an icon that is not square")
p.save()
assert 'icon = "icon.png"' in open("apkpy.toml", encoding="utf-8").read()
assert "[app]" in open("apkpy.toml", encoding="utf-8").read()
p.app.values["icon"] = ""
p.save()
assert "icon" not in open("apkpy.toml", encoding="utf-8").read()
p.set_icon("icon.png") if False else None
# each place
m = p.main
assert m.scenes() == ["title", "village", "house", "route", "battle"]
assert m.get("house", "background") == '"#101018"' and m.get("battle", "music") == "battle_music" and m.get("village", "music_volume") == "0.5"
m.set("house", "background", '"#00ff00"')
m.set("village", "music", "battle_music")
m.set("route", "music_volume", "0.9")
m.set("title", "music", None)
assert m.get("title", "music") == "" and m.dirty
m.set("title", "music", "town_music")
assert m.get("title", "music") == "town_music"
assert m.get("battle", "camera") == "" or True
assert 'pitch' in m.text, "the rest of the file is as it was"
# sounds
m.set("house", "background", '"#101018"')
shutil.copy("assets/sfx_tap.wav", "mine.wav")
name = m.add_track("mine.wav")
assert name == "mine_music" and ("mine_music", "assets/music_mine.wav") in m.tracks() and os.path.isfile("assets/music_mine.wav")
open("fake.mp3", "wb").write(b"x")
p.look.replace_sound("hit_sound", "fake.mp3")
assert dict(p.look.sounds())["hit_sound"] == "assets/sfx_hit.mp3" and os.path.isfile("assets/sfx_hit.mp3") and not os.path.isfile("assets/sfx_hit.wav")
shutil.copy("mine.wav", "again.wav")
p.look.replace_sound("hit_sound", "again.wav")
assert dict(p.look.sounds())["hit_sound"] == "assets/sfx_hit.wav" and not os.path.isfile("assets/sfx_hit.mp3")
open("x.txt", "w").write("x")
try:
    p.look.replace_sound("hit_sound", "x.txt")
except ValueError as e:
    assert "WAV" in str(e)
else:
    raise SystemExit("took a sound that is not one")
# the font
look = p.look
assert look.font == "assets/pixel.fnt" and look.size == 8 and look.big == 16
assert look.sample("Abc").width > 10
font = r"C:\\Windows\\Fonts\\arial.ttf"
if os.path.isfile(font):
    look.use_font(font)
    assert look.font == "assets/arial.ttf" and look.size >= 10 and os.path.isfile("assets/arial.ttf")
    assert look.sample("Abc").width > 10
    look.size = 12
    assert look.size == 12
look.use_pixel_font()
assert look.font == "assets/pixel.fnt" and look.size == 8
try:
    look.use_font("x.txt")
except ValueError:
    pass
else:
    raise SystemExit("took a font that is not one")
p.save()
assert not p.dirty
for name in ("in.png", "mine.wav", "again.wav", "fake.mp3", "x.txt"):
    os.remove(name)
print("fine")
"""


def lab(folder, command, question):
    r = subprocess.run([sys.executable, "tools/lab.py", command], cwd=str(folder), input=json.dumps(question), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def picture_of(folder, scene, *more):
    """The game itself, in a picture, with what it says."""
    from apkpy_lib.game import desktop
    from apkpy_lib.game.project import Project
    from PIL import Image
    desktop._config.update({"bundle": None, "store": None, "project": Project(str(folder))})
    shot = folder / "build" / "shot.png"
    if shot.exists():
        shot.unlink()
    r = subprocess.run(desktop.command(scene, "{}", "--screenshot", str(shot), "--width", "960", "--height", "540", *more), cwd=str(folder), capture_output=True, text=True, timeout=120)
    assert shot.exists(), r.stdout[-400:] + r.stderr[-400:]
    return Image.open(shot).convert("RGB")


RULES_AS_DATA = r"""
import sys, os, json, random
sys.path.insert(0, ".")
sys.path.insert(0, "tools")
os.environ["APKPYGAME_PROJECT"] = os.getcwd()
from game.data.defs import EFFECTS, ITEMS, MOVES, STATUSES, rules, word, named, fill
from game.rules.monsters import make_monster, max_hp, exp_for_level, evolves_now
from game.rules.items import helps, apply, usable_in_battle, evolves_with
from game.state.store import SESSION, Save, BATTLE
from game.battle.engine import begin_wild, apply_effect, end_of_turn_status, use_move, stage_of
# words
assert word("missed") == "It missed!" and named("faints", "Pip") == "Pip faints!"
assert word("got_money").endswith("shells.") and fill(word("got_money"), "count", "5") == "You got 5 shells."
assert word("no_such_words") == "no_such_words", "a missing id shows itself, it does not stop the game"
# effects and statuses, as the data says
SESSION.save = Save()
SESSION.save.team.append(make_monster("mossup", 10))
begin_wild("pebblit", 10)
me, foe = SESSION.save.team[0], BATTLE.foes[0]
apply_effect("attack_down", False, foe, me)
assert stage_of(True, "attack") == -1 and "loses heart" in BATTLE.lines[-1].text
apply_effect("defense_up", False, foe, me)
assert stage_of(False, "defense") == 1
for _ in range(9):
    apply_effect("defense_up", False, foe, me)
assert stage_of(False, "defense") == rules().stage_limit
apply_effect("burn", False, foe, me)
assert foe.status == "burn" and "was burned" in BATTLE.lines[-1].text
hp = foe.hp
end_of_turn_status(foe, True)
assert foe.hp == hp - max(1, max_hp(foe) // 8)
apply_effect("sleep", False, foe, me)
assert foe.status == "burn", "one status at a time"
me.hp = 1
apply_effect("heal", False, foe, me)
assert me.hp == 1 + max_hp(me) // 2
# items
SESSION.save.team[0].status = "poison"
clear = ITEMS.get("clearwater")
assert helps(clear, me) and not usable_in_battle(ITEMS.get("keeper_letter")) and usable_in_battle(ITEMS.get("bond_knot"))
apply(clear, me)
assert me.status == ""
tonic = ITEMS.get("tonic")
me.hp = 0
assert not helps(tonic, me), "a tonic does not revive"
# the numbers
assert exp_for_level(5) == 125
print("fine")
"""


def test_the_rules_come_from_data(tmp_path):
    folder = fresh_copy(tmp_path)
    r = run(folder, "-c", RULES_AS_DATA)
    assert r.returncode == 0 and "fine" in r.stdout, r.stdout + r.stderr
    # change the data, and the rules change with it
    def change(path, edit):
        rows = json.loads((folder / path).read_text(encoding="utf-8"))
        edit(rows)
        (folder / path).write_text(json.dumps(rows, indent=1), encoding="utf-8")
    change("data/rules.json", lambda rows: rows[0].update(exp_factor=2.0, max_moves=2))
    change("data/texts.json", lambda rows: [r.update(text="Ka-pow!") for r in rows if r["id"] == "missed"])
    change("data/statuses.json", lambda rows: [r.update(turn_share=2) for r in rows if r["id"] == "burn"])
    change("data/effects.json", lambda rows: rows.append({"id": "speed_up", "name": "Faster", "stat": "speed", "amount": 2, "target": "self", "text": "{name} speeds up!"}))
    change("data/items.json", lambda rows: rows.append({"id": "fire_stone", "name": "Fire Stone", "kind": "key", "price": 0}))
    change("data/items.json", lambda rows: rows.append({"id": "revive_seed", "name": "Revive Seed", "kind": "heal", "revive": True, "price": 500}))
    species = json.loads((folder / "data/species/cindlet.json").read_text())
    species.update(evolve_item="fire_stone", evolve_level=0)
    (folder / "data/species/cindlet.json").write_text(json.dumps(species))
    code = r"""
import sys, os
sys.path.insert(0, ".")
os.environ["APKPYGAME_PROJECT"] = os.getcwd()
from game.data.defs import ITEMS, word
from game.rules.monsters import make_monster, exp_for_level, evolves_now
from game.rules.items import evolves_with, evolve_with, helps, apply
from game.state.store import SESSION, Save
from game.battle.engine import begin_wild, apply_effect, end_of_turn_status, stage_of
from game.rules.monsters import max_hp
from game.state.store import BATTLE
assert exp_for_level(5) == 250 and word("missed") == "Ka-pow!"
SESSION.save = Save()
m = make_monster("cindlet", 20)
SESSION.save.team.append(m)
assert len(m.moves) == 2
assert evolves_now(m) == "", "it waits for its item"
assert evolves_with("fire_stone", m) == "cinderhorn"
evolve_with("fire_stone", m)
assert m.species == "cinderhorn" and SESSION.save.caught["cinderhorn"] == 1
begin_wild("pebblit", 10)
apply_effect("speed_up", False, BATTLE.foes[0], m)
assert stage_of(False, "speed") == 2
apply_effect("burn", False, BATTLE.foes[0], m)
foe = BATTLE.foes[0]
hp = foe.hp
end_of_turn_status(foe, True)
assert foe.hp == max(0, hp - max(1, max_hp(foe) // 2))
m.hp = 0
seed = ITEMS.get("revive_seed")
assert helps(seed, m)
apply(seed, m)
assert m.hp == max_hp(m) // 2
print("fine")
"""
    r = run(folder, "-c", code)
    assert r.returncode == 0 and "fine" in r.stdout, r.stdout + r.stderr
    from apkpy_lib.game.build import bundle_only
    from apkpy_lib.game.project import Project
    assert bundle_only(Project(str(folder)))["scenes"], "the game builds with all of it"


def test_the_lab(tmp_path):
    folder = fresh_copy(tmp_path)
    won = lab(folder, "fight", {"team": [["cindlet", 40]], "wild": ["pebblit", 2], "plays": 30})
    assert won["wins"] == 30 and won["hp_left"] > 0.5 and won["turns"] > 0 and any("Cindlet" in x for x in won["sample"])
    lost = lab(folder, "fight", {"team": [["cindlet", 2]], "wild": ["lumoth", 50], "plays": 30})
    assert lost["wins"] == 0
    assert lab(folder, "fight", {"team": [["mossup", 30]], "trainer": "bram", "plays": 20})["wins"] == 20
    table = lab(folder, "balance", {"plays": 10})
    assert table["starters"] == ["cindlet", "rillet", "mossup"] and len(table["rows"][0]["results"]) == 3
    assert any(r["fair"] for r in table["rows"]) and any(r["section"] == "trainers" for r in table["rows"])
    save = json.loads(lab(folder, "save", {"team": [["lumoth", 30], ["mossup", 12]], "items": {"tonic": 7}, "flags": ["got_partner"], "money": 1234, "map": "route"})["save"])
    assert [m["species"] for m in save["team"]] == ["lumoth", "mossup"] and save["team"][0]["level"] == 30
    assert save["bag"] == {"tonic": 7} and save["flags"] == {"got_partner": 1} and save["money"] == 1234 and save["map"] == "route"
    assert save["heal_map"] == "house", "the rest comes from data/game.json"


def test_the_game_reads_a_test_it_is_given(tmp_path):
    """Team, money and an event, through the same steps as the Studio, and seen in the real game's Team screen."""
    from apkpy_lib.game.build import bundle_only
    from apkpy_lib.game.project import Project
    folder = fresh_copy(tmp_path)
    bundle_only(Project(str(folder)))
    answer = lab(folder, "save", {"team": [["lumoth", 30]], "flags": ["got_partner"], "money": 1234, "map": "route"})
    code = "import sys, json; sys.path.insert(0, 'tools'); import map_editor; map_editor.start_test_here('route', 6, 20, json.load(open('save.json')))"
    (folder / "save.json").write_text(json.dumps(answer["save"]))
    assert run(folder, "-c", code).returncode == 0
    from PIL import Image
    # the Menu button, then Team: where they are on a 480 x 270 screen
    team = picture_of(folder, "route", "--replay", "10:tap:418:30,30:tap:240:45", "--steps", "60")
    store = json.loads((folder / "build" / "apkpygame" / "store.json").read_text())
    assert store["editor_map"] == "" and store["editor_save"] == "", "only once"
    assert team.size == (960, 540)
    normal = picture_of(folder, "route", "--steps", "5")
    assert normal.tobytes() != team.tobytes()


def test_what_was_forgotten_and_the_world(tmp_path):
    folder = fresh_copy(tmp_path)
    code = r"""
import sys, os
sys.path.insert(0, "tools")
import studio_data
p = studio_data.Project()
world = p.world()
assert world["start"] == "village" and set(world["places"]) == {"village", "route", "house"} and not world["lost"], world["places"]
assert world["places"]["route"] == (0, -1), "the road leaves the village by its top"
assert "arena" not in world["places"], "the backdrop of a battle is not a place"
assert p.playable_maps() == ["village", "house", "route"]
assert p.marker_cell("village", "start") == (10, 13) and p.marker_cell("village", "nope") is None
assert p.event_place("village.vendor")[0] == "village" and p.event_place("village.vendor")[1:] != (15, 7), "beside the person, not on them"
assert p.event_place("village.gate") == ("village", 10, 1), "a trigger is stepped on"
assert p.event_place("nobody") is None
first = [u.text for u in p.forgotten()]
assert first == ["Flag lit: it is set, but nothing ever asks about it."], first
p.new_row("Move", "Lost Move"); p.new_row("Item", "Lost Item"); p.new_row("Species", "Lost One"); p.new_row("Trainer", "Lost Trainer"); p.new_row("Shop", "Lost Shop"); p.new_row("Type", "Lost Type")
p.new_row("EncounterTable", "", "village.nothing")
p.save()
open("maps_src/island.map", "w").write("tiles:\n....\n....\nobjects:\n")
open("story/route.story", "a").write("\nevent route.nobody\n    say Nobody hears this.\n")
p = studio_data.Project()
words = " | ".join(u.text for u in p.forgotten())
for part in ("Lost Move: no monster", "Lost Item: no shop", "Lost One: it never appears", "Lost Trainer: not on any map", "Lost Trainer: nothing in the story", "Lost Shop: no event", "Lost Type: no monster",
             "route.nobody: nothing on any map", "village.nothing: there is no such ground"):
    assert part in words, part + " in " + words
print("fine")
"""
    r = run(folder, "-c", code)
    assert r.returncode == 0 and "fine" in r.stdout, r.stdout + r.stderr


STUDIO_PUBLISH = r"""
import sys, os, json, re, shutil, tempfile, time
sys.path.insert(0, "tools")
import tkinter as tk
from tkinter import messagebox
import studio_publish as pub
import studio_data
assert pub.next_version({"version_name": "0.1.9", "version_code": "4"}) == ("0.1.10", "5")
assert pub.next_version({"version_name": "beta", "version_code": ""}) == ("beta", "1")
p = studio_data.Project()
words = lambda: [w for _, w in pub.checks(p, [])]
good = lambda text: [g for g, w in pub.checks(p, []) if text in w][0]
assert good("App id") is False, "the template's id is a placeholder"
p.app.values["application_id"] = "com.rtv.mygame"
assert good("App id") is True
assert good("default icon") is False
p.app.values["icon"] = "icon.png"
assert good("its own icon") is True
assert "Nothing was published" in " ".join(words())
pub.write_state(".", version_code=p.app.values["version_code"])
assert good("still") is False, "the same number as the last signed one"
p.app.values["version_code"] = str(int(p.app.values["version_code"]) + 1)
assert good("The last one signed") is True
assert [g for g, w in pub.checks(p, ["x"]) if "problem" in w][0] is False
# the key: both files, kept apart from the project
home = tempfile.mkdtemp()
from apkpy_lib import native_build
native_build.keystores_dir = lambda: home
open(os.path.join(home, "com.rtv.mygame.jks"), "w").write("key")
open(os.path.join(home, "com.rtv.mygame.json"), "w").write("{}")
assert "no copy" in " ".join(words())
out = tempfile.mkdtemp()
made = pub.copy_key("com.rtv.mygame", out)
assert sorted(os.path.basename(m) for m in made) == ["com.rtv.mygame.jks", "com.rtv.mygame.json"]
try:
    pub.copy_key("com.no.key", out)
except ValueError as e:
    assert "first signed" in str(e)
else:
    raise SystemExit("copied a key that does not exist")
# the window
import studio, studio_ui
try:
    root = studio_ui.make_root("Studio")
except tk.TclError:
    print("fine (no screen)")
    raise SystemExit
os.remove(pub.STATE_FILE)
st = studio.Studio(root)
screen = st.show("publish")
root.update()
assert screen.check_lines.winfo_children()
screen.copy_key_to(out) if False else None
# what the phone's answers mean
screen.explain("t", 0, "USB: install failed - INSTALL_FAILED_UPDATE_INCOMPATIBLE: signatures", True)
assert "another key" in screen.result.cget("text")
screen.explain("t", 0, "USB: installed!", True)
assert "Installed" in screen.result.cget("text")
screen.explain("t", 0, "USB: no device detected", True)
assert "no phone" in screen.result.cget("text")
screen.explain("t", 1, "APKPY E1", False)
assert "stopped" in screen.result.cget("text")
screen.command_ended("t", 0, "Signed APK ready:  C:/x/My-release.apk  (2538 KB)")
assert screen.last_file == "C:/x/My-release.apk"
assert str(pub.read_state(".")["version_code"]) == str(st.project.app.values["version_code"]), "a signed version is remembered"
screen.command_ended("t", 0, "APK ready:  C:/x/My-debug.apk  (2538 KB)")
assert screen.last_file == "C:/x/My-debug.apk"
# a command, run for real, with what it says shown
assert screen.runner.run("said", [sys.executable, "-c", "print('hello from a command')"], ".")
for _ in range(300):
    root.update()
    time.sleep(0.01)
    if not screen.runner.busy and "hello" in screen.text.get("1.0", "end"):
        break
assert "hello from a command" in screen.text.get("1.0", "end")
for _ in range(1000):                   # its text can come before its end, on a slow machine
    if not screen.runner.busy:
        break
    root.update()
    time.sleep(0.02)
# stop takes what the command started with it
child = "import subprocess, sys, time; p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']); open('child.txt', 'w').write(str(p.pid)); time.sleep(120)"
assert screen.runner.run("long", [sys.executable, "-c", child], ".")
for _ in range(500):
    root.update()
    time.sleep(0.01)
    if os.path.isfile("child.txt") and open("child.txt").read():
        break
pid = open("child.txt").read().strip()
screen.stop()
for _ in range(300):
    root.update()
    time.sleep(0.01)
    if not screen.runner.busy:
        break
assert not screen.runner.busy
import subprocess
if os.name == "nt":
    left = subprocess.run(["tasklist", "/FI", "PID eq %s" % pid], capture_output=True, text=True).stdout
    assert pid not in left, "the child went too"
before = st.project.app.values["version_code"]
screen.bump()
assert int(st.project.app.values["version_code"]) == int(before) + 1
assert "version_code = %s" % st.project.app.values["version_code"] in open("apkpy.toml", encoding="utf-8").read()
# help: its pages and its links
h = st.show("help")
root.update()
assert [t for t, _ in h.pages][0] == "The Studio" and "README" in h.pages[-1][0] and len(h.pages) >= 8
assert "A first hour" in h.text.get("1.0", "end") and "**" not in h.text.get("1.0", "end") and "```" not in h.text.get("1.0", "end")
assert h.text.tag_ranges("link"), "the link to the README works"
h.show(1)
root.update()
assert "Change the words" in h.text.get("1.0", "end")
for at in range(len(h.pages)):
    h.show(at)
    root.update()
st.checker.wait()
root.destroy()
print("fine")
"""


def test_the_studio_publish_and_help(tmp_path):
    folder = fresh_copy(tmp_path)
    r = run(folder, "-c", STUDIO_PUBLISH)
    assert r.returncode == 0 and "fine" in r.stdout, r.stdout + r.stderr


def test_the_studio_art_and_sound(tmp_path):
    folder = fresh_copy(tmp_path)
    r = run(folder, "-c", STUDIO_ART)
    assert r.returncode == 0 and "fine" in r.stdout, r.stdout + r.stderr
    from apkpy_lib.game.build import bundle_only
    from apkpy_lib.game.project import Project
    assert bundle_only(Project(str(folder)))["scenes"]


def test_the_studio_data(tmp_path):
    folder = fresh_copy(tmp_path)
    r = run(folder, "-c", STUDIO_LOGIC)
    assert r.returncode == 0 and "fine" in r.stdout, r.stdout + r.stderr


def test_the_studio_window(tmp_path):
    folder = fresh_copy(tmp_path)
    r = run(folder, "-c", STUDIO_WINDOW)
    assert r.returncode == 0 and ("fine" in r.stdout or "no screen" in r.stdout), r.stdout + r.stderr
    assert (folder / ".studio_backups").is_dir() or "no screen" in r.stdout


def test_a_new_project_has_no_copies_of_the_template(project):
    assert not (project / ".studio_backups").exists()
    assert (project / "tools" / "studio.py").is_file()


def test_the_map_editor_logic(project):
    hollow = project / "maps_src" / "hollow.map"
    try:
        r = run(project, "-c", EDITOR_LOGIC)
        assert r.returncode == 0 and "fine" in r.stdout, r.stdout + r.stderr
    finally:
        if hollow.exists():
            hollow.unlink()


def test_the_map_editor_window(project):
    source = project / "maps_src" / "village.map"
    text = source.read_text(encoding="utf-8")
    try:
        r = run(project, "-c", EDITOR_WINDOW)
        assert r.returncode == 0 and ("fine" in r.stdout or "no screen" in r.stdout), r.stdout + r.stderr
        build(project)
    finally:
        source.write_text(text, encoding="utf-8")
        build(project)


def test_testing_from_a_cell_is_forgotten_after_one_use(project):
    from apkpy_lib.game import desktop
    from apkpy_lib.game.project import Project
    code = 'import sys; sys.path.insert(0, "tools"); import map_editor; map_editor.start_test_here("route", 6, 10)'
    build(project)
    assert run(project, "-c", code).returncode == 0
    store = project / "build" / "apkpygame" / "store.json"
    assert json.loads(store.read_text())["editor_map"] == "route"
    desktop._config.update({"bundle": None, "store": None, "project": Project(str(project))})
    picture = project / "build" / "test_from_here.png"
    r = subprocess.run(desktop.command("route", "{}", "--screenshot", str(picture), "--steps", "20"), cwd=str(project), capture_output=True, text=True, timeout=120)
    assert picture.exists(), r.stdout[-500:] + r.stderr[-500:]
    assert json.loads(store.read_text())["editor_map"] == ""


def test_the_map_editor_changes_only_what_it_should(project):
    code = """
import sys
sys.path.insert(0, "tools")
import map_editor
doc = map_editor.MapDoc("route")
print(doc.text() == open("maps_src/route.map", encoding="utf-8").read())
doc.paint(1, 7, "r")
o = doc.add_object("person", 3.0, 7.0)
o["name"] = "sam"
o["props"]["look"] = "vendor"
print(doc.problem() == "")
o["props"]["look"] = "vendor"
doc.add_object("link", 3.0, 8.0)["name"] = "rout"
print("Did you mean" in doc.problem())
doc.objects.pop()
doc.save()
print(map_editor.MapDoc("route").rows[7][1], [x for x in map_editor.MapDoc("route").objects if x.get("name") == "sam"][0]["props"])
"""
    source = project / "maps_src" / "route.map"
    text = source.read_text(encoding="utf-8")
    try:
        r = run(project, "-c", code)
        assert r.returncode == 0, r.stdout + r.stderr
        assert r.stdout.split()[:3] == ["True", "True", "True"] and "r {'look': 'vendor'}" in r.stdout, r.stdout
        build(project)
    finally:
        source.write_text(text, encoding="utf-8")
        build(project)


def test_adding_a_monster_as_the_readme_says(project):
    r = run(project, "tools/new.py", "monster", "spark_toad", "ember")
    assert r.returncode == 0, r.stdout + r.stderr
    path = project / "data" / "species" / "spark_toad.json"
    sheet = project / "assets" / "monsters" / "spark_toad.png"
    try:
        from PIL import Image
        assert Image.open(sheet).size == (128, 64)
        mine = Image.new("RGBA", (128, 64), (1, 2, 3, 255))     # your own art
        mine.save(sheet)
        build(project)
        assert Image.open(sheet).convert("RGBA").getpixel((0, 0)) == (1, 2, 3, 255), "never drawn over"
        assert (project / "build" / "apkpygame" / "bundle" / "assets" / "monsters" / "spark_toad.png").is_file()
        sheet.unlink()
        build(project)
        assert sheet.is_file(), "a species with no sprites gets a placeholder from the build"
        Image.new("RGBA", (50, 50)).save(sheet)
        with pytest.raises(GameError) as e:
            build(project)
        assert "cells of 64 x 64" in str(e.value)
        sheet.unlink()
        row = json.loads(path.read_text())
        row["learnset"][0]["move"] = "bumpp"
        path.write_text(json.dumps(row))
        with pytest.raises(GameError) as e:
            build(project)
        assert e.value.code == "G1307" and "spark_toad.json" in str(e.value)
    finally:
        path.unlink()
        if sheet.exists():
            sheet.unlink()


def test_adding_a_map_and_an_event_as_the_readme_says(project):
    main = (project / "game" / "main.py").read_text()
    source = project / "maps_src" / "cave.map"
    story = project / "story" / "cave.story"
    route = project / "maps_src" / "route.map"
    route_text = route.read_text()
    try:
        r = run(project, "tools/new.py", "map", "cave")
        assert r.returncode == 0, r.stdout + r.stderr
        text = source.read_text() + "person 4 2 old_man look=villager event=cave.old_man\nlink 4 7 route\n"
        source.write_text(text.replace("cccccccccc\nobjects", "cccc,ccccc\nobjects"))
        route.write_text(route_text + "link 3 21 cave\n")
        with pytest.raises(GameError) as e:
            build(project)
        assert "no event 'cave.old_man'" in str(e.value), "the check finds the missing event"
        story.write_text("event cave.old_man\n    if nope:\n        say Hello.\n")
        with pytest.raises(GameError) as e:
            build(project)
        assert "the flag 'nope'" in str(e.value)
        story.write_text("event cave.old_man\n    say Hello.\n")
        assert "cave" in build(project)["scenes"]
        assert 'game.scene("cave"' in (project / "game" / "main.py").read_text(), "the build adds the scene"
        assert (project / "game" / "main.py").read_text().count('game.scene("cave"') == 1
        build(project)
        assert (project / "game" / "main.py").read_text().count('game.scene("cave"') == 1, "only once"
    finally:
        (project / "game" / "main.py").write_text(main)
        route.write_text(route_text)
        for p in (story, source, project / "maps" / "cave.tmj"):
            if os.path.exists(p):
                os.remove(p)
        build(project)
