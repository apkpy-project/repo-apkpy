# Changelog

All notable changes to ApkPy will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

## [1.6.0] - 2026-09

Almost everything here began the same way: something did not work, and nothing
said so. Full notes in [Version 1.6.0](docs/version-1.6.0.md).

### Added -- the app now says what it could not do

- **`U2033`** -- Python with no translation stops the build and names the
  construct, instead of compiling to the empty string. Separates a gap ApkPy
  has not filled (`re`, `json.dumps`, `base64`) from a wall that cannot exist
  on a phone (`requests`, `numpy`, `os`), and points at the ApkPy API that
  covers the same ground. Also catches a mistyped helper, `print()`, and a
  modal opened above the line that creates it.
- **`try` / `except` / `finally`** -- the body used to be dropped whole. One
  handler, deliberately: Python's exception types have no equivalent where
  every value is text, so a second one is refused with its reason rather than
  half-honoured. `except ... as e` binds a String.
- **`items.append(x)`**, plus reading a list back: indexing with Python's
  negative indices, `len()`, and `for`. A module-level list the app appends to
  is now one list for the whole app, as it is in Python.
- **`math`**, with `abs`, `min`, `max` and `sum`. Only names where Java's
  answer is Python's; `log2` and `inf` are left out with their reasons.
- **The list of translated Python** now exists, on Compatibility and limits.

### Added -- hardware, money and business

- **`bluetooth` and `ble`** -- both radios, the same four verbs and the same
  result contract. Classic declares no location permission at all; BLE defaults
  to the Nordic UART Service. Ten reasons, never an empty string. Verified
  against a real device.
- **`billing`** -- one-time unlocks and subscriptions, acknowledged before
  success is reported, with purchases completed while the app was closed
  settled on the next launch. Compiled and reviewed; never sold.
- **`translations()` / `t()` / `language`** -- each language becomes its own
  `res/values-<tag>/` folder, the phone picks by locale, and `language.set()`
  switches while the app runs.
- **`crash.last()` / `crash.clear()`** -- the previous crash, kept where the
  next launch can read it. No vendor chosen, no endpoint invented.
- **`scan.code()`** -- barcodes and QR codes with **no CAMERA permission**.
- **`app.version_code()` / `version_name()` / `open_store()`** and
  `modal(dismissable=False)`, which together are a forced update without a
  protocol imposed on you.
- **`https.pin()`** -- certificate pinning as configuration, with two pins
  required. The Previewer opens a real handshake and prints the live pin when
  it does not match.
- **`describe=`** on components, and a `U2035` accessibility report during the
  build: undescribed images, unlabelled icon buttons, text below WCAG contrast,
  tap targets under 48dp.
- **Encryption that travels** (`crypto.encrypt(password=)`, a standard
  PBKDF2 + AES-GCM format), `crypto.totp()` verified against RFC 6238's
  vectors, plus `token()`, `hash()`, `hash_file()` and `secure_screen()`.

### Fixed

- **Auto-backup was emptying people's data.** Values are encrypted with a key
  in the old phone's Keystore, which does not travel, so a restored app read
  every one of them as empty and reported it as never saved. The encrypted
  store and login token are now excluded from cloud backup and device transfer.
- **`round(2.5)`** gave 2 in the Previewer and 3 on the phone. Over 4001
  values the old rule disagreed with Python on 1000 of them.
- **Decimals printed differently on the two sides** -- `math.pow(10, 8)` was
  `1.0E8` on the phone and `100000000.0` on the desktop. Proven against
  `repr()` across 90 022 values.
- **`math.floor(2.7)` printed `2.0`**; floor, ceil and trunc return an int.
- **`math.sqrt(-1)` returned NaN** and put that word on screen, where Python
  raises. Both sides now raise.
- **Indexing a list generated invalid Java** (`(x)[Integer.parseInt(...)]`).
- **`set_items()` inlined the original list**, so the screen kept showing the
  starting items after the list had grown.
- **`label(MSG)` and `label("a" + "b")` produced an empty attribute** -- the
  text showed in the Previewer and nothing on the phone.
- **`background-color` on a label** reached the Previewer and vanished on the
  phone: the `TextView` never carried a background, so dark text on a light
  band came out invisible on the device.
- **Apps target API 35** (required by Play) and every screen root now declares
  `fitsSystemWindows`, so Android 15's enforced edge-to-edge does not hide the
  first line under the status bar.
- **Two shipped examples were broken**: `22_chat_composer.py` appended to a
  list, which did nothing, and `23_settings_rows.py` opened a modal declared
  below its own button.


### Added

- **`bluetooth` and `ble`** -- talking to hardware over both Bluetooth radios,
  with the same four verbs and the same result contract: `devices()`/`scan()`,
  `connect()`, `send()`, `disconnect()`. Lines of text out, lines of text back.
- **Classic declares no location permission at all.** `devices()` lists paired
  devices rather than scanning, because an RFCOMM socket needs a bonded device
  anyway and pairing belongs to system Settings. An app that only talks to a
  printer should never have to ask where its user is. BLE has no such choice --
  devices advertise -- so its scan grant is capped at API 30 and carries
  `neverForLocation` above it.
- **`ble` defaults to the Nordic UART Service**, which is what an ESP32, a
  micro:bit or an HM-10 exposes, so the common case names no UUIDs. Others are
  named in 16-bit shorthand or in full, expanded identically on both runtimes.
- **The permission and the radio are asked for, not assumed.** If the
  permission is missing the app asks and resumes what you called; if Bluetooth
  is off it offers Android's own prompt to turn it on. Either refusal is
  remembered, so a second tap reports `denied` or `off` instead of reopening
  the dialog.
- **Ten reasons, never an empty string** -- `off`, `unsupported`, `denied`,
  `not_paired`, `not_found`, `unreachable`, `no_service`, `not_connected`,
  `lost`, `failed`. Both runtimes read one table, and the generated Java's
  `switch` is emitted *from* it.
- `terminator=` on `send()`: `newline`, `return`, `crlf`, `none`, or the
  characters. Sending the wrong line ending is the usual reason a board never
  answers.
- BLE writes are queued, so several `send()` calls in a row arrive in order
  instead of the second being refused -- GATT allows one operation at a time.
  A connect that never answers times out with `unreachable` rather than
  hanging forever.
- `bluetooth`, `link`, `fingerprint`, `lock` and `lock_open` in the icon
  catalogue. **70 names.**
