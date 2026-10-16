"""Compiler support for ``ble`` -- Bluetooth Low Energy.

The same four verbs as classic serial, over the other radio::

    ble.scan(on_result=found, seconds=8)
    ble.connect(address, on_result=..., on_line=...)
    ble.send("LED ON")
    ble.disconnect()

**It defaults to the Nordic UART Service**, which is what an ESP32, a
micro:bit or an HM-10 module exposes: one characteristic the phone writes to
and one it subscribes to, carrying lines of text. That is BLE's answer to a
serial port, and it is what almost every hobby board speaks -- so the common
case needs no UUIDs at all. A device with its own profile names them:

    ble.connect(address, service="180d", write_uuid="2a39", notify_uuid="2a37")

Short 16-bit UUIDs are expanded against the Bluetooth base UUID, so ``180d``
and the full ``0000180d-0000-1000-8000-00805f9b34fb`` mean the same thing.

**Unlike classic serial, this one must scan.** BLE devices advertise rather
than pair, so there is no bonded list to read. That costs a permission:
``BLUETOOTH_SCAN`` on API 31+, and ``ACCESS_FINE_LOCATION`` below it, because
Android used a scan's results as a location signal. Both are declared as
narrowly as the platform allows -- ``neverForLocation`` on the scan, and the
location grant capped at API 30 -- so a modern install never sees a location
request.
"""

from __future__ import annotations

import ast

from .bluetooth import (  # one vocabulary, two radios
    DEFAULT_TERMINATOR, TERMINATORS, normalise_terminator,
)

__all__ = [
    "COMMAND_TYPES", "REASONS", "PERMISSIONS", "SUCCESS", "UART",
    "TERMINATORS", "normalise_terminator",
    "expand_uuid", "is_call", "parse_call", "commands_use_ble", "emit_command",
    "callback_interface_java", "activity_runtime_java",
    "shared_class_java",
]


COMMAND_TYPES = frozenset({
    "ble_scan", "ble_connect", "ble_send", "ble_disconnect",
})

SUCCESS = "ok"

# The Nordic UART Service, and the descriptor every notification needs.
UART = {
    "service": "6e400001-b5a3-f393-e0a9-e50e24dcca9e",
    "write": "6e400002-b5a3-f393-e0a9-e50e24dcca9e",   # phone -> device
    "notify": "6e400003-b5a3-f393-e0a9-e50e24dcca9e",  # device -> phone
}
CCCD = "00002902-0000-1000-8000-00805f9b34fb"

# The scan is what forces the location grant, so it is capped where the
# platform stopped requiring it. `neverForLocation` tells Android 12+ that the
# app does not derive position from the results, which is true.
PERMISSIONS = (
    "BLUETOOTH|maxSdkVersion=30",
    "BLUETOOTH_ADMIN|maxSdkVersion=30",
    "ACCESS_FINE_LOCATION|maxSdkVersion=30",
    "BLUETOOTH_SCAN|usesPermissionFlags=neverForLocation",
    "BLUETOOTH_CONNECT",
)

REASONS = {
    "ok": "The call did what it said.",
    "off": "Bluetooth is switched off on the phone.",
    "unsupported": "This device has no Bluetooth Low Energy radio.",
    "denied": "The app does not have permission to scan or connect.",
    "not_found": "Nothing answered at that address while scanning.",
    "unreachable": "The device did not accept the connection.",
    "no_service": "Connected, but the device does not expose that service.",
    "not_connected": "Nothing is connected, so there was nothing to send.",
    "lost": "The connection dropped.",
    "failed": "It did not work, for another reason.",
}

_BASE_UUID = "0000%s-0000-1000-8000-00805f9b34fb"


