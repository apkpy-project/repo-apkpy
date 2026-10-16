"""Shared notification contract and narrow native compiler hooks."""
import ast
import hashlib
import json
from pathlib import Path
import re

from ...diagnostics import ApkpyError

IMPORTANCE = {"min": "IMPORTANCE_MIN", "low": "IMPORTANCE_LOW",
              "default": "IMPORTANCE_DEFAULT", "high": "IMPORTANCE_HIGH"}
STYLES = ("none", "big_text", "big_picture", "inbox")
MAX_ACTIONS = 3
DEFAULT_CHANNEL = "apkpy_default"
REASONS = {"ok": "Posted", "not_allowed": "Notifications are disabled",
           "no_channel": "Declare the channel before posting", "invalid_style": "Unknown notification style",
           "invalid_picture": "Use a readable local image or content URI",
           "invalid_progress": "Use 0 to 100, None, or indeterminate"}
VERBS = ("channel", "cancel", "cancel_all", "allowed", "ask")
PARAMS = ("title", "message", "id", "channel", "icon", "style", "picture", "lines",
          "actions", "on_tap", "on_dismiss", "ongoing", "progress", "group", "when")
DEFAULTS = dict(id="apkpy_notification", channel=DEFAULT_CHANNEL, icon="notifications",
                style="none", picture=None, lines=None, actions=None, on_tap=None,
                on_dismiss=None, ongoing=False, progress=None, group=None, when=None)


def validate(style="none", picture=None, lines=None, actions=None, progress=None):
    if style not in STYLES:
        raise ValueError("Notification style must be one of: " + ", ".join(STYLES))
    if style == "big_picture" and not picture:
        raise ValueError("style='big_picture' requires picture='local-image.jpg'")
    if picture is not None and style != "big_picture":
        raise ValueError("picture is only valid with style='big_picture'")
    if lines is not None and style != "inbox":
        raise ValueError("lines is only valid with style='inbox'")
    if lines is not None and (not isinstance(lines, (list, tuple)) or not all(isinstance(x, str) for x in lines)):
        raise ValueError("Notification lines must be a list of strings")
    if actions is not None:
        if not isinstance(actions, (list, tuple)) or len(actions) > MAX_ACTIONS:
            raise ValueError("Notifications support at most 3 actions")
        if any(not isinstance(x, (list, tuple)) or len(x) != 2 for x in actions):
            raise ValueError("Use actions=[('Label', callback)]")
    if progress is not None and progress != "indeterminate":
        if isinstance(progress, bool) or not isinstance(progress, (int, float)) or not 0 <= progress <= 100:
            raise ValueError(REASONS["invalid_progress"])


def is_call(node):
    f = getattr(node, "func", None)
    return isinstance(node, ast.Call) and (
        isinstance(f, ast.Name) and f.id == "notify" or
        isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "notifications")


def is_value_call(node):
    return is_call(node) and isinstance(node.func, ast.Attribute) and node.func.attr == "allowed"


def fail(message, node):
    raise ApkpyError(message, code="C1710", title="Check the notification declaration",
                     line=getattr(node, "lineno", 0), suggestions=["Check the notification API arguments and declare its channel first."])


def constant(node, name, default=None):
    if node is None:
        return default
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        fail("Notification %s must be constant" % name, node)


def arguments(call, names, defaults=()):
    if len(call.args) > len(names):
        fail("Too many notification arguments", call)
    result = dict(zip(names, call.args))
    for kw in call.keywords:
        if kw.arg not in names or kw.arg in result:
            fail("Unknown or repeated notification argument: " + str(kw.arg), call)
        result[kw.arg] = kw.value
    for name, value in dict(defaults).items():
        result.setdefault(name, ast.Constant(value=value))
    return result