- The Previewer offers one openly simulated device and a monitor you drive by
  hand: what the app sends appears in it, what you type arrives at `on_line`.
- **The link outlives the screen.** It lives in a generated
  `ApkpyBluetooth` / `ApkpyBle` class rather than on an Activity, so
  connecting on one screen and talking on the next works. A screen that
  wants the lines calls `connect()` again -- already-open is free, and it
  simply adopts the new callback. A screen owns only its callback: being
  destroyed stops it receiving, it does not close the radio.

- **`billing`** -- Google Play in-app purchases and subscriptions.
  `prices()`, `buy()`, `subscribe()`, `owned()` and `consume()`, with the same
  `(ok, value)` contract as everything else.
- **Every purchase is acknowledged before your callback is told it worked**,
  including one that completed while the app was closed: that case never
  reaches the live listener, so `owned()` settles anything it finds
  unacknowledged.
  Google refunds anything an app leaves unacknowledged for three days, so this
  is not a call you can forget: `consumable=True` consumes instead, which
  settles the same clock and is what lets something be bought again.
- `pending` is its own word, not a success and not an error: a slow payment
  method has started and nothing should be unlocked yet. So is `owned`, which
  means they already paid.
- Prices are asked of Play rather than written down, so they arrive in the
  person's own currency and locale. A subscription reports the offer that
  `subscribe()` will actually launch.
- `owned()` reports every purchase with its `token`, because on-device state
  can be faked and a server checking that token is the only real proof.

### Fixed

- A permission whose name carries a package -- `com.android.vending.BILLING` --
  was written as `android.permission.com.android.vending.BILLING`, and turned
  into a Java identifier with dots in it. The namespace is only added to a
  bare name now, and the identifier uses the last segment.
- `AndroidManifest.xml` could only write a permission's name. Bluetooth needs
  `maxSdkVersion` and `usesPermissionFlags`, so an entry may now carry
  attributes -- and everything that builds a Java identifier from one reads the
  bare name, which a real build caught after brace-counting did not.

### Known limits

- **Checked on a phone, up to the point a peer is needed.** An Android
  emulator has no Bluetooth radio, so this was exercised on a real device
  against a smartwatch: the permission and enable prompts appear, a scan finds
  real devices, connecting establishes the link and discovers services, and
  every failure word comes back correctly -- including `unreachable` after the
  fifteen-second timeout. **Not yet proven:** lines arriving through
  `on_line`, `send()` reaching a peer, and the write queue under real timing.
  Those need a board that speaks back.
- Line-oriented text only, one device at a time, client only, and pairing stays
  in system Settings.

---

## [1.5.0] — 2026-08-31

Two things, and they turned out to be the same thing.

The first is **the fingerprint check**: `biometrics.unlock(...)`, one call with
one result. The second is **the two renderers agreeing** — a shared vocabulary
for sizes and surfaces, and the places where the Previewer and the Android
generator had quietly picked different numbers for the same idea.

They belong together because the biometric prompt is the sharpest case of the
same problem. Android draws that dialog itself, so an app supplies three
strings and the platform does the rest — and the only thing the two runtimes
*can* agree on is the words and the result. Getting that right meant giving the
seven possible outcomes one shared table, which is exactly what the type ramp
and the surface planes do for sizes and colours.

A value with no shared name is a value each side is free to guess at. Both
sides guessed reasonably. That is precisely why nobody noticed.

### Added

- **`biometrics.unlock(...)`** -- the fingerprint or face check, as one call
  with one result. Android draws this dialog itself, so the API is the three
  strings it lets an app choose: `title`, `subtitle` and `cancel_text`. Plus
  `allow_pin=True` for the device PIN, pattern or password, which drops the
  cancel button because `PromptInfo.Builder` refuses a negative button
  alongside `DEVICE_CREDENTIAL`.
- `on_result` receives `(success, reason)`, and `reason` is one of seven
  words -- `ok`, `cancelled`, `no_hardware`, `not_enrolled`, `unavailable`,
  `lockout`, `failed` -- **never an empty string**. Both runtimes resolve them
  from one table, so an app that says "try again" for a missing sensor is a
  bug you can write, not one the library hands you. A scan that simply does
  not match is not a result: the prompt stays open on both sides.
- The Previewer draws a **replica** of the system dialog from the same three
  strings. Click the fingerprint to scan, right-click it for a bad scan,
  Escape to cancel. The desktop hint sits on the scrim, outside the card, so
  the card stays a copy of what the phone shows.
- `fingerprint`, `lock` and `lock_open` in the icon catalogue, with
  `biometrics`, `touch_id` and `unlock` as aliases. **68 names.**
- `USE_BIOMETRIC` is declared automatically, and
  `androidx.biometric:biometric:1.1.0` is added only to an app that asks for
  the prompt. An app that never mentions it generates the project it generated
  before -- no interface, no runtime, no permission, no dependency.

- **A type ramp.** `--text-xs`, `--text-sm`, `--text-base`, `--text-lg`,
  `--text-xl`, `--text-2xl` and `--text-3xl`, resolving to **11, 12, 14, 16,
  20, 24 and 32** at the default `Theme(font_size=14)` and scaling with it.
  The steps are Material's own sp values, **not** a geometric series: one
  ratio produces 29.3 where the platform says 32, and each renderer rounds it
  differently. Across the 25 shipped examples there were **17 distinct font
  sizes**, with 13px, 14px and 15px accounting for 32 uses between them --
  the same intent written three ways.
- **`--leading-tight`, `--leading-normal` and `--leading-loose`** (1.2, 1.45,
  1.7). `line-height` already read a bare number as a multiple of the font
  size on both sides, so these ride on machinery that was already correct.
- **Three planes: `--surface-low`, `--surface-high` and `--border-subtle`.**
  A card that has to sit on a surface, a well that has to sit under one, and a
  divider that should not shout. When the app declared its own
  `surface`/`background`/`border`, all three are **derived from those
  colours** rather than falling back to Material's palette -- otherwise a warm
  theme grows a cold grey plane it never asked for. `--surface-high` is the
  surface 6% toward the text, `--surface-low` is 55% of the way to the
  background, and `--border-subtle` sits 35% from the surface toward the
  border, which is where Material puts `outlineVariant` in both modes.
- Like every other theme token, the three new colours are written into layouts
  and drawables as **resource references**, so `values-night/` answers them
  and `appearance.set()` moves them.
