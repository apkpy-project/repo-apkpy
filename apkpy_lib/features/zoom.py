"""The full-screen picture viewer, in the Previewer.

A black frame over the whole app with the picture fitted in it. The mouse
wheel zooms about the pointer (the phone's pinch), a double click zooms in
and back, a drag moves a zoomed picture, and a drag down on a fitted one
closes the viewer -- as do Escape and the cross in the corner. Where the
picture sits and how far it goes come from ``zoom_rules``, which ApkpyZoom
mirrors on the phone.
"""

import os
import threading
import time
import tkinter as tk

from .. import zoom_rules as rules

_FRAME_MS = 16
_active = [None]


class Viewer:
    """One open viewer."""

    def __init__(self, ui, raw, thumb=None, describe=''):
        self.ui = ui
        self.raw = raw                  # a PIL image, or None while it loads
        self.thumb_widget = thumb       # the widget the picture opens from
        self.describe = describe or ''
        self.zoom, self.x, self.y = rules.MIN_ZOOM, 0.0, 0.0
        self.drag_y = 0.0
        self.progress = 1.0             # 0 at the thumbnail, 1 open
        self.closed = False
        self._photo = None
        self._press = None
        self._job = None
        self._thumb = None

    # ── building ───────────────────────────────────────────────────────────

    def open(self):
        root = self.ui._app.root
        root.update_idletasks()
        if _active[0] is not None:
            _active[0].close(animate=False)
        _active[0] = self
        host = tk.Frame(root, bg=rules.BACKDROP)
        host.place(x=0, y=0, relwidth=1, relheight=1)
        host.lift()
        canvas = tk.Canvas(host, bg=rules.BACKDROP, highlightthickness=0, cursor='fleur')
        canvas.pack(fill='both', expand=True)
        self.host, self.canvas = host, canvas
        canvas.bind('<Configure>', lambda _e: self._laid_out())
        canvas.bind('<MouseWheel>', self._wheel)
        canvas.bind('<Button-4>', lambda e: self.wheel(e.x, e.y, 1))
        canvas.bind('<Button-5>', lambda e: self.wheel(e.x, e.y, -1))
        canvas.bind('<ButtonPress-1>', self._press_at)
        canvas.bind('<B1-Motion>', self._move)
        canvas.bind('<ButtonRelease-1>', self._release)
        canvas.bind('<Double-Button-1>', lambda e: self.double_tap(e.x, e.y))
        canvas.bind('<Escape>', lambda _e: self.close())
        canvas.focus_set()
        host.update_idletasks()
        self._laid_out(first=True)
        return self

    def size(self):
        return max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())

    def image_size(self):
        return self.raw.size if self.raw is not None else (0, 0)

    def _laid_out(self, first=False):
        if self.closed:
            return
        self._settle()
        if first and self.raw is not None and self.thumb_widget is not None:
            try:
                widget = self.thumb_widget
                self._thumb = (widget.winfo_rootx() - self.canvas.winfo_rootx(),
                               widget.winfo_rooty() - self.canvas.winfo_rooty(),
                               widget.winfo_width(), widget.winfo_height())
            except tk.TclError:
                self._thumb = None
            if self._thumb is not None:
                self._animate(0.0, 1.0, rules.OPEN_MS)
                return
        self.draw()

    def set_image(self, raw):
        """The picture arrived (it was loading)."""
        if self.closed:
            return
        self.raw = raw
        self.zoom, self.x, self.y = rules.MIN_ZOOM, 0.0, 0.0
        self._settle()
        self.draw()

    # ── the state, through the rules ───────────────────────────────────────

    def _settle(self):
        (iw, ih), (vw, vh) = self.image_size(), self.size()
        self.zoom, self.x, self.y = rules.place(self.zoom, self.x, self.y, iw, ih, vw, vh)

    def wheel(self, x, y, notches):
        """One or more notches of the wheel at (x, y): the pinch."""
        (iw, ih), (vw, vh) = self.image_size(), self.size()
        self.zoom, self.x, self.y = rules.zoom_at(
            self.zoom, self.x, self.y, x, y, rules.WHEEL_STEP ** notches, iw, ih, vw, vh)
        self.draw()

    def double_tap(self, x, y):
        (iw, ih), (vw, vh) = self.image_size(), self.size()
        target = rules.double_tap(self.zoom)
        self.zoom, self.x, self.y = rules.zoom_at(
            self.zoom, self.x, self.y, x, y, target / self.zoom, iw, ih, vw, vh)
        self._press = None
        self.draw()

    def drag(self, dx, dy):
        """Move by (dx, dy): a zoomed picture pans, a fitted one is pulled
        down to close."""
        (iw, ih), (vw, vh) = self.image_size(), self.size()
        if rules.can_dismiss(self.zoom):
            self.drag_y = max(0.0, self.drag_y + dy)
        else:
            self.zoom, self.x, self.y = rules.place(
                self.zoom, self.x + dx, self.y + dy, iw, ih, vw, vh)
        self.draw()

    def release(self):
        """Let go: pulled far enough, the viewer closes; else it goes back."""
        if self.drag_y <= 0:
            return 'open'
        if rules.dismisses(self.drag_y):
            self.close()
            return 'closed'
        self.drag_y = 0.0
        self.draw()
        return 'open'

    # ── the mouse ──────────────────────────────────────────────────────────

    def _wheel(self, event):
        self.wheel(event.x, event.y, 1 if event.delta > 0 else -1)

    def _on_close_button(self, x, y):
        left, top = rules.CLOSE_INSET, self._top_inset() + rules.CLOSE_INSET
        return left <= x <= left + rules.CLOSE and top <= y <= top + rules.CLOSE

    def _press_at(self, event):
        if self._on_close_button(event.x, event.y):
            self.close()
            return
        self._press = (event.x, event.y)

    def _move(self, event):
        if self._press is None:
            return
        dx, dy = event.x - self._press[0], event.y - self._press[1]
        self._press = (event.x, event.y)
        self.drag(dx, dy)

    def _release(self, _event):
        if self._press is not None:
            self._press = None
            self.release()

    # ── drawing ────────────────────────────────────────────────────────────

    def _top_inset(self):
        """The Previewer's status bar strip, which the close button clears."""
        return 24

    def draw(self):
        if self.closed:
            return
        canvas = self.canvas
        try:
            canvas.delete('all')
        except tk.TclError:
            return
        vw, vh = self.size()
        if self.raw is None:
            canvas.create_text(vw / 2, vh / 2, text='Loading…', fill='#9E9E9E',
                               font=('Segoe UI' if os.name == 'nt' else 'Helvetica', 11))
            self._draw_close()
            return
        iw, ih = self.image_size()
        scale = rules.fit(iw, ih, vw, vh) * self.zoom
        x, y = self.x, self.y + self.drag_y
        clip = (0, 0, vw, vh)
        if self.progress < 1.0 and self._thumb is not None:
            start = rules.thumb_start(self._thumb, iw, ih, vw, vh)
            t = self.progress
            scale = start[0] + (scale - start[0]) * t
            x = start[1] + (x - start[1]) * t
            y = start[2] + (y - start[2]) * t
            tx, ty, tw, th = self._thumb
            clip = (tx * (1 - t), ty * (1 - t),
                    tx + tw + (vw - tx - tw) * t, ty + th + (vh - ty - th) * t)
        self._paint(scale, x, y, clip)
        if self.progress >= 1.0:
            self._draw_close()

    def _paint(self, scale, x, y, clip):
        """Only the part of the picture that shows is resized."""
        from PIL import Image, ImageTk
        if scale <= 0:
            return
        iw, ih = self.image_size()
        left, top = max(clip[0], x), max(clip[1], y)
        right, bottom = min(clip[2], x + iw * scale), min(clip[3], y + ih * scale)
        width, height = int(round(right - left)), int(round(bottom - top))
        if width < 1 or height < 1:
            return
        box = ((left - x) / scale, (top - y) / scale, (right - x) / scale, (bottom - y) / scale)
        shown = self.raw.convert('RGB').resize((width, height), Image.BILINEAR, box=box)
        self._photo = ImageTk.PhotoImage(shown, master=self.canvas)
        self.canvas.create_image(int(round(left)), int(round(top)), image=self._photo, anchor='nw')

    def _draw_close(self):
        left = rules.CLOSE_INSET + (rules.CLOSE - rules.CLOSE_ICON) / 2.0
        top = self._top_inset() + rules.CLOSE_INSET + (rules.CLOSE - rules.CLOSE_ICON) / 2.0
        inset = rules.CLOSE_ICON * 0.25
        a, b = left + inset, left + rules.CLOSE_ICON - inset
        c, d = top + inset, top + rules.CLOSE_ICON - inset
        for line in ((a, c, b, d), (a, d, b, c)):
            self.canvas.create_line(*line, fill=rules.INK, width=2, capstyle='round')

    # ── opening and closing ────────────────────────────────────────────────

    def _animate(self, start, end, duration, then=None):
        began = time.time()

        def step():
            if self.closed:
                return
            t = min(1.0, (time.time() - began) * 1000.0 / max(1, duration))
            eased = 1 - (1 - t) ** 3
            self.progress = start + (end - start) * eased
            self.draw()
            if t < 1.0:
                self._job = self.canvas.after(_FRAME_MS, step)
            else:
                self._job = None
                if then:
                    then()
        step()

    def close(self, animate=True):
        if self.closed:
            return
        if animate and self._thumb is not None and self.raw is not None:
            self._animate(self.progress, 0.0, rules.CLOSE_MS, self._destroy)
            return
        self._destroy()

    def _destroy(self):
        self.closed = True
        if _active[0] is self:
            _active[0] = None
        try:
            self.host.destroy()
        except Exception:
            pass


