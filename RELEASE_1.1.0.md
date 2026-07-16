# ApkPy 1.1.0 — one Python tree, a complete native design system

ApkPy 1.1.0 is the release where building a polished interface stops meaning
repeating styles on every component. You describe the product once in Python,
choose how it should adapt, and ApkPy keeps the desktop Previewer and generated
Android project on the same visual language.

This guide follows the nine parts of the development plan that became 1.1.0.

## 1. Global themes and design tokens

A `Theme` is the visual foundation of the whole application. It styles regular
components, Material surfaces, system bars and navigation without forcing every
button or label to carry its own CSS.

```python
from apkpy_lib import Screen, Theme, button, inputs, label, run

home = Screen(id="home")
label("Welcome back", screen=home)
inputs("Email", screen=home)
button("Continue", variant="filled", screen=home)

theme = Theme(
    mode="dark",
    primary="#8B5CF6",
    secondary="#22D3EE",
    background="#09090B",
    surface="#18181B",
    text="#FAFAFA",
    text_secondary="#A1A1AA",
    border="#3F3F46",
    radius=18,
    spacing=14,
)

run(start_screen=home, theme=theme)
```

Tokens remain available inside CSS, so a product can keep one palette while
still giving a specific component its own character:

```css
panel { background-color: var(--surface); border-color: var(--border); }
danger_action { background-color: var(--error); color: var(--on-primary); }
```

The cascade is predictable: Theme defaults, component selector, semantic
variant, then component ID. The ID is always the final override.

## 2. Material buttons and native vector icons

Buttons now describe intent, not just colour. Filled, outlined, tonal, text,
danger and icon variants share the Theme automatically.

```python
from apkpy_lib import button, container

actions = container(id="actions", screen=home)
button("Continue", variant="filled", icon="arrow_forward", parent=actions)
button("Save draft", variant="tonal", icon="save", parent=actions)
button("Details", variant="outlined", icon="info", parent=actions)
button("Delete", variant="danger", icon="delete", parent=actions)
button("More options", variant="icon", icon="more_vert", parent=actions)
```

The Previewer draws font-independent icon geometry and Android receives native
vector drawables. This avoids missing emoji glyphs and keeps icon size,
alignment and colour stable across machines.

## 3. Responsive mobile, tablet and landscape layouts

The component tree stays the same at every size. `responsive()` only changes
how those components are arranged.

```python
from apkpy_lib import Screen, column, container, label, responsive, row

dashboard = Screen(id="dashboard", scroll=True)

profile = container(id="profile")
label("Marta Costa", parent=profile)

activity = container(id="activity")
label("Recent activity", parent=activity)

responsive(
    mobile=column(profile, activity),
    tablet=row(profile, activity),
    landscape=row(profile, activity),
    breakpoint=600,
    id="dashboard_layout",
    screen=dashboard,
)
```

The Previewer can be resized with `device("responsive")`. Android receives
native resources in `layout`, `layout-land`, `layout-sw600dp` and
`layout-sw600dp-land`, allowing the OS to choose the correct layout before the
Activity is drawn.

## 4. Flex, grid, aspect ratio and layered composition

Advanced layouts can wrap actions on narrow screens, let important children
grow, build real grids and place badges above artwork.

```python
gallery = container(id="gallery", screen=home)
featured = container(id="featured", parent=gallery)
label("NEW", id="badge", parent=featured)
```

```css
actions {
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 12px;
}

actions button { flex-grow: 1; flex-basis: 140px; }

gallery {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
}

featured { grid-column: 1 / span 2; aspect-ratio: 16 / 7; }
badge { position: absolute; top: 12px; right: 12px; z-index: 3; }
```

Simple screens remain ordinary native `LinearLayout`s. ApkPy only generates
its optimized `ApkpyLayout` ViewGroup when a project actually uses advanced
layout rules.

## 5. Material cards and composable surfaces

Use the ready-made form for a familiar media card, or create an empty card and
attach any component hierarchy to it.

