---
title: Camera
description: "Photo and video inside your own app: lenses, zoom, flash, timer, manual ISO and shutter, an embedded viewfinder, and what the Previewer really simulates."
---

# Camera

Two ways to photograph. `camera.open()` opens a camera **screen** your app owns,
with its own controls and a review step. `camera_view()` puts a live viewfinder
**inside your layout**, with your own buttons around it.

Both are new in [1.8.0](../version-1.8.0.md).

## The camera screen

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
    camera.open(mode="photo", lens="back", flash="auto", grid=True,
                on_result=captured, on_error=failed)


button("Photo", id="photo", command=take_photo, screen=home)
run(start_screen=home)
```

| Call | What it does |
| --- | --- |
| `camera.open(...)` | The camera screen, in `mode="photo"` or `"video"` |
| `camera.capture(...)` | Photo. The 1.7.0 callback, now with the in-app camera |
| `camera.record(...)` | `camera.open(mode="video", ...)`, said shortly |
| `camera.capabilities(on_result=...)` | What this hardware can actually do |
| `camera.available()` | Whether there is a camera at all |

`capture()` and `record()` take every option below except `mode`, and everything
after `on_result` is a named argument.

### The two callbacks

`on_result(success, path)` runs **once** — when the person accepts, cancels, or
a fatal error closes the camera.

`on_error(reason)` is optional and receives one string, before an unsuccessful
result, for failures that close the camera. **Cancelling is not an error.** A
photo that fails but can be retried stays inside the camera, so the person can
simply try again.

!!! warning "The path is not a filesystem path on Android"

    Android answers a `content://` URI for a file private to your app. It is a
    handle, not a location on disk. Nothing is published to the gallery or
    uploaded unless your app does it. The Previewer answers a filename.

### Options

| Option | Values and meaning |
| --- | --- |
| `mode` | `photo` / `video` |
| `lens` | `back` / `front`. A missing lens falls back, visibly |
| `flash` | `off` / `on` / `auto`. Photo only, needs a flash, off under manual exposure |
| `quality` | `sd` / `hd` / `fhd` / `uhd`. A video *preference*, with a supported fallback |
| `aspect_ratio` | `4:3` / `16:9`. A preference for photo and preview, not a promise about video dimensions |
| `zoom` | Ratio from `1.0`, clamped to the lens's range |
| `exposure` | Compensation **index**, not EV. The step and range come from `capabilities()` |
| `timer` | Seconds, 0–30 |
| `grid` | The framing grid |
| `audio` | Microphone permission and sound while recording. `False` records silently |
| `mirror` | Mirror the front lens, default `True` |
| `max_duration` | 1–3600 seconds, default 60 |
| `jpeg_quality` | 1–100, default 95. Not a resolution setting |
| `iso`, `shutter_ms` | Both `0` for automatic, or both positive. ISO, and **milliseconds** |
| `focus_distance` | `-1` autofocus, `0` infinity, positive is **diopters** |
| `white_balance` | `auto`, `daylight`, `cloudy`, `incandescent`, `fluorescent` |

### Manual settings tell the truth

```python
# 10 ms is 1/100 second. Needs a lens with manual sensor control.
camera.capture(iso=200, shutter_ms=10, white_balance="daylight",
               focus_distance=-1, on_result=captured, on_error=failed)
```

A setting the hardware cannot honour **reports an error instead of pretending it
applied**. Ask first if you mean to offer manual controls in your interface:

```python
def hardware_known(info):
    # JSON on Android, a dict in the Previewer. json_get() reads both.
    status.set_value(str(info))


camera.capabilities(on_result=hardware_known)
```

Capabilities cover lenses, flash, zoom, the exposure range and step, ISO and
shutter ranges, focus range, white-balance modes, and a `simulated` flag that is
true in the Previewer. A RAW flag in there describes the **hardware** — this API
does not capture RAW.

## Shaping the camera's interface

`controls`, `labels`, `colors`, `title` and `button_radius` reshape the camera
screen. Leave them out and the default interface is unchanged. Each opening
carries its own configuration and changes nothing else in your app.

