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
| [`29_nfc_tags.py`](29_nfc_tags.py) | NFC status, foreground reading, one-shot text/URL writes, cancellation, settings and error recovery; simulated tags on desktop |
| [`30_contacts.py`](30_contacts.py) | People Desk — pick phone/email, search and get with read permission, native create/edit forms, settings and fictional desktop contacts |
| [`32_offline_queue.py`](32_offline_queue.py) | A background job that downloads a page, saves it in the database from the download's callback, and a screen that counts it through an observer |
| [`33_reusable_screens.py`](33_reusable_screens.py) | Three screens built by two functions -- a header and a card written once, a returned component updated by a button, cards unrolled from lists |
| [`34_sign_up_form.py`](34_sign_up_form.py) | A form that says what is wrong with it: help text under fields, required fields checked together with `validate()`, and rules of its own shown with `set_error()` |
| [`35_filter_sheet.py`](35_filter_sheet.py) | A bottom sheet with components in it -- a segmented button, chips, a field and two buttons -- that filters the list behind it and drags down to close |
| [`36_android_from_python.py`](36_android_from_python.py) | Android reached from Python: six `@native` functions -- vibrate, battery, the phone's name, its sensors, keep the screen on, open a page -- whose bodies are translated to Java and checked against `android.jar` when the app is built |
| [`37_the_rest_of_the_phone.py`](37_the_rest_of_the_phone.py) | Sixteen rows, one call each, past the app: a touch you can feel, a voice, dictation, a page over the app and one inside it, the calendar, the dialler, a message, a file saved where the person chooses, a download, print, the recorder -- and a link or a share that opens the app |
| [`38_outside_the_app.py`](38_outside_the_app.py) | What an app has outside its own screens, a row for every call: a widget on the home screen, a tile in quick settings, AdMob ads (banner, between two screens, for a reward, consent), a newer version from Google Play, and steps, heart rate and sleep from Health Connect |
| [`39_text_files.py`](39_text_files.py) | A journal kept in the app's own files: `files.write()` keeps the page, `files.append()` adds a line to a history of every save, `files.read()` brings both back the next time the app opens |
| [`40_timers.py`](40_timers.py) | A function run later, or again and again: a clock that ticks with `timer.every()`, a countdown that `timer.cancel()` pauses and `timer.running()` asks about, a search that waits for the typing to stop and a message that goes away, both `timer.after()` |
| [`41_network.py`](41_network.py) | Online or not, and over what: a banner that comes when the connection goes, messages that wait and are sent when `network.on_change()` says it is back, a download that waits until `network.metered()` is false. In the Previewer, click the connection in the status bar to take it away |
| [`42_display.py`](42_display.py) | The screen kept on, brighter, without its bars and which way up: a recipe switch for `display.keep_on()`, a ticket at `display.brightness(1)`, `display.orientation()` from a segmented control, and a player screen with `Screen(orientation="landscape")` that hides the bars when it opens. In the Previewer, Ctrl+Left and Ctrl+Right turn the phone |
| [`43_app_lock.py`](43_app_lock.py) | The app lock: a journal that locks a minute after you leave it with `app_lock.after(1)`, a "Lock now" button that is `app_lock.now`, and a banner for a phone with no screen lock (`"no_lock"`). Locked, the phone's own prompt opens it. In the Previewer, minimise the window to send the app to the background |
| [`44_classes.py`](44_classes.py) | Classes: a month's budget where `Expense` and `Income` extend `Entry` and each says how it moves the total, and `Budget` keeps the entries in a list, adds them up and writes itself out with `__str__`. Every name for an object sees the same changes, as in Python. Needs 1.14.1 |
| [`45_dataclasses_and_errors.py`](45_dataclasses_and_errors.py) | `@dataclass` and errors of your own: a pantry list where each line is a dataclass, and wrong input raises `NoName` or `BadAmount`, caught together as `PantryError` and shown on the screen. Needs 1.14.1 |
| [`photo_viewer/`](photo_viewer/) | Pictures that open over the whole screen and zoom: `image(zoom=True)` and `view_image()`. Run `make_assets.py` first: it draws the pictures |
| [`replicas/`](replicas/) | Four apps you know, rebuilt: a chat list and a conversation, a music home and a player with its own tracks, a photo feed whose posts are rows built from components, stories, and a ride sheet over a map. Run `make_assets.py` first |

**NFC version requirement:** example 29 needs ApkPy 1.9.0 or later. Use your own spare,
rewritable tag for writes; its previous contents will be replaced. No physical
tag is needed for the Previewer simulator. See the [NFC guide](https://repo-apkpy.pages.dev/guides/nfc/).

**Contacts version requirement:** example 30 also needs ApkPy 1.9.0 or later.
Use fictional data for testing. Picking one detail needs no broad
permission; Search/Get ask for read access. Create/Edit open the native editor
and do not guarantee a save. See the [Contacts guide](https://repo-apkpy.pages.dev/guides/contacts/).

## Practical note

The examples use small in-memory datasets so their behavior is easy to inspect.
In production, replace those lists with the results returned by your API,
SQLite database, WebSocket channel or push callback. ApkPy manages the native
interface and efficient collection updates; the application still owns its
backend cursor and conflict rules.

The examples are yours to start from: an exception at the end of the
[licence](../LICENSE) lets you copy them into an app of your own with nothing
of ApkPy's licence to carry along.