def expand_uuid(value, default=None):
    """A 16-bit shorthand or a full UUID, as a full UUID.

    ``180d`` and ``0000180d-0000-1000-8000-00805f9b34fb`` are the same service;
    accepting only the long form would make every call unreadable.
    """
    text = str(value or "").strip().lower().replace("0x", "")
    if not text:
        return default
    if len(text) == 4:
        return _BASE_UUID % text
    if len(text) == 8:
        return "%s-0000-1000-8000-00805f9b34fb" % text
    return text


def is_call(call):
    func = getattr(call, "func", None)
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "ble"
        and func.attr in ("scan", "connect", "send", "disconnect")
    )


def _literal(transpiler, node, default=None):
    if node is None:
        return default
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        found = getattr(transpiler, "string_constants", {}).get(node.id)
        return default if found is None else found
    return default


def parse_call(transpiler, call):
    verb = call.func.attr
    for permission in PERMISSIONS:
        if permission not in transpiler.declared_permissions:
            transpiler.declared_permissions.append(permission)

    command = {"type": "ble_" + verb}

    result_cb = transpiler._kw(call.keywords, "on_result")
    if result_cb:
        transpiler.boolean_first_arg_callbacks.add(result_cb)
        command["callback"] = result_cb

    if verb == "scan":
        seconds = _literal(transpiler, transpiler._kw_node(call.keywords, "seconds"), 8)
        try:
            seconds = max(1, min(60, int(float(seconds))))
        except (TypeError, ValueError):
            seconds = 8
        command["seconds"] = seconds
    elif verb == "connect":
        line_cb = transpiler._kw(call.keywords, "on_line")
        if line_cb:
            transpiler.boolean_first_arg_callbacks.add(line_cb)
            command["line_callback"] = line_cb
        command["address"] = _argument_node(transpiler, call, "address")
        command["service"] = expand_uuid(
            _literal(transpiler, transpiler._kw_node(call.keywords, "service")),
            UART["service"])
        command["write_uuid"] = expand_uuid(
            _literal(transpiler, transpiler._kw_node(call.keywords, "write_uuid")),
            UART["write"])
        command["notify_uuid"] = expand_uuid(
            _literal(transpiler, transpiler._kw_node(call.keywords, "notify_uuid")),
            UART["notify"])
    elif verb == "send":
        command["text"] = _argument_node(transpiler, call, "text")
        raw = transpiler._kw_node(call.keywords, "terminator")
        command["terminator"] = normalise_terminator(
            raw.value if isinstance(raw, ast.Constant) else None)

    return command


def _argument_node(transpiler, call, keyword):
    node = call.args[0] if call.args else transpiler._kw_node(call.keywords, keyword)
    if node is None:
        return {"kind": "literal", "value": ""}
    if isinstance(node, ast.Constant):
        return {"kind": "literal", "value": str(node.value)}
    if isinstance(node, ast.Name):
        found = getattr(transpiler, "string_constants", {}).get(node.id)
        if found is not None:
            return {"kind": "literal", "value": str(found)}
        return {"kind": "name", "value": node.id}
    return {"kind": "expression", "value": node}


def commands_use_ble(functions_map, module_init_cmds=None):
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

    if kind == "ble_scan":
        lines.append("%s_bleScan(%d, %s);" % (
            indent, int(command.get("seconds", 8)), handler))
    elif kind == "ble_connect":
        line_cb = command.get("line_callback")
        line_handler = (
            "(success, value) -> pythonCallback_%s(success, value)" % line_cb
            if line_cb else "null")
        lines.append("%s_bleConnect(%s, %s, %s, %s, %s, %s);" % (
            indent,
            _argument(command.get("address"), val_to_java),
            _java_string(command.get("service")),
            _java_string(command.get("write_uuid")),
            _java_string(command.get("notify_uuid")),
            handler, line_handler))
    elif kind == "ble_send":
        lines.append("%s_bleSend(%s, %s, %s);" % (
            indent, _argument(command.get("text"), val_to_java),
            _java_string(command.get("terminator", DEFAULT_TERMINATOR)), handler))
    elif kind == "ble_disconnect":
        lines.append("%s_bleDisconnect();" % indent)


