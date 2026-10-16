# -*- coding: utf-8 -*-
"""Compiler support for ``sensors`` and ``battery`` -- what the phone feels.

    from apkpy_lib import button, label, sensors

    def turned(degrees):
        heading.set_value(degrees + " deg")

    sensors.compass(on_change=turned)

**A sensor is a stream, not an answer.** Every other API in ApkPy is asked once
and replies once. These fire tens of times a second, for as long as they are
registered, and that difference is the whole design:

* **They stop when the screen stops.** Registering in ``onResume`` and
  unregistering in ``onPause`` is not tidiness, it is the difference between an
  app and a battery complaint. A ``SensorEventListener`` left registered keeps
  the sensor hub awake behind a screen nobody is looking at. So these are
  Activity methods with a lifecycle, and deliberately NOT a static class that
  outlives screens the way the torch is -- the torch should survive navigation,
  a sensor should not.

* **They only speak when something changed.** A light sensor at
  ``SENSOR_DELAY_UI`` reports about sixteen times a second, and the same lux
  sixteen times a second is not news. :data:`THRESHOLDS` is how much has to
  change before the app hears about it, and it is read by both runtimes so
  neither can be chattier than the other.

**Names for what people want, not for what the chip is called.** ``shake`` is
the accelerometer with the arithmetic already done; ``compass`` is the rotation
vector turned into degrees. Handing an app three raw axes and letting every
author invent their own shake detector would guarantee that no two ApkPy apps
shake alike.

**battery is not a sensor** and travels here anyway, because it is asked for in
the same breath and needs no permission either. ``battery.level()``,
``battery.charging()`` and ``battery.saver()`` read the state the phone already
publishes; nothing is registered and nothing has to be stopped.

**Permissions:** only ``steps`` needs one -- ``ACTIVITY_RECOGNITION``, and only
from Android 10. Raw accelerometer and gyroscope streams use UI sampling,
not high-rate acquisition. Pressure is atmospheric pressure, not altitude.
"""

from __future__ import annotations

import ast
import math
import struct

__all__ = [
    "SENSORS", "RATES", "THRESHOLDS", "REASONS", "BATTERY_VERBS",
    "SHAKE_G", "SHAKE_GAP_MS", "VERBS", "VALUE_VERBS", "COMMAND_TYPES",
    "format_value", "shake_detected", "passes_threshold",
    "is_call", "is_value_call", "parse_call", "commands_use_sensors",
    "reads_sensors", "emit_command", "value_java", "condition_java",
    "activity_runtime_java", "manifest_features", "permissions_needed",
    "sensors_used", "VECTOR_SENSORS", "normalize_vector",
]


COMMAND_TYPES = frozenset({"sensor_watch", "sensor_stop"})

# ── The table both runtimes read ─────────────────────────────────────────────
#
# `android` is the Sensor.TYPE_* constant, `rate` a key of RATES, `args` how
# many values the callback receives, and `feature` the <uses-feature> name.
SENSORS = {
    "shake": {
        "android": "TYPE_ACCELEROMETER",
        "rate": "GAME",
        "args": 0,
        "feature": "android.hardware.sensor.accelerometer",
        "permission": None,
    },
    "compass": {
        "android": "TYPE_ROTATION_VECTOR",
        "rate": "UI",
        "args": 1,
        "feature": "android.hardware.sensor.compass",
        "permission": None,
    },
    "steps": {
        "android": "TYPE_STEP_COUNTER",
        "rate": "NORMAL",
        "args": 1,
        "feature": "android.hardware.sensor.stepcounter",
        "permission": "ACTIVITY_RECOGNITION",
    },
    "light": {
        "android": "TYPE_LIGHT",
        "rate": "UI",
        "args": 1,
        "feature": "android.hardware.sensor.light",
        "permission": None,
    },
    "proximity": {
        "android": "TYPE_PROXIMITY",
        "rate": "UI",
        "args": 1,
        "feature": "android.hardware.sensor.proximity",
        "permission": None,
    },
    "accelerometer": {
        "android": "TYPE_ACCELEROMETER", "rate": "UI", "args": 1,
        "feature": "android.hardware.sensor.accelerometer", "permission": None,
    },
    "gyroscope": {
        "android": "TYPE_GYROSCOPE", "rate": "UI", "args": 1,
        "feature": "android.hardware.sensor.gyroscope", "permission": None,
    },
    "pressure": {
        "android": "TYPE_PRESSURE", "rate": "UI", "args": 1,
        "feature": "android.hardware.sensor.barometer", "permission": None,
    },
}