- `U2031`: a token used in a slot of the wrong kind. `--text` is a colour and
  `--text-lg` is a size, three characters apart. A size in a colour slot dies
  in `parseColor` when the screen opens; a colour in a size slot is worse --
  `#211F26` silently becomes 21px and the app just looks wrong. A composite
  value like `0 3px 8px var(--border)` is left alone.
- `U2029`: a stylesheet property no renderer reads is reported by name, with
  the closest match and a link to the table. `frobnicate: 3px` used to
  transpile clean, and so did `elevation`, `transform`, `overflow` and
  `background` -- four names a person reaches for out of browser habit, all of
  them dropped when the layout was written. That looks like the *value* not
  working rather than the *name* not existing, which is why it goes unnoticed:
  designing is a loop -- try, look, adjust -- and half the loop returning
  nothing with no message turns it into guessing. It is a warning, not a
  failure, the way an unknown icon name is.
- The full stylesheet vocabulary is now a table in the docs, generated from
  the same set the two renderers read, so it cannot drift from what actually
  works. **87 properties.**

### Fixed

- The prompt reached for `ui._app.root` to find its window. `ui._app` is a
  lazy proxy, so *asking* it builds the Previewer -- which would have opened
  an empty window from `apkpy build` alone. It now checks whether one was
  constructed before touching it, the same guard the motion work needed.

- **`label("...")` with no stylesheet at all was 14px in the Previewer and
  16sp on Android.** Two literals written into two files at different times,
  each defensible on its own, and invisible because "body text" had no shared
  name for the two sides to disagree about. It is the most used component in
  the library, so the gap was in every app ever built with it. Both sides now
  read the same step of the ramp; **the phone's number wins**, so no compiled
  app changes.
- **The active tab's label in the bottom bar was bold in the Previewer and not
  on the phone.** Material's `Widget.MaterialComponents.BottomNavigationView`
  points `itemTextAppearanceActive` *and* `itemTextAppearanceInactive` at the
  same `textAppearanceCaption` -- 12sp, weight normal -- so on the device only
  the tint changes, and the state is carried by the pill and the filled icon.
  The desktop was adding a third signal the phone does not have. The same line
  also asked Tk for ten *points*, which is 13.3px at 96dpi, where the phone
  renders 12sp. Previewer-only: the generated XML is unchanged.
- `box-shadow` on a `container` drew a shadow in the Previewer and nothing on
  the phone. The container branch never asked for `android:elevation` -- the
  card and the image did -- so the same declaration meant two different things
  depending on which runtime read it.
- And asking was only half of it: a `ViewGroup` clips its children to its
  padding box, so a shadow was drawn and then cut off exactly where it starts.
  The parents of anything that asks for a shadow, and the screen root, stop
  clipping. **Cards have carried `box-shadow` in the theme defaults since the
  beginning and have been having their shadow clipped away all along**, so an
  app that uses `card` will look slightly different -- it now gets the shadow
  it always asked for. An app with no shadow anywhere generates the XML it
  always generated.
- `padding` with three or four values reached the Previewer whole and the
  compiler truncated it to two: `padding: 0 20 24 20` came out as
  `0 20 0 20` on the phone, and the bottom silently disappeared. Both sides
  now read one, two, three and four values the way CSS reads them.
- `padding-top`, `padding-right`, `padding-bottom` and `padding-left` were
  read by neither renderer, despite appearing in the shipped examples. They
  are read by both now, and overlay the shorthand.

---

## [1.4.0] — 2026-08-27

Two batches that turned out to be one. An app that can hold a conversation
with an API -- a request body that keeps its types, a timeout long enough for
something that thinks first, an answer rendered as Markdown in a row that
takes the height it needs -- and an app that stops looking like every other
app built with the same tool: a drawer, a settings row, a typeface of your
own, and control over tracking, leading and alignment.

They are one release because they are the same problem seen twice. An
assistant app is not hard to build; it is hard to make look right, and every
shape it needed was missing.

And an app that looks like yours has to keep looking like yours in the other
mode, so the release ends where it had to: colours that stop being literals
in a compiled layout, and a switch that changes them while the app runs.

### Added

- `appearance.set("dark" | "light" | "system")` and `appearance.get()`: the
  app changes its colours while it runs, and opens the way it was left.
  Android reads `values/` or `values-night/` and `AppCompatDelegate` picks;
  the Previewer swaps the theme and re-renders. Different machinery, and the
  same two palettes, because both are built from the one `Theme` the app
  declared.
- A colour that came from a theme token is written into layouts, drawables and
  the generated Java as a **resource reference** rather than as a literal. A
  two-screen app went from 472 literal colours to 98, and what is left is what
  should be left: mixed shades, transparents, and the colours the author wrote
  by hand.
- `Theme.counterpart()`: the same theme in the other mode. The accent carries
  over and the surfaces flip -- a background chosen at `#1B1B19` was chosen
  *because* the mode was dark, so carrying it into light would produce a light
  mode that is still dark, which is a switch that appears to do nothing.
- The status bar's clock and battery follow the mode. They are drawn by the
  system over whatever the app puts behind them, and deciding light-on-dark at
  build time left them invisible the moment the app switched. The answer comes
  from the same resource qualifier the colours do.
- `dark_mode`, `light_mode` and `contrast` in the icon catalogue -- an
  appearance screen needs a moon, a sun and a half-filled circle, and the
  catalogue had none of the three. **65 names, 96 with aliases.**

- `U2028`: a stylesheet asking for a theme token that does not exist is
  reported by name, with the closest match and the full list of tokens. It
  used to resolve to *itself* -- the literal text `var(--muted)` travelled
  into the layout XML and surfaced forty seconds later as an AAPT link failure
  whose stated cause is about stale generated files. Raised in the one module
  both runtimes read, so whichever you run first is the one that tells you.
- `scroll_to_end()`, `scroll_to_top()` and `scroll_to_item(id, key="id")` on a
  virtual collection. Adding a row never moved the viewport, which is right for
  a feed and wrong for a conversation: you send a question and end up looking
  at your own question while the answer grows below the fold. The scroll is
  animated over the duration the theme's `motion` preset gives the `nav`
  moment, out of the table both runtimes read, so `motion="none"` makes it a
  jump on the desktop and on the phone alike.
