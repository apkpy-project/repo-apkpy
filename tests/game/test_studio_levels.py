"""The Studio's levels (.tmj, the files Tiled makes) and sounds: what it writes, the build and Tiled read."""
import json
import os
import shutil
import wave

from conftest import EXAMPLES

from apkpy_lib.game.compiler import tiled
from apkpy_lib.game.studio import check as studio_check
from apkpy_lib.game.studio import sound
from apkpy_lib.game.studio.code import GameCode
from apkpy_lib.game.studio.levels import Level, dump, level_files, new_level, starter_tiles, tilemaps_of

IGNORE = shutil.ignore_patterns("build", "__pycache__", ".studio_backups", "*.apk")


def copy_of(name, tmp_path):
    folder = tmp_path / name
    shutil.copytree(os.path.join(EXAMPLES, name), str(folder), ignore=IGNORE)
    return folder


def test_a_level_changed_and_saved_reads_in_the_build_with_all_it_had(tmp_path):
    folder = copy_of("platformer", tmp_path)
    level = Level(str(folder), "levels/meadow.tmj")
    before = json.loads((folder / "levels" / "meadow.tmj").read_text(encoding="utf-8"))
    assert not level.dirty and level.save() is False
    assert level.tileset["image"] == "assets/tiles.png" and level.tileset["count"] == 8
    ground = level.layer("ground")
    assert Level.solid(ground) and not Level.solid(level.layer("decor"))
    level.remember()
    assert level.set(ground, 3, 2, 5) and level.get(ground, 3, 2) == 5
    things = level.layer("things")
    level.add_object(things, "coin", 10, 4)
    assert level.dirty and level.save()
    after = json.loads((folder / "levels" / "meadow.tmj").read_text(encoding="utf-8"))
    assert set(after) - set(before) <= {"nextobjectid"} and set(before) <= set(after), "every key it had"
    assert after["layers"][2]["objects"][:-1] == before["layers"][2]["objects"]
    m = tiled.read(str(folder / "levels" / "meadow.tmj"), str(folder), "levels/meadow.tmj")
    assert m.layers[0][1][2 * m.cols + 3] == 5
    assert m.objects[-1][:3] == ("coin", 10 * 16 + 8, 4 * 16 + 8), "the object stands in the middle of its cell"
    assert studio_check.check(str(folder)) is None
    level.undo()
    assert level.get(level.layer("ground"), 3, 2) == before["layers"][0]["data"][2 * 64 + 3]


def test_tiles_are_written_on_one_line_as_tiled_does():
    text = dump({"width": 2, "layers": [{"data": [0, 1, 2], "name": "g"}]})
    assert '"data":[0, 1, 2]' in text and json.loads(text)["layers"][0]["data"] == [0, 1, 2]


def test_a_new_level_with_starter_tiles_is_a_map_the_build_reads(tmp_path):
    rel = new_level(str(tmp_path), "Level 1", 20, 8, 16)
    assert rel == "levels/level_1.tmj" and level_files(str(tmp_path)) == [rel]
    assert (tmp_path / "assets" / "tiles.png").is_file()
    m = tiled.read(str(tmp_path / "levels" / "level_1.tmj"), str(tmp_path), rel)
    assert (m.cols, m.rows) == (20, 8) and [n for n, _, _, _ in m.layers] == ["ground", "decor"]
    engine, names = tiled.engine_json(m, None)
    assert sum(engine["solid"]) == 20, "the bottom row is ground, and ground is solid"
    level = Level(str(tmp_path), rel)
    level.resize(10, 10)
    level.fill(level.layer("decor"), 0, 0, 3)
    level.save()
    m = tiled.read(str(tmp_path / "levels" / "level_1.tmj"), str(tmp_path), rel)
    assert (m.cols, m.rows) == (10, 10) and m.layers[1][1].count(3) == 100
    assert m.layers[0][1][7 * 10:8 * 10] == [1] * 10, "the ground stays where it was"


