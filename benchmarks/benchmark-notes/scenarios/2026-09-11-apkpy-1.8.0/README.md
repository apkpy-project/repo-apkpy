# Benchmark Notes — ApkPy 1.8.0 scenario

**Date:** 2026-09-11  
**Device:** Pixel 9 emulator (`sdk_gphone16k_x86_64`), Android API 35, x86_64, 16 KB pages, 2 GB RAM  
**ApkPy:** 1.8.0 candidate from the local workspace, not released  
**Dataset:** the same 100 deterministic notes, no network, images, audio or backend.

This folder contains application code and measurements only. It does not
contain the source of the ApkPy compiler or runtime generator.

This is a separate scenario. The [2026-08-17 run](../../README.md) is left as
it was recorded: its README asks for a new scenario whenever conditions change,
and here the ApkPy program, the checks and the timing method all changed.

## Why the ApkPy row had to be measured again

The 2026-08-17 ApkPy program built its notes with a list comprehension at
module level, formatted titles with `{index:03d}` and picked favourites with
`index % 5`. The ApkPy version measured then translated none of that and said
nothing: on the phone the app opened with an empty list. The UI smoke check
only looked for four labels, and the labels were there. The 590 ms and
46.3 MiB were real measurements of an app that did less than the other three.

Current ApkPy stops the build on that program instead of compiling it to
nothing, so it could not be measured again unchanged either.

## What changed in the ApkPy program

| 2026-08-17 | 2026-09-11 | Why |
| --- | --- | --- |
| a module-level comprehension builds `NOTES` | `lifecycle(home, on_mount=load_notes)` fills it with a `for` loop and `append()` | a comprehension at module level is not translated |
| `f"Note {index:03d}"` | `"Note " + padded(index)` | the `03d` format is not translated |
| `visible_notes()` returns a comprehension | it builds the list in a `for` loop | a comprehension inside a function is not translated |
| `index % 5 == 0` | unchanged | translated since 1.8.0, where a `range()` index is a number |

Labels, dataset, style and behaviour are the same. The program is 104
physical lines, 81 without blank and comment lines (83 and 66 before). The
Flet, Kivy and BeeWare/Toga programs are unchanged and stay in the parent
folder.

## A check that each app works

Before any launch is timed, `tools/measure.py` drives the app through adb and
reads the status label (`Showing N notes`) back from the UI tree after every
action:

1. it opens showing 100 notes, with `Note 001` on screen;
2. **FAVORITES ONLY** shows 20;
3. tapping it again shows 100;
4. **ADD NOTE** shows 101;
5. typing `Note 010` into the search shows 1.

Each step waits up to 20 seconds for the expected count, 40 for the first.

## How the launches were timed

The cold-start and memory reading is the 2026-08-17 one: force-stop, 250 ms,
`adb shell am start -W`, the first `TotalTime`/`WaitTime`, then two seconds
and `TOTAL PSS` from `dumpsys meminfo`. Two things were added, because this
emulator needed them:

- **A warm-up.** A 2 GB emulator with Play services keeps settling after it
  boots and after an install: the same APK timed 5.7 s, 4.1 s and 1.4 s
  depending only on when it was launched. Each app is cold-started until three
  launches in a row agree within 15 % (at most 12), and those launches are not
  counted.
- **Ten timed launches.** The median of the first three is kept, so it can be
  set beside the 2026-08-17 method, together with the median, minimum and
  maximum of all ten.

Every benchmark app is force-stopped before the next one is measured, so one
stack is not left resident in memory while another is timed.

## Result

Session 4 in `results/`: BeeWare/Toga and then ApkPy, back to back on the same
emulator, with the final ApkPy APK. Debug builds.

| Stack | APK | Cold start, first three | Cold start, all ten (min–max) | PSS median | Functional check |
| --- | ---: | ---: | ---: | ---: | --- |
| **ApkPy 1.8.0 candidate** | **5.37 MiB** | **2,565 ms** | **2,855 ms** (2,542–7,332) | **67.0 MiB** | 5/5 |
| BeeWare/Toga, same-session control | 34.46 MiB | 5,536 ms | 5,573 ms (5,445–5,846) | 83.4 MiB | 4/5 |

In the same session ApkPy started about **2x sooner** than BeeWare/Toga, held
about **a fifth less memory**, and its APK was **6.4x smaller**.

One ApkPy launch took 7,332 ms. It is kept rather than dropped; it is not among
the first three, and it moves the median of all ten by little.

