"""What a gradient container shows under the widgets inside it (Previewer).

Tk has no transparent widgets: a label in a card with a gradient was a band of
one colour across it. On the phone the label is transparent and the gradient
runs under its text. Here every widget in the card whose surface is the
card's -- which is what a transparent surface resolves to -- is given the
piece of the gradient it covers: a canvas at the bottom of what it draws, a
frame on a picture behind its children, and a label as its picture.

A label draws its text centred on its picture, so the picture is made larger
than the label and anchored so that its centre falls where the text would be
without it: the text stays where its alignment puts it.
"""

import tkinter as tk

_PASS_DELAY_MS = 30
_TEXT_OPTIONS = frozenset(("text", "font", "wraplength", "justify", "padx", "pady",
                           "anchor"))
_HORIZONTAL = {"w": "w", "nw": "w", "sw": "w", "e": "e", "ne": "e", "se": "e"}
_VERTICAL = {"n": "n", "nw": "n", "ne": "n", "s": "s", "sw": "s", "se": "s"}


def install(panel, content, picture_at, surface):
    """Keep the widgets in ``content`` showing ``panel``'s gradient.

    ``picture_at()`` returns ``(image, x, y)``: the gradient shape as an RGB
    picture and where its corner lies in ``panel``. ``surface`` is the colour
    the content's widgets carry when they have none of their own.
    """
    first = panel.__dict__.get("_apkpy_gradient_under") is None
    panel._apkpy_gradient_under = (content, picture_at, surface)
    if first:
        # paint() skips a panel that is not on screen yet; one whose last
        # <Configure> came before it was mapped -- the avatar of a screen
        # opened from the bar -- stayed a black square.
        try:
            panel.bind("<Map>", lambda _e: schedule(panel), add="+")
        except Exception:
            pass
    schedule(panel)


def schedule(panel):
    if panel.__dict__.get("_apkpy_gradient_pending"):
        return
    # Tk sends a label's <Configure> from inside the configure() that puts
    # the picture on or takes it off. Taken as a request, it painted, took
    # the picture off, painted again... every 45 ms, and a screenshot caught
    # a shaped label (an avatar, a badge) as a dark square half the time.
    if (panel.__dict__.get("_apkpy_under_state") or {}).get("painting"):
        return
    panel._apkpy_gradient_pending = True

    def run():
        panel._apkpy_gradient_pending = False
        try:
            paint(panel)
        except Exception:
            pass
    try:
        panel.after(_PASS_DELAY_MS, run)
    except Exception:
        panel._apkpy_gradient_pending = False


_FLAT = {}
_FLAT_LIMIT = 16


def flatten(picture, base_rgb):
    """``picture`` (RGBA) over a plain ``base_rgb``, as RGB.

    Every label under a gradient asks for its piece through ``picture_at()``;
    on a long screen that was hundreds of full-size composites per pass, which
    took minutes. ``gradient_image.render`` hands back the same image while
    the size holds, so the result is kept by that image and the base colour.
    """
    from PIL import Image
    key = (id(picture), base_rgb)
    found = _FLAT.pop(key, None)
    if found is None or found[0] is not picture:
        base = Image.new("RGBA", picture.size, tuple(base_rgb) + (255,))
        base.alpha_composite(picture)
        found = (picture, base.convert("RGB"))
    _FLAT[key] = found
    while len(_FLAT) > _FLAT_LIMIT:
        _FLAT.pop(next(iter(_FLAT)))
    return found[1]


def _walk(widget):
    pending = [widget]
    while pending:
        current = pending.pop()
        yield current
        try:
            pending.extend(current.winfo_children())
        except Exception:
            pass


def _rgb(widget, colour):
    try:
        return tuple(v >> 8 for v in widget.winfo_rgb(colour))
    except Exception:
        return None