```python
from apkpy_lib import card, card_action, toast

card(
    title="Premium",
    subtitle="No ads and offline downloads",
    image="premium.jpg",
    content="High-quality audio on every device.",
    actions=[
        card_action("Learn more", variant="text"),
        card_action("Try it", variant="filled",
                    command=lambda: toast("Trial started")),
    ],
    variant="elevated",
    id="premium_card",
    screen=home,
)
```

```python
custom = card(id="custom_card", variant="outlined", screen=home)
label("COMPOSITION", variant="overline", parent=custom)
label("Any content can live here", variant="title", parent=custom)
button("Open example", variant="text", parent=custom)
```

Generated Android cards are native `MaterialCardView` components. The three
surface variants are `elevated`, `filled` and `outlined`.

## 6. Fixed app bars and collapsible media headers

Toolbars are attached to a `Screen`, so they remain outside scrollable content
and do not need placeholder containers.

```python
from apkpy_lib import Screen, action, app_bar, sliver_app_bar, toast

library = Screen(id="library", scroll=True)
app_bar(
    "Library",
    leading="arrow_back",
    actions=[
        action("search", label="Search",
               command=lambda: toast("Search library")),
        action("more_vert", label="More options"),
    ],
    screen=library,
)

artist = Screen(id="artist", scroll=True)
sliver_app_bar(
    "Mira Nox",
    image="artist-cover.jpg",
    expanded_height=240,
    pinned=True,
    screen=artist,
)
```

Android output uses `MaterialToolbar`, `AppBarLayout` and
`CollapsingToolbarLayout` under the generated `Theme.App` Material Components
theme.

## 7. Bottom sheets, dialogs, menus, snackbars and pickers

Overlays are lightweight definitions. No hidden View is added to the screen;
the native component is created only when `.open()` is called.

```python
from apkpy_lib import bottom_sheet, button, date_picker, modal, snackbar

playlist_sheet = bottom_sheet(
    "Add to playlist",
    content="Choose where to save this track.",
    items=["Focus", "Training", "Favourites"],
    on_select=lambda name: snackbar("Added to " + name),
)

delete_dialog = modal(
    "Delete download?",
    content="The online copy will remain available.",
    confirm_text="Delete",
    on_confirm=lambda: snackbar("Download deleted", action="Undo"),
)

release_date = date_picker("Release date", initial="2026-07-16")

button("Add to playlist", command=lambda: playlist_sheet.open(), screen=home)
button("Delete", command=lambda: delete_dialog.open(), screen=home)
button("Choose date", command=lambda: release_date.open(), screen=home)
```

The same family also includes context menus, popup menus, time pickers and
tooltips. Android maps them to Material/native dialogs and menus; the Previewer
keeps the same callbacks and dismiss behaviour.

## 8. Skeleton, loading, empty and error states

Content states share one region and switch visibility without rebuilding the
screen tree.

```python
from apkpy_lib import empty_state, error_state, skeleton, toast

loading = skeleton("music_card", count=4, screen=library)

empty = empty_state(
    icon="music_off",
    title="Your library is empty",
    message="Save a track and it will appear here.",
    action="Explore music",
    on_action=lambda: toast("Opening catalogue"),
    visible=False,
    screen=library,
)

error = error_state(
    title="Could not load the library",
    message="Check your connection and try again.",
    retry=lambda: toast("Trying again"),
    visible=False,
    screen=library,
)

def show_empty():
    loading.hide()
    error.hide()
    empty.show()
```

Skeleton animation helpers are generated only for Activities that use them.
Empty and error actions remain ordinary native buttons and callbacks.

## 9. Smart images and avatars

Remote artwork can display a local placeholder immediately, use a fallback on
failure, reuse a bounded cache and fade into place without blocking the UI.

```python
from apkpy_lib import avatar, image

image(
    "https://example.com/cover.jpg",
    placeholder="cover-placeholder.png",
    fallback="cover-fallback.png",
    cache=True,
    fade_in=True,
    aspect_ratio="16:9",
    id="cover",
    screen=home,
)

avatar(
    "profile.jpg",
    size=52,
    status="online",
    id="profile_avatar",
    screen=home,
)
```

