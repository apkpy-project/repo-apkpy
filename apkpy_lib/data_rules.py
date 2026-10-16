# -*- coding: utf-8 -*-
"""The rules the two runtimes have to answer the same way.

The database layer has its rules written twice -- once in
``apkpy_lib/features/data.py``, which runs on your computer, and once in
``apkpy_lib/core/features/data.py``, which writes the Java that runs on the
phone. Nobody decided they should disagree; they were written months apart and
each one was right on its own. An audit found eight places where they had
drifted, and every one of them is silent: the app works at the desk and
answers something else in your hand.

This module is the cure that already worked three times in this project --
:mod:`apkpy_lib.icons` for the drawings, :mod:`apkpy_lib.theme` for the
colours, :mod:`apkpy_lib.layout_engine` for the box shorthand. One place says
what the rule *is*; each side translates it.

The phone does not run Python, so what is shared is the decision, not the
code. Each rule below therefore carries two things: an executable Python
answer, which the Previewer uses directly, and the Java the compiler has to
emit for the same decision. :data:`CASES` is the table both sides are measured
against, and ``tests/features/test_data_rules.py`` walks it asking each side
in turn. The day they disagree again, that test goes red before anything
leaves the house.

Nothing here imports Tk or anything Android. It is meant to be readable on its
own, because a rule nobody can read is a rule nobody can check.
"""

import json
import math
from base64 import b64decode, b64encode
from collections import namedtuple

# ── What an answer looks like ───────────────────────────────────────────────
#
# A rule answers with a verdict instead of raising, so the table can hold the
# refusals next to the acceptances and compare them the same way. The callers
# turn a refusal into whatever their side raises.
Verdict = namedtuple("Verdict", "ok value reason")


def accept(value):
    return Verdict(True, value, "")


def refuse(reason):
    return Verdict(False, None, reason)


# ── Rule 1: how long a piece of text is ─────────────────────────────────────

def text_length(text):
    """The length ``max_length`` means: characters, not units of memory.

    Python counts characters already. Java's ``String.length()`` counts UTF-16
    units, so an emoji counts as two and ``max_length=1`` refuses a single
    character. The SQLite ``CHECK`` in the very same generated schema uses
    SQLite's ``length()``, which counts characters -- so today the Java refuses
    what its own table would have accepted.
    """
    return len(text)


# ── Rule 2: a whole number is a whole number ────────────────────────────────

def is_whole_number(value):
    """``1.9`` is not an integer, on either side.

    Python refuses it. Java calls ``longValue()``, which truncates to ``1`` and
    says nothing -- the row is written with a number the person never gave.
    """
    if isinstance(value, bool):
        return True
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value) and float(value).is_integer()
    return False


# ── A row's on/off field ─────────────────────────────────────────────────────

# What a field reads as "off" in visible="{liked}" and active="{liked}" inside
# a virtual_collection row -- after trimming, in lower case. Anything else is
# on. The phone's row adapter is written from this same tuple.
FIELD_OFF = ("", "false", "0", "no", "off", "none", "null")


def field_is_on(value):
    """True when a row field shows its component (``visible=``) or lights its
    button (``active=``): not empty, not false, not 0."""
    return str("" if value is None else value).strip().lower() not in FIELD_OFF


# ── Rule 3: a boolean is stored and compared as 1 or 0 ──────────────────────

def boolean_as_stored(value):
    """What a boolean looks like once it is in the column: ``1`` or ``0``.

    Both sides already store it this way. The gap is in the comparing: the
    ``eq`` filter converts to ``"1"``/``"0"`` and the ``in`` filter does not,
    so ``db.in_("flag", [True])`` looks for the text ``"true"`` in a column
    full of ones and quietly finds nothing.
    """
    return 1 if value else 0


# ── Rule 4: choices are compared after normalising ──────────────────────────

def matches_choice(value, choices):
    """``choices=[True, False]`` has to accept ``True``.

    Java normalises the value to ``1L`` and then compares it against the raw
    choice ``true`` as text: ``"1"`` against ``"true"``, never equal. A field
    declared that way refuses every value it was declared to allow.
    """
    if choices is None:
        return True
    wanted = [boolean_as_stored(item) if isinstance(item, bool) else item
              for item in choices]
    seen = boolean_as_stored(value) if isinstance(value, bool) else value
    return seen in wanted