```python
camera.capture(
    controls=["close", "shutter", "flip"],
    title="RECEIPT CAMERA",
    labels={"close": "Back", "capture": "Take receipt",
            "flip": "Switch lens", "use_photo": "Keep receipt"},
    colors={"accent": "#a5b4fc", "on_accent": "#151a2d"},
    button_radius=10,
    controls_position="bottom",
    grid=False, audio=False,
    on_result=captured,
)
```

| Option | Contract |
| --- | --- |
| `controls` | `None` for all of them; a list to choose and order. Omitted controls leave **no gap** |
| `title` | 1–48 characters |
| `labels` | A partial map. Anything you leave out keeps its default |
| `colors` | A partial palette of opaque `#RRGGBB` |
| `button_radius` | 0–32, dp on Android and logical pixels in the Previewer |
| `controls_position` | `auto` (bottom in portrait, side when wide), or `top` / `bottom` |

Control names: `close`, `pro`, `flash`, `timer`, `grid`, `quality`, `ratio`,
`torch`, `zoom`, `exposure`, `flip`, `shutter`, `pause`, `mode`, `audio`.

Palette keys: `background`, `surface`, `accent`, `on_accent`, `text`, `muted`.

Label keys are the control names plus `capture`, `record`, `stop`, `resume`,
`retake`, `use_photo` and `use_video`.

**What cannot be taken away:**

- `close` and `shutter` are required. An unknown, duplicated or missing required
  name is an error, not a silent shrug.
- Review always keeps **Retake** and **Use photo/video**, and recording always
  uses the shutter as Stop. Those cannot vanish mid-capture.
- Hiding a control hides the button, not the feature. `grid=True` still draws
  the grid; pinch and tap-to-focus still work with no slider on screen.

Close and Pro stay in the header; the rest follow your order, wrapping after
three buttons, with sliders on a full row. It is a responsive panel, not
free-form placement. For an Android build, `controls`, `labels` and `colors`
must be **literal** lists and dictionaries written in the call.

## The embedded viewfinder

```python
visor = camera_view(id="visor", screen=home, lens="back", fit="cover",
                    on_ready=ready, on_capture=saved, on_error=failed)

button("Take photo", id="shoot", command=lambda: visor.capture(), screen=home)
button("Switch lens", id="flip", command=lambda: visor.flip(), screen=home)
```

```css
visor { width: 100%; height: 300px; margin-bottom: 12px; }
```

No toolbar, no review, no mandatory anything — a live picture in your layout and
ordinary ApkPy widgets around it. Arguments: `lens`, `flash`, `zoom`, `mirror`,
`fit` (`cover` or `contain`), `aspect_ratio`, `autostart`, and the three
callbacks. Change things at runtime with the instance's methods; the values in
the constructor must be literals for an Android build.

## What the Previewer really does

The camera is drawn **inside the phone frame**, not in a separate window, and it
never starts your webcam or microphone. The screen says so:
`PREVIEW SIMULATOR · NO CAMERA ACCESS`.

- The viewfinder shows a synthetic calibration scene, or an image you import.
  Imported files are never overwritten.
- **The files are real.** Photos are genuine JPEGs. Video is a playable MP4, and
  the footer states exactly what it is rather than implying it matches a phone:
  `Video simulation: 640px · 12 fps · no audio`.
- Zoom, crop, mirroring and white balance affect the output. **Focus, flash and
  manual exposure are rehearsals**, not measurements of real optics or light.
- Pause and resume, duration limits, review, retake, cancellation and every
  callback work locally — so every branch your app must handle can be exercised
  at a desk.
- **Pro** also simulates a refused permission, an unavailable camera and a
  storage failure. Those are simulator tools, not Android controls.

## On Android

CameraX and ExifInterface are added **only** when your app uses the camera.
Manual controls go through Camera2 interop. Encoding and review decoding happen
off the UI thread, and your callbacks arrive on it. Callback routing and a
pending review survive the screen being rebuilt. Camera and torch are released
on exit.

Backgrounding the camera stops recording: it never records out of sight.

### Not in this API

RAW/DNG, vendor HDR, night and portrait modes, slow motion and high-speed
frame rates, concurrent cameras, choosing a physical lens, live frame analysis,
publishing to the gallery, and capture from the background or the lock screen.
Barcodes are the separate [`scan`](../native-features.md) API.

UHD, long recordings and manual settings all depend on the hardware, on free
storage and on how hot the phone is. Ask `capabilities()`, and handle
`on_error`.
