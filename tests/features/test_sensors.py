# -*- coding: utf-8 -*-
"""Sensors and battery: the rules both runtimes have to agree on.

The interesting tests here are the transcriptions. A sensor's formatting rule
and its threshold exist once in Python and once, by hand, in the Java the
compiler writes. Nothing stops those two from drifting except a test that
re-implements the Java in Python and compares -- which is what
:class:`TheJavaSaysTheSameTests` does.
"""

import math
import os
import json
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from apkpy_lib.core.features import sensors as feature


def transpile(source):
    from apkpy_lib.core.compiler import translate_python_to_android
    return translate_python_to_android(source, package="com.apkpy.test")


def activity_of(files):
    for name, text in files.items():
        if name.endswith("Activity.java"):
            return text
    raise AssertionError("no Activity was generated")


APP = '''
from apkpy_lib import Screen, label, button, sensors, battery, run
home = Screen(id="home")
lbl = label("", id="lbl", screen=home)
def show(value):
    lbl.set_value(value)
def shaken():
    lbl.set_value("abanou")
def start():
    %s
button("go", id="b", screen=home, command=start)
run(start_screen=home)
'''


class TheFormattingRuleTests(unittest.TestCase):
    """One reading, one piece of text, on both sides."""

    def test_a_whole_number_keeps_no_decimal(self):
        self.assertEqual(feature.format_value("light", 12.0), "12")

    def test_light_keeps_one_decimal_when_it_has_one(self):
        self.assertEqual(feature.format_value("light", 12.34), "12.3")

    def test_degrees_and_steps_are_whole(self):
        self.assertEqual(feature.format_value("compass", 47.6), "48")
        self.assertEqual(feature.format_value("steps", 3.0), "3")

    def test_proximity_is_a_word_not_a_number(self):
        # 1 near / 0 far, already normalised. The raw sensor reports distance,
        # so this is the one place the inversion could creep back in.
        self.assertEqual(feature.format_value("proximity", 1.0), "True")
        self.assertEqual(feature.format_value("proximity", 0.0), "False")


class TheThresholdTests(unittest.TestCase):

    def test_the_first_reading_always_gets_through(self):
        self.assertTrue(feature.passes_threshold("light", None, 0.0))

    def test_a_smaller_change_is_not_news(self):
        self.assertFalse(feature.passes_threshold("compass", 100.0, 100.4))

    def test_a_big_enough_change_is(self):
        self.assertTrue(feature.passes_threshold("compass", 100.0, 101.0))

    def test_proximity_only_speaks_when_it_flips(self):
        self.assertFalse(feature.passes_threshold("proximity", 1.0, 1.0))
        self.assertTrue(feature.passes_threshold("proximity", 1.0, 0.0))


class TheShakeTests(unittest.TestCase):

    def test_a_phone_lying_still_is_not_a_shake(self):
        # One g straight down is a phone on a table, not a shake.
        self.assertFalse(feature.shake_detected(0.0, 0.0, 9.80665))

    def test_a_real_shake_is(self):
        self.assertTrue(feature.shake_detected(20.0, 20.0, 20.0))

    def test_the_threshold_is_where_it_says_it_is(self):
        just_under = 9.80665 * feature.SHAKE_G * 0.99
        just_over = 9.80665 * feature.SHAKE_G * 1.01
        self.assertFalse(feature.shake_detected(just_under, 0.0, 0.0))
        self.assertTrue(feature.shake_detected(just_over, 0.0, 0.0))


