---
title: Real-time WebSocket chat
description: Connect, send, reconnect and close a real-time ApkPy channel safely.
---

# Real-time WebSocket chat

Create the connection when the screen is active and close it when the screen is
destroyed. Messages sent during the handshake are queued by the client.

```python
from apkpy_lib import Screen, button, inputs, label, lifecycle, run, websocket

room = Screen(id="room")
status = label("Offline", id="status", screen=room)
latest = label("No messages yet", id="latest", screen=room)
message = inputs("Write a message", id="message", screen=room)

def connected():
    status.set_value("Live")

def received(text):
    latest.set_value(text)

def failed(error):
    status.set_value("Reconnecting")

def connect_room():
    websocket.connect(
        "support-room",
        "wss://api.example.com/chat",
        headers={"Authorization": "Bearer YOUR_TOKEN"},
        on_open=connected,
        on_message=received,
        on_error=failed,
        reconnect=True,
    )

def send_message():
    text = message.get_value()
    if text != "":
        websocket.send("support-room", text)
        message.set_value("")

button("Send", command=send_message, screen=room)
lifecycle(
    room,
    on_resume=connect_room,
    on_destroy=lambda: websocket.close("support-room"),
)
run(room)
```

## Production responsibilities

- authenticate the WebSocket upgrade;
- validate messages on the server;
- persist delivery state and message history;
- define ordering, deduplication and retry semantics;
- use push notifications when the process is not connected.

ApkPy provides WSS framing, ping/pong handling, bounded pending sends and
backoff reconnection. It does not provide end-to-end encryption or a chat
backend.
