# 🚀 ApkPy — Build Native Android Apps in Pure Python

> **Transform Python scripts into real, native Android projects — no Java required.**

[![PyPI version](https://img.shields.io/pypi/v/apkpy)](https://pypi.org/project/apkpy/)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-Proprietary-red)](#license)
[![Platform](https://img.shields.io/badge/platform-Android-green)](https://developer.android.com)

**ApkPy** is a closed-source Python-to-Android transpiler. Write your app in pure Python using a clean, CSS-inspired design system. ApkPy handles all the Java, XML, and Gradle complexity behind the scenes.

---

## ✨ Features

- 🐍 **Pure Python** — No Java, no Kotlin, no Android SDK knowledge needed to design
- 🎨 **CSS-inspired styling** — Style your app with familiar CSS syntax
- 🔄 **Live Previewer** — See your app instantly on your computer before building
- 📦 **One-command build** — `apkpy build` generates a ready-to-compile Android Studio project
- 💾 **Built-in storage** — Persistent data that compiles to native `SharedPreferences`
- 🔐 **Native permissions** — Camera, Location, and more with a single Python call
- 🎬 **Declarative animations** — `@keyframes`-style animations that compile to native Android XML
- 🖼️ **Image support** — Drop any `.png` or `.jpg` next to your script — ApkPy handles the rest

---

## 📦 Installation

```bash
pip install apkpy
```

---

## 🚀 Quick Start

```bash
apkpy start my_app
cd my_app
python writehere.py   # Preview on your computer
apkpy build           # Build the Android project
```

That's it. Open the generated `.zip` in Android Studio and compile your APK.

---

## 📁 Examples

Check out the [`examples/`](examples/) folder for complete working apps:

| File | What it shows |
| :--- | :--- |
| [`01_hello_world.py`](examples/01_hello_world.py) | The simplest possible app |
| [`02_multi_screen.py`](examples/02_multi_screen.py) | Navigation between multiple screens |
| [`03_storage.py`](examples/03_storage.py) | Saving & loading persistent data |
| [`04_coffee_haven.py`](examples/04_coffee_haven.py) | A full real-world multi-screen app |
| [`05_permissions.py`](examples/05_permissions.py) | Requesting camera & location permissions |

---

## 📖 Documentation

Full documentation is available at:

**👉 [github.com/apkpy/apkpy-docs](https://github.com/apkpy/apkpy-docs)**

---

## 🔐 License

ApkPy is **proprietary software**. The source code is not open for redistribution or modification.  
See [`LICENSE`](LICENSE) for full details.

© 2025 ApkPy. All rights reserved.

---

## 🤝 Community

- **Found a bug?** [Open an Issue](../../issues/new?template=bug_report.md)
- **Have a feature idea?** [Request a Feature](../../issues/new?template=feature_request.md)
- **Reddit:** [u/idkaesd](https://www.reddit.com/user/idkaesd/)
