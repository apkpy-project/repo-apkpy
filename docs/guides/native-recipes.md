---
title: Native recipes
description: Ready-made native.java blocks for the Android capabilities ApkPy does not reach yet — each one compiled before it was published.
---

# Native recipes

[What ApkPy reaches](../coverage.md) names eighteen capabilities it does not
have. This page is the other half of that sentence: the ones you can have today
by declaring the Java yourself, copied and pasted.

Read [your own Java](native.md) first for the rules. In short: every block
needs a `preview=` that answers on the desktop, `context` is handed to you, and
an async block answers through `done` from any thread.

!!! note "Run on a phone, and changed because of it"

    All six were put in one app and run on a Xiaomi 25069PTEBG on Android 16:
    the page opened, the download came back with an id, the dialer and the
    calendar opened, the file appeared in Downloads and the phone read the text
    aloud. Two of them only work because of what that run found — the
    permission the download needs, and the guard that was wrong on Android 11
    and later. One phone, one manufacturer; and keeping a block's Java and its
    `preview=` in step is still your promise, not ApkPy's.

## Read text aloud

The engine starts asynchronously, so this is a `java_async` block: the answer
arrives from the init callback, not from the call.

```python
speak = native.java_async(
    "speak",
    args=("text",),
    imports=["android.speech.tts.TextToSpeech"],
    code="""
        try {
            final TextToSpeech[] engine = new TextToSpeech[1];
            engine[0] = new TextToSpeech(context, new TextToSpeech.OnInitListener() {
                @Override
                public void onInit(int status) {
                    if (status != TextToSpeech.SUCCESS) {
                        done.run(false, "text to speech unavailable");
                        return;
                    }
                    engine[0].speak(text, TextToSpeech.QUEUE_FLUSH, null, "apkpy");
                    done.run(true, text);
                }
            });
        } catch (Exception problem) {
            done.run(false, String.valueOf(problem.getMessage()));
        }
    """,
    preview=lambda text, done: done(True, text),
)

speak("Good morning", on_result=spoken)
```

No permission. The array holds the engine so the listener can reach it — a
local would not be in scope by the time Android calls back.

## Open a page in the browser

```python
open_page = native.java(
    "openPage",
    args=("url",),
    imports=["android.content.Intent", "android.net.Uri",
             "android.content.ActivityNotFoundException"],
    code="""
        try {
            Intent view = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            view.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(view);
            return "ok";
        } catch (ActivityNotFoundException missing) {
            return "no browser";
        }
    """,
    preview=lambda url: "ok",
)
```

Catch `ActivityNotFoundException`; do **not** guard with `resolveActivity`.
From Android 11 an app cannot see other packages unless it declares them in a
`<queries>` element, so `resolveActivity` answers `null` on a phone that has a
browser — and the guard refuses for nothing, silently. This was written the
wrong way first, and only running it on a phone showed it.

## Download a file

```python
download = native.java(
    "download",
    args=("url", "name"),
    imports=["android.app.DownloadManager", "android.net.Uri",
             "android.os.Environment", "android.content.Context"],
    code="""
        DownloadManager manager = (DownloadManager)
                context.getSystemService(Context.DOWNLOAD_SERVICE);
        if (manager == null) {
            return "no download manager";
        }
        DownloadManager.Request ask = new DownloadManager.Request(Uri.parse(url));
        ask.setTitle(name);
        ask.setNotificationVisibility(
                DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
        ask.setDestinationInExternalFilesDir(
                context, Environment.DIRECTORY_DOWNLOADS, name);
        return String.valueOf(manager.enqueue(ask));
    """,
    preview=lambda url, name: "1",
)
```

It returns the download id, and it needs a permission:

```python
native.manifest(permission="android.permission.INTERNET")
```

Without it `enqueue()` throws `SecurityException` and takes the app down --
found by running this on a phone, after the guide had already claimed it needed
nothing. The *destination* needs no permission, which is what misled me: the
file lands in your app's own downloads folder. Talking to the network does.

## Save a text file where the user will find it

