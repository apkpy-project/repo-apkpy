"""USB/device test app for ApkPy's motion and environment sensors.

Run this file for the Previewer, or `apkpy run` from this directory.
No network, files, location, step-counting or personal data is accessed.
"""
from apkpy_lib import Screen, Theme, app_bar, label, button, container, sensors, json_get, run

home = Screen(id="home")
app_bar("Sensor Lab", screen=home)
label("MOTION + ENVIRONMENT", id="eyebrow", screen=home)
label("See what your phone feels.", id="heading", screen=home)
label("Start, then gently tilt or rotate the phone. Stop freezes the readings. Desktop readings are simulated.",
      id="intro", screen=home)
status = label("Ready - nothing is being monitored", id="status", screen=home)

acc_card = container(id="acc_card", screen=home)
label("Accelerometer / m/s2", id="acc_title", parent=acc_card)
acc = label("Not started", id="acc", parent=acc_card)
gyro_card = container(id="gyro_card", screen=home)
label("Gyroscope / rad/s", id="gyro_title", parent=gyro_card)
gyro = label("Not started", id="gyro", parent=gyro_card)
pressure_card = container(id="pressure_card", screen=home)
label("Pressure / hPa", id="pressure_title", parent=pressure_card)
pressure = label("Not started", id="pressure", parent=pressure_card)


def acceleration_changed(reading):
    acc.set_value("X " + json_get(reading, "x") + "\nY " + json_get(reading, "y") + "\nZ " + json_get(reading, "z"))


def rotation_changed(reading):
    gyro.set_value("X " + json_get(reading, "x") + "\nY " + json_get(reading, "y") + "\nZ " + json_get(reading, "z"))


def pressure_changed(value):
    pressure.set_value(value + " hPa")


def start_readings():
    if sensors.available("accelerometer"):
        acc.set_value("Waiting for a reading...")
        sensors.accelerometer(on_change=acceleration_changed)
    else:
        acc.set_value("Not available on this device")
    if sensors.available("gyroscope"):
        gyro.set_value("Waiting for a reading...")
        sensors.gyroscope(on_change=rotation_changed)
    else:
        gyro.set_value("Not available on this device")
    if sensors.available("pressure"):
        pressure.set_value("Waiting for a reading...")
        sensors.pressure(on_change=pressure_changed)
    else:
        pressure.set_value("No barometer on this device")
    status.set_value("Live - tilt or rotate the phone")


def stop_readings():
    sensors.stop()
    status.set_value("Stopped - readings are frozen")


button("Start sensors", id="start", icon="play_arrow", command=start_readings, screen=home)
button("Stop sensors", id="stop", variant="outlined", command=stop_readings, screen=home)

style = """
home { background-color: #0b1018; padding: 18px; }
label { color: #e6edf7; font-size: 14px; }
eyebrow { color: #69e6c4; font-size: 11px; margin-top: 12px; }
heading { font-size: 26px; font-weight: bold; margin-top: 10px; margin-bottom: 10px; }
intro { color: #a4b3c8; margin-bottom: 12px; }
status { color: #69e6c4; margin-bottom: 12px; }
acc_card, gyro_card, pressure_card { background-color: #151e2b; padding: 14px; border-radius: 16px; margin-bottom: 10px; }
acc_title, gyro_title, pressure_title { color: #a4b3c8; font-size: 12px; margin-bottom: 8px; }
acc, gyro { font-size: 16px; min-height: 64px; }
pressure { font-size: 18px; }
start, stop { width: 100%; min-height: 48px; margin-bottom: 10px; }
"""

if __name__ == "__main__":
    run(start_screen=home, theme=Theme(mode="dark", primary="#69e6c4"))
