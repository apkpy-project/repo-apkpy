"""draw_pad(): a box to sign or scribble in with a finger, kept as a PNG.

In the Previewer it is a Tk canvas the mouse draws on; on the phone it is
ApkpyDrawPad (core/features/draw_pad.py). Both take their sizes and colours
from draw_pad_rules and draw a stroke the same way: straight to the middle of
its first segment, then a curve through each point, so a slow hand and a fast
one leave the same smooth line.

``pad.clear()`` empties it, ``pad.is_empty()`` says whether anything is drawn,
and ``pad.save("signature.png")`` keeps what is drawn as a PNG in the app's
folder (``files.path("signature.png")``), answering ``"ok"``, ``"invalid"``
when the name is not a file of the app's folder, or ``"failed"``.
"""

import os
import tkinter as tk

from .. import draw_pad_rules as rules
from ..ui import ComponentDef


class DrawPadDef(ComponentDef):
    """A draw_pad() on a screen."""

    def _strokes(self):
        return self.kwargs.setdefault('_strokes', [])

    def clear(self):
        """Wipe what is drawn. on_change is not called: it answers the finger."""
        del self._strokes()[:]
        redraw = getattr(self, '_pad_redraw', None)
        if redraw is not None:
            redraw()

    def is_empty(self):
        """True when nothing is drawn."""
        return not any(self._strokes())

    def save(self, name):
        """Keep what is drawn as the PNG ``name`` in the app's folder, the size the
        box has on the screen. Answers ``"ok"``, ``"invalid"`` or ``"failed"``."""
        from .kit import _own_file
        path = _own_file(name)
        if not path:
            return "invalid"
        try:
            image = picture(self)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            spare = os.path.join(os.path.dirname(path), ".apkpy-" + os.path.basename(path) + ".tmp")
            image.save(spare, format="PNG")
            os.replace(spare, path)
        except (OSError, ValueError):
            return "failed"
        return "ok"


def draw_pad(id=None, on_change=None, pen=3, hint="", screen=None, parent=None):
    """A box the person draws in with a finger: a signature on a delivery, a
    sketch, a note by hand. Kept as a picture with ``save()``::

        pad = draw_pad(id="signature", hint="Sign here", on_change=signed, screen=home)

        def done():
            if pad.is_empty():
                toast("Sign first")
            else:
                pad.save("signature.png")       # files.path("signature.png")

    ``on_change()`` is called each time a stroke ends. ``pad.clear()`` wipes it
    (and does not call on_change). ``pen=`` is the line's width; ``hint=`` shows
    in the middle while it is empty.

    CSS on its id (or ``draw_pad { }``): ``color`` (the ink),
    ``background-color`` (the paper), ``border-color``, ``border-radius``,
    ``height`` (200 unless given) and ``hint-color``.
    """
    from .rich_content import _attach
    if on_change is not None and not callable(on_change):
        raise TypeError("draw_pad(on_change=...) must be a function")
    comp = DrawPadDef(rules.COMPONENT, comp_id=id, on_change=on_change,
                      pen=rules.pen_from(pen), hint=str(hint or ""), _strokes=[])
    _attach(comp, screen=screen, parent=parent)
    return comp


def _style(comp):
    from .. import ui
    own = ui.component_style(ui.global_styles, rules.COMPONENT, comp.kwargs.get('comp_id'),
                             include_body=False)
    tokens = ui.global_styles.get('__theme__', {}) or {}
    return own, rules.colors(tokens, own)


def picture(comp):
    """What is drawn, as a PIL image the size of the box (paper and ink, no
    border and no hint), drawn four times bigger and brought down so the line
    is smooth at its edges."""
    from PIL import Image, ImageDraw
    from .. import ui
    own, colors = _style(comp)
    widget = getattr(comp, 'widget', None)
    try:
        width, height = int(widget.winfo_width()), int(widget.winfo_height())
    except Exception:
        width, height = 0, 0
    if width <= 2 or height <= 2:
        width, height = 360, int(rules.height(own))
    big = 4
    paper = colors['paper']
    fill = (0, 0, 0, 0)
    if paper:
        fill = _rgba(ui._tk_color(paper, '#FFFFFF'))
    image = Image.new("RGBA", (width * big, height * big), fill)
    draw = ImageDraw.Draw(image)
    ink = _rgba(ui._tk_color(colors['ink'], '#000000'))
    pen = comp.kwargs.get('pen', rules.PEN) * big
    for stroke in comp._strokes():
        points = [(x * big, y * big) for x, y in rules.smooth(stroke)]
        if len(points) > 1:
            draw.line(points, fill=ink, width=max(1, int(round(pen))), joint="curve")
        for x, y in (points[0], points[-1]):
            r = pen / 2.0
            draw.ellipse((x - r, y - r, x + r, y + r), fill=ink)
    return image.resize((width, height), Image.BOX)


