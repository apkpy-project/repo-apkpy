"""Data tables, JSON, saves and the properties of Tiled maps.

- a table, Ref[...], to_json / from_json and a save give the same values and the same
  JSON text in the game (JVM) and in CPython (the same module, imported);
- every kind of bad data is a G13xx error naming the file and the path inside it;
- a save read is part of the journal: a game brought back reads what the first run read;
- Tiled objects keep their custom properties (self.props), tiles their tags (scene.tile_tag).
"""
import importlib
import json
import os
import subprocess
import sys
import textwrap

import pytest

from apkpy_lib.game import engine, templates
from apkpy_lib.game._host import toolchain
from apkpy_lib.game.errors import GameError

DEFS = '''
from __future__ import annotations

from apkpy_lib.game import *
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Move:
    id: str
    power: int
    kind: str = "normal"


@dataclass
class Species:
    id: str
    name: str
    base_hp: int
    moves: list[Ref[Move]] = field(default_factory=list)
    evolves: Optional[Ref[Species]] = None
    weight: float = 1.0


MOVES = table("data/moves", Move)
SPECIES = table("data/species", Species)


@dataclass
class Save:
    version: int = 1
    team: list[str] = field(default_factory=list)
    hp: dict[str, int] = field(default_factory=dict)
    note: Optional[str] = None
    lead: Optional[Move] = None


def summary() -> str:
    out = ""
    for s in SPECIES:
        total = 0
        for m in s.moves:
            total += MOVES.get(m).power
        out = out + s.id + ":" + str(total) + ":" + str(s.weight) + ";"
    first = SPECIES.get("ember")
    nxt = first.evolves
    if nxt is not None:
        out = out + "->" + SPECIES.get(nxt).name
    return out + "|" + str(len(MOVES)) + str("drip" in SPECIES) + str(SPECIES.has("nope"))


def roundtrip() -> str:
    s = Save(team=["ember", "drip"], note="o\\"k \\u00e9\\n", lead=MOVES.get("spark"))
    s.hp["ember"] = 12
    text = to_json(s)
    back = from_json(text, Save)
    old = from_json("{\\"team\\":[\\"x\\"],\\"extra\\":5,\\"version\\":2.0}", Save)
    return text + "|" + str(back == s) + "|" + to_json(old) + "|" + to_json(MOVES.all())
'''

MAIN = '''
from apkpy_lib.game import *
from game.data.defs import summary, roundtrip


class Run(Script):
    step: int = 0

    def update(self, dt: float):
        self.step += 1
        if self.step == 1:
            saves.write("slot1", roundtrip())
        if self.step == 2:
            text = saves.read("slot1")
            if text is not None:
                game.exit({"summary": summary(), "save": text, "exists": saves.exists("slot1"),
                           "none": saves.exists("zz")})


game = Game("t", size=(100, 100))
s = game.scene("main")
s.add(Entity("r", Run()))
'''

MOVES = [{"id": "spark", "power": 40, "kind": "fire"}, {"id": "splash", "power": 10}, {"id": "tackle", "power": 35}]
SPECIES = {"a_ember.json": {"id": "ember", "name": "Ember", "base_hp": 40, "moves": ["spark", "tackle"],
                            "evolves": "blaze"},
           "b_blaze.json": {"id": "blaze", "name": "Blaze", "base_hp": 70, "moves": ["spark"], "weight": 2},
           "c_drip.json": {"id": "drip", "name": "Drip", "base_hp": 44, "moves": ["splash", "tackle"]}}


def make(tmp_path, files, moves=None, species=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "apkpy.toml").write_text('[app]\nname = "t"\napplication_id = "com.test.data"\n')
    templates.write_assets(str(tmp_path / "assets"))
    for name, body in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body if name.endswith(".json") else textwrap.dedent(body), encoding="utf-8")
    (tmp_path / "data" / "species").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "moves.json").write_text(json.dumps(MOVES if moves is None else moves))
    for name, row in (SPECIES if species is None else species).items():
        (tmp_path / "data" / "species" / name).write_text(json.dumps(row))
    from apkpy_lib.game.build import bundle_only
    from apkpy_lib.game.project import Project
    project = Project(str(tmp_path))
    return project, bundle_only(project)


def replay(project, steps=20):
    from apkpy_lib.game import desktop
    desktop._config.update({"bundle": None, "store": None, "project": project})
    r = subprocess.run(desktop.command("main", "{}", "--replay", "", "--steps", str(steps)),
                       capture_output=True, text=True)
    out = r.stdout + r.stderr
    assert "APKPYGAME_RESULT " in out, out
    return json.loads(out.split("APKPYGAME_RESULT ", 1)[1].splitlines()[0])["result"]


