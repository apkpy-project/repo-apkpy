"""The Previewer reloads when a .py file of the app is saved.

``python writehere.py`` keeps a small Python here that watches the folder and
runs the app in a second one. A save starts the new code behind the window
that is open, on the same screen and in the same place, and the old window
closes only once the new one is drawn. A change that does not start leaves
the old window up, with the error on it; the terminal has the whole of it.

Three things keep it quick and keep what is on the screen:

- a save that changes only ``style = \"\"\"...\"\"\"`` goes to the open window,
  which takes the new CSS without starting again;
- a spare Python waits with ApkPy, Pillow and its window already loaded, so a
  save only has to run the app's own code and draw it;
- what the person typed and chose on the screens that were open -- fields
  with an ``id``, switches, chips, the page of a pager -- comes back, and so
  does how far the screen was scrolled. Passwords are never written down.

``APKPY_RELOAD=0`` turns this off. It is also off when the script does not
call run() itself, under ``python -i``, in IDLE (which keeps its own
output), and in a frozen app.

This module is imported before Tk: the watching Python never opens a window
and never runs the app's code.
"""

import ast
import collections
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import tokenize

_DIR = "APKPY_RELOAD_DIR"
_GEN = "APKPY_RELOAD_GEN"
_PARENT = "APKPY_RELOAD_PARENT"
# A spare: the script it will run, with what sys.argv and sys.path[0] are.
_SPARE = "APKPY_RELOAD_SPARE"
_HOME = "APKPY_RELOAD_HOME"
_ARGV = "APKPY_RELOAD_ARGV"

# What a spare Python runs: the app's folder first on the path, as
# ``python writehere.py`` would have it, then ApkPy, then it waits.
_SPARE_BOOT = ("import os, sys; sys.path[0] = os.environ.get('APKPY_RELOAD_HOME', ''); "
               "import apkpy_lib.reload as r; r.serve_as_spare()")

# Folders next to the app that are not the app: environments, caches and
# what apkpy build writes.
_NOT_THE_APP = {"__pycache__", "venv", "env", "build", "dist", "node_modules",
                "site-packages"}

_STATE = "state.json"
_ERROR = "error.json"
_COMMAND = "command.json"          # new CSS, from the watcher to the open window
_DONE = "command-done.json"        # and its answer

# (folder, generation) in the app's own Python when the watcher started it.
_child = None
# (script, sys.argv) while this Python waits as a spare; None otherwise.
_spare_for = None
# How the app knows the watcher is still there: its pid, and on Windows a
# handle to it, which a reused pid cannot fool.
_watcher = [None, None]


# -- In the app's Python ------------------------------------------------------

def _take_child_env():
    """Read, then remove, what the watcher handed this Python, so that a
    Python the app itself starts is not mistaken for one of ours."""
    global _child, _spare_for
    folder = os.environ.pop(_DIR, None)
    generation = os.environ.pop(_GEN, None)
    parent = os.environ.pop(_PARENT, None)
    spare = os.environ.pop(_SPARE, None)
    os.environ.pop(_HOME, None)
    argv = os.environ.pop(_ARGV, None)
    if folder and generation and parent == str(os.getppid()):
        try:
            _child = (folder, int(generation))
            if spare:
                _spare_for = (spare, json.loads(argv or "[]"))
        except ValueError:
            _child = None
            return
        _watcher[0] = os.getppid()
        if sys.platform == "win32":
            try:
                import ctypes
                # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION
                _watcher[1] = ctypes.windll.kernel32.OpenProcess(0x00100000 | 0x1000,
                                                                 False, _watcher[0])
            except Exception:
                pass


def _watcher_gone():
    """True once the watching Python has ended -- an IDE's Stop button ends
    it without a word, and its app must not stay behind on its own."""
    if sys.platform == "win32":
        if not _watcher[1]:
            return False
        import ctypes
        return ctypes.windll.kernel32.WaitForSingleObject(_watcher[1], 0) == 0
    return _watcher[0] is not None and os.getppid() != _watcher[0]


