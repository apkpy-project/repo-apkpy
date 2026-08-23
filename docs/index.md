---
title: ApkPy
description: Build native Android Java, XML and Gradle projects from a supported declarative Python API.
---

<section class="home-hero">
  <div class="home-hero__copy">
    <span class="eyebrow">APKPY / PYTHON → ANDROID</span>
    <h1>Write the app in Python.<br><span>Keep the Android output.</span></h1>
    <p>ApkPy is a source-to-source compiler for native Android apps. You describe screens, state and callbacks in Python; ApkPy generates Activities, XML layouts, drawables, resources and manifest entries that Android understands directly.</p>
    <div class="home-hero__actions">
      <a class="md-button md-button--primary" href="getting-started/">Install and build</a>
      <a class="md-button home-hero__secondary" href="tutorial-end-to-end/">Build the tutorial app</a>
      <a class="md-button home-hero__secondary" href="can-apkpy-build-this/">Can it build my app?</a>
      <a class="text-link" href="architecture/">Read how generation works <span>→</span></a>
    </div>
    <div class="hero-facts" aria-label="ApkPy output facts">
      <span><strong>1</strong> Python source tree</span>
      <span><strong>0</strong> Python runtimes in the APK</span>
      <span><strong>185</strong> transpiler checks</span>
      <span><strong>83</strong> focused unit tests</span>
    </div>
  </div>
  <div class="editor-card" aria-label="Example ApkPy source code">
    <div class="editor-card__bar">
      <span class="window-dot window-dot--red"></span><span class="window-dot window-dot--amber"></span><span class="window-dot window-dot--green"></span>
      <span class="editor-card__file">writehere.py</span>
      <span class="editor-card__state">preview ready</span>
    </div>
    <pre><code><span class="code-muted">01</span> <span class="code-keyword">from</span> apkpy_lib <span class="code-keyword">import</span> Screen, Theme
<span class="code-muted">02</span> <span class="code-keyword">from</span> apkpy_lib <span class="code-keyword">import</span> card, button, run
<span class="code-muted">03</span>
<span class="code-muted">04</span> home = Screen(id=<span class="code-string">"home"</span>, scroll=<span class="code-bool">True</span>)
<span class="code-muted">05</span> card(title=<span class="code-string">"Available balance"</span>,
<span class="code-muted">06</span>      content=<span class="code-string">"€ 8,420.16"</span>, screen=home)
<span class="code-muted">07</span> button(<span class="code-string">"Transfer"</span>, variant=<span class="code-string">"filled"</span>,
<span class="code-muted">08</span>        command=open_transfer, screen=home)
<span class="code-muted">09</span>
<span class="code-muted">10</span> run(start_screen=home, theme=Theme(mode=<span class="code-string">"dark"</span>))<span class="code-caret"></span></code></pre>
    <div class="editor-card__footer"><span>Python AST</span><span>4 screens</span><span>Java + XML</span></div>
  </div>
</section>

<div class="release-line">
  <span class="release-line__pulse"></span>
  <strong>ApkPy 1.3.2</strong>
  <span>Persistent background jobs that survive backgrounding, network loss and a reboot</span>
  <a href="background-jobs/">Explore background jobs</a>
</div>

<section class="home-errors">
  <div class="home-errors__copy">
    <span class="eyebrow">FRIENDLY DIAGNOSTICS</span>
    <h2>The error should tell you what to change.</h2>
    <p>Previewer callbacks, imports, Data Core declarations, compilation and Android toolchain checks now share one readable report: a stable code, the useful application line, the original cause and a concrete correction.</p>
    <div class="home-errors__tags"><span>source location</span><span>did you mean?</span><span>safe debug mode</span></div>
    <a class="md-button md-button--primary" href="friendly-errors/">Learn to read an ApkPy error</a>
  </div>
  <div class="home-errors__terminal" aria-label="Example friendly ApkPy error">
    <div><span></span><span></span><span></span><small>apkpy preview</small></div>
    <pre><code><b>APKPY E1102</b> - This import is not available

<i>Where</i>
  writehere.py:1

<i>Received</i>
  bottom_nva

