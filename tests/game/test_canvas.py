"""Canvas: pixels a game paints while it runs.

- the build reads Canvas(...) and refuses what the engine could not start (a size it cannot have,
  an image that is not a PNG, or an interlaced one), with the line;
- scripts paint with set/rect/line/circle/flood/stamp and read back with get/count, in Java;
- a canvas with a brush is painted by the finger: a drag leaves a line with no gaps, a drag that starts
  off the canvas leaves nothing, and the pixels are part of the state hash (the same game, the same hash);
- a canvas starts from a PNG with its exact colours (see-through pixels keep theirs).
"""
import json
import os
import subprocess
import textwrap

import pytest
from PIL import Image

from apkpy_lib.game import templates
from apkpy_lib.game.compiler import reader
from apkpy_lib.game.errors import GameError


def make(tmp_path, body):
    (tmp_path / "apkpy.toml").write_text('[app]\nname = "t"\napplication_id = "com.test.canvas"\n')
    templates.write_assets(str(tmp_path / "assets"))
    pic = Image.new("RGBA", (4, 2), (0, 0, 0, 0))
    pic.putpixel((0, 0), (255, 0, 0, 255))
    pic.putpixel((1, 0), (0, 128, 255, 255))
    pic.putpixel((2, 0), (10, 20, 30, 128))                  # half see-through: its colour must stay 0a141e
    pic.putpixel((3, 1), (0, 255, 0, 255))
    pic.save(str(tmp_path / "assets" / "pic.png"))
    (tmp_path / "game").mkdir(exist_ok=True)
    (tmp_path / "game" / "main.py").write_text(textwrap.dedent(body), encoding="utf-8")
    from apkpy_lib.game.build import bundle_only
    from apkpy_lib.game.project import Project
    project = Project(str(tmp_path))
    return project, bundle_only(project)


def run(project, scene, *extra):
    from apkpy_lib.game import desktop
    desktop._config.update({"bundle": None, "store": None, "project": project})
    r = subprocess.run(desktop.command(scene, "{}", *extra), capture_output=True, text=True)
    return r.stdout + r.stderr


def line(out, key):
    assert key + " " in out, out
    return out.split(key + " ", 1)[1].splitlines()[0]


def result(out):
    return json.loads(line(out, "APKPYGAME_RESULT"))["result"]


# ── the build ────────────────────────────────────────────────────────────

HEADER = 'from apkpy_lib.game import *\ngame = Game("t")\npic = assets.image("assets/pic.png")\n'


def read(tmp_path, body):
    (tmp_path / "apkpy.toml").write_text('[app]\nname = "t"\napplication_id = "com.test.canvas"\n')
    (tmp_path / "game").mkdir(exist_ok=True)
    os.makedirs(str(tmp_path / "assets"), exist_ok=True)
    if not (tmp_path / "assets" / "pic.png").exists():
        Image.new("RGBA", (4, 2), (255, 0, 0, 255)).save(str(tmp_path / "assets" / "pic.png"))
    path = tmp_path / "game" / "main.py"
    path.write_text(HEADER + textwrap.dedent(body), encoding="utf-8")
    return reader.read(str(path), str(tmp_path))


def test_the_build_reads_a_canvas(tmp_path):
    model = read(tmp_path, """
        s = game.scene("main")
        s.add(Entity("a", Canvas(32, 16, color="#ffffff", brush="#ff0000", brush_size=4)))
        s.add(Entity("b", Canvas(image=pic)))
    """)
    a, b = (next(c for c in e.components if c.type == "Canvas") for e in model.scenes[0].entities)
    assert a.values["width"] == 32 and a.values["height"] == 16 and a.values["brush"] == "#ff0000"
    assert a.values["brush_size"] == 4 and a.values["color"] == "#ffffff"
    assert b.values["image"].path == "assets/pic.png"


