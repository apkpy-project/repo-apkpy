---
title: Previewer versus Android
description: Understand which ApkPy behavior is simulated on desktop and which is native on Android.
---

# Previewer versus Android

One Python declaration drives two renderers. The Previewer optimizes the edit
loop; the generated project uses Android widgets and services.

<div class="renderer-compare">
  <section>
    <span>DESKTOP</span>
    <h2>Hot Previewer</h2>
    <p>Fast layout, callbacks, simulated device events and deterministic test data.</p>
    <ul>
      <li>Tk-based visual renderer</li>
      <li>desktop file and network workers</li>
      <li>explicit simulation for push and GPS</li>
      <li>no Android permission or OEM behavior</li>
    </ul>
  </section>
  <div class="renderer-arrow" aria-hidden="true">same Python source</div>
  <section>
    <span>DEVICE</span>
    <h2>Native Android</h2>
    <p>Material widgets, Activities, RecyclerView, Media3, FCM and device services.</p>
    <ul>
      <li>Java, XML and Gradle output</li>
      <li>native lifecycle and permissions</li>
      <li>real codecs, GPS and notifications</li>
      <li>Android Studio inspection</li>
    </ul>
  </section>
</div>

## Behavior map

| Feature | Previewer | Android |
| --- | --- | --- |
| Components | desktop widgets styled from the same tokens | Material/native views and generated drawables |
| Navigation | screen-tree switch | Activity navigation and extras |
| Feeds | pooled virtual rows | `RecyclerView` with targeted notifications |
| SQLite | Python SQLite | `SQLiteDatabase` |
| Encrypted values | local preview key store | Android-backed encrypted storage |
| HTTP/uploads | background desktop workers | Android background network workers |
| WebSocket | WSS client with reconnect | Android WSS client with lifecycle callbacks |
| Audio/video | desktop media backend | foreground MediaSession and Media3 |
| Push | `push.simulate()` | Firebase Cloud Messaging |
| Location | explicit `preview_route` | fused device location |
| Routes | compatible HTTP routing endpoint | same request contract from Android |
| Background jobs | on-disk queue in `~/.apkpy/jobs` | WorkManager `OneTimeWorkRequest` queue |
| Soft keyboard | none: the desktop keyboard is always there | the window resizes and the layout moves up |
| Leaving a screen | the app bar's back arrow, or **Alt+Left** | the arrow, the Back gesture or the hardware key |

## Leaving a screen

On Android every `Screen` is an Activity, so there are always two ways out: an
app bar's back arrow, and the system Back gesture. `action("arrow_back")` with
no `command=` of its own compiles to `finish()`.

The Previewer swaps one widget tree for another. It keeps a history of the
screens behind the current one and offers the same two ways out:

- the app bar's back arrow, on the same `arrow_back` icon name the generator
  tests for;
- **Alt+Left**, standing in for the Back gesture a desktop window does not
  have.

Both follow Android's order: an open `drawer()` closes first, and only then
does Back leave the screen. At the first screen, Back does nothing -- on a
phone that is where it would close the app, and the Previewer stays put rather
than shutting its own window.

A screen already open behind you is brought forward rather than stacked a
second time, which is what `FLAG_ACTIVITY_REORDER_TO_FRONT` does for the tabs
of a `bottom_nav`.

~~~ python
model_screen = Screen(id="model_screen")
app_bar("Default model",
        leading=action("arrow_back", label="Back"),
        screen=model_screen)
~~~

Escape is not bound: overlays bind it themselves, and a modal that both closed
and navigated would be worse than no shortcut.

## The soft keyboard

The Previewer has no soft keyboard. A desktop window is never covered by one,
so a screen that looks right there tells you nothing about what happens on a
phone when a field is focused. This is the one gap in the map above that
cannot be closed by making the Previewer better -- there is nothing to
simulate that would be true.

What Android does, measured on a Pixel 9 Pro (API 36) across the three shapes
a generated screen takes:

| Screen | Root the generator writes | Keyboard opens |
| --- | --- | --- |
| No app bar, `scroll=False` | `LinearLayout` | window resizes; content stays visible |
| With an `app_bar()` | `RelativeLayout` wrapping a `NestedScrollView` | window resizes; the bar stays put |
| `Screen(scroll=True)` | `NestedScrollView` | window resizes; the focused field scrolls into view |

ApkPy does **not** declare `windowSoftInputMode` in the generated manifest.
Android's default, `adjustUnspecified`, resolved to a resize in all three
cases, and adding the attribute would change the manifest of every app to no
observable effect.

Two things this does *not* promise:

- **A list does not follow the keyboard.** A `virtual_collection` keeps its
  scroll position when the window shrinks, so the newest row can end up above
  the fold. Call `scroll_to_end()` after the field gains focus if the screen
  is a conversation.
- **It was measured on one API level.** On API 24-29 a screen with no
  scrolling view in it can resolve to `adjustPan` instead, which slides the
  whole window up rather than resizing it. If your app supports those levels
  and puts a field near the bottom of a non-scrolling screen, check it there.

## Visual parity is a contract, not pixel identity

Text metrics, system fonts and native controls can differ slightly. The goal is
the same hierarchy, spacing, color, behavior and responsive decisions. Native
Android conventions take precedence for permission dialogs, media controllers,
date pickers and notifications.

When a mismatch is a library bug, fix both the Previewer renderer and the
generator. Editing only generated Java is temporary because a later
`apkpy build` regenerates it.

### The strip along the top

The Previewer draws a clock and the signal, wifi and battery marks so a screen
is composed against the same 24dp the phone takes. It is scenery -- there is no
carrier, no network and no battery behind it -- and the phone draws its own.

The marks are vectors on the icon catalogue's 24x24 grid, rasterised by the
same antialiasing pass every `icon=` goes through, and they take the app bar's
colours. They used to be block characters borrowed from the system font, which
at that size read as a row of dashes.

### A number with no name is a number each side guesses

The mismatches that survive longest are not the loud ones. They are the values
both renderers had to pick, that nobody ever wrote down, so each side picked
something reasonable in its own file and neither looked wrong on its own.

Two were found and repaired in 1.5.0, and they have the same shape:

| What | Previewer | Android |
| --- | --- | --- |
| `label()` with no stylesheet | 14px | 16sp |
| the bottom bar's active label | bold, 10pt (13.3px) | normal, 12sp |

Neither was a rendering bug. Both were two literals, written into two files at
different times, with no shared name to disagree about. `label()` is the most
used component in the library, so that one was in every app ever built.

The repair in both cases was the same, and it is the pattern worth copying:
**give the value a name in a neutral module both sides import**, then let each
renderer read it. `apkpy_lib/theme.py` holds the type ramp,
`apkpy_lib/motion.py` the durations, `apkpy_lib/icons.py` the glyphs. A test
that asserts both sides resolve the same value from the same table is what
keeps them from drifting again -- a test comparing two hard-coded numbers only
proves that somebody typed the same thing twice.

When you find one of these, check the platform before choosing a side. The
bottom-bar label was settled by reading Material's own
`Widget.MaterialComponents.BottomNavigationView`, which points the active and
inactive text appearances at the same 12sp caption -- so the phone was right
and the desktop was inventing a third state signal.

## Release test

1. Exercise every primary action in the Previewer.
2. Build a fresh project rather than reusing stale generated files.
3. Compare a narrow phone and a wide/tablet layout.
4. Test loading, empty, error and offline states.
5. Put the app in the background during media, upload, GPS and WebSocket work.
6. Test a physical device before store release.
