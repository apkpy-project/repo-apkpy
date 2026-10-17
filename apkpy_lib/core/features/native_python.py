# -*- coding: utf-8 -*-
"""``@native`` functions written in Python: the body is translated to Java here.

    Vibrator = native.use("android.os.Vibrator")

    @native(preview=lambda ms: None)
    def buzz(ms: int):
        vibrator = context.getSystemService(Vibrator)
        if vibrator.hasVibrator():
            vibrator.vibrate(ms)

There is no Python on the phone, so nothing there can look ``Vibrator`` up by
name while the app runs -- which is how Pyjnius and Chaquopy reach a Java
class. What ApkPy has instead is the build: the body is read once, every
class, field and method it names is looked up in ``android.jar`` (the file the
app is compiled against), each line is given its Java type, and the function
is written out as the Java somebody would have typed.

That is also where it gains something a bridge cannot have. A method that does
not exist, an argument of the wrong kind, a class that only arrived in a newer
Android than the oldest phone the app runs on: each stops the build, with the
line, instead of the app on that phone.

What comes out is an ordinary ``native.java()`` block -- :func:`rewrite` puts
one in the module where the function was -- so calling it, refusing it in a
background job, the Previewer's ``preview=`` and everything else are the code
that was already there.

The language inside a body is small on purpose: Java objects and their own
methods, numbers, text, ``if``/``for``/``while``/``try``. No listeners yet
(an interface implemented in Python), and nothing of the app: a block is
handed its arguments and answers a value.
"""
from __future__ import annotations

import ast
import difflib
import keyword

from ...diagnostics import ApkpyError
from ... import native_rules
from .. import java_api
from .. import unsupported
from ..java_api import (Arr, Cls, NULL, OBJECT, Prim, STRING, TVar, Wild, BOXES,
                        UNBOXES, erase, source, substitute)

__all__ = ["CODE", "MIN_SDK", "rewrite", "helpers_java", "label_for", "reset",
           "uses_python_blocks", "written_as"]

CODE = native_rules.CODE
DOCS = "https://repo-apkpy.pages.dev/guides/native/#written-in-python"
MIN_SDK = 24                # what the generated project declares
COMPILE_SDK = 35

BOOLEAN = Prim("boolean")
INT = Prim("int")
LONG = Prim("long")
FLOAT = Prim("float")
DOUBLE = Prim("double")
CHAR = Prim("char")
VOID = Prim("void")
_RANK = {"byte": 1, "short": 2, "char": 2, "int": 3, "long": 4, "float": 5,
         "double": 6}
_WIDENS = {
    "byte": ("short", "int", "long", "float", "double"),
    "short": ("int", "long", "float", "double"),
    "char": ("int", "long", "float", "double"),
    "int": ("long", "float", "double"),
    "long": ("float", "double"),
    "float": ("double",),
}
_KIND_TYPES = {"text": STRING, "int": INT, "long": LONG, "double": DOUBLE,
               "boolean": BOOLEAN}
_JAVA_WORDS = frozenset("""
abstract assert boolean break byte case catch char class const continue default
do double else enum extends final finally float for goto if implements import
instanceof int interface long native new package private protected public
return short static strictfp super switch synchronized this throw throws
transient try void volatile while true false null var
""".split())
_GIVEN = ("context", "activity")
_PYTHON_ERRORS = {"Exception": "java.lang.Exception",
                  "RuntimeError": "java.lang.RuntimeException",
                  "ValueError": "java.lang.IllegalArgumentException",
                  "TypeError": "java.lang.IllegalArgumentException"}

# How tightly each Java operator binds; an expression is bracketed only where
# the one around it binds tighter.
_ATOM = 15
_UNARY = 13
_PRECEDENCE = {"*": 12, "/": 12, "%": 12, "+": 11, "-": 11, "<<": 10, ">>": 10,
               "<": 9, "<=": 9, ">": 9, ">=": 9, "instanceof": 9, "==": 8,
               "!=": 8, "&": 7, "^": 6, "|": 5, "&&": 4, "||": 3, "?": 2}

# Per transpilation: which blocks came from Python, for the comment over each
# generated method and for the helpers an Activity then needs.
_BLOCKS = [{}]
_LIBRARIES = {}


def reset():
    _BLOCKS[0] = {}


def uses_python_blocks():
    return bool(_BLOCKS[0])


def label_for(java_name):
    """``@native def buzz`` for a block that was written in Python."""
    return "@native def %s" % java_name if java_name in _BLOCKS[0] else None


def written_as(java_name):
    """``def buzz(ms)`` for a block written in Python, for the errors about
    calling it; ``None`` for one written in Java."""
    found = _BLOCKS[0].get(java_name)
    if not found:
        return None
    return "def %s(%s)" % (java_name, ", ".join(found["names"]))


def _fail(node, message, cause="", suggestions=(), received="", expected=""):
    raise ApkpyError(
        message,
        code=CODE,
        title="A native block written in Python cannot be translated",
        cause=cause,
        expected=expected,
        received=received,
        suggestions=list(suggestions),
        docs=DOCS,
        line=getattr(node, "lineno", 0),
    )


def _close(name, names, count=3):
    return difflib.get_close_matches(name, list(names), n=count, cutoff=0.6)


# --- the classes -------------------------------------------------------------

def _library(node):
    jar, table = java_api.find_android_jar(COMPILE_SDK)
    if not jar:
        _fail(node, "a native block written in Python needs the Android SDK",
              cause=("Its lines are checked against android.jar, the file with "
                     "every class of Android, and no SDK was found on this "
                     "computer."),
              suggestions=["Run: apkpy setup",
                           "Or point APKPY_ANDROID_JAR at an android.jar."])
    if jar not in _LIBRARIES:
        levels = java_api.ApiLevels(table) if table else None
        _LIBRARIES[jar] = (java_api.Library([jar]), levels)
    return _LIBRARIES[jar]


class _E:
    """One translated expression: the Java, and what it is."""

    __slots__ = ("code", "type", "kind", "cls", "items", "const", "atom", "field",
                 "prec")

    def __init__(self, code="", type=None, kind="value", cls=None, items=None,
                 const=None, atom=False, field=None, prec=0):
        self.prec = _ATOM if atom else prec
        self.code = code
        self.type = type
        self.kind = kind            # value | class | list
        self.cls = cls
        self.items = items
        self.const = const
        self.atom = atom
        self.field = field


def _p(e, need=None):
    """The expression where an operand or a receiver goes: in brackets unless
    it binds at least as tightly as the place needs."""
    return e.code if e.prec >= (_ATOM if need is None else need) else "(%s)" % e.code


def _java_string(text):
    out = ['"']
    for char in text:
        point = ord(char)
        if char == "\\":
            out.append("\\\\")
        elif char == '"':
            out.append('\\"')
        elif char == "\n":
            out.append("\\n")
        elif char == "\r":
            out.append("\\r")
        elif char == "\t":
            out.append("\\t")
        elif 32 <= point < 127:
            out.append(char)
        elif point > 0xFFFF:
            point -= 0x10000
            out.append("\\u%04x\\u%04x" % (0xD800 + (point >> 10), 0xDC00 + (point & 0x3FF)))
        else:
            out.append("\\u%04x" % point)
    out.append('"')
    return "".join(out)


def _unboxed(kind):
    if isinstance(kind, Cls) and kind.name in UNBOXES:
        return Prim(UNBOXES[kind.name])
    return kind


def _is_numeric(kind):
    kind = _unboxed(kind)
    return isinstance(kind, Prim) and kind.name in _RANK


def _is_integral(kind):
    kind = _unboxed(kind)
    return isinstance(kind, Prim) and kind.name in ("byte", "short", "char", "int", "long")


def _promote(left, right):
    left, right = _unboxed(left).name, _unboxed(right).name
    for name in ("double", "float", "long"):
        if name in (left, right):
            return Prim(name)
    return INT


def _shown(kind):
    """A type as an error names it: without its package."""
    if kind is NULL:
        return "None"
    if kind == STRING:
        return "text"
    if isinstance(kind, Cls):
        return kind.name.rsplit(".", 1)[-1].replace("$", ".")
    if isinstance(kind, Arr):
        return _shown(kind.elem) + "[]"
    return source(kind)


def _a(kind):
    """``an int``, ``a Vibrator``, ``text``."""
    name = _shown(kind)
    if name in ("text", "None"):
        return name
    return ("an " if name[:1].lower() in "aeiou" else "a ") + name


def _signature(method):
    """``vibrate(long, AudioAttributes)`` -- as an error lists it."""
    parts = [_shown(erase(kind, dict(method.type_params))).replace("text", "String")
             for kind in method.params]
    if method.varargs and parts and parts[-1].endswith("[]"):
        parts[-1] = parts[-1][:-2] + "..."
    name = _shown(Cls(method.owner)) if method.is_constructor else method.name
    return "%s(%s)" % (name, ", ".join(parts))


def _listed(candidates, most=6):
    shown = [_signature(method) for method, _bindings in candidates[:most]]
    if len(candidates) > most:
        shown.append("and %d more" % (len(candidates) - most))
    return shown


