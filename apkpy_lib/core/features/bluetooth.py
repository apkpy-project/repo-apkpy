"""Compiler support for ``bluetooth`` -- classic serial (SPP/RFCOMM).

Talking to hardware: an Arduino, an ESP32, a thermal printer, a scale. Lines of
text out, lines of text back.

Four calls, and the same result contract everywhere else in this library uses::

    bluetooth.devices(on_result=found)                  # (ok, json | reason)
    bluetooth.connect(address, on_result=..., on_line=...)
    bluetooth.send("LED ON")
    bluetooth.disconnect()

**``devices()`` lists paired devices, and does not scan.** That is deliberate.
An RFCOMM socket needs a bonded device anyway -- pairing asks for a PIN, and
that happens in system Settings, not in an app -- so discovery would return
things you cannot connect to. Skipping it also skips ``ACCESS_FINE_LOCATION``,
which Android used to demand for a Bluetooth scan: an app that only wants to
talk to a printer should never have to ask for the user's location, and a
manifest that asks anyway is the kind of thing the Play Store flags and people
read as spyware.

``on_line`` is called for every line the device sends, as ``(True, text)``, and
once as ``(False, reason)`` when the link drops. One callback carries both the
data and its loss, so an app cannot forget to handle the disconnect.
"""

from __future__ import annotations

import ast

__all__ = [
    "COMMAND_TYPES", "REASONS", "PERMISSIONS", "SPP_UUID", "SUCCESS", "TERMINATORS", "normalise_terminator",
    "is_call", "parse_call", "commands_use_bluetooth", "emit_command",
    "callback_interface_java", "activity_runtime_java",
    "shared_class_java",
]


COMMAND_TYPES = frozenset({
    "bluetooth_devices", "bluetooth_connect", "bluetooth_send",
    "bluetooth_disconnect",
})

# The well-known Serial Port Profile UUID. Every SPP module answers on it.
SPP_UUID = "00001101-0000-1000-8000-00805F9B34FB"

SUCCESS = "ok"

# What ends a line on the wire. Most serial sketches read to a newline, but
# plenty of hardware wants a carriage return -- an ELM327 car adapter answers
# nothing without one -- and some framed protocols want neither.
TERMINATORS = {
    "newline": "\n", "\n": "\n",
    "return": "\r", "\r": "\r", "cr": "\r",
    "crlf": "\r\n", "\r\n": "\r\n",
    "none": "", "": "",
}
DEFAULT_TERMINATOR = "\n"


def normalise_terminator(value):
    """A name or the characters themselves -> the characters."""
    if value is None:
        return DEFAULT_TERMINATOR
    raw = str(value)
    # The characters themselves first: stripping would turn a carriage return
    # into an empty string, which is a different terminator entirely.
    if raw in TERMINATORS:
        return TERMINATORS[raw]
    key = raw.strip().lower()
    if key in TERMINATORS:
        return TERMINATORS[key]
    # An explicit string nobody named: trust it, so an odd device stays
    # reachable without waiting for us to name its terminator.
    return raw


# `BLUETOOTH` stops at API 30 because 31 replaced it, and leaving it uncapped
# makes a modern install list a permission it never uses.
PERMISSIONS = (
    "BLUETOOTH|maxSdkVersion=30",
    "BLUETOOTH_CONNECT",
)

REASONS = {
    "ok": "The call did what it said.",
    "off": "Bluetooth is switched off on the phone.",
    "unsupported": "This device has no Bluetooth radio at all.",
    "denied": "The app does not have permission to use Bluetooth.",
    "not_paired": "No paired device with that address. Pair it in Settings first.",
    "unreachable": "The device is paired but did not answer. Out of range, or off.",
    "not_connected": "Nothing is connected, so there was nothing to send.",
    "lost": "The connection dropped.",
    "failed": "It did not work, for another reason.",
}


