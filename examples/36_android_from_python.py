"""Pocket tools - Android reached from Python.

Six things reached through Android's own classes -- vibrate, read the
battery, name the phone, count its sensors, keep the screen on, open a page --
each one a function written in Python. Some of them ApkPy also has a call for
(haptics, display.keep_on(), browser.open()); written here they show the way
to anything it has none for.

There is no Python on the phone, so nothing there looks a class up by name.
The body of a @native function is translated to Java when the app is built,
and every class, method and argument in it is checked against android.jar:
a misspelt method stops the build with the line. So does something newer than
the oldest phone the app runs on -- VibrationEffect arrived in Android 8, and
buzz() says what an Android 7 phone does instead.

On the desk the body never runs: preview= answers.

Needs ApkPy 1.13.0.
"""

from apkpy_lib import *

home = Screen(id="home", scroll=True)

Build = native.use("android.os.Build")
Vibrator = native.use("android.os.Vibrator")
VibrationEffect = native.use("android.os.VibrationEffect")
BatteryManager = native.use("android.os.BatteryManager")
Intent = native.use("android.content.Intent")
Uri = native.use("android.net.Uri")
WindowManager = native.use("android.view.WindowManager")
SensorManager = native.use("android.hardware.SensorManager")
Sensor = native.use("android.hardware.Sensor")

native.manifest(permission="android.permission.VIBRATE")


@native(preview=lambda ms: "buzzed")
def buzz(ms: int):
    vibrator = context.getSystemService(Vibrator)
    if not vibrator.hasVibrator():
        return "this phone has no vibrator"
    if Build.VERSION.SDK_INT >= 26:
        vibrator.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE))
    else:
        vibrator.vibrate(ms)
    return "buzzed"


@native(preview=lambda: 87)
def battery() -> int:
    manager = context.getSystemService(BatteryManager)
    return manager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)


@native(preview=lambda: "the desktop Previewer")
def phone_name():
    return Build.MANUFACTURER + " " + Build.MODEL + ", Android " + Build.VERSION.RELEASE


@native(preview=lambda: "3 sensors")
def sensors():
    manager = context.getSystemService(SensorManager)
    count = 0
    for sensor in manager.getSensorList(Sensor.TYPE_ALL):
        count += 1
    return f"{count} sensors"


@native(preview=lambda on: None)
def keep_awake(on: bool):
    window = activity.getWindow()
    if on:
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    else:
        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)


@native(preview=lambda url: None)
def open_page(url):
    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))


label("Android from Python", id="title", variant="title", screen=home)
label("Each button calls a function written in Python that runs as Java.", id="lead", screen=home)
status = label("Nothing yet", id="status", screen=home)


def do_buzz():
    status.set_value("Vibration: " + buzz(150))


def do_battery():
    status.set_value("Battery: " + battery() + "%")


def do_name():
    status.set_value(phone_name())


def do_sensors():
    status.set_value(sensors())


def awake(value):
    keep_awake(value)
    status.set_value("Screen stays on: " + value)


def do_page():
    open_page("https://repo-apkpy.pages.dev/")


button("Vibrate", id="b_buzz", command=do_buzz, screen=home)
button("Battery level", id="b_battery", command=do_battery, screen=home)
button("Which phone is this?", id="b_name", command=do_name, screen=home)
button("Count the sensors", id="b_sensors", command=do_sensors, screen=home)
inputs("Keep the screen on", id="awake", type="switch", on_change=awake, screen=home)
button("Open the ApkPy site", id="b_page", variant="outlined", command=do_page, screen=home)

style = """
home {
    padding: 20px;
    gap: 12px;
}
status {
    font-size: 18px;
    font-weight: bold;
    margin-top: 8px;
    margin-bottom: 8px;
}
"""

run(start_screen=home, theme=Theme(primary="#0B6E4F"))
