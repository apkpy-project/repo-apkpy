# 🚀 ApkPy — Build Native Android Apps in Pure Python

> **Transform Python scripts into real, native Android projects — no Java required.**

[![PyPI version](https://img.shields.io/pypi/v/apkpy)](https://pypi.org/project/apkpy/)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-Proprietary-red)](#-license)
[![Platform](https://img.shields.io/badge/platform-Android-green)](https://developer.android.com)

**ApkPy** is a closed-source Python-to-Android transpiler. Write your app in pure Python using a clean, CSS-inspired design system. ApkPy parses your Python code, generates native Java + XML Android projects, and bundles everything into a ready-to-compile `.zip`. **No Java, no Kotlin, no Android Studio configuration.**

---

## ✨ What's in v0.9.7.1

> The biggest update yet. Two completely new API modules for **data** and **networking**.

### 🗄️ SQLite Database — Offline Data Storage
Build fully offline, persistent Android apps. The same `db` object works on your computer (Python `sqlite3`) and on real Android devices (native `SQLiteDatabase`).

```python
from apkpy_lib import db, json_get

# Create table on startup
db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)")

# Insert a row
db.execute("INSERT INTO users (name) VALUES ('Alice')")

# Read data — always returns a JSON string
result = db.query("SELECT * FROM users ORDER BY id DESC")
first_name = json_get(result, "0.name")   # → "Alice"
total      = json_get(db.query("SELECT COUNT(*) as n FROM users"), "0.n")
```

### 🌐 HTTPS Network API — Connect to Any REST API
Make real HTTP requests to any API on the internet. Runs in a **background thread** — the UI never freezes. Supports custom headers for API keys and Bearer tokens.

```python
from apkpy_lib import https, json_get

# Simple GET request
def on_response(success, response):
    if success:
        temp = json_get(response, "main.temp")   # Reads nested JSON fields
        city = json_get(response, "name")
        label_temp.set_value(f"{city}: {temp}°C")

https.get("https://api.openweathermap.org/data/2.5/weather?q=Lisbon&appid=YOUR_KEY&units=metric",
          on_response=on_response)

# POST with headers (e.g., Bearer token auth)
https.post(
    "https://api.example.com/submit",
    data={"key": "value"},
    headers={"Authorization": "Bearer YOUR_TOKEN", "Content-Type": "application/json"},
    on_response=on_response
)
```

### 🔎 `json_get()` — Navigate JSON Responses Effortlessly
Read any value from a JSON string using dot-notation. No imports, no try/except — returns `""` safely if the key doesn't exist.

```python
json_get(response, "name")              # Top-level key
json_get(response, "main.temp")         # Nested object
json_get(response, "weather.0.description")  # List index + key
json_get(db.query("SELECT * FROM t"), "0.id")  # First row, "id" column
```

---

## ✨ Full Feature Set

| Feature | Details |
| :--- | :--- |
| 🐍 **Pure Python** | No Java, no Kotlin, no Android SDK knowledge needed |
| 🎨 **CSS-inspired styling** | `border-radius`, `gap`, `flex-direction`, `padding`, animations — all in a CSS string |
| 🔄 **Live Previewer** | `python writehere.py` instantly shows your app on your computer (Tkinter) |
| 📦 **One-command build** | `apkpy build` generates a ready-to-compile Android Studio project as `.zip` |
| 🗄️ **SQLite database** | `db.execute()` / `db.query()` → native `SQLiteDatabase` on Android |
| 🌐 **HTTPS requests** | `https.get()` / `https.post()` with headers support → native `HttpURLConnection` |
| 🔎 **`json_get()`** | Read JSON fields with dot-notation (`"main.temp"`, `"0.name"`) |
| 💾 **Shared Preferences** | `storage.set()` / `storage.get()` → native `SharedPreferences` |
| 🔐 **Native permissions** | Camera, Location, and more with a single Python call |
| 🎬 **Declarative animations** | `@keyframes`-style animations that compile to native Android XML |
| 🖼️ **Image support** | Drop any `.png` or `.jpg` next to your script — ApkPy handles the rest |
| 🍞 **Toast notifications** | `toast("message")` → native `Toast.makeText()` |
| 📡 **Multi-screen navigation** | Multiple `Screen` objects with `on_click_navigate()` |

---

## 📦 Installation

```bash
pip install apkpy
```

Need the latest features? Upgrade to v0.9.7.1:
```bash
pip install --upgrade apkpy
```

---

## 🚀 Quick Start

```bash
# 1. Create a new project
apkpy start my_app

# 2. Enter the project folder
cd my_app

# 3. Preview instantly on your computer (no Android needed)
python writehere.py

# 4. Build the native Android project
apkpy build
# → Enter your app name when prompted
# → A .zip file is generated!

# 5. Open the .zip in Android Studio → Build → Generate APK
```

---

## 💡 Code Examples

### Hello World
```python
from apkpy_lib import Screen, label, button, run, toast

home = Screen(id="home")

label("Welcome to ApkPy! 🚀", id="title", screen=home)

def on_click():
    toast("Hello from Python! 👋")

button("Say Hello", id="btn", command=on_click, screen=home)

style = """
home {
    flex-direction: column;
    gap: 20px;
    padding: 40px;
    background-color: #0F172A;
}
title {
    color: #10B981;
    font-size: 26px;
    font-weight: bold;
    text-align: center;
}
btn {
    background-color: #10B981;
    color: #0F172A;
    border-radius: 14px;
    font-weight: bold;
    padding: 16px;
    pressed-color: #059669;
}
"""

if __name__ == "__main__":
    run(start_screen=home)
```

### SQLite — Offline Notes App
```python
from apkpy_lib import Screen, label, input_field, button, run, toast, db, json_get

db.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT)")

screen = Screen(id="notes_screen")
note_input = input_field("Write a note...", id="note_input", screen=screen)
lbl_last   = label("No notes yet.", id="lbl_last", screen=screen)

def refresh():
    result = db.query("SELECT * FROM notes ORDER BY id DESC")
    last   = json_get(result, "0.text")
    lbl_last.set_value(f"Last note: {last}" if last else "No notes yet.")

def save_note():
    text = note_input.get_value()
    if text != "":
        db.execute(f"INSERT INTO notes (text) VALUES ('{text}')")
        note_input.set_value("")
        toast("Note saved! ✅")
        refresh()

button("SAVE NOTE", id="btn_save", command=save_note, screen=screen)
refresh()

if __name__ == "__main__":
    run(start_screen=screen)
```

### HTTPS — Live Weather App
```python
from apkpy_lib import Screen, label, inputs, button, run, toast, https, json_get

API_KEY = "your_openweathermap_key"

screen     = Screen(id="weather")
city_input = inputs("Enter city...", type="text", id="city_input", screen=screen)
temp_lbl   = label("-- °C", id="temp", screen=screen)
desc_lbl   = label("---", id="desc", screen=screen)

def on_weather(success, response):
    if success:
        temp_lbl.set_value(f"{json_get(response, 'main.temp')} °C")
        desc_lbl.set_value(json_get(response, "weather.0.description").capitalize())
    else:
        toast("Failed to connect.")

def get_weather():
    city = city_input.get_value()
    if city != "":
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
        https.get(url, on_response=on_weather)

button("GET WEATHER ☁️", id="btn", command=get_weather, screen=screen)

if __name__ == "__main__":
    run(start_screen=screen)
```

---

## 📁 Examples

Check out the [`examples/`](examples/) folder for complete, runnable apps:

| File | What it shows |
| :--- | :--- |
| [`01_hello_world.py`](examples/01_hello_world.py) | The simplest possible app — label, button, toast |
| [`02_multi_screen.py`](examples/02_multi_screen.py) | Navigation between multiple screens |
| [`03_storage.py`](examples/03_storage.py) | Saving & loading persistent data with `storage` |
| [`04_coffee_haven.py`](examples/04_coffee_haven.py) | Full real-world multi-screen app with images, radio buttons, and animations |
| [`05_permissions.py`](examples/05_permissions.py) | Requesting camera & location permissions at runtime |

---

## 🔐 License

ApkPy is **proprietary software**. The source code is not open for redistribution or modification.  
See [`LICENSE`](LICENSE) for full details.

© 2025 ApkPy. All rights reserved.

---

## 🤝 Community

- **Found a bug or have a feature idea?** [Open an issue on GitHub!](https://github.com/apkpy-project/repo-apkpy/issues)
- **Want to contribute?** We're looking for contributors to expand the native component library!

---

*Made with ❤️ for the Python community.*
