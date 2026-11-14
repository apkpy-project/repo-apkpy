"""Builds the game engine from game_engine/java/, without Gradle (working on ApkPy itself).

    python tools/game/build_engine.py

Outputs (game_engine/build/engine/):
  apkpygame-engine-<v>.aar     core + testkit + platform-android, for the APK
  apkpygame-desktop-<v>.jar    core + testkit + platform-desktop, the PC runner
and copies both into apkpy_lib/game/engine/, which the wheel ships.

Before compiling, it checks the rule that keeps the engine portable:
core/ and testkit/ import nothing from android.*, java.awt.* or javax.swing.*.
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toolchain  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # ApkPy's repository
TOOLS = os.path.join(ROOT, "tools", "game")
SRC = ROOT
JAVA = os.path.join(ROOT, "game_engine", "java")
OUT = os.path.join(ROOT, "game_engine", "build", "engine")
PORTABLE = ("core", "testkit")
FORBIDDEN = re.compile(r"^\s*import\s+(android\.|java\.awt\.|javax\.swing\.)", re.M)


def sources(*modules):
    found = []
    for m in modules:
        found += glob.glob(os.path.join(JAVA, m, "**", "*.java"), recursive=True)
    return found


def check_portable():
    bad = []
    for path in sources(*PORTABLE):
        with open(path, encoding="utf-8") as fh:
            for m in FORBIDDEN.finditer(fh.read()):
                bad.append("%s: %s" % (os.path.relpath(path, ROOT), m.group(0).strip()))
    if bad:
        sys.exit("core/testkit must stay plain Java:\n  " + "\n  ".join(bad))


def javac(tools, out, files, classpath=None):
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    cmd = [tools.javac, "--release", "8", "-Xlint:all", "-Xlint:-options", "-Werror",
           "-encoding", "UTF-8", "-d", out]
    if classpath:
        cmd += ["-cp", classpath]
    subprocess.run(cmd + files, check=True)


def main():
    tools = toolchain.find()
    version = toolchain.engine_version(JAVA)
    check_portable()
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)

    portable = os.path.join(OUT, "classes-portable")
    javac(tools, portable, sources(*PORTABLE))
    print("core + testkit: plain Java, compiled without android.jar")

    android = os.path.join(OUT, "classes-android")
    javac(tools, android, sources(*PORTABLE, "platform-android"), tools.android_jar)
    classes_jar = os.path.join(OUT, "classes.jar")
    subprocess.run([tools.jar, "cf", classes_jar, "-C", android, "."], check=True)
    aar = os.path.join(OUT, "apkpygame-engine-%s.aar" % version)
    aar_dir = os.path.join(JAVA, "platform-android", "aar")
    with zipfile.ZipFile(aar, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(aar_dir, "AndroidManifest.xml"), "AndroidManifest.xml")
        z.write(os.path.join(aar_dir, "proguard.txt"), "proguard.txt")
        z.write(classes_jar, "classes.jar")
        z.writestr("R.txt", "")
    print("android:", aar)

    desktop = os.path.join(OUT, "classes-desktop")
    javac(tools, desktop, sources(*PORTABLE, "platform-desktop"))
    desktop_jar = os.path.join(OUT, "apkpygame-desktop-%s.jar" % version)
    subprocess.run([tools.jar, "cfe", desktop_jar, "apkpygame.desktop.Main", "-C", desktop, "."], check=True)
    print("desktop:", desktop_jar)

    # the Python package ships the engine (apkpy_lib/game/engine/, package data)
    packaged = os.path.join(ROOT, "apkpy_lib", "game", "engine")
    os.makedirs(packaged, exist_ok=True)
    shutil.copy2(aar, os.path.join(packaged, "apkpygame-engine.aar"))
    shutil.copy2(desktop_jar, os.path.join(packaged, "apkpygame-desktop.jar"))
    print("packaged in", packaged)


if __name__ == "__main__":
    main()
