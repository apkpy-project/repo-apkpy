# Contributing to ApkPy

ApkPy is open source under the [Apache License 2.0](LICENSE), and changes to
it are welcome: a fix, a test, a clearer error message, an example.

It is maintained by one person. A report or a pull request is read, but an
answer can take some days.

---

## Reporting bugs

If you find a bug, please [open an issue](../../issues/new?template=bug_report.md) and include:

- **ApkPy version** (run `pip show apkpy`)
- **Python version** (run `python --version`)
- **Operating System** (Windows / macOS / Linux)
- A **minimal code snippet** that reproduces the bug
- The **full error message** or unexpected output

The more detail you provide, the faster it can be fixed.

---

## Requesting features

Have an idea for a new component, CSS property, or workflow improvement?

[Open a feature request](../../issues/new?template=feature_request.md) and describe:

- **What you want to do** that you currently can't
- **Why it would be useful** to other developers
- Any **examples or references** from other frameworks

---

## Changing the code

For anything larger than a fix, open an issue first and say what you want to
do: it saves writing something that cannot go in.

```bash
git clone https://github.com/apkpy-project/repo-apkpy
cd repo-apkpy
python -m pip install -e .
```

### What is where

| Folder | What is in it |
| --- | --- |
| `apkpy_lib/core/` | The build: your Python read, and written out as an Android project. `compiler.py` is the translator; `core/features/` holds the features one by one, with the Java classes that go into the apps. |
| `apkpy_lib/ui.py`, `apkpy_lib/features/` | The Previewer: the same app drawn on the desktop. |
| `apkpy_lib/*_rules.py` | What both sides read, so the phone and the Previewer cannot disagree. |
| `tests/` | The tests. |
| `examples/` | Complete apps. |

### A feature has two sides

Everything an app can do is done twice: by the build, for the phone, and by
the Previewer, for the desktop. A change to one that leaves the other behind
is the commonest defect ApkPy has had. If you change how something looks or
behaves, change both, and say in the pull request how you saw each.

### Tests

```bash
cd tests/features
python -W ignore -m unittest discover -s .
```

About four minutes. The Previewer's tests open windows, so they need a
display; the ones that compile ApkPy's Java need a JDK, and a few an Android
SDK. A test that lacks what it needs is skipped and says why.

The core tests run from the root of the repository:

```bash
python -m unittest discover -s tests -q
```

A fix comes with a test that fails without it.

### Before you open the pull request

- the suites pass;
- you built an app that uses the change (`apkpy build`) and read the Java it
  wrote: tests have passed over Java that was wrong;
- if a user would notice the change, it has a line in
  [`CHANGELOG.md`](CHANGELOG.md) under `[Unreleased]`.

---

## Licence of contributions

What you contribute is under the same licence as ApkPy — the Apache License
2.0, with the exception at the end of the [`LICENSE`](LICENSE) file — as
section 5 of the licence says. There is no separate agreement to sign.
Contribute only what is yours to give.

---

## Contributing examples

An example goes in [`examples/`](examples/) by pull request: the complete app
source, every asset it needs, and in the description one screenshot, the
ApkPy version and where you ran it (Android version, or the Previewer).
Never include API keys, signing material or private user data.

---

## Community guidelines

- Be respectful and inclusive.
- Stay on topic — this repository is specifically for ApkPy.
- Search existing issues before opening a new one.

GitHub Issues is currently the single public support channel. Separate forums,
chat servers and community starter repositories will be created only when
there is enough recurring participation to maintain them.
