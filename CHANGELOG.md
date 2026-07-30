# Changelog

All notable changes to ApkPy will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.2.2] — Unreleased

### Added

- `prepend_items(items)` for stable top insertion without moving the visible
  record.
- `update_item(item_id, changes, key="id", optimistic=False)` and
  `remove_item(item_id, key="id", optimistic=False)` for keyed record changes.
- `merge_items(items, key="id")` for in-place live reconciliation without
  duplicate stable IDs.
- `commit(mutation_id=None)` and `rollback(mutation_id=None)` with first-state
  snapshots for optimistic transactions.

### Android and Previewer

- Generated RecyclerViews use targeted range/change/remove notifications.
- Multi-record merges and rollbacks dispatch a native `DiffUtil` result.
- Mutation helpers are conditionally emitted only when the new API is used.
- The Previewer preserves virtual scroll position and follows the same keyed
  transaction rules.

### Validation

- Added runtime tests for keyed merge, removal, commit, rollback and repeated
  changes in one optimistic transaction.
- Added generated-source tests for targeted adapter notifications,
  conditional `DiffUtil` output and optimistic history.

---

## [1.2.1] — Unreleased

### Added

- **Incremental virtual collections**: `virtual_collection()` now accepts
  `on_end_reached`, `on_refresh` and `prefetch`.
- **Efficient page insertion**: `append_items(items, has_more=True)` preserves
  the current records and scroll position while Android uses
  `notifyItemRangeInserted()`.
- **Explicit request completion**: `finish_load()` releases the loading latch
  after an empty response or recoverable error, and `refresh()` starts the same
  guarded callback as the top pull gesture.
- **End-of-results state**: `has_more=False` prevents new page requests until a
  refresh begins a new pagination generation.
- **Native Android refresh**: generated projects use
  `RecyclerView.OnScrollListener`; `SwipeRefreshLayout 1.2.0` is emitted only
  for collections with `on_refresh`.
- **Production Feeds demo**: the English `playground/writehere.py` example
  includes a list, grid, prefetch, refresh, deliberate failure, retry and
  no-more-results path.

### Changed

- The generated Android toolchain baseline is now AGP 8.6.1, Gradle 8.7 and
  compile SDK 35 so the stable SwipeRefreshLayout 1.2.0 artifact can compile.
  Projects without refresh keep their dependency graph free of
  SwipeRefreshLayout.

### Validation

- Added focused feed-state, generated-code and conditional-dependency tests.
- Verified the generated Java contains the native listener, duplicate-request
  latch and range insertion.
- Built the generated Android demo with Gradle successfully.

---

## [1.2.0] — 2026-07-27

### Added and documented

- **Native audio capability baseline**: consolidated the music features that
  already exist in ApkPy so evaluations do not mistake the player for a
  foreground-only demo. The current Android output includes a foreground media
  service, `MediaSession`, notification and lock-screen metadata and transport
  controls, audio-focus handling, queue navigation, shuffle/repeat, seeking,
  synchronized full-player bindings, a persistent mini-player, favourites,
  editable playlists and explicit offline downloads.
- **Player reliability behaviour**: documented guarded duration/position
  polling while `MediaPlayer` is unprepared, buffering state, one controlled
  retry of the same source after a preparation failure and the rule that an
  error must not trigger a skip storm through the queue.
- **Clear support boundary**: documented that image/artwork caching and explicit
  offline file downloads exist, while transparent audio caching, adaptive
  quality selection, guaranteed gapless playback, crossfade, DRM and resumable
  downloads with progress do not yet exist. Stream bitrate and quality are
  determined by the supplied source; ApkPy does not transcode audio.
- **New 1.2.0 release guide**: `RELEASE_1.2.0.md` begins with a complete
  native-player example and an implementation-oriented capability matrix.
- **Native documents without a WebView**: added `rich_text()` for exact inline
  spans, `markdown()` for headings, emphasis, links, code, quotes, lists,
  checkboxes and dividers, and `tree_view()` for recursive expandable data.
  Android emits selectable `Spannable` text and a `RecyclerView` containing
  only visible hierarchy rows; plain projects do not ship these helpers.
- **Runnable structured-content applications**:
  `examples/16_knowledge_base.py` combines rich spans, Markdown and a workspace
  hierarchy, while `examples/17_discussion_tree.py` demonstrates a formatted
  article and nested social discussion.