Images also support `blur=`, `tint=`, `object-fit`, circular crops and runtime
`set_src()`. Android uses a three-worker loader, bounded LRU cache and native
fade; Previewer requests run outside the UI thread and stale responses are
ignored.

## Parity and reliability work included in the release

The nine features were developed together with fixes that make the Previewer a
more useful approximation of the final Android application:

- Material button geometry, borders, colours, pressed states and wrapping now
  follow the same cascade on both targets.
- Font-dependent emoji icons were replaced by matching vector geometry.
- `Theme.App` prevents Material cards and toolbars from crashing during Android
  layout inflation.
- Bottom navigation preserves input state in the Previewer and opens the
  correct Activity on Android.
- Rounded cards, inputs, selects and switches render consistently.
- Bottom sheets keep the background visible instead of replacing the whole
  Previewer with a black window.
- Previewer toasts now use a compact Material capsule instead of a rectangular
  black block.
- Image crop, aspect ratio, placeholder, tint and narrow-screen button wrapping
  were aligned with Android behaviour.

## The visual system works with ApkPy's native data stack

The 1.1.0 interface APIs do not replace SQLite, REST, encryption or media; they
make those features easier to present. These existing APIs remain fully
documented and supported.

### SQLite with encrypted fields and safe parameters

```python
from apkpy_lib import crypto, db

db.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, body TEXT)")

secret = crypto.encrypt("Private tour notes")
db.execute("INSERT INTO notes (body) VALUES (?)", [secret])

rows = db.query("SELECT body FROM notes WHERE id = ?", [1])
```

Passwords should be hashed rather than encrypted:

```python
stored_hash = crypto.hash_password("correct horse battery staple")
if crypto.verify_password("correct horse battery staple", stored_hash):
    toast("Password verified")
```

On Android, two-way encryption uses AES-256-GCM with a per-device key protected
by Android Keystore. `storage.set()` also encrypts values automatically before
they reach SharedPreferences.

### REST data into a list

```python
from apkpy_lib import https, list_view

results = list_view([], rich=True, screen=home)

def loaded(success, body):
    if success:
        results.set_items(body, title="name", subtitle="description", image="cover")

https.get(
    "https://api.example.com/releases",
    headers={"Authorization": "Bearer your-token"},
    on_response=loaded,
)
```

Requests run away from the UI thread in both environments. GET, POST, PUT,
PATCH and DELETE are available.

### Background audio and persistent playlists

```python
from apkpy_lib import audio

audio.play_playlist(
    ["https://cdn.example.com/one.mp3", "https://cdn.example.com/two.mp3"],
    titles=["Soft Static", "Glass District"],
    artists=["Mira Nox", "Frame Relay"],
)

audio.add_to_playlist("Night drive")
audio.play_saved_playlist("Night drive")
audio.remove_from_playlist("Night drive")
audio.delete_playlist("Night drive")
```

The generated Android foreground media service integrates with system
notifications, the lock screen, transport controls and audio focus.

## Validation performed before release

The 1.1.0 wheel was installed into a clean Python environment and used to
generate four independent applications:

| Application | Product | Android Activities |
| --- | --- | ---: |
| Lumen | Personal finance | 4 |
| Onda | Wellbeing | 4 |
| Northline | Travel | 4 |
| Afterglow | Music discovery | 4 |

All four projects compiled with Gradle 8.6. Their 16 Activities were installed
and opened on a Pixel 9 Android emulator without an AndroidRuntime crash. The
generated output also passed XML parsing, Java structure checks and the 146-case
transpiler regression suite.

## Upgrade

```bash
pip install --upgrade apkpy==1.1.0
```

Run the Previewer as usual with `python writehere.py`, create an Android Studio
project with `apkpy build`, or compile an installable APK directly with
`apkpy run`.
