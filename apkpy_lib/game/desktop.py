"""The Previewer's side of the glue: the same engine, run by the desktop JVM.

The ApkPy build ignores preview=, so this runs only on the developer's PC.
play() rebuilds the bundle (so the Previewer shows the game as written now)
and starts apkpygame-desktop.jar as a subprocess without blocking the
Previewer (Tk). The answer goes to ``done`` on Tk's thread.

Two modes:
- embedded (the default inside the Previewer): the game is drawn inside the
  Previewer's own window, where the phone's screen is (see embedded.py);
- window (APKPYGAME_PREVIEW=window, or no Tk loop): the runner opens its own
  Java window, as `apkpy game play` does.
"""
import json
import os
import queue
import subprocess
import sys
import threading

from .errors import GameError

_config = {"bundle": None, "store": None, "project": None}
_answers = queue.Queue()
_waiting = [0]
_suspended = {"process": None, "embedded": None}
_holders = {}


def configure(bundle, store=None):
    """A fixed bundle folder (no project, no rebuild): the phase-1 example uses this."""
    _config["bundle"] = os.path.abspath(bundle)
    _config["store"] = os.path.abspath(store or os.path.join(os.path.dirname(bundle), "store.json"))


def _project():
    if _config["project"] is None:
        from .project import Project
        # the app's writehere.py: __main__'s file, or sys.argv[0] in the Python that ApkPy's hot reload
        # keeps ready (it runs the app with no __file__ on __main__), else the current folder
        main = sys.modules.get("__main__")
        script = getattr(main, "__file__", None) or (sys.argv[0] if sys.argv and sys.argv[0].endswith(".py") else None)
        start = os.path.dirname(os.path.abspath(script)) if script else os.getcwd()
        _config["project"] = Project.find(start)
    return _config["project"]


def _paths(rebuild=False):
    if _config["bundle"]:
        return _config["bundle"], _config["store"]
    project = _project()
    if rebuild or not os.path.isfile(os.path.join(project.bundle_dir, "game.json")):
        from .build import bundle_only
        bundle_only(project)
    return project.bundle_dir, project.store_file


def _embedding():
    """The Previewer's window when the game should be drawn inside it, else None."""
    if os.environ.get("APKPYGAME_PREVIEW", "embedded") == "window":
        return None
    from ._host import preview_window
    root = preview_window()
    if root is None:
        return None
    try:
        from . import embedded  # noqa: F401  (needs Pillow, which ApkPy brings)
    except ImportError:
        return None
    return root


def _java():
    from ._host import toolchain
    return toolchain().java


def command(scene, args_json, *extra, rebuild=False):
    from .engine import desktop_jar
    bundle, store = _paths(rebuild)
    for env, flag in (("APKPYGAME_AUTOEXIT_MS", "--autoexit-ms"), ("APKPYGAME_AUTOBACK_MS", "--autoback-ms")):
        if os.environ.get(env):                             # automatic tests only
            extra = (flag, os.environ[env]) + extra
    classpath = desktop_jar()
    game_jar = os.path.join(os.path.dirname(bundle), "game.jar")       # the translated scripts, if any
    if os.path.isfile(game_jar):
        classpath += os.pathsep + game_jar
    return [_java(), "-cp", classpath, "apkpygame.desktop.Main", "--bundle", bundle, "--store", store,
            "--scene", scene or "", "--args", args_json or "{}"] + list(extra)


def _error_json(e):
    return json.dumps({"v": 1, "action": "error", "error": {"code": getattr(e, "code", "G1999"),
                                                             "message": str(e)}, "suspended": False})


def _poll(root):
    try:
        while True:
            done, ok, value = _answers.get_nowait()
            done.run(ok, value)
    except queue.Empty:
        pass
    if _waiting[0]:
        root.after(50, _poll, root)


