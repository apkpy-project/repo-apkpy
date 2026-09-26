# Changelog

All notable changes to ApkPy will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

---

## [1.11.0] - 2026-09-26

### Added

- **Functions that build UI, reused across screens.** A header, a card or a
  bar is written once and called once per screen -- `header("Home", home)`,
  `header("Profile", profile)` -- and `t = stat(...)` binds `t` to the
  component the function returns. The Previewer always ran this as Python;
  the compiler refused it (`U2033` on the `label()` inside the function), so a
  header on five screens was written five times. Now each module-level call is
  replaced by the function's body before anything is translated, with the
  arguments in place of the parameters and the function's own names made
  unique to the call -- the module you would have written by hand. A
  module-level `for` that builds UI is unrolled the same way, over a list
  written in the file or `range(N)`, and a UI function may live in a helper
  file. Called from a tap, a callback or a job, it stops the build with the new
  `U2038` instead: by then the screens exist. A test runs the same app through
  the Previewer and the compiler and compares every screen. On a phone, three
  screens built by two functions showed exactly what the Previewer showed,
  and the returned card answered to its name.

- **A background job can save what it fetched.** The data layer --
  `insert`, `insert_many`, `get`, `find`, `update`, `delete`, `count` and
  `db.transaction()` -- and `files.download()` now run inside a
  `background_job`, `service.every()` and `service.once()`. That is the
  offline queue most apps want: download or ask for something, keep it, and
  let the screen show it.

  Inside a job they answer **before the next line**. The Worker is already
  off the main thread, so it runs the operation where it is instead of
  handing it to the data thread; the Previewer keeps the same order inside a
  job. The callbacks are part of the body, and a screen observing the model
  still hears about the write and re-queries on its own side.

  Each operation is written once: the repository now builds a Task
  (`NoteRepository.insertTask(...)`) that a screen submits and a Worker runs
  here, and the download is one method (`_filesDownloadNow`) that a screen
  calls on a thread and a Worker calls directly -- no third copy of either.
  Verified on a phone: a job downloaded a page, saved it from the download's
  `on_result`, and the screen's observer counted it. The app is
  [`examples/32_offline_queue.py`](examples/32_offline_queue.py).

- **`AGENTS.md` in every new project, so AI assistants write ApkPy.** No
  language model knows ApkPy from its training: asked to add a screen, an
  assistant writes Kivy, or Python that ApkPy cannot translate. `apkpy start`,
  `apkpy init` and `apkpy examples` now put an `AGENTS.md` beside
  `writehere.py` -- the file coding assistants read before they work in a
  project -- with what ApkPy translates, the nine rules that stop a build and
  the API to reach for, plus a `CLAUDE.md` that points Claude Code at it.
  `apkpy agents` adds them to a project that already exists. A copy the
  person has edited is never replaced (`--force` does). A test builds the
  guide's own examples and checks every API name and error code it cites
  against the library, so the guide cannot drift from what builds.

  Tried on AI coding assistants that had never seen ApkPy and had no web
  access, all asked for the same habit tracker. With the first version of the
  guide the app built, but the assistant pre-built sixteen hidden buttons
  because nothing told it how to show rows that change, and its stats never
  reached the other screen on a phone. The guide now carries a list backed by
  SQLite, today's date, the icon names and the rule for values shown on
  another screen; the next assistant built a correct app on its first
  attempt, in a quarter of the time, and it ran in the Previewer as written.

- **`llms.txt` rewritten, and `llms-full.txt`.** The file an assistant with
  web access reads first still described 1.9.0 and quoted the 590 ms cold
  start that measured an empty list. It now says what ApkPy is and is not,
  its limits, its commands and where each answer lives. `llms-full.txt` is
  nineteen pages of the site in one plain file, built from the pages by
  `tools/build_llms_full.py`; a test fails when it falls behind them.

- **Native recipes.** Six ready-made `native.java` blocks for capabilities
  ApkPy has no API for — reading text aloud, opening a page, downloading a
  file, saving a text file, dialling a number and adding a calendar event.
  All six were built **and run on a phone**, which changed two of them:
  `DownloadManager.enqueue()` needs `INTERNET` and was crashing the app,
  and `resolveActivity()` answers `null` from Android 11 without a
  `<queries>` entry, so three recipes were refusing on a phone that had a
  browser, a dialer and a calendar. The guide says plainly which of the
  remaining gaps a block *cannot* close.

- **One set of database rules instead of two.** The data layer had its rules
  written twice -- once for the Previewer, once for the Java that goes on the
  phone -- and an audit found **nine** places where the two copies had drifted
  apart. Every one of them was silent: the app worked at the desk and answered
  something else in your hand. `db.in_("flag", [True])` found nothing on
  Android, `choices=[True, False]` refused every value it was declared to
  allow, an emoji broke `max_length=1` on the phone but not on the desk,
  `contains("%")` returned every row on both, and a blob read back as
  hexadecimal here and Base64 there -- under a comment claiming the two
  matched.

  Each rule now lives once, in `apkpy_lib/data_rules.py`, next to the modules
  that already ended this for icons, colours and the box shorthand. A test
  walks its table and asks both sides: the Previewer by calling the code it
  really runs, and the compiler by lifting the helper methods **verbatim out
  of the generated Java**, compiling them with `javac` and putting the same
  questions to both languages. Twenty-five of them, no disagreements. The day
  they drift again, that test goes red before anything leaves the house.

  **Five of these change what an app already does**, and all five were a
  divergence before:

  - Reading a `db.blob()` in the Previewer now gives Base64, like the phone
    always did, instead of hexadecimal.
  - `db.gt()`, `db.gte()`, `db.lt()` and `db.lte()` against `None` now stop
    with the new `D2014` instead of guessing -- the Previewer used to answer
    with nothing and Android with the opposite rows. `db.eq()` and `db.ne()`
    are unchanged; asking whether a value is there at all is a real question.
  - `NaN` and infinity in a `db.real()` are refused. They used to slip past
    `min_value` and `max_value`, because every comparison with `NaN` is false,
    and SQLite wrote NULL.
  - A whole number written with a decimal point -- `2.0`, which is the shape
    every number out of a JSON response has -- is now accepted by a
    `db.integer()` field. It was accepted on the phone and refused here.
  - `%` and `_` typed into `contains()`, `starts_with()` or `ends_with()` are
    now searched for literally, on both sides. They used to act as wildcards
    by accident, so searching for a per-cent sign returned everything.

- **Rows built from components: `virtual_collection(items, row=post_row)`.**
  A row had fixed slots (title, subtitle, image, meta, badge): a feed post,
  a comment or a product card could not be written, and the photo-feed
  replica built two posts by hand. `def post_row(row):` now builds one row
  from ordinary components with `parent=row`; `{field}` in a text, a
  picture's source or a `describe` is filled from each item, and a command
  that takes an argument receives the item. The Previewer draws a copy per
  visible item; the phone gets a layout of its own per row, inflated and
  recycled by a RecyclerView, its pictures loaded at their own size and
  cached, and the local ones the items name packaged. Checked on a phone:
  four posts from data, square photos, the like button names its post.

- **A row that changes.** `visible="{field}"` shows a component of a row only
  when the item's field is on, and a button's `active="{field}"` shows its
  `active_icon` in its `active-color`; `update_item(id, {...})` patches one
  item and draws its row again. What reads as off (`""`, `false`, `0`, `no`,
  `off`, `none`, `null`) is one tuple both runtimes read
  (`data_rules.FIELD_OFF`). Checked on a phone: the heart turns red and the
  count goes from 1284 to 1285 on that post alone, and back; a sponsored
  post shows "Sponsored", the others do not.

- **All 2,000+ Material Icons.** `icon=` took the 71 names ApkPy drew itself;
  any Material Icons name works now (`add_comment`, `cameraswitch`,
  `chat_bubble_outline`...), drawn from the same paths on both runtimes.
  `icons.search("heart")` finds one. Glyphs from Google's set (Apache 2.0),
  386 KB compressed in the package.

- **Chat bubbles.** A `virtual_collection` with `variant=` styles each kind of
  row with `id:kind`: `align-self` and `max-width` make a bubble that hugs its
  text on one side, `item-border-radius` rounds the rows and `gap` spaces them.

- **`badge-position: end`** draws a chat list as messengers do: the time level
  with the name, the unread count under it, round.

- **`image(..., command=)`, `avatar(..., command=)`** -- a picture you can tap
  -- and **`image.set_src(file_or_url)`**, which changes what it shows; the
  files it names are packaged.

- **Corners one by one:** `border-radius: 22px 22px 0px 0px`.

- **`mini_player(open=..., id=...)` has a stylesheet:** `background-color`,
  `color` (title and play icon) and `subtitle-color` (artist), on its id or on
  `mini_player { }`. It could only follow the theme -- a light bar over a dark
  player screen in a light app.

- **`title-color` and `subtitle-color` on `grid()` and `carousel()`**
  (`color` also sets the title).

- **A player drawn with icons.** An icon button bound to `audio.controls`
  swaps `play_arrow`/`pause` and lights shuffle and repeat in its
  `active-color`; `audio.like_button` swaps `favorite_border`/`favorite`; the
  mini-player's play/pause is an icon. The text defaults are English words --
  they were Portuguese with emoji ("⏸ Pausa", "❤️") that the Previewer drew as
  empty circles.

### Fixed

- **Four showcase apps had empty screens on the phone.** A module-level loop
  that unpacks -- `for page, title, copy in [(...), ...]:` -- was dropped by the
  compiler without a word. Afterglow Music lost its three tracks and the title
  and copy of three tabs; Lumen Finance, Northline Travel and Onda Wellness
  lost the title and copy of three tabs each. The Previewer showed all of it.
  The loops that build UI are now unrolled, so those screens are complete; a
  module-level loop that unpacks and builds nothing stops the build with
  `U2033` and says why. **The published showcase APKs were built without those
  components;** the rebuilt ones show every tab on a phone.

- **The bottom bar on a phone, without a `Theme()`.** The bar was painted with
  the dark fallback and its pill and labels with the light palette -- a lilac
  pill and dark-grey labels on a navy bar -- while the Previewer drew colours
  that belong to that bar. The four colours now come from one rule both
  runtimes read (`theme.nav_colors`). And the 32dp pill covered the top of the
  active label on the phone; the bar now leaves 4dp between them. Seen on a
  phone and fixed there.

- **The bottom bar was 56dp on a phone and 64 in the Previewer.** What the
  bar carries -- 6 above, the 32dp pill, 4 between pill and label, the label,
  6 below -- adds up to 64, and the Material 2 bar kept its own 56 and sat the
  label on its bottom edge. The phone's bar now has the Previewer's height
  (`android:minHeight`), and both read the numbers from one place
  (`theme.NAV_BAR_DP`). Measured on a phone: 56.0dp before, 64.0dp after.

- **Bold came out regular on phones with a font theme.** On a Xiaomi with a
  theme font installed, every weight of the system font links to one
  variable file and the system never turns its weight axis:
  `font-weight: bold`, a toolbar title, markdown `**bold**` and a button's
  medium all drew at regular weight -- in every app on that phone, not just
  ApkPy's. Each screen now measures once whether the system's bold reaches
  the weight the font's own axis reaches, and only where it does not, gives
  each text its weight through the axis, in the font the person chose. On a
  phone whose bold works nothing changes. The new `ApkpyWeight` class does it
  for every screen, the overlays the app builds, and bold inside a text.
  Seen on that phone: every bold, before and after.

  Finding it undid a decision. The active tab's label had been made regular
  in the Previewer because "on the phone only the tint changes" -- measured on
  this same phone, which had lost every bold. Material 1.11 draws the active
  label bold (`itemTextAppearanceActiveBoldEnabled`), and every phone whose
  bold works always showed it that way. The Previewer draws it bold again,
  and the compiler writes the rule down so a library upgrade cannot move it.

- **A black strip under the bottom bar.** On Android 15 and later an app is
  drawn under the gesture area, and the screen's root kept that area as
  padding -- so the page colour showed through beneath the bar, a dark band
  between the bar and the edge of the phone. The bar now takes that area
  itself: its colour runs to the edge and its items stay above the gesture
  handle. The top, where the app bar already did this, is unchanged. On older
  phones, which draw their own navigation bar, it is painted the bar's colour
  with icons that show on it. Checked on a phone in five apps, with light bars
  and dark ones: the bar's colour reaches the last row of the screen.

- **`x["key"]` handed back the whole value on a phone.** Unless the compiler
  knew `x` was a loop row, a key read on a screen assumed a `list_view` row's
  "title — subtitle" text: `x["title"]` cut that text, and every other key
  returned the entire value. `first["name"]` after `first = rows[0]`, a dict
  written in the source, a `json_get()` record and a tapped row's `"id"` all
  came back whole -- in the Previewer they read the key. A key now reads the
  key on every screen, as the background Worker already did.

  And a `list_view` row is the record it came from. `set_items(rows,
  title=, subtitle=)` kept only the text shown, so a tapped row's
  `item["id"]` was that text and `DELETE ... WHERE id = ?` matched nothing, on
  the phone only. The row now keeps every column, plus `title` and `subtitle`,
  and still shows "title — subtitle"; the Previewer keeps the whole row too.
  A real-time search on a `list_view` now finds its rows as well.

- **A component changed from another screen was dropped on the phone.** Each
  screen is its own Activity and only has its own views, so a function
  running on one screen that set a label or showed a button on another left
  no trace in the Java: the Previewer updated it, the phone did not. The
  value is now left for the screen that owns the component, which applies it
  when it comes to the front -- or at once, if it already is (an `https`
  answer arriving after the person moved on). The last value written wins,
  as in the Previewer. `set_value()`, `show()`, `hide()` and `set_items()`
  are covered -- a list's rows travel as that list would have stored them,
  normalised by the same code its own screen runs. Reading another screen's
  component, and the other list operations, still belong on its screen. The
  published
  `26_biometric_lock` was one of them: its vault screen's messages ("Could
  not confirm it was you.") never reached the home screen on a phone.

  Both were found by AI assistants writing a habit tracker from AGENTS.md,
  and checked on an Android 15 emulator: with the old compiler, tapping a
  habit did nothing and the stats screen stayed at 0; with this one, both
  work, and a stats screen brought back to the front shows the new count and
  the new rows of its two lists. Built with only the box switched off, the
  same app showed the old rows. The same two apps then passed on a phone
  (Xiaomi, Android 16).

- **A background job could compile, run, report `success` and do nothing.**
  The body of a `background_job` -- and of `service.every()` and
  `service.once()` -- is written into a WorkManager Worker, and the generator
  for it dropped every call it could not write, without a word.
  `if permissions.has("CAMERA"): ...` became an empty `try`. So did
  `note.insert(...)`, `files.download(...)`, `out.set_value(...)` -- and a
  plain call to one of your own functions, which is how most job bodies are
  written: the method was generated and never called.

  What a Worker can do, it now does: calls to your functions, however deep,
  `permissions.has()` (checked against the application's context, since only
  *asking* needs a screen), `files.delete()`, and -- see Added -- the data
  layer and `files.download()`. Everything else stops the build with the line
  it is on -- **`J7004`** when the call needs a screen, **`J7005`** when it
  could run in the background but is only written for screens so far
  (uploads, WebSockets, location) -- and the error follows your calls into
  helpers. The rule
  lives once, in `apkpy_lib/job_rules.py`, and the Previewer asks it too: a
  job body that reaches one of those calls stops with the same code and the
  same words, once, without a retry, instead of the desk running what the
  phone refuses. An observer setting a label is the screen, not the body, and
  stays open.

  **This can stop a build that went through before** -- and every such build
  was shipping a job with part of its body missing. None of the 71 example
  apps is affected: none had a job body the Worker was cutting short, and
  every one builds as before.

- **A finished job told the screen something else on the phone.** Seen on a
  phone, in the Job Bodies Lab: after a success the desk showed
  `success · done` and the phone `success` with no message and progress `0`
  -- WorkManager clears a finished job's progress, and the status was built
  from nothing else. It was not the only disagreement: a job waiting out its
  backoff was `retry` at the desk and `enqueued` on the phone; enqueuing while
  one ran flipped the desk to `enqueued` while the phone said `running`; and on
  the phone a failure still in WorkManager's history outranked the success that
  came after it.

  The status now has one rule, in `apkpy_lib/job_rules.py`, built from facts
  both sides have -- what is running, what is pending and with how many
  attempts used, and the last thing that finished. The Previewer reports
  through it; the generated `ApkpyJobs.status()` is its translation; and a test
  lifts that method out of the generated file, compiles it against
  WorkManager's own classes and gives both the same 18 situations. The Worker
  now leaves its last message where the status reads it, and the result of the
  last item survives a restart on both sides.