class _Translator:
    """One ``@native`` function, statement by statement."""

    def __init__(self, library, levels, aliases, function, source_name):
        self.library = library
        self.levels = levels
        self.aliases = aliases              # python name -> JavaClass
        self.function = function
        self.source_name = source_name
        self.locals = {}
        self.hoisted = []
        self.depth = 0
        self.floor = MIN_SDK                # the oldest Android this line can meet
        self.uses_activity = False
        self.needs_wrap = False
        self._tries = []
        self._loops = []
        self._catches = 0

    # -- the function --------------------------------------------------------

    def translate(self):
        function = self.function
        arguments = function.args
        if (arguments.vararg or arguments.kwarg or arguments.kwonlyargs
                or getattr(arguments, "posonlyargs", None)):
            _fail(function, "@native %s(): only plain arguments" % function.name,
                  cause="The block becomes a Java method, and Java has neither "
                        "*args nor keyword-only arguments.",
                  suggestions=["def %s(a, b): ..." % function.name])
        if arguments.defaults:
            _fail(function, "@native %s(): an argument cannot have a default"
                  % function.name,
                  cause="A block is always called with every argument.",
                  suggestions=["Leave the default out and pass the value in the call."])

        head, java_arguments, kinds = [], [], []
        for argument in arguments.args:
            name = argument.arg
            self._check_name(argument, name)
            kind = self._annotation(argument, argument.annotation, name)
            kinds.append(kind)
            self.locals[name] = _KIND_TYPES[kind]
            if kind == "text":
                java_arguments.append(name)
                continue
            java_arguments.append("apkpyArg_" + name)
            reader = {"int": "_apkpyNativeInt(%s, %s)", "long": "_apkpyNativeLong(%s, %s)",
                      "double": "_apkpyNativeDouble(%s, %s)",
                      "boolean": "_apkpyNativeBool(%s)"}[kind]
            values = ("apkpyArg_" + name, _java_string(name))
            head.append("%s %s = %s;" % (
                source(_KIND_TYPES[kind]), name,
                reader % (values if kind != "boolean" else values[:1])))
        self.returns = self._annotation(function, function.returns, "the answer") \
            if function.returns is not None else None

        body, completes = self._block(function.body, top=True)
        if completes:
            body.append('return "";')

        lines = []
        if self.uses_activity:
            lines.append("final android.app.Activity activity = this;")
        lines.extend(head)
        for name, kind in self.hoisted:
            lines.append("%s %s = %s;" % (source(kind), name, _default(kind)))
        if self.needs_wrap:
            # Python has no checked exceptions: one that nothing in the body
            # catches leaves the function as it would leave a Python one.
            lines.append("try {")
            lines.extend("    " + line for line in body)
            lines.append("} catch (RuntimeException apkpyUnchecked) {")
            lines.append("    throw apkpyUnchecked;")
            lines.append("} catch (Exception apkpyChecked) {")
            lines.append("    throw new RuntimeException(apkpyChecked);")
            lines.append("}")
        else:
            lines.extend(body)
        return {"code": "\n".join(lines), "args": java_arguments, "kinds": kinds}

    def _annotation(self, node, annotation, what):
        if annotation is None:
            return "text"
        name = None
        if isinstance(annotation, ast.Name):
            name = annotation.id
        elif isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            name = annotation.value
        kind = native_rules.kind_of(name) if name else None
        if kind is None:
            _fail(node, "@native %s(): %s cannot be %s" % (
                self.function.name, what, unsupported.describe(annotation)),
                cause=("What crosses into a block and back is text or a number: "
                       "a Java object cannot leave the block that made it."),
                suggestions=['One of: str, int, float, bool, "long".'])
        return kind

    def _check_name(self, node, name):
        if name in _JAVA_WORDS:
            _fail(node, "%r is a word of the Java language" % name,
                  cause="The name is written into the generated Java as it is.",
                  suggestions=["Call it something else: %s_value" % name])
        if name in _GIVEN or name in self.aliases or name.startswith("apkpy") \
                or name.startswith("_apkpy"):
            _fail(node, "%r is taken" % name,
                  cause=("`context` and `activity` are handed to every block, a "
                         "class keeps its name, and names starting with apkpy "
                         "are the generator's."),
                  suggestions=["Call it something else."])

    # -- statements ----------------------------------------------------------

    def _block(self, statements, top=False):
        """``(lines, completes)``: the Java, and whether the line after the
        block can be reached -- javac refuses a statement that cannot."""
        if not top:
            self.depth += 1
        floor = self.floor
        lines, completes = [], True
        for statement in statements:
            if not completes:
                break                       # Python allows dead code; Java does not
            found, completes = self._statement(statement)
            lines.extend(found)
        self.floor = floor
        if not top:
            self.depth -= 1
        return lines, completes

    def _statement(self, node):
        if isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return [], True             # a docstring
            if not isinstance(node.value, ast.Call):
                _fail(node, "this line does nothing",
                      suggestions=["Give its value a name, or call something."])
            return [self._expression(node.value, statement=True).code + ";"], True
        if isinstance(node, ast.Assign):
            return self._assign(node), True
        if isinstance(node, ast.AnnAssign):
            _fail(node, "a variable takes its type from its value here",
                  suggestions=["Write it without the annotation: x = ..."])
        if isinstance(node, ast.AugAssign):
            return self._augmented(node), True
        if isinstance(node, ast.If):
            return self._if(node)
        if isinstance(node, ast.While):
            return self._while(node)
        if isinstance(node, ast.For):
            return self._for(node)
        if isinstance(node, ast.Return):
            return [self._return(node)], False
        if isinstance(node, ast.Try):
            return self._try(node)
        if isinstance(node, ast.Raise):
            return [self._raise(node)], False
        if isinstance(node, ast.Pass):
            return [], True
        if isinstance(node, ast.Break):
            if not self._loops:
                _fail(node, "break outside a loop")
            self._loops[-1]["breaks"] = True
            return ["break;"], False
        if isinstance(node, ast.Continue):
            if not self._loops:
                _fail(node, "continue outside a loop")
            return ["continue;"], False
        _fail(node, "%s is not available inside a native block"
              % _statement_name(node),
              cause=("A block written in Python is a small language: values, "
                     "calls, if, for, while, try and return."),
              suggestions=["For anything else, write that block in Java: "
                           "native.java(...)."])

    def _assign(self, node):
        if len(node.targets) != 1:
            _fail(node, "one name per assignment inside a native block",
                  suggestions=["a = value", "b = a"])
        target = node.targets[0]
        value = self._expression(node.value)
        if isinstance(target, ast.Name):
            return [self._assign_name(node, target.id, value)]
        if isinstance(target, ast.Attribute):
            owner = self._expression(target.value)
            if owner.kind == "class":
                found = self._static_member(target, owner.cls, target.attr)
                if found.kind != "value" or found.field is None:
                    _fail(node, "%s.%s is not a field" % (owner.cls.simple, target.attr))
                field, kind, text = found.field, found.type, found.code
            else:
                field, kind, text = self._field(target, owner, target.attr)
            if field.final:
                _fail(node, "%s.%s cannot be changed" % (_shown(Cls(field.owner)), field.name),
                      cause="It is a constant of the class.")
            return ["%s = %s;" % (text, self._to(node, value, kind, "given to %s" % field.name))]
        if isinstance(target, ast.Subscript):
            owner = self._value(target.value)
            index = self._expression(_slice(target))
            if isinstance(owner.type, Arr):
                return ["%s[%s] = %s;" % (_p(owner), self._to(node, index, INT, "the index"),
                                          self._to(node, value, owner.type.elem, "stored"))]
            for name in ("set", "put"):
                if self.library.methods(owner.type, name):
                    call = self._invoke(node, owner, owner.type, name, [index, value], False)
                    return [call.code + ";"]
            _fail(node, "%s has no items to set" % _shown(owner.type))
        _fail(node, "this cannot be assigned to inside a native block",
              suggestions=["Give the value a name: name = value"])

    def _assign_name(self, node, name, value):
        if value.kind == "class":
            _fail(node, "%s is the class, not an object of it" % value.cls.simple,
                  cause="A name holds a value; the class is already called %s."
                        % value.cls.simple,
                  suggestions=self._ways_to_make(value.cls))
        if value.kind == "list":
            _fail(node, "a list written here has no Java type yet",
                  cause=("Java has to know what the list holds. A list can be "
                         "written where a method expects an array: "
                         "vibrator.vibrate([0, 200, 100], -1)."),
                  suggestions=["Pass it straight to the call that takes it."])
        if value.type == VOID:
            _fail(node, "there is no value to keep: that call answers nothing",
                  suggestions=["Call it on a line of its own."])
        if name in self.locals:
            return "%s = %s;" % (name, self._to(
                node, value, self.locals[name],
                "kept in %s" % name,
                cause=("%s held %s when it was first given a value, and a Java "
                       "variable keeps one kind." % (name, _a(self.locals[name]))),
                suggestions=["Use another name for this value."]))
        self._check_name(node, name)
        if value.type is NULL:
            _fail(node, "None alone does not say what %s is" % name,
                  cause="A Java variable has one type, taken from its first value.",
                  suggestions=["Give %s its real value first." % name])
        kind = value.type
        self.locals[name] = kind
        if self.depth == 0:
            return "%s %s = %s;" % (source(kind), name, value.code)
        # First met inside an if or a loop: Python keeps it after the block,
        # so it is declared at the top of the method.
        self.hoisted.append((name, kind))
        return "%s = %s;" % (name, value.code)

    def _augmented(self, node):
        if not isinstance(node.target, ast.Name) or node.target.id not in self.locals:
            _fail(node, "+= works on a variable of the block",
                  suggestions=["total = total + value"])
        both = ast.BinOp(left=ast.Name(id=node.target.id, ctx=ast.Load()),
                         op=node.op, right=node.value)
        ast.copy_location(both, node)
        ast.copy_location(both.left, node)
        value = self._expression(both)
        return ["%s = %s;" % (node.target.id, self._to(
            node, value, self.locals[node.target.id], "kept in %s" % node.target.id))]

    def _if(self, node):
        test = self._expression(node.test)
        inside, outside = self._guard(node.test)
        before = self.floor
        self.floor = max(before, inside)
        body, body_completes = self._block(node.body)
        self.floor = max(before, outside)
        other, other_completes = self._block(node.orelse) if node.orelse else ([], True)
        self.floor = before
        lines = ["if (%s) {" % self._truth(test)]
        lines.extend("    " + line for line in body)
        if node.orelse:
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If) and other \
                    and other[0].startswith("if ("):
                lines.append("} else " + other[0])
                lines.extend(other[1:])
            else:
                lines.append("} else {")
                lines.extend("    " + line for line in other)
                lines.append("}")
        else:
            lines.append("}")
        # `if SDK_INT < 26: return` -- everything after it is the else.
        if not body_completes and (other_completes or not node.orelse):
            self.floor = max(self.floor, outside)
        elif node.orelse and body_completes and not other_completes:
            self.floor = max(self.floor, inside)
        completes = (body_completes or other_completes) if node.orelse else True
        return lines, completes

    def _guard(self, test):
        """``(floor where the test is true, floor where it is false)`` for a
        test on ``Build.VERSION.SDK_INT``; the current floor for any other."""
        here = self.floor
        if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
            inside = here
            for part in test.values:
                inside = max(inside, self._guard(part)[0])
            return inside, here
        if not (isinstance(test, ast.Compare) and len(test.ops) == 1):
            return here, here
        try:
            left = self._expression(test.left)
            right = self._expression(test.comparators[0])
        except ApkpyError:
            return here, here
        op = test.ops[0]
        if _is_sdk_int(right) and isinstance(left.const, int):
            left, right = right, left
            op = {ast.Lt: ast.Gt(), ast.LtE: ast.GtE(), ast.Gt: ast.Lt(),
                  ast.GtE: ast.LtE()}.get(type(op), op)
        if not (_is_sdk_int(left) and isinstance(right.const, int)
                and not isinstance(right.const, bool)):
            return here, here
        level = right.const
        if isinstance(op, ast.GtE):
            return max(here, level), here
        if isinstance(op, ast.Gt):
            return max(here, level + 1), here
        if isinstance(op, ast.Lt):
            return here, max(here, level)
        if isinstance(op, ast.LtE):
            return here, max(here, level + 1)
        return here, here

    def _while(self, node):
        if node.orelse:
            _fail(node, "while ... else is not available inside a native block")
        forever = isinstance(node.test, ast.Constant) and node.test.value is True
        test = "true" if forever else self._truth(self._expression(node.test))
        self._loops.append({"breaks": False})
        body, _completes = self._block(node.body)
        loop = self._loops.pop()
        lines = ["while (%s) {" % test]
        lines.extend("    " + line for line in body)
        lines.append("}")
        return lines, (loop["breaks"] if forever else True)

    def _for(self, node):
        if node.orelse:
            _fail(node, "for ... else is not available inside a native block")
        if not isinstance(node.target, ast.Name):
            _fail(node, "a for loop takes one name inside a native block",
                  suggestions=["for item in items: ..."])
        name = node.target.id
        if name in self.locals:
            _fail(node, "%r already has a value" % name,
                  cause="The loop's own name lives inside the loop only.",
                  suggestions=["Give the loop another name."])
        self._check_name(node, name)

        iterable = node.iter
        if isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Name) \
                and iterable.func.id == "range":
            head, kind = self._range(node, name, iterable)
        else:
            over = self._value(iterable)
            kind = self._element(node, over)
            head = "for (%s %s : %s) {" % (source(kind), name, over.code)

        self.locals[name] = kind
        self._loops.append({"breaks": False})
        body, _completes = self._block(node.body)
        self._loops.pop()
        del self.locals[name]
        lines = [head]
        lines.extend("    " + line for line in body)
        lines.append("}")
        return lines, True

    def _range(self, node, name, call):
        if call.keywords or not 1 <= len(call.args) <= 3:
            _fail(node, "range() takes one to three numbers")
        values = [self._value(argument) for argument in call.args]
        for value in values:
            if not _is_integral(value.type):
                _fail(node, "range() counts in whole numbers",
                      received=_shown(value.type))
        kind = LONG if any(_unboxed(value.type) == LONG for value in values) else INT
        start, stop, step = "0", values[0].code, 1
        if len(values) >= 2:
            start, stop = values[0].code, values[1].code
        if len(values) == 3:
            if not isinstance(values[2].const, int) or values[2].const == 0:
                _fail(node, "the step of range() has to be a number written out",
                      suggestions=["range(0, 10, 2)", "range(10, 0, -1)"])
            step = values[2].const
        if len(values) >= 2:
            start, stop = values[0].code, _p(values[1], 10)
        else:
            stop = _p(values[0], 10)
        compare = "<" if step > 0 else ">"
        change = "%s++" % name if step == 1 else "%s--" % name if step == -1 \
            else "%s += %d" % (name, step)
        return ("for (%s %s = %s; %s %s %s; %s) {"
                % (source(kind), name, start, name, compare, stop, change)), kind

    def _element(self, node, over):
        if isinstance(over.type, Arr):
            return over.type.elem
        if isinstance(over.type, Cls):
            for kind in self.library.lineage(over.type):
                if kind.name == "java.lang.Iterable":
                    if kind.args:
                        return erase(_upper(kind.args[0]))
                    return OBJECT
            if self.library.is_a(over.type.name, "java.util.Map"):
                _fail(node, "a Map is walked through its keys or its entries",
                      suggestions=["for key in %s.keySet(): ..." % over.code])
        _fail(node, "%s cannot be walked with for" % _shown(over.type),
              cause="A for loop needs an array or something Iterable.")

    def _return(self, node):
        if node.value is None or (isinstance(node.value, ast.Constant)
                                  and node.value.value is None):
            return 'return "";'
        value = self._value(node.value)
        kind = _unboxed(value.type)
        if value.type == VOID:
            _fail(node, "that call answers nothing, so there is nothing to return",
                  suggestions=["Call it on its own line, then return."])
        if self.returns is not None:
            wanted = _KIND_TYPES[self.returns]
            text = self._to(node, value, wanted, "returned",
                            cause="%s() says it answers %s." % (
                                self.function.name,
                                "text" if wanted == STRING else source(wanted)))
            return "return %s;" % self._as_text(_E(text, wanted))
        if not (isinstance(kind, Prim) or value.type == STRING or value.type is NULL):
            _fail(node, "a block answers text or a number, not %s" % _a(value.type),
                  cause=("A Java object cannot leave the block that made it: "
                         "the rest of the app is not Java."),
                  suggestions=["Return one of its values: return str(value)",
                               "Or do everything that needs the object inside the block."])
        return "return %s;" % self._as_text(value)

    def _as_text(self, value):
        kind = _unboxed(value.type)
        if value.type is NULL:
            return '""'
        if value.type == STRING:
            return value.code
        if kind == DOUBLE:
            return "_apkpyFloat(%s)" % value.code
        return "String.valueOf(%s)" % value.code

    def _raise(self, node):
        if node.exc is None or node.cause is not None:
            _fail(node, "raise needs an error: raise Exception(\"why\")")
        call = node.exc
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) \
                and call.func.id in _PYTHON_ERRORS and call.func.id not in self.aliases:
            if len(call.args) > 1 or call.keywords:
                _fail(node, "%s takes one message" % call.func.id)
            message = self._str(node, self._value(call.args[0])) if call.args else '""'
            name = _PYTHON_ERRORS[call.func.id]
            if name == "java.lang.Exception":
                name = "java.lang.RuntimeException"
            return "throw new %s(%s);" % (name, message)
        value = self._value(call)
        if not (isinstance(value.type, Cls)
                and self.library.is_a(value.type.name, "java.lang.Throwable")):
            _fail(node, "only an error can be raised",
                  suggestions=['raise Exception("why")'])
        self._thrown(node, value.type.name)
        return "throw %s;" % value.code

    def _try(self, node):
        if node.orelse:
            _fail(node, "try ... else is not available inside a native block",
                  suggestions=["Put those lines at the end of the try."])
        if not node.handlers and not node.finalbody:
            _fail(node, "try needs an except")
        catches = []
        for handler in node.handlers:
            catches.append((handler, self._caught(handler)))
        frame = {"catches": [name for _h, names in catches for name in names],
                 "seen": set()}
        self._tries.append(frame)
        body, completes = self._block(node.body)
        self._tries.pop()

        lines = ["try {"]
        lines.extend("    " + line for line in body)
        earlier = []
        for handler, names in catches:
            for name in names:
                self._needed(handler, name, frame["seen"])
                if any(self.library.is_a(name, before) for before in earlier):
                    _fail(handler, "this except can never run",
                          cause="An except above it already catches %s."
                                % _shown(Cls(name)),
                          suggestions=["Put the more particular error first."])
            earlier.extend(names)
            self._catches += 1
            variable = handler.name or "apkpyError%d" % self._catches
            if handler.name:
                if handler.name in self.locals:
                    _fail(handler, "%r already has a value" % handler.name,
                          suggestions=["Give the error another name."])
                self._check_name(handler, handler.name)
            kind = Cls(names[0]) if len(names) == 1 else Cls("java.lang.Exception")
            self.locals[variable] = kind
            inside, inside_completes = self._block(handler.body)
            del self.locals[variable]
            completes = completes or inside_completes
            lines.append("} catch (%s %s) {" % (
                " | ".join(source(Cls(name)) for name in names), variable))
            lines.extend("    " + line for line in inside)
        if node.finalbody:
            final, final_completes = self._block(node.finalbody)
            lines.append("} finally {")
            lines.extend("    " + line for line in final)
            completes = completes and final_completes
        lines.append("}")
        return lines, completes

    def _caught(self, handler):
        kinds = handler.type
        if kinds is None:
            return ["java.lang.Exception"]
        nodes = kinds.elts if isinstance(kinds, ast.Tuple) else [kinds]
        names = []
        for node in nodes:
            if isinstance(node, ast.Name) and node.id in self.aliases:
                found = self.aliases[node.id]
                if not self.library.is_a(found.name, "java.lang.Throwable"):
                    _fail(handler, "%s is not an error" % found.simple)
                self._since_class(handler, found.name)
                names.append(found.name)
            elif isinstance(node, ast.Name) and node.id in _PYTHON_ERRORS:
                names.append(_PYTHON_ERRORS[node.id])
            else:
                _fail(handler, "except takes an error class",
                      suggestions=["except Exception as error:",
                                   'IOException = native.use("java.io.IOException") '
                                   "and then: except IOException:"])
        # javac refuses a multi-catch where one is a kind of another.
        return [name for name in names
                if not any(other != name and self.library.is_a(name, other)
                           for other in names)]

    def _needed(self, handler, name, seen):
        """javac refuses to catch a checked exception nothing in the try can
        throw; say it in the app's own words first."""
        if not self._checked(name) or name in ("java.lang.Exception", "java.lang.Throwable"):
            return
        for thrown in seen:
            if self.library.is_a(thrown, name) or self.library.is_a(name, thrown):
                return
        _fail(handler, "nothing in this try can fail with %s" % _shown(Cls(name)),
              cause="Java does not allow catching an error that cannot happen.",
              suggestions=["Take this except out, or write: except Exception:"])

    def _checked(self, name):
        return (self.library.is_a(name, "java.lang.Throwable")
                and not self.library.is_a(name, "java.lang.RuntimeException")
                and not self.library.is_a(name, "java.lang.Error"))

    def _thrown(self, node, name):
        if not self._checked(name):
            return
        for frame in reversed(self._tries):
            for caught in frame["catches"]:
                if self.library.is_a(name, caught):
                    frame["seen"].add(name)
                    return
        self.needs_wrap = True

    # -- expressions ---------------------------------------------------------

    def _value(self, node):
        """An expression that has to be a value: not a class, not a bare list."""
        found = self._expression(node)
        if found.kind == "class":
            _fail(node, "%s is the class, not an object of it" % found.cls.simple,
                  suggestions=self._ways_to_make(found.cls))
        if found.kind == "list":
            _fail(node, "a list written here has no Java type yet",
                  cause="A list can be written where a method expects an array.",
                  suggestions=["Pass it straight to the call that takes it."])
        return found

    def _expression(self, node, statement=False):
        if isinstance(node, ast.Constant):
            return self._constant(node)
        if isinstance(node, ast.Name):
            return self._name(node)
        if isinstance(node, ast.Attribute):
            owner = self._expression(node.value)
            if owner.kind == "class":
                return self._static_member(node, owner.cls, node.attr)
            if owner.kind == "list":
                _fail(node, "a list written here has no Java type yet")
            if isinstance(owner.type, Arr) and node.attr == "length":
                return _E("%s.length" % _p(owner), INT, atom=True)
            field, kind, text = self._field(node, owner, node.attr)
            return _E(text, kind, atom=True, field=field)
        if isinstance(node, ast.Call):
            return self._call(node, statement)
        if isinstance(node, ast.BinOp):
            return self._binary(node)
        if isinstance(node, ast.UnaryOp):
            return self._unary(node)
        if isinstance(node, ast.BoolOp):
            both = isinstance(node.op, ast.And)
            before, parts = self.floor, []
            for value in node.values:
                parts.append(self._truth(self._expression(value), 5 if both else 4))
                # `SDK_INT >= 26 and effect.x()`: the right side only runs
                # where the left side was true (or, for `or`, false).
                self.floor = max(self.floor, self._guard(value)[0 if both else 1])
            self.floor = before
            return _E((" && " if both else " || ").join(parts), BOOLEAN,
                      prec=4 if both else 3)
        if isinstance(node, ast.Compare):
            return self._compare(node)
        if isinstance(node, ast.IfExp):
            return self._conditional(node)
        if isinstance(node, ast.JoinedStr):
            return self._fstring(node)
        if isinstance(node, (ast.List, ast.Tuple)):
            return _E(kind="list", items=[self._expression(item) for item in node.elts])
        if isinstance(node, ast.Subscript):
            return self._item(node)
        _fail(node, "%s is not available inside a native block" % _expression_name(node),
              cause=("A block written in Python is a small language: values, "
                     "calls, if, for, while, try and return."),
              suggestions=["For anything else, write that block in Java: "
                           "native.java(...)."])

    def _constant(self, node):
        value = node.value
        if value is None:
            return _E("null", NULL, atom=True)
        if value is True or value is False:
            return _E("true" if value else "false", BOOLEAN, const=value, atom=True)
        if isinstance(value, int):
            return _int(node, value)
        if isinstance(value, float):
            if value != value or value in (float("inf"), float("-inf")):
                _fail(node, "that number cannot be written in Java")
            return _E(repr(value), DOUBLE, const=value, atom=value >= 0)
        if isinstance(value, str):
            return _E(_java_string(value), STRING, const=value, atom=True)
        _fail(node, "this kind of value is not available inside a native block",
              received=type(value).__name__)

    def _name(self, node):
        name = node.id
        if name in self.locals:
            return _E(name, self.locals[name], atom=True)
        if name == "context":
            return _E("context", Cls("android.content.Context"), atom=True)
        if name == "activity":
            self.uses_activity = True
            return _E("activity", Cls("android.app.Activity"), atom=True)
        if name in self.aliases:
            # Naming a class costs nothing on an older phone; what is checked
            # is each thing taken from it.
            return _E(kind="class", cls=self.aliases[name])
        known = list(self.locals) + list(self.aliases) + list(_GIVEN)
        hints = ["Did you mean %s?" % close for close in _close(name, known)]
        if name[:1].isupper():
            hints.extend('%s = native.use("%s")' % (name, full)
                         for full in self.library.packages_with(name)[:2])
            hints.append("A class is named at the top of the file with native.use().")
        else:
            hints.append("A value of the app: pass it as an argument.")
        _fail(node, "%r is not known inside this block" % name,
              cause=("A native block sees its own arguments and variables, "
                     "`context`, `activity`, and the classes named with "
                     "native.use(). The rest of the app is not Java, so it is "
                     "not reachable from here."),
              suggestions=hints)

    def _static_member(self, node, owner, name):
        kind = Cls(owner.name)
        field, field_type = self.library.field(kind, name)
        if field is not None and field.static:
            self._since_field(node, field)
            constant = field.constant if field.final else None
            if isinstance(constant, int) and field_type == BOOLEAN:
                constant = bool(constant)
            return _E("%s.%s" % (source(kind), name), field_type, const=constant,
                      atom=True, field=field)
        inner = self.library.nested(owner, name)
        if inner is not None:
            return _E(kind="class", cls=inner)
        if field is not None:
            _fail(node, "%s.%s belongs to an object, not to the class"
                  % (owner.simple, name),
                  suggestions=self._ways_to_make(owner))
        if self.library.methods(kind, name):
            _fail(node, "%s.%s is a method: call it" % (owner.simple, name),
                  suggestions=["%s.%s(...)" % (owner.simple, name)])
        _fail(node, "%s has no %s" % (owner.simple, name),
              suggestions=["Did you mean %s.%s?" % (owner.simple, close) for close in
                           _close(name, self.library.member_names(kind, static=True))])

    def _field(self, node, owner, name):
        kind = _upper(owner.type)
        if not isinstance(kind, Cls):
            _fail(node, "%s has no %s" % (_shown(owner.type), name))
        field, field_type = self.library.field(kind, name)
        if field is None or not field.public:
            hints = []
            if self.library.methods(kind, name):
                hints.append("It is a method: %s.%s()" % (owner.code, name))
            getter = "get" + name[:1].upper() + name[1:]
            if self.library.methods(kind, getter):
                hints.append("%s.%s()" % (owner.code, getter))
            hints.extend("Did you mean %s?" % close for close in
                         _close(name, self.library.member_names(kind)))
            _fail(node, "%s has no field %s" % (_shown(kind), name), suggestions=hints)
        self._since_field(node, field)
        text = ("%s.%s" % (source(Cls(field.owner)), name) if field.static
                else "%s.%s" % (_p(owner), name))
        return field, erase(_upper(field_type), self.library.bounds(kind)), text

    def _call(self, node, statement=False):
        if node.keywords:
            _fail(node, "a Java method takes its arguments by position",
                  cause="There are no keyword arguments in Java.",
                  suggestions=["Write the values in order, without names."])
        function = node.func
        if isinstance(function, ast.Name):
            name = function.id
            if name in self.aliases:
                return self._construct(node, self.aliases[name])
            builtin = getattr(self, "_builtin_" + name, None)
            if builtin is not None and name not in self.locals:
                return builtin(node)
            _fail(node, "%s() is not known inside this block" % name,
                  cause=("A native block calls Java: the methods of its objects "
                         "and of the classes named with native.use(). The "
                         "functions of the app are not reachable from here."),
                  suggestions=["Return a value and call %s() with it outside the block."
                               % name])
        if not isinstance(function, ast.Attribute):
            _fail(node, "this cannot be called inside a native block")
        if isinstance(function.value, ast.Name) and function.value.id == "native" \
                and "native" not in self.locals:
            return self._native_call(node, function.attr)
        owner = self._expression(function.value)
        arguments = [self._expression(argument) for argument in node.args]
        if owner.kind == "class":
            inner = self.library.nested(owner.cls, function.attr)
            if inner is not None and not self.library.methods(Cls(owner.cls.name), function.attr):
                return self._construct(node, inner)
            return self._invoke(node, None, Cls(owner.cls.name), function.attr,
                                arguments, True)
        if owner.kind == "list":
            _fail(node, "a list written here has no Java type yet")
        if owner.type is NULL or isinstance(owner.type, Prim):
            _fail(node, "%s has no methods" % _shown(owner.type))
        return self._invoke(node, owner, _upper(owner.type), function.attr, arguments, False)

    def _construct(self, node, found):
        arguments = [self._expression(argument) for argument in node.args]
        if found.is_interface or found.is_abstract:
            _fail(node, "%s cannot be made with %s()" % (found.simple, found.simple),
                  cause="It is %s: Android hands you one instead." % (
                      "an interface" if found.is_interface else "an abstract class"),
                  suggestions=self._ways_to_make(found))
        kind = Cls(found.name)
        candidates = [pair for pair in self.library.methods(kind, "<init>") if pair[0].public]
        if not candidates:
            _fail(node, "%s cannot be made with %s()" % (found.simple, found.simple),
                  suggestions=self._ways_to_make(found))
        fit = self._pick(node, candidates, arguments, "%s(...)" % found.simple)
        self._after_pick(node, fit, arguments)
        return _E("new %s(%s)" % (source(kind), ", ".join(fit["codes"])), kind, atom=True)

    def _invoke(self, node, owner, kind, name, arguments, on_class):
        if isinstance(kind, Arr):
            _fail(node, "an array has no %s()" % name,
                  suggestions=["len(values) for how many it holds."])
        candidates = [pair for pair in self.library.methods(kind, name) if pair[0].public]
        if not candidates:
            field, _type = self.library.field(kind, name)
            hints = []
            if field is not None:
                hints.append("It is a field, not a method: leave the () out.")
            hints.extend("Did you mean %s()?" % close for close in
                         _close(name, self.library.member_names(kind, static=True if on_class else None)))
            if kind == OBJECT:
                hints.extend([
                    "All Java knows here is that it is an Object. Say what it "
                    "is: native.cast(Vibrator, value)",
                    "A system service comes typed when you pass the class: "
                    "context.getSystemService(Vibrator)"])
            _fail(node, "%s has no method %s()" % (_shown(kind), name),
                  cause="Checked against android.jar, the classes the app is built with.",
                  suggestions=hints)
        if on_class:
            statics = [pair for pair in candidates if pair[0].static]
            if not statics:
                _fail(node, "%s() needs a %s object, not the class"
                      % (name, _shown(kind)),
                      suggestions=self._ways_to_make(self.library.find(kind.name)))
            candidates = statics
        fit = self._pick(node, candidates, arguments, "%s()" % name)
        method = fit["method"]
        self._after_pick(node, fit, arguments)
        receiver = source(Cls(kind.name)) if on_class else _p(owner)
        bindings = dict(fit["class_bindings"])
        bindings.update(fit["bindings"])
        bounds = dict(self.library.bounds(Cls(method.owner)))
        bounds.update(dict(method.type_params))
        answer = erase(_upper(substitute(method.ret, bindings)), bounds)
        return _E("%s.%s(%s)" % (receiver, name, ", ".join(fit["codes"])), answer, atom=True)

    def _after_pick(self, node, fit, arguments=()):
        method = fit["method"]
        for name in method.throws:
            self._thrown(node, name)
        for argument in arguments:
            if argument.kind == "class":        # Vibrator.class: the class itself
                self._since_class(node, argument.cls.name)
        if self.levels is not None:
            level = self.levels.of_method(method.owner, method.name, method.descriptor)
            what = ("%s(...)" % _shown(Cls(method.owner)) if method.is_constructor
                    else "%s.%s()" % (_shown(Cls(method.owner)), method.name))
            self._since(node, level, what)

    # -- which method --------------------------------------------------------

    def _pick(self, node, candidates, arguments, what):
        """The overload Java would choose, widened by two things Python needs:
        a list where an array goes, and a long or a float narrowed when no
        method takes it as it is."""
        for limit, spread in ((1, False), (2, False), (2, True), (5, False), (5, True)):
            fits = []
            for method, class_bindings in candidates:
                fit = self._fit(method, class_bindings, arguments, limit, spread)
                if fit is not None:
                    fits.append(fit)
            if not fits:
                continue
            if len(fits) > 1:
                fits = self._most_specific(fits)
            if len(fits) > 1:
                best = min(fit["cost"] for fit in fits)
                fits = [fit for fit in fits if fit["cost"] == best]
            if len(fits) > 1:
                _fail(node, "%s could be more than one method" % what,
                      cause="These all take what was passed: %s." % "; ".join(
                          _listed([(fit["method"], None) for fit in fits])),
                      suggestions=["Say which with native.cast(): "
                                   'native.cast("long", value), native.cast(String, None).'])
            return fits[0]
        given = ", ".join(_shown_argument(argument) for argument in arguments) or "nothing"
        _fail(node, "%s does not take (%s)" % (what, given),
              cause="Checked against android.jar, the classes the app is built with.",
              suggestions=["It takes: %s" % shown if not shown.startswith("and ")
                           else "(%s)" % shown for shown in _listed(candidates)])

    def _fit(self, method, class_bindings, arguments, limit, spread):
        params = [substitute(param, class_bindings) for param in method.params]
        if spread:
            if not method.varargs or len(arguments) < len(params) - 1:
                return None
            fixed = params[:-1]
            rest = [params[-1].elem] * (len(arguments) - len(fixed))
            params = fixed + rest
        elif len(arguments) != len(params):
            return None
        variables = {name for name, _bound in method.type_params}
        bindings = {}
        for param, argument in zip(params, arguments):
            self._unify(param, argument, variables, bindings)
        bounds = dict(method.type_params)
        codes, cost, kinds = [], 0, []
        for param, argument in zip(params, arguments):
            wanted = erase(_upper(substitute(param, bindings)), bounds)
            found = self._convert(argument, wanted)
            if found is None or found[0] > limit:
                return None
            cost += found[0]
            codes.append(found[1])
            kinds.append(wanted)
        return {"method": method, "codes": codes, "cost": cost, "kinds": kinds,
                "bindings": bindings, "class_bindings": class_bindings, "spread": spread}

    def _unify(self, param, argument, variables, bindings):
        """What the method's own type variables are, from what was passed:
        ``getSystemService(Class<T>)`` given ``Vibrator`` makes ``T`` a
        Vibrator."""
        if not variables:
            return
        if isinstance(param, TVar):
            if param.name in variables and param.name not in bindings \
                    and argument.kind == "value" and argument.type is not NULL:
                kind = argument.type
                if isinstance(kind, Prim) and kind.name in BOXES:
                    kind = Cls(BOXES[kind.name])
                if not isinstance(kind, Prim):
                    bindings[param.name] = kind
            return
        if isinstance(param, Arr) and argument.kind == "value" \
                and isinstance(argument.type, Arr):
            self._unify(param.elem, _E(type=argument.type.elem), variables, bindings)
            return
        if not (isinstance(param, Cls) and param.args):
            return
        if argument.kind == "class":
            if param.name == "java.lang.Class":
                inner = param.args[0]
                if isinstance(inner, Wild):
                    inner = inner.bound
                if isinstance(inner, TVar) and inner.name in variables:
                    bindings.setdefault(inner.name, Cls(argument.cls.name))
            return
        if argument.kind != "value" or not isinstance(argument.type, Cls):
            return
        for kind in self.library.lineage(argument.type):
            if kind.name == param.name and len(kind.args) == len(param.args):
                for inner, actual in zip(param.args, kind.args):
                    if isinstance(inner, Wild):
                        inner = inner.bound
                    if isinstance(inner, TVar) and inner.name in variables \
                            and not isinstance(actual, (Wild, TVar)):
                        bindings.setdefault(inner.name, actual)
                return

    def _most_specific(self, fits):
        def narrower(one, other):
            if len(one["kinds"]) != len(other["kinds"]):
                return False
            return all(self._assignable(a, b) for a, b in zip(one["kinds"], other["kinds"]))
        best = [fit for fit in fits
                if all(fit is other or narrower(fit, other) for other in fits)]
        if not best:
            return fits
        # The same method reached through two parents, or two with the very
        # same arguments: the nearest one is the one javac takes.
        first = best[0]
        if all(fit["kinds"] == first["kinds"] for fit in best):
            return [first]
        return best

    def _assignable(self, kind, target):
        if kind == target:
            return True
        if isinstance(kind, Prim) and isinstance(target, Prim):
            return target.name in _WIDENS.get(kind.name, ())
        if isinstance(kind, Cls) and isinstance(target, Cls):
            return self.library.is_a(kind.name, target.name)
        if isinstance(kind, Arr):
            if isinstance(target, Arr):
                return self._assignable(kind.elem, target.elem) and not isinstance(kind.elem, Prim)
            return isinstance(target, Cls) and target.name in (
                "java.lang.Object", "java.lang.Cloneable", "java.io.Serializable")
        return False

    def _convert(self, argument, target):
        """``(cost, java)`` for the argument where ``target`` is expected, or
        ``None``. 0 as it is, 1 widened, 2 boxed, 3 a literal re-spelt, 5
        narrowed with a cast."""
        if argument.kind == "class":
            if isinstance(target, Cls) and target.name in (
                    "java.lang.Class", "java.lang.Object", "java.io.Serializable",
                    "java.lang.reflect.Type"):
                return 0, source(Cls(argument.cls.name)) + ".class"
            return None
        if argument.kind == "list":
            if not isinstance(target, Arr):
                return None
            codes, cost = [], 0
            for item in argument.items:
                found = self._convert(item, target.elem)
                if found is None:
                    return None
                # A number written in a list is the kind of number the array
                # holds: [0, 200] is a long[] where a long[] is expected.
                cost = max(cost, min(found[0], 1) if item.const is not None else found[0])
                codes.append(found[1])
            return cost, "new %s{%s}" % (source(target), ", ".join(codes))
        kind = argument.type
        if kind == VOID:
            return None
        if kind is NULL:
            return (None if isinstance(target, Prim) else (1, "null"))
        if isinstance(target, Prim):
            plain = _unboxed(kind)
            if not isinstance(plain, Prim):
                return None
            extra = 0 if plain is kind or plain == kind else 2
            if plain == target:
                return extra, argument.code
            if plain == BOOLEAN or target == BOOLEAN:
                return None
            if target.name in _WIDENS.get(plain.name, ()):
                return 1 + extra, argument.code
            if isinstance(argument.const, float) and target == FLOAT:
                return 3, repr(argument.const) + "f"
            if isinstance(argument.const, str) and len(argument.const) == 1 \
                    and target == CHAR:
                return 3, _java_char(argument.const)
            if isinstance(argument.const, int) and not isinstance(argument.const, bool) \
                    and target.name in ("byte", "short", "char") and plain == INT:
                return 3, "(%s) %s" % (target.name, _p(argument, _UNARY))
            if (plain.name, target.name) in (("long", "int"), ("double", "float")):
                # Python has one whole number and one decimal; Java has two
                # of each, and a method that only takes the smaller one.
                return 5, "(%s) %s" % (target.name, _p(argument, _UNARY))
            return None
        if isinstance(kind, Prim):
            box = BOXES.get(kind.name)
            if box and isinstance(target, Cls) and self.library.is_a(box, target.name):
                return 2, argument.code
            return None
        if isinstance(target, Cls):
            if isinstance(argument.const, str) and len(argument.const) == 1 \
                    and target.name == "java.lang.Character":
                return 3, _java_char(argument.const)
            if isinstance(kind, Cls):
                if kind.name == target.name:
                    return 0, argument.code
                if self.library.is_a(kind.name, target.name):
                    return 1, argument.code
                return None
            if isinstance(kind, Arr) and target.name in (
                    "java.lang.Object", "java.lang.Cloneable", "java.io.Serializable"):
                return 1, argument.code
            return None
        if isinstance(target, Arr) and isinstance(kind, Arr):
            if kind.elem == target.elem:
                return 0, argument.code
            if self._assignable(kind, target):
                return 1, argument.code
        return None

    def _to(self, node, value, target, what, cause="", suggestions=()):
        """The value where ``target`` is wanted, or the error that says why
        it cannot go there."""
        if value.kind == "value" and value.type == VOID:
            _fail(node, "that call answers nothing, so there is nothing to be %s" % what)
        found = self._convert(value, target)
        if found is None:
            _fail(node, "%s cannot be %s: it has to be %s"
                  % (_shown_argument(value), what, _a(target)),
                  cause=cause, suggestions=suggestions)
        return found[1]

    # -- since which Android -------------------------------------------------

    def _since(self, node, level, what):
        if level is None or level <= self.floor:
            return
        _fail(node, "%s arrived in %s" % (what, java_api.android_version(level)),
              cause=("The app also runs on older phones -- from %s -- and "
                     "there this line would crash it: the class or method is "
                     "not in that Android." % java_api.android_version(self.floor)),
              suggestions=["Put it under: if Build.VERSION.SDK_INT >= %d:" % level,
                           "And say in the else what an older phone does instead.",
                           'Build = native.use("android.os.Build")'])

    def _since_class(self, node, name):
        if self.levels is not None:
            self._since(node, self.levels.of_class(name), _shown(Cls(name)))

    def _since_field(self, node, field):
        if field.static and field.final and field.constant is not None:
            return          # javac copies a constant in: Build.VERSION_CODES.O is 26
        if self.levels is not None:
            self._since(node, self.levels.of_field(field.owner, field.name),
                        "%s.%s" % (_shown(Cls(field.owner)), field.name))

    def _ways_to_make(self, found):
        """How somebody gets an object of a class that has no constructor to
        call: the static methods that answer one, and the system service."""
        out = []
        if found is None:
            return out
        kind = Cls(found.name)
        for overloads in found.methods.values():
            for method in overloads:
                if method.static and method.public and isinstance(method.ret, Cls) \
                        and method.ret.name == found.name:
                    out.append("%s.%s" % (found.simple, method.shown()))
        if not (found.is_interface or found.is_abstract):
            for method, _b in self.library.methods(kind, "<init>"):
                if method.public:
                    out.append(method.shown())
        out = out[:4]
        if found.name.startswith("android.") and (found.is_abstract or not out):
            out.append("context.getSystemService(%s)" % found.simple)
        return out

    # -- operators -----------------------------------------------------------

    def _binary(self, node):
        left = self._value(node.left)
        right = self._value(node.right)
        op = node.op
        if isinstance(op, ast.Add) and (left.type == STRING or right.type == STRING):
            if left.type != STRING or right.type != STRING:
                other = right if left.type == STRING else left
                _fail(node, "text can only be joined to text",
                      received="text + %s" % _shown(other.type),
                      suggestions=["Wrap the other side: str(...)"])
            return _E("%s + %s" % (_p(left, 11), _p(right, 12)), STRING, prec=11)
        symbols = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.BitOr: "|",
                   ast.BitAnd: "&", ast.BitXor: "^", ast.LShift: "<<", ast.RShift: ">>"}
        if not (_is_numeric(left.type) and _is_numeric(right.type)):
            if isinstance(op, (ast.BitOr, ast.BitAnd, ast.BitXor)) \
                    and _unboxed(left.type) == BOOLEAN and _unboxed(right.type) == BOOLEAN:
                return self._operator(left, symbols[type(op)], right, BOOLEAN)
            _fail(node, "this needs two numbers",
                  received="%s and %s" % (_shown(left.type), _shown(right.type)))
        kind = _promote(left.type, right.type)
        if type(op) in (ast.BitOr, ast.BitAnd, ast.BitXor, ast.LShift, ast.RShift):
            if not (_is_integral(left.type) and _is_integral(right.type)):
                _fail(node, "this needs two whole numbers",
                      received="%s and %s" % (_shown(left.type), _shown(right.type)))
            if type(op) in (ast.LShift, ast.RShift):
                kind = _promote(left.type, INT)
            return self._operator(left, symbols[type(op)], right, kind,
                                  _fold(op, left, right))
        if type(op) in symbols:
            return self._operator(left, symbols[type(op)], right, kind,
                                  _fold(op, left, right))
        whole = _is_integral(left.type) and _is_integral(right.type)
        if isinstance(op, ast.Div):
            if whole:
                # Python's / is never the whole-number division Java's is.
                return _E("(double) %s / %s" % (_p(left, _UNARY), _p(right, 13)),
                          DOUBLE, prec=12)
            return self._operator(left, "/", right, kind)
        if isinstance(op, ast.FloorDiv):
            if whole:
                return _E("Math.floorDiv(%s, %s)" % (
                    _as(left, kind), _as(right, kind)), kind, atom=True)
            return _E("Math.floor(%s / %s)" % (_p(left, 12), _p(right, 13)),
                      DOUBLE, atom=True)
        if isinstance(op, ast.Mod):
            if whole:
                # % in Python takes the sign of the right side; floorMod does too.
                return _E("Math.floorMod(%s, %s)" % (
                    _as(left, kind), _as(right, kind)), kind, atom=True)
            return _E("%s - Math.floor(%s / %s) * %s" % (
                _p(left, 11), _p(left, 12), _p(right, 13), _p(right, 13)),
                      DOUBLE, prec=11)
        if isinstance(op, ast.Pow):
            return _E("Math.pow(%s, %s)" % (left.code, right.code), DOUBLE, atom=True)
        _fail(node, "this operator is not available inside a native block")

    @staticmethod
    def _operator(left, symbol, right, kind, const=None):
        level = _PRECEDENCE[symbol]
        return _E("%s %s %s" % (_p(left, level), symbol, _p(right, level + 1)),
                  kind, const=const, prec=level)

    def _unary(self, node):
        if isinstance(node.op, ast.Not):
            return _E(self._truth(self._expression(node.operand), 8, negate=True),
                      BOOLEAN, prec=8)
        value = self._value(node.operand)
        if isinstance(node.op, ast.USub) and isinstance(value.const, (int, float)) \
                and not isinstance(value.const, bool):
            if isinstance(value.const, int):
                return _int(node, -value.const)
            return _E(repr(-value.const), DOUBLE, const=-value.const)
        if not _is_numeric(value.type):
            _fail(node, "this needs a number", received=_shown(value.type))
        kind = _promote(value.type, INT)
        if isinstance(node.op, ast.USub):
            return _E("-%s" % _p(value, _UNARY), kind, prec=_UNARY)
        if isinstance(node.op, ast.UAdd):
            return _E(value.code, kind, prec=value.prec)
        if not _is_integral(value.type):
            _fail(node, "~ needs a whole number", received=_shown(value.type))
        return _E("~%s" % _p(value, _UNARY), kind, prec=_UNARY,
                  const=~value.const if isinstance(value.const, int) else None)

    def _truth(self, value, need=0, negate=False):
        """The expression as a Java condition, with Python's idea of true --
        or of false, for ``not``. ``need`` is how tightly the place it goes
        binds."""
        if value.kind != "value":
            _fail(None, "a class is not a condition")
        kind = value.type
        plain = _unboxed(kind)
        if kind == VOID:
            _fail(None, "that call answers nothing, so it cannot be a condition")
        if kind == BOOLEAN:
            text, level = ("!" + _p(value, _UNARY), _UNARY) if negate \
                else (value.code, value.prec)
        elif plain == BOOLEAN:
            text, level = "Boolean.%s.equals(%s)" % (
                "FALSE" if negate else "TRUE", value.code), _ATOM
        elif isinstance(plain, Prim) and plain.name in _RANK:
            text, level = "%s %s 0" % (_p(value, 9), "==" if negate else "!="), 8
        elif kind == STRING or (isinstance(kind, Cls) and kind.name == "java.lang.CharSequence"):
            # Empty text is false in Python, and so is no text at all.
            text = "android.text.TextUtils.isEmpty(%s)" % value.code
            text, level = (text, _ATOM) if negate else ("!" + text, _UNARY)
        else:
            text, level = "%s %s null" % (_p(value, 9), "==" if negate else "!="), 8
        return text if level >= need else "(%s)" % text

    def _compare(self, node):
        parts = []
        left = self._value(node.left)
        for op, right_node in zip(node.ops, node.comparators):
            right = self._value(right_node)
            parts.append(self._compare_pair(node, left, op, right))
            left = right
        if len(parts) == 1:
            return _E(parts[0][0], BOOLEAN, prec=parts[0][1])
        return _E(" && ".join(text if level > 4 else "(%s)" % text
                              for text, level in parts), BOOLEAN, prec=4)

    def _compare_pair(self, node, left, op, right):
        numbers = _is_numeric(left.type) and _is_numeric(right.type)
        if isinstance(op, (ast.In, ast.NotIn)):
            if right.type is NULL or isinstance(right.type, Prim):
                _fail(node, "`in` needs text or a collection on its right")
            kind = _upper(right.type)
            name = "containsKey" if (isinstance(kind, Cls) and self.library.is_a(
                kind.name, "java.util.Map")) else "contains"
            if isinstance(kind, Arr) or not self.library.methods(kind, name):
                _fail(node, "%s cannot be searched with `in`" % _shown(kind))
            found = self._invoke(node, right, kind, name, [left], False)
            return (found.code, _ATOM) if isinstance(op, ast.In) else ("!" + found.code, _UNARY)
        if isinstance(op, (ast.Is, ast.IsNot)):
            symbol = "==" if isinstance(op, ast.Is) else "!="
            if isinstance(left.type, Prim) != isinstance(right.type, Prim) \
                    and NULL in (left.type, right.type):
                _fail(node, "a number is never None")
            return "%s %s %s" % (_p(left, 9), symbol, _p(right, 9)), 8
        if isinstance(op, (ast.Eq, ast.NotEq)):
            symbol = "==" if isinstance(op, ast.Eq) else "!="
            both_boolean = _unboxed(left.type) == BOOLEAN and _unboxed(right.type) == BOOLEAN
            if (numbers or both_boolean) and (
                    isinstance(left.type, Prim) or isinstance(right.type, Prim)):
                return "%s %s %s" % (_p(left, 9), symbol, _p(right, 9)), 8
            if NULL in (left.type, right.type):
                if isinstance(left.type, Prim) or isinstance(right.type, Prim):
                    _fail(node, "a number is never None")
                return "%s %s %s" % (_p(left, 9), symbol, _p(right, 9)), 8
            if isinstance(left.type, Prim) or isinstance(right.type, Prim):
                _fail(node, "these two cannot be compared",
                      received="%s and %s" % (_shown(left.type), _shown(right.type)),
                      suggestions=["Compare text with text: str(number) == text",
                                   "Or numbers with numbers: number == int(text)"])
            text = "java.util.Objects.equals(%s, %s)" % (left.code, right.code)
            return (text, _ATOM) if isinstance(op, ast.Eq) else ("!" + text, _UNARY)
        symbol = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="}[type(op)]
        if numbers:
            return "%s %s %s" % (_p(left, 10), symbol, _p(right, 10)), 9
        if left.type == STRING and right.type == STRING:
            return "%s.compareTo(%s) %s 0" % (_p(left), right.code, symbol), 9
        _fail(node, "these two cannot be put in order",
              received="%s and %s" % (_shown(left.type), _shown(right.type)))

    def _conditional(self, node):
        test = self._truth(self._expression(node.test), 3)
        inside, outside = self._guard(node.test)
        before = self.floor
        self.floor = max(before, inside)
        yes = self._value(node.body)
        self.floor = max(before, outside)
        no = self._value(node.orelse)
        self.floor = before
        kind = None
        if yes.type == no.type:
            kind = yes.type
        elif _is_numeric(yes.type) and _is_numeric(no.type):
            kind = _promote(yes.type, no.type)
        elif yes.type is NULL and not isinstance(no.type, Prim):
            kind = no.type
        elif no.type is NULL and not isinstance(yes.type, Prim):
            kind = yes.type
        elif self._assignable(yes.type, no.type):
            kind = no.type
        elif self._assignable(no.type, yes.type):
            kind = yes.type
        if kind is None or kind is NULL:
            _fail(node, "both answers of `x if ... else y` have to be the same kind",
                  received="%s and %s" % (_shown(yes.type), _shown(no.type)))
        return _E("%s ? %s : %s" % (test, _p(yes, 3), _p(no, 3)), kind, prec=2)

    def _fstring(self, node):
        parts = []
        for part in node.values:
            if isinstance(part, ast.Constant):
                if part.value:
                    parts.append(_java_string(str(part.value)))
                continue
            if part.format_spec is not None or part.conversion != -1:
                _fail(node, "a format inside {} is not available in a native block",
                      suggestions=["Work the text out first, then put it in the f-string."])
            parts.append(self._str(node, self._value(part.value)))
        if not parts:
            return _E('""', STRING, const="", atom=True)
        if len(parts) == 1:
            return _E(parts[0], STRING, atom=parts[0].startswith('"'))
        return _E(" + ".join(parts), STRING)

    def _item(self, node):
        owner = self._value(node.value)
        index_node = _slice(node)
        if isinstance(index_node, ast.Slice):
            _fail(node, "slices are not available inside a native block",
                  suggestions=["text.substring(start, end) for text."])
        index = self._value(index_node)
        if isinstance(owner.type, Arr):
            return _E("%s[%s]" % (_p(owner), self._to(node, index, INT, "an index")),
                      owner.type.elem, atom=True)
        if owner.type == STRING:
            _fail(node, "text has no [] in Java",
                  suggestions=["text.charAt(i) for one character",
                               "text.substring(start, end) for a piece"])
        if isinstance(owner.type, Cls) and self.library.methods(owner.type, "get"):
            return self._invoke(node, owner, owner.type, "get", [index], False)
        _fail(node, "%s has no items" % _shown(owner.type))

    # -- what Python has and Java spells differently -------------------------

    def _one(self, node, name):
        if len(node.args) != 1:
            _fail(node, "%s() takes one value" % name)
        return self._value(node.args[0])

    def _str(self, node, value):
        kind = _unboxed(value.type)
        if value.type == STRING:
            return _p(value)
        if value.type == VOID:
            _fail(node, "that call answers nothing, so there is no text to make of it")
        if kind == DOUBLE:
            return "_apkpyFloat(%s)" % value.code
        return "String.valueOf(%s)" % value.code

    def _builtin_str(self, node):
        value = self._one(node, "str")
        if value.type == STRING:
            return value
        return _E(self._str(node, value), STRING, atom=True)

    def _builtin_int(self, node):
        value = self._one(node, "int")
        kind = _unboxed(value.type)
        if value.type == STRING:
            return _E("Integer.parseInt(%s.trim())" % _p(value), INT, atom=True)
        if kind == BOOLEAN:
            return _E("%s ? 1 : 0" % _p(value, 3), INT, prec=2)
        if kind == INT:
            return value
        if isinstance(kind, Prim) and kind.name in _RANK:
            return _E("(int) %s" % _p(value, _UNARY), INT, prec=_UNARY)
        _fail(node, "int() needs text or a number", received=_shown(value.type))

    def _builtin_float(self, node):
        value = self._one(node, "float")
        kind = _unboxed(value.type)
        if value.type == STRING:
            return _E("Double.parseDouble(%s.trim())" % _p(value), DOUBLE, atom=True)
        if kind == DOUBLE:
            return value
        if isinstance(kind, Prim) and kind.name in _RANK:
            return _E("(double) %s" % _p(value, _UNARY), DOUBLE, prec=_UNARY)
        _fail(node, "float() needs text or a number", received=_shown(value.type))

    def _builtin_bool(self, node):
        return _E(self._truth(self._one(node, "bool")), BOOLEAN)

    def _builtin_len(self, node):
        value = self._one(node, "len")
        if isinstance(value.type, Arr):
            return _E("%s.length" % _p(value), INT, atom=True)
        if isinstance(value.type, Cls):
            for name in ("length", "size"):
                for method, _b in self.library.methods(value.type, name):
                    if not method.params and method.public:
                        return _E("%s.%s()" % (_p(value), name), INT, atom=True)
        _fail(node, "%s has no length" % _shown(value.type))

    def _builtin_print(self, node):
        parts = [self._str(node, self._value(argument)) for argument in node.args]
        text = ' + " " + '.join(parts) if parts else '""'
        return _E('android.util.Log.d("apkpy", %s)' % text, INT, atom=True)

    def _builtin_isinstance(self, node):
        if len(node.args) != 2:
            _fail(node, "isinstance() takes a value and a class")
        value = self._value(node.args[0])
        kind = self._expression(node.args[1])
        if kind.kind != "class" or isinstance(value.type, Prim):
            _fail(node, "isinstance() takes an object and a class named with native.use()")
        self._since_class(node, kind.cls.name)
        return _E("%s instanceof %s" % (_p(value, 10), source(Cls(kind.cls.name))),
                  BOOLEAN, prec=9)

    def _builtin_abs(self, node):
        value = self._one(node, "abs")
        if not _is_numeric(value.type):
            _fail(node, "abs() needs a number", received=_shown(value.type))
        return _E("Math.abs(%s)" % value.code, _promote(value.type, INT), atom=True)

    def _two_numbers(self, node, name):
        if len(node.args) != 2:
            _fail(node, "%s() takes two numbers inside a native block" % name)
        left, right = self._value(node.args[0]), self._value(node.args[1])
        if not (_is_numeric(left.type) and _is_numeric(right.type)):
            _fail(node, "%s() needs two numbers" % name,
                  received="%s and %s" % (_shown(left.type), _shown(right.type)))
        return _E("Math.%s(%s, %s)" % (name, left.code, right.code),
                  _promote(left.type, right.type), atom=True)

    def _builtin_min(self, node):
        return self._two_numbers(node, "min")

    def _builtin_max(self, node):
        return self._two_numbers(node, "max")

    def _builtin_round(self, node):
        value = self._one(node, "round")
        if not _is_numeric(value.type):
            _fail(node, "round() needs a number", received=_shown(value.type))
        if _is_integral(value.type):
            return value
        return _E("(int) Math.rint(%s)" % value.code, INT, prec=_UNARY)

    def _native_call(self, node, verb):
        if verb != "cast":
            _fail(node, "native.%s() is not something a block can call" % verb,
                  suggestions=["native.cast(Class, value) says what a value is."])
        if len(node.args) != 2:
            _fail(node, "native.cast() takes the class and the value",
                  suggestions=["native.cast(Vibrator, service)", 'native.cast("long", number)'])
        value = self._expression(node.args[1])
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            name = first.value.strip()
            if name not in _RANK and name != "boolean":
                _fail(node, "native.cast(%r, ...) is not a kind of number" % name,
                      suggestions=['One of: "int", "long", "float", "double", '
                                   '"short", "byte", "char".'])
            plain = _unboxed(value.type) if value.kind == "value" else None
            if not (isinstance(plain, Prim) and plain.name in _RANK):
                _fail(node, "native.cast(%r, ...) needs a number" % name)
            if isinstance(value.const, float) and name == "float":
                return _E(repr(value.const) + "f", FLOAT, atom=value.const >= 0)
            if isinstance(value.const, int) and name == "long":
                return _E("%dL" % value.const, LONG, const=value.const, atom=value.const >= 0)
            return _E("(%s) %s" % (name, _p(value, _UNARY)), Prim(name), prec=_UNARY)
        target = self._expression(first)
        if target.kind != "class":
            _fail(node, "native.cast() takes a class named with native.use()",
                  suggestions=["native.cast(Vibrator, service)"])
        kind = Cls(target.cls.name)
        self._since_class(node, kind.name)
        if value.kind != "value" or isinstance(value.type, Prim):
            _fail(node, "native.cast(%s, ...) needs an object" % target.cls.simple)
        if value.type is NULL:
            return _E("(%s) null" % source(kind), kind, prec=_UNARY)
        return _E("(%s) %s" % (source(kind), _p(value, _UNARY)), kind, prec=_UNARY)


