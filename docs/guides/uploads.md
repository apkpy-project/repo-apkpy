---
title: Streaming multipart uploads
description: Upload images, audio, video and files with progress and cancellation.
---

# Streaming multipart uploads

The upload worker streams the file in chunks instead of loading the complete
payload into memory.

## One button that picks and sends

`upload_button` opens the file picker and uploads the chosen file in a single
call. Any file type is accepted, not only images.

```python
from apkpy_lib import Screen, label, run, upload_button

transfer = Screen(id="transfer")
progress = label("No file chosen", screen=transfer)


def file_chosen(path, name, size, mime):
    progress.set_value(name + " - " + size + " bytes")


def upload_finished(success, response):
    progress.set_value("Upload complete" if success else "Upload failed")


upload_button(
    "ATTACH A FILE",
    url="https://api.example.com/media",
    types=["pdf", "docx", "png"],
    fields={"album_id": "42"},
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    on_file=file_chosen,
    on_result=upload_finished,
    id="attach", screen=transfer,
)

run(transfer)
```

`task_id` defaults to the button's `id`, so a second tap restarts the transfer
instead of racing a duplicate, and `uploads.cancel("attach")` works.

## Picking and sending separately

Use the two primitives when the upload has to be conditional -- rejecting a
file above a size limit, for example. `upload_button` generates exactly this
code.

```python
from apkpy_lib import Screen, button, files, label, uploads, run

transfer = Screen(id="transfer")
progress = label("Choose a file", screen=transfer)


def file_chosen(success, path, name, size, mime):
    if not success:
        return
    if int(size) > 10000000:
        progress.set_value(name + " is too large")
        return
    uploads.file("attachment", "https://api.example.com/media", path,
                 on_result=upload_finished)


button("CHOOSE A FILE", id="choose", screen=transfer,
       command=lambda: files.pick(on_result=file_chosen, types=["pdf"]))
```

`on_result` receives `(success, path, name, size, mime)`. Every value is a
string, so `name + " (" + size + ")"` works, while `size > 10000000` does not --
convert first.

### `path` is an opaque handle

On Android it is a `content://` Uri from the Storage Access Framework; on the
desktop it is a filesystem path. Pass it to `uploads.*` and read
`name`/`size`/`mime` instead of parsing it -- `path.split("/")[-1]` returns the
filename on the desktop and a provider id on the phone.

`uploads.multipart`, `file`, `image`, `audio` and `video` are the supported
consumers. A picked path cannot currently be displayed with an `image`
component.

It is also unrelated to `files.path()` / `files.exists()` / `files.delete()`,
which address the app's own folder.

### The type filter is advisory

`types=["pdf"]` becomes `EXTRA_MIME_TYPES` on Android and a dialog filter on the
desktop, and both always offer an all-files escape hatch, because many Android
document providers ignore the filter. Validate with the returned `mime` or
`name` when it matters.

Accepted forms: an extension (`"pdf"`, `".pdf"`), a complete MIME type
(`"application/pdf"`), a family (`"image/*"`), or nothing at all for any file.

Picking needs no storage permission: the generated app uses
`ActivityResultContracts.OpenDocument`, which grants access to the single file
the user chose.

## The multipart engine

```python
from apkpy_lib import Screen, button, label, uploads, run

transfer = Screen(id="transfer")
progress = label("Choose a file", screen=transfer)
selected_path = "artwork.jpg"

def progress_changed(percent, sent, total):
    # All three arrive as strings on both runtimes; use int(percent) to compare.
    progress.set_value("Uploading - " + percent + "%")

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

The `file`, `image`, `audio` and `video` helpers share the multipart engine,
and all of them accept a picked `path` from `files.pick`.
Your endpoint must enforce file size, content type, authentication and storage
policy. A displayed `100%` only means all request bytes were sent; success is
determined by the HTTP response.