- An `avatar` slot in a collection's `template` draws a circle with up to two
  initials taken from its value, over a colour that value picks. It is what
  separates a list of paragraphs from a conversation: two speakers you tell
  apart at a glance. One palette decides the colour -- read directly by the
  Previewer, written into the generated Java as a literal by the compiler --
  so the same name cannot be orange on one side and green on the other. An
  empty value hides the circle rather than leaving a coloured hole.
- CSS `code-copy: button` puts a tappable **Copy** under every fenced code
  block, in a `markdown()` component and in a collection's `markdown` slot. It
  copies that block and nothing else -- not the paragraph above it, not the
  whole message. A block of code you cannot copy is a block of code you retype
  by hand. On Android 13 and later the system shows its own confirmation for
  every copy, so the app stays quiet rather than talking over it.
- CSS `max-rows` on a `type="textarea"`: `rows` is where the field starts and
  `max-rows` is where it stops growing, and between the two it follows the
  text. One line is the right start for a reply box; two fixed lines are half
  an empty composer waiting. Without `max-rows` the ceiling is what it always
  was.
- `virtual_collection(item_height="auto")`: each row wraps its own content
  instead of every row taking the same measured-out height. A conversation
  needs it -- one fixed height gives "yes" the same space as a twenty-line
  answer, so one floats in a void and the other is cut off mid-sentence. Text
  also stops being clipped to a single line unless the stylesheet says
  otherwise. A number still fixes every row, exactly as before.
- A `markdown` slot in a collection's `template` renders that field as
  Markdown -- headings, emphasis, links, lists, quotes and fenced code blocks
  -- rather than as plain text. It is the same renderer the `markdown()`
  component uses, extracted rather than copied, so a fenced block looks the
  same in a row as it does on a page. Both runtimes read the same styles for
  the same reason.
- A dict passed as `data=` to `https.post` / `put` / `patch` is sent as JSON,
  with the types of the literal intact: `{"max_tokens": 1024}` arrives as the
  number and not as `"1024"`, which is the difference between an API accepting
  a request and rejecting it. Nested lists and objects nest. Because the
  serialiser writes the body, a quote or a newline in text the user typed is
  escaped properly rather than breaking the JSON, which is what building the
  body by concatenation does the first time somebody presses the wrong key.
- `Content-Type: application/json; charset=utf-8` is set on a body that starts
  with `{` or `[`, unless the caller chose the header themselves. A string
  body is still sent exactly as written, so form-encoded and XML bodies are
  unaffected.
- `timeout=` on every `https` verb, in seconds, defaulting to 60 and capped at
  600. It replaces a fixed 10 seconds that no request to anything slow could
  survive.
- A module-level constant written by joining text -- `URL = BASE + MODEL +
  ":generate"`, which is how a URL is naturally written -- is folded into one
  literal and reaches the app. It used to produce nothing at all, and the name
  was then used in the generated Java without ever having been declared. A
  piece it cannot resolve, because the name is declared further down the file,
  is now `U2027` rather than a `cannot find symbol` from the Android build.
- `list_row.set_trailing()` and `.set_subtitle()`: a settings row
  shows three texts, so it needs three ways to change one. The slot has to
  have been declared -- pass `trailing=""` for one you intend to fill
  later -- and the lookup is guarded rather than assumed.
- `flex-grow: 1` on a stacked column child takes whatever its siblings leave,
  and `justify-content` / `align-items` place the children along and across the
  column. Together they are the empty state every assistant app opens on: the
  greeting in the middle, the composer pinned under it. A column that names
  neither still centres horizontally, which it always did.
- `label.stream(text, speed=)` and `collection.stream_item(id, field, text)`:
  text arriving a few characters at a time, the way an answer does. The rate
  lives in one table both runtimes read, so the phone and the desktop type at
  the same speed; `instant`, and a theme with `motion="none"`, put the whole
  thing there at once. The Android side is a Handler on the main looper and the
  Previewer a Tk `after` -- a few characters per tick rather than one every few
  milliseconds, because neither clock is accurate below about 10ms.
- The streaming helpers are emitted only for screens that carry the widget they
  touch. Commands come from the whole module, so a collection helper on a
  screen with no collection is a "cannot find symbol" at build time.
- `drawer(screens, labels=, icons=, header=, subtitle=)`: the navigation panel
  that slides in from the leading edge, and the last shape on the list that was
  outright impossible rather than merely unstyled. Declared once for the whole
  app the way `bottom_nav` is; each item starts the screen it names, the open
  screen stays checked, and `menu.open()` from an app bar's leading icon is
  what finally gives the hamburger something to open. Back closes the panel
  before it leaves the screen, which DrawerLayout does not do on its own.
- The compiler looks for the drawer before it reads any function body, because
  a drawer needs every screen to exist and the app bars that open it are
  written above it. Parsing strictly top to bottom would have met `menu.open()`
  before `menu` was anything and dropped it in silence.
- `list_row(text, subtitle, icon, trailing, trailing_icon, command)`: the
  settings row, and the one shape a button could never be. Its label starts at
  the leading edge with the icon beside it, it carries a second line, and it
  keeps room on the right for a value, a plan or a chevron. The text block
  takes what the icon and the trailing pieces leave, so a long label is cut
  with an ellipsis instead of pushing the chevron off the screen. Tapped like
  a button -- same `command=`, same navigation.
- `divider-color` on a container groups rows with hairlines, drawn between
  them and never at the edges (`android:showDividers="middle"`).
  `divider-width` sets the thickness and `divider-inset` starts the line past
  the icon column. Opt-in, so no container already written changes shape, and
  it works on any container rather than only ones holding rows.
- Rows stacked in a container sit flush against each other. The 6dp baseline
  gap between stacked children would have lifted every hairline off the seam
  it belongs on -- visible only once the APK was on a phone.
- `text-align: left | center | right` on labels and buttons. A button centred
  its label and nothing could move it, so three stacked rows read as three fat
  pills instead of a settings list. Written to Android as `start` / `center` /
  `end` so a right-to-left locale mirrors for free, and an aligned button pins
  its icon to the leading edge (`app:iconGravity="start"`) rather than grouping
  it with the label. `justify` is reported as `U2022` instead of half-done: it
  needs `android:justificationMode`, which arrived at API 26 while the
  generated app targets 24.
- `text-align: center` on an app bar centres its title
  (`app:titleCentered`). Android centres it in the whole toolbar and the
  Previewer does the same -- packing centred it in the gap the actions left
  over, which drifted left as soon as one appeared.
