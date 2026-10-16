# -*- coding: utf-8 -*-
"""What the Previewer draws when an app reaches past itself.

On the phone ``phone.dial()`` puts the dialler in front of the app, and
``calendar.add_event()`` the calendar. A desk has neither, so the Previewer
draws the moment instead: a sheet that rises over the app and says, in the
other app's own terms, what it was handed -- the number, the event, the
message -- and goes away when the person "comes back".

Two shapes:

* :class:`Handover` -- the sheet. A badge with the other app's icon, its
  name, what it was given, and one way back. ``speech.listen()`` uses the
  same sheet with a field to type what would have been said, and
  ``recorder.start()`` with the three answers Android offers when it asks
  for the microphone.
* :func:`caption` -- a line of text over the bottom of the screen, for the
  voice the desk does not have.

Both take their colours and their typeface from the app's ``Theme``, so they
look like part of the phone the app is running on rather than like a debug
window. The measurements are the bottom sheet's own (``sheet_rules``).
"""
from __future__ import annotations

import time
import tkinter as tk

from .. import sheet_rules

__all__ = ["Handover", "caption", "current", "close_all", "later", "peek", "Cover",
           "Banner", "ad_cover", "update_cover", "draw_widget", "draw_tile", "outside",
           "current_cover", "current_peek"]

_SEE_THROUGH = "#010203"
_FRAME_MS = 16
_SIDE = 24
_BADGE = 44
_open = []          # the sheets that are up, newest last
_captions = []


_pending = {}       # a Tk root -> the timers still waiting on it


def later(root, seconds, work):
    """``work()`` after ``seconds``, unless the window closes first.

    A plain ``root.after`` outlives the window: Tk still fires it, finds the
    Python function gone, and prints "invalid command name" at whoever is
    closing the Previewer. These are cancelled when the root goes.
    """
    waiting = _pending.get(root)
    if waiting is None:
        waiting = _pending[root] = set()

        def gone(event, root=root):
            if event.widget is not root:
                return
            for ident in list(_pending.pop(root, ())):
                try:
                    root.after_cancel(ident)
                except Exception:
                    pass
        try:
            root.bind("<Destroy>", gone, add="+")
        except tk.TclError:
            _pending.pop(root, None)
            return None

    def run():
        waiting.discard(ident)
        work()

    try:
        ident = root.after(max(0, int(seconds * 1000)), run)
    except tk.TclError:
        return None
    waiting.add(ident)
    return ident


def current():
    """The sheet in front, or ``None``. Tests and the harness ask this."""
    return _open[-1] if _open else None


def current_cover():
    """What has the whole screen, or ``None``."""
    return _covers[-1] if _covers else None


def current_peek():
    """The glimpse at the top of the window, or ``None``."""
    return _peeks[-1] if _peeks else None


def close_all():
    for sheet in list(_open):
        sheet.close(answer=False)
    for win in list(_captions):
        _drop_caption(win)
    for win in list(_peeks):
        _drop_peek(win)
    for cover in list(_covers):
        cover.on_close = None
        cover.close()


def _palette(ui, root):
    tokens = ui.global_styles.get("__theme__", {}) or {}
    base = ui._overlay_palette("bottom_sheet", None)
    surface = tokens.get("surface") or base["surface"]
    text = tokens.get("text") or base["text"]
    muted = tokens.get("text_secondary") or base["muted"]
    primary = tokens.get("primary") or base["primary"]
    try:
        rgb = root.winfo_rgb(surface)
        dark = sum(rgb) < 3 * 32768
    except tk.TclError:
        dark = False
    on_primary = tokens.get("on_primary") or ("#FFFFFF" if not dark else base["on_primary"])
    return {
        "surface": surface, "text": text, "muted": muted, "primary": primary,
        "on_primary": on_primary, "dark": dark,
        # Material's tonal container: the accent, mostly surface.
        "tonal": ui._mix_color(surface, primary, 0.16 if dark else 0.12),
        "field": ui._mix_color(surface, text, 0.07 if dark else 0.05),
        "line": ui._mix_color(surface, text, 0.14),
        "family": tokens.get("font-family", ""),
    }


def _font(ui, palette, size, bold=False):
    return ui._build_tk_font(
        {"font-size": "%dpx" % size, "font-weight": "bold" if bold else "normal",
         "font-family": palette["family"]}, default_size=size)


