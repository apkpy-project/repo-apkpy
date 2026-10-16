"""Preview-only static wallpaper confirmation. Never changes the host desktop."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, urlparse
import os

from ..core.features.wallpaper import REASONS, TARGETS

__all__ = ["WallpaperAPI", "wallpaper"]
_IO = ThreadPoolExecutor(max_workers=1, thread_name_prefix="apkpy-wallpaper")


def _load_image(source):
    from PIL import Image, ImageOps

    if not isinstance(source, str) or not source:
        raise ValueError("Choose a local image first")
    if source.startswith("file://"):
        source = unquote(urlparse(source).path)
        if os.name == "nt" and source.startswith("/") and len(source) > 2 and source[2] == ":":
            source = source[1:]
    elif "://" in source:
        raise ValueError("The desktop Previewer requires a local image")
    with Image.open(Path(source)) as original:
        # Refuse decompression bombs. JPEG draft reduces allocation before load.
        if original.width * original.height > 64_000_000:
            raise ValueError("Preview image exceeds 64 megapixels")
        original.draft("RGB", (2048, 2048))
        original.thumbnail((2048, 2048))
        image = ImageOps.exif_transpose(original).convert("RGB")
    return image


class WallpaperAPI:
    """Static wallpaper API for Android (API 24+).

    ``set(source, target="home", on_result=None)`` always shows a confirmation.
    ``target`` is ``home``, ``lock`` or ``both``. ``on_result(success, reason)``
    runs on the UI thread; desktop success is explicitly ``simulated``.
    Use a path from ``gallery.pick``/``files.pick`` or a literal image filename.
    No remote downloads, wallpaper reading, silent mode or live wallpapers.
    """
    reasons = REASONS

    def __init__(self):
        self._request = None

    def available(self):
        """True in Previewer simulation; Android checks support and policy."""
        return True

    def set(self, source, target="home", on_result=None):
        from ..ui import live_preview_root

        if on_result is not None and not callable(on_result):
            raise TypeError("wallpaper.set on_result must accept (success, reason)")
        if target not in TARGETS:
            _answer(on_result, False, "invalid_target")
            return
        root = live_preview_root()
        if root is None:
            _answer(on_result, False, "unavailable")
            return
        if self._request is not None:
            _answer(on_result, False, "busy")
            return
        request = _PreviewRequest(self, root, source, target, on_result)
        self._request = request
        request.start()


def _answer(callback, success, reason):
    # Do not catch TypeError from user callbacks and accidentally call them twice.
    if callback is not None:
        callback(success, reason)


class _PreviewRequest:
    def __init__(self, owner, root, source, target, callback):
        self.owner, self.root = owner, root
        self.source, self.target, self.callback = source, target, callback
        self.window = None
        self.photo = None
        self.finished = False
        self.future = None
        self._destroy_binding = None

    def start(self):
        self._destroy_binding = self.root.bind("<Destroy>", self._root_destroyed, add="+")
        self.future = _IO.submit(_load_image, self.source)
        self.root.after(30, self.poll)

    def _root_destroyed(self, event):
        if event.widget is self.root:
            self.finish(False, "cancelled", notify=False)

    def poll(self):
        if self.finished:
            return
        if not self.future.done():
            self.root.after(30, self.poll)
            return
        try:
            image = self.future.result()
        except Exception:
            self.finish(False, "invalid_image")
            return
        try:
            self.show(image)
        except Exception:
            self.finish(False, "unavailable")

    def show(self, image):
        import tkinter as tk
        from PIL import ImageTk
        from .. import ui

        tokens = ui.global_styles.get("__theme__", {})
        bg = tokens.get("surface", "#181B24")
        fg = tokens.get("text", "#F4F5F7")
        muted = tokens.get("text_secondary", "#ADB5C6")
        accent = tokens.get("primary", "#7856FF")
        self.window = tk.Toplevel(self.root)
        self.window.title("Wallpaper - Preview simulation")
        self.window.transient(self.root)
        self.window.configure(bg=bg, padx=20, pady=16)
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", lambda: self.finish(False, "cancelled"))
        self.window.bind("<Escape>", lambda event: self.finish(False, "cancelled"))
        tk.Label(self.window, text="Set wallpaper", bg=bg, fg=fg,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=(0, 10))
        image.thumbnail((280, 280))
        self.photo = ImageTk.PhotoImage(image, master=self.window)
        tk.Label(self.window, image=self.photo, bg=bg).pack(fill="x")
        target = {"home": "home screen", "lock": "lock screen", "both": "home and lock screens"}[self.target]
        tk.Label(self.window, text="Apply to " + target + ".\nAndroid may crop or zoom the image.",
                 bg=bg, fg=fg, justify="left", wraplength=300).pack(anchor="w", pady=(12, 8))
        tk.Label(self.window, text="SIMULATION - your computer wallpaper will not change.",
                 bg=bg, fg=muted, justify="left", wraplength=300).pack(anchor="w", pady=(0, 12))
        actions = tk.Frame(self.window, bg=bg)
        actions.pack(fill="x")
        tk.Button(actions, text="Cancel", command=lambda: self.finish(False, "cancelled"),
                  bg=bg, fg=fg, padx=16, pady=8).pack(side="left")
        tk.Button(actions, text="Simulate apply", command=lambda: self.finish(True, "simulated"),
                  bg=accent, fg="#FFFFFF", padx=16, pady=8).pack(side="right")
        self.window.grab_set()

    def finish(self, success, reason, notify=True):
        if self.finished:
            return
        self.finished = True
        self.owner._request = None
        callback, self.callback = self.callback, None
        if self.future is not None:
            self.future.cancel()
        if self._destroy_binding is not None:
            try:
                self.root.unbind("<Destroy>", self._destroy_binding)
            except Exception:
                pass
        if self.window is not None:
            try:
                self.window.grab_release()
                self.window.destroy()
            except Exception:
                pass
        self.photo = None
        if notify:
            _answer(callback, success, reason)


wallpaper = WallpaperAPI()
