"""See-through colours and ``opacity`` in the Previewer.

Tk has no alpha. The phone does: ``background-color: rgba(0, 0, 0, 0.5)`` is a
glass panel over the screen, and ``opacity: 0.5`` lays a whole component over
what is behind it at half strength. In the Previewer the first was a solid
black box, a text colour with alpha stopped the app ("invalid color name
#99FFFFFF"), and the second did nothing except on an image.

Both are done here the only way Tk allows: by mixing each colour with the one
behind it. On a plain surface that is exactly the colour the phone shows.

* :func:`install_alpha_net` makes every colour with alpha that reaches Tk
  mixed over what is behind it, so none can stop the app.
* :func:`over` is the same mixing for a renderer that knows the surface below.
* :func:`apply_opacity` shows a rendered component and everything inside it
  at an opacity, and keeps it so through a hover, a fade or a redraw.
"""

import re
import tkinter as tk

from ..core.css_colors import over  # noqa: F401  (the renderers' mixing)

_ALPHA_HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{4})$")

# What a widget paints its box with: these go over the parent's surface.
_SURFACE_OPTIONS = frozenset((
    "bg", "background", "activebackground", "highlightbackground",
    "selectbackground", "readonlybackground", "disabledbackground", "troughcolor",
))
# What a canvas item paints. "transparent" there is no paint at all.
_ITEM_OPTIONS = frozenset((
    "fill", "outline", "activefill", "activeoutline", "disabledfill", "disabledoutline",
))


def _is_alpha(value):
    """A colour Tk would refuse because it carries alpha."""
    if not isinstance(value, str):
        return False
    raw = value.strip()
    return raw.lower() == "transparent" or bool(_ALPHA_HEX.match(raw))


def _split(value):
    """``#AARRGGBB`` / ``#ARGB`` / ``transparent`` -> (alpha 0-1, (r, g, b))."""
    raw = value.strip()
    if raw.lower() == "transparent":
        return 0.0, (0, 0, 0)
    digits = raw[1:]
    if len(digits) == 4:
        digits = "".join(d * 2 for d in digits)
    alpha = int(digits[:2], 16) / 255.0
    return alpha, tuple(int(digits[i:i + 2], 16) for i in (2, 4, 6))


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def _mix(under, top, amount):
    return tuple(u + (t - u) * amount for u, t in zip(under, top))


# ── The net under every renderer ─────────────────────────────────────────────

def _surface(widget):
    """The colour ``widget`` paints its box with, or its nearest ancestor's."""
    while widget is not None:
        try:
            value = str(widget.tk.call(widget._w, "cget", "-background"))
        except Exception:
            value = ""
        if value and not _is_alpha(value):
            return value
        widget = getattr(widget, "master", None)
    return "#FFFFFF"


def _rgb(widget, color):
    try:
        return tuple(v >> 8 for v in widget._root().winfo_rgb(color))
    except Exception:
        return (255, 255, 255)


def _over_widget(widget, value, behind):
    alpha, top = _split(value)
    return _hex(_mix(_rgb(widget, behind), top, alpha))


def _carries_alpha(cnf):
    if isinstance(cnf, dict):
        return any(_is_alpha(v) for v in cnf.values())
    if isinstance(cnf, (tuple, list)):
        return any(_carries_alpha(c) for c in cnf)
    return False


def _resolve(widget, options):
    """The same options with every colour carrying alpha mixed over its surface."""
    parent = getattr(widget, "master", None)
    own = None
    for key in ("bg", "background"):
        value = options.get(key)
        if _is_alpha(value):
            options[key] = _over_widget(widget, value, _surface(parent))
        if options.get(key):
            own = options[key]
    for key, value in list(options.items()):
        name = key.rstrip("_")
        if name in ("bg", "background") or not _is_alpha(value):
            continue
        if name in _ITEM_OPTIONS:
            alpha, _ = _split(value)
            options[key] = "" if alpha <= 0 else _over_widget(widget, value, _surface(widget))
        elif name in _SURFACE_OPTIONS:
            options[key] = _over_widget(widget, value, _surface(parent))
        else:  # a text, a cursor, a ring: over the widget's own surface
            options[key] = _over_widget(widget, value, own or _surface(widget))
    return options