class Handover:
    """One sheet: another app in front of this one, as far as a desk can show."""

    def __init__(self, kind, icon, app_name, title, rows=(), quote="", note="",
                 back="Back to the app", field=None, done="Done", choices=(),
                 on_close=None, on_done=None, on_choice=None, picture=None):
        self.kind = kind                # "dial", "sms", "event", "page", ...
        self.icon = icon
        self.app_name = str(app_name)
        self.title = str(title)
        self.rows = [(row_icon, str(text)) for row_icon, text in rows if str(text).strip()]
        self.quote = str(quote or "")
        self.note = str(note or "")
        self.back = back
        self.field = field              # None, or the placeholder of a text field
        self.done = done
        self.choices = list(choices)    # [(label, value)]: answers, one under another
        self.on_close = on_close        # the person came back without answering
        self.on_done = on_done          # they answered: on_done(text)
        self.on_choice = on_choice      # they picked one: on_choice(value)
        # Something drawn under the title: picture(canvas, x, y, width)
        # answers where it ends.
        self.picture = picture
        self.entry = None
        self.win = None
        self.scrim = None
        self.closed = False
        self._run = 0                   # which slide is the current one

    # ── building ───────────────────────────────────────────────────────────

    def open(self):
        from .. import ui
        root = ui.live_preview_root()
        if root is None:
            return self
        for older in list(_open):
            older.close()
        root.update_idletasks()
        self.ui, self.root = ui, root
        self.palette = palette = _palette(ui, root)
        self.root_x, self.root_y = root.winfo_rootx(), root.winfo_rooty()
        self.root_w, self.root_h = max(1, root.winfo_width()), max(1, root.winfo_height())
        self.width = min(self.root_w, 640)
        self.x = self.root_x + (self.root_w - self.width) // 2

        scrim = tk.Toplevel(root)
        scrim.overrideredirect(True)
        scrim.configure(bg="#000000")
        scrim.geometry("%dx%d+%d+%d" % (self.root_w, self.root_h, self.root_x, self.root_y))
        try:
            scrim.attributes("-alpha", 0.01)
            scrim.attributes("-topmost", True)
        except tk.TclError:
            pass
        scrim.bind("<Button-1>", lambda _event: self.close())
        self.scrim = scrim

        win = tk.Toplevel(root)
        win.overrideredirect(True)
        corners = _SEE_THROUGH
        try:
            win.attributes("-transparentcolor", _SEE_THROUGH)
        except tk.TclError:
            corners = palette["surface"]
        win.configure(bg=corners)
        try:
            win.attributes("-alpha", 0.0)
            win.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.win = win
        self.canvas = canvas = tk.Canvas(win, width=self.width, height=10, bg=corners,
                                         highlightthickness=0, borderwidth=0)
        canvas.pack()
        self.height = self._draw(canvas)
        canvas.configure(height=self.height)
        self.rest_y = self.root_y + self.root_h - self.height
        win.geometry("%dx%d+%d+%d" % (self.width, self.height, self.x,
                                      self.root_y + self.root_h))
        win.lift(scrim)
        for window in (scrim, win):
            window.bind("<Escape>", lambda _event: self.close())
        _open.append(self)
        try:
            win.attributes("-alpha", 1.0)
        except tk.TclError:
            pass
        if self.entry is not None:
            win.after_idle(self.entry.focus_force)
        else:
            win.after_idle(win.focus_force)
        self._slide(self.height, 0, sheet_rules.OPEN_MS)
        return self

    def _draw(self, canvas):
        """Everything on the sheet, top to bottom. Answers its height."""
        ui, palette, width = self.ui, self.palette, self.width
        inner = width - _SIDE * 2
        self._keep = []
        # The surface goes in last, once the height is known, and under.
        y = 28

        # The other app: its icon in a tonal circle, and its name.
        canvas.create_oval(_SIDE, y, _SIDE + _BADGE, y + _BADGE,
                           fill=palette["tonal"], outline=palette["tonal"])
        ui._draw_material_icon(canvas, self.icon, _SIDE + _BADGE / 2, y + _BADGE / 2,
                               palette["primary"], size=24, tags="badge")
        canvas.create_text(_SIDE + _BADGE + 14, y + _BADGE / 2, text=self.app_name,
                           anchor="w", fill=palette["muted"],
                           font=_font(ui, palette, 14, True))
        y += _BADGE + 18

        title = canvas.create_text(_SIDE, y, text=self.title, anchor="nw", width=inner,
                                   fill=palette["text"],
                                   font=_font(ui, palette, sheet_rules.TITLE_SIZE, True))
        y = canvas.bbox(title)[3] + 14

        if self.picture is not None:
            y = self.picture(canvas, _SIDE, y + 2, inner) + 16

        for row_icon, text in self.rows:
            line = canvas.create_text(_SIDE + 34, y, text=text, anchor="nw",
                                      width=inner - 34, fill=palette["text"],
                                      font=_font(ui, palette, 15))
            top, bottom = canvas.bbox(line)[1], canvas.bbox(line)[3]
            first_line = min(bottom, top + 22)
            ui._draw_material_icon(canvas, row_icon, _SIDE + 10, (top + first_line) / 2,
                                   palette["muted"], size=20, tags="row")
            y = bottom + 12

        if self.quote:
            # What was written for the other app, as that app would show it:
            # a message in its bubble.
            pad = 14
            text = canvas.create_text(_SIDE + pad, y + pad, text=self.quote, anchor="nw",
                                      width=inner - pad * 2, fill=palette["text"],
                                      font=_font(ui, palette, 15))
            box = canvas.bbox(text)
            bubble = ui._create_rounded_rect(
                canvas, _SIDE, y, max(_SIDE + 120, min(width - _SIDE, box[2] + pad)),
                box[3] + pad, 18, fill=palette["tonal"], outline=palette["tonal"])
            canvas.tag_lower(bubble, text)
            y = box[3] + pad + 14

        if self.field is not None:
            field_height = 52
            frame = ui._create_rounded_rect(canvas, _SIDE, y, width - _SIDE, y + field_height,
                                            14, fill=palette["field"], outline=palette["field"])
            self.entry = entry = tk.Entry(
                canvas, bd=0, relief="flat", highlightthickness=0,
                bg=palette["field"], fg=palette["text"], insertbackground=palette["primary"],
                font=_font(ui, palette, 16))
            canvas.create_window(_SIDE + 16, y + field_height / 2, window=entry, anchor="w",
                                 width=inner - 32, height=30)
            self._placeholder = canvas.create_text(
                _SIDE + 18, y + field_height / 2, text=self.field, anchor="w",
                fill=palette["muted"], font=_font(ui, palette, 16))
            canvas.tag_lower(frame)

            def typed(_event=None):
                canvas.itemconfigure(
                    self._placeholder, state="hidden" if entry.get() else "normal")
            entry.bind("<KeyRelease>", typed)
            entry.bind("<Return>", lambda _event: self.finish())
            # The placeholder sits over the field: a click on it is a click
            # on the field.
            canvas.tag_bind(self._placeholder, "<Button-1>", lambda _event: entry.focus_set())
            canvas.tag_raise(self._placeholder)
            y += field_height + 14

        if self.note:
            # Said plainly, in the smallest type on the sheet: this is the
            # desk standing in, and here is what the phone does.
            note = canvas.create_text(_SIDE, y + 2, text=self.note, anchor="nw", width=inner,
                                      fill=palette["muted"], font=_font(ui, palette, 13))
            y = canvas.bbox(note)[3] + 12

        y += 6
        right = width - _SIDE
        if self.choices:
            # Android's permission dialog: every answer a full-width button of
            # the same weight, so none of them is the one being pushed.
            for position, (label, value) in enumerate(self.choices):
                self._wide_button(canvas, y, label, lambda chosen=value: self.choose(chosen),
                                  position)
                y += 48 + 6
            y += 18
        elif self.field is not None:
            right = self._button(canvas, right, y, self.done, self.finish, filled=True)
            self._button(canvas, right - 8, y, "Cancel", self.close, filled=False)
            y += 40 + 24
        else:
            self._button(canvas, right, y, self.back, self.close, filled=True)
            y += 40 + 24

        surface = ui._create_rounded_rect(
            canvas, 0, 0, width, y + sheet_rules.RADIUS * 2, sheet_rules.RADIUS,
            fill=palette["surface"], outline=palette["surface"])
        canvas.tag_lower(surface)
        return int(y)

    def _button(self, canvas, right, y, label, command, filled):
        """A pill ending at ``right``. Answers where it starts."""
        ui, palette = self.ui, self.palette
        font = _font(ui, palette, 14, True)
        import tkinter.font as tkfont
        try:
            measured = tkfont.Font(root=self.root, font=font).measure(label)
        except tk.TclError:
            measured = len(label) * 8
        width, height = measured + 48, 40
        tag = "button_%d" % int(right)
        fill = palette["primary"] if filled else palette["surface"]
        hover = ui._mix_color(fill, palette["on_primary"] if filled else palette["primary"],
                              0.10)
        pill = ui._create_rounded_rect(canvas, right - width, y, right, y + height, height / 2,
                                       fill=fill, outline=fill, tags=tag)
        canvas.create_text(right - width / 2, y + height / 2, text=label,
                           fill=palette["on_primary"] if filled else palette["primary"],
                           font=font, tags=tag)

        def lit(active):
            canvas.itemconfigure(pill, fill=hover if active else fill,
                                 outline=hover if active else fill)
            canvas.configure(cursor="hand2" if active else "")
        canvas.tag_bind(tag, "<Enter>", lambda _event: lit(True))
        canvas.tag_bind(tag, "<Leave>", lambda _event: lit(False))
        canvas.tag_bind(tag, "<Button-1>", lambda _event: command())
        return right - width

    def _wide_button(self, canvas, y, label, command, position):
        ui, palette = self.ui, self.palette
        tag = "choice_%d" % position
        fill = palette["tonal"]
        hover = ui._mix_color(fill, palette["primary"], 0.14)
        pill = ui._create_rounded_rect(canvas, _SIDE, y, self.width - _SIDE, y + 48, 24,
                                       fill=fill, outline=fill, tags=tag)
        canvas.create_text(self.width / 2, y + 24, text=label, fill=palette["primary"],
                           font=_font(ui, palette, 15, True), tags=tag)

        def lit(active):
            canvas.itemconfigure(pill, fill=hover if active else fill,
                                 outline=hover if active else fill)
            canvas.configure(cursor="hand2" if active else "")
        canvas.tag_bind(tag, "<Enter>", lambda _event: lit(True))
        canvas.tag_bind(tag, "<Leave>", lambda _event: lit(False))
        canvas.tag_bind(tag, "<Button-1>", lambda _event: command())

    # ── moving ─────────────────────────────────────────────────────────────

    def _place(self, offset):
        offset = max(0, min(self.height, int(round(offset))))
        shown = max(1, self.height - offset)
        try:
            self.win.geometry("%dx%d+%d+%d" % (self.width, shown, self.x, self.rest_y + offset))
            self.scrim.attributes(
                "-alpha", max(0.01, sheet_rules.scrim_alpha(offset, self.height)))
        except tk.TclError:
            pass

    def _slide(self, start, end, duration, then=None):
        self._run += 1
        run = self._run
        began = time.time()

        def step():
            if run != self._run:
                return                  # a newer slide took over
            try:
                if not self.win.winfo_exists():
                    return
            except tk.TclError:
                return
            t = min(1.0, (time.time() - began) * 1000.0 / max(1, duration))
            self._place(start + (end - start) * (1 - (1 - t) ** 3))
            if t < 1.0:
                later(self.root, _FRAME_MS / 1000.0, step)
            elif then:
                then()
        step()

    # ── leaving ────────────────────────────────────────────────────────────

    def finish(self):
        """The person answered: the field's text goes to ``on_done``."""
        if self.closed:
            return
        text = self.entry.get() if self.entry is not None else ""
        self._leave(lambda: self.on_done and self.on_done(text))

    def choose(self, value):
        """The person picked one of the answers."""
        if self.closed:
            return
        self._leave(lambda: self.on_choice and self.on_choice(value))

    def close(self, answer=True):
        """The person came back: ``on_close`` hears, once."""
        if self.closed:
            return
        self._leave((lambda: self.on_close and self.on_close()) if answer else None)

    def _leave(self, then):
        self.closed = True
        if self in _open:
            _open.remove(self)

        def gone():
            for window in (self.win, self.scrim):
                try:
                    window.destroy()
                except Exception:
                    pass
            if then:
                then()

        if self.win is None:
            if then:
                then()
            return
        try:
            self._slide(0, self.height, sheet_rules.CLOSE_MS, gone)
        except Exception:
            gone()


