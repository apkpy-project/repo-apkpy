"""The game inside the ApkPy Previewer's own window (no second window).

The Java engine runs with --embed (no window of its own). Its frames come
through a pipe and are shown in one Label placed over the whole Previewer
window, as GameActivity covers the whole phone screen (immersive). Mouse,
keys and Back go back to the engine on its stdin. On open_app the Label
hides and the ApkPy screen shows; resume() puts it back. The protocol is in
src/java/platform-desktop/apkpygame/desktop/Embed.java; Dev machine only (the ApkPy build ignores preview=).
"""
import json
import os
import queue
import struct
import subprocess
import threading
import tkinter as tk

from PIL import Image, ImageTk

from . import _host as compat

# Tk keysym -> the engine's key names (the same names as the desktop window, Main.keyName)
KEYS = {"Left": "left", "Right": "right", "Up": "up", "Down": "down", "space": "space", "Return": "enter"}


def _orientation(bundle):
    try:
        with open(os.path.join(bundle, "game.json"), encoding="utf-8") as fh:
            return json.load(fh).get("orientation", "portrait")
    except (OSError, ValueError):
        return "portrait"



def _read_exactly(f, n):
    """n bytes from the engine's pipe. An unbuffered pipe gives what it has, which can be less than a whole frame
    (Python 3.8 on Windows does, often): so it reads until it has them all. EOFError when the engine has ended."""
    parts, left = [], n
    while left:
        part = f.read(left)
        if not part:
            raise EOFError
        parts.append(part)
        left -= len(part)
    return b"".join(parts)

