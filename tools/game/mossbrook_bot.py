"""Plays "Lanterns of Mossbrook" to the end (dev machine only):

    python src/tools/mossbrook_bot.py

Finds a path on the village grid (the generator's map: solid tiles, villagers)
to each lantern and then to the elder, writes it as a replay of keys that
follows GridController's rules (a short press in a new direction only turns;
held, it walks one cell), plays it with the engine (no window) and checks the
game ends with the three lanterns. The replay is saved as
src/examples/mossbrook/winning_replay.txt (the phone plays it too: parity app).
"""
import collections
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # ApkPy's repository
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import where  # noqa: E402
TOOLS = os.path.join(ROOT, "tools", "game")
SRC = ROOT
sys.path.insert(0, ROOT)
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "dev"))             # the village's map is made by dev/make_phase7_example.py
import make_phase7_example as village  # noqa: E402

KEYS = {(0, -1): "up", (0, 1): "down", (-1, 0): "left", (1, 0): "right"}
FACING = {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270}


def walkable():
    _, _, _, solid = village.build_map()
    blocked = {(i % village.COLS, i // village.COLS) for i, s in enumerate(solid) if s}
    return blocked | {village.ELDER, village.MILLER}


def path(blocked, start, goal):
    prev, todo = {start: None}, collections.deque([start])
    while todo:
        cell = todo.popleft()
        if cell == goal:
            break
        for d in KEYS:
            nxt = (cell[0] + d[0], cell[1] + d[1])
            if nxt not in prev and nxt not in blocked and 0 <= nxt[0] < village.COLS and 0 <= nxt[1] < village.ROWS:
                prev[nxt] = cell
                todo.append(nxt)
    if goal not in prev:
        raise SystemExit("no way from %s to %s" % (start, goal))
    out, cell = [], goal
    while prev[cell] is not None:
        out.append((cell[0] - prev[cell][0], cell[1] - prev[cell][1]))
        cell = prev[cell]
    return out[::-1]


def replay():
    blocked = walkable()
    events, step, facing, at = [], 10, (0, 1), village.HERO
    targets = list(village.LANTERNS)
    moves = []
    while targets:
        targets.sort(key=lambda t: len(path(blocked, at, t)))
        goal = targets.pop(0)
        moves += path(blocked, at, goal)
        at = goal
    below_elder = (village.ELDER[0], village.ELDER[1] + 1)
    moves += path(blocked, at, below_elder)
    for d in moves:
        key = KEYS[d]
        if d != facing:                                       # a short press only turns
            events += ["%d:%s:down" % (step, key), "%d:%s:up" % (step + 2, key)]
            step += 4
            facing = d
        events += ["%d:%s:down" % (step, key), "%d:%s:up" % (step + 7, key)]   # held: one cell
        step += 24
    if facing != (0, -1):                                     # face the elder, above
        events += ["%d:up:down" % step, "%d:up:up" % (step + 2)]
        step += 4
    events += ["%d:space:down" % step, "%d:space:up" % (step + 1)]
    return ",".join(events), step + 30, len(moves)


def main():
    from apkpy_lib.game import engine
    from apkpy_lib.game._host import toolchain
    script, steps, cells = replay()
    folder = where.examples("mossbrook")
    with open(os.path.join(folder, "winning_replay.txt"), "w", encoding="utf-8") as fh:
        fh.write(script)
    build = os.path.join(folder, "build", "apkpygame")
    classpath = engine.desktop_jar() + os.pathsep + os.path.join(build, "game.jar")
    out = subprocess.run([toolchain().java, "-cp", classpath, "apkpygame.desktop.Main", "--bundle",
                          os.path.join(build, "bundle"), "--scene", "town", "--replay", script, "--steps", str(steps)],
                         capture_output=True, text=True).stdout
    summary = re.search(r"APKPYGAME_SUMMARY (.*)", out)
    print("%d cells walked, %d steps" % (cells, steps))
    print(summary.group(1) if summary else out[-2000:])
    if summary and '"result":"done"' in summary.group(1) and '"lanterns":3' in summary.group(1):
        print("WON")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