def child():
    """True in an app the watcher started."""
    return _child is not None


def _read(name):
    try:
        with open(os.path.join(_child[0], name), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def _write(name, data):
    path = os.path.join(_child[0], name)
    temporary = path + ".%d.tmp" % os.getpid()
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    os.replace(temporary, path)


def child_window(root):
    """A new window starts invisible, where the old one stands. A spare's
    stays hidden as well until a save calls for it (see _wake)."""
    if _child is None:
        return
    try:
        if _spare_for is not None:
            # Hidden before Tk ever maps it: a window that shows, even for
            # a moment, takes the keyboard from the editor.
            root.withdraw()
            root.attributes("-alpha", 0.0)
            return
        root.attributes("-alpha", 0.0)
        _wake(root)
    except Exception:
        pass


def _wake(root):
    """Where the old window stands, still invisible; and on Windows the
    keyboard handed back to whoever had it."""
    position = _read(_STATE).get("position")
    if position:
        root.geometry("+%d+%d" % (position[0], position[1]))
    root.deiconify()
    if _child[1] > 1 and sys.platform == "win32":
        _hand_the_keyboard_back(root)


def serve_as_spare():
    """A spare Python: load what the first frame needs, wait for a save to
    call for it, then become the app -- ``python writehere.py`` with
    ApkPy, Pillow and the window already there."""
    global _spare_for
    if _child is None or _spare_for is None:
        raise SystemExit("serve_as_spare() is for a Python the watcher started")
    folder, generation = _child
    script, argv = _spare_for
    root = before = None
    if os.environ.get("APKPY_HEADLESS_CORE", "").strip() != "1":
        from . import ui
        try:
            import PIL.Image, PIL.ImageDraw, PIL.ImageFont, PIL.ImageTk  # noqa: E401,F401
        except ImportError:
            pass
        before = _foreground()
        root = ui._app._get().root
        try:
            root.update()
        except Exception:
            pass
        _give_back(before)
    path = os.path.join(folder, "spare-%d" % generation)
    with open(path + ".tmp", "w") as handle:
        handle.write(str(os.getpid()))
    os.replace(path + ".tmp", path)          # whole, or not there yet
    go = os.path.join(folder, "go-%d" % generation)
    elsewhere = [before]
    while not os.path.exists(go):
        if _watcher_gone():
            os._exit(0)
        if root is not None:
            try:
                root.update()        # a hidden window still answers Windows
            except Exception:
                pass
            # Whatever hands a hidden window the keyboard, a spare gives it
            # straight back to where the person was typing.
            elsewhere[0] = _keep_elsewhere(elsewhere[0])
        time.sleep(0.02)
    _spare_for = None
    if root is not None:
        try:
            _wake(root)
        except Exception:
            pass
    import __main__
    sys.argv = list(argv) or [script]
    __main__.__dict__["__file__"] = script
    try:
        with tokenize.open(script) as handle:
            code = compile(handle.read(), script, "exec")
        exec(code, __main__.__dict__)
    except SystemExit:
        raise
    except BaseException:
        kind, error, trace = sys.exc_info()
        # The person's traceback starts in their own file, as it would have
        # with python writehere.py: these lines are not theirs.
        while trace is not None and trace.tb_frame.f_code.co_filename != script:
            trace = trace.tb_next
        sys.excepthook(kind, error, trace)
        sys.exit(1)


def _foreground():
    """The window that has the keyboard (Windows), else None."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        return ctypes.windll.user32.GetForegroundWindow()
    except Exception:
        return None


def _give_back(before):
    """If one of this Python's windows took the keyboard, hand it back."""
    if not before or sys.platform != "win32":
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        now = user32.GetForegroundWindow()
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(now, ctypes.byref(owner))
        if now != before and owner.value == os.getpid():
            user32.SetForegroundWindow(before)
    except Exception:
        pass


def _keep_elsewhere(last):
    """For a spare: the window the person last typed in; if the keyboard has
    come to this Python, it goes back there."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        user32 = ctypes.windll.user32
        now = user32.GetForegroundWindow()
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(now, ctypes.byref(owner))
        if owner.value != os.getpid():
            return now
        if last and user32.IsWindow(last):
            user32.SetForegroundWindow(last)
    except Exception:
        pass
    return last


def _hand_the_keyboard_back(root):
    """Windows makes a new window the active one when it first shows, even
    behind an editor someone is typing in -- always from VS Code's own
    terminal. Show it now, still invisible, and give the keyboard back to
    whoever had it, unless that was the window being replaced."""
    import ctypes
    user32 = ctypes.windll.user32
    before = user32.GetForegroundWindow()
    root.update_idletasks()
    if (before and before != saved().get("window")
            and user32.GetForegroundWindow() != before):
        user32.SetForegroundWindow(before)


def saved():
    """What the window that is being replaced was showing: {} outside a
    reload, or before the first window was drawn."""
    return _read(_STATE) if _child is not None else {}


def screens_to_restore(all_screens, start_screen):
    """(screens behind, screen on top) to reopen, by their ids, or None when
    the saved screens are not all in the new code."""
    names = saved().get("screens") or []
    if not names or start_screen is None:
        return None
    by_id = {}
    for screen in all_screens:
        by_id.setdefault(getattr(screen, "id", None), screen)
    found = [by_id.get(name) for name in names]
    if any(screen is None for screen in found):
        return None
    params = saved().get("params") or {}
    for screen in found:
        if screen.id in params:
            screen._params = dict(params[screen.id])
    return found[:-1], found[-1]


def child_shown(root, describe, restyle=None, settle=None):
    """The first screen is drawn: put the window just behind the old one,
    show it, say so, then keep the state for the next reload, watch for an
    error to show and answer new CSS with ``restyle(css)``. ``settle()``
    runs once everything is drawn, before the window says it is ready."""
    if _child is None:
        return
    folder, generation = _child
    old = saved().get("window")
    try:
        root.update_idletasks()
        if old and sys.platform == "win32":
            import ctypes
            # Same place in the stack of windows: a save in the editor does
            # not bring the Previewer in front of the editor.
            flags = 0x0001 | 0x0002 | 0x0010     # NOSIZE | NOMOVE | NOACTIVATE
            ctypes.windll.user32.SetWindowPos(int(root.wm_frame(), 16), old,
                                              0, 0, 0, 0, flags)
        root.attributes("-alpha", 1.0)
        if sys.platform == "win32":
            _opaque(root)
        # What draws on <Configure> -- charts, covers, wrapped text -- waits
        # in the event queue; draw it now, still behind the old window, so
        # the first frame shown is the finished one.
        root.update()
        if settle is not None:
            settle()
            # Scrolled: what moved paints where it now is before the old
            # window goes, or the first frame shows half of each.
            root.update()
    except Exception:
        pass
    with open(os.path.join(folder, "ready-%d" % generation), "w") as handle:
        handle.write(str(os.getpid()))

    command_path = os.path.join(folder, _COMMAND)
    # CSS sent before this window started is older than the code it runs.
    try:
        heard = [_read(_COMMAND).get("id", 0), os.stat(command_path).st_mtime_ns]
    except OSError:
        heard = [0, None]

    def listen():
        # New CSS from the watcher: a quick look every 40 ms, a read only
        # when the file changed.
        try:
            stamp = os.stat(command_path).st_mtime_ns
        except OSError:
            stamp = None
        if stamp is not None and stamp != heard[1]:
            heard[1] = stamp
            command = _read(_COMMAND)
            if command.get("id", 0) > heard[0]:
                heard[0] = command["id"]
                ok = False
                if restyle is not None:
                    try:
                        ok = bool(restyle(command.get("style", "")))
                    except Exception:
                        ok = False
                _write(_DONE, {"id": command["id"], "ok": ok})
        root.after(40, listen)

    listen()
    last = [None, 0]

    def keep():
        if _watcher_gone():
            os._exit(0)
        try:
            data = describe()
            data["window"] = int(root.wm_frame(), 16)
            shape = re.match(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", root.geometry())
            if shape:
                width, height, x, y = (int(part) for part in shape.groups())
                data["size"], data["position"] = [width, height], [x, y]
            text = json.dumps(data, sort_keys=True)
            if text != last[0]:
                _write(_STATE, data)
                last[0] = text
            error = _read(_ERROR)
            if error.get("generation", 0) > max(generation, last[1]):
                last[1] = error["generation"]
                _show_error(root, error.get("text", ""))
        except Exception:
            pass
        root.after(300, keep)

    keep()


def hold(root):
    """Windows: keep showing what the window shows now while it is drawn
    again underneath -- new CSS rebuilds the screen, and the steps in
    between (the top of the screen, half the cards) are not for showing.
    Returns what release() needs."""
    if sys.platform != "win32":
        return None
    try:
        user32 = _user32()
        window = int(root.wm_frame(), 16)
        user32.SendMessageW(window, 0x000B, 0, 0)          # WM_SETREDRAW off
        return window
    except Exception:
        return None


def release(root, window):
    """Show what was drawn while held, all at once."""
    if not window:
        return
    try:
        user32 = _user32()
        user32.SendMessageW(window, 0x000B, 1, 0)          # WM_SETREDRAW on
        # INVALIDATE | ALLCHILDREN | FRAME: every part paints the new screen.
        user32.RedrawWindow(window, None, None, 0x0001 | 0x0080 | 0x0400)
        root.update()
    except Exception:
        pass


def _user32():
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32")      # its own argtypes, not the shared ones
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                    wintypes.LPARAM]
    user32.SendMessageW.restype = ctypes.c_ssize_t
    user32.RedrawWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p,
                                    wintypes.UINT]
    return user32


def _opaque(root):
    """-alpha leaves a window layered on Windows, even back at 1.0; a
    Previewer window is not, so the one a reload opens is not either."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32")      # its own argtypes, not the shared ones
    get = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
    put = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
    get.restype = put.restype = ctypes.c_ssize_t
    get.argtypes = [wintypes.HWND, ctypes.c_int]
    put.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    user32.RedrawWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p,
                                    wintypes.UINT]
    window = int(root.wm_frame(), 16)
    style = get(window, -20)                              # GWL_EXSTYLE
    if style & 0x00080000:                                # WS_EX_LAYERED
        put(window, -20, style & ~0x00080000)
        # INVALIDATE | ERASE | ALLCHILDREN | FRAME: draw it again, opaque.
        user32.RedrawWindow(window, None, None, 0x0001 | 0x0004 | 0x0080 | 0x0400)


