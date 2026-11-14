"""The game's interface: panels, buttons, bars, pausing, Back, changing scene.

Everything is played by replays (the same on the PC and on the phone), and what is drawn is
checked on screenshots.
"""
import json
import os
import subprocess
import textwrap

import pytest
from PIL import Image

from apkpy_lib.game import engine, templates
from apkpy_lib.game._host import toolchain
from apkpy_lib.game.errors import GameError


def make(tmp_path, body):
    (tmp_path / "apkpy.toml").write_text('[app]\nname = "t"\napplication_id = "com.test.ui"\n')
    templates.write_assets(str(tmp_path / "assets"))
    (tmp_path / "game").mkdir()
    (tmp_path / "game" / "main.py").write_text(textwrap.dedent(body), encoding="utf-8")
    from apkpy_lib.game.build import bundle_only
    from apkpy_lib.game.project import Project
    project = Project(str(tmp_path))
    return project, bundle_only(project)


def run(project, *extra, scene="main"):
    from apkpy_lib.game import desktop
    desktop._config.update({"bundle": None, "store": None, "project": project})
    r = subprocess.run(desktop.command(scene, "{}", *extra), capture_output=True, text=True)
    return r.stdout + r.stderr


def play(project, script="", steps=60):
    """(the game's variables at the end, the whole output)."""
    out = run(project, "--replay", script, "--steps", str(steps))
    line = next((l for l in out.splitlines() if l.startswith("APKPYGAME_REPLAY")), None)
    assert line, out
    return json.loads(line.split("vars=", 1)[1]), out


def shot(project, tmp_path, width, height, steps=3):
    path = tmp_path / "shot.png"
    out = run(project, "--screenshot", str(path), "--steps", str(steps), "--width", str(width), "--height", str(height))
    assert path.is_file(), out
    return Image.open(path).convert("RGB")


BUTTONS = '''
from apkpy_lib.game import *

game = Game("t", size=(200, 200), vars={"a": 0, "b": 0, "world": 0, "off": 0, "script": 0})


class Watch(Script):
    def update(self, dt: float):
        if self.button.clicked:
            game.add("script", 1)


s = game.scene("main")
s.add(Entity("a", Button("A", var_add("a", 1), size=(40, 20)), Watch(), ui=True), at=(30, 30))
s.add(Entity("under", Button("U", var_add("b", 10), size=(40, 20), layer=1), ui=True), at=(100, 30))
s.add(Entity("over", Button("O", var_add("b", 1), size=(40, 20), layer=2), ui=True), at=(100, 30))
s.add(Entity("off", Button("X", var_add("off", 1), size=(40, 20), enabled=False), ui=True), at=(30, 80))
s.add(Entity("thing", Shape(size=(200, 40)), OnTap(var_add("world", 1))), at=(100, 30))
s.add(Entity("thing2", Shape(size=(40, 40)), OnTap(var_add("world", 1))), at=(170, 170))
'''


def test_buttons_take_their_presses(tmp_path):
    project, _ = make(tmp_path, BUTTONS)
    v, _ = play(project, "5:tap:30:30")
    assert v["a"] == 1 and v["script"] == 1, "a click, seen once by the script"
    assert v["world"] == 0, "the world under a button does not get the tap"
    v, _ = play(project, "5:tap:100:30")
    assert v["b"] == 1, "only the one on top"
    v, _ = play(project, "5:tap:30:80")
    assert v["off"] == 0, "disabled"
    v, _ = play(project, "5:tap:170:170,20:tap:30:30")
    assert v["world"] == 1 and v["a"] == 1, "the world still gets what the interface does not take"


MODAL = '''
from apkpy_lib.game import *

game = Game("t", size=(200, 200), vars={"under": 0, "menu": 0, "closed": 0})


class Menu(Script):
    def update(self, dt: float):
        if game.steps == 40:
            self.entity.active = False


s = game.scene("main")
s.add(Entity("under", Button("U", var_add("under", 1)), ui=True), at=(50, 150))
s.add(Entity("menu", Panel(size=(100, 60), modal=True), Menu(), ui=True,
             children=[Entity("ok", Button("OK", var_add("menu", 1), size=(60, 20)), ui=True)]), at=(100, 50))
'''