class TheJavaSaysTheSameTests(unittest.TestCase):
    """Re-implement the emitted Java in Python and compare, value by value."""

    def setUp(self):
        self.java = feature.activity_runtime_java(list(feature.SENSORS))

    def java_format(self, name, value):
        """_sensorFormat, transcribed from the Java the compiler writes."""
        if name == "proximity":
            return "True" if value >= 0.5 else "False"
        if name in ("compass", "steps"):
            # Math.rint, which rounds a half to the even number -- the same
            # rule Python's round() uses, and the rule the rest of ApkPy
            # already rounds by. Math.round would take 0.5 up to 1 and this
            # comparison is what caught that.
            floor = int(value // 1)
            remainder = value - floor
            if remainder > 0.5:
                return str(floor + 1)
            if remainder < 0.5:
                return str(floor)
            return str(floor if floor % 2 == 0 else floor + 1)
        text = "%.1f" % value
        return text[:-2] if text.endswith(".0") else text

    @staticmethod
    def java_rint(value):
        """``Math.rint``: half to even, and it keeps the sign of a zero.

        Python's ``round()`` returns an int, so it loses ``-0.0`` on its own
        and would hide the very case the Java guards against.
        """
        rounded = float(round(value))
        return math.copysign(rounded, value) if rounded == 0.0 else rounded

    def java_axis(self, value):
        """``_sensorAxis``, transcribed."""
        # SensorEvent.values is a float[], so the reading is float32 before
        # any of this arithmetic happens.
        value = struct.unpack("f", struct.pack("f", value))[0]
        rounded = self.java_rint(value * 10000.0) / 10000.0
        # Without this, a slightly negative axis prints "-0.0000" on the phone
        # and "0.0000" in the Previewer.
        return "%.4f" % (0.0 if rounded == 0.0 else rounded)

    def java_vector(self, axes):
        """``_sensorVector``, transcribed."""
        return "{%s}" % ",".join(
            '"%s":%s' % (axis, self.java_axis(number))
            for axis, number in zip(("x", "y", "z"), axes))

    def test_every_value_formats_the_same_both_sides(self):
        values = [i / 8.0 for i in range(0, 4000)]
        for name in ("light", "pressure", "compass", "steps", "proximity"):
            for value in values:
                self.assertEqual(
                    feature.format_value(name, value),
                    self.java_format(name, value),
                    "%s disagreed at %r" % (name, value),
                )

    def test_every_axis_formats_the_same_both_sides(self):
        """The rule the value-by-value test used to skip.

        Vector formatting is the most intricate thing in the module -- float32,
        rint, four decimals and a negative zero -- and it was the only one with
        no comparison behind it. The ties at the fifth decimal and the tiny
        negatives are the two places it would come apart.
        """
        axes = [i / 16.0 for i in range(-4000, 4001, 3)]
        axes += [i / 10000.0 + 0.00005 for i in range(-400, 401)]
        axes += [i / 10000.0 - 0.00005 for i in range(-400, 401)]
        axes += [-i * 1e-9 for i in range(1, 400)]
        axes += [0.0, -0.0, 9.80665, -9.80665, 1e-7, -1e-7]
        for name in sorted(feature.VECTOR_SENSORS):
            for value in axes:
                reading = (value, -value, 9.80665)
                self.assertEqual(
                    feature.format_value(name, reading),
                    self.java_vector(reading),
                    "%s disagreed at %r" % (name, value),
                )

    def test_the_java_still_carries_the_negative_zero_guard(self):
        """A transcription only checks the Python half.

        These two lines are what the transcription is modelling, so if the
        emitted Java loses them the comparison above would go on passing while
        the phone quietly disagreed.
        """
        self.assertIn("Math.rint((double) value * 10000d) / 10000d", self.java)
        self.assertIn("rounded == 0d ? 0d : rounded", self.java)
        self.assertIn('String.format(java.util.Locale.ROOT, "%.4f"', self.java)

    def test_the_thresholds_in_the_java_are_the_python_ones(self):
        for name, threshold in feature.THRESHOLDS.items():
            self.assertIn('case "%s": return %sf;' % (name, threshold),
                          self.java)

    def test_the_shake_numbers_in_the_java_are_the_python_ones(self):
        self.assertIn("force <= %sd" % feature.SHAKE_G, self.java)
        self.assertIn("< %dL" % feature.SHAKE_GAP_MS, self.java)

    def test_every_sensor_maps_to_the_constant_the_table_names(self):
        for name, info in feature.SENSORS.items():
            self.assertIn(
                'case "%s": return android.hardware.Sensor.%s;'
                % (name, info["android"]),
                self.java,
            )


class TheGeneratedAppTests(unittest.TestCase):

    def test_watching_registers_and_the_screen_unregisters(self):
        files = transpile(APP % "sensors.light(on_change=show)")
        java = activity_of(files)
        self.assertIn('_sensorsStart("light"', java)
        # The whole point of the feature: a listener left registered keeps the
        # sensor hub awake behind a screen nobody is looking at.
        self.assertIn("protected void onPause()", java)
        self.assertIn("_sensorsPauseAll();", java)
        self.assertIn("protected void onResume()", java)
        self.assertIn("_sensorsResumeAll();", java)

    def test_a_shake_callback_takes_no_argument(self):
        java = activity_of(transpile(APP % "sensors.shake(on_shake=shaken)"))
        self.assertIn('_sensorsStartEvent("shake", () -> pythonCallback_shaken());',
                      java)

    def test_proximity_reaches_python_as_a_real_boolean(self):
        java = activity_of(transpile(APP % "sensors.proximity(on_change=show)"))
        self.assertIn('value.equals("True")', java)

    def test_the_java_normalises_proximity_before_formatting(self):
        java = activity_of(transpile(APP % "sensors.proximity(on_change=show)"))
        # Distance, not a boolean. Without this the reading is inverted and a
        # phone flat on a desk reports something touching it.
        self.assertIn("reading.sensor.getMaximumRange()", java)

    def test_steps_start_from_this_app_not_from_the_last_reboot(self):
        java = activity_of(transpile(APP % "sensors.steps(on_change=show)"))
        self.assertIn("stepBase", java)

    def test_only_steps_asks_for_a_permission(self):
        with_steps = transpile(APP % "sensors.steps(on_change=show)")
        with_light = transpile(APP % "sensors.light(on_change=show)")
        manifest_steps = with_steps["AndroidManifest.xml"]
        manifest_light = with_light["AndroidManifest.xml"]
        self.assertIn("android.permission.ACTIVITY_RECOGNITION", manifest_steps)
        self.assertNotIn("ACTIVITY_RECOGNITION", manifest_light)

    def test_the_permission_is_only_asked_for_from_android_10(self):
        java = activity_of(transpile(APP % "sensors.steps(on_change=show)"))
        self.assertIn("VERSION_CODES.Q", java)

    def test_an_app_only_declares_the_sensors_it_watches(self):
        manifest = transpile(APP % "sensors.shake(on_shake=shaken)")["AndroidManifest.xml"]
        self.assertIn("android.hardware.sensor.accelerometer", manifest)
        self.assertNotIn("stepcounter", manifest)

    def test_nothing_is_ever_required(self):
        manifest = transpile(APP % "sensors.steps(on_change=show)")["AndroidManifest.xml"]
        for line in manifest.splitlines():
            if "hardware.sensor" in line:
                # required="true" would let the Play Store hide the app from
                # every phone without the sensor.
                self.assertIn('android:required="false"', line)

    def test_an_app_with_no_sensors_gets_none_of_the_machinery(self):
        java = activity_of(transpile(
            APP % 'lbl.set_value("nada")'))
        self.assertNotIn("_sensorsStart", java)
        self.assertNotIn("ApkpySensorWatch", java)

    def test_stopping_one_is_not_stopping_all(self):
        java = activity_of(transpile(APP % 'sensors.stop("light")'))
        self.assertIn('_sensorsStop("light");', java)
        java_all = activity_of(transpile(APP % "sensors.stop()"))
        self.assertIn("_sensorsStopAll();", java_all)


class TheBatteryTests(unittest.TestCase):

    def test_the_level_is_a_value_and_the_rest_are_questions(self):
        java = activity_of(transpile(APP % 'lbl.set_value(battery.level())'))
        self.assertIn("_batteryLevel()", java)

    def test_charging_compiles_to_a_real_boolean_condition(self):
        source = APP % "lbl.set_value('x')"
        source = source.replace("def start():",
                                "def start():\n    if battery.charging():\n        lbl.set_value('sim')\n    ")
        java = activity_of(transpile(source))
        self.assertIn("if (_batteryCharging())", java)

    def test_battery_needs_no_permission_at_all(self):
        manifest = transpile(
            APP % "lbl.set_value(battery.level())")["AndroidManifest.xml"]
        self.assertNotIn("BATTERY", manifest)

    def test_asking_about_the_battery_is_enough_to_get_the_methods(self):
        # battery.* is an expression, never a command, so the command walk
        # cannot see it. Without the value gate this compiles to a call on a
        # method that was never written.
        java = activity_of(transpile(APP % "lbl.set_value(battery.level())"))
        self.assertIn("private String _batteryLevel()", java)


class ThePreviewerAgreesTests(unittest.TestCase):

    def setUp(self):
        from apkpy_lib.features.sensors import SensorsAPI
        self.api = SensorsAPI()
        self.seen = []

    def test_it_reports_through_the_same_rule_the_phone_uses(self):
        self.api._watches["light"] = self.seen.append
        self.api._feed("light", 12.34)
        self.assertEqual(self.seen, ["12.3"])

    def test_it_stays_quiet_for_a_change_too_small_to_matter(self):
        self.api._watches["compass"] = self.seen.append
        self.api._feed("compass", 100.0)
        self.api._feed("compass", 100.4)
        self.assertEqual(self.seen, ["100"])

    def test_proximity_arrives_as_a_boolean_here_too(self):
        self.api._watches["proximity"] = self.seen.append
        self.api._feed("proximity", 1.0)
        self.assertEqual(self.seen, [True])

    def test_a_shake_callback_is_called_with_nothing(self):
        held = []
        self.api._watches["shake"] = lambda: held.append("shook")
        self.api._fire_shake()
        self.assertEqual(held, ["shook"])

    def test_watching_nothing_opens_no_window(self):
        # The lazy-proxy trap: asking ui._app for anything but _instance builds
        # a Tk window, and a headless build must never open one.
        from apkpy_lib import ui
        before = getattr(ui._app, "_instance", None)
        self.api.light(on_change=self.seen.append)
        self.assertIs(getattr(ui._app, "_instance", None), before)


class MotionAndPressureTests(unittest.TestCase):
    def test_new_watches_generate_real_sensor_types_without_permissions(self):
        for name in ("accelerometer", "gyroscope", "pressure"):
            with self.subTest(sensor=name):
                files = transpile(APP % ("sensors.%s(on_change=show)" % name))
                java = activity_of(files)
                self.assertIn('_sensorsStart("%s", value -> pythonCallback_show(value));' % name, java)
                self.assertIn("Sensor." + feature.SENSORS[name]["android"], java)
                self.assertIn(feature.SENSORS[name]["feature"], files["AndroidManifest.xml"])
                self.assertNotIn("ACTIVITY_RECOGNITION", java)
                self.assertNotIn("_sensorsStepPermission", java)
                self.assertNotIn("_apkpyStepPermissionLauncher", java)
                self.assertNotIn("ACTIVITY_RECOGNITION", files["AndroidManifest.xml"])

    def test_vectors_are_numeric_json_not_rounded_scalar_readings(self):
        for name in feature.VECTOR_SENSORS:
            self.assertEqual(json.loads(feature.format_value(name, (1.25, -2, 9.80665))),
                             {"x": 1.25, "y": -2.0, "z": 9.8067})

    def test_all_three_axes_can_trigger_a_reading(self):
        for name in feature.VECTOR_SENSORS:
            self.assertTrue(feature.passes_threshold(name, None, (0, 0, 0)))
            self.assertFalse(feature.passes_threshold(name, (0, 0, 0), (0.001, 0.001, 0.001)))
            for axis in range(3):
                changed = [0, 0, 0]
                changed[axis] = 1
                self.assertTrue(feature.passes_threshold(name, (0, 0, 0), changed))

    def test_invalid_vectors_fail_clearly(self):
        for value in ([1, 2], [1, 2, 3, 4], "abc", [0, float("nan"), 0], [0, float("inf"), 0]):
            with self.assertRaises(ValueError):
                feature.format_value("accelerometer", value)

    def test_vector_threshold_and_negative_zero_match_sensor_event_precision(self):
        self.assertTrue(feature.passes_threshold("gyroscope", (0, 0, 0), (0.01, 0, 0)))
        self.assertEqual(feature.format_value("gyroscope", (-0.00001, 0, 0)),
                         '{"x":0.0000,"y":0.0000,"z":0.0000}')

    def test_pressure_keeps_existing_scalar_callback_contract(self):
        self.assertEqual(feature.format_value("pressure", 1013.24), "1013.2")
        self.assertFalse(feature.passes_threshold("pressure", 1000, 1000.05))
        self.assertTrue(feature.passes_threshold("pressure", 1000, 1000.2))

    def test_preview_copies_vector_buffers_and_stops_callbacks(self):
        from apkpy_lib.features.sensors import SensorsAPI
        api = SensorsAPI()
        seen = []
        api.accelerometer(on_change=seen.append)
        sample = [0, 0, 9.8]
        api._feed("accelerometer", sample)
        sample[0] = 2
        api._feed("accelerometer", sample)
        self.assertEqual(len(seen), 2)
        self.assertEqual(json.loads(seen[0])["x"], 0)
        api.stop("accelerometer")
        api._feed("accelerometer", [4, 0, 0])
        self.assertEqual(len(seen), 2)

    def test_available_and_keyword_stop_work_for_new_sensors(self):
        from apkpy_lib.features.sensors import SensorsAPI
        api = SensorsAPI()
        for name in ("accelerometer", "gyroscope", "pressure"):
            self.assertTrue(api.available(name))
            source = APP % ('if sensors.available("%s"):\n        sensors.%s(on_change=show)' % (name, name))
            self.assertIn('_sensorsAvailable("%s")' % name, activity_of(transpile(source)))
        self.assertIn('_sensorsStop("gyroscope");',
                      activity_of(transpile(APP % 'sensors.stop(name="gyroscope")')))

    def test_shake_and_raw_acceleration_share_one_manifest_feature(self):
        manifest = transpile(APP % 'sensors.shake(on_shake=shaken)\n    sensors.accelerometer(on_change=show)')["AndroidManifest.xml"]
        self.assertEqual(manifest.count('android.hardware.sensor.accelerometer'), 1)

    def test_pause_discards_queued_events_and_registration_checks_success(self):
        java = activity_of(transpile(APP % 'sensors.gyroscope(on_change=show)'))
        self.assertIn('if (!active) return;', java)
        self.assertIn('watch.active = manager.registerListener', java)


class SensorPreviewControlsTests(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk
            self.root = tk.Tk()
            self.root.withdraw()
        except Exception as error:
            self.skipTest("Tk display unavailable: " + str(error))
        self.addCleanup(self.root.destroy)
        from apkpy_lib.features.sensors import SensorsAPI, _Panel
        self.api = SensorsAPI()
        self.panel = _Panel()
        self.panel.body = tk.Frame(self.root)

    def scales(self, widget):
        import tkinter as tk
        result = []
        for child in widget.winfo_children():
            if isinstance(child, tk.Scale):
                result.append(child)
            result.extend(self.scales(child))
        return result

    def test_all_axis_controls_deliver_the_named_sensor(self):
        seen = {"accelerometer": [], "gyroscope": []}
        for name in seen:
            self.api._watches[name] = seen[name].append
            self.panel.add(name, self.api)
        for name in seen:
            controls = self.scales(self.panel.rows[name])
            self.assertEqual(len(controls), 3)
            for axis, control in enumerate(controls):
                # Invoke Tk's registered widget command without moving the
                # user's mouse or requiring a visible desktop window.
                control.tk.call(control.cget("command"), str(axis + 1))
            self.assertEqual(json.loads(seen[name][-1]), {"x": 1, "y": 2, "z": 3})

    def test_pressure_control_reports_hpa(self):
        seen = []
        self.api._watches["pressure"] = seen.append
        self.panel.add("pressure", self.api)
        control = self.scales(self.panel.rows["pressure"])[0]
        control.tk.call(control.cget("command"), "998.3")
        self.assertEqual(seen, ["998.3"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
