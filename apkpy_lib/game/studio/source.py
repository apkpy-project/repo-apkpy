"""The game's own Python, in pieces the Studio can show and change: Game(...), the assets, the @prefab objects, the
scenes and what is added to them, and the Script classes with their typed fields.

The file stays the truth. The Studio keeps nothing in a format of its own: it reads game/main.py with ast, and a change
rewrites only the text of the value, argument or line that changed. Comments, spacing, Script code and everything the
Studio does not understand stay as they are, byte for byte. What it writes is what the build reads, in the style of the
examples: one call per line, and lines under 120 characters.
"""
import ast
import bisect
import json
import os
import re

LINE_BREAK = re.compile(r"\r\n|\r|\n")
EMPTY_LINES = re.compile(r"(?:[ \t]*(?:\r\n|\r|\n))*")
EMPTY_LINES_AT_END = re.compile(r"(?:(?<=\n)|^)(?:[ \t]*(?:\r\n|\n))*$")
WIDTH = 120


class Stale(Exception):
    """A value read before the text changed: read the source again (Source.at) and use the new one."""


# ── values ──────────────────────────────────────────────────────────────


def is_literal(node):
    """A value written out: numbers, texts, True/False/None, and tuples, lists and dicts of them."""
    if isinstance(node, ast.Constant):
        return node.value is None or isinstance(node.value, (bool, int, float, str))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, (int, float)) \
            and not isinstance(node.operand.value, bool)
    if isinstance(node, (ast.Tuple, ast.List)):
        return all(is_literal(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all(k is not None and is_literal(k) and is_literal(v) for k, v in zip(node.keys, node.values))
    return False


def literal(value):
    """A value as the Python that writes it: "text", 3, 2.5, True, (1, 2), ["a"], {"k": 1}."""
    if value is None or isinstance(value, bool):
        return repr(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(int(value)) + ".0" if value == int(value) and abs(value) < 1e15 else repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, tuple):
        return "(%s)" % (literal(value[0]) + "," if len(value) == 1 else ", ".join(literal(v) for v in value))
    if isinstance(value, list):
        return "[%s]" % ", ".join(literal(v) for v in value)
    if isinstance(value, dict):
        return "{%s}" % ", ".join("%s: %s" % (literal(k), literal(v)) for k, v in value.items())
    raise ValueError("%r cannot be written as a value" % (value,))


def dotted(node):
    """Sprite, assets.image, meadow.add: the name of what is called, or '' for anything else."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return base + "." + node.attr if base else ""
    return ""


def ast_text(text, node):
    """The part of a one-line expression text that node is (columns in UTF-8 bytes, as ast gives them)."""
    if node.lineno == node.end_lineno == 1:
        return text.strip().encode("utf-8")[node.col_offset:node.end_col_offset].decode("utf-8")
    return ast.get_source_segment(text.strip(), node)


def check_expression(text):
    """The text is one Python expression (what a field written as code holds), or ValueError says why not."""
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except SyntaxError as e:
        raise ValueError("this is not a Python value: %s" % e.msg)
    return tree.body


class Value:
    """One expression of the file: where it is, its text, and what it is."""

    def __init__(self, source, node, path):
        self.source, self.node, self.path = source, node, path
        self.version = source.version
        self.start, self.end = source.span(node)
        self.text = source.text[self.start:self.end]

    @property
    def kind(self):
        if is_literal(self.node):
            return "literal"
        if isinstance(self.node, ast.Name):
            return "name"
        if isinstance(self.node, ast.Call):
            return "call"
        return "code"

    @property
    def value(self):
        """The Python value of a literal (tuples stay tuples)."""
        return ast.literal_eval(self.node)

    @property
    def name(self):
        return self.node.id if isinstance(self.node, ast.Name) else ""

    def __repr__(self):
        return "<%s %s>" % (type(self).__name__, self.text[:40])


class Item:
    """One argument of a call or one element of a list: key is its index, or its name for name=value."""

    def __init__(self, key, value, start):
        self.key, self.value, self.start = key, value, start

    @property
    def end(self):
        return self.value.end


class Group(Value):
    """A call, a list or a tuple: something with arguments or elements that can be added, changed and removed."""

    def __init__(self, source, node, path):
        Value.__init__(self, source, node, path)
        self.items = []

    @property
    def args(self):
        return [i.value for i in self.items if isinstance(i.key, int)]

    def get(self, key):
        """The value of argument key (an index, or a name), or None."""
        for item in self.items:
            if item.key == key:
                return item.value
        return None

    def item(self, key):
        for item in self.items:
            if item.key == key:
                return item
        return None

    @property
    def keywords(self):
        return [i.key for i in self.items if isinstance(i.key, str)]

    def opening(self):
        """The index just after ( or [."""
        raise NotImplementedError

    @property
    def closing(self):
        """The index of ) or ]."""
        return self.end - 1


class Call(Group):
    def __init__(self, source, node, path):
        Group.__init__(self, source, node, path)
        self.func = dotted(node.func)
        for i, a in enumerate(node.args):
            v = source.value(a, path + (i,))
            self.items.append(Item(i, v, v.start))
        for k in node.keywords:
            if k.arg is None:
                continue
            v = source.value(k.value, path + (k.arg,))
            self.items.append(Item(k.arg, v, source.keyword_start(k, v.start)))
        self.items.sort(key=lambda i: i.start)

    def opening(self):
        func_end = self.source.span(self.node.func)[1]
        at = self.source.text.index("(", func_end)
        return at + 1


class Sequence(Group):
    def __init__(self, source, node, path):
        Group.__init__(self, source, node, path)
        for i, e in enumerate(node.elts):
            v = source.value(e, path + (i,))
            self.items.append(Item(i, v, v.start))

    @property
    def bracketed(self):
        return self.source.text[self.start] in "([" and self.source.text[self.end - 1] in ")]"

    def opening(self):
        return self.start + 1


class Mapping(Group):
    """A dictionary: {"coin": coin(), ...}. An item's key is its text key (its index when the key is not a text);
    a new item is written as '"key": value'."""

    def __init__(self, source, node, path):
        Group.__init__(self, source, node, path)
        for i, (k, v) in enumerate(zip(node.keys, node.values)):
            if k is None:
                continue
            key = k.value if isinstance(k, ast.Constant) and isinstance(k.value, str) else i
            value = source.value(v, path + (key,))
            self.items.append(Item(key, value, source.span(k)[0]))

    def opening(self):
        return self.start + 1


# ── pieces: the statements of the file ──────────────────────────────────


class Piece:
    """A statement at the top of the file. kind: docstring, import, game, asset, constant, scene, add, prefab, script,
    record, table, function or code. name: the name it gives (or, for an add, the scene's name)."""

    def __init__(self, source, node, kind, name="", key=None):
        self.source, self.node, self.kind, self.name = source, node, kind, name
        self.key = key or (kind, name)
        if getattr(node, "decorator_list", None):
            self.start = source.lines.starts[node.decorator_list[0].lineno - 1]        # the line of the @
        else:
            self.start = source.lines.index(node.lineno, node.col_offset)
        self.end = source.span(node)[1]
        self.call = None
        self.entity = None
        self.params = []
        self.fields = []
        self.doc = ast.get_docstring(node) if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else None

    @property
    def text(self):
        return self.source.text[self.start:self.end]

    def __repr__(self):
        return "<Piece %s %s>" % (self.kind, self.name)


class Field:
    """A parameter of a @prefab, or a typed field of a Script: name, its type as written, its starting value."""

    def __init__(self, name, annotation, default):
        self.name, self.annotation, self.default = name, annotation, default


class Lines:
    """From ast's (line, column in UTF-8 bytes) to an index in the text, for any line ending."""

    def __init__(self, text):
        self.text = text
        self.starts = [0] + [m.end() for m in LINE_BREAK.finditer(text)]

    def index(self, lineno, col):
        start = self.starts[lineno - 1]
        end = self.starts[lineno] if lineno < len(self.starts) else len(self.text)
        line = self.text[start:end]
        if line.isascii():
            return start + col
        return start + len(line.encode("utf-8")[:col].decode("utf-8"))

    def line_start(self, index):
        return self.starts[bisect.bisect_right(self.starts, index) - 1]

    def column(self, index):
        return index - self.line_start(index)

    def line_end(self, index):
        m = LINE_BREAK.search(self.text, index)
        return m.start() if m else len(self.text)

    def line_number(self, index):
        return bisect.bisect_right(self.starts, index)


API_CALLS = {"Game": "game", "table": "table"}


class Source:
    """One file of the game, read in pieces. Every change rewrites the text and reads it again; values read before
    a change are stale (Stale), so find them again with at(path)."""

    def __init__(self, path=None, text=None):
        self.path = path
        if text is None:
            with open(path, encoding="utf-8", newline="") as fh:
                text = fh.read()
        self.saved = text
        self.version = 0
        self.undo_stack, self.redo_stack = [], []
        self.merging = None             # typing in one field: one undo for the whole word
        self.on_change = None           # called with this source after each change (GameCode keeps one undo order)
        self.read(text)

    # ── reading ──

    def read(self, text):
        tree = ast.parse(text)          # a SyntaxError leaves the source as it was
        self.text, self.tree = text, tree
        self.lines = Lines(text)
        self.version += 1
        self.pieces = []
        self.game_name = ""
        self.scene_names = {}           # variable -> scene name
        counts = {}
        for node in tree.body:
            piece = self.piece(node)
            if piece.kind == "add":
                n = counts.get(piece.name, 0)
                counts[piece.name] = n + 1
                piece.key = ("add", piece.name, n)
                piece.call = self.value(node.value, (piece.key,))
                first = piece.call.get(0)
                piece.entity = first if isinstance(first, Call) else None
            self.pieces.append(piece)

    def piece(self, node):
        if isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return Piece(self, node, "docstring")
            if isinstance(node.value, ast.Call):
                func = dotted(node.value.func)
                if func.endswith(".add") and func[:-4] in self.scene_names:
                    return Piece(self, node, "add", func[:-4])
            return Piece(self, node, "code")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return Piece(self, node, "import")
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            value = node.value
            if isinstance(value, ast.Call):
                func = dotted(value.func)
                kind = API_CALLS.get(func)
                if func.startswith("assets."):
                    kind = "asset"
                elif self.game_name and func == self.game_name + ".scene":
                    kind = "scene"
                if kind:
                    piece = Piece(self, node, kind, name)
                    piece.call = self.value(value, (piece.key,))
                    if kind == "game":
                        self.game_name = name
                    elif kind == "scene":
                        first = piece.call.get(0) or piece.call.get("name")
                        self.scene_names[name] = first.value if first is not None and first.kind == "literal" else name
                    return piece
            if is_literal(value):
                piece = Piece(self, node, "constant", name)
                piece.call = self.value(value, (piece.key,))
                return piece
            return Piece(self, node, "code", name)
        if isinstance(node, ast.FunctionDef):
            if len(node.decorator_list) == 1 and dotted(node.decorator_list[0]) == "prefab":
                return self.prefab(node)
            return Piece(self, node, "function" if not node.decorator_list else "code", node.name)
        if isinstance(node, ast.ClassDef):
            if node.decorator_list:
                return Piece(self, node, "record", node.name)
            if any(dotted(b) == "Script" for b in node.bases):
                return self.script(node)
            return Piece(self, node, "code", node.name)
        return Piece(self, node, "code")

    def prefab(self, node):
        piece = Piece(self, node, "prefab", node.name)
        args = node.args
        defaults = [None] * (len(args.args) - len(args.defaults)) + list(args.defaults)
        for i, (a, d) in enumerate(zip(args.args, defaults)):
            annotation = self.segment(a.annotation) if a.annotation is not None else ""
            piece.params.append(Field(a.arg, annotation, self.value(d, (piece.key, "param", i)) if d is not None else None))
        body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
        if len(body) == 1 and isinstance(body[0], ast.Return) and isinstance(body[0].value, ast.Call) \
                and dotted(body[0].value.func) == "Entity":
            piece.entity = self.value(body[0].value, (piece.key, "return"))
        return piece

    def script(self, node):
        piece = Piece(self, node, "script", node.name)
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                value = self.value(item.value, (piece.key, item.target.id)) if item.value is not None else None
                piece.fields.append(Field(item.target.id, self.segment(item.annotation), value))
        return piece

    def value(self, node, path):
        if isinstance(node, ast.Call):
            return Call(self, node, path)
        if isinstance(node, (ast.List, ast.Tuple)):
            return Sequence(self, node, path)
        if isinstance(node, ast.Dict):
            return Mapping(self, node, path)
        return Value(self, node, path)

    def span(self, node):
        return (self.lines.index(node.lineno, node.col_offset), self.lines.index(node.end_lineno, node.end_col_offset))

    def segment(self, node):
        start, end = self.span(node)
        return self.text[start:end]

    def keyword_start(self, keyword, value_start):
        """Where name=value starts: ast gives it from Python 3.9; on 3.8 it is found before the value."""
        if getattr(keyword, "lineno", None) is not None:
            return self.lines.index(keyword.lineno, keyword.col_offset)
        m = re.search(r"\b%s\s*=\s*$" % re.escape(keyword.arg), self.text[max(0, value_start - 400):value_start])
        return value_start - len(m.group(0))

    @property
    def newline(self):
        m = LINE_BREAK.search(self.text)
        return m.group(0) if m else "\n"

    @property
    def dirty(self):
        return self.text != self.saved

    # ── finding ──

    def find(self, kind, name=None):
        return [p for p in self.pieces if p.kind == kind and (name is None or p.name == name)]

    def first(self, kind, name=None):
        found = self.find(kind, name)
        return found[0] if found else None

    def piece_of(self, key):
        for p in self.pieces:
            if p.key == key:
                return p
        return None

    def at(self, path):
        """The value at a path, read from the text as it is now: (piece key, step, step...); a step is an argument
        (index or name), "return" (a prefab's Entity) or ("param", i)."""
        piece = self.piece_of(path[0])
        if piece is None:
            return None
        steps = list(path[1:])
        if piece.kind == "prefab":
            if steps[:1] == ["return"]:
                here, steps = piece.entity, steps[1:]
            elif steps[:1] == ["param"]:
                field = piece.params[steps[1]]
                here, steps = field.default, steps[2:]
            else:
                return None
        elif piece.kind == "script":
            field = next((f for f in piece.fields if f.name == steps[0]), None) if steps else None
            if field is None:
                return None
            here, steps = field.default, steps[1:]
        else:
            here = piece.call
        for step in steps:
            if not isinstance(here, Group):
                return None
            here = here.get(step)
        return here

    def fresh(self, value):
        """The same value in the text as it is now."""
        if value.version == self.version:
            return value
        found = self.at(value.path)
        if found is None:
            raise Stale("%s is gone" % (value.path,))
        return found

    # ── names the Studio offers ──

    def assets(self, *kinds):
        """[(name, kind, path)] of the assets = assets.<kind>(...) lines."""
        out = []
        for p in self.find("asset"):
            kind = p.call.func.split(".", 1)[1]
            first = p.call.get(0)
            if not kinds or kind in kinds:
                out.append((p.name, kind, first.value if first is not None and first.kind == "literal" else ""))
        return out

    def prefab_names(self):
        return [p.name for p in self.find("prefab")]

    def script_names(self):
        return [p.name for p in self.find("script")]

    # ── changing ──

    def replace(self, start, end, text, merge=None):
        """The one way the text changes: the old one goes on the undo list, and the new one is read again. Changes
        with the same merge key one after the other (letters typed in one field) are undone together."""
        if "\n" in text and self.newline != "\n":
            text = text.replace("\r\n", "\n").replace("\n", self.newline)
        new = self.text[:start] + text + self.text[end:]
        if new == self.text:
            return
        old = self.text
        self.read(new)
        joined = merge is not None and merge == self.merging and self.undo_stack
        self.merging = merge
        if not joined:
            self.undo_stack.append(old)
        self.redo_stack = []
        if self.on_change is not None and not joined:
            self.on_change(self)

    def undo(self):
        if not self.undo_stack:
            return False
        self.redo_stack.append(self.text)
        self.read(self.undo_stack.pop())
        self.merging = None
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        self.undo_stack.append(self.text)
        self.read(self.redo_stack.pop())
        self.merging = None
        return True

    def set_text(self, text):
        """The whole file (read again from disk, or a copy): undo goes back to what was here."""
        self.replace(0, len(self.text), text)

    def set(self, value, text, merge=None):
        """The text of one value becomes text (a Python expression)."""
        value = self.fresh(value)
        check_expression(text)
        self.replace(value.start, value.end, self.fitted(text.strip(), value.start, value.end), merge)

    def set_arg(self, group, key, text, merge=None):
        """Argument key (an index, or a name) of a call becomes text; a name that is not there is added at the end."""
        group = self.fresh(group)
        check_expression(text)
        here = group.get(key)
        if here is not None:
            self.replace(here.start, here.end, self.fitted(text.strip(), here.start, here.end), merge)
        elif isinstance(key, str):
            self.insert(group, "%s=%s" % (key, text.strip()), len(group.items))
        else:
            raise IndexError("%s has no argument %d" % (group.text[:30], key))

    def fitted(self, text, start, end):
        """text in place of start..end, as it fits the line: a dictionary or a list too long for it is broken after
        its commas, each item under the first."""
        tail = self.lines.line_end(end) - end
        column = self.lines.column(start)
        if "\n" in text or column + len(text) + tail <= WIDTH:
            return text
        node = check_expression(text)
        if isinstance(node, ast.Dict) and all(k is not None for k in node.keys):
            parts = ["%s: %s" % (ast_text(text, k), ast_text(text, v)) for k, v in zip(node.keys, node.values)]
        elif isinstance(node, (ast.List, ast.Tuple)) and text[:1] in "[(" and len(node.elts) > 1:
            parts = [ast_text(text, e) for e in node.elts]
        else:
            return text
        return text[0] + (",\n" + " " * (column + 1)).join(parts) + text[-1]

    def remove_arg(self, group, key):
        group = self.fresh(group)
        items = group.items
        k = next((i for i, item in enumerate(items) if item.key == key), None)
        if k is None:
            return
        if len(items) == 1:
            self.replace(group.opening(), group.closing, "")
        elif k > 0:
            self.replace(items[k - 1].end, items[k].end, "")
        else:
            self.replace(items[0].start, items[1].start, "")

    def insert(self, group, text, index=None, own_line=None):
        """A new argument (or element) at position index of the items. By default a positional one goes before the
        first name=value: pass len(group.items) for a name=value. own_line: on a line of its own (by default, when
        the other arguments are)."""
        group = self.fresh(group)
        items = group.items
        if index is None:
            index = next((i for i, item in enumerate(items) if isinstance(item.key, str)), len(items))
        if not items:
            self.replace(group.opening(), group.closing, text)
            return
        multi = self.one_per_line(group) if own_line is None else own_line
        align = " " * self.lines.column(items[0].start)
        if index == 0:
            first = items[0]
            sep = ",%s%s" % (self.newline, align) if multi else ", "
            self.replace(first.start, first.start, text + sep)
            return
        after = items[index - 1]
        line_end = self.lines.line_end(after.end)
        long = self.lines.column(after.end) + len(text) + 2 + (line_end - after.end) > WIDTH
        sep = ",%s%s" % (self.newline, align) if multi or long else ", "
        self.replace(after.end, after.end, sep + text)

    def one_per_line(self, group):
        """The items after the first each start a line of their own (Entity("coin",\\n Sprite(...),\\n ...)): new
        ones do too."""
        items = group.items
        if len(items) < 2:
            return False
        lines = [self.lines.line_number(i.start) for i in items[1:]]
        if len(set(lines)) != len(lines):
            return False
        return len(lines) > 1 or lines[0] != self.lines.line_number(items[0].start)

    def set_rest(self, call, first, texts):
        """Arguments from index first to the last positional one become texts (the actions of OnTap(...),
        OnCollide("tag", ...), Timer(1, ...)): what *actions holds."""
        call = self.fresh(call)
        rest = [i for i in call.items if isinstance(i.key, int) and i.key >= first]
        if not rest:
            for n, text in enumerate(texts):
                self.insert(self.at(call.path), text, index=first + n)
            return
        if not texts:
            for item in reversed(rest):
                self.remove_arg(self.at(call.path), item.key)
            return
        multi = self.one_per_line(call)
        align = " " * self.lines.column(call.items[0].start)
        joined = ", ".join(texts)
        if multi or self.lines.column(rest[0].start) + len(joined) + (self.lines.line_end(rest[-1].end) - rest[-1].end) > WIDTH:
            joined = (",%s%s" % (self.newline, align)).join(texts)
        self.replace(rest[0].start, rest[-1].end, joined)

    # ── whole statements ──

    def add_statement(self, text, after=None, blank_lines=None):
        """A new statement after the piece after (default: the end of the file), with the blank lines the house style
        puts around it: two around a def or a class, and by default none after a line of the same kind."""
        nl = self.newline
        defines = text.lstrip().startswith(("@", "def ", "class "))
        if after is None:
            body = self.text.rstrip()
            self.replace(0, len(self.text), body + nl * (3 if defines else 2) + text + nl)
            return
        after = self.piece_of(after.key)
        if blank_lines is None:
            blank_lines = 2 if defines or after.kind in ("prefab", "script", "function", "record") else 0
        at = self.lines.line_end(after.end)
        rest = self.text[at:]
        breaks = len(EMPTY_LINES.match(rest).group(0).splitlines())
        tail = nl * (3 - breaks) if defines and rest.strip() and breaks < 3 else ""
        self.replace(at, at, nl * (blank_lines + 1) + text + tail)

    def remove_piece(self, piece):
        """A statement goes, and the blank lines left around it are as many as on its wider side."""
        piece = self.piece_of(piece.key)
        start = self.lines.line_start(piece.start)
        end = self.lines.line_end(piece.end)
        m = LINE_BREAK.match(self.text, end)
        end = m.end() if m else end
        before, after = self.text[:start], self.text[end:]
        lead = EMPTY_LINES.match(after).group(0)
        if not after.strip():
            new = before.rstrip() + self.newline
        elif not before.strip():
            new = after[len(lead):]
        else:
            above = len(EMPTY_LINES_AT_END.search(before).group(0).splitlines(True))
            below = lead.splitlines(True)
            drop = min(above, len(below))
            new = before + after[len("".join(below[:drop])):]
        self.replace(0, len(self.text), new)

    # ── saving ──

    def reload(self):
        """The file changed on disk: read it again (the Studio's changes not saved are lost)."""
        with open(self.path, encoding="utf-8", newline="") as fh:
            text = fh.read()
        self.saved = text
        if text != self.text:
            self.read(text)
            self.undo_stack, self.redo_stack = [], []

    def changed_on_disk(self):
        try:
            with open(self.path, encoding="utf-8", newline="") as fh:
                return fh.read() != self.saved
        except OSError:
            return False

    def save(self):
        if not self.dirty:
            return False
        tmp = self.path + ".studio-tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(self.text)
        os.replace(tmp, self.path)
        self.saved = self.text
        return True


# ── what the build reads: Game(...), the scenes, the components ─────────


def bind(call, args):
    """{field: key} for a call of a component or an action: key is the index of a positional argument or the name
    of name=value. args is the schema's list of positional fields; '*actions' takes the rest (key: (first, None))."""
    out = {}
    positional = list(args)
    for item in call.items:
        if isinstance(item.key, int):
            if positional and positional[0].startswith("*"):
                out.setdefault(positional[0][1:], (item.key, None))
                continue
            if positional:
                out[positional.pop(0)] = item.key
        else:
            out[item.key] = item.key
    return out


def call_text(func, args=(), kwargs=(), column=0):
    """func(a, b, k=v) as the examples write it: on one line, or broken at the arguments, lined up, past WIDTH."""
    parts = list(args) + ["%s=%s" % (k, v) for k, v in kwargs]
    one = "%s(%s)" % (func, ", ".join(parts))
    if column + len(one) <= WIDTH or len(parts) < 2:
        return one
    align = " " * (column + len(func) + 1)
    lines, line = [], ""
    for part in parts:
        candidate = part if not line else line + ", " + part
        if line and column + len(func) + 1 + len(candidate) + 2 > WIDTH:
            lines.append(line + ",")
            line = part
        else:
            line = candidate
    lines.append(line)
    return func + "(" + ("\n" + align).join(lines) + ")"


def entity_text(name, components, kwargs=(), column=0):
    """Entity("coin",\\n  Sprite(...),\\n  ...): a component on each line, as in the examples."""
    head = "Entity(%s" % literal(name)
    align = " " * (column + len("Entity("))
    rest = list(components) + ["%s=%s" % (k, v) for k, v in kwargs]
    if not rest:
        return head + ")"
    if column + len(head) + sum(len(r) + 2 for r in rest) <= WIDTH and len(rest) <= 2:
        return head + ", " + ", ".join(rest) + ")"
    return head + ",\n" + align + (",\n" + align).join(rest) + ")"


def prefab_text(name, entity_name, components, tags=(), params=""):
    """A new @prefab function."""
    kwargs = [("tags", literal(list(tags)))] if tags else []
    body = entity_text(entity_name, components, kwargs, column=len("    return "))
    return "@prefab\ndef %s(%s):\n    return %s" % (name, params, body)