# ── the caption ──────────────────────────────────────────────────────────────

def _drop_caption(win):
    try:
        win.destroy()
    except Exception:
        pass
    if win in _captions:
        _captions.remove(win)


def caption(text, seconds, icon="volume_up"):
    """A line of text over the bottom of the screen, for as long as a voice
    would take over it. Answers the window, or ``None`` with no Previewer."""
    from .. import ui
    root = ui.live_preview_root()
    if root is None:
        return None
    for old in list(_captions):
        _drop_caption(old)
    root.update_idletasks()
    palette = _palette(ui, root)
    # The inverse of the page, as a snackbar is: it has to read over anything.
    ground = palette["text"]
    ink = palette["surface"]
    width = max(220, min(420, root.winfo_width() - 32))

    win = tk.Toplevel(root)
    win.overrideredirect(True)
    corners = _SEE_THROUGH
    try:
        win.attributes("-transparentcolor", _SEE_THROUGH)
        win.attributes("-topmost", True)
    except tk.TclError:
        corners = root.cget("bg")
    win.configure(bg=corners)
    canvas = tk.Canvas(win, width=width, height=10, bg=corners, highlightthickness=0,
                       borderwidth=0)
    canvas.pack()
    words = canvas.create_text(60, 16, text=str(text), anchor="nw", width=width - 78,
                               fill=ink, font=_font(ui, palette, 14))
    box = canvas.bbox(words)
    height = max(56, box[3] + 16)
    if box[3] - box[1] < 24:                    # one line: centred on the badge
        canvas.coords(words, 60, (height - (box[3] - box[1])) / 2)
    canvas.configure(height=height)
    pill = ui._create_rounded_rect(canvas, 0, 0, width, height, 18, fill=ground, outline=ground)
    canvas.tag_lower(pill)
    badge = ui._mix_color(ground, ink, 0.16)
    canvas.create_oval(12, height / 2 - 18, 48, height / 2 + 18, fill=badge, outline=badge)
    ui._draw_material_icon(canvas, icon, 30, height / 2, ink, size=20, tags="voice")

    nav = getattr(ui._app, "_bottom_nav_frame", None)
    try:
        lift = nav.winfo_height() if nav is not None and nav.winfo_exists() else 0
    except Exception:
        lift = 0
    lift += sum(BANNER_HEIGHT for banner in _banners if banner.shown and not banner.top)
    x = root.winfo_rootx() + (root.winfo_width() - width) // 2
    y = root.winfo_rooty() + root.winfo_height() - max(24, lift + 12) - height
    win.geometry("%dx%d+%d+%d" % (width, height, x, y))
    win.update_idletasks()
    win.lift(root)
    win.apkpy_caption = str(text)
    _captions.append(win)
    canvas.bind("<Button-1>", lambda _event: _drop_caption(win))
    later(root, max(0.4, seconds), lambda: _drop_caption(win))
    return win