- **An `https` callback inside a job did not compile.** The Worker ignored
  the mark that says a callback's first argument is a boolean, so
  `def got(ok, body)` was declared `String ok` and called with a `boolean`,
  and `if ok:` became `ok.isEmpty()`. javac refused both, unless the
  parameter happened to be called `success`. The Worker now reads the same
  mark as the screens.

- **A transaction that returned a value did not compile, on any screen.**
  `def seed(tx): ... return total` -- the natural way to hand a result to
  `on_result` -- was followed by a `return "";` that javac refuses as
  unreachable. It is written only when the body can end without returning.

- **`service.every(sync, 15)` produced no Worker.** Only `run=` by name was
  read, so the positional form -- the order the Previewer's own signature
  gives -- ran at the desk and never on the phone, with nothing said. Both
  `service.every()` and `service.once()` now read their arguments by
  position or by name, and a `run=` that names no function in the file stops
  with `J7002` instead of being skipped.

- **A storage key that was never written answered `None` in the Previewer.**
  The phone always answered `""`, so `"Last: " + storage.get("step")` worked
  in your hand and raised a `TypeError` at the desk. An explicit default
  still wins.

- **A quick click left a button in its pressed colour.** The Previewer eases
  the fill towards the pressed colour over 90 ms, and releasing sooner --
  a fast click, or a tap on a touchpad -- let the remaining frames run after
  the button had redrawn itself. It stayed grey until the next redraw.

- **A declaration written inside `db.schema()` never reached Android.**
  The schema call collected *variable names* out of its `models=`,
  `relations=` and `migrations=` lists and dropped everything else, so a
  `db.model()`, `db.relation()` or `db.migration()` written inline -- ordinary
  Python, and accepted by the Previewer -- simply was not in the app. No
  table, no `FOREIGN KEY`, no `ALTER TABLE`, and not a word about any of it:
  deleting a parent row cleaned up on the desk and left orphans on the phone,
  and an app that upgraded its schema crashed on somebody else's device with
  "No migration from version 1".

  Refusing the inline form would only have moved the divergence to the end of
  the build, so it is read where it is written, by the same parser the named
  form uses. An entry that is neither a declaration nor the name of one now
  stops the build with the new `C4004` instead of disappearing.

- **A delete stopped short of the far end of a cascade.** With three models
  related A to B to C, deleting a row in A cascades all the way to C in
  SQLite, but the Previewer only told the observers of A and B, so a list
  watching C went on showing rows that were gone. It walked the relations once
  instead of repeating until nothing new appeared, which meant the answer
  depended on the order the relations happened to be declared in -- the same
  schema, written in the other order, was right. The rule joins the shared
  table, and the generated Java always did this correctly.

- **Denying a permission once denied it for ever in the Previewer.** The
  contacts simulator only offered the permission panel from its initial state,
  so after a plain Deny every later call answered `permission_denied` without
  asking. Android reopens the dialog after a plain deny; only "do not ask
  again" is final, which is what the generated Java checks. The effect was not
  a broken app -- it was that the recovery path, the one that breaks most
  often in real apps, could not be exercised at the desk at all.

- **A new NFC reader inherited the previous one's tag.** Starting a new
  session inside a write callback -- `nfc.start(on_tag=other)` -- delivered
  the finished session's tag to the new handler, with nobody having tapped
  anything. The checks after the callback only asked whether the reader was
  started and the screen current, and both survive a restart. The Previewer
  now holds a session number and compares it after running a callback, which
  is what the generated Java has always done.

- **A contacts call that ran here and stopped the build.**
  `contacts.pick("phone", picked)` matches the signature the library
  publishes -- `pick(kind="phone", on_result=None)` -- and it ran in the
  Previewer, but the compiler refused it with a `U2033` about too many
  positional arguments. Its table of contacts arguments listed the options and
  left the callback out, so it allowed exactly one argument fewer than the
  signature promised, on all six verbs. Nobody decided that; nfc, camera and
  flashlight already took a positional callback. The callback is now the last
  positional slot, the refusal for a genuinely wrong call says how many
  arguments there are and names them, and a test compares the two sides'
  arities directly so the next option added to a verb cannot drift again.

- **A cancelled camera was announced as a success.** Only the callback named
  in an API call was marked as taking a boolean first, so
  `on_result=lambda ok, value: result(ok, value)` marked the lambda and left
  `result` with a `String` parameter: `false` arrived as the text `"false"`,
  which is not empty, and `if ok:` ran the success branch. It said nothing,
  which is the part that matters. The mark now follows the boolean into every
  function it is handed to, however many hops. Found in an audit, reproduced,
  then fixed.
- **Keyword arguments were dropped from calls to your own functions.**
  `result(ok=False, value="denied")` declared two parameters and called with
  none, and there was no diagnostic: the build went on and `javac` failed on
  generated code nobody wrote by hand. Names are now lined up with the
  parameters, and a call that cannot be lined up stops the build with the new
  `U2037`.
- **Contrast was measured against the wrong background.** The style cascade
  starts at `body`, which carries the theme's page colour, so every component
  claimed to paint the page: a container's own background was computed, passed
  down and never used. White text on a dark card was reported at 1.14:1 when
  it is 13:1. A check that cries wolf gets switched off.
- **Four icon names that do not exist.** `battery_full`, `credit_card`,
  `payments`, `shopping_bag` and `train` are not in the 71-icon catalogue, so
  both runtimes drew a plain circle -- which reads as a design choice rather
  than a typo. Two of them were in showcase apps whose APKs are published, one
  was in the notifications guide people copy from. All replaced with names that
  exist, the showcase APKs rebuilt, and a test now fails if any example or
  guide names an icon the catalogue does not have.
- **A background job that ended in `return` did not compile.** The generated
  `doWork()` always got a closing `return Result.success();` after its
  try/catch, without asking whether the body already returned on every path,
  and in Java a statement that cannot be reached is a compile error. So
  `def task(): ... return "ok"` -- the most natural way to write a job --
  stopped the build, on generated code nobody wrote by hand. The published
  example escaped by accident: it ends in a call, not a return. The guard for
  exactly this already existed and the Worker simply never used it; it was
  also blind to `try`/`except`, which hit screen functions the same way.
  Reproduced, fixed, and both directions pinned by tests -- cutting the
  closing return where it *is* needed would only trade one compile error for
  another.
- **A number bigger than a Java `int` broke the build.** Python counts as high
  as memory allows; Java's `int` stops at 2,147,483,647. A timestamp in
  milliseconds written into the source came out as a plain `int` and `javac`
  refused, with an error about generated code nobody wrote by hand. Such a
  number now gets the `L` a Java long needs, and one past the long is refused
  with a reason instead of unreadable output.
- **A permission named any way but upper case did not build.**
  `permissions.has("camera")` wrote `Manifest.permission.camera`, and the
  form the native-features guide shows, `"android.permission.CAMERA"`, wrote
  `Manifest.permission.android.permission.CAMERA`; javac refused both. An app
  that asked with `permissions.request()` without `declare_permissions()` did
  not build either (`PERMISSION_REQ_CAMERA` was never declared). Every form
  now names the Android constant, asking declares the permission in the
  manifest, and the Previewer reads `"camera"` and `"CAMERA"` as one.
- **Closed from recents with the music paused, the player stayed** -- its
  notification, its media session and the media island of a Xiaomi phone,
  with the app gone. A paused player now goes with the app, a paused
  notification can be swiped away (which stops it), and music that is
  playing keeps playing, as in any music app. Checked on a phone: paused and
  closed, no session and no notification; playing and closed, still playing.
- **A music app with its own files played nothing on a phone.** Local
  tracks in `audio.play()` / `audio.play_playlist()` were never packaged and
  the media service opened the bare file name: the player stayed at 0:00.
  Local covers -- `arts=`, and the `image` of `grid()`, `carousel()` and rich
  `list_view()` items -- were not packaged either, and the phone looked for
  them as file paths: a shelf of blank cards, a mini-player without its
  cover. Audio now goes into `res/raw`, pictures into `res/drawable`, and the
  Activity and the media service find them by the name the compiler gives
  every picture. Checked on a phone: the replica's three tracks play, with
  their covers on the shelf, the player and the mini-player.
- **Shuffle and repeat did nothing when tapped** unless the app wrote
  `command=audio.shuffle` -- the media guide's own example did not.
  `audio.controls` wires them now, on both runtimes; a button with a command
  of its own keeps it.
- **Play did nothing after the last track.** The finished queue stopped the
  media service, and play reached a new one with nothing to play. The last
  queue is kept while the app runs, and play starts its last track again.
  Shuffle and repeat are read from what the buttons show, not from a new
  service's defaults.
- **When the queue ended, the progress bar stayed at the end** and the time
  read "0:00 / 0:00". It goes back to the start with the last track's length,
  on both runtimes. The Previewer also cleared the track at the end (its
  mini-player vanished) and play did nothing there: it keeps the last track
  on screen and plays it again, as the phone does.
- **The progress bar of `audio.now_playing` was always sky blue** and a
  `range` input ignored `accent-color` on the phone, while the Previewer
  drew both in it.
- **An avatar's `describe=` never reached the phone** (a story ring was a
  nameless button to TalkBack), and in a chat list with
  `badge-position: end` the time shrank to "2..." beside its badge.
- **English on the phone too:** `confirm()` said "Cancel" in the Previewer
  and "Cancelar" on the phone; a `radio` with no options offered "Opção 1".
- **`lambda t=target: ...` in a loop did nothing on a phone.** It is how
  Python gives each button of a loop its own value, and the Previewer ran it
  as Python. The compiler read the lambda's parameters and never its
  defaults: `on_click_navigate(t)` was dropped without a word -- a menu of six
  buttons built by a loop did nothing on the phone -- and `toast(c)` stopped
  the build with a Java error about generated code (B5005). Each default is
  now written into the lambda before translation, which is exact for a
  literal or a name bound once; a default the program changes later is
  refused with `U2039` instead of being translated into something Python
  would not do. Found rebuilding six well-known screens; checked on a phone:
  the six menu buttons open their screens and the loop's toast shows its own
  value.
- **`position: absolute` on a screen's own component was laid out in the
  column** with everything else, on the phone and in the Previewer: no
  floating button, no composer or player bar pinned to the bottom. It is on
  a layer over the content now, fixed while the content scrolls, above the
  bottom bar if there is one; taps that miss its components reach the
  content. Every view keeps its id.
- **A sheet at `bottom: 0` stopped above the navigation bar,** leaving a strip
  of map under it. It reaches the bottom of the screen now, as a bottom sheet
  does.
- **A scrolling screen without a bottom bar drew its title under the
  clock** on Android 15 and later: with targetSdk 35 the window is
  edge-to-edge, and that was the only screen root that did not fit the
  system windows. Six of the published examples had it, the Knowledge Vault
  tutorial among them.
- **The clock was dark on a dark screen** in a light app -- a chat, a player,
  a story. On a screen without an app bar the status icons now follow the
  colour behind them, read at run time (tokens and night mode included).
- **An icon-only button's icon sat left of centre** (the like on a post, the
  send button): MaterialButton kept its 8dp icon padding. Centred now, and
  a button that is only an icon, with no size in the stylesheet, is a 48dp
  square -- the touch target Android asks for and what the Previewer draws.
  Checked on a phone: Onda's profile button.
- **An avatar's ring was cut at the sides** and drawn over the picture: the
  stroke is inside the view now.
- **`margin: 4px 14px 0px 14px` on a label wrote `layout_marginTop` twice,**
  which AAPT refuses: the app did not build. The shorthand is written out as
  its four sides first; a label's indent also sees its left side now.
- **Grid and carousel cards were white on the phone whatever the stylesheet
  said.**
- **An absolute box with no width was as wide as the screen,** so
  `right: 12px` did nothing -- a column of buttons sat on the left edge. It
  is as wide as its content, as in CSS; with `left` and `right` it
  stretches between them. Same in the Previewer.
- **`align-self` on a screen's own component did nothing,** and `max-width`
  centred every chat bubble, the reply that belongs on the right included.