@pytest.mark.parametrize("body, words", [
    ("Canvas(0, 10)", "width has to be 1 or more"),
    ("Canvas(10, -1)", "height has to be 1 or more"),
    ("Canvas(5000, 5000)", "at most 4096 x 4096"),
    ("Canvas(image=jpeg)", "is not a PNG"),
    ("Canvas(image=laced)", "interlaced"),
])
def test_the_build_refuses_what_the_engine_could_not_start(tmp_path, body, words):
    assets = tmp_path / "assets"
    assets.mkdir()
    Image.new("RGB", (4, 4), (1, 2, 3)).save(str(assets / "photo.png"), format="JPEG")    # a JPEG named .png
    Image.new("RGB", (4, 4), (1, 2, 3)).save(str(assets / "laced.png"))
    data = bytearray((assets / "laced.png").read_bytes())
    data[28] = 1                                              # IHDR's interlace byte: Adam7
    (assets / "laced.png").write_bytes(bytes(data))
    with pytest.raises(GameError) as e:
        read(tmp_path, """
            jpeg = assets.image("assets/photo.png")
            laced = assets.image("assets/laced.png")
            s = game.scene("main")
            s.add(Entity("a", %s))
        """ % body)
    assert e.value.code == "G1205" and words in str(e.value), str(e.value)
    assert e.value.line == 8, str(e.value)


# ── scripts ──────────────────────────────────────────────────────────────

PAINT = '''
from apkpy_lib.game import *

pic = assets.image("assets/pic.png")


class Paint(Script):
    def update(self, dt: float):
        c = self.canvas
        c.fill("#000000")
        c.set(0, 0, "#ff0000")
        c.rect(2, 1, 3, 2, "#00ff00")
        c.line(0, 7, 15, 7, "#0000ff")
        c.circle(12, 3, 1, "#ffffff")
        c.rect(6, 0, 4, 4, "#ffff00")
        c.rect(7, 1, 2, 2, "#000000")
        c.flood(7, 1, "#ff00ff")
        c.stamp(pic, 0, 4)
        c.brush_size = 3
        game.exit({"red": c.get(0, 0), "green": c.count("#00ff00"), "blue": c.count("#0000ff"),
                   "white": c.count("#ffffff"), "inside": c.count("#ff00ff"), "out": c.get(99, 99),
                   "stamped": c.get(1, 4), "half": c.get(2, 4), "under": c.get(0, 5), "size": c.width * 100 + c.height,
                   "brush": c.brush, "brush_size": c.brush_size})


class Bad(Script):
    def update(self, dt: float):
        self.canvas.set(0, 0, "red")


class Start(Script):
    def update(self, dt: float):
        c = self.canvas
        game.exit({"size": c.width * 100 + c.height, "a": c.get(0, 0), "b": c.get(1, 0), "half": c.get(2, 0),
                   "clear": c.get(0, 1), "green": c.get(3, 1)})


game = Game("t", size=(100, 100))
s = game.scene("main")
s.add(Entity("c", Canvas(16, 8), Paint()))
bad = game.scene("bad")
bad.add(Entity("c", Canvas(4, 4), Bad()))
start = game.scene("start")
start.add(Entity("c", Canvas(image=pic), Start()))
'''


def test_scripts_paint_and_read_back(tmp_path):
    project, _ = make(tmp_path, PAINT)
    end = result(run(project, "main", "--replay", "", "--steps", "3"))
    assert end["red"] == "#ff0000" and end["blue"] == 16, end
    assert end["green"] == 6 + 1, end                         # the rect, and pic's green pixel stamped at (3, 5)
    assert end["white"] == 9, end                             # radius 1 is dx*dx + dy*dy <= 1 + 1: a 3x3 spot
    assert end["inside"] == 4 and end["out"] == "", end       # flood stops at the yellow ring
    assert end["stamped"] == "#0080ff", end                   # pic's second pixel, stamped at (1, 4)
    assert end["half"] == "#050a0f", end                      # (10, 20, 30) at half over black, rounded
    assert end["under"] == "#000000", end                     # pic is see-through there: the black stays
    assert end["size"] == 1608 and end["brush"] == "" and end["brush_size"] == 3, end