```python
save_text = native.java(
    "saveText",
    args=("name", "body"),
    imports=["android.content.ContentValues", "android.net.Uri",
             "android.os.Build", "android.os.Environment",
             "android.provider.MediaStore", "java.io.OutputStream"],
    code="""
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            return "needs Android 10";
        }
        try {
            ContentValues details = new ContentValues();
            details.put(MediaStore.Downloads.DISPLAY_NAME, name);
            details.put(MediaStore.Downloads.MIME_TYPE, "text/plain");
            details.put(MediaStore.Downloads.RELATIVE_PATH,
                        Environment.DIRECTORY_DOWNLOADS);
            Uri where = context.getContentResolver().insert(
                    MediaStore.Downloads.EXTERNAL_CONTENT_URI, details);
            if (where == null) {
                return "could not create the file";
            }
            OutputStream stream = context.getContentResolver().openOutputStream(where);
            stream.write(body.getBytes("UTF-8"));
            stream.close();
            return String.valueOf(where);
        } catch (Exception problem) {
            return String.valueOf(problem.getMessage());
        }
    """,
    preview=lambda name, body: "content://downloads/1",
)
```

This writes into the shared Downloads folder with no permission at all, which
is what Android 10 changed. It is **not** the file picker: the user does not
choose the name or the place. A real "Save as" needs an Activity result, which
a block cannot receive — see [what a block cannot do](#what-a-block-cannot-do).

## Dial a number

```python
dial = native.java(
    "dial",
    args=("number",),
    imports=["android.content.Intent", "android.net.Uri",
             "android.content.ActivityNotFoundException"],
    code="""
        try {
            Intent call = new Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + number));
            call.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(call);
            return "ok";
        } catch (ActivityNotFoundException missing) {
            return "no dialer";
        }
    """,
    preview=lambda number: "ok",
)
```

`ACTION_DIAL` opens the dialer with the number typed in and lets the person
press the button. Use a number you are allowed to put in front of someone:
the example uses `+15550100`, which is reserved for fiction. Never write an
emergency number into a dialer a stray tap could place. `ACTION_CALL` would place the call itself and needs the
`CALL_PHONE` permission — this one needs nothing, and is the one Play will not
ask you about.

## Put something in the calendar

```python
add_event = native.java(
    "addEvent",
    args=("title", "startMillis"),
    imports=["android.content.Intent", "android.provider.CalendarContract",
             "android.content.ActivityNotFoundException"],
    code="""
        try {
            Intent event = new Intent(Intent.ACTION_INSERT)
                    .setData(CalendarContract.Events.CONTENT_URI)
                    .putExtra(CalendarContract.Events.TITLE, title)
                    .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME,
                              Long.parseLong(startMillis.trim()))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(event);
            return "ok";
        } catch (ActivityNotFoundException missing) {
            return "no calendar";
        }
    """,
    preview=lambda title, start_millis: "ok",
)
```

The calendar app opens with the event filled in and the person saves it. No
`WRITE_CALENDAR`, and nothing is written behind their back.

## Vibrate

Already written, in [the native example](https://github.com/apkpy-project/repo-apkpy/blob/main/examples/31_native_java.py)
together with reading the battery. It needs
`native.manifest(permission="android.permission.VIBRATE")`.

## What the phone said

Each block reports what it returned, because a block that quietly answers "not
available" looks exactly like one that worked:

| Recipe | On the phone |
| --- | --- |
| open a page | `ok` — the browser opened |
| download | `1373` — a real DownloadManager id |
| dial | `ok` — the dialer opened with the number |
| calendar | `ok` — the calendar opened with the event |
| save a file | `content://media/external/downloads/12736`, and the file is in Downloads |
| read aloud | `bom dia` — through `done`, from the engine's init callback |

No exception in `logcat`. Before the two fixes above, the same run crashed on
the download and answered "no browser", "no dialer" and "no calendar" on a
phone that has all three.

## What a block cannot do

Being honest about the other half of the eighteen. These are **not** a handful
of lines, and no recipe here would be:

- **Anything that waits for another screen to come back** — the system file
  picker's "Save as", a share target, a permission flow of your own. A block
  runs and returns; it cannot receive an `onActivityResult`.
- **Anything that adds a view to the layout** — a WebView, a chart. The layout
  is written as XML at build time, and a block runs after it.
- **A home-screen widget or a quick settings tile.** Both are separate
  components declared in the manifest with their own classes; a block is a
  method inside an Activity.
- **AdMob, Play in-app updates, Health Connect.** Each is an SDK with its own
  lifecycle and callbacks. `native.gradle()` can pull the dependency in, but
  what you would write around it is an integration, not a recipe.

For those, the answer is still "not yet" rather than "write it yourself", and
[the coverage page](../coverage.md) says so.
