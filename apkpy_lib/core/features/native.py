# -*- coding: utf-8 -*-
"""The escape hatch: your own Java, declared as a named seam.

ApkPy translates a documented subset of Python, and when something is missing
the honest answer used to be "wait for the next release". Editing the generated
project in Android Studio is not an answer: ``apkpy build`` rewrites it, so the
change is gone at the next APK.

This module gives that gap a shape. You do not paste Java into the middle of an
app; you declare a **function** -- arguments in, one String out -- and say what
the Previewer answers instead. That last part is not politeness: the desktop
cannot run Java, and a seam that only works on the phone brings back exactly
the divergence 1.6.0 and 1.8.0 spent their releases removing.

    battery = native.java("batteryHealth", code="...", preview=lambda: "87")
    reader = native.java_async("readCard", args=("id",), code="...", preview=...)
    native.gradle("implementation 'com.example:sdk:2.1.0'")
    native.manifest(permission="android.permission.VIBRATE")
    native.keep("com.example.sdk.**")

Inside a block you get the arguments you declared (all String, like everything
else the generator writes), a ``context``, and -- for ``java_async`` -- a
``done`` you call as ``done.run(true, "value")`` from any thread: the generated
wrapper moves it to the UI thread before your Python callback runs.

What a block does **not** get is the inside of the generated code. Its fields
are named by the generator and change between versions; an app reaching into
them would break on an upgrade with no way to see it coming.

Every argument of a declaration has to be written in the source, because the
build reads your module, it does not run it. A value computed at run time
cannot be in the APK.
"""
from __future__ import annotations

import ast
import re
import textwrap

from ...diagnostics import ApkpyError
from . import native_python
from . import kit as kit_feature

__all__ = [
    "VERBS", "prescan", "is_declaration", "function_for", "is_async_name",
    "activity_runtime_java", "imports_java", "manifest_lines",
    "application_lines", "gradle_text", "keep_text", "sync_call_java",
    "emit_command", "uses_native",
]

VERBS = ("java", "java_async", "gradle", "manifest", "keep")
DONE_INTERFACE = "ApkpyNativeDone"
METHOD_PREFIX = "_apkpyNative_"
COMMAND_TYPES = frozenset({"native_call", "native_call_async"})
DOCS = "https://repo-apkpy.pages.dev/guides/native/"

_JAVA_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_GRADLE_CONFIGURATIONS = (
    "implementation", "api", "compileOnly", "runtimeOnly",
    "annotationProcessor", "coreLibraryDesugaring",
)

# Per transpilation, like _MUTATED_LISTS in the compiler: the emitters run far
# from the parser and need to see what was declared without carrying the
# transpiler around.
_FUNCTIONS = [{}]
_DIRECTIVES = [{"gradle": [], "keep": [], "permissions": [], "features": [],
                "xml": []}]


def _fail(node, message, cause="", suggestions=(), received=""):
    """One error shape for every native mistake."""
    raise ApkpyError(
        message,
        code="U2035",
        title="A native block cannot be read",
        cause=cause,
        expected="a declaration written in the source, with code= and preview=",
        received=received,
        suggestions=list(suggestions),
        docs=DOCS,
        line=getattr(node, "lineno", 0),
    )


# --- reading the declaration ------------------------------------------------

def _keyword(call, name):
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _literal_text(node, call, label, value, required=True):
    """A string written in the source. An f-string is computed, so it is not."""
    if value is None:
        if not required:
            return ""
        _fail(node, "native: %s is missing" % label,
              cause="%s has to be given, and written out in the source." % label,
              suggestions=['Write it as text: %s="..."' % label])
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    if isinstance(value, ast.JoinedStr):
        _fail(node, "native: %s cannot be an f-string" % label,
              cause=("An f-string is put together while the app runs, and the "
                     "build has to read this while it writes the APK."),
              suggestions=["Write the text out, or pass the changing part as "
                           "an argument: args=(\"value\",)"])
    _fail(node, "native: %s has to be text written in the source" % label,
          cause="The build reads your module, it never runs it.",
          suggestions=['Write it as text: %s="..."' % label])