def install_alpha_net():
    """Every colour with alpha that reaches Tk is mixed over what is behind it.

    Widget creation, ``configure`` and the canvas's ``create_*`` and
    ``itemconfigure`` all turn their options into Tcl arguments through
    ``Misc._options``; the colours are resolved there. A call without such a
    colour takes the original path untouched.
    """
    original = tk.Misc._options
    if getattr(original, "_apkpy_alpha_net", False):
        return

    def _options(self, cnf, kw=None):
        try:
            found = _carries_alpha(cnf) or _carries_alpha(kw)
        except Exception:
            found = False
        if not found:
            return original(self, cnf, kw)
        merged = dict(tk._cnfmerge((cnf, kw)) if kw else tk._cnfmerge(cnf))
        try:
            merged = _resolve(self, merged)
        except Exception:
            pass
        return original(self, merged)

    _options._apkpy_alpha_net = True
    tk.Misc._options = _options


# ── opacity ──────────────────────────────────────────────────────────────────
# Android draws a component with `opacity` into a layer and lays the layer over
# what is behind it at that strength. Here each colour the component paints is
# mixed towards the colour behind it. The mixing sits in the widget's
# configure and the canvas's create_* / itemconfigure, so a hover, a fade or a
# redraw on resize keeps it; cget answers the colour the code set, because a
# fade reads it and writes it back. Nested opacities mix one after the other,
# the innermost first, which is how the layers compose.

LAYERS_ATTR = "_apkpy_opacity_layers"
_WIDGET_OPTIONS = (
    "bg", "fg", "activebackground", "activeforeground", "highlightbackground",
    "highlightcolor", "insertbackground", "disabledforeground", "selectbackground",
    "selectforeground",
)
_ALIASES = {"background": "bg", "foreground": "fg"}
_CANVAS_OPTIONS = ("fill", "outline")
_CREATORS = ("create_rectangle", "create_oval", "create_polygon", "create_line",
             "create_text", "create_arc")
_MAX_WIDGETS = 800
_AA_REGISTRY = "_apkpy_aa"      # shapes ui.py draws as images; they mix as drawn


def layered(widget, rgb):
    """``rgb`` as it shows through the opacities ``widget`` sits in."""
    layers = getattr(widget, "__dict__", {}).get(LAYERS_ATTR)
    if not layers:
        return rgb
    for opacity, backdrop in layers:
        rgb = _mix(backdrop, rgb, opacity)
    return tuple(int(round(c)) for c in rgb)


def opacity_product(widget):
    """How strongly ``widget`` shows, all its opacities together (1.0 for none)."""
    product = 1.0
    for opacity, _ in getattr(widget, "__dict__", {}).get(LAYERS_ATTR) or ():
        product *= opacity
    return product


def _shown(widget, color, layers):
    if not layers or not isinstance(color, str):
        return color
    raw = color.strip()
    if not raw or _is_alpha(raw) or raw.lower() == "none":
        return color
    try:
        rgb = tuple(v >> 8 for v in widget.winfo_rgb(raw))
    except Exception:
        return color
    for opacity, backdrop in layers:
        rgb = _mix(backdrop, rgb, opacity)
    return _hex(rgb)


def _install(widget):
    """Teach ``widget`` to show its colours through its opacity layers."""
    layers = widget.__dict__.get(LAYERS_ATTR)
    if layers is not None:
        return layers
    layers = []
    widget.__dict__[LAYERS_ATTR] = layers
    authored = {}               # option -> (what the code set, what is shown)
    configure_, cget_ = widget.configure, widget.cget

    def configure(cnf=None, **kw):
        if isinstance(cnf, dict):
            kw = dict(cnf, **kw)
            cnf = None
        if cnf is not None or not kw:
            return configure_(cnf, **kw)
        for key, value in list(kw.items()):
            name = _ALIASES.get(key, key)
            if name in _WIDGET_OPTIONS and isinstance(value, str) and layers:
                shown = _shown(widget, value, layers)
                authored[name] = (value, shown)
                kw[key] = shown
        return configure_(**kw)

    def cget(key):
        value = cget_(key)
        entry = authored.get(_ALIASES.get(key, key))
        if entry is not None and str(value) == entry[1]:
            return entry[0]
        return value

    widget.configure = widget.config = configure
    widget.cget = cget
    if isinstance(widget, tk.Canvas):
        _install_canvas(widget, layers)
    return layers


