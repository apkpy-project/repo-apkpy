"""Finds a replay that wins each genre template (dev machine only).

    python tools/game/genre_bots.py [genre ...]
    python tools/game/genre_bots.py --pictures

Makes each genre's game in a temporary folder (as `apkpy start NAME --game GENRE` does), builds it, and plays it with
the engine with no window (--replay), looking for the keys and taps that win. Where the things in the game are, step
by step, comes from the replay's --trace. The engine is deterministic, so a replay found here wins the same way on
every run and on the phone. The replays are saved in tests/game/genre_replays.json, which tests/game/test_starters.py
plays.

--pictures takes the picture of each kind of game that the Studio's New game shows (apkpy_lib/game/studio/pictures):
the engine's own picture of a moment of the game, cut to 4:3.
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # ApkPy's repository
sys.path.insert(0, ROOT)
from apkpy_lib.game import engine  # noqa: E402
from apkpy_lib.game._host import toolchain  # noqa: E402
from apkpy_lib.game.build import bundle_only  # noqa: E402
from apkpy_lib.game.cli import GENRES  # noqa: E402
from apkpy_lib.game.project import Project  # noqa: E402
from apkpy_lib.game.templates import copy_project_template  # noqa: E402

REPLAYS = os.path.join(ROOT, "tests", "game", "genre_replays.json")


class Run:
    """What one replay did: the end, the variables when they changed, and where the traced things were."""

    def __init__(self, out):
        self.out = out
        self.events = []                    # (step, vars)
        self.trace = {}                     # step -> (scene, [(name, x, y)])
        self.end = None
        for line in out.splitlines():
            if line.startswith("APKPYGAME_EVENT "):
                m = re.match(r"APKPYGAME_EVENT step=(\d+) vars=(.*)", line)
                self.events.append((int(m.group(1)), json.loads(m.group(2))))
            elif line.startswith("APKPYGAME_TRACE "):
                parts = line.split()
                things = []
                for item in parts[3:]:
                    name, x, y = item.rsplit(":", 2)
                    things.append((name, float(x), float(y)))
                self.trace[int(parts[1])] = (parts[2], things)
            elif line.startswith("APKPYGAME_RESULT "):
                self.end = json.loads(line[len("APKPYGAME_RESULT "):])
            elif line.startswith("APKPYGAME_REPLAY "):
                self.steps = int(re.search(r"steps=(\d+)", line).group(1))
        summary = re.search(r"APKPYGAME_SUMMARY (.*)", out)
        self.summary = summary.group(1) if summary else out[-2000:]

    @property
    def result(self):
        return ((self.end or {}).get("result") or {}).get("result")

    @property
    def won(self):
        return self.result == "win"

    def lost_at(self, var="lives"):
        """The first step a variable went down (a life lost), or None."""
        last = None
        for step, values in self.events:
            if var in values:
                if last is not None and values[var] < last:
                    return step
                last = values[var]
        return None

    def things(self, step, name=None):
        scene, found = self.trace.get(step, ("", []))
        return [t for t in found if name is None or t[0] == name]


def make(genre, base):
    folder = os.path.join(base, genre)
    if not os.path.isdir(folder):
        copy_project_template(folder, genre, "dev.apkpy.check." + genre, genre)
    bundle_only(Project(folder))
    return folder


def play(folder, script, steps, trace=None, scene="main"):
    build = os.path.join(folder, "build", "apkpygame")
    classpath = engine.desktop_jar()
    jar = os.path.join(build, "game.jar")
    if os.path.isfile(jar):
        classpath += os.pathsep + jar
    cmd = [toolchain().java, "-cp", classpath, "apkpygame.desktop.Main", "--bundle", os.path.join(build, "bundle"),
           "--scene", scene, "--replay", script or "0:nothing:up", "--steps", str(steps)]
    if trace:
        cmd += ["--trace", trace]
    return Run(subprocess.run(cmd, capture_output=True, text=True).stdout)


def tap(step, x, y):
    return "%d:tap:%g:%g" % (step, x, y)


def key(step, name, hold):
    return "%d:%s:down,%d:%s:up" % (step, name, step + hold, name)


def module(folder):
    with open(os.path.join(folder, "game", "main.py"), encoding="utf-8") as fh:
        return ast.parse(fh.read())


# ── puzzle: Lights Off ──────────────────────────────────────────────────

def lights_out(board, size):
    """The lights to press to turn a board off (a 0/1 string, rows one after the other), over GF(2)."""
    n = size * size
    rows = []
    for i in range(n):
        r, c = divmod(i, size)
        mask = 0
        for dr, dc in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            if 0 <= r + dr < size and 0 <= c + dc < size:
                mask |= 1 << ((r + dr) * size + c + dc)
        rows.append(mask | (int(board[i]) << n))
    pivots, rank = [], 0
    for col in range(n):
        found = next((i for i in range(rank, n) if rows[i] >> col & 1), None)
        if found is None:
            continue
        rows[rank], rows[found] = rows[found], rows[rank]
        for i in range(n):
            if i != rank and rows[i] >> col & 1:
                rows[i] ^= rows[rank]
        pivots.append(col)
        rank += 1
    if any(rows[i] >> n & 1 for i in range(rank, n)):
        raise SystemExit("this board cannot be turned off: %s" % board)
    return [col for i, col in enumerate(pivots) if rows[i] >> n & 1]


def board_settings(folder):
    tree = module(folder)
    names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                names[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    fields = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Board":
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and item.value is not None:
                    value = item.value
                    if isinstance(value, ast.Name) and value.id in names:
                        fields[item.target.id] = names[value.id]
                    else:
                        try:
                            fields[item.target.id] = ast.literal_eval(value)
                        except ValueError:
                            pass
    return fields


def puzzle(folder):
    f = board_settings(folder)
    size, cell, left, top = f["size"], f["cell"], f["left"], f["top"]
    n = size * size
    events, step = [], 10
    for level in range(f["count"]):
        for i in lights_out(f["levels"][level * n:(level + 1) * n], size):
            r, c = divmod(i, size)
            events.append(tap(step, left + c * cell + cell / 2, top + r * cell + cell / 2))
            step += 6
        step += 75                          # the board waits a second before the next one
    script = ",".join(events)
    return script, step + 30


# ── tap: Quick Pop ──────────────────────────────────────────────────────

def appearances(run, name):
    """(step, x, y) each time a thing with this name shows up where none was the step before."""
    out, before = [], []
    for step in sorted(run.trace):
        now = [(x, y) for n, x, y in run.things(step, name)]
        for x, y in now:
            if not any(abs(x - a) < 1 and abs(y - b) < 1 for a, b in before):
                out.append((step, x, y))
        before = now
    return out


def tap_game(folder):
    taps = []                               # (step, x, y)
    for _ in range(80):
        script = ",".join(tap(*t) for t in taps)
        run = play(folder, script, 4000, trace="star")
        missed = run.events[-1][1].get("missed") if run.events else None
        if run.won and missed == 0:
            return script, run.steps + 30
        plan = []
        for step, x, y in taps:             # a tap is good if a star was there the step before
            if not any(abs(x - a) < 2 and abs(y - b) < 2 for _, a, b in run.things(step - 1, "star")):
                break
            plan.append((step, x, y))
        for step, x, y in appearances(run, "star"):
            if any(abs(x - a) < 1 and abs(y - b) < 1 and step <= s <= step + 100 for s, a, b in plan):
                continue
            at = step + 3
            while any(abs(at - s) < 3 for s, _, _ in plan):
                at += 1
            plan.append((at, x, y))
        plan.sort()
        if plan == taps:
            if run.won:
                return script, run.steps + 30
            raise SystemExit("tap: stuck, missed %s" % missed)
        taps = plan
        print("  tap: %d taps, missed %s, ended %s" % (len(taps), missed, run.result))
    raise SystemExit("tap: no win")


# ── runner: Rooftop Run ─────────────────────────────────────────────────

def tracks(run, name):
    """Each thing with this name that moves left in a line: (first step, its x then, px per step, y)."""
    out, live = [], []                      # live: [index in out, last x, y]
    for step in sorted(run.trace):
        now = []
        for n, x, y in run.things(step, name):
            match = next((t for t in live if abs(t[2] - y) < 0.5 and 0 < t[1] - x < 8), None)
            if match is None:
                out.append([step, x, None, y])
                now.append([len(out) - 1, x, y])
                continue
            live.remove(match)
            if out[match[0]][2] is None:
                out[match[0]][2] = match[1] - x
            now.append([match[0], x, y])
        live = now
    return [t for t in out if t[2]]


def over(track, x, reach):
    """The steps a thing is within reach of x."""
    first, x0, v, _ = track
    return range(int(first + (x0 - x - reach) / v), int(first + (x0 - x + reach) / v) + 2)


def runner(folder):
    hold = 4                                # a tap: a hop, which goes under the birds
    air = play(folder, key(20, "jump", hold), 80, trace="player")
    arc = [147 - air.things(s, "player")[0][2] for s in range(20, 80)]      # how high, each step after the key
    flight = max(n for n, h in enumerate(arc) if h > 0) + 2
    jumps = []
    for _ in range(40):
        script = ",".join(key(j, "jump", hold) for j in jumps)
        run = play(folder, script, 6000, trace="crate")
        if run.won and run.lost_at() is None:
            return script, run.steps + 30
        plan = []
        for crate in tracks(run, "crate"):
            under = over(crate, 60, 13)     # the crate is under the runner: 16 px up all that time
            options = [j for j in range(under[0] - flight, under[0])
                       if not (plan and j < plan[-1] + flight + 2)
                       and all(0 <= s - j < len(arc) and arc[s - j] >= 16 for s in under)]
            if options:
                middle = (under[0] + under[-1]) / 2 - flight / 2
                plan.append(min(options, key=lambda j: abs(j - middle)))
        if plan == jumps:
            if run.won:
                return script, run.steps + 30
            raise SystemExit("runner: stuck, a life lost at %s" % run.lost_at())
        jumps = plan
        print("  runner: %d jumps, a life lost at %s, ended %s" % (len(jumps), run.lost_at(), run.result))
    raise SystemExit("runner: no win")


# ── bricks: Brickfall ───────────────────────────────────────────────────

def follow(xs, y, last):
    """Drags that keep the finger under a thing: one for each stretch where its x changes evenly."""
    out, s = [], min(xs) if xs else 0
    while s < last:
        if s not in xs or s + 1 not in xs:
            s += 1
            continue
        pace, e = xs[s + 1] - xs[s], s + 1
        while e < last and e + 1 in xs and abs(xs[e + 1] - xs[e] - pace) < 0.3 and e - s < 900:
            e += 1
        out.append("%d:drag:%g:%g:%g:%g:%d" % (s, xs[s], y, xs[e], y, e - s))
        s = e + 1
    return out


# Where on the paddle the ball lands, touch after touch (-1 its left end, 1 its right end): the ball leaves at another
# angle each time (the game's deflect), and so goes all over the wall.
SIDES = (0.5, -0.3, 0.15, -0.65, 0.35, -0.1, 0.65, -0.45, 0.25, -0.55, 0.05, 0.45, -0.2, 0.6, -0.4)


def under_the_ball(run, half=36):
    """For each step, where the paddle's middle should be: under the ball, to the side this touch asks for."""
    out, touch, before, rising = {}, 0, None, False
    for step in sorted(run.trace):
        scene, things = run.trace[step]
        if not things:
            continue
        x, y = things[0][1], things[0][2]
        if before is not None:
            if before[0] != scene or abs(y - before[2]) > 40:
                touch += 1                  # another level, or a ball lost and back
            elif y < before[2] and not rising and before[2] > 560:
                touch += 1                  # it was going down by the paddle and now goes up: a touch
            rising = y < before[2]
        before = (scene, x, y)
        out[step] = x - SIDES[touch % len(SIDES)] * half
    return out


