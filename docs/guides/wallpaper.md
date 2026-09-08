---
title: Static wallpapers
description: Preview and confirm a static Android wallpaper with ApkPy, choose home or lock screen, handle errors and test safely on desktop.
---

# Static wallpapers

!!! info "Available in ApkPy 1.7.0"

    Install ApkPy 1.7.0 or newer and regenerate your Android project.
    The confirmation step is mandatory on Android and in the Previewer.

Use `wallpaper` for personalisation apps, photo galleries or a small “use as
wallpaper” action. Every request opens an image preview and asks the user to
confirm. There is no silent mode.

## API

| Method | Behaviour |
| --- | --- |
| `wallpaper.available()` | Boolean: Android supports wallpapers and allows this app to change them. Always `True` in desktop simulation. |
| `wallpaper.set(source, target="home", on_result=None)` | Load the image, show confirmation and apply only after **Apply**. Returns no value. |

`target` accepts `"home"`, `"lock"` or `"both"`. `on_result(success, reason)`
receives a boolean and a stable reason string on the UI thread. Start from a
visible screen, normally a button or image-picker callback. Background jobs
cannot open this confirmation.

The preview displays the selected image without editing it. Android and the
launcher can crop or zoom the final wallpaper; the dialog is not a pixel-exact
lock-screen simulator. On devices where lock-screen wallpaper follows the home
wallpaper, the OEM's linking behaviour still applies.

## Complete example: choose, review, apply

Copy this into `writehere.py` with ApkPy 1.7.0 or newer:

```python
from apkpy_lib import Screen, Theme, app_bar, label, button, gallery, wallpaper, run

home = Screen(id="home", scroll=True)
app_bar("My wallpaper", screen=home)
label("Choose an image. Review it before changing your home screen.", screen=home)
status = label("Nothing has changed.", id="status", screen=home)


def finished(success, reason):
    if success:
        status.set_value("Completed: " + reason)
    else:
        status.set_value("Not changed: " + reason)


def image_chosen(success, path):
    if success:
        wallpaper.set(path, target="home", on_result=finished)
    else:
        status.set_value("No image selected.")


def choose():
    if wallpaper.available():
        gallery.pick(on_result=image_chosen)
    else:
        status.set_value("Wallpaper changes are not allowed on this device.")


button("Choose image", command=choose, screen=home)
run(start_screen=home, theme=Theme(mode="dark", primary="#7856FF"))
```

Change `target="home"` to `"lock"` or `"both"` to choose the destination.
The complete [Wallpaper Lab app source](../downloads/wallpaper/wallpaper-lab.py)
includes all three target buttons and status messages.

## Image sources

- **Gallery:** pass the path from `gallery.pick(on_result=...)`. Android supplies
  a `content://` URI; desktop supplies a local path. Treat it as an opaque handle.
- **File picker:** pass the `path` from `files.pick(types=["image/*"], ...)`.
  Its callback has five parameters, unlike the gallery's two.
- **Camera:** the successful `camera.capture()` result can be used too.
- **Bundled image:** a direct string literal such as
  `wallpaper.set("assets/background.jpg", target="both", on_result=finished)`
  is resolved relative to the project and copied into Android assets. A missing
  file is a build error with the source line.
- **Runtime file:** a dynamically supplied local path must exist in the running
  app's accessible storage. Relative runtime paths use Android's private files
  directory. A path stored in a variable is **not** automatically bundled.

There is no automatic HTTP download. Download through your app's explicit file
workflow first, then pass the accessible file. No broad storage permission is
needed for an image already granted by the picker.

Use static JPEG or PNG for the most predictable cross-platform result. Decoder
support for other formats depends on Android/Pillow; SVG and live wallpapers
are not supported. Animated formats are not animated by this API.

## Result reasons

| Reason | Success | Meaning / next action |
| --- | --- | --- |
| `ok` | `True` | Android returned a non-zero wallpaper ID after the user confirmed. |
| `simulated` | `True` | Previewer confirmation succeeded. The computer wallpaper was not changed. |
| `cancelled` | `False` | The user pressed Cancel, Back or closed the confirmation. |
| `busy` | `False` | Another wallpaper request is preparing, open or applying; wait for its result. |
| `unsupported` | `False` | Wallpapers are unavailable for this Android user/device. |
| `not_allowed` | `False` | Policy or permission prevented the change. |
| `invalid_target` | `False` | A runtime target is not `home`, `lock` or `both`. Invalid literals fail during compilation. |
| `invalid_image` | `False` | Missing/unreadable source, unsupported format or decoding/memory limit. Choose another image. |
| `unavailable` | `False` | No usable foreground screen, or the confirmation could not open. Retry from a visible button. |
| `failed` | `False` | Android could not apply the image. Do not report success. |