# --- helpers that need no translator ----------------------------------------

def _int(node, value):
    if native_rules.INT_MIN <= value <= native_rules.INT_MAX:
        return _E(str(value), INT, const=value, atom=value >= 0)
    if native_rules.LONG_MIN <= value <= native_rules.LONG_MAX:
        return _E("%dL" % value, LONG, const=value, atom=value >= 0)
    _fail(node, "that number is too large for Java",
          cause="A whole number on the phone has 64 bits.")


def _fold(op, left, right):
    """The value of two numbers written out, so `FLAG_A | FLAG_B` and
    `26 + 1` are still known where the build reads them."""
    if not (isinstance(left.const, int) and isinstance(right.const, int)) \
            or isinstance(left.const, bool) or isinstance(right.const, bool):
        return None
    try:
        return {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
                ast.Mult: lambda a, b: a * b, ast.BitOr: lambda a, b: a | b,
                ast.BitAnd: lambda a, b: a & b, ast.BitXor: lambda a, b: a ^ b,
                }[type(op)](left.const, right.const)
    except KeyError:
        return None


def _as(value, kind):
    """The number as the kind both sides of an operator were promoted to."""
    if _unboxed(value.type) == kind:
        return value.code
    return "(%s) %s" % (kind.name, _p(value, _UNARY))


