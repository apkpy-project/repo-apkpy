"""The Studio reads and changes the game's own Python (apkpy_lib.game.studio.source): nothing changed, the file is the
same byte for byte; changed, only what changed is rewritten, and the build still reads it."""
import ast
import glob
import os
import shutil

import pytest

from conftest import EXAMPLES, TEMPLATES

from apkpy_lib.game.studio import check as studio_check
from apkpy_lib.game.studio.source import Source, Stale, bind, call_text, entity_text, literal, prefab_text

GAME_FILES = sorted(glob.glob(os.path.join(EXAMPLES, "*", "game", "**", "*.py"), recursive=True)
                    + glob.glob(os.path.join(TEMPLATES, "*", "game", "**", "*.py"), recursive=True))
IGNORE = shutil.ignore_patterns("build", "__pycache__", ".studio_backups", "*.apk")


def copy_of(name, tmp_path):
    folder = tmp_path / name
    shutil.copytree(os.path.join(EXAMPLES, name), str(folder), ignore=IGNORE)
    return folder


def builds(folder):
    error = studio_check.check(str(folder))
    assert error is None, studio_check.problem_line(error)


@pytest.mark.parametrize("path", GAME_FILES, ids=lambda p: os.path.relpath(p, os.path.dirname(os.path.dirname(p))))
def test_every_game_file_reads_and_stays_the_same(path):
    with open(path, encoding="utf-8", newline="") as fh:
        raw = fh.read()
    s = Source(path)
    assert s.text == raw and not s.dirty and s.save() is False
    for piece in s.pieces:
        for value in (piece.call, piece.entity):
            if value is not None:
                assert s.at(value.path).text == value.text, piece
                for item in getattr(value, "items", ()):
                    assert s.at(item.value.path).text == item.value.text, (piece, item.key)
        assert raw[piece.start:piece.end] == piece.text
        if piece.kind == "prefab":
            assert piece.text.startswith("@prefab")


def test_the_pieces_of_the_platformer():
    s = Source(os.path.join(EXAMPLES, "platformer", "game", "main.py"))
    assert s.first("game").call.get(0).value == "Meadow Run"
    assert s.first("game").call.get("size").value == (320, 180)
    assert ("hero", "sheet", "assets/hero.png") in s.assets("sheet")
    assert s.prefab_names() == ["player", "coin", "enemy", "goal", "pad"]
    pad = s.first("prefab", "pad")
    assert [(f.name, f.annotation, f.default.text) for f in pad.params] == [("image", "", "left"), ("key", "str", '"left"')]
    coin = s.first("prefab", "coin").entity
    assert [v.func for v in coin.args[1:]] == ["Sprite", "Animator", "Collider", "OnCollide"]
    assert coin.get("tags").value == ["coin"]
    on = coin.get(4)
    assert bind(on, ["tag", "*actions"]) == {"tag": 0, "actions": (1, None)}
    assert [a.func for a in on.args[1:]] == ["destroy", "var_add", "sound"]
    scene = s.first("scene", "meadow")
    assert s.scene_names == {"meadow": "main"} and scene.call.get("start").value is True
    adds = s.find("add", "meadow")
    assert len(adds) == 6 and adds[0].entity.func == "Entity" and adds[3].call.get(0).func == "pad"
    assert adds[0].call.get(0).get(1).func == "Tilemap"


