"""Every native recipe in one app, so they can be compiled and run together.

Each block declares a piece of Android that ApkPy has no API for. Read the
rules in docs/guides/native.md and the recipes in
docs/guides/native-recipes.md.

Run it: python writehere.py for the simulated answers, apkpy run to build.
Each row shows what its block returned on the phone, which is the only way to
tell a block that worked from one that quietly answered "not available".
"""
from apkpy_lib import Screen, Theme, button, label, native, run

Theme(mode="dark")

home = Screen(id="home", scroll=True)
label("NATIVE RECIPES", id="kicker", screen=home)
row_open = label("open a page ...", id="row_open", screen=home)
row_down = label("download ...", id="row_down", screen=home)
row_dial = label("dial ...", id="row_dial", screen=home)
row_cal = label("calendar ...", id="row_cal", screen=home)
row_save = label("save a file ...", id="row_save", screen=home)
row_say = label("read aloud ...", id="row_say", screen=home)


# ── read text aloud ─────────────────────────────────────────────────────
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


# ── open a page in the browser ──────────────────────────────────────────
# startActivity in a try, not resolveActivity: from Android 11 an app cannot
# see other packages without a <queries> entry, so resolveActivity answers
# null on a phone that has a browser and the guard refuses for nothing.
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


# ── download a file ─────────────────────────────────────────────────────
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

# The DownloadManager talks to the network: without this it throws
# SecurityException and takes the app down.
native.manifest(permission="android.permission.INTERNET")


# ── dial a number ───────────────────────────────────────────────────────
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


# ── put something in the calendar ───────────────────────────────────────
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


# ── save a text file where the user will find it ────────────────────────
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


def spoken(ok, value):
    row_say.set_value("read aloud: " + value)


def go():
    row_save.set_value("save a file: " + save_text("notes.txt", "hello"))
    row_down.set_value("download: " + download("https://example.com/a.pdf", "a.pdf"))
    row_cal.set_value("calendar: " + add_event("Dentist", 1790000000000))
    row_dial.set_value("dial: " + dial("+15550100"))
    row_open.set_value("open a page: " + open_page("https://repo-apkpy.pages.dev"))
    speak("bom dia", on_result=spoken)


button("Run every recipe", id="b", screen=home, command=go)

style = """
kicker { color: #C8FF5A; font-size: 12px; margin-top: 20px; }
row_open { font-size: 15px; margin-top: 10px; }
row_down { font-size: 15px; margin-top: 10px; }
row_dial { font-size: 15px; margin-top: 10px; }
row_cal { font-size: 15px; margin-top: 10px; }
row_save { font-size: 15px; margin-top: 10px; }
row_say { font-size: 15px; margin-top: 10px; }
b { margin-top: 20px; }
"""

if __name__ == "__main__":
    run(start_screen=home)
