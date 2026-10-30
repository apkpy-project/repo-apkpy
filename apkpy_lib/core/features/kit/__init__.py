# -*- coding: utf-8 -*-
"""Compiler support for the calls that reach the rest of the phone.

    haptics.tap()            speech.say("Welcome back")      browser.open(url)
    files.save_as(name, text, on_result=saved)      downloads.start(url)
    calendar.add_event(...)  phone.dial(number)      recorder.start()
    printing.html(invoice)   incoming.links("notes")

Which calls exist, what each takes and what each answers is one table,
``apkpy_lib/kit_rules.py``, read by this module and by the Previewer.

**How they get into the app.** None of them is taught to the two generators.
Each call is a line of Java in a class of its own (the ``Apkpy*.java`` files
next to this one), and what reaches it from a screen is the seam ApkPy already
has for Java an app brings itself: a native block. :func:`rewrite` runs before
anything else reads the module and turns

    speech.say("Hello", rate=1.2, on_result=said)

into a call to a block it declares at the top of the module, with every
argument in its place and the ones left out filled in -- exactly what the
person would have written with ``native.java_async``. From there the call is
a native block like any other: it works as a statement and as a value, in a
function and in a lambda, it is refused inside a background job, and its
answer comes back on the main thread. Nothing in the two generators changed,
which is what keeps an app that uses none of this byte for byte the same.

Only what is used is written: one small method per call into each screen's
Activity, one class per family, and the manifest lines that family needs.
"""
from __future__ import annotations

import ast
import difflib
import os
import re
from pathlib import Path

from .... import kit_rules as rules
from .... import native_rules

__all__ = [
    "rewrite", "reset", "uses_kit", "label_for", "shared_files", "java_source",
    "class_names", "ALIAS_PREFIX", "activity_members", "orientation_of",
    "manifest_orientations",
]

ALIAS_PREFIX = "_apkpy_"
_HERE = Path(__file__).resolve().parent

_LAUNCHER_XML = (
    '<activity android:name=".ApkpyKitActivity" android:exported="false" '
    'android:theme="@android:style/Theme.Translucent.NoTitleBar" '
    'android:configChanges="orientation|screenSize|screenLayout|keyboardHidden|uiMode" />')

_APP_LOCK_XML = (
    '<provider android:name=".ApkpyAppLockStart" '
    'android:authorities="${applicationId}.apkpy.applock" android:exported="false" />')

# What a call needs around it. Keys are the ones named in kit_rules.SPEC.
NEEDS = {
    "vibrate": {"permissions": ("android.permission.VIBRATE",)},
    "internet": {"permissions": ("android.permission.INTERNET",)},
    "microphone": {"permissions": ("android.permission.RECORD_AUDIO",),
                   "features": ("android.hardware.microphone",)},
    # Since Android 11 an app only sees the other apps it says it looks for:
    # the speech engine, and whichever app turns speech into text.
    "tts": {"queries": ("android.intent.action.TTS_SERVICE",)},
    "recognise": {"queries": ("android.speech.action.RECOGNIZE_SPEECH",)},
    "launcher": {"classes": ("ApkpyKitActivity",), "application": (_LAUNCHER_XML,)},
    "incoming": {"classes": ("ApkpyIncoming", "ApkpyIncomingActivity")},
    # What these five write besides is made from what the app declared:
    # see _needs().
    "widget": {"classes": ("ApkpyWidgetProvider",)},
    "tile": {"classes": ("ApkpyTileService",)},
    "ads": {"permissions": ("android.permission.INTERNET",
                            "android.permission.ACCESS_NETWORK_STATE"),
            "gradle": rules.GRADLE["ads"]},
    # Play's own screen answers to an Activity, like the file picker does.
    "updates": {"gradle": rules.GRADLE["updates"], "classes": ("ApkpyKitActivity",),
                "application": (_LAUNCHER_XML,)},
    "health": {"classes": ("ApkpyHealthPolicyActivity",)},
    # A normal permission: it is in the manifest and nobody is asked.
    "network_state": {"permissions": ("android.permission.ACCESS_NETWORK_STATE",)},
    # The phone's own prompt (a normal permission), and the provider that
    # starts the lock with the process, before any screen.
    "app_lock": {"permissions": ("android.permission.USE_BIOMETRIC",),
                 "classes": ("ApkpyAppLockStart",),
                 "application": (_APP_LOCK_XML,)},
}

# Classes that are compiled against a library the family brings, not against
# android.jar alone: kept apart so the rest can be checked without it.
_WITH_LIBRARY = ("ApkpyAds", "ApkpyUpdates")

# Per transpilation, like the native module's own registers.
_USED = [{}]        # (namespace, verb) -> the first call, for its line
_LINKS = [[]]       # (scheme, host)
_SHARES = [[]]      # kind
_DECLARED = [{}]    # (namespace, verb) -> {argument: what was written}
_HEALTH = [[]]      # the kinds of health record the app names
_TIMED = [{}]       # function -> the first timer call that names it
_WATCHED = [{}]     # function -> the first network.on_change() that names it
_TOP = [{}]         # the functions written at the top level of the module


def reset():
    _USED[0] = {}
    _LINKS[0] = []
    _SHARES[0] = []
    _DECLARED[0] = {}
    _HEALTH[0] = []
    _TIMED[0] = {}
    _WATCHED[0] = {}
    _TOP[0] = {}


def uses_kit():
    return bool(_USED[0]) or bool(_LINKS[0]) or bool(_SHARES[0]) or bool(_DECLARED[0])


def declared(namespace):
    """What the app wrote in a family's declaration, or ``{}``."""
    verb = rules.DECLARED_BY.get(namespace, ("",))[0]
    return dict(_DECLARED[0].get((namespace, verb), {}))


def _java_name(namespace, verb):
    return "%s_%s" % (namespace, verb)


def _alias(namespace, verb):
    return "%s%s_%s" % (ALIAS_PREFIX, namespace, verb)


def label_for(java_name):
    """``haptics.tap()`` for one of these blocks, ``None`` for an app's own."""
    for namespace, verb in _USED[0]:
        if _java_name(namespace, verb) == java_name:
            return rules.label(namespace, verb)
    return None


# --- reading the module -----------------------------------------------------

