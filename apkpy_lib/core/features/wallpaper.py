"""Static wallpaper generation. No network, live wallpaper or silent writes."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from ...diagnostics import ApkpyError

TARGETS = ("home", "lock", "both")
REASONS = {
    "ok": "Android accepted the wallpaper after confirmation.",
    "simulated": "The Previewer simulated success; the desktop was not changed.",
    "cancelled": "The confirmation was cancelled.",
    "busy": "Another wallpaper request is still open or running.",
    "unsupported": "Wallpapers are not supported for this Android user.",
    "not_allowed": "Device policy or a permission prevents this change.",
    "invalid_target": "Use home, lock or both.",
    "invalid_image": "The image could not be read or decoded.",
    "unavailable": "An active foreground screen is required.",
    "failed": "Android could not apply the wallpaper.",
}
COMMAND_TYPES = frozenset({"wallpaper_set"})


def _named(node, method):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "wallpaper" and node.func.attr == method)


def is_call(node):
    return _named(node, "set")


def is_value_call(node):
    return _named(node, "available")


def uses_wallpaper(tree):
    # Walk the AST, not just top-level commands: conditions and nested callbacks
    # must include the helper too. No mutable, cross-compilation registry.
    return any(is_call(n) or is_value_call(n) for n in ast.walk(tree))


def commands_use_wallpaper(functions_map, module_init_cmds=None):
    def walk(commands):
        for command in commands or []:
            if not isinstance(command, dict):
                continue
            if command.get("type") in COMMAND_TYPES:
                return True
            if any(walk(command.get(key)) for key in ("true_body", "false_body", "body", "handler", "final")):
                return True
        return False
    return walk(module_init_cmds) or any(walk(info.get("cmds")) for info in (functions_map or {}).values() if info)


def _error(message, node, suggestion):
    raise ApkpyError(message, code="C1700", line=getattr(node, "lineno", 0),
                     suggestions=[suggestion])


def _arguments(call):
    names = ("source", "target", "on_result")
    if len(call.args) > 3 or any(isinstance(a, ast.Starred) for a in call.args):
        _error("Invalid wallpaper.set() arguments", call,
               'Use wallpaper.set(source, target="home", on_result=done).')
    values = dict(zip(names, call.args))
    for kw in call.keywords:
        if kw.arg not in names or kw.arg in values:
            _error("Unknown or repeated wallpaper.set() argument: %s" % kw.arg,
                   call, "Accepted arguments: source, target, on_result.")
        values[kw.arg] = kw.value
    if "source" not in values:
        _error("wallpaper.set() needs an image source", call,
               "Pass the path returned by gallery.pick(), or a literal image filename.")
    target = values.get("target", ast.Constant(value="home"))
    if isinstance(target, ast.Constant) and target.value not in TARGETS:
        _error("Invalid wallpaper target: %r" % target.value, call,
               'Use target="home", "lock" or "both".')
    return values, target


def _bundled(node):
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        return False
    return bool(node.value) and "://" not in node.value


def _asset_name(source):
    return "apkpy_wallpaper/" + hashlib.sha256(source.encode("utf-8")).hexdigest()[:20] + ".img"


def validate_and_assets(tree, project_root):
    assets = {}
    for node in ast.walk(tree):
        if is_value_call(node) and (node.args or node.keywords):
            _error("wallpaper.available() takes no arguments", node,
                   "Call wallpaper.available().")
        if not is_call(node):
            continue
        values, _ = _arguments(node)
        source = values["source"]
        if _bundled(source):
            path = (Path(project_root) / source.value).resolve()
            if not path.is_file():
                _error("Wallpaper image not found: %s" % source.value, node,
                       "Check the filename relative to your project, or use gallery.pick().")
            assets["app/src/main/assets/" + _asset_name(source.value)] = ("COPY_FILE", str(path))
    return assets


def parse_call(transpiler, call):
    values, target = _arguments(call)
    source = values["source"]
    if _bundled(source):
        source = ast.Constant(value="asset://" + _asset_name(source.value))
    cb = values.get("on_result")
    if cb is not None and not (isinstance(cb, (ast.Name, ast.Lambda))
                               or isinstance(cb, ast.Constant) and cb.value is None):
        _error("Invalid wallpaper result callback", call,
               "Pass a function accepting (success, reason), or a two-argument lambda.")
    if isinstance(cb, ast.Lambda) and len(cb.args.args) != 2:
        _error("Wallpaper callbacks receive two arguments", call,
               "Use lambda success, reason: toast(reason).")
    if isinstance(cb, ast.Lambda):
        callback = transpiler._unique_function_name("wallpaper_result")
        params = [arg.arg for arg in cb.args.args]
        body = ast.fix_missing_locations(ast.Expr(value=cb.body))
        transpiler.functions[callback] = {
            "args": params, "cmds": transpiler._parse_statements([body]),
            "string_args": {params[1]},
        }
        transpiler.boolean_first_arg_callbacks.add(callback)
    else:
        callback = transpiler._register_result_callback(cb, True, "wallpaper")
    if "SET_WALLPAPER" not in transpiler.declared_permissions:
        transpiler.declared_permissions.append("SET_WALLPAPER")
    return {"type": "wallpaper_set", "source": source, "target": target,
            "callback": callback, "line": getattr(call, "lineno", 0)}


def emit_command(lines, indent, command, val_to_java, functions_map=None, scope="activity"):
    if scope != "activity":
        raise ApkpyError("wallpaper.set() cannot run in a background job", code="C1700",
                         line=command.get("line", 0),
                         suggestions=["Call it from a button on a visible screen; confirmation is required."])
    cb = command.get("callback")
    callback = "null" if not cb else "(_apkpyWallOk, _apkpyWallReason) -> pythonCallback_%s(_apkpyWallOk, _apkpyWallReason)" % cb
    # The tag travels with the request so the answer can find its way back to
    # the right callback even when this Activity does not survive to hear it.
    tag = "null" if not cb else '"%s"' % cb
    lines.append('%s_apkpyWallpaperSet(String.valueOf(%s), String.valueOf(%s), %s, %s);' % (
        indent, val_to_java(command["source"]), val_to_java(command["target"]),
        tag, callback))


def callbacks_used(functions_map, module_init_cmds=None):
    """Every ``on_result`` name reachable in this screen, in source order.

    The Activity needs them by name: applying a wallpaper recreates it, so the
    replacement has to re-offer the same callbacks to collect an answer that
    arrived while it was being rebuilt.
    """
    found = []

    def walk(commands):
        for command in commands or []:
            if not isinstance(command, dict):
                continue
            if command.get("type") in COMMAND_TYPES:
                name = command.get("callback")
                if name and name not in found:
                    found.append(name)
            for key in ("true_body", "false_body", "body", "handler", "final"):
                walk(command.get(key))

    walk(module_init_cmds)
    for info in (functions_map or {}).values():
        if info:
            walk(info.get("cmds"))
    return found


def condition_java(node):
    return "ApkpyWallpaper.available(getApplicationContext())"


def value_java(node):
    return '(%s ? "True" : "False")' % condition_java(node)


def shared_class_java(package):
    return Path(__file__).with_name("wallpaper_android.java").read_text(encoding="utf-8").replace("__PACKAGE__", package)