# ── what lives outside the app ───────────────────────────────────────────────
#
# A widget is drawn by the launcher and a tile by quick settings: neither is
# on any screen of the app, and a desk has no home screen to put them on. So
# the Previewer draws them where the person can see them change -- a glimpse
# at the top of the window, on the dark of a wallpaper or of the shade --
# with the measurements Android uses, from the same texts the phone is given.

_OUTSIDE = "#1B1F27"            # a home screen at dusk, the shade pulled down
_OUTSIDE_INK = "#E3E6EC"
_OUTSIDE_MUTED = "#A3A9B5"
# Quick settings is the system's, in the system's colours: Android's own
# blue for a tile that is on, its grey for one that is off.
_TILE_ON = "#A8C7FA"
_TILE_ON_INK = "#062E6F"
_TILE_OFF = "#2F333B"
_AD_BADGE = "#F9AB00"
_peeks = []
_covers = []
_banners = []


def _measure(root, font, text):
    import tkinter.font as tkfont
    try:
        return tkfont.Font(root=root, font=font).measure(text)
    except tk.TclError:
        return len(text) * 8


def _fit(root, font, text, width):
    """``text``, cut short with an ellipsis when it is wider than ``width``."""
    text = str(text)
    if _measure(root, font, text) <= width:
        return text
    while text and _measure(root, font, text + "\u2026") > width:
        text = text[:-1]
    return text.rstrip() + "\u2026"


def widget_palette(ui, root):
    """The widget's colours: the app's own, as the phone takes them from its
    ``Theme``."""
    return _palette(ui, root)


