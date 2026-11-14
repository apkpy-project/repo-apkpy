"""Scripts in Python, translated to Java.

- the semantics corpus: functions run by CPython (the oracle, tests only) and by the
  translated Java on the JVM must give the same text for the same arguments;
- a game with scripts plays deterministically (replay) and its errors point at Python lines;
- the translator refuses what it does not translate, with a G2xxx and the line.
"""
import ast
import json
import os
import subprocess
import textwrap

import pytest

from apkpy_lib.game import engine, templates
from apkpy_lib.game._host import toolchain
from apkpy_lib.game.compiler.scripts import Function, Translator
from apkpy_lib.game.errors import GameError

CORPUS = '''
def div(a: float, b: float) -> float:
    return a / b

def idiv(a: int, b: int) -> int:
    return a // b

def fdiv(a: float, b: float) -> float:
    return a // b

def imod(a: int, b: int) -> int:
    return a % b

def fmod(a: float, b: float) -> float:
    return a % b

def power(a: int, b: int) -> int:
    return a ** b

def fpower(a: float, b: float) -> float:
    return a ** b

def rounding(x: float) -> int:
    return round(x)

def rounding2(x: float) -> float:
    return round(x, 2)

def to_int(x: float) -> int:
    return int(x)

def text(x: float) -> str:
    return str(x)

def itext(x: int) -> str:
    return str(x)

def fmt(x: float) -> str:
    return f"[{x:.2f}|{x:8.3f}|{int(x):04d}]"

def mixed(n: int) -> float:
    total = 0
    for i in range(n):
        total += i * 2.5
    return total

def countdown(n: int) -> str:
    out = ""
    for i in range(n, 0, -2):
        out = out + str(i) + ","
    return out

def lists(n: int) -> str:
    xs: list[int] = []
    for i in range(n):
        xs.append(i * i)
    last = xs[-1]
    xs.pop()
    return str(xs) + " " + str(last) + " " + str(len(xs))

def strings(s: str) -> str:
    return s.upper() + "|" + s * 2 + "|" + str(s.startswith("ab")) + "|" + str("b" in s)

def chained(x: int) -> bool:
    return 0 < x <= 10 and x != 5

def ternary(x: float) -> float:
    return x if x > 0 else -x * 2

def minmax(a: int, b: float) -> float:
    return max(a, b) - min(a, b, 3) + abs(-a)

def loop_while(n: int) -> int:
    steps = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        steps += 1
    return steps

def trig(x: float) -> float:
    return round(math.sin(x) * 1000 + math.atan2(x, 2) * 100 + math.sqrt(abs(x)), 6)

def swap(a: int, b: int) -> str:
    a, b = b, a
    return str(a) + "-" + str(b)

def nested(n: int) -> int:
    total = 0
    for i in range(n):
        for j in range(i):
            if j == 3:
                continue
            if i > 7:
                break
            total += j
    return total
'''

CASES = [
    ("div", [(7.0, 2.0), (-7.0, 2.0), (1.0, 3.0)]),
    ("idiv", [(7, 2), (-7, 2), (7, -2), (-7, -2)]),
    ("fdiv", [(7.5, 2.0), (-7.5, 2.0)]),
    ("imod", [(7, 3), (-7, 3), (7, -3), (-7, -3)]),
    ("fmod", [(7.5, 2.0), (-7.5, 2.0), (7.5, -2.0)]),
    ("power", [(2, 10), (-3, 3)]),
    ("fpower", [(2.0, 0.5), (10.0, -2.0)]),
    ("rounding", [(0.5,), (1.5,), (2.5,), (-0.5,), (-1.5,), (2.675,)]),
    ("rounding2", [(2.675,), (1.005,), (-3.14159,)]),
    ("to_int", [(3.9,), (-3.9,)]),
    ("text", [(1.0,), (0.1,), (1e16,), (1.5e-5,), (123456.789,), (-0.0,), (2.5,), (1e22,)]),
    ("itext", [(-42,)]),
    ("fmt", [(3.14159,), (-2.5,)]),
    ("mixed", [(3,), (0,)]),
    ("countdown", [(9,)]),
    ("lists", [(5,)]),
    ("strings", [("abc",)]),
    ("chained", [(5,), (7,), (11,), (0,)]),
    ("ternary", [(2.5,), (-1.5,)]),
    ("minmax", [(5, 2.5), (1, 9.0)]),
    ("loop_while", [(27,)]),
    ("trig", [(0.7,), (-2.0,)]),
    ("swap", [(1, 2)]),
    ("nested", [(10,)]),
]


