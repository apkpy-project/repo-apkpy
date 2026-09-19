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
| `22_chat_composer.py` | Borderless field, a flex row of pills and a send/stop swap |
| `23_settings_rows.py` | Grouped rows with hairlines, tracked section headers and readable leading |
| `24_ask_an_api.py` | A JSON body, a long timeout, a user-supplied key and a Markdown answer |
| `25_appearance.py` | Dark, light or follow-the-system at run time, and why a hand-written colour stays put |
| `26_biometric_lock.py` | A vault behind the fingerprint, and what to say for each of the seven reasons a check can fail |
| `27_bluetooth_serial.py` | Both radios behind one screen: paired devices or a scan, then lines of text each way |
| `28_in_app_purchases.py` | A shop: a one-time unlock, a consumable, a subscription, and restoring what was already paid for |
| [`29_nfc_tags.py`](29_nfc_tags.py) | **1.9.0 unreleased:** NFC status, foreground reading, one-shot text/URL writes, cancellation, settings and error recovery; simulated tags on desktop |
| [`30_contacts.py`](30_contacts.py) | **1.9.0 unreleased:** People Desk — pick phone/email, search and get with read permission, native create/edit forms, settings and fictional desktop contacts |

**NFC version requirement:** example 29 needs the development library. The
current published 1.8.0 package does not contain `nfc`. Use your own spare,
rewritable tag for writes; its previous contents will be replaced. No physical
tag is needed for the Previewer simulator. See the [NFC guide](../docs/guides/nfc.md).

**Contacts version requirement:** example 30 also needs the 1.9.0 development
library. Use fictional data for testing. Picking one detail needs no broad
permission; Search/Get ask for read access. Create/Edit open the native editor
and do not guarantee a save. See the [Contacts guide](../docs/guides/contacts.md).

## Practical note

The examples use small in-memory datasets so their behavior is easy to inspect.
In production, replace those lists with the results returned by your API,
SQLite database, WebSocket channel or push callback. ApkPy manages the native
interface and efficient collection updates; the application still owns its
backend cursor and conflict rules.

ApkPy is proprietary software. See [LICENSE](../LICENSE) for the license terms.
