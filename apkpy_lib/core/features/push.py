"""Parser and Android code generation for ``push.*``.

This module is deliberately isolated from the legacy compiler.  The compiler
only forwards push calls here and includes the returned runtime when needed.
"""

from __future__ import annotations

import ast
import json
import re


COMMAND_TYPES = frozenset(
    {
        "push_listen",
        "push_get_token",
        "push_subscribe",
        "push_unsubscribe",
        "push_simulate",
    }
)


def is_push_call(call):
    func = getattr(call, "func", None)
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "push"
        and func.attr in {"listen", "get_token", "subscribe", "unsubscribe", "simulate"}
    )


def _kw_node(transpiler, call, name):
    return transpiler._kw_node(call.keywords, name)


def _pos_or_kw(transpiler, call, position, name):
    if len(call.args) > position:
        return call.args[position]
    return _kw_node(transpiler, call, name)


def _callback(transpiler, node, arity, tag, boolean_first=False):
    if isinstance(node, ast.Name):
        name = node.id
        if boolean_first:
            transpiler.boolean_first_arg_callbacks.add(name)
        return name
    if not isinstance(node, ast.Lambda):
        return None

    defaults = {
        1: ["value"],
        2: ["success", "value"],
        3: ["title", "body", "data"],
    }
    params = [arg.arg for arg in node.args.args]
    params = (params + defaults.get(arity, []))[:arity]
    while len(params) < arity:
        params.append("arg%d" % (len(params) + 1))
    name = transpiler._unique_function_name("push_%s_cb" % tag)
    body = ast.Expr(value=node.body)
    ast.fix_missing_locations(body)
    string_args = set(params[1:] if boolean_first else params)
    transpiler.functions[name] = {
        "args": params,
        "cmds": transpiler._parse_statements([body]),
        "string_args": string_args,
    }
    if boolean_first:
        transpiler.boolean_first_arg_callbacks.add(name)
    return name


def _literal_data(node):
    if node is None or isinstance(node, ast.Constant):
        return node
    try:
        value = ast.literal_eval(node)
    except (TypeError, ValueError, SyntaxError):
        return node
    if isinstance(value, dict):
        return ast.Constant(
            value=json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        )
    return node


def parse_call(transpiler, call):
    """Translate one ``push.*`` AST call into a compact compiler command."""
    if not is_push_call(call):
        return None

    action = call.func.attr
    for permission in ("INTERNET", "POST_NOTIFICATIONS"):
        if permission not in transpiler.declared_permissions:
            transpiler.declared_permissions.append(permission)

    if action == "listen":
        screen_node = _kw_node(transpiler, call, "screen")
        screen_var = screen_node.id if isinstance(screen_node, ast.Name) else None
        screen_id = transpiler.screens.get(screen_var) if screen_var else None
        config = {
            "auto_notify": bool(transpiler._kw(call.keywords, "auto_notify", True)),
            "channel_id": str(transpiler._kw(call.keywords, "channel_id", "apkpy_push")),
            "channel_name": str(transpiler._kw(call.keywords, "channel_name", "Updates")),
            "screen_id": screen_id,
        }
        # One app-level Firebase service is generated.  The final declaration
        # wins deliberately, matching the Previewer's listener replacement.
        transpiler.push_config = config
        return {
            "type": "push_listen",
            "screen_id": screen_id,
            "message_callback": _callback(
                transpiler, _kw_node(transpiler, call, "on_message"), 3, "message"
            ),
            "token_callback": _callback(
                transpiler, _kw_node(transpiler, call, "on_token"), 1, "token"
            ),
            "error_callback": _callback(
                transpiler, _kw_node(transpiler, call, "on_error"), 1, "error"
            ),
        }

    if action == "get_token":
        return {
            "type": "push_get_token",
            "callback": _callback(
                transpiler, _kw_node(transpiler, call, "on_result"), 2,
                "token_result", boolean_first=True,
            ),
        }

    if action in {"subscribe", "unsubscribe"}:
        return {
            "type": "push_" + action,
            "topic_node": _pos_or_kw(transpiler, call, 0, "topic"),
            "callback": _callback(
                transpiler, _kw_node(transpiler, call, "on_result"), 2,
                action, boolean_first=True,
            ),
        }

    return {
        "type": "push_simulate",
        "title_node": _pos_or_kw(transpiler, call, 0, "title"),
        "body_node": _pos_or_kw(transpiler, call, 1, "body"),
        "data_node": _literal_data(_pos_or_kw(transpiler, call, 2, "data")),
    }