VECTOR_SENSORS = frozenset({"accelerometer", "gyroscope"})

# SensorManager.SENSOR_DELAY_*, and the microseconds Android maps them to.
# The numbers are here so the Previewer can tick at the same speed instead of
# guessing -- a stand-in that reports faster than the phone teaches the wrong
# thing about how often a screen will redraw.
RATES = {
    "FASTEST": 0,
    "GAME": 20000,
    "UI": 66667,
    "NORMAL": 200000,
}

# How much has to change before the app is told. Chosen in the unit each
# sensor reports: degrees, lux, steps, and near/far as 0 or 1.
THRESHOLDS = {
    "compass": 1.0,
    "light": 1.0,
    "steps": 1.0,
    "proximity": 0.5,
    "accelerometer": 0.05,  # m/s2, including gravity
    "gyroscope": 0.01,     # rad/s, not an angle
    "pressure": 0.1,       # hPa
}

# A shake, in g. 2.7 is the long-standing Android figure: high enough that
# putting the phone down or walking with it does not register, low enough that
# a deliberate flick of the wrist does.
SHAKE_G = 2.7
SHAKE_GAP_MS = 800

VERBS = tuple(SENSORS) + ("stop",)
VALUE_VERBS = ("available",)
BATTERY_VERBS = ("level", "charging", "saver")

REASONS = {
    "ok": "The sensor is registered and reporting.",
    "no_sensor": "This phone does not have that sensor.",
    "permission_required": "Step counting needs the activity permission.",
    "permission_denied": "The person said no to the activity permission.",
    "stopped": "The watch was stopped, by the app or by leaving the screen.",
}


# ── The one formatting rule ──────────────────────────────────────────────────

def format_value(name, value):
    """The text one reading becomes.

    Written once and transcribed into Java, because a reading that reads
    ``12`` in the Previewer and ``12.0`` on the phone is a bug an app author
    would find by shipping.

    ``proximity`` arrives here already normalised to ``1`` near / ``0`` far.
    The raw sensor reports a *distance*, so small means near and the sensor's
    own maximum means far -- reading that raw number as a boolean inverts it,
    and a phone flat on a desk claims something is touching it. The Java side
    normalises before formatting for exactly that reason.
    """
    if name in VECTOR_SENSORS:
        axes = normalize_vector(value)
        # SensorEvent uses float32. Match that precision and Java Math.rint
        # before formatting; locale-independent JSON, with numeric fields.
        parts = ['"%s":%.4f' % (axis, round(number * 10000) / 10000)
                 for axis, number in zip(("x", "y", "z"), axes)]
        return "{" + ",".join(parts) + "}"
    if name == "proximity":
        return "True" if float(value) >= 0.5 else "False"
    if name in ("compass", "steps"):
        return str(int(round(float(value))))
    text = "%.1f" % float(value)
    return text[:-2] if text.endswith(".0") else text


def passes_threshold(name, previous, current):
    """Whether this reading is different enough to be worth reporting."""
    if name in VECTOR_SENSORS:
        current = normalize_vector(current)
        if previous is None:
            return True
        previous = normalize_vector(previous)
        threshold = struct.unpack("f", struct.pack("f", THRESHOLDS[name]))[0]
        return max(abs(a - b) for a, b in zip(current, previous)) >= threshold
    if previous is None:
        return True
    return abs(float(current) - float(previous)) >= THRESHOLDS.get(name, 0.0)