def _reader(process, holder):
    """Reads the runner's answers. A suspended game (open_app) keeps its process: the
    next answer comes after game_resume() writes "resume" to it."""
    for line in process.stdout:
        if not line.startswith("APKPYGAME_RESULT "):
            continue
        value = line[len("APKPYGAME_RESULT "):].strip()
        suspended = '"suspended":true' in value
        _suspended["process"] = process if suspended else None
        put("apkpygame.last_result", value)
        done, holder["done"] = holder["done"], None
        if done is not None:
            _answers.put((done, '"action":"error"' not in value, value))
            _waiting[0] -= 1
    if holder["done"] is not None:          # ended without an answer (killed, crashed)
        _answers.put((holder["done"], False, '{"v":1,"action":"error","error":{"code":"G3998",'
                                             '"message":"the desktop runner gave no answer"}}'))
        _waiting[0] -= 1
        holder["done"] = None
    if _suspended.get("process") is process:
        _suspended["process"] = None


def _deliver():
    from ._host import preview_window
    root = preview_window()
    if root is not None:
        root.after(50, _poll, root)
    else:                                       # no Tk (a script): answer here
        d, ok, value = _answers.get()
        d.run(ok, value)


def _quit_suspended():
    game = _suspended.get("embedded")
    _suspended["embedded"] = None
    if game is not None:
        game.close()
    process = _suspended.get("process")
    _suspended["process"] = None
    if process is not None and process.poll() is None:
        try:
            process.stdin.write("quit\n")
            process.stdin.flush()
        except OSError:
            pass


def play(scene, args_json, done):
    _quit_suspended()                           # a new game_play ends a suspended one, as on the phone
    root = _embedding()
    try:
        cmd = command(scene, args_json, "--parent-pipe", rebuild=True)      # no window left if the Previewer dies
    except GameError as e:
        print(e)
        answer = _error_json(e)
        if root is not None:                    # shown where the game would be; a tap closes it
            from .embedded import show_error
            where, _, rest = str(e).partition("\n")
            show_error(root, where.replace("APKPY ", "", 1), rest.replace("\n  ", "\n").strip(), None,
                       lambda: done.run(False, answer))
        else:
            done.run(False, _error_json(e))
        return
    if root is not None:
        _play_embedded(root, cmd, done)
        return
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    holder = {"done": done}
    _holders[process] = holder
    _waiting[0] += 1
    threading.Thread(target=_reader, args=(process, holder), daemon=True).start()
    _deliver()


def _ended(done):
    def ended(value):
        put("apkpygame.last_result", value)
        game = _current["game"]
        _suspended["embedded"] = game if '"suspended":true' in value else None
        done.run('"action":"error"' not in value, value)
    return ended


_current = {"game": None}


def _play_embedded(root, cmd, done):
    from .embedded import EmbeddedGame
    bundle = cmd[cmd.index("--bundle") + 1]
    _current["game"] = EmbeddedGame(root, lambda w, h: cmd + ["--embed", "%dx%d" % (w, h)], bundle,
                                    _ended(done))


def current():
    """The embedded game on show (or suspended), for tests and tools; None in window mode."""
    game = _current["game"]
    return game if game is not None and game.alive() else None


def resume(done):
    """Continues the game the runner keeps (world in memory), or answers "none"."""
    game = _suspended.get("embedded")
    if game is not None:
        _suspended["embedded"] = None
        if game.alive():
            game.resume(_ended(done))
            return
    process = _suspended.get("process")
    if process is None or process.poll() is not None:
        done.run(True, '{"v":1,"action":"none","suspended":false}')
        return
    _suspended["process"] = None
    _holders[process]["done"] = done
    _waiting[0] += 1
    process.stdin.write("resume\n")
    process.stdin.flush()
    _deliver()


def suspended():
    game = _suspended.get("embedded")
    if game is not None and game.alive():
        return "true"
    process = _suspended.get("process")
    return "true" if process is not None and process.poll() is None else "false"


def snapshot(scene, args_json, steps):
    out = subprocess.run(command(scene, args_json, "--headless", str(steps)), capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith("APKPYGAME_STATE "):
            return line[len("APKPYGAME_STATE "):]
    return "error: no state"


def _store():
    return _paths()[1]


def _load():
    try:
        with open(_store(), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save(data):
    os.makedirs(os.path.dirname(_store()), exist_ok=True)
    with open(_store(), "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def get(key):
    return str(_load().get(key, ""))


def put(key, value):
    data = _load()
    data[key] = value
    _save(data)
    return "ok"


def last_result():
    data = _load()
    value = data.pop("apkpygame.last_result", "")
    _save(data)
    return value