- `letter-spacing` and `line-height`, in `px`, `em` or -- for `line-height` --
  a bare multiple, the way CSS reads them. Both resolve through one shared
  module, so the em Android is handed and the pixels the Previewer measures
  come from the same arithmetic. `letter-spacing: 0px` is written out even
  though it is zero, because a MaterialButton tracks its label at ~0.089em on
  its own and silence would have left the phone spaced out while the Previewer
  sat tight.
- `font(family, regular=, bold=, italic=, bold_italic=)`: your own typeface,
  from `.ttf` or `.otf` files beside your code. The Android build copies them
  into `res/font`, writes the `<font-family>` that maps weights onto them, and
  reaches them through `app:fontFamily` -- the AppCompat attribute, because the
  framework one only learned to take a font resource at API 26 and ApkPy
  targets 24. The Previewer loads the same files into the session without
  installing anything. `Theme(font_family="Tiempos")` or
  `font-family: "Tiempos"` in CSS then reaches them, and the app bar title
  carries it too, through a generated text appearance.
- Four font slots and no more, because four is what both sides can address: Tk
  has a family plus `bold` and `italic`, Android expresses the same four as
  `fontWeight`/`fontStyle` pairs. A `medium` would render on the phone and not
  on the desktop, so it is reported as `U2024` rather than half-done. A slot
  you leave out is synthesised by both renderers alike.
- A missing font file or a web font format is reported at build time (`U2025`,
  `U2026`) and that slot is dropped. The family still ships with whatever
  survived, and a family left with nothing is never named by a layout --
  referencing a resource that was never written is an AAPT link failure, which
  is a much worse way to find out.
- `chevron_right` and `chevron_left` in the icon catalogue, with
  `navigate_next`, `navigate_before` and `disclosure` as aliases. The
  catalogue had no sideways chevron at all, and a right chevron is what tells
  a row that tapping it opens something. **62 names, 93 with aliases.**
- An app that mentions none of these generates byte-identical XML.

### Fixed

- An app bar's back arrow did nothing in the Previewer. `action("arrow_back")`
  with no `command=` of its own compiles to `finish()` on Android, so the same
  screen was one tap from leaving on a phone and a dead end on the desktop --
  a settings screen you could open and not get out of. The Previewer keeps a
  history now and the arrow walks it back, on exactly the icon name the
  generator tests for, so neither side can start answering differently.
- The Previewer had no equivalent of the system Back gesture at all, so a
  screen that draws no arrow of its own was a dead end even after the fix
  above. **Alt+Left** is that equivalent, and it follows Android's order: an
  open drawer closes first, and only then does Back leave the screen. Escape
  is deliberately left alone -- overlays bind it themselves, and a modal that
  both closed and navigated would be worse than no shortcut.
- A screen already open behind you is brought forward rather than stacked
  twice, which is what `FLAG_ACTIVITY_REORDER_TO_FRONT` does for a
  `bottom_nav`. Without it, hopping between two tabs grew the history for as
  long as you kept tapping.
- The Previewer's signal, wifi and battery symbols were the string
  `▮▮▮  ▲  ▮▮▮` -- three block characters, an arrowhead, three more --
  borrowed from whatever the system font happened to carry. At 24px that read
  as a row of dashes, and nothing in it said "battery". They are vectors now,
  on the icon catalogue's 24x24 grid and through the same antialiasing
  rasteriser every icon goes through, and they follow the app bar's palette
  the way the clock beside them always did.
- `?attr/...` in a colour position was reported as an unreadable colour. It
  is a reference to whatever the theme in force says, which is exactly right
  for a ripple, and it now passes through like `@color/...` always did.

- `var(--primary)` resolved to `#6750A4` in an app that declared a `Theme` and
  to the literal text `var(--primary)` in an app that did not, which failed the
  Android build. The generated `apkpy_theme.xml` is written from that same
  default palette either way, so the token was never wrong -- only unresolved,
  and whether it worked came down to a keyword the stylesheet has nothing to do
  with. An app that never names a theme now reads the same tokens as one that
  does. No theme stylesheet is merged into it, so nothing else about its output
  moves.
- A `type="textarea"` grew with its text on Android and never grew in the
  Previewer, so the same composer was one line on the desktop and three on the
  phone. Both now start at `rows` and stop at the same ceiling.
- A dict as the body of an `https` request compiled to an empty string. The
  request went out with nothing in it, in silence, and `body = {...}` on a line
  of its own generated no Java at all -- the name was then used without ever
  having been declared, so the build failed somewhere else entirely. The
  Previewer, which runs the Python, saw the whole dictionary: the divergence
  this compiler pays the most for.
- A list of objects became a list of strings. `[{"role": "user"}]` was written
  as `["{\"role\":\"user\"}"]`, so `{"messages": msgs}` handed the far end a
  quoted blob where an array belonged.
- An `https` body was read back with `readLine()` into a `StringBuilder`, which
  dropped every line break in the response, and both the body and the answer
  used the platform charset instead of UTF-8.
- The read timeout was 10 seconds on both sides, hard-coded. Anything that
  takes longer to answer than an ordinary endpoint -- a model, a report, a cold
  start -- died before replying, and the error that surfaced was a bare timeout
  that said nothing about why.
- The Previewer form-encoded a dict body while Android sent nothing at all, and
  disabled TLS certificate verification for every request. It now sends JSON
  like the phone does, verifies certificates by default, and only falls back to
  an unverified context when the system has no CA store -- saying so once, in
  the console, rather than quietly downgrading a request carrying an API key.
- `label.stream()` written inside a named function referred to the view by its
  local name, which only exists inside `onCreate`: a `cannot find symbol` at
  build time. It reaches the view through `findViewById` now, like every other
  setter does.
- `Theme(primary=...)` left `on_primary` at the Material baseline dark purple,
  so a filled button on any custom primary carried a label nobody could read.
  It is now derived from the primary's luminance unless you set it yourself.
- `storage.get(key, default)` used **inside** an expression -- as an argument
  rather than on a line of its own -- compiled to an empty string in silence.
  The Previewer read the stored value and the phone read nothing, which is the
  failure this compiler's own notes call class number one. It now reaches
  `_apkpyStorageGet` from both copies of the expression translator.
- `set_value()` on a `list_row` emitted `setText` on the row itself, which is a
  LinearLayout: a `cannot find symbol` at build time. It targets the row's
  label now, and `set_trailing()` / `set_subtitle()` reach the other two slots.