def draw_widget(ui, root, canvas, x, y, width, palette, title, text, caption="",
                icon="", card=False, tags="widget"):
    """The app's widget as a launcher draws it: the row a widget one cell
    high gets, or the card a taller one does. Answers its bottom edge."""
    height = 132 if card else 64
    ui._create_rounded_rect(canvas, x, y, x + width, y + height, 22,
                            fill=palette["surface"], outline=palette["surface"], tags=tags)
    if card:
        left = x + 16
        if icon:
            canvas.create_oval(left, y + 16, left + 36, y + 52, fill=palette["tonal"],
                               outline=palette["tonal"], tags=tags)
            ui._draw_material_icon(canvas, icon, left + 18, y + 34, palette["primary"],
                                   size=20, tags=tags)
            left += 46
        font = _font(ui, palette, 13, True)
        canvas.create_text(left, y + 34, anchor="w", fill=palette["muted"], font=font,
                           text=_fit(root, font, title, x + width - 16 - left), tags=tags)
        bottom = y + height - 16
        if str(caption).strip():
            font = _font(ui, palette, 13)
            canvas.create_text(x + 16, bottom, anchor="sw", fill=palette["muted"], font=font,
                               text=_fit(root, font, caption, width - 32), tags=tags)
            bottom -= 20
        font = _font(ui, palette, 30, True)
        canvas.create_text(x + 16, bottom + 4, anchor="sw", fill=palette["text"], font=font,
                           text=_fit(root, font, text, width - 32), tags=tags)
        return y + height

    left = x + 16
    if icon:
        canvas.create_oval(left, y + 12, left + 40, y + 52, fill=palette["tonal"],
                           outline=palette["tonal"], tags=tags)
        ui._draw_material_icon(canvas, icon, left + 20, y + 32, palette["primary"],
                               size=22, tags=tags)
        left += 52
    room = x + width - 16 - left
    font = _font(ui, palette, 12, True)
    canvas.create_text(left, y + 21, anchor="w", fill=palette["muted"], font=font,
                       text=_fit(root, font, title, room), tags=tags)
    font = _font(ui, palette, 20, True)
    shown = _fit(root, font, text, room)
    canvas.create_text(left, y + 42, anchor="w", fill=palette["text"], font=font,
                       text=shown, tags=tags)
    taken = _measure(root, font, shown) + 8
    if str(caption).strip() and room - taken > 24:
        font = _font(ui, palette, 13)
        canvas.create_text(left + taken, y + 44, anchor="w", fill=palette["muted"], font=font,
                           text=_fit(root, font, caption, room - taken), tags=tags)
    return y + height


def draw_tile(ui, root, canvas, x, y, width, palette, label, subtitle="", icon="",
              active=False, tags="tile"):
    """One quick settings tile, as Android has drawn them since 12: a long
    pill, lit in the system's colour when it is on. Answers its bottom edge."""
    height = 68
    fill = _TILE_ON if active else _TILE_OFF
    ink = _TILE_ON_INK if active else _OUTSIDE_INK
    soft = _TILE_ON_INK if active else _OUTSIDE_MUTED
    ui._create_rounded_rect(canvas, x, y, x + width, y + height, 26, fill=fill,
                            outline=fill, tags=tags)
    ui._draw_material_icon(canvas, icon or "bolt", x + 30, y + height / 2, ink,
                           size=22, tags=tags)
    room = width - 56 - 16
    font = _font(ui, palette, 14, True)
    canvas.create_text(x + 56, y + 25, anchor="w", fill=ink, font=font,
                       text=_fit(root, font, label, room), tags=tags)
    # With no line of its own a tile says whether it is on.
    under = str(subtitle).strip() or ("On" if active else "Off")
    font = _font(ui, palette, 12)
    canvas.create_text(x + 56, y + 45, anchor="w", fill=soft, font=font,
                       text=_fit(root, font, under, room), tags=tags)
    return y + height


def outside(ui, root, canvas, x, y, width, draw, pad=14):
    """A panel of the world outside the app, with something drawn on it:
    ``draw(canvas, x, y, width)`` answers where it ends. Answers the panel's
    bottom edge."""
    bottom = draw(canvas, x + pad, y + pad, width - pad * 2) + pad
    panel = ui._create_rounded_rect(canvas, x, y, x + width, bottom, 24, fill=_OUTSIDE,
                                    outline=_OUTSIDE)
    canvas.tag_lower(panel)
    return bottom


def _drop_peek(win):
    try:
        win.destroy()
    except Exception:
        pass
    if win in _peeks:
        _peeks.remove(win)