def paint(panel):
    from .. import ui
    state = panel.__dict__.get("_apkpy_gradient_under")
    if state is None or not panel.winfo_ismapped():
        return
    content, picture_at, surface = state
    found = picture_at()
    if found is None:
        return
    image, ox, oy = found
    # What the content shows now (an opacity around it may have mixed it).
    try:
        surface = tk.Misc.cget(content, "bg")
    except Exception:
        pass
    surface_rgb = _rgb(panel, surface)
    px, py = panel.winfo_rootx(), panel.winfo_rooty()

    def region(left, top, width, height):
        """The picture under a box at panel coordinates, edges extended."""
        from PIL import Image
        tile = Image.new("RGB", (max(1, width), max(1, height)), surface_rgb or (0, 0, 0))
        x1, y1 = max(left, ox), max(top, oy)
        x2, y2 = min(left + width, ox + image.width), min(top + height, oy + image.height)
        if x2 > x1 and y2 > y1:
            tile.paste(image.crop((x1 - ox, y1 - oy, x2 - ox, y2 - oy)), (x1 - left, y1 - top))
        return tile

    for widget in _walk(content):
        if widget.__dict__.get("_apkpy_see_skip"):
            continue
        if widget is not content and widget.__dict__.get("_apkpy_gradient_under") is not None:
            # It draws its own content, over this picture. A label draws all
            # of itself (backdrop()); a panel's canvas still needs this
            # gradient behind its rounded corners, so it is painted below.
            schedule(widget)
            if isinstance(widget, tk.Label):
                continue
        if not isinstance(widget, (tk.Canvas, tk.Label, tk.Frame)):
            continue
        try:
            if not widget.winfo_ismapped():
                continue
            wx, wy = widget.winfo_rootx() - px, widget.winfo_rooty() - py
            ww, wh = widget.winfo_width(), widget.winfo_height()
        except Exception:
            continue
        if ww < 1 or wh < 1:
            continue
        try:
            own = _rgb(widget, tk.Misc.cget(widget, "bg"))
        except Exception:
            continue
        # Painted before by this gradient (its colour since mixed by an
        # opacity, say) still is; one painted by another -- a card's content
        # under a screen's gradient -- is that one's.
        if own != surface_rgb and widget.__dict__.get("_apkpy_under_painted") is not panel:
            continue
        widget._apkpy_under_painted = panel
        if isinstance(widget, tk.Label):
            paint_label(widget, lambda x, y, w, h, wx=wx, wy=wy: region(wx + x, wy + y, w, h))
        else:
            ui._see_paint(widget, region(wx, wy, ww, wh))


def backdrop(widget, width, height):
    """What the nearest gradient around ``widget`` shows under it, as an RGB
    picture ``width`` x ``height``, or None when there is none."""
    panel = getattr(widget, "master", None)
    while panel is not None and panel.__dict__.get("_apkpy_gradient_under") is None:
        panel = getattr(panel, "master", None)
    if panel is None:
        return None
    content, picture_at, surface = panel._apkpy_gradient_under
    found = picture_at()
    if found is None:
        return None
    from PIL import Image
    image, ox, oy = found
    left = widget.winfo_rootx() - panel.winfo_rootx() - ox
    top = widget.winfo_rooty() - panel.winfo_rooty() - oy
    tile = Image.new("RGB", (width, height), _rgb(panel, tk.Misc.cget(content, "bg")) or (0, 0, 0))
    x1, y1 = max(left, 0), max(top, 0)
    x2, y2 = min(left + width, image.width), min(top + height, image.height)
    if x2 > x1 and y2 > y1:
        tile.paste(image.crop((x1, y1, x2, y2)), (x1 - left, y1 - top))
    return tile


