"""Incremental feed state shared by ApkPy components and the Previewer.

The module deliberately knows nothing about Tkinter.  ``ui.py`` attaches a
small renderer bridge when a virtual collection is mounted, while these
helpers own the loading latch, ``has_more`` flag and data mutations.
"""

from __future__ import annotations

import copy
import json


def normalize_items(items):
    """Return *items* as a list while accepting JSON array strings."""
    if isinstance(items, str):
        try:
            # ``JsonRows`` intentionally subclasses ``str`` while exposing
            # row-style integer indexing.  Always coerce it back to a plain
            # string before handing it to the JSON decoder; otherwise the
            # Previewer can interpret a valid database result as an empty
            # feed when the decoder touches the overridden ``__getitem__``.
            items = json.loads(str(items))
        except (TypeError, ValueError):
            items = []
    if not isinstance(items, (list, tuple)):
        return []
    return list(items)


def state_for(component):
    """Return the persistent pagination state for a virtual collection."""
    state = getattr(component, "_feed_state", None)
    if state is None:
        state = {
            "loading": False,
            "refreshing": False,
            "has_more": True,
            "mode": None,
            "optimistic": {},
        }
        component._feed_state = state
    return state


def _require_virtual_collection(component):
    if getattr(component, "comp_type", None) != "virtual_collection":
        raise TypeError(
            "feed mutations and pagination methods require "
            "virtual_collection()"
        )


def _preview_call(component, name, *args):
    """Call a mounted Previewer bridge without coupling this module to Tk.

    Async database/network callbacks may finish after navigation destroyed the
    old widget tree.  The feed data must still be committed to the declarative
    component; a future render will bind a fresh bridge and read that state.
    """
    callback = getattr(component, name, None)
    if callback is None:
        return False
    try:
        callback(*args)
    except Exception:
        if getattr(component, name, None) is callback:
            setattr(component, name, None)
        return False
    return True


def _notify(component):
    _preview_call(
        component, "_feed_state_changed", dict(state_for(component))
    )


def bind_preview(component, update_items, state_changed):
    """Attach Previewer-only rendering callbacks to *component*."""
    _require_virtual_collection(component)
    component._feed_update_fn = update_items
    component._feed_state_changed = state_changed
    _notify(component)


def _invoke(component, callback, mode):
    if callback is None:
        return False
    state = state_for(component)
    if state["loading"]:
        return False
    if mode == "end" and not state["has_more"]:
        return False
    state["loading"] = True
    state["refreshing"] = mode == "refresh"
    state["mode"] = mode
    if mode == "refresh":
        # A refresh starts a new pagination generation.
        state["has_more"] = True
    _notify(component)
    try:
        callback()
    except Exception:
        state["loading"] = False
        state["refreshing"] = False
        state["mode"] = None
        _notify(component)
        raise
    return True


def request_end(component):
    """Request the next page once, respecting loading and ``has_more``."""
    _require_virtual_collection(component)
    return _invoke(
        component, component.kwargs.get("on_end_reached"), "end"
    )


def request_refresh(component):
    """Start the same callback used by pull-to-refresh."""
    _require_virtual_collection(component)
    return _invoke(component, component.kwargs.get("on_refresh"), "refresh")


def _complete(component, has_more):
    state = state_for(component)
    state["loading"] = False
    state["refreshing"] = False
    state["has_more"] = bool(has_more)
    state["mode"] = None
    _notify(component)


def replace_items(component, items, has_more=True):
    """Replace a virtual collection and finish any active load."""
    _require_virtual_collection(component)
    normalized = normalize_items(items)
    state_for(component)["optimistic"].clear()
    component._initial_value = list(normalized)
    component.kwargs["items"] = list(normalized)
    update = getattr(component, "_feed_update_fn", None)
    if update is not None:
        _preview_call(component, "_feed_update_fn", "replace", list(normalized))
    elif hasattr(component, "_list_update_fn"):
        _preview_call(component, "_list_update_fn", list(normalized))
    _complete(component, has_more)
    return len(normalized)


def append_items(component, items, has_more=True):
    """Append one page without replacing the existing data."""
    _require_virtual_collection(component)
    page = normalize_items(items)
    current = list(
        component._initial_value
        if component._initial_value is not None
        else component.kwargs.get("items", [])
    )
    current.extend(page)
    component._initial_value = current
    component.kwargs["items"] = list(current)
    update = getattr(component, "_feed_update_fn", None)
    if update is not None:
        _preview_call(component, "_feed_update_fn", "append", list(page))
    elif hasattr(component, "_list_update_fn"):
        _preview_call(component, "_list_update_fn", list(current))
    _complete(component, has_more)
    return len(page)


