# -*- coding: utf-8 -*-
"""``from apkpy_lib import native`` -- your own Java, with a desktop answer.

The Previewer cannot run Java, and pretending otherwise is the failure this
project keeps paying for: something works on the phone, does nothing on the
desktop, and nobody is told. So a native block is declared with two halves --
the Java that runs on the phone, and the ``preview=`` that answers here. This
module is the desktop half.

    battery = native.java(
        "batteryHealth",
        imports=["android.os.BatteryManager", "android.content.Context"],
        code='''
            BatteryManager bm = (BatteryManager)
                    context.getSystemService(Context.BATTERY_SERVICE);
            return String.valueOf(bm.getIntProperty(
                    BatteryManager.BATTERY_PROPERTY_CAPACITY));
        ''',
        preview=lambda: "87",
    )

    def show():
        level.set_value(battery())          # a String, like everything else

The rules of the seam live in :mod:`apkpy_lib.core.features.native`, which is
what the build reads; this module keeps the same shape so an app behaves the
same in both places.
"""
from __future__ import annotations

from .. import native_rules
from ..diagnostics import ApkpyError

__all__ = ["NativeAPI", "NativeFunction", "JavaClass", "native"]

DOCS = "https://repo-apkpy.pages.dev/guides/native/"

# What was declared, for the note the Previewer prints and for tests.
DECLARED = {"java": [], "gradle": [], "manifest": [], "keep": []}
_ANNOUNCED = set()


def _fail(message, cause="", suggestions=()):
    raise ApkpyError(message, code="U2035",
                     title="A native block cannot be read",
                     cause=cause, suggestions=list(suggestions), docs=DOCS)


def _text(label, value, required=True):
    if value is None:
        if not required:
            return ""
        _fail("native: %s is missing" % label,
              suggestions=['Write it as text: %s="..."' % label])
    if not isinstance(value, str):
        _fail("native: %s has to be text" % label,
              cause="The build reads your module, it never runs it.",
              suggestions=['Write it as text: %s="..."' % label])
    return value


class _Done:
    """What an async block answers through.

    On the phone the block writes ``done.run(true, value)``. Here both
    spellings work, so the two halves of a block read the same way.
    """

    def __init__(self, deliver):
        self._deliver = deliver
        self._used = False

    def __call__(self, ok=True, value=""):
        self.run(ok, value)

    def run(self, ok=True, value=""):
        if self._used:
            return          # the phone calls back once; so does this
        self._used = True
        self._deliver(bool(ok), "" if value is None else str(value))


class JavaClass:
    """What ``native.use("android.os.Vibrator")`` is on the desktop: a name.

    The class exists on the phone. Here it can be handed to ``@native``
    functions, whose bodies the Previewer never runs, and nothing else.
    """

    def __init__(self, name):
        self.java_name = name

    def __repr__(self):                                   # pragma: no cover
        return "<Java class %s>" % self.java_name

    def _only_on_the_phone(self, what):
        raise ApkpyError(
            "%s is an Android class: it only exists on the phone" % self.java_name,
            code=native_rules.CODE,
            title="A Java class was used outside a @native function",
            cause=("The Previewer runs your Python, and there is no Android "
                   "on the desktop to %s." % what),
            suggestions=["Use it inside a function decorated with "
                         "@native(preview=...): its body is translated to Java "
                         "and runs on the phone."],
            docs=DOCS + "#written-in-python")

    def __call__(self, *args, **kwargs):
        self._only_on_the_phone("make one")

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        self._only_on_the_phone("read %s from" % name)


class NativeFunction:
    """A declared block, called like any other function."""

    def __init__(self, java_name, preview, is_async, args, kinds=None,
                 written="Java"):
        self.java_name = java_name
        self.is_async = is_async
        self.args = tuple(args)
        # A block written in Python says what each argument is; one written
        # in Java takes text, like everything else the generator writes.
        self.kinds = tuple(kinds) if kinds is not None else None
        self._written = written
        self._preview = preview

    def __repr__(self):                                   # pragma: no cover
        return "<native %s%s>" % (self.java_name, "()" if not self.args else
                                  "(%s)" % ", ".join(self.args))

    def _announce(self):
        if self.java_name in _ANNOUNCED:
            return
        _ANNOUNCED.add(self.java_name)
        print('[ApkPy] native block "%s" is simulated here by its preview='
              ' -- the %s runs on the phone.' % (
                  self.java_name,
                  "Java" if self._written == "Java" else "function"))

    def __call__(self, *values, **kwargs):
        on_result = kwargs.pop("on_result", None)
        if kwargs:
            _fail("native: %s() got %s" % (self.java_name,
                                           ", ".join(sorted(kwargs))),
                  suggestions=["Pass the arguments you declared in args=, and "
                               "on_result= for an async block."])
        if len(values) != len(self.args):
            _fail("native: %s() takes %d argument(s), got %d"
                  % (self.java_name, len(self.args), len(values)),
                  suggestions=["It was declared with args=%r." % (self.args,)])
        self._announce()
        if self.kinds is not None:
            # What the phone does: the value crosses as text and is read as
            # the kind the function declared. The same rules, so a text the
            # phone would refuse is refused here.
            given = []
            for name, kind, value in zip(self.args, self.kinds, values):
                try:
                    given.append(native_rules.read(kind, native_rules.text_of(value), name))
                except ValueError as problem:
                    _fail("native: %s() was given a wrong %s" % (self.java_name, name),
                          cause=str(problem),
                          suggestions=["Pass what %s is declared to take." % name])
            return native_rules.text_of(self._preview(*given))
        texts = ["" if value is None else str(value) for value in values]

        if not self.is_async:
            if on_result is not None:
                _fail("native: %s() answers straight away" % self.java_name,
                      cause="on_result= belongs to native.java_async().",
                      suggestions=["value = %s(...)" % self.java_name])
            answer = self._preview(*texts)
            return "" if answer is None else str(answer)

        done = _Done(lambda ok, value: _report(on_result, ok, value))
        self._preview(*texts, done)
        return None