def _is_ours(node, bound=()):
    """``namespace.verb`` -> (namespace, verb), for the namespaces of the table
    that the module has not given to something of its own."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
            and node.value.id in rules.SPEC and node.value.id not in bound:
        return node.value.id, node.attr
    return None


def _bound_names(tree):
    """Every name the module makes its own, with the line it does it on.

    ``phone = inputs("Phone", ...)`` is an ordinary thing to write, and then
    ``phone`` is the person's component, not ApkPy's dialler -- in Python, so
    in the build too. Such a name is left entirely alone: ``browser.open()``
    on a modal the app called ``browser`` is the modal's own ``open()``.
    """
    bound = {}

    def note(name, node):
        bound.setdefault(name, getattr(node, "lineno", 0))

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            note(node.id, node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            note(node.name, node)
        elif isinstance(node, ast.arg):
            note(node.arg, node)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            note(node.name, node)
        elif isinstance(node, ast.Import):
            for item in node.names:
                note((item.asname or item.name).split(".")[0], node)
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] == "apkpy_lib":
                continue
            for item in node.names:
                note(item.asname or item.name, node)
    return bound


def _functions(tree):
    return {node.name: node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)}


def _text(node):
    """Source-ish text of a small expression, for an error."""
    from ...unsupported import describe   # ast.unparse() is 3.9+; this is not
    try:
        return describe(node)
    except Exception:
        return "..."


def _fail(node, message, **more):
    rules.refuse(message, line=getattr(node, "lineno", 0), **more)


def _unknown_verb(node, namespace, name):
    _fail(node, **rules.unknown(namespace, name))


def _arguments(node, namespace, name, found, functions):
    """The call's arguments, each in its place: ``(values, on_result)``.

    ``values`` holds an AST node for every parameter, in the table's order --
    the one written, or the default as a constant.
    """
    shown = rules.signature(namespace, name)
    label = rules.label(namespace, name)
    if any(isinstance(argument, ast.Starred) for argument in node.args) \
            or any(keyword.arg is None for keyword in node.keywords):
        _fail(node, "%s takes its arguments written out" % label,
              cause="The build reads the call, it does not run it, so *args and "
                    "**kwargs have nothing in them yet.",
              received=_text(node), expected=shown)

    names = found.names
    later = found.mode == rules.LATER
    slots = names + (("on_result",) if later else ())
    if len(node.args) > len(slots):
        _fail(node, "%s takes %s, got %d"
              % (label, "no arguments" if not slots else
                 "at most %d argument%s" % (len(slots), "" if len(slots) == 1 else "s"),
                 len(node.args)),
              received=_text(node), expected=shown)

    given = {}
    for position, value in enumerate(node.args):
        given[slots[position]] = value
    for keyword in node.keywords:
        if keyword.arg not in slots:
            close = difflib.get_close_matches(keyword.arg, slots, n=1, cutoff=0.5)
            hints = ["Did you mean %s=?" % close[0]] if close else []
            if keyword.arg in ("on_result", "on_done", "callback") and not later:
                hints.append("%s answers at once: use what it returns." % label)
            _fail(node, "%s has no %s=" % (label, keyword.arg),
                  received=_text(node), expected=shown, suggestions=hints)
        if keyword.arg in given:
            _fail(node, "%s got %s twice" % (label, keyword.arg),
                  received=_text(node), expected=shown)
        given[keyword.arg] = keyword.value

    callback = given.pop("on_result", None) if later else None
    if callback is not None and not (isinstance(callback, ast.Constant)
                                     and callback.value is None):
        if not isinstance(callback, ast.Name) or callback.id not in functions:
            _fail(node, "%s: on_result= has to be a function you defined" % label,
                  cause="The generated Java calls it by name, so a lambda or an "
                        "expression has nothing to call.",
                  received=_text(node),
                  suggestions=["def answered(ok, value): ...   then   on_result=answered"])
        function = functions[callback.id]
        taken = len(function.args.args)
        if taken != 2 or function.args.vararg or function.args.kwonlyargs:
            _fail(function, "%s() is handed two things by %s: ok and value"
                  % (callback.id, label),
                  cause="ok is True or False; value is the result when ok, and "
                        "the word for why not when it is not.",
                  received="def %s(%s)" % (callback.id, ", ".join(
                      argument.arg for argument in function.args.args)),
                  expected="def %s(ok, value):" % callback.id)
    else:
        callback = None

    values = []
    for argument, kind, default in found.params:
        value = given.get(argument)
        if value is None:
            if default is rules.REQUIRED:
                _fail(node, "%s needs %s" % (label, argument),
                      received=_text(node), expected=shown)
            value = ast.Constant(value=_default_text(default))
        elif kind == "function":
            value = _function_named(node, label, value, functions,
                                    _WATCHED[0] if namespace == "network" else _TIMED[0])
        else:
            if isinstance(value, ast.Name) and value.id in _TOP[0] \
                    and any(other == "function" for _name, other, _default in found.params):
                _fail(node, **rules.timer_swapped(label, value.id))
            _check_literal(node, label, argument, kind, value)
        values.append(value)
    return values, callback


def _function_named(node, label, value, functions, called_by_name):
    """``run=tick`` crosses as the text ``"tick"``.

    Everything an app passes is text by the time it reaches the phone, and a
    function is no exception: the screen is asked for it by name when the
    time comes (see :func:`activity_members`). So it has to be a function
    with a name, written at the top level of the module, that takes nothing.
    """
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) \
            and value.func.id in functions:
        _fail(node, **rules.timer_called(label, value.func.id))
    function = _TOP[0].get(value.id) if isinstance(value, ast.Name) else None
    if function is None or function.decorator_list:
        _fail(node, **rules.timer_not_a_function(label, _text(node)))
    arguments = function.args
    taken = [argument.arg for argument in
             arguments.posonlyargs + arguments.args + arguments.kwonlyargs]
    taken += ["*" + extra.arg for extra in (arguments.vararg,) if extra is not None]
    taken += ["**" + extra.arg for extra in (arguments.kwarg,) if extra is not None]
    if taken:
        _fail(function, **rules.timer_takes_nothing(label, value.id, taken))
    called_by_name.setdefault(value.id, node)
    return ast.copy_location(ast.Constant(value=value.id), value)


def _default_text(default):
    """A default as the text that crosses to the phone."""
    if default is True:
        return "true"
    if default is False:
        return "false"
    return str(default)


def _check_literal(node, label, argument, kind, value):
    """A constant of the wrong kind is a mistake the build can see. Anything
    computed is passed on: it is text by the time it gets there."""
    if not isinstance(value, ast.Constant):
        return
    written = value.value
    if kind in ("number", "whole"):
        wrong = isinstance(written, bool) or written is None or (
            isinstance(written, str)
            and not re.fullmatch(native_rules.NUMBER, rules.trim(written)))
        if wrong:
            _fail(node, "%s: %s= is a number, got %r" % (label, argument, written),
                  received=_text(node))
    elif kind == "bool":
        if not isinstance(written, bool):
            _fail(node, "%s: %s= is True or False, got %r" % (label, argument, written),
                  received=_text(node))
    elif written is None:
        _fail(node, "%s: %s= is text, got None" % (label, argument),
              received=_text(node), suggestions=['Leave it out, or pass "".'])


def _literal(node, label, argument, value):
    """A declaration is read by the build, so it is written out."""
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    _fail(node, "%s: %s= has to be text written in the source" % (label, argument),
          cause="This line changes what is built -- the app's manifest -- and "
                "the build reads your module, it never runs it.",
          received=_text(node))


# --- the rewrite ------------------------------------------------------------

# What belongs to the screen on show when the line runs, and so cannot be a
# line at the top of the file, which runs before there is one.
_NEEDS_A_SCREEN = (("timer", "after"), ("timer", "every"), ("network", "on_change"),
                   ("display", "keep_on"), ("display", "brightness"),
                   ("display", "immersive"), ("display", "orientation"),
                   ("app_lock", "after"), ("app_lock", "now"), ("app_lock", "off"),
                   ("app_lock", "locked"))

# What each family says to a call at the top of the file.
_AT_THE_TOP = {"display": rules.display_at_the_top, "app_lock": rules.app_lock_at_the_top}


class _Rewriter(ast.NodeTransformer):

    def __init__(self, functions, truthy, called, bound):
        self.functions = functions
        self.truthy = truthy        # ids of nodes whose truth is what is read
        self.called = called        # ids of Attribute nodes that are being called
        self.bound = bound          # names the module made its own
        self.depth = 0              # how many functions deep the visit is

    def _in_a_function(self, node):
        self.depth += 1
        try:
            return self.generic_visit(node)
        finally:
            self.depth -= 1

    visit_FunctionDef = visit_AsyncFunctionDef = visit_Lambda = _in_a_function

    def visit_Call(self, node):
        ours = _is_ours(node.func, self.bound)
        in_condition = id(node) in self.truthy
        self.generic_visit(node)
        if ours is None:
            return node
        namespace, name = ours
        found = rules.verb(namespace, name)
        if found is None:
            return node             # files.download() and friends: not ours
        if (namespace, name) in _NEEDS_A_SCREEN and not self.depth:
            at_the_top = _AT_THE_TOP.get(namespace, rules.timer_at_the_top)
            _fail(node, **at_the_top(rules.label(namespace, name)))
        values, callback = _arguments(node, namespace, name, found, self.functions)
        _check_call(node, namespace, name, found, values)
        _USED[0].setdefault((namespace, name), node)
        call = ast.Call(func=ast.Name(id=_alias(namespace, name), ctx=ast.Load()),
                        args=values, keywords=[])
        if callback is not None:
            call.keywords.append(ast.keyword(arg="on_result", value=callback))
        replacement = call
        if found.mode == rules.FLAG and in_condition:
            # A yes/no crosses as the text "True" or "False", and text that is
            # not empty is true: the question has to be asked of the word.
            replacement = ast.Compare(left=call, ops=[ast.Eq()],
                                      comparators=[ast.Constant(value="True")])
        ast.copy_location(replacement, node)
        ast.fix_missing_locations(replacement)
        return replacement

    def visit_Attribute(self, node):
        self.generic_visit(node)
        ours = _is_ours(node, self.bound)
        if ours is None or id(node) in self.called or not isinstance(node.ctx, ast.Load):
            return node
        namespace, name = ours
        found = rules.verb(namespace, name)
        if found is None:
            return node
        label = rules.label(namespace, name)
        if found.mode in (rules.VALUE, rules.FLAG):
            _fail(node, "%s is missing its brackets" % label,
                  cause="Without them this is the function itself, not what it answers.",
                  received="%s.%s" % (namespace, name),
                  suggestions=["Write %s" % label])
        if found.required or found.mode in (rules.DECLARE,):
            _fail(node, "%s is handed over without being called" % label,
                  cause="It needs %s, so there is nothing to call it with here."
                        % " and ".join(found.required or ("its arguments",)),
                  received="%s.%s" % (namespace, name),
                  suggestions=["command=lambda: %s" % rules.signature(namespace, name)])
        # command=haptics.tap -- a function handed over. The generator calls
        # functions by name and lambdas by their body, so it becomes one.
        _USED[0].setdefault((namespace, name), node)
        call = ast.Call(func=ast.Name(id=_alias(namespace, name), ctx=ast.Load()),
                        args=[ast.Constant(value=_default_text(default))
                              for _argument, _kind, default in found.params],
                        keywords=[])
        replacement = ast.Lambda(
            args=ast.arguments(posonlyargs=[], args=[], vararg=None, kwonlyargs=[],
                               kw_defaults=[], kwarg=None, defaults=[]),
            body=call)
        ast.copy_location(replacement, node)
        ast.fix_missing_locations(replacement)
        return replacement


def _written(value):
    """The text of an argument written out in the source, else ``None``."""
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def _written_value(value):
    """An argument written out in the source -- text, or a number with its
    sign -- as the text that crosses to the phone, else ``None``."""
    if isinstance(value, ast.Constant) and isinstance(value.value, (str, int, float)):
        return str(value.value)
    if isinstance(value, ast.UnaryOp) and isinstance(value.op, (ast.USub, ast.UAdd)) \
            and isinstance(value.operand, ast.Constant) \
            and isinstance(value.operand.value, (int, float)) \
            and not isinstance(value.operand.value, bool):
        return ("-" if isinstance(value.op, ast.USub) else "") + str(value.operand.value)
    return None


def _check_call(node, namespace, name, found, values):
    """What the build can see is wrong in one call, said before it is built."""
    named = dict(zip(found.names, values))
    label = rules.label(namespace, name)
    if namespace == "health" and name in ("allowed", "read", "ask"):
        argument = "kinds" if name == "ask" else "kind"
        text = _written(named[argument])
        if text is None:
            _fail(node, "%s: %s= has to be written in the source" % (label, argument),
                  cause="Each kind of record is a permission in the app's manifest, "
                        "and the build reads your module, it never runs it.",
                  received=_text(node),
                  suggestions=['health.read("steps", on_result=got)',
                               "One function for each kind, rather than one that "
                               "takes the kind."])
        kinds, wrong = rules.health_kinds(text)
        if kinds is None:
            _fail(node, "%s: there is no kind %r" % (label, wrong), received=_text(node),
                  suggestions=["One of: %s." % ", ".join(rules.HEALTH_KINDS)])
        if not kinds or (name != "ask" and len(kinds) != 1):
            _fail(node, "%s takes %s" % (label, "one kind" if name != "ask"
                                         else "at least one kind"),
                  received=_text(node),
                  suggestions=['health.ask("steps, heart_rate", on_result=asked)'
                               if name == "ask" else 'health.read("steps", on_result=got)'])
        for kind in kinds:
            if kind not in _HEALTH[0]:
                _HEALTH[0].append(kind)
    elif namespace == "ads" and name in ("banner", "interstitial", "rewarded"):
        unit = _written(named["unit"])
        if unit is not None and not rules.ad_unit(unit, name):
            _fail(node, "%s: %r is not an ad unit" % (label, unit), received=_text(node),
                  cause="An ad unit is the id AdMob gives one place an ad appears.",
                  suggestions=['"test" shows Google\'s sample ad while you build the app.',
                               'Your own looks like "ca-app-pub-1234567890123456/1234567890".'])
        position = _written(named.get("position")) if "position" in named else None
        if position is not None and position not in rules.AD_POSITIONS:
            _fail(node, "%s: position= is %s, got %r"
                  % (label, " or ".join('"%s"' % known for known in rules.AD_POSITIONS),
                     position), received=_text(node))
    elif namespace == "timer" and name in ("after", "every"):
        seconds = named["seconds"]
        below = isinstance(seconds, ast.UnaryOp) and isinstance(seconds.op, ast.USub) \
            and isinstance(seconds.operand, ast.Constant) \
            and isinstance(seconds.operand.value, (int, float)) and seconds.operand.value > 0
        if below:
            _fail(node, "%s: seconds= is zero or more, got %s" % (label, _text(seconds)),
                  received=_text(node))
    elif namespace == "display" and name == "orientation":
        kind = _written_value(named["kind"])
        if kind is not None and not rules.display_orientation(kind):
            _fail(node, **rules.display_wrong_orientation(label, kind))
    elif namespace == "display" and name == "brightness":
        level = _written_value(named["level"])
        if level is not None and rules.display_brightness(level) == rules.BRIGHTNESS_INVALID:
            _fail(node, **rules.display_wrong_brightness(label, level))
    elif namespace == "app_lock" and name == "after":
        minutes = _written_value(named["minutes"])
        if minutes is not None and rules.app_lock_minutes(minutes) == rules.APP_LOCK_INVALID:
            _fail(node, **rules.app_lock_wrong_minutes(label, minutes))
    elif namespace == "updates" and name == "start":
        mode = _written(named["mode"])
        if mode is not None and mode not in rules.UPDATE_MODES:
            _fail(node, "%s: mode= is %s, got %r"
                  % (label, " or ".join('"%s"' % known for known in rules.UPDATE_MODES),
                     mode), received=_text(node),
                  suggestions=['"flexible" downloads while the person carries on.',
                               '"immediate" takes the screen until it is installed.'])


def _declare(node, ours, label, named):
    """One of the five's declarations: read, checked, written down."""
    namespace = ours[0]
    if ours in _DECLARED[0]:
        _fail(node, "%s is written once" % label,
              cause="It says what the app is built with, and an app is built once.",
              received=_text(node))
    said = {}
    for argument, kind, _default in rules.verb(*ours).params:
        value = named[argument]
        written = value.value if isinstance(value, ast.Constant) else None
        if kind == "bool" and written in ("true", "false"):
            written = written == "true"         # a default, as the rewrite fills it in
        right = isinstance(written, bool) if kind == "bool" else (
            isinstance(written, str))
        if not right:
            _fail(node, "%s: %s= has to be %s written in the source"
                  % (label, argument, "True or False" if kind == "bool" else "text"),
                  cause="This line changes what is built, and the build reads your "
                        "module, it never runs it.",
                  received=_text(node))
        said[argument] = written
    problem = ""
    if namespace == "home_widget" and not rules.trim(said["title"]):
        problem = "a widget has at least a title"
    elif namespace == "quick_tile" and not rules.trim(said["label"]):
        problem = "a tile has a name"
    elif namespace == "ads" and not rules.ad_app_id(said["app_id"]):
        problem = ('app_id= is the id AdMob gives the app -- '
                   '"ca-app-pub-1234567890123456~1234567890" -- or "test"')
    elif namespace == "health" and not rules.web_address(said["url"]):
        problem = "url= is the address of the privacy policy, starting with https://"
    if problem:
        _fail(node, "%s: %s" % (label, problem), received=_text(node),
              suggestions=[rules.DECLARED_BY[namespace][2]])
    _DECLARED[0][ours] = said