def is_call(call):
    """True for ``bluetooth.<verb>(...)`` with a verb we generate."""
    func = getattr(call, "func", None)
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "bluetooth"
        and func.attr in ("devices", "connect", "send", "disconnect")
    )


def parse_call(transpiler, call):
    """``bluetooth.<verb>(...)`` -> the command dict the emitters read."""
    verb = call.func.attr
    for permission in PERMISSIONS:
        if permission not in transpiler.declared_permissions:
            transpiler.declared_permissions.append(permission)

    command = {"type": "bluetooth_" + verb}

    result_cb = transpiler._kw(call.keywords, "on_result")
    if result_cb:
        transpiler.boolean_first_arg_callbacks.add(result_cb)
        command["callback"] = result_cb

    if verb == "connect":
        line_cb = transpiler._kw(call.keywords, "on_line")
        if line_cb:
            # (True, text) per line, (False, reason) when the link drops -- the
            # same boolean-first shape as every other callback here.
            transpiler.boolean_first_arg_callbacks.add(line_cb)
            command["line_callback"] = line_cb
        command["address"] = _first_value(transpiler, call, "address")
    elif verb == "send":
        command["text"] = _first_value(transpiler, call, "text")
        raw = transpiler._kw_node(call.keywords, "terminator")
        command["terminator"] = normalise_terminator(
            raw.value if isinstance(raw, ast.Constant) else None)

    return command


def _first_value(transpiler, call, keyword):
    """The first positional argument, or the one named ``keyword``."""
    node = None
    if call.args:
        node = call.args[0]
    else:
        node = transpiler._kw_node(call.keywords, keyword)
    if node is None:
        return {"kind": "literal", "value": ""}
    if isinstance(node, ast.Constant):
        return {"kind": "literal", "value": str(node.value)}
    if isinstance(node, ast.Name):
        constant = getattr(transpiler, "string_constants", {}).get(node.id)
        if constant is not None:
            return {"kind": "literal", "value": str(constant)}
        return {"kind": "name", "value": node.id}
    return {"kind": "expression", "value": node}


def commands_use_bluetooth(functions_map, module_init_cmds=None):
    """True when anything in the app talks to a device."""
    def _uses(cmds):
        return any((cmd.get("type") in COMMAND_TYPES) for cmd in (cmds or []))

    if _uses(module_init_cmds):
        return True
    return any(info and _uses(info.get("cmds", []))
               for info in (functions_map or {}).values())


# --- Emission --------------------------------------------------------------

def _java_string(value):
    text = "" if value is None else str(value)
    return '"%s"' % (
        text.replace("\\", "\\\\").replace('"', '\\"')
            .replace("\n", "\\n").replace("\r", "\\r")
            .replace("\t", "\\t")
    )


def _argument(value, val_to_java):
    """A parsed argument as Java: a literal, a variable, or an expression."""
    if not isinstance(value, dict):
        return _java_string(value)
    kind = value.get("kind")
    if kind == "literal":
        return _java_string(value.get("value", ""))
    if kind == "name":
        return "String.valueOf(%s)" % value["value"]
    if kind == "expression" and val_to_java is not None:
        try:
            return val_to_java(value["value"])
        except Exception:
            return '""'
    return '""'


def emit_command(lines, indent, command, val_to_java=None, functions_map=None):
    kind = command.get("type")
    callback = command.get("callback")
    handler = ("(success, value) -> pythonCallback_%s(success, value)" % callback
               if callback else "null")

    if kind == "bluetooth_devices":
        lines.append("%s_btPairedDevices(%s);" % (indent, handler))
    elif kind == "bluetooth_connect":
        line_cb = command.get("line_callback")
        line_handler = (
            "(success, value) -> pythonCallback_%s(success, value)" % line_cb
            if line_cb else "null")
        lines.append("%s_btConnect(%s, %s, %s);" % (
            indent, _argument(command.get("address"), val_to_java),
            handler, line_handler))
    elif kind == "bluetooth_send":
        lines.append("%s_btSend(%s, %s, %s);" % (
            indent, _argument(command.get("text"), val_to_java),
            _java_string(command.get("terminator", DEFAULT_TERMINATOR)), handler))
    elif kind == "bluetooth_disconnect":
        lines.append("%s_btDisconnect();" % indent)