def open_from(comp, widget, state):
    """A tap on image(..., zoom=True): the picture it already shows."""
    from .. import ui
    raw = (state or {}).get('raw')
    if raw is None or (state or {}).get('placeholder'):
        return None                       # nothing loaded yet: nothing to open
    viewer = Viewer(ui, raw, widget, comp.kwargs.get('describe') or '')
    comp._viewer = viewer
    return viewer.open()


def _asset_path(path):
    import __main__
    if os.path.isabs(path):
        return path
    try:
        base = os.path.dirname(os.path.abspath(__main__.__file__))
    except AttributeError:
        base = os.getcwd()
    return os.path.join(base, path)


def view(source, describe=''):
    """view_image(src): a file beside the app, or an address."""
    from .. import ui
    from PIL import Image
    source = str(source or '').strip()
    if not source:
        return None
    if not source.startswith(('http://', 'https://')):
        try:
            with Image.open(_asset_path(source)) as opened:
                raw = opened.copy()
        except Exception:
            ui.toast('Could not open ' + os.path.basename(source))
            return None
        return Viewer(ui, raw, None, describe).open()

    viewer = Viewer(ui, None, None, describe).open()
    root = ui._app.root

    def fetch():
        try:
            import io
            import urllib.request
            request = urllib.request.Request(source, headers={'User-Agent': 'ApkPyPreviewer'})
            with urllib.request.urlopen(request, timeout=15) as response:
                raw = Image.open(io.BytesIO(response.read()))
                raw.load()
        except Exception:
            raw = None
        try:
            root.after(0, lambda: viewer.set_image(raw) if raw is not None else viewer.close(False))
        except Exception:
            pass

    threading.Thread(target=fetch, daemon=True).start()
    return viewer


def active():
    return _active[0]
