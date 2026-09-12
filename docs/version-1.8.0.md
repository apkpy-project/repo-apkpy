---
title: Version 1.8.0 — The camera, and smaller releases
description: "ApkPy 1.8.0: an in-app camera with photo, video and manual controls, an embedded viewfinder component, release builds about a third of their previous size, and Python that used to fail quietly on the phone."
---

# ApkPy 1.8.0 — The camera, and smaller releases

Three things. Your app gets a camera of its own instead of borrowing the
phone's, your signed release stops carrying code it never runs, and Python that
quietly did nothing on the phone now either works or stops the build saying why.

## A camera inside your app

Until now `camera.capture()` handed the job to whatever camera app the phone
had. 1.8.0 opens a camera **your app owns**: photo and video, both lenses,
zoom, focus, exposure, flash and torch, a timer, pause and resume while
recording, a review step, and manual ISO, shutter, white balance and focus for
apps that need them.

```python
from apkpy_lib import Screen, button, camera, label, run

home = Screen(id="home")
status = label("Ready", id="status", screen=home)


def captured(success, path):
    if success:
        status.set_value(path)
    else:
        status.set_value("Nothing was kept")


def failed(reason):
    status.set_value("Camera: " + reason)


def take_photo():
    camera.open(mode="photo", lens="back", flash="auto",
                grid=True, on_result=captured, on_error=failed)


def record_clip():
    camera.record(quality="fhd", max_duration=30, audio=True,
                  on_result=captured, on_error=failed)


button("Photo", id="photo", command=take_photo, screen=home)
button("Video", id="video", command=record_clip, screen=home)
run(start_screen=home)
```

`camera.capture()` keeps the callback it always had, so an app written against
1.7.0 gains the new camera without a line changing. `camera.record(...)` is
`camera.open(mode="video", ...)` said shortly.

`on_result(success, path)` runs **once**, when the person accepts, cancels, or
a fatal error closes the camera. Cancelling is not an error, and does not call
`on_error`.

!!! warning "A path from Android is not a filesystem path"

    Android answers a `content://` URI for a file private to your app. It is a
    handle, not a location on disk, and the file is not published to the
    gallery or uploaded anywhere unless your app does that itself.

### Manual controls, and hardware that says no

```python
# 10 ms is 1/100 second. Needs a lens with manual sensor control.
camera.capture(iso=200, shutter_ms=10, white_balance="daylight",
               focus_distance=-1, on_result=captured, on_error=failed)
```

A manual setting the phone cannot honour **reports an error rather than
pretending it applied**, which is the difference between a photography app you
can trust and one that quietly lies about its settings. `camera.capabilities()`
asks the hardware what it can actually do before you offer it.

### The camera's own interface is yours to shape

`controls`, `labels`, `colors`, `title` and `button_radius` change the camera
screen without you rebuilding it:

```python
camera.capture(
    controls=["close", "shutter", "flip"],
    title="RECEIPT CAMERA",
    labels={"capture": "Take receipt", "use_photo": "Keep receipt"},
    colors={"accent": "#a5b4fc", "on_accent": "#151a2d"},
    button_radius=10,
    on_result=captured,
)
```

Controls you leave out leave **no empty slot**, and `close` and `shutter` cannot
be removed. Hiding a control hides its button, not the feature: `grid=True`
still draws the grid without a grid button, and pinch-to-zoom still works with
no zoom slider.

## A viewfinder inside your own layout

When you do not want a camera screen at all, `camera_view()` puts a live
viewfinder in your own layout, with your own buttons around it:

```python
visor = camera_view(id="visor", screen=home, lens="back", fit="cover",
                    on_ready=ready, on_capture=saved, on_error=failed)

button("Take photo", id="shoot", command=lambda: visor.capture(), screen=home)
button("Switch lens", id="flip", command=lambda: visor.flip(), screen=home)
```

No toolbar, no review step, no decisions made for you.

## Releases are about a third of the size

`apkpy release` now runs **R8**, Android's shrinker, which drops library code
your app cannot reach. A screen using two Material widgets was shipping the
whole of Material.

| same app, signed release | |
| --- | --- |
| 1.7.0 | 4,496 KB |
| 1.8.0 | **1,536 KB** |

An app pulling in Firebase, WorkManager, media3 and RecyclerView still comes to
2,085 KB.

Names are deliberately **not** obfuscated. Renaming would turn every class into
`a.b.c`, which would make `crash.last()` useless to your app and force a mapping
file to be kept for the life of every published version. The saving is in the
shrinking, so ApkPy keeps that and leaves the renaming off.

Memory drops by about 6 MB too, because unreachable code is no longer mapped
into the process. **Start-up is unchanged** — code that is never called was
never costing time, only space. Release builds take longer to produce, and
`apkpy run` is unaffected.

The [build and release guide](build-release.md) has the measurements and what to
check on a device before publishing.

## Python that used to fail quietly

A search filter is usually written like this, and on the phone it did nothing:

```python
def visible_notes():
    query = query_state.get().strip().lower()
    result = []
    for item in NOTES:
        if not query or query in item["title"].lower():
            result.append(item)
    return result
```

The whole `if` -- condition, body and all -- left the app, and the build said
nothing. The list came back empty. Several shapes behaved like that, and in
1.8.0 each one either works or stops the build saying why:

