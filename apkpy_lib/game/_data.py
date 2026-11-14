"""Data tables and JSON for game code: table(), Ref, to_json(), from_json().

In the game these are translated (compiler/scripts.py, apkpygame.core.Data and
Table). Here they really run, so the rules of a game can be tested with
CPython (pytest) on the same data, giving the same values and the same JSON
text as the phone.
"""
import dataclasses
import json
import os
import typing
from ._pycompat import type_hints


class _RefAlias:
    """Ref[Move]: the id (a str) of a row of the Move table; the build checks it exists."""

    def __getitem__(self, record):
        return str


Ref = _RefAlias()


class Table:
    """The rows of a data table, by id (read the first time the table is used)."""

    def __init__(self, path, record):
        self.path, self.record = path, record
        self.root = os.environ.get("APKPYGAME_PROJECT") or os.getcwd()     # the project, when the module is imported
        self._rows = None

    def _load(self):
        if self._rows is None:
            self._rows = {}
            for row in read_rows(self.root, self.path):
                self._rows[row["id"]] = _build(row, self.record, self.path)
        return self._rows

    def get(self, id: str):
        rows = self._load()
        if id not in rows:
            raise KeyError("'%s' is not in %s" % (id, self.path))
        return rows[id]

    def has(self, id: str) -> bool:
        return id in self._load()

    def all(self) -> list:
        return list(self._load().values())

    def __len__(self):
        return len(self._load())

    def __iter__(self):
        return iter(self.all())

    def __contains__(self, id):
        return self.has(id)


def table(path: str, record: type) -> Table:
    """A data table: SPECIES = table("data/species", Species), at the top of a game module.

    The rows are data/species.json (a list of objects) or data/species/*.json (one object
    or a list per file, by file name). Each has an "id"; the build checks every row against the
    @dataclass (and every Ref[...] against the table it points to)."""
    return Table(path, record)


def read_rows(root, path):
    """The rows of a table, as JSON objects, in their order (shared with the build)."""
    single = os.path.join(root, *path.split("/")) + ".json"
    folder = os.path.join(root, *path.split("/"))
    if os.path.isfile(single):
        with open(single, encoding="utf-8") as fh:
            rows = json.load(fh)
        return rows if isinstance(rows, list) else [rows]
    rows = []
    for name in sorted(os.listdir(folder)):
        if name.endswith(".json"):
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                row = json.load(fh)
            rows.extend(row if isinstance(row, list) else [row])
    return rows


def to_json(value) -> str:
    """A @dataclass (or a list / dict of them, or plain values) as JSON text: the same text in CPython
    and in the game."""
    return json.dumps(_plain(value), separators=(",", ":"))


def from_json(text: str, record: type):
    """The @dataclass back from to_json's text. Unknown keys are ignored; a missing key takes the
    field's default (so an older save still loads)."""
    return _build(json.loads(text), record, record.__name__)


def _plain(v):
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return {f.name: _plain(getattr(v, f.name)) for f in dataclasses.fields(v)}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    return v


def _build(v, t, where):
    if dataclasses.is_dataclass(t):
        if not isinstance(v, dict):
            raise ValueError("%s is a JSON object" % t.__name__)
        hints = type_hints(t)
        args = {}
        for f in dataclasses.fields(t):
            if f.name in v:
                args[f.name] = _build(v[f.name], hints[f.name], where)
            elif f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
                raise ValueError("%s needs '%s' (it has no default)" % (t.__name__, f.name))
        return t(**args)
    origin, args = typing.get_origin(t), typing.get_args(t)
    if origin is typing.Union:
        inner = [a for a in args if a is not type(None)][0]
        return None if v is None else _build(v, inner, where)
    if origin is list:
        return [_build(x, args[0], where) for x in v]
    if origin is dict:
        return {k: _build(x, args[1], where) for k, x in v.items()}
    if t is int:
        if isinstance(v, float) and v.is_integer():
            return int(v)
        if not isinstance(v, int) or isinstance(v, bool):
            raise ValueError("expected a whole number, got %r" % (v,))
        return v
    if t is float:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError("expected a number, got %r" % (v,))
        return float(v)
    return v


class _Saves:
    """The game's save slots (in Script methods): text per slot name (letters, digits, _ and -)."""

    def write(self, slot: str, text: str) -> None:
        """Writes the slot; a save is never left half written, even if the app is killed."""

    def read(self, slot: str) -> typing.Optional[str]:
        """The slot's text, or None if it is empty."""

    def exists(self, slot: str) -> bool:
        """Whether the slot holds a save."""

    def delete(self, slot: str) -> None:
        """Empties the slot."""


saves = _Saves()
