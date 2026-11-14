"""A game in many files of game/, @dataclass classes and module state.

- imports between files of game/ (from game.x import y, import game.x as x), read and
  translated, never run; cycles and missing files are errors that say where;
- the semantics corpus for @dataclass, dicts and None checks: CPython (the oracle,
  the very same module imported) and the translated Java give the same text;
- module state is reset for each game and is part of the state hash.
"""
import importlib
import json
import os
import subprocess
import sys
import textwrap

import pytest

from apkpy_lib.game import engine, templates
from apkpy_lib.game._host import toolchain
from apkpy_lib.game.errors import GameError

MONSTER = '''
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Monster:
    """A monster of the team."""
    species: str
    level: int
    hp: int = 10
    moves: list[str] = field(default_factory=list)

    def is_fainted(self) -> bool:
        return self.hp <= 0

    def hurt(self, amount: int) -> None:
        self.hp = max(0, self.hp - amount)


def strongest(team: list[Monster]) -> Optional[Monster]:
    best: Optional[Monster] = None
    for m in team:
        if best is None or m.level > best.level:
            best = m
    return best
'''

STORE = '''
from dataclasses import dataclass, field
from game.data.monster import Monster

LIMIT = 4


@dataclass
class Store:
    team: list[Monster] = field(default_factory=list)
    flags: dict[str, int] = field(default_factory=dict)
    turns: int = 0


STATE = Store()
'''

DAMAGE = '''
import random
from game.data.monster import Monster

BASE = 3


def damage(attacker: Monster, roll: bool) -> int:
    extra = random.randint(0, 2) if roll else 0
    return BASE + attacker.level // 2 + extra
'''

COUNTER = '''
from apkpy_lib.game import *
from dataclasses import replace
from game.data.monster import Monster, strongest
from game.state.store import STATE
import game.rules.damage as rules


class Counter(Script):
    goal: int = 3

    def on_start(self):
        STATE.team.append(Monster("ember", 5, moves=["spark"]))
        STATE.team.append(Monster(species="drip", level=7))

    def update(self, dt: float):
        STATE.turns += 1
        lead = strongest(STATE.team)
        if lead is None:
            return
        target = STATE.team[0]
        target.hurt(rules.damage(lead, True))
        STATE.flags["hits"] = STATE.flags.get("hits", 0) + 1
        if target.is_fainted() or STATE.turns >= self.goal * 10:
            healed = replace(target, hp=99)
            game.exit({"turns": STATE.turns, "hp": healed.hp, "same": healed == target, "lead": str(lead),
                       "fainted": target.is_fainted(), "hits": STATE.flags["hits"]})
'''

MAIN = '''
from apkpy_lib.game import *
from game.world.counter import Counter
from game.state.store import LIMIT

game = Game("m", size=(320, 240))
s = game.scene("main")
s.add(Entity("c", Shape(size=(8, 8)), Counter(goal=LIMIT)), at=(10, 10))
'''

FILES = {"main.py": MAIN, "data/monster.py": MONSTER, "state/store.py": STORE, "rules/damage.py": DAMAGE,
         "world/counter.py": COUNTER}


def make(tmp_path, files):
    (tmp_path / "apkpy.toml").write_text('[app]\nname = "t"\napplication_id = "com.test.modules"\n')
    templates.write_assets(str(tmp_path / "assets"))
    for name, body in files.items():
        path = tmp_path / "game" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(body), encoding="utf-8")
    from apkpy_lib.game.build import bundle_only
    from apkpy_lib.game.project import Project
    project = Project(str(tmp_path))
    return project, bundle_only(project)


def replay(project, steps=600):
    from apkpy_lib.game import desktop
    desktop._config.update({"bundle": None, "store": None, "project": project})
    r = subprocess.run(desktop.command("main", "{}", "--replay", "", "--steps", str(steps)),
                       capture_output=True, text=True)
    return r.stdout + r.stderr


def result(out):
    return json.loads(out.split("APKPYGAME_RESULT ", 1)[1].splitlines()[0])["result"]