| Python | Before | 1.8.0 |
| --- | --- | --- |
| `in` / `not in` inside `and`, `or`, `not` | the `if` vanished | translated |
| `x not in y` on its own | the `if` vanished | translated |
| `"a" if q in text else "b"` | became empty text | translated |
| `for part in text.split(","):` | ran no times | translated, with Python's rules |
| `i + 1` on a `range()` index | `01` on the phone, `1` in the Previewer | translated |
| `if i % 2 == 0:` on a `range()` index | the `if` vanished | translated |
| `x = -1`, `x = a if test else b`, `x = math.pi` | the line vanished | translated |
| a condition with no translation (`is`, `0 < x < 10`) | the branch vanished, or ran on half the test | stops the build, U2033 |
| a side with no translation inside `and`, `not` or a ternary, such as `text * 2 == 4` | `Double.parseDouble("")`: a crash when it ran | stops the build, U2033 |
| `"n=%s" % n`, or `price * 2` on text from an input | became empty text | stops the build, U2033 |
| `a, b = parts`, `row["k"] = v`, `for key, value in pairs:` | the line, or the whole loop, vanished | stops the build, U2033 |
| a list comprehension at module level | the list was created empty | stops the build, U2033 |
| an f-string format such as `{n:03d}` | `7` on the phone, `007` in the Previewer | stops the build, U2033 |

`in` asks the question Python asks. Against a list, tuple, set or dict written
in the source, a list kept at module level, or a `split()` call, it is
membership; against anything else it searches the text. That is decided from
the source and never from the value, because a search box holding `[a` is text.

`split()` follows Python's rules rather than Java's. The separator is text, not
a regular expression, so `"a.b".split(".")` gives two parts; empty parts are
kept; `maxsplit` is honoured; and `split()` with nothing splits on runs of
whitespace. The generated helper was compiled and run against Python's own
`str.split` on 628 cases, with no difference.

Every case that now stops the build was already giving a different result on
the phone than in the Previewer -- or none at all. The build is simply where
you now hear about it, together with a form that does compile.

!!! note "What still differs without stopping the build"

    ApkPy decides from the source, not from the running value, and a few shapes
    still give a different answer: `text[0]` on text, `+` on a function's
    parameter, and `in` against a local variable that holds a list. The
    [compatibility page](compatibility.md#the-python-apkpy-translates) lists
    each one and what to write instead.

## The benchmark, measured again

Fixing those failures showed that the ApkPy row on the
[benchmark page](benchmark.md) had measured an app whose list was empty: its
comprehension at module level had compiled to nothing. The notes app was
rewritten so it builds on 1.8.0, checked on the device to show, filter, add
and search its 100 notes, and timed again beside BeeWare/Toga in the same
session, on the Pixel 9 emulator:

| Same session, debug builds | APK | Cold start, first three | PSS |
| --- | ---: | ---: | ---: |
| **ApkPy 1.8.0 candidate** | **5.37 MiB** | **2,565 ms** | **67.0 MiB** |
| BeeWare/Toga | 34.46 MiB | 5,536 ms | 83.4 MiB |

About twice as soon to start, about a fifth less memory, and a 6.4x smaller
APK. The 590 ms published before is withdrawn: it was never a like-for-like
number. Times on this emulator also moved by more than 2x within one day, which
is why the comparison stays inside one session. The benchmark page has the
method and every session.

## In the Previewer

The camera is drawn **inside the phone frame**, not in a window of its own, and
it never opens your webcam or microphone. It says so on screen:
`PREVIEW SIMULATOR · NO CAMERA ACCESS`.

The viewfinder shows a synthetic calibration scene, or an image you import. The
files it produces are real: photos are genuine JPEGs, and video is a playable
MP4 — and the footer states exactly what that MP4 is rather than implying it
matches the phone: `Video simulation: 640px · 12 fps · no audio`.

Zoom, crop, mirroring and white balance affect the output. Focus, flash and
manual exposure are **rehearsals**, not measurements of real optics. Pause and
resume, duration limits, review, retake, cancellation and every callback work
locally, so the branches your app has to handle can all be exercised at a desk.

## Verification, and what is not verified

| Check | Result |
| --- | --- |
| Feature suite | 1,040 tests passed |
| `split()` helper | compiled and run against `str.split` on 628 cases: no difference |
| Example apps and documented snippets | 92 transpiled with the engine from before and after these changes: every app that built still builds; two scripts that are not apps now stop, both on code that was being dropped |
| Transpiler suite | 258 checks passed |
| Previewer, seen not assumed | photo mode, video mode with Record/Pause/Mic, grid, zoom and EV sliders, and the honest simulator banners, all photographed |
| Review contract | Retake and Use photo/video are fixed in both runtimes, not optional |
| Android build | a generated project compiles and installs |
| EXIF from manual settings | reported as ISO 200 and 10 ms on a device — **taken from the implementation report, not re-measured here** |
| Video with audio, lens switching, rotation | reported working on one device — **not re-measured here** |
| Other phone models | **not verified**: one device, one manufacturer |

Not implemented, and not planned for this release: RAW/DNG, vendor HDR, night
and portrait modes, slow motion, concurrent cameras, live frame analysis,
publishing to the gallery, and capture from the background or lock screen.
Barcodes remain the separate `scan` API.

The [camera guide](guides/camera.md) has the full option tables, the interface
customisation contract, and the Previewer's limits in detail.