def callback_interface_java(package):
    """The Activity's alias for the shared listener type."""
    return ("    private interface BluetoothResultCallback "
            "extends " + package + ".ApkpyBluetooth.Listener { }")


def shared_class_java(package):
    """The link itself, owned by the app rather than by a screen.

    Every screen compiles to its own Activity, and a field on one of them dies
    with it -- which is why a connection used to end the moment you navigated
    away. A ``static`` would not help either: each Activity is a different
    class, so each would get its own copy. The state has to live somewhere
    that is neither, so it lives here.

    Callbacks are posted through a Handler on the main looper rather than
    through an Activity, so nothing in here keeps a dead screen alive.
    """
    return '''package %(package)s;

public final class ApkpyBluetooth {

    public interface Listener { void onResult(boolean success, String value); }

    private static final android.os.Handler MAIN =
            new android.os.Handler(android.os.Looper.getMainLooper());

    // Written on the connect thread, read on the main one: without volatile
    // a screen can see a stale null and report not_connected on a live link.
    private static volatile android.bluetooth.BluetoothSocket sSocket;
    private static volatile java.io.OutputStream sOut;
    private static Thread sReader;
    private static volatile String sAddress = "";
    // Bumped by every disconnect, so a reader whose socket we closed knows it
    // is stale and stays quiet.
    private static volatile int sGeneration;
    // Whichever screen asked most recently. A screen re-points this by calling
    // connect() again, which costs nothing when the link is already open.
    private static Listener sLine;

    private ApkpyBluetooth() { }

    private static void post(final Listener cb, final boolean ok, final String value) {
        if (cb == null) return;
        MAIN.post(new Runnable() {
            @Override public void run() { cb.onResult(ok, value); }
        });
    }

    private static android.bluetooth.BluetoothAdapter adapter(
            android.content.Context ctx) {
        android.bluetooth.BluetoothManager manager =
                (android.bluetooth.BluetoothManager)
                        ctx.getSystemService(android.content.Context.BLUETOOTH_SERVICE);
        return manager == null ? null : manager.getAdapter();
    }

    public static String blockedReason(android.content.Context ctx) {
        android.bluetooth.BluetoothAdapter a = adapter(ctx);
        if (a == null) return "unsupported";
        if (android.os.Build.VERSION.SDK_INT >= 31
                && ctx.checkSelfPermission(
                        android.Manifest.permission.BLUETOOTH_CONNECT)
                   != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            return "denied";
        }
        if (!a.isEnabled()) return "off";
        return "%(success)s";
    }

    public static boolean isConnected() { return sOut != null; }

    public static String connectedAddress() { return sAddress; }

    /** Drop a listener whose screen is going away, without touching a newer one. */
    public static void forget(Listener onLine) {
        if (onLine != null && sLine == onLine) sLine = null;
    }

    private static String jsonEscape(String raw) {
        if (raw == null) return "";
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < raw.length(); i++) {
            char c = raw.charAt(i);
            if (c == '"' || c == '\\\\') out.append('\\\\').append(c);
            else if (c >= ' ') out.append(c);
        }
        return out.toString();
    }

    public static void devices(android.content.Context ctx, Listener cb) {
        String blocked = blockedReason(ctx);
        if (!blocked.equals("%(success)s")) { post(cb, false, blocked); return; }
        try {
            StringBuilder json = new StringBuilder("[");
            boolean first = true;
            for (android.bluetooth.BluetoothDevice device
                    : adapter(ctx).getBondedDevices()) {
                if (!first) json.append(",");
                first = false;
                String name = device.getName();
                json.append("{\\"name\\":\\"")
                    .append(jsonEscape(name == null ? device.getAddress() : name))
                    .append("\\",\\"address\\":\\"")
                    .append(jsonEscape(device.getAddress()))
                    .append("\\"}");
            }
            json.append("]");
            post(cb, true, json.toString());
        } catch (SecurityException e) {
            post(cb, false, "denied");
        } catch (Exception e) {
            post(cb, false, "failed");
        }
    }

    public static void connect(final android.content.Context ctx,
                               final String address, final Listener cb,
                               final Listener onLine) {
        String blocked = blockedReason(ctx);
        if (!blocked.equals("%(success)s")) { post(cb, false, blocked); return; }
        // Already talking to this device: adopt the new screen's callback and
        // say yes. This is what lets a link outlive a navigation -- the next
        // screen calls connect() and inherits the conversation.
        if (isConnected() && sAddress.equalsIgnoreCase(address)) {
            sLine = onLine;
            post(cb, true, "%(success)s");
            return;
        }
        disconnect();
        sLine = onLine;
        final android.content.Context app = ctx.getApplicationContext();
        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    android.bluetooth.BluetoothDevice device = null;
                    for (android.bluetooth.BluetoothDevice bonded
                            : adapter(app).getBondedDevices()) {
                        if (bonded.getAddress().equalsIgnoreCase(address)) {
                            device = bonded;
                            break;
                        }
                    }
                    if (device == null) { post(cb, false, "not_paired"); return; }
                    // Discovery, if any is running, starves the connect.
                    try { adapter(app).cancelDiscovery(); } catch (Exception ignored) { }
                    android.bluetooth.BluetoothSocket socket =
                            device.createRfcommSocketToServiceRecord(
                                    java.util.UUID.fromString("%(uuid)s"));
                    socket.connect();
                    sSocket = socket;
                    sOut = socket.getOutputStream();
                    sAddress = address;
                    startReader(socket);
                    post(cb, true, "%(success)s");
                } catch (SecurityException e) {
                    post(cb, false, "denied");
                } catch (java.io.IOException e) {
                    post(cb, false, "unreachable");
                } catch (Exception e) {
                    post(cb, false, "failed");
                }
            }
        }).start();
    }

    private static void startReader(final android.bluetooth.BluetoothSocket socket) {
        final int mine = sGeneration;
        sReader = new Thread(new Runnable() {
            @Override public void run() {
                java.io.BufferedReader reader = null;
                try {
                    reader = new java.io.BufferedReader(
                            new java.io.InputStreamReader(
                                    socket.getInputStream(), "UTF-8"));
                    String line;
                    while ((line = reader.readLine()) != null) {
                        post(sLine, true, line);
                    }
                } catch (Exception ignored) {
                } finally {
                    try { if (reader != null) reader.close(); } catch (Exception e) { }
                }
                // Only a link that ended on its own is a loss. If we closed
                // it -- disconnect(), or connecting somewhere else -- the
                // generation has moved on, and announcing "lost" would tell
                // the next screen its brand new link had died.
                if (mine == sGeneration) post(sLine, false, "lost");
            }
        });
        sReader.start();
    }

    public static void send(String text, String terminator, Listener cb) {
        if (sOut == null) { post(cb, false, "not_connected"); return; }
        try {
            sOut.write((text + terminator).getBytes("UTF-8"));
            sOut.flush();
            post(cb, true, "%(success)s");
        } catch (Exception e) {
            post(cb, false, "lost");
        }
    }

    public static void disconnect() {
        sGeneration++;
        try { if (sSocket != null) sSocket.close(); } catch (Exception ignored) { }
        sSocket = null;
        sOut = null;
        sReader = null;
        sAddress = "";
    }
}
''' % {"package": package, "success": SUCCESS, "uuid": SPP_UUID}