def test_a_change_rewrites_only_what_changed_and_builds(tmp_path):
    folder = copy_of("platformer", tmp_path)
    path = str(folder / "game" / "main.py")
    before = open(path, encoding="utf-8", newline="").read()
    s = Source(path)
    s.set_arg(s.first("game").call, "size", "(400, 240)")
    s.set_arg(s.first("game").call, "pixel_scale", "True")
    player = s.first("prefab", "player").entity
    s.set_arg(player.get(4), "jump", "320")
    s.insert(s.first("prefab", "coin").entity, "Spin(90)")
    on = s.first("prefab", "coin").entity.get(4)
    s.set_rest(on, 1, ["destroy()", 'var_add("coins", 2)', "sound(ding)"])
    s.add_statement(prefab_text("spring", "spring", ["Sprite(flag, filter=\"nearest\")",
                                                     "Collider(size=(10, 10), trigger=True)"], tags=["spring"]),
                    after=s.find("prefab")[-1])
    s.add_statement("meadow.add(spring(), at=(100, 120))", after=s.find("add", "meadow")[-1])
    s.add_statement('boing = assets.sound("assets/jump.wav")', after=s.find("asset")[-1])
    assert s.dirty and s.save()
    after = open(path, encoding="utf-8", newline="").read()
    flat = after.replace("\r\n", "\n")
    assert "\r\n" not in before or "\n" not in after.replace("\r\n", ""), "new lines end as the file does"
    assert 'game = Game("Meadow Run", size=(400, 240), scale="fit"' in flat
    assert 'vars={"coins": 0, "lives": 3}, pixel_scale=True)' in flat
    assert "PlatformerController(speed=110, jump=320)" in flat
    assert ('                  OnCollide("player", destroy(), var_add("coins", 2), sound(ding)),\n'
            '                  Spin(90),\n'
            '                  tags=["coin"])') in flat
    assert ('                  TouchButton(key, radius=22))\n\n\n@prefab\ndef spring():\n    return Entity("spring",\n'
            '                  Sprite(flag, filter="nearest"),\n') in flat
    assert 'tags=["spring"])\n\n\nmeadow = game.scene(' in flat
    assert flat.endswith('meadow.add(pad(up, "jump"), at=(292, 152), ui=True)\nmeadow.add(spring(), at=(100, 120))\n')
    assert 'music = assets.music("assets/theme.wav")\nboing = assets.sound("assets/jump.wav")\n\n\n@prefab' in flat
    changed = [n for n, (a, b) in enumerate(zip(before.splitlines(), after.splitlines())) if a != b]
    assert changed and changed[0] >= 7, "the lines above Game(...) are untouched"
    builds(folder)
    s.remove_piece(s.first("asset", "boing"))
    s.remove_piece(s.find("add", "meadow")[-1])
    s.remove_piece(s.first("prefab", "spring"))
    s.remove_arg(s.first("prefab", "coin").entity, 5)
    s.set_rest(s.first("prefab", "coin").entity.get(4), 1, ["destroy()", 'var_add("coins")', "sound(ding)"])
    s.set_arg(s.first("prefab", "player").entity.get(4), "jump", "300")
    s.remove_arg(s.first("game").call, "pixel_scale")
    s.set_arg(s.first("game").call, "size", "(320, 180)")
    assert s.text == before, "taking each change back gives the same file"
    while s.undo():
        pass
    assert s.text == before, "undo goes back to the first text"
    for _ in range(8):
        s.redo()
    assert s.text == after, "and redo comes back through the saved one"
    s.set_text(before)
    s.save()
    assert open(path, encoding="utf-8", newline="").read() == before


def test_new_lines_keep_the_file_s_line_endings_and_columns_count_letters(tmp_path):
    path = str(tmp_path / "main.py")
    text = ('from apkpy_lib.game import *\r\n\r\ngame = Game("Café", size=(360, 640), vars={"pão": 0})\r\n'
            'play = game.scene("main", start=True)\r\n'
            'play.add(Entity("título", Text("Olá {pão}", size=20)), at=(180, 40), ui=True)\r\n')
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    s = Source(path)
    add = s.first("add", "play")
    assert add.entity.get(1).get("size").text == "20", "UTF-8 columns of ast become letters"
    s.set_arg(add.entity.get(1), "size", "24")
    s.insert(s.first("add", "play").entity, 'Spin(10)')
    s.add_statement(prefab_text("star", "star", ['Shape(size=(4, 4), color="#ffffff")']), after=s.first("scene"))
    s.add_statement("play.add(star(), at=(10, 10))")
    assert "\n" not in s.text.replace("\r\n", ""), "every new line ends as the others do"
    assert 'Text("Olá {pão}", size=24), Spin(10)), at=(180, 40)' in s.text
    ast.parse(s.text)


