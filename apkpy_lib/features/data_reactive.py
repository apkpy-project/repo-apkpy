"""Relations and lifecycle-aware query observation for ApkPy Data Core.

The module is intentionally independent from Tk and Android.  The owner passed
to :class:`QuerySubscription` is the public ``db`` object, which supplies the
single data executor and the UI-thread dispatcher.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import threading
from typing import Any, Optional


_UNSET = object()


@dataclass(frozen=True)
class RelationDef:
    """A controlled one-to-many relation declared as part of a schema."""

    name: str
    parent: Any
    child: Any
    foreign_key: str
    parent_as: str
    children_as: str
    on_delete: str = "restrict"

    def describe(self) -> dict:
        return {
            "name": self.name,
            "parent": self.parent.name,
            "child": self.child.name,
            "foreign_key": self.foreign_key,
            "parent_as": self.parent_as,
            "children_as": self.children_as,
            "on_delete": self.on_delete,
        }


class QuerySubscription:
    """A query that reruns after committed writes while its screen is active."""

    def __init__(
        self, owner, model, *, filters=None, order_by=None, limit=None,
        offset=0, include=None, screen=None, on_change=None, on_error=None,
    ):
        self.owner = owner
        self.model = model
        self.filters = list(filters or ())
        self.order_by = list(order_by or ())
        self.limit = limit
        self.offset = int(offset or 0)
        self.include = list(include or ())
        self.screen = screen
        self.on_change = on_change
        self.on_error = on_error
        self._lock = threading.RLock()
        self._active = False
        self._closed = False
        self._running = False
        self._pending = False
        self._force = False
        self._generation = 0
        self._snapshot: Optional[str] = None
        self.dependencies = owner._data_query_dependencies(model, self.include)

    @property
    def closed(self):
        return self._closed

    def resume(self):
        with self._lock:
            if self._closed:
                return self
            self._active = True
        self.refresh()
        return self

    def pause(self):
        with self._lock:
            self._active = False
            self._generation += 1
        return self

    def refresh(self):
        """Force the current query to run once while the screen is active."""
        with self._lock:
            if self._closed or not self._active:
                return self
            self._force = True
        self._schedule()
        return self

    def update_query(
        self, *, filters=_UNSET, order_by=_UNSET, limit=_UNSET,
        offset=_UNSET, include=_UNSET,
    ):
        """Replace selected query arguments and immediately requery."""
        with self._lock:
            if self._closed:
                return self
            if filters is not _UNSET:
                self.filters = list(filters or ())
            if order_by is not _UNSET:
                self.order_by = list(order_by or ())
            if limit is not _UNSET:
                self.limit = limit
            if offset is not _UNSET:
                self.offset = int(offset or 0)
            if include is not _UNSET:
                self.include = list(include or ())
                self.dependencies = self.owner._data_query_dependencies(
                    self.model, self.include,
                )
            self._generation += 1
            self._snapshot = None
            self._force = True
            self._pending = self._running
        self._schedule()
        return self

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._active = False
            self._pending = False
            self._generation += 1
        self.owner._data_remove_observer(self)

    def invalidate(self, models):
        with self._lock:
            if self._closed or not self._active:
                return
            if models is not None and not (self.dependencies & set(models)):
                return
            self._pending = self._running
        self._schedule()

    def _schedule(self):
        with self._lock:
            if self._closed or not self._active:
                return
            if self._running:
                self._pending = True
                return
            self._running = True
            self._pending = False
            generation = self._generation
            force = self._force
            self._force = False

        def loaded(rows):
            try:
                materialized = list(rows or ())
                snapshot = json.dumps(
                    materialized, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":"), default=str,
                )
                callback = None
                with self._lock:
                    current = (
                        not self._closed and self._active
                        and generation == self._generation
                    )
                    if current and (force or snapshot != self._snapshot):
                        self._snapshot = snapshot
                        callback = self.on_change
                if callback is not None:
                    callback(self.owner._json_rows(materialized))
            finally:
                self._complete(generation)

        def failed(message):
            try:
                with self._lock:
                    current = (
                        not self._closed and self._active
                        and generation == self._generation
                    )
                if current:
                    if self.on_error is not None:
                        self.on_error(str(message))
                    else:
                        print("[data observe]", message)
            finally:
                self._complete(generation)

        self.owner._data_find(
            self.model, self.filters, self.order_by, self.limit, self.offset,
            loaded, failed, self.include,
        )

    def _complete(self, generation):
        rerun = False
        with self._lock:
            if generation == self._generation:
                self._running = False
                rerun = self._pending and self._active and not self._closed
                self._pending = False
            elif not self._closed:
                # A newer generation superseded this result.  Its query may
                # now start because the single in-flight slot is free.
                self._running = False
                rerun = self._active
        if rerun:
            self._schedule()


__all__ = ["RelationDef", "QuerySubscription"]