def _error_line(text):
    """The line that names the error, and where it is, from a traceback."""
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "The new code stopped before it opened a window."
    where = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('File "') and ", line " in stripped:
            name = stripped[6:stripped.index('"', 6)]
            if "apkpy_lib" not in name and "<frozen" not in name:
                where = "%s, line %s" % (os.path.basename(name),
                                         stripped.split(", line ")[1].split(",")[0])
    return lines[-1].strip() + ("\n" + where if where else "")


def _show_error(root, text):
    import tkinter as tk
    old = getattr(root, "_apkpy_reload_error", None)
    if old is not None:
        try:
            old.destroy()
        except Exception:
            pass
    width = max(200, root.winfo_width())
    banner = tk.Frame(root, bg="#8C1D18", cursor="hand2")
    title = tk.Label(banner, text="Your change did not start", bg="#8C1D18", fg="#FFFFFF",
                     font=("Segoe UI", 10, "bold"), anchor="w", justify="left")
    body = tk.Label(banner, text=_error_line(text) + "\n\nThe window still runs the last "
                    "version. The terminal has the whole error; save again to retry.",
                    bg="#8C1D18", fg="#FFDAD6", font=("Segoe UI", 9), anchor="w",
                    justify="left", wraplength=width - 40)
    title.pack(fill="x", padx=16, pady=(12, 2))
    body.pack(fill="x", padx=16, pady=(0, 12))
    banner.place(x=0, y=0, relwidth=1)
    banner.lift()
    root._apkpy_reload_error = banner

    def close(_event=None):
        banner.destroy()
        root._apkpy_reload_error = None

    for widget in (banner, title, body):
        widget.bind("<Button-1>", close)


