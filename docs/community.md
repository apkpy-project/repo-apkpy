---
title: Community and support
description: Where to ask for help, report defects and share ApkPy examples without creating empty community channels.
---

# Community and support

ApkPy is still early. Support is intentionally concentrated in one place so a
question does not disappear between an empty forum, chat server and issue
tracker.

## Choose the right route

| You need | Use |
| --- | --- |
| A reproducible defect | [Bug report](https://github.com/apkpy-project/repo-apkpy/issues/new?template=bug_report.md) |
| A missing public capability | [Feature request](https://github.com/apkpy-project/repo-apkpy/issues/new?template=feature_request.md) |
| Help diagnosing a build | Read [Troubleshooting](troubleshooting.md), then open a bug report with the requested evidence |
| A responsible security report | Follow the private process in [SECURITY.md](https://github.com/apkpy-project/repo-apkpy/blob/main/SECURITY.md) |
| An example worth sharing | Open an issue with the complete app file, assets, screenshot and tested ApkPy version |

Search existing issues before opening a new one. A minimal reproduction is
more useful than a screenshot of the final exception alone.

## What a useful report contains

~~~ text
ApkPy version:
Python version:
Operating system:
Command that failed:
Previewer or Android:
Generated project rebuilt after the change: yes/no
Minimal writehere.py:
Full traceback or Logcat cause:
Expected result:
Actual result:
~~~

For Android-only failures, include the first `FATAL EXCEPTION` and its deepest
`Caused by` section. Remove tokens, signing material, device identifiers and
private endpoint data before posting.

## Start from a maintained example

There is no separate starter-repository catalogue yet. Until repeated user
demand justifies maintaining one, use these versioned sources:

- [End-to-end Knowledge Vault tutorial](tutorial-end-to-end.md) — complete
  local-data app from install to Android build;
- [Tutorial source file](https://github.com/apkpy-project/repo-apkpy/blob/main/examples/tutorials/knowledge_vault.py)
  — the copyable `writehere.py` from that tutorial;
- [Showcase sources](https://github.com/apkpy-project/repo-apkpy/tree/main/examples/showcase)
  — four complete visual applications;
- `apkpy start` — creates the smallest supported local project.

## When more community infrastructure will appear

GitHub Discussions, a public chat server and independent starter repositories
will be opened only when there are enough recurring questions and maintainers
to keep them useful. Until then, Issues provide searchable decisions and a
single support history.

The core compiler is currently proprietary. Public contributions are still
welcome as reproducible reports, documentation corrections and complete
example apps; see
[CONTRIBUTING.md](https://github.com/apkpy-project/repo-apkpy/blob/main/CONTRIBUTING.md).
The maintainer may open-source the compiler later and will release the core as
open source if active development is permanently discontinued. Read the
[project continuity policy](project-continuity.md) for the exact boundary.