<i>How to fix</i>
  1. Did you mean:
     <strong>from apkpy_lib import bottom_nav</strong></code></pre>
  </div>
</section>

<section class="home-proof">
  <div>
    <span>MEASURED ON ANDROID</span>
    <strong>5.38 MiB debug APK in the Benchmark Notes test.</strong>
    <p>The same 100-note app was built with ApkPy, Flet and BeeWare/Toga, then installed and measured on one emulator. The programs, line counts, raw starts, memory samples and artifact hashes are available for review.</p>
  </div>
  <a href="benchmark/">Inspect the benchmark <span>→</span></a>
</section>

<section class="home-proof">
  <div>
    <span>INSPECTABLE OUTPUT</span>
    <strong>Python in. Native Android out.</strong>
    <p>Open the generated Java, XML and Gradle project in Android Studio. ApkPy does not hide a web page or Python interpreter inside the APK.</p>
  </div>
  <a href="trust-maturity/">See the validation evidence <span>→</span></a>
</section>

## Start from the product you are building

If this is your first project, use the
[complete Knowledge Vault tutorial](tutorial-end-to-end.md) before choosing a
feature-specific guide. It ends with a generated Android project you can open
and inspect.

<div class="guide-path-grid guide-path-grid--home">
  <a href="reactive-data/"><strong>Live relational data</strong><span>Foreign keys, batched includes and queries that follow screen lifecycle.</span></a>
  <a href="data-core/"><strong>Local data and migrations</strong><span>Typed models, indexed queries, transactions and safe upgrades.</span></a>
  <a href="guides/feed-api/"><strong>Social or catalog feed</strong><span>Pagination, refresh and optimistic actions.</span></a>
  <a href="guides/chat-realtime/"><strong>Chat or live activity</strong><span>WebSocket reconnect, queued sends and push.</span></a>
  <a href="guides/media-player/"><strong>Music or media app</strong><span>Background playback, playlists and lock screen.</span></a>
  <a href="guides/maps-tracking/"><strong>Delivery or tracking</strong><span>Maps, fused location and calculated routes.</span></a>
  <a href="guides/knowledge-app/"><strong>Notes or knowledge</strong><span>Native Markdown, rich text, trees and SQLite.</span></a>
  <a href="can-apkpy-build-this/"><strong>Compare complete app types</strong><span>See what ApkPy owns and what your backend owns.</span></a>
</div>

## One source file, two useful feedback loops

The Previewer is for short iteration cycles. Android generation is for checking the real platform output. They share the same declarations and callbacks, but each target does the job it is good at.

<div class="target-grid">
  <article class="target-card">
    <div class="target-card__top"><span class="target-icon">P</span><code>python writehere.py</code></div>
    <h3>Hot Previewer</h3>
    <p>Open the interface in seconds. Exercise navigation, inputs, callbacks, storage and responsive breakpoints before starting Gradle.</p>
    <ul><li>Fast UI iteration</li><li>Desktop state and callback testing</li><li>Phone, tablet and resizable presets</li></ul>
  </article>
  <article class="target-card">
    <div class="target-card__top"><span class="target-icon target-icon--android">A</span><code>apkpy build</code></div>
    <h3>Native Android project</h3>
    <p>Inspect exactly what will run on the device: Java Activities, XML layouts, Material resources, services and permissions.</p>
    <ul><li>Openable in Android Studio</li><li>No WebView or embedded Python interpreter</li><li>Device APIs stay native</li></ul>
  </article>
</div>

## What one button becomes

This is a representative view of the compiler pipeline. Names and generated attributes can vary with the screen and theme, but the mapping is direct: a Python declaration becomes an Android view and its callback becomes a Java listener.