# -- In the watching Python ---------------------------------------------------

def _is_run(statement):
    if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
        return False
    func = statement.value.func
    if isinstance(func, ast.Name):
        return func.id == "run"
    return (isinstance(func, ast.Attribute) and func.attr == "run"
            and isinstance(func.value, ast.Name) and func.value.id in ("apkpy_lib", "apkpy"))


def _is_main_test(test):
    if (not isinstance(test, ast.Compare) or len(test.ops) != 1
            or not isinstance(test.ops[0], ast.Eq)):
        return False
    sides = (test.left, test.comparators[0])
    return (any(isinstance(side, ast.Name) and side.id == "__name__" for side in sides)
            and any(isinstance(side, ast.Constant) and side.value == "__main__"
                    for side in sides))


def calls_run(source):
    """Whether a script opens the Previewer itself: run(...) at the top of
    the file or under ``if __name__ == "__main__":``, there or in a function
    of the file called from there (``def main(): run(...)``)."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return False
    starters = {statement.name for statement in tree.body
                if isinstance(statement, ast.FunctionDef)
                and any(_is_run(inner) for inner in statement.body)}

    def starts(statement):
        if _is_run(statement):
            return True
        call = statement.value if isinstance(statement, ast.Expr) else None
        return (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id in starters and not call.args and not call.keywords)

    for statement in tree.body:
        if starts(statement):
            return True
        if isinstance(statement, ast.If) and _is_main_test(statement.test):
            if any(starts(inner) for inner in statement.body):
                return True
    return False


def _off():
    return os.environ.get("APKPY_RELOAD", "").strip().lower() in ("0", "false", "no", "off")


def _script():
    """The app's script when this Python should watch it, else None."""
    if _off() or os.environ.get("APKPY_HEADLESS_CORE", "").strip() == "1":
        return None
    if getattr(sys, "frozen", False) or sys.flags.interactive:
        return None
    main = sys.modules.get("__main__")
    path = getattr(main, "__file__", None)
    if not path or getattr(main, "__spec__", None) is not None or not path.endswith(".py"):
        return None
    if not sys.argv or os.path.abspath(sys.argv[0]) != os.path.abspath(path):
        return None
    if sys.stderr is None or sys.stderr is not sys.__stderr__:
        return None
    try:
        with tokenize.open(path) as handle:
            source = handle.read()
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None
    return os.path.abspath(path) if calls_run(source) else None


