# -*- coding: utf-8 -*-
"""What a ``@native`` function is handed and what it hands back.

Everything that crosses the line between an app and one of its native blocks
is text -- a screen's value, a number worked out in Python -- and the block
declares what it wants to make of it::

    @native(preview=lambda ms: None)
    def buzz(ms: int):
        ...

On the phone the generated Java turns ``"200"`` into the ``int``; on the desk
the Previewer turns it into the Python ``int`` it hands to ``preview=``. Both
have to accept the same texts and refuse the same ones, so the rule is written
once, here: the Activity's helpers are these functions again in Java, and a
test compiles them and asks both the same questions.
"""
from __future__ import annotations

import re

__all__ = [
    "CODE", "KINDS", "JAVA_TYPES", "WHOLE", "NUMBER", "INT_MIN", "INT_MAX",
    "LONG_MIN", "LONG_MAX", "kind_of", "whole", "number", "truth", "read",
    "text_of",
]

CODE = "U2047"

# What an annotation says the argument is. Python's own names come first; the
# Java ones are for the two cases Python has no word for.
KINDS = {
    "str": "text", "String": "text",
    "int": "int", "long": "long",
    "float": "double", "double": "double",
    "bool": "boolean", "boolean": "boolean",
}
JAVA_TYPES = {"text": "java.lang.String", "int": "int", "long": "long",
              "double": "double", "boolean": "boolean"}

# ASCII digits on purpose: ``\d`` is every script's digits in Python and only
# these ten in Java.
WHOLE = r"[+-]?[0-9]+"
NUMBER = r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
INT_MIN, INT_MAX = -2 ** 31, 2 ** 31 - 1
LONG_MIN, LONG_MAX = -2 ** 63, 2 ** 63 - 1

_WHOLE = re.compile(WHOLE)
_NUMBER = re.compile(NUMBER)


def kind_of(annotation):
    """``int``, ``"long"``, nothing at all -> the kind of argument, or ``None``
    for an annotation that is not one of them."""
    if annotation is None:
        return "text"
    name = annotation if isinstance(annotation, str) else getattr(annotation, "__name__", "")
    return KINDS.get(name.strip())


def whole(text, name, kind="int"):
    """The whole number in ``text``. ``"12"`` and ``"12.0"`` are twelve --
    numbers reach a block as text, and a division leaves a ``.0`` -- and
    anything else is a mistake worth stopping for."""
    trimmed = "" if text is None else str(text).strip()
    value = None
    if _WHOLE.fullmatch(trimmed):
        value = int(trimmed)
    elif _NUMBER.fullmatch(trimmed):
        decimal = float(trimmed)
        if abs(decimal) < 9.0e18 and decimal == int(decimal):
            value = int(decimal)
    if value is None or not LONG_MIN <= value <= LONG_MAX:
        raise ValueError('%s has to be a whole number, got "%s"' % (name, trimmed))
    if kind == "int" and not INT_MIN <= value <= INT_MAX:
        raise ValueError('%s: %d does not fit in an int; declare it as "long"'
                         % (name, value))
    return value


def number(text, name):
    trimmed = "" if text is None else str(text).strip()
    if not _NUMBER.fullmatch(trimmed):
        raise ValueError('%s has to be a number, got "%s"' % (name, trimmed))
    return float(trimmed)


def truth(text):
    """``"true"`` in any case is true; everything else is not."""
    return text is not None and str(text).strip().lower() == "true"


def read(kind, text, name):
    """The text an app passed, as the kind of value the block declared."""
    if kind == "text":
        return "" if text is None else str(text)
    if kind in ("int", "long"):
        return whole(text, name, kind)
    if kind == "double":
        return number(text, name)
    if kind == "boolean":
        return truth(text)
    raise ValueError("unknown kind %r" % (kind,))


def text_of(value):
    """What a block's answer is once it is back in the app: text, with a
    boolean spelt the way every other value in an ApkPy app spells it."""
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)
