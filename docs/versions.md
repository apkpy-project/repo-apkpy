---
title: Versions
description: ApkPy stable version, release candidates and version history.
---

# Versions

| Version | Status | Main addition |
| --- | --- | --- |
| 1.6.0 | prepared | the silence: Python that did nothing now says so, plus Bluetooth, purchases, languages, crash reports, code scanning, pinning and accessibility |
| 1.5.0 | prepared | the fingerprint check, a shared vocabulary for sizes and surfaces, and the places where the two renderers had picked different numbers |
| 1.4.0 | published | typed JSON bodies and timeouts, Markdown answers in rows that fit them, a drawer, settings rows and your own typeface |
| 1.3.2 | published | persistent background jobs, offline queue, any-file picker, `upload_button` and 64 diagnostic codes |
| 1.3.1 | published | relations, batched includes, observable queries and friendly diagnostics |
| 1.3.0 | published | typed Data Core, async CRUD, transactions and migrations |
| 1.2.2 | release candidate | keyed feed mutations and optimistic rollback |
| 1.2.1 | documented line | incremental pagination, prefetch and refresh |
| 1.2.0 | published feature line | media, realtime, maps, push, uploads and native documents |
| 1.1.0 | published | wider UI, lifecycle and Android parity work |
| 1.0.0 | published | first stable package |

Check the version shown by your installed package:

```powershell
python -c "import importlib.metadata; print(importlib.metadata.version('apkpy'))"
```

The [Android benchmark](benchmark.md) was measured against the local 1.3.0
candidate. It is kept separate from release status so its device, build mode
and limitations remain explicit.

Use the page matching your installed package:

- [Version 1.6.0](version-1.6.0.md)
- [Version 1.5.0](version-1.5.0.md)
- [Version 1.4.0](version-1.4.0.md)
- [Version 1.3.2](version-1.3.2.md)
- [Version 1.3.1](version-1.3.1.md)
- [Version 1.3.0](version-1.3.0.md)
- [Version 1.2.2](version-1.2.2.md)
- [Version 1.2.1](version-1.2.1.md)
- [Version 1.2.0](version-1.2.0.md)
- [Version 1.1.0](version-1.1.0.md)
- [Version 1.0.0](version-1.0.0.md)