def callback_interface_java(package):
    """The Activity's alias for the shared listener type."""
    return ("    private interface BleResultCallback "
            "extends " + package + ".ApkpyBle.Listener { }")


def shared_class_java(package):
    """The GATT link, owned by the app rather than by a screen.

    Same reasoning as the classic radio: a field on one Activity dies with it,
    and a ``static`` would be per-class because every screen is its own class.
    """
    return '''package %(package)s;

public final class ApkpyBle {

    public interface Listener { void onResult(boolean success, String value); }

    private static final android.os.Handler MAIN =
            new android.os.Handler(android.os.Looper.getMainLooper());

    // GATT callbacks arrive on binder threads and screens read these on the
    // main one, so every field that crosses is volatile.
    private static volatile android.bluetooth.BluetoothGatt sGatt;
    private static volatile android.bluetooth.BluetoothGattCharacteristic sWrite;
    private static volatile android.bluetooth.le.ScanCallback sScan;
    private static volatile String sAddress = "";
    private static volatile Listener sLine;
    // Bumped by every connect and disconnect, so a timeout armed for an older
    // attempt cannot tear down a newer one.
    private static volatile int sGeneration;

    private static final java.util.LinkedHashMap<String, String> SEEN =
            new java.util.LinkedHashMap<>();
    // GATT allows one outstanding operation, so writes wait their turn.
    private static final java.util.ArrayDeque<byte[]> QUEUE =
            new java.util.ArrayDeque<>();
    private static volatile boolean sWriting;
    // Whether the current attempt has reached a verdict, so the timeout knows
    // there is still nothing to report.
    private static volatile boolean sSettled;

    private ApkpyBle() { }

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
        if (!ctx.getPackageManager().hasSystemFeature(
                android.content.pm.PackageManager.FEATURE_BLUETOOTH_LE)) {
            return "unsupported";
        }
        if (android.os.Build.VERSION.SDK_INT >= 31) {
            if (ctx.checkSelfPermission(android.Manifest.permission.BLUETOOTH_SCAN)
                    != android.content.pm.PackageManager.PERMISSION_GRANTED
                || ctx.checkSelfPermission(
                        android.Manifest.permission.BLUETOOTH_CONNECT)
                    != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                return "denied";
            }
        } else if (ctx.checkSelfPermission(
                android.Manifest.permission.ACCESS_FINE_LOCATION)
                != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            // Below API 31 a scan without this returns zero results and no
            // error, which reads as "nothing is nearby".
            return "denied";
        }
        if (!a.isEnabled()) return "off";
        return "%(success)s";
    }

    public static boolean isConnected() { return sWrite != null; }

    public static String connectedAddress() { return sAddress; }

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

    public static void scan(final android.content.Context ctx, int seconds,
                            final Listener cb) {
        String blocked = blockedReason(ctx);
        if (!blocked.equals("%(success)s")) { post(cb, false, blocked); return; }
        final android.bluetooth.le.BluetoothLeScanner scanner =
                adapter(ctx).getBluetoothLeScanner();
        if (scanner == null) { post(cb, false, "off"); return; }
        final android.content.Context app = ctx.getApplicationContext();
        stopScan(app);
        SEEN.clear();
        sScan = new android.bluetooth.le.ScanCallback() {
            @Override
            public void onScanResult(int type, android.bluetooth.le.ScanResult result) {
                try {
                    android.bluetooth.BluetoothDevice device = result.getDevice();
                    String name = device.getName();
                    if (name == null && result.getScanRecord() != null) {
                        name = result.getScanRecord().getDeviceName();
                    }
                    // A nameless device is still connectable, and hiding it
                    // would hide most beacons.
                    SEEN.put(device.getAddress(),
                             name == null ? device.getAddress() : name);
                } catch (SecurityException ignored) { }
            }

            @Override
            public void onScanFailed(int errorCode) {
                stopScan(app);
                post(cb, false, "failed");
            }
        };
        try {
            scanner.startScan(sScan);
        } catch (SecurityException e) {
            post(cb, false, "denied");
            return;
        }
        MAIN.postDelayed(new Runnable() {
            @Override public void run() {
                stopScan(app);
                StringBuilder json = new StringBuilder("[");
                boolean first = true;
                for (java.util.Map.Entry<String, String> entry : SEEN.entrySet()) {
                    if (!first) json.append(",");
                    first = false;
                    json.append("{\\"name\\":\\"")
                        .append(jsonEscape(entry.getValue()))
                        .append("\\",\\"address\\":\\"")
                        .append(jsonEscape(entry.getKey()))
                        .append("\\"}");
                }
                json.append("]");
                post(cb, true, json.toString());
            }
        }, seconds * 1000L);
    }

    private static void stopScan(android.content.Context ctx) {
        if (sScan == null) return;
        try {
            android.bluetooth.BluetoothAdapter a = adapter(ctx);
            android.bluetooth.le.BluetoothLeScanner scanner =
                    a == null ? null : a.getBluetoothLeScanner();
            if (scanner != null) scanner.stopScan(sScan);
        } catch (Exception ignored) { }
        sScan = null;
    }

    public static void connect(final android.content.Context ctx,
                               final String address, final String serviceUuid,
                               final String writeUuid, final String notifyUuid,
                               final Listener cb, final Listener onLine) {
        String blocked = blockedReason(ctx);
        if (!blocked.equals("%(success)s")) { post(cb, false, blocked); return; }
        // Already talking to this device: adopt the new screen's callback. This
        // is what lets the conversation outlive a navigation.
        if (isConnected() && sAddress.equalsIgnoreCase(address)) {
            sLine = onLine;
            post(cb, true, "%(success)s");
            return;
        }
        final android.content.Context app = ctx.getApplicationContext();
        stopScan(app);
        disconnect();
        sLine = onLine;
        final android.bluetooth.BluetoothDevice device;
        try {
            device = adapter(app).getRemoteDevice(address);
        } catch (Exception e) {
            post(cb, false, "not_found");
            return;
        }
        sSettled = false;
        final int mine = ++sGeneration;
        // connectGatt to a device that is not there never calls back at all,
        // so without this the app would wait forever.
        MAIN.postDelayed(new Runnable() {
            @Override public void run() {
                // A timeout armed for an attempt that has since been replaced
                // would tear down the link the app is now using.
                if (sSettled || mine != sGeneration) return;
                sSettled = true;
                disconnect();
                post(cb, false, "unreachable");
            }
        }, 15000L);
        try {
            sGatt = device.connectGatt(app, false,
                    new android.bluetooth.BluetoothGattCallback() {
                @Override
                public void onConnectionStateChange(
                        android.bluetooth.BluetoothGatt gatt, int status, int newState) {
                    if (newState == android.bluetooth.BluetoothProfile.STATE_CONNECTED) {
                        try { gatt.discoverServices(); }
                        catch (SecurityException e) { post(cb, false, "denied"); }
                    } else if (newState
                               == android.bluetooth.BluetoothProfile.STATE_DISCONNECTED) {
                        boolean everReady = sWrite != null;
                        sSettled = true;
                        sWrite = null;
                        sAddress = "";
                        // A dropped link left the client open. Android allows
                        // a limited number of them per app, so leaking one per
                        // drop eventually breaks BLE everywhere in the app.
                        try { gatt.close(); } catch (Exception ignored) { }
                        if (gatt == sGatt) sGatt = null;
                        synchronized (QUEUE) { QUEUE.clear(); sWriting = false; }
                        // Before the service was found this is a refused
                        // connection; after it, a link that dropped.
                        if (!everReady) post(cb, false, "unreachable");
                        else post(sLine, false, "lost");
                    }
                }

                @Override
                public void onServicesDiscovered(
                        android.bluetooth.BluetoothGatt gatt, int status) {
                    try {
                        sSettled = true;
                        android.bluetooth.BluetoothGattService service =
                                gatt.getService(java.util.UUID.fromString(serviceUuid));
                        if (service == null) { post(cb, false, "no_service"); return; }
                        sWrite = service.getCharacteristic(
                                java.util.UUID.fromString(writeUuid));
                        android.bluetooth.BluetoothGattCharacteristic notify =
                                service.getCharacteristic(
                                        java.util.UUID.fromString(notifyUuid));
                        if (notify != null) {
                            gatt.setCharacteristicNotification(notify, true);
                            // Setting the flag locally is not enough: the device
                            // only starts sending once its CCCD is written.
                            android.bluetooth.BluetoothGattDescriptor cccd =
                                    notify.getDescriptor(
                                            java.util.UUID.fromString("%(cccd)s"));
                            if (cccd != null) {
                                cccd.setValue(android.bluetooth.BluetoothGattDescriptor
                                        .ENABLE_NOTIFICATION_VALUE);
                                gatt.writeDescriptor(cccd);
                            }
                        }
                        if (sWrite == null && notify == null) {
                            post(cb, false, "no_service");
                            return;
                        }
                        sAddress = address;
                        post(cb, true, "%(success)s");
                    } catch (SecurityException e) {
                        post(cb, false, "denied");
                    } catch (Exception e) {
                        post(cb, false, "failed");
                    }
                }

                @Override
                public void onCharacteristicWrite(
                        android.bluetooth.BluetoothGatt gatt,
                        android.bluetooth.BluetoothGattCharacteristic characteristic,
                        int status) {
                    synchronized (QUEUE) { sWriting = false; }
                    pump();
                }

                @Override
                public void onCharacteristicChanged(
                        android.bluetooth.BluetoothGatt gatt,
                        android.bluetooth.BluetoothGattCharacteristic characteristic) {
                    byte[] value = characteristic.getValue();
                    if (value == null) return;
                    try {
                        post(sLine, true, new String(value, "UTF-8").trim());
                    } catch (Exception ignored) { }
                }
            });
        } catch (SecurityException e) {
            post(cb, false, "denied");
        }
    }

    public static void send(String text, String terminator, Listener cb) {
        if (sGatt == null || sWrite == null) {
            post(cb, false, "not_connected");
            return;
        }
        try {
            byte[] payload = (text + terminator).getBytes("UTF-8");
            synchronized (QUEUE) { QUEUE.add(payload); }
            pump();
            // "ok" means accepted for sending, not delivered: BLE gives no
            // end-to-end receipt, and pretending otherwise would be a lie.
            post(cb, true, "%(success)s");
        } catch (Exception e) {
            post(cb, false, "lost");
        }
    }

    private static void pump() {
        byte[] next;
        synchronized (QUEUE) {
            if (sWriting || QUEUE.isEmpty()) return;
            next = QUEUE.poll();
            sWriting = true;
        }
        try {
            sWrite.setValue(next);
            if (!sGatt.writeCharacteristic(sWrite)) {
                synchronized (QUEUE) { sWriting = false; }
            }
        } catch (Exception e) {
            synchronized (QUEUE) { sWriting = false; }
        }
    }

    public static void disconnect() {
        sGeneration++;
        synchronized (QUEUE) { QUEUE.clear(); sWriting = false; }
        try {
            if (sGatt != null) { sGatt.disconnect(); sGatt.close(); }
        } catch (Exception ignored) { }
        sGatt = null;
        sWrite = null;
        sAddress = "";
    }
}
''' % {"package": package, "success": SUCCESS, "cccd": CCCD}