def bricks(folder):
    script, steps = "", 900
    for n in range(600):
        run = play(folder, script, steps, trace="ball")
        lost = run.lost_at()
        if run.won and lost is None:
            return script, run.steps + 30
        if run.end and lost is None:
            raise SystemExit("bricks: ended %s" % run.result)
        good = lost if lost is not None else max(run.trace)
        plan = ",".join(follow(under_the_ball(run), 620, max(run.trace)))
        if plan == script:
            if lost is None:
                steps += 1800               # nothing went wrong yet: play on
            else:
                raise SystemExit("bricks: stuck, a life lost at %s" % lost)
        script, steps = plan, max(steps, good + 900)
        if n % 10 == 0:
            print("  bricks: good until %d, score %s" % (good, run.events[-1][1].get("score") if run.events else 0))
        if steps > 60000:
            raise SystemExit("bricks: too long (the ball may be going round and round)")
    raise SystemExit("bricks: no win")


# ── levels: the maps the world and the adventure walk ───────────────────

class Level:
    """A .tmj level as cells: which are solid, and the cell of each object."""

    def __init__(self, folder, name):
        with open(os.path.join(folder, "levels", name), encoding="utf-8") as fh:
            data = json.load(fh)
        self.cols, self.rows, self.tile = data["width"], data["height"], data["tilewidth"]
        self.solid, self.objects = set(), []
        for layer in data["layers"]:
            if layer["type"] == "tilelayer":
                if any(p["name"] == "solid" and p["value"] for p in layer.get("properties", [])):
                    self.solid |= {(i % self.cols, i // self.cols) for i, gid in enumerate(layer["data"]) if gid}
            elif layer["type"] == "objectgroup":
                for o in layer["objects"]:
                    cell = (int((o["x"] + o.get("width", 0) / 2) // self.tile),
                            int((o["y"] + o.get("height", 0) / 2) // self.tile))
                    self.objects.append((o.get("class") or o.get("type") or o.get("name"), cell))

    def cells(self, kind):
        return [cell for name, cell in self.objects if name.startswith(kind)]

    def path(self, start, goal, cost):
        """The cheapest way, cell by cell (not the start): cost(cell) is None for a cell nobody walks on."""
        import heapq
        best, prev, todo = {start: 0}, {start: None}, [(0, start)]
        while todo:
            d, cell = heapq.heappop(todo)
            if cell == goal:
                break
            if d > best[cell]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (cell[0] + dx, cell[1] + dy)
                if not (0 <= nxt[0] < self.cols and 0 <= nxt[1] < self.rows) or nxt in self.solid:
                    continue
                c = cost(nxt)
                if c is None or (nxt in best and best[nxt] <= d + c):
                    continue
                best[nxt], prev[nxt] = d + c, cell
                heapq.heappush(todo, (d + c, nxt))
        if goal not in prev:
            return None
        out, cell = [], goal
        while prev[cell] is not None:
            out.append(cell)
            cell = prev[cell]
        return out[::-1]


def runs(start, cells):
    """A walk as straight stretches: (dx, dy, how many cells)."""
    out, at = [], start
    for cell in cells:
        d = (cell[0] - at[0], cell[1] - at[1])
        if out and out[-1][:2] == d:
            out[-1] = (d[0], d[1], out[-1][2] + 1)
        else:
            out.append((d[0], d[1], 1))
        at = cell
    return out


KEYS = {(0, -1): "up", (0, 1): "down", (-1, 0): "left", (1, 0): "right"}


# ── world: Gem Valley ───────────────────────────────────────────────────

def world(folder):
    level = Level(folder, "valley.tmj")
    blocked = set(level.cells("tree")) | set(level.cells("elder"))
    for cx, cy in level.cells("house"):     # a house is on the cells around its own too
        blocked |= {(cx + dx, cy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    at, left, walk = level.cells("hero")[0], level.cells("lantern"), []
    start = at
    while left:
        ways = [(level.path(at, goal, lambda c: None if c in blocked else 1), goal) for goal in left]
        way, goal = min((w for w in ways if w[0] is not None), key=lambda w: len(w[0]))
        walk += way
        at = goal
        left.remove(goal)
    # GridController: a short press in a new direction only turns; held, it walks a cell every 15 steps
    events, step, facing = [], 10, (0, 1)
    for dx, dy, n in runs(start, walk):
        name = KEYS[(dx, dy)]
        if (dx, dy) != facing:
            events.append(key(step, name, 2))
            step += 6
            facing = (dx, dy)
        events.append(key(step, name, 15 * (n - 1) + 9))
        step += 15 * n + 12
    return ",".join(events), step + 60


# ── adventure: Keys of the Keep ─────────────────────────────────────────

def keep_walk(level):
    """The cells from the hero to the stairs: a key first for each door on the way."""
    slimes = {(sx + d, sy) for sx, sy in level.cells("slime") for d in range(-4, 5)}
    doors, keys = set(level.cells("door")), level.cells("key")
    at, have, walk = level.cells("hero")[0], 0, []
    stairs = level.cells("stairs")[0]

    def cost(shut):
        return lambda c: None if (c in doors and shut) else 60 if c in doors else 30 if c in slimes else 1

    for _ in range(10):
        way = level.path(at, stairs, cost(False))
        need = sum(1 for c in way if c in doors)
        if need <= have:
            return walk + way
        ways = [w for w in (level.path(at, k, cost(True)) for k in keys) if w is not None]
        way = min(ways, key=len)
        walk += way
        at = way[-1]
        keys.remove(at)
        have += 1
    raise SystemExit("adventure: no way to the stairs")


def adventure(folder):
    pace = 80 / 60.0                        # TopDownController(speed=80), px a step
    events, step = [], 10
    for scene, name in (("main", "level1.tmj"), ("level2", "level2.tmj")):
        level = Level(folder, name)
        at = level.cells("hero")[0]
        for dx, dy, n in runs(at, keep_walk(level)):
            at = (at[0] + dx * n, at[1] + dy * n)
            goal = (at[0] * level.tile + level.tile / 2, at[1] * level.tile + level.tile / 2)
            for _ in range(6):              # walk, look where the hero is, walk the rest (a door stops it a moment)
                run = play(folder, ",".join(events), step + 2, trace="hero")
                now, things = run.trace[max(run.trace)]
                if now != scene or not things or run.end:
                    break
                off = (goal[0] - things[0][1]) if dx else (goal[1] - things[0][2])
                if abs(off) <= 1:
                    break
                hold = max(1, int(round(abs(off) / pace)))
                events.append(key(step, KEYS[(1 if off > 0 else -1, 0) if dx else (0, 1 if off > 0 else -1)], hold))
                step += hold + 3
        step += 60                          # the stairs: the next floor fades in
        print("  adventure: %s walked by step %d" % (name, step))
    return ",".join(events), step + 60


# ── platformer: Hop Hills ───────────────────────────────────────────────

def trouble(run, order):
    """The first step something goes wrong (a life lost, or the player stopped getting anywhere), and how far it got."""
    lost = run.lost_at()
    best, since, stuck = (-1, 0.0), 0, None
    for step in sorted(run.trace):
        scene, things = run.trace[step]
        if not things or scene not in order:
            continue
        here = (order.index(scene), things[0][1])
        if here > best:
            best, since = here, step
        elif step - since > 50 and stuck is None:
            stuck = since
    if run.end:
        stuck = None if run.won else stuck
    first = min([s for s in (lost, stuck) if s is not None], default=None)
    return first, best


def platformer(folder):
    """Holds right all the way and looks for the moves that get it through: a jump (at, how long held), or a wait
    (at, how long it lets go of right, for a slime to walk away). Each trouble: the move before it that goes furthest."""
    from concurrent.futures import ThreadPoolExecutor
    order = ["main", "level2"]
    limit = 9000

    def script(moves):
        events = ["5:right:down"]
        for kind, at, n in sorted(moves, key=lambda m: m[1]):
            events.append(key(at, "jump", n) if kind == "jump" else "%d:right:up,%d:right:down" % (at, at + n))
        return ",".join(events)

    def judge(moves, steps):
        run = play(folder, script(moves), steps, trace="player")
        first, best = trouble(run, order)
        return (1 if run.won and first is None else 0, first if first is not None else 10 ** 9, best), run

    def free(moves, at, n):
        return at > 6 and not any(a - 6 < at + n and at < a + m + 6 for _, a, m in moves)

    moves = []
    with ThreadPoolExecutor(8) as pool:
        for _ in range(120):
            score, run = judge(moves, limit)
            if score[0]:
                return script(moves), run.steps + 30
            at = score[1]
            if at == 10 ** 9:
                raise SystemExit("platformer: no trouble and no win: %s" % run.summary)
            tries = [moves + [("jump", at - back, hold)] for back in range(2, 100, 3) for hold in (14, 5)
                     if free(moves, at - back, hold)]
            tries += [moves + [("wait", at - back, n)] for back in range(10, 130, 12) for n in (20, 45, 90)
                      if free(moves, at - back, n)]
            scores = list(pool.map(lambda ms: judge(ms, min(limit, at + 900))[0], tries))
            top = max(range(len(tries)), key=lambda i: scores[i])
            if scores[top][:2] <= (0, at):
                raise SystemExit("platformer: stuck at step %d (%s)" % (at, score[2]))
            moves = tries[top]
            print("  platformer: a %s at %d (%d steps): fine until %s, got to %s"
                  % (moves[-1] + (scores[top][1], scores[top][2])))
    raise SystemExit("platformer: no win")


# ── shooter: Star Guard ─────────────────────────────────────────────────

def shooter(folder):
    """Every quarter of a second it looks where everything is and holds the finger where the ship should go: under the
    lowest rock nobody has fired at yet (or ahead of a saucer), and never under a shot or a rock about to land."""
    every, ship_y = 15, 570
    events, step, doomed, target = [], 5, set(), 180.0
    while step < 15000:
        run = play(folder, ",".join(events), step + 1, trace="ship,rock,saucer,shot,bullet")
        if run.end:
            if run.won:
                return ",".join(events), run.steps + 30
            raise SystemExit("shooter: lost at step %d: %s" % (run.steps, run.summary))
        last = max(run.trace)
        scene, things = run.trace[last]
        ship = next((x for n, x, y in things if n == "ship"), target)
        rocks = [(x, y) for n, x, y in things if n == "rock"]
        for s in range(last - every, last + 1):          # a bullet that left under a rock: that rock is done
            for n, x, y in run.things(s, "bullet"):
                if y > ship_y - 40:
                    under = [r for r in rocks if abs(r[0] - x) < 13 and r[1] < y]
                    if under:
                        doomed.add((scene, max(under, key=lambda r: r[1])[0]))
        danger = [x for x, y in rocks if y > 500 and (scene, x) not in doomed]
        danger += [x for n, x, y in things if n == "shot" and 0 < ship_y - y < 4.4 * (every + 8)]
        aims = sorted(((x, y) for x, y in rocks if y <= 500 and (scene, x) not in doomed), key=lambda r: -r[1])
        saucers = [(x, y) for n, x, y in things if n == "saucer"]
        if aims and (aims[0][1] > 200 or not saucers):
            target = aims[0][0]
        elif saucers:
            x, y = max(saucers, key=lambda s: s[1])
            before = [a for n, a, b in run.things(last - 1, "saucer") if abs(b - y) < 1 and abs(a - x) < 3]
            pace = (x - before[0]) if before else 0
            ahead = x + pace * (every / 2 + (ship_y - 20 - y) / 8.7)
            target = min(340.0, max(20.0, ahead if 14 <= ahead <= 346 else x))
        elif aims:
            target = aims[0][0]
        for _ in range(4):                               # out of the way of what is coming down
            near = [x for x in danger if abs(x - target) < 26]
            if not near:
                break
            side = 1 if (target >= near[0] and near[0] < 320) or near[0] < 40 else -1
            target = min(346.0, max(14.0, near[0] + side * 27))
        events.append("%d:drag:%g:610:%g:610:%d" % (step, target, target, every - 2))
        step += every
        if (step // every) % 20 == 0:
            print("  shooter: step %d, %s, %s" % (step, scene, run.events[-1][1] if run.events else ""))
    raise SystemExit("shooter: no win")


BOTS = {"puzzle": puzzle, "tap": tap_game, "runner": runner, "bricks": bricks, "world": world,
        "adventure": adventure, "platformer": platformer, "shooter": shooter}


PICTURES = os.path.join(ROOT, "apkpy_lib", "game", "studio", "pictures")
# kind: (the step, with the replay that wins or with no hands, the scene, the top of the part shown of a tall game)
SHOTS = {"platformer": (250, True, "main", 0), "shooter": (420, False, "main", 330), "runner": (700, True, "main", 0),
         "bricks": (700, True, "main", 40), "adventure": (300, True, "main", 0), "tap": (260, False, "main", 150),
         "puzzle": (8, False, "main", 165), "world": (300, True, "main", 130),
         "monster-rpg": (60, False, "title", 0)}


def pictures(base, saved):
    from PIL import Image
    os.makedirs(PICTURES, exist_ok=True)
    env = dict(os.environ, APKPYGAME_LANG="en")
    for kind, (step, replayed, scene, top) in SHOTS.items():
        folder = make(kind, base)
        build = os.path.join(folder, "build", "apkpygame")
        with open(os.path.join(build, "bundle", "game.json"), encoding="utf-8") as fh:
            w, h = json.load(fh)["size"]
        if w > h:
            w, h = w * 2, h * 2             # the small pixel games, drawn larger
        classpath = engine.desktop_jar()
        if os.path.isfile(os.path.join(build, "game.jar")):
            classpath += os.pathsep + os.path.join(build, "game.jar")
        png = os.path.join(base, kind + ".png")
        cmd = [toolchain().java, "-cp", classpath, "apkpygame.desktop.Main", "--bundle", os.path.join(build, "bundle"),
               "--scene", scene, "--screenshot", png, "--steps", str(step), "--width", str(int(w)), "--height", str(int(h))]
        if replayed:
            cmd += ["--replay", saved[kind]["replay"]]
        subprocess.run(cmd, capture_output=True, text=True, env=env)
        im = Image.open(png).convert("RGB")
        if im.width > im.height:
            side = im.height * 4 // 3
            im = im.crop(((im.width - side) // 2, 0, (im.width + side) // 2, im.height))
        else:
            im = im.crop((0, top, im.width, top + im.width * 3 // 4))
        im = im.resize((320, 240), Image.LANCZOS).quantize(96)
        name = kind.replace("-", "_") + ".png"
        im.save(os.path.join(PICTURES, name), optimize=True)
        print("  %s: %d bytes" % (name, os.path.getsize(os.path.join(PICTURES, name))))


def main():
    wanted = [a for a in sys.argv[1:] if not a.startswith("--")] or [g for g in GENRES if g in BOTS]
    try:
        with open(REPLAYS, encoding="utf-8") as fh:
            saved = json.load(fh)
    except OSError:
        saved = {}
    base = tempfile.mkdtemp(prefix="genre_bots_")
    if "--pictures" in sys.argv:
        try:
            pictures(base, saved)
        finally:
            shutil.rmtree(base, ignore_errors=True)
        return
    failed = []
    try:
        for genre in wanted:
            print(genre)
            folder = make(genre, base)
            script, steps = BOTS[genre](folder)
            run = play(folder, script, steps)
            print("  " + run.summary)
            if not run.won:
                failed.append(genre)
                continue
            saved[genre] = {"scene": "main", "steps": steps, "replay": script}
    finally:
        shutil.rmtree(base, ignore_errors=True)
    with open(REPLAYS, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(dict(sorted(saved.items())), fh, indent=1)
        fh.write("\n")
    print("saved", REPLAYS)
    if failed:
        sys.exit("no win: " + ", ".join(failed))


if __name__ == "__main__":
    main()
