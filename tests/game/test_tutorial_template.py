"""The Tutorial template: its game is what the steps say it is, and every step of its tutorial builds and plays."""
import os
import re
import shutil
import subprocess
import sys

import pytest

from apkpy_lib.game import desktop
from apkpy_lib.game.build import bundle_only
from apkpy_lib.game.project import Project
from conftest import TEMPLATES, new_game  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(TEMPLATES, "tutorial")
STEPS = os.path.join(TEMPLATE, "tutorial")


def blocks(name, language):
    with open(os.path.join(STEPS, name), encoding="utf-8") as fh:
        return re.findall(r"```%s\n(.*?)```" % language, fh.read(), re.S)


@pytest.fixture
def project(tmp_path):
    """The project made by following step 2."""
    folder = tmp_path / "my_square"
    (folder / "game").mkdir(parents=True)
    (folder / "apkpy.toml").write_text(blocks("02-make-the-project.md", "toml")[0], encoding="utf-8")
    (folder / "writehere.py").write_text(blocks("02-make-the-project.md", "python")[0], encoding="utf-8")
    return folder


def read(*parts):
    with open(os.path.join(TEMPLATE, *parts), encoding="utf-8") as fh:
        return fh.read()


def test_the_finished_game_is_the_last_step_and_is_small():
    main = read("game", "main.py")
    assert main == blocks("05-follow-the-finger.md", "python")[0]
    assert len(main.strip().splitlines()) <= 6


def test_writehere_is_the_one_in_step_2():
    assert read("writehere.py") == blocks("02-make-the-project.md", "python")[0]


@pytest.mark.parametrize("step", ["03-white-screen.md", "04-red-square.md", "05-follow-the-finger.md", "07-try-changing-things.md"])
def test_every_step_builds(project, step):
    (project / "game" / "main.py").write_text(blocks(step, "python")[0], encoding="utf-8")
    info = bundle_only(Project(str(project)))
    assert info["scenes"] == ["main"]


def test_new_makes_the_tutorial_project(tmp_path):
    """apkpy start X --game tutorial: the template, with its own name and id, and nothing left over."""
    folder = tmp_path / "Red Square"
    r = new_game(folder, "tutorial")
    assert r.returncode == 0 and "tutorial/01-before-you-start.md" in r.stdout, r.stdout + r.stderr
    toml = (folder / "apkpy.toml").read_text(encoding="utf-8")
    assert 'name = "Red Square"' in toml and 'application_id = "com.example.redsquare"' in toml, toml
    assert (folder / "game" / "main.py").is_file() and (folder / "tutorial" / "01-before-you-start.md").is_file()
    assert not (folder / "build").exists()
    assert bundle_only(Project(str(folder)))["scenes"]


def square_after_a_press(project, tmp_path, width, height):
    """Where the square's middle is on a window of this shape, after holding the finger at (60, 100) of the virtual screen."""
    from PIL import Image
    desktop._config.update({"bundle": None, "store": None, "project": Project(str(project))})
    shot = tmp_path / "shot.png"
    old = os.getcwd()
    os.chdir(str(project))
    try:
        p = subprocess.run(desktop.command("main", "{}", "--screenshot", str(shot), "--replay", "5:drag:60:100:60:100:200", "--steps", "120",
                                           "--width", str(width), "--height", str(height)), capture_output=True, text=True)
    finally:
        os.chdir(old)
    assert shot.exists(), p.stdout[-800:] + p.stderr[-800:]
    img = Image.open(shot).convert("RGB")
    red = [(x, y) for y in range(img.height) for x in range(img.width) if img.getpixel((x, y)) == (255, 0, 0)]
    assert red, "no red square"
    corners = {img.getpixel((0, 0)), img.getpixel((img.width - 1, img.height - 1))}
    assert corners == {(255, 255, 255)}, "white to the edges"
    return img, sum(x for x, y in red) / len(red), sum(y for x, y in red) / len(red)


@pytest.mark.parametrize("step", ["05-follow-the-finger.md", "07-try-changing-things.md"])
def test_the_square_goes_to_the_finger(project, tmp_path, step):
    (project / "game" / "main.py").write_text(blocks(step, "python")[0], encoding="utf-8")
    bundle_only(Project(str(project)))
    img, x, y = square_after_a_press(project, tmp_path, 360, 640)
    assert abs(x - 60) < 3 and abs(y - 100) < 3, (x, y)