def test_a_modal_panel_blocks_what_is_below_until_it_closes(tmp_path):
    project, _ = make(tmp_path, MODAL)
    v, _ = play(project, "5:tap:50:150,10:tap:100:50")
    assert v == {"under": 0, "menu": 1, "closed": 0}, "the button in the menu works, the one below does not"
    v, _ = play(project, "50:tap:50:150,60:tap:100:50")
    assert v["under"] == 1 and v["menu"] == 0, "closed: its children are gone with it"


PAUSE = '''
from apkpy_lib.game import *

game = Game("t", size=(200, 200), vars={"world": 0, "ui": 0, "paused": 0})


class Count(Script):
    name: str = "world"

    def update(self, dt: float):
        game.add(self.name, 1)


class Boss(Script):
    def update(self, dt: float):
        if game.steps == 10:
            scene.pause("world")
        if scene.is_paused("world"):
            game.set("paused", 1)
        if game.steps == 30:
            scene.resume("world")
            game.set("paused", 0)
        if game.steps == 40:
            ball = scene.find("ball")
            if ball is not None:
                game.set("x", ball.x)


s = game.scene("main")
s.add(Entity("w", Count(name="world")))
s.add(Entity("u", Count(name="ui"), ui=True))
s.add(Entity("boss", Boss(), ui=True))
s.add(Entity("ball", Shape(size=(4, 4)), Collider(size=(4, 4)), Body(velocity=(60, 0), gravity=0)), at=(0, 0))
'''


def test_pausing_a_group(tmp_path):
    project, _ = make(tmp_path, PAUSE)
    v, _ = play(project, steps=20)
    assert v["world"] == 11 and v["ui"] == 20 and v["paused"] == 1, v
    v, out = play(project, steps=50)
    assert v["world"] == 11 + 19 and v["ui"] == 50 and v["paused"] == 0, v
    assert abs(v["x"] - 60 * (11 + 10) / 60) < 1.01, "the body stopped too: %s" % v
    assert play(project, steps=50)[1] == out


SCENES = '''
from apkpy_lib.game import *

game = Game("t", size=(200, 200), vars={"carried_starts": 0, "ticks": 0, "changed_at": 0, "x": 0, "y": 0, "town": 0})
village = assets.tilemap("assets/m.tmj")


class Carried(Script):
    def on_start(self):
        game.add("carried_starts", 1)

    def update(self, dt: float):
        game.add("ticks", 1)


class Leave(Script):
    def update(self, dt: float):
        if game.steps == 5:
            game.goto("second", "from_town", 0.2)


class Hero(Script):
    def on_start(self):
        game.set("changed_at", game.steps)
        game.set("x", self.x)
        game.set("y", self.y)
        if game.arrival == "from_town":
            game.set("town", 1)


a = game.scene("main")
a.add(Entity("box", Shape(size=(10, 10)), Carried(), ui=True, persistent=True, group="always"))
a.add(Entity("leave", Leave()))
b = game.scene("second")
b.add(Entity("map", Tilemap(village, objects={"warp": Entity("warp")})))
b.add(Entity("hero", Hero(), tags=["arrives"]), at=(1, 1))
b.add(Entity("box", Shape(size=(10, 10)), Carried(), ui=True, persistent=True))
'''


def write_map(tmp_path):
    (tmp_path / "assets").mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (16, 16)).save(str(tmp_path / "assets" / "t.png"))
    tmj = {"orientation": "orthogonal", "width": 4, "height": 4, "tilewidth": 16, "tileheight": 16,
           "tilesets": [{"firstgid": 1, "image": "t.png", "imagewidth": 16, "imageheight": 16, "columns": 1,
                         "tilewidth": 16, "tileheight": 16}],
           "layers": [{"type": "tilelayer", "name": "g", "data": [1] * 16},
                      {"type": "objectgroup", "name": "o", "objects": [
                          {"type": "warp", "name": "from_town", "x": 40, "y": 24, "width": 0, "height": 0}]}]}
    (tmp_path / "assets" / "m.tmj").write_text(json.dumps(tmj))