def commands_use_push(functions_map, module_init_cmds=None):
    def walk(commands):
        for command in commands or []:
            if not isinstance(command, dict):
                continue
            if command.get("type") in COMMAND_TYPES:
                return True
            for key in ("true_body", "false_body", "body"):
                if walk(command.get(key, [])):
                    return True
        return False

    if walk(module_init_cmds):
        return True
    return any(
        walk(info.get("cmds", [])) for info in functions_map.values() if info
    )


def emit_command(lines, indent, command, val_to_java):
    kind = command.get("type")
    if kind == "push_listen":
        message = command.get("message_callback")
        token = command.get("token_callback")
        error = command.get("error_callback")
        message_arg = (
            "(title, body, data) -> pythonCallback_%s(title, body, data)" % message
            if message else "null"
        )
        token_arg = (
            "value -> pythonCallback_%s(value)" % token if token else "null"
        )
        error_arg = (
            "value -> pythonCallback_%s(value)" % error if error else "null"
        )
        lines.append(
            "%s_pushListen(%s, %s, %s);"
            % (indent, message_arg, token_arg, error_arg)
        )
        return

    if kind == "push_get_token":
        callback = command.get("callback")
        callback_arg = (
            "(success, value) -> pythonCallback_%s(success, value)" % callback
            if callback else "null"
        )
        lines.append("%s_pushGetToken(%s);" % (indent, callback_arg))
        return

    if kind in {"push_subscribe", "push_unsubscribe"}:
        topic = val_to_java(command.get("topic_node"))
        callback = command.get("callback")
        callback_arg = (
            "(success, value) -> pythonCallback_%s(success, value)" % callback
            if callback else "null"
        )
        subscribe = "true" if kind == "push_subscribe" else "false"
        lines.append(
            "%s_pushTopic(String.valueOf(%s), %s, %s);"
            % (indent, topic, subscribe, callback_arg)
        )
        return

    title = val_to_java(command.get("title_node"))
    body = val_to_java(command.get("body_node"))
    data = val_to_java(command.get("data_node")) if command.get("data_node") is not None else '"{}"'
    lines.append(
        "%s_pushSimulate(String.valueOf(%s), String.valueOf(%s), String.valueOf(%s));"
        % (indent, title, body, data)
    )


