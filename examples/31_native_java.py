"""Your own Java, for the parts ApkPy does not translate yet.

The battery level and the vibrator are both one Android call away and neither
has an ApkPy API, so this app declares them itself. Each block has two halves:
the Java that runs on the phone, and the preview= that answers on the desktop,
because the Previewer has no Android to ask.

Run it with `apkpy preview` to see the simulated answers, and `apkpy run` to
read the real battery on a phone.
"""
from apkpy_lib import Screen, Theme, button, label, native, run

Theme(mode="dark")

home = Screen(id="home")
label("YOUR OWN JAVA", id="kicker", screen=home)
reading = label("Toca para ler a bateria", id="reading", screen=home)
status = label("", id="status", screen=home)

# A value: arguments in, one String out. `context` is handed to the block, so
# it never reaches into the generated Activity.
battery = native.java(
    "batteryLevel",
    imports=["android.os.BatteryManager", "android.content.Context"],
    code="""
        BatteryManager bm = (BatteryManager)
                context.getSystemService(Context.BATTERY_SERVICE);
        int level = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);
        return String.valueOf(level);
    """,
    preview=lambda: "87",
)

# An answer that arrives later goes through `done`, which may be called from
# any thread: ApkPy moves it to the UI thread before your callback runs.
buzz = native.java_async(
    "buzz",
    args=("millis",),
    imports=["android.os.Vibrator", "android.os.VibrationEffect"],
    code="""
        try {
            Vibrator vibrator = (Vibrator) context.getSystemService(
                    android.content.Context.VIBRATOR_SERVICE);
            if (vibrator == null || !vibrator.hasVibrator()) {
                done.run(false, "este telemóvel não vibra");
                return;
            }
            vibrator.vibrate(VibrationEffect.createOneShot(
                    Long.parseLong(millis.trim()),
                    VibrationEffect.DEFAULT_AMPLITUDE));
            done.run(true, "ok");
        } catch (Exception problem) {
            done.run(false, String.valueOf(problem.getMessage()));
        }
    """,
    preview=lambda millis, done: done(True, "ok"),
)

# The build around the code: a permission the vibrator needs, and a keep rule
# for anything R8 could only reach by reflection.
native.manifest(permission="android.permission.VIBRATE")
native.keep("com.example.sdk.**")


def buzzed(ok, reason):
    status.set_value("Vibrou" if ok else "Sem vibração: " + reason)


def read_battery():
    reading.set_value("Bateria: " + battery() + "%")
    buzz("120", on_result=buzzed)


button("Ler bateria", id="read", icon="bolt", screen=home,
       command=read_battery)

style = """
home { background-color: #0B0F14; padding: 20px; }
kicker { color: #4ADE80; font-size: 11px; font-weight: bold; margin-bottom: 10px; }
reading { color: #F4F6FB; font-size: 22px; font-weight: bold; margin-bottom: 6px; }
status { color: #9AA6B2; font-size: 13px; margin-bottom: 14px; }
read { background-color: #1F3A5F; color: #FFFFFF; border-radius: 14px; min-height: 48px; font-weight: bold; }
"""

run(start_screen=home)
