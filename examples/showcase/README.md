# ApkPy showcase applications

These are the complete Python declarations behind the public Lumen, Onda,
Northline and Afterglow case studies. They contain app code and styles only;
the private ApkPy compiler source is not part of this directory.

| App | Entry file | Screens | Verified debug APK |
| --- | --- | ---: | --- |
| Lumen | `lumen_finance.py` | 4 | `docs/downloads/showcase/Lumen-debug.apk` |
| Onda | `onda_wellness.py` | 4 | `docs/downloads/showcase/Onda-debug.apk` |
| Northline | `northline_travel.py` | 4 | `docs/downloads/showcase/Northline-debug.apk` |
| Afterglow | `afterglow_music.py` | 4 | `docs/downloads/showcase/Afterglow-debug.apk` |

To rebuild an app, copy its entry file to a project as `writehere.py`, copy any
referenced local image next to it, then run `apkpy build` or `apkpy run`.

The included APKs are historical debug artifacts from the clean-wheel 1.1.0
verification run. See `docs/downloads/showcase/SHA256SUMS.txt` before installing
one on a test device.