def test_values_and_calls_are_written_as_the_examples_write_them():
    assert literal("a \"b\"") == '"a \\"b\\""' and literal(3) == "3" and literal(2.0) == "2.0" and literal(0.25) == "0.25"
    assert literal((1, 2)) == "(1, 2)" and literal((1,)) == "(1,)" and literal([True, None]) == "[True, None]"
    assert literal({"coins": 0}) == '{"coins": 0}'
    assert call_text("Spin", ["90"]) == "Spin(90)"
    long = call_text("Emitter", [], [("rate", "40"), ("lifetime", "(0.2, 0.4)"), ("speed", "(60, 120)"), ("angle", "(80, 100)"),
                                      ("size", "(4, 1)"), ("color", '"#5cd6ff"'), ("color_end", '"#2a2f45"'), ("layer", "-1")], column=16)
    first, second = long.split("\n")
    assert len(first) + 16 <= 120 and second.startswith(" " * (16 + len("Emitter("))) and second.strip().endswith("layer=-1)")
    assert entity_text("star", ["Spin(1)"]) == 'Entity("star", Spin(1))'
    assert entity_text("coin", ["Sprite(c)", "Spin(1)", "Lifetime(2)"], [("tags", '["coin"]')]) == \
        'Entity("coin",\n       Sprite(c),\n       Spin(1),\n       Lifetime(2),\n       tags=["coin"])'


def test_a_value_read_before_a_change_is_found_again_and_a_gone_one_says_so():
    s = Source(text='from apkpy_lib.game import *\ngame = Game("A", size=(1, 2))\nx = game.scene("main", start=True)\n'
                    'x.add(Entity("a", Spin(1)))\nx.add(Entity("b", Spin(2)))\n')
    old = s.find("add", "x")[1].entity
    s.set_arg(s.first("game").call, "size", "(360, 640)")
    s.set_arg(old, "tags", '["b"]')
    assert 'x.add(Entity("b", Spin(2), tags=["b"]))' in s.text
    s.remove_piece(s.find("add", "x")[1])
    with pytest.raises(Stale):
        s.set_arg(old, "tags", '["c"]')
    with pytest.raises(ValueError):
        s.set_arg(s.first("game").call, "size", "(1, ")
    assert s.text.endswith('x.add(Entity("a", Spin(1)))\n')


def test_name_value_is_found_where_python_3_8_gives_no_position():
    import types
    s = Source(text='game = Game("A", size = (1, 2), seed=3)\n')
    size = s.first("game").call.get("size")
    assert s.keyword_start(types.SimpleNamespace(arg="size"), size.start) == s.text.index("size")
    assert s.first("game").call.item("size").start == s.text.index("size")


def test_a_long_dictionary_or_list_is_broken_after_its_commas():
    s = Source(text='from apkpy_lib.game import *\n\n\n@prefab\ndef hero():\n'
                    '    return Entity("hero",\n                  Animator({"idle": {"frames": [0]}}))\n')
    animator = s.first("prefab", "hero").entity.get(1)
    long = ('{"idle": {"frames": [0, 1], "fps": 2}, "run": {"frames": [2, 3, 4, 5], "fps": 12}, '
            '"jump": {"frames": [6]}, "fall": {"frames": [7]}}')
    s.set_arg(animator, 0, long)
    assert all(len(line) <= 120 for line in s.text.splitlines()), s.text
    assert ('                  Animator({"idle": {"frames": [0, 1], "fps": 2},\n'
            '                            "run": {"frames": [2, 3, 4, 5], "fps": 12},\n') in s.text
    assert s.first("prefab", "hero").entity.get(1).get(0).value["fall"] == {"frames": [7]}
    s.set_arg(s.first("prefab", "hero").entity.get(1), 0, '{"idle": {"frames": [0]}}')
    assert 'Animator({"idle": {"frames": [0]}}))' in s.text, "short again: one line"
