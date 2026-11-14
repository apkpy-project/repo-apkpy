"""Lists, tabs, toggles, sliders and the keyboard, played by replays (drags included)."""
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_ui import make, play, shot      # noqa: E402

LIST = '''
from apkpy_lib.game import *

game = Game("t", size=(200, 300), background="#000000",
            vars={"filled": 0, "last": -1, "rows": 0, "tapped": -1, "buttons": 0, "scroll": 0})


class Items(Script):
    def on_row(self, row: Entity, index: int):
        game.add("filled", 1)
        game.set("last", index)
        row.child("name").text.text = "Item " + str(index)

    def update(self, dt: float):
        game.set("rows", scene.count("row"))
        game.set("scroll", self.list.scroll)
        if self.list.tapped >= 0:
            game.set("tapped", self.list.tapped)


@prefab
def row():
    return Entity("row", Shape(size=(180, 28), color="#ff0000"), tags=["row"], children=[
        Entity("name", Text("", size=12)),
        Entity("use", Button("x", var_add("buttons", 1), size=(30, 20)), at=(70, 0)),
    ])


s = game.scene("main")
s.add(Entity("list", ScrollList(row(), count=500, size=(180, 200), item_size=(180, 30), gap=2), Items(), ui=True), at=(10, 50))
'''


def test_only_the_rows_that_fit_exist(tmp_path):
    project, _ = make(tmp_path, LIST)
    v, _ = play(project, steps=5)
    assert v["rows"] == 8, "200 / 32, plus one"
    assert v["filled"] == 8
    v, out = play(project, "5:drag:100:240:100:60:30", steps=60)
    assert v["rows"] == 8 and v["filled"] > 8, "the same rows, filled again"
    assert play(project, "5:drag:100:240:100:60:30", steps=60)[1] == out, "a drag replays the same"


def test_dragging_and_inertia(tmp_path):
    project, _ = make(tmp_path, LIST)
    at_release, _ = play(project, "5:drag:100:240:100:60:30", steps=37)
    assert 170 <= at_release["scroll"] <= 200, at_release
    later, _ = play(project, "5:drag:100:240:100:60:30", steps=100)
    assert later["scroll"] > at_release["scroll"] + 20, "it keeps going after the finger leaves"
    end, _ = play(project, "5:drag:100:240:100:60:30", steps=400)
    still, _ = play(project, "5:drag:100:240:100:60:30", steps=500)
    assert end["scroll"] == still["scroll"], "and it stops"
    up, _ = play(project, "5:drag:100:60:100:250:10", steps=60)
    assert up["scroll"] == 0, "it does not go above the first row"


def test_tapping_rows_and_their_buttons(tmp_path):
    project, _ = make(tmp_path, LIST)
    v, _ = play(project, "5:tap:30:115", steps=20)      # the third row: 50 + 2 * 32 = 114
    assert v["tapped"] == 2 and v["buttons"] == 0, v
    v, _ = play(project, "5:tap:170:66", steps=20)      # the first row's button
    assert v["buttons"] == 1 and v["tapped"] == -1, "the button takes it"
    v, _ = play(project, "5:drag:170:162:170:80:20", steps=40)
    assert v["buttons"] == 0 and v["scroll"] > 50, "a drag starting on a button scrolls, and is not a click"
    v, _ = play(project, "5:tap:170:255", steps=20)     # below the box: a row is there, hidden
    assert v["buttons"] == 0 and v["tapped"] == -1, "what is outside the box cannot be tapped"


def test_rows_are_cut_at_the_box(tmp_path):
    project, _ = make(tmp_path, LIST)
    im = shot(project, tmp_path, 200, 300)
    assert im.getpixel((20, 60)) == (255, 0, 0)
    assert im.getpixel((20, 249)) == (255, 0, 0), "inside the box"
    assert im.getpixel((20, 251)) == (0, 0, 0), "the row goes on, but it is not drawn"


