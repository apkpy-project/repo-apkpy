"""Shared advanced-camera contract and small Android generator hooks."""
import ast
import json
import re
from pathlib import Path
from ...diagnostics import ApkpyError
from .camera_ui import UI_OPTIONS, JSON_OPTIONS, CONTROLS, LABELS, COLORS, validate_ui

CAMERAX_VERSION = "1.4.2"  # Stable, supports this generator's compileSdk 35.
OPTIONS = {
    "mode": "photo", "lens": "back", "flash": "off", "quality": "fhd",
    "aspect_ratio": "4:3", "zoom": 1.0, "exposure": 0, "timer": 0,
    "grid": True, "audio": True, "mirror": True, "max_duration": 60,
    "jpeg_quality": 95,
    "iso": 0, "shutter_ms": 0.0, "focus_distance": -1.0, "white_balance": "auto",
    **UI_OPTIONS,
}
CHOICES = {"mode": ("photo", "video"), "lens": ("back", "front"),
           "flash": ("off", "on", "auto"), "quality": ("sd", "hd", "fhd", "uhd"),
           "aspect_ratio": ("4:3", "16:9"),
           "white_balance": ("auto", "daylight", "cloudy", "incandescent", "fluorescent")}
RANGES = {"zoom": (1, 100), "exposure": (-20, 20), "timer": (0, 30),
          "max_duration": (1, 3600), "jpeg_quality": (1, 100),
          "iso": (0, 51200), "shutter_ms": (0, 1000), "focus_distance": (-1, 100)}
BOOLS = ("grid", "audio", "mirror")
VERBS = ("open", "capture", "record", "capabilities")
COMMAND_TYPES = ("camera_open", "camera_capabilities")


def validate(options):
    unknown = set(options) - set(OPTIONS)
    if unknown:
        raise ValueError("Unknown camera option: " + sorted(unknown)[0])
    out = dict(OPTIONS, **options)
    for name, allowed in CHOICES.items():
        if out[name] not in allowed:
            raise ValueError("camera.%s must be one of: %s" % (name, ", ".join(allowed)))
    for name, (low, high) in RANGES.items():
        v = out[name]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not low <= v <= high:
            raise ValueError("camera.%s must be a number between %s and %s" % (name, low, high))
        if name not in ("zoom", "shutter_ms", "focus_distance") and int(v) != v:
            raise ValueError("camera.%s must be an integer" % name)
    for name in BOOLS:
        if not isinstance(out[name], bool):
            raise ValueError("camera.%s must be True or False" % name)
    if out['focus_distance'] < 0 and out['focus_distance'] != -1:
        raise ValueError("camera.focus_distance is -1 for autofocus or a nonnegative diopter value")
    validate_ui(out)
    return out


def validate_callbacks(tree):
    definitions = {n.name:n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)}
    for call in ast.walk(tree):
        if not is_call(call):
            continue
        cbs = {kw.arg:kw.value for kw in call.keywords if kw.arg in ('on_result','on_error')}
        if call.args:cbs.setdefault('on_result',call.args[0])
        for tag, node in cbs.items():
            expected = 1 if tag=='on_error' or call.func.attr=='capabilities' else 2
            if isinstance(node,ast.Name) and node.id in definitions:
                args=definitions[node.id].args
                if len(args.args)!=expected or args.vararg or args.kwarg or args.kwonlyargs:
                    fail("Camera %s callback '%s' must accept %d arguments"%(tag,node.id,expected),call)


def named(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "camera")


def is_call(node):
    return named(node) and node.func.attr != "available"


def is_value_call(node):
    return named(node) and node.func.attr == "available"


def used(tree):
    return any(named(n) for n in ast.walk(tree))


def fail(message, node):
    raise ApkpyError(message, code="C1800", line=getattr(node, "lineno", 0),
                     suggestions=['Use camera.open(on_result=done), where done(success, path) receives the saved file. See the camera guide for supported options.'])


def callback(t, node, count, tag):
    if node is None or isinstance(node, ast.Constant) and node.value is None:
        return None
    if not isinstance(node, (ast.Name, ast.Lambda)):
        fail("Camera callback must be a function or lambda", node)
    if isinstance(node, ast.Lambda):
        if len(node.args.args) != count or node.args.vararg or node.args.kwarg or node.args.kwonlyargs:
            fail("Camera %s callback expects %d arguments" % (tag, count), node)
        # The old generic helper uses fixed lambda names. Camera calls must not
        # overwrite each other's callbacks when more than one button uses them.
        name = t._unique_function_name("camera_" + tag)
        params = [arg.arg for arg in node.args.args]
        body = ast.fix_missing_locations(ast.Expr(value=node.body))
        t.functions[name] = {"args": params, "cmds": t._parse_statements([body]),
                             "string_args": set(params[1:] if count == 2 else params)}
    else:
        name = node.id
    if count == 2:
        t.boolean_first_arg_callbacks.add(name)
    elif tag == "capabilities":
        t.json_item_callbacks.add(name)
    return name


