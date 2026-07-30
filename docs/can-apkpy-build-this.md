---
title: Can ApkPy build this?
description: An honest capability matrix for building social, media, delivery and knowledge apps with ApkPy.
---

# Can ApkPy build this?

ApkPy can generate a large part of a modern Android client, but it does not
replace the product backend. Use this page to separate native interface
capabilities from infrastructure that your application must still own.

<div class="capability-controls" role="group" aria-label="Filter app types">
  <button class="capability-filter is-active" type="button" data-capability-filter="all">All</button>
  <button class="capability-filter" type="button" data-capability-filter="social">Social</button>
  <button class="capability-filter" type="button" data-capability-filter="media">Media</button>
  <button class="capability-filter" type="button" data-capability-filter="live">Real time</button>
  <button class="capability-filter" type="button" data-capability-filter="location">Location</button>
  <button class="capability-filter" type="button" data-capability-filter="knowledge">Knowledge</button>
</div>

<div class="capability-grid" id="capability-grid">
  <article class="capability-card" data-capabilities="social media live">
    <span class="capability-card__status capability-card__status--strong">Strong client fit</span>
    <h2>Instagram / Facebook</h2>
    <p>Virtual feeds, pagination, optimistic likes, uploads, profiles, video, WebSocket events and push notifications.</p>
    <small>You still provide accounts, moderation, recommendations, storage and the social graph.</small>
  </article>
  <article class="capability-card" data-capabilities="social live">
    <span class="capability-card__status capability-card__status--strong">Strong client fit</span>
    <h2>X / Reddit</h2>
    <p>Keyed feed updates, threads, Markdown, trees, votes, live events, notifications and cached local data.</p>
    <small>You still provide ranking, search, anti-abuse systems and canonical server state.</small>
  </article>
  <article class="capability-card" data-capabilities="live social media">
    <span class="capability-card__status capability-card__status--partial">Good foundation</span>
    <h2>WhatsApp-style chat</h2>
    <p>Persistent WebSockets, reconnect, queued sends, uploads, push, local SQLite history and encrypted local values.</p>
    <small>ApkPy does not provide an end-to-end encryption protocol, calls or multi-device reconciliation.</small>
  </article>
  <article class="capability-card" data-capabilities="media social">
    <span class="capability-card__status capability-card__status--partial">Good foundation</span>
    <h2>TikTok / Reels</h2>
    <p>Native Media3 video, buffering callbacks, seek, speed, lifecycle-safe release and virtual collections.</p>
    <small>A production vertical pager, recommendation system, CDN and content moderation remain app work.</small>
  </article>
  <article class="capability-card" data-capabilities="media">
    <span class="capability-card__status capability-card__status--strong">Strong client fit</span>
    <h2>Spotify-style audio</h2>
    <p>Background playback, MediaSession, lock-screen controls, playlists, favourites, offline files and a mini-player.</p>
    <small>No automatic adaptive-quality engine, DRM, guaranteed gapless playback or crossfade is promised.</small>
  </article>
  <article class="capability-card" data-capabilities="location live">
    <span class="capability-card__status capability-card__status--strong">Strong client fit</span>
    <h2>Uber / Delivery</h2>
    <p>Maps, fused location, continuous and background tracking, route calculation, live events and push.</p>
    <small>Dispatch, pricing, ETA models, fraud protection and payments belong to your services.</small>
  </article>
  <article class="capability-card" data-capabilities="knowledge">
    <span class="capability-card__status capability-card__status--strong">Strong client fit</span>
    <h2>Notion / Notes</h2>
    <p>Native rich text, Markdown, expandable trees, SQLite, encrypted values and responsive layouts.</p>
    <small>Collaborative CRDT editing and a block-editor engine are not built into ApkPy.</small>
  </article>
  <article class="capability-card" data-capabilities="social location media">
    <span class="capability-card__status capability-card__status--strong">Strong client fit</span>
    <h2>Store / Food delivery</h2>
    <p>Catalog grids, production feeds, uploads, maps, notifications, local data and API-driven states.</p>
    <small>Inventory, checkout, payments, order validation and fulfilment require a backend.</small>
  </article>
</div>

<p class="capability-result" id="capability-result" aria-live="polite">Showing all app types.</p>

## What "client fit" means

It means ApkPy already has native generation rules for the interface and device
features in the row. It does **not** mean a clone can be produced without
servers, security design, product rules, testing and operations.

| Layer | ApkPy can own | Your application owns |
| --- | --- | --- |
| Interface | screens, themes, components, navigation, responsive layout | product design and accessibility review |
| Client state | reactive state, loading, optimistic mutations, local persistence | canonical business rules and conflict policy |
| Device | media, notifications, files, location, maps and permissions | consent text, privacy policy and device testing |
| Network | HTTPS, uploads, WebSockets, reconnect and callbacks | API, authentication authority, rate limits and observability |
| Delivery | Java/XML/Gradle generation and Android Studio project | signing, store policy, rollout and production monitoring |

## Pick a complete path

<div class="guide-path-grid">
  <a href="../guides/feed-api/"><strong>Build a production feed</strong><span>Pages, refresh, retries and optimistic actions.</span></a>
  <a href="../guides/chat-realtime/"><strong>Build a live room</strong><span>WebSocket lifecycle, queued sends and push hand-off.</span></a>
  <a href="../guides/media-player/"><strong>Build a music player</strong><span>Background audio, MediaSession and saved playlists.</span></a>
  <a href="../guides/maps-tracking/"><strong>Build live tracking</strong><span>Permissions, fused location, routes and background work.</span></a>
</div>

For exact supported names and methods, use the [modular API reference](api-reference.md).
