"""Bottom sheets: the sizes and the drag both runtimes follow.

A sheet is drawn twice -- by the Previewer and, on the phone, by Material's
BottomSheetDialog around a layout ApkPy writes. The sizes here are Material
3's (in dp on the phone and px in the Previewer, which is the same number),
and ``settle`` is what Material's BottomSheetBehavior decides when a drag
ends, so a sheet let go in the Previewer lands where it would on the phone.

A sheet with ``screen=`` holds components: ``label("...", parent=sheet)``.
Its body is a column with ``DEFAULT_STYLE``, which the sheet's own CSS (by
its ``id``) overrides like any container's.
"""

CODE = "U2045"
DOCS = "https://repo-apkpy.pages.dev/overlays-states/#a-sheet-with-components"

RADIUS = 28             # the two top corners
HANDLE_WIDTH = 32
HANDLE_HEIGHT = 4
HANDLE_PAD = 22         # above and below the handle: a 48 strip to drag by
HANDLE_ALPHA = 0.4      # of the secondary text colour
SCRIM = 0.32            # black over the screen behind
TOP_GAP = 56            # the sheet never covers the top of the screen
SIDE = 24               # the title's and the body's distance from the edges
TITLE_SIZE = 22         # sp / px, Material's title-large
CONTENT_SIZE = 14
TITLE_GAP = 4           # between the title and the text under it
HEADER_GAP = 16         # between the header and the components

# When a drag ends: past half way, or flung down, the sheet closes.
DISMISS_FRACTION = 0.5
FLING = 500             # px (dp) a second

OPEN_MS = 250
CLOSE_MS = 200

# The body is a column whose components are as wide as the sheet, with
# their words at the start. A sheet's own CSS wins, property by property.
DEFAULT_STYLE = {
    'display': 'flex',
    'flex-direction': 'column',
    'align-items': 'stretch',
    'gap': '12px',
    'padding': '0px %dpx %dpx %dpx' % (SIDE, SIDE, SIDE),
    'margin': '0px',
}

# Material 3's surface-container-low and inks, for an app with no Theme.
_SURFACE = '#F7F2FA'
_TEXT = '#1D1B20'
_MUTED = '#49454F'


def refuse(message, received, line=0, suggestions=None):
    from .diagnostics import ApkpyError
    raise ApkpyError(
        message,
        code=CODE,
        title="A bottom sheet ApkPy cannot build",
        cause=("A sheet that holds components is built into one screen's "
               "layout, so it has to say which screen, and its rows are the "
               "components you put in it."),
        expected=('filters = bottom_sheet("Filters", screen=home)\n'
                  'chips(["Newest", "Price"], parent=filters)\n'
                  'button("Apply", command=filters.close, parent=filters)'),
        received=received,
        suggestions=suggestions or [
            'Add screen=<the screen it opens over> to bottom_sheet().',
            'A sheet with only a title, text and items= needs no screen.',
        ],
        docs=DOCS,
        line=line or 0,
    )


def is_composed(screen):
    """Whether the sheet holds components: it does when it names a screen."""
    return screen is not None


def check_plain_arguments(composed, items, line=0):
    """items= draws the rows of a plain sheet; a sheet of components has
    components for rows."""
    if composed and items:
        refuse('bottom_sheet(screen=...) holds components, so it takes no items=.',
               'bottom_sheet(..., items=[...], screen=...)', line,
               ['Put list_row(...) or button(...) in it with parent=<the sheet>.',
                'Or drop screen= for a plain sheet with a title, text and items=.'])


def body_style(own):
    """The style of the sheet's body: the defaults under the sheet's CSS."""
    style = dict(DEFAULT_STYLE)
    style.update(own or {})
    return style


def max_height(window_height):
    return max(0, int(window_height) - TOP_GAP)


def height(content_height, window_height):
    """How tall the sheet is: its content, up to what the window allows."""
    return max(0, min(int(content_height), max_height(window_height)))


def settle(offset, sheet_height, velocity=0.0):
    """'open' or 'closed' for a sheet let go ``offset`` below where it rests,
    moving ``velocity`` px a second (down is positive)."""
    if sheet_height <= 0:
        return 'closed'
    if velocity >= FLING:
        return 'closed'
    if velocity <= -FLING:
        return 'open'
    return 'closed' if offset > sheet_height * DISMISS_FRACTION else 'open'


def scrim_alpha(offset, sheet_height):
    """The scrim fades as the sheet leaves."""
    if sheet_height <= 0:
        return 0.0
    shown = 1.0 - min(1.0, max(0.0, float(offset) / float(sheet_height)))
    return round(SCRIM * shown, 4)


def colors(tokens, own=None):
    tokens = tokens or {}
    own = own or {}
    return {
        'surface': (own.get('background-color') or tokens.get('surface_low')
                    or tokens.get('surface') or _SURFACE),
        'title': tokens.get('text') or _TEXT,
        'content': tokens.get('text_secondary') or _MUTED,
        'handle': tokens.get('text_secondary') or _MUTED,
    }
