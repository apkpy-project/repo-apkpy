"""The game's tests (apkpy_lib.game), run with pytest from the repository:

    python -m pytest tests/game -m "not slow"

The slow ones open real windows (Java and Tk) for a few seconds each.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # ApkPy's repository
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# Python started by a test finds this ApkPy, and no test turns into the Previewer's reload watcher.
os.environ["PYTHONPATH"] = os.pathsep.join([ROOT] + [p for p in [os.environ.get("PYTHONPATH")] if p])
os.environ.setdefault("APKPY_RELOAD", "0")

PACKAGE = os.path.join(ROOT, "apkpy_lib", "game")
TEMPLATES = os.path.join(PACKAGE, "project_templates")
sys.path.insert(0, os.path.join(ROOT, "tools", "game"))
import where  # noqa: E402
EXAMPLES = where.examples()          # examples/games of the repository
TOOLS = os.path.join(ROOT, "tools", "game")
APKPY = [sys.executable, "-c", "from apkpy_lib.cli import main; main()"]


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: opens real windows (Java and Tk) for a few seconds each")


def apkpy(*args, cwd=None, **kw):
    """`apkpy <args>`, as a person types it, in another Python."""
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    return subprocess.run(APKPY + [str(a) for a in args], cwd=None if cwd is None else str(cwd), **kw)


def new_game(folder, template="menus", app_id=None):
    """`apkpy start <folder> --game <template>`, with the application id the test wants."""
    folder = str(folder)
    r = apkpy("start", os.path.basename(folder), "--game", template, cwd=os.path.dirname(folder))
    if r.returncode == 0 and app_id:
        toml = os.path.join(folder, "apkpy.toml")
        with open(toml, encoding="utf-8") as fh:
            text = fh.read()
        import re
        text = re.sub(r'application_id = ".*"', 'application_id = "%s"' % app_id, text, count=1)
        with open(toml, "w", encoding="utf-8") as fh:
            fh.write(text)
    return r