BeeWare/Toga's search still read 101 notes after 20 seconds, in this session
and in session 3. It reached one match in session 1, when the emulator was
faster. Every other step passed.

The ApkPy debug build took 49.2 s from source to APK with dependencies cached.
A short transpiler check was running during its first seconds; an earlier build
of the same program that day took 35.1 s.

Both APKs are debug builds, which is the class the 2026-08-17 run compared. For
scale, the same ApkPy program signed as a release, with R8, comes to 1,518 KB.
The debug APK carries 4,105 KB of code; R8 leaves 645 KB of it, and shrinks the
resource table from 963 KB to 595 KB. The other stacks were not rebuilt as
releases.

## Only the same session compares

Cold start on this emulator moved a great deal between sessions of the same
day, and between days:

| Session | ApkPy, median | BeeWare/Toga, median | BeeWare/Toga ÷ ApkPy |
| --- | ---: | ---: | ---: |
| 2026-08-17, published | 590 ms, empty list | 2,334 ms | -- |
| 1 · trial: three launches, no warm-up | 1,387 ms | 2,145 ms | 1.55x |
| 3 · control: ten launches after a warm-up | 2,550 ms | 5,212 ms | 2.04x |
| 4 · final: ten launches after a warm-up | 2,855 ms | 5,573 ms | 1.95x |

The same BeeWare/Toga program started in 2,145 ms in the first session and in
5,573 ms in the last one, on the same day. An ApkPy time from 2026-09-11
therefore cannot be set beside a Flet or BeeWare/Toga time from 2026-08-17 as if
they had been measured together. The ratio inside one session is the
comparison; an absolute time describes this emulator at that moment.

Memory moved far less. ApkPy's PSS median stayed between 66.9 and 67.9 MiB in
every session, and BeeWare/Toga's between 81.6 and 83.4 MiB (79.7 MiB on
2026-08-17).

## Flet and BeeWare/Toga

The Flet and BeeWare/Toga rows on the benchmark page stay as recorded on
2026-08-17. Neither framework changed, and this scenario is about ApkPy.

- **BeeWare/Toga** was rebuilt from the same program with Briefcase 0.4.4 only
  to be measured in the same sessions as ApkPy. Its published row is not
  replaced.
- **Flet** was not rebuilt. Its Android build needs symbolic links, which
  Windows only allows with Developer Mode, and that was off on this host. The
  published Flet APK was built for `arm64-v8a` and ran on this x86_64 emulator
  through ARM translation, which is likely to slow its start and raise its
  memory; a native x86_64 build was not measured.
- **Kivy** still has no Android build.

## Where ApkPy's start-up time goes

This was not profiled; it is what the generated Java does. `load_notes`
appends the 100 notes one at a time, and every append reads the whole list back
from JSON text and writes it out again. `refresh_rows` then builds the visible
list the same way, and does it twice -- once for the rows and once for the
count. All of it runs before the first frame, and the work grows with the
square of the number of notes. It is the most likely reason the populated app
starts so much later than the empty one did, and the obvious place to make
ApkPy faster.

## Files

- `apkpy/writehere.py`, `apkpy/apkpy.toml` -- the measured program.
- `tools/measure.py` -- the functional check, warm-up and timing. It builds and
  publishes nothing. The only change from the copy that ran is where it finds
  `adb`.
- `results/session-4-final.json` -- the numbers above: BeeWare/Toga and ApkPy
  back to back, with the final ApkPy APK.
- `results/session-1-trial.json` to `session-3-control.json` -- earlier
  sessions of the same day, kept to show the spread.
- `results/discarded/` -- three sessions that were not used, each with the
  reason inside the file.
- `results/summary.json` -- the medians of every session, and the 2026-08-17
  rows for reference.

APK binaries are not included. Every result file records the SHA-256 of the APK
it measured.

## Reproduce

1. Build `apkpy/` with `apkpy run` and keep the debug APK.
2. Start a Pixel 9, API 35, x86_64 emulator and put `adb` on your `PATH` (or
   set `ADB`).
3. `py tools/measure.py --out results.json --app "ApkPy=path/to/Benchmark_Notes-debug.apk"`,
   adding `--app "BeeWare/Toga=path/to/app-debug.apk"` for a reference measured
   in the same session.
4. Publish a new dated scenario instead of editing this one.

## Limits

Debug builds, one emulator, one day and one small app. This is not a
release-build comparison, not a physical phone, and says nothing about apps
that use Data Core, media, maps or a backend.