def _literal_list(node, call, label, value):
    """A list or tuple of literal strings, or nothing."""
    if value is None:
        return []
    if not isinstance(value, (ast.List, ast.Tuple)):
        _fail(node, "native: %s has to be a list written in the source" % label,
              suggestions=['%s=["android.os.BatteryManager"]' % label])
    out = []
    for element in value.elts:
        if not (isinstance(element, ast.Constant)
                and isinstance(element.value, str)):
            _fail(node, "native: every item of %s has to be text" % label,
                  suggestions=['%s=["android.os.BatteryManager"]' % label])
        out.append(element.value)
    return out


def is_declaration(call):
    """True for ``native.<verb>(...)``."""
    func = getattr(call, "func", None)
    return (isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "native")


def _verb(call):
    return call.func.attr


def _known_verb(node, verb):
    if verb not in VERBS:
        _fail(node, "native has no %s()" % verb,
              cause="The native seam is these five: %s." % ", ".join(VERBS),
              received="native.%s(...)" % verb,
              suggestions=["native.java(...) for a value, native.java_async(...) "
                           "for a callback, and gradle/manifest/keep for the build."])


def prescan(transpiler, tree):
    """Read every ``native.*`` declaration before the module is visited.

    Like the jobs prescan: the function a screen calls is declared at the
    bottom of the file, and the parser meets the call first.
    """
    _FUNCTIONS[0] = {}
    _DIRECTIVES[0] = {"gradle": [], "keep": [], "permissions": [],
                      "features": [], "xml": []}

    for node in tree.body:
        call = None
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
        if call is None or not is_declaration(call):
            continue
        verb = _verb(call)
        _known_verb(node, verb)
        if verb in ("java", "java_async"):
            if not isinstance(node, ast.Assign):
                _fail(node, "a native block needs a name",
                      cause=("The block becomes a function your screens call, "
                             "so it has to be given a name."),
                      suggestions=['battery = native.java("batteryHealth", ...)'])
            _parse_function(node, call, verb == "java_async")
        else:
            if isinstance(node, ast.Assign):
                _fail(node, "native.%s() does not return anything" % verb,
                      cause="It adds a line to the build, it is not a value.",
                      suggestions=['Call it on its own line: native.%s("...")' % verb])
            _parse_directive(node, call, verb)

    transpiler.native_functions = dict(_FUNCTIONS[0])
    transpiler.native_directives = {k: list(v) for k, v in _DIRECTIVES[0].items()}
    for permission in _DIRECTIVES[0]["permissions"]:
        # ApkPy's own calls name an Android permission by its last word
        # ("INTERNET"), and one asked for here under its whole name is the
        # same permission: written twice it was two constants of one name in
        # every Activity, which javac refuses.
        prefix = "android.permission."
        if permission.startswith(prefix) and "." not in permission[len(prefix):] \
                and "|" not in permission:
            permission = permission[len(prefix):]
        if permission not in transpiler.declared_permissions:
            transpiler.declared_permissions.append(permission)


