# Changelog

All notable changes to ApkPy will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
