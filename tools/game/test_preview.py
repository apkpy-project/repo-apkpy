"""The Previewer path, automatically (dev machine only):

    python src/tools/test_preview.py

Under a Tk loop (like ApkPy's Previewer), the stress example's glue opens the
desktop runner through apkpygame.desktop.play(); the runner exits by itself
after 3 s. Checks: Tk stayed responsive, the answer came on Tk's thread with
protocol v1, and the headless state equals the one the phone printed.
"""
import os
import sys
import threading
import time
import tkinter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # ApkPy's repository
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import where  # noqa: E402
TOOLS = os.path.join(ROOT, "tools", "game")
SRC = ROOT
sys.path.insert(0, where.examples("stress", "app"))
os.environ["APKPYGAME_AUTOEXIT_MS"] = "3000"
from desktop import game  # noqa: E402  (the example's Previewer shim)

PHONE_STATE = "600:2954a8594f2d3007"     # printed by the phone (Parity check), 01/11/2026


class Done:
    def __init__(self, root):
        self.root, self.value, self.thread = root, None, None

    def run(self, ok, value):
        self.value, self.thread = (ok, value), threading.current_thread()
        self.root.after(100, self.root.quit)


def main():
    root = tkinter.Tk()
    ticks = [0]

    def tick():
        ticks[0] += 1
        root.after(20, tick)

    done = Done(root)
    start = time.time()
    root.after(0, tick)
    root.after(10, lambda: game.play("main", "{}", done))
    root.after(20000, root.quit)
    root.mainloop()
    elapsed = time.time() - start
    root.destroy()
    state = game.snapshot("main", "{}", 600)
    checks = [
        ("answer is an exit (protocol v1)", done.value is not None and '"v":1,"action":"exit"' in done.value[1]),
        ("answer on Tk's thread", done.thread is threading.main_thread()),
        ("Tk kept running (%d ticks in %.1fs)" % (ticks[0], elapsed), ticks[0] > elapsed * 15),
        ("PC state %s == phone %s" % (state, PHONE_STATE), state == PHONE_STATE),
        ("last_result kept for on_resume", '"action":"exit"' in game.last_result()),
    ]
    print("answer:", done.value)
    for name, ok in checks:
        print("  %s  %s" % ("ok  " if ok else "FAIL", name))
    sys.exit(0 if all(ok for _, ok in checks) else 1)


if __name__ == "__main__":
    main()