def activity_runtime_java(package):
    """What stays on the screen: the two prompts, and thin calls into the link."""
    return '''
    // The link itself lives in ApkpyBluetooth, so it outlives this screen.
    // What stays here are the two things only a visible screen can do: ask
    // for the permission, and offer to turn the radio on.

    private boolean _btAsked;
    private boolean _btAskedEnable;
    private Runnable _btAfterPermission;
    private BluetoothResultCallback _btMyLine;

    private final ActivityResultLauncher<String[]> _btPermissionLauncher =
            registerForActivityResult(
                    new ActivityResultContracts.RequestMultiplePermissions(),
                    granted -> {
                        Runnable next = _btAfterPermission;
                        _btAfterPermission = null;
                        if (next != null) next.run();
                    });

    private final ActivityResultLauncher<android.content.Intent> _btEnableLauncher =
            registerForActivityResult(
                    new ActivityResultContracts.StartActivityForResult(),
                    result -> {
                        Runnable next = _btAfterPermission;
                        _btAfterPermission = null;
                        if (next != null) next.run();
                    });

    private String[] _btMissingPermissions() {
        if (android.os.Build.VERSION.SDK_INT < 31) return new String[0];
        java.util.ArrayList<String> missing = new java.util.ArrayList<>();
        if (checkSelfPermission(android.Manifest.permission.BLUETOOTH_CONNECT)
                != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            missing.add(android.Manifest.permission.BLUETOOTH_CONNECT);
        }
        return missing.toArray(new String[0]);
    }

    private boolean _btReady(Runnable retry) {
        String[] missing = _btMissingPermissions();
        if (missing.length > 0) {
            // Asked and refused: fall through so the caller reports "denied"
            // instead of reopening the dialog on every tap.
            if (_btAsked) return true;
            _btAsked = true;
            _btAfterPermission = retry;
            _btPermissionLauncher.launch(missing);
            return false;
        }
        // Permission first, then the radio: the enable prompt itself needs
        // BLUETOOTH_CONNECT on API 31+.
        android.bluetooth.BluetoothManager _m =
                (android.bluetooth.BluetoothManager) getSystemService(BLUETOOTH_SERVICE);
        android.bluetooth.BluetoothAdapter _a = _m == null ? null : _m.getAdapter();
        if (_a != null && !_a.isEnabled()) {
            if (_btAskedEnable) return true;
            _btAskedEnable = true;
            _btAfterPermission = retry;
            try {
                _btEnableLauncher.launch(new android.content.Intent(
                        android.bluetooth.BluetoothAdapter.ACTION_REQUEST_ENABLE));
                return false;
            } catch (Exception e) {
                _btAfterPermission = null;
            }
        }
        return true;
    }

    private void _btPairedDevices(final BluetoothResultCallback cb) {
        if (!_btReady(new Runnable() {
            @Override public void run() { _btPairedDevices(cb); }
        })) return;
        %(package)s.ApkpyBluetooth.devices(this, cb);
    }

    private void _btConnect(final String address, final BluetoothResultCallback cb,
                            final BluetoothResultCallback onLine) {
        if (!_btReady(new Runnable() {
            @Override public void run() { _btConnect(address, cb, onLine); }
        })) return;
        _btMyLine = onLine;
        %(package)s.ApkpyBluetooth.connect(this, address, cb, onLine);
    }

    private void _btSend(String text, String terminator,
                         BluetoothResultCallback cb) {
        %(package)s.ApkpyBluetooth.send(text, terminator, cb);
    }

    private void _btDisconnect() {
        %(package)s.ApkpyBluetooth.disconnect();
    }

    // Only the callback is dropped when the screen dies. Closing the link here
    // is what used to end the conversation the moment you changed screen.
    private void _btReleaseListener() {
        %(package)s.ApkpyBluetooth.forget(_btMyLine);
        _btMyLine = null;
    }
''' % {"package": package}
