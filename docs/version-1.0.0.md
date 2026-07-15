# Version 1.0.0

Version 1.0.0 is the release in which ApkPy becomes a complete native-app workflow rather than only a basic screen generator.

## Build and release

- <code>apkpy run</code> generates and compiles an installable debug APK.
- <code>apkpy doctor</code> diagnoses the JDK/Android SDK setup.
- <code>apkpy setup</code> installs a compatible toolchain when needed.
- <code>apkpy init</code> creates application identity configuration.
- <code>apkpy release</code> and <code>--aab</code> create signed release artifacts.
- QR and USB options shorten the device-install loop.

## Interface system

- Global <code>Theme</code> and reusable design tokens.
- Material button variants and named icons.
- Responsive row/column composition, advanced flex/grid and layering.
- Semantic and composable cards.
- Fixed and collapsible app bars.
- Bottom navigation and parameterized navigation between screens.
- Sheets, modals, popup/context menus, tooltips, pickers and snackbars.
- Skeleton, spinner, empty and error states.
- Improved Previewer shape, icon and toast parity with Android.

## Lists and media

- Plain and rich <code>list_view</code> rows.
- JSON-to-list mapping for database and API results.
- Carousels and multi-column grids.
- Foreground background-audio service with metadata.
- Queue navigation, shuffle, repeat, seeking and bound player controls.
- Persistent mini-player.
- Favourites, playlist creation, editing, track removal and playlist deletion.
- Offline downloads in private app storage.

## Spotify-style applications

ApkPy now supplies the complete interface and infrastructure layer needed for a Spotify-style client:

- rich music shelves, grids and lists;
- background playback and native media notification;
- a full player and mini-player;
- favourites and editable local playlists;
- offline files;
- OAuth with Spotify through Authorization Code + PKCE.

The application developer remains responsible for API authorization, catalogue access and media rights.

## Security and data

- Transparent encrypted key/value storage.
- AES-256-GCM with Android Keystore for values that must be decrypted.
- Salted PBKDF2 password hashing and constant-time verification.
- Parameterized SQLite queries.
- SQLite transactions and inserted-row IDs.
- Full REST operations: GET, POST, PUT, PATCH and DELETE.
- Safe JSON access and direct JSON list population.

## Python language support

The compiler handles real iteration over lists, ranges and JSON/database rows, together with nested conditions, <code>break</code>, <code>continue</code>, <code>while</code>, f-strings, augmented assignments and common string validation helpers.

## Native integrations

The release includes notifications, background work, sharing, clipboard, camera, gallery, location, OAuth and installed-app inspection APIs.

## Compatibility principle

All public features are designed around one rule:

> Write the flow once in Python, test it in the Hot Previewer, and generate the equivalent native Android behavior.

Platform surfaces can render differently, but state, callback and navigation semantics should remain aligned.