<div class="code-journey">
  <section>
    <header><span>01</span><strong>Python source</strong><small>writehere.py</small></header>
    <pre><code>button(
    "Transfer",
    id="transfer",
    variant="filled",
    command=open_transfer,
    screen=home,
)</code></pre>
  </section>
  <div class="code-journey__arrow" aria-hidden="true">→</div>
  <section>
    <header><span>02</span><strong>Layout resource</strong><small>screen_home.xml</small></header>
    <pre><code>&lt;MaterialButton
    android:id="@+id/transfer"
    android:text="Transfer"
    android:minHeight="48dp"
    android:background="@drawable/…" /&gt;</code></pre>
  </section>
  <div class="code-journey__arrow" aria-hidden="true">→</div>
  <section>
    <header><span>03</span><strong>Activity callback</strong><small>Screen_homeActivity.java</small></header>
    <pre><code>btn_transfer.setOnClickListener(
    view -&gt; {
        pythonCallback_open_transfer();
    }
);</code></pre>
  </section>
</div>

<p class="inline-note"><strong>Generated code is an output.</strong> Keep behavior in <code>writehere.py</code>; rebuilding may replace the Android files. <a href="core-concepts/">Read the source-of-truth rules →</a></p>

## A real Android project, not a screenshot exporter

The compiler creates only the helpers a project needs. A simple screen stays small; media, OAuth, advanced layout or image caching add their runtime pieces when those APIs appear in the source.

<div class="project-tree">
  <div class="project-tree__head"><span>generated-project/</span><span>typical output</span></div>
  <pre><code><span class="tree-folder">app/src/main/</span>
├── <span class="tree-file">AndroidManifest.xml</span>       <span class="tree-comment"># activities, services, permissions</span>
├── <span class="tree-folder">java/com/example/app/</span>
│   ├── <span class="tree-file">Screen_homeActivity.java</span>
│   ├── <span class="tree-file">Screen_libraryActivity.java</span>
│   └── <span class="tree-file">ApkpyMediaService.java</span> <span class="tree-comment"># only when media is used</span>
└── <span class="tree-folder">res/</span>
    ├── <span class="tree-folder">layout/</span>               <span class="tree-comment"># phone layouts</span>
    ├── <span class="tree-folder">layout-sw600dp/</span>       <span class="tree-comment"># tablet layouts when responsive</span>
    ├── <span class="tree-folder">drawable/</span>             <span class="tree-comment"># shapes, vectors and local images</span>
    ├── <span class="tree-folder">menu/</span>                 <span class="tree-comment"># navigation and toolbar actions</span>
    └── <span class="tree-folder">values/</span>               <span class="tree-comment"># themes, colors and strings</span></code></pre>
</div>

## Build more than static screens

<div class="capability-ledger">
  <div><span>Interface</span><strong>Theme · cards · lists · grids · flex · responsive · app bars</strong><p>Compose a reusable hierarchy and override it through component or ID selectors.</p></div>
  <div><span>State</span><strong>Inputs · callbacks · loops · conditions · content states</strong><p>Read and update values using normal supported Python control flow.</p></div>
  <div><span>Data</span><strong>SQLite · REST · encrypted storage · files</strong><p>Keep local data, call APIs and download private app files without a separate plugin layer.</p></div>
  <div><span>Feeds</span><strong>Pagination · refresh · keyed merge · optimistic rollback</strong><p>Keep long timelines responsive while the application remains in control of cursors and conflict rules.</p></div>
  <div><span>Media</span><strong>Queues · background audio · playlists · mini-player</strong><p>Generate an Android foreground media service, notification controls and persistent libraries.</p></div>
  <div><span>Identity</span><strong>OAuth 2.0 + PKCE · Google · Spotify · GitHub</strong><p>Use browser authorization and generated deep-link handling without embedding a client secret.</p></div>
  <div><span>Device</span><strong>Camera · gallery · location · notifications · app inspection</strong><p>Declare the API and let ApkPy add the matching permission and native Android integration.</p></div>
  <div><span>Documents</span><strong>Rich spans · Markdown · expandable trees</strong><p>Build notes, articles, comments and knowledge bases with native selectable text and recycled hierarchy rows.</p></div>
</div>

<p class="inline-note"><strong>No browser hidden in the app.</strong>
<code>rich_text()</code> and <code>markdown()</code> compile to Android
<code>Spannable</code> text, while <code>tree_view()</code> uses a native
visible-row <code>RecyclerView</code>.
<a href="rich-content/">Open the native rich-content guide →</a></p>

## Native audio is already a system player

