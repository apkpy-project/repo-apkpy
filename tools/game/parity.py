"""The parity check: a replay must end in the same state on the phone as on the PC.

    python tools/game/parity.py platformer|sunbeam|mossbrook

Builds that example's game, puts its AAR where the parity app (examples/games/parity) takes it, and prints what
the PC computes for the parity app's button that replays it. Then, in examples/games/parity:

    apkpy run --usb

and the button's line on the phone must be the same as the one printed here.
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # ApkPy's repository
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import where  # noqa: E402
sys.path.insert(0, ROOT)

EXAMPLES = where.examples()
PARITY = os.path.join(EXAMPLES, "parity")
# example: (the parity app's button, scene, the name of its replay in parity/writehere.py, steps)
BUTTONS = {
    "platformer": ("Replay main", "main", None, 7200),
    "sunbeam": ("Replay solution", "main", "SOLUTION", 3000),
    "mossbrook": ("Replay 2.5D", "town", "MOSSBROOK", 1344),
}


def replay_script(name):
    if name is None:
        return ""
    with open(os.path.join(PARITY, "writehere.py"), encoding="utf-8") as fh:
        return re.search(r'^%s = "([^"]*)"' % name, fh.read(), re.M).group(1)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in BUTTONS:
        sys.exit(__doc__)
    from apkpy_lib.game import engine
    from apkpy_lib.game._host import toolchain
    from apkpy_lib.game.build import build
    from apkpy_lib.game.compiler.pack import AAR
    from apkpy_lib.game.project import Project

    example = sys.argv[1]
    button, scene, script_name, steps = BUTTONS[example]
    project = Project(os.path.join(EXAMPLES, example))
    build(project)
    target = Project(PARITY)
    os.makedirs(target.build_dir, exist_ok=True)
    shutil.copyfile(os.path.join(project.build_dir, AAR), os.path.join(target.build_dir, AAR))

    classpath = engine.desktop_jar()
    game_jar = os.path.join(project.build_dir, "game.jar")
    if os.path.isfile(game_jar):
        classpath += os.pathsep + game_jar
    out = subprocess.run([toolchain().java, "-cp", classpath, "apkpygame.desktop.Main",
                          "--bundle", project.bundle_dir, "--scene", scene,
                          "--replay", replay_script(script_name), "--steps", str(steps)],
                         capture_output=True, text=True).stdout
    summary = next((line[len("APKPYGAME_SUMMARY "):] for line in out.splitlines()
                    if line.startswith("APKPYGAME_SUMMARY ")), None)
    if summary is None:
        sys.exit("the PC gave no summary:\n" + out[-2000:])
    print("\nThe parity app now replays %s. On the phone, its button '%s' must show:\n\n%s\n" % (example, button, summary))


if __name__ == "__main__":
    main()