def normalize_vector(value):
    """Validate and copy a three-axis reading using SensorEvent precision."""
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise ValueError("A sensor vector needs exactly three finite values: x, y, z")
    try:
        axes = tuple(struct.unpack("f", struct.pack("f", float(v)))[0] for v in value)
    except (TypeError, ValueError, OverflowError, struct.error):
        raise ValueError("Sensor axes must be finite numbers") from None
    if not all(math.isfinite(v) for v in axes):
        raise ValueError("Sensor axes must be finite numbers")
    return axes


def shake_detected(x, y, z):
    """Whether these three axes add up to a shake.

    ``9.80665`` is ``SensorManager.GRAVITY_EARTH`` spelled out, so the Python
    side does not have to import Android to agree with it.
    """
    force = ((float(x) ** 2 + float(y) ** 2 + float(z) ** 2) ** 0.5) / 9.80665
    return force > SHAKE_G


# ── Parsing ──────────────────────────────────────────────────────────────────

def _on(call, holder, names):
    func = getattr(call, "func", None)
    return (
        isinstance(func, ast.Attribute)
        and func.attr in names
        and isinstance(func.value, ast.Name)
        and func.value.id == holder
    )


def is_call(call):
    """True for the ``sensors.*`` verbs that start or stop a stream."""
    return _on(call, "sensors", VERBS)


def is_value_call(node):
    """True for ``sensors.available(...)`` and every ``battery.*``."""
    if not isinstance(node, ast.Call):
        return False
    return _on(node, "sensors", VALUE_VERBS) or _on(node, "battery", BATTERY_VERBS)


def parse_call(transpiler, call):
    """``sensors.compass(on_change=...)`` -> the command dict emitters read."""
    verb = call.func.attr
    if verb == "stop":
        which = None
        if call.args:
            which = transpiler._literal_str(call.args[0]) \
                if hasattr(transpiler, "_literal_str") else None
            if which is None and isinstance(call.args[0], ast.Constant):
                which = str(call.args[0].value)
        if not call.args:
            for keyword in call.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                    which = keyword.value.value
        return {"type": "sensor_stop", "sensor": which}

    permission = SENSORS.get(verb, {}).get("permission")
    if permission and permission not in transpiler.declared_permissions:
        # Declared from here rather than by the app author, the way the camera
        # is: an app that counts steps needs this and should not have to know
        # that Android 10 changed its mind about it.
        transpiler.declared_permissions.append(permission)

    callback = (transpiler._kw(call.keywords, "on_change")
                or transpiler._kw(call.keywords, "on_shake"))
    if callback and verb == "proximity":
        # near/far is a boolean everywhere else in the app, so `if near:` has
        # to compile to `if (near)` and not to a comparison against "True".
        transpiler.boolean_first_arg_callbacks.add(callback)
    return {"type": "sensor_watch", "sensor": verb, "callback": callback}


def _walk_cmds(functions_map, module_init_cmds=None):
    for cmd in module_init_cmds or []:
        if isinstance(cmd, dict):
            yield cmd
    for info in (functions_map or {}).values():
        for cmd in (info or {}).get("cmds", []) or []:
            if isinstance(cmd, dict):
                yield cmd


def commands_use_sensors(functions_map, module_init_cmds=None):
    """True when anything in the app watches or stops a sensor."""
    for cmd in _walk_cmds(functions_map, module_init_cmds):
        if cmd.get("type") in COMMAND_TYPES:
            return True
    return False


def sensors_used(functions_map, module_init_cmds=None):
    """Which sensors this app actually watches, for the manifest.

    An app that only shakes should not tell the store it wants a barometer.
    """
    found = []
    for cmd in _walk_cmds(functions_map, module_init_cmds):
        name = cmd.get("sensor")
        if cmd.get("type") == "sensor_watch" and name in SENSORS \
                and name not in found:
            found.append(name)
    return found


def reads_sensors(tree):
    """True when the source asks ``sensors.available()`` or ``battery.*``.

    These are expressions, never commands, so the command walk above cannot
    see them -- and an app whose only mention is ``if battery.charging():``
    would otherwise compile to a call on methods that were never written.
    """
    for node in ast.walk(tree):
        if is_value_call(node):
            return True
    return False


