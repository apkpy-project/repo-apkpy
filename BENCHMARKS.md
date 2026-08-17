# ApkPy Android benchmark

This repository contains a reproducible, intentionally small Android
comparison named **Benchmark Notes**. The same deterministic 100-note dataset
and four visible actions were implemented with ApkPy, Flet, BeeWare/Toga and
Kivy:

- search the note title and subtitle;
- toggle a favorites-only filter;
- add one note;
- scroll the result list.

The benchmark includes the application source and packaging configuration for
every candidate. It does **not** contain the private source of the ApkPy
compiler.

## Result from 2026-08-17

All produced APKs are debug builds. Cold start and memory were measured on the
same Pixel 9 emulator running Android API 35.

These are development-build measurements. Android recommends optimized
release-like builds for production-performance conclusions; this run keeps all
artifacts inspectable and compares the same debug build class instead.

| Stack | App source | APK | Cached build | Cold start | PSS | UI smoke |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| ApkPy 1.3.0 workspace | 83 lines | **5.38 MiB** | 20.9 s | **590 ms** | **46.3 MiB** | 4/4 |
| Flet 0.86.5 | **70 lines** | 25.28 MiB | 143.0 s | 1,824 ms | 206.1 MiB | 4/4 |
| BeeWare/Toga 0.5.6 | 73 lines | 33.98 MiB | **17.8 s** | 2,334 ms | 79.7 MiB | 4/4 |
| Kivy 2.3.1 | 78 lines | not produced | not produced | not produced | not produced | source smoke only |

For this one small app, the ApkPy debug APK was **4.70x smaller than Flet**
and **6.32x smaller than BeeWare/Toga**. Its measured PSS was **4.46x lower
than Flet** and **1.72x lower than BeeWare/Toga**.

Those statements apply only to this app, device and build mode. They are not a
claim that one framework wins every workload. Release signing, R8, assets,
plugins, backend code and application architecture can change the result.

## What the result does and does not say

- It identifies the smallest, fastest-starting and lowest-PSS artifacts among
  the three APKs that were actually produced.
- It compares the complete packaging path of each framework, not merely Python
  syntax.
- It does not rank store-release builds or every type of application.
- It makes no Android performance claim for Kivy because no Kivy APK was
  produced on this host.

## Source-line rule

“App source” is the physical line count of the primary Python application
entry files. Blank lines are included; package configuration and generated
code are excluded. BeeWare needs both `app.py` and its five-line
`__main__.py`, so both are counted.

| Stack | Files | Physical | Non-blank, non-comment |
| --- | --- | ---: | ---: |
| ApkPy | `apkpy/writehere.py` | 83 | 66 |
| Flet | `flet/main.py` | 70 | 58 |
| Kivy | `kivy/main.py` | 78 | 67 |
| BeeWare/Toga | `beeware/src/benchmark_notes/app.py` + `__main__.py` | 73 | 60 |

Line count is included for transparency, not as a standalone measure of
maintainability. Formatting choices and framework conventions differ.

## Read the programs

- [ApkPy application](benchmarks/benchmark-notes/apkpy/writehere.py)
- [Flet application](benchmarks/benchmark-notes/flet/main.py)
- [Kivy application](benchmarks/benchmark-notes/kivy/main.py)
- [BeeWare/Toga application](benchmarks/benchmark-notes/beeware/src/benchmark_notes/app.py)
- [Packaging configurations and raw measurements](benchmarks/benchmark-notes/)

## Measurement protocol

1. Build a debug APK after its dependencies and Android toolchain are cached.
2. Install every produced APK on the same emulator.
3. Force-stop the package before each launch.
4. Run `adb shell am start -W` three times and report the median.
5. Wait two seconds after each launch, sample `dumpsys meminfo`, and report
   median total PSS.
6. Inspect the Android UI tree for `Benchmark Notes`, `Search notes`,
   `FAVORITES ONLY` and `ADD NOTE`.
7. Mark a missing platform tool as blocked instead of inventing a result.

Flet's first setup took 822.0 seconds because it downloaded Flutter, a JDK and
Android tooling. That one-time setup cost is recorded separately and is not
mixed into the cached-build column.

Kivy passed Python source compilation, but this Windows host had no
Buildozer/python-for-Android installation and no WSL distribution. Its Android
cells are deliberately empty.

The official Kivy guide recommends Buildozer for Android packaging and directs
Windows users to WSL. The source and `buildozer.spec` stay in the evidence
bundle so a future Linux/WSL measurement can complete that row without changing
the app contract.

See the [complete benchmark folder](benchmarks/benchmark-notes/README.md) for
raw runs, hashes, environment information and rerun instructions.

Measurement references: [Android performance](https://developer.android.com/topic/performance/measuring-performance),
[Android startup](https://developer.android.com/topic/performance/vitals/launch-time),
[Kivy Android packaging](https://kivy.org/doc/stable/guide/packaging-android.html)
and [BeeWare's Android tutorial](https://tutorial.beeware.org/en/latest/).