def _current_items(component):
    return list(
        component._initial_value
        if component._initial_value is not None
        else component.kwargs.get("items", [])
    )


def _store_items(component, items):
    current = list(items)
    component._initial_value = current
    component.kwargs["items"] = list(current)
    return current


def _optimistic_token(optimistic, item_id):
    if optimistic is True:
        return str(item_id)
    if optimistic in (False, None, ""):
        return None
    return str(optimistic)


def _capture_optimistic(component, token, items):
    if token is None:
        return
    history = state_for(component)["optimistic"]
    # Several changes may belong to the same optimistic transaction. Keep the
    # first snapshot so one rollback restores the state before the transaction.
    if token not in history:
        history[token] = copy.deepcopy(list(items))


def _object(value, name):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"{name} must be a dict or JSON object") from exc
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict or JSON object")
    return dict(value)


def _matching_index(items, item_id, key):
    for index, item in enumerate(items):
        if isinstance(item, dict) and item.get(key) == item_id:
            return index
    return -1


def prepend_items(component, items):
    """Insert records at the beginning while preserving their input order."""
    _require_virtual_collection(component)
    page = normalize_items(items)
    current = page + _current_items(component)
    _store_items(component, current)
    update = getattr(component, "_feed_update_fn", None)
    if update is not None:
        _preview_call(
            component, "_feed_update_fn", "prepend", {"items": list(page)}
        )
    elif hasattr(component, "_list_update_fn"):
        component._list_update_fn(list(current))
    return len(page)


def update_item(component, item_id, changes, key="id", optimistic=False):
    """Merge *changes* into one record selected by a stable key."""
    _require_virtual_collection(component)
    patch = _object(changes, "changes")
    current = _current_items(component)
    index = _matching_index(current, item_id, key)
    if index < 0 or not isinstance(current[index], dict):
        return False
    token = _optimistic_token(optimistic, item_id)
    _capture_optimistic(component, token, current)
    updated = dict(current[index])
    updated.update(patch)
    current[index] = updated
    _store_items(component, current)
    update = getattr(component, "_feed_update_fn", None)
    if update is not None:
        _preview_call(
            component,
            "_feed_update_fn",
            "update",
            {"index": index, "item": copy.deepcopy(updated)},
        )
    elif hasattr(component, "_list_update_fn"):
        component._list_update_fn(list(current))
    return True


def remove_item(component, item_id, key="id", optimistic=False):
    """Remove one record by key and optionally retain a rollback snapshot."""
    _require_virtual_collection(component)
    current = _current_items(component)
    index = _matching_index(current, item_id, key)
    if index < 0:
        return False
    token = _optimistic_token(optimistic, item_id)
    _capture_optimistic(component, token, current)
    current.pop(index)
    _store_items(component, current)
    update = getattr(component, "_feed_update_fn", None)
    if update is not None:
        _preview_call(
            component, "_feed_update_fn", "remove", {"index": index}
        )
    elif hasattr(component, "_list_update_fn"):
        component._list_update_fn(list(current))
    return True


def remove_at(component, index):
    """Take the row at *index* out, for a swipe; returns the item or None.

    Swiped rows need no key: the finger chose the row, not an id.
    """
    _require_virtual_collection(component)
    current = _current_items(component)
    if not 0 <= int(index) < len(current):
        return None
    item = current.pop(int(index))
    _store_items(component, current)
    if getattr(component, "_feed_update_fn", None) is not None:
        _preview_call(component, "_feed_update_fn", "remove", {"index": int(index)})
    return item


def insert_at(component, index, item):
    """Put a row back where it was -- the snackbar's Undo after a swipe."""
    _require_virtual_collection(component)
    current = _current_items(component)
    position = max(0, min(len(current), int(index)))
    current.insert(position, item)
    _store_items(component, current)
    if getattr(component, "_feed_update_fn", None) is not None:
        _preview_call(component, "_feed_update_fn", "rollback",
                      {"items": copy.deepcopy(current)})
    return position


