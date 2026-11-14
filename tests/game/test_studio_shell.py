"""ApkPy's Studio for any game (apkpy game studio, apkpy_lib.game.studio): it opens a game that is not the monster
RPG, reads its data tables and pictures, saves only what changed, keeps copies, says what the build would say without
writing anything, and a kit (the monster RPG's tools/studio_kit.py) adds its own sections."""
import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import EXAMPLES, ROOT, TEMPLATES

IGNORE = shutil.ignore_patterns("build", "__pycache__", ".studio_backups", ".pytest_cache", "*.apk")


def copy_of(source, folder):
    shutil.copytree(source, folder, ignore=IGNORE)
    return folder


def run(folder, code):
    env = dict(os.environ, PYTHONPATH=ROOT, APKPY_RELOAD="0", PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-c", code], cwd=str(folder), capture_output=True, text=True, timeout=280, env=env)


def check(folder):
    env = dict(os.environ, PYTHONPATH=ROOT, APKPY_RELOAD="0", PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", "apkpy_lib.game.studio.check"], cwd=str(folder), capture_output=True,
                          text=True, timeout=280, env=env)


@pytest.fixture
def platformer(tmp_path):
    return copy_of(os.path.join(EXAMPLES, "platformer"), tmp_path / "meadow")


def test_a_project_with_no_game_has_no_studio(tmp_path, monkeypatch):
    from apkpy_lib.game import cli
    from apkpy_lib.game.errors import GameError
    (tmp_path / "apkpy.toml").write_text('[app]\nname = "x"\napplication_id = "com.test.x"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(GameError) as e:
        cli.studio(say=lambda *a: None)
    assert e.value.code == "G1001" and "apkpy game init" in str(e.value)


def test_the_monster_rpg_opens_with_its_kit_and_any_other_game_with_the_plain_studio(tmp_path, platformer):
    rpg = copy_of(os.path.join(TEMPLATES, "monster_rpg"), tmp_path / "rpg")
    code = """
import sys
from apkpy_lib.game.studio import studio_class
from apkpy_lib.game.studio.shell import Shell
plain, kit = studio_class(sys.argv[1]), studio_class(sys.argv[2])
assert plain is Shell, plain
assert kit is not Shell and issubclass(kit, Shell) and kit.FIRST == "game" and ("monsters", "Monsters") in kit.SECTIONS
print("fine")
"""
    env = dict(os.environ, PYTHONPATH=ROOT, APKPY_RELOAD="0")
    r = subprocess.run([sys.executable, "-c", code, str(platformer), str(rpg)], capture_output=True, text=True, timeout=120, env=env)
    assert r.returncode == 0 and "fine" in r.stdout, r.stdout + r.stderr


def test_the_check_says_what_the_build_would_and_writes_nothing(platformer):
    r = check(platformer)
    assert r.returncode == 0 and r.stdout.strip() == "", r.stdout + r.stderr
    assert not (platformer / "build").exists(), "Play builds in the same folder at the same time: the check writes nothing"
    main = platformer / "game" / "main.py"
    main.write_text(main.read_text(encoding="utf-8").replace("jump=300", "jumpp=300"), encoding="utf-8")
    r = check(platformer)
    assert r.returncode == 1 and r.stdout.startswith("game/main.py:") and "jumpp" in r.stdout and r.stdout.strip().endswith("(G1204)"), r.stdout


def test_records_in_any_module_and_the_comment_is_the_help(platformer):
    from apkpy_lib.game.studio.data import DataProject
    (platformer / "game" / "rules.py").write_text('''from dataclasses import dataclass
from apkpy_lib.game import *


@dataclass
class Kind:
    id: str
    name: str


@dataclass
class Enemy:
    id: str
    name: str
    kind: Ref[Kind]
    speed: float = 30.0     # how fast it walks, in pixels a second
    lives: int = 1


class Bounce(Script):
    height: float = 10.0


kinds = table("data/kinds", Kind)
enemies = table("data/enemies", Enemy)
''', encoding="utf-8")
    (platformer / "data").mkdir()
    (platformer / "data" / "kinds.json").write_text(json.dumps([{"id": "slime", "name": "Slime"}]), encoding="utf-8")
    (platformer / "data" / "enemies.json").write_text(json.dumps([{"id": "blob", "name": "Blob", "kind": "slime", "speed": 30.0, "lives": 1}]), encoding="utf-8")
    p = DataProject(str(platformer))
    assert set(p.paths) == {"Kind", "Enemy"} and "Bounce" not in p.classes, "a Script is not a record"
    assert p.help("Enemy", "speed") == "how fast it walks, in pixels a second" and p.help("Enemy", "lives") == ""
    row = p.new_row("Enemy", "Big Blob")
    assert row["id"] == "big_blob" and row["kind"] == "slime" and p.row_problems("Enemy", row) == []
    assert [u.text for u in p.uses("Kind", "slime")] == ["enemy: Blob", "enemy: Big Blob"]
    p.save()
    assert json.loads((platformer / "data" / "enemies.json").read_text(encoding="utf-8"))[1]["id"] == "big_blob"
    p.rename("Kind", "slime", "jelly")
    rows = json.loads((platformer / "data" / "enemies.json").read_text(encoding="utf-8"))
    assert {r["kind"] for r in rows} == {"jelly"}, "renamed everywhere"
    with pytest.raises(ValueError):
        p.rename("Kind", "jelly", "Not An Id")


def test_copies_of_any_game(platformer):
    from apkpy_lib.game.studio import data
    (platformer / "game" / "__pycache__").mkdir()
    (platformer / "game" / "__pycache__" / "main.cpython-313.pyc").write_bytes(b"x")
    (platformer / "build").mkdir()
    (platformer / "build" / "big.bin").write_bytes(b"x" * 10)
    made = data.make_backup("first", str(platformer))
    copy = platformer / data.BACKUPS / made
    for rel in ("game/main.py", "levels/meadow.tmj", "assets/hero.png", "assets/coin.wav", "apkpy.toml", "writehere.py"):
        assert (copy / rel).is_file(), rel
    assert not (copy / "build").exists() and not (copy / "game" / "__pycache__").exists()
    assert data.make_backup("again", str(platformer)) == "", "nothing changed: no new copy"
    main = platformer / "game" / "main.py"
    before = main.read_text(encoding="utf-8")
    main.write_text(before + "\n# changed\n", encoding="utf-8")
    data.restore_backup(made, str(platformer))
    assert main.read_text(encoding="utf-8") == before
    assert len(data.list_backups(str(platformer))) == 2, "going back first keeps how things were"


WINDOW = r"""
import os, sys, time, re, tkinter as tk
from apkpy_lib.game.studio.ui import make_root
from apkpy_lib.game.studio.shell import Shell
try:
    root = make_root("Studio")
except tk.TclError:
    print("no screen")
    raise SystemExit
root.withdraw()
st = Shell(root, ".")

def settle():
    for _ in range(1500):
        root.update()
        time.sleep(0.02)
        if st.checker.poll() is not None and st.summary.cget("text") != "Checking...":
            return
    raise SystemExit("the check never ended")

settle()
assert [k for k, _ in st.sections()] == ["play", "game", "objects", "scenes", "levels", "table:Enemy", "art", "sounds", "publish", "backups", "help"], st.sections()
assert st.summary.cget("text") == "No problems in the saved files.", st.summary.cget("text")
for key, _ in st.sections():
    if key != "play":
        st.show(key)
        root.update()
art = st.show("art")
assert art.tree.exists("other/hero") and art.tree.exists("other/coin")
art.go_to("other/hero")
assert art.doc.cell_size == (16, 16) and art.doc.count > 1, "assets.sheet(frame=(16, 16)) cuts it in frames"
art.go_to("other/coin")
assert art.doc.cell_size == (12, 12)
table = st.show("table:Enemy")
assert table.selected["id"] == "blob"
table.selected["speed"] = 45.0
table.field_changed("Enemy.speed")
game = st.show("game")
st.project.app.values["name"] = "Meadow Dash"
st.content_changed()
assert {"game", "table:Enemy"} <= st.dirty_sections(), st.dirty_sections()
st.save_all()
settle()
assert st.dirty_sections() == set()
assert 'name = "Meadow Dash"' in open("apkpy.toml", encoding="utf-8").read()
assert 'Game("Meadow Dash"' in open("game/main.py", encoding="utf-8").read()
assert '"speed": 45.0' in open("data/enemies.json", encoding="utf-8").read()
assert st.summary.cget("text") == "No problems in the saved files.", st.summary.cget("text")
with open("game/main.py", encoding="utf-8") as fh:
    text = fh.read()
with open("game/main.py", "w", encoding="utf-8") as fh:
    fh.write(text.replace("jump=300", "jumpp=300"))
st.run_check()
settle()
assert st.real_problems and st.real_problems[0].startswith("game/main.py:"), st.real_problems
st.go_problem(st.real_problems[0])
assert st.current == "objects" and st.screens["objects"].chosen == "player", "the object on that line"
names = os.listdir(".studio_backups")
assert any("opened" in n for n in names), names
assert not any("before_saving" in n for n in names), "the files on disk were still those of the copy made on opening"
assert st.backup("by hand"), "after saving, the files changed: a new copy"
assert st.backup("by hand again") == "", "the same as the newest copy: none"
st.close_screens()
root.destroy()
print("fine")
"""


def test_the_window_on_a_game_that_is_not_the_monster_rpg(platformer):
    (platformer / "game" / "rules.py").write_text('''from dataclasses import dataclass
from apkpy_lib.game import *


@dataclass
class Enemy:
    id: str
    name: str
    speed: float = 30.0     # pixels a second


enemies = table("data/enemies", Enemy)
''', encoding="utf-8")
    (platformer / "data").mkdir()
    (platformer / "data" / "enemies.json").write_text(json.dumps([{"id": "blob", "name": "Blob", "speed": 30.0}]), encoding="utf-8")
    r = run(platformer, WINDOW)
    assert r.returncode == 0 and ("fine" in r.stdout or "no screen" in r.stdout), r.stdout + r.stderr


CODE_WINDOW = r"""
import os, sys, time, tkinter as tk
from apkpy_lib.game.studio.ui import make_root
from apkpy_lib.game.studio.shell import Shell
from apkpy_lib.game.studio.fields import ActionsEditor, AnimationsEditor, CallForm
from apkpy_lib.game.studio.objects import EntityEditor
from apkpy_lib.game.studio.scenes import RulesEditor, VariablesEditor
try:
    root = make_root("Studio")
except tk.TclError:
    print("no screen")
    raise SystemExit
root.withdraw()
st = Shell(root, ".")

def settle():
    for _ in range(1500):
        root.update()
        time.sleep(0.02)
        if st.checker.poll() is not None and st.summary.cget("text") != "Checking...":
            return
    raise SystemExit("the check never ended")

def inside(widget, cls):
    out = []
    for child in widget.winfo_children():
        if isinstance(child, cls):
            out.append(child)
        out.extend(inside(child, cls))
    return out

def form_of(screen, func):
    main = st.code.main
    return next(f for f in inside(screen, CallForm) if getattr(main.at(f.path), "func", "") == func)

settle()
assert [k for k, _ in st.sections()][:4] == ["play", "game", "objects", "scenes"], st.sections()
before = open("game/main.py", encoding="utf-8", newline="").read()

objects = st.show("objects")
objects.go_to("player")
root.update()
jump = form_of(objects, "PlatformerController")
entry = next(w for w in inside(jump, tk.Entry) if w.get() == "300")
entry.delete(0, "end")
entry.insert(0, "320")
entry.typed()
assert "PlatformerController(speed=110, jump=320)" in st.code.main.text
assert st.dirty_sections() == {"objects"}, st.dirty_sections()
run = inside(objects, AnimationsEditor)[0]
assert len(run.frames) == 8, "the hero's sheet, cut in its frames"
run.rows[1]["fps"].delete(0, "end")
run.rows[1]["fps"].insert(0, "14")
run.rows[1]["fps"].event_generate("<KeyRelease>")
run.write()
assert '"run": {"frames": [2, 3, 4, 5], "fps": 14}' in st.code.main.text
assert all(len(line) <= 120 for line in st.code.main.text.splitlines())
run.rows[1]["frames"].delete(0, "end")
run.rows[1]["frames"].insert(0, "2, 9")
run.write()
assert "frames 0 to 7" in run.note.cget("text") and '"fps": 14' in st.code.main.text, "a frame the sheet has not: nothing written"
objects.go_to("coin")
root.update()
inside(objects, EntityEditor)[0].add("Spin")
root.update()
form_of(objects, "Spin").commit("speed", "45")
assert "                  Spin(speed=45),\n" in st.code.main.text.replace("\r\n", "\n"), st.code.main.text
objects.do_undo()
assert "Spin(speed=45)" not in st.code.main.text and "Spin()" in st.code.main.text
inside(objects, ActionsEditor)[0].add("only_if")
root.update()
assert 'OnCollide("player", destroy(), var_add("coins"), sound(ding), only_if("coins >= 1", sound(jump)))' in st.code.main.text
condition = next(w for w in inside(form_of(objects, "only_if"), tk.Entry) if w.get() == "coins >= 1")
condition.delete(0, "end")
condition.insert(0, "lives < 3 and more")
condition.typed()
assert 'only_if("coins >= 1"' in st.code.main.text, "not a condition: nothing written"
condition.delete(0, "end")
condition.insert(0, "count(coin) == 0")
condition.typed()
assert 'only_if("count(coin) == 0", sound(jump))' in st.code.main.text

scenes = st.show("scenes")
root.update()
inside(scenes, RulesEditor)[0].add()
root.update()
assert 'when("coins >= 10", exit_game({"result": "win"}))' in st.code.main.text
scenes.add_thing(st.code.main.first("scene"), "coin()")
root.update()
assert st.code.main.text.replace("\r\n", "\n").endswith('meadow.add(pad(up, "jump"), at=(292, 152), ui=True)\nmeadow.add(coin(), at=(160, 90))\n')

game = st.show("game")
root.update()
vars_ = inside(game, VariablesEditor)[0]
vars_.row("time", "60")
vars_.write()
assert 'vars={"coins": 0, "lives": 3, "time": 60}' in st.code.main.text
form_of(game, "Game").commit("size", "(400, 240)")
assert st.dirty_sections() >= {"objects", "scenes", "game"}, st.dirty_sections()
st.save_all()
settle()
assert st.dirty_sections() == set()
assert st.summary.cget("text") == "No problems in the saved files.", (st.summary.cget("text"), st.real_problems)
after = open("game/main.py", encoding="utf-8", newline="").read()
assert after != before and after.startswith(before[:before.index("game = Game(")]), "the docstring and imports are as they were"
assert ("\r\n" in before) == ("\r\n" in after)

with open("game/main.py", "w", encoding="utf-8", newline="") as fh:
    fh.write(after.replace("Spin()", "Spin(spin=1)"))
st.watch_files()
assert "Spin(spin=1)" in st.code.main.text, "read again when it changes on disk"
st.run_check()
settle()
assert st.real_problems and st.real_problems[0].startswith("game/main.py:"), st.real_problems
st.go_problem(st.real_problems[0])
assert st.current == "objects" and st.screens["objects"].chosen == "coin", (st.current, st.screens["objects"].chosen)
st.close_screens()
root.destroy()
print("fine")
"""


def test_objects_scenes_and_the_game_change_the_code_and_it_still_builds(platformer):
    r = run(platformer, CODE_WINDOW)
    assert r.returncode == 0 and ("fine" in r.stdout or "no screen" in r.stdout), r.stdout + r.stderr


def test_my_game_keeps_the_line_endings_of_the_files_it_writes(tmp_path):
    from apkpy_lib.game.studio.data import AppFile
    toml = tmp_path / "apkpy.toml"
    toml.write_bytes(b'[app]\nname = "A"\napplication_id = "com.t.a"\n')
    (tmp_path / "game").mkdir()
    main = tmp_path / "game" / "main.py"
    main.write_bytes(b'from apkpy_lib.game import *\ngame = Game("A", size=(1, 2))\n')
    app = AppFile(str(tmp_path))
    app.values["name"] = "B"
    app.save()
    assert toml.read_bytes() == b'[app]\nname = "B"\napplication_id = "com.t.a"\n', "Windows wrote \r\n here"
    assert main.read_bytes() == b'from apkpy_lib.game import *\ngame = Game("B", size=(1, 2))\n'
    toml.write_bytes(toml.read_bytes().replace(b"\n", b"\r\n"))
    app.values["version_name"] = "2.0"
    app.save()
    assert toml.read_bytes() == b'[app]\r\nversion_name = "2.0"\r\nname = "B"\r\napplication_id = "com.t.a"\r\n'