A second request does not replace the first callback. A write already
confirmed and started is not rolled back if the screen closes.

Your callback runs once per request in the ordinary case. It runs a second
time, with the same answer, when Android rebuilds your screen straight after
the change -- see the section below, which is the one surprise in this API.

## Applying a wallpaper rebuilds your screen

This is the part that catches people, so it is worth reading before you write
the callback.

Changing the wallpaper changes the system colour palette. A changed palette is
a **configuration change**, so about a second after your callback runs Android
destroys your Activity and builds a new one from the layout. Anything the
callback wrote onto the screen is wiped by that rebuild.

Measured on a phone running Android 16: the window handle changed from
`ac84994` to `644ddc7`, the status line correctly read `Completed: ok`, and a
second later the rebuilt screen showed its original text again. It looked
exactly like nothing had happened, while the wallpaper had in fact changed.

**ApkPy handles this for you.** The answer outlives the screen: the rebuilt
screen is told the same result again, so your status line survives.

Two things follow for your code:

```python
def finished(success, reason):
    # Safe: writing to the screen. If the rebuild wipes it, ApkPy calls this
    # again on the new screen and it is written a second time.
    status.set_value("Completed: " + reason if success else "Not changed: " + reason)
```

```python
def finished(success, reason):
    # Careful: this can run twice for one wallpaper change, so the person
    # would see two toasts. Prefer writing to the screen.
    toast(reason)
    counter.set_value(str(int(counter.get_value()) + 1))   # counts 2, not 1
```

The repeat only happens when Android really did rebuild the screen. Leaving the
app normally and coming back does **not** replay the answer -- ApkPy tells the
two apart with `isChangingConfigurations()`, so a screen the person simply
walked away from has already had its say.

Anything you must count or send exactly once belongs behind a flag of your own:

```python
done = state("false", id="done")


def finished(success, reason):
    status.set_value("Completed: " + reason)
    if success and done.get() == "false":
        done.set("true")
        analytics_ping()          # once, whatever the rebuild does
```

That guard works because `state()` lives in the app's process rather than in
the screen -- it is exactly what the rebuild does *not* reset. A flag kept in a
label would be wiped along with everything else.

!!! note "This is not only about wallpapers"

    Any Activity rebuild -- rotating the phone, a system font-size change --
    resets what your code wrote onto a screen, because `set_value()` writes
    straight to the view. The wallpaper case is handled because ApkPy causes
    it; the general case is on the roadmap.

## Android implementation and permissions

Only apps that call `wallpaper.set()` receive `android.permission.SET_WALLPAPER`
in the manifest. This is a normal manifest permission, not a runtime permission
prompt. Calling `available()` alone does not add it. Apps that never use the
API receive no wallpaper helper or additional dependency.

The implementation uses Android's `WallpaperManager`, support/policy checks,
and `FLAG_SYSTEM`/`FLAG_LOCK` on API 24+. The Android APIs are described in the
[official WallpaperManager reference](https://developer.android.com/reference/android/app/WallpaperManager).

Image decoding, EXIF orientation and the final write run on one background
executor. Decoding is sampled to a maximum edge of 2,048 pixels to bound memory;
this API does not promise original-resolution 4K wallpapers. The confirmed
image is sent with Android backup disabled. No current wallpaper is read,
exported or retained, and this API adds no network request.

## Previewer and testing limits

The desktop confirmation has **Cancel** and **Simulate apply**. It displays
the target and an explicit simulation notice. It never calls Windows wallpaper
APIs. Large desktop images are reduced; images above 64 megapixels are rejected
before full decoding.

The local implementation has tests for generated Java, conditional assets and
permissions, invalid arguments, callbacks, duplicate requests, cancellation and
actual Tk button commands. A real generated Android project compiles with
Gradle, including the direct bundled-image button.

**Verified on a phone.** On a Xiaomi running Android 16: choosing from the
gallery, the confirmation dialog, Apply, and the status line surviving the
screen rebuild that follows. Repeated applications in one session were checked
too, because a wallpaper request that never finished used to answer `busy` to
every later one.

Still test Cancel and each target you support on your own devices. OEMs differ
on whether the lock screen follows the home screen, and on how aggressively
they crop.