ApkPy's music API is not limited to playing a sound inside the current screen.
The generated Android project can keep a queue in a foreground media service,
publish a native `MediaSession`, show metadata and previous/play/next controls
in the notification and lock screen, handle audio focus, synchronize a full
player and mini-player, and keep favourites and editable playlists.

~~~ python
audio.play_background(
    "https://cdn.example.com/night-drive.mp3",
    title="Night Drive",
    artist="Nova",
    art="https://cdn.example.com/night-drive.jpg",
)

audio.now_playing(progress=seek, time=elapsed, cover=cover,
                  title=title, artist=artist)
audio.controls(play_pause=play_pause, shuffle=shuffle, repeat=repeat)
mini_player(open=player)
~~~

[See the complete capability matrix, queues, playlists and offline files](media-auth.md).
The documentation also states the current limits clearly: automatic audio
caching, adaptive quality, guaranteed gapless playback, crossfade and DRM are
not claimed as supported features.

## Data code you can ship

SQLite, REST and cryptography are part of the normal ApkPy workflow. The Previewer uses local Python backends for fast testing; Android generation maps the same calls to `SQLiteDatabase`, background `HttpURLConnection`, `SharedPreferences` and Android Keystore.

<div class="data-lab">
  <article class="data-card data-card--sqlite">
    <header><span class="data-card__icon">DB</span><div><strong>SQLite</strong><small>parameter binding + transactions</small></div></header>
    <pre><code>db.execute(
    "CREATE TABLE IF NOT EXISTS tracks "
    "(id INTEGER PRIMARY KEY, title TEXT)"
)

db.execute(
    "INSERT INTO tracks(title) VALUES (?)",
    [title_input.get_value()],
)

rows = db.query(
    "SELECT id, title FROM tracks "
    "ORDER BY id DESC"
)
track_list.set_items(rows, title="title", subtitle="id")</code></pre>
    <p>The <code>?</code> placeholder is bound by SQLite instead of concatenated into the query. This handles apostrophes correctly and prevents SQL injection.</p>
    <a href="data-security/#sqlite">Transactions and query results →</a>
  </article>

  <article class="data-card data-card--api">
    <header><span class="data-card__icon">HTTP</span><div><strong>REST APIs</strong><small>GET, POST, PUT, PATCH and DELETE</small></div></header>
    <pre><code>def loaded(success, response):
    if success:
        tracks.set_items(
            response,
            title="name",
            subtitle="artist",
            image="cover",
        )
    else:
        snackbar("Could not refresh library")

https.get(
    "https://api.example.com/tracks",
    headers={"Authorization": "Bearer " + auth.token()},
    on_response=loaded,
)</code></pre>
    <p>Requests run away from the UI thread. The callback receives the body on success and also receives structured error bodies for HTTP 4xx/5xx responses.</p>
    <a href="data-security/#https">See the complete REST surface →</a>
  </article>

  <article class="data-card data-card--crypto">
    <header><span class="data-card__icon">KEY</span><div><strong>Encryption</strong><small>AES-256-GCM + PBKDF2</small></div></header>
    <pre><code># storage is encrypted automatically
storage.set("session", auth.token())
token = storage.get("session", "")

# hash values that must only be verified
password_hash = crypto.hash_password(password)
valid = crypto.verify_password(candidate, password_hash)

# encrypt database fields that must be read later
ciphertext = crypto.encrypt(private_note)
db.execute(
    "INSERT INTO notes(content) VALUES (?)",
    [ciphertext],
)
plain_text = crypto.decrypt(ciphertext)</code></pre>
    <p>Android keeps the AES key in Android Keystore. Passwords use salted PBKDF2 with 200,000 iterations and should never be stored with reversible encryption.</p>
    <a href="data-security/#password-hashing">Read the threat model →</a>
  </article>
</div>

<div class="security-boundary">
  <strong>Client-side security has a boundary.</strong>
  <p>Do not put permanent service secrets inside an APK. Use HTTPS, short-lived tokens or OAuth with PKCE, and keep privileged authorization on a server you control.</p>
</div>

## Four small products used as regression tests

The showcase is executable code, not a set of design mockups. Every app has four screens, working navigation and generated Android output. Together they deliberately exercise different palettes and layout choices.