def snapshot(folder):
    """{path: (mtime, size)} of the .py files in the folder and in the
    folders directly inside it."""
    files = {}
    inside = []
    try:
        entries = list(os.scandir(folder))
    except OSError:
        return files
    for entry in entries:
        try:
            if entry.is_file() and entry.name.endswith(".py"):
                info = entry.stat()
                files[entry.path] = (info.st_mtime_ns, info.st_size)
            elif (entry.is_dir() and not entry.name.startswith(".")
                  and entry.name not in _NOT_THE_APP):
                inside.append(entry.path)
        except OSError:
            pass
    for directory in inside[:64]:
        try:
            for entry in os.scandir(directory):
                if entry.name.endswith(".py") and entry.is_file():
                    info = entry.stat()
                    files[entry.path] = (info.st_mtime_ns, info.st_size)
        except OSError:
            pass
    return files


def style_change(old, new):
    """The new CSS when the only difference between two versions of a
    script is the text given to ``style``; None otherwise."""
    try:
        before, after = ast.parse(old), ast.parse(new)
    except (SyntaxError, ValueError, TypeError):
        return None

    def take_css(tree):
        found = []
        for node in tree.body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "style"
                    and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
                found.append(node.value.value)
                node.value = ast.Constant(value="", kind=None)
        return found

    old_css, new_css = take_css(before), take_css(after)
    if not new_css or old_css == new_css or ast.dump(before) != ast.dump(after):
        return None
    return new_css[-1]