def _report(callback, ok, value):
    if not callback:
        return
    try:
        callback(ok, value)
    except Exception as exc:                    # pragma: no cover - user code
        from ..ui import report_exception
        report_exception(exc, context="native callback")


class NativeAPI:
    """Android you reach yourself.

    ``java`` and ``java_async`` are seams for Java code; ``@native`` over a
    function and ``use`` are the same seam written in Python, translated when
    the app is built; ``gradle``, ``manifest`` and ``keep`` are for the build
    around either. Most real cases need both: an SDK is a dependency, a
    permission and some code, and a seam that only carried the code would
    leave you stuck at the second step.
    """

    def __call__(self, *positional, preview=None, **others):
        """``@native(preview=...)`` over a function whose body is Java
        written in Python. Here the body is never run: ``preview=`` answers."""
        if positional or others:
            _fail("@native takes preview= and nothing else",
                  suggestions=['@native(preview=lambda: "87")'])
        if preview is None:
            _fail("@native needs preview=",
                  cause=("The Previewer cannot run Java. Without preview= the "
                         "block would work on the phone and do nothing here."),
                  suggestions=['@native(preview=lambda: "87")',
                               "@native(preview=a function that answers the same)"])
        if not callable(preview):
            _fail("@native: preview= has to be something callable",
                  suggestions=['@native(preview=lambda: "87")'])

        def declare(function):
            code = getattr(function, "__code__", None)
            names = code.co_varnames[:code.co_argcount] if code else ()
            annotations = getattr(function, "__annotations__", {}) or {}
            kinds = []
            for name in names:
                kind = native_rules.kind_of(annotations.get(name))
                if kind is None:
                    _fail("@native %s(): %s cannot be %r" % (
                        function.__name__, name, annotations.get(name)),
                          suggestions=['One of: str, int, float, bool, "long".'])
                kinds.append(kind)
            DECLARED["java"].append(function.__name__)
            return NativeFunction(function.__name__, preview, False, names,
                                  kinds=kinds, written="Python")

        return declare

    def use(self, name):
        """A Java class by its full name, for the ``@native`` functions."""
        return JavaClass(_text("the class name", name))

    def java(self, name, code=None, imports=(), args=(), preview=None):
        """A block that answers one String."""
        return self._declare(name, code, imports, args, preview, False)

    def java_async(self, name, code=None, imports=(), args=(), preview=None):
        """A block that answers later, through ``done``."""
        return self._declare(name, code, imports, args, preview, True)

    def _declare(self, name, code, imports, args, preview, is_async):
        java_name = _text("the method name", name)
        _text("code", code)
        if preview is None:
            _fail("native: preview= is missing",
                  cause=("The Previewer cannot run Java. Without preview= the "
                         "block would work on the phone and do nothing here."),
                  suggestions=['preview=lambda: "87"',
                               "preview=a function that answers the same shape"])
        if not callable(preview):
            _fail("native: preview= has to be something callable",
                  suggestions=['preview=lambda: "87"'])
        function = NativeFunction(java_name, preview, is_async, args)
        DECLARED["java"].append(java_name)
        return function

    def gradle(self, line):
        """One Gradle dependency line for the generated project."""
        DECLARED["gradle"].append(_text("the dependency", line))

    def manifest(self, permission=None, feature=None, xml=None):
        """A permission, a ``<uses-feature>`` or an element of your own."""
        if permission is None and feature is None and xml is None:
            _fail("native.manifest() needs permission=, feature= or xml=",
                  suggestions=['native.manifest(permission="android.permission.VIBRATE")'])
        DECLARED["manifest"].append({
            "permission": _text("permission", permission, required=False),
            "feature": _text("feature", feature, required=False),
            "xml": _text("xml", xml, required=False),
        })

    def keep(self, pattern):
        """An R8 keep rule, for classes only reached by reflection."""
        DECLARED["keep"].append(_text("the pattern", pattern))


native = NativeAPI()