def parse_call(t, call):
    if not is_call(call):
        return None
    if "POST_NOTIFICATIONS" not in t.declared_permissions:
        t.declared_permissions.append("POST_NOTIFICATIONS")
    if isinstance(call.func, ast.Attribute):
        verb = call.func.attr
        if verb not in VERBS:
            fail("Unknown notifications method: " + verb, call)
        names = ("id", "name", "importance") if verb == "channel" else (("id",) if verb == "cancel" else ())
        args = arguments(call, names, {"importance": "default"} if verb == "channel" else {})
        if verb == "channel":
            if not all(k in args for k in ("id", "name")):
                fail("channel requires id and name", call)
            importance = constant(args["importance"], "importance")
            if importance not in IMPORTANCE:
                fail("importance must be min, low, default or high", call)
        if verb == "cancel" and "id" not in args:
            fail("cancel requires the notification id", call)
        return {"type": "notification_" + verb, "args": args}
    if len(call.args) > 3:
        fail("After title, message and id, use named notification arguments", call)
    args = arguments(call, PARAMS, DEFAULTS)
    if "title" not in args or "message" not in args:
        fail("notify requires title and message", call)
    style = constant(args["style"], "style")
    icon = constant(args["icon"], "icon")
    from ... import icons
    if not isinstance(icon, str) or icons.resolve(icon) is None:
        fail("Unknown notification icon: %s. Choose a name from the icon catalogue." % icon, call)
    actions = args["actions"]
    parsed_actions = []
    if not (isinstance(actions, ast.Constant) and actions.value is None):
        if not isinstance(actions, (ast.List, ast.Tuple)) or len(actions.elts) > MAX_ACTIONS:
            fail("Notifications support at most 3 actions", call)
        for row in actions.elts:
            if not isinstance(row, (ast.List, ast.Tuple)) or len(row.elts) != 2:
                fail("Use actions=[('Label', callback)]", row)
            if isinstance(row.elts[1], ast.Lambda) and (row.elts[1].args.args or row.elts[1].args.kwonlyargs or row.elts[1].args.vararg or row.elts[1].args.kwarg):
                fail("Notification callbacks take no parameters", row.elts[1])
            callback = t._register_overlay_callback(row.elts[1], "notification_action")
            if not callback:
                fail("Each notification action requires a callback", row)
            parsed_actions.append((row.elts[0], callback))
    for key in ("on_tap", "on_dismiss"):
        value = args[key]
        if isinstance(value, ast.Constant) and value.value is None:
            args[key] = None
        elif isinstance(value, ast.Name):
            args[key] = value.id
        else:
            if isinstance(value, ast.Lambda) and (value.args.args or value.args.kwonlyargs or value.args.vararg or value.args.kwarg):
                fail("Notification callbacks take no parameters", value)
            callback = t._register_overlay_callback(value, "notification_" + key)
            if not callback:
                fail(key + " must be a callback" + (" or Screen" if key == "on_tap" else ""), value)
            args[key] = callback
    picture = args["picture"]
    known_picture = constant(picture, "picture") if isinstance(picture, ast.Constant) else "dynamic"
    try:
        raw_lines = args["lines"]
        try:
            checked_lines = ast.literal_eval(raw_lines)
        except (ValueError, TypeError):
            checked_lines = [] if style == "inbox" else [""]
        validate(style, known_picture,
                 checked_lines,
                 parsed_actions,
                 constant(args["progress"], "progress") if isinstance(args["progress"], ast.Constant) else None)
    except ValueError as e:
        fail(str(e), call)
    args["style"] = ast.Constant(value=style)
    args["icon"] = ast.Constant(value=icon)
    return {"type": "notify", "args": args, "actions": parsed_actions, "line": call.lineno}


def value_java(node):
    if is_value_call(node):
        if node.args or node.keywords:
            fail("notifications.allowed() takes no arguments", node)
        return '(ApkpyNotifications.allowed(getApplicationContext()) ? "True" : "False")'