- The Previewer's app bar read its stylesheet for two colours and nothing
  else, so a custom typeface or size reached the title on the phone and not on
  the desktop.
- `item-background-color: #00000000` on a collection took the Previewer down
  with an `E1999` at startup. Tk has no per-widget alpha, so every colour a
  collection reads now resolves to whatever sits behind it -- which is how a
  chat turn asks to be text on the page rather than a card.
- A collection drew a scrollbar down the Previewer even with one item in it. A
  RecyclerView draws none until you drag it, so the rail is now shown only when
  there is something to scroll.

### Note on existing apps

- An app that declares `Theme(mode="dark")` still opens dark on a phone set to
  light, and the other way round: the declared mode is pinned at startup.
  Without that, `values-night/` would have made every existing app follow the
  system, which is a behaviour change nobody asked for.
- The generated XML *does* change: colours that came from tokens are now
  references. The app looks the same, and the project is easier to read and to
  edit by hand, which the generator has always aimed for.

### Verified, not changed

- A field at the bottom of a screen stays above the soft keyboard. Three
  shapes were checked on a Pixel 9 Pro (API 36) -- a plain `LinearLayout` with
  no scrolling view, a screen with an `app_bar()`, and a column with a
  composer pinned by `flex-grow` -- and Android resized the window correctly
  in all three without ApkPy declaring `windowSoftInputMode`. The attribute
  was not added: it would change the manifest of every app to no observable
  effect. What Android does, and the two things it does not promise, are in
  [Previewer versus Android](docs/preview-android.md).

### Known limits

- A collection row with a `markdown` slot renders the whole answer, but the
  Markdown it understands is the same subset the `markdown()` component
  understands: no tables and no images inside a row. A fenced block is
  monospace on a tinted background with a Copy under it, not a widget.
- Row heights in the Previewer are measured after a row is drawn, so a long
  row is estimated once before it settles into its real height. The phone has
  no such pass -- RecyclerView measures as it lays out -- which is the usual
  trade: the shape matches, the first frame may not.
- `scroll_to_end()` moves once, when it is called. It does not follow text
  that keeps arriving, so a long streamed answer still grows past the bottom
  edge after the jump. On Android a very long jump also takes longer than the
  stated duration: the RecyclerView re-aims as it goes, because it cannot know
  a row's height before laying it out.
- `https` still delivers the whole answer at once. There is no server-sent
  events reader yet, so an API that streams its reply token by token is read to
  the end before the callback fires. `label.stream()` types text that has
  already arrived; it is not the same thing.
- Every row in a collection has the same shape. The adapter has one view type,
  so a row cannot change its alignment, its surface or its width based on its
  own data. A chat where your turn is an inset bubble and the reply is
  full-width text is not expressible yet -- which is what still separates a
  thread built with ApkPy from the assistant apps it is modelled on.
- Nothing keeps the conversation for you. Sending the history back with each
  turn is your `data=` dict to build.
- An `on_response=` callback must be a named function, and it cannot see
  variables from the function that started the request -- the compiler reads
  your module rather than running it. Hand the value over through `storage`.
- Tk has no tracking and no line spacing on a label, so the Previewer shows the
  right words at the right size without the gaps between them.
  `letter-spacing` still changes where a button's label wraps and how wide it
  asks to be, and `line-height` still adds the leading above and below, so one
  line takes the height it takes on the phone. A paragraph that wraps comes out
  shorter in the Previewer, by the leading of each line after the first.
- Loading a font file into Tk is platform-specific. Windows and Linux work;
  macOS declines, falls back to the nearest system family and says so once in
  the console. The APK is unaffected.
- Text Android draws rather than your layout does not pick a custom family up
  yet: `bottom_nav` labels and `virtual_collection` rows stay on the system
  font. The app bar title does carry it.

## [1.3.2] — 2026-08-21

### Added

- One shared icon table: 60 names (88 with aliases) that the Previewer and the
  Android compiler both read, replacing two unrelated systems that agreed on
  only 29 of their 48 names. `person` used to render as a ring with a dot on
  the desktop; `skip_next` as a solid disc on the phone.
- The Previewer rasterises the shared vector with antialiasing instead of
  redrawing every icon by hand with canvas primitives Tk cannot smooth.
- `icon="assets/logo.svg"` accepts your own artwork. Read at build time and
  turned into an Android vector drawable, with `viewBox`, nested `transform=`,
  arcs and the common shape elements handled. Shapes painted in a second colour
  are cut out rather than merged, which is how designers fake a hole.
- Thirteen navigation names ship an outlined variant. `bottom_nav` fills the
  active item: a pill lights up behind the icon and the icon goes from outline
  to solid. `indicator="pill" | "line" | "none"` and `icons_active=`.
- `Theme(motion=...)`: `none`, `subtle`, `standard`, `expressive`. Four moments
  scale from one base, and both runtimes resolve every duration from the same
  module.
- CSS `transition:` on appearing and disappearing, and `press:` for touch
  feedback.
- `on_click_navigate(transition="slide" | "slide_up")`, using
  `overrideActivityTransition` on API 34+ and `overridePendingTransition`
  below, because the older call is deprecated at the generated `targetSdk`.
- Animations honour Android's *Remove animations* accessibility setting.
- Five diagnostic codes for icons: an unknown name (`U2015`, a warning with the
  closest match), a missing file, a stroke-only export, an unconvertible
  element and an unreadable file.
- `subtitle-lines` and `title-lines` on a list or collection: one line is
  still the default, and a chat message needs more than one to be readable at
  all. Both runtimes read the same two numbers.
- Composer controls in the catalogue: `mic`, `send`, `stop`, `bolt`,
  `expand_more`, `expand_less` and `content_copy` — the set a chat-style input
  bar needs.
- `text-transform: none` on a button label. Material shouts them and ApkPy
  always has, so the default is unchanged and an app that never mentions the
  property generates byte-identical XML; `none` is the opt-out a chip or a pill
  wants. `uppercase` and `none` are the two values offered, because they are
  the two Android expresses as `android:textAllCaps`; anything else is reported
  as `U2021` rather than half-done.
- `U2020` reports a colour Android cannot parse, at build time instead of as an
  `IllegalArgumentException` while the screen is created.

### Fixed

- `background-color: #00000000` on an input took the whole Previewer down with
  an `E1999` at startup. Tk has no per-widget alpha, so a transparent surface
  now resolves to whatever sits behind it — which is what transparency means on
  screen — everywhere a CSS colour can reach a Tk option.
