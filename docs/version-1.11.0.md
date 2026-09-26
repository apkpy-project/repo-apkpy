---
title: Version 1.11.0
description: Apps you know, rebuilt -- rows built from components, every Material icon, a music player with its own files, a Previewer that looks like the phone, UI written once, and background jobs that save what they fetched.
---

# ApkPy 1.11.0

Released 2026-09-26. `python -m pip install --upgrade apkpy==1.11.0`.

A build can stop where it used to pass -- every time, because it was shipping
something broken. See [Upgrading](#upgrading).

## UI written once

A header, a card or a bar that appears on several screens is now a function,
called once per screen:

```python
def stat(name, value, screen):
    box = card(id="stat", screen=screen)
    label(name, id="stat_name", parent=box)
    number = label(value, id="stat_value", parent=box)
    return number

distance = stat("Distance", "0.0 km", today)   # distance.set_value(...) later
for week, km in [("This week", "18.4 km"), ("Last week", "22.1 km")]:
    stat(week, km, history)
```

The Previewer always ran this as Python; the compiler refused it. Now each
module-level call is expanded before anything is translated -- the module you
would have written by hand -- and a module-level loop that builds UI is
unrolled. Called from a tap or a callback, a UI function stops the build with
`U2038`: by then the screens exist. The complete app is
[`examples/33_reusable_screens.py`](https://github.com/apkpy-project/repo-apkpy/tree/main/examples/33_reusable_screens.py),
and on a phone its three screens showed exactly what the Previewer showed.
See [Functions that build UI](guides/modules.md#functions-that-build-ui).

Writing the tests for it found something worse: a module-level
`for page, title, copy in [...]:` was dropped without a word, and four
published showcase apps -- Afterglow, Lumen, Northline and Onda -- had tabs with
nothing on them on the phone. Those loops are unrolled now, and the rebuilt
showcase APKs show every tab on a phone.

## Apps you know, rebuilt

The test behind most of this release: rebuild a chat, a music player, a photo
feed with stories and a ride app, photograph them on a phone next to what they
imitate, and fix every place they fell short. The screenshots and the source
are in the [showcase](showcase.md#apps-you-know-rebuilt).

## Rows built from components

A `virtual_collection` row had fixed slots -- a title, a subtitle, a picture, a
badge. A feed post is a layout of its own. Now one function builds it:

```python
def post_row(row):
    avatar("{face}", size=34, id="post_face", parent=row, describe="{user}")
    image("{picture}", id="post_pic", parent=row, aspect_ratio="1:1", describe="")
    button("", icon="favorite_border", active_icon="favorite", active="{liked}",
           describe="Like", id="post_like", parent=row,
           command=lambda item: like(item))
    label("{likes} likes", id="post_likes", parent=row)

feed = virtual_collection(POSTS, row=post_row, id="feed", screen=home)
```

`{field}` is filled from each item; a command that takes an argument gets the
item; `visible="{field}"` and `active="{field}"` read a field, and
`feed.update_item("p1", {"liked": "yes"})` draws that row again. On the phone
each row is a layout of its own, recycled by a RecyclerView, its pictures
packaged or loaded at their own size. See
[Rows built from components](ui-components.md#rows-built-from-components).

## Every Material icon

`icon=` took the 71 names ApkPy drew itself. Any of the 2,032 Material Icons
works now -- `add_comment`, `cameraswitch`, `chat_bubble_outline` -- drawn from
the same paths in the Previewer and on the phone. `icons.search("heart")`
finds one. See [Icons](ui-components.md#icons).

## A music player with its own files

A music app with its own tracks played nothing on a phone: local files were
never packaged, and local covers left a shelf of blank cards. Audio now goes
into the app's raw resources and pictures into its drawables, found by the
same name everywhere. An icon button bound to `audio.controls` swaps
`play_arrow` and `pause` and lights shuffle and repeat; the mini-player takes
a stylesheet; and a player paused and closed from recents goes with the app
-- on a Xiaomi it stayed in the media island. See [Media](media-auth.md).

## A Previewer that looks like the phone

People trying ApkPy took the Previewer's stepped edges for what Android would
show. Rounded shapes are antialiased now, shadows are soft, a glass button
over a photo shows the photo, `#AARRGGBB` keeps its alpha, the screen starts
below the status strip, and a row is laid out as the phone lays it out. See
[Preview and Android](preview-android.md).

## An assistant that knows ApkPy

No AI model knows ApkPy from its training. Asked to add a screen, an
assistant writes Kivy, or Python ApkPy cannot translate. So every new project
now tells it: `apkpy start`, `apkpy init` and `apkpy examples` put an
`AGENTS.md` beside `writehere.py` -- the file Codex, Cursor, Copilot and
other coding assistants read before they work in a project -- and a
`CLAUDE.md` that points Claude Code at it. It says what ApkPy translates,
which rules stop the build and with which code, and which API to reach for.

```
apkpy agents    # add it to a project you already have
```

A copy you have edited is never replaced. A test builds the guide's own
example and checks every API and error code it names against the library.

For assistants that read the web, [`llms.txt`](llms.txt) now says what ApkPy
is and is not, and [`llms-full.txt`](llms-full.txt) holds the documentation in
one file.

## A job that keeps what it fetched

The offline queue most apps want is a job that downloads or asks for something
and saves it. Until now the data layer and `files.download()` could not run in
a job at all. Now they do, and inside a job they answer **before the next
line**:

```python
def downloaded(ok, path):
    if ok:
        page.insert({"path": path}, on_result=saved)

def work():
    files.download(PAGE, "page.html", on_result=downloaded)
    # the file is on disk and the row is written

job = background_job("fetch_page", run=work, requires_network=True)
saved_pages = page.observe(on_change=count, screen=home)
```

The Worker is already off the main thread, so it runs each operation where it
is instead of handing it to the data thread, and the Previewer keeps the same
order inside a job. A screen observing the model hears about the write the same
way it hears about its own. Each operation is still written once: the
repository builds a Task that a screen submits and a Worker runs.

On a Xiaomi running Android 16, this job -- the complete app is
[`examples/32_offline_queue.py`](https://github.com/apkpy-project/repo-apkpy/tree/main/examples/32_offline_queue.py)
-- downloaded a page, saved it from the download's callback, and the screen
counted it.

## A job either runs or says why

The Worker used to drop every call it could not write. A job that checked a
permission, set a label or called one of your own functions compiled, ran,
reported `success` and did nothing -- and said nothing.

Now what a Worker can do, it does: your functions, however deep,
`permissions.has()`, the data layer, `files.download()` and `files.delete()`.
What it cannot stops the build with the call and its line:

| Code | Means | Fix |
| --- | --- | --- |
| `J7004` | the call needs a screen -- a component, a dialog, a permission request, navigation, `audio` | report with `job.progress()` and show it from `job.observe()` |
| `J7005` | it could run in the background but is only written for screens so far -- uploads, WebSockets, location | do it on a screen and pass what the job needs through `enqueue()` |

The Previewer refuses the same calls with the same code when the body reaches
them, instead of running at the desk what the phone refuses. The full table is
in [What a job body can call](background-jobs.md#what-a-job-body-can-call).

The status a job reports is one rule now, too. On the phone a finished job
used to show no message and progress `0` -- WorkManager clears a finished job's
progress -- a retry was just `enqueued`, and an old failure could outrank the
success after it. The generated Worker now leaves its last word where the
status reads it, and a test compiles `ApkpyJobs.status()` against WorkManager's
own classes and puts 18 situations to it and to the Previewer. The table of
what each state carries is in [Observing progress](background-jobs.md#observing-progress).

Found on the way and fixed: `service.every(sync, 15)` -- the positional form --
produced no Worker; an `https` callback in a job did not compile; and a
transaction that returned a value did not compile on any screen.

## One set of database rules

An audit found nine places where the Previewer and the phone answered the same
database question differently, all of them silently. Each rule now lives once,
in `apkpy_lib/data_rules.py`, and a test lifts the generated Java helpers out of
the build, compiles them with `javac` and asks both languages 25 questions.

Five of these change what an app does, and all five were a divergence before:
a `blob` reads as Base64 in the Previewer; `gt`/`lt` against `None` stop with
`D2014`; `NaN` is refused; `2.0` is accepted by an `integer` field; `%` and `_`
in a search are searched for literally.

## Native recipes

Six ready-made `native.java` blocks for things ApkPy has no API for -- reading
text aloud, opening a page, downloading a file, saving a text file, dialling a
number and adding a calendar event. All six were run on a phone.

## Fixed

- `permissions.has("camera")`, `"android.permission.CAMERA"` (the form the
  guide shows) and a `request()` without `declare_permissions()` did not build.
  Every form names the Android constant now, and asking declares it.
- `lambda t=target: ...` in a loop did nothing on a phone; a default the
  program changes later stops with `U2039`.
- `position: absolute` on a screen's own component was laid out in the
  column; a sheet at `bottom: 0` stopped above the navigation bar; an absolute
  box with no width filled the screen; `align-self` on a screen's component
  did nothing.
- A scrolling screen without a bottom bar drew its title under the clock on
  Android 15+, and the clock was dark on a dark screen.
- Shuffle and repeat did nothing unless given a command, play did nothing
  after the last track, the bar stayed at the end, and `audio.now_playing`'s
  bar was always sky blue.
- A margin shorthand on a label broke the build; an icon-only button's icon
  sat off centre; an avatar's ring was cut and its `describe=` lost; grid and
  carousel cards were white; a growing label's text was centred on the phone;
  `confirm()` said "Cancelar" on the phone.
- `x["key"]` returned the whole value on a phone -- a tapped `list_view`
  row's `item["id"]`, `first["name"]` after `first = rows[0]`, a dict written
  in the source. A key reads the key, and a `list_view` row keeps every
  column of the record it came from.
- A label set, a button shown or a list filled from a function running on
  another screen never changed on a phone. The owning screen now applies it
  when it comes to the front.
- Keyword arguments to your own functions were dropped (`U2037` when they
  cannot be lined up).
- A cancelled camera or NFC was announced as a success through a lambda.
- A declaration written inside `db.schema()` never reached Android (`C4004`).
- A job ending in `return`, and a number bigger than a Java `int`, broke the
  build.
- In the Previewer: cascades stopped short, a plain Deny was final, NFC handed
  the previous tag to a new reader, a missing storage key was `None`, and a
  quick click left a button grey.
- `contacts.pick("phone", cb)` ran in the Previewer and stopped the build.
- Without a `Theme()`, the bottom bar on a phone had a lilac pill and dark-grey
  labels on a navy bar, and the pill covered the active label; it was 56dp
  where the Previewer drew 64, and a black strip showed under it on Android 15.
- On a phone with a font theme, bold came out regular in every app -- the
  theme's weight axis was never turned. Each screen now measures that once
  and, only there, asks the axis for the weight. The active tab's label is
  bold in the Previewer again, as Material draws it.
- Contrast was measured against the wrong background; four icon names did not
  exist.

## Upgrading

- **A build can stop where it used to pass:** a UI function called from a
  callback (`U2038`), a module-level loop that unpacks and builds nothing
  (`U2033`), a job body calling the screen
  (`J7004`/`J7005`), a service naming no function (`J7002`), keywords that do
  not match (`U2037`), a schema entry that is not a declaration (`C4004`),
  `gt`/`lt` against `None` (`D2014`).
- The five data rules above.
- `storage.get("key")` for a key never written is `""` in the Previewer, as on
  the phone.
- A `list_view` click hands over the row: in an app that used the tapped
  `item` as text after `set_items(rows, ...)`, it is now the record -- read
  `item["title"]`.
- A job's status after a success reads `100` and the last message on the
  phone too; a retry is `retry` on both sides.
- `lambda x=value:` whose default the program changes later stops with
  `U2039` -- it used to be dropped.
- A component with `position: absolute` directly on a screen now floats over
  the content instead of taking a place in the column.
- On screens without an app bar the status icons follow the colour behind
  them; scrolling screens without a bottom bar start below the status bar.
- The text defaults of `audio.controls` and `audio.like_button` are English
  words (they were Portuguese with emoji); pass `text=` to keep your own.
- The Previewer draws shapes antialiased; `APKPY_PREVIEW_AA=0` brings back the
  old polygons.
- Regenerate the Android project: the generated repositories are organised as
  Tasks; they behave the same.

The complete list is in the
[changelog](https://github.com/apkpy-project/repo-apkpy/blob/main/CHANGELOG.md).