def _parse_function(node, call, is_async):
    if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
        _fail(node, "a native block is given one name",
              suggestions=['battery = native.java("batteryHealth", ...)'])
    python_name = node.targets[0].id
    if not call.args:
        _fail(node, "native.java() needs the Java method name",
              suggestions=['native.java("batteryHealth", code="...")'])
    java_name = _literal_text(node, call, "the method name", call.args[0])
    if not _JAVA_NAME.match(java_name):
        _fail(node, "%r is not a Java method name" % java_name,
              cause="It becomes a method in the generated Activity.",
              suggestions=["Use letters and digits, starting with a letter: "
                           '"batteryHealth"'])
    if java_name in {info["java_name"] for info in _FUNCTIONS[0].values()}:
        _fail(node, "there is already a native block called %r" % java_name,
              suggestions=["Give this one another name."])

    code = _literal_text(node, call, "code", _keyword(call, "code"))
    arguments = _literal_list(node, call, "args", _keyword(call, "args"))
    for argument in arguments:
        if not _JAVA_NAME.match(argument):
            _fail(node, "%r is not an argument name" % argument,
                  suggestions=['args=("id", "amount")'])
    if _keyword(call, "preview") is None:
        _fail(node, "native: preview= is missing",
              cause=("The Previewer cannot run Java. Without preview= the "
                     "block would work on the phone and do nothing on the "
                     "desktop, which is the divergence ApkPy exists to stop."),
              suggestions=['preview=lambda: "87"',
                           "preview=a function that answers the same shape"])

    body = textwrap.dedent(code).strip("\n")
    if not body.strip():
        _fail(node, "native: code= is empty", suggestions=['code="return \\"ok\\";"'])
    if not is_async and "return" not in body:
        _fail(node, "native.java(%r) never returns" % java_name,
              cause=("A native.java block answers one String; without a return "
                     "the generated Java does not compile."),
              suggestions=['End the block with return String.valueOf(value);',
                           "Use native.java_async() when the answer comes later."])
    if is_async and "done" not in body:
        _fail(node, "native.java_async(%r) never calls done" % java_name,
              cause=("An async block answers through done, and a block that "
                     "never calls it leaves the app waiting for ever."),
              suggestions=['Call done.run(true, "value") when the work ends.',
                           'And done.run(false, "reason") when it fails.'])

    _FUNCTIONS[0][python_name] = {
        "python_name": python_name,
        "java_name": java_name,
        "async": is_async,
        "code": body,
        "imports": _literal_list(node, call, "imports", _keyword(call, "imports")),
        "args": arguments,
        "line": getattr(node, "lineno", 0),
    }


def _parse_directive(node, call, verb):
    if verb == "gradle":
        if not call.args:
            _fail(node, "native.gradle() needs the dependency line",
                  suggestions=["native.gradle(\"implementation 'group:name:1.0'\")"])
        text = _literal_text(node, call, "the dependency", call.args[0]).strip()
        first = text.split(" ", 1)[0] if text else ""
        if first not in _GRADLE_CONFIGURATIONS:
            _fail(node, "native.gradle() takes one Gradle dependency line",
                  cause="It is copied into the dependencies block as it stands.",
                  received=text[:60],
                  suggestions=["native.gradle(\"implementation 'group:name:1.0'\")",
                               "The first word is the configuration: %s."
                               % ", ".join(_GRADLE_CONFIGURATIONS[:4])])
        if text not in _DIRECTIVES[0]["gradle"]:
            _DIRECTIVES[0]["gradle"].append(text)
        return

    if verb == "keep":
        if not call.args:
            _fail(node, "native.keep() needs a class pattern",
                  suggestions=['native.keep("com.example.sdk.**")'])
        pattern = _literal_text(node, call, "the pattern", call.args[0]).strip()
        if pattern and pattern not in _DIRECTIVES[0]["keep"]:
            _DIRECTIVES[0]["keep"].append(pattern)
        return

    # manifest(permission=..., feature=..., xml=...)
    permission = _keyword(call, "permission")
    feature = _keyword(call, "feature")
    xml = _keyword(call, "xml")
    if permission is None and feature is None and xml is None:
        _fail(node, "native.manifest() needs permission=, feature= or xml=",
              suggestions=['native.manifest(permission="android.permission.VIBRATE")',
                           'native.manifest(feature="android.hardware.nfc")',
                           'native.manifest(xml="<service android:name=\\"...\\" />")'])
    if permission is not None:
        value = _literal_text(node, call, "permission", permission).strip()
        if value and value not in _DIRECTIVES[0]["permissions"]:
            _DIRECTIVES[0]["permissions"].append(value)
    if feature is not None:
        value = _literal_text(node, call, "feature", feature).strip()
        if value and value not in _DIRECTIVES[0]["features"]:
            _DIRECTIVES[0]["features"].append(value)
    if xml is not None:
        value = _literal_text(node, call, "xml", xml).strip()
        if "</application>" in value or "<application" in value:
            _fail(node, "native.manifest(xml=) cannot rewrite <application>",
                  cause=("The application element is written by ApkPy, and two "
                         "of them is a manifest that does not merge."),
                  suggestions=["Pass the child element only: "
                               '<service android:name="..." />'])
        if value and value not in _DIRECTIVES[0]["xml"]:
            _DIRECTIVES[0]["xml"].append(value)


