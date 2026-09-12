# ApkPy 1.8.0 — A camera of your own, smaller releases, and fewer silences

Write native Android apps in the supported Python subset. The generated APK
still contains Java/XML, not a Python runtime.

## New

- **A camera your app owns.** `camera.open()`, `capture()`, `record()` and
  `capabilities()`: photo and video, both lenses, zoom, focus, exposure, flash
  and torch, a timer, pause and resume while recording, a review step, and
  manual ISO, shutter, white balance and focus. A manual setting the hardware
  cannot honour reports an error instead of pretending it applied. The camera
  screen's controls, labels, colours and title are yours to change.
  `camera.capture(on_result=...)` keeps its 1.7.0 signature.
- **`camera_view()`**, a live viewfinder placed inside your own layout, with
  your own buttons around it.
- **Smaller releases.** `apkpy release` runs R8, which drops the library code
  the app cannot reach. A measured release went from 4,496 KB to 1,536 KB, and
  the Benchmark Notes app ships at 1,518 KB. Names are deliberately **not**
  obfuscated, so `crash.last()` stays readable and no mapping file has to be
  kept. `apkpy run` is unaffected.
- **`in` and `not in`** inside `and`, `or` and `not`, on their own, and in a
  ternary. Membership against a list, tuple, set or dict written in the source,
  a list kept at module level, or a `split()` call; a text search otherwise.
  That is decided from the source, never from the running value.

## Fixed — Python that used to fail quietly

- **`text.split()`** compiled to Java's array: a `for` loop over it ran no
  times, `len()` counted the characters of its address, and a label showed
  `[Ljava.lang.String;@…`. It is now a list with Python's rules — the separator
  is text rather than a regular expression, empty parts are kept, `maxsplit` is
  honoured, and with no separator it splits on whitespace. The generated helper
  was compiled and run against Python's own `str.split` on 628 cases, with no
  difference.
- **A `range()` index is a number.** `i + 1` printed `01` on the phone and `1`
  in the Previewer, `n += i` joined text, and `i % 2` had no translation at all.
- **An `if` whose condition could not be written** no longer disappears, body
  and all. Nor does a ternary become empty text, nor a comparison compile to
  `Double.parseDouble("")`, which crashed the app when that code ran.
- **Assignments and loops that left the app without a word** — unpacking,
  `a = b = 0`, assigning to an item or attribute, a comprehension, a condition
  or tuple used as a value, `for ... else`, and looping over text, a dict or a
  set — now stop the build with U2033 and name a form that compiles. `x = -1`,
  `x = a if test else b` and `x = math.pi` translate instead.
- **`%` formatting and arithmetic on text** (`"n=%s" % n`, `price * 2`,
  `"-" * 20`, `-n`) no longer become empty text.
- **An f-string format other than `.2f` or `,.2f`** no longer prints the
  unformatted value on the phone while the Previewer formats it.

## Upgrading

These fixes turn silence into build errors. An app that relied on one of those
shapes quietly doing nothing will now stop the build, naming the line and a
form that does compile. That is the point of the change: every case listed
above already behaved differently on the phone than in the Previewer, or did
nothing at all.

## Benchmark, corrected

The ApkPy row of the published benchmark measured an app whose list was empty
on the phone: its module-level comprehension compiled to nothing. The app was
rewritten so it builds, checked on the device to show, filter, add and search
its 100 notes, and timed again beside BeeWare/Toga in the same session: 2,565 ms
against 5,536 ms, 67.0 MiB against 83.4 MiB, and a debug APK 6.4x smaller. Cold
start on that emulator moved by more than 2x within one day, so times from
different sessions are not comparable. Method, every session and three
discarded ones are in
[`benchmarks/benchmark-notes/scenarios/2026-09-11-apkpy-1.8.0/`](benchmarks/benchmark-notes/scenarios/2026-09-11-apkpy-1.8.0/README.md).

## Verified in this release

- 1,040 feature tests, 35 general tests and 258 transpiler checks passed.
- The `split()` helper compiled with the JDK and compared with `str.split` on
  628 cases: no difference, and the same whitespace set across the BMP.
- 92 example apps and documented snippets transpiled with the engine from
  before and after the changes: every app that built still builds. Two scripts
  that are not apps now stop, both on code that was being dropped.
- MkDocs strict build.
- The measured benchmark app was built, installed and driven on a Pixel 9
  emulator (API 35, x86_64): it opens with 100 notes, filters to 20 favourites,
  adds one, and finds a single match.

## Not verified

The camera's EXIF from manual settings, video with audio, lens switching and
rotation are taken from the implementation report on one device, not
re-measured here. Other phone models are not verified. RAW/DNG, vendor HDR,
night and portrait modes, slow motion, concurrent cameras, live frame analysis,
publishing to the gallery and capture from the background are not implemented.

Full notes: [1.8.0](docs/version-1.8.0.md) ·
[camera guide](docs/guides/camera.md) ·
[build and release](docs/build-release.md) ·
[compatibility](docs/compatibility.md)
