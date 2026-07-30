---
title: Firebase push notifications
description: Add FCM token and topic handling to an ApkPy Android project.
---

# Firebase push notifications

Push is conditional. ApkPy adds Firebase Android code only when the app uses
`push` and a valid `google-services.json` is placed beside `writehere.py`.

```python
from apkpy_lib import Screen, label, lifecycle, push, run

inbox = Screen(id="inbox")
status = label("Waiting for delivery events", screen=inbox)

def push_event(title, body, data):
    status.set_value(title + " - " + body)

def push_error(message):
    status.set_value("Push unavailable: " + message)

push.listen(screen=inbox, on_message=push_event, on_error=push_error)

def subscribe():
    push.get_token(
        lambda success, token: status.set_value(
            "Device registered" if success else "Token unavailable"
        )
    )
    push.subscribe("live-orders")

lifecycle(inbox, on_resume=subscribe)
run(inbox)
```

## Setup

1. Register the Android package ID in Firebase.
2. Download `google-services.json`.
3. Put it in the same folder as `writehere.py`.
4. Re-run `apkpy build`.
5. Test on an emulator with Google Play services or a physical device.

The Previewer uses `push.simulate(...)` for interface testing. It cannot obtain
a real FCM token. Your server must store tokens securely, remove invalid tokens
and authorize topic or direct-message sends.
