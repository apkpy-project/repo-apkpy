"""The game inside ApkPy's REAL Previewer, automatically (dev machine only):

    python src/tools/preview_embedded.py PROJECT

PROJECT is a copy of src/examples/menus (pytest passes one in tmp). Runs its
writehere.py in ApkPy's own Previewer, with the real apkpygame.desktop (the
embedded mode is the default there). A driver on Tk's loop presses Play,
taps the stars, presses Back (Alt+Left: the game's on_back opens the ApkPy
pause screen), presses Continue, presses the game's Done button, checks the
results screen, then plays again and destroys the window (as a hot reload
does) to check the Java process goes with it. Prints one JSON line at the end.
"""
import json
import os
import runpy
import sys
import time
import tkinter as tk

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # ApkPy's repository
TOOLS = os.path.join(ROOT, "tools", "game")
SRC = ROOT
sys.path.insert(0, ROOT)
from apkpy_lib.game import desktop  # noqa: E402

PROJECT = os.path.abspath(sys.argv[1])
log = {"answers": [], "toplevels": 0, "frames": 0, "pause_screen": False, "results_screen": False,
       "java_ended_with_the_window": False, "steps": []}
_ended = desktop._ended


def spy(done):
    ended = _ended(done)

    def answer(value):
        log["answers"].append(json.loads(value))
        ended(value)
    return answer


desktop._ended = spy


def texts(widget, out):
    for child in widget.winfo_children():
        try:
            t = child.cget("text")
            if t:
                out.append((t, child))
        except tk.TclError:
            pass
        if isinstance(child, tk.Canvas):
            for item in child.find_all():
                try:
                    t = child.itemcget(item, "text")
                    if t:
                        out.append((t, child))
                except tk.TclError:
                    pass
        texts(child, out)
    return out


def shown(root, *words):
    """One of ``words`` is on a widget the window shows (not under the game)."""
    return any(t.strip().lower() in [w.lower() for w in words] and w.winfo_ismapped() for t, w in texts(root, []))


def click(root, *words):
    for t, w in texts(root, []):
        if t.strip().lower() in [x.lower() for x in words] and w.winfo_ismapped():
            x, y = w.winfo_width() // 2, w.winfo_height() // 2
            w.event_generate("<ButtonPress-1>", x=x, y=y)
            w.event_generate("<ButtonRelease-1>", x=x, y=y)
            log["steps"].append("click " + t)
            return True
    log["steps"].append("not found: %s" % (words,))
    return False


def game_point(vx, vy):
    """A point of the game's 360x640 virtual screen, in the Label's pixels (the engine's "fit")."""
    g = desktop.current()
    scale = min(g.w / 360, g.h / 640)
    return int((g.w - 360 * scale) / 2 + vx * scale), int((g.h - 640 * scale) / 2 + vy * scale)


def tap(vx, vy, up=True):
    g = desktop.current()
    x, y = game_point(vx, vy)
    g.label.event_generate("<ButtonPress-1>", x=x, y=y)
    if up:
        g.label.event_generate("<ButtonRelease-1>", x=x, y=y)


def when(root, cond, then, timeout=30.0, what=""):
    """Runs then() once cond() holds; fails the run after timeout seconds."""
    end = time.time() + timeout

    def check():
        try:
            ok = cond()
        except Exception:
            ok = False
        if ok:
            log["steps"].append("ok " + what)
            then()
        elif time.time() > end:
            log["steps"].append("timeout " + what)
            root.quit()
        else:
            root.after(50, check)
    check()


def driver(root):
    root.attributes("-topmost", True)

    def playing(min_frames=20):
        g = desktop.current()
        return g is not None and g.label.winfo_ismapped() and g.shown >= min_frames

    def start():
        click(root, "Jogar", "Play")
        when(root, playing, sweep, what="game shown")

    def sweep(i=0):
        log["toplevels"] += len([w for w in root.winfo_children() if isinstance(w, tk.Toplevel)])
        tap(20 + (i % 8) * 46, 140 + (i // 8) * 45)
        if i < 80:
            root.after(25, sweep, i + 1)
        else:
            root.after(300, back)

    def back():
        g = desktop.current()
        log["frames"] = g.shown
        g.label.focus_force()
        g.label.event_generate("<Alt-Left>", when="tail")       # the Previewer's Back
        when(root, lambda: shown(root, "Em pausa", "Paused"), paused, what="pause screen")

    def paused():
        log["pause_screen"] = True
        click(root, "Continuar", "Continue")
        when(root, lambda: playing(log["frames"] + 10), done, what="game shown again")

    def done():
        tap(180, 600, up=False)                                   # the game's Done button
        when(root, lambda: shown(root, "Muito bem!", "Well played!"), results, what="results screen")

    def results():
        log["results_screen"] = True
        click(root, "Menu")
        root.after(500, again)

    def again():
        click(root, "Jogar", "Play")
        when(root, playing, close, what="second game shown")

    def close():
        log["java"] = desktop.current().proc
        root.destroy()                                            # the window goes, as in a hot reload

    root.after(500, start)
    root.after(90000, root.quit)


_mainloop = tk.Misc.mainloop


def mainloop(self, n=0):
    if not getattr(tk, "_driver_started", False):
        tk._driver_started = True
        driver(self)
    return _mainloop(self, n)


tk.Misc.mainloop = mainloop
os.environ["APKPY_RELOAD"] = "0"
os.environ.pop("APKPYGAME_PREVIEW", None)
os.chdir(PROJECT)
sys.argv = [os.path.join(PROJECT, "writehere.py")]
try:
    runpy.run_path(sys.argv[0], run_name="__main__")
except SystemExit:
    pass
java = log.pop("java", None)
if java is not None:
    try:
        java.wait(timeout=5)
        log["java_ended_with_the_window"] = True
    except Exception:
        java.kill()
print(json.dumps(log))
