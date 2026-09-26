---
title: Your own Java
description: "native.java() and native.java_async(): declare a Java block with a desktop answer, plus the Gradle dependency, manifest line and R8 rule it needs."
---

# Your own Java

Looking for one that is already written? [Native recipes](native-recipes.md) has six, compiled before they were published.

ApkPy translates a documented subset of Python. When the thing you need is not
in it, the answer used to be "wait for the next release" -- and editing the
generated project in Android Studio is not an answer, because `apkpy build`
rewrites that project every time.

`native` gives the gap a shape. You do not paste Java into the middle of an
app; you declare a **function** with a name, arguments and one answer, and you
say what the Previewer answers instead.

```python
from apkpy_lib import Screen, button, label, native, run

home = Screen(id="home")
reading = label("", id="reading", screen=home)

battery = native.java(
    "batteryLevel",
    imports=["android.os.BatteryManager", "android.content.Context"],
    code="""
        BatteryManager bm = (BatteryManager)
                context.getSystemService(Context.BATTERY_SERVICE);
        return String.valueOf(bm.getIntProperty(
                BatteryManager.BATTERY_PROPERTY_CAPACITY));
    """,
    preview=lambda: "87",
)


def show():
    reading.set_value("Battery: " + battery() + "%")


button("Read", id="read", command=show, screen=home)
run(start_screen=home)
```

## Why `preview=` is not optional

The Previewer cannot run Java. A block without a desktop answer would work on
the phone and do nothing on your desk -- the exact divergence that made
[1.6.0](../version-1.6.0.md) and [1.8.0](../version-1.8.0.md) what they were.
So `preview=` is required, and the build stops without it.

`preview=` is a promise you make. ApkPy cannot check that your Java and your
Python agree; it can only make sure both exist.

## An answer that arrives later

Most Android APIs call you back. `native.java_async()` hands your block a
`done`, which you may call from **any thread**: the generated wrapper moves it
to the UI thread before your Python callback runs.

```python
buzz = native.java_async(
    "buzz",
    args=("millis",),
    imports=["android.os.Vibrator", "android.os.VibrationEffect"],
    code="""
        Vibrator vibrator = (Vibrator) context.getSystemService(
                android.content.Context.VIBRATOR_SERVICE);
        if (vibrator == null || !vibrator.hasVibrator()) {
            done.run(false, "no vibrator");
            return;
        }
        vibrator.vibrate(VibrationEffect.createOneShot(
                Long.parseLong(millis.trim()),
                VibrationEffect.DEFAULT_AMPLITUDE));
        done.run(true, "ok");
    """,
    preview=lambda millis, done: done(True, "ok"),
)


def buzzed(ok, reason):
    status.set_value("Buzzed" if ok else "No buzz: " + reason)


buzz("120", on_result=buzzed)
```

`on_result` has to be a function you defined with `def`: the generated Java
calls it by name, so a lambda has nothing to call. It is answered `(ok, value)`,
like every other callback in ApkPy.

## What a block is given, and what it is not

| Inside the block | |
| --- | --- |
| the arguments you declared in `args=` | all `String`, like everything else the generator writes |
| `context` | the Activity, as a `Context` |
| `done` | `java_async` only: `done.run(true, "value")` |

A block does **not** see the inside of the generated code. Those fields are
named by the generator and change between versions; an app reaching into them
would break on an upgrade with nothing to warn you.

## The build around the code

An SDK is rarely just code. These three go with it:

```python
native.gradle("implementation 'com.example:sdk:2.1.0'")
native.manifest(permission="android.permission.VIBRATE")
native.manifest(feature="android.hardware.nfc")
native.manifest(xml='<service android:name="com.example.sdk.SyncService" />')
native.keep("com.example.sdk.**")
```

- `gradle` adds one dependency line to the generated `app/build.gradle`.
- `manifest(permission=)` asks for it like any permission ApkPy asks for;
  `manifest(feature=)` writes `<uses-feature ... required="false">`, so the Play
  Store still shows your app to phones without that hardware; `manifest(xml=)`
  adds your own element inside `<application>`.
- `keep` writes an R8 rule. Since 1.8.0 `apkpy release` shrinks the app, and a
  class only reached by reflection disappears without one.

## What the generator writes

Each block becomes a private method of the screen's Activity:

```java
/** native.java("batteryLevel") -- writehere.py:8 */
private String _apkpyNative_batteryLevel() {
    final android.content.Context context = this;
    BatteryManager bm = (BatteryManager)
            context.getSystemService(Context.BATTERY_SERVICE);
    return String.valueOf(bm.getIntProperty(
            BatteryManager.BATTERY_PROPERTY_CAPACITY));
}
```

Run `apkpy build` and read it. The Java inside is yours, unchanged; a mistake
in it is a `javac` error about your own lines.

## What stops the build

Every one of these is `U2035`, and each names the line:

- `preview=` missing, or not something callable;
- `code=` that is an f-string, or any argument computed while the app runs --
  the build **reads** your module, it never runs it;
- a `native.java` block with no `return`, or a `native.java_async` block that
  never calls `done`;
- a call with the wrong number of arguments, a keyword the block does not take,
  or an async block used where a value is expected;
- `on_result=` that is not a function you defined;
- a block called from the body of a `background_job`: a block is a method of a
  screen's Activity, and a job runs in a Worker with no screen;
- `native.manifest(xml=)` that rewrites `<application>`, and
  `native.gradle()` that is not a dependency line.

## The boundary of the guarantee

Inside the translated subset, ApkPy promises the Previewer and the phone agree,
and that promise is tested. Inside a `native` block that promise is yours: your
Java and your `preview=` are two pieces of code that only you can keep in step.

That is the trade. It is worth making when the alternative is waiting -- and
worth telling us about, because what people put in these blocks is the list of
what ApkPy should translate next.
