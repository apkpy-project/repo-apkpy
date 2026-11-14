"""Builds the game and lets tools/advanced/bot/Bot.java play its opening: every feature, or it says where it got stuck.

    python tools/advanced/play_bot.py

It writes tools/advanced/bot/replay.txt, then plays that replay again on its own: both must reach the same state.
"""
import os
import subprocess
import sys

from apkpy_lib.game import desktop, engine
from apkpy_lib.game._host import toolchain
from apkpy_lib.game.build import bundle_only
from apkpy_lib.game.project import Project

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    os.chdir(ROOT)
    project = Project(ROOT)
    info = bundle_only(project)
    tools = toolchain()
    classes = os.path.join(ROOT, "build", "bot")
    os.makedirs(classes, exist_ok=True)
    cp = engine.desktop_jar() + os.pathsep + info["game_jar"]
    r = subprocess.run([tools.javac, "-nowarn", "-Xlint:-options", "-cp", cp, "-d", classes, os.path.join(ROOT, "tools", "advanced", "bot", "Bot.java")],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr)
    replay = os.path.join(ROOT, "tools", "advanced", "bot", "replay.txt")
    r = subprocess.run([tools.java, "-cp", cp + os.pathsep + classes, "apkpygame.game.Bot", info["bundle"], replay], capture_output=True, text=True, timeout=240)
    print(r.stdout)
    if r.returncode:
        sys.exit("the bot failed:\n" + r.stderr[-3000:])
    steps = r.stdout.split("steps=", 1)[1].split()[0]
    desktop._config.update({"bundle": None, "store": None, "project": project})
    with open(replay, encoding="utf-8") as fh:
        script = fh.read()
    r = subprocess.run(desktop.command("title", "{}", "--replay", script, "--steps", steps), capture_output=True, text=True, timeout=300)
    summary = [l for l in r.stdout.splitlines() if l.startswith("APKPYGAME_SUMMARY")]
    print("replayed: " + (summary[0] if summary else r.stdout[-400:] + r.stderr[-400:]))


if __name__ == "__main__":
    main()