---

## [1.1.0] — 2026-07-16

### Added
- **1/9 — Global themes and reusable design tokens**: `Theme(...)` now supplies light/dark mode, primary and secondary colours, background, surface, text, border, error/success colours, radius, spacing and typography to the Previewer and generated Android resources. CSS can reuse the normalized values through `var(--primary)`, `var(--surface)`, `var(--text)`, and the other theme tokens. The cascade is deterministic: Theme → component selector → semantic variant → component ID.
- **2/9 — Material button variants and vector icons**: `button(..., variant=...)` supports `filled`, `outlined`, `tonal`, `text`, `danger` and `icon`. `icon=` uses matching font-independent geometry in the Previewer and generated Android vector drawables, avoiding missing emoji glyphs. Variant selectors such as `button:outlined` remain customizable through CSS.
- **3/9 — Responsive layouts**: `responsive(mobile=..., tablet=..., landscape=..., breakpoint=...)`, `row(...)` and `column(...)` arrange one component tree for each viewport. Builds generate native `layout`, `layout-land`, `layout-sw600dp` and `layout-sw600dp-land` resources. Preview presets include phones, tablets, landscape and a freely resizable responsive window.
- **4/9 — Advanced flex, grid and layered composition**: added `flex-wrap`, grow/shrink/basis, `align-self`, fractional grid tracks, `repeat()`, row/column spans, aspect ratios, absolute offsets and z-index. Simple screens remain ordinary native layouts; the optimized `ApkpyLayout` helper is emitted only for projects that require advanced geometry.
- **5/9 — Material cards and semantic surfaces**: `card()` supports `elevated`, `filled` and `outlined` surfaces, a ready-made title/subtitle/image/content/actions form, or arbitrary child composition. `card_action()` creates compact card actions, and semantic label variants include title, subtitle, body and overline. Android uses native `MaterialCardView`.
- **6/9 — Native app bars and collapsible media headers**: `app_bar()`, `sliver_app_bar()` and `action()` generate fixed Material toolbars, menus and collapsible image headers without placing toolbar Views in scrollable content. Android output uses `MaterialToolbar`, `AppBarLayout` and `CollapsingToolbarLayout`.
- **7/9 — Overlays, menus and pickers**: added `bottom_sheet`, `modal`, `menu`/`popup_menu`, `context_menu`, `snackbar`, `tooltip`, `date_picker` and `time_picker`. Definitions are lightweight until opened, expose callbacks and programmatic close methods, and map to native Material dialogs/menus on Android.
- **8/9 — Content states**: `skeleton`, `empty_state` and `error_state` share a screen region and switch through `show()`/`hide()` without rebuilding the component tree. Skeleton variants include music card, list, card and text. Animation helpers are generated only for Activities that use them.
- **9/9 — Smart images and avatars**: `image()` and `avatar()` now support local placeholders, network fallbacks, bounded caching, fade-in, aspect ratio, blur, tint and runtime source changes. Avatars add a circular crop and online/away/busy/offline badge. Network work runs away from the UI thread and stale responses are ignored.
- **Four English showcase applications**: Lumen (finance), Onda (wellbeing), Northline (travel) and Afterglow (music) demonstrate distinct visual systems rather than template recolours. Together they generate sixteen Android Activities.
- **Complete 1.1.0 release guide**: `RELEASE_1.1.0.md` documents all nine plan items with executable Python/CSS examples, explains native output and shows how the design system works with SQLite, REST, encryption and background audio.

### Fixed
- Kept Material button height, padding, corner radius, border, colour, pressed state and narrow-screen wrapping consistent between Previewer and Android.
- Replaced fragile emoji/font icons with Previewer vector geometry and generated Android vector drawables, including bottom navigation, toolbars and buttons.
- Prevented card and toolbar Activities from crashing during layout inflation by generating `Theme.App` from `Theme.MaterialComponents.DayNight.NoActionBar`, mapping the ApkPy palette to Material attributes and applying the theme in `AndroidManifest.xml`.
- Preserved Previewer input state while rebuilding bottom navigation and made tab changes persist correctly across separate Android Activities.
- Matched rounded corners for cards, containers, inputs, selects and switches across both renderers.
- Fixed the Previewer bottom sheet replacing the entire window with a black screen; the sheet now appears above the existing content.
- Reworked Previewer toasts into a compact Material capsule with vector status icon, responsive width and non-blocking placement.
- Corrected image crop, avatar clipping, aspect ratio, blur/tint handling and fallback behaviour, including the Android colour filter path that previously produced a solid purple block.
- Matched Android text wrapping for constrained buttons instead of keeping labels on one overflowing Previewer line.
- Kept generated Material helpers conditional so ordinary projects do not gain unused layout engines, image loaders, overlay helpers or skeleton animation code.

