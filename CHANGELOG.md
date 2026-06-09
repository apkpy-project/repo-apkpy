# Changelog

All notable changes to ApkPy will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.9.9] — 2026-06-09

### Added
- **`type="date"`**: Opens the native Android `DatePickerDialog`. `get_value()` returns `"DD/MM/YYYY"` after the user picks a date, or `""` if not picked yet. In the Hot Previewer, opens a spinbox dialog (Day / Month / Year) so you can test without a device.
- **`type="time"`**: Opens the native Android `TimePickerDialog`. `get_value()` returns `"HH:MM"` after the user picks a time, or `""` if not picked yet. In the Hot Previewer, opens a spinbox dialog (Hour / Minute).
- **`type="number"`**: Shows the numeric keyboard on Android automatically. In the Hot Previewer, rejects non-numeric characters as you type. Supports integers, decimals, and negatives. `get_value()` always returns a string — use `int()` or `float()` in your Python code.
- **`type="switch"`**: Native Android `SwitchCompat` toggle switch. CSS `background-color` sets the track color when the switch is ON (defaults to `#4CAF50`). `get_value()` returns `"true"` or `"false"`.
- **`type="select"`**: Native Android `Spinner` dropdown. Pass options as `"A|B|C"`. `get_value()` returns the selected option text. CSS supports `color`, `background-color`, `border-*`, and `border-radius`.
- **`type="textarea"`**: Multi-line `EditText`. Control height with CSS `rows` (e.g. `rows: 6;`). Supports all standard input CSS properties.
- **`apkpy examples`**: New CLI command that lets you pick one of 5 complete, ready-made apps (`Hello World`, `Calculator`, `Notes`, `Settings`, `Login Screen`) and drop it straight into any folder. Each example can be previewed immediately with `python writehere.py` and built for Android with `apkpy build`.

### Fixed
- Fixed `AndroidManifest.xml` template using the wrong XML namespace (`schemas.microsoft.com` instead of `schemas.android.com`), which could cause build failures in Android Studio.
- Removed hardcoded `android:icon="@mipmap/ic_launcher"` and `android:label="Meu App ApkPy"` from the template manifest; the label is now set to a generic `"ApkPy App"` placeholder and `android:supportsRtl="true"` is added.

---

## [0.9.8] — 2026-06-08

### Added
- **`service` (Background Services API)**: Run code in the background, even when the app is closed. `service.every(run=fn, minutes=N, id="...", only_on_wifi=True, only_when_charging=True)` schedules a recurring task; `service.once(run=fn, after_minutes=N, id="...")` schedules a one-time delayed task; `service.cancel(id="...")` stops a scheduled task. In the Hot Previewer, runs on a background thread on a timer. On Android, compiles to native `WorkManager` (`PeriodicWorkRequest` / `OneTimeWorkRequest`) with real `setInitialDelay`, `NetworkType`, and `requiresCharging` constraints — background functions can use `storage`, `db`, `https`, `toast` and `notify`, just like in the Preview, with **100% identical code**.
- **`notify(title, message, id=...)`**: Show native system notifications in the phone's notification bar — unlike `toast()`, these are visible even when the app isn't open, making them the natural companion to background services. Compiles to a real `NotificationCompat.Builder` + `NotificationManager` on Android, and to a native OS toast/banner-style popup in the Hot Previewer.
- **`share(text, title=None)`**: Open the system's native share sheet to send text to other apps (WhatsApp, Email, SMS, Bluetooth, etc.). Compiles to `Intent.ACTION_SEND` + `Intent.createChooser(...)` on Android (works from both screens and background services via `FLAG_ACTIVITY_NEW_TASK`), and shows a Preview popup that mimics the Android share sheet with a list of common apps.
- **`clipboard.copy(text)`**: Copy text to the system clipboard — handy for sharing links, codes or generated results. Compiles to native `ClipboardManager`/`ClipData` on Android. In the Hot Previewer it writes to the **real OS clipboard** via Tkinter, so `Ctrl+V` outside the app pastes the actual copied text.
- **`camera.capture(on_result=callback)`**: Opens the device's native camera app to take a photo, delivering `(success, path)` to an async callback — the same pattern as `https.get/post`. Compiles to `ActivityResultContracts.TakePicture()` with automatic `CAMERA` runtime-permission requests and a `FileProvider`/`content://` setup (manifest `<provider>` entry + `res/xml/file_paths.xml` generated automatically — zero manual configuration). Since a desktop computer has no camera app, the Hot Previewer simulates the flow by opening the OS file picker filtered to images; the callback receives the real path of whatever file is chosen, keeping the Python code 100% identical between Preview and Android.
- **`gallery.pick(on_result=callback)`**: Opens the system's native image picker and delivers `(success, path)` to an async callback. Compiles to `ActivityResultContracts.GetContent()`, which is scoped-storage compliant and requires **no storage permissions** on modern Android. In the Hot Previewer it simulates the picker with the OS file explorer filtered to images, for the same reason and with the same 100%-identical-code guarantee as `camera.capture`.
- **`alert(title, message)`**: Show a native informational dialog with an OK button. Fire-and-forget — no callback needed. Compiles to `AlertDialog.Builder` on Android. In the Hot Previewer, opens a custom dialog with English button text regardless of OS language.
- **`confirm(title, message, on_result=callback)`**: Show a native confirmation dialog with OK and Cancel buttons. Calls `on_result(True)` if the user confirms, `on_result(False)` if they cancel — the same async `on_result` pattern as `camera.capture` / `gallery.pick`. Compiles to `AlertDialog.Builder` with positive/negative buttons on Android.