def _check_declared():
    """A call of a family that was never declared has nothing behind it."""
    for namespace, (verb, why, example) in rules.DECLARED_BY.items():
        if (namespace, verb) in _DECLARED[0]:
            continue
        for (used, name), node in list(_USED[0].items()):
            if used == namespace:
                _fail(node, "%s: %s" % (rules.label(namespace, name), why),
                      cause="What the app has outside its own screens is written "
                            "into it when it is built, from one line at the top of "
                            "the file.",
                      received=_text(node) if isinstance(node, ast.Call) else
                      "%s.%s" % (namespace, name),
                      suggestions=["Add this at the top of the file: " + example])


def _truth_positions(tree):
    """ids of the expressions that are read for their truth."""
    found = set()

    def mark(node):
        found.add(id(node))

    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While, ast.IfExp, ast.Assert)):
            mark(node.test)
        elif isinstance(node, ast.BoolOp):
            for value in node.values:
                mark(value)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            mark(node.operand)
    return found


def _declarations(tree, bound):
    """Take ``incoming.links(...)`` and ``incoming.shares(...)`` out of the
    module and write down what they said."""
    top = {}
    for statement in tree.body:
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            ours = _is_ours(statement.value.func, bound)
            if ours:
                found = rules.verb(*ours)
                if found is not None and found.mode == rules.DECLARE:
                    top[id(statement.value)] = statement

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        ours = _is_ours(node.func, bound)
        if not ours:
            continue
        found = rules.verb(*ours)
        if found is None or found.mode != rules.DECLARE:
            continue
        label = rules.label(*ours)
        if id(node) not in top:
            _fail(node, "%s is written once, on a line of its own at the top of the file" % label,
                  cause="It says what the app is built to accept from outside. "
                        "That goes into the manifest when the app is built; "
                        "nothing happens when the line is reached.",
                  received=_text(node),
                  suggestions=["Move it out of the function, next to the screens."])
        values, _callback = _arguments(node, ours[0], ours[1], found, {})
        named = dict(zip(found.names, values))
        if ours[0] != "incoming":
            _declare(node, ours, label, named)
            _USED[0].setdefault(ours, node)
            continue
        if ours[1] == "links":
            scheme = _literal(node, label, "scheme", named["scheme"])
            host = _literal(node, label, "host", named["host"])
            _literal(node, label, "preview", named["preview"])
            problem = rules.link_scheme(scheme, host)
            if problem:
                _fail(node, "%s: %s" % (label, problem), received=_text(node),
                      suggestions=['incoming.links("notes")   # notes://anything',
                                   'incoming.links("https", "example.com")'])
            if (scheme, host) not in _LINKS[0]:
                _LINKS[0].append((scheme, host))
        else:
            kind = _literal(node, label, "kind", named["kind"])
            _literal(node, label, "preview", named["preview"])
            if kind not in rules.SHARE_KINDS:
                _fail(node, "%s: there is no kind %r" % (label, kind),
                      received=_text(node),
                      suggestions=["One of: %s." % ", ".join(
                          '"%s"' % known for known in rules.SHARE_KINDS)])
            if kind not in _SHARES[0]:
                _SHARES[0].append(kind)
        _USED[0].setdefault(ours, node)
    if top:
        gone = set(id(statement) for statement in top.values())
        tree.body = [statement for statement in tree.body if id(statement) not in gone]


