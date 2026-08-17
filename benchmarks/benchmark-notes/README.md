# Benchmark Notes

**Date:** 2026-08-17  
**Device:** Pixel 9 emulator, Android API 35, x86_64  
**Dataset:** 100 deterministic notes, no network, images, audio or backend.

This folder contains application code only. It does not contain the source of
the ApkPy compiler or runtime generator.

## Fairness contract

Each implementation presents the same title and helper copy, starts with the
same 100 records, searches title and subtitle, filters every fifth record as a
favorite, appends a new note and renders a scrollable list.

The visual APIs are idiomatic to each framework; the product behavior and
dataset remain fixed. Debug builds are used consistently because they are
inspectable and do not mix framework-specific release shrinker configuration
into the result.

This is a development-artifact comparison. Android's production guidance
prefers optimized release-like builds for performance conclusions, so these
numbers must not be presented as a universal store-release ranking.

## Measured result

| Stack | APK bytes | APK MiB | Cached build | Cold-start median | PSS median |
| --- | ---: | ---: | ---: | ---: | ---: |
| ApkPy | 5,637,396 | 5.38 | 20.863 s | 590 ms | 47,375 kB |
| Flet 0.86.5 | 26,505,412 | 25.28 | 143.009 s | 1,824 ms | 211,060 kB |
| BeeWare/Toga 0.5.6 | 35,634,620 | 33.98 | 17.783 s | 2,334 ms | 81,630 kB |
| Kivy 2.3.1 | — | — | — | — | — |

## Application source

| Candidate | Program | Packaging |
| --- | --- | --- |
| ApkPy | [`apkpy/writehere.py`](apkpy/writehere.py) | [`apkpy/apkpy.toml`](apkpy/apkpy.toml) |
| Flet | [`flet/main.py`](flet/main.py) | [`flet/pyproject.toml`](flet/pyproject.toml) |
| Kivy | [`kivy/main.py`](kivy/main.py) | [`kivy/buildozer.spec`](kivy/buildozer.spec) |
| BeeWare/Toga | [`beeware/src/benchmark_notes/app.py`](beeware/src/benchmark_notes/app.py) | [`beeware/pyproject.toml`](beeware/pyproject.toml) |

## Source lines

The physical count includes blank lines. The second count excludes blank
lines and lines whose first non-space character is `#`. Generated Java, XML,
Gradle output and configuration files are excluded.

| Stack | Physical | Non-blank, non-comment |
| --- | ---: | ---: |
| ApkPy | 83 | 66 |
| Flet | 70 | 58 |
| Kivy | 78 | 67 |
| BeeWare/Toga | 73 | 60 |

## Raw evidence

- [`results/benchmark.json`](results/benchmark.json) contains APK sizes,
  commands, SHA-256 hashes, raw start/PSS samples and ratios.
- [`results/device-runs.json`](results/device-runs.json) contains each device
  sample.
- [`results/environment.json`](results/environment.json) records host,
  framework and emulator versions.
- [`tools/measure-device.ps1`](tools/measure-device.ps1) repeats the installed
  app measurements without building or publishing anything.

APK binaries and generated framework output are intentionally excluded from
the repository. Their hashes identify the exact local artifacts used.

## Reproduce the device measurements

1. Build and install one candidate without changing its app contract.
2. Keep the same emulator, API, ABI and debug build class.
3. Run `tools/measure-device.ps1` with the candidate package and launcher.
4. Record a new JSON result; do not replace the dated source measurements.
5. If any condition changes, label the result as a separate scenario.

Kivy has no Android number because this Windows host had neither a usable
Buildozer/python-for-Android environment nor an installed WSL distribution.
The application and `buildozer.spec` are included for a later Linux/WSL run.

## Limits

This benchmark isolates a small UI/runtime floor. It does not measure Data
Core queries, media, maps, uploads, encryption, release shrinking, backend
latency or a large production app. A future benchmark may add release builds
and a Linux/WSL Kivy result without rewriting this measured run.