def _java_char(text):
    if text == "'":
        return "'\\''"
    return "'" + _java_string(text)[1:-1].replace('\\"', '"') + "'"


def _default(kind):
    if isinstance(kind, Prim):
        return "false" if kind == BOOLEAN else "0"
    return "null"


def _upper(kind):
    """What a value read through a wildcard is known to be."""
    if isinstance(kind, Wild):
        return kind.bound if kind.kind == "+" and kind.bound is not None else OBJECT
    return kind


def _is_sdk_int(value):
    return (value.field is not None and value.field.name == "SDK_INT"
            and value.field.owner == "android.os.Build$VERSION")


def _slice(node):
    inner = node.slice
    if inner.__class__.__name__ == "Index":         # Python 3.8
        inner = inner.value
    return inner


def _shown_argument(argument):
    if argument.kind == "class":
        return "the class %s" % argument.cls.simple
    if argument.kind == "list":
        return "a list"
    if isinstance(argument.const, str):
        return "the text %s" % argument.code
    if argument.const is not None and not isinstance(argument.const, bool) \
            and argument.field is None:
        return "the number %s" % argument.code
    return _a(argument.type)


def _statement_name(node):
    return {"With": "with", "AsyncWith": "async with", "FunctionDef": "a function",
            "AsyncFunctionDef": "an async function", "ClassDef": "a class",
            "Delete": "del", "Global": "global", "Nonlocal": "nonlocal",
            "Import": "import", "ImportFrom": "import", "Assert": "assert",
            "Match": "match", "AsyncFor": "async for"}.get(
                type(node).__name__, type(node).__name__)