def _check_incoming(tree):
    """Asking what came in, in an app nothing can come into, is always ""."""
    asks = {
        "link": (_LINKS[0], 'incoming.links("notes")',
                 "no address opens this app"),
        "text": (_SHARES[0], 'incoming.shares("text")',
                 "nothing can be shared into this app"),
        "file": ([kind for kind in _SHARES[0] if kind != "text"],
                 'incoming.shares("image")   # or "file"',
                 "no file can be shared into this app"),
    }
    for (namespace, name), node in list(_USED[0].items()):
        if namespace != "incoming" or name not in asks:
            continue
        declared, example, why = asks[name]
        if not declared:
            _fail(node, "incoming.%s() would always answer \"\": %s" % (name, why),
                  cause="What an app accepts from outside is written in its "
                        "manifest, and this app declares nothing of the kind.",
                  received="incoming.%s()" % name,
                  suggestions=["Add this at the top of the file: " + example])


def rewrite(tree):
    """Turn every call of the table into a call to a native block, and declare
    those blocks at the top of the module. A module with none of them comes
    back untouched."""
    reset()
    if not any(_is_ours(node) is not None for node in ast.walk(tree)):
        return tree

    bound = _bound_names(tree)
    for node in ast.walk(tree):
        ours = _is_ours(node, bound)
        # files is older than this table and has verbs of its own.
        if ours is not None and ours[0] != "files" and rules.verb(*ours) is None:
            _unknown_verb(node, *ours)

    _declarations(tree, bound)
    _TOP[0] = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_ours(node.func, bound) is not None:
            called.add(id(node.func))

    tree = _Rewriter(_functions(tree), _truth_positions(tree), called, bound).visit(tree)
    _check_incoming(tree)
    _check_declared()
    if not uses_kit():
        return tree

    at = _insert_at(tree)
    tree.body[at:at] = _declared_blocks()
    ast.fix_missing_locations(tree)
    return tree