def _source(path):
    try:
        with tokenize.open(path) as handle:
            return handle.read()
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None


class _Run:
    """One Python running the app, or waiting as a spare to run it."""

    def __init__(self, argv, state, generation, out, extra=None):
        self.state, self.generation, self.out = state, generation, out
        env = dict(os.environ)
        env.update(extra or {})
        env[_DIR], env[_GEN], env[_PARENT] = state, str(generation), str(os.getpid())
        env.setdefault("PYTHONIOENCODING", "utf-8")
        self.encoding = env["PYTHONIOENCODING"].split(":")[0] or "utf-8"
        self.tail = collections.deque(maxlen=80)
        self.process = subprocess.Popen(argv, env=env, stderr=subprocess.PIPE)
        if generation == 1 and sys.platform == "win32":
            # The first window comes to the front, as it did in one Python.
            try:
                import ctypes
                ctypes.windll.user32.AllowSetForegroundWindow(self.process.pid)
            except Exception:
                pass
        self.pump = threading.Thread(target=self._pump, daemon=True)
        self.pump.start()

    def _pump(self):
        for raw in iter(self.process.stderr.readline, b""):
            text = raw.decode(self.encoding, "replace").replace("\r\n", "\n")
            self.tail.append(text)
            try:
                self.out.write(text)
                self.out.flush()
            except Exception:
                pass
        self.process.stderr.close()

    def ready(self):
        return os.path.exists(os.path.join(self.state, "ready-%d" % self.generation))

    def go(self):
        """A spare: run the app now (it does as soon as it has loaded)."""
        with open(os.path.join(self.state, "go-%d" % self.generation), "w") as handle:
            handle.write("go")

    def exited(self):
        return self.process.poll() is not None

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def error(self):
        self.pump.join(2)
        return "".join(self.tail)


def _say(out, text):
    try:
        out.write("[ApkPy] " + text + "\n")
        out.flush()
    except Exception:
        pass


def _restyle(state, number, css, seconds=2.0):
    """Hand new CSS to the open window; True once it has drawn it."""
    path = os.path.join(state, _COMMAND)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump({"id": number, "style": css}, handle)
    os.replace(temporary, path)
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            with open(os.path.join(state, _DONE), encoding="utf-8") as handle:
                done = json.load(handle)
            if done.get("id") == number:
                return bool(done.get("ok"))
        except (OSError, ValueError):
            pass
        time.sleep(0.02)
    return False