# ── Rule 5: a real number is a real number ──────────────────────────────────

def is_real_number(value):
    """``NaN`` and infinity are not values a column can hold.

    ``float("NaN")`` slips past ``min_value`` and ``max_value`` because every
    comparison with NaN is false, and SQLite then writes NULL. The number the
    person gave is gone and nothing was said. Both sides do this today.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    return False


# ── Rule 6: a search for "%" searches for "%" ───────────────────────────────

LIKE_ESCAPE = "\\"


def like_pattern(operation, text):
    """What the person typed is text, not a pattern.

    ``contains("%")`` should find the one row with a per-cent sign in it.
    Today it returns every row, on both sides, because the value is dropped
    into a ``LIKE`` without escaping. The Previewer also emits ``ESCAPE`` and
    the compiler does not, so a backslash means different things in the two.
    """
    escaped = (str(text).replace(LIKE_ESCAPE, LIKE_ESCAPE + LIKE_ESCAPE)
               .replace("%", LIKE_ESCAPE + "%")
               .replace("_", LIKE_ESCAPE + "_"))
    if operation == "contains":
        return "%" + escaped + "%"
    if operation == "starts_with":
        return escaped + "%"
    if operation == "ends_with":
        return "%" + escaped
    raise ValueError("like_pattern does not know '%s'" % operation)


# ── Rule 7: ordering against nothing ────────────────────────────────────────

ORDERING = ("gt", "gte", "lt", "lte")


def comparison_with_nothing(operation):
    """``db.gt("flag", None)`` is a question with no answer.

    The Previewer asks ``flag > NULL`` and gets nothing back. Java turns every
    operator except ``ne`` into ``IS NULL`` and hands back the rows that have
    no value at all -- the opposite rows. Neither is right, and a filter built
    from an empty form field lands here by accident.

    ``eq`` and ``ne`` are different and stay as they are: asking whether
    something *is* nothing is a real question, and both sides already answer it
    with ``IS NULL`` / ``IS NOT NULL``.
    """
    if operation in ORDERING:
        return refuse(
            "Comparing with nothing has no answer. Use db.is_null(field) to "
            "ask for the empty ones, or leave this filter out."
        )
    return accept(operation)


# ── Rule 8: JSON all the way to the end ─────────────────────────────────────

def is_json(text):
    """``{"a":1} rubbish`` is not JSON, and neither is ``hello``.

    Java validates with ``new JSONTokener(text).nextValue()`` and never checks
    that the text ended. It reads the object, ignores the rest, and stores the
    whole string; a bare word comes back as a string and passes too. Python
    refuses both. A column promising validated JSON has to mean it.
    """
    try:
        json.loads(text)
    except Exception:
        return False
    return True


# ── Rule 9: bytes have one spelling ─────────────────────────────────────────

def blob_to_text(data):
    """Reading a blob gives the same text on both sides: Base64.

    The Previewer answers in hexadecimal (``"414243"``) and the phone in
    Base64 (``"QUJD"``), so code reading a blob from a callback has to guess
    which machine it is on. Base64 wins because it is already what the phone
    writes and what its own ``normalize`` accepts back, so only one side has to
    move.
    """
    return b64encode(bytes(data)).decode("ascii")


def blob_from_text(text):
    return b64decode(str(text).encode("ascii"))


# ── Rule 10: how far a change reaches ───────────────────────────────────────

CASCADING = ("cascade", "set_null")


def invalidated_by(changed, relations):
    """Every table a change in *changed* can reach by following relations.

    Deleting a row in A cascades to B, and from B to C -- so a list watching C
    is showing rows that are gone. The Previewer used to walk the relation
    list once, which reaches C only when the relations happen to be declared
    parent first. The same schema gave a different answer depending on the
    order two lines were written in, which is the kind of bug that looks like
    a ghost. Java already repeats until nothing new appears.

    *relations* is a sequence of ``(parent, child, on_delete)`` triples, named
    by table, so each side can hand over its own shape without this module
    knowing about either.
    """
    reached = set(changed)
    growing = True
    while growing:
        growing = False
        for parent, child, on_delete in relations or ():
            if on_delete in CASCADING and parent in reached and child not in reached:
                reached.add(child)
                growing = True
    return reached


# ── The whole of a value, in one call ───────────────────────────────────────

def normalize(kind, value, max_length=None, choices=None,
              min_value=None, max_value=None):
    """Put a value into the shape its column holds, or refuse it with a reason.

    This is the single answer both sides owe. The Previewer calls it; the
    compiler emits the Java listed in :data:`JAVA` for the same decisions.
    """
    if value is None:
        return accept(None)

    if kind in ("integer", "datetime"):
        if isinstance(value, str):
            try:
                value = int(value.strip())
            except ValueError:
                return refuse("expects an integer")
        elif not is_whole_number(value):
            return refuse("expects a whole number, and %r is not one" % (value,))
        value = int(value)

    elif kind == "real":
        if isinstance(value, str):
            try:
                value = float(value.strip())
            except ValueError:
                return refuse("expects a real number")
        if not is_real_number(value):
            return refuse("expects a real number, and %r is not one" % (value,))
        value = float(value)

    elif kind == "text":
        if not isinstance(value, str):
            return refuse("expects text")

    elif kind == "boolean":
        if isinstance(value, str) and value.strip().lower() in ("true", "false", "1", "0"):
            value = value.strip().lower() in ("true", "1")
        elif isinstance(value, int) and not isinstance(value, bool) and value in (0, 1):
            value = bool(value)
        if not isinstance(value, bool):
            return refuse("expects a boolean")
        value = boolean_as_stored(value)

    elif kind == "json":
        if isinstance(value, str):
            if not is_json(value):
                return refuse("contains invalid JSON")
        else:
            try:
                value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            except Exception:
                return refuse("is not JSON serializable")

    elif kind == "blob":
        if isinstance(value, str):
            try:
                value = blob_from_text(value)
            except Exception:
                return refuse("expects bytes or Base64 text")
        if not isinstance(value, (bytes, bytearray, memoryview)):
            return refuse("expects bytes")
        value = bytes(value)

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if min_value is not None and value < min_value:
            return refuse("is below min_value")
        if max_value is not None and value > max_value:
            return refuse("is above max_value")

    if max_length is not None and isinstance(value, str) \
            and text_length(value) > max_length:
        return refuse("exceeds max_length=%d" % max_length)

    if not matches_choice(value, choices):
        return refuse("is not one of %r" % (list(choices),))

    return accept(value)


# ── What the generated Java has to say ──────────────────────────────────────
#
# The phone cannot call the functions above, so the compiler has to emit Java
# that decides the same way. Each entry is a fragment that must appear in the
# generated ApkpyDatabase.java -- the visible sign that the rule crossed over.
#
# Checking a fragment proves the Java *mentions* the rule, not that it behaves.
# Running the emitted Java against this same table is the stronger test and the
# step after this one; it needs a JVM harness, so it is not pretended here.
JAVA = {
    "text_length": "codePointCount(0,",
    "whole_number": "_apkpyIsWholeNumber(",
    "boolean_in_filter": "_apkpyBooleanArg(",
    "choices_normalised": "_apkpyChoiceText(",
    "real_number": "Double.isNaN(",
    "like_escape": "_apkpyLikeEscape(",
    "like_escape_clause": "ESCAPE '\\\\'",
    "ordering_with_null": "_apkpyRefuseNullOrdering(",
    # nextClean() e nao more(): more() olha para o caracter seguinte em cru,
    # por isso um simples fim de linha depois do JSON contaria como lixo.
    "json_to_the_end": "nextClean()",
    "blob_base64": "Base64.encodeToString(",
    # O ponto fixo: o Java repete ate nada de novo aparecer, e e isso que
    # torna a resposta independente da ordem das relacoes.
    "invalidation_fixpoint": "while(added)",
}


# ── The table ───────────────────────────────────────────────────────────────
#
# Every line is a question with one right answer, and both sides are asked it.
# `previewer_today` records what the Previewer answers as things stand, so the
# red test says which side has to move rather than just that something is off.
Case = namedtuple("Case", "rule kind options value ok note previewer_today")

CASES = (
    Case("text_length", "text", {"max_length": 1}, u"\U0001F600", True,
         "one emoji is one character; Java counts two UTF-16 units",
         "agrees"),
    Case("text_length", "text", {"max_length": 1}, u"ab", False,
         "two characters is still two",
         "agrees"),

    Case("whole_number", "integer", {}, 1.9, False,
         "Java truncates it to 1 without a word",
         "agrees"),
    Case("whole_number", "integer", {}, 2.0, True,
         "2.0 is a whole number written with a dot",
         "refuses it -- stricter than the rule"),
    Case("whole_number", "integer", {}, 7, True,
         "the ordinary case still works",
         "agrees"),

    Case("choices_normalised", "boolean", {"choices": [True, False]}, True, True,
         "Java compares \"1\" against \"true\" and refuses every valid value",
         "agrees"),
    Case("choices_normalised", "boolean", {"choices": [True, False]}, False, True,
         "the other half of the same field",
         "agrees"),

    Case("real_number", "real", {"min_value": 0, "max_value": 1}, "NaN", False,
         "NaN slips past both limits and SQLite writes NULL",
         "accepts it"),
    Case("real_number", "real", {"min_value": 0, "max_value": 1}, 0.5, True,
         "an ordinary number in range",
         "agrees"),

    Case("blob_base64", "blob", {}, b"ABC", True,
         "bytes go in; reading them back must give QUJD on both sides",
         "agrees on the way in, differs on the way out"),

    Case("json_to_the_end", "json", {}, '{"a":1} rubbish', False,
         "Java reads the object and ignores the rest",
         "agrees"),
    Case("json_to_the_end", "json", {}, "hello", False,
         "a bare word is not JSON; Java takes it as a string",
         "agrees"),
    Case("json_to_the_end", "json", {}, '{"a":1}', True,
         "real JSON still passes",
         "agrees"),
)

# The two rules that are about a query rather than a value, kept apart because
# they are asked of the filter compiler and not of normalize().
LIKE_CASES = (
    ("contains", "%", "%\\%%", "searching for a per-cent sign finds one row, not all"),
    ("contains", "_", "%\\_%", "the same for the underscore"),
    ("starts_with", "100%", "100\\%%", "a prefix that happens to contain a wildcard"),
    ("contains", "plain", "%plain%", "ordinary text is untouched"),
)

# (relacoes por nome, o que mudou, o que tem de ser alcancado, porque)
CASCADE_CASES = (
    ((("a", "b", "cascade"), ("b", "c", "cascade")), ("a",), ("a", "b", "c"),
     "duas cascatas seguidas chegam ao fim"),
    ((("b", "c", "cascade"), ("a", "b", "cascade")), ("a",), ("a", "b", "c"),
     "as mesmas relacoes pela ordem inversa -- a ordem nao pode decidir"),
    ((("a", "b", "restrict"),), ("a",), ("a",),
     "restrict nao propaga: o SQLite recusa a eliminacao"),
    ((("a", "b", "set_null"),), ("a",), ("a", "b"),
     "set_null propaga: as linhas filhas mudam"),
    ((("a", "b", "cascade"),), ("b",), ("b",),
     "a cascata anda do pai para o filho, nao ao contrario"),
)

ORDERING_CASES = (
    ("gt", False, "greater-than nothing has no answer"),
    ("gte", False, "the same for >="),
    ("lt", False, "and for <"),
    ("lte", False, "and for <="),
    ("eq", True, "asking whether it is empty is a real question"),
    ("ne", True, "and so is asking whether it is not"),
)

__all__ = [
    "Verdict", "accept", "refuse", "text_length", "is_whole_number",
    "boolean_as_stored", "matches_choice", "is_real_number", "like_pattern",
    "LIKE_ESCAPE", "comparison_with_nothing", "ORDERING", "is_json",
    "blob_to_text", "blob_from_text", "normalize", "JAVA", "Case", "CASES",
    "LIKE_CASES", "ORDERING_CASES", "CASCADING", "invalidated_by",
    "CASCADE_CASES",
]
