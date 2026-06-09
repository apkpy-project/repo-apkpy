# Examples — README

This folder contains complete, runnable ApkPy example apps.

## How to run an example

1. Install ApkPy:
   ```bash
   pip install apkpy
   ```

2. Run the example directly to preview it on your computer:
   ```bash
   python 01_hello_world.py
   ```

3. To build it as a real Android project:
   ```bash
   apkpy build
   ```
   Copy the example file to a new `apkpy start` project folder, or just run `apkpy build` from the examples directory.

---

## Example List

| File | Concepts Covered |
| :--- | :--- |
| `01_hello_world.py` | `Screen`, `label`, `button`, `toast`, basic CSS |
| `02_multi_screen.py` | Multi-screen navigation, `on_click_navigate`, input types |
| `03_storage.py` | `storage.set()`, `storage.get()`, `storage.clear()`, auto-load on start |
| `04_coffee_haven.py` | Full app: `image`, `radio`, storage persistence, animations, navigation |
| `05_permissions.py` | `declare_permissions`, `permissions.request()`, runtime callbacks |
| `06_background_and_sharing.py` | `service.every()`, `service.once()`, `service.cancel()`, `notify()`, `share()`, `clipboard.copy()` |
| `07_camera_and_gallery.py` | `camera.capture()`, `gallery.pick()`, async `on_result(success, path)` callbacks |
| `08_alert_and_confirm.py` | `alert()`, `confirm()`, async `on_result(confirmed)` callback, storage integration |

---

> **Note**: These examples are provided as-is for educational purposes. ApkPy is proprietary software — see [LICENSE](../LICENSE) for details.