def _install_canvas(canvas, layers):
    authored = {}               # (item, option) -> (what the code set, what is shown)
    itemconfigure_, itemcget_ = canvas.itemconfigure, canvas.itemcget

    def as_image(item):
        return item in (canvas.__dict__.get(_AA_REGISTRY) or {})

    def forget_deleted():
        if len(authored) > 2048:
            alive = set(canvas.find_all())
            for key in [k for k in authored if k[0] not in alive]:
                del authored[key]

    def itemconfigure(tag_or_id, cnf=None, **kw):
        if isinstance(cnf, dict):
            kw = dict(cnf, **kw)
            cnf = None
        if (cnf is not None or not kw or not layers
                or not any(o in kw for o in _CANVAS_OPTIONS)):
            return itemconfigure_(tag_or_id, cnf, **kw)
        for item in canvas.find_withtag(tag_or_id):
            if as_image(item):
                itemconfigure_(item, **kw)
                continue
            each = dict(kw)
            for option in _CANVAS_OPTIONS:
                value = each.get(option)
                if isinstance(value, str) and value:
                    each[option] = _shown(canvas, value, layers)
                    authored[(item, option)] = (value, each[option])
            itemconfigure_(item, **each)
        return None

    def itemcget(tag_or_id, option):
        value = itemcget_(tag_or_id, option)
        if option in _CANVAS_OPTIONS:
            found = canvas.find_withtag(tag_or_id)
            entry = authored.get((found[0], option)) if found else None
            if entry is not None and str(value) == entry[1]:
                return entry[0]
        return value

    def creator(original):
        def create(*args, **kw):
            if args and isinstance(args[-1], dict):
                kw = dict(args[-1], **kw)
                args = args[:-1]
            set_by_code = {}
            if layers:
                for option in _CANVAS_OPTIONS:
                    value = kw.get(option)
                    if isinstance(value, str) and value:
                        set_by_code[option] = value
                        kw[option] = _shown(canvas, value, layers)
            item = original(*args, **kw)
            for option, value in set_by_code.items():
                authored[(item, option)] = (value, kw[option])
            if set_by_code:
                forget_deleted()
            return item
        return create

    canvas.itemconfigure = canvas.itemconfig = itemconfigure
    canvas.itemcget = itemcget
    for name in _CREATORS:
        setattr(canvas, name, creator(getattr(canvas, name)))


def apply_opacity(widgets, opacity, backdrop, redraw_image=None):
    """Show ``widgets`` and everything inside them at ``opacity`` over ``backdrop``.

    ``backdrop`` is the colour behind the component, ``(r, g, b)``.
    ``redraw_image(canvas, item)`` redraws a shape ui.py draws as an image, so
    its colours are mixed as it is drawn again.
    """
    layer = (max(0.0, min(1.0, float(opacity))), tuple(backdrop))
    budget = _MAX_WIDGETS
    stack = list(widgets)
    seen = set()
    while stack and budget > 0:
        widget = stack.pop()
        if id(widget) in seen:
            continue
        seen.add(id(widget))
        budget -= 1
        try:
            layers = _install(widget)
        except Exception:
            continue
        layers.append(layer)
        for option in _WIDGET_OPTIONS:
            try:
                value = widget.cget(option)
            except Exception:
                continue
            if isinstance(value, str) and value:
                try:
                    widget.configure(**{option: value})
                except Exception:
                    pass
        if isinstance(widget, tk.Canvas):
            _reapply_items(widget, redraw_image)
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _reapply_items(canvas, redraw_image):
    registry = canvas.__dict__.get(_AA_REGISTRY) or {}
    try:
        items = canvas.find_all()
    except Exception:
        return
    for item in items:
        if item in registry:
            if redraw_image is not None:
                try:
                    redraw_image(canvas, item)
                except Exception:
                    pass
            continue
        options = {}
        for option in _CANVAS_OPTIONS:
            try:
                value = canvas.itemcget(item, option)
            except Exception:
                continue
            if value:
                options[option] = value
        if options:
            try:
                canvas.itemconfigure(item, **options)
            except Exception:
                pass
