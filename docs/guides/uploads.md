---
title: Streaming multipart uploads
description: Upload images, audio, video and files with progress and cancellation.
---

# Streaming multipart uploads

The upload worker streams the file in chunks instead of loading the complete
payload into memory.

```python
from apkpy_lib import Screen, button, label, uploads, run

transfer = Screen(id="transfer")
progress = label("Choose a file", screen=transfer)
selected_path = "artwork.jpg"

def progress_changed(percent, sent, total):
    progress.set_value("Uploading - " + str(percent) + "%")

def upload_finished(success, response):
    if success:
        progress.set_value("Upload complete")
    elif response == "cancelled":
        progress.set_value("Upload cancelled")
    else:
        progress.set_value("Upload failed")

def start_upload():
    uploads.image(
        "artwork-upload",
        "https://api.example.com/media",
        selected_path,
        fields={"album_id": "42"},
        headers={"Authorization": "Bearer YOUR_TOKEN"},
        on_progress=progress_changed,
        on_result=upload_finished,
    )

button("Start upload", command=start_upload, screen=transfer)
button(
    "Cancel",
    command=lambda: uploads.cancel("artwork-upload"),
    variant="outlined",
    screen=transfer,
)
run(transfer)
```

The `file`, `image`, `audio` and `video` helpers share the multipart engine.
Your endpoint must enforce file size, content type, authentication and storage
policy. A displayed `100%` only means all request bytes were sent; success is
determined by the HTTP response.