def paint_label(label, region):
    """Show ``region(x, y, w, h)`` (label coordinates) under the label's text,
    with the text where Tk puts it without a picture."""
    from PIL import ImageTk
    state = label.__dict__.get("_apkpy_under_state")
    if state is None:
        state = {key: tk.Misc.cget(label, key)
                 for key in ("padx", "pady", "anchor", "bd", "highlightthickness")}
        label._apkpy_under_state = state
        _watch_text(label)
    elif state.get("painted"):
        # Measured again from the label as it is without a picture: its
        # text, wrap or width may have changed since.
        _restore(label, state)
        state["painted"] = False
        panel = _panel_of(label)
        if panel is not None:
            schedule(panel)
        return
    W, H = label.winfo_width(), label.winfo_height()
    if W < 2 or H < 2:
        return
    edge = _px(label, state["bd"]) + _px(label, state["highlightthickness"])
    padx, pady = _px(label, state["padx"]), _px(label, state["pady"])
    text = str(tk.Misc.cget(label, "text"))
    if text:
        tw = max(0, label.winfo_reqwidth() - 2 * (edge + padx))
        th = max(0, label.winfo_reqheight() - 2 * (edge + pady))
    else:
        tw = th = 0
    anchor = str(state["anchor"])
    left, right = edge + padx, W - edge - padx
    top, bottom = edge + pady, H - edge - pady
    side = _HORIZONTAL.get(anchor)
    x_t = left if side == "w" else (right - tw if side == "e" else (left + right - tw) / 2.0)
    side = _VERTICAL.get(anchor)
    y_t = top if side == "n" else (bottom - th if side == "s" else (top + bottom - th) / 2.0)
    centre_x, centre_y = x_t + tw / 2.0, y_t + th / 2.0
    hl = _px(label, state["highlightthickness"])
    inner_w, inner_h = W - 2 * hl, H - 2 * hl
    centre_x, centre_y = centre_x - hl, centre_y - hl
    if centre_x <= inner_w / 2.0:
        horizontal, I = "e", int(round(2 * (inner_w - centre_x)))
        image_x = inner_w - I
    else:
        horizontal, I = "w", int(round(2 * centre_x))
        image_x = 0
    if centre_y <= inner_h / 2.0:
        vertical, J = "s", int(round(2 * (inner_h - centre_y)))
        image_y = inner_h - J
    else:
        vertical, J = "n", int(round(2 * centre_y))
        image_y = 0
    photo = ImageTk.PhotoImage(region(image_x + hl, image_y + hl, max(1, I), max(1, J)),
                               master=label)
    label._apkpy_see_photo = photo
    state["painting"] = True
    try:
        tk.Label.configure(label, image=photo, compound="center", anchor=vertical + horizontal,
                           padx=0, pady=0, bd=0, width=inner_w, height=inner_h)
    finally:
        state["painting"] = False
    state["painted"] = True


def _px(label, value):
    """A size Tk gave back, in pixels. The Tk of Python 3.8 to 3.11 gives
    padx, bd and the like as a Tcl_Obj, which int() refuses: the label was
    left without its rounded or gradient background in the Previewer."""
    return int(round(float(label.winfo_fpixels(str(value)))))


def _restore(label, state):
    state["painting"] = True
    try:
        tk.Label.configure(label, image="", width=0, height=0, padx=state["padx"],
                           pady=state["pady"], anchor=state["anchor"], bd=state["bd"])
    finally:
        state["painting"] = False


def _watch_text(label):
    """A new text, font or wrap moves the text: draw the picture again."""
    configure_ = label.configure

    def configure(cnf=None, **kw):
        if isinstance(cnf, dict):
            kw = dict(cnf, **kw)
            cnf = None
        result = configure_(cnf, **kw) if cnf is not None or not kw else configure_(**kw)
        state = label.__dict__.get("_apkpy_under_state")
        if kw and state is not None and not state.get("painting"):
            for key in ("padx", "pady", "anchor"):
                if key in kw:
                    state[key] = kw[key]
            if _TEXT_OPTIONS & set(kw):
                panel = _panel_of(label)
                if panel is not None:
                    schedule(panel)
        return result

    label.configure = label.config = configure


def _panel_of(widget):
    while widget is not None:
        if widget.__dict__.get("_apkpy_gradient_under") is not None:
            return widget
        widget = getattr(widget, "master", None)
    return None