def activity_runtime_java(package):
    """What stays on the screen: the two prompts, and thin calls into the link."""
    return '''
    // The link lives in ApkpyBle, so it outlives this screen. What stays here
    // are the two things only a visible screen can do: ask for the permission,
    // and offer to turn the radio on.

    private boolean _bleAsked;
    private boolean _bleAskedEnable;
    private Runnable _bleAfterPermission;
    private BleResultCallback _bleMyLine;

    private final ActivityResultLauncher<String[]> _blePermissionLauncher =
            registerForActivityResult(
                    new ActivityResultContracts.RequestMultiplePermissions(),
                    granted -> {
                        Runnable next = _bleAfterPermission;
                        _bleAfterPermission = null;
                        if (next != null) next.run();
                    });

    private final ActivityResultLauncher<android.content.Intent> _bleEnableLauncher =
            registerForActivityResult(
                    new ActivityResultContracts.StartActivityForResult(),
                    result -> {
                        Runnable next = _bleAfterPermission;
                        _bleAfterPermission = null;
                        if (next != null) next.run();
                    });

    private String[] _bleMissingPermissions() {
        java.util.ArrayList<String> missing = new java.util.ArrayList<>();
        if (android.os.Build.VERSION.SDK_INT >= 31) {
            if (checkSelfPermission(android.Manifest.permission.BLUETOOTH_SCAN)
                    != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                missing.add(android.Manifest.permission.BLUETOOTH_SCAN);
            }
            if (checkSelfPermission(android.Manifest.permission.BLUETOOTH_CONNECT)
                    != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                missing.add(android.Manifest.permission.BLUETOOTH_CONNECT);
            }
        } else if (checkSelfPermission(
                android.Manifest.permission.ACCESS_FINE_LOCATION)
                != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            missing.add(android.Manifest.permission.ACCESS_FINE_LOCATION);
        }
        return missing.toArray(new String[0]);
    }

    private boolean _bleReady(Runnable retry) {
        String[] missing = _bleMissingPermissions();
        if (missing.length > 0) {
            if (_bleAsked) return true;
            _bleAsked = true;
            _bleAfterPermission = retry;
            _blePermissionLauncher.launch(missing);
            return false;
        }
        // Permission first, then the radio: the enable prompt needs
        // BLUETOOTH_CONNECT on API 31+.
        android.bluetooth.BluetoothManager _m =
                (android.bluetooth.BluetoothManager) getSystemService(BLUETOOTH_SERVICE);
        android.bluetooth.BluetoothAdapter _a = _m == null ? null : _m.getAdapter();
        if (_a != null && !_a.isEnabled()) {
            if (_bleAskedEnable) return true;
            _bleAskedEnable = true;
            _bleAfterPermission = retry;
            try {
                _bleEnableLauncher.launch(new android.content.Intent(
                        android.bluetooth.BluetoothAdapter.ACTION_REQUEST_ENABLE));
                return false;
            } catch (Exception e) {
                _bleAfterPermission = null;
            }
        }
        return true;
    }

    private void _bleScan(final int seconds, final BleResultCallback cb) {
        if (!_bleReady(new Runnable() {
            @Override public void run() { _bleScan(seconds, cb); }
        })) return;
        %(package)s.ApkpyBle.scan(this, seconds, cb);
    }

    private void _bleConnect(final String address, final String serviceUuid,
                             final String writeUuid, final String notifyUuid,
                             final BleResultCallback cb,
                             final BleResultCallback onLine) {
        if (!_bleReady(new Runnable() {
            @Override public void run() {
                _bleConnect(address, serviceUuid, writeUuid, notifyUuid, cb, onLine);
            }
        })) return;
        _bleMyLine = onLine;
        %(package)s.ApkpyBle.connect(this, address, serviceUuid, writeUuid,
                                     notifyUuid, cb, onLine);
    }

    private void _bleSend(String text, String terminator, BleResultCallback cb) {
        %(package)s.ApkpyBle.send(text, terminator, cb);
    }

    private void _bleDisconnect() {
        %(package)s.ApkpyBle.disconnect();
    }

    private void _bleReleaseListener() {
        %(package)s.ApkpyBle.forget(_bleMyLine);
        _bleMyLine = null;
    }
''' % {"package": package}
