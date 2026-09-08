---
title: Sensors and battery
description: Complete ApkPy examples for shake, compass, steps, light, proximity, accelerometer, gyroscope, pressure and battery state. Includes the 1.7.0 additions.
---

# Sensors and battery

The current released API includes shake detection, compass, steps, ambient
light and proximity. Battery level, charging and power-saver state are exposed
separately through `battery`.

!!! info "New in 1.7.0"

    `accelerometer`, `gyroscope` and `pressure` were added in
    [ApkPy 1.7.0](../version-1.7.0.md). Install version 1.7.0 or newer.
    The other sensors below are existing APIs, now documented together.

## Callback reference

Import `sensors` and `battery` from `apkpy_lib`. Supply the named callback
when starting a watch. These methods do not return a reading immediately.

| Method | Callback value |
| --- | --- |
| `sensors.shake(on_shake=callback)` | No arguments: one shake event |
| `sensors.compass(on_change=callback)` | Heading in degrees, as text |
| `sensors.steps(on_change=callback)` | Steps since registration, as text |
| `sensors.light(on_change=callback)` | Ambient light in lux, as text |
| `sensors.proximity(on_change=callback)` | Boolean: `True` means near |
| `sensors.accelerometer(on_change=callback)` | JSON text with numeric `x`, `y`, `z`, in m/s² including gravity |
| `sensors.gyroscope(on_change=callback)` | JSON text with numeric `x`, `y`, `z`, in rad/s |
| `sensors.pressure(on_change=callback)` | Atmospheric pressure in hPa, as text |

`shake()` also accepts `on_change` as an alias for `on_shake`; its callback
still takes **no arguments**. All other sensor callbacks take one argument.
Only proximity is a Python boolean; numeric scalar readings are text.
The two vector sensors pass one JSON string, not three callback arguments.

| Control / battery method | Result |
| --- | --- |
| `sensors.available("light")` | Boolean: is the named sensor present? |
| `sensors.stop("light")` | Stop that watch; no result |
| `sensors.stop()` | Stop every sensor watch; no result |
| `battery.level()` | Percentage as text, for example `"80"` |
| `battery.charging()` | Boolean: charging state |
| `battery.saver()` | Boolean: power-saving mode |

Battery methods read a snapshot. They do not subscribe to future changes.
Call them again when the user requests a refresh or when your screen resumes.
Battery reads do not need Android permissions.

## Choose the right measurement

| Sensor | Useful for | What it does not mean |
| --- | --- | --- |
| Shake | a deliberate gesture such as resetting a game | every bump or raw acceleration sample |
| Compass | a heading display | GPS position or a perfectly calibrated navigation instrument |
| Steps | steps counted during one watch | a persistent daily fitness total |
| Light | reacting to ambient brightness | screen brightness or a camera exposure reading |
| Proximity | near/far interaction near the earpiece | an exact distance measurement |
| Accelerometer — 1.7.0 | tilt, motion feedback, simple instruments | acceleration with gravity removed |
| Gyroscope — 1.7.0 | rotation-rate feedback and motion controls | a rotation angle or absolute heading |
| Pressure — 1.7.0 | a barometer display | altitude without calibration |

## Complete example: existing sensors and battery

This app keeps each reading separate. Step counting starts only when the user
taps its own button, because it may require a permission prompt on Android.

```python
from apkpy_lib import Screen, Theme, label, button, sensors, battery, run

home = Screen(id="home", scroll=True)
status = label("Tap Start instruments", id="status", screen=home)
shake_label = label("Shake: waiting", screen=home)
compass_label = label("Heading: waiting", screen=home)
light_label = label("Light: waiting", screen=home)
near_label = label("Proximity: waiting", screen=home)
steps_label = label("Steps: not started", screen=home)
battery_label = label("Battery: tap Read battery", screen=home)

def shaken():
    shake_label.set_value("Shake detected")

def heading_changed(degrees):
    compass_label.set_value("Heading: " + degrees + " degrees")

def light_changed(lux):
    light_label.set_value("Light: " + lux + " lux")

def proximity_changed(near):
    if near:
        near_label.set_value("Proximity: near")
    else:
        near_label.set_value("Proximity: far")

def steps_changed(count):
    steps_label.set_value("Steps in this watch: " + count)

def start_instruments():
    if sensors.available("shake"):
        sensors.shake(on_shake=shaken)
    else:
        shake_label.set_value("No accelerometer for shake detection")
    if sensors.available("compass"):
        sensors.compass(on_change=heading_changed)
    else:
        compass_label.set_value("No heading sensor")
    if sensors.available("light"):
        sensors.light(on_change=light_changed)
    else:
        light_label.set_value("No light sensor")
    if sensors.available("proximity"):
        sensors.proximity(on_change=proximity_changed)
    else:
        near_label.set_value("No proximity sensor")
    status.set_value("Watching available instruments")

def start_steps():
    if not sensors.available("steps"):
        steps_label.set_value("No step counter on this device")
        return
    steps_label.set_value("Allow activity access if asked, then walk")
    sensors.steps(on_change=steps_changed)

def read_battery():
    charging = "not charging"
    saver = "power saver off"
    if battery.charging():
        charging = "charging"
    if battery.saver():
        saver = "power saver on"
    battery_label.set_value(battery.level() + "% / " + charging + " / " + saver)

def stop():
    sensors.stop()
    status.set_value("Stopped: readings stay on screen")

button("Start instruments", command=start_instruments, screen=home)
button("Start step counter", command=start_steps, screen=home)
button("Read battery", command=read_battery, screen=home)
button("Stop all sensors", command=stop, screen=home)

style = """
home { background-color: #0b1018; padding: 18px; }
label { color: #e6edf7; font-size: 16px; margin-bottom: 12px; }
status { color: #69e6c4; font-weight: bold; }
button { width: 100%; min-height: 48px; margin-bottom: 10px; }
"""

if __name__ == "__main__":
    run(start_screen=home, theme=Theme(mode="dark"))
```

