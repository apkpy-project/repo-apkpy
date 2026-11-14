"""The declaration reader: what it reads, what it refuses (with which code and line)."""
import json
import os
import textwrap

import pytest

from apkpy_lib.game.compiler import bundle, reader
from apkpy_lib.game.errors import GameError
from apkpy_lib.game.project import Project
from apkpy_lib.game import templates

HEADER = 'from apkpy_lib.game import *\ngame = Game("t")\n'


@pytest.fixture
def project(tmp_path):
    (tmp_path / "apkpy.toml").write_text('[app]\nname = "t"\napplication_id = "com.test.t"\n')
    (tmp_path / "game").mkdir()
    templates.write_assets(str(tmp_path / "assets"))
    return tmp_path


def read(project, body, header=HEADER):
    path = project / "game" / "main.py"
    path.write_text(header + textwrap.dedent(body), encoding="utf-8")
    return reader.read(str(path), str(project))


def fails(project, body, code, line=None, header=HEADER):
    with pytest.raises(GameError) as e:
        read(project, body, header)
    assert e.value.code == code, str(e.value)
    if line is not None:
        assert e.value.line == line, str(e.value)
    return e.value


def test_the_template_reads(project):
    (project / "game" / "main.py").write_text(templates.MAIN_BLANK.format(name="Demo"), encoding="utf-8")
    model = reader.read(str(project / "game" / "main.py"), str(project))
    scene = model.scenes[0]
    assert model.name == "Demo" and scene.start and scene.music.path == "assets/theme.wav"
    coins = [e for e in scene.entities if e.name == "coin"]
    assert len(coins) == 5
    mover = next(c for c in coins[1].components if c.type == "Mover")
    assert mover.values["velocity"] == [-80.0, -160 / 3]       # prefab parameters folded: speed=-160
    assert coins[2].scale == 1.4 and coins[3].rotation == 30


def test_prefab_parameters_and_arithmetic(project):
    model = read(project, """
        star = assets.image("assets/star.png")
        @prefab
        def thing(size: float = 2, label: str = "x"):
            return Entity("t-" + label, Sprite(star, alpha=size / 4), Text(f"{label}:{size:.1f}"))
        s = game.scene("main")
        s.add(thing(), at=(10 * 2, -5))
        s.add(thing(3, label="y"))
    """)
    a, b = model.scenes[0].entities
    assert (a.name, a.x, a.y) == ("t-x", 20, -5)
    assert a.components[0].values["alpha"] == 0.5
    assert b.components[1].values["text"] == "y:3.0"


def test_nothing_is_executed(project, tmp_path):
    marker = tmp_path / "ran.txt"
    read(project, """
        s = game.scene("main")
        '''open(%r, "w")'''
    """ % str(marker))
    assert not marker.exists()


@pytest.mark.parametrize("body, code, line", [
    ("for i in range(3):\n    pass\n", "G1201", 3),
    ("if True:\n    pass\n", "G1201", 3),
    ("import os\n", "G1207", 3),
    ("from random import randint\n", "G1207", 3),
    ("x = len([1])\n", "G1203", 3),
    ("x = [i for i in (1, 2)]\n", "G1202", 3),
    ("s = game.scene('main')\ns.add(Entity('a', Sprite(assets.image('nope.png'))))\n", "G1211", 4),
    ("s = game.scene('main')\ns.add(Entity('a', Spin(spped=3)))\n", "G1204", 4),
    ("s = game.scene('main')\ns.add(Entity('a', Shape(color='red')))\n", "G1205", 4),
    ("s = game.scene('main')\ns.add(Entity('a', Text()))\n", "G1206", 4),
    ("class Player:\n    pass\n", "G2001", 3),
    ("class Player(Script):\n    x = 1\n", "G2006", 4),
    ("@prefab\n@prefab\ndef helper():\n    return 1\n", "G1212", 5),
    ("game2 = Game('again')\n", "G1209", 3),
    ("a = game.scene('main')\nb = game.scene('main')\n", "G1210", 4),
    ("a = game.scene('a', start=True)\nb = game.scene('b', start=True)\n", "G1210", 4),
    ("s = game.scene('main')\ns.add(Entity('a', OnTap(destroy, sound)))\n", "G1205", 4),
])
def test_refusals_have_a_code_and_a_line(project, body, code, line):
    fails(project, body, code, line)