def parse_call(t, call):
    verb = call.func.attr
    if verb not in VERBS:
        fail("Unknown camera method: " + verb, call)
    names = ("on_result",)  # Original camera.capture(callback) stays valid.
    if len(call.args) > 1:
        fail("Use named camera options after on_result", call)
    args = dict(zip(names, call.args))
    allowed = {"on_result", "on_error"} | (set(OPTIONS) if verb != "capabilities" else set())
    for kw in call.keywords:
        if kw.arg not in allowed or kw.arg in args:
            fail("Unknown or repeated camera argument: " + str(kw.arg), call)
        args[kw.arg] = kw.value
    options = {k: args[k] for k in OPTIONS if k in args}
    if verb in ("capture", "record"):
        if "mode" in options:
            fail("Use camera.open(mode=...) or omit mode from " + verb, call)
        options["mode"] = ast.Constant(value="photo" if verb == "capture" else "video")
    for k, v in options.items():
        try:
            literal = ast.literal_eval(v)
        except (ValueError, TypeError):
            if k in JSON_OPTIONS:
                fail("camera.%s must be a literal list/dictionary (or None) in Android builds" % k, v)
            continue
        try:
            validate({k: literal})
        except ValueError as e:
            fail(str(e), v)
    try:
        known_iso=ast.literal_eval(options.get('iso',ast.Constant(0)))
        known_shutter=ast.literal_eval(options.get('shutter_ms',ast.Constant(0)))
    except (ValueError,TypeError):
        pass
    else:
        if bool(known_iso)!=bool(known_shutter):
            fail("Set both iso and shutter_ms, or leave both at 0 for auto exposure",call)
    for p in ("CAMERA",) + (("RECORD_AUDIO",) if verb != "capabilities" and
                           not (isinstance(options.get("audio"), ast.Constant) and options["audio"].value is False) else ()):
        if p not in t.declared_permissions:
            t.declared_permissions.append(p)
    return {"type": "camera_capabilities" if verb == "capabilities" else "camera_open",
            "options": options, "line": call.lineno,
            "callback": callback(t, args.get("on_result"), 1 if verb == "capabilities" else 2, "capabilities" if verb == "capabilities" else "result"),
            "error": callback(t, args.get("on_error"), 1, "error")}


def condition_java(node):
    if node.args or node.keywords:
        fail("camera.available() takes no arguments", node)
    return 'getPackageManager().hasSystemFeature("android.hardware.camera.any")'


def value_java(node):
    return '(%s ? "True" : "False")' % condition_java(node)


def emit_command(lines, indent, c, val, functions_map=None, scope="activity"):
    if scope != "activity":
        raise ApkpyError("Camera operations require a foreground screen, not a background job",code="C1800",line=c.get('line',0),suggestions=["Call camera.open() from a visible screen."])
    cb = c["callback"]
    err = c["error"]
    if c["type"] == "camera_capabilities":
        lines.append('%s%s;' % (indent, ('pythonCallback_%s(ApkpyCameraActivity.capabilities(getApplicationContext()))' % cb) if cb else 'ApkpyCameraActivity.capabilities(getApplicationContext())'))
    else:
        pairs = []
        for k, v in c["options"].items():
            if k in JSON_OPTIONS:
                literal = ast.literal_eval(v)
                if literal is None:
                    continue
                encoded = json.dumps(json.dumps(literal, ensure_ascii=True), ensure_ascii=True)
            else:
                encoded = "String.valueOf(%s)" % val(v)
            pairs.extend((json.dumps(k), encoded))
        lines.append('%s_apkpyCameraOpen(ApkpyCameraActivity.options(%s), %s, %s);' % (
            indent, ", ".join(pairs), json.dumps(cb or ""), json.dumps(err or "")))


def files(package):
    source = Path(__file__).with_name("camera_android.java").read_text(encoding="utf-8").replace("__PACKAGE__", package)
    for marker, value in (("__CAMERA_UI_CONTROLS__", CONTROLS), ("__CAMERA_UI_LABELS__", LABELS), ("__CAMERA_UI_COLORS__", COLORS)):
        source = source.replace(marker, json.dumps(json.dumps(value, ensure_ascii=True)))
    return {"java/ApkpyCameraActivity.java": source}