def peek(where, icon, draw, seconds=2.8):
    """A glimpse of something outside the app, at the top of the window.

    ``where`` names the place ("Home screen", "Quick settings");
    ``draw(canvas, x, y, width)`` draws what is there and answers its bottom
    edge. It stays for ``seconds`` and a click sends it away. Answers the
    window, or ``None`` with no Previewer.
    """
    from .. import ui
    root = ui.live_preview_root()
    if root is None:
        return None
    for old in list(_peeks):
        _drop_peek(old)
    root.update_idletasks()
    palette = _palette(ui, root)
    width = max(240, min(380, root.winfo_width() - 24))

    win = tk.Toplevel(root)
    win.overrideredirect(True)
    corners = _SEE_THROUGH
    try:
        win.attributes("-transparentcolor", _SEE_THROUGH)
        win.attributes("-topmost", True)
    except tk.TclError:
        corners = root.cget("bg")
    win.configure(bg=corners)
    canvas = tk.Canvas(win, width=width, height=10, bg=corners, highlightthickness=0,
                       borderwidth=0)
    canvas.pack()
    ui._draw_material_icon(canvas, icon, 26, 24, _OUTSIDE_MUTED, size=16, tags="where")
    canvas.create_text(40, 24, text=str(where), anchor="w", fill=_OUTSIDE_MUTED,
                       font=_font(ui, palette, 12, True))
    bottom = draw(canvas, 14, 42, width - 28) + 14
    panel = ui._create_rounded_rect(canvas, 0, 0, width, bottom, 24, fill=_OUTSIDE,
                                    outline=_OUTSIDE)
    canvas.tag_lower(panel)
    height = int(bottom)
    canvas.configure(height=height)

    x = root.winfo_rootx() + (root.winfo_width() - width) // 2
    rest = root.winfo_rooty() + 34
    win.geometry("%dx%d+%d+%d" % (width, height, x, rest - 18))
    win.update_idletasks()
    win.lift(root)
    win.apkpy_peek = str(where)
    _peeks.append(win)
    canvas.bind("<Button-1>", lambda _event: _drop_peek(win))

    # It comes down into place, as a notification does.
    began = time.time()

    def settle():
        try:
            if not win.winfo_exists():
                return
        except tk.TclError:
            return
        t = min(1.0, (time.time() - began) / 0.18)
        offset = int(round(18 * (1 - t) ** 3))
        try:
            win.geometry("+%d+%d" % (x, rest - offset))
            win.attributes("-alpha", 0.35 + 0.65 * t)
        except tk.TclError:
            return
        if t < 1.0:
            later(root, _FRAME_MS / 1000.0, settle)
    settle()
    later(root, max(0.6, seconds), lambda: _drop_peek(win))
    return win


# ── the whole screen, taken ──────────────────────────────────────────────────

class Cover:
    """The app's screen with something else over all of it: a full-screen
    ad, or Play's own screen for an update that cannot wait.

    ``draw(cover)`` draws on ``cover.canvas`` (``cover.width`` by
    ``cover.height``); ``cover.close(value)`` takes it away and hands
    ``value`` to ``on_close``.
    """

    def __init__(self, kind, draw, on_close=None, ground="#101114"):
        self.kind = kind
        self.draw = draw
        self.on_close = on_close
        self.ground = ground
        self.win = None
        self.closed = False
        self.state = {}

    def open(self):
        from .. import ui
        root = ui.live_preview_root()
        if root is None:
            return self
        for older in list(_covers):
            older.close()
        root.update_idletasks()
        self.ui, self.root = ui, root
        self.palette = _palette(ui, root)
        self.width, self.height = max(1, root.winfo_width()), max(1, root.winfo_height())
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.configure(bg=self.ground)
        win.geometry("%dx%d+%d+%d" % (self.width, self.height, root.winfo_rootx(),
                                      root.winfo_rooty()))
        try:
            win.attributes("-alpha", 0.0)
            win.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.win = win
        self.canvas = tk.Canvas(win, width=self.width, height=self.height, bg=self.ground,
                                highlightthickness=0, borderwidth=0)
        self.canvas.pack()
        self.draw(self)
        _covers.append(self)
        win.after_idle(win.focus_force)
        began = time.time()

        def fade():
            try:
                if not win.winfo_exists():
                    return
                t = min(1.0, (time.time() - began) / 0.16)
                win.attributes("-alpha", t)
            except tk.TclError:
                return
            if t < 1.0:
                later(root, _FRAME_MS / 1000.0, fade)
        fade()
        return self

    def font(self, size, bold=False):
        return _font(self.ui, self.palette, size, bold)

    def after(self, seconds, work):
        """``work()`` later, unless the cover has gone by then."""
        def run():
            if not self.closed:
                work()
        later(self.root, seconds, run)

    def button(self, x1, y1, x2, y2, label, command, fill, ink, tag, size=15, radius=None):
        """A pill between two corners."""
        canvas, ui = self.canvas, self.ui
        radius = (y2 - y1) / 2 if radius is None else radius
        hover = ui._mix_color(fill, ink, 0.10)
        pill = ui._create_rounded_rect(canvas, x1, y1, x2, y2, radius, fill=fill,
                                       outline=fill, tags=tag)
        canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=label, fill=ink,
                           font=self.font(size, True), tags=tag)

        def lit(active):
            canvas.itemconfigure(pill, fill=hover if active else fill,
                                 outline=hover if active else fill)
            canvas.configure(cursor="hand2" if active else "")
        canvas.tag_bind(tag, "<Enter>", lambda _event: lit(True))
        canvas.tag_bind(tag, "<Leave>", lambda _event: lit(False))
        canvas.tag_bind(tag, "<Button-1>", lambda _event: command())

    def close(self, value=None):
        if self.closed:
            return
        self.closed = True
        if self in _covers:
            _covers.remove(self)
        try:
            if self.win is not None:
                self.win.destroy()
        except Exception:
            pass
        if self.on_close:
            self.on_close(value)


