"""Swipe and drag on the rows of a list, said once for both runtimes.

The Previewer (``ui.py``) and the phone (``ApkpyGestures`` in
``core/features/gestures.py``) both read these numbers and names, the way
``chart_rules`` and ``theme`` are shared: a threshold written twice drifts,
and a row that commits at 40% of its width on the desktop and 50% on the phone
is two different apps.

A swipe is described by the direction the finger moves. ``swipe_right``
slides the row to the right and shows its action at the left edge, which is
where Gmail puts Archive; ``swipe_left`` shows its action at the right edge.
"""

CODE = "U2042"

# Past this fraction of the row's width, letting go completes the swipe;
# short of it, the row slides back. ItemTouchHelper's own default is 0.5,
# which asks for a long drag on a phone held in one hand.
SWIPE_THRESHOLD = 0.4

# A drag starts moving sideways once it has gone this far (dp/px), and more
# sideways than down -- the same 12 the pager uses, so a list inside a pager
# does not fight it.
SLOP = 12

# How long a finger rests on a row before it lifts for reordering (ms).
# Android's long press is 400-500ms depending on the device; the Previewer
# uses the same number for the mouse.
LONG_PRESS_MS = 450

# What the revealed strip draws: an icon and the action's words in white,
# 24dp from the edge the row left.
ICON_SIZE = 24
EDGE_PADDING = 24
LABEL_GAP = 8
LABEL_SIZE = 14
FOREGROUND = "#FFFFFF"

# Icons that take something away get the error colour unless told otherwise;
# everything else gets the theme's primary colour.
DESTRUCTIVE_ICONS = frozenset((
    "delete", "delete_outline", "delete_forever", "remove_circle",
    "remove_circle_outline", "block", "close", "cancel",
))
DESTRUCTIVE_COLOR = "#D93446"
FALLBACK_COLOR = "#6750A4"

# The words TalkBack offers for moving a row, next to each swipe's own text.
MOVE_UP = "Move up"
MOVE_DOWN = "Move down"
UNDO = "Undo"

# How long the Undo snackbar stays; on_swipe runs once it has gone without
# being pressed (Material's LENGTH_LONG is 2750ms, short for reading it).
UNDO_MS = 4000

# How long a swiped row takes to slide off, or back (ms).
SLIDE_MS = 160


def swipe_color(icon, own_color=None, tokens=None):
    """The colour of the strip a swipe reveals."""
    if own_color:
        return str(own_color)
    if str(icon or "").strip().lower() in DESTRUCTIVE_ICONS:
        return DESTRUCTIVE_COLOR
    tokens = tokens or {}
    return tokens.get("primary") or FALLBACK_COLOR


def commits(distance, width):
    """Whether letting go after *distance* of a row *width* wide completes it."""
    try:
        return abs(float(distance)) >= SWIPE_THRESHOLD * max(1.0, float(width))
    except (TypeError, ValueError):
        return False


def is_sideways(dx, dy):
    """A drag that has become a swipe: past the slop, and more across than down."""
    return abs(dx) > SLOP and abs(dx) > abs(dy) * 1.2


def moved_index(from_index, to_index, count):
    """Where a row dropped at *to_index* ends up, clamped to the list."""
    if count <= 0:
        return 0
    return max(0, min(int(count) - 1, int(to_index)))


def reorder(items, from_index, to_index):
    """The list with one row moved; the other rows keep their order."""
    out = list(items)
    if not out:
        return out
    source = max(0, min(len(out) - 1, int(from_index)))
    target = moved_index(source, to_index, len(out))
    row = out.pop(source)
    out.insert(target, row)
    return out


def accessibility_actions(right=None, left=None, reorder_enabled=False,
                          index=0, count=0):
    """The actions a screen reader offers on one row, in the order it lists them.

    Every swipe is also an action, so nobody needs the gesture to archive a
    message. Moving a row is "Move up" / "Move down" -- on every row, as the
    phone registers them once per recycled row view; the third value says
    whether it can do anything from this position (the first row cannot go
    up), and the Previewer greys out the one that cannot.
    """
    actions = []
    if right is not None:
        actions.append(("right", right.get("text") or right.get("icon") or "Swipe right", True))
    if left is not None:
        actions.append(("left", left.get("text") or left.get("icon") or "Swipe left", True))
    if reorder_enabled:
        actions.append(("up", MOVE_UP, index > 0))
        actions.append(("down", MOVE_DOWN, index < count - 1))
    return actions


__all__ = [
    "CODE", "SWIPE_THRESHOLD", "SLOP", "LONG_PRESS_MS", "ICON_SIZE",
    "EDGE_PADDING", "LABEL_GAP", "LABEL_SIZE", "FOREGROUND",
    "DESTRUCTIVE_ICONS", "DESTRUCTIVE_COLOR", "FALLBACK_COLOR", "MOVE_UP",
    "MOVE_DOWN", "UNDO", "UNDO_MS", "SLIDE_MS", "swipe_color", "commits", "is_sideways",
    "moved_index", "reorder", "accessibility_actions",
]