def _rgba(colour):
    """A colour as Tk takes it ("#rrggbb", "#rgb", a name), as (r, g, b, a)."""
    from PIL import ImageColor
    try:
        found = ImageColor.getrgb(str(colour))
    except ValueError:
        found = (0, 0, 0)
    return tuple(found) + (255,) if len(found) == 3 else tuple(found)


def render_draw_pad(app, comp, parent_widget, is_flex, pack_side, bg_color):
    from .. import ui
    from .rich_content import _pack_outer
    comp_id = comp.kwargs.get('comp_id')
    own, colors = _style(comp)
    corner = rules.radius(own)
    tall = int(round(rules.height(own)))
    bg = ui._tk_color(bg_color, '#FFFFFF')
    margin = ui._parse_margin(ui._merge_with_body(comp_id, rules.COMPONENT))
    canvas = tk.Canvas(parent_widget, height=tall, bg=bg, highlightthickness=0, bd=0, cursor='pencil')
    _pack_outer(canvas, is_flex=is_flex, pack_side=pack_side, margin=margin)
    if is_flex:
        canvas.configure(width=320)
    comp.widget = canvas
    ink = ui._tk_color(colors['ink'], '#000000')
    pen = comp.kwargs.get('pen', rules.PEN)
    font = ui._build_tk_font({'font-size': '%dpx' % rules.HINT_SIZE}, default_size=rules.HINT_SIZE)
    live = []          # the stroke under the mouse

    def line(points, tag):
        if len(points) == 1:
            x, y = points[0]
            canvas.create_oval(x - pen / 2.0, y - pen / 2.0, x + pen / 2.0, y + pen / 2.0,
                               fill=ink, outline='', tags=tag)
            return
        flat = [v for point in points for v in point]
        canvas.create_line(*flat, fill=ink, width=pen, capstyle=tk.ROUND, joinstyle=tk.ROUND, tags=tag)

    def draw(_event=None):
        try:
            width, height = canvas.winfo_width(), canvas.winfo_height()
        except tk.TclError:
            return
        if width <= 2:
            return
        canvas.delete('all')
        half = rules.BORDER / 2.0 if colors['border'] else 0
        ui._create_rounded_rect(canvas, half, half, width - 1 - half, height - 1 - half, corner,
                                fill=(colors['paper'] or ''),
                                outline=(colors['border'] or ''),
                                width=(rules.BORDER if colors['border'] else 0))
        strokes = comp._strokes()
        if not any(strokes) and not live and comp.kwargs.get('hint'):
            canvas.create_text(width / 2.0, height / 2.0, text=comp.kwargs['hint'], font=font,
                               fill=ui._tk_color(colors['hint'], '#49454F'))
        for stroke in strokes:
            line(rules.smooth(stroke), 'ink')

    def press(event):
        live[:] = [(event.x, event.y)]
        if not any(comp._strokes()):
            draw()                      # the hint goes as the first stroke starts
        line(live, 'live')

    def move(event):
        if not live:
            return
        last = live[-1]
        if (event.x, event.y) == last:
            return
        live.append((event.x, event.y))
        canvas.delete('live')
        line(rules.smooth(live), 'live')

    def release(_event):
        if not live:
            return
        comp._strokes().append(list(live))
        live[:] = []
        draw()
        callback = comp.kwargs.get('on_change')
        if callable(callback):
            callback()

    comp._pad_redraw = draw
    canvas.bind('<Configure>', draw)
    canvas.bind('<ButtonPress-1>', press)
    canvas.bind('<B1-Motion>', move)
    canvas.bind('<ButtonRelease-1>', release)