- `border-width: 0px` drew a hairline anyway on an input with a radius, and
  focus grew it to 2px. Android emitted no `<stroke>` for the resting state but
  did for the focused one. Both sides now draw nothing, in both states.
- A variable first assigned inside an `if` branch was declared inside that
  branch in Java, so the next line could not see it. Python has no block
  scope; the app failed to compile with "cannot find symbol" after running
  fine in the Previewer.
- `merge_items([{...}])` accepted only fully literal rows. A row built from
  what the user just typed — the normal case for a chat — was dropped in
  silence, and the generated Java compiled, ran and added nothing.
- A `rich=True` list row with no image still reserved its thumbnail, which
  showed as an empty blue square on the phone and nowhere else.
- A child of a flex row asked the Previewer for the full row width instead of
  its own content width, so a row only looked right because `flex-shrink`
  squeezed it back. `flex-shrink: 0` then pushed the last controls off the
  edge. Children now measure like Android's `wrap_content`.
- A hidden child still reserved its box in a Previewer flex row, a gap the
  phone never had — `ApkpyLayout` has always skipped a `GONE` view.
- `popup_menu(anchor=...)` and `context_menu(target=...)` written as bare
  statements — the natural way to write them, since they attach to another
  component — were parsed only in their assigned form, so the menu opened in
  the Previewer and the button did nothing on the phone.
- `component.hide()` at module level set the starting state in the Previewer
  and was dropped entirely for Android, which showed every control at launch.
  It is now emitted as an instant `setVisibility`, not an animated one.
- Emptying a textarea with `set_value("")` left it blank instead of bringing
  the placeholder back; the single-line field already did the right thing, and
  `android:hint` does it by itself.
- `button(text=...)`, `label(text=...)` and `inputs(placeholder=...)` passed by
  name never reached the generated XML — the parser read only the positional
  argument, so the label or hint showed in the Previewer and came out empty on
  the phone.
- `#111` reached `Color.parseColor`, which accepts only `#RRGGBB` and
  `#AARRGGBB`, and closed the app the moment it opened. The `#RGB` and `#ARGB`
  shorthands are expanded; four digits are the shorthand of eight, matching the
  `#AARRGGBB` convention the rest of the project uses.

- `files.pick(on_result=, types=)` picks any file type through the Storage
  Access Framework and reports `(success, path, name, size, mime)` — five
  strings in both runtimes. No storage permission is declared.
- `upload_button(...)` picks and uploads in a single call. It is expanded at
  parse time into an ordinary button plus two callbacks, so the generated Java
  is identical to the hand-written form; a regression test asserts that.
- `types=` accepts extensions, complete MIME types and families, resolved in
  Python at build time so the two runtimes cannot disagree.
- Diagnostics expanded to 64 codes across eight families, each with a
  "Why this happened" explanation and a documentation link. 166 of the 167
  messages the library raises are matched by a specific rule.
- Gradle failures are diagnosed: eight recognised signatures, and an
  unrecognised failure still reports Gradle's own reason and the project path.
- Compiler diagnostics point at the line in `writehere.py` instead of ApkPy's
  own source, and never report a location inside the library.
- A search filter that cannot become a `TextWatcher` is reported as `C4002`
  instead of a one-line note; a background job body that raises is reported
  with the job name, attempt number and payload keys.

### Added

- `background_job()` declares persistent work that survives backgrounding,
  network loss, process death and a reboot. Android generates a WorkManager
  `OneTimeWorkRequest` pipeline; the Previewer runs the same contract against
  an on-disk queue in `~/.apkpy/jobs`.
- Constraints `requires_network`, `requires_unmetered`, `requires_charging`
  and `requires_battery_not_low`, generated as an `androidx.work.Constraints`
  object.
- Automatic retries with `retry="exponential"` or `"linear"` and
  `retry_seconds=`, generated as `setBackoffCriteria` with WorkManager's
  ten-second floor.
- Unique work through `unique=True` and `on_conflict="append" | "keep" |
  "replace"`, generated as `ExistingWorkPolicy`. `"append"` maps to
  `APPEND_OR_REPLACE` so a queue is not silently cancelled after one failure.
- `job.enqueue(data)`, `job.cancel()` and `job.observe(on_change=, screen=)`.
- Inside the job body: `job.input(key)`, `job.attempt()`,
  `job.progress(percent, message)`, `job.retry()` and `job.fail()`.
- One JSON status document — `state`, `progress`, `message`, `pending`,
  `running`, `attempt` — delivered identically by both runtimes.
- The English **Offline Outbox** demonstration in `playground/writehere.py`,
  covering queueing, offline hold, drain on reconnection, restart recovery,
  a deliberate failure with backoff and queue cancellation.

### Android and Previewer

- Conditional `ApkpyJobs.java` runtime with one `enqueue_<job>` entry point
  per declared job, plus `cancel` and a `status` collector that folds a list of
  `WorkInfo` into the JSON document.
- One generated `<Job>JobWorker.java` per job, reusing the existing worker
  generator rather than duplicating it, extended with `getInputData()`,
  `setProgressAsync()` and the attempt result.
- `observe()` attaches to `getWorkInfosByTagLiveData(...)`, so progress
  survives rotation and resumes with the Activity without polling.
- Job declarations are collected in a pass that runs before the module is
  visited. Python requires the run function to be written above the
  declaration, and without that pass its job calls were dropped in silence.
- The `androidx.work:work-runtime` dependency, the runtime class and the
  worker are emitted only when a job is declared.
- Worker helpers `_jobInput` and `_jobProgress`, and the attempt-result field,
  are emitted only when the job body uses them.

### Fixed

- `animation-duration: 0.5s` was parsed as 0.5 ms in the Previewer and 5 ms on
  Android; neither understood seconds. The default duration also differed,
  600 ms against 1000 ms, and the two easing curves were different.
- A `@keyframes` fade interpolated towards a hard-coded `#ffffff`, so every
  fade in a dark app flashed white.
- `scale` and `margin-left` animated on Android and did nothing in the
  Previewer.
- `inputs.set_value("")` cleared the field without restoring its placeholder,
  so a form that clears itself after submitting went blank and stayed blank.
- CSS `placeholder-color` was honoured on Android and ignored by the Previewer.
- Rounded containers re-measured after the first paint, so a freshly rendered
  screen showed clipped cards for about 250 ms before settling.