### Fixed
- Fixed a bug where running `apkpy build` opened a blank, empty Hot Previewer window that the user had to manually close every time — the preview window is now created lazily, only the first time the app actually runs the Previewer (`run()`), not on a simple `import`.
- Fixed `toast(f"...")` (and any other f-string passed to `toast`) generating an empty string in the compiled app — the message is now correctly compiled as a Java string concatenation, exactly like `notify`, `share` and `clipboard.copy` already did.
- Fixed `notify()` declaring the `POST_NOTIFICATIONS` permission in the manifest but never requesting it at runtime on Android 13+, which silently prevented notifications from showing on newer devices.
- Fixed `service.cancel()` and `service.once()` calls being silently dropped when used inside nested/indirect button-handler code paths (calls routed through `pythonCallback_X`), so they now generate correctly in every codegen path.
- Fixed `apkpy build` crashing with `FileNotFoundError: ... 'res/xml/file_paths.xml'` whenever an app used `camera.capture()` — the build command didn't know how to place files generated under `res/xml/` (the `FileProvider` paths file). It now creates `app/src/main/res/xml/` and writes the file there, just like it already did for `res/values/`.

---

## [0.9.7.1] — 2026-06-04

### Added
- **`https` (Network API)**: Make async HTTP requests to any REST API on the internet. Supports `https.get(url, headers={}, on_response=callback)` and `https.post(url, data={}, headers={}, on_response=callback)`. In the Hot Previewer, uses `urllib.request` on a daemon thread. On Android, compiles to native `HttpURLConnection` running in a background thread — the UI **never freezes**.
- **Custom `headers` support**: Pass any HTTP header as a Python dictionary (e.g. `{"Authorization": "Bearer TOKEN", "Content-Type": "application/json"}`). Works in both GET and POST requests, compiles cleanly to Java `setRequestProperty()` calls.
- **`db` (SQLite API)**: Brand new database module for native local storage. Use `db.execute(sql)` for write operations (`INSERT`, `UPDATE`, `DELETE`, `CREATE TABLE`) and `db.query(sql)` for read operations (`SELECT`). In the Hot Previewer, uses Python's built-in `sqlite3`. On Android, compiles to the native `android.database.sqlite.SQLiteDatabase` API — no Java knowledge required.
- **`json_get(json_string, path)` helper**: Safely read values from JSON strings (from `https` responses or `db.query()`) using dot-notation paths. Supports nested objects (`"main.temp"`) and list index access (`"weather.0.description"`). Returns `""` safely on any error.
- **`input_field()` component alias**: New alias for `inputs()` with cleaner semantics for single-line text fields.

### Changed
- `db.query()` always returns results as a **JSON string array** to ensure seamless cross-platform compatibility between Python and Java.

### Fixed
- Fixed issue where UI labels would not update after database writes — callers must now explicitly call their UI refresh function after a `db.execute()` call.
- Fixed Java compilation error caused by `__name__ == "__main__"` blocks being incorrectly included in the generated Activity class.

---

## [0.9.3] — 2025-05-29

### Added
- **Named builds**: `apkpy build` now asks for your app name interactively, so the generated `.zip` file uses your chosen name instead of a generic one.
- **`image()` component**: Display `.png` and `.jpg` files natively as Android `ImageView`. ApkPy automatically copies assets into the correct `res/drawable` folder.
- **`storage` API**: Persist data across app sessions with `storage.set()`, `storage.get()`, `storage.delete()`, and `storage.clear()`. Compiles to native Android `SharedPreferences`.
- **`toast()` notifications**: Trigger native Android Toast messages from any function.
- **Radio button inputs**: `inputs("A|B|C", type="radio")` now generates a full native radio button group.
- **`box-shadow` in CSS**: Adds drop shadows to components.

### Changed
- **XML Layout Engine**: Completely rewritten from programmatic Java UI to native Android XML layouts. This resolves 99% of layout and alignment inconsistencies.
- **Hot Previewer calibration**: Now matches the exact screen dimensions of a Pixel 9 Pro for a more accurate preview.
- **`@keyframes` stability**: Fixed `margin-top` animation glitches during transitions.

### Fixed
- `justify-content` and `align-items` now correctly map to native Android `gravity` attributes.
- `border-radius` no longer causes layout crashes on certain Android API levels.

---

## [0.9.0] — 2025-04-10

### Added
- **Declarative CSS animations** with `@keyframes` syntax.
- Supported animation properties: `opacity`, `scale`, `margin-top`, `margin-left`.
- Animation cross-platform support: works in Tkinter Previewer and compiles to native Android XML.
- `container()` component for nesting and grouping UI elements.
- `parent=` parameter on all components for nested layouts.

### Changed
- Improved error messages when `writehere.py` is missing or contains syntax errors.

---

## [0.8.5] — 2025-03-01

### Added
- Multi-screen support with `Screen()` and `on_click_navigate()`.
- `declare_permissions()` for static AndroidManifest permissions.
- Runtime permission requests with `permissions.request()` and callback support.
- `type="password"`, `type="search"`, `type="checkbox"`, `type="range"` input types.

### Fixed
- Initial release of the Hot Previewer (Tkinter-based live preview).

---

## [0.1.0] — 2025-01-15

### Added
- Initial release of ApkPy.
- Basic `Screen`, `label`, `button`, `inputs` components.
- Single-Activity Android project generation.
- `apkpy start` and `apkpy build` CLI commands.