def _expression_name(node):
    return {"Lambda": "a lambda", "Dict": "a dict", "Set": "a set",
            "ListComp": "a comprehension", "SetComp": "a comprehension",
            "DictComp": "a comprehension", "GeneratorExp": "a comprehension",
            "Await": "await", "Yield": "yield", "Starred": "*args",
            "NamedExpr": ":="}.get(type(node).__name__, type(node).__name__)


# --- the module --------------------------------------------------------------

def _is_native_name(node):
    return isinstance(node, ast.Name) and node.id == "native"


def _use_call(node):
    """The ``native.use("...")`` of ``X = native.use("...")``, or ``None``."""
    if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
        return None
    function = node.value.func
    if isinstance(function, ast.Attribute) and function.attr == "use" \
            and _is_native_name(function.value):
        return node.value
    return None


def _decorator(function):
    """The ``native(...)`` over a function, or ``None``."""
    for decorator in function.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if _is_native_name(target):
            return decorator
    return None


def rewrite(tree, source_name="writehere.py"):
    """Replace every ``@native`` function with the ``native.java()`` block it
    translates to, and take the ``native.use()`` lines out.

    An app that has neither is returned untouched, and nothing of the SDK is
    looked at.
    """
    reset()
    uses, functions = [], []
    for node in tree.body:
        if _use_call(node) is not None:
            uses.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and _decorator(node) is not None:
            functions.append(node)
    _refuse_elsewhere(tree, uses, functions)
    if not uses and not functions:
        return tree

    library, levels = _library((uses + functions)[0])
    aliases = {}
    for node in uses:
        aliases.update([_alias(node, library, aliases)])

    blocks = {}
    for function in functions:
        blocks[id(function)] = _block_for(function, library, levels, aliases,
                                          source_name)

    used_outside = _names_outside(tree, functions, uses)
    for name, node in used_outside:
        if name in aliases:
            _fail(node, "%s is a Java class: it only exists inside a @native function"
                  % name,
                  cause=("The rest of the app is translated from Python and has "
                         "no Java objects in it."),
                  suggestions=["Use %s inside a function decorated with @native(...), "
                               "and return what the app needs." % name])

    body = []
    for node in tree.body:
        if node in uses:
            continue
        body.append(blocks.get(id(node), node))
    tree.body = body
    return tree