def emit_command(lines, c, val, indent, scope="activity"):
    kind = c.get("type", "")
    if kind != "notify" and not kind.startswith("notification_"):
        return False
    args = c["args"]
    def text(name):
        n = args[name]
        return '""' if isinstance(n, ast.Constant) and n.value is None else "String.valueOf(%s)" % val(n)
    if kind == "notification_channel":
        lines.append('%sApkpyNotifications.channel(getApplicationContext(), %s, %s, %s);' % (indent, text("id"), text("name"), text("importance")))
    elif kind == "notification_cancel":
        lines.append('%sApkpyNotifications.cancel(getApplicationContext(), %s);' % (indent, text("id")))
    elif kind == "notification_cancel_all":
        lines.append(indent + "ApkpyNotifications.cancelAll(getApplicationContext());")
    elif kind == "notification_ask":
        if scope == "worker":
            fail("Request notifications.ask() from a screen, not a background worker", None)
        lines.append(indent + "_apkpyNotificationAsk();")
    elif kind == "notification_allowed":
        lines.append(indent + "ApkpyNotifications.allowed(getApplicationContext());")
    else:
        pairs = []
        for key in ("title", "message", "id", "channel", "icon", "style", "picture", "lines", "ongoing", "progress", "group", "when"):
            pairs.extend((json.dumps(key), text(key)))
        for key in ("on_tap", "on_dismiss"):
            pairs.extend((json.dumps(key), json.dumps(args[key] or "")))
        for i, (label, callback) in enumerate(c["actions"]):
            pairs.extend((json.dumps("action_%d_title" % i), "String.valueOf(%s)" % val(label),
                          json.dumps("action_%d_callback" % i), json.dumps(callback)))
        spec = "ApkpyNotifications.spec(%s)" % ", ".join(pairs)
        if scope == "worker":
            lines.append('%sApkpyNotifications.post(getApplicationContext(), %s, null);' % (indent, spec))
        else:
            lines.append('%s_apkpyNotify(%s);' % (indent, spec))
    return True


def used(tree):
    return any(is_call(n) or (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name) and n.func.value.id == "push" and n.func.attr in ("listen", "simulate", "get_token", "subscribe", "unsubscribe")) for n in ast.walk(tree))


def files(tree, t, package, asset_root, icon_vector):
    if not used(tree):
        return {}
    icons = {"notifications"}
    pictures = {}
    for call in ast.walk(tree):
        if not is_call(call) or not isinstance(call.func, ast.Name):
            continue
        kw = {k.arg: k.value for k in call.keywords}
        callback_nodes = [(k, kw[k]) for k in ("on_tap", "on_dismiss") if k in kw]
        if isinstance(kw.get("actions"), (ast.List, ast.Tuple)):
            callback_nodes += [("action", row.elts[1]) for row in kw["actions"].elts if isinstance(row, (ast.List, ast.Tuple)) and len(row.elts) == 2]
        for kind, callback in callback_nodes:
            if isinstance(callback, ast.Name):
                if kind == "on_tap" and callback.id in t.screens:
                    continue
                info = t.functions.get(callback.id)
                if info is None or info.get("args"):
                    fail("%s requires a declared callback with no parameters%s" % (kind, " or a Screen" if kind == "on_tap" else ""), callback)
        icons.add(constant(kw.get("icon"), "icon", "notifications"))
        pic = kw.get("picture")
        if isinstance(pic, ast.Constant) and isinstance(pic.value, str):
            name = pic.value
            if name.startswith(("http:", "https:")):
                fail("Notification pictures must be local files or content URIs", pic)
            if name.startswith("content:"):
                continue
            p = (Path(asset_root) / name).resolve()
            if not p.is_file():
                fail("Notification picture does not exist: " + name, pic)
            pictures[name] = ("apkpy_notifications/" + hashlib.sha256(name.encode()).hexdigest()[:16] + p.suffix.lower(), str(p))
    screens = t.screens
    routes = {name: "Screen_%sActivity" % sid for name, sid in screens.items()}
    start = "Screen_%sActivity" % (t.start_screen_id or next(iter(screens.values())))
    source = Path(__file__).with_name("notifications_android.java").read_text(encoding="utf-8")
    importance = "\n".join('case "%s": return android.app.NotificationManager.%s;' % item for item in IMPORTANCE.items())
    source = source.replace("__PACKAGE__", package).replace("__START__", start).replace("__IMPORTANCE__", importance)
    source = source.replace("__ROUTES__", "\n".join('case %s: return %s.class;' % (json.dumps(k), v) for k,v in routes.items()))
    source = source.replace("__SCREENS__", "\n".join('case %s: return true;' % json.dumps(k) for k in routes))
    source = source.replace("__STYLES__", ",".join(json.dumps(s) for s in STYLES)).replace("__MAX_ACTIONS__", str(MAX_ACTIONS))
    source = source.replace("__PICTURES__", "\n".join('case %s: return %s;' % (json.dumps(k), json.dumps(v[0])) for k,v in pictures.items()))
    source = source.replace("__ICONS__", "\n".join('case %s: return R.drawable.apkpy_notification_%s;' % (json.dumps(k), re.sub('[^a-z0-9_]','_',k.lower())) for k in sorted(icons)))
    result = {"java/ApkpyNotifications.java": source}
    for icon in icons:
        result["res/drawable/apkpy_notification_%s.xml" % re.sub('[^a-z0-9_]','_',icon.lower())] = icon_vector(icon, "#FFFFFF")
    for target, original in pictures.values():
        result["app/src/main/assets/" + target] = ("COPY_FILE", original)
    return result


