"""Runs the game engine's own tests (Java) on the desktop JVM (working on ApkPy itself).

    python tools/game/test_engine.py
"""
import glob
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toolchain  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # ApkPy's repository
TOOLS = os.path.join(ROOT, "tools", "game")
SRC = ROOT
JAVA = os.path.join(ROOT, "game_engine", "java")
OUT = os.path.join(ROOT, "game_engine", "build", "tests")


def main():
    tools = toolchain.find(android=False)
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    files = []
    for module in ("core", "testkit", "tests"):
        files += glob.glob(os.path.join(JAVA, module, "**", "*.java"), recursive=True)
    subprocess.run([tools.javac, "--release", "8", "-Xlint:-options", "-encoding", "UTF-8", "-d", OUT] + files,
                   check=True)
    codes = [subprocess.run([tools.java, "-cp", OUT, "apkpygame.tests." + suite]).returncode
             for suite in ("CoreTests", "GameplayTests", "CanvasTests")]
    sys.exit(max(codes))


if __name__ == "__main__":
    main()
