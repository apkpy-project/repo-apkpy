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

## Visual parity is a contract, not pixel identity

Text metrics, system fonts and native controls can differ slightly. The goal is
the same hierarchy, spacing, color, behavior and responsive decisions. Native
Android conventions take precedence for permission dialogs, media controllers,
date pickers and notifications.

When a mismatch is a library bug, fix both the Previewer renderer and the
generator. Editing only generated Java is temporary because a later
`apkpy build` regenerates it.

## Release test

1. Exercise every primary action in the Previewer.
2. Build a fresh project rather than reusing stale generated files.
3. Compare a narrow phone and a wide/tablet layout.
4. Test loading, empty, error and offline states.
5. Put the app in the background during media, upload, GPS and WebSocket work.
6. Test a physical device before store release.