# --- what the compiler asks -------------------------------------------------

def function_for(name):
    """The declaration behind a Python name, or ``None``."""
    return _FUNCTIONS[0].get(name)


def is_async_name(name):
    info = _FUNCTIONS[0].get(name)
    return bool(info and info["async"])


def uses_native(_transpiler=None):
    directives = _DIRECTIVES[0]
    return bool(_FUNCTIONS[0]) or any(directives[key] for key in directives)


def imports_java(_transpiler=None):
    """The import lines every declared block asked for, once each."""
    seen, out = set(), []
    for info in _FUNCTIONS[0].values():
        for name in info["imports"]:
            line = "import %s;" % name.strip().rstrip(";")
            if line not in seen:
                seen.add(line)
                out.append(line)
    return out


def sync_call_java(info, arguments_java):
    """``battery()`` where a value is expected."""
    return "_apkpyNativeText(%s%s(%s))" % (
        METHOD_PREFIX, info["java_name"], ", ".join(arguments_java))


def register_callback(transpiler, call):
    """Tell the generator that this callback is answered ``(ok, value)``.

    The signature of pythonCallback_x is decided while the module is parsed, so
    a callback registered any later is written with a String where the boolean
    goes -- which javac catches and the tests do not.
    """
    info = _FUNCTIONS[0].get(getattr(call.func, "id", ""))
    if not info or not info["async"]:
        return
    for keyword in call.keywords:
        if keyword.arg == "on_result" and isinstance(keyword.value, ast.Name):
            transpiler.boolean_first_arg_callbacks.add(keyword.value.id)


def value_call_java(node, val_to_java):
    """A declared block used where a value is expected.

    Everything a call may or may not look like is decided here, so the value
    path and the statement path cannot drift apart.
    """
    info = _FUNCTIONS[0][node.func.id]
    if info["async"]:
        _fail(node, "native: %s() answers later, through done" % info["java_name"],
              cause=("An async block has no value at the moment it is called; "
                     "the answer arrives in on_result."),
              suggestions=["Call it on its own line with on_result=, and use "
                           "the value inside that callback."])
    _check_arity(node, info, len(node.args))
    if node.keywords:
        _fail(node, "native: %s() got %s" % (
            info["java_name"], ", ".join(sorted(k.arg or "**" for k in node.keywords))),
              suggestions=["A native.java block takes the arguments you "
                           "declared in args=, and nothing else."])
    return sync_call_java(
        info, ["String.valueOf(%s)" % val_to_java(argument)
               for argument in node.args])


def _refuse_own_call_in_job(info, line):
    """haptics.tap() and the like, inside a job: said the way the Previewer
    says it, with the call the person wrote rather than the block behind it."""
    own = kit_feature.label_for(info["java_name"]) if info else None
    if own:
        from ... import job_rules
        job_rules.refuse("screen_api", own, line=line)


def refuse_in_job_call(node):
    """A native block asked for inside the body of a background job."""
    info = _FUNCTIONS[0].get(getattr(node.func, "id", ""))
    _refuse_own_call_in_job(info, getattr(node, "lineno", 0))
    _fail(node, "native: %s() runs on a screen, not in a background job"
          % (info["java_name"] if info else "this block"),
          cause=("A native block is written into the Activity of a screen. A "
                 "background job runs in a Worker, which has no screen."),
          suggestions=["Call the block from a screen and keep what it answers.",
                       "Or do the work in the job with the APIs ApkPy "
                       "translates."])


def _check_arity(node, info, given):
    if given != len(info["args"]):
        written = native_python.written_as(info["java_name"])
        _fail(node, "native: %s() takes %d argument(s), got %d"
              % (info["java_name"], len(info["args"]), given),
              cause=("It was written %s." % written if written else
                     "It was declared with args=%r." % (tuple(info["args"]),)))