def test_changing_scene_with_a_fade_and_an_arrival(tmp_path):
    write_map(tmp_path)
    project, _ = make(tmp_path, SCENES)
    v, out = play(project, steps=40)
    # the step of the goto, then 6 steps to black (0.2 s / 2 at 60 Hz) with nothing moving
    assert v["changed_at"] == 6 + 6, v
    assert (v["x"], v["y"], v["town"]) == (40, 24, 1), "the hero arrives at the Tiled object"
    assert v["carried_starts"] == 1, "a persistent entity does not start again, and the second scene's copy gives way"
    assert v["ticks"] == 40 - 6, "it only stops during the fade to black"
    assert play(project, steps=40)[1] == out


def test_arriving_nowhere_is_an_error(tmp_path):
    write_map(tmp_path)
    project, _ = make(tmp_path, SCENES.replace('"from_town", 0.2', '"nowhere"'))
    out = run(project, "--replay", "", "--steps", "20")
    assert "G3024" in out and "nowhere" in out, out


BACK = '''
from apkpy_lib.game import *

game = Game("t", size=(100, 100), vars={"lower": 0, "upper": 0})


class Lower(Script):
    def on_back(self) -> bool:
        game.add("lower", 1)
        return True


class Upper(Script):
    open: bool = True

    def on_back(self) -> bool:
        game.add("upper", 1)
        if self.open:
            self.open = False
            return True
        return False


s = game.scene("main")
s.add(Entity("lower", Lower()))
s.add(Entity("upper", Upper()))
'''