def move_row(component, from_index, to_index):
    """Move one row, for a drag or TalkBack's Move up/down; returns its item."""
    from .. import gesture_rules
    _require_virtual_collection(component)
    current = _current_items(component)
    if not 0 <= int(from_index) < len(current):
        return None
    item = current[int(from_index)]
    moved = gesture_rules.reorder(current, from_index, to_index)
    _store_items(component, moved)
    if getattr(component, "_feed_update_fn", None) is not None:
        _preview_call(component, "_feed_update_fn", "rollback",
                      {"items": copy.deepcopy(moved)})
    return item


def scroll_to_index(component, index):
    """Bring the row at *index* into view, clamped to the current data.

    A collection that virtualises its rows cannot rely on the widget tree to
    find a row: only the data knows where a record sits. Both runtimes take
    the position from the same list for that reason.
    """
    _require_virtual_collection(component)
    total = len(_current_items(component))
    if total == 0:
        return False
    try:
        target = int(index)
    except (TypeError, ValueError):
        raise TypeError("scroll_to_index(index=...) must be an integer")
    target = max(0, min(total - 1, target))
    _preview_call(component, "_feed_update_fn", "scroll", {"index": target})
    return True


def scroll_to_end(component):
    """Bring the last row into view -- the message that just arrived."""
    _require_virtual_collection(component)
    return scroll_to_index(component, len(_current_items(component)) - 1)


def scroll_to_item(component, item_id, key="id"):
    """Bring one record into view, selected by the same key the mutations use."""
    _require_virtual_collection(component)
    index = _matching_index(_current_items(component), item_id, key)
    if index < 0:
        return False
    return scroll_to_index(component, index)


def merge_items(component, items, key="id"):
    """Upsert records without moving existing rows or creating duplicates."""
    _require_virtual_collection(component)
    incoming = normalize_items(items)
    current = _current_items(component)
    positions = {
        item.get(key): index
        for index, item in enumerate(current)
        if isinstance(item, dict) and item.get(key) is not None
    }
    changed = 0
    for item in incoming:
        if not isinstance(item, dict) or item.get(key) is None:
            current.append(copy.deepcopy(item))
            changed += 1
            continue
        item_key = item.get(key)
        index = positions.get(item_key)
        if index is None:
            positions[item_key] = len(current)
            current.append(copy.deepcopy(item))
            changed += 1
        else:
            merged = dict(current[index])
            merged.update(item)
            if merged != current[index]:
                current[index] = merged
                changed += 1
    _store_items(component, current)
    update = getattr(component, "_feed_update_fn", None)
    if update is not None:
        _preview_call(
            component,
            "_feed_update_fn",
            "merge",
            {"items": copy.deepcopy(current), "key": str(key)},
        )
    elif hasattr(component, "_list_update_fn"):
        component._list_update_fn(list(current))
    return changed


def _history_token(component, mutation_id):
    history = state_for(component)["optimistic"]
    if mutation_id not in (None, ""):
        return str(mutation_id)
    if not history:
        return None
    return next(reversed(history))


def rollback(component, mutation_id=None):
    """Restore an optimistic transaction, or the most recent one."""
    _require_virtual_collection(component)
    state = state_for(component)
    token = _history_token(component, mutation_id)
    if token is None or token not in state["optimistic"]:
        return False
    restored = state["optimistic"].pop(token)
    _store_items(component, copy.deepcopy(restored))
    update = getattr(component, "_feed_update_fn", None)
    if update is not None:
        _preview_call(
            component,
            "_feed_update_fn",
            "rollback",
            {"items": copy.deepcopy(restored)},
        )
    elif hasattr(component, "_list_update_fn"):
        component._list_update_fn(list(restored))
    return True


def commit(component, mutation_id=None):
    """Discard a rollback snapshot after the server accepts a mutation."""
    _require_virtual_collection(component)
    state = state_for(component)
    token = _history_token(component, mutation_id)
    if token is None or token not in state["optimistic"]:
        return False
    del state["optimistic"][token]
    return True


def finish_load(component, has_more=True):
    """Release the loading latch after an empty page or an error."""
    _require_virtual_collection(component)
    _complete(component, has_more)
    return bool(has_more)


def refresh(component):
    """Manually trigger the collection's pull-to-refresh callback."""
    return request_refresh(component)


__all__ = [
    "append_items",
    "bind_preview",
    "commit",
    "finish_load",
    "merge_items",
    "normalize_items",
    "prepend_items",
    "refresh",
    "remove_item",
    "replace_items",
    "request_end",
    "request_refresh",
    "rollback",
    "scroll_to_end",
    "scroll_to_index",
    "scroll_to_item",
    "state_for",
    "update_item",
]