def test_suggests_close_names(project):
    e = fails(project, "s = game.scene('main')\ns.add(Entity('a', Spin(speeed=3)))\n", "G1204")
    assert "speed" in str(e)


def test_no_scene_and_no_game(project):
    fails(project, "", "G1210")
    fails(project, "s = 1\n", "G1209", header="from apkpy_lib.game import *\n")


def test_bundle_matches_the_engine_format(project):
    model = read(project, """
        star = assets.image("assets/star.png")
        pop = assets.sound("assets/pop.wav")
        s = game.scene("main", background="#102030", camera={"x": 0, "y": 0, "zoom": 2})
        s.add(Entity("a", Sprite(star, pivot=0.5, filter="nearest"), OnTap(sound(pop, 0.5), exit_game({"k": [1, 2]})),
                     tags=["t"], children=[Entity("c", Shape(shape="circle", radius=3), at=(1, 2))]), at=(5, 6))
    """)
    info = bundle.write(model, Project(str(project)))
    scene = json.loads((project / "build" / "apkpygame" / "bundle" / "scenes" / "main.json").read_text())
    game = json.loads((project / "build" / "apkpygame" / "bundle" / "game.json").read_text())
    assert game["format"] == 1 and game["start_scene"] == "main" and game["size"] == [360, 640]
    e = scene["entities"][0]
    assert e["transform"] == {"x": 5, "y": 6} and e["tags"] == ["t"]
    assert e["components"][0] == {"type": "Sprite", "image": "assets/star.png", "pivot": 0.5, "filter": "nearest"}
    assert e["components"][1]["actions"] == [{"do": "sound", "sound": "assets/pop.wav", "volume": 0.5},
                                             {"do": "exit", "result": {"k": [1, 2]}}]
    assert e["children"][0]["components"][0] == {"type": "Shape", "shape": "circle", "radius": 3}
    assert scene["camera"]["zoom"] == 2 and scene["background"] == "#102030"
    assert os.path.isfile(os.path.join(info["bundle"], "assets", "pop.wav"))


def test_atlas(project):
    from PIL import Image
    (project / "assets" / "coins").mkdir()
    for i, size in enumerate((16, 24, 8)):
        Image.new("RGBA", (size, size), (255, 0, 0, 255)).save(project / "assets" / "coins" / ("c%d.png" % i))
    model = read(project, """
        coins = assets.atlas("assets/coins/*.png")
        s = game.scene("main")
        s.add(Entity("a", Sprite(coins, frame="c1")))
        s.add(Entity("b", Sprite(coins, frame=2)))
    """)
    bundle.write(model, Project(str(project)))
    scene = json.loads((project / "build" / "apkpygame" / "bundle" / "scenes" / "main.json").read_text())
    a, b = (e["components"][0] for e in scene["entities"])
    assert a["image"] == "atlas/assets_coins.png" and a["region"][2:] == [24, 24] and b["region"][2:] == [8, 8]
    assert a["region"][:2] != b["region"][:2]
    fails(project, 'coins = assets.atlas("assets/coins/*.png")\ns = game.scene("m")\ns.add(Entity("a", Sprite(coins, frame="zz")))\n',
          "G1214", 5)


APP = '''from apkpy_lib import *
home = Screen(id="home")
pause_menu = Screen(id="pause_menu")
translations({"en": {"hi": "Hello", "go": "Go"}, "pt": {"hi": "Ola"}}, default="en")
run(start_screen=home)
'''


def build_with_app(project, body):
    from apkpy_lib.game.build import bundle_only
    (project / "writehere.py").write_text(APP, encoding="utf-8")
    (project / "game" / "main.py").write_text(HEADER + textwrap.dedent(body), encoding="utf-8")
    bundle_only(Project(str(project)))
    out = project / "build" / "apkpygame" / "bundle"
    return json.loads((out / "scenes" / "main.json").read_text(encoding="utf-8")), out


