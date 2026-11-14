"""The genre templates (apkpy start NAME --game platformer|shooter|...): each starts, builds, opens in the Studio,
and can be won. The replay that wins each is in genre_replays.json, found by tools/game/genre_bots.py."""
import json
import os
import re
import subprocess
import sys

import pytest

from conftest import ROOT, TEMPLATES, new_game

from apkpy_lib.game.build import bundle_only
from apkpy_lib.game.cli import GENRES
from apkpy_lib.game.project import Project
from apkpy_lib.game.studio import check as studio_check
from apkpy_lib.game.studio.code import GameCode
from apkpy_lib.game.studio.levels import Level, level_files

import genre_bots

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "genre_replays.json"), encoding="utf-8") as fh:
    REPLAYS = json.load(fh)


def test_every_genre_has_a_template_and_a_replay_that_wins_it():
    assert sorted(REPLAYS) == sorted(GENRES)
    for genre in GENRES:
        folder = os.path.join(TEMPLATES, genre)
        for name in ("README.md", "apkpy.toml", "writehere.py", "sounds.json", os.path.join("game", "main.py")):
            assert os.path.isfile(os.path.join(folder, name)), "%s has no %s" % (genre, name)
        waves = [f for _, _, names in os.walk(folder) for f in names if f.endswith(".wav")]
        assert not waves, "%s: the sounds are made when the game is created, the package carries none" % genre


@pytest.mark.parametrize("genre", GENRES)
def test_a_genre_starts_builds_and_can_be_won(genre, tmp_path):
    folder = tmp_path / ("my_" + genre)
    r = new_game(folder, genre, app_id="dev.apkpy.check." + genre)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "README.md" in r.stdout and "apkpy game studio" in r.stdout, r.stdout
    assert not (folder / "sounds.json").exists(), "the recipe is used and taken away"
    main = (folder / "game" / "main.py").read_text(encoding="utf-8")
    files = re.findall(r'assets\.\w+\("([^"]+)"', main)
    assert files and all((folder / f).is_file() for f in files), [f for f in files if not (folder / f).is_file()]
    assert 'name = "my_%s"' % genre in (folder / "apkpy.toml").read_text(encoding="utf-8")

    assert studio_check.check(str(folder)) is None, "what the Studio's check says"
    code = GameCode(str(folder))
    assert code.broken == {} and code.prefabs() and code.scenes()
    for rel in level_files(str(folder)):
        level = Level(str(folder), rel)
        assert level.cols > 0 and not level.dirty, rel

    bundle_only(Project(str(folder)))
    replay = REPLAYS[genre]
    run = genre_bots.play(str(folder), replay["replay"], replay["steps"], scene=replay["scene"])
    assert run.won, run.summary


@pytest.mark.parametrize("genre", ["platformer", "adventure", "puzzle", "world"])
def test_nothing_hurts_a_player_who_has_not_moved_yet(genre, tmp_path):
    """Half a minute with no hands on every level: the games where things come to you are the other four."""
    folder = tmp_path / ("my_" + genre)
    assert new_game(folder, genre).returncode == 0
    bundle_only(Project(str(folder)))
    for scene in sorted(f[:-5] for f in os.listdir(str(folder / "build" / "apkpygame" / "bundle" / "scenes"))):
        run = genre_bots.play(str(folder), "", 1800, scene=scene)
        assert run.end is None and run.lost_at() is None, "%s, scene %s: %s" % (genre, scene, run.summary)


STUDIO = r"""
import sys, time, tkinter as tk
from apkpy_lib.game.studio.ui import make_root
from apkpy_lib.game.studio.shell import Shell
try:
    root = make_root("Studio")
except tk.TclError:
    print("no screen")
    raise SystemExit
root.withdraw()
st = Shell(root, ".")
for _ in range(1500):
    root.update()
    time.sleep(0.02)
    if st.checker.poll() is not None and st.summary.cget("text") != "Checking...":
        break
assert st.summary.cget("text") == "No problems in the saved files.", st.summary.cget("text")
keys = [k for k, _ in st.sections()]
assert keys[:4] == ["play", "game", "objects", "scenes"] and "sounds" in keys and "art" in keys, keys
for key in keys:
    if key != "play":
        st.show(key)
        root.update()
objects = st.show("objects")
names = [piece.name for _, piece in st.code.prefabs()]
for name in names:
    objects.go_to(name)
    root.update()
    assert objects.chosen == name
scenes = st.show("scenes")
for piece in st.code.scenes():
    scenes.go_to(piece.name)
    root.update()
levels = st.show("levels") if "levels" in keys else None
assert st.dirty_sections() == set(), st.dirty_sections()
print("fine", len(names), "objects")
"""


@pytest.mark.parametrize("genre", GENRES)
def test_the_studio_opens_every_genre_and_shows_every_object(genre, tmp_path):
    folder = tmp_path / ("my_" + genre)
    assert new_game(folder, genre).returncode == 0
    before = (folder / "game" / "main.py").read_bytes()
    env = dict(os.environ, PYTHONPATH=ROOT, APKPY_RELOAD="0", PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-c", STUDIO], cwd=str(folder), capture_output=True, text=True, timeout=280,
                       env=env)
    assert r.returncode == 0 and ("fine" in r.stdout or "no screen" in r.stdout), r.stdout + r.stderr
    assert (folder / "game" / "main.py").read_bytes() == before, "looking at a game changes nothing in it"


# ── a new game: its name, and the Studio's screen that makes one ────────

