---
title: Device and Android API
description: Permissions, push, maps, location, notifications and Android integrations.
---

# Device and Android API

| Object/API | Purpose |
| --- | --- |
| `declare_permissions` / `permissions` | manifest and runtime permissions |
| `notify` | Android system notification |
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

Use [Background jobs](../background-jobs.md),
[Firebase push](../guides/push-firebase.md),
[Maps and continuous location](../guides/maps-tracking.md) and
[Native Android features](../native-features.md).