def test_texts_and_on_back_reach_the_bundle(project):
    scene, out = build_with_app(project, """
        s = game.scene("main", on_back=open_app("pause_menu", {"from": "back"}))
        s.add(Entity("a", Text(t("hi"), size=12)))
    """)
    assert scene["on_back"] == [{"do": "open", "screen": "pause_menu", "data": {"from": "back"}}]
    assert scene["entities"][0]["components"][0] == {"type": "Text", "key": "hi", "text": "Hello", "size": 12}
    texts = json.loads((out / "texts.json").read_text(encoding="utf-8"))
    assert texts["default"] == "en" and texts["languages"]["pt"]["hi"] == "Ola"


def test_the_app_is_checked(project):
    with pytest.raises(GameError) as e:
        build_with_app(project, "s = game.scene('main')\ns.add(Entity('a', OnTap(open_app('shop'))))\n")
    assert e.value.code == "G1102" and e.value.line == 4 and "pause_menu" in str(e.value)
    with pytest.raises(GameError) as e:
        build_with_app(project, "s = game.scene('main', on_back=[open_app('nope')])\n")
    assert e.value.code == "G1102" and e.value.line == 3
    with pytest.raises(GameError) as e:
        build_with_app(project, "s = game.scene('main')\ns.add(Entity('a', Text(t('missing'))))\n")
    assert e.value.code == "G1103" and e.value.line == 4


def test_t_needs_a_written_key(project):
    fails(project, "k = 'x'\ns = game.scene('main')\ns.add(Entity('a', Text(t(k + 1))))\n", "G1205")
    fails(project, "k = 3\ns = game.scene('main')\ns.add(Entity('a', Text(t(k))))\n", "G1204")


# ── without code ──────────────────────────────────────────────────────────────

def _sheet(project, name="hero.png", size=(64, 16)):
    from PIL import Image
    Image.new("RGBA", size, (255, 0, 0, 255)).save(project / "assets" / name)


def test_sheet_animator_and_templates(project):
    _sheet(project)
    model = read(project, """
        hero = assets.sheet("assets/hero.png", frame=(16, 16))
        pop = assets.sound("assets/pop.wav")
        @prefab
        def spark():
            return Entity("spark", Emitter(burst=5), Lifetime(0.5))
        s = game.scene("main", vars={"lives": 3}, rules=[when("lives <= 0", exit_game({"score": "{score}"})),
                                                       when("count(coin) == 0", sound(pop))])
        s.add(Entity("p", Sprite(hero, frame=1), Animator({"run": {"frames": [0, 1, 2, 3], "fps": 10}}),
                     Collider(size=(10, 14)), Body(gravity=900), PlatformerController(),
                     OnCollide("enemy", destroy("other"), spawn(spark(), offset=(0, -4)), side="top"),
                     Spawner(spark(), every=2, area=(0, 0, 10, 10))))
        s.add(Entity("hud", Text("Lives {lives}")), at=(8, 8), ui=True)
    """)
    from apkpy_lib.game.compiler import bundle
    bundle.write(model, Project(str(project)))
    scene = json.loads((project / "build" / "apkpygame" / "bundle" / "scenes" / "main.json").read_text())
    p = scene["entities"][0]["components"]
    assert p[0] == {"type": "Sprite", "image": "assets/hero.png", "region": [16, 0, 16, 16]}
    assert p[1]["animations"]["run"]["frames"][3] == [48, 0, 16, 16]
    oncollide = p[5]
    assert oncollide["side"] == "top" and oncollide["actions"][0] == {"do": "destroy", "target": "other"}
    assert oncollide["actions"][1]["entity"]["components"][0]["type"] == "Emitter"
    assert p[6]["entity"]["name"] == "spark" and p[6]["area"] == [0, 0, 10, 10]
    assert scene["rules"][0] == {"var": "lives", "op": "<=", "value": 0.0,
                                 "actions": [{"do": "exit", "result": {"score": "{score}"}}]}
    assert scene["rules"][1]["count"] == "coin" and scene["vars"] == {"lives": 3}
    assert scene["entities"][1]["ui"] is True