def cpython(tmp_path, module):
    """The game module run by CPython (the oracle), with the project's data."""
    sys.path.insert(0, str(tmp_path))
    os.environ["APKPYGAME_PROJECT"] = str(tmp_path)
    try:
        for m in [m for m in sys.modules if m == "game" or m.startswith("game.")]:
            del sys.modules[m]
        return importlib.import_module(module)
    finally:
        sys.path.remove(str(tmp_path))
        del os.environ["APKPYGAME_PROJECT"]


def test_tables_json_and_saves_match_cpython(tmp_path):
    project, info = make(tmp_path, {"game/main.py": MAIN, "game/data/defs.py": DEFS})
    bundled = json.loads((tmp_path / "build" / "apkpygame" / "bundle" / "tables" / "data" / "species.json").read_text())
    assert [r["id"] for r in bundled] == ["ember", "blaze", "drip"], "a row per file, by file name"
    end = replay(project)
    defs = cpython(tmp_path, "game.data.defs")
    assert end["summary"] == defs.summary() == "ember:75:1.0;blaze:40:2.0;drip:45:1.0;->Blaze|3TrueFalse"
    assert end["save"] == defs.roundtrip(), (end["save"], defs.roundtrip())
    assert '"version":2,' in end["save"] and '"note":"o\\"k \\u00e9\\n"' in end["save"]
    assert end["exists"] is True and end["none"] is False


@pytest.mark.parametrize("moves, species, code, where, words", [
    ([{"id": "spark", "power": "40"}], None, "G1303", "data/moves.json: [0]", 'power: expected a whole number, got "40"'),
    (None, {"x.json": {"id": "x", "name": "X", "base_hp": 1, "moves": ["spark", "splsh"]}}, "G1307", "data/species/x.json",
     'moves: "splsh" is not in data/moves'),
    (None, {"x.json": {"id": "x", "name": "X", "base_hp": 1, "evolves": "nope"}}, "G1307", "data/species/x.json",
     'evolves: "nope" is not in data/species'),
    (None, {"x.json": {"id": "x", "name": "X", "base_hp": 1, "wieght": 2}}, "G1304", "data/species/x.json",
     "Did you mean weight?"),
    (None, {"x.json": {"id": "x", "name": "X"}}, "G1304", "data/species/x.json", "'base_hp' is missing"),
    ([{"id": "a", "power": 1}, {"id": "a", "power": 2}], None, "G1305", "data/moves.json: [1]", '"a" is used twice'),
    (None, {"x.json": {"id": "x", "name": "X", "base_hp": 1, "moves": "spark"}}, "G1303", "data/species/x.json",
     "moves: expected a list"),
])
def test_bad_data_is_named_where_it_is(tmp_path, moves, species, code, where, words):
    with pytest.raises(GameError) as e:
        make(tmp_path, {"game/main.py": MAIN, "game/data/defs.py": DEFS}, moves, species)
    text = str(e.value)
    assert e.value.code == code and where in text and words in text, text


def test_table_file_errors(tmp_path):
    (tmp_path / "data" / "species").mkdir(parents=True)
    (tmp_path / "data" / "species" / "bad.json").write_text('{"id": "x",, }')
    with pytest.raises(GameError) as e:
        make(tmp_path, {"game/main.py": MAIN, "game/data/defs.py": DEFS}, species={})
    assert e.value.code == "G1302" and "data/species/bad.json:1" in str(e.value), str(e.value)
    defs = DEFS.replace('MOVES = table("data/moves", Move)', 'MOVES = table("data/movez", Move)')
    with pytest.raises(GameError) as e:
        make(tmp_path / "b", {"game/main.py": MAIN, "game/data/defs.py": defs})
    assert e.value.code == "G1301" and "data/movez" in str(e.value)
    defs = DEFS.replace("class Move:\n    id: str\n", "class Move:\n    key: str\n")
    with pytest.raises(GameError) as e:
        make(tmp_path / "c", {"game/main.py": MAIN, "game/data/defs.py": defs})
    assert e.value.code == "G1306" and "'id: str'" in str(e.value)


READER = '''
from apkpy_lib.game import *
from dataclasses import dataclass


@dataclass
class Box:
    text: str = ""
    reads: int = 0


STATE = Box()
'''

SUSPEND = '''
from apkpy_lib.game import *
from game.box import STATE


class Reader(Script):
    def update(self, dt: float):
        if game.steps == 2:
            got = saves.read("slot")
            if got is not None:
                STATE.text = got
            STATE.reads += 1
        if game.steps == 4:
            game.open_app("menu")


game = Game("j", size=(100, 100))
s = game.scene("main")
s.add(Entity("r", Reader()))
'''


