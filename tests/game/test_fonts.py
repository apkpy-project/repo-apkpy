"""Fonts, text layout and pixel art.

- line breaks, pages and measures come from the font's measures in the bundle (never from a
  platform's rasteriser), so scripts see the same numbers everywhere;
- a bitmap font is drawn at whole screen pixels, with no blur, and with colours inside the text;
- pixel_scale makes a virtual pixel a whole number of screen pixels.
"""
import json
import os
import subprocess
import textwrap

import pytest
from PIL import Image

from apkpy_lib.game import templates
from apkpy_lib.game.errors import GameError

CHARS = [chr(c) for c in range(32, 127)]


def write_block_font(folder):
    """A BMFont of solid blocks: every character 5x7 texels, advance 6, at size 8, base 7."""
    os.makedirs(folder, exist_ok=True)
    page = Image.new("RGBA", (6 * 16, 8 * 6), (0, 0, 0, 0))
    lines = ['info face="blocks" size=8', "common lineHeight=10 base=7 scaleW=96 scaleH=48 pages=1",
             'page id=0 file="blocks.png"', "chars count=%d" % len(CHARS)]
    for i, ch in enumerate(CHARS):
        x, y = (i % 16) * 6, (i // 16) * 8
        if ch != " ":
            page.paste((255, 255, 255, 255), (x, y, x + 5, y + 7))
        lines.append("char id=%d x=%d y=%d width=%d height=%d xoffset=0 yoffset=0 xadvance=6 page=0"
                     % (ord(ch), x, y, 5 if ch != " " else 0, 7 if ch != " " else 0))
    page.save(os.path.join(folder, "blocks.png"))
    with open(os.path.join(folder, "blocks.fnt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def make(tmp_path, body):
    (tmp_path / "apkpy.toml").write_text('[app]\nname = "t"\napplication_id = "com.test.fonts"\n')
    templates.write_assets(str(tmp_path / "assets"))
    write_block_font(str(tmp_path / "fonts"))
    (tmp_path / "game").mkdir()
    (tmp_path / "game" / "main.py").write_text(textwrap.dedent(body), encoding="utf-8")
    from apkpy_lib.game.build import bundle_only
    from apkpy_lib.game.project import Project
    project = Project(str(tmp_path))
    return project, bundle_only(project)


def run(project, *extra):
    from apkpy_lib.game import desktop
    desktop._config.update({"bundle": None, "store": None, "project": project})
    r = subprocess.run(desktop.command("main", "{}", *extra), capture_output=True, text=True)
    return r.stdout + r.stderr


LAYOUT = '''
from apkpy_lib.game import *

blocks = assets.font("fonts/blocks.fnt")


def report(name: str, lines: int, pages: int, chars: int) -> str:
    return name + ":" + str(lines) + "/" + str(pages) + "/" + str(chars) + " "


class Check(Script):
    def update(self, dt: float):
        t = self.text
        out = ""
        t.max_width = 30.0
        t.text = "aaa bbb ccc"
        out += report("words", t.lines, t.pages, t.page_chars)
        t.text = "aaaaaaaaaaaa"
        out += report("long", t.lines, t.pages, t.page_chars)
        t.text = "a\\nb"
        out += report("newline", t.lines, t.pages, t.page_chars)
        t.text = "[c=#ff0000]aaa[/c] bb"
        out += report("marks", t.lines, t.pages, t.page_chars)
        t.max_width = 0.0
        t.text = "aaa bbb ccc"
        out += report("nowrap", t.lines, t.pages, t.page_chars)
        game.exit({"out": out, "measure": t.measure("abc"), "width": t.width, "line": t.line_height})


class Paged(Script):
    def update(self, dt: float):
        t = self.text
        before = t.page_chars
        t.page = 1
        game.exit({"pages": t.pages, "first": before, "second": t.page_chars})


game = Game("t", size=(100, 100))
s = game.scene("main")
s.add(Entity("c", Text("x", font=blocks, size=8), Check()))
s2 = game.scene("paged")
s2.add(Entity("p", Text("aaaa bbbb cccc", font=blocks, size=8, max_width=30, max_lines=2), Paged()))
'''


def result(out):
    assert "APKPYGAME_RESULT " in out, out
    return json.loads(out.split("APKPYGAME_RESULT ", 1)[1].splitlines()[0])["result"]


def test_layout_uses_the_fonts_measures(tmp_path):
    project, _ = make(tmp_path, LAYOUT)
    end = result(run(project, "--replay", "", "--steps", "3"))
    assert end["out"] == "words:3/1/9 long:3/1/12 newline:2/1/2 marks:2/1/5 nowrap:1/1/11 ", end
    assert end["measure"] == 18 and end["width"] == 66 and end["line"] == 10, end
    from apkpy_lib.game import desktop
    desktop._config.update({"bundle": None, "store": None, "project": project})
    r = subprocess.run(desktop.command("paged", "{}", "--replay", "", "--steps", "3"), capture_output=True, text=True)
    assert result(r.stdout + r.stderr) == {"pages": 2, "first": 8, "second": 4}


PIXELS = '''
from apkpy_lib.game import *

blocks = assets.font("fonts/blocks.fnt")
game = Game("t", size=(100, 50), scale="fit", background="#000000", font=blocks, pixel_scale=True)
s = game.scene("main")
s.add(Entity("c", Text("a[c=#ff0000]b[/c]", size=8)), at=(10, 20))
'''


def test_bitmap_font_at_whole_pixels(tmp_path):
    project, _ = make(tmp_path, PIXELS)
    shot = tmp_path / "shot.png"
    out = run(project, "--screenshot", str(shot), "--steps", "2", "--width", "350", "--height", "175")
    assert shot.is_file(), out
    img = Image.open(shot).convert("RGB")
    assert img.size == (350, 175)
    colours = {c for _, c in img.getcolors(100000)}
    assert colours == {(0, 0, 0), (255, 255, 255), (255, 0, 0)}, "no blur: %s" % colours
    # 350/100 = 3.5: the scale is 3, and the game (300x150) is centred: 25 and 12.5 at the edges
    white = [(x, y) for y in range(175) for x in range(350) if img.getpixel((x, y)) == (255, 255, 255)]
    red = [(x, y) for y in range(175) for x in range(350) if img.getpixel((x, y)) == (255, 0, 0)]
    width = lambda ps: max(p[0] for p in ps) - min(p[0] for p in ps) + 1
    height = lambda ps: max(p[1] for p in ps) - min(p[1] for p in ps) + 1
    assert (width(white), height(white)) == (15, 21), "5x7 texels, 3 screen pixels each"
    assert (width(red), height(red)) == (15, 21)
    assert min(p[0] for p in white) == 25 + 10 * 3
    assert min(p[0] for p in red) - min(p[0] for p in white) == 18, "advance 6 at 3 pixels"


LETTERS = '''
from apkpy_lib.game import *

blocks = assets.font("fonts/blocks.fnt")
game = Game("t", size=(100, 50), background="#000000", font=blocks, pixel_scale=True)


class Typing(Script):
    def on_start(self):
        self.text.visible_chars = 2


s = game.scene("main")
s.add(Entity("c", Text("abcd", size=8), Typing()), at=(10, 20))
'''


def test_letter_by_letter(tmp_path):
    project, _ = make(tmp_path, LETTERS)
    shot = tmp_path / "shot.png"
    run(project, "--screenshot", str(shot), "--steps", "2", "--width", "100", "--height", "50")
    img = Image.open(shot).convert("RGB")
    columns = [x for x in range(100) if any(img.getpixel((x, y)) != (0, 0, 0) for y in range(50))]
    assert (min(columns), max(columns)) == (10, 10 + 6 + 4), columns


def system_font():
    for path in ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if os.path.isfile(path):
            return path
    pytest.skip("no TrueType font on this machine")


def test_truetype_font(tmp_path):
    import shutil
    (tmp_path / "fonts").mkdir()
    shutil.copy(system_font(), tmp_path / "fonts" / "body.ttf")
    project, _ = make(tmp_path, '''
        from apkpy_lib.game import *

        body = assets.font("fonts/body.ttf")
        game = Game("t", size=(200, 100), background="#000000")
        s = game.scene("main")
        s.add(Entity("c", Text("One two three four five six seven eight", font=body, size=16, max_width=120)), at=(4, 20))
        ''')
    measures = json.loads((tmp_path / "build" / "apkpygame" / "bundle" / "fonts" / "body.ttf.json").read_text(encoding="utf-8"))
    assert measures["kind"] == "ttf" and measures["advances"]["i"] < measures["advances"]["W"]
    assert (tmp_path / "build" / "apkpygame" / "bundle" / "fonts" / "body.ttf").is_file()
    shot = tmp_path / "shot.png"
    run(project, "--screenshot", str(shot), "--steps", "2", "--width", "200", "--height", "100")
    img = Image.open(shot).convert("L")
    rows = [y for y in range(100) if any(img.getpixel((x, y)) > 128 for x in range(200))]
    assert max(rows) > 30, "more than one line"
    assert max(x for x in range(200) if any(img.getpixel((x, y)) > 128 for y in range(100))) < 4 + 125


@pytest.mark.parametrize("name, content, code, words", [
    ("bad.fnt", "<font></font>", "G1221", "text format"),
    ("two.fnt", 'info size=8\ncommon lineHeight=9 base=7\npage id=0 file="a.png"\npage id=1 file="b.png"\n', "G1221", "2 pages"),
    ("none.fnt", 'info size=8\ncommon lineHeight=9 base=7\npage id=0 file="missing.png"\n'
                 "char id=65 x=0 y=0 width=1 height=1 xoffset=0 yoffset=0 xadvance=1\n", "G1221", "not in the project"),
    ("bad.ttf", "not a font", "G1221", "not a font"),
    ("bad.txt", "text", "G1211", "not a font file"),
])
def test_font_errors(tmp_path, name, content, code, words):
    (tmp_path / "fonts").mkdir()
    (tmp_path / "fonts" / name).write_text(content)
    with pytest.raises(GameError) as e:
        make(tmp_path, '''
            from apkpy_lib.game import *

            f = assets.font("fonts/%s")
            game = Game("t")
            game.scene("main")
            ''' % name)
    assert e.value.code == code and words in str(e.value) and "game/main.py:4" in str(e.value), str(e.value)