- **A label with `flex-grow` had its text centred on the phone** ("Thursday
  plan" in the published Northline) while the Previewer and CSS keep it at
  the start.

### Previewer

- **Rounded shapes are antialiased.** Tk fills a polygon without smoothing
  on Windows, so every rounded button, card, field and ring had stepped
  edges -- people trying ApkPy took that for what Android would show. Shapes
  are drawn as images: the flat interior at its own size and the corners at
  4x, scaled down (1-2 ms at any size). The press tint and the theme fade
  still reach them. `APKPY_PREVIEW_AA=0` draws the old polygons.
- **See-through over a picture.** A transparent button, label or row over an
  image or the camera was a black square; it shows the picture now, and a
  glass colour darkens it as on the phone.
- **Soft shadows.** `box-shadow` was two near-black layers offset down and to
  the right, a hard dark edge on light screens. It is a blurred shadow now,
  and a card's content no longer pokes out of its rounded corners.
- **The screen starts below the status strip,** as on the phone; content was
  laid out from the top of the window, half a row of chips under the clock.
  `height: 100%` is what is left below it.
- **Rows as the phone lays them out:** a label in a flex row or column has no
  padding of its own (8px each side and a doubled top margin before); a
  label with `margin-left` is measured from the edge, as on the phone; a
  growing box in a row fills its slot (a composer's pill left a hole before
  the send button); a container that grows taller tells the one holding it
  (the pill stayed 19px tall, its text height, and vanished); a chip's width
  is rounded up ("Music" wrapped to "Musi / c").
- **A field with a background has no underline,** as the phone's shape
  drawable has none.
- **A button has the size the stylesheet gives it.** `width`/`height` never
  reached the code that draws a button, so a 76x76 ring came out as a pill
  the width of its text, while the phone drew the circle.
- **Glass colours.** `#AARRGGBB` lost its alpha: a `#33FFFFFF` button was an
  opaque white disc hiding its white icon.
- **A square transparent button took the Previewer down** (Tcl rejects
  `#00000000`); it draws no body now.
- **Round images keep round borders**, and badges are round as on the phone.
- **`height: 100%`** fills the parent for `image`, `map_view` and
  `camera_view`, as `match_parent` does on the phone. The map read it as
  100 pixels.

### Known limits

- The Previewer sees through a transparent component to a picture under it,
  not yet to another component; a label's text over a picture is centred on it.
- A `display: flex` row with no `justify-content` centres its children, as
  ApkPy always has, where CSS starts them. Write `justify-content: flex-start`;
  changing the default would move existing apps.

---

## [1.10.0] - 2026-09-19

### Added

- **More than one file.** `writehere.py` can `import` plain Python modules
  beside it and share their functions and constants across screens. The helper
  is merged before anything is translated, so its functions become ordinary
  methods of the generated Activity and the Previewer needs nothing special.
  Only the whole-module form is accepted; `from helpers import x` and a name
  defined in two files stop the build with the new `U2036`.
- **Numbers that stay numbers.** A function parameter every call site fills
  with a number now counts as one inside the body, so `cents / 100` is
  arithmetic instead of a refusal. Numbers written at module level are emitted
  as fields, and a function whose every `return` is a number lets one helper
  feed another. Anything ApkPy cannot prove is a number stays text.
- **What it reaches.** A page naming every Android capability ApkPy covers
  and every one it is missing, with the numbers measured against
  `android.jar` rather than estimated.

### Fixed

- **`margin` with more than one value.** Both renderers stripped the
  non-digits out of the whole string and read the rest as one number, so
  `margin: 24px 16px 0px 16px` became a margin of 2,416,016: the Previewer
  screen went blank and the phone layout was pushed off it, with nothing
  said on either side. The CSS shorthand is now read once, in the module
  both renderers share.

---

## [1.9.0] - 2026-09-19

Read the [complete 1.9.0 notes](docs/version-1.9.0.md).

### Added

- `contacts.pick`, `list`, `get`, `create`, `edit` and `settings`, with
  two-argument UI-thread callbacks and explicit reason strings.
- Scoped phone/email selection without broad contact access; paginated
  display-name search and detail reads with runtime `READ_CONTACTS` permission.
- User-mediated native create/edit forms. No `WRITE_CONTACTS` or direct delete
  API; editor return is not save confirmation.
- Fictional, theme-aware Contacts Previewer with picker, editor and permission
  simulation. No desktop address book is read or written.
- [Contacts guide](docs/guides/contacts.md) and complete
  [People Desk app](examples/30_contacts.py), plus reference, permission,
  troubleshooting, compatibility and 1.9.0 documentation.

- `native.java()` and `native.java_async()`: declare a Java block with the
  arguments it takes, the `imports=` it needs and a `preview=` that answers
  on the desktop, then call it like any function. An async block answers
  `(ok, value)` through `done` from any thread; ApkPy moves it to the UI
  thread. `native.gradle()`, `native.manifest()` and `native.keep()` add the
  dependency, manifest entry and R8 rule around it.
- Blocks that would be silent are refused with `U2035`: no `preview=`, code
  computed at run time, a `java` block with no `return`, a `java_async`
  block that never calls `done`, a call with the wrong arguments, or a
  block called from a background job.
- [Your own Java guide](docs/guides/native.md) and
  [example](examples/31_native_java.py).

- `nfc.status`, `start`, `stop`, `write(text=... / url=...)`, `cancel_write`
  and `settings`: foreground NDEF reading and one-shot writes, shared error
  vocabulary and UI-thread callbacks.
- Theme-aware in-frame NFC simulator with six tag types, write failures,
  cancellation and tag-loss simulation. No desktop radio is implied.
- Optional manifest permission/feature, lifecycle cleanup and stale-callback
  rejection. Apps that do not use NFC receive no NFC runtime.
- [NFC guide](docs/guides/nfc.md), API reference and
  `examples/29_nfc_tags.py`, including the formatable-tag read-back limitation.
- NFC documentation across README/package-description draft, home page, guide
  hub, API overview, compatibility, Previewer comparison, troubleshooting,
  example index and [1.9.0 notes](docs/version-1.9.0.md).

This work is not published. Package version and release metadata are unchanged.

## [1.8.0] - 2026-09-12

Read the [complete 1.8.0 notes](docs/version-1.8.0.md).

**Upgrading:** several fixes below turn silence into build errors. Code that
relied on `%` formatting, arithmetic on text, unpacking, item or attribute
assignment, `for ... else` or a comprehension outside the search callback
quietly doing nothing will now stop the build, naming a form that compiles.

### Added

- An in-app camera: `camera.open()`, `capture()`, `record()` and
  `capabilities()` with photo and video, both lenses, zoom, focus, exposure,
  flash and torch, a timer, pause and resume, a review step, manual ISO,
  shutter, white balance and focus, and a customisable interface.
  `camera.capture()` keeps its 1.7.0 callback.
- `camera_view()`, a live viewfinder embedded in your own layout.
- `in` and `not in` inside `and`, `or` and `not`, `x not in y` on its own, and
  `in` in a ternary condition. Membership for lists, tuples, sets and dicts
  written in the source or kept at module level; a text search otherwise.

### Changed

- `apkpy release` shrinks with R8 (`minifyEnabled`, `shrinkResources`) and keeps
  names readable with `-dontobfuscate`: a measured release went from 4,496 KB
  to 1,536 KB. Release builds take longer; `apkpy run` is unchanged.

### Fixed

- An `if` whose condition ApkPy could not write no longer disappears, body and
  all: it stops the build with U2033. That covers `is`, chained comparisons and
  any other shape without a translation, at module level and in functions.
- A ternary whose condition could not be written no longer becomes empty text.
- A comparison with a side ApkPy could not write -- inside `and`, `not` or a
  ternary -- no longer compiles to `Double.parseDouble("")`, which crashed the
  app when that code ran. Calls into
  the other runtime of a background job (`job.input()`, `job.attempt()`) stay
  exempt, as before, and so does `get_value()` of a component in a callback
  that is also written into a screen without that component.
- A list comprehension at module level no longer creates an empty list.
- An f-string format other than `.Nf` no longer prints the unformatted value on
  the phone while the Previewer formats it.
- `x in some_list` now asks the list instead of searching its JSON text, which
  answered `True` for `"a" in ["ab"]`.
- `text.split()` compiled to Java's array: a `for` loop over it ran no times,
  `len()` counted the characters of its address, and a label showed
  `[Ljava.lang.String;@…`. It is now a list with Python's rules -- the separator
  is text rather than a regular expression, empty parts are kept, `maxsplit` is
  honoured, and with no separator it splits on whitespace. `x in
  text.split(",")` is membership. Checked against `str.split` on 628 cases.
- A `range()` index is a number. `i + 1` showed `01` on the phone and `1` in the
  Previewer, `n += i` joined text, and `i % 2` had no translation.
- Arithmetic ApkPy cannot write -- `"n=%s" % n`, `price * 2` on text from an
  input, `"-" * 20`, `-n` on text -- no longer becomes empty text. It stops the
  build with U2033 and a form that compiles. `-x` of a number is translated.
- Assignments that left the app without a word now stop the build with U2033:
  unpacking, `a = b = 0`, assigning to an item or an attribute, and a
  comprehension, a condition, a tuple or a set used as a value. `x = -1`,
  `x = a if test else b` and `x = math.pi` now translate instead.
- `for` loops that were left out, or ran over nothing, now stop the build with
  U2033: unpacking, `for ... else`, and looping over text, a dict or a set. A
  tuple written in the source is looped like a list.
- `not x` used as a value no longer becomes empty text.

## [1.7.0] - 2026-09-08

Native device updates, portable text processing and actionable notifications.
Read the [complete 1.7.0 notes](docs/version-1.7.0.md).

### Added

- Accelerometer, gyroscope and pressure streams, plus complete documentation for
  all existing sensors and battery snapshots. Hardware availability is explicit.
- Static home/lock/both wallpapers, with preview and mandatory user confirmation.
- A portable subset of `re.match`, `re.search`, `re.findall` and `re.sub`, including
  Match captures and constant flags; unsupported patterns stop generation clearly.
- Extended `notify()` with channels/importance, monochrome native icons,
  big-text, picture and inbox styles, up to three actions, tap/dismiss callbacks,
  grouping, ongoing/progress state and displayed timestamps. Existing calls
  with title, message and ID remain supported; timestamps do not schedule delivery.
- `notifications.channel()`, `allowed()`, `ask()`, `cancel()` and `cancel_all()`.
  Activity permission requests, workers and ApkPy-handled Firebase messages use
  the shared native publisher. Projects without the feature get no notification
  helper or Activity notification hooks.
- Persistent Previewer cards in the device window; high-importance heads-up
  banners expire without deleting their cards. No notification Toplevel.
- A complete [notification guide](docs/guides/notifications.md), four checked
  Python examples, real Previewer screenshots, callback signatures, a demo
  control checklist and an app-only Order Desk download.

### Changed

- Redesigned Previewer drawer: fixed header, scrollable rounded cards, improved
  title/body hierarchy, soft icon backgrounds, full-area action pills, wrapping
  labels, progress tracks, and clearer permission/empty states in both themes.
  Wide windows center the content; redraws preserve scroll where possible.
  This does not restyle Android's system-controlled notification shade.
- Order Desk's View action opens details and cancels the card. Later cancels
  and confirms; it intentionally does not schedule a reminder.

### Fixed

- Values written with `set_value()` survive Android Activity recreation without
  disabling orientation changes. Screen-local values remain isolated.
- The demo/guide background callback now uses `task()`, not `task(job, payload)`.
- Conflicting button drawables from different screens receive separate names
  instead of overwriting one another and making labels invisible.
- Generated worker helpers use application Context, not Activity-only methods.
- Bundled big pictures are copied into Android assets. Cancelled/superseded
  image loads cannot publish stale cards.
- Notification permission queuing survives Activity recreation; callbacks work
  with warm and newly created Activities. Dismissal never forces an app launch.

### Verification and limits

- 970 feature tests (including 21 focused notification tests), 258 transpiler
  checks, both Previewer scripts and the four guide examples passed.
- Notification Lab and Firebase integration projects compiled with Gradle.
  The lab passed 39 instrumentation checkpoints on Android 16 / API 36;
  direct system-drawer View/Later taps were also checked on that device.
- The Previewer simulates permission and does not reproduce sound, vibration,
  lock-screen policy or process survival. Android 14+ can allow dismissal of
  ongoing cards. Actual FCM remote delivery and other device versions were not
  validated. Test counts cover the recorded scenarios, not every device.

## [1.6.1] - 2026-09

Three fixes that landed just after 1.6.0 was published. A version on PyPI
cannot be replaced, so they arrive here.

### Fixed

- **Google Play rejected builds made with 1.6.0.** Projects were generated with
  `targetSdk 34`, below the minimum Google requires for a new app or an update.
  1.6.1 targets API 35.
- **Every screen root now declares `fitsSystemWindows`.** From API 35 Android
  draws the app behind the status and navigation bars, so without this the
  first line of a screen without an app bar would sit under the clock. On the
  root deliberately: it consumes the insets, so the toolbar's own listener
  stops growing and the top is not padded twice. Checked on Android 16 across
  all five screen shapes.
- **`background-color` on a label did nothing on the phone.** The `TextView`
  never carried a background, so dark text on a light band came out invisible
  on the device while looking right in the Previewer. The accessibility report
  was measuring contrast against that unpainted background; the number now
  describes what is on screen.


## [1.6.0] - 2026-09

Almost everything here began the same way: something did not work, and nothing
said so. Full notes in [Version 1.6.0](docs/version-1.6.0.md).

### Added -- the app now says what it could not do

- **`U2033`** -- Python with no translation stops the build and names the
  construct, instead of compiling to the empty string. Separates a gap ApkPy
  has not filled (`re`, `json.dumps`, `base64`) from a wall that cannot exist
  on a phone (`requests`, `numpy`, `os`), and points at the ApkPy API that
  covers the same ground. Also catches a mistyped helper, `print()`, and a
  modal opened above the line that creates it.
- **`try` / `except` / `finally`** -- the body used to be dropped whole. One
  handler, deliberately: Python's exception types have no equivalent where
  every value is text, so a second one is refused with its reason rather than
  half-honoured. `except ... as e` binds a String.
- **`items.append(x)`**, plus reading a list back: indexing with Python's
  negative indices, `len()`, and `for`. A module-level list the app appends to
  is now one list for the whole app, as it is in Python.
- **`math`**, with `abs`, `min`, `max` and `sum`. Only names where Java's
  answer is Python's; `log2` and `inf` are left out with their reasons.
- **The list of translated Python** now exists, on Compatibility and limits.

### Added -- hardware, money and business

- **`bluetooth` and `ble`** -- both radios, the same four verbs and the same
  result contract. Classic declares no location permission at all; BLE defaults
  to the Nordic UART Service. Ten reasons, never an empty string. Verified
  against a real device.
- **`billing`** -- one-time unlocks and subscriptions, acknowledged before
  success is reported, with purchases completed while the app was closed
  settled on the next launch. Compiled and reviewed; never sold.
- **`translations()` / `t()` / `language`** -- each language becomes its own
  `res/values-<tag>/` folder, the phone picks by locale, and `language.set()`
  switches while the app runs.
- **`crash.last()` / `crash.clear()`** -- the previous crash, kept where the
  next launch can read it. No vendor chosen, no endpoint invented.
- **`scan.code()`** -- barcodes and QR codes with **no CAMERA permission**.
- **`app.version_code()` / `version_name()` / `open_store()`** and
  `modal(dismissable=False)`, which together are a forced update without a
  protocol imposed on you.
- **`https.pin()`** -- certificate pinning as configuration, with two pins
  required. The Previewer opens a real handshake and prints the live pin when
  it does not match.
- **`describe=`** on components, and a `U2035` accessibility report during the
  build: undescribed images, unlabelled icon buttons, text below WCAG contrast,
  tap targets under 48dp.
- **Encryption that travels** (`crypto.encrypt(password=)`, a standard
  PBKDF2 + AES-GCM format), `crypto.totp()` verified against RFC 6238's
  vectors, plus `token()`, `hash()`, `hash_file()` and `secure_screen()`.

### Fixed

- **Auto-backup was emptying people's data.** Values are encrypted with a key
  in the old phone's Keystore, which does not travel, so a restored app read
  every one of them as empty and reported it as never saved. The encrypted
  store and login token are now excluded from cloud backup and device transfer.
- **`round(2.5)`** gave 2 in the Previewer and 3 on the phone. Over 4001
  values the old rule disagreed with Python on 1000 of them.
- **Decimals printed differently on the two sides** -- `math.pow(10, 8)` was
  `1.0E8` on the phone and `100000000.0` on the desktop. Proven against
  `repr()` across 90 022 values.
- **`math.floor(2.7)` printed `2.0`**; floor, ceil and trunc return an int.
- **`math.sqrt(-1)` returned NaN** and put that word on screen, where Python
  raises. Both sides now raise.
- **Indexing a list generated invalid Java** (`(x)[Integer.parseInt(...)]`).
- **`set_items()` inlined the original list**, so the screen kept showing the
  starting items after the list had grown.
- **`label(MSG)` and `label("a" + "b")` produced an empty attribute** -- the
  text showed in the Previewer and nothing on the phone.
- **Two shipped examples were broken**: `22_chat_composer.py` appended to a
  list, which did nothing, and `23_settings_rows.py` opened a modal declared
  below its own button.


### Added

- **`bluetooth` and `ble`** -- talking to hardware over both Bluetooth radios,
  with the same four verbs and the same result contract: `devices()`/`scan()`,
  `connect()`, `send()`, `disconnect()`. Lines of text out, lines of text back.
- **Classic declares no location permission at all.** `devices()` lists paired
  devices rather than scanning, because an RFCOMM socket needs a bonded device
  anyway and pairing belongs to system Settings. An app that only talks to a
  printer should never have to ask where its user is. BLE has no such choice --
  devices advertise -- so its scan grant is capped at API 30 and carries
  `neverForLocation` above it.
- **`ble` defaults to the Nordic UART Service**, which is what an ESP32, a
  micro:bit or an HM-10 exposes, so the common case names no UUIDs. Others are
  named in 16-bit shorthand or in full, expanded identically on both runtimes.
- **The permission and the radio are asked for, not assumed.** If the
  permission is missing the app asks and resumes what you called; if Bluetooth
  is off it offers Android's own prompt to turn it on. Either refusal is
  remembered, so a second tap reports `denied` or `off` instead of reopening
  the dialog.
- **Ten reasons, never an empty string** -- `off`, `unsupported`, `denied`,
  `not_paired`, `not_found`, `unreachable`, `no_service`, `not_connected`,
  `lost`, `failed`. Both runtimes read one table, and the generated Java's
  `switch` is emitted *from* it.
- `terminator=` on `send()`: `newline`, `return`, `crlf`, `none`, or the
  characters. Sending the wrong line ending is the usual reason a board never
  answers.
- BLE writes are queued, so several `send()` calls in a row arrive in order
  instead of the second being refused -- GATT allows one operation at a time.
  A connect that never answers times out with `unreachable` rather than
  hanging forever.
- `bluetooth`, `link`, `fingerprint`, `lock` and `lock_open` in the icon
  catalogue. **70 names.**
- The Previewer offers one openly simulated device and a monitor you drive by
  hand: what the app sends appears in it, what you type arrives at `on_line`.
- **The link outlives the screen.** It lives in a generated
  `ApkpyBluetooth` / `ApkpyBle` class rather than on an Activity, so
  connecting on one screen and talking on the next works. A screen that
  wants the lines calls `connect()` again -- already-open is free, and it
  simply adopts the new callback. A screen owns only its callback: being
  destroyed stops it receiving, it does not close the radio.

- **`billing`** -- Google Play in-app purchases and subscriptions.
  `prices()`, `buy()`, `subscribe()`, `owned()` and `consume()`, with the same
  `(ok, value)` contract as everything else.
- **Every purchase is acknowledged before your callback is told it worked**,
  including one that completed while the app was closed: that case never
  reaches the live listener, so `owned()` settles anything it finds
  unacknowledged.
  Google refunds anything an app leaves unacknowledged for three days, so this
  is not a call you can forget: `consumable=True` consumes instead, which
  settles the same clock and is what lets something be bought again.
- `pending` is its own word, not a success and not an error: a slow payment
  method has started and nothing should be unlocked yet. So is `owned`, which
  means they already paid.
- Prices are asked of Play rather than written down, so they arrive in the
  person's own currency and locale. A subscription reports the offer that
  `subscribe()` will actually launch.
- `owned()` reports every purchase with its `token`, because on-device state
  can be faked and a server checking that token is the only real proof.

### Fixed

- A permission whose name carries a package -- `com.android.vending.BILLING` --
  was written as `android.permission.com.android.vending.BILLING`, and turned
  into a Java identifier with dots in it. The namespace is only added to a
  bare name now, and the identifier uses the last segment.
- `AndroidManifest.xml` could only write a permission's name. Bluetooth needs
  `maxSdkVersion` and `usesPermissionFlags`, so an entry may now carry
  attributes -- and everything that builds a Java identifier from one reads the
  bare name, which a real build caught after brace-counting did not.

### Known limits

- **Checked on a phone, up to the point a peer is needed.** An Android
  emulator has no Bluetooth radio, so this was exercised on a real device
  against a smartwatch: the permission and enable prompts appear, a scan finds
  real devices, connecting establishes the link and discovers services, and
  every failure word comes back correctly -- including `unreachable` after the
  fifteen-second timeout. **Not yet proven:** lines arriving through
  `on_line`, `send()` reaching a peer, and the write queue under real timing.
  Those need a board that speaks back.
- Line-oriented text only, one device at a time, client only, and pairing stays
  in system Settings.

---

## [1.5.0] — 2026-08-31

Two things, and they turned out to be the same thing.

The first is **the fingerprint check**: `biometrics.unlock(...)`, one call with
one result. The second is **the two renderers agreeing** — a shared vocabulary
for sizes and surfaces, and the places where the Previewer and the Android
generator had quietly picked different numbers for the same idea.

They belong together because the biometric prompt is the sharpest case of the
same problem. Android draws that dialog itself, so an app supplies three
strings and the platform does the rest — and the only thing the two runtimes
*can* agree on is the words and the result. Getting that right meant giving the
seven possible outcomes one shared table, which is exactly what the type ramp
and the surface planes do for sizes and colours.

A value with no shared name is a value each side is free to guess at. Both
sides guessed reasonably. That is precisely why nobody noticed.

### Added

- **`biometrics.unlock(...)`** -- the fingerprint or face check, as one call
  with one result. Android draws this dialog itself, so the API is the three
  strings it lets an app choose: `title`, `subtitle` and `cancel_text`. Plus
  `allow_pin=True` for the device PIN, pattern or password, which drops the
  cancel button because `PromptInfo.Builder` refuses a negative button
  alongside `DEVICE_CREDENTIAL`.
- `on_result` receives `(success, reason)`, and `reason` is one of seven
  words -- `ok`, `cancelled`, `no_hardware`, `not_enrolled`, `unavailable`,
  `lockout`, `failed` -- **never an empty string**. Both runtimes resolve them
  from one table, so an app that says "try again" for a missing sensor is a
  bug you can write, not one the library hands you. A scan that simply does
  not match is not a result: the prompt stays open on both sides.
- The Previewer draws a **replica** of the system dialog from the same three
  strings. Click the fingerprint to scan, right-click it for a bad scan,
  Escape to cancel. The desktop hint sits on the scrim, outside the card, so
  the card stays a copy of what the phone shows.
- `fingerprint`, `lock` and `lock_open` in the icon catalogue, with
  `biometrics`, `touch_id` and `unlock` as aliases. **68 names.**
- `USE_BIOMETRIC` is declared automatically, and
  `androidx.biometric:biometric:1.1.0` is added only to an app that asks for
  the prompt. An app that never mentions it generates the project it generated
  before -- no interface, no runtime, no permission, no dependency.

- **A type ramp.** `--text-xs`, `--text-sm`, `--text-base`, `--text-lg`,
  `--text-xl`, `--text-2xl` and `--text-3xl`, resolving to **11, 12, 14, 16,
  20, 24 and 32** at the default `Theme(font_size=14)` and scaling with it.
  The steps are Material's own sp values, **not** a geometric series: one
  ratio produces 29.3 where the platform says 32, and each renderer rounds it
  differently. Across the 25 shipped examples there were **17 distinct font
  sizes**, with 13px, 14px and 15px accounting for 32 uses between them --
  the same intent written three ways.
- **`--leading-tight`, `--leading-normal` and `--leading-loose`** (1.2, 1.45,
  1.7). `line-height` already read a bare number as a multiple of the font
  size on both sides, so these ride on machinery that was already correct.
- **Three planes: `--surface-low`, `--surface-high` and `--border-subtle`.**
  A card that has to sit on a surface, a well that has to sit under one, and a
  divider that should not shout. When the app declared its own
  `surface`/`background`/`border`, all three are **derived from those
  colours** rather than falling back to Material's palette -- otherwise a warm
  theme grows a cold grey plane it never asked for. `--surface-high` is the
  surface 6% toward the text, `--surface-low` is 55% of the way to the
  background, and `--border-subtle` sits 35% from the surface toward the
  border, which is where Material puts `outlineVariant` in both modes.
- Like every other theme token, the three new colours are written into layouts
  and drawables as **resource references**, so `values-night/` answers them
  and `appearance.set()` moves them.
- `U2031`: a token used in a slot of the wrong kind. `--text` is a colour and
  `--text-lg` is a size, three characters apart. A size in a colour slot dies
  in `parseColor` when the screen opens; a colour in a size slot is worse --
  `#211F26` silently becomes 21px and the app just looks wrong. A composite
  value like `0 3px 8px var(--border)` is left alone.
- `U2029`: a stylesheet property no renderer reads is reported by name, with
  the closest match and a link to the table. `frobnicate: 3px` used to
  transpile clean, and so did `elevation`, `transform`, `overflow` and
  `background` -- four names a person reaches for out of browser habit, all of
  them dropped when the layout was written. That looks like the *value* not
  working rather than the *name* not existing, which is why it goes unnoticed:
  designing is a loop -- try, look, adjust -- and half the loop returning
  nothing with no message turns it into guessing. It is a warning, not a
  failure, the way an unknown icon name is.
- The full stylesheet vocabulary is now a table in the docs, generated from
  the same set the two renderers read, so it cannot drift from what actually
  works. **87 properties.**

### Fixed

- The prompt reached for `ui._app.root` to find its window. `ui._app` is a
  lazy proxy, so *asking* it builds the Previewer -- which would have opened
  an empty window from `apkpy build` alone. It now checks whether one was
  constructed before touching it, the same guard the motion work needed.

- **`label("...")` with no stylesheet at all was 14px in the Previewer and
  16sp on Android.** Two literals written into two files at different times,
  each defensible on its own, and invisible because "body text" had no shared
  name for the two sides to disagree about. It is the most used component in
  the library, so the gap was in every app ever built with it. Both sides now
  read the same step of the ramp; **the phone's number wins**, so no compiled
  app changes.
- **The active tab's label in the bottom bar was bold in the Previewer and not
  on the phone.** Material's `Widget.MaterialComponents.BottomNavigationView`
  points `itemTextAppearanceActive` *and* `itemTextAppearanceInactive` at the
  same `textAppearanceCaption` -- 12sp, weight normal -- so on the device only
  the tint changes, and the state is carried by the pill and the filled icon.
  The desktop was adding a third signal the phone does not have. The same line
  also asked Tk for ten *points*, which is 13.3px at 96dpi, where the phone
  renders 12sp. Previewer-only: the generated XML is unchanged.
- `box-shadow` on a `container` drew a shadow in the Previewer and nothing on
  the phone. The container branch never asked for `android:elevation` -- the
  card and the image did -- so the same declaration meant two different things
  depending on which runtime read it.
- And asking was only half of it: a `ViewGroup` clips its children to its
  padding box, so a shadow was drawn and then cut off exactly where it starts.
  The parents of anything that asks for a shadow, and the screen root, stop
  clipping. **Cards have carried `box-shadow` in the theme defaults since the
  beginning and have been having their shadow clipped away all along**, so an
  app that uses `card` will look slightly different -- it now gets the shadow
  it always asked for. An app with no shadow anywhere generates the XML it
  always generated.
- `padding` with three or four values reached the Previewer whole and the
  compiler truncated it to two: `padding: 0 20 24 20` came out as
  `0 20 0 20` on the phone, and the bottom silently disappeared. Both sides
  now read one, two, three and four values the way CSS reads them.
- `padding-top`, `padding-right`, `padding-bottom` and `padding-left` were
  read by neither renderer, despite appearing in the shipped examples. They
  are read by both now, and overlay the shorthand.

---

## [1.4.0] — 2026-08-27

Two batches that turned out to be one. An app that can hold a conversation
with an API -- a request body that keeps its types, a timeout long enough for
something that thinks first, an answer rendered as Markdown in a row that
takes the height it needs -- and an app that stops looking like every other
app built with the same tool: a drawer, a settings row, a typeface of your
own, and control over tracking, leading and alignment.

They are one release because they are the same problem seen twice. An
assistant app is not hard to build; it is hard to make look right, and every
shape it needed was missing.

And an app that looks like yours has to keep looking like yours in the other
mode, so the release ends where it had to: colours that stop being literals
in a compiled layout, and a switch that changes them while the app runs.

### Added

- `appearance.set("dark" | "light" | "system")` and `appearance.get()`: the
  app changes its colours while it runs, and opens the way it was left.
  Android reads `values/` or `values-night/` and `AppCompatDelegate` picks;
  the Previewer swaps the theme and re-renders. Different machinery, and the
  same two palettes, because both are built from the one `Theme` the app
  declared.
- A colour that came from a theme token is written into layouts, drawables and
  the generated Java as a **resource reference** rather than as a literal. A
  two-screen app went from 472 literal colours to 98, and what is left is what
  should be left: mixed shades, transparents, and the colours the author wrote
  by hand.
- `Theme.counterpart()`: the same theme in the other mode. The accent carries
  over and the surfaces flip -- a background chosen at `#1B1B19` was chosen
  *because* the mode was dark, so carrying it into light would produce a light
  mode that is still dark, which is a switch that appears to do nothing.
- The status bar's clock and battery follow the mode. They are drawn by the
  system over whatever the app puts behind them, and deciding light-on-dark at
  build time left them invisible the moment the app switched. The answer comes
  from the same resource qualifier the colours do.
- `dark_mode`, `light_mode` and `contrast` in the icon catalogue -- an
  appearance screen needs a moon, a sun and a half-filled circle, and the
  catalogue had none of the three. **65 names, 96 with aliases.**

- `U2028`: a stylesheet asking for a theme token that does not exist is
  reported by name, with the closest match and the full list of tokens. It
  used to resolve to *itself* -- the literal text `var(--muted)` travelled
  into the layout XML and surfaced forty seconds later as an AAPT link failure
  whose stated cause is about stale generated files. Raised in the one module
  both runtimes read, so whichever you run first is the one that tells you.
- `scroll_to_end()`, `scroll_to_top()` and `scroll_to_item(id, key="id")` on a
  virtual collection. Adding a row never moved the viewport, which is right for
  a feed and wrong for a conversation: you send a question and end up looking
  at your own question while the answer grows below the fold. The scroll is
  animated over the duration the theme's `motion` preset gives the `nav`
  moment, out of the table both runtimes read, so `motion="none"` makes it a
  jump on the desktop and on the phone alike.
- An `avatar` slot in a collection's `template` draws a circle with up to two
  initials taken from its value, over a colour that value picks. It is what
  separates a list of paragraphs from a conversation: two speakers you tell
  apart at a glance. One palette decides the colour -- read directly by the
  Previewer, written into the generated Java as a literal by the compiler --
  so the same name cannot be orange on one side and green on the other. An
  empty value hides the circle rather than leaving a coloured hole.
- CSS `code-copy: button` puts a tappable **Copy** under every fenced code
  block, in a `markdown()` component and in a collection's `markdown` slot. It
  copies that block and nothing else -- not the paragraph above it, not the
  whole message. A block of code you cannot copy is a block of code you retype
  by hand. On Android 13 and later the system shows its own confirmation for
  every copy, so the app stays quiet rather than talking over it.
- CSS `max-rows` on a `type="textarea"`: `rows` is where the field starts and
  `max-rows` is where it stops growing, and between the two it follows the
  text. One line is the right start for a reply box; two fixed lines are half
  an empty composer waiting. Without `max-rows` the ceiling is what it always
  was.
- `virtual_collection(item_height="auto")`: each row wraps its own content
  instead of every row taking the same measured-out height. A conversation
  needs it -- one fixed height gives "yes" the same space as a twenty-line
  answer, so one floats in a void and the other is cut off mid-sentence. Text
  also stops being clipped to a single line unless the stylesheet says
  otherwise. A number still fixes every row, exactly as before.
- A `markdown` slot in a collection's `template` renders that field as
  Markdown -- headings, emphasis, links, lists, quotes and fenced code blocks
  -- rather than as plain text. It is the same renderer the `markdown()`
  component uses, extracted rather than copied, so a fenced block looks the
  same in a row as it does on a page. Both runtimes read the same styles for
  the same reason.
- A dict passed as `data=` to `https.post` / `put` / `patch` is sent as JSON,
  with the types of the literal intact: `{"max_tokens": 1024}` arrives as the
  number and not as `"1024"`, which is the difference between an API accepting
  a request and rejecting it. Nested lists and objects nest. Because the
  serialiser writes the body, a quote or a newline in text the user typed is
  escaped properly rather than breaking the JSON, which is what building the
  body by concatenation does the first time somebody presses the wrong key.
- `Content-Type: application/json; charset=utf-8` is set on a body that starts
  with `{` or `[`, unless the caller chose the header themselves. A string
  body is still sent exactly as written, so form-encoded and XML bodies are
  unaffected.
- `timeout=` on every `https` verb, in seconds, defaulting to 60 and capped at
  600. It replaces a fixed 10 seconds that no request to anything slow could
  survive.
- A module-level constant written by joining text -- `URL = BASE + MODEL +
  ":generate"`, which is how a URL is naturally written -- is folded into one
  literal and reaches the app. It used to produce nothing at all, and the name
  was then used in the generated Java without ever having been declared. A
  piece it cannot resolve, because the name is declared further down the file,
  is now `U2027` rather than a `cannot find symbol` from the Android build.
- `list_row.set_trailing()` and `.set_subtitle()`: a settings row
  shows three texts, so it needs three ways to change one. The slot has to
  have been declared -- pass `trailing=""` for one you intend to fill
  later -- and the lookup is guarded rather than assumed.
- `flex-grow: 1` on a stacked column child takes whatever its siblings leave,
  and `justify-content` / `align-items` place the children along and across the
  column. Together they are the empty state every assistant app opens on: the
  greeting in the middle, the composer pinned under it. A column that names
  neither still centres horizontally, which it always did.
- `label.stream(text, speed=)` and `collection.stream_item(id, field, text)`:
  text arriving a few characters at a time, the way an answer does. The rate
  lives in one table both runtimes read, so the phone and the desktop type at
  the same speed; `instant`, and a theme with `motion="none"`, put the whole
  thing there at once. The Android side is a Handler on the main looper and the
  Previewer a Tk `after` -- a few characters per tick rather than one every few
  milliseconds, because neither clock is accurate below about 10ms.
- The streaming helpers are emitted only for screens that carry the widget they
  touch. Commands come from the whole module, so a collection helper on a
  screen with no collection is a "cannot find symbol" at build time.
- `drawer(screens, labels=, icons=, header=, subtitle=)`: the navigation panel
  that slides in from the leading edge, and the last shape on the list that was
  outright impossible rather than merely unstyled. Declared once for the whole
  app the way `bottom_nav` is; each item starts the screen it names, the open
  screen stays checked, and `menu.open()` from an app bar's leading icon is
  what finally gives the hamburger something to open. Back closes the panel
  before it leaves the screen, which DrawerLayout does not do on its own.
- The compiler looks for the drawer before it reads any function body, because
  a drawer needs every screen to exist and the app bars that open it are
  written above it. Parsing strictly top to bottom would have met `menu.open()`
  before `menu` was anything and dropped it in silence.
- `list_row(text, subtitle, icon, trailing, trailing_icon, command)`: the
  settings row, and the one shape a button could never be. Its label starts at
  the leading edge with the icon beside it, it carries a second line, and it
  keeps room on the right for a value, a plan or a chevron. The text block
  takes what the icon and the trailing pieces leave, so a long label is cut
  with an ellipsis instead of pushing the chevron off the screen. Tapped like
  a button -- same `command=`, same navigation.
- `divider-color` on a container groups rows with hairlines, drawn between
  them and never at the edges (`android:showDividers="middle"`).
  `divider-width` sets the thickness and `divider-inset` starts the line past
  the icon column. Opt-in, so no container already written changes shape, and
  it works on any container rather than only ones holding rows.
- Rows stacked in a container sit flush against each other. The 6dp baseline
  gap between stacked children would have lifted every hairline off the seam
  it belongs on -- visible only once the APK was on a phone.
- `text-align: left | center | right` on labels and buttons. A button centred
  its label and nothing could move it, so three stacked rows read as three fat
  pills instead of a settings list. Written to Android as `start` / `center` /
  `end` so a right-to-left locale mirrors for free, and an aligned button pins
  its icon to the leading edge (`app:iconGravity="start"`) rather than grouping
  it with the label. `justify` is reported as `U2022` instead of half-done: it
  needs `android:justificationMode`, which arrived at API 26 while the
  generated app targets 24.
- `text-align: center` on an app bar centres its title
  (`app:titleCentered`). Android centres it in the whole toolbar and the
  Previewer does the same -- packing centred it in the gap the actions left
  over, which drifted left as soon as one appeared.
- `letter-spacing` and `line-height`, in `px`, `em` or -- for `line-height` --
  a bare multiple, the way CSS reads them. Both resolve through one shared
  module, so the em Android is handed and the pixels the Previewer measures
  come from the same arithmetic. `letter-spacing: 0px` is written out even
  though it is zero, because a MaterialButton tracks its label at ~0.089em on
  its own and silence would have left the phone spaced out while the Previewer
  sat tight.
- `font(family, regular=, bold=, italic=, bold_italic=)`: your own typeface,
  from `.ttf` or `.otf` files beside your code. The Android build copies them
  into `res/font`, writes the `<font-family>` that maps weights onto them, and
  reaches them through `app:fontFamily` -- the AppCompat attribute, because the
  framework one only learned to take a font resource at API 26 and ApkPy
  targets 24. The Previewer loads the same files into the session without
  installing anything. `Theme(font_family="Tiempos")` or
  `font-family: "Tiempos"` in CSS then reaches them, and the app bar title
  carries it too, through a generated text appearance.
- Four font slots and no more, because four is what both sides can address: Tk
  has a family plus `bold` and `italic`, Android expresses the same four as
  `fontWeight`/`fontStyle` pairs. A `medium` would render on the phone and not
  on the desktop, so it is reported as `U2024` rather than half-done. A slot
  you leave out is synthesised by both renderers alike.
- A missing font file or a web font format is reported at build time (`U2025`,
  `U2026`) and that slot is dropped. The family still ships with whatever
  survived, and a family left with nothing is never named by a layout --
  referencing a resource that was never written is an AAPT link failure, which
  is a much worse way to find out.
- `chevron_right` and `chevron_left` in the icon catalogue, with
  `navigate_next`, `navigate_before` and `disclosure` as aliases. The
  catalogue had no sideways chevron at all, and a right chevron is what tells
  a row that tapping it opens something. **62 names, 93 with aliases.**
- An app that mentions none of these generates byte-identical XML.

### Fixed

- An app bar's back arrow did nothing in the Previewer. `action("arrow_back")`
  with no `command=` of its own compiles to `finish()` on Android, so the same
  screen was one tap from leaving on a phone and a dead end on the desktop --
  a settings screen you could open and not get out of. The Previewer keeps a
  history now and the arrow walks it back, on exactly the icon name the
  generator tests for, so neither side can start answering differently.
- The Previewer had no equivalent of the system Back gesture at all, so a
  screen that draws no arrow of its own was a dead end even after the fix
  above. **Alt+Left** is that equivalent, and it follows Android's order: an
  open drawer closes first, and only then does Back leave the screen. Escape
  is deliberately left alone -- overlays bind it themselves, and a modal that
  both closed and navigated would be worse than no shortcut.
- A screen already open behind you is brought forward rather than stacked
  twice, which is what `FLAG_ACTIVITY_REORDER_TO_FRONT` does for a
  `bottom_nav`. Without it, hopping between two tabs grew the history for as
  long as you kept tapping.
- The Previewer's signal, wifi and battery symbols were the string
  `▮▮▮  ▲  ▮▮▮` -- three block characters, an arrowhead, three more --
  borrowed from whatever the system font happened to carry. At 24px that read
  as a row of dashes, and nothing in it said "battery". They are vectors now,
  on the icon catalogue's 24x24 grid and through the same antialiasing
  rasteriser every icon goes through, and they follow the app bar's palette
  the way the clock beside them always did.
- `?attr/...` in a colour position was reported as an unreadable colour. It
  is a reference to whatever the theme in force says, which is exactly right
  for a ripple, and it now passes through like `@color/...` always did.

- `var(--primary)` resolved to `#6750A4` in an app that declared a `Theme` and
  to the literal text `var(--primary)` in an app that did not, which failed the
  Android build. The generated `apkpy_theme.xml` is written from that same
  default palette either way, so the token was never wrong -- only unresolved,
  and whether it worked came down to a keyword the stylesheet has nothing to do
  with. An app that never names a theme now reads the same tokens as one that
  does. No theme stylesheet is merged into it, so nothing else about its output
  moves.
- A `type="textarea"` grew with its text on Android and never grew in the
  Previewer, so the same composer was one line on the desktop and three on the
  phone. Both now start at `rows` and stop at the same ceiling.
- A dict as the body of an `https` request compiled to an empty string. The
  request went out with nothing in it, in silence, and `body = {...}` on a line
  of its own generated no Java at all -- the name was then used without ever
  having been declared, so the build failed somewhere else entirely. The
  Previewer, which runs the Python, saw the whole dictionary: the divergence
  this compiler pays the most for.
- A list of objects became a list of strings. `[{"role": "user"}]` was written
  as `["{\"role\":\"user\"}"]`, so `{"messages": msgs}` handed the far end a
  quoted blob where an array belonged.
- An `https` body was read back with `readLine()` into a `StringBuilder`, which
  dropped every line break in the response, and both the body and the answer
  used the platform charset instead of UTF-8.
- The read timeout was 10 seconds on both sides, hard-coded. Anything that
  takes longer to answer than an ordinary endpoint -- a model, a report, a cold
  start -- died before replying, and the error that surfaced was a bare timeout
  that said nothing about why.
- The Previewer form-encoded a dict body while Android sent nothing at all, and
  disabled TLS certificate verification for every request. It now sends JSON
  like the phone does, verifies certificates by default, and only falls back to
  an unverified context when the system has no CA store -- saying so once, in
  the console, rather than quietly downgrading a request carrying an API key.
- `label.stream()` written inside a named function referred to the view by its
  local name, which only exists inside `onCreate`: a `cannot find symbol` at
  build time. It reaches the view through `findViewById` now, like every other
  setter does.
- `Theme(primary=...)` left `on_primary` at the Material baseline dark purple,
  so a filled button on any custom primary carried a label nobody could read.
  It is now derived from the primary's luminance unless you set it yourself.
- `storage.get(key, default)` used **inside** an expression -- as an argument
  rather than on a line of its own -- compiled to an empty string in silence.
  The Previewer read the stored value and the phone read nothing, which is the
  failure this compiler's own notes call class number one. It now reaches
  `_apkpyStorageGet` from both copies of the expression translator.
- `set_value()` on a `list_row` emitted `setText` on the row itself, which is a
  LinearLayout: a `cannot find symbol` at build time. It targets the row's
  label now, and `set_trailing()` / `set_subtitle()` reach the other two slots.
- The Previewer's app bar read its stylesheet for two colours and nothing
  else, so a custom typeface or size reached the title on the phone and not on
  the desktop.
- `item-background-color: #00000000` on a collection took the Previewer down
  with an `E1999` at startup. Tk has no per-widget alpha, so every colour a
  collection reads now resolves to whatever sits behind it -- which is how a
  chat turn asks to be text on the page rather than a card.
- A collection drew a scrollbar down the Previewer even with one item in it. A
  RecyclerView draws none until you drag it, so the rail is now shown only when
  there is something to scroll.

### Note on existing apps

- An app that declares `Theme(mode="dark")` still opens dark on a phone set to
  light, and the other way round: the declared mode is pinned at startup.
  Without that, `values-night/` would have made every existing app follow the
  system, which is a behaviour change nobody asked for.
- The generated XML *does* change: colours that came from tokens are now
  references. The app looks the same, and the project is easier to read and to
  edit by hand, which the generator has always aimed for.

### Verified, not changed

- A field at the bottom of a screen stays above the soft keyboard. Three
  shapes were checked on a Pixel 9 Pro (API 36) -- a plain `LinearLayout` with
  no scrolling view, a screen with an `app_bar()`, and a column with a
  composer pinned by `flex-grow` -- and Android resized the window correctly
  in all three without ApkPy declaring `windowSoftInputMode`. The attribute
  was not added: it would change the manifest of every app to no observable
  effect. What Android does, and the two things it does not promise, are in
  [Previewer versus Android](docs/preview-android.md).

### Known limits

- A collection row with a `markdown` slot renders the whole answer, but the
  Markdown it understands is the same subset the `markdown()` component
  understands: no tables and no images inside a row. A fenced block is
  monospace on a tinted background with a Copy under it, not a widget.
- Row heights in the Previewer are measured after a row is drawn, so a long
  row is estimated once before it settles into its real height. The phone has
  no such pass -- RecyclerView measures as it lays out -- which is the usual
  trade: the shape matches, the first frame may not.
- `scroll_to_end()` moves once, when it is called. It does not follow text
  that keeps arriving, so a long streamed answer still grows past the bottom
  edge after the jump. On Android a very long jump also takes longer than the
  stated duration: the RecyclerView re-aims as it goes, because it cannot know
  a row's height before laying it out.
- `https` still delivers the whole answer at once. There is no server-sent
  events reader yet, so an API that streams its reply token by token is read to
  the end before the callback fires. `label.stream()` types text that has
  already arrived; it is not the same thing.
- Every row in a collection has the same shape. The adapter has one view type,
  so a row cannot change its alignment, its surface or its width based on its
  own data. A chat where your turn is an inset bubble and the reply is
  full-width text is not expressible yet -- which is what still separates a
  thread built with ApkPy from the assistant apps it is modelled on.
- Nothing keeps the conversation for you. Sending the history back with each
  turn is your `data=` dict to build.
- An `on_response=` callback must be a named function, and it cannot see
  variables from the function that started the request -- the compiler reads
  your module rather than running it. Hand the value over through `storage`.
- Tk has no tracking and no line spacing on a label, so the Previewer shows the
  right words at the right size without the gaps between them.
  `letter-spacing` still changes where a button's label wraps and how wide it
  asks to be, and `line-height` still adds the leading above and below, so one
  line takes the height it takes on the phone. A paragraph that wraps comes out
  shorter in the Previewer, by the leading of each line after the first.
- Loading a font file into Tk is platform-specific. Windows and Linux work;
  macOS declines, falls back to the nearest system family and says so once in
  the console. The APK is unaffected.
- Text Android draws rather than your layout does not pick a custom family up
  yet: `bottom_nav` labels and `virtual_collection` rows stay on the system
  font. The app bar title does carry it.

## [1.3.2] — 2026-08-21

### Added

- One shared icon table: 60 names (88 with aliases) that the Previewer and the
  Android compiler both read, replacing two unrelated systems that agreed on
  only 29 of their 48 names. `person` used to render as a ring with a dot on
  the desktop; `skip_next` as a solid disc on the phone.
- The Previewer rasterises the shared vector with antialiasing instead of
  redrawing every icon by hand with canvas primitives Tk cannot smooth.
- `icon="assets/logo.svg"` accepts your own artwork. Read at build time and
  turned into an Android vector drawable, with `viewBox`, nested `transform=`,
  arcs and the common shape elements handled. Shapes painted in a second colour
  are cut out rather than merged, which is how designers fake a hole.
- Thirteen navigation names ship an outlined variant. `bottom_nav` fills the
  active item: a pill lights up behind the icon and the icon goes from outline
  to solid. `indicator="pill" | "line" | "none"` and `icons_active=`.
- `Theme(motion=...)`: `none`, `subtle`, `standard`, `expressive`. Four moments
  scale from one base, and both runtimes resolve every duration from the same
  module.
- CSS `transition:` on appearing and disappearing, and `press:` for touch
  feedback.
- `on_click_navigate(transition="slide" | "slide_up")`, using
  `overrideActivityTransition` on API 34+ and `overridePendingTransition`
  below, because the older call is deprecated at the generated `targetSdk`.
- Animations honour Android's *Remove animations* accessibility setting.
- Five diagnostic codes for icons: an unknown name (`U2015`, a warning with the
  closest match), a missing file, a stroke-only export, an unconvertible
  element and an unreadable file.
- `subtitle-lines` and `title-lines` on a list or collection: one line is
  still the default, and a chat message needs more than one to be readable at
  all. Both runtimes read the same two numbers.
- Composer controls in the catalogue: `mic`, `send`, `stop`, `bolt`,
  `expand_more`, `expand_less` and `content_copy` — the set a chat-style input
  bar needs.
- `text-transform: none` on a button label. Material shouts them and ApkPy
  always has, so the default is unchanged and an app that never mentions the
  property generates byte-identical XML; `none` is the opt-out a chip or a pill
  wants. `uppercase` and `none` are the two values offered, because they are
  the two Android expresses as `android:textAllCaps`; anything else is reported
  as `U2021` rather than half-done.
- `U2020` reports a colour Android cannot parse, at build time instead of as an
  `IllegalArgumentException` while the screen is created.

### Fixed

- `background-color: #00000000` on an input took the whole Previewer down with
  an `E1999` at startup. Tk has no per-widget alpha, so a transparent surface
  now resolves to whatever sits behind it — which is what transparency means on
  screen — everywhere a CSS colour can reach a Tk option.
- `border-width: 0px` drew a hairline anyway on an input with a radius, and
  focus grew it to 2px. Android emitted no `<stroke>` for the resting state but
  did for the focused one. Both sides now draw nothing, in both states.
- A variable first assigned inside an `if` branch was declared inside that
  branch in Java, so the next line could not see it. Python has no block
  scope; the app failed to compile with "cannot find symbol" after running
  fine in the Previewer.
- `merge_items([{...}])` accepted only fully literal rows. A row built from
  what the user just typed — the normal case for a chat — was dropped in
  silence, and the generated Java compiled, ran and added nothing.
- A `rich=True` list row with no image still reserved its thumbnail, which
  showed as an empty blue square on the phone and nowhere else.
- A child of a flex row asked the Previewer for the full row width instead of
  its own content width, so a row only looked right because `flex-shrink`
  squeezed it back. `flex-shrink: 0` then pushed the last controls off the
  edge. Children now measure like Android's `wrap_content`.
- A hidden child still reserved its box in a Previewer flex row, a gap the
  phone never had — `ApkpyLayout` has always skipped a `GONE` view.
- `popup_menu(anchor=...)` and `context_menu(target=...)` written as bare
  statements — the natural way to write them, since they attach to another
  component — were parsed only in their assigned form, so the menu opened in
  the Previewer and the button did nothing on the phone.
- `component.hide()` at module level set the starting state in the Previewer
  and was dropped entirely for Android, which showed every control at launch.
  It is now emitted as an instant `setVisibility`, not an animated one.
- Emptying a textarea with `set_value("")` left it blank instead of bringing
  the placeholder back; the single-line field already did the right thing, and
  `android:hint` does it by itself.
- `button(text=...)`, `label(text=...)` and `inputs(placeholder=...)` passed by
  name never reached the generated XML — the parser read only the positional
  argument, so the label or hint showed in the Previewer and came out empty on
  the phone.
- `#111` reached `Color.parseColor`, which accepts only `#RRGGBB` and
  `#AARRGGBB`, and closed the app the moment it opened. The `#RGB` and `#ARGB`
  shorthands are expanded; four digits are the shorthand of eight, matching the
  `#AARRGGBB` convention the rest of the project uses.

- `files.pick(on_result=, types=)` picks any file type through the Storage
  Access Framework and reports `(success, path, name, size, mime)` — five
  strings in both runtimes. No storage permission is declared.
- `upload_button(...)` picks and uploads in a single call. It is expanded at
  parse time into an ordinary button plus two callbacks, so the generated Java
  is identical to the hand-written form; a regression test asserts that.
- `types=` accepts extensions, complete MIME types and families, resolved in
  Python at build time so the two runtimes cannot disagree.
- Diagnostics expanded to 64 codes across eight families, each with a
  "Why this happened" explanation and a documentation link. 166 of the 167
  messages the library raises are matched by a specific rule.
- Gradle failures are diagnosed: eight recognised signatures, and an
  unrecognised failure still reports Gradle's own reason and the project path.
- Compiler diagnostics point at the line in `writehere.py` instead of ApkPy's
  own source, and never report a location inside the library.
- A search filter that cannot become a `TextWatcher` is reported as `C4002`
  instead of a one-line note; a background job body that raises is reported
  with the job name, attempt number and payload keys.

### Added

- `background_job()` declares persistent work that survives backgrounding,
  network loss, process death and a reboot. Android generates a WorkManager
  `OneTimeWorkRequest` pipeline; the Previewer runs the same contract against
  an on-disk queue in `~/.apkpy/jobs`.
- Constraints `requires_network`, `requires_unmetered`, `requires_charging`
  and `requires_battery_not_low`, generated as an `androidx.work.Constraints`
  object.
- Automatic retries with `retry="exponential"` or `"linear"` and
  `retry_seconds=`, generated as `setBackoffCriteria` with WorkManager's
  ten-second floor.
- Unique work through `unique=True` and `on_conflict="append" | "keep" |
  "replace"`, generated as `ExistingWorkPolicy`. `"append"` maps to
  `APPEND_OR_REPLACE` so a queue is not silently cancelled after one failure.
- `job.enqueue(data)`, `job.cancel()` and `job.observe(on_change=, screen=)`.
- Inside the job body: `job.input(key)`, `job.attempt()`,
  `job.progress(percent, message)`, `job.retry()` and `job.fail()`.
- One JSON status document — `state`, `progress`, `message`, `pending`,
  `running`, `attempt` — delivered identically by both runtimes.
- The English **Offline Outbox** demonstration in `playground/writehere.py`,
  covering queueing, offline hold, drain on reconnection, restart recovery,
  a deliberate failure with backoff and queue cancellation.

### Android and Previewer

- Conditional `ApkpyJobs.java` runtime with one `enqueue_<job>` entry point
  per declared job, plus `cancel` and a `status` collector that folds a list of
  `WorkInfo` into the JSON document.
- One generated `<Job>JobWorker.java` per job, reusing the existing worker
  generator rather than duplicating it, extended with `getInputData()`,
  `setProgressAsync()` and the attempt result.
- `observe()` attaches to `getWorkInfosByTagLiveData(...)`, so progress
  survives rotation and resumes with the Activity without polling.
- Job declarations are collected in a pass that runs before the module is
  visited. Python requires the run function to be written above the
  declaration, and without that pass its job calls were dropped in silence.
- The `androidx.work:work-runtime` dependency, the runtime class and the
  worker are emitted only when a job is declared.
- Worker helpers `_jobInput` and `_jobProgress`, and the attempt-result field,
  are emitted only when the job body uses them.

### Fixed

- `animation-duration: 0.5s` was parsed as 0.5 ms in the Previewer and 5 ms on
  Android; neither understood seconds. The default duration also differed,
  600 ms against 1000 ms, and the two easing curves were different.
- A `@keyframes` fade interpolated towards a hard-coded `#ffffff`, so every
  fade in a dark app flashed white.
- `scale` and `margin-left` animated on Android and did nothing in the
  Previewer.
- `inputs.set_value("")` cleared the field without restoring its placeholder,
  so a form that clears itself after submitting went blank and stayed blank.
- CSS `placeholder-color` was honoured on Android and ignored by the Previewer.
- Rounded containers re-measured after the first paint, so a freshly rendered
  screen showed clipped cards for about 250 ms before settling.
- The bottom bar's active pill used the same colour as the icon behind it,
  hiding the icon on a device.
- `render_diagnostic` printed an empty *Technical details* heading.
- `db.text(choices=[...])` generated `new JSONArray(String)`, whose checked
  `JSONException` the field initialiser neither caught nor declared, so any
  model using `choices=` failed the build with *unreported exception
  JSONException*.
- Upload progress delivered integers in the Previewer and strings on Android,
  so `"Uploading " + percent + "%"` worked on the phone and raised `TypeError`
  on the desktop. Both runtimes now deliver strings.
- Upload lambdas could shadow a parameter of the enclosing method, producing
  Java that did not compile.
- Diagnostic output is normalised to ASCII for legacy Windows code pages.
- A `return` inside a generated `Worker` emitted `return;` from `doWork()`,
  which returns `Result` and therefore did not compile. Early returns now
  produce the correct result. This also affected `service.every` workers and
  is covered by a regression test.
- Previewer connectivity for `requires_network` is decided by a route check
  combined with a reachability check on port 443. A reachability check alone
  reported offline on machines that block outbound port 53, and a route check
  alone reported online with the Wi-Fi switched off on machines with Hyper-V,
  WSL, VirtualBox or VPN adapters.
- Previewer job status values are strings, matching the generated `_jsonGet`
  accessor. Numeric keys previously returned integers, so string concatenation
  worked on Android and raised `TypeError` on the desktop.
- Observer notifications raised on a worker thread are delivered through an
  interface-thread pump. Scheduling them directly stalled the worker and left
  the queue frozen.

### Documentation

- New [Background jobs and offline queue](https://repo-apkpy.pages.dev/background-jobs/)
  page and [Version 1.3.2](https://repo-apkpy.pages.dev/version-1.3.2/) notes.

---

## [1.3.1] — 2026-08-20

### Added

- Friendly diagnostics shared by Previewer callbacks, application startup,
  Data Core, the Android compiler and build-toolchain checks. Reports include
  stable codes, the relevant application line, the original cause and an
  ordered correction, with `APKPY_DEBUG=1` retaining the full traceback.
- `apkpy preview` and `apkpy preview --debug` for startup and syntax failures
  that occur before the normal Previewer lifecycle begins.
- Controlled one-to-many `db.relation()` declarations with validated parent
  keys, foreign-key types, unique aliases and `restrict`, `cascade` or
  `set_null` delete behavior.
- `relations=[...]` in `db.schema()` and real SQLite foreign-key constraints
  with foreign-key enforcement enabled in Previewer and Android.
- `include=[...]` for typed `find()` and `get()`, loading each relation with
  one batched bound query instead of one query per record.
- Lifecycle-safe `model.observe()` queries with `refresh()`,
  `update_query()` and `close()`.
- The English **Knowledge Vault Live** demo with folders, related notes,
  dynamic observed search, CRUD, favorites, cascade and live update counts.

### Android and Previewer

- Added a conditional shared `ApkpyDataInvalidationTracker` and
  `ApkpyQuerySubscription` runtime.
- Successful writes invalidate only affected model dependencies after commit;
  transactions publish one combined invalidation and rollback publishes none.
- In-flight invalidations are coalesced, stale query generations are ignored
  and repeated visible snapshots are deduplicated.
- Activity observers resume, pause and close with their owning screen.
- Projects without relations or observation do not receive the corresponding
  metadata, hydration or subscription code.

### Validation

- Added relation validation, foreign-key policy, include hydration, observer
  lifecycle, dynamic-query and rollback tests.
- 21 focused Data Core/Reactive Data tests, 8 focused diagnostic tests and 167
  transpiler checks pass.
- Compiled the generated Knowledge Vault Live Java with Gradle; this caught
  and fixed SQL-identifier escaping and cross-screen observer-handle errors.

### Documentation

- Added the complete Reactive Data contract, migration guidance, lifecycle
  behavior, deliberate limits and a runnable Knowledge Vault Live example.
- Documented the project's current proprietary status and the commitment to
  release the core source as open source if active development is permanently
  discontinued.

### Deliberate limits

- Only one-to-many and one-level eager includes are supported. This version
  does not add many-to-many, recursive relations, lazy loading, polling,
  offline synchronization or external SQLite change detection.

---

## [1.3.0] — 2026-08-17

### Added

- Declarative `db.model()` and `db.schema()` definitions with typed integer,
  real, text, boolean, datetime, JSON and blob fields.
- Required/optional/default values, keys, uniqueness, numeric and text bounds,
  choices, and simple or composite indexes.
- Asynchronous `insert`, `insert_many`, `get`, `find`, `update`, `delete` and
  `count`, with callbacks delivered on the interface thread.
- Parameterized comparisons, text matching, null checks, logical groups,
  ordering and `limit`/`offset` pagination.
- Atomic `db.transaction()` operations and optimized prepared batch insertion.
- Explicit migration operations, schema hash/version metadata, downgrade
  refusal and private backup/restore for destructive migration paths.
- The English two-screen **Knowledge Vault** application covering indexed
  search, filters, paging, CRUD, batch work, errors and a v1-to-v2 migration.

### Android and Previewer

- Android generation emits `ApkpyDatabase.java`, one shared single-threaded
  data executor and one repository per model.
- Generated repositories use `SQLiteStatement`, bound arguments and
  main-thread callbacks; they never execute queries on the UI thread.
- The Previewer uses Python `sqlite3` and a single ordered worker with the same
  validation and migration contract.
- Data Core files are conditional; applications without `db.model()` receive
  no repository, executor, metadata or migration output.
- The previous `db.execute`, `db.query`, `begin`, `commit` and `rollback` API
  remains compatible.

### Validation

- Added focused tests for declarations, CRUD, JSON, order, pagination,
  compound indexes, atomic batches and transaction rollback.
- Verified v1-to-v2 preservation, missing paths, schema hash mismatches,
  downgrade refusal and restore after a failed destructive migration.
- Verified existing feed, rich-content and Gradle-generation tests and built
  the generated Knowledge Vault Android project successfully.
- Added the reproducible Benchmark Notes comparison with four application
  sources, transparent line counts, raw device samples and APK hashes. The
  benchmark is documented as a scoped debug-app measurement, not a universal
  framework ranking.

### Deliberate limits

- Relations, observable queries, offline-first synchronization, conflict
  resolution and persistent background jobs are not included in 1.3.0.

---

## [1.2.2] — Unreleased

### Added

- `prepend_items(items)` for stable top insertion without moving the visible
  record.
- `update_item(item_id, changes, key="id", optimistic=False)` and
  `remove_item(item_id, key="id", optimistic=False)` for keyed record changes.
- `merge_items(items, key="id")` for in-place live reconciliation without
  duplicate stable IDs.
- `commit(mutation_id=None)` and `rollback(mutation_id=None)` with first-state
  snapshots for optimistic transactions.

### Android and Previewer

- Generated RecyclerViews use targeted range/change/remove notifications.
- Multi-record merges and rollbacks dispatch a native `DiffUtil` result.
- Mutation helpers are conditionally emitted only when the new API is used.
- The Previewer preserves virtual scroll position and follows the same keyed
  transaction rules.

### Validation

- Added runtime tests for keyed merge, removal, commit, rollback and repeated
  changes in one optimistic transaction.
- Added generated-source tests for targeted adapter notifications,
  conditional `DiffUtil` output and optimistic history.

---

## [1.2.1] — Unreleased

### Added

- **Incremental virtual collections**: `virtual_collection()` now accepts
  `on_end_reached`, `on_refresh` and `prefetch`.
- **Efficient page insertion**: `append_items(items, has_more=True)` preserves
  the current records and scroll position while Android uses
  `notifyItemRangeInserted()`.
- **Explicit request completion**: `finish_load()` releases the loading latch
  after an empty response or recoverable error, and `refresh()` starts the same
  guarded callback as the top pull gesture.
- **End-of-results state**: `has_more=False` prevents new page requests until a
  refresh begins a new pagination generation.
- **Native Android refresh**: generated projects use
  `RecyclerView.OnScrollListener`; `SwipeRefreshLayout 1.2.0` is emitted only
  for collections with `on_refresh`.
- **Production Feeds demo**: the English `playground/writehere.py` example
  includes a list, grid, prefetch, refresh, deliberate failure, retry and
  no-more-results path.

### Changed

- The generated Android toolchain baseline is now AGP 8.6.1, Gradle 8.7 and
  compile SDK 35 so the stable SwipeRefreshLayout 1.2.0 artifact can compile.
  Projects without refresh keep their dependency graph free of
  SwipeRefreshLayout.

### Validation

- Added focused feed-state, generated-code and conditional-dependency tests.
- Verified the generated Java contains the native listener, duplicate-request
  latch and range insertion.
- Built the generated Android demo with Gradle successfully.

---

## [1.2.0] — 2026-07-27

### Added and documented

- **Native audio capability baseline**: consolidated the music features that
  already exist in ApkPy so evaluations do not mistake the player for a
  foreground-only demo. The current Android output includes a foreground media
  service, `MediaSession`, notification and lock-screen metadata and transport
  controls, audio-focus handling, queue navigation, shuffle/repeat, seeking,
  synchronized full-player bindings, a persistent mini-player, favourites,
  editable playlists and explicit offline downloads.
- **Player reliability behaviour**: documented guarded duration/position
  polling while `MediaPlayer` is unprepared, buffering state, one controlled
  retry of the same source after a preparation failure and the rule that an
  error must not trigger a skip storm through the queue.
- **Clear support boundary**: documented that image/artwork caching and explicit
  offline file downloads exist, while transparent audio caching, adaptive
  quality selection, guaranteed gapless playback, crossfade, DRM and resumable
  downloads with progress do not yet exist. Stream bitrate and quality are
  determined by the supplied source; ApkPy does not transcode audio.
- **New 1.2.0 release guide**: `RELEASE_1.2.0.md` begins with a complete
  native-player example and an implementation-oriented capability matrix.
- **Native documents without a WebView**: added `rich_text()` for exact inline
  spans, `markdown()` for headings, emphasis, links, code, quotes, lists,
  checkboxes and dividers, and `tree_view()` for recursive expandable data.
  Android emits selectable `Spannable` text and a `RecyclerView` containing
  only visible hierarchy rows; plain projects do not ship these helpers.
- **Runnable structured-content applications**:
  `examples/16_knowledge_base.py` combines rich spans, Markdown and a workspace
  hierarchy, while `examples/17_discussion_tree.py` demonstrates a formatted
  article and nested social discussion.

---

## [1.1.0] — 2026-07-16

### Added
- **1/9 — Global themes and reusable design tokens**: `Theme(...)` now supplies light/dark mode, primary and secondary colours, background, surface, text, border, error/success colours, radius, spacing and typography to the Previewer and generated Android resources. CSS can reuse the normalized values through `var(--primary)`, `var(--surface)`, `var(--text)`, and the other theme tokens. The cascade is deterministic: Theme → component selector → semantic variant → component ID.
- **2/9 — Material button variants and vector icons**: `button(..., variant=...)` supports `filled`, `outlined`, `tonal`, `text`, `danger` and `icon`. `icon=` uses matching font-independent geometry in the Previewer and generated Android vector drawables, avoiding missing emoji glyphs. Variant selectors such as `button:outlined` remain customizable through CSS.
- **3/9 — Responsive layouts**: `responsive(mobile=..., tablet=..., landscape=..., breakpoint=...)`, `row(...)` and `column(...)` arrange one component tree for each viewport. Builds generate native `layout`, `layout-land`, `layout-sw600dp` and `layout-sw600dp-land` resources. Preview presets include phones, tablets, landscape and a freely resizable responsive window.
- **4/9 — Advanced flex, grid and layered composition**: added `flex-wrap`, grow/shrink/basis, `align-self`, fractional grid tracks, `repeat()`, row/column spans, aspect ratios, absolute offsets and z-index. Simple screens remain ordinary native layouts; the optimized `ApkpyLayout` helper is emitted only for projects that require advanced geometry.
- **5/9 — Material cards and semantic surfaces**: `card()` supports `elevated`, `filled` and `outlined` surfaces, a ready-made title/subtitle/image/content/actions form, or arbitrary child composition. `card_action()` creates compact card actions, and semantic label variants include title, subtitle, body and overline. Android uses native `MaterialCardView`.
- **6/9 — Native app bars and collapsible media headers**: `app_bar()`, `sliver_app_bar()` and `action()` generate fixed Material toolbars, menus and collapsible image headers without placing toolbar Views in scrollable content. Android output uses `MaterialToolbar`, `AppBarLayout` and `CollapsingToolbarLayout`.
- **7/9 — Overlays, menus and pickers**: added `bottom_sheet`, `modal`, `menu`/`popup_menu`, `context_menu`, `snackbar`, `tooltip`, `date_picker` and `time_picker`. Definitions are lightweight until opened, expose callbacks and programmatic close methods, and map to native Material dialogs/menus on Android.
- **8/9 — Content states**: `skeleton`, `empty_state` and `error_state` share a screen region and switch through `show()`/`hide()` without rebuilding the component tree. Skeleton variants include music card, list, card and text. Animation helpers are generated only for Activities that use them.
- **9/9 — Smart images and avatars**: `image()` and `avatar()` now support local placeholders, network fallbacks, bounded caching, fade-in, aspect ratio, blur, tint and runtime source changes. Avatars add a circular crop and online/away/busy/offline badge. Network work runs away from the UI thread and stale responses are ignored.
- **Four English showcase applications**: Lumen (finance), Onda (wellbeing), Northline (travel) and Afterglow (music) demonstrate distinct visual systems rather than template recolours. Together they generate sixteen Android Activities.
- **Complete 1.1.0 release guide**: `RELEASE_1.1.0.md` documents all nine plan items with executable Python/CSS examples, explains native output and shows how the design system works with SQLite, REST, encryption and background audio.

### Fixed
- Kept Material button height, padding, corner radius, border, colour, pressed state and narrow-screen wrapping consistent between Previewer and Android.
- Replaced fragile emoji/font icons with Previewer vector geometry and generated Android vector drawables, including bottom navigation, toolbars and buttons.
- Prevented card and toolbar Activities from crashing during layout inflation by generating `Theme.App` from `Theme.MaterialComponents.DayNight.NoActionBar`, mapping the ApkPy palette to Material attributes and applying the theme in `AndroidManifest.xml`.
- Preserved Previewer input state while rebuilding bottom navigation and made tab changes persist correctly across separate Android Activities.
- Matched rounded corners for cards, containers, inputs, selects and switches across both renderers.
- Fixed the Previewer bottom sheet replacing the entire window with a black screen; the sheet now appears above the existing content.
- Reworked Previewer toasts into a compact Material capsule with vector status icon, responsive width and non-blocking placement.
- Corrected image crop, avatar clipping, aspect ratio, blur/tint handling and fallback behaviour, including the Android colour filter path that previously produced a solid purple block.
- Matched Android text wrapping for constrained buttons instead of keeping labels on one overflowing Previewer line.
- Kept generated Material helpers conditional so ordinary projects do not gain unused layout engines, image loaders, overlay helpers or skeleton animation code.

### Validation
- Installed the 1.1.0 wheel into clean Python environments and verified that `apkpy_lib` was loaded from `site-packages` rather than the development checkout.
- Generated and compiled four complete projects with JDK 21, Gradle 8.6 and Android SDK 34.
- Parsed 108 generated XML files, inspected 24 Java files and verified the expected Material theme, application ids, launcher Activities and version metadata.
- Installed the four APKs on a Pixel 9 Android emulator and opened all 16 Activities through their real bottom navigation without an AndroidRuntime fatal exception.
- Passed the complete transpiler suite: 146 tests passed, 0 failed.

---

## [1.0.0] — 2026-06-09

### Added
- **Native audio and background playback — `audio`**: build music and podcast experiences with `audio.play`, `pause`, `resume`, `stop`, `seek`, and `play_background`. Background playback uses an Android foreground `Service` + `MediaSession`, continues outside the Activity, publishes title/artist/artwork and transport controls to the notification and lock screen, and handles audio focus natively.
- **Playback queues and synchronized player UI**: `audio.play_playlist(sources, titles=..., artists=..., arts=..., start=...)` creates a queue with `next()`, `previous()`, `shuffle()` and `repeat()`. `audio.now_playing(progress=..., time=..., cover=..., title=..., artist=...)` binds normal ApkPy components to the active track and enables seeking; `audio.controls(...)` keeps ordinary buttons synchronized with playback state.
- **Persistent `mini_player(open=...)`**: add a now-playing bar above `bottom_nav` across the app. It follows the foreground media service and opens the chosen full-player screen when tapped.
- **Music favourites and playlists**: `audio.like_button`, `audio.liked_list`, `audio.add_to_playlist`, `audio.play_saved_playlist`, `audio.playlists_list`, `audio.edit_playlist`, `audio.playlist_editor`, `audio.remove_from_playlist`, and `audio.delete_playlist` provide persistent favourites and user-created playlists without requiring an app-specific database schema.
- **Rich media collections — `list_view(..., rich=True)`, `carousel`, and `grid`**: render native cards with remote artwork, title, subtitle and an optional `src` payload. Rich lists generate custom Android rows, carousels generate horizontal shelves, and grids generate an N-column `GridLayout`. The complete item is delivered to `on_click`; `set_items(..., image="field")` maps dynamic API/database artwork into rich rows.
- **Private file downloads — `files`**: `files.download(url, name, on_result=...)`, `files.exists(name)`, `files.path(name)`, and `files.delete(name)` support offline media and other downloaded assets. Downloads are asynchronous and stored in the Android app-private files directory.
- **OAuth 2.0 + PKCE — `auth`**: browser-based sign-in with provider defaults for Google, Spotify and GitHub or custom OAuth endpoints. `auth.login`, `is_logged_in`, `token`, `user`, and `logout` cover authorization, token persistence and normalized profile data. Android uses a generated deep-link Activity; the Previewer uses a localhost loopback redirect. No client secret is embedded in the APK.
- **SQLite transactions — `db.begin()`, `db.commit()`, `db.rollback()`**: group several `db.execute()` calls into one atomic, all-or-nothing unit. Everything between `db.begin()` and `db.commit()` is written to disk together; `db.rollback()` undoes everything since `db.begin()`, leaving the database exactly as it was. The classic use case is a transfer (debit one account *and* credit another — never just one), but it's also the right tool for any multi-row write that must not be left half-done, and it's much faster than committing each insert separately (SQLite flushes to disk once). Inside a transaction every `db.execute()`/`db.query()` shares a single connection, so atomicity is real. On Android this transpiles to native `SQLiteDatabase.beginTransaction()` → `setTransactionSuccessful()` → `endTransaction()`; a `rollback()` ends the transaction without marking it successful. In the Hot Previewer it uses a shared Python `sqlite3` connection with `commit()`/`rollback()`. Works in callbacks, at module level (`onCreate`), and in background `service` workers.
- **`db.last_insert_id()`**: returns the `rowid` (auto-increment id) of the row just inserted with `db.execute(...)`, with no extra `SELECT`. Use it right after an `INSERT` to learn the id the database generated (e.g. to reference the new row, or feed it as a `?` parameter to the next query). Works in any expression — f-strings, `set_value()`, query params. In the Hot Previewer it returns Python's `cursor.lastrowid`; on Android it transpiles to `SELECT last_insert_rowid()` on the same connection, giving the same value on both platforms. New example shipped in `writehere.py`: an atomic bank-transfer demo (RESET / TRANSFER / ROLLBACK) that shows balances staying consistent and the rolled-back movement never being persisted.
- **`for` loops — real Python iteration compiled to native Java**: plain `for` loops now work on Android. Three forms: `for x in ["a", "b"]:` (list literals and list variables), `for i in range(n):` (also `range(a, b)`), and `for row in rows:` where `rows` is the JSON returned by `db.query()` or an `https` response — `row["column"]` reads each field (a real dict in the Hot Previewer; safe `_jsonGet` access in the generated Java). Loops work inside callbacks, at module level (they run in `onCreate`), nested, and combined with `if`/`else`. `break` and `continue` are supported (they compile to native Java `break;`/`continue;`). Non-array/invalid JSON makes the loop run zero times on both platforms instead of crashing. Not yet supported: iterating dicts.
- **`crypto` — password hashing and encryption built in**: Protect sensitive data stored via `storage` (SharedPreferences) or `db` (SQLite) — both are readable by anyone who decompiles the APK or steals the files. No `hashlib`/crypto imports needed — the module is built into ApkPy, with zero external dependencies and no new permissions.
  - `crypto.hash_password(password, algo="sha256", iterations=200000)`: salted **PBKDF2** hash (`"pbkdf2-algo$iterations$salt$hash"`). Key stretching makes every brute-force guess cost 200,000 hashes instead of 1 — GPU cracking becomes ~200,000× slower. `crypto.verify_password(password, stored)` checks it with a constant-time comparison and returns a real boolean (safe in `if ok:`); it also accepts the legacy single-SHA format. On Android, PBKDF2 is generated as a manual `javax.crypto.Mac` loop (works on minSdk 24, bit-for-bit identical to Python's `hashlib.pbkdf2_hmac` — a hash created in the Previewer verifies on Android and vice-versa). `hash_password` works inside any expression (`storage.set(...)`, `db.execute(...)`, assignments, f-strings).
  - `crypto.encrypt(text)` / `crypto.decrypt(stored)`: two-way encryption for data you need to read back (notes, tokens, db fields). On Android, **AES-256-GCM with the key in the Android Keystore** — hardware-backed and non-extractable, even with root; decompiling the APK reveals no key. In the Hot Previewer, an equivalent authenticated stream cipher with a local device-key file. Values are per-device by design: a stolen database cannot be decrypted elsewhere. `decrypt` returns `""` for tampered, malformed or foreign-device values.
- **Automatic storage encryption**: `storage.set()` now encrypts every value before it touches the disk and `storage.get()` decrypts transparently — no code changes needed. The SharedPreferences XML (Android) / `apkpy_storage.json` (Previewer) only ever contains `enc1$…` ciphertext. Values saved in plain text by older versions are still read normally (automatic fallback).
- **Parameterized SQL queries — SQL injection protection**: `db.execute(sql, [values])` and `db.query(sql, [values])` now accept an optional list of parameters that fills the `?` placeholders with safe binding (also accepted as `params=[...]`). The values are bound by the SQLite engine itself instead of being concatenated into the SQL string — making SQL injection impossible and fixing queries that broke on apostrophes (`O'Brien`, `don't`). Works identically in the Hot Previewer (Python `sqlite3` placeholders) and on Android (`SQLiteDatabase.execSQL(sql, args)` / `rawQuery(sql, args)`). Calls without parameters keep working unchanged.
- **Full REST client — `https.put`, `https.patch`, `https.delete`**: the `https` API now covers all five HTTP methods, enabling full CRUD against any REST backend (Supabase, Firebase, Django, FastAPI...). `put`/`patch` take a body like `post`; `delete` takes none, like `get`. On a 4xx/5xx response the callback now receives the server's **error body** (instead of just an error message), in both environments. PATCH on Android falls back to `POST` + `X-HTTP-Method-Override: PATCH` (Android's `HttpURLConnection` doesn't accept PATCH natively); the Hot Previewer sends native PATCH. Works in callbacks and in background `service` workers. New example: `apkpy examples` -> [10] REST Client / `examples/13_rest_client.py`.
- **`set_items` accepts JSON — feed a `list_view` straight from SQLite or an API**: `my_list.set_items(json_rows, title="field", subtitle="field")` takes the JSON string returned by `db.query()` (or an `https` response body) and renders every row, mapping the chosen fields to the item's title and subtitle. Plain-value arrays also work; invalid JSON yields an empty list instead of crashing. Plain Python lists keep working as before. Also new: module-level calls to your own functions (e.g. `refresh()` at the bottom of the file) now compile into `onCreate`, so initial data loads when the app starts. Closes the data->UI loop (fetch rows -> show list -> tap -> detail). New example: `apkpy examples` -> [11] DB Notes List / `examples/14_db_notes_list.py`.
- **`spinner(id=..., screen=..., visible=True)`**: Native circular loading indicator — ideal for showing while `https.get()`, `db.query()`, or background work is in progress. Toggle it with `.show()` / `.hide()`. On Android, compiles to an indeterminate `ProgressBar` (color via CSS `color` → `indeterminateTint`; size via `width`/`height`); `.show()`/`.hide()` compile to `setVisibility(View.VISIBLE / View.GONE)`. Pass `visible=False` to start hidden. In the Hot Previewer, renders an animated rotating arc on a Canvas that starts/stops with `.show()`/`.hide()`.
- **`location.get_current(on_result=callback)`**: Read the device's GPS position. The callback receives `(success, lat, lng, city)` — latitude and longitude as strings, plus the resolved city name via reverse geocoding. On Android, compiles to `LocationManager.getLastKnownLocation()` (GPS, falling back to network) followed by `android.location.Geocoder` on a background thread; `ACCESS_FINE_LOCATION` and `INTERNET` are declared automatically and location is requested at runtime. In the Hot Previewer, a dialog asks for coordinates to simulate (defaults to Lisbon) and resolves the city via OpenStreetMap (Nominatim) in a background thread. Same Python code in both environments.
- **Remote images — `image("https://...")`**: `image()` now accepts a full URL. ApkPy detects the `http://` / `https://` prefix and loads the image at runtime in a background thread, so the UI never freezes. On Android, compiles to a background `Thread` + `HttpURLConnection` + `BitmapFactory.decodeStream(...)` → `setImageBitmap(...)` on the UI thread (the `INTERNET` permission is declared automatically; no Glide/Picasso dependency). In the Hot Previewer, the image is downloaded with `urllib` and a "loading…" placeholder shows until it arrives. All the same CSS (`width`, `height`, `border-radius`, `object-fit`, `opacity`, `box-shadow`, animations) applies to remote images.
- **`on_click_navigate(screen, data={})`**: Pass data when navigating between screens. Call `on_click_navigate(target, data={"key": value})` from a button command lambda or a `list_view` `on_click` lambda. On Android, compiles to `Intent.putExtra("key", String.valueOf(value))` + `startActivity(intent)`. In the Hot Previewer, stores the values in `screen._params` before rendering the screen.
- **`screen.get_param(key, default="")`**: Read a value that was passed via `data=`. On Android, compiles to `getIntent().getStringExtra("key")` (with a null-check ternary when a default is provided). In the Hot Previewer, reads from `screen._params`.
- **Module-level `set_value` for screen load**: Calling `lbl.set_value(screen.get_param("key"))` at module level (outside any function) causes the compiler to generate `setText(getIntent().getStringExtra("key"))` in the correct Activity's `onCreate` — so labels are populated automatically when the screen opens.
- **`bottom_nav(screens, labels=[], icons=[])`**: Native bottom navigation bar that links multiple screens. Pass a list of `Screen` objects, optional tab labels, and optional icon names (`"home"`, `"person"`, `"settings"`, `"search"`, `"list"`, `"add"`, `"star"`, `"bell"`, `"chart"`, `"message"`, `"heart"`, `"camera"`, `"info"`, `"circle"`). On Android, compiles to a `BottomNavigationView` with a `RelativeLayout` wrapper — each tab starts the corresponding Activity with `FLAG_ACTIVITY_REORDER_TO_FRONT` (no re-creation, no animation flash). Vector drawables and menu XML are auto-generated — no icon font or image assets needed. Bar background is `#1E293B`; active icon/label is white, inactive is grey; all tabs always visible (`labelVisibilityMode="labeled"`). Each Activity overrides `onResume()` with a guard flag to restore the correct selected tab on return. In the Hot Previewer, renders a styled dark bottom bar with an active-tab indicator line and label highlight; clicking any tab navigates instantly.
- **`Screen(scroll=True)`**: Makes the entire screen vertically scrollable. All components — labels, inputs, buttons, and lists — scroll together as a single page. In the Hot Previewer, the screen becomes a scrollable canvas; scroll with the mouse wheel from anywhere (no need to hover a specific widget). On Android, compiles to a `NestedScrollView` wrapping a `LinearLayout` with `fillViewport="true"`. The scrollbar is intentionally hidden in the Previewer to match Android's default behaviour.
- **`list_view(items, id=..., screen=..., on_click=...)`**: Native list component with full cross-platform support. Accepts a list of strings or dicts with `"title"` and `"subtitle"` keys. In the Hot Previewer, renders as a styled scrollable canvas with title + subtitle rows and mouse-wheel scroll support. On Android, compiles to a native `ListView` backed by an `ArrayAdapter` (when `scroll=False`) or to `TextViews` inside a `LinearLayout` container (when `scroll=True` — avoids nested scroll conflict). CSS properties `color`, `background-color`, `border-color`, and `height` are all applied. Items can be updated at runtime with `list_view_var.set_items(new_list)`.
- **`list_view` lambda `on_click`**: `on_click` callbacks can now be written as inline lambdas — `on_click=lambda item: toast(item["title"] + ": " + item["subtitle"])`. The lambda is compiled to a `pythonCallback_*` method on Android. `item["title"]` and `item["subtitle"]` correctly extract their respective parts from the stored string by splitting on the ` — ` separator, matching the Python preview exactly.
- **Variable reference in `list_view` items**: Passing a module-level list variable as items (`list_view(my_items, ...)`) is now fully resolved at compile time — the static items from that variable are correctly emitted as `lst_items.add(...)` calls in `onCreate`, instead of producing an empty list.

### Fixed
- Fixed the app crashing on launch when a `db.query()` referenced a column or table that doesn't exist (e.g. after reinstalling a demo that left an older table with a different schema in `apkpy_app.db`). The generated `_sqliteQuery` helper compiled the SQL outside its try/catch, so an invalid query threw `SQLiteException` instead of failing gracefully. The whole query now runs inside the try/catch and returns an empty result (`[]`) on error — the app keeps running and the error is logged to Logcat.
- Fixed a Java compilation error (`cannot find symbol`) when a function used `component.get_value()` on a component that belongs to a different screen. Callback methods are emitted into every Activity; on screens that don't own the component, the variable assignment was silently dropped while later uses of the variable remained. The variable is now declared as an empty string on those screens (the callback is never invoked there).
- Fixed `list_view` rendering as a large white box on Android when no `background-color` or `height` was set. The list now defaults to a transparent background (inheriting the screen, matching the Previewer) instead of white, and to `wrap_content` height (sizing to its items) instead of a fixed 300dp — eliminating the empty white area below the items.
- Fixed `label` alignment parity between the Hot Previewer and Android. On screens without `display: flex`, labels were centered on Android but left-aligned in the Previewer; they are now left-aligned (with a 16dp indent) on both. Labels on a `display: flex` screen stay centered.
- Fixed components appearing "glued together" / overlapping on Android when no CSS `gap` was set. The Hot Previewer always renders a few pixels of breathing room between stacked components, but the Android generator only added spacing when a `gap` was explicitly defined — so on screens without `gap`, buttons and labels were rendered with zero margin and could overlap. Vertically-stacked siblings now get a 6dp baseline `margin-top` when no `gap` is set (the `gap` value still takes precedence when present), matching the Previewer's spacing.
- Fixed the loading `spinner` jumping to the bottom of the screen in the Hot Previewer after a `.hide()` / `.show()` cycle. Root cause: re-showing re-packed the spinner's container, which Tkinter appends at the end of the parent's layout order. The container is now packed once in its correct position and `.show()` / `.hide()` only toggle the inner canvas, so the spinner always reappears exactly where it was declared (matching Android).
- Fixed `bottom_nav` tab bar appearing white on Android — added `android:background="#1E293B"` and a `res/color/nav_item_color.xml` color-state-list so active icons/labels are white and inactive are grey.
- Fixed `bottom_nav` tabs other than the selected one appearing to disappear or shrink on Android — added `app:labelVisibilityMode="labeled"` to keep all tabs the same size at all times (Material Design's default `auto` mode hides labels for non-selected items with 3+ tabs).
- Fixed `bottom_nav` requiring two taps to navigate: the first tap briefly showed the target screen then reverted. Root cause: when an Activity came back to the foreground the `BottomNavigationView` still showed the previously-selected (wrong) tab; tapping the same tab again triggered the correct navigation. Fix: each Activity now overrides `onResume()` to restore the correct selected tab, guarded by a `_navReady` boolean flag so the `setOnItemSelectedListener` does not accidentally trigger a new navigation during the restore.
- Fixed `bottom_nav` not placing `res/menu/bottom_nav_menu.xml` and `res/color/nav_item_color.xml` in the correct folders when running `apkpy build` — the build command now creates `app/src/main/res/menu/` and `app/src/main/res/color/` automatically.
- Fixed `list_view` inside a scrollable screen not scrolling on Android. The previous `ListView`-inside-`NestedScrollView` approach is fundamentally broken on Android (the inner `ListView` intercepts all touch events). The fix replaces `ListView` with a `LinearLayout` container whose items are added as `TextView`s at runtime — an `updateXxxList()` helper method is generated for this. This is the same approach recommended by Google for list-in-scroll layouts.
- Fixed `inputs(type="range")` (`SeekBar`) generating `setText()` in `set_value()` and `getText()` in `get_value()`, causing Gradle build errors. It now uses `setProgress(Integer.parseInt(...))` and `String.valueOf(getProgress())` respectively.
- Fixed `list_view` `on_click` lambda being silently dropped — only named function callbacks worked before. Now any lambda is compiled to an inline `pythonCallback_*` method and the `setOnItemClickListener` / `setOnClickListener` is always generated.
- Fixed `list_view` items always appearing with black text on Android regardless of the CSS `color` property. A custom `ArrayAdapter` subclass with `getView()` override is generated to apply `tv.setTextColor(...)` and `tv.setBackgroundColor(...)` per item (non-scroll mode), and the `updateXxxList()` method applies both directly to each `TextView` (scroll mode).
- Fixed `list_view` `on_click` toast showing the item string duplicated (e.g. `"08/06/2026 — ...: 08/06/2026 — ..."`) when the lambda used `item["title"]` and `item["subtitle"]`. Both now correctly extract title and subtitle from the stored `"title — subtitle"` string.
- Fixed class-level instance field scoping for `list_view` internals (`lst_items`, `lstAdapter`) — these were generated as `final` local variables inside `onCreate`, making them inaccessible from `pythonCallback_*` methods. They are now declared as `private` instance fields on the `Activity` class.
- Fixed `on_click_navigate(screen, data={...})` inside a `list_view` `on_click` lambda generating an empty `pythonCallback_*` method on Android. Root cause: `_gen_cmds_local` (the code generator for callback methods with parameters) was missing the `navigate` case that `_gen_cmds` already handled. Fix: added the `navigate` case to `_gen_cmds_local`.
- Fixed `screen.get_param()` values not appearing in labels in the Hot Previewer. Root cause: `lbl.set_value(screen.get_param("key"))` runs at module load time when `screen._params` is still empty, so labels were always set to `""`. Fix: `get_param()` now returns a lazy `_ParamRef` object; `set_value` stores the binding, and `render_screen` re-evaluates all bindings before drawing so labels always reflect the current params.
- Fixed `list_view` with a `height` CSS property (e.g. `height: 400px`) showing a large empty colored box on Android when the number of items is smaller than the fixed height. Root cause: the `ListView` respects the fixed `android:layout_height`, leaving visible empty space filled with the list's `background-color`. Fix: remove the fixed `height` from the list style and let the `ListView` use `wrap_content` so it sizes to its content.

---

## [0.9.9] — 2026-06-09

### Added
- **`type="date"`**: Opens the native Android `DatePickerDialog`. `get_value()` returns `"DD/MM/YYYY"` after the user picks a date, or `""` if not picked yet. In the Hot Previewer, opens a spinbox dialog (Day / Month / Year) so you can test without a device.
- **`type="time"`**: Opens the native Android `TimePickerDialog`. `get_value()` returns `"HH:MM"` after the user picks a time, or `""` if not picked yet. In the Hot Previewer, opens a spinbox dialog (Hour / Minute).
- **`type="number"`**: Shows the numeric keyboard on Android automatically. In the Hot Previewer, rejects non-numeric characters as you type. Supports integers, decimals, and negatives. `get_value()` always returns a string — use `int()` or `float()` in your Python code.
- **`type="switch"`**: Native Android `SwitchCompat` toggle switch. CSS `background-color` sets the track color when the switch is ON (defaults to `#4CAF50`). `get_value()` returns `"true"` or `"false"`.
- **`type="select"`**: Native Android `Spinner` dropdown. Pass options as `"A|B|C"`. `get_value()` returns the selected option text. CSS supports `color`, `background-color`, `border-*`, and `border-radius`.
- **`type="textarea"`**: Multi-line `EditText`. Control height with CSS `rows` (e.g. `rows: 6;`). Supports all standard input CSS properties.
- **`apkpy examples`**: New CLI command that lets you pick one of 5 complete, ready-made apps (`Hello World`, `Calculator`, `Notes`, `Settings`, `Login Screen`) and drop it straight into any folder. Each example can be previewed immediately with `python writehere.py` and built for Android with `apkpy build`.

### Fixed
- Fixed `AndroidManifest.xml` template using the wrong XML namespace (`schemas.microsoft.com` instead of `schemas.android.com`), which could cause build failures in Android Studio.
- Removed hardcoded `android:icon="@mipmap/ic_launcher"` and `android:label="Meu App ApkPy"` from the template manifest; the label is now set to a generic `"ApkPy App"` placeholder and `android:supportsRtl="true"` is added.

---

## [0.9.8] — 2026-06-08

### Added
- **`service` (Background Services API)**: Run code in the background, even when the app is closed. `service.every(run=fn, minutes=N, id="...", only_on_wifi=True, only_when_charging=True)` schedules a recurring task; `service.once(run=fn, after_minutes=N, id="...")` schedules a one-time delayed task; `service.cancel(id="...")` stops a scheduled task. In the Hot Previewer, runs on a background thread on a timer. On Android, compiles to native `WorkManager` (`PeriodicWorkRequest` / `OneTimeWorkRequest`) with real `setInitialDelay`, `NetworkType`, and `requiresCharging` constraints — background functions can use `storage`, `db`, `https`, `toast` and `notify`, just like in the Preview, with **100% identical code**.
- **`notify(title, message, id=...)`**: Show native system notifications in the phone's notification bar — unlike `toast()`, these are visible even when the app isn't open, making them the natural companion to background services. Compiles to a real `NotificationCompat.Builder` + `NotificationManager` on Android, and to a native OS toast/banner-style popup in the Hot Previewer.
- **`share(text, title=None)`**: Open the system's native share sheet to send text to other apps (WhatsApp, Email, SMS, Bluetooth, etc.). Compiles to `Intent.ACTION_SEND` + `Intent.createChooser(...)` on Android (works from both screens and background services via `FLAG_ACTIVITY_NEW_TASK`), and shows a Preview popup that mimics the Android share sheet with a list of common apps.
- **`clipboard.copy(text)`**: Copy text to the system clipboard — handy for sharing links, codes or generated results. Compiles to native `ClipboardManager`/`ClipData` on Android. In the Hot Previewer it writes to the **real OS clipboard** via Tkinter, so `Ctrl+V` outside the app pastes the actual copied text.
- **`camera.capture(on_result=callback)`**: Opens the device's native camera app to take a photo, delivering `(success, path)` to an async callback — the same pattern as `https.get/post`. Compiles to `ActivityResultContracts.TakePicture()` with automatic `CAMERA` runtime-permission requests and a `FileProvider`/`content://` setup (manifest `<provider>` entry + `res/xml/file_paths.xml` generated automatically — zero manual configuration). Since a desktop computer has no camera app, the Hot Previewer simulates the flow by opening the OS file picker filtered to images; the callback receives the real path of whatever file is chosen, keeping the Python code 100% identical between Preview and Android.
- **`gallery.pick(on_result=callback)`**: Opens the system's native image picker and delivers `(success, path)` to an async callback. Compiles to `ActivityResultContracts.GetContent()`, which is scoped-storage compliant and requires **no storage permissions** on modern Android. In the Hot Previewer it simulates the picker with the OS file explorer filtered to images, for the same reason and with the same 100%-identical-code guarantee as `camera.capture`.
- **`alert(title, message)`**: Show a native informational dialog with an OK button. Fire-and-forget — no callback needed. Compiles to `AlertDialog.Builder` on Android. In the Hot Previewer, opens a custom dialog with English button text regardless of OS language.
- **`confirm(title, message, on_result=callback)`**: Show a native confirmation dialog with OK and Cancel buttons. Calls `on_result(True)` if the user confirms, `on_result(False)` if they cancel — the same async `on_result` pattern as `camera.capture` / `gallery.pick`. Compiles to `AlertDialog.Builder` with positive/negative buttons on Android.

### Fixed
- Fixed a bug where running `apkpy build` opened a blank, empty Hot Previewer window that the user had to manually close every time — the preview window is now created lazily, only the first time the app actually runs the Previewer (`run()`), not on a simple `import`.
- Fixed `toast(f"...")` (and any other f-string passed to `toast`) generating an empty string in the compiled app — the message is now correctly compiled as a Java string concatenation, exactly like `notify`, `share` and `clipboard.copy` already did.
- Fixed `notify()` declaring the `POST_NOTIFICATIONS` permission in the manifest but never requesting it at runtime on Android 13+, which silently prevented notifications from showing on newer devices.
- Fixed `service.cancel()` and `service.once()` calls being silently dropped when used inside nested/indirect button-handler code paths (calls routed through `pythonCallback_X`), so they now generate correctly in every codegen path.
- Fixed `apkpy build` crashing with `FileNotFoundError: ... 'res/xml/file_paths.xml'` whenever an app used `camera.capture()` — the build command didn't know how to place files generated under `res/xml/` (the `FileProvider` paths file). It now creates `app/src/main/res/xml/` and writes the file there, just like it already did for `res/values/`.

---

## [0.9.7.1] — 2026-06-04

### Added
- **`https` (Network API)**: Make async HTTP requests to any REST API on the internet. Supports `https.get(url, headers={}, on_response=callback)` and `https.post(url, data={}, headers={}, on_response=callback)`. In the Hot Previewer, uses `urllib.request` on a daemon thread. On Android, compiles to native `HttpURLConnection` running in a background thread — the UI **never freezes**.
- **Custom `headers` support**: Pass any HTTP header as a Python dictionary (e.g. `{"Authorization": "Bearer TOKEN", "Content-Type": "application/json"}`). Works in both GET and POST requests, compiles cleanly to Java `setRequestProperty()` calls.
- **`db` (SQLite API)**: Brand new database module for native local storage. Use `db.execute(sql)` for write operations (`INSERT`, `UPDATE`, `DELETE`, `CREATE TABLE`) and `db.query(sql)` for read operations (`SELECT`). In the Hot Previewer, uses Python's built-in `sqlite3`. On Android, compiles to the native `android.database.sqlite.SQLiteDatabase` API — no Java knowledge required.
- **`json_get(json_string, path)` helper**: Safely read values from JSON strings (from `https` responses or `db.query()`) using dot-notation paths. Supports nested objects (`"main.temp"`) and list index access (`"weather.0.description"`). Returns `""` safely on any error.
- **`input_field()` component alias**: New alias for `inputs()` with cleaner semantics for single-line text fields.

### Changed
- `db.query()` always returns results as a **JSON string array** to ensure seamless cross-platform compatibility between Python and Java.

### Fixed
- Fixed issue where UI labels would not update after database writes — callers must now explicitly call their UI refresh function after a `db.execute()` call.
- Fixed Java compilation error caused by `__name__ == "__main__"` blocks being incorrectly included in the generated Activity class.

---

## [0.9.3] — 2025-05-29

### Added
- **Named builds**: `apkpy build` now asks for your app name interactively, so the generated `.zip` file uses your chosen name instead of a generic one.
- **`image()` component**: Display `.png` and `.jpg` files natively as Android `ImageView`. ApkPy automatically copies assets into the correct `res/drawable` folder.
- **`storage` API**: Persist data across app sessions with `storage.set()`, `storage.get()`, `storage.delete()`, and `storage.clear()`. Compiles to native Android `SharedPreferences`.
- **`toast()` notifications**: Trigger native Android Toast messages from any function.
- **Radio button inputs**: `inputs("A|B|C", type="radio")` now generates a full native radio button group.
- **`box-shadow` in CSS**: Adds drop shadows to components.

### Changed
- **XML Layout Engine**: Completely rewritten from programmatic Java UI to native Android XML layouts. This resolves 99% of layout and alignment inconsistencies.
- **Hot Previewer calibration**: Now matches the exact screen dimensions of a Pixel 9 Pro for a more accurate preview.
- **`@keyframes` stability**: Fixed `margin-top` animation glitches during transitions.

### Fixed
- `justify-content` and `align-items` now correctly map to native Android `gravity` attributes.
- `border-radius` no longer causes layout crashes on certain Android API levels.

---

## [0.9.0] — 2025-04-10

### Added
- **Declarative CSS animations** with `@keyframes` syntax.
- Supported animation properties: `opacity`, `scale`, `margin-top`, `margin-left`.
- Animation cross-platform support: works in Tkinter Previewer and compiles to native Android XML.
- `container()` component for nesting and grouping UI elements.
- `parent=` parameter on all components for nested layouts.

### Changed
- Improved error messages when `writehere.py` is missing or contains syntax errors.

---

## [0.8.5] — 2025-03-01

### Added
- Multi-screen support with `Screen()` and `on_click_navigate()`.
- `declare_permissions()` for static AndroidManifest permissions.
- Runtime permission requests with `permissions.request()` and callback support.
- `type="password"`, `type="search"`, `type="checkbox"`, `type="range"` input types.

### Fixed
- Initial release of the Hot Previewer (Tkinter-based live preview).

---

## [0.1.0] — 2025-01-15

### Added
- Initial release of ApkPy.
- Basic `Screen`, `label`, `button`, `inputs` components.
- Single-Activity Android project generation.
- `apkpy start` and `apkpy build` CLI commands.