def integrate_activity(source):
    """Generated class hook; no rewriting of application logic or layout."""
    # Replace the older startup prompt with the on-demand Activity Result path.
    source = re.sub(r'        // [^\n]*Pedir permissão de notificações[^\n]*\n'
                    r'        if \(android\.os\.Build\.VERSION\.SDK_INT[^\n]*\n'
                    r'[^\n]*POST_NOTIFICATIONS[^\n]*\n'
                    r'[^\n]*ActivityCompat\.requestPermissions[^\n]*\n        }\n', '', source)
    # Only methods actually emitted for this screen can be dispatched.
    callbacks = sorted(set(re.findall(r'private void pythonCallback_([A-Za-z0-9_]+)\(\)', source)))
    arms = "\n".join('case %s: pythonCallback_%s(); return;' % (json.dumps(c),c) for c in callbacks)
    helper = '''
    private final java.util.LinkedHashMap<String, org.json.JSONObject> _apkpyPendingNotifications = new java.util.LinkedHashMap<>();
    private boolean _apkpyNotificationRequestActive;
    private final androidx.activity.result.ActivityResultLauncher<String> _apkpyNotificationPermission = registerForActivityResult(
        new androidx.activity.result.contract.ActivityResultContracts.RequestPermission(), granted -> {
            _apkpyNotificationRequestActive = false;
            if (granted) for (org.json.JSONObject spec : new java.util.ArrayList<>(_apkpyPendingNotifications.values()))
                ApkpyNotifications.post(this, spec, getClass());
            _apkpyPendingNotifications.clear();
        });
    private void _apkpyNotificationAsk() {
        if (!_apkpyNotificationRequestActive && android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU &&
            androidx.core.content.ContextCompat.checkSelfPermission(this, android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            _apkpyNotificationRequestActive = true;
            _apkpyNotificationPermission.launch(android.Manifest.permission.POST_NOTIFICATIONS);
        }
    }
    private void _apkpyNotify(org.json.JSONObject spec) {
        if (android.os.Build.VERSION.SDK_INT >= 33 &&
            androidx.core.content.ContextCompat.checkSelfPermission(this, android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            if (_apkpyPendingNotifications.size() >= 32) _apkpyPendingNotifications.remove(_apkpyPendingNotifications.keySet().iterator().next());
            boolean first = _apkpyPendingNotifications.isEmpty();
            _apkpyPendingNotifications.put(spec.optString("id"), spec);
            if (first) _apkpyNotificationAsk();
        } else ApkpyNotifications.post(this, spec, getClass());
    }
    private void _apkpyNotificationDispatch(String callback) {
        switch (callback) { __ARMS__ }
    }
    private void _apkpyNotificationSave(android.os.Bundle state) {
        java.util.ArrayList<String> pending = new java.util.ArrayList<>();
        for (org.json.JSONObject spec : _apkpyPendingNotifications.values()) pending.add(spec.toString());
        state.putStringArrayList("apkpy:pendingNotifications", pending);
        state.putBoolean("apkpy:notificationRequest", _apkpyNotificationRequestActive);
    }
    private void _apkpyNotificationRestore(android.os.Bundle state) {
        if (state == null) return;
        _apkpyNotificationRequestActive = state.getBoolean("apkpy:notificationRequest", false);
        java.util.ArrayList<String> pending = state.getStringArrayList("apkpy:pendingNotifications");
        if (pending != null) for (String raw : pending) try {
            org.json.JSONObject spec = new org.json.JSONObject(raw);
            if (_apkpyPendingNotifications.size() < 32) _apkpyPendingNotifications.put(spec.optString("id"), spec);
        } catch (org.json.JSONException ignored) { }
    }
'''.replace("__ARMS__", arms)
    source = source.replace("        super.onCreate(savedInstanceState);", "        super.onCreate(savedInstanceState);\n        _apkpyNotificationRestore(savedInstanceState);", 1)
    if "protected void onSaveInstanceState(" in source:
        source = source.replace("        super.onSaveInstanceState(outState);", "        _apkpyNotificationSave(outState);\n        super.onSaveInstanceState(outState);", 1)
    else:
        helper += '''
    @Override protected void onSaveInstanceState(android.os.Bundle outState) {
        _apkpyNotificationSave(outState); super.onSaveInstanceState(outState);
    }
'''
    source = source.replace("        setContentView(", "        ApkpyNotifications.attach(this, this::_apkpyNotificationDispatch);\n        setContentView(", 1)
    source = source.replace("        _apkpyPushMessage = onMessage;", "        if (ApkpyFirebaseMessagingService.autoNotificationsEnabled()) _apkpyNotificationAsk();\n        _apkpyPushMessage = onMessage;")
    if "protected void onNewIntent(android.content.Intent intent)" in source:
        source = source.replace("        setIntent(intent);", "        setIntent(intent);\n        ApkpyNotifications.open(this, intent);", 1)
    else:
        helper += '''
    @Override protected void onNewIntent(android.content.Intent intent) {
        super.onNewIntent(intent); setIntent(intent); ApkpyNotifications.open(this, intent);
    }
'''
    at = source.rfind("}")
    return source[:at] + helper + source[at:]