def statement_command(command, functions_map=None):
    """A ``function_call`` the parser made, turned into a native command.

    The parser cannot tell ``atualizar()`` from ``battery()`` -- both are a
    call to a name -- so the sorting happens here, where the declarations are.
    """
    info = _FUNCTIONS[0].get(command.get("name"))
    node = _CommandNode(command.get("lineno", 0))
    arguments = list(command.get("args_nodes", []))
    _check_arity(node, info, len(arguments))

    keywords = dict(command.get("keywords_nodes") or {})
    callback = None
    if info["async"]:
        answer = keywords.pop("on_result", None)
        if answer is not None:
            if not (isinstance(answer, ast.Name)
                    and answer.id in (functions_map or {})):
                _fail(node, "native: on_result= has to be a function you defined",
                      cause=("The generated Java calls it by name, so a lambda "
                             "or an expression has nothing to call."),
                      suggestions=["def got(ok, value): ...  then "
                                   "on_result=got"])
            callback = answer.id
    if keywords:
        _fail(node, "native: %s() got %s"
              % (info["java_name"], ", ".join(sorted(keywords))),
              suggestions=["Pass the arguments you declared in args=, and "
                           "on_result= for an async block."])

    return {"type": "native_call_async" if info["async"] else "native_call",
            "name": info["python_name"], "args": arguments,
            "callback": callback, "line": command.get("lineno", 0)}


def refuse_in_job(command):
    """A native block asked for from the body of a background job."""
    info = _FUNCTIONS[0].get(command.get("name"))
    _refuse_own_call_in_job(info, command.get("lineno", 0))
    _fail(_CommandNode(command.get("lineno", 0)),
          "native: %s() runs on a screen, not in a background job"
          % (info["java_name"] if info else command.get("name")),
          cause=("A native block is written into the Activity of a screen. A "
                 "background job runs in a Worker, which has no screen."),
          suggestions=["Call the block from a screen and keep what it answers.",
                       "Or do the work in the job with the APIs ApkPy "
                       "translates."])


class _CommandNode:
    """Carries a line number where the emitters no longer have the AST node."""

    def __init__(self, lineno):
        self.lineno = int(lineno or 0)


def emit_command(lines, indent, command, val_to_java=None, functions_map=None):
    info = _FUNCTIONS[0].get(command.get("name"))
    if info is None:
        return
    arguments = ["String.valueOf(%s)" % (val_to_java(node) if val_to_java else '""')
                 for node in command.get("args", [])]
    if command.get("type") == "native_call":
        lines.append("%s%s%s(%s);" % (indent, METHOD_PREFIX, info["java_name"],
                                      ", ".join(arguments)))
        return
    callback = command.get("callback")
    body = ("pythonCallback_%s(ok, value);" % callback) if callback else ""
    arguments.append(
        "_apkpyNativeMain(new %s() { @Override public void run(boolean ok, "
        "String value) { %s } })" % (DONE_INTERFACE, body))
    lines.append("%s%s%s(%s);" % (indent, METHOD_PREFIX, info["java_name"],
                                  ", ".join(arguments)))