def supervise(script, argv=None, out=None, interval=0.1, stop=None, spares=True):
    """Run the app and start it again on each save; returns the exit code
    the app closed with. *stop* (a threading.Event) is for the tests."""
    out = out or sys.stderr
    script = os.path.abspath(script)
    folder = os.path.dirname(script)
    flags = getattr(subprocess, "_args_from_interpreter_flags", lambda: [])()
    if argv is None:
        argv, app_argv = [sys.executable] + flags + list(sys.argv), list(sys.argv)
    else:
        app_argv = list(argv[1:])
    spare_argv = [argv[0]] + flags + ["-c", _SPARE_BOOT]
    spare_env = {_SPARE: script, _HOME: folder, _ARGV: json.dumps(app_argv)}
    state = tempfile.mkdtemp(prefix="apkpy-reload-")
    _say(out, "The Previewer reloads when you save a .py file in this folder "
              "(APKPY_RELOAD=0 turns this off).")
    generation = [0]
    settle = interval      # one look with nothing new: the editor has finished writing
    # ApkPy's own files, when the app sits beside them (working on ApkPy).
    engine = os.path.normcase(os.path.dirname(os.path.abspath(__file__)) + os.sep)

    def start():
        generation[0] += 1
        return _Run(argv, state, generation[0], out)

    def make_spare():
        generation[0] += 1
        return _Run(spare_argv, state, generation[0], out, extra=spare_env)

    live, pending, spare = None, start(), None
    spare_failures = 0
    seen = snapshot(folder)
    started = seen                       # the files as the newest app read them
    live_source = pending_source = _source(script)
    changed_at = None
    restyles = 0
    try:
        while stop is None or not stop.is_set():
            time.sleep(interval)
            now = snapshot(folder)
            if now != seen:
                seen, changed_at = now, time.monotonic()
            elif changed_at is not None and time.monotonic() - changed_at >= settle:
                changed_at = None
                source = _source(script)
                touched = {path for path in set(now) | set(started)
                           if now.get(path) != started.get(path)}
                only_the_script = touched <= {script}
                if (only_the_script and pending is None and live is not None
                        and source == live_source
                        and not os.path.exists(os.path.join(state, _ERROR))):
                    started = now                # saved again, nothing new
                    continue
                css = None
                if only_the_script and pending is None and live is not None:
                    css = style_change(live_source, source)
                if css is not None:
                    restyles += 1
                    if _restyle(state, restyles, css):
                        live_source, started = source, now
                        _say(out, "New CSS applied.")
                        continue
                if pending is not None:
                    pending.stop()
                if spare is not None and any(os.path.normcase(path).startswith(engine) for path in touched):
                    spare.stop()             # it has ApkPy as it was before the save
                    spare = None
                if spare is not None and not spare.exited():
                    spare.go()               # it starts as soon as it has loaded
                    pending, spare = spare, None
                else:
                    spare = None
                    pending = start()
                pending_source, started = source, now
            if pending is not None:
                if pending.ready():
                    if live is not None:
                        live.stop()
                        _say(out, "Reloaded.")
                    live, pending, live_source = pending, None, pending_source
                    try:
                        os.remove(os.path.join(state, _ERROR))
                    except OSError:
                        pass
                elif pending.exited():
                    text = pending.error()
                    failed, pending = pending, None
                    if live is not None:
                        _write_error(state, failed.generation, text)
                        _say(out, "The change did not start; the window keeps the last "
                                  "version. Save again to retry.")
                    else:
                        _say(out, "The app did not start. Save again to retry, or "
                                  "Ctrl+C to stop.")
            if live is not None and live.exited():
                code = live.process.returncode
                live = None
                if code == 0:
                    return 0            # the window was closed
                _say(out, "The app stopped (exit code %s). Save again to start it, or "
                          "Ctrl+C to stop." % code)
            if spare is not None and spare.exited():
                spare, spare_failures = None, spare_failures + 1
            # The next save's Python, loaded while nothing else is starting.
            if (spares and spare is None and pending is None and live is not None
                    and spare_failures < 2):
                spare = make_spare()
        return 0
    except KeyboardInterrupt:
        return 130
    finally:
        for run in (spare, pending, live):
            if run is not None:
                run.stop()
        _clean(state)


def _write_error(state, generation, text):
    path = os.path.join(state, _ERROR)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump({"generation": generation, "text": text}, handle)
    os.replace(temporary, path)


def _clean(state):
    for name in os.listdir(state) if os.path.isdir(state) else ():
        try:
            os.remove(os.path.join(state, name))
        except OSError:
            pass
    try:
        os.rmdir(state)
    except OSError:
        pass


def start():
    """Called first thing by ``import apkpy_lib``. In the app's Python it
    only notes that the watcher started it; in the Python that ran
    ``writehere.py`` it becomes the watcher and does not come back."""
    _take_child_env()
    if _child is not None:
        return
    script = _script()
    if script is not None:
        sys.exit(supervise(script))