def test_a_colour_that_is_not_one_is_a_python_error(tmp_path):
    project, _ = make(tmp_path, PAINT)
    out = run(project, "bad", "--replay", "", "--steps", "3")
    assert "ValueError: 'red' is not a colour" in out, out
    assert "main.py:" in out, out


def test_a_canvas_starts_from_a_png_with_its_exact_colours(tmp_path):
    project, _ = make(tmp_path, PAINT)
    end = result(run(project, "start", "--replay", "", "--steps", "3"))
    assert end["size"] == 402 and end["a"] == "#ff0000" and end["b"] == "#0080ff", end
    assert end["half"] == "#800a141e", end                     # not premultiplied: the colour is kept
    assert end["clear"] == "#00000000" and end["green"] == "#00ff00", end


def test_scripts_name_the_images_and_sounds_declared_in_their_own_file(tmp_path):
    """main.py's scripts see main.py's assets, as a module's scripts always saw the module's."""
    project, _ = make(tmp_path, PAINT.replace('pic = assets.image("assets/pic.png")',
                                              'pic = assets.image("assets/pic.png")\npop = assets.sound("assets/pop.wav")')
                      .replace("c.brush_size = 3", "c.brush_size = 3\n        audio.play(pop)"))
    src = os.path.join(project.build_dir, "java", "apkpygame", "game")
    java = "".join(open(os.path.join(src, f), encoding="utf-8").read() for f in os.listdir(src))
    assert 'playSound("assets/pop.wav"' in java and 'stamp("assets/pic.png"' in java
    end = result(run(project, "main", "--replay", "", "--steps", "3"))
    assert end["brush_size"] == 3, end


def test_stamp_takes_an_image_declared_in_the_game(tmp_path):
    """A path written as text may not be in the bundle; an image declared with assets.image always is."""
    with pytest.raises(GameError) as e:
        make(tmp_path, PAINT.replace("c.stamp(pic, 0, 4)", 'c.stamp("assets/pic.png", 0, 4)'))
    assert e.value.code == "G2003" and "assets.image" in str(e.value), str(e.value)


# ── the brush ────────────────────────────────────────────────────────────

BRUSH = '''
from apkpy_lib.game import *


class Watch(Script):
    n: int = 0
    strokes: int = 0
    first: int = 0

    def update(self, dt: float):
        self.n += 1
        c = self.canvas
        if c.changed:
            self.strokes += 1
        if self.n == 18:
            self.first = c.count("#ff0000")
        if self.n == 40:
            game.exit({"first": self.first, "red": c.count("#ff0000"), "mid": c.get(20, 10),
                       "above": c.get(20, 8), "below": c.get(20, 12), "strokes": self.strokes})


game = Game("t", size=(100, 100))
s = game.scene("main")
s.add(Entity("pad", Canvas(40, 30, color="#ffffff", brush="#ff0000", brush_size=3), Watch()), at=(50, 50))
'''

# a drag across the canvas (pixels 5..35 of row 10), then one that starts off it and crosses it
DRAGS = "2:drag:35:45:65:45:10,20:drag:5:5:50:90:10"


def test_the_brush_paints_where_the_finger_went(tmp_path):
    project, _ = make(tmp_path, BRUSH)
    out = run(project, "main", "--replay", DRAGS, "--steps", "60")
    end = result(out)
    # brush_size 3 is a 3x3 spot: a line from column 5 to 35 on row 10 covers columns 4..36, rows 9..11
    assert end["first"] == 33 * 3, end
    assert end["red"] == end["first"], end                    # the second drag started off the canvas
    assert end["mid"] == "#ff0000" and end["above"] == "#ffffff" and end["below"] == "#ffffff", end
    assert end["strokes"] >= 5, end
    again = run(project, "main", "--replay", DRAGS, "--steps", "60")
    assert line(out, "APKPYGAME_STATE") == line(again, "APKPYGAME_STATE")
    other = run(project, "main", "--replay", "2:drag:35:50:65:50:10", "--steps", "60")
    assert line(out, "APKPYGAME_STATE") != line(other, "APKPYGAME_STATE")      # other pixels, another hash
