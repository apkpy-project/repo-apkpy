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
| `nfc` | Foreground NDEF tags and one-shot writes — new in 1.9.0 |
| `contacts` | Scoped phone/email selection, read-only queries and native editors — new in 1.9.0 |
| `billing` | Play in-app purchases and subscriptions, acknowledged for you |
| `apps` | installed app inspection |
| `sensors` | shake, compass, steps, light and proximity; three new streams in the 1.7.0 |
| `battery` | charge percentage, charging and power-saving state |
| `wallpaper` | static wallpaper preview and confirmation — 1.7.0 |

Use [Background jobs](../background-jobs.md),
[Firebase push](../guides/push-firebase.md),
[Maps and continuous location](../guides/maps-tracking.md) and
[Native Android features](../native-features.md).

## NFC — 1.9.0

| Method | Contract |
| --- | --- |
| `nfc.status(on_result=None)` | `(True, "ready")` or `(False, reason)` |
| `nfc.start(on_tag=None, on_error=None)` | Start foreground reading; `on_tag(True, tag_json)`, `on_error(False, reason)` |
| `nfc.stop()` | Stop reading and silently cancel pending writes |
| `nfc.write(*, text=None, url=None, on_result=None)` | Exactly one payload; arm one attempt on the next tag; callback `(ok, reason)` |
| `nfc.cancel_write()` | Cancel an armed write; does not undo a physical write |
| `nfc.settings()` | Open Android NFC settings; never enable the radio automatically |

Tags are JSON text with `id`, `type`, `text`, `url`, `records`, `writable`,
`size`, `used` and `tech`. Reasons: `unsupported`, `off`, `not_started`,
`no_ndef`, `read_only`, `too_small`, `tag_lost`, `unknown`.
Callbacks return on the UI thread. Pausing disables reading and cancels writes.
The Previewer offers simulated tags, not real NFC. Read the
[complete NFC guide](../guides/nfc.md) for runnable code, formatting/read-back
limits, lifecycle, error recovery and excluded protocols.

## Contacts — 1.9.0

| Method | Successful `(ok, value)` result |
| --- | --- |
| `contacts.pick(kind="phone", on_result=None)` | One JSON contact with the selected phone or email; `kind` is `phone` or `email` |
| `contacts.list(query="", limit=50, offset=0, on_result=None)` | JSON array, display-name substring search; limit 1–100, offset 0–100000 |
| `contacts.get(id, on_result=None)` | One JSON contact by numeric id or returned lookup URI |
| `contacts.create(name="", phone="", email="", on_result=None)` | Editor-return JSON, not a confirmed save |
| `contacts.edit(id, on_result=None)` | Editor-return JSON, not a confirmed save |
| `contacts.settings(on_result=None)` | `"opened"` when app settings opened |

Contact fields: `id`, `uri`, `name`, `phone`, `email`, `phones`, `emails`.
Editor fields: `status="editor_returned"`, `result_code="ok"|"cancelled"`,
`uri`. Callbacks receive a boolean followed by JSON text or a reason string.
Reasons: `cancelled`, `permission_denied`, `permission_blocked`, `not_found`,
`unsupported`, `busy`, `invalid`, `unavailable`, `unknown`.

Only list/get add and request `READ_CONTACTS`. The picker grants access to the
selected detail; create/edit use the system editor without `WRITE_CONTACTS`.
Queries run off the UI thread; callbacks return on it. Background-job calls
are rejected. No direct deletion is provided. See the
[complete guide and People Desk source](../guides/contacts.md) for permission
recovery, lifecycle, editor-return limitations and fictional Previewer data.

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
