---
title: What ApkPy reaches, and what it does not
description: Every Android capability ApkPy covers and every one it is missing, named, with the numbers behind them.
---

# What ApkPy reaches, and what it does not

Most tools tell you what they do. This page also tells you what they do not,
because that is the half you need before you start building and the half that
is usually missing.

Everything here was measured against `android.jar` from API 35 — the same file
the build compiles against — not estimated.

## The number you would put on a slide

| Measure | ApkPy | The platform | |
| --- | ---: | ---: | ---: |
| `android.*` classes referenced | 167 | 2,585 | **6.5%** |
| `android.*` packages touched | 31 | 186 | **16.7%** |
| System services (`getSystemService`) | 9 | 97 | **9.3%** |
| Permissions it knows how to declare | 20 | 322 | **6.2%** |

That is the honest number, and it is small.

It is also close to meaningless. Most of that denominator is not something an
app uses: `android.renderscript` is 48 deprecated classes, `android.icu.text`
is 55 classes of the ICU library, `android.health.connect.datatypes` is 59
classes of one feature, and there are whole packages for device administration
and carrier services that a normal application never touches. "6.5% of the
Android API" is as true as it is useless.

So here is the other count, with the list attached, so you can argue with it
instead of believing it.

## The count that means something

Sixty capabilities an application actually uses. **ApkPy covers 42.**

The list is ours. That is exactly why it is printed in full.

### Screens

| | |
| :--: | --- |
| yes | screens and navigation |
| yes | bottom bar and drawer |
| yes | lists and virtual collections |
| yes | light/dark theme at run time |
| yes | your own typefaces |
| yes | Markdown and rich text |
| yes | maps |
| **no** | **charts** |
| **no** | **WebView / Custom Tabs** |

### Data

| | |
| :--: | --- |
| yes | key-value storage |
| yes | typed SQLite |
| yes | HTTP with JSON |
| yes | WebSocket |
| yes | files and uploads |
| yes | encryption and keys |
| **no** | **saving a file to the user's storage** |
| **no** | **DownloadManager** |

### Background

| | |
| :--: | --- |
| yes | background work that survives the app |
| yes | notifications |
| yes | push (Firebase) |
| yes | continuous location |
| yes | scheduled tasks |

### The device

| | |
| :--: | --- |
| yes | camera and gallery |
| yes | embedded camera |
| yes | barcodes and QR |
| yes | motion sensors |
| yes | location |
| yes | biometrics |
| yes | NFC |
| yes | Bluetooth and BLE |
| yes | flashlight |
| yes | battery |
| yes | wallpaper |
| yes | contacts |
| yes | clipboard |
| **no** | **vibration and haptics** |
| **no** | **recording audio** |
| **no** | **reading text aloud** |
| **no** | **dictation (speech to text)** |
| **no** | **calendar** |
| **no** | **phone and SMS** |
| **no** | **printing and PDF** |
| **no** | **health sensors** |

### Media

| | |
| :--: | --- |
| yes | playing audio |
| yes | video |
| yes | sharing to other apps |
| **no** | **receiving a share from another app** |

### System

| | |
| :--: | --- |
| yes | runtime permissions |
| yes | languages |
| yes | crash reports |
| yes | accessibility checks |
| yes | app inspection |
| yes | in-app purchases |
| yes | OAuth sign-in |
| yes | [your own Java](guides/native.md) |
| **no** | **deep links into your app** |
| **no** | **home-screen widget** |
| **no** | **quick settings tile** |
| **no** | **ads (AdMob)** |
| **no** | **updates through Play** |

## What a "no" costs you

Since 1.9.0, a missing capability is not always a wait. `native.java()` lets
you declare the Java for it yourself, with the arguments it takes and the
answer the Previewer gives instead — see [your own Java](guides/native.md).

**Six of the eighteen are written already.** Reading text aloud, opening a
page, downloading a file, saving a text file where the user will find it,
dialling a number and putting something in the calendar are in
[Native recipes](guides/native-recipes.md), copy and paste, each one compiled
before it was published. Vibration is in
[the native example](https://github.com/apkpy-project/repo-apkpy/blob/main/examples/31_native_java.py).

**The rest are not a handful of lines, and saying otherwise would be a
sales pitch.** A block runs and returns: it cannot wait for another screen to
come back, so the system file picker and receiving a share are out. It is a
method inside an Activity, so it cannot add a view to the layout — no WebView,
no charts — and it cannot be a home-screen widget or a quick settings tile,
which are separate components. AdMob, Play in-app updates and Health Connect
are SDKs with their own lifecycles; `native.gradle()` can pull them in, but
what you would write around them is an integration, not a recipe.

That is the honest position: for six of them ApkPy does not stand in your way,
and for the others it is still "not yet".

## The other ceiling

Coverage is the question everyone asks. It is not the one that stops apps
growing. Until 1.10.0 an application had to live in a single `writehere.py`,
because ApkPy does not translate Python classes — so every screen, callback
and helper landed in one file. [More than one file](guides/modules.md) is what
changed that, and it matters more than any single item on the list above.

## How these numbers were produced

- Classes, packages: every fully qualified `android.*` name the compiler, the
  feature modules and the Java sidecars can emit, checked against the classes
  that really exist in `android.jar` (10 of the 177 matches were permission
  and intent strings, not classes, and were dropped).
- System services: the `*_SERVICE` constants declared on `android.content.Context`.
- Permissions: the constants on `android.Manifest.permission`.
- Capabilities: our list of sixty, each decided by a named signal in the
  source — a public API name, or a specific Android class in the generated
  Java. Printed above in full so the list can be checked rather than trusted.

See also [Compatibility and limits](compatibility.md) for the Python ApkPy
translates, and [Can ApkPy build this?](can-apkpy-build-this.md) for whole app
types rather than single capabilities.