def test_a_save_read_comes_back_from_the_journal(tmp_path):
    """The slot changes after the game read it; the game brought back from its journal still read the
    old text (or its state hash would differ: G3030)."""
    project, info = make(tmp_path, {"game/main.py": SUSPEND, "game/box.py": READER})
    src = tmp_path / "j" / "apkpygame" / "game"
    src.mkdir(parents=True)
    (src / "Journaled.java").write_text(textwrap.dedent('''
        package apkpygame.game;
        import apkpygame.core.*;
        import apkpygame.testkit.HeadlessPlatform;
        public final class Journaled {
            public static void main(String[] a) {
                final java.io.File folder = new java.io.File(a[0]);
                Platform.AssetSource assets = new Platform.AssetSource() {
                    public byte[] read(String p) throws java.io.IOException {
                        return java.nio.file.Files.readAllBytes(new java.io.File(folder, p).toPath());
                    }
                    public boolean exists(String p) { return new java.io.File(folder, p).isFile(); }
                };
                HeadlessPlatform first = new HeadlessPlatform(assets);
                first.saveSlots.put("slot", "old");
                Game g = Game.load(first);
                g.start("main", "{}");
                while (!g.isEnded()) g.step();
                String journal = g.journalJson();
                System.out.println(M_box.STATE.text + " " + g.stateHash());
                HeadlessPlatform second = new HeadlessPlatform(assets);
                second.saveSlots.put("slot", "new");
                Game back = Game.restore(second, journal);
                System.out.println(M_box.STATE.text + " " + back.stateHash());
            }
        }
    '''), encoding="utf-8")
    tools = toolchain()
    classpath = engine.desktop_jar() + os.pathsep + info["game_jar"]
    out = tmp_path / "j" / "classes"
    out.mkdir()
    r = subprocess.run([tools.javac, "--release", "8", "-nowarn", "-Xlint:-options", "-cp", classpath, "-d", str(out),
                        str(src / "Journaled.java")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([tools.java, "-cp", classpath + os.pathsep + str(out), "apkpygame.game.Journaled",
                        info["bundle"]], capture_output=True, text=True)
    lines = r.stdout.splitlines()
    assert len(lines) == 2, r.stdout + r.stderr
    assert lines[0].startswith("old ") and lines[0] == lines[1], r.stdout


TILED_MAIN = '''
from apkpy_lib.game import *


class Npc(Script):
    def update(self, dt: float):
        if game.steps == 1:
            game.exit({"event": self.props.get_str("event"), "level": self.props.get_int("level"),
                       "brave": self.props.get_bool("brave"), "missing": self.props.get_str("nope", "dflt"),
                       "has": self.props.has("event"), "grass": scene.tile_tag(24, 8, "zone"),
                       "water": scene.tile_tag(8, 8, "zone"), "none": scene.tile_tag(8, 24, "zone"),
                       "outside": scene.tile_tag(500, 500, "zone")})


game = Game("tiled", size=(100, 100))
village = assets.tilemap("assets/village.tmj")
s = game.scene("main")
s.add(Entity("map", Tilemap(village, objects={"npc": Entity("npc", Npc())})))
'''


def test_tiled_object_properties_and_tile_tags(tmp_path):
    from PIL import Image
    (tmp_path / "assets").mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (48, 16)).save(str(tmp_path / "assets" / "tiles.png"))
    tmj = {"orientation": "orthogonal", "width": 2, "height": 2, "tilewidth": 16, "tileheight": 16,
           "tilesets": [{"firstgid": 1, "image": "tiles.png", "imagewidth": 48, "imageheight": 16, "columns": 3,
                         "tilewidth": 16, "tileheight": 16,
                         "tiles": [{"id": 1, "properties": [{"name": "zone", "type": "string", "value": "grass"}]},
                                   {"id": 2, "properties": [{"name": "zone", "type": "string", "value": "water"},
                                                            {"name": "height", "type": "int", "value": 0}]}]}],
           "layers": [{"type": "tilelayer", "name": "ground", "data": [1, 1, 1, 1]},
                      {"type": "tilelayer", "name": "zones", "visible": False, "data": [3, 2, 0, 0]},
                      {"type": "objectgroup", "name": "people", "objects": [
                          {"name": "npc", "x": 8, "y": 8, "width": 0, "height": 0,
                           "properties": [{"name": "event", "type": "string", "value": "town.nurse"},
                                          {"name": "level", "type": "int", "value": 7},
                                          {"name": "brave", "type": "bool", "value": True}]}]}]}
    (tmp_path / "assets" / "village.tmj").write_text(json.dumps(tmj))
    (tmp_path / "apkpy.toml").write_text('[app]\nname = "t"\napplication_id = "com.test.tiled"\n')
    (tmp_path / "game").mkdir()
    (tmp_path / "game" / "main.py").write_text(textwrap.dedent(TILED_MAIN), encoding="utf-8")
    from apkpy_lib.game.build import bundle_only
    from apkpy_lib.game.project import Project
    project = Project(str(tmp_path))
    bundle_only(project)
    end = replay(project, steps=5)
    assert end == {"event": "town.nurse", "level": 7, "brave": True, "missing": "dflt", "has": True,
                   "grass": "grass", "water": "water", "none": "", "outside": ""}, end