def _insert_at(tree):
    """After the docstring and the imports that open the module."""
    index = 0
    for position, node in enumerate(tree.body):
        docstring = (position == 0 and isinstance(node, ast.Expr)
                     and isinstance(node.value, ast.Constant)
                     and isinstance(node.value.value, str))
        if not docstring and not isinstance(node, (ast.Import, ast.ImportFrom)):
            break
        index = position + 1
    return index


def _used_in_order():
    """(namespace, verb) of every call in use, in the table's order."""
    out = []
    for namespace in rules.SPEC:
        for name in rules.verbs(namespace):
            if (namespace, name) in _USED[0]:
                out.append((namespace, name))
    return out


def block_code(namespace, name):
    """The body of the native block behind one call."""
    found = rules.verb(namespace, name)
    klass = found.home or rules.SPEC[namespace]["class"]
    handed = ["this"] + ['"%s"' % constant for constant in found.fixed] + list(found.names)
    if found.mode == rules.LATER:
        # The answer can arrive after the screen that asked has gone; a
        # callback into a screen that no longer exists is dropped.
        handed.append("new ApkpyKit.Done() {\n"
                      "    @Override public void run(boolean ok, String value) {\n"
                      "        if (!isDestroyed()) done.run(ok, value);\n"
                      "    }\n"
                      "}")
        return "%s.%s(%s);" % (klass, found.java, ", ".join(handed))
    return "return %s.%s(%s);" % (klass, found.java, ", ".join(handed))


def _native_call(verb, arguments, keywords, at):
    call = ast.Call(
        func=ast.Attribute(value=ast.Name(id="native", ctx=ast.Load()),
                           attr=verb, ctx=ast.Load()),
        args=[ast.Constant(value=value) for value in arguments],
        keywords=[ast.keyword(arg=key, value=value) for key, value in keywords])
    return ast.copy_location(call, at)


def _homes():
    """The classes the calls in use live in, in a steady order."""
    homes = []
    for namespace, name in _used_in_order():
        klass = rules.verb(namespace, name).home or rules.SPEC[namespace]["class"]
        if klass not in homes:
            homes.append(klass)
    return homes


_LAUNCHER_PART = re.compile(
    r"^    // apkpy:launcher --[^\n]*\n.*?^    // apkpy:launcher-end\n",
    re.S | re.M)
_LAUNCHER_MARK = re.compile(r"^    // apkpy:launcher(?: --[^\n]*|-end)\n", re.M)


def _without_launcher(source):
    """A class's Java without the methods only the launcher's calls use."""
    return _LAUNCHER_PART.sub("", source.replace("\r\n", "\n"))


def _class_text(class_name):
    """A class's Java as it is shipped, before the marks are filled in."""
    folder = _HERE / "libs" if class_name in _WITH_LIBRARY else _HERE
    try:
        return (folder / (class_name + ".java")).read_text(encoding="utf-8")
    except OSError:
        return ""


def _needs():
    """Every requirement of the calls in use, each once, in a steady order."""
    out = {"permissions": [], "features": [], "queries": [], "application": [],
           "classes": [], "gradle": [], "beside": []}
    for namespace, name in _used_in_order():
        for key in rules.verb(namespace, name).needs:
            for kind, values in NEEDS[key].items():
                for value in values:
                    if value not in out[kind]:
                        out[kind].append(value)
    # A class carries the code of every verb it is home to, less the methods
    # marked as the launcher's (listen(), recorder start(), health ask()),
    # which java_source leaves out when no call asked for the launcher: an
    # app that only says() has no screen that waits. What is left must not
    # name the launcher -- if it does, the launcher comes with it, or javac
    # stops on "package ApkpyKitActivity does not exist" (it did, for
    # speech.say() alone).
    if "ApkpyKitActivity" not in out["classes"] and any(
            "ApkpyKitActivity" in _without_launcher(_class_text(klass))
            for klass in _homes() + out["classes"]):
        for kind, values in NEEDS["launcher"].items():
            for value in values:
                if value not in out[kind]:
                    out[kind].append(value)
    incoming = incoming_xml()
    if incoming:
        out["application"].append(incoming)
    for element in (widget_xml(), tile_xml(), ads_xml(), health_xml()):
        if element:
            out["application"].append(element)
    # A health permission has dots in its name, and is asked for by the
    # health classes themselves: it is written as it stands.
    for kind in _HEALTH[0]:
        out["beside"].append(
            '<uses-permission android:name="android.permission.health.%s" />'
            % rules.HEALTH_KINDS[kind][0])
    return out


def _attribute(text):
    """Text as the value of an XML attribute in the manifest."""
    from xml.sax.saxutils import escape
    text = escape(str(text), {'"': "&quot;", "\n": " "})
    # A value that opens with @ or ? is read as a reference to a resource.
    return ("\\" + text) if text[:1] in ("@", "?") else text


def _resource_text(text):
    """Text as ``android:text`` in a layout: what aapt unescapes, escaped."""
    from xml.sax.saxutils import escape
    text = str(text).replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
    text = text.replace("\n", "\\n")
    if text[:1] in ("@", "?"):
        text = "\\" + text
    return escape(text, {'"': "&quot;"})


def widget_xml():
    """The receiver the launcher talks to, or ``""`` for an app with no widget."""
    said = declared("home_widget")
    if not said:
        return ""
    label = ' android:label="%s"' % _attribute(said["name"]) if rules.trim(said["name"]) else ""
    return "\n".join([
        '<receiver android:name=".ApkpyWidgetProvider" android:exported="true"%s>' % label,
        '    <intent-filter>',
        '        <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />',
        '    </intent-filter>',
        '    <meta-data android:name="android.appwidget.provider" '
        'android:resource="@xml/apkpy_widget_info" />',
        '</receiver>'])


def tile_xml():
    """The service quick settings binds to, or ``""`` for an app with no tile."""
    said = declared("quick_tile")
    if not said:
        return ""
    return "\n".join([
        '<service android:name=".ApkpyTileService" android:exported="true" '
        'android:label="%s" android:icon="@drawable/ic_apkpy_tile" '
        'android:permission="android.permission.BIND_QUICK_SETTINGS_TILE">'
        % _attribute(said["label"]),
        '    <intent-filter>',
        '        <action android:name="android.service.quicksettings.action.QS_TILE" />',
        '    </intent-filter>',
        '    <meta-data android:name="android.service.quicksettings.ACTIVE_TILE" '
        'android:value="true" />',
        '</service>'])