def test_a_game_in_many_files(tmp_path):
    project, info = make(tmp_path, FILES)
    assert info["scripts"] == ["Counter"]
    out1, out2 = replay(project), replay(project)
    end = result(out1)
    assert end["lead"] == "Monster(species='drip', level=7, hp=10, moves=[])", out1
    assert end["fainted"] is True and end["hp"] == 99 and end["same"] is False, end
    assert end["turns"] == end["hits"] and 1 <= end["turns"] <= 2, end
    assert out1 == out2, "same build, same replay"
    java = (tmp_path / "build" / "apkpygame").rglob("*.java")
    names = {p.name for p in java}
    assert {"M_data__monster.java", "M_state__store.java", "Monster.java", "Store.java", "Counter.java"} <= names


def test_module_state_is_reset_for_each_game_and_hashed(tmp_path):
    """Two games in one JVM (as a journal played again after a new game): the second starts
    from STATE = Store() again, so both reach the same state hash."""
    project, info = make(tmp_path, dict(FILES, **{"world/counter.py": COUNTER.replace(
        "if target.is_fainted() or", "if False and")}))
    bundle = os.path.dirname(info["bundle"]) if os.path.isfile(info["bundle"]) else info["bundle"]
    src = tmp_path / "twice" / "apkpygame" / "game"
    src.mkdir(parents=True)
    (src / "Twice.java").write_text(textwrap.dedent('''
        package apkpygame.game;
        public final class Twice {
            public static void main(String[] a) {
                final java.io.File folder = new java.io.File(a[0]);
                apkpygame.core.Platform.AssetSource assets = new apkpygame.core.Platform.AssetSource() {
                    public byte[] read(String p) throws java.io.IOException {
                        return java.nio.file.Files.readAllBytes(new java.io.File(folder, p).toPath());
                    }
                    public boolean exists(String p) { return new java.io.File(folder, p).isFile(); }
                };
                for (int i = 0; i < 2; i++) {
                    apkpygame.testkit.Replay r = apkpygame.testkit.Replay.run(assets, "main", "{}", "", 40);
                    System.out.println(r.hash + " " + M_state__store.STATE.turns);
                }
            }
        }
    '''), encoding="utf-8")
    tools = toolchain()
    classpath = engine.desktop_jar() + os.pathsep + info["game_jar"]
    out = tmp_path / "twice" / "classes"
    out.mkdir()
    r = subprocess.run([tools.javac, "--release", "8", "-nowarn", "-Xlint:-options", "-cp", classpath, "-d", str(out),
                        str(src / "Twice.java")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([tools.java, "-cp", classpath + os.pathsep + str(out), "apkpygame.game.Twice", bundle],
                       capture_output=True, text=True)
    lines = r.stdout.split()
    assert len(lines) == 4, r.stdout + r.stderr
    assert lines[0] == lines[2] and lines[1] == lines[3] == "40", r.stdout


# ── the corpus: the same module in CPython and in Java ───────────────────

CORPUS = '''
from __future__ import annotations       # CPython 3.8 runs this too, as the oracle: list[str] in a dataclass needs it there

from dataclasses import dataclass, field, replace
from typing import Optional


@dataclass
class Item:
    name: str
    count: int = 1
    tags: list[str] = field(default_factory=list)

    def total(self, price: int) -> int:
        return self.count * price


@dataclass
class Bag:
    items: dict[str, Item] = field(default_factory=dict)
    owner: Optional[Item] = None


def find(bag: Bag, name: str) -> Optional[Item]:
    return bag.items.get(name)


def bag_text(n: int) -> str:
    bag = Bag()
    for i in range(n):
        key = "k" + str(i % 3)
        found = find(bag, key)
        if found is None:
            bag.items[key] = Item(key, tags=["new"])
        else:
            found.count += i
    out = ""
    for k in bag.items:
        it = bag.items[k]
        out = out + k + "=" + str(it.count) + ";"
    return out + str(len(bag.items))


def equality(a: int) -> str:
    x = Item("a", a)
    y = Item("a", a)
    z = replace(x, count=a + 1)
    return str(x == y) + str(x != z) + str(z.count) + str(x.count)


def printed(a: int) -> str:
    x = Item("o'k", a, ["t"])
    return str(x) + " " + str(Bag())


def shared(a: int) -> str:
    x = Item("s", a)
    y = replace(x)
    y.tags.append("both")
    return str(len(x.tags)) + str(y == x) + str(y is x)


def narrowing(n: int) -> str:
    best: Optional[Item] = None
    for i in range(n):
        it = Item("i" + str(i), (i * 7) % 5)
        if best is None or it.count > best.count:
            best = it
    if best is None:
        return "none"
    return best.name + ":" + str(best.total(3))


def dicts(n: int) -> str:
    d: dict[str, int] = {}
    for i in range(n):
        d["z" + str(i)] = i * i
    gone = d.pop("z1")
    return str(d) + str(gone) + str(d.get("q", -1)) + str(d.get("z2")) + str(d.get("q")) + str(len(d.values()))
'''

CASES = [("bag_text", [(7,), (0,)]), ("equality", [(3,)]), ("printed", [(2,)]), ("shared", [(1,)]),
         ("narrowing", [(6,), (0,)]), ("dicts", [(4,)])]


def test_dataclass_semantics_match_cpython(tmp_path):
    project, info = make(tmp_path, {"main.py": '''
        from apkpy_lib.game import *
        from game.corpus import bag_text

        game = Game("c", size=(100, 100))
        game.scene("main")
        ''', "corpus.py": CORPUS})
    sys.path.insert(0, str(tmp_path))
    try:
        for m in [m for m in sys.modules if m == "game" or m.startswith("game.")]:
            del sys.modules[m]
        corpus = importlib.import_module("game.corpus")           # CPython: the oracle (tests only)
        expected = [str(getattr(corpus, name)(*args)) for name, calls in CASES for args in calls]
    finally:
        sys.path.remove(str(tmp_path))
        for m in [m for m in sys.modules if m == "game" or m.startswith("game.")]:
            del sys.modules[m]
    calls = ["        System.out.println(M_corpus.%s(%s));" % (name, ", ".join(map(str, args)))
             for name, cs in CASES for args in cs]
    src = tmp_path / "main_src" / "apkpygame" / "game"
    src.mkdir(parents=True)
    (src / "CorpusMain.java").write_text("package apkpygame.game;\npublic final class CorpusMain {\n"
                                         "    public static void main(String[] a) {\n" + "\n".join(calls)
                                         + "\n    }\n}\n", encoding="utf-8")
    tools = toolchain()
    classpath = engine.desktop_jar() + os.pathsep + info["game_jar"]
    out = tmp_path / "main_classes"
    out.mkdir()
    r = subprocess.run([tools.javac, "--release", "8", "-nowarn", "-Xlint:-options", "-cp", classpath, "-d", str(out),
                        str(src / "CorpusMain.java")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([tools.java, "-cp", classpath + os.pathsep + str(out), "apkpygame.game.CorpusMain"],
                       capture_output=True, text=True)
    got = r.stdout.splitlines()
    labels = ["%s%r" % (name, args) for name, cs in CASES for args in cs]
    assert len(got) == len(expected), r.stderr
    bad = ["%s: CPython %s, Java %s" % m for m in zip(labels, expected, got) if m[1] != m[2]]
    assert not bad, "\n".join(bad)


# ── errors ───────────────────────────────────────────────────────────────

MINIMAL = '''
from apkpy_lib.game import *
from game.a import thing

game = Game("e", size=(100, 100))
game.scene("main")
'''


@pytest.mark.parametrize("files, code, where, words", [
    ({"a.py": "from game.b import other\ndef thing() -> int:\n    return 1\n", "b.py": "from game.a import thing\n"
      "def other() -> int:\n    return 2\n"}, "G1219", "game/b.py:1", "cycle: game/a.py -> game/b.py -> game/a.py"),
    ({}, "G1218", "game/main.py:3", "game/a.py"),
    ({"a.py": "thing = 1\nfor i in range(3):\n    pass\n"}, "G1220", "game/a.py:2", "'for'"),
    ({"a.py": "from dataclasses import dataclass\n@dataclass\nclass thing:\n    xs: list[int] = []\n"},
     "G2006", "game/a.py:4", "default_factory=list"),
    ({"a.py": "from dataclasses import dataclass\n@dataclass\nclass thing:\n    a: int = 1\n    b: int\n"},
     "G2006", "game/a.py:5", "come before a"),
    ({"a.py": "from game.c import Dup as thing\n", "c.py": "from apkpy_lib.game import *\nclass Dup(Script):\n    pass\n"
      "from game.d import Dup2\n", "d.py": "from apkpy_lib.game import *\nclass Dup(Script):\n    pass\nDup2 = 1\n"},
     "G2012", "game/d.py:2", "taken (by game/c.py)"),
    ({"a.py": "thing: list[int] = []\ndef f() -> None:\n    thing = [1]\n"}, "G2003", "game/a.py:3", "module state"),
    ({"a.py": "from .b import x\n"}, "G1207", "game/a.py:1", "from game.<path>"),
])
def test_module_errors(tmp_path, files, code, where, words):
    with pytest.raises(GameError) as e:
        make(tmp_path, dict({"main.py": MINIMAL}, **files))
    text = str(e.value)
    assert e.value.code == code and where in text and words in text, text


def test_an_error_in_a_module_names_its_file_and_line(tmp_path):
    files = dict(FILES)
    files["world/counter.py"] = COUNTER.replace("        STATE.turns += 1", "        STATE.turns += 1\n"
                                                "        print(STATE.team[5])")
    project, _ = make(tmp_path, files)
    out = replay(project, steps=30)
    line = next(i for i, l in enumerate(textwrap.dedent(files["world/counter.py"]).splitlines(), 1) if "team[5]" in l)
    assert "G3100" in out and "game/world/counter.py:%d" % line in out and "IndexError" in out, out


def test_ten_files_in_three_folders(tmp_path):
    files = {"main.py": '''
        from apkpy_lib.game import *
        from game.c.m9 import Last

        game = Game("ten", size=(100, 100))
        s = game.scene("main")
        s.add(Entity("e", Last()))
        '''}
    for i in range(10):
        folder = "abc"[i // 4]
        body = "from apkpy_lib.game import *\n"
        if i:
            body += "from game.%s.m%d import f%d\n" % ("abc"[(i - 1) // 4], i - 1, i - 1)
            body += "def f%d(x: int) -> int:\n    return f%d(x) * 2 + %d\n" % (i, i - 1, i)
        else:
            body += "def f0(x: int) -> int:\n    return x + 1\n"
        if i == 9:
            body += ("class Last(Script):\n    def update(self, dt: float):\n"
                     "        game.exit({\"v\": f9(1)})\n")
        files["%s/m%d.py" % (folder, i)] = body
    project, info = make(tmp_path, files)
    expected = 2
    for i in range(1, 10):
        expected = expected * 2 + i
    assert result(replay(project, steps=5)) == {"v": expected}


def test_the_previewer_reload_sees_game_subfolders(tmp_path):
    """ApkPy's reload (python writehere.py) looks at every .py under game/, however deep: a save there reloads."""
    from apkpy_lib import reload
    (tmp_path / "game" / "battle" / "deep").mkdir(parents=True)
    (tmp_path / "game" / "battle" / "deep" / "x.py").write_text("X = 1\n")
    (tmp_path / "writehere.py").write_text("")
    seen = sorted(os.path.relpath(p, str(tmp_path)).replace(os.sep, "/") for p in reload.snapshot(str(tmp_path)))
    assert "game/battle/deep/x.py" in seen and "writehere.py" in seen, seen