- The bottom bar's active pill used the same colour as the icon behind it,
  hiding the icon on a device.
- `render_diagnostic` printed an empty *Technical details* heading.
- `db.text(choices=[...])` generated `new JSONArray(String)`, whose checked
  `JSONException` the field initialiser neither caught nor declared, so any
  model using `choices=` failed the build with *unreported exception
  JSONException*.
- Upload progress delivered integers in the Previewer and strings on Android,
  so `"Uploading " + percent + "%"` worked on the phone and raised `TypeError`
  on the desktop. Both runtimes now deliver strings.
- Upload lambdas could shadow a parameter of the enclosing method, producing
  Java that did not compile.
- Diagnostic output is normalised to ASCII for legacy Windows code pages.
- A `return` inside a generated `Worker` emitted `return;` from `doWork()`,
  which returns `Result` and therefore did not compile. Early returns now
  produce the correct result. This also affected `service.every` workers and
  is covered by a regression test.
- Previewer connectivity for `requires_network` is decided by a route check
  combined with a reachability check on port 443. A reachability check alone
  reported offline on machines that block outbound port 53, and a route check
  alone reported online with the Wi-Fi switched off on machines with Hyper-V,
  WSL, VirtualBox or VPN adapters.
- Previewer job status values are strings, matching the generated `_jsonGet`
  accessor. Numeric keys previously returned integers, so string concatenation
  worked on Android and raised `TypeError` on the desktop.
- Observer notifications raised on a worker thread are delivered through an
  interface-thread pump. Scheduling them directly stalled the worker and left
  the queue frozen.

### Documentation

- New [Background jobs and offline queue](https://repo-apkpy.pages.dev/background-jobs/)
  page and [Version 1.3.2](https://repo-apkpy.pages.dev/version-1.3.2/) notes.

---

## [1.3.1] — 2026-08-20

### Added

- Friendly diagnostics shared by Previewer callbacks, application startup,
  Data Core, the Android compiler and build-toolchain checks. Reports include
  stable codes, the relevant application line, the original cause and an
  ordered correction, with `APKPY_DEBUG=1` retaining the full traceback.
- `apkpy preview` and `apkpy preview --debug` for startup and syntax failures
  that occur before the normal Previewer lifecycle begins.
- Controlled one-to-many `db.relation()` declarations with validated parent
  keys, foreign-key types, unique aliases and `restrict`, `cascade` or
  `set_null` delete behavior.
- `relations=[...]` in `db.schema()` and real SQLite foreign-key constraints
  with foreign-key enforcement enabled in Previewer and Android.
- `include=[...]` for typed `find()` and `get()`, loading each relation with
  one batched bound query instead of one query per record.
- Lifecycle-safe `model.observe()` queries with `refresh()`,
  `update_query()` and `close()`.
- The English **Knowledge Vault Live** demo with folders, related notes,
  dynamic observed search, CRUD, favorites, cascade and live update counts.

### Android and Previewer

- Added a conditional shared `ApkpyDataInvalidationTracker` and
  `ApkpyQuerySubscription` runtime.
- Successful writes invalidate only affected model dependencies after commit;
  transactions publish one combined invalidation and rollback publishes none.
- In-flight invalidations are coalesced, stale query generations are ignored
  and repeated visible snapshots are deduplicated.
- Activity observers resume, pause and close with their owning screen.
- Projects without relations or observation do not receive the corresponding
  metadata, hydration or subscription code.

### Validation

- Added relation validation, foreign-key policy, include hydration, observer
  lifecycle, dynamic-query and rollback tests.
- 21 focused Data Core/Reactive Data tests, 8 focused diagnostic tests and 167
  transpiler checks pass.
- Compiled the generated Knowledge Vault Live Java with Gradle; this caught
  and fixed SQL-identifier escaping and cross-screen observer-handle errors.

### Documentation

- Added the complete Reactive Data contract, migration guidance, lifecycle
  behavior, deliberate limits and a runnable Knowledge Vault Live example.
- Documented the project's current proprietary status and the commitment to
  release the core source as open source if active development is permanently
  discontinued.

### Deliberate limits

- Only one-to-many and one-level eager includes are supported. This version
  does not add many-to-many, recursive relations, lazy loading, polling,
  offline synchronization or external SQLite change detection.

---

## [1.3.0] — 2026-08-17

### Added

- Declarative `db.model()` and `db.schema()` definitions with typed integer,
  real, text, boolean, datetime, JSON and blob fields.
- Required/optional/default values, keys, uniqueness, numeric and text bounds,
  choices, and simple or composite indexes.
- Asynchronous `insert`, `insert_many`, `get`, `find`, `update`, `delete` and
  `count`, with callbacks delivered on the interface thread.
- Parameterized comparisons, text matching, null checks, logical groups,
  ordering and `limit`/`offset` pagination.
- Atomic `db.transaction()` operations and optimized prepared batch insertion.
- Explicit migration operations, schema hash/version metadata, downgrade
  refusal and private backup/restore for destructive migration paths.
- The English two-screen **Knowledge Vault** application covering indexed
  search, filters, paging, CRUD, batch work, errors and a v1-to-v2 migration.

### Android and Previewer

- Android generation emits `ApkpyDatabase.java`, one shared single-threaded
  data executor and one repository per model.
- Generated repositories use `SQLiteStatement`, bound arguments and
  main-thread callbacks; they never execute queries on the UI thread.
- The Previewer uses Python `sqlite3` and a single ordered worker with the same
  validation and migration contract.
- Data Core files are conditional; applications without `db.model()` receive
  no repository, executor, metadata or migration output.
- The previous `db.execute`, `db.query`, `begin`, `commit` and `rollback` API
  remains compatible.

### Validation

- Added focused tests for declarations, CRUD, JSON, order, pagination,
  compound indexes, atomic batches and transaction rollback.
- Verified v1-to-v2 preservation, missing paths, schema hash mismatches,
  downgrade refusal and restore after a failed destructive migration.
- Verified existing feed, rich-content and Gradle-generation tests and built
  the generated Knowledge Vault Android project successfully.
- Added the reproducible Benchmark Notes comparison with four application
  sources, transparent line counts, raw device samples and APK hashes. The
  benchmark is documented as a scoped debug-app measurement, not a universal
  framework ranking.

### Deliberate limits

- Relations, observable queries, offline-first synchronization, conflict
  resolution and persistent background jobs are not included in 1.3.0.

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
