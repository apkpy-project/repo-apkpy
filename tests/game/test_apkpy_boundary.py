"""Where the game package meets the rest of ApkPy: only in _host.py, at named points. The engine side stays apart
from the app's build, so either can change without the other noticing."""
import ast
import os

from apkpy_lib.game import _host

from conftest import PACKAGE  # noqa: E402

ALLOWED = {"_host.py"}


def package_modules():
    for where, dirs, names in os.walk(PACKAGE):
        dirs[:] = [d for d in dirs if d not in ("project_templates", "__pycache__", "engine")]   # templates are games
        for name in names:
            if name.endswith(".py"):
                path = os.path.join(where, name)
                yield os.path.relpath(path, PACKAGE).replace(os.sep, "/"), path


def reaches_outside(rel, path):
    """The lines that import from ApkPy outside apkpy_lib.game, or reach Tk's default window."""
    depth = rel.count("/") + 1                      # how many dots reach apkpy_lib.game itself
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level > depth:
                found.append(node.lineno)
            elif not node.level and (node.module or "").split(".")[0] == "apkpy_lib" \
                    and not (node.module or "").startswith("apkpy_lib.game"):
                found.append(node.lineno)
        elif isinstance(node, ast.Import):
            if any(a.name.split(".")[0] == "apkpy_lib" and not a.name.startswith("apkpy_lib.game") for a in node.names):
                found.append(node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr == "_default_root":
            found.append(node.lineno)
    return found


def test_only_the_host_module_reaches_the_rest_of_apkpy():
    outside = {rel: lines for rel, path in package_modules() if os.path.basename(rel) not in ALLOWED
               for lines in [reaches_outside(rel, path)] if lines}
    assert not outside, "these reach outside apkpy_lib.game (move it into _host.py): %s" % outside


def test_the_meeting_points_are_listed():
    doc = _host.__doc__
    for point in ("E1 toolchain()", "E2 (apkpy_lib.cli)", "E3 preview_window()", "E4 preview_keys()",
                  "E5 (apkpy_lib.reload)", "E6", "E7 keystores_dir(), find_adb()"):
        assert point in doc, point
    for name in ("toolchain", "preview_window", "preview_keys", "keystores_dir", "find_adb"):
        assert (getattr(_host, name).__doc__ or "").startswith(("E1", "E3", "E4", "E7")), name


def test_the_previewer_keys_are_the_ones_it_binds():
    """AppPreview binds Back and turning with bind_all; the game takes the same keys while it is on show."""
    with open(os.path.join(os.path.dirname(PACKAGE), "ui.py"), encoding="utf-8") as fh:
        ui = fh.read()
    for key in _host.preview_keys()["back"] + _host.preview_keys()["turn"]:
        assert "bind_all('%s'" % key in ui, key


def test_no_previewer_no_window():
    """Asking for the Previewer's window never opens one (the app is a lazy proxy that would)."""
    assert _host.preview_window() is None


def test_the_reload_looks_into_game():
    from apkpy_lib import reload
    assert "game" in reload.DEEP_FOLDERS