@pytest.mark.parametrize("body, code", [
    ("h = assets.sheet('assets/hero.png')\n", "G1206"),
    ("h = assets.sheet('assets/hero.png', frame=(16, 16))\ns = game.scene('m')\ns.add(Entity('a', Sprite(h, frame=9)))\n",
     "G1214"),
    ("h = assets.sheet('assets/hero.png', frame=(16, 16))\ns = game.scene('m')\n"
     "s.add(Entity('a', Sprite(h), Animator({'x': {'frames': [0, 7]}})))\n", "G1214"),
    ("s = game.scene('m')\ns.add(Entity('a', Animator({'x': {'frames': [0]}})))\n", "G1205"),
    ("s = game.scene('m', rules=[when('lives is 0', destroy())])\n", "G1205"),
    ("s = game.scene('m', rules=[when('lives <= 0')])\n", "G1205"),
    ("s = game.scene('m', camera={'follow': 'nobody'})\n", "G1210"),
    ("s = game.scene('m', camera={'bounds': 'map'})\n", "G1210"),
    ("s = game.scene('m', vars={'lives': 'three'})\n", "G1205"),
    ("s = game.scene('m')\ns.add(Entity('a', Spawner(Sprite(assets.image('assets/star.png')))))\n", "G1205"),
])
def test_phase4_refusals(project, body, code):
    _sheet(project)
    fails(project, body, code)


def _tmj(project, objects=("coin",)):
    (project / "levels").mkdir(exist_ok=True)
    from PIL import Image
    Image.new("RGBA", (32, 16), (0, 0, 0, 255)).save(project / "assets" / "tiles.png")
    data = [0] * 20
    data[15:20] = [1, 1, 1, 1, 1]
    tmj = {"orientation": "orthogonal", "width": 5, "height": 4, "tilewidth": 16, "tileheight": 16,
           "tilesets": [{"firstgid": 1, "image": "../assets/tiles.png", "columns": 2, "tilewidth": 16,
                         "tileheight": 16}],
           "layers": [{"type": "tilelayer", "name": "ground", "data": data,
                       "properties": [{"name": "solid", "type": "bool", "value": True}]},
                      {"type": "group", "layers": [{"type": "objectgroup", "objects": [
                          {"class": k, "x": 16 * i, "y": 16, "width": 16, "height": 16} for i, k in
                          enumerate(objects)]}]}]}
    (project / "levels" / "one.tmj").write_text(json.dumps(tmj))


def test_tilemap_objects_and_bounds(project):
    _tmj(project, ("coin", "coin", "player"))
    model = read(project, """
        level = assets.tilemap("levels/one.tmj")
        s = game.scene("main", camera={"follow": "hero", "bounds": "map"})
        s.add(Entity("map", Tilemap(level, objects={"coin": Entity("c", Shape()), "player": Entity("hero")})),
              at=(100, 0))
    """)
    names = [(e.name, e.x, e.y) for e in model.scenes[0].entities]
    assert names == [("map", 100, 0), ("c", 108.0, 24.0), ("c", 124.0, 24.0), ("hero", 140.0, 24.0)]
    assert model.scenes[0].camera["bounds"] == [100, 0, 80, 64]
    from apkpy_lib.game.compiler import bundle
    bundle.write(model, Project(str(project)))
    out = project / "build" / "apkpygame" / "bundle"
    tm = json.loads((out / "tilemaps" / "levels_one.json").read_text())
    assert tm["cols"] == 5 and tm["solid"][15:] == [1] * 5 and sum(tm["solid"]) == 5
    assert tm["image"] == "assets/tiles.png" and (out / "assets" / "tiles.png").is_file()


def test_tilemap_unknown_objects_and_layers(project):
    _tmj(project, ("coin", "door"))
    e = fails(project, "level = assets.tilemap('levels/one.tmj')\ns = game.scene('m')\n"
                       "s.add(Entity('map', Tilemap(level, objects={'coin': Entity('c')})))\n", "G1217")
    assert "door" in str(e)
    fails(project, "level = assets.tilemap('levels/one.tmj')\ns = game.scene('m')\n"
                   "s.add(Entity('map', Tilemap(level, solid=['nope'], objects={'coin': Entity('c'), "
                   "'door': Entity('d')})))\n", "G1216")