def ad_cover(rewarded, on_close, wait=5):
    """A full-screen ad, as far as a desk has one: the place a real ad takes,
    with the two things an ad always carries -- that it is an ad, and a way
    out. A rewarded one counts down first; leaving before the end forfeits
    the reward. ``on_close`` hears ``True`` when the reward was earned (or,
    for a plain interstitial, always)."""

    def draw(cover):
        canvas, ui, width, height = cover.canvas, cover.ui, cover.width, cover.height
        primary = cover.palette["primary"]
        state = cover.state
        state["left"] = wait if rewarded else 0

        # That it is an ad, top left: the yellow mark Google puts on every one.
        ui._create_rounded_rect(canvas, 20, 46, 48, 66, 6, fill=_AD_BADGE, outline=_AD_BADGE)
        canvas.create_text(34, 56, text="Ad", fill="#1F1F1F", font=cover.font(11, True))
        state["word"] = canvas.create_text(58, 56, anchor="w", fill="#E8EAED",
                                           font=cover.font(13, True), text="")

        # The way out, top right.
        canvas.create_oval(width - 56, 38, width - 20, 74, fill="#2A2D33", outline="#2A2D33",
                           tags="leave")
        ui._draw_material_icon(canvas, "close", width - 38, 56, "#FFFFFF", size=18,
                               tags="leave")
        canvas.tag_bind("leave", "<Button-1>", lambda _event: cover.close(state["left"] <= 0))
        canvas.tag_bind("leave", "<Enter>", lambda _event: canvas.configure(cursor="hand2"))
        canvas.tag_bind("leave", "<Leave>", lambda _event: canvas.configure(cursor=""))

        # The ad itself: a card where the picture and the pitch would be.
        card_w = min(width - 40, 360)
        card_h = min(height - 220, 420)
        left = (width - card_w) / 2
        top = max(96, (height - card_h) / 2 - 6)
        ui._create_rounded_rect(canvas, left, top, left + card_w, top + card_h, 26,
                                fill="#FFFFFF", outline="#FFFFFF")
        art_h = card_h * 0.46
        tint = ui._mix_color("#FFFFFF", primary, 0.16)
        ui._create_rounded_rect(canvas, left + 12, top + 12, left + card_w - 12,
                                top + art_h, 18, fill=tint, outline=tint)
        ui._draw_material_icon(canvas, "redeem" if rewarded else "campaign",
                               left + card_w / 2, top + 12 + (art_h - 12) / 2, primary,
                               size=56, tags="art")
        y = top + art_h + 22
        canvas.create_text(left + 22, y, anchor="nw", width=card_w - 44, fill="#1F1F1F",
                           font=cover.font(20, True),
                           text="A reward for watching" if rewarded else "An ad goes here")
        y += 34
        words = canvas.create_text(
            left + 22, y, anchor="nw", width=card_w - 44, fill="#5F6368", font=cover.font(14),
            text=("On the phone this is a video from AdMob that the person chose to "
                  "watch. Stay to the end and the reward is theirs."
                  if rewarded else
                  "On the phone this is a real ad from AdMob, over the whole screen, "
                  "until the person closes it."))
        cover.button(left + 22, top + card_h - 70, left + card_w - 22, top + card_h - 22,
                     "Learn more", lambda: None, primary, cover.palette["on_primary"], "pitch")
        state["note"] = canvas.create_text(
            width / 2, min(height - 34, top + card_h + 30), fill="#9AA0A6",
            font=cover.font(12), width=width - 48, justify="center", text="")
        del words

        def tick():
            left_now = state["left"]
            if left_now > 0:
                canvas.itemconfigure(state["word"], text="Reward in %d" % left_now)
                canvas.itemconfigure(
                    state["note"], text="Leaving now gives the reward up.")
                state["left"] = left_now - 1
                cover.after(1.0, tick)
                return
            canvas.itemconfigure(state["word"],
                                 text="Reward earned" if rewarded else "Test ad")
            canvas.itemconfigure(
                state["note"],
                text="Close it to go back to the app with the reward." if rewarded
                else "Close it to go back to the app.")
        tick()

    return Cover("rewarded" if rewarded else "interstitial", draw, on_close).open()


def update_cover(app_name, on_close):
    """Play's screen for an update that cannot wait: it has the whole screen
    until the new version is in, or the person backs out. ``on_close`` hears
    ``True`` once it is installed and ``False`` when they left."""

    def draw(cover):
        canvas, ui, width, height = cover.canvas, cover.ui, cover.width, cover.height
        palette = cover.palette
        middle = width / 2
        top = max(96, height * 0.22)
        ui._draw_material_icon(canvas, "shop", 30, 56, palette["muted"], size=18, tags="play")
        canvas.create_text(46, 56, anchor="w", text="Google Play", fill=palette["muted"],
                           font=cover.font(13, True))
        canvas.create_oval(middle - 44, top, middle + 44, top + 88, fill=palette["tonal"],
                           outline=palette["tonal"])
        ui._draw_material_icon(canvas, "system_update", middle, top + 44, palette["primary"],
                               size=40, tags="badge")
        canvas.create_text(middle, top + 122, text="Update available", fill=palette["text"],
                           font=cover.font(24, True))
        canvas.create_text(
            middle, top + 150, anchor="n", width=width - 64, justify="center",
            fill=palette["muted"], font=cover.font(15),
            text="%s needs its newest version to carry on. It downloads and installs "
                 "here, and the app opens again when it is done." % app_name)
        base = height - 150

        def choose():
            cover.button(32, base, width - 32, base + 52, "Update", install,
                         palette["primary"], palette["on_primary"], "go", size=16)
            cover.button(32, base + 62, width - 32, base + 110, "Not now",
                         lambda: cover.close(False), palette["surface"], palette["primary"],
                         "leave")

        def install():
            canvas.delete("go")
            canvas.delete("leave")
            canvas.configure(cursor="")
            ui._create_rounded_rect(canvas, 32, base + 30, width - 32, base + 38, 4,
                                    fill=palette["line"], outline=palette["line"], tags="bar")
            cover.state["word"] = canvas.create_text(
                middle, base + 4, text="Downloading\u2026", fill=palette["text"],
                font=cover.font(14, True))
            cover.state["began"] = time.time()
            step()

        def step():
            t = min(1.0, (time.time() - cover.state["began"]) / 2.2)
            canvas.delete("fill")
            reach = 32 + (width - 64) * t
            if reach > 40:
                ui._create_rounded_rect(canvas, 32, base + 30, reach, base + 38, 4,
                                        fill=palette["primary"], outline=palette["primary"],
                                        tags="fill")
            if t >= 0.72:
                canvas.itemconfigure(cover.state["word"], text="Installing\u2026")
            if t < 1.0:
                cover.after(_FRAME_MS / 1000.0, step)
            else:
                cover.after(0.35, lambda: cover.close(True))

        choose()

    from .. import ui as _ui
    root = _ui.live_preview_root()
    ground = _palette(_ui, root)["surface"] if root is not None else "#FFFFFF"
    return Cover("update", draw, on_close, ground=ground).open()