def activity_runtime_java():
    """Activity-side receiver and Firebase helpers, emitted only when used."""
    return r'''
    // -- push.* : Firebase Cloud Messaging + UI-thread callbacks -----------
    private interface PushMessageCallback {
        void onMessage(String title, String body, String data);
    }
    private interface PushTokenCallback { void onToken(String token); }
    private interface PushErrorCallback { void onError(String error); }
    private interface PushResultCallback {
        void onResult(boolean success, String value);
    }

    private PushMessageCallback _apkpyPushMessage;
    private PushTokenCallback _apkpyPushToken;
    private PushErrorCallback _apkpyPushError;
    private boolean _apkpyPushRegistered = false;

    private final android.content.BroadcastReceiver _apkpyPushReceiver =
            new android.content.BroadcastReceiver() {
        @Override
        public void onReceive(android.content.Context context,
                              android.content.Intent intent) {
            _pushHandleIntent(intent);
        }
    };

    private void _pushListen(PushMessageCallback onMessage,
                             PushTokenCallback onToken,
                             PushErrorCallback onError) {
        _apkpyPushMessage = onMessage;
        _apkpyPushToken = onToken;
        _apkpyPushError = onError;
        if (!_apkpyPushRegistered) {
            android.content.IntentFilter filter = new android.content.IntentFilter(
                    ApkpyFirebaseMessagingService.ACTION_PUSH);
            androidx.core.content.ContextCompat.registerReceiver(
                    this, _apkpyPushReceiver, filter,
                    androidx.core.content.ContextCompat.RECEIVER_NOT_EXPORTED);
            _apkpyPushRegistered = true;
        }
        String savedToken = getSharedPreferences(
                "apkpy_push", android.content.Context.MODE_PRIVATE)
                .getString("token", "");
        if (!savedToken.isEmpty() && _apkpyPushToken != null) {
            _apkpyPushToken.onToken(savedToken);
        } else if (savedToken.isEmpty()) {
            _pushGetToken(null);
        }
        _pushHandleIntent(getIntent());
    }

    private void _pushHandleIntent(android.content.Intent intent) {
        if (intent == null || !intent.hasExtra(
                ApkpyFirebaseMessagingService.EXTRA_TYPE)) return;
        String type = intent.getStringExtra(
                ApkpyFirebaseMessagingService.EXTRA_TYPE);
        if (ApkpyFirebaseMessagingService.TYPE_TOKEN.equals(type)) {
            String token = intent.getStringExtra(
                    ApkpyFirebaseMessagingService.EXTRA_TOKEN);
            if (_apkpyPushToken != null) _apkpyPushToken.onToken(
                    token == null ? "" : token);
            intent.removeExtra(ApkpyFirebaseMessagingService.EXTRA_TYPE);
            return;
        }
        if (ApkpyFirebaseMessagingService.TYPE_MESSAGE.equals(type)
                && _apkpyPushMessage != null) {
            String title = intent.getStringExtra(
                    ApkpyFirebaseMessagingService.EXTRA_TITLE);
            String body = intent.getStringExtra(
                    ApkpyFirebaseMessagingService.EXTRA_BODY);
            String data = intent.getStringExtra(
                    ApkpyFirebaseMessagingService.EXTRA_DATA);
            _apkpyPushMessage.onMessage(
                    title == null ? "" : title,
                    body == null ? "" : body,
                    data == null ? "{}" : data);
            intent.removeExtra(ApkpyFirebaseMessagingService.EXTRA_TYPE);
        }
    }

    @Override
    protected void onNewIntent(android.content.Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        _pushHandleIntent(intent);
    }

    private String _pushFriendlyError(Throwable error) {
        String fallback = "Firebase request failed";
        if (error == null || error.getMessage() == null
                || error.getMessage().trim().isEmpty()) return fallback;
        String raw = error.getMessage().trim();
        String lower = raw.toLowerCase(java.util.Locale.ROOT);
        if (lower.contains("firebaseapp")
                || lower.contains("initializeapp")
                || lower.contains("google-services")) {
            return "Firebase is not configured. Add google-services.json "
                    + "and rebuild the app.";
        }
        return raw;
    }

    private void _pushReportError(String error,
                                  final PushResultCallback callback) {
        if (_apkpyPushError != null) _apkpyPushError.onError(error);
        if (callback != null) callback.onResult(false, error);
    }

    private boolean _pushEnsureFirebase(final PushResultCallback callback) {
        try {
            try {
                com.google.firebase.FirebaseApp.getInstance();
            } catch (IllegalStateException missingDefaultApp) {
                com.google.firebase.FirebaseApp initialized =
                        com.google.firebase.FirebaseApp.initializeApp(
                                getApplicationContext());
                if (initialized == null) {
                    _pushReportError(
                            "Firebase is not configured. Add google-services.json "
                                    + "and rebuild the app.",
                            callback);
                    return false;
                }
            }
            return true;
        } catch (Exception exception) {
            _pushReportError(_pushFriendlyError(exception), callback);
            return false;
        }
    }

    private void _pushGetToken(final PushResultCallback callback) {
        if (!_pushEnsureFirebase(callback)) return;
        try {
            com.google.firebase.messaging.FirebaseMessaging.getInstance()
                    .getToken()
                    .addOnCompleteListener(task -> runOnUiThread(() -> {
                        if (task.isSuccessful() && task.getResult() != null) {
                            String token = task.getResult();
                            getSharedPreferences("apkpy_push", MODE_PRIVATE)
                                    .edit().putString("token", token).apply();
                            if (_apkpyPushToken != null) _apkpyPushToken.onToken(token);
                            if (callback != null) callback.onResult(true, token);
                        } else {
                            String error = task.getException() == null
                                    ? "Firebase token unavailable"
                                    : _pushFriendlyError(task.getException());
                            _pushReportError(error, callback);
                        }
                    }));
        } catch (Exception exception) {
            _pushReportError(_pushFriendlyError(exception), callback);
        }
    }

    private void _pushTopic(String topic, boolean subscribe,
                            final PushResultCallback callback) {
        String clean = topic == null ? "" : topic.trim();
        if (!clean.matches("[A-Za-z0-9_.~%\\-]{1,900}")) {
            String error = "Invalid Firebase topic";
            if (_apkpyPushError != null) _apkpyPushError.onError(error);
            if (callback != null) callback.onResult(false, error);
            return;
        }
        if (!_pushEnsureFirebase(callback)) return;
        try {
            com.google.android.gms.tasks.Task<Void> task = subscribe
                    ? com.google.firebase.messaging.FirebaseMessaging.getInstance()
                            .subscribeToTopic(clean)
                    : com.google.firebase.messaging.FirebaseMessaging.getInstance()
                            .unsubscribeFromTopic(clean);
            task.addOnCompleteListener(result -> runOnUiThread(() -> {
                boolean success = result.isSuccessful();
                String value = success ? clean
                        : (result.getException() == null ? "Topic request failed"
                        : _pushFriendlyError(result.getException()));
                if (!success && _apkpyPushError != null) {
                    _apkpyPushError.onError(value);
                }
                if (callback != null) callback.onResult(success, value);
            }));
        } catch (Exception exception) {
            _pushReportError(_pushFriendlyError(exception), callback);
        }
    }

    private void _pushSimulate(String title, String body, String data) {
        String safeTitle = title == null || title.isEmpty() ? "Update" : title;
        String safeBody = body == null ? "" : body;
        String safeData = data == null || data.isEmpty() ? "{}" : data;
        if (_apkpyPushMessage != null) {
            _apkpyPushMessage.onMessage(safeTitle, safeBody, safeData);
        }
        ApkpyFirebaseMessagingService.showNotification(
                this, safeTitle, safeBody, safeData);
    }

    private void _pushDispose() {
        if (_apkpyPushRegistered) {
            try { unregisterReceiver(_apkpyPushReceiver); }
            catch (IllegalArgumentException ignored) { }
            _apkpyPushRegistered = false;
        }
        _apkpyPushMessage = null;
        _apkpyPushToken = null;
        _apkpyPushError = null;
    }
'''


