# ApkPy 1.11.0 — apps you know, rebuilt in Python

Write native Android apps in the supported Python subset. The generated APK
still contains Java/XML, not a Python runtime.

This release was driven by one test: rebuild the screens everybody knows -- a
chat, a music player, a photo feed with stories, a ride app -- photograph them
on a phone, and fix every place they fell short. They are on the site, with
their source: [Apps you know, rebuilt](https://repo-apkpy.pages.dev/showcase/#apps-you-know-rebuilt).

## New

- **Rows built from components.** `virtual_collection(items, row=post_row)`:
  one function builds a row from ordinary components, `{field}` fills texts,
  pictures and `describe` from each item, and a command that takes an
  argument receives the item. A feed post, a comment or a product card can be
  written at last; the phone inflates and recycles a layout of its own per
  row. `visible="{field}"`, a button's `active="{field}"` with `active_icon`,
  and `update_item(id, {...})` make a row change -- the heart that turns red
  on its own post.
- **All 2,032 Material Icons.** Any Material Icons name works in `icon=`,
  drawn from the same paths on both runtimes; `icons.search("heart")` finds
  one.
- **A music player with its own files.** Local tracks and covers are packaged
  with the app (they played nothing before); `audio.controls` and
  `audio.like_button` on an icon button swap play/pause and light shuffle,
  repeat and the heart; `mini_player()` takes a stylesheet.
- **Chat bubbles** (`align-self`, `max-width`, `item-border-radius` per kind of
  row), **`badge-position: end`** for a chat list, **pictures you can tap**
  (`image(..., command=)`, `image.set_src()`), **corners one by one**
  (`border-radius: 22px 22px 0px 0px`), and `title-color`/`subtitle-color` on
  `grid()` and `carousel()`.
- **A Previewer that looks like the phone.** Rounded shapes are antialiased
  (they had stepped edges on Windows), shadows are soft, a transparent button
  over a picture shows the picture, the screen starts below the status strip,
  and rows are laid out as the phone lays them out.
- **Functions that build UI, reused across screens.** A header or a card is
  written once and called once per screen; `t = stat(...)` binds the component
  it returns. Each module-level call is expanded before anything is
  translated, a module-level `for` that builds UI is unrolled, and a call from
  a tap or a callback stops with the new `U2038`. The Previewer and the phone
  end up with the same components on the same screens -- checked by a test and
  on a phone.
- **A background job can save what it fetched.** The data layer -- `insert`,
  `insert_many`, `get`, `find`, `update`, `delete`, `count`,
  `db.transaction()` -- and `files.download()` now run inside a
  `background_job`, `service.every()` and `service.once()`, and answer
  **before the job's next line**, on the phone and in the Previewer. A screen
  observing the model hears about the write. That is the offline queue: fetch
  something in the background, keep it, show it.
- **One set of database rules instead of two.** Nine places where the
  Previewer and the phone had drifted apart -- all of them silent -- now read
  one table, `apkpy_lib/data_rules.py`. A test compiles the generated helpers
  with `javac` and asks both languages the same 25 questions.
- **`AGENTS.md` in every new project.** No AI model knows ApkPy from its
  training, so each project tells the assistant working in it: `apkpy start`,
  `apkpy init` and `apkpy examples` write an `AGENTS.md` (and a `CLAUDE.md`
  pointing at it) with what ApkPy translates, the rules that stop a build and
  the API to use. `apkpy agents` adds it to an existing project; an edited
  copy is kept. Its example is built by a test.
- **`llms.txt` rewritten and `llms-full.txt` added** for assistants that read
  the web: what ApkPy is and is not, and the documentation in one file.
- **Native recipes.** Six `native.java` blocks for things ApkPy has no API
  for: reading text aloud, opening a page, downloading a file, saving a text
  file, dialling a number, adding a calendar event.
- **`J7004` and `J7005`.** A job body that calls something a Worker cannot run
  stops the build naming the call and its line -- see Fixed.

## Fixed

- `permissions.has("camera")`, `"android.permission.CAMERA"` (the form the
  guide shows) and a `request()` without `declare_permissions()` did not build.
  Every form names the Android constant now, and asking declares it.
- **`lambda t=target: ...` in a loop did nothing on a phone** -- a menu of
  buttons built by a loop opened nothing, and `toast(c)` stopped the build
  with a Java error. Each default is written into the lambda; one the program
  changes later stops with `U2039`.
- **`position: absolute` on a screen's own component was laid out in the
  column**: no floating button, no composer or player bar pinned to the
  bottom. It floats over the content now. A sheet at `bottom: 0` reaches the
  bottom of the screen, an absolute box with no width is as wide as its
  content, and `align-self` works on a screen's own component.
- **A scrolling screen without a bottom bar drew its title under the clock**
  on Android 15+ (six published examples), and **the clock was dark on a dark
  screen** in a light app.
- **The music player:** closed from recents while paused, it stayed in the
  notification and a Xiaomi's media island; shuffle and repeat did nothing
  unless the app gave them a command; play did nothing after the last track;
  the bar stayed at the end of a finished queue; `audio.now_playing`'s bar was
  always sky blue.
- **`margin: 4px 14px 0px 14px` on a label** wrote `layout_marginTop` twice and
  the app did not build.
- An icon-only button's icon sat left of centre (it is centred, in a 48dp
  square when the stylesheet gives no size); an avatar's ring was cut and
  its `describe=` never reached TalkBack; grid and carousel cards were white
  whatever the stylesheet said; a label with `flex-grow` had its text centred
  on the phone; `confirm()` said "Cancelar" on the phone.
