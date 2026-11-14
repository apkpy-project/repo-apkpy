"""Test driver for ApkPy's hot reload (dev machine only; see test_hot_reload_* in test_tools.py).

Loaded by every Python that ApkPy's reload starts (PYTHONPATH points here),
and active only with APKPYGAME_RELOAD_LOG set: when the Previewer's window
runs, it presses Play, waits for the embedded game to draw, and writes
"playing PYTHON_PID JAVA_PID" to that file.
"""
import os

LOG = os.environ.get("APKPYGAME_RELOAD_LOG")


def _debug(text):
    if os.environ.get("APKPYGAME_RELOAD_DEBUG"):
        with open(LOG + ".debug", "a", encoding="utf-8") as fh:
            fh.write("%d %s\n" % (os.getpid(), text))


if LOG:
    import tkinter as tk

    def _texts(widget, out):
        for child in widget.winfo_children():
            try:
                text = child.cget("text")
                if text:
                    out.append((text, child))
            except tk.TclError:
                pass
            if isinstance(child, tk.Canvas):
                for item in child.find_all():
                    try:
                        text = child.itemcget(item, "text")
                        if text:
                            out.append((text, child))
                    except tk.TclError:
                        pass
            _texts(child, out)
        return out

    def _drive(root):
        report = root.report_callback_exception

        def failed(kind, error, tb):
            import traceback
            _debug("callback error: " + "".join(traceback.format_exception(kind, error, tb))[-1500:])
            report(kind, error, tb)
        root.report_callback_exception = failed

        def press():
            found = _texts(root, [])
            _debug("press: %s" % [(t, w.winfo_ismapped()) for t, w in found][:6])
            for text, w in found:
                if text.strip().lower() in ("jogar", "play") and w.winfo_ismapped():
                    w.event_generate("<ButtonPress-1>", x=5, y=5)
                    w.event_generate("<ButtonRelease-1>", x=5, y=5)
                    root.after(200, wait)
                    return
            root.after(200, press)

        def wait():
            from apkpy_lib.game import desktop
            game = desktop.current()
            if game is None or game.shown < 10:
                root.after(100, wait)
                return
            with open(LOG, "a", encoding="utf-8") as fh:
                fh.write("playing %d %d\n" % (os.getpid(), game.proc.pid))

        root.after(1000, press)

    _mainloop = tk.Misc.mainloop

    def mainloop(self, n=0):
        root = self._root()
        _debug("mainloop root=%s armed=%s" % (root, getattr(root, "_reload_driver", False)))
        if not getattr(root, "_reload_driver", False):       # once per window (a spare Python makes its own)
            root._reload_driver = True
            _drive(root)
        return _mainloop(self, n)

    tk.Misc.mainloop = mainloop
    _debug("loaded")