### Existing-sensor details

- **Shake:** acceleration magnitude must exceed 2.7 g. Android filters repeated
  crossings with an 800 ms gap. The Previewer has a deliberate shake button.
- **Compass:** reports the heading derived from the rotation-vector sensor in
  whole degrees, with a one-degree change threshold. Availability checks that
  sensor; a separate magnetometer alone is not enough for this implementation.
  The current rounding can show `360` near north; treat it as equivalent to `0`.
- **Steps:** Android's raw counter runs since reboot. ApkPy subtracts the first
  reading of the watch; pause/resume retains that baseline, while stopping and
  starting again creates a new one. The first reading may require actual steps.
- **Light:** reports lux, retaining one decimal when needed. Changes smaller
  than one lux are filtered.
- **Proximity:** reports `True` for near and `False` for far. Android converts
  the raw distance using the sensor's maximum range; do not interpret the
  callback as centimetres. A callback is delivered when near/far changes.

## Permission and missing-sensor handling

The only sensor here requiring a dangerous permission is `steps`:
`android.permission.ACTIVITY_RECOGNITION` on Android 10 and later.
ApkPy declares it for a step-watching app and requests it when the watch starts.
No explicit permission declaration is needed for the example above.

`available()` only checks hardware, not whether activity access was granted.
The sensor API has no `on_error` parameter today. A missing sensor, denied
permission or failed registration must not be mistaken for a zero reading.
Use an explicit waiting/unavailable state, offer Stop/Retry, and direct the
user to app permissions when activity access has been denied.

Use literal sensor names such as `sensors.available("pressure")` and
`sensors.stop("light")` in compiled apps. Dynamic sensor names are not part of
the current compiler contract. Use a button/callback to start a watch; avoid
starting it as a side effect of importing a module.

!!! note "Keep the step registration outside nested blocks"

    Use the early-return guard in `start_steps()` above. The current compiler's
    sensor dependency scan does not traverse every nested command block; a
    `sensors.steps()` call inside an `if` can omit its permission helper in the
    generated Java. This is a known limit, not a permission-denial result.
    No library-code change is included in this documentation update.

## Complete example: acceleration monitor

```python
from apkpy_lib import Screen, Theme, label, button, sensors, json_get, run

home = Screen(id="home")
reading_label = label("Tap Start", id="reading", screen=home)

def changed(reading):
    reading_label.set_value(
        "X: " + json_get(reading, "x") + "\n"
        + "Y: " + json_get(reading, "y") + "\n"
        + "Z: " + json_get(reading, "z")
    )

def start():
    if sensors.available("accelerometer"):
        sensors.accelerometer(on_change=changed)
    else:
        reading_label.set_value("No accelerometer on this device")

def stop():
    sensors.stop("accelerometer")

button("Start", command=start, screen=home)
button("Stop", command=stop, screen=home)

style = """
home { background-color: #0b1018; padding: 20px; }
reading { color: #e6edf7; font-size: 20px; margin-bottom: 16px; }
button { width: 100%; min-height: 48px; margin-bottom: 10px; }
"""

if __name__ == "__main__":
    run(start_screen=home, theme=Theme(mode="dark"))
```

### Gyroscope and pressure variants

These replace `changed()`, `start()` and `stop()` in the acceleration-monitor app above;
keep `home`, `reading_label`, buttons and the rest of the app.

