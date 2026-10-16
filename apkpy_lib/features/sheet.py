"""The bottom sheet, in the Previewer.

Two windows over the app: a black one for the scrim, and the sheet. The
sheet has rounded top corners, a handle, and either the plain content it
always had (a title, text, a list of items, a close button) or the
components the app put in it with ``parent=``.

It can be dragged by its handle and its title: let go past half way, or
flung down, and it closes -- ``sheet_rules.settle`` is
what Material's BottomSheetBehavior decides on the phone.
"""

import os
import time
import tkinter as tk

from .. import sheet_rules as rules

# The colour the window manager treats as see-through, for the corners.
_SEE_THROUGH = '#010203'
_FRAME_MS = 16


def _blend(top, under, alpha):
    """``top`` at ``alpha`` over ``under``, as #rrggbb."""
    def parts(colour):
        colour = str(colour).lstrip('#')
        if len(colour) == 8:
            colour = colour[2:]
        if len(colour) != 6:
            return (128, 128, 128)
        return tuple(int(colour[i:i + 2], 16) for i in (0, 2, 4))
    a, b = parts(top), parts(under)
    return '#%02x%02x%02x' % tuple(round(a[i] * alpha + b[i] * (1 - alpha)) for i in range(3))


class Sheet:
    """One open bottom sheet."""

    def __init__(self, ui, overlay):
        self.ui = ui
        self.overlay = overlay
        self.data = overlay.kwargs
        self.composed = bool(self.data.get('composed'))
        self.offset = 0             # how far below its resting place it is
        self.height = 0
        self.closing = False
        self._drag = None
        self._samples = []
        self._job = None

    # ── building ───────────────────────────────────────────────────────────

    def open(self):
        ui, root = self.ui, self.ui._app.root
        root.update_idletasks()
        palette = ui._overlay_palette('bottom_sheet', self.data.get('comp_id'))
        self.palette = palette
        self.root_x, self.root_y = root.winfo_rootx(), root.winfo_rooty()
        self.root_w = max(1, root.winfo_width())
        self.root_h = max(1, root.winfo_height())
        # The sheet's own colour, else the theme's surface -- which is what
        # the phone paints. The palette's 'surface' folds the page's
        # background in, and a sheet in the page's colour is not a sheet.
        tokens = ui.global_styles.get('__theme__', {}) or {}
        own = ui.global_styles.get(self.data.get('comp_id'), {}) if self.data.get('comp_id') else {}
        resting = tokens.get('surface') or palette['surface']
        self.surface = ui._tk_color(ui._get_style_bg(own) if own else None, resting) or resting

        scrim = tk.Toplevel(root)
        scrim.overrideredirect(True)
        scrim.configure(bg='#000000')
        scrim.geometry(f'{self.root_w}x{self.root_h}+{self.root_x}+{self.root_y}')
        try:
            scrim.attributes('-alpha', rules.SCRIM)
            scrim.attributes('-topmost', True)
        except tk.TclError:
            pass
        self.scrim = scrim

        self.width = min(self.root_w, 640)
        self.x = self.root_x + (self.root_w - self.width) // 2
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        corners = _SEE_THROUGH
        try:
            win.attributes('-transparentcolor', _SEE_THROUGH)
        except tk.TclError:
            corners = self.surface          # no see-through here: square corners
        win.configure(bg=self.surface)
        try:
            win.attributes('-alpha', 0.0)   # until it is measured and placed
            win.attributes('-topmost', True)
        except tk.TclError:
            pass
        win.geometry(f'{self.width}x{self.root_h}+{self.x}+{self.root_y}')
        win.lift(scrim)
        self.win = win

        scrim._apkpy_overlay_extras = [win]
        scrim._apkpy_before_close = self._before_close
        scrim._apkpy_after_close = self._after_close
        self.overlay.widget = scrim
        scrim.bind('<Button-1>', lambda _e: self.overlay.close())
        for window in (scrim, win):
            window.bind('<Escape>', lambda _e: self.overlay.close())

        content = tk.Frame(win, bg=self.surface)
        content.pack(fill='x', side='top', anchor='n')
        self.content = content

        strip = rules.HANDLE_PAD * 2 + rules.HANDLE_HEIGHT
        header = tk.Canvas(content, height=strip, bg=corners, highlightthickness=0,
                           cursor='sb_v_double_arrow')
        header.pack(fill='x')
        handle = _blend(palette['muted'], self.surface, rules.HANDLE_ALPHA)

        def _draw_header(event=None):
            width = header.winfo_width() if event is None else event.width
            header.delete('all')
            ui._create_rounded_rect(header, 0, 0, width, strip + rules.RADIUS * 2, rules.RADIUS,
                                    fill=self.surface, outline='')
            left = (width - rules.HANDLE_WIDTH) / 2
            ui._create_rounded_rect(header, left, rules.HANDLE_PAD,
                                    left + rules.HANDLE_WIDTH,
                                    rules.HANDLE_PAD + rules.HANDLE_HEIGHT,
                                    rules.HANDLE_HEIGHT / 2, fill=handle, outline='')
        header.bind('<Configure>', _draw_header)
        self.header = header
        self._drag_surfaces = [header, content]

        if self.composed:
            self._fill_composed()
        else:
            self._fill_plain()

        for surface in self._drag_surfaces:
            surface.bind('<ButtonPress-1>', self._press, add='+')
            surface.bind('<B1-Motion>', self._move, add='+')
            surface.bind('<ButtonRelease-1>', self._release, add='+')

        self._fit()
        try:
            win.attributes('-alpha', 1.0)
        except tk.TclError:
            pass
        win.after_idle(win.focus_force)
        self._slide(self.height, 0, rules.OPEN_MS)

    def _heading(self, size, bold, colour, text, pady):
        tokens = self.ui.global_styles.get('__theme__', {}) or {}
        font = self.ui._build_tk_font(
            {'font-size': '%dpx' % size, 'font-weight': 'bold' if bold else 'normal',
             'font-family': tokens.get('font-family', '')}, default_size=size)
        label = tk.Label(self.content, text=text, bg=self.surface, fg=colour, font=font,
                         anchor='w', justify='left', bd=0, padx=0, pady=0,
                         wraplength=max(120, self.width - rules.SIDE * 2))
        label.pack(fill='x', padx=rules.SIDE, pady=pady)
        self._drag_surfaces.append(label)
        return label

    def _fill_composed(self):
        ui, data = self.ui, self.data
        title, text = data.get('title') or '', data.get('content') or ''
        if title:
            self._heading(rules.TITLE_SIZE, True, self.palette['text'], title,
                          (0, rules.TITLE_GAP if text else rules.HEADER_GAP))
        if text:
            self._heading(rules.CONTENT_SIZE, False, self.palette['muted'], text,
                          (0, rules.HEADER_GAP))
        comp_id = data.get('comp_id')
        # The body is a column with the sheet's defaults under its own CSS.
        ui.global_styles[comp_id] = rules.body_style(ui.global_styles.get(comp_id, {}))
        body = ui.ComponentDef('container', comp_id=comp_id)
        body.children = list(self.overlay.children)
        self.body = body
        ui._app._render_container(body, self.content, False, tk.TOP, self.surface)

    def _fill_plain(self):
        ui, data, palette = self.ui, self.data, self.palette
        panel = tk.Frame(self.content, bg=self.surface, padx=20)
        panel.pack(fill='x')
        self._drag_surfaces.append(panel)
        family = 'Segoe UI' if os.name == 'nt' else 'Helvetica'
        title = tk.Label(panel, text=data.get('title', ''), bg=self.surface, fg=palette['text'],
                         font=(family, 16, 'bold'), anchor='w')
        title.pack(fill='x')
        self._drag_surfaces.append(title)
        if data.get('content'):
            copy = tk.Label(panel, text=data['content'], bg=self.surface, fg=palette['muted'],
                            font=(family, 10), wraplength=max(220, self.width - 72),
                            justify='left', anchor='w')
            copy.pack(fill='x', pady=(6, 10))
            self._drag_surfaces.append(copy)

        def _choose(value):
            self.overlay.close()
            ui._overlay_callback(data.get('on_select'), value)

        for item in data.get('items') or []:
            tk.Button(
                panel, text=str(item), command=lambda value=item: _choose(value),
                bg=self.surface, fg=palette['text'], activebackground=palette['border'],
                activeforeground=palette['text'], relief='flat', bd=0, anchor='w',
                font=(family, 11), padx=8, pady=9,
            ).pack(fill='x')
        tk.Button(
            panel, text=data.get('close_text', 'Close'), command=self.overlay.close,
            bg=self.surface, fg=palette['primary'], activebackground=palette['border'],
            activeforeground=palette['primary'], relief='flat', bd=0, anchor='e',
            font=(family, 10, 'bold'), pady=8,
        ).pack(fill='x', pady=(0, 8))

    def _fit(self):
        """Measure the content at the sheet's width and stand the sheet on
        the bottom edge."""
        self.win.update()
        wanted = self.content.winfo_reqheight()
        self.height = rules.height(wanted, self.root_h)
        self.rest_y = self.root_y + self.root_h - self.height
        self._place(self.height)        # starts below the edge, slides up

    # ── moving ─────────────────────────────────────────────────────────────

    def _place(self, offset):
        self.offset = max(0, min(self.height, int(round(offset))))
        shown = max(1, self.height - self.offset)
        try:
            self.win.geometry(f'{self.width}x{shown}+{self.x}+{self.rest_y + self.offset}')
            self.scrim.attributes('-alpha', max(0.01, rules.scrim_alpha(self.offset, self.height)))
        except tk.TclError:
            pass

    def _slide(self, start, end, duration, then=None):
        """Ease from one offset to another."""
        if self._job is not None:
            try:
                self.win.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        began = time.time()

        def step():
            try:
                if not self.win.winfo_exists():
                    return
            except tk.TclError:
                return
            t = min(1.0, (time.time() - began) * 1000.0 / max(1, duration))
            eased = 1 - (1 - t) ** 3
            self._place(start + (end - start) * eased)
            if t < 1.0:
                self._job = self.win.after(_FRAME_MS, step)
            else:
                self._job = None
                if then:
                    then()
        step()

    def _press(self, event):
        if self.closing:
            return
        self._drag = (event.y_root, self.offset)
        self._samples = [(time.time(), event.y_root)]

    def _move(self, event):
        if self._drag is None:
            return
        self.drag_to(self._drag[1] + (event.y_root - self._drag[0]))
        self._samples = (self._samples + [(time.time(), event.y_root)])[-5:]

    def _release(self, event):
        if self._drag is None:
            return
        self._drag = None
        velocity = 0.0
        if len(self._samples) >= 2:
            (t0, y0), (t1, y1) = self._samples[0], self._samples[-1]
            if t1 > t0:
                velocity = (y1 - y0) / (t1 - t0)
        self.release(velocity)

    def drag_to(self, offset):
        """Hold the sheet ``offset`` below where it rests. It does not go up."""
        self._place(offset)

    def release(self, velocity=0.0):
        """Let go: the sheet settles open or closes, as on the phone."""
        if rules.settle(self.offset, self.height, velocity) == 'closed':
            self.closing = True
            self._slide(self.offset, self.height, rules.CLOSE_MS, self.overlay.close)
            return 'closed'
        self._slide(self.offset, 0, rules.CLOSE_MS)
        return 'open'

    # ── closing ────────────────────────────────────────────────────────────

    def _before_close(self):
        if self.composed:
            # What was typed stays for the next time, as the phone's views do.
            holder = type('Holder', (), {'components': list(self.overlay.children)})()
            try:
                self.ui._remember_screen_state(holder)
            except Exception:
                pass

    def _after_close(self):
        self.overlay._sheet = None
        self.ui._overlay_callback(self.data.get('on_close'))


def show(overlay):
    from .. import ui
    sheet = Sheet(ui, overlay)
    overlay._sheet = sheet
    sheet.open()
    return sheet