<div class="showcase-grid showcase-grid--home">
  <a class="showcase-card" href="showcase/#lumen-personal-finance">
    <div class="app-shot"><img src="assets/showcase/lumen-finance.png" alt="Lumen personal finance dashboard built with ApkPy"></div>
    <div class="showcase-copy"><span class="showcase-tag">LIGHT / FINANCE</span><h3>Lumen</h3><p>Balance surfaces, transactions, Material actions and four destinations.</p><span class="card-link">Open case study →</span></div>
  </a>
  <a class="showcase-card" href="showcase/#onda-daily-wellbeing">
    <div class="app-shot"><img src="assets/showcase/onda-wellness.png" alt="Onda daily wellness dashboard built with ApkPy"></div>
    <div class="showcase-copy"><span class="showcase-tag">DARK / WELLBEING</span><h3>Onda</h3><p>Responsive metrics, semantic status colors and a quiet daily plan.</p><span class="card-link">Open case study →</span></div>
  </a>
  <a class="showcase-card" href="showcase/#northline-travel-companion">
    <div class="app-shot"><img src="assets/showcase/northline-travel.png" alt="Northline travel itinerary built with ApkPy"></div>
    <div class="showcase-copy"><span class="showcase-tag">TRAVEL / APP BAR</span><h3>Northline</h3><p>A boarding pass, itinerary hierarchy and practical trip actions.</p><span class="card-link">Open case study →</span></div>
  </a>
  <a class="showcase-card" href="showcase/#afterglow-music-discovery">
    <div class="app-shot"><img src="assets/showcase/afterglow-music.png" alt="Afterglow music discovery app built with ApkPy"></div>
    <div class="showcase-copy"><span class="showcase-tag">MEDIA / LOCAL ART</span><h3>Afterglow</h3><p>Packaged artwork, track rows, listening actions and a saved library.</p><span class="card-link">Open case study →</span></div>
  </a>
</div>

## The workflow in three commands

<div class="command-rail command-rail--technical">
  <div><span class="command-index">01</span><code>python writehere.py</code><strong>Iterate</strong><p>Open the Hot Previewer and test interface behavior.</p></div>
  <div><span class="command-index">02</span><code>apkpy build</code><strong>Inspect</strong><p>Generate a ZIP project for Android Studio.</p></div>
  <div><span class="command-index">03</span><code>apkpy run</code><strong>Install</strong><p>Compile a debug APK; add <code>--qr</code> or <code>--usb</code>.</p></div>
</div>

## Questions developers usually ask

<div class="technical-faq">
  <details><summary>Does the APK contain Python?</summary><p>No. ApkPy compiles the supported source model into native Android Java, XML and resources. The generated application does not bundle a Python interpreter.</p></details>
  <details><summary>Can I open the result in Android Studio?</summary><p>Yes. <code>apkpy build</code> produces a Gradle project ZIP intended for inspection, emulator testing and normal Android tooling.</p></details>
  <details><summary>Is every Python library supported?</summary><p>No. ApkPy supports a deliberate Python subset plus its own Android-facing APIs. Arbitrary CPython packages cannot automatically become Java. The <a href="api-reference/">API reference</a> is the contract.</p></details>
  <details><summary>Should I trust only the desktop preview?</summary><p>No. Use the Previewer for fast feedback, then test device-only behavior, permissions, services and final rendering on an emulator or physical Android device. <a href="preview-android/">See the renderer comparison.</a></p></details>
</div>

<section class="closing-panel">
  <span class="eyebrow">START WITH A SMALL SCREEN</span>
  <h2>Install ApkPy, open the Previewer, then inspect what it generated.</h2>
  <div><a class="md-button md-button--primary" href="getting-started/">Follow the installation guide</a><a href="api-reference/">Browse the public API →</a></div>
</section>

!!! note "Closed source, public contract"
    ApkPy's compiler is proprietary while active development continues. Open-sourcing may be considered later; if the project is permanently abandoned, the core source will be released as open source so it can be maintained and continued. Until an explicit source release and new licence are published, the current proprietary licence remains in force. [Read the project continuity policy.](project-continuity.md)