def integrate_manifest(source):
    source = source.replace("</application>", '<activity android:name=".ApkpyCameraActivity" android:exported="false" android:configChanges="orientation|screenSize|keyboardHidden" />\n    </application>')
    for feature in ("camera", "camera.any", "camera.autofocus", "microphone"):
        if 'android.hardware.' + feature + '"' not in source:
            source = source.replace("<application", '<uses-feature android:name="android.hardware.%s" android:required="false" />\n    <application' % feature, 1)
    return source


def integrate_activity(source):
    result_names = set(re.findall(r'private void pythonCallback_(\w+)\(boolean\s+\w+,\s*String\s+\w+\)', source))
    error_names = set(re.findall(r'private void pythonCallback_(\w+)\(String\s+\w+\)', source))
    result_arms = '\n'.join('case "%s": pythonCallback_%s(ok, path); break;' % (n, n) for n in sorted(result_names))
    error_arms = '\n'.join('case "%s": pythonCallback_%s(reason); break;' % (n, n) for n in sorted(error_names))
    helper = '''
    private String _apkpyCameraResult = "", _apkpyCameraError = "";
    private boolean _apkpyCameraBusy;
    private final androidx.activity.result.ActivityResultLauncher<android.content.Intent> _apkpyCameraLauncher = registerForActivityResult(
        new androidx.activity.result.contract.ActivityResultContracts.StartActivityForResult(), result -> {
            android.content.Intent data = result.getData();
            String cb = data == null ? _apkpyCameraResult : data.getStringExtra("resultCallback");
            String err = data == null ? _apkpyCameraError : data.getStringExtra("errorCallback");
            boolean ok = result.getResultCode() == RESULT_OK;
            String path = data == null ? "" : data.getStringExtra("path");
            String reason = data == null ? "cancelled" : data.getStringExtra("reason");
            _apkpyCameraBusy = false;
            _apkpyCameraResult = ""; _apkpyCameraError = "";
            _apkpyCameraDispatch(cb, err, ok, path == null ? "" : path, reason == null ? "cancelled" : reason);
        });
    private void _apkpyCameraDispatch(String cb, String err, boolean ok, String path, String reason) {
        if (!ok && !"cancelled".equals(reason)) switch (err == null ? "" : err) { __ERRORS__ }
        switch (cb == null ? "" : cb) { __RESULTS__ }
    }
    private void _apkpyCameraOpen(android.os.Bundle options, String cb, String err) {
        if (_apkpyCameraBusy) { _apkpyCameraDispatch(cb, err, false, "", "busy"); return; }
        _apkpyCameraBusy = true; _apkpyCameraResult = cb; _apkpyCameraError = err;
        android.content.Intent intent = new android.content.Intent(this, ApkpyCameraActivity.class);
        intent.putExtras(options); intent.putExtra("resultCallback", cb); intent.putExtra("errorCallback", err);
        _apkpyCameraLauncher.launch(intent);
    }
    private void _apkpyCameraSave(android.os.Bundle s) {
        s.putBoolean("apkpy:cameraBusy", _apkpyCameraBusy);
        s.putString("apkpy:cameraResult", _apkpyCameraResult); s.putString("apkpy:cameraError", _apkpyCameraError);
    }
    private void _apkpyCameraRestore(android.os.Bundle s) {
        if (s == null) return;
        _apkpyCameraBusy = s.getBoolean("apkpy:cameraBusy");
        _apkpyCameraResult = s.getString("apkpy:cameraResult", ""); _apkpyCameraError = s.getString("apkpy:cameraError", "");
    }
'''.replace("__RESULTS__", result_arms).replace("__ERRORS__", error_arms)
    source = source.replace("        super.onCreate(savedInstanceState);", "        super.onCreate(savedInstanceState);\n        _apkpyCameraRestore(savedInstanceState);", 1)
    if "protected void onSaveInstanceState(" in source:
        source = source.replace("        super.onSaveInstanceState(outState);", "        _apkpyCameraSave(outState);\n        super.onSaveInstanceState(outState);", 1)
    else:
        helper += '\n    @Override protected void onSaveInstanceState(android.os.Bundle outState) { _apkpyCameraSave(outState); super.onSaveInstanceState(outState); }\n'
    at = source.rfind("}")
    return source[:at] + helper + source[at:]