def test_the_code_that_uses_a_level_is_found(tmp_path):
    folder = copy_of("platformer", tmp_path)
    code = GameCode(str(folder))
    uses = tilemaps_of(code, "levels/meadow.tmj")
    assert len(uses) == 1 and uses[0][1].func == "Tilemap"
    assert [i.key for i in uses[0][1].get("objects").items] == ["player", "coin", "slime", "flag"]
    assert tilemaps_of(code, "levels/other.tmj") == []


def test_sounds_made_here_are_the_same_each_time_and_real_wav_files(tmp_path):
    for kind in sound.KINDS:
        assert sound.make_sound(kind, seed=2) == sound.make_sound(kind, seed=2)
        assert sound.make_sound(kind, seed=2) != sound.make_sound(kind, seed=5) or kind in ("click",)
    path = str(tmp_path / "coin.wav")
    sound.write_wav(path, sound.make_sound("coin"))
    with wave.open(path) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, sound.RATE) and w.getnframes() > 1000
    tune = sound.make_music("calm", seed=1)
    assert 8 * sound.RATE < len(tune) < 40 * sound.RATE and max(abs(v) for v in tune) <= 1


def test_a_sound_made_here_is_written_in_the_code_and_builds(tmp_path):
    folder = copy_of("platformer", tmp_path)
    sound.write_wav(str(folder / "assets" / "laser.wav"), sound.make_sound("laser"))
    code = GameCode(str(folder))
    name = code.declare(code.main, "assets/laser.wav", "sound")
    assert name == "laser" and 'laser = assets.sound("assets/laser.wav")' in code.main.text
    code.save()
    assert studio_check.check(str(folder)) is None


def test_starter_tiles_are_eight_tiles_in_a_row(tmp_path):
    from PIL import Image
    path = str(tmp_path / "t.png")
    assert starter_tiles(path, 16) == 8
    with Image.open(path) as img:
        assert img.size == (128, 16)


LEVEL_WINDOW = r"""
import json, time, tkinter as tk
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

class Click:
    def __init__(self, col, row):
        self.x, self.y = col * 16 * lv.zoom + 3, row * 16 * lv.zoom + 3

settle()
lv = st.show("levels")
root.update()
level = lv.level()
lv.choose_tile(4)
lv.press(Click(2, 3), False)
lv.drag(Click(3, 3), False)
lv.drag(Click(4, 3), False)
lv.release()
assert [level.get(level.layer("ground"), c, 3) for c in (2, 3, 4)] == [4, 4, 4]
assert st.dirty_sections() == {"levels"}, st.dirty_sections()
lv.choose_layer("things")
assert lv.object_kinds()[:4] == ["player", "coin", "slime", "flag"], lv.object_kinds()
lv.choose_kind("coin")
lv.press(Click(6, 3), False)
lv.release()
assert level.layer("things")["objects"][-1]["class"] == "coin"
count = len(level.layer("things")["objects"])
lv.do_undo()
assert len(lv.level().layer("things")["objects"]) == count - 1
lv.do_redo()
assert len(lv.level().layer("things")["objects"]) == count
st.save_all()
settle()
assert st.dirty_sections() == set() and st.summary.cget("text") == "No problems in the saved files.", st.real_problems
saved = json.load(open("levels/meadow.tmj", encoding="utf-8"))
assert saved["layers"][2]["objects"][-1]["x"] == 96 and saved["layers"][0]["data"][3 * 64 + 2] == 4
st.close_screens()
root.destroy()
print("fine")
"""


def test_painting_and_placing_in_the_window_saves_a_level_the_build_reads(tmp_path):
    import subprocess
    import sys
    from conftest import ROOT
    folder = copy_of("platformer", tmp_path)
    env = dict(os.environ, PYTHONPATH=ROOT, APKPY_RELOAD="0", PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-c", LEVEL_WINDOW], cwd=str(folder), capture_output=True, text=True, timeout=280, env=env)
    assert r.returncode == 0 and ("fine" in r.stdout or "no screen" in r.stdout), r.stdout + r.stderr
