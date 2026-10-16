"""Transpile every example app and compare two runs byte for byte.

    python tools/sweep_apps.py snapshot before.json
    ... change the engine ...
    python tools/sweep_apps.py snapshot after.json
    python tools/sweep_apps.py compare before.json after.json

``snapshot --dump DIR`` also writes every generated file under DIR, one
folder per app, so two runs can be read with ``diff -r`` rather than only
counted.

``snapshot --engine DIR`` imports apkpy_lib from DIR instead of this tree --
a copy of the engine taken before a change is the cleanest baseline.

The generator names some Java locals after ``id(command) & 0xFFFF`` (a memory
address) and one after ``hash()`` of a string, so the same source gives
different Java on every run. This script injects a stable ``id`` into the
compiler modules and re-runs itself with PYTHONHASHSEED=0; without both, two
snapshots of an unchanged tree already differ in ~19 apps.
"""
import builtins
import contextlib
import glob
import hashlib
import io
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The examples beside apkpy_lib, as the repository has them; the other two
# are where the apps are in the tree ApkPy is developed in.
PATTERNS = (
    os.path.join(ROOT, "examples", "**", "*.py"),
    os.path.join(ROOT, "playground", "**", "*.py"),
    os.path.join(ROOT, "github-repo", "repo-apkpy", "examples", "**", "*.py"),
)
SKIP = ("site-packages", "_wheel_check", os.sep + "build" + os.sep, "__pycache__")


def _apps():
    found = []
    for pattern in PATTERNS:
        for path in glob.glob(pattern, recursive=True):
            if any(part in path.lower() for part in SKIP):
                continue
            try:
                source = open(path, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            if "apkpy_lib" in source and "run(" in source and "Screen" in source:
                found.append(path)
    return sorted(found)


def _digest(value):
    if isinstance(value, str):
        value = value.encode("utf-8")
    elif not isinstance(value, (bytes, bytearray)):
        value = repr(value).encode("utf-8")
    return hashlib.sha1(value).hexdigest()


def snapshot(out_path, engine=None, dump=None):
    if os.environ.get("PYTHONHASHSEED") != "0":
        env = dict(os.environ, PYTHONHASHSEED="0", PYTHONIOENCODING="utf-8")
        raise SystemExit(subprocess.call([sys.executable] + sys.argv, env=env))

    sys.path.insert(0, engine or ROOT)
    import apkpy_lib
    from apkpy_lib.core.compiler import translate_python_to_android
    print("engine:", os.path.dirname(apkpy_lib.__file__))

    ids = {}

    def stable_id(obj):
        key = builtins.id(obj)
        if key not in ids:
            ids[key] = (len(ids) + 1) * 7919
        return ids[key]

    for name, module in list(sys.modules.items()):
        if name.startswith("apkpy_lib.core") and module is not None:
            module.id = stable_id

    result = {}
    for path in _apps():
        ids.clear()
        cwd = os.getcwd()
        try:
            os.chdir(os.path.dirname(path))
            quiet = io.StringIO()
            with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
                files = translate_python_to_android(open(path, encoding="utf-8").read())
            if "error.txt" in files:
                head = files["error.txt"].strip().splitlines()[:3]
                result[path] = {"status": "error.txt", "msg": " | ".join(head)[:300]}
            else:
                result[path] = {"status": "ok", "files": {
                    k: _digest(v) for k, v in sorted(files.items())}}
                if dump:
                    folder = os.path.join(dump, os.path.relpath(path, ROOT).replace(os.sep, "__"))
                    for key, value in files.items():
                        target = os.path.join(folder, key)
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        if isinstance(value, bytes):
                            with open(target, "wb") as out:
                                out.write(value)
                        elif not isinstance(value, str):
                            # an asset to copy, e.g. ("copy", path): its repr
                            with open(target, "w", encoding="utf-8") as out:
                                out.write(repr(value))
                        else:
                            with open(target, "w", encoding="utf-8", newline="") as out:
                                out.write(value)
        except BaseException as error:   # noqa: BLE001 - recorded, not hidden
            text = str(error).splitlines()[0] if str(error) else ""
            result[path] = {"status": "raise",
                            "msg": (type(error).__name__ + ": " + text)[:300]}
        finally:
            os.chdir(cwd)

    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1)
    counts = {}
    for entry in result.values():
        counts[entry["status"]] = counts.get(entry["status"], 0) + 1
    print(len(result), "apps", counts)


def compare(first, second):
    a = json.load(open(first, encoding="utf-8"))
    b = json.load(open(second, encoding="utf-8"))
    differences = 0
    for path in sorted(set(a) | set(b)):
        name = os.path.relpath(path, ROOT)
        x, y = a.get(path), b.get(path)
        if x is None or y is None:
            print("only in one:", name)
            differences += 1
        elif x["status"] != y["status"]:
            print("STATUS", name, x["status"], "->", y["status"], y.get("msg", "")[:160])
            differences += 1
        elif x["status"] == "ok":
            changed = sorted(k for k in set(x["files"]) | set(y["files"])
                             if x["files"].get(k) != y["files"].get(k))
            if changed:
                print("FILES", name, changed[:6])
                differences += 1
        elif x.get("msg") != y.get("msg"):
            print("MSG", name, x.get("msg", "")[:80], "->", y.get("msg", "")[:80])
            differences += 1
    print("differences:", differences)
    return differences


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "snapshot":
        engine = args[args.index("--engine") + 1] if "--engine" in args else None
        dump = args[args.index("--dump") + 1] if "--dump" in args else None
        snapshot(args[1], engine, dump)
    elif len(args) == 3 and args[0] == "compare":
        raise SystemExit(1 if compare(args[1], args[2]) else 0)
    else:
        print(__doc__)
        raise SystemExit(2)