def _refuse_elsewhere(tree, uses, functions):
    """``native.use()`` and ``@native`` are declarations of the module."""
    top = set(map(id, uses)) | set(map(id, functions))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "use" and _is_native_name(node.func.value):
            if not any(use.value is node for use in uses):
                _fail(node, "native.use() names a class at the top of the file",
                      suggestions=['Vibrator = native.use("android.os.Vibrator")'])
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and _decorator(node) is not None and id(node) not in top:
            _fail(node, "@native goes on a function at the top of the file",
                  cause="The block becomes a method of every screen's Activity.")


def _alias(node, library, aliases):
    call = node.value
    if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
        _fail(node, "native.use() is given one name",
              suggestions=['Vibrator = native.use("android.os.Vibrator")'])
    name = node.targets[0].id
    if call.keywords or len(call.args) != 1 or not (
            isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str)):
        _fail(node, "native.use() takes the full name of one class, written out",
              cause="The build reads your module, it never runs it.",
              suggestions=['%s = native.use("android.os.%s")' % (name, name)])
    dotted = call.args[0].value.strip()
    if name in aliases or name in _GIVEN or name in _JAVA_WORDS or keyword.iskeyword(name):
        _fail(node, "%r is taken" % name, suggestions=["Give the class another name."])
    found = library.resolve(dotted)
    if found is None:
        simple = dotted.rsplit(".", 1)[-1]
        hints = ['native.use("%s")' % close for close in library.packages_with(simple)[:4]]
        if not hints:
            hints = ['Did you mean native.use("%s")?' % close
                     for close in library.close_to(simple)]
        if not hints:
            hints.append("Classes of a library added with native.gradle() are not "
                         "readable yet: write that block in Java, native.java(...).")
        _fail(node, "there is no class %s in Android" % dotted,
              cause="Looked for in android.jar, the classes the app is built with.",
              received=dotted, suggestions=hints)
    return name, found


