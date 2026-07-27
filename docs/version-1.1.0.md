# ApkPy 1.1.0

!!! info "Released"
    ApkPy 1.1.0 was released on 2026-07-16. This page remains the complete guide
    to that version's interface and compiler changes.

Version 1.1.0 turns ApkPy's interface layer into a coherent product system.
The same component tree, theme and callbacks are interpreted by the Hot
Previewer and transpiled into native Android Java, XML and resources.

## The nine parts of the update

### 1. Global themes and design tokens

`Theme` defines light or dark mode, semantic colors, type, spacing and corner
radius once. CSS can reuse normalized tokens such as `var(--primary)`,
`var(--surface)` and `var(--text-secondary)`.

### 2. Material-style buttons and icons

Buttons support filled, outlined, tonal, text, danger and icon variants.
Android receives native vector drawables while the Previewer uses matching
symbols, sizing and interaction states.

### 3. Responsive composition

`responsive()`, `row()` and `column()` describe a single component tree that
adapts to phone, tablet and landscape. Android uses qualified resource folders
instead of rebuilding the interface after launch.

### 4. Advanced flex, grid and layering

Wrapping, flexible bases, grid tracks and spans, aspect ratios, absolute
positioning and z-index are available where a product needs more control. The
extra native layout helper is generated only for projects that use it.

### 5. Cards and surfaces

`card()` supports a ready-made media structure or arbitrary child components.
Elevated, filled and outlined variants compile to Material card surfaces.

### 6. App bars and collapsible headers

`app_bar()` adds fixed navigation and actions. `sliver_app_bar()` combines a
large media header with a pinned toolbar as the page scrolls.

### 7. Overlays, menus and pickers

Bottom sheets, dialogs, anchored menus, context menus, snackbars, tooltips,
date pickers and time pickers share one public API across both environments.

### 8. Loading and content states

Efficient skeletons, loading indicators, empty states and recoverable error
states can be shown and hidden without recreating the screen tree.

### 9. Advanced images and avatars

Images support local placeholders, failure fallbacks, bounded memory caching,
fade-in, blur, tint and fixed aspect ratios. Avatars reuse the same pipeline
and add circular cropping and presence states.

## Showcase validation

The release candidate includes four English-language applications: Lumen,
Onda, Northline and Afterglow. Together they cover light and dark themes,
finance, wellbeing, travel and media interfaces.

[Open the visual showcase](showcase.md)

The current local review generated sixteen Android Activities. Generated XML
passed parsing, Java passed structural checks and the main transpiler suite
completed with 146 passing tests.

## Before publishing

- review the four isolated Previewer captures;
- compile the final package artifacts locally;
- confirm the version and release notes;
- publish the package, repository changes and documentation only after approval.