- **Four showcase apps had empty screens on the phone.** A module-level
  `for page, title, copy in [...]:` was dropped without a word: Afterglow lost
  its tracks, and each app lost the title and copy of three tabs. Rebuilt APKs
  replace the published ones.
- **The bottom bar without a `Theme()`** had a lilac pill and dark-grey labels
  on a navy bar on the phone, and its pill covered the active label. One colour
  rule for both runtimes now, and 4dp between pill and label.
- **A black strip under the bottom bar** on Android 15+: the page colour showed
  in the gesture area. The bar now runs to the edge of the phone.
- **The bottom bar was 56dp on a phone and 64 in the Previewer**, with the
  label sat on its bottom edge. Both are 64 now, read from one place.
- **Bold came out regular on phones with a font theme** (seen on a Xiaomi):
  every weight of the system font pointed at one variable file whose weight
  axis the system never turned. Each screen now measures that once and, only
  there, gives bold and medium text their weight through the axis. On a phone
  whose bold works nothing changes. The active tab's label is bold again in
  the Previewer -- it had been made regular on the word of that phone.
- **`x["key"]` handed back the whole value on a phone** -- a tapped
  `list_view` row's `item["id"]`, `first["name"]` after `first = rows[0]`, a
  dict written in the source. A key reads the key now, and a `list_view` row
  is the record it came from, every column kept.
- **A component changed from another screen was dropped on the phone.** A
  function running on one screen that set a label on another now leaves the
  value for that screen, which applies it when it comes to the front:
  `set_value()`, `show()`, `hide()` and `set_items()`. Checked on an
  emulator, with the old compiler and with the box switched off as controls,
  and then on a phone.
- **A background job could compile, run, report `success` and do nothing.**
  The Worker dropped every call it could not write: a permission check, a
  label, an insert, a download, even a call to one of your own functions. It
  now writes what it can and refuses the rest, with the same code in the
  Previewer.
- **A finished job told the screen something else on the phone** -- no
  message and progress 0 after a success, `enqueued` for a retry, and an old
  failure outranking a newer success. The status now has one rule both sides
  report through, checked against WorkManager's own classes.
- **`service.every(sync, 15)` produced no Worker** -- only `run=` by name was
  read. A `run=` naming no function now stops with `J7002`.
- **An `https` callback inside a job did not compile**, unless its first
  parameter was called `success`.
- **A transaction that returned a value did not compile**, on any screen.
- **Keyword arguments were dropped from calls to your own functions**
  (`U2037` when they cannot be lined up).
- **A cancelled camera or an unavailable NFC was announced as a success**
  when the callback went through a lambda.
- **A declaration written inside `db.schema()` never reached Android**
  (`C4004` for an entry that is not one).