def ads_xml():
    """Which AdMob app this is; the library stops the app at start without it."""
    said = declared("ads")
    if not said:
        return ""
    return ('<meta-data android:name="com.google.android.gms.ads.APPLICATION_ID" '
            'android:value="%s" />' % rules.ad_app_id(said["app_id"]))


def health_xml():
    """The screen Health Connect opens for "why does this app want my data"."""
    if not declared("health"):
        return ""
    return "\n".join([
        '<activity android:name=".ApkpyHealthPolicyActivity" android:exported="true" '
        'android:theme="@android:style/Theme.Translucent.NoTitleBar" '
        'android:permission="android.permission.START_VIEW_PERMISSION_USAGE">',
        '    <intent-filter>',
        '        <action android:name="android.intent.action.VIEW_PERMISSION_USAGE" />',
        '        <category android:name="android.intent.category.HEALTH_PERMISSIONS" />',
        '    </intent-filter>',
        '</activity>'])


# --- what a widget and a tile are made of ------------------------------------

_WIDGET_DAY = {"surface": "#FFFFFF", "text": "#1B1B1F", "text_secondary": "#5F6368",
               "primary": "#3D5AFE"}
_WIDGET_NIGHT = {"surface": "#1F1F23", "text": "#F2F2F2", "text_secondary": "#B4B7BD",
                 "primary": "#AAB6FE"}


def _widget_colours():
    """(day, night): the widget's colours, from the app's Theme when it has
    one. The home screen follows the phone, not the app, so both are written."""
    from ... import compiler
    from .... import theme as theme_rules
    day, night = dict(_WIDGET_DAY), dict(_WIDGET_NIGHT)
    declared_theme = compiler._APP_THEME[0]
    if declared_theme is not None:
        own, other = dict(declared_theme.tokens), dict(declared_theme.counterpart().tokens)
        if own.get("mode") == "dark":
            own, other = other, own
        for table, tokens in ((day, own), (night, other)):
            for key in table:
                if tokens.get(key):
                    table[key] = str(tokens[key])
    for table, strength in ((day, 0.12), (night, 0.20)):
        table["tonal"] = theme_rules._mix_color(table["surface"], table["primary"], strength)
    return day, night


def _colour_table(colours):
    lines = ['<?xml version="1.0" encoding="utf-8"?>', '<resources>']
    for name in ("surface", "text", "text_secondary", "primary", "tonal"):
        lines.append('    <color name="apkpy_widget_%s">%s</color>' % (name, colours[name]))
    lines.append('</resources>')
    return "\n".join(lines) + "\n"


def _vector(icon, colour, size=24):
    from ... import compiler
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
            '    android:width="%ddp"\n    android:height="%ddp"\n'
            '    android:viewportWidth="24"\n    android:viewportHeight="24">\n'
            '    <path android:fillColor="%s" android:pathData="%s"/>\n'
            '</vector>\n' % (size, size, colour, compiler._icon_path_data(icon)))


def _widget_text(name, size, colour, text, more=()):
    lines = [
        '<TextView',
        '    android:id="@+id/apkpy_widget_%s"' % name,
        '    android:layout_width="match_parent"',
        '    android:layout_height="wrap_content"',
        '    android:maxLines="1"',
        '    android:ellipsize="end"',
        '    android:includeFontPadding="false"',
        '    android:textSize="%ssp"' % size,
        '    android:textColor="@color/apkpy_widget_%s"' % colour,
    ]
    lines += list(more)
    lines.append('    android:text="%s" />' % _resource_text(text))
    return lines


def _widget_badge(size, pad, gap):
    return [
        '<ImageView',
        '    android:layout_width="%ddp"' % size,
        '    android:layout_height="%ddp"' % size,
        '    android:layout_marginEnd="%ddp"' % gap,
        '    android:padding="%ddp"' % pad,
        '    android:background="@drawable/apkpy_widget_badge"',
        '    android:src="@drawable/ic_apkpy_widget"',
        '    android:importantForAccessibility="no" />',
    ]


def _nest(lines, depth=1):
    return [("    " * depth) + line for line in lines]


def _widget_layout(said, card=False):
    """The widget as a layout the launcher can draw: only the few views a
    widget may be made of, and no code. ``card`` is the taller drawing."""
    icon = bool(rules.trim(said["icon"]))
    caption_shown = "visible" if rules.trim(said["caption"]) else "gone"
    root = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"',
        # The name Android 12 looks for to round the corners itself, and the
        # one the tap is hung on.
        '    android:id="@android:id/background"',
        '    android:layout_width="match_parent"',
        '    android:layout_height="match_parent"',
        '    android:background="@drawable/apkpy_widget_bg"',
    ]
    if card:
        body = root + [
            '    android:orientation="vertical"',
            '    android:padding="16dp">',
            '    <LinearLayout',
            '        android:layout_width="match_parent"',
            '        android:layout_height="wrap_content"',
            '        android:orientation="horizontal"',
            '        android:gravity="center_vertical">',
        ]
        if icon:
            body += _nest(_widget_badge(36, 8, 10), 2)
        body += _nest(_widget_text("title", 13, "text_secondary", said["title"], [
            '    android:fontFamily="sans-serif-medium"']), 2)
        body += [
            '    </LinearLayout>',
            '    <LinearLayout',
            '        android:layout_width="match_parent"',
            '        android:layout_height="0dp"',
            '        android:layout_weight="1"',
            '        android:orientation="vertical"',
            '        android:gravity="bottom">',
        ]
        body += _nest(_widget_text("text", 32, "text", said["text"], [
            '    android:textStyle="bold"']), 2)
        body += _nest(_widget_text("caption", 13, "text_secondary", said["caption"], [
            '    android:layout_marginTop="2dp"',
            '    android:visibility="%s"' % caption_shown]), 2)
        body += ['    </LinearLayout>', '</LinearLayout>']
        return "\n".join(body) + "\n"

    body = root + [
        '    android:orientation="horizontal"',
        '    android:gravity="center_vertical"',
        '    android:paddingStart="16dp"',
        '    android:paddingEnd="16dp">',
    ]
    if icon:
        body += _nest(_widget_badge(40, 9, 12))
    body += [
        '    <LinearLayout',
        '        android:layout_width="0dp"',
        '        android:layout_height="wrap_content"',
        '        android:layout_weight="1"',
        '        android:orientation="vertical">',
    ]
    body += _nest(_widget_text("title", 12, "text_secondary", said["title"], [
        '    android:fontFamily="sans-serif-medium"']), 2)
    # The number and what it counts share a line, on one baseline: a widget
    # one cell high has room for two lines and no more.
    number = _widget_text("text", 20, "text", said["text"], [
        '    android:textStyle="bold"'])
    number[2] = '    android:layout_width="wrap_content"'
    caption = _widget_text("caption", 13, "text_secondary", said["caption"], [
        '    android:layout_marginStart="8dp"',
        '    android:visibility="%s"' % caption_shown])
    caption[2] = '    android:layout_width="0dp"'
    caption.insert(4, '    android:layout_weight="1"')
    body += [
        '        <LinearLayout',
        '            android:layout_width="match_parent"',
        '            android:layout_height="wrap_content"',
        '            android:layout_marginTop="2dp"',
        '            android:orientation="horizontal">',
    ]
    body += _nest(number, 3) + _nest(caption, 3)
    body += ['        </LinearLayout>', '    </LinearLayout>', '</LinearLayout>']
    return "\n".join(body) + "\n"