class EmbeddedGame:
    """One run of the engine, drawn in ``root``. ``ended(json)`` is called on Tk's
    thread with each answer (protocol v1): a suspended run waits for resume()."""

    def __init__(self, root, command, bundle, ended):
        self.root, self.ended = root, ended
        self.orientation = _orientation(bundle)
        self.upright = None                         # the window's shape before the game turned it
        self._turn()
        self.w, self.h = compat.window_shape(root)
        self.label = tk.Label(root, bd=0, highlightthickness=0, bg="black", takefocus=1, cursor="hand2")
        self.inbox = queue.Queue()
        self.frame = None                           # only the newest frame is kept
        self.frame_lock = threading.Lock()
        self.photo = None
        self.shown = 0
        self.held = set()
        self.closed = False
        self.proc = subprocess.Popen(command(self.w, self.h), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     bufsize=0)
        threading.Thread(target=self._read, daemon=True).start()
        self._bind()
        self._show()
        self._tick()

    # ── on screen ────────────────────────────────────────────────────────────

    def _show(self):
        self.label.place(x=0, y=0, relwidth=1, relheight=1)
        self.label.lift()
        self.label.focus_set()

    def _hide(self):
        self.label.place_forget()
        self._unturn()

    def _turn(self):
        """A landscape game turns the Previewer's phone, as GameActivity does on the phone."""
        w, h = compat.window_shape(self.root)
        if self.orientation == "landscape" and h > w:
            self.upright = (w, h)
            compat.window_shape(self.root, (h, w))

    def _unturn(self):
        if self.upright is not None:
            compat.window_shape(self.root, self.upright)
            self.upright = None

    # ── input ────────────────────────────────────────────────────────────────

    def send(self, line):
        try:
            self.proc.stdin.write((line + "\n").encode())
            self.proc.stdin.flush()
        except (OSError, ValueError):
            pass

    def _bind(self):
        lab = self.label
        for ev, kind in (("<ButtonPress-1>", "down"), ("<B1-Motion>", "move"), ("<ButtonRelease-1>", "up")):
            lab.bind(ev, lambda e, k=kind: self._pointer(k, e))
        lab.bind("<KeyPress>", self._key_down)
        lab.bind("<KeyRelease>", self._key_up)
        # Back: the Previewer's Alt+Left, and Escape as in the desktop window. "break"
        # stops the Previewer's own Back (bind_all) from navigating under the game.
        keys = compat.preview_keys()
        for ev in keys["back"] + ("<Escape>",):
            lab.bind(ev, lambda e: (self.send("back"), "break")[1])
        # Turning the device: only a game with orientation "any" follows it (GameActivity holds the others)
        for ev in keys["turn"]:
            lab.bind(ev, lambda e: None if self.orientation == "any" else "break")
        lab.bind("<Configure>", self._resized)
        lab.bind("<Destroy>", self._destroyed)

    def _pointer(self, kind, e):
        if kind == "down":
            self.label.focus_set()
        self.send("%s 0 %d %d" % (kind, e.x, e.y))

    @staticmethod
    def _key(e):
        if e.keysym in KEYS:
            return KEYS[e.keysym]
        k = e.keysym.lower()
        return k if len(k) == 1 and k.isalnum() else None

    def _key_down(self, e):
        k = self._key(e)
        if k is not None and k not in self.held:        # the key's auto-repeat is one press
            self.held.add(k)
            self.send("key down " + k)

    def _key_up(self, e):
        k = self._key(e)
        if k is not None:
            self.held.discard(k)
            self.send("key up " + k)

    def _resized(self, e):
        if (e.width, e.height) != (self.w, self.h) and e.width > 1 and e.height > 1:
            self.w, self.h = e.width, e.height
            self.send("resize %d %d" % (self.w, self.h))

    def _destroyed(self, e):
        """The Previewer's window went away (closed, or replaced by a hot reload): the engine goes too."""
        if e.widget is self.label:
            self.closed = True
            self.send("quit")
            proc = self.proc

            def reap():
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
            threading.Thread(target=reap, daemon=True).start()

    # ── output ───────────────────────────────────────────────────────────────

    def _read(self):
        f = self.proc.stdout
        try:
            while True:
                kind = _read_exactly(f, 1)
                if kind == b"F":
                    w, h = struct.unpack(">ii", _read_exactly(f, 8))
                    data = _read_exactly(f, w * h * 3)
                    with self.frame_lock:
                        self.frame = (w, h, data)
                elif kind == b"R":
                    (n,) = struct.unpack(">i", _read_exactly(f, 4))
                    self.inbox.put(_read_exactly(f, n).decode("utf-8"))
        except EOFError:
            pass
        self.inbox.put(None)                            # the engine ended

    def _tick(self):
        if self.closed:
            return
        with self.frame_lock:
            frame, self.frame = self.frame, None
        if frame is not None:
            w, h, data = frame
            img = Image.frombuffer("RGB", (w, h), data, "raw", "BGR", 0, 1)
            if self.photo is None or self.photo.width() != w or self.photo.height() != h:
                self.photo = ImageTk.PhotoImage(img)
                self.label.configure(image=self.photo)
            else:
                self.photo.paste(img)
            self.shown += 1
            if self.shown % 30 == 0 and self.label.winfo_ismapped():
                self.label.lift()                       # over anything the Previewer raised since
        try:
            while True:
                answer = self.inbox.get_nowait()
                if answer is None:
                    answer = ('{"v":1,"action":"error","error":{"code":"G3998",'
                              '"message":"the desktop runner gave no answer"}}')
                    self._answer(answer)
                    return
                self._answer(answer)
                if self.closed:
                    return
        except queue.Empty:
            pass
        self.root.after(8, self._tick)

    def _answer(self, value):
        if '"suspended":true' in value:
            self.held.clear()
            self._hide()
            self.ended(value)
            return
        self.close()
        if '"action":"error"' in value:
            try:
                error = json.loads(value).get("error", {})
            except ValueError:
                error = {}
            show_error(self.root, error.get("code", "G3999"), error.get("message", value), error.get("fix"),
                       lambda: self.ended(value))
        else:
            self.ended(value)

    # ── lifecycle ────────────────────────────────────────────────────────────

    def alive(self):
        return not self.closed and self.proc.poll() is None

    def resume(self, ended):
        self.ended = ended
        self._turn()
        self._show()
        self.send("resume")

    def close(self):
        if not self.closed:
            self.send("quit")
            self.closed = True
        self._unturn()
        try:
            self.label.destroy()
        except tk.TclError:
            pass


def show_error(root, code, message, fix, then):
    """An error where the game would be (a build error G1xxx/G2xxx or a runtime one).
    A tap closes it, then ``then()`` hands the error answer to the app."""
    panel = tk.Frame(root, bg="#1e1e1e", cursor="hand2")
    lines = [message]
    if fix:
        lines += [""] + (["Fix: " + f for f in fix] if isinstance(fix, list) else ["Fix: " + str(fix)])
    tk.Label(panel, text=code, bg="#1e1e1e", fg="#ff6b6b", font=("Arial", 16, "bold")).pack(
        anchor="w", padx=16, pady=(32, 8))
    body = tk.Label(panel, text="\n".join(lines), bg="#1e1e1e", fg="#f0f0f0", justify="left", anchor="nw",
                    font=("Consolas", 10), wraplength=max(200, compat.window_shape(root)[0] - 32))
    body.pack(fill="both", expand=True, padx=16)
    tk.Label(panel, text="Tap to close", bg="#1e1e1e", fg="#9a9a9a", font=("Arial", 10)).pack(pady=16)
    panel.place(x=0, y=0, relwidth=1, relheight=1)
    panel.lift()
    panel.focus_set()

    def close(_e=None):
        if panel.winfo_exists():
            panel.destroy()
            then()
    for w in [panel] + panel.winfo_children():
        w.bind("<ButtonRelease-1>", close)
    panel.bind("<Escape>", close)
    return panel