=== "Gyroscope"

    ```python
    def changed(reading):
        reading_label.set_value(
            "X: " + json_get(reading, "x") + " rad/s\n"
            + "Y: " + json_get(reading, "y") + " rad/s\n"
            + "Z: " + json_get(reading, "z") + " rad/s"
        )

    def start():
        if sensors.available("gyroscope"):
            sensors.gyroscope(on_change=changed)
        else:
            reading_label.set_value("No gyroscope on this device")

    def stop():
        sensors.stop("gyroscope")
    ```

=== "Pressure"

    ```python
    def changed(hpa):
        reading_label.set_value(hpa + " hPa")

    def start():
        if sensors.available("pressure"):
            sensors.pressure(on_change=changed)
        else:
            reading_label.set_value("No barometer on this device")

    def stop():
        sensors.stop("pressure")
    ```

For all three at once, download the complete
[Sensor Lab source](../downloads/sensors/sensor-lab.py). This is application
code, not the library's implementation. Save it as `writehere.py` in a project
using the 1.7.0 build; run `python writehere.py` for the Previewer
or `apkpy run` to produce an Android debug APK.

| Test | Expected result |
| --- | --- |
| Start sensors | present sensors begin reporting; absent ones are identified |
| Gently tilt the phone | accelerometer axes change; gravity remains included |
| Rotate the phone | gyroscope reports rotation rate |
| Stop sensors | values freeze; listeners are unregistered |
| Start again | a new watch starts without accumulating duplicate listeners |
| Leave and return on Android | requested watches suspend and resume |

## Behaviour and limits

- Check `sensors.available("pressure")` before starting pressure readings: many
  phones do not have a barometer. This tests hardware, not permission status.
- `sensors.stop("gyroscope")` stops one watch; `sensors.stop()` stops them all.
  Starting the same sensor again replaces its callback on Android.
- Android unregisters sensors on Activity pause and restores requested watches
  on resume. Sensor callbacks update the interface on its main thread.
- The new streams use `SENSOR_DELAY_UI`. This is a requested sampling rate,
  not a fixed timer. Changes smaller than 0.05 m/s², 0.01 rad/s or 0.1 hPa are
  filtered respectively. These are UI streams, not high-rate data capture.
- Axes follow the device's natural orientation and do not rotate with the UI.
  Acceleration at rest includes gravity. Gyroscope readings are rotation rates,
  not angles. Pressure alone is not a calibrated altitude reading.
- No extra dependency or permission is added for the three new sensors.
  Step counting still needs activity-recognition permission on Android 10+.
- Projects without sensor or battery calls do not receive the sensor runtime.

In the desktop Previewer, these readings are **simulated**: a panel provides
three axis sliders per motion sensor and a pressure slider. Availability means
the simulator is supported, not that the desktop or connected phone contains
the hardware. Use the installed Android app for real measurements.

### What the Previewer panel can simulate

| Control | What to do |
| --- | --- |
| Shake button | fire the no-argument callback |
| Compass dial | change heading and exercise the one-degree filter |
| Light slider | change lux and test the brightness-dependent interface |
| Near/far checkbox | exercise both boolean branches |
| Steps buttons | add one or ten simulated steps |
| Three axis sliders | change X, Y and Z independently for each motion sensor |
| Pressure slider | test values even if your phone has no barometer |
| Battery row | adjust percentage, charging and power saver, then read again |

The panel does not read the connected phone, reproduce sensor calibration or
certify hardware sampling rates. Android lifecycle suspension is native-device
behaviour: stop watches explicitly when testing screen changes in the desktop
simulator. Closing the simulator panel hides its controls; it is not a
substitute for `sensors.stop()`.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Nothing happens when registering | supply `on_change` (`on_shake` for shake); check hardware first |
| No step readings | grant activity access, then walk; this API is not a daily history service |
| Accelerometer is not zero on a desk | gravity is included; this is expected |
| Gyroscope is near zero on a desk | no rotation is expected; the change filter suppresses small noise |
| No pressure on the phone | it may lack a barometer; do not substitute fake readings on Android |
| Values display in scientific notation | `json_get` can stringify small numeric JSON values that way; their numeric meaning is unchanged |
| Old readings remain after Stop | Stop freezes the interface; clear the labels yourself if desired |
| App works in Previewer but not on the phone | simulation does not prove hardware presence, permissions or calibration |

## Verification scope

The 1.7.0 sensor implementation passed 47 focused sensor tests within a run
of 882 feature tests, plus an Android Gradle build. Sensor Lab was installed
on one Android 16 phone: real accelerometer and gyroscope readings, Start,
Stop, restart and pause/resume were checked. That phone has no barometer;
physical pressure readings have **not** been verified. Pressure simulation,
formatting, generated mapping and compilation were checked instead.

See the [Android SensorEvent reference](https://developer.android.com/reference/android/hardware/SensorEvent)
for the sensor units and coordinate system.