_WIDGET_INFO = """<?xml version="1.0" encoding="utf-8"?>
<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android"
    android:minWidth="180dp"
    android:minHeight="56dp"
    android:minResizeWidth="110dp"
    android:minResizeHeight="56dp"
    android:targetCellWidth="3"
    android:targetCellHeight="1"
    android:resizeMode="horizontal|vertical"
    android:updatePeriodMillis="0"
    android:widgetCategory="home_screen"
    android:initialLayout="@layout/apkpy_widget"
    android:previewLayout="@layout/apkpy_widget" />
"""

_SHAPE = """<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="%s">
    <solid android:color="%s" />%s
</shape>
"""


def resource_files():
    """``res/...`` -> text, for the widget and the tile the app declared."""
    files = {}
    widget = declared("home_widget")
    if widget:
        day, night = _widget_colours()
        files["res/values/apkpy_widget.xml"] = _colour_table(day)
        files["res/values-night/apkpy_widget.xml"] = _colour_table(night)
        files["res/layout/apkpy_widget.xml"] = _widget_layout(widget)
        files["res/layout/apkpy_widget_card.xml"] = _widget_layout(widget, card=True)
        files["res/xml/apkpy_widget_info.xml"] = _WIDGET_INFO
        # Android 12 gave every widget the launcher's own corner; before it,
        # a corner of our own that is close to it.
        files["res/drawable/apkpy_widget_bg.xml"] = _SHAPE % (
            "rectangle", "@color/apkpy_widget_surface",
            '\n    <corners android:radius="22dp" />')
        files["res/drawable-v31/apkpy_widget_bg.xml"] = _SHAPE % (
            "rectangle", "@color/apkpy_widget_surface",
            '\n    <corners android:radius="@android:dimen/system_app_widget_background_radius" />')
        files["res/drawable/apkpy_widget_badge.xml"] = _SHAPE % (
            "oval", "@color/apkpy_widget_tonal", "")
        if rules.trim(widget["icon"]):
            files["res/drawable/ic_apkpy_widget.xml"] = _vector(
                rules.trim(widget["icon"]), "@color/apkpy_widget_primary")
    tile = declared("quick_tile")
    if tile:
        # Quick settings tints a tile's icon itself; white is what it expects.
        files["res/drawable/ic_apkpy_tile.xml"] = _vector(
            rules.trim(tile["icon"]) or "bolt", "#FFFFFFFF")
    if files:
        # A release build drops the resources nothing refers to, and these
        # are found by name while the app runs -- which it cannot follow.
        kept = sorted("@%s/%s" % (os.path.basename(os.path.dirname(name)).split("-")[0],
                                  os.path.basename(name)[:-4])
                      for name in files
                      if name.startswith(("res/layout/", "res/drawable/")))
        files["res/raw/apkpy_kit_keep.xml"] = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<resources xmlns:tools="http://schemas.android.com/tools"\n'
            '    tools:keep="%s" />\n' % ",".join(kept))
    return files


def queries_xml(actions):
    """One ``<queries>`` naming every kind of app these calls look for."""
    lines = ["<queries>"]
    for action in actions:
        lines.append('    <intent><action android:name="%s" /></intent>' % action)
    lines.append("</queries>")
    return "\n".join(lines)


def incoming_xml():
    """The Activity a link or a share lands on, with one filter for each
    address and each kind the app declared. ``""`` when it declared none."""
    if not _LINKS[0] and not _SHARES[0]:
        return ""
    lines = ['<activity android:name=".ApkpyIncomingActivity" android:exported="true" '
             'android:noHistory="true" android:excludeFromRecents="true" '
             'android:theme="@android:style/Theme.Translucent.NoTitleBar">']
    for scheme, host in _LINKS[0]:
        web = scheme in ("http", "https")
        # autoVerify is what lets an https link open the app without asking;
        # Android only honours it for a site that names the app back.
        lines.append('    <intent-filter%s>' % (' android:autoVerify="true"' if web else ""))
        lines.append('        <action android:name="android.intent.action.VIEW" />')
        lines.append('        <category android:name="android.intent.category.DEFAULT" />')
        lines.append('        <category android:name="android.intent.category.BROWSABLE" />')
        lines.append('        <data android:scheme="%s"%s />' % (
            scheme, ' android:host="%s"' % host if host else ""))
        lines.append('    </intent-filter>')
    for kind in _SHARES[0]:
        lines.append('    <intent-filter>')
        lines.append('        <action android:name="android.intent.action.SEND" />')
        lines.append('        <category android:name="android.intent.category.DEFAULT" />')
        lines.append('        <data android:mimeType="%s" />' % rules.SHARE_KINDS[kind])
        lines.append('    </intent-filter>')
    lines.append('</activity>')
    return "\n".join(lines)


