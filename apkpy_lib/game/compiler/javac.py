"""Translated scripts to class files: javac against the engine, then build/apkpygame/game.jar.

The same classes go to the desktop runner (game.jar on its classpath) and
into game.aar (classes.jar), so the PC and the phone run the same code.
"""
import os
import re
import shutil
import subprocess
import zipfile

from .. import engine
from .._host import toolchain
from ..errors import GameError


def compile_scripts(project, files):
    """files: {"Ship.java": text, ...}. Answers the path of game.jar, or None when there is nothing to compile."""
    out_dir = os.path.join(project.build_dir, "java")
    classes = os.path.join(project.build_dir, "classes")
    jar = os.path.join(project.build_dir, "game.jar")
    for d in (out_dir, classes):
        if os.path.isdir(d):
            shutil.rmtree(d)
    if os.path.isfile(jar):
        os.remove(jar)
    if not files:
        return None
    src = os.path.join(out_dir, "apkpygame", "game")
    os.makedirs(src)
    os.makedirs(classes)
    paths = []
    for name, text in files.items():
        path = os.path.join(src, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        paths.append(path)
    tools = toolchain()
    r = subprocess.run([tools.javac, "--release", "8", "-Xlint:-options", "-nowarn", "-encoding", "UTF-8",
                        "-cp", engine.desktop_jar(), "-d", classes] + paths, capture_output=True, text=True)
    if r.returncode != 0:
        first = next((l for l in r.stderr.splitlines() if ": error:" in l), r.stderr.strip()[:300])
        m = re.search(r"([A-Za-z0-9_]+\.java):(\d+)", first)
        raise GameError("G2999", "the translated Java did not compile (a bug of the translator): %s" % first.strip(),
                        fix=["Please report it with the script; meanwhile, write that line another way.",
                             "The Java is in %s" % project.rel(out_dir)],
                        received=(m.group(0) if m else ""))
    with zipfile.ZipFile(jar, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, names in os.walk(classes):
            for n in names:
                p = os.path.join(root, n)
                z.write(p, os.path.relpath(p, classes).replace("\\", "/"))
    return jar