def _block_for(function, library, levels, aliases, source_name):
    decorator = _decorator(function)
    if isinstance(function, ast.AsyncFunctionDef):
        _fail(function, "@native goes on a plain def",
              suggestions=["def %s(...): ..." % function.name])
    if len(function.decorator_list) != 1:
        _fail(function, "@native is the only decorator a block takes")
    if not isinstance(decorator, ast.Call) or decorator.args:
        _fail(function, "@native needs preview=",
              cause=("The Previewer cannot run Java. Without preview= the block "
                     "would work on the phone and do nothing on the desktop."),
              suggestions=["@native(preview=lambda: \"87\")",
                           "@native(preview=a_function_that_answers_the_same)"])
    preview = None
    for item in decorator.keywords:
        if item.arg == "preview":
            preview = item.value
        else:
            _fail(function, "@native takes preview= and nothing else",
                  received="%s=" % item.arg)
    if preview is None:
        _fail(function, "@native needs preview=",
              cause=("The Previewer cannot run Java. Without preview= the block "
                     "would work on the phone and do nothing on the desktop."),
              suggestions=['@native(preview=lambda: "87")'])
    if function.name in aliases or function.name in _JAVA_WORDS:
        _fail(function, "%r is taken" % function.name,
              suggestions=["Give the function another name."])

    found = _Translator(library, levels, aliases, function, source_name).translate()
    _BLOCKS[0][function.name] = {
        "line": function.lineno, "kinds": found["kinds"],
        "names": [argument.arg for argument in function.args.args]}

    def text(value):
        return ast.copy_location(ast.Constant(value=value), function)

    call = ast.Call(
        func=ast.Attribute(value=ast.Name(id="native", ctx=ast.Load()),
                           attr="java", ctx=ast.Load()),
        args=[text(function.name)],
        keywords=[
            ast.keyword(arg="code", value=text(found["code"])),
            ast.keyword(arg="args", value=ast.Tuple(
                elts=[text(name) for name in found["args"]], ctx=ast.Load())),
            ast.keyword(arg="preview", value=preview),
        ])
    block = ast.Assign(targets=[ast.Name(id=function.name, ctx=ast.Store())],
                       value=call)
    ast.copy_location(block, function)
    ast.fix_missing_locations(block)
    return block


