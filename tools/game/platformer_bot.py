"""Finds a winning input replay for the platformer example (dev machine only).

    python src/tools/platformer_bot.py

Holds "right" all the way and searches jump times: each time a life is lost,
it tries jumps a little before that moment and keeps the one that gets
furthest. The engine is deterministic, so the replay found here plays the
same on the phone. Prints the replay and saves it to
src/examples/platformer/winning_replay.txt.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"))
from apkpy_lib.game import engine  # noqa: E402
from apkpy_lib.game._host import toolchain  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # ApkPy's repository
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import where  # noqa: E402
TOOLS = os.path.join(ROOT, "tools", "game")
SRC = ROOT
BUNDLE = where.examples("platformer", "build", "apkpygame", "bundle")
HOLD = 14            # steps the jump key is held (a full jump needs it held)


def script(jumps):
    events = ["5:right:down"]
    for s in sorted(jumps):
        events += ["%d:jump:down" % s, "%d:jump:up" % (s + HOLD)]
    return ",".join(events)


def play(jumps):
    out = subprocess.run([toolchain().java, "-jar", engine.desktop_jar(), "--bundle", BUNDLE, "--scene", "main",
                          "--replay", script(jumps), "--steps", "3600"], capture_output=True, text=True).stdout
    lost = None
    lives = 3
    for line in out.splitlines():
        m = re.match(r"APKPYGAME_EVENT step=(\d+) vars=(\{.*?\})", line)
        if m:
            v = json.loads(m.group(2))
            if v.get("lives", 3) < lives and lost is None:
                lost = int(m.group(1))
            lives = v.get("lives", lives)
    result = re.search(r"APKPYGAME_RESULT (.*)", out)
    max_x = float(re.search(r"APKPYGAME_MAXX (\S+)", out).group(1))
    return (json.loads(result.group(1)) if result else None), lost, max_x, out


def main():
    jumps = []
    for _ in range(40):
        result, lost, max_x, _ = play(jumps)
        if result and result["result"].get("result") == "win" and lost is None:
            break
        if lost is None:
            print("no life lost and no win; furthest x =", max_x)
            break
        best = None
        for back in range(4, 70, 3):
            at = lost - back
            if at <= 5 or any(abs(at - j) < HOLD + 4 for j in jumps):
                continue
            r, l2, x2, _ = play(jumps + [at])
            score = (1 if r and r["result"].get("result") == "win" and l2 is None else 0, l2 or 10 ** 6, x2)
            if best is None or score > best[0]:
                best = (score, at)
        if best is None:
            print("stuck at step", lost)
            break
        jumps.append(best[1])
        print("jump at step %d -> next loss %s, furthest x %.0f" % (best[1], best[0][1], best[0][2]))
    result, lost, max_x, out = play(jumps)
    print(out)
    replay = script(jumps)
    with open(where.examples("platformer", "winning_replay.txt"), "w") as fh:
        fh.write(replay + "\n")
    print("REPLAY:", replay)
    won = result and result["result"].get("result") == "win"
    print("WON" if won else "NOT WON", "lives lost:", "none" if lost is None else "yes")
    sys.exit(0 if won else 1)


if __name__ == "__main__":
    main()