def test_back_goes_to_the_scripts_from_the_top(tmp_path):
    project, info = make(tmp_path, BACK)
    src = tmp_path / "j" / "apkpygame" / "game"
    src.mkdir(parents=True)
    (src / "Backs.java").write_text(textwrap.dedent('''
        package apkpygame.game;
        import apkpygame.core.*;
        import apkpygame.testkit.HeadlessPlatform;
        public final class Backs {
            public static void main(String[] a) {
                final java.io.File folder = new java.io.File(a[0]);
                Game g = Game.load(new HeadlessPlatform(new Platform.AssetSource() {
                    public byte[] read(String p) throws java.io.IOException {
                        return java.nio.file.Files.readAllBytes(new java.io.File(folder, p).toPath());
                    }
                    public boolean exists(String p) { return new java.io.File(folder, p).isFile(); }
                }));
                g.start("main", "{}");
                g.step();
                g.step();
                g.back();
                System.out.println(g.var("upper") + " " + g.var("lower") + " " + g.isEnded());
                g.back();
                System.out.println(g.var("upper") + " " + g.var("lower") + " " + g.isEnded());
            }
        }
    '''), encoding="utf-8")
    tools = toolchain()
    classpath = engine.desktop_jar() + os.pathsep + info["game_jar"]
    out = tmp_path / "j" / "classes"
    out.mkdir()
    r = subprocess.run([tools.javac, "--release", "8", "-nowarn", "-Xlint:-options", "-cp", classpath, "-d", str(out),
                        str(src / "Backs.java")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([tools.java, "-cp", classpath + os.pathsep + str(out), "apkpygame.game.Backs", info["bundle"]],
                       capture_output=True, text=True)
    assert r.stdout.split() == ["1.0", "0.0", "false", "2.0", "1.0", "false"], r.stdout + r.stderr


def test_nine_slice_and_bar_on_screen(tmp_path):
    (tmp_path / "assets").mkdir()
    img = Image.new("RGB", (24, 24), (0, 0, 255))
    for x0, y0 in ((0, 0), (16, 0), (0, 16), (16, 16)):
        img.paste((255, 0, 0), (x0, y0, x0 + 8, y0 + 8))
    img.save(str(tmp_path / "assets" / "box.png"))
    project, _ = make(tmp_path, '''
        from apkpy_lib.game import *

        box = assets.image("assets/box.png")
        game = Game("t", size=(200, 100), background="#000000")
        s = game.scene("main")
        s.add(Entity("p", Panel(box, size=(64, 40), pivot=(0, 0)), ui=True), at=(10, 10))
        s.add(Entity("full", Bar(1.0, size=(40, 4), speed=0), ui=True), at=(100, 20))
        s.add(Entity("mid", Bar(0.4, size=(40, 4), speed=0), ui=True), at=(100, 30))
        s.add(Entity("low", Bar(0.1, size=(40, 4), speed=0), ui=True), at=(100, 40))
        ''')
    im = shot(project, tmp_path, 200, 100)
    red, blue = (255, 0, 0), (0, 0, 255)
    assert im.getpixel((10, 10)) == red and im.getpixel((17, 17)) == red, "corners keep their 8 pixels"
    assert im.getpixel((18, 18)) == blue and im.getpixel((71, 11)) == red and im.getpixel((62, 11)) == blue
    assert im.getpixel((74, 10)) == (0, 0, 0) and im.getpixel((10, 50)) == (0, 0, 0), "64 x 40, not more"
    assert im.getpixel((71, 49)) == red
    assert im.getpixel((139, 20)) == (0x58, 0xc8, 0x58)
    assert im.getpixel((110, 30)) == (0xe8, 0xc8, 0x40) and im.getpixel((120, 30)) == (0x30, 0x30, 0x30)
    assert im.getpixel((102, 40)) == (0xd8, 0x48, 0x40)


GLIDE = '''
from apkpy_lib.game import *

game = Game("t", size=(100, 100), vars={"s30": 0, "m30": 0, "done": 0})


class Drop(Script):
    def update(self, dt: float):
        b = self.bar
        if game.steps == 0:
            b.value = 0.0
        if game.steps == 30:
            game.set("s30", b.shown)
            game.set("m30", 1 if b.moving else 0)
        if game.steps == 130:
            game.set("done", 1 if b.moving else 0)


s = game.scene("main")
s.add(Entity("b", Bar(10.0, max=10, speed=0.5), Drop(), ui=True))
'''


def test_a_bar_glides_and_says_so(tmp_path):
    project, _ = make(tmp_path, GLIDE)
    v, _ = play(project, steps=140)
    assert v["m30"] == 1 and v["done"] == 0
    assert 7.3 < v["s30"] < 7.6, "half of max per second, for half a second: %s" % v


def test_the_interface_is_over_the_world_and_at_the_edges(tmp_path):
    project, _ = make(tmp_path, '''
        from apkpy_lib.game import *

        game = Game("t", size=(100, 100), scale="expand", background="#000000")
        s = game.scene("main")
        s.add(Entity("corner", Shape(size=(10, 10), color="#00ff00", pivot=(1, 1)), ui=True, anchor="bottom-right"), at=(100, 100))
        s.add(Entity("over", Shape(size=(20, 20), color="#0000ff"), ui=True), at=(50, 50))
        s.add(Entity("world", Shape(size=(40, 40), color="#ff0000", layer=50)), at=(50, 50))
        ''')
    im = shot(project, tmp_path, 200, 400)      # 100 x 200 virtual: 100 more below
    assert im.getpixel((395 // 2, 395)) == (0, 255, 0), "the corner of the real screen"
    assert im.getpixel((100, 100)) == (0, 0, 255), "over the world, whatever the layer"


@pytest.mark.parametrize("line, code, words", [
    ('Entity("x", Collider(size=(4, 4)), persistent=True)', "G1205", "persistent"),
    ('Entity("x", anchor="top")', "G1205", "interface"),
    ('Entity("x", ui=True, anchor="middle")', "G1205", "anchor"),
])
def test_entity_refusals(tmp_path, line, code, words):
    with pytest.raises(GameError) as e:
        make(tmp_path, '''
            from apkpy_lib.game import *

            game = Game("t")
            s = game.scene("main")
            s.add(%s)
            ''' % line)
    assert e.value.code == code and words in str(e.value), str(e.value)


def test_on_back_says_if_it_dealt_with_it(tmp_path):
    with pytest.raises(GameError) as e:
        make(tmp_path, '''
            from apkpy_lib.game import *

            class M(Script):
                def on_back(self):
                    pass

            game = Game("t")
            game.scene("main")
            ''')
    assert e.value.code == "G2011" and "-> bool" in str(e.value)
