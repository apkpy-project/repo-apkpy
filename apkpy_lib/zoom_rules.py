"""The full-screen picture viewer: the arithmetic both runtimes follow.

``image(src, zoom=True)`` opens the picture over the whole screen when it is
tapped, and ``view_image(src)`` opens any picture from a function. In the
viewer the picture can be pinched, double-tapped and dragged. It is drawn
twice -- by the Previewer and by ApkpyZoom on the phone -- so where the
picture sits, how far it zooms and where a drag stops are decided here, and
ApkpyZoom mirrors ``fit``, ``clamp_offset``, ``zoom_at`` and ``double_tap``
one for one.

A picture's state is its ``zoom`` (1 is fitted to the screen) and the
top-left corner ``(x, y)`` of where it is drawn. Sizes are in dp on the
phone and px in the Previewer, which is the same number.
"""

CODE = "U2046"
DOCS = "https://repo-apkpy.pages.dev/ui-components/#a-picture-that-opens-and-zooms"

MIN_ZOOM = 1.0
MAX_ZOOM = 4.0
DOUBLE_TAP = 2.5        # what a double tap zooms to, and back from
WHEEL_STEP = 1.2        # one notch of the Previewer's mouse wheel

CLOSE = 48              # the close button's touch square, top start
CLOSE_ICON = 24
CLOSE_INSET = 8         # from the top and the side, under the status bar

DISMISS = 120           # dragged down this far, a fitted picture closes
OPEN_MS = 250
CLOSE_MS = 200

BACKDROP = '#000000'
INK = '#FFFFFF'


def refuse(message, received, line=0, suggestions=None):
    from .diagnostics import ApkpyError
    raise ApkpyError(
        message,
        code=CODE,
        title="A picture viewer ApkPy cannot build",
        cause=("zoom=True makes a tap on a picture open it full screen, so "
               "the tap cannot also run a command; and view_image() opens "
               "one picture, named by its file or its address."),
        expected='image("beach.jpg", id="photo", zoom=True, screen=home)',
        received=received,
        suggestions=suggestions or [
            'Drop command= and keep zoom=True, or the other way round.',
            'From a function: view_image("beach.jpg") or view_image(item["photo"]).',
        ],
        docs=DOCS,
        line=line or 0,
    )


def check_image(zoom, command, avatar=False, line=0):
    """What a tap does has one answer."""
    if zoom and command is not None:
        refuse('image(zoom=True) opens the picture when it is tapped, so it takes no command=.',
               'image(..., zoom=True, command=...)', line)
    if zoom and avatar:
        refuse('zoom=True is for image(); an avatar is too small a picture to open.',
               'avatar(..., zoom=True)', line,
               ['Use image(src, zoom=True) for the picture that opens.'])


def fit(image_w, image_h, view_w, view_h):
    """The scale that fits the whole picture in the view, never larger than
    the view allows. 0 when there is nothing to draw."""
    if image_w <= 0 or image_h <= 0 or view_w <= 0 or view_h <= 0:
        return 0.0
    return min(float(view_w) / image_w, float(view_h) / image_h)


def clamp_zoom(zoom):
    return max(MIN_ZOOM, min(MAX_ZOOM, float(zoom)))


def clamp_offset(offset, content, view):
    """Where a picture ``content`` wide may start in a view ``view`` wide:
    centred while it is smaller, and never past either edge once larger."""
    if content <= view:
        return (view - content) / 2.0
    return max(float(view - content), min(0.0, float(offset)))


def place(zoom, x, y, image_w, image_h, view_w, view_h):
    """(zoom, x, y) made legal: the zoom in range, the picture centred or
    held inside the edges."""
    zoom = clamp_zoom(zoom)
    scale = fit(image_w, image_h, view_w, view_h) * zoom
    return (zoom,
            clamp_offset(x, image_w * scale, view_w),
            clamp_offset(y, image_h * scale, view_h))


def zoom_at(zoom, x, y, focus_x, focus_y, factor, image_w, image_h, view_w, view_h):
    """Zoom by ``factor`` keeping the point under ``(focus_x, focus_y)``
    where it is -- the point between two fingers, or under the mouse."""
    target = clamp_zoom(zoom * factor)
    if zoom <= 0:
        return place(target, x, y, image_w, image_h, view_w, view_h)
    ratio = target / zoom
    return place(target,
                 focus_x - (focus_x - x) * ratio,
                 focus_y - (focus_y - y) * ratio,
                 image_w, image_h, view_w, view_h)


def double_tap(zoom):
    """The zoom a double tap goes to: in, or back to fitted."""
    return DOUBLE_TAP if zoom < (MIN_ZOOM + DOUBLE_TAP) / 2.0 else MIN_ZOOM


def can_dismiss(zoom):
    """A drag down closes the viewer only while the picture is fitted; once
    zoomed, a drag moves the picture."""
    return zoom <= MIN_ZOOM + 0.01


def dismisses(drag_y):
    return drag_y >= DISMISS


def backdrop_alpha(drag_y, view_h):
    """The black behind the picture fades as it is dragged away."""
    if view_h <= 0:
        return 1.0
    return round(max(0.0, 1.0 - max(0.0, float(drag_y)) / (view_h * 0.75)), 4)


def thumb_start(thumb, image_w, image_h, view_w, view_h):
    """Where the picture is drawn at the start of the opening: covering its
    thumbnail ``(x, y, w, h)``, in the viewer's coordinates. Returns
    (scale, x, y) with scale absolute, not relative to fit."""
    tx, ty, tw, th = thumb
    if image_w <= 0 or image_h <= 0 or tw <= 0 or th <= 0:
        scale = fit(image_w, image_h, view_w, view_h)
        return (scale, clamp_offset(0, image_w * scale, view_w),
                clamp_offset(0, image_h * scale, view_h))
    scale = max(float(tw) / image_w, float(th) / image_h)
    return (scale, tx + (tw - image_w * scale) / 2.0, ty + (th - image_h * scale) / 2.0)