def uses_battery(tree):
    """True when the source reads any ``battery.*`` value."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _on(node, "battery", BATTERY_VERBS):
            return True
    return False


# ── Emission ─────────────────────────────────────────────────────────────────

def emit_command(lines, indent, command, val_to_java=None, functions_map=None,
                 scope="activity"):
    """Emit one ``sensors.*`` statement."""
    if command.get("type") == "sensor_stop":
        which = command.get("sensor")
        if which:
            lines.append('%s_sensorsStop("%s");' % (indent, which))
        else:
            lines.append("%s_sensorsStopAll();" % indent)
        return

    name = command.get("sensor")
    callback = command.get("callback")
    if name not in SENSORS:
        return
    if not callback:
        # Watching with nobody listening burns battery for no one. Saying so
        # at compile time beats a phone getting warm in somebody's pocket.
        lines.append('%s// sensors.%s() with no on_change -- nothing to start.'
                     % (indent, name))
        return
    if SENSORS[name]["args"] == 0:
        lambda_java = "() -> pythonCallback_%s()" % callback
        lines.append('%s_sensorsStartEvent("%s", %s);' % (indent, name, lambda_java))
    else:
        boolean = name == "proximity"
        arg = ('value.equals("True")' if boolean else "value")
        lines.append('%s_sensorsStart("%s", value -> pythonCallback_%s(%s));'
                     % (indent, name, callback, arg))


def value_java(node, scope="activity"):
    """``sensors.available(...)`` / ``battery.*`` as text."""
    if not is_value_call(node):
        return None
    holder = node.func.value.id
    verb = node.func.attr
    if holder == "battery" and verb == "level":
        return "_batteryLevel()"
    return '(%s ? "True" : "False")' % condition_java(node, scope)


def condition_java(node, scope="activity"):
    """The same, as a real Java boolean, for ``if`` and ``while``."""
    if not is_value_call(node):
        return None
    holder = node.func.value.id
    verb = node.func.attr
    if holder == "battery":
        if verb == "charging":
            return "_batteryCharging()"
        if verb == "saver":
            return "_batterySaver()"
        # battery.level() in a condition is a number, not a question. Compare
        # it rather than pretending a percentage is true or false.
        return "(_apkpySensorNumber(_batteryLevel()) > 0)"
    name = None
    if node.args and isinstance(node.args[0], ast.Constant):
        name = str(node.args[0].value)
    if name not in SENSORS:
        return "false"
    return '_sensorsAvailable("%s")' % name


def permissions_needed(names):
    """The manifest permissions for the sensors this app watches."""
    wanted = []
    for name in names or []:
        permission = SENSORS.get(name, {}).get("permission")
        if permission and permission not in wanted:
            wanted.append(permission)
    return wanted


def manifest_features(names):
    """``<uses-feature>`` for each sensor watched, never required.

    ``required="false"`` for the same reason the torch is: describing what the
    app touches is honest, but letting the Play Store hide the app from every
    phone without a step counter -- because one screen counts steps -- is not.
    A phone without the sensor answers ``no_sensor`` and the app carries on.
    """
    lines = []
    seen = set()
    for name in names or []:
        feature = SENSORS.get(name, {}).get("feature")
        if feature and feature not in seen:
            seen.add(feature)
            lines.append(
                '    <uses-feature android:name="%s" android:required="false" />'
                % feature)
    return lines


def _type_arms():
    return "\n".join(
        '            case "%s": return android.hardware.Sensor.%s;'
        % (name, info["android"])
        for name, info in sorted(SENSORS.items())
    )


def _rate_arms():
    return "\n".join(
        '            case "%s": return android.hardware.SensorManager.SENSOR_DELAY_%s;'
        % (name, info["rate"])
        for name, info in sorted(SENSORS.items())
    )


def _threshold_arms():
    return "\n".join(
        '            case "%s": return %sf;' % (name, THRESHOLDS[name])
        for name in sorted(THRESHOLDS)
    )


def activity_runtime_java(names=()):
    """The Activity's sensor machinery: start, stop, and the lifecycle.

    Activity methods rather than a static class, because these must stop when
    the screen stops. See the module docstring.
    """
    return '''
    // ── sensors.* : streams, with a lifecycle ──────────────────────────────

    public interface ApkpySensorCallback { void onSensor(String value); }
    public interface ApkpySensorEvent { void onSensor(); }

    private final java.util.Map<String, ApkpySensorWatch> _apkpySensorWatches =
            new java.util.LinkedHashMap<>();

    private static int _sensorType(String name) {
        switch (name) {
%(type_arms)s
            default: return -1;
        }
    }

    private static int _sensorRate(String name) {
        switch (name) {
%(rate_arms)s
            default: return android.hardware.SensorManager.SENSOR_DELAY_NORMAL;
        }
    }

    private static float _sensorThreshold(String name) {
        switch (name) {
%(threshold_arms)s
            default: return 0f;
        }
    }

    /** The one formatting rule, transcribed from apkpy_lib/core/features/sensors.py. */
    private static String _sensorFormat(String name, float value) {
        if (name.equals("proximity")) return value >= 0.5f ? "True" : "False";
        if (name.equals("compass") || name.equals("steps")) {
            // rint and not round. Python rounds a half to the EVEN number and
            // Math.round takes it upwards, so a heading of 0.5 would read 0 in
            // the Previewer and 1 on the phone. rint is Python's rule, and it
            // is already the rule the rest of ApkPy rounds by.
            return String.valueOf((int) Math.rint(value));
        }
        String text = String.format(java.util.Locale.ROOT, "%%.1f", value);
        return text.endsWith(".0") ? text.substring(0, text.length() - 2) : text;
    }

    private static double _apkpySensorNumber(String text) {
        try { return Double.parseDouble(text); }
        catch (Exception ignored) { return 0d; }
    }

    private static boolean _sensorIsVector(String name) {
        return name.equals("accelerometer") || name.equals("gyroscope");
    }

    private static String _sensorAxis(float value) {
        double rounded = Math.rint((double) value * 10000d) / 10000d;
        return String.format(java.util.Locale.ROOT, "%%.4f",
                rounded == 0d ? 0d : rounded);
    }

    private static String _sensorVector(float x, float y, float z) {
        return "{\\\"x\\\":" + _sensorAxis(x) + ",\\\"y\\\":" + _sensorAxis(y)
                + ",\\\"z\\\":" + _sensorAxis(z) + "}";
    }

    private final class ApkpySensorWatch
            implements android.hardware.SensorEventListener {
        final String name;
        final ApkpySensorCallback callback;
        final ApkpySensorEvent event;
        boolean active = false;
        Float last = null;
        long lastShake = 0L;
        Float stepBase = null;
        final float[] lastAxes = new float[3];
        boolean hasAxes = false;

        ApkpySensorWatch(String name, ApkpySensorCallback callback,
                         ApkpySensorEvent event) {
            this.name = name;
            this.callback = callback;
            this.event = event;
        }

        @Override
        public void onAccuracyChanged(android.hardware.Sensor sensor, int accuracy) { }

        @Override
        public void onSensorChanged(android.hardware.SensorEvent reading) {
            // Queued readings must not reach callbacks after stop/onPause.
            if (!active) return;
            if (_sensorIsVector(name)) {
                if (reading.values.length < 3) return;
                float x = reading.values[0], y = reading.values[1], z = reading.values[2];
                if (Float.isNaN(x) || Float.isInfinite(x) || Float.isNaN(y)
                        || Float.isInfinite(y) || Float.isNaN(z) || Float.isInfinite(z)) return;
                float threshold = _sensorThreshold(name);
                if (hasAxes && Math.abs((double) x - lastAxes[0]) < threshold
                        && Math.abs((double) y - lastAxes[1]) < threshold
                        && Math.abs((double) z - lastAxes[2]) < threshold) return;
                lastAxes[0] = x; lastAxes[1] = y; lastAxes[2] = z;
                hasAxes = true;
                final String text = _sensorVector(x, y, z);
                if (callback != null) runOnUiThread(() -> callback.onSensor(text));
                return;
            }
            if (name.equals("shake")) {
                float x = reading.values[0], y = reading.values[1], z = reading.values[2];
                // GRAVITY_EARTH, so a phone lying still reads 1g and not 0.
                double force = Math.sqrt(x * x + y * y + z * z)
                        / android.hardware.SensorManager.GRAVITY_EARTH;
                if (force <= %(shake_g)sd) return;
                long now = android.os.SystemClock.elapsedRealtime();
                // One flick of the wrist crosses the threshold many times over.
                // Without this gap a single shake would fire a dozen callbacks.
                if (now - lastShake < %(shake_gap)dL) return;
                lastShake = now;
                if (event != null) runOnUiThread(() -> event.onSensor());
                return;
            }

            float value;
            if (name.equals("compass")) {
                float[] rotation = new float[9];
                // Some phones report five values here and getRotationMatrix-
                // FromVector throws on the extra one, so it is trimmed to the
                // four the method documents.
                float[] vector = reading.values;
                if (vector.length > 4) {
                    vector = new float[] { vector[0], vector[1], vector[2], vector[3] };
                }
                try {
                    android.hardware.SensorManager
                            .getRotationMatrixFromVector(rotation, vector);
                } catch (Throwable t) {
                    return;
                }
                float[] orientation = new float[3];
                android.hardware.SensorManager.getOrientation(rotation, orientation);
                value = (float) Math.toDegrees(orientation[0]);
                if (value < 0) value += 360f;
            } else if (name.equals("proximity")) {
                // TYPE_PROXIMITY reports DISTANCE in cm, so small means near
                // and the sensor's own maximum means far. Most phones only
                // ever report those two numbers. Reading the raw value as a
                // boolean gets it exactly backwards -- a phone lying on a desk
                // reports 5cm, which is "far", and would have read as "near".
                float reach = reading.sensor.getMaximumRange();
                value = (reading.values[0] < reach) ? 1f : 0f;
            } else if (name.equals("steps")) {
                // TYPE_STEP_COUNTER counts from the last reboot, which is a
                // number about the phone and not about this app. The first
                // reading becomes zero so the app counts its own steps.
                if (stepBase == null) stepBase = reading.values[0];
                value = reading.values[0] - stepBase;
            } else {
                value = reading.values[0];
            }

            if (last != null
                    && Math.abs(value - last) < _sensorThreshold(name)) {
                return;
            }
            last = value;
            final String text = _sensorFormat(name, value);
            if (callback != null) runOnUiThread(() -> callback.onSensor(text));
        }
    }

    private android.hardware.SensorManager _sensorManager() {
        return (android.hardware.SensorManager)
                getSystemService(android.content.Context.SENSOR_SERVICE);
    }

    /** Does this phone have it at all? */
    private boolean _sensorsAvailable(String name) {
        int type = _sensorType(name);
        if (type < 0) return false;
        android.hardware.SensorManager manager = _sensorManager();
        return manager != null && manager.getDefaultSensor(type) != null;
    }

    private void _sensorsRegister(ApkpySensorWatch watch) {
        if (watch.active) return;
        android.hardware.SensorManager manager = _sensorManager();
        if (manager == null) return;
        android.hardware.Sensor sensor = manager.getDefaultSensor(_sensorType(watch.name));
        if (sensor == null) return;
%(step_register)s
        watch.active = manager.registerListener(watch, sensor, _sensorRate(watch.name));
    }

    private void _sensorsStart(final String name, final ApkpySensorCallback callback) {
        _sensorsStartWatch(new ApkpySensorWatch(name, callback, null));
    }

    private void _sensorsStartEvent(final String name, final ApkpySensorEvent event) {
        _sensorsStartWatch(new ApkpySensorWatch(name, null, event));
    }

    private void _sensorsStartWatch(ApkpySensorWatch watch) {
        // Watching the same sensor twice would deliver every reading twice.
        _sensorsStop(watch.name);
        _apkpySensorWatches.put(watch.name, watch);
%(step_start)s
        _sensorsRegister(watch);
    }

    private void _sensorsStop(String name) {
        ApkpySensorWatch watch = _apkpySensorWatches.remove(name);
        if (watch == null) return;
        android.hardware.SensorManager manager = _sensorManager();
        if (manager != null && watch.active) manager.unregisterListener(watch);
        watch.active = false;
    }

    private void _sensorsStopAll() {
        for (String name : new java.util.ArrayList<>(_apkpySensorWatches.keySet())) {
            _sensorsStop(name);
        }
    }

    /**
     * Unregister everything while the screen is away.
     *
     * The watches stay in the map on purpose: onResume puts back exactly what
     * the app asked for, without the app having to ask again.
     */
    private void _sensorsPauseAll() {
        android.hardware.SensorManager manager = _sensorManager();
        for (ApkpySensorWatch watch : _apkpySensorWatches.values()) {
            if (manager != null && watch.active) manager.unregisterListener(watch);
            watch.active = false;
        }
    }

    private void _sensorsResumeAll() {
        for (ApkpySensorWatch watch : _apkpySensorWatches.values()) {
            _sensorsRegister(watch);
        }
    }

    // ── battery : state the phone already publishes, no permission ─────────

    private String _batteryLevel() {
        try {
            android.os.BatteryManager manager = (android.os.BatteryManager)
                    getSystemService(android.content.Context.BATTERY_SERVICE);
            if (manager == null) return "0";
            return String.valueOf(manager.getIntProperty(
                    android.os.BatteryManager.BATTERY_PROPERTY_CAPACITY));
        } catch (Throwable t) {
            return "0";
        }
    }

    private boolean _batteryCharging() {
        try {
            android.os.BatteryManager manager = (android.os.BatteryManager)
                    getSystemService(android.content.Context.BATTERY_SERVICE);
            return manager != null && manager.isCharging();
        } catch (Throwable t) {
            return false;
        }
    }

    private boolean _batterySaver() {
        try {
            android.os.PowerManager manager = (android.os.PowerManager)
                    getSystemService(android.content.Context.POWER_SERVICE);
            return manager != null && manager.isPowerSaveMode();
        } catch (Throwable t) {
            return false;
        }
    }
''' % {
        "type_arms": _type_arms(),
        "rate_arms": _rate_arms(),
        "threshold_arms": _threshold_arms(),
        "shake_g": SHAKE_G,
        "shake_gap": SHAKE_GAP_MS,
        "step_register": ('        if (watch.name.equals("steps") && !_sensorsStepPermission()) return;'
                          if "steps" in names else ""),
        "step_start": ('''        if (watch.name.equals("steps") && !_sensorsStepPermission()) {
            _apkpyStepPermissionLauncher.launch(_ACTIVITY_RECOGNITION);
            return;
        }''' if "steps" in names else ""),
    }


def step_permission_java():
    """The ACTIVITY_RECOGNITION dance, emitted only for an app that counts.

    Android 10 made this a runtime permission; before that the manifest entry
    was enough. The version guard is why an app counting steps still works on
    a phone from 2018 without asking anybody anything.
    """
    return '''
    private static final String _ACTIVITY_RECOGNITION =
            "android.permission.ACTIVITY_RECOGNITION";

    private boolean _sensorsStepPermission() {
        if (android.os.Build.VERSION.SDK_INT < android.os.Build.VERSION_CODES.Q) {
            return true;
        }
        return androidx.core.content.ContextCompat.checkSelfPermission(
                this, _ACTIVITY_RECOGNITION)
                == android.content.pm.PackageManager.PERMISSION_GRANTED;
    }

    private final androidx.activity.result.ActivityResultLauncher<String>
            _apkpyStepPermissionLauncher = registerForActivityResult(
            new androidx.activity.result.contract.ActivityResultContracts.RequestPermission(),
            granted -> {
                // Granted or not, the app is told once. A step watch that
                // silently never fires is the hardest kind of bug to see.
                if (Boolean.TRUE.equals(granted)) {
                    _sensorsResumeAll();
                }
            });
'''
