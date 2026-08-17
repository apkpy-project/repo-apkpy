---
title: Practical guides
description: Complete ApkPy workflows from a Python screen to native Android behavior.
---

# Practical guides

These guides are task-oriented. Each one shows the Python declaration, the
generated Android behavior and the part that remains under application control.

For a single continuous path through installation, a real two-screen app,
Previewer validation and Android generation, follow the
[end-to-end Knowledge Vault tutorial](../tutorial-end-to-end.md).

<div class="guide-hub">
  <a href="../data-core/"><span>00</span><strong>Typed local data</strong><p>Models, indexed queries, transactions and explicit migrations.</p></a>
  <a href="feed-api/"><span>01</span><strong>API-backed feed</strong><p>Pagination, refresh, retry and optimistic rows.</p></a>
  <a href="chat-realtime/"><span>02</span><strong>Real-time chat</strong><p>WebSocket lifecycle, pending sends and reconnect.</p></a>
  <a href="push-firebase/"><span>03</span><strong>Firebase push</strong><p>Token, topics, foreground events and Android setup.</p></a>
  <a href="media-player/"><span>04</span><strong>Spotify-style audio</strong><p>Background service, playlists and lock-screen controls.</p></a>
  <a href="sqlite-security/"><span>05</span><strong>SQLite and encryption</strong><p>Legacy SQL, protected values and security boundaries.</p></a>
  <a href="uploads/"><span>06</span><strong>Streaming uploads</strong><p>Multipart progress, cancellation and result handling.</p></a>
  <a href="maps-tracking/"><span>07</span><strong>Maps and tracking</strong><p>Device location, preview simulation and calculated routes.</p></a>
  <a href="knowledge-app/"><span>08</span><strong>Knowledge app</strong><p>Markdown, inline spans, trees and local documents.</p></a>
</div>

## How to use a guide

1. Copy the smallest example into `writehere.py`.
2. Confirm callbacks and layout in the Hot Previewer.
3. Run `apkpy build`.
4. Open the generated project in Android Studio.
5. Test platform behavior on an emulator and a physical device.

The Previewer is a fast development surface. Permission dialogs, codecs,
background restrictions, Firebase and GPS must still be validated on Android.