def _declared_blocks():
    """The statements put at the top of the module: one native block for each
    call in use, and the manifest lines they need."""
    out = []
    answers_nothing = ast.Lambda(
        args=ast.arguments(posonlyargs=[], args=[], vararg=ast.arg(arg="given"),
                           kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
        body=ast.Constant(value=None))
    for namespace, name in _used_in_order():
        found = rules.verb(namespace, name)
        if found.mode == rules.DECLARE:
            continue
        at = _USED[0][(namespace, name)]
        call = _native_call(
            "java_async" if found.mode == rules.LATER else "java",
            [_java_name(namespace, name)],
            [("code", ast.Constant(value=block_code(namespace, name))),
             ("args", ast.Tuple(elts=[ast.Constant(value=argument)
                                      for argument in found.names], ctx=ast.Load())),
             ("preview", answers_nothing)], at)
        out.append(ast.copy_location(
            ast.Assign(targets=[ast.Name(id=_alias(namespace, name), ctx=ast.Store())],
                       value=call), at))

    needs = _needs()
    first = next(iter(_USED[0].values()))
    for permission in needs["permissions"]:
        out.append(ast.copy_location(ast.Expr(value=_native_call(
            "manifest", [], [("permission", ast.Constant(value=permission))], first)), first))
    for feature in needs["features"]:
        out.append(ast.copy_location(ast.Expr(value=_native_call(
            "manifest", [], [("feature", ast.Constant(value=feature))], first)), first))
    for element in ([queries_xml(needs["queries"])] if needs["queries"] else []) \
            + needs["beside"] + needs["application"]:
        out.append(ast.copy_location(ast.Expr(value=_native_call(
            "manifest", [], [("xml", ast.Constant(value=element))], first)), first))
    for line in needs["gradle"]:
        out.append(ast.copy_location(ast.Expr(value=_native_call("gradle", [line], [], first)),
                                     first))
    for statement in out:
        ast.fix_missing_locations(statement)
    return out


# --- which way up a screen is -------------------------------------------------

# What Android calls each of them in the manifest. "landscape" is either way
# round, as display.orientation("landscape") is.
_MANIFEST_ORIENTATION = {"portrait": "portrait", "landscape": "sensorLandscape"}


def orientation_of(call, where):
    """``orientation=`` of a ``Screen(...)`` or of ``run(...)``: one of
    ``kit_rules.ORIENTATIONS``, or ``None`` when the call says nothing."""
    for keyword in call.keywords:
        if keyword.arg != "orientation":
            continue
        value = keyword.value
        if isinstance(value, ast.Constant) and value.value is None:
            return None
        label = "%s(orientation=)" % where
        written = _written(value)
        if written is None:
            _fail(call, "%s has to be text written in the source" % label,
                  cause="It goes into the app's manifest when the app is built, and "
                        "the build reads your module, it never runs it.",
                  received=_text(value),
                  suggestions=['%s(..., orientation="portrait")' % where,
                               'To turn a screen while the app runs: '
                               'display.orientation("landscape")'],
                  docs=rules.DOCS_OF["display"])
        kind = rules.display_orientation(written)
        if not kind:
            _fail(call, docs=rules.DOCS_OF["display"],
                  **rules.display_wrong_orientation(label, written))
        return kind
    return None


def manifest_orientations(screen_ids, per_screen, app_wide):
    """Screen id -> what its ``<activity>`` is given, for the screens that are
    held one way up. What a screen says wins over what ``run()`` says for all
    of them; a screen that turns with the phone is given nothing, which is
    what Android does with a screen that asks for nothing."""
    out = {}
    for sid in screen_ids:
        kind = per_screen.get(sid) or app_wide
        if kind in _MANIFEST_ORIENTATION:
            out[sid] = ' android:screenOrientation="%s"' % _MANIFEST_ORIENTATION[kind]
    return out


# --- the Java ---------------------------------------------------------------

def activity_members():
    """What a screen's class needs beside its blocks.

    A timer is handed the *name* of a function, and outlives the copy of the
    screen that started it: Android builds the screen again when the phone is
    turned. So every screen says, as it is made, how its functions are called
    by name -- the functions an app times, and no others. What an app asks to
    be told about the connection is kept the same way, by its own class.
    """
    lines = []
    for functions, klass, member, said in (
            (_TIMED[0], "ApkpyTimers", "_apkpyTimerCalls",
             "timer.after() and timer.every() call these"),
            (_WATCHED[0], "ApkpyNetwork", "_apkpyNetworkCalls",
             "network.on_change() calls these")):
        if not functions:
            continue
        lines += [
            "",
            "    /** %s by name -- written by ApkPy */" % said,
            "    private final %s.Calls %s = %s.host(this," % (klass, member, klass),
            "            new %s.Calls() {" % klass,
            "        @Override public void call(String name) {",
        ]
        for position, name in enumerate(sorted(functions)):
            lines.append('            %sif ("%s".equals(name)) pythonCallback_%s();'
                         % ("else " if position else "", name, name))
        lines.extend(["        }", "    });"])
    return lines


def class_names():
    """The classes an app using these calls is built with, in a steady order."""
    if not uses_kit():
        return []
    names = ["ApkpyKit", "ApkpyKitRules"]
    for namespace, name in _used_in_order():
        klass = rules.verb(namespace, name).home or rules.SPEC[namespace]["class"]
        if klass not in names:
            names.append(klass)
    for extra in _needs()["classes"]:
        if extra not in names:
            names.append(extra)
    return names


def _java_string(text):
    return (str(text).replace("\\", "\\\\").replace('"', '\\"')
            .replace("\r", "").replace("\n", "\\n"))


def _health_arms():
    return "\n".join(
        '        if ("%s".equals(kind)) return "android.permission.health.%s";'
        % (kind, permission) for kind, (permission, _unit, _icon, _sample)
        in rules.HEALTH_KINDS.items())


def _feedback_arms():
    arms = []
    for kind, (modern, older) in rules.FEEDBACK.items():
        arms.append(
            '        if ("%s".equals(kind)) return modern ? HapticFeedbackConstants.%s\n'
            '                : HapticFeedbackConstants.%s;' % (kind, modern, older))
    return "\n".join(arms)


def java_source(class_name, package):
    """One of the classes, ready to compile."""
    folder = _HERE / "libs" if class_name in _WITH_LIBRARY else _HERE
    source = (folder / (class_name + ".java")).read_text(encoding="utf-8")
    if "ApkpyKitActivity" in _needs()["classes"]:
        source = _LAUNCHER_MARK.sub("", source.replace("\r\n", "\n"))
    else:
        source = _without_launcher(source)
    widget, tile, health = declared("home_widget"), declared("quick_tile"), declared("health")
    low_ms, high_ms = rules.LIMITS["vibrate_ms"]
    low_rate, high_rate = rules.LIMITS["rate"]
    low_pitch, high_pitch = rules.LIMITS["pitch"]
    default_ms = rules.verb("haptics", "vibrate").params[0][2]
    for mark, value in (
            ("__PACKAGE__", package),
            ("__NUMBER__", _java_string(native_rules.NUMBER)),
            ("__WEB__", _java_string(rules.WEB)),
            ("__PAGE_CSS__", _java_string(rules.PAGE_CSS)),
            ("__PRINT_CSS__", _java_string(rules.PRINT_CSS)),
            ("__WIDGET_TITLE__", _java_string(widget.get("title", ""))),
            ("__WIDGET_TEXT__", _java_string(widget.get("text", ""))),
            ("__WIDGET_CAPTION__", _java_string(widget.get("caption", ""))),
            ("__TILE_LABEL__", _java_string(tile.get("label", ""))),
            ("__HEALTH_POLICY__", _java_string(health.get("url", ""))),
            ("__HEALTH_ARMS__", _health_arms()),
            ("__ADS_TEST_BANNER__", rules.ADS_TEST["banner"]),
            ("__ADS_TEST_INTERSTITIAL__", rules.ADS_TEST["interstitial"]),
            ("__ADS_TEST_REWARDED__", rules.ADS_TEST["rewarded"]),
            ("__FEEDBACK_ARMS__", _feedback_arms()),
            ("__DEFAULT_MS__", str(int(default_ms))),
            ("__MIN_MS__", "%d.0" % low_ms), ("__MAX_MS__", "%d.0" % high_ms),
            ("__MIN_RATE__", repr(float(low_rate))), ("__MAX_RATE__", repr(float(high_rate))),
            ("__MIN_PITCH__", repr(float(low_pitch))),
            ("__TIMER_SHORTEST__", str(int(rules.TIMER_SHORTEST))),
            ("__TIMER_LONGEST__", str(int(rules.TIMER_LONGEST))),
            ("__MAX_PITCH__", repr(float(high_pitch)))):
        source = source.replace(mark, value)
    return source


def shared_files(package):
    """``java/ApkpyX.java`` -> source for the classes this app needs, and the
    resources its widget and its tile are made of."""
    files = {"java/%s.java" % name: java_source(name, package) for name in class_names()}
    if uses_kit():
        files.update(resource_files())
    return files