- **A job that ended in `return` did not compile**, and a number bigger than
  a Java `int` broke the build.
- In the Previewer: a delete stopped short of the far end of a cascade; a
  plain Deny closed the permission for ever; a new NFC reader inherited the
  previous tag; a missing storage key answered `None` instead of `""`; a quick
  click left a button grey.
- `contacts.pick("phone", cb)` ran in the Previewer and stopped the build.
- Contrast was measured against the wrong background; four icon names did
  not exist.

## Upgrading

Most apps generate what they generated before. These can change what you see:

- **A build can stop where it used to pass**, and each time it was shipping
  something broken: a UI function called from a callback (`U2038`), a
  module-level loop that unpacks and builds nothing (`U2033`, it was dropped),
  a job body calling the screen (`J7004`/`J7005`), a
  service naming no function (`J7002`), a call whose keywords do not match
  (`U2037`), a schema entry that is not a declaration (`C4004`), `gt`/`lt`
  against `None` (`D2014`).
- The data rules: a `blob` reads as Base64 in the Previewer, `NaN` is refused,
  `2.0` is accepted by an `integer` field, and `%`/`_` in a search are
  searched for literally.
- `storage.get("key")` for a key never written answers `""` in the Previewer,
  as the phone always did.
- A job's status: after a success the phone now reads `100` and the job's last
  message; a job waiting out its backoff is `retry` on both sides; and in the
  Previewer an `enqueue()` no longer carries the previous item's progress and
  message.
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
- Regenerate your Android project. The generated repositories are organised
  differently (each operation is a Task, run by a screen or by a job); they
  behave the same.

## Verified

- Tests: 1505 feature tests, 35 core tests and 258 transpiler checks, all
  green.
- **On a phone**, the rebuilt apps: the chat's unread count under the time,
  its bubbles and a sent message with its time; the music app's covers,
  three local tracks playing, shuffle and repeat lit, play after the end;
  the feed built from data rows, the heart turning red and the count going
  from 1284 to 1285 on that post alone, "Sponsored" only on the sponsored
  post, stories that advance; the ride sheet reaching the bottom. Paused and
  closed from recents, the player left no notification and no media session.
- 75 example apps transpiled with a deterministic sweep
  (`tools/sweep_apps.py`); every generated difference was expected and read.
- APKs built (`BUILD SUCCESSFUL`) for a job using the whole data layer,
  `files.download()` and an `https` callback, with the Java read by hand.
- **On a phone** (Xiaomi 25069PTEBG, Android 16): the Job Bodies Lab job
  downloaded a page, saved it from the download's `on_result`, and the
  screen's observer counted it; WorkManager reported `SUCCESS`. After the
  status fix the phone showed `success done` -- the same words as the
  Previewer -- and still did after the app was closed and opened again.
- The data rules: 25 questions to Python and to `javac`-compiled Java, no
  disagreement; an APK with all nine field types.
- **On a phone**, the four rebuilt showcase apps: every tab shows its title
  and copy, and Afterglow its three tracks. In five apps, with light bars and
  dark ones, the bottom bar's colour reaches the last row of the screen.
- The job status: the generated `ApkpyJobs.status()`, compiled against
  WorkManager 2.9.0's own `WorkInfo`, answers 18 situations exactly as the
  rule the Previewer uses.

- **Bold on the phone with the font theme**, before and after: labels, the
  toolbar title, markdown bold and headings, the active tab. The bottom bar
  measured 56.0dp before and 64.0dp after, the same as the Previewer.

## Not verified

- The Previewer at Windows display scaling above 100%.
- Bold on a second phone, one whose bold already worked: the measurement
  says to leave it alone, but it has only been read, not seen there.
- `camera`, `contacts`, `nfc` and `wallpaper` inside a job are refused by the
  build with their own codes; the Previewer does not stop them yet.

Full notes: [1.11.0](docs/version-1.11.0.md) ·
[apps you know, rebuilt](docs/showcase.md#apps-you-know-rebuilt) ·
[rows built from components](docs/ui-components.md#rows-built-from-components) ·
[background jobs](docs/background-jobs.md) ·
[data core](docs/data-core.md) ·
[friendly errors](docs/friendly-errors.md)
