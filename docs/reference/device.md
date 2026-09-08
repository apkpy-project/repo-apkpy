---
title: Device and Android API
description: Permissions, push, maps, location, notifications and Android integrations.
---

# Device and Android API

| Object/API | Purpose |
| --- | --- |
| `declare_permissions` / `permissions` | manifest and runtime permissions |
| `notify` | Android system notification |
| `notifications` | channels, permission checks and cancellation — 1.7.0 |
| `push` | FCM listeners, token, topics and Preview simulation |
| `share` | native share sheet |
| `clipboard` | system clipboard |
| `camera` / `gallery` | capture and media picker (images) |
| `files.pick` / `upload_button` | pick any file type, and pick-then-upload |
| `location` | current, continuous and background location |
| `map_view` | map tiles, markers, routes and user layer |
| `routes` / `route_points` | cancellable route calculation and decoding |
| `service` | periodic and one-shot background work |
| `background_job` | persistent queue: constraints, retries, cancellation and observable progress |
| `biometrics` | the system fingerprint or face prompt, and why a check ended |
| `bluetooth` | classic serial (SPP): paired devices, lines in and out |
| `ble` | Bluetooth Low Energy: scan, connect, and the Nordic UART default |
| `billing` | Play in-app purchases and subscriptions, acknowledged for you |
| `apps` | installed app inspection |
| `sensors` | shake, compass, steps, light and proximity; three new streams in the 1.7.0 |
| `battery` | charge percentage, charging and power-saving state |
| `wallpaper` | static wallpaper preview and confirmation — 1.7.0 |

Use [Background jobs](../background-jobs.md),
[Firebase push](../guides/push-firebase.md),
[Maps and continuous location](../guides/maps-tracking.md) and
[Native Android features](../native-features.md).

## Notifications

For `notify` styles, callbacks, progress, grouping and permission behavior,
read the [complete notification guide](../guides/notifications.md). It includes
copyable apps and explains where Previewer simulation differs from Android.

The extended arguments and `notifications` object are **1.7.0**.
`notify(title, message, id)` remains compatible. Its optional keyword-only
arguments are `channel`, `icon`, `style`, `picture`, `lines`, `actions`,
`on_tap`, `on_dismiss`, `ongoing`, `progress`, `group` and `when`.

| Method | Contract |
| --- | --- |
| `notifications.channel(id, name, importance="default")` | Declare a channel; importance is `min`, `low`, `default` or `high` and fixed on first creation |
| `notifications.allowed()` | Boolean app-level permission snapshot, not a channel/delivery guarantee |
| `notifications.ask()` | Ask from a screen; a worker cannot open the permission dialog |
| `notifications.cancel(id)` | Remove one card without its user-dismissal callback |
| `notifications.cancel_all()` | Remove this publisher's cards, including ongoing ones |

Actions accept up to three `(label, handler)` pairs; `handler()` has no
arguments. `on_tap` also accepts a `Screen`. `on_dismiss` may be deferred until
the owning Activity resumes. Reusing the same ID updates a card. `when` is
epoch milliseconds for display, **not** scheduling. See the guide for styles,
static declaration restrictions, pictures, progress and lifecycle details.

## Sensors and battery

The [complete sensor guide](../guides/sensors.md) includes runnable apps,
availability checks and the Previewer simulation controls.

| Method | Callback / return type |
| --- | --- |
| `sensors.shake(on_shake=handler)` | `handler()` |
| `sensors.compass(on_change=handler)` | `handler(degrees_text)` |
| `sensors.steps(on_change=handler)` | `handler(count_text)` |
| `sensors.light(on_change=handler)` | `handler(lux_text)` |
| `sensors.proximity(on_change=handler)` | `handler(near_bool)` |
| `sensors.accelerometer(on_change=handler)` — 1.7.0 release | `handler(json_text)` with numeric X/Y/Z in m/s² |
| `sensors.gyroscope(on_change=handler)` — 1.7.0 release | `handler(json_text)` with numeric X/Y/Z in rad/s |
| `sensors.pressure(on_change=handler)` — 1.7.0 release | `handler(hpa_text)` |
| `sensors.available(name)` | boolean; pass a literal sensor name |
| `sensors.stop(name=None)` | stop one watch, or all watches when omitted |
| `battery.level()` | percentage as text |
| `battery.charging()` / `battery.saver()` | boolean snapshot |

JSON field names are lowercase `x`, `y`, `z`; read them with `json_get`.
Step counting requires activity-recognition permission on Android 10+.
The other listed sensors and battery reads do not add runtime permissions.
Check availability: the Previewer simulator is not a hardware probe.

## Static wallpapers

| Method | Callback / return type |
| --- | --- |
| `wallpaper.available()` | boolean; checks Android support and policy |
| `wallpaper.set(source, target="home", on_result=None)` | `on_result(success_bool, reason_text)` after confirmation/error |

Targets are `home`, `lock` and `both`. This always shows confirmation; the
Previewer simulates success without changing the desktop. Read the
[complete wallpaper guide](../guides/wallpaper.md) for runnable code, image
sources, result reasons and device-testing limits. **Requires ApkPy 1.7.0 or newer.**
