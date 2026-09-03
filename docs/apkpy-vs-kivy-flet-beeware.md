---
title: ApkPy vs Kivy, BeeWare and Flet
description: How ApkPy differs from Kivy, BeeWare/Toga, Flet and Chaquopy — what goes into the APK, what draws the screen, whether pip packages work, and which one to pick.
---

# ApkPy compared with Kivy, BeeWare and Flet

All of these let you write an Android app in Python. They disagree about one
thing, and everything else follows from it: **is there a Python interpreter
inside the APK?**

ApkPy is the only one here that answers no. That is its whole reason to exist,
and it is also the source of its biggest limitation — so this page is as much
about when *not* to use it.

## The short version

| | Python in the APK? | What draws the screen | `pip` packages | Source |
| --- | --- | --- | --- | --- |
| **ApkPy** | **No** — Python is translated to Java at build time | Android's own views (`TextView`, `RecyclerView`, Material) | **No** | Closed |
| **Kivy** | Yes — CPython is bundled | Its own widgets, drawn with OpenGL | Yes (pure Python; C needs a recipe) | Open |
| **BeeWare / Toga** | Yes — CPython is bundled | Android's own native widgets | Yes | Open |
| **Flet** | Yes — CPython is bundled | Flutter | Yes | Open |
| **Chaquopy** | Yes — CPython is embedded | You write the UI in Kotlin/Java | Yes | Open |

## What each one actually does

**Kivy** ships a Python runtime and draws every button, label and list itself
with OpenGL. That is why a Kivy app looks like a Kivy app on every platform:
it is not using the operating system's widgets. It is the oldest and most
battle-tested of these, and if you need arbitrary Python on a phone it works
today.

**BeeWare / Toga** also ships a Python runtime, but maps your code onto the
**real** Android widgets. So it looks native *and* runs real Python — the
combination ApkPy cannot offer. It is actively developed and targets iOS and
desktop from the same code.

**Flet** ships a Python runtime and renders with Flutter. You get Flutter's
Material widgets, which look close to Android's without being Android's, and
the same code runs on desktop and the web.

**Chaquopy** is the odd one out: it puts Python *inside* a normal Android
Studio project, so you write your interface in Kotlin or Java and call Python
for the parts you want in Python. It is the right answer when you already have
an Android app and want to bring a Python library into it.

**ApkPy** reads your Python file rather than running it, and writes Android
source: `Activity` classes, layout XML, `res/` drawables and strings. There is
nothing to interpret on the device. The output is a project you can open in
Android Studio and read.

## Where ApkPy wins

- **Nothing to boot.** No interpreter starts, because there is not one. The app
  launches like any other Android app.
- **Size.** A debug build of a small app is around 5 MB. A bundled runtime is
  the largest single thing in the other approaches.
- **They are Android's widgets, not lookalikes.** Scrolling, text selection,
  accessibility services, keyboard behaviour and dark mode are the platform's,
  because the views are the platform's.
- **You can read the output.** `apkpy build` gives you a normal Android project.
  If you outgrow ApkPy, you keep the code.
- **Errors that name themselves.** Python ApkPy cannot translate stops the build
  and says which construct and why, instead of producing a blank value.

## Where ApkPy loses, and it is not close

- **No `pip` packages. At all.** `requests`, `numpy`, `pandas`, `pillow` — none
  of them can come, because there is no interpreter to import them into. Kivy,
  BeeWare and Flet all run real Python and can. **If your app needs a Python
  library, stop reading and use one of them.**
- **Only a subset of Python.** ApkPy translates a
  [documented vocabulary](compatibility.md) — control flow, functions, lists,
  dicts, f-strings, `try`/`except`, `math`, the common string methods. `re`,
  comprehensions in some positions, classes and much else are not in it. The
  build tells you, but it still tells you no.
- **Android only.** The others target iOS, desktop, and in some cases the web.
- **Closed source.** You cannot read the engine, audit it, or fix it yourself.
  The examples and documentation are public; the transpiler is not.
- **New, and small.** Kivy has been used in production for over a decade and
  BeeWare has an organisation behind it. ApkPy has neither yet. That is a real
  reason to choose something else, and pretending otherwise would not help you.

## Which one to pick

**Use Kivy** if you need real Python with arbitrary packages, you are happy for
the app to have its own look, and you want the option that has been around
longest.

**Use BeeWare** if you want native widgets *and* real Python, or you want the
same code on iOS and desktop. It is the closest thing to "the best of both",
and the cost is the runtime in the package.

**Use Flet** if you like Flutter's widgets and want desktop and web from the
same source.

**Use Chaquopy** if you already have an Android app and want to call Python
from it.

**Use ApkPy** if the app is Android, the interface matters, you want a small
APK with no interpreter, and your logic fits in ordinary Python — screens,
forms, lists, a database, network calls, background work. A shop floor tool, an
internal business app, a form-and-list app with a REST API behind it. That is
the shape it is built for.

## Frequently asked

**Does the APK contain Python?** No. The Python is translated at build time and
does not exist on the device.

**Is there a WebView?** No. The screens are Android views.

**Can I use `requests` / `numpy` / any package?** No. Use `https` for network
calls and `db` for data; for anything genuinely needing a Python library, use
BeeWare or Kivy.

**Can I open the result in Android Studio?** Yes — `apkpy build` produces a
normal Android project.

**Is it open source?** No. The engine is closed; examples and documentation are
public.
