"""Take out of a generated class the private methods nothing calls.

A screen is written with the whole kit of helpers ApkPy might need (format(),
the https call, SQLite, TOTP, the styled dialog...) and with a callback for
every function of the app, before anyone knows which of them this screen
reaches. Opened in Android Studio, two thirds of each screen was code that
never runs (06-11-2026: 1 834 of 2 665 lines on the first screen of a
four-screen app), and R8 does not take it out either: proguard-rules.pro keeps
every member of the generated classes, so crash.last() goes on reading real
names.

Only private methods go. Nothing outside the file can call one, and Android
never calls one by itself: the framework's callbacks, and anything an
interface asks for, are public or protected. A private method stays when a
method that stays names it, or when anything outside a method does (a field,
an inner class). A name counts wherever it is written -- a call, a lambda, a
method reference, a string, a comment -- so a doubt keeps the method.
"""

import contextlib
import re

# On for a test that reads how a function is translated, whether anything
# calls it or not (everything_kept below).
_KEEP_ALL = [False]

_HEADER = re.compile(
    r"\s*((?:@\w+(?:\([^)]*\))?\s+)*)"                  # annotations
    r"((?:(?:public|private|protected|static|final|synchronized|abstract|native|strictfp)\s+)*)"
    r"(?:<[^>]*>\s+)?"                                     # <T>
    r"[\w$.]+(?:\s*<[^;{}()=]*>)?(?:\s*\[\s*\])*"         # return type
    r"\s+([A-Za-z_$][\w$]*)\s*\(")                        # name (
_WORD = re.compile(r"[A-Za-z_$][\w$]*")
_ANNOTATION = re.compile(r"@(\w+)")
# Annotations that say nothing about who calls the method.
_PLAIN_ANNOTATIONS = {"SuppressWarnings", "SafeVarargs", "Deprecated"}
_LINE_MARK = re.compile(r"\x00apkpy-line:[^\x00]*\x00")


def _blank_literals(source):
    """The source with the inside of every string, char and comment turned to
    spaces (new lines kept), so that braces can be counted on it."""
    out = list(source)
    i, n = 0, len(source)
    while i < n:
        c = source[i]
        if c == "/" and source.startswith("//", i):
            j = source.find("\n", i)
            j = n if j < 0 else j
            out[i:j] = " " * (j - i)
            i = j
        elif c == "/" and source.startswith("/*", i):
            j = source.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n and source[j] != c and source[j] != "\n":
                j += 2 if source[j] == "\\" else 1
            j = min(j + 1, n)
            for k in range(i + 1, j - 1):
                out[k] = " "
            i = j
        else:
            i += 1
    return "".join(out)


def _members(lines, code_lines):
    """[(name, first, last, private, plain)] for each method of a top-level
    class: the lines it spans, its header included."""
    found = []
    depth = 0
    i = 0
    while i < len(code_lines):
        code = code_lines[i]
        header = _HEADER.match(code) if depth == 1 else None
        if header and not code.lstrip().startswith(("return ", "new ", "else")):
            # Follow the braces to the end of the body; a ';' before the first
            # brace is a declaration without one.
            level, opened, j = depth, False, i
            end = None
            while j < len(code_lines) and end is None:
                for ch in code_lines[j]:
                    if ch == "{":
                        level += 1
                        opened = True
                    elif ch == "}":
                        level -= 1
                        if opened and level == depth:
                            end = j
                            break
                    elif ch == ";" and not opened and level == depth:
                        end = -1
                        break
                if end is None:
                    j += 1
            if end is None or end < 0:
                depth += code.count("{") - code.count("}")
                i += 1
                continue
            first = i
            while first > 0 and _attached(lines[first - 1]):
                first -= 1
            # Comments are blank in code_lines: an @param is not an annotation.
            annotations = set(_ANNOTATION.findall(
                "\n".join(code_lines[first:i]) + header.group(1)))
            found.append((header.group(3), first, end,
                          "private" in header.group(2).split(),
                          annotations <= _PLAIN_ANNOTATIONS))
            i = end + 1
            continue
        depth += code.count("{") - code.count("}")
        i += 1
    return found


def _attached(line):
    """Whether a line just above a method belongs to it: its comment, an
    annotation, a mark of the Python line it came from."""
    text = line.strip()
    return bool(text) and (text.startswith(("//", "/*", "*", "@"))
                           or _LINE_MARK.fullmatch(text) is not None)


@contextlib.contextmanager
def everything_kept():
    """Write every method, reached or not: for a test of the translation of a
    function its app never calls."""
    before = _KEEP_ALL[0]
    _KEEP_ALL[0] = True
    try:
        yield
    finally:
        _KEEP_ALL[0] = before


def drop_unreached(source):
    """The class, without the private methods nothing that stays can reach."""
    if _KEEP_ALL[0]:
        return source
    lines = source.split("\n")
    # A mark names the Python file it came from, which may hold a quote.
    code = _LINE_MARK.sub(lambda mark: " " * len(mark.group(0)), source)
    code_lines = _blank_literals(code).split("\n")
    members = _members(lines, code_lines)
    if not members:
        return source
    spans = {}
    inside = set()
    for name, first, last, private, plain in members:
        spans.setdefault(name, []).append((first, last, private and plain))
        inside.update(range(first, last + 1))
    # One overload that has to stay keeps them all: a name is called, not a
    # signature.
    removable = {name for name, found in spans.items()
                 if all(can_go for _, _, can_go in found)}
    if not removable:
        return source
    outside = "\n".join(text for k, text in enumerate(lines) if k not in inside)
    queue = [name for name in spans if name not in removable]
    queue += [word for word in set(_WORD.findall(outside)) if word in removable]
    reached = set()
    while queue:
        name = queue.pop()
        if name in reached:
            continue
        reached.add(name)
        for first, last, _ in spans.get(name, ()):
            body = "\n".join(lines[first:last + 1])
            for word in set(_WORD.findall(body)):
                if word in spans and word not in reached and word != name:
                    queue.append(word)
    dead = [(first, last) for name in removable - reached
            for first, last, _ in spans[name]]
    if not dead:
        return source
    drop = set()
    for first, last in dead:
        drop.update(range(first, last + 1))
        # The blank line that separated it goes with it.
        if first > 0 and not lines[first - 1].strip():
            drop.add(first - 1)
        elif last + 1 < len(lines) and not lines[last + 1].strip():
            drop.add(last + 1)
    kept = []
    for k, text in enumerate(lines):
        # A method that sat between two fields leaves their blank lines
        # side by side.
        if k not in drop and not (kept and not kept[-1].strip() and not text.strip()):
            kept.append(text)
    return "\n".join(kept)