def activity_runtime_java(_package=None):
    """The interface, the two helpers and one method per declared block."""
    if not _FUNCTIONS[0]:
        return []
    out = [
        "",
        "    // --- native blocks ------------------------------------------",
        "    // Written by native.java()/java_async() in writehere.py. What is",
        "    // inside each method is the app author's Java, not ApkPy's.",
        "    private interface %s { void run(boolean ok, String value); }" % DONE_INTERFACE,
        "",
        "    /** A block may answer from any thread; Python callbacks run on this one. */",
        "    private %s _apkpyNativeMain(final %s target) {" % (DONE_INTERFACE, DONE_INTERFACE),
        "        return new %s() {" % DONE_INTERFACE,
        "            @Override public void run(final boolean ok, final String value) {",
        "                runOnUiThread(new Runnable() {",
        "                    @Override public void run() {",
        "                        target.run(ok, value == null ? \"\" : value);",
        "                    }",
        "                });",
        "            }",
        "        };",
        "    }",
        "",
        "    /** A block that answers null would put the word null on a screen. */",
        "    private String _apkpyNativeText(String value) {",
        "        return value == null ? \"\" : value;",
        "    }",
    ]
    if native_python.uses_python_blocks():
        out[4:4] = ["    // Under \"@native def\" it is the author's Python, translated line",
                    "    // by line and checked against android.jar when the app was built."]
    ours = [bool(kit_feature.label_for(info["java_name"]))
            for info in _FUNCTIONS[0].values()]
    if any(ours):
        if all(ours):
            # Nothing here is the author's Java: say what it is instead.
            out[1:4] = ["    // --- calls to the phone -------------------------------------",
                        "    // haptics, speech, browser and the like: each call the app makes",
                        "    // is one line into a class of ApkPy's (ApkpyHaptics, ...)."]
        else:
            out[4:4] = ["    // The ones marked \"written by ApkPy\" are haptics, speech, browser",
                        "    // and the like: one line each into a class of ApkPy's."]
    for info in _FUNCTIONS[0].values():
        parameters = ["String %s" % name for name in info["args"]]
        if info["async"]:
            parameters.append("final %s done" % DONE_INTERFACE)
            signature = "    private void %s%s(%s) {" % (
                METHOD_PREFIX, info["java_name"], ", ".join(parameters))
        else:
            signature = "    private String %s%s(%s) {" % (
                METHOD_PREFIX, info["java_name"], ", ".join(parameters))
        written = native_python.label_for(info["java_name"]) or 'native.%s("%s")' % (
            "java_async" if info["async"] else "java", info["java_name"])
        own = kit_feature.label_for(info["java_name"])
        out.extend([
            "",
            ("    /** %s -- written by ApkPy */" % own) if own else
            "    /** %s -- writehere.py:%d */" % (written, info["line"]),
            signature,
        ])
        if not own:
            # What an app's own block is promised. ApkPy's blocks are one
            # line that hands over the Activity itself.
            out.append("        final android.content.Context context = this;")
        out.extend("        " + line if line.strip() else ""
                   for line in info["code"].split("\n"))
        out.append("    }")
    out.extend(kit_feature.activity_members())
    out.extend(native_python.helpers_java())
    return out


# The elements that are children of <manifest>. Everything else an app adds
# with native.manifest(xml=) -- a service, a receiver, an activity, a
# provider, meta-data -- is a child of <application>.
_MANIFEST_LEVEL = frozenset({
    "queries", "uses-permission", "uses-permission-sdk-23", "uses-feature",
    "permission", "permission-group", "permission-tree", "supports-screens",
    "compatible-screens", "uses-configuration", "supports-gl-texture",
    "instrumentation", "uses-sdk",
})


def _belongs_to_manifest(element):
    found = re.match(r"\s*<([A-Za-z][A-Za-z0-9-]*)", element)
    return bool(found) and found.group(1) in _MANIFEST_LEVEL


def manifest_lines(_transpiler=None):
    """``<uses-feature>`` and the elements the app added that sit beside
    ``<application>``, such as ``<queries>``.

    Permissions go the usual way, through ``declared_permissions``: they are
    written with the same rules as every other permission ApkPy asks for.
    """
    out = []
    for feature in _DIRECTIVES[0]["features"]:
        out.append('    <uses-feature android:name="%s" android:required="false" />'
                   % feature)
    for element in _DIRECTIVES[0]["xml"]:
        if _belongs_to_manifest(element):
            out.extend("    " + line for line in element.split("\n"))
    return out


def application_lines(_transpiler=None):
    """The elements the app added that go inside ``<application>``.

    Until 1.13.0 these were written beside it, where Android reads a
    ``<service>`` as nothing at all: the build passed and the component did
    not exist.
    """
    out = []
    for element in _DIRECTIVES[0]["xml"]:
        if not _belongs_to_manifest(element):
            out.extend("        " + line for line in element.split("\n"))
    return out


def gradle_text(_transpiler=None):
    """The dependency lines, one per line, or empty."""
    return "\n".join(_DIRECTIVES[0]["gradle"])


def keep_text(_transpiler=None):
    """R8 keep rules. A block reached only by reflection disappears without them."""
    if not _DIRECTIVES[0]["keep"]:
        return ""
    out = ["# Asked for by native.keep() in writehere.py."]
    for pattern in _DIRECTIVES[0]["keep"]:
        out.append("-keep class %s { *; }" % pattern)
    return "\n".join(out) + "\n"