def _names_outside(tree, functions, uses):
    """Every name read outside the native functions, with where."""
    skip = set(map(id, functions)) | set(map(id, uses))
    out = []

    def walk(node):
        if id(node) in skip:
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            out.append((node.id, node))
        for child in ast.iter_child_nodes(node):
            walk(child)

    walk(tree)
    return out


def helpers_java():
    """What turns the text an app passes into the number a block declared.
    ``native_rules`` is the same rules in Python; a test asks both."""
    if not _BLOCKS[0]:
        return []
    return [
        "",
        "    // --- arguments of @native functions ---------------------------",
        "    // The same rules as apkpy_lib/native_rules.py, which the Previewer uses.",
        "    private static long _apkpyNativeLong(String text, String name) {",
        "        String trimmed = text == null ? \"\" : text.trim();",
        "        if (trimmed.matches(\"%s\")) {" % native_rules.WHOLE.replace("\\", "\\\\"),
        "            try { return Long.parseLong(trimmed.startsWith(\"+\") ? trimmed.substring(1) : trimmed); }",
        "            catch (NumberFormatException tooLong) { }",
        "        } else if (trimmed.matches(\"%s\")) {" % native_rules.NUMBER.replace("\\", "\\\\"),
        "            double decimal = Double.parseDouble(trimmed);",
        "            if (Math.abs(decimal) < 9.0e18 && decimal == Math.rint(decimal)) return (long) decimal;",
        "        }",
        "        throw new IllegalArgumentException(",
        "                name + \" has to be a whole number, got \\\"\" + trimmed + \"\\\"\");",
        "    }",
        "",
        "    private static int _apkpyNativeInt(String text, String name) {",
        "        long value = _apkpyNativeLong(text, name);",
        "        if (value < Integer.MIN_VALUE || value > Integer.MAX_VALUE) {",
        "            throw new IllegalArgumentException(",
        "                    name + \": \" + value + \" does not fit in an int; declare it as \\\"long\\\"\");",
        "        }",
        "        return (int) value;",
        "    }",
        "",
        "    private static double _apkpyNativeDouble(String text, String name) {",
        "        String trimmed = text == null ? \"\" : text.trim();",
        "        if (!trimmed.matches(\"%s\")) {" % native_rules.NUMBER.replace("\\", "\\\\"),
        "            throw new IllegalArgumentException(",
        "                    name + \" has to be a number, got \\\"\" + trimmed + \"\\\"\");",
        "        }",
        "        return Double.parseDouble(trimmed);",
        "    }",
        "",
        "    private static boolean _apkpyNativeBool(String text) {",
        "        return text != null && text.trim().equalsIgnoreCase(\"true\");",
        "    }",
    ]