# ── the banner's place on a screen ───────────────────────────────────────────

BANNER_HEIGHT = 58


class Banner:
    """A banner ad's place: a strip along one edge of the screen, with the
    screen made that much shorter -- which is what the phone does, so a
    layout can be judged with the banner in it."""

    def __init__(self, top=False):
        self.top = bool(top)
        self.frame = None

    def open(self):
        from .. import ui
        root = ui.live_preview_root()
        app = ui.live_preview()
        if root is None or app is None:
            return self
        self.ui, self.root, self.app = ui, root, app
        self.palette = palette = _palette(ui, root)
        ground = palette["surface"]
        nav = getattr(app, "_bottom_nav_frame", None)
        try:
            if not self.top and nav is not None and nav.winfo_exists():
                ground = nav.cget("bg")         # under a bar of tabs it continues the bar
            else:
                ground = app.body.cget("bg")
        except Exception:
            pass
        self.ground = ground
        frame = tk.Frame(root, bg=ground, height=BANNER_HEIGHT)
        strip = getattr(ui, "_STATUS_STRIP_HEIGHT", 24)
        if self.top:
            # Below the clock, and the screen below the banner.
            frame.pack(side="top", fill="x", before=app.body, pady=(strip, 0))
            app.body.pack_configure(pady=(0, 0))
        else:
            frame.pack(side="bottom", fill="x", before=app.body)
        frame.pack_propagate(False)
        self.frame = frame
        self.canvas = canvas = tk.Canvas(frame, height=BANNER_HEIGHT, bg=ground,
                                         highlightthickness=0, borderwidth=0)
        canvas.pack(fill="both", expand=True)
        canvas.bind("<Configure>", lambda event: self._draw(event.width))

        def gone(event):
            if event.widget is frame and self.top:
                try:
                    app.body.pack_configure(pady=(strip, 0))
                except Exception:
                    pass
        frame.bind("<Destroy>", gone, add="+")
        _banners.append(self)
        root.update_idletasks()
        self._draw(max(1, canvas.winfo_width()))
        return self

    def _draw(self, width):
        canvas, ui, palette = self.canvas, self.ui, self.palette
        canvas.delete("all")
        try:
            rgb = self.root.winfo_rgb(self.ground)
            dark = sum(rgb) < 3 * 32768
        except tk.TclError:
            dark = False
        ink = "#F1F3F4" if dark else "#1F1F1F"
        soft = "#B6BBC4" if dark else "#5F6368"
        line = ui._mix_color(self.ground, ink, 0.12)
        edge = BANNER_HEIGHT - 1 if self.top else 0
        canvas.create_line(0, edge, width, edge, fill=line)
        middle = BANNER_HEIGHT / 2
        tint = ui._mix_color(self.ground, palette["primary"], 0.16)
        ui._create_rounded_rect(canvas, 14, middle - 19, 52, middle + 19, 10, fill=tint,
                                outline=tint)
        ui._draw_material_icon(canvas, "campaign", 33, middle, palette["primary"], size=20,
                               tags="art")
        ui._create_rounded_rect(canvas, 64, middle - 17, 86, middle - 3, 4, fill=_AD_BADGE,
                                outline=_AD_BADGE)
        canvas.create_text(75, middle - 10, text="Ad", fill="#1F1F1F",
                           font=_font(ui, palette, 9, True))
        button = 74
        room = width - 64 - button - 24
        font = _font(ui, palette, 13, True)
        canvas.create_text(92, middle - 10, anchor="w", fill=ink, font=font,
                           text=_fit(self.root, font, "Test ad", max(10, room - 28)))
        font = _font(ui, palette, 12)
        canvas.create_text(64, middle + 10, anchor="w", fill=soft, font=font,
                           text=_fit(self.root, font, "A banner from AdMob goes here",
                                     max(10, room)))
        ui._create_rounded_rect(canvas, width - 14 - button, middle - 15, width - 14,
                                middle + 15, 15, fill=self.ground,
                                outline=palette["primary"], width=1)
        canvas.create_text(width - 14 - button / 2, middle, text="Open",
                           fill=palette["primary"], font=_font(ui, palette, 12, True))

    @property
    def shown(self):
        try:
            return self.frame is not None and bool(self.frame.winfo_exists())
        except Exception:
            return False

    def close(self):
        frame, self.frame = self.frame, None
        if self in _banners:
            _banners.remove(self)
        if frame is None:
            return
        try:
            frame.destroy()
        except Exception:
            pass