GRID = '''
from apkpy_lib.game import *

game = Game("t", size=(200, 300), vars={"tapped": -1, "rows": 0, "left": 0})


class Cells(Script):
    def on_start(self):
        self.list.count = 10

    def update(self, dt: float):
        game.set("rows", scene.count("cell"))
        if self.list.tapped >= 0:
            game.set("tapped", self.list.tapped)
        if game.steps == 30:
            self.list.count = 3
        if game.steps == 40:
            game.set("left", len(scene.with_tag("cell")))

    def on_row(self, row: Entity, index: int):
        pass


s = game.scene("main")
s.add(Entity("g", ScrollList(Entity("cell", Shape(size=(40, 40)), tags=["cell"]), size=(150, 100), item_size=(50, 50), columns=3),
             Cells(), ui=True), at=(0, 0))
'''


def test_a_grid(tmp_path):
    project, _ = make(tmp_path, GRID)
    assert play(project, "5:tap:125:75", steps=20)[0]["tapped"] == 5, "the second line's third cell"
    assert play(project, steps=5)[0]["rows"] == 9, "3 lines of 3"
    assert play(project, "35:tap:75:75", steps=45)[0]["tapped"] == -1, "only 3 now: there is no row there"


WIDGETS = '''
from apkpy_lib.game import *

game = Game("t", size=(300, 300), vars={"tab": 0, "tabs": 0, "on": 0, "toggles": 0, "level": 0, "slides": 0, "typed": 0})


class Watch(Script):
    def update(self, dt: float):
        t = self.entity.child("tabs_here").tabs
        if t.changed:
            game.add("tabs", 1)
        game.set("tab", t.selected)
        o = self.entity.child("sound").toggle
        if o.changed:
            game.add("toggles", 1)
        game.set("on", 1 if o.value else 0)
        s = self.entity.child("volume").slider
        if s.changed:
            game.add("slides", 1)
        game.set("level", s.value)
        k = self.entity.child("keys").keyboard
        if k.done:
            game.exit({"name": k.text})


s = game.scene("main")
s.add(Entity("all", Watch(), ui=True, children=[
    Entity("tabs_here", Tabs(["A", "B", "C"], size=(150, 30)), ui=True, at=(0, 0)),
    Entity("sound", Toggle("Sound", size=(100, 20)), ui=True, at=(0, 50)),
    Entity("volume", Slider(0, max=100, step=10, size=(100, 20)), ui=True, at=(0, 80)),
    Entity("keys", Keyboard(size=(300, 120), max_length=4), ui=True, at=(0, 120)),
]))
'''


def test_tabs_toggle_slider(tmp_path):
    project, _ = make(tmp_path, WIDGETS)
    v, _ = play(project, "5:tap:75:15,20:tap:75:15", steps=40)
    assert v["tab"] == 1 and v["tabs"] == 1, "selecting the selected one changes nothing"
    v, _ = play(project, "5:tap:50:50", steps=20)
    assert v["on"] == 1 and v["toggles"] == 1
    v, _ = play(project, "5:tap:50:50,15:tap:50:50", steps=30)
    assert v["on"] == 0 and v["toggles"] == 2
    v, _ = play(project, "5:drag:5:80:60:80:10", steps=30)
    assert v["level"] == 60 and 2 <= v["slides"] <= 10, v
    v, _ = play(project, "5:drag:5:80:300:80:10", steps=30)
    assert v["level"] == 100, "it stops at the end"


def test_keyboard(tmp_path):
    project, _ = make(tmp_path, WIDGETS)
    from test_ui import run
    import json
    # keys are 30 wide, rows 30 high from y=120: Q=(15,135), W=(45,135), A=(30,165); last row y=225
    taps = ["5:tap:15:135", "15:tap:45:135", "25:tap:15:135", "35:tap:45:135", "45:tap:15:135",   # Q w q w (full), q ignored
            "55:tap:220:225", "65:tap:45:135", "75:tap:275:225"]                                  # delete, w, OK
    out = run(project, "--replay", ",".join(taps), "--steps", "100")
    assert json.loads(out.split("APKPYGAME_RESULT ", 1)[1].splitlines()[0])["result"] == {"name": "Qwqw"}, out


@pytest.mark.parametrize("field", ["count=1", "columns=2"])
def test_a_list_needs_a_row(tmp_path, field):
    from apkpy_lib.game.errors import GameError
    with pytest.raises(GameError) as e:
        make(tmp_path, '''
            from apkpy_lib.game import *

            game = Game("t")
            s = game.scene("main")
            s.add(Entity("l", ScrollList(%s), ui=True))
            ''' % field)
    assert "row" in str(e.value)