def test_goto_scene_must_exist(project):
    from apkpy_lib.game.build import check_against_app
    model = read(project, "s = game.scene('main')\ns.add(Entity('a', Timer(1, goto_scene('two'))))\n")
    with pytest.raises(GameError) as e:
        check_against_app(model, None, Project(str(project)))
    assert e.value.code == "G1210" and e.value.line == 4


def test_a_25d_scene_reads_and_writes(project):
    """kind="2.5d": the 3D camera keys, (x, y, elevation), Billboard sheets (frame size), Block, Plane, GridController."""
    model = read(project, """
        star = assets.image("assets/star.png")
        sheet = assets.sheet("assets/star.png", frame=(16, 16))
        s = game.scene("town", start=True, kind="2.5d",
                       camera={"follow": "hero", "pitch": 45, "yaw": 10, "distance": 200, "fov": 40, "fog": (100, 300)})
        s.add(Entity("hero", Billboard(sheet, directions=4), GridController(tile=16)), at=(8, 8, 2))
        s.add(Entity("house", Block((32, 16), 24, top=star, side_color="#ccbbaa")), at=(40, 40))
        s.add(Entity("tree", Plane(star, size=(20, 30), cross=True)), at=(60, 40))
    """)
    bundle.write(model, Project(str(project)))
    scene = json.loads((project / "build" / "apkpygame" / "bundle" / "scenes" / "town.json").read_text())
    assert scene["kind"] == "2.5d" and scene["camera"]["fog"] == [100, 300] and scene["camera"]["pitch"] == 45
    hero, house, tree = scene["entities"]
    assert hero["transform"] == {"x": 8, "y": 8, "elevation": 2}
    assert hero["components"][0]["frame_size"] == [16, 16] and hero["components"][0]["directions"] == 4
    assert house["components"][0]["size"] == [32, 16] and house["components"][0]["top"] == "assets/star.png"
    assert tree["components"][0]["cross"] is True


@pytest.mark.parametrize("body", [
    's = game.scene("m", start=True, camera={"pitch": 40})',                    # 3D camera keys in a 2D scene
    's = game.scene("m", start=True, kind="3d")',                               # no such kind
    's = game.scene("m", start=True, kind="2.5d", camera={"fog": 100})',        # fog is (start, end)
])
def test_25d_refusals(project, body):
    fails(project, body, "G1205")


def test_only_if_runs_its_actions_when_its_condition_holds(project):
    model = read(project, """
        pop = assets.sound("assets/pop.wav")
        s = game.scene("main", vars={"keys": 0})
        s.add(Entity("door", Shape(size=(16, 32)), OnTap(only_if("keys >= 1", var_add("keys", -1), destroy()),
                                                         only_if("count(door) == 1", sound(pop)))), at=(8, 8))
    """)
    bundle.write(model, Project(str(project)))
    scene = json.loads((project / "build" / "apkpygame" / "bundle" / "scenes" / "main.json").read_text())
    tap = scene["entities"][0]["components"][1]
    assert tap["actions"][0] == {"do": "if", "condition": {"var": "keys", "op": ">=", "value": 1.0},
                                 "actions": [{"do": "var_add", "var": "keys", "amount": -1}, {"do": "destroy"}]}
    assert tap["actions"][1]["condition"] == {"count": "door", "op": "==", "value": 1.0}
    e = fails(project, """
        s = game.scene("main")
        s.add(Entity("door", OnTap(only_if("keys > one", destroy()))))
    """, "G1205", line=5)
    assert "only_if: the condition is" in str(e)


def test_deflect_is_read_with_its_angle(project):
    model = read(project, """
        s = game.scene("main")
        s.add(Entity("ball", Collider(size=(8, 8)), Body(velocity=(0, 300), bounce=1),
                     OnCollide("paddle", deflect(45), deflect(target="other"))), at=(8, 8))
    """)
    bundle.write(model, Project(str(project)))
    scene = json.loads((project / "build" / "apkpygame" / "bundle" / "scenes" / "main.json").read_text())
    actions = scene["entities"][0]["components"][2]["actions"]
    assert actions[0]["do"] == "deflect" and actions[0]["angle"] == 45
    assert actions[1]["do"] == "deflect" and actions[1]["target"] == "other"