### Validation
- Installed the 1.1.0 wheel into clean Python environments and verified that `apkpy_lib` was loaded from `site-packages` rather than the development checkout.
- Generated and compiled four complete projects with JDK 21, Gradle 8.6 and Android SDK 34.
- Parsed 108 generated XML files, inspected 24 Java files and verified the expected Material theme, application ids, launcher Activities and version metadata.
- Installed the four APKs on a Pixel 9 Android emulator and opened all 16 Activities through their real bottom navigation without an AndroidRuntime fatal exception.
- Passed the complete transpiler suite: 146 tests passed, 0 failed.

---

## [1.0.0] — 2026-06-09

### Added
- **Native audio and background playback — `audio`**: build music and podcast experiences with `audio.play`, `pause`, `resume`, `stop`, `seek`, and `play_background`. Background playback uses an Android foreground `Service` + `MediaSession`, continues outside the Activity, publishes title/artist/artwork and transport controls to the notification and lock screen, and handles audio focus natively.
- **Playback queues and synchronized player UI**: `audio.play_playlist(sources, titles=..., artists=..., arts=..., start=...)` creates a queue with `next()`, `previous()`, `shuffle()` and `repeat()`. `audio.now_playing(progress=..., time=..., cover=..., title=..., artist=...)` binds normal ApkPy components to the active track and enables seeking; `audio.controls(...)` keeps ordinary buttons synchronized with playback state.
- **Persistent `mini_player(open=...)`**: add a now-playing bar above `bottom_nav` across the app. It follows the foreground media service and opens the chosen full-player screen when tapped.
- **Music favourites and playlists**: `audio.like_button`, `audio.liked_list`, `audio.add_to_playlist`, `audio.play_saved_playlist`, `audio.playlists_list`, `audio.edit_playlist`, `audio.playlist_editor`, `audio.remove_from_playlist`, and `audio.delete_playlist` provide persistent favourites and user-created playlists without requiring an app-specific database schema.
- **Rich media collections — `list_view(..., rich=True)`, `carousel`, and `grid`**: render native cards with remote artwork, title, subtitle and an optional `src` payload. Rich lists generate custom Android rows, carousels generate horizontal shelves, and grids generate an N-column `GridLayout`. The complete item is delivered to `on_click`; `set_items(..., image="field")` maps dynamic API/database artwork into rich rows.
- **Private file downloads — `files`**: `files.download(url, name, on_result=...)`, `files.exists(name)`, `files.path(name)`, and `files.delete(name)` support offline media and other downloaded assets. Downloads are asynchronous and stored in the Android app-private files directory.
- **OAuth 2.0 + PKCE — `auth`**: browser-based sign-in with provider defaults for Google, Spotify and GitHub or custom OAuth endpoints. `auth.login`, `is_logged_in`, `token`, `user`, and `logout` cover authorization, token persistence and normalized profile data. Android uses a generated deep-link Activity; the Previewer uses a localhost loopback redirect. No client secret is embedded in the APK.
- **SQLite transactions — `db.begin()`, `db.commit()`, `db.rollback()`**: group several `db.execute()` calls into one atomic, all-or-nothing unit. Everything between `db.begin()` and `db.commit()` is written to disk together; `db.rollback()` undoes everything since `db.begin()`, leaving the database exactly as it was. The classic use case is a transfer (debit one account *and* credit another — never just one), but it's also the right tool for any multi-row write that must not be left half-done, and it's much faster than committing each insert separately (SQLite flushes to disk once). Inside a transaction every `db.execute()`/`db.query()` shares a single connection, so atomicity is real. On Android this transpiles to native `SQLiteDatabase.beginTransaction()` → `setTransactionSuccessful()` → `endTransaction()`; a `rollback()` ends the transaction without marking it successful. In the Hot Previewer it uses a shared Python `sqlite3` connection with `commit()`/`rollback()`. Works in callbacks, at module level (`onCreate`), and in background `service` workers.
- **`db.last_insert_id()`**: returns the `rowid` (auto-increment id) of the row just inserted with `db.execute(...)`, with no extra `SELECT`. Use it right after an `INSERT` to learn the id the database generated (e.g. to reference the new row, or feed it as a `?` parameter to the next query). Works in any expression — f-strings, `set_value()`, query params. In the Hot Previewer it returns Python's `cursor.lastrowid`; on Android it transpiles to `SELECT last_insert_rowid()` on the same connection, giving the same value on both platforms. New example shipped in `writehere.py`: an atomic bank-transfer demo (RESET / TRANSFER / ROLLBACK) that shows balances staying consistent and the rolled-back movement never being persisted.
- **`for` loops — real Python iteration compiled to native Java**: plain `for` loops now work on Android. Three forms: `for x in ["a", "b"]:` (list literals and list variables), `for i in range(n):` (also `range(a, b)`), and `for row in rows:` where `rows` is the JSON returned by `db.query()` or an `https` response — `row["column"]` reads each field (a real dict in the Hot Previewer; safe `_jsonGet` access in the generated Java). Loops work inside callbacks, at module level (they run in `onCreate`), nested, and combined with `if`/`else`. `break` and `continue` are supported (they compile to native Java `break;`/`continue;`). Non-array/invalid JSON makes the loop run zero times on both platforms instead of crashing. Not yet supported: iterating dicts.
- **`crypto` — password hashing and encryption built in**: Protect sensitive data stored via `storage` (SharedPreferences) or `db` (SQLite) — both are readable by anyone who decompiles the APK or steals the files. No `hashlib`/crypto imports needed — the module is built into ApkPy, with zero external dependencies and no new permissions.
  - `crypto.hash_password(password, algo="sha256", iterations=200000)`: salted **PBKDF2** hash (`"pbkdf2-algo$iterations$salt$hash"`). Key stretching makes every brute-force guess cost 200,000 hashes instead of 1 — GPU cracking becomes ~200,000× slower. `crypto.verify_password(password, stored)` checks it with a constant-time comparison and returns a real boolean (safe in `if ok:`); it also accepts the legacy single-SHA format. On Android, PBKDF2 is generated as a manual `javax.crypto.Mac` loop (works on minSdk 24, bit-for-bit identical to Python's `hashlib.pbkdf2_hmac` — a hash created in the Previewer verifies on Android and vice-versa). `hash_password` works inside any expression (`storage.set(...)`, `db.execute(...)`, assignments, f-strings).
  - `crypto.encrypt(text)` / `crypto.decrypt(stored)`: two-way encryption for data you need to read back (notes, tokens, db fields). On Android, **AES-256-GCM with the key in the Android Keystore** — hardware-backed and non-extractable, even with root; decompiling the APK reveals no key. In the Hot Previewer, an equivalent authenticated stream cipher with a local device-key file. Values are per-device by design: a stolen database cannot be decrypted elsewhere. `decrypt` returns `""` for tampered, malformed or foreign-device values.
- **Automatic storage encryption**: `storage.set()` now encrypts every value before it touches the disk and `storage.get()` decrypts transparently — no code changes needed. The SharedPreferences XML (Android) / `apkpy_storage.json` (Previewer) only ever contains `enc1$…` ciphertext. Values saved in plain text by older versions are still read normally (automatic fallback).
- **Parameterized SQL queries — SQL injection protection**: `db.execute(sql, [values])` and `db.query(sql, [values])` now accept an optional list of parameters that fills the `?` placeholders with safe binding (also accepted as `params=[...]`). The values are bound by the SQLite engine itself instead of being concatenated into the SQL string — making SQL injection impossible and fixing queries that broke on apostrophes (`O'Brien`, `don't`). Works identically in the Hot Previewer (Python `sqlite3` placeholders) and on Android (`SQLiteDatabase.execSQL(sql, args)` / `rawQuery(sql, args)`). Calls without parameters keep working unchanged.
- **Full REST client — `https.put`, `https.patch`, `https.delete`**: the `https` API now covers all five HTTP methods, enabling full CRUD against any REST backend (Supabase, Firebase, Django, FastAPI...). `put`/`patch` take a body like `post`; `delete` takes none, like `get`. On a 4xx/5xx response the callback now receives the server's **error body** (instead of just an error message), in both environments. PATCH on Android falls back to `POST` + `X-HTTP-Method-Override: PATCH` (Android's `HttpURLConnection` doesn't accept PATCH natively); the Hot Previewer sends native PATCH. Works in callbacks and in background `service` workers. New example: `apkpy examples` -> [10] REST Client / `examples/13_rest_client.py`.
- **`set_items` accepts JSON — feed a `list_view` straight from SQLite or an API**: `my_list.set_items(json_rows, title="field", subtitle="field")` takes the JSON string returned by `db.query()` (or an `https` response body) and renders every row, mapping the chosen fields to the item's title and subtitle. Plain-value arrays also work; invalid JSON yields an empty list instead of crashing. Plain Python lists keep working as before. Also new: module-level calls to your own functions (e.g. `refresh()` at the bottom of the file) now compile into `onCreate`, so initial data loads when the app starts. Closes the data->UI loop (fetch rows -> show list -> tap -> detail). New example: `apkpy examples` -> [11] DB Notes List / `examples/14_db_notes_list.py`.
- **`spinner(id=..., screen=..., visible=True)`**: Native circular loading indicator — ideal for showing while `https.get()`, `db.query()`, or background work is in progress. Toggle it with `.show()` / `.hide()`. On Android, compiles to an indeterminate `ProgressBar` (color via CSS `color` → `indeterminateTint`; size via `width`/`height`); `.show()`/`.hide()` compile to `setVisibility(View.VISIBLE / View.GONE)`. Pass `visible=False` to start hidden. In the Hot Previewer, renders an animated rotating arc on a Canvas that starts/stops with `.show()`/`.hide()`.
- **`location.get_current(on_result=callback)`**: Read the device's GPS position. The callback receives `(success, lat, lng, city)` — latitude and longitude as strings, plus the resolved city name via reverse geocoding. On Android, compiles to `LocationManager.getLastKnownLocation()` (GPS, falling back to network) followed by `android.location.Geocoder` on a background thread; `ACCESS_FINE_LOCATION` and `INTERNET` are declared automatically and location is requested at runtime. In the Hot Previewer, a dialog asks for coordinates to simulate (defaults to Lisbon) and resolves the city via OpenStreetMap (Nominatim) in a background thread. Same Python code in both environments.
- **Remote images — `image("https://...")`**: `image()` now accepts a full URL. ApkPy detects the `http://` / `https://` prefix and loads the image at runtime in a background thread, so the UI never freezes. On Android, compiles to a background `Thread` + `HttpURLConnection` + `BitmapFactory.decodeStream(...)` → `setImageBitmap(...)` on the UI thread (the `INTERNET` permission is declared automatically; no Glide/Picasso dependency). In the Hot Previewer, the image is downloaded with `urllib` and a "loading…" placeholder shows until it arrives. All the same CSS (`width`, `height`, `border-radius`, `object-fit`, `opacity`, `box-shadow`, animations) applies to remote images.
- **`on_click_navigate(screen, data={})`**: Pass data when navigating between screens. Call `on_click_navigate(target, data={"key": value})` from a button command lambda or a `list_view` `on_click` lambda. On Android, compiles to `Intent.putExtra("key", String.valueOf(value))` + `startActivity(intent)`. In the Hot Previewer, stores the values in `screen._params` before rendering the screen.
- **`screen.get_param(key, default="")`**: Read a value that was passed via `data=`. On Android, compiles to `getIntent().getStringExtra("key")` (with a null-check ternary when a default is provided). In the Hot Previewer, reads from `screen._params`.
- **Module-level `set_value` for screen load**: Calling `lbl.set_value(screen.get_param("key"))` at module level (outside any function) causes the compiler to generate `setText(getIntent().getStringExtra("key"))` in the correct Activity's `onCreate` — so labels are populated automatically when the screen opens.
- **`bottom_nav(screens, labels=[], icons=[])`**: Native bottom navigation bar that links multiple screens. Pass a list of `Screen` objects, optional tab labels, and optional icon names (`"home"`, `"person"`, `"settings"`, `"search"`, `"list"`, `"add"`, `"star"`, `"bell"`, `"chart"`, `"message"`, `"heart"`, `"camera"`, `"info"`, `"circle"`). On Android, compiles to a `BottomNavigationView` with a `RelativeLayout` wrapper — each tab starts the corresponding Activity with `FLAG_ACTIVITY_REORDER_TO_FRONT` (no re-creation, no animation flash). Vector drawables and menu XML are auto-generated — no icon font or image assets needed. Bar background is `#1E293B`; active icon/label is white, inactive is grey; all tabs always visible (`labelVisibilityMode="labeled"`). Each Activity overrides `onResume()` with a guard flag to restore the correct selected tab on return. In the Hot Previewer, renders a styled dark bottom bar with an active-tab indicator line and label highlight; clicking any tab navigates instantly.
- **`Screen(scroll=True)`**: Makes the entire screen vertically scrollable. All components — labels, inputs, buttons, and lists — scroll together as a single page. In the Hot Previewer, the screen becomes a scrollable canvas; scroll with the mouse wheel from anywhere (no need to hover a specific widget). On Android, compiles to a `NestedScrollView` wrapping a `LinearLayout` with `fillViewport="true"`. The scrollbar is intentionally hidden in the Previewer to match Android's default behaviour.
- **`list_view(items, id=..., screen=..., on_click=...)`**: Native list component with full cross-platform support. Accepts a list of strings or dicts with `"title"` and `"subtitle"` keys. In the Hot Previewer, renders as a styled scrollable canvas with title + subtitle rows and mouse-wheel scroll support. On Android, compiles to a native `ListView` backed by an `ArrayAdapter` (when `scroll=False`) or to `TextViews` inside a `LinearLayout` container (when `scroll=True` — avoids nested scroll conflict). CSS properties `color`, `background-color`, `border-color`, and `height` are all applied. Items can be updated at runtime with `list_view_var.set_items(new_list)`.
- **`list_view` lambda `on_click`**: `on_click` callbacks can now be written as inline lambdas — `on_click=lambda item: toast(item["title"] + ": " + item["subtitle"])`. The lambda is compiled to a `pythonCallback_*` method on Android. `item["title"]` and `item["subtitle"]` correctly extract their respective parts from the stored string by splitting on the ` — ` separator, matching the Python preview exactly.
- **Variable reference in `list_view` items**: Passing a module-level list variable as items (`list_view(my_items, ...)`) is now fully resolved at compile time — the static items from that variable are correctly emitted as `lst_items.add(...)` calls in `onCreate`, instead of producing an empty list.

### Fixed
- Fixed the app crashing on launch when a `db.query()` referenced a column or table that doesn't exist (e.g. after reinstalling a demo that left an older table with a different schema in `apkpy_app.db`). The generated `_sqliteQuery` helper compiled the SQL outside its try/catch, so an invalid query threw `SQLiteException` instead of failing gracefully. The whole query now runs inside the try/catch and returns an empty result (`[]`) on error — the app keeps running and the error is logged to Logcat.
- Fixed a Java compilation error (`cannot find symbol`) when a function used `component.get_value()` on a component that belongs to a different screen. Callback methods are emitted into every Activity; on screens that don't own the component, the variable assignment was silently dropped while later uses of the variable remained. The variable is now declared as an empty string on those screens (the callback is never invoked there).
- Fixed `list_view` rendering as a large white box on Android when no `background-color` or `height` was set. The list now defaults to a transparent background (inheriting the screen, matching the Previewer) instead of white, and to `wrap_content` height (sizing to its items) instead of a fixed 300dp — eliminating the empty white area below the items.
- Fixed `label` alignment parity between the Hot Previewer and Android. On screens without `display: flex`, labels were centered on Android but left-aligned in the Previewer; they are now left-aligned (with a 16dp indent) on both. Labels on a `display: flex` screen stay centered.
- Fixed components appearing "glued together" / overlapping on Android when no CSS `gap` was set. The Hot Previewer always renders a few pixels of breathing room between stacked components, but the Android generator only added spacing when a `gap` was explicitly defined — so on screens without `gap`, buttons and labels were rendered with zero margin and could overlap. Vertically-stacked siblings now get a 6dp baseline `margin-top` when no `gap` is set (the `gap` value still takes precedence when present), matching the Previewer's spacing.
- Fixed the loading `spinner` jumping to the bottom of the screen in the Hot Previewer after a `.hide()` / `.show()` cycle. Root cause: re-showing re-packed the spinner's container, which Tkinter appends at the end of the parent's layout order. The container is now packed once in its correct position and `.show()` / `.hide()` only toggle the inner canvas, so the spinner always reappears exactly where it was declared (matching Android).
- Fixed `bottom_nav` tab bar appearing white on Android — added `android:background="#1E293B"` and a `res/color/nav_item_color.xml` color-state-list so active icons/labels are white and inactive are grey.
- Fixed `bottom_nav` tabs other than the selected one appearing to disappear or shrink on Android — added `app:labelVisibilityMode="labeled"` to keep all tabs the same size at all times (Material Design's default `auto` mode hides labels for non-selected items with 3+ tabs).
- Fixed `bottom_nav` requiring two taps to navigate: the first tap briefly showed the target screen then reverted. Root cause: when an Activity came back to the foreground the `BottomNavigationView` still showed the previously-selected (wrong) tab; tapping the same tab again triggered the correct navigation. Fix: each Activity now overrides `onResume()` to restore the correct selected tab, guarded by a `_navReady` boolean flag so the `setOnItemSelectedListener` does not accidentally trigger a new navigation during the restore.
- Fixed `bottom_nav` not placing `res/menu/bottom_nav_menu.xml` and `res/color/nav_item_color.xml` in the correct folders when running `apkpy build` — the build command now creates `app/src/main/res/menu/` and `app/src/main/res/color/` automatically.
- Fixed `list_view` inside a scrollable screen not scrolling on Android. The previous `ListView`-inside-`NestedScrollView` approach is fundamentally broken on Android (the inner `ListView` intercepts all touch events). The fix replaces `ListView` with a `LinearLayout` container whose items are added as `TextView`s at runtime — an `updateXxxList()` helper method is generated for this. This is the same approach recommended by Google for list-in-scroll layouts.
- Fixed `inputs(type="range")` (`SeekBar`) generating `setText()` in `set_value()` and `getText()` in `get_value()`, causing Gradle build errors. It now uses `setProgress(Integer.parseInt(...))` and `String.valueOf(getProgress())` respectively.
- Fixed `list_view` `on_click` lambda being silently dropped — only named function callbacks worked before. Now any lambda is compiled to an inline `pythonCallback_*` method and the `setOnItemClickListener` / `setOnClickListener` is always generated.
- Fixed `list_view` items always appearing with black text on Android regardless of the CSS `color` property. A custom `ArrayAdapter` subclass with `getView()` override is generated to apply `tv.setTextColor(...)` and `tv.setBackgroundColor(...)` per item (non-scroll mode), and the `updateXxxList()` method applies both directly to each `TextView` (scroll mode).
- Fixed `list_view` `on_click` toast showing the item string duplicated (e.g. `"08/06/2026 — ...: 08/06/2026 — ..."`) when the lambda used `item["title"]` and `item["subtitle"]`. Both now correctly extract title and subtitle from the stored `"title — subtitle"` string.
- Fixed class-level instance field scoping for `list_view` internals (`lst_items`, `lstAdapter`) — these were generated as `final` local variables inside `onCreate`, making them inaccessible from `pythonCallback_*` methods. They are now declared as `private` instance fields on the `Activity` class.
- Fixed `on_click_navigate(screen, data={...})` inside a `list_view` `on_click` lambda generating an empty `pythonCallback_*` method on Android. Root cause: `_gen_cmds_local` (the code generator for callback methods with parameters) was missing the `navigate` case that `_gen_cmds` already handled. Fix: added the `navigate` case to `_gen_cmds_local`.
- Fixed `screen.get_param()` values not appearing in labels in the Hot Previewer. Root cause: `lbl.set_value(screen.get_param("key"))` runs at module load time when `screen._params` is still empty, so labels were always set to `""`. Fix: `get_param()` now returns a lazy `_ParamRef` object; `set_value` stores the binding, and `render_screen` re-evaluates all bindings before drawing so labels always reflect the current params.
- Fixed `list_view` with a `height` CSS property (e.g. `height: 400px`) showing a large empty colored box on Android when the number of items is smaller than the fixed height. Root cause: the `ListView` respects the fixed `android:layout_height`, leaving visible empty space filled with the list's `background-color`. Fix: remove the fixed `height` from the list style and let the `ListView` use `wrap_content` so it sizes to its content.

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
