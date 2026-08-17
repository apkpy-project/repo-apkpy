# ApkPy examples

This folder contains complete, runnable ApkPy apps. Every example can open in
the desktop Previewer and can also be transpiled into a native Android project.

## Run an example

```bash
python -m pip install --upgrade apkpy
python 18_social_feed.py
```

To build one example for Android, copy it to the `writehere.py` file of an
ApkPy project and run:

```bash
apkpy build
```

## Example index

| File | Concepts covered |
| --- | --- |
| `01_hello_world.py` | `Screen`, labels, buttons, toasts and basic styling |
| `02_multi_screen.py` | Multi-screen navigation and input types |
| `03_storage.py` | Local storage and initial state |
| `04_coffee_haven.py` | Complete ordering app with images and animations |
| `05_permissions.py` | Runtime permission requests |
| `06_background_and_sharing.py` | Background work, notifications, sharing and clipboard |
| `07_camera_and_gallery.py` | Camera and gallery result callbacks |
| `08_alert_and_confirm.py` | Alerts, confirmations and stored state |
| `09_location.py` | Device location and reverse geocoding |
| `10_network_images.py` | Remote images |
| `11_spinner.py` | Native loading state around an HTTP request |
| `12_secure_login.py` | Salted password hashing and local storage |
| `13_rest_client.py` | REST CRUD operations and error handling |
| `14_db_notes_list.py` | Feeding SQLite and HTTP JSON into a list |
| `15_for_loops.py` | Lists, ranges, database rows and API responses |
| `16_knowledge_base.py` | Native rich text, Markdown and expandable trees |
| `17_discussion_tree.py` | Formatted articles and nested discussions |
| `18_social_feed.py` | Pagination, prefetch, refresh and live prepend |
| `19_product_catalog.py` | Virtual grid, SKU merge and optimistic removal |
| `20_chat_history.py` | Older-message prepend, local sends and delivery state |
| `21_data_core_notes.py` | Typed SQLite, async CRUD, refresh and explicit migration |

## Practical note

The examples use small in-memory datasets so their behavior is easy to inspect.
In production, replace those lists with the results returned by your API,
SQLite database, WebSocket channel or push callback. ApkPy manages the native
interface and efficient collection updates; the application still owns its
backend cursor and conflict rules.

ApkPy is proprietary software. See [LICENSE](../LICENSE) for the license terms.