def integrate_push(source):
    start = source.index("    public static void showNotification(")
    target = re.search(r'context,\s*(Screen_[A-Za-z0-9_]+Activity)\.class', source[start:])
    if target is None:
        raise ValueError("Firebase notification target Activity was not generated")
    return source[:start] + '''    public static boolean autoNotificationsEnabled() { return AUTO_NOTIFY; }
    public static void showNotification(android.content.Context context,
                                        String title, String body, String data) {
        if (!AUTO_NOTIFY) return;
        ApkpyNotifications.channel(context, CHANNEL_ID, CHANNEL_NAME, "default");
        android.content.Intent open = new android.content.Intent(context, __PUSH_ACTIVITY__.class);
        open.putExtra(EXTRA_TYPE, TYPE_MESSAGE);
        open.putExtra(EXTRA_TITLE, title == null ? "Update" : title);
        open.putExtra(EXTRA_BODY, body == null ? "" : body);
        open.putExtra(EXTRA_DATA, data == null ? "{}" : data);
        ApkpyNotifications.post(context, ApkpyNotifications.spec(
            "title", title == null ? "Update" : title, "message", body == null ? "" : body,
            "id", "push_" + java.util.UUID.randomUUID(), "channel", CHANNEL_ID, "style", "big_text"), null, open);
    }
}
'''.replace("__PUSH_ACTIVITY__", target.group(1))