def _java_literal(value):
    return json.dumps(str(value), ensure_ascii=False)


def generate_service_java(package, start_activity, config=None):
    config = config or {}
    auto_notify = "true" if config.get("auto_notify", True) else "false"
    channel_id = _java_literal(config.get("channel_id", "apkpy_push"))
    channel_name = _java_literal(config.get("channel_name", "Updates"))
    safe_activity = re.sub(r"[^A-Za-z0-9_]", "_", str(start_activity))
    return f'''package {package};

public final class ApkpyFirebaseMessagingService extends
        com.google.firebase.messaging.FirebaseMessagingService {{
    public static final String ACTION_PUSH = "{package}.APKPY_PUSH";
    public static final String EXTRA_TYPE = "apkpy_push_type";
    public static final String EXTRA_TITLE = "apkpy_push_title";
    public static final String EXTRA_BODY = "apkpy_push_body";
    public static final String EXTRA_DATA = "apkpy_push_data";
    public static final String EXTRA_TOKEN = "apkpy_push_token";
    public static final String TYPE_MESSAGE = "message";
    public static final String TYPE_TOKEN = "token";
    private static final String CHANNEL_ID = {channel_id};
    private static final String CHANNEL_NAME = {channel_name};
    private static final boolean AUTO_NOTIFY = {auto_notify};

    @Override
    public void onNewToken(String token) {{
        super.onNewToken(token);
        getSharedPreferences("apkpy_push", MODE_PRIVATE).edit()
                .putString("token", token == null ? "" : token).apply();
        android.content.Intent intent = baseIntent(TYPE_TOKEN);
        intent.putExtra(EXTRA_TOKEN, token == null ? "" : token);
        sendBroadcast(intent);
    }}

    @Override
    public void onMessageReceived(
            com.google.firebase.messaging.RemoteMessage message) {{
        super.onMessageReceived(message);
        String title = "Update";
        String body = "";
        if (message.getNotification() != null) {{
            if (message.getNotification().getTitle() != null) {{
                title = message.getNotification().getTitle();
            }}
            if (message.getNotification().getBody() != null) {{
                body = message.getNotification().getBody();
            }}
        }}
        if (message.getData().containsKey("title")) {{
            title = message.getData().get("title");
        }}
        if (message.getData().containsKey("body")) {{
            body = message.getData().get("body");
        }}
        org.json.JSONObject json = new org.json.JSONObject(message.getData());
        android.content.Intent intent = baseIntent(TYPE_MESSAGE);
        intent.putExtra(EXTRA_TITLE, title);
        intent.putExtra(EXTRA_BODY, body);
        intent.putExtra(EXTRA_DATA, json.toString());
        sendBroadcast(intent);
        if (AUTO_NOTIFY) showNotification(this, title, body, json.toString());
    }}

    private android.content.Intent baseIntent(String type) {{
        android.content.Intent intent = new android.content.Intent(ACTION_PUSH);
        intent.setPackage(getPackageName());
        intent.putExtra(EXTRA_TYPE, type);
        return intent;
    }}

    public static void showNotification(android.content.Context context,
                                        String title, String body, String data) {{
        if (!AUTO_NOTIFY) return;
        android.app.NotificationManager manager =
                (android.app.NotificationManager) context.getSystemService(
                        android.content.Context.NOTIFICATION_SERVICE);
        if (manager == null) return;
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {{
            android.app.NotificationChannel channel = new android.app.NotificationChannel(
                    CHANNEL_ID, CHANNEL_NAME,
                    android.app.NotificationManager.IMPORTANCE_DEFAULT);
            manager.createNotificationChannel(channel);
        }}
        android.content.Intent open = new android.content.Intent(
                context, Screen_{safe_activity}Activity.class);
        open.addFlags(android.content.Intent.FLAG_ACTIVITY_CLEAR_TOP
                | android.content.Intent.FLAG_ACTIVITY_SINGLE_TOP);
        open.putExtra(EXTRA_TYPE, TYPE_MESSAGE);
        open.putExtra(EXTRA_TITLE, title == null ? "Update" : title);
        open.putExtra(EXTRA_BODY, body == null ? "" : body);
        open.putExtra(EXTRA_DATA, data == null ? "{{}}" : data);
        android.app.PendingIntent pending = android.app.PendingIntent.getActivity(
                context, 8127, open,
                android.app.PendingIntent.FLAG_UPDATE_CURRENT
                        | android.app.PendingIntent.FLAG_IMMUTABLE);
        int smallIcon = context.getApplicationInfo().icon;
        if (smallIcon == 0) smallIcon = android.R.drawable.ic_dialog_info;
        androidx.core.app.NotificationCompat.Builder notification =
                new androidx.core.app.NotificationCompat.Builder(context, CHANNEL_ID)
                        .setSmallIcon(smallIcon)
                        .setContentTitle(title == null ? "Update" : title)
                        .setContentText(body == null ? "" : body)
                        .setStyle(new androidx.core.app.NotificationCompat.BigTextStyle()
                                .bigText(body == null ? "" : body))
                        .setAutoCancel(true)
                        .setPriority(androidx.core.app.NotificationCompat.PRIORITY_DEFAULT)
                        .setContentIntent(pending);
        if (android.os.Build.VERSION.SDK_INT < 33
                || androidx.core.content.ContextCompat.checkSelfPermission(
                        context, android.Manifest.permission.POST_NOTIFICATIONS)
                == android.content.pm.PackageManager.PERMISSION_GRANTED) {{
            manager.notify((int) (System.currentTimeMillis() & 0x7fffffff),
                    notification.build());
        }}
    }}
}}
'''


def manifest_service_lines():
    return [
        "        <service",
        '            android:name=".ApkpyFirebaseMessagingService"',
        '            android:exported="false">',
        "            <intent-filter>",
        '                <action android:name="com.google.firebase.MESSAGING_EVENT" />',
        "            </intent-filter>",
        "        </service>",
        "",
    ]


__all__ = [
    "COMMAND_TYPES",
    "activity_runtime_java",
    "commands_use_push",
    "emit_command",
    "generate_service_java",
    "is_push_call",
    "manifest_service_lines",
    "parse_call",
]