def jlit(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v) if v == v else "Double.NaN"
    return json.dumps(v)


def test_semantics_match_cpython(tmp_path):
    tree = ast.parse(CORPUS)
    functions = [Function(n) for n in tree.body if isinstance(n, ast.FunctionDef)]
    files = Translator("corpus.py", [], functions, {}).translate()
    lines = []
    expected = []
    namespace = {}
    import math as _math
    namespace["math"] = _math
    exec(compile(CORPUS, "corpus.py", "exec"), namespace)          # CPython: the oracle (tests only)
    returns = {n.name: getattr(n.returns, "id", None) for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name, calls in CASES:
        for args in calls:
            value = namespace[name](*args)
            if returns[name] == "float" and isinstance(value, int):
                value = float(value)       # declared -> float: Python may hand back an int (mixed(0)); Java keeps the type
            expected.append(str(value))
            lines.append('        System.out.println(Py.str(GameModule.%s(%s)));' % (name, ", ".join(map(jlit, args))))
    files["CorpusMain.java"] = ("package apkpygame.game;\nimport apkpygame.core.*;\n"
                                "public final class CorpusMain {\n    public static void main(String[] a) {\n"
                                + "\n".join(lines) + "\n    }\n}\n")
    src = tmp_path / "apkpygame" / "game"
    src.mkdir(parents=True)
    for n, text in files.items():
        (src / n).write_text(text, encoding="utf-8")
    tools = toolchain()
    out = tmp_path / "classes"
    out.mkdir()
    r = subprocess.run([tools.javac, "--release", "8", "-Xlint:-options", "-nowarn", "-encoding", "UTF-8", "-cp",
                        engine.desktop_jar(), "-d", str(out)] + [str(p) for p in src.iterdir()],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([tools.java, "-cp", engine.desktop_jar() + os.pathsep + str(out), "apkpygame.game.CorpusMain"],
                       capture_output=True, text=True)
    got = r.stdout.splitlines()
    labels = ["%s%r" % (name, args) for name, calls in CASES for args in calls]
    mismatches = [(l, e, g) for l, e, g in zip(labels, expected, got) if e != g]
    assert len(got) == len(expected), r.stderr
    assert not mismatches, "\n".join("%s: CPython %s, Java %s" % m for m in mismatches)


# ── a game with scripts ──────────────────────────────────────────────────

GAME = '''
from apkpy_lib.game import *
import math

game = Game("t", size=(320, 240), vars={"score": 0})
pop = assets.sound("assets/pop.wav")
LIMIT = 3


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


@prefab
def dot():
    return Entity("dot", Shape(size=(4, 4)), Collider(size=(4, 4), trigger=True), tags=["dot"])


class Mover2(Script):
    speed: float = 50.0
    hits: int = 0
    trail: Prefab = dot()
    boom: Sound = pop
    seen: list[str] = []

    def on_start(self):
        self.seen.append("start")

    def update(self, dt: float):
        self.x = clamp(self.x + self.speed * dt, 0.0, 300.0)
        if game.steps % 30 == 0:
            scene.spawn(self.trail, self.x, self.y + 10)
            game.add("score", 1)
        if game.get("score") >= LIMIT and self.hits == 0:
            self.hits = 1
            audio.play(self.boom)
            game.exit({"score": game.get("score"), "x": round(self.x, 1), "seen": len(self.seen)})


class Broken(Script):
    items: list[int] = []

    def update(self, dt: float):
        if game.steps > 5:
            print(self.items[2])
'''


def make(tmp_path, body, writehere=None):
    (tmp_path / "apkpy.toml").write_text('[app]\nname = "t"\napplication_id = "com.test.scripts"\n')
    (tmp_path / "game").mkdir()
    templates.write_assets(str(tmp_path / "assets"))
    (tmp_path / "game" / "main.py").write_text(textwrap.dedent(body), encoding="utf-8")
    from apkpy_lib.game.build import bundle_only
    from apkpy_lib.game.project import Project
    project = Project(str(tmp_path))
    return project, bundle_only(project)


def replay(project, scene="main", steps=600):
    from apkpy_lib.game import desktop
    desktop._config.update({"bundle": None, "store": None, "project": project})
    cmd = desktop.command(scene, "{}", "--replay", "", "--steps", str(steps))
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout, r.stderr


def test_a_game_with_scripts_runs_and_is_deterministic(tmp_path):
    project, info = make(tmp_path, GAME + '''
s = game.scene("main")
s.add(Entity("m", Shape(size=(8, 8)), Mover2(speed=120)), at=(10, 100))
''')
    assert info["scripts"] == ["Mover2", "Broken"] and info["game_jar"]
    scene = json.loads((tmp_path / "build" / "apkpygame" / "bundle" / "scenes" / "main.json").read_text())
    comp = scene["entities"][0]["components"][1]
    assert comp["type"] == "Mover2" and comp["speed"] == 120.0 and comp["boom"] == "assets/pop.wav"
    assert comp["trail"]["name"] == "dot"
    out1, err = replay(project)
    out2, _ = replay(project)
    assert '"action":"exit"' in out1, out1 + err
    end = json.loads(out1.split("APKPYGAME_RESULT ", 1)[1].splitlines()[0])
    assert end["result"] == {"score": 3, "x": 10 + round(120 * 61 / 60, 1), "seen": 1}, end
    assert out1 == out2, "same build, same replay"


def test_a_script_error_names_the_python_line(tmp_path):
    project, _ = make(tmp_path, GAME + '''
s = game.scene("main")
s.add(Entity("b", Broken()))
''')
    out, err = replay(project, steps=60)
    assert "G3100" in out + err
    line = next(i for i, l in enumerate(GAME.splitlines(), 1) if "print(self.items[2])" in l)
    assert "main.py:%d" % line in out + err and "IndexError" in out + err, out + err


def test_scale_grows_both_sides(tmp_path):
    """self.scale = 2.0 (and e.scale, and +=) is the size on both sides, as scale= is in a declaration."""
    project, _ = make(tmp_path, '''
from apkpy_lib.game import *


class Grow(Script):
    def update(self, dt: float):
        self.scale = 2.0
        self.scale += 0.5
        other = scene.find("other")
        if other is not None:
            other.scale = 3.0
            game.exit({"self": self.scale, "other": other.scale})


game = Game("t", size=(100, 100))
s = game.scene("main")
s.add(Entity("g", Shape(size=(8, 8)), Grow()))
s.add(Entity("other", Shape(size=(8, 8))))
''')
    src = os.path.join(project.build_dir, "java", "apkpygame", "game")
    java = "".join(open(os.path.join(src, f), encoding="utf-8").read() for f in os.listdir(src))
    assert java.count("transform.scaleY = ") == 3, java
    out, err = replay(project, steps=3)
    end = json.loads(out.split("APKPYGAME_RESULT ", 1)[1].splitlines()[0])
    assert end["result"] == {"self": 2.5, "other": 3.0}, end


@pytest.mark.parametrize("method, code", [
    ("def update(self, dt: float):\n        if self.speed:\n            pass", "G2008"),
    ("def update(self, dt: float):\n        x = [i for i in range(3)]", "G2002"),
    ("def update(self, dt: float):\n        self.nope = 1.0", "G2007"),
    ("def update(self, dt: float):\n        y = 'a' + 1", "G2003"),
    ("def update(self, dt: float):\n        with open('x') as f:\n            pass", "G2001"),
    ("def helper(self, a):\n        return a", "G2006"),
    ("def update(self, dt: float):\n        z = undefined_name", "G2004"),
    ("def update(self, dt: float):\n        e = scene.find('x')\n        e.x = 1.0", "G2010"),
    ("def size(self) -> float:\n        return 'big'", "G2003"),
])
def test_translator_refusals(tmp_path, method, code):
    body = '''
from apkpy_lib.game import *
game = Game("t")

class S(Script):
    speed: float = 1.0

    %s

s = game.scene("main")
s.add(Entity("e", S()))
''' % method
    with pytest.raises(GameError) as e:
        make(tmp_path, body)
    assert e.value.code == code, str(e.value)
    assert e.value.line and e.value.line >= 8, str(e.value)