def test_a_genre_game_is_called_as_its_project(tmp_path, monkeypatch):
    from apkpy_lib.game import cli
    monkeypatch.chdir(tmp_path)
    said = []
    folder = cli.new("treasure", "adventure", say=said.append, title="Caça ao \"Tesouro\"")
    assert os.path.basename(folder) == "treasure" and "README.md" in said[0]
    toml = (tmp_path / "treasure" / "apkpy.toml").read_text(encoding="utf-8")
    assert 'name = "Caça ao \\"Tesouro\\""' in toml and 'application_id = "com.example.caaaotesouro"' in toml
    main = (tmp_path / "treasure" / "game" / "main.py").read_text(encoding="utf-8")
    assert 'Game("Caça ao \\"Tesouro\\"", size=(320, 180)' in main and "Keys of the Keep" not in main
    app = (tmp_path / "treasure" / "writehere.py").read_text(encoding="utf-8")
    assert app.count('"title": "Caça ao \\"Tesouro\\""') == 2 and "Keys of the Keep" not in app, "both languages"
    assert studio_check.check(str(folder)) is None
    plain = cli.new("plain", "tap", say=said.append)
    assert 'Game("plain"' in open(os.path.join(plain, "game", "main.py"), encoding="utf-8").read()


def test_the_studio_started_where_there_is_no_project_opens_on_a_new_game(tmp_path, monkeypatch):
    from apkpy_lib.game import cli
    from apkpy_lib.game import studio
    opened = []
    monkeypatch.setattr(studio, "open_new_game", opened.append)
    monkeypatch.chdir(tmp_path)
    cli.studio(say=lambda *a: None)
    assert opened == [str(tmp_path)]


def test_every_kind_of_new_game_is_a_template_with_its_picture():
    from apkpy_lib.game import cli
    from apkpy_lib.game.studio import newgame
    kinds = [kind for kind, _, _ in newgame.KINDS]
    assert set(GENRES) < set(kinds) <= set(cli.TEMPLATES)
    for kind in kinds:
        if kind != "blank":
            path = os.path.join(newgame.PICTURES, kind.replace("-", "_") + ".png")
            assert os.path.isfile(path) and os.path.getsize(path) < 12000, path
    assert newgame.folder_name("Sky Hopper 2!") == "sky_hopper_2" and newgame.folder_name("???") == "my_game"
    assert newgame.app_id_of("Sky Hopper") == "com.example.skyhopper"


NEW_GAME = r"""
import os, sys, time, tkinter as tk
from apkpy_lib.game.studio import studio_class
from apkpy_lib.game.studio.newgame import KINDS, NewGame
from apkpy_lib.game.studio.ui import make_root
try:
    root = make_root("Studio")
except tk.TclError:
    print("no screen")
    raise SystemExit
root.withdraw()
made = []
screen = NewGame(root, ".", made.append)
screen.pack(fill="both", expand=True)
root.update()
assert set(screen.cards) == {k for k, _, _ in KINDS} and len(screen.images) == len(KINDS) - 1, "a picture on each card"
assert screen.kind == "platformer" and screen.app_id.get() == "com.example.mygame"
screen.choose("tap")
screen.name.set("Star Pop")
root.update()
assert screen.app_id.get() == "com.example.starpop", "the id follows the name until it is typed"
assert screen.place.cget("text").endswith("star_pop")
screen.name.set('Star "Pop"')
screen.create()
assert not made and "no quotes" in screen.problem.cget("text"), screen.problem.cget("text")
screen.name.set("Star Pop")
screen.app_id.set("Star Pop")
screen.create()
assert not made and "small letters" in screen.problem.cget("text"), screen.problem.cget("text")
screen.app_id.set("com.test.starpop")
os.mkdir("star_pop")
screen.create()
assert not made and "is there already" in screen.problem.cget("text"), screen.problem.cget("text")
os.rmdir("star_pop")
screen.create()
assert made == [os.path.abspath("star_pop")], screen.problem.cget("text")
text = open(os.path.join("star_pop", "apkpy.toml"), encoding="utf-8").read()
assert 'name = "Star Pop"' in text and 'application_id = "com.test.starpop"' in text, text
assert 'Game("Star Pop"' in open(os.path.join("star_pop", "game", "main.py"), encoding="utf-8").read()
assert os.path.isfile(os.path.join("star_pop", "assets", "pop.wav")) and not os.path.exists(os.path.join("star_pop", "sounds.json"))
screen.destroy()
st = studio_class(made[0])(root, made[0])
for _ in range(1500):
    root.update()
    time.sleep(0.02)
    if st.checker.poll() is not None and st.summary.cget("text") != "Checking...":
        break
assert st.summary.cget("text") == "No problems in the saved files.", st.summary.cget("text")
assert st.name_label.cget("text") == "Star Pop"
box = st.new_game()
root.update()
assert box.winfo_exists() and isinstance(box.winfo_children()[0], NewGame)
assert box.winfo_children()[0].where == os.path.abspath("."), "beside this game"
box.destroy()
print("fine")
"""


def test_the_new_game_screen_makes_a_game_and_the_studio_opens_on_it(tmp_path):
    env = dict(os.environ, PYTHONPATH=ROOT, APKPY_RELOAD="0", PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-c", NEW_GAME], cwd=str(tmp_path), capture_output=True, text=True, timeout=280,
                       env=env)
    assert r.returncode == 0 and ("fine" in r.stdout or "no screen" in r.stdout), r.stdout + r.stderr
