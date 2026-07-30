# ApkPy 1.2.0 — live data, media and device runtime { .release12-page-title }

<section class="release12-hero">
  <div>
    <span class="release12-kicker">VERSION 1.2.0 / RELEASED 2026-07-27</span>
    <h2>The interface no longer waits for the app.</h2>
    <p>ApkPy 1.2.0 connects the component tree to large datasets, observable state, streaming transfers, persistent sockets, native video, remote push, continuous location and structured documents. The same Python callbacks still run in the Previewer and compile into an inspectable Android project.</p>
    <div class="release12-actions">
      <a class="md-button md-button--primary" href="#capability-explorer">Explore the runtime</a>
      <a href="#generated-output">See generated output <span>→</span></a>
    </div>
  </div>
  <div class="release12-signal" aria-label="Version 1.2.0 capability summary">
    <div class="release12-signal__head"><span>runtime / 1.2</span><strong>released</strong></div>
    <div class="release12-signal__line"><span>01</span><b>collections</b><i>RecyclerView</i></div>
    <div class="release12-signal__line"><span>02</span><b>state</b><i>observable</i></div>
    <div class="release12-signal__line"><span>03</span><b>transfers</b><i>streaming</i></div>
    <div class="release12-signal__line"><span>04</span><b>realtime</b><i>WSS</i></div>
    <div class="release12-signal__line"><span>05</span><b>video</b><i>Media3</i></div>
    <div class="release12-signal__line"><span>06</span><b>push</b><i>FCM</i></div>
    <div class="release12-signal__line"><span>07</span><b>location</b><i>Fused</i></div>
    <div class="release12-signal__line"><span>08</span><b>documents</b><i>Spannable</i></div>
  </div>
</section>

<div class="release12-status">
  <span class="release12-status__dot"></span>
  <strong>Release build</strong>
  <span>Documented from the public API and verified generated Android output.</span>
</div>

!!! info "Native verification still matters"
    The release passed compiler tests and a real Android Java compilation.
    Device integrations should still be tested on an emulator or physical
    Android device as part of each application's own release process.

## What this update changes

1. **Large collections stop allocating every row.** A template is recycled for
   visible items in the Previewer and Android `RecyclerView`.
2. **State becomes observable.** Text and visibility bindings update when the
   value changes, while lifecycle callbacks stop screen work at the right time.
3. **Uploads stream instead of buffering entire files.** Progress,
   cancellation, form fields and Android content URIs use one API.
4. **WebSocket connections become a supported runtime primitive.** Messages,
   reconnects, ping/pong and a bounded pre-connect queue stay off the UI thread.
5. **Video becomes native media.** The Previewer plays real picture and sound;
   Android uses Media3/ExoPlayer for progressive MP4, HLS and DASH.
6. **Remote push becomes conditional Android output.** FCM code and Gradle
   dependencies are generated only when the app is configured for push.
7. **Maps and location become continuous.** Key-free OpenStreetMap tiles,
   Fused Location, route calculation and an Android 14 foreground location
   service share one declarative surface.
8. **Documents stay native.** Rich inline spans and Markdown compile to
   selectable Android text, while expandable trees recycle only visible rows.

## Capability explorer

<div id="capability-explorer" class="release12-explorer" data-release12-explorer>
  <div class="release12-explorer__tabs" role="tablist" aria-label="Version 1.2.0 capabilities">
    <button type="button" role="tab" aria-selected="true" data-release12-tab="collections">Collections</button>
    <button type="button" role="tab" aria-selected="false" data-release12-tab="state">State</button>
    <button type="button" role="tab" aria-selected="false" data-release12-tab="uploads">Uploads</button>
    <button type="button" role="tab" aria-selected="false" data-release12-tab="websocket">WebSocket</button>
    <button type="button" role="tab" aria-selected="false" data-release12-tab="video">Video</button>
    <button type="button" role="tab" aria-selected="false" data-release12-tab="push">Push</button>
    <button type="button" role="tab" aria-selected="false" data-release12-tab="location">Maps + GPS</button>
    <button type="button" role="tab" aria-selected="false" data-release12-tab="documents">Documents</button>
  </div>
  <div class="release12-explorer__stage" aria-live="polite">
    <article data-release12-panel="collections">
      <span>VISIBLE WORK ONLY</span><h3>Thousands of records, a handful of row views.</h3>
      <p>Use it for music queues, message history, feeds, catalogues and search results. Change the template without changing the dataset.</p>
      <dl><div><dt>Previewer</dt><dd>Materializes the visible window plus a small buffer.</dd></div><div><dt>Android</dt><dd>Generates RecyclerView, Adapter and recycled ViewHolders.</dd></div></dl>
    </article>
    <article data-release12-panel="state" hidden>
      <span>DATA DRIVES UI</span><h3>Callbacks change values, not individual widgets.</h3>
      <p>One value can update several labels and visibility targets. Screen lifecycle callbacks connect and release observers predictably.</p>
      <dl><div><dt>Bindings</dt><dd>Value templates and conditional visibility.</dd></div><div><dt>Lifecycle</dt><dd>Mount, resume, pause and destroy.</dd></div></dl>
    </article>
    <article data-release12-panel="uploads" hidden>
      <span>BOUNDED MEMORY</span><h3>Multipart transfers with progress and cancellation.</h3>
      <p>Files, images, audio and video share a streaming encoder. ApkPy owns the multipart boundary so application headers cannot corrupt the body.</p>
      <dl><div><dt>Progress</dt><dd>Percent, bytes sent and total bytes.</dd></div><div><dt>Android</dt><dd>File paths and content:// URIs.</dd></div></dl>
    </article>
    <article data-release12-panel="websocket" hidden>
      <span>PERSISTENT CHANNEL</span><h3>Chat, presence, live likes and order events.</h3>
      <p>WSS frames are handled away from the UI thread with ping/pong, intentional close and bounded exponential reconnect behavior.</p>
      <dl><div><dt>Handshake</dt><dd>Queues up to 64 outgoing messages.</dd></div><div><dt>Recovery</dt><dd>Bounded backoff after network changes.</dd></div></dl>
    </article>
    <article data-release12-panel="video" hidden>
      <span>REAL PLAYBACK</span><h3>One player surface in both feedback loops.</h3>
      <p>The Previewer decodes picture and sound with drag seeking. The Android project uses Media3 and releases the player with the Activity lifecycle.</p>
      <dl><div><dt>Sources</dt><dd>Progressive MP4, HLS and DASH on Android.</dd></div><div><dt>Controls</dt><dd>Play, pause, seek, speed, mute and source changes.</dd></div></dl>
    </article>
    <article data-release12-panel="push" hidden>
      <span>OUTSIDE THE SCREEN</span><h3>Delivery, token refresh and topic subscriptions.</h3>
      <p>The Previewer delivers deterministic local events. Configured Android apps receive FCM callbacks and native system notifications.</p>
      <dl><div><dt>Local test</dt><dd>push.simulate() uses the same callbacks.</dd></div><div><dt>Android</dt><dd>Conditional Firebase plugin and messaging service.</dd></div></dl>
    </article>
    <article data-release12-panel="location" hidden>
      <span>DEVICE-AWARE MOVEMENT</span><h3>The map follows GPS without fighting the user.</h3>
      <p>Starting tracking enables follow mode. A manual pan or pinch disables it, and the app can opt back in when the user presses recenter or Start.</p>
      <dl><div><dt>Foreground</dt><dd>Fused Location with filtering and fallback.</dd></div><div><dt>Background</dt><dd>Android 14 typed foreground service and START_STICKY.</dd></div></dl>
    </article>
    <article data-release12-panel="documents" hidden>
      <span>NO EMBEDDED BROWSER</span><h3>Notes, posts and trees become native views.</h3>
      <p>Use exact inline spans, readable Markdown and expandable hierarchies for knowledge bases, social discussions, release notes and structured editors.</p>
      <dl><div><dt>Text</dt><dd>Selectable TextView content backed by Android Spannable.</dd></div><div><dt>Trees</dt><dd>RecyclerView containing only currently visible rows.</dd></div></dl>
    </article>
  </div>
</div>

## 1. Virtual collections with custom templates

`virtual_collection()` accepts ordinary dictionaries. Its template maps five
visual slots — `title`, `subtitle`, `image`, `meta` and `badge` — to fields in
each item. Only visible rows and a small overscan buffer exist as views.

~~~ python
from apkpy_lib import Screen, toast, virtual_collection

library = Screen(id="library", scroll=False)

tracks = [
    {
        "title": "Afterimage",
        "artist": "North Arcade",
        "album": "Night Transit",
        "duration": "3:42",
        "quality": "LOSSLESS",
        "artwork": "afterimage.jpg",
    },
    # The list may contain thousands of records.
]

track_list = virtual_collection(
    tracks,
    template={
        "image": "{artwork}",
        "title": "{title}",
        "subtitle": "{artist} · {album}",
        "meta": "{duration}",
        "badge": "{quality}",
    },
    layout="list",       # use "grid" with columns=... for catalogues
    item_height=92,
    buffer=3,
    on_click=lambda item: toast(item["title"]),
    screen=library,
)

# Replace the dataset without rebuilding the screen tree.
track_list.set_items(tracks)
~~~

The Previewer calculates the visible window. Android generates a
`RecyclerView.Adapter` and ViewHolders, so scrolling cost tracks the viewport
rather than the total record count.

!!! update "Extended in 1.2.1"
    [Production Feeds](version-1.2.1.md) adds guarded end-of-list pagination,
    prefetch, efficient page insertion and pull-to-refresh to this component
    without changing the 1.2.0 template model.

## 2. Reactive state and screen lifecycle

`state()` returns an observable value. A callback mutates the value once and
every binding is refreshed automatically. `lifecycle()` scopes work to a
screen instead of leaving network or playback callbacks running forever.

~~~ python
from apkpy_lib import Screen, label, lifecycle, spinner, state

queue = Screen(id="queue")
queue_count = state(2, id="queue_count")
syncing = state(False, id="syncing")
phase = state("Waiting", id="phase")

count_view = label("", screen=queue)
phase_view = label("", screen=queue)
loader = spinner(screen=queue)

queue_count.bind(count_view, "{value} tracks queued")
phase.bind(phase_view)
syncing.bind_visibility(loader, when=True)

def add_track():
    queue_count.increment()

def toggle_sync():
    syncing.toggle()

lifecycle(
    screen=queue,
    on_mount=lambda: phase.set("Mounted"),
    on_resume=lambda: phase.set("Active · observers resumed"),
    on_pause=lambda: phase.set("Paused · work suspended"),
    on_destroy=lambda: phase.set("Destroyed · resources released"),
)
~~~

Available state operations are `get()`, `set(value)`, `increment(amount)`,
`decrement(amount)`, `toggle()`, `bind(component, template)` and
`bind_visibility(component, when=True)`.

## 3. Streaming multipart uploads

Uploads use 64 KiB chunks instead of reading the whole payload into memory.
The task ID makes cancellation explicit and stable across Previewer and Java
generation.

~~~ python
from apkpy_lib import Screen, gallery, label, storage, uploads

upload_screen = Screen(id="upload")
status = label("Choose a file", screen=upload_screen)
access_token = storage.get("access_token", "")

selected_path = ""

def picked(success, path):
    global selected_path
    if success:
        selected_path = path

def progress(percent, sent, total):
    status.set_value(
        "Uploading · " + str(percent) + "% · "
        + str(sent) + "/" + str(total) + " bytes"
    )

def finished(success, response):
    if success:
        status.set_value("Upload complete")
    elif response == "cancelled":
        status.set_value("Upload cancelled safely")
    else:
        status.set_value("Upload failed · " + str(response))

def start_upload():
    if selected_path == "":
        status.set_value("Choose a file first")
        return
    uploads.image(
        "artwork-upload",
        "https://api.example.com/releases/artwork",
        selected_path,
        field="artwork",
        fields={"release_id": "482"},
        headers={"Authorization": "Bearer " + access_token},
        on_progress=progress,
        on_result=finished,
    )

def choose_file():
    gallery.pick(on_result=picked)

def cancel_upload():
    uploads.cancel("artwork-upload")
~~~

`uploads.file()`, `uploads.image()`, `uploads.audio()` and `uploads.video()`
share the same transport. ApkPy controls `Content-Type`, `Content-Length` and
the multipart boundary; application code should supply authentication and
domain-specific headers only.

## 4. WebSocket and real-time messages

The WebSocket client supports `ws://` and encrypted `wss://` endpoints,
optional headers and protocols, ping/pong, server close frames, intentional
disconnects and bounded reconnection. Messages sent during the handshake wait
in a bounded queue rather than disappearing.

~~~ python
from apkpy_lib import Screen, lifecycle, state, storage, websocket

room = Screen(id="room")
connection = "live-room"
phase = state("Offline")
latest = state("No events yet")
access_token = storage.get("access_token", "")

def opened():
    phase.set("Connected")

def received(message):
    latest.set(message)

def closed(code, reason):
    phase.set("Closed · " + code)

def failed(message):
    phase.set("Network changed · retry scheduled")

def connect_room():
    websocket.connect(
        connection,
        "wss://realtime.example.com/rooms/482",
        headers={"Authorization": "Bearer " + access_token},
        on_open=opened,
        on_message=received,
        on_close=closed,
        on_error=failed,
        reconnect=True,
        reconnect_delay=1.0,
        max_reconnect_delay=12.0,
        ping_interval=25.0,
    )

def send_message(text):
    websocket.send(connection, text)

lifecycle(
    screen=room,
    on_mount=connect_room,
    on_destroy=lambda: websocket.close(
        connection, code=1000, reason="left the room"
    ),
)
~~~

The connection runs away from the UI thread. Callbacks return to the interface
thread in both targets, which makes them safe inputs for reactive state.

## 5. Native video with Media3

The normal ApkPy installation includes the Previewer video dependencies. The
desktop player displays real frames and sound, supports drag seeking and hides
its controller after inactivity. Android uses Media3/ExoPlayer and the native
`PlayerView` controller.

~~~ python
from apkpy_lib import Screen, label, video

watch = Screen(id="watch", scroll=True)
status = label("Preparing video", screen=watch)

def progress(position, duration, buffered):
    status.set_value(
        str(position) + "s / " + str(duration)
        + "s · " + str(buffered) + "% buffered"
    )

player = video(
    "https://cdn.example.com/trailers/episode-01.mp4",
    poster="episode-01.jpg",
    controls=True,
    preload=True,
    aspect_ratio="16:9",
    fit="cover",
    on_ready=lambda: status.set_value("Ready"),
    on_progress=progress,
    on_end=lambda: status.set_value("Finished"),
    on_error=lambda message: status.set_value("Error · " + str(message)),
    screen=watch,
)

player.play()
player.pause()
player.seek(30)
player.set_speed(1.25)
player.set_muted(False)
~~~

The returned component also exposes `stop()` and
`set_source(url, autoplay=False)`. Player preparation, pause/resume behavior
and release are connected to the Activity lifecycle.

## 6. Remote push with Firebase Cloud Messaging

The event callbacks are shared. `push.simulate()` makes the Previewer
deterministic; a configured Android build receives real Firebase messages,
registration-token changes and native notification delivery.

~~~ python
from apkpy_lib import Screen, push, state

updates_screen = Screen(id="updates")
delivery = state("Waiting for an update")
device_token = state("No token yet")

def message_received(title, body, data_json):
    delivery.set(title + " · " + body)

def token_changed(token):
    device_token.set(token)

def subscription_finished(success, value):
    delivery.set("Subscribed · " + value if success else "Push unavailable")

def token_finished(success, value):
    device_token.set(value if success else "Token unavailable")

push.listen(
    screen=updates_screen,
    on_message=message_received,
    on_token=token_changed,
    on_error=lambda message: delivery.set("Push error · " + message),
    auto_notify=True,
    channel_id="order_updates",
    channel_name="Order updates",
)

push.subscribe("live-orders", on_result=subscription_finished)
push.get_token(on_result=token_finished)

def simulate_delivery():
    # Deterministic Previewer delivery through the same callback.
    push.simulate(
        "Courier nearby",
        "Your order is approaching",
        {"order_id": "482", "kind": "delivery"},
    )
~~~

Place `google-services.json` beside `writehere.py` for a real Firebase-enabled
Android build. ApkPy then adds the Firebase Gradle plugin, messaging dependency,
service and required manifest entries. Projects that do not use push receive
none of that output.

## 7. Maps, routes and continuous location

`map_view()` uses OpenStreetMap raster tiles without a bundled map-vendor key.
Markers, the route and the user's live position are separate layers. That is
why a map can show a start marker, a finish marker and a third live-position
dot at the same time.

~~~ python
from apkpy_lib import Screen, label, map_view, location, routes

trip_screen = Screen(id="trip", scroll=True)
status = label("Tracking is paused", screen=trip_screen)

DEMO_PATH = [
    [37.7750, -122.4183],
    [37.7762, -122.4168],
    [37.7774, -122.4151],
]

trip_map = map_view(
    markers=[
        {"lat": 37.7750, "lng": -122.4183,
         "title": "Start", "color": "#8B5CF6"},
        {"lat": 37.7774, "lng": -122.4151,
         "title": "Finish", "color": "#22D3EE"},
    ],
    route=DEMO_PATH,
    show_user=True,
    follow_user=True,
    cache_days=7,
    screen=trip_screen,
)

def location_sample(success, latitude, longitude, accuracy, speed,
                    bearing, timestamp, provider, is_mock):
    if success:
        trip_map.set_location(latitude, longitude, accuracy)

def start_tracking():
    # A pan or pinch disables camera follow. Start opts back in.
    trip_map.set_follow_user(True)
    location.watch(
        "active-trip",
        on_sample=location_sample,
        interval=1200,
        min_distance=0,
        accuracy="high",
        provider="auto",
        max_age=12000,
        max_accuracy=150,
        timeout=20000,
        preview_route=DEMO_PATH,
        screen=trip_screen,
    )

def start_background_tracking():
    trip_map.set_follow_user(True)
    location.start_background_tracking(
        "background-trip",
        on_sample=location_sample,
        title="Trip tracking is active",
        text="Tap to return to the route",
        interval=5000,
        min_distance=0,
        preview_route=DEMO_PATH,
        screen=trip_screen,
    )
~~~

Android uses `FusedLocationProviderClient`, with `LocationManager` as a
fallback. It filters stale or excessively inaccurate readings, uses an Android
14 foreground service declared as `location`, and returns `START_STICKY` so the
system can restore a long-running trip after memory pressure.

Manual pan or pinch intentionally disables camera following. Calling
`set_follow_user(True)` recentres on the latest reading. Longitude animation
uses the shortest path across the `180/-180` date-line boundary.

### Street-aware routes are an explicit network action

Route calculation does not move the GPS dot. It replaces the route geometry;
`location.watch()` moves the user layer when the device or emulator reports a
new position.

~~~ python
def route_ready(success, route_json, distance, duration, error):
    if success:
        trip_map.set_route(route_json)
    else:
        status.set_value("Route unavailable · " + error)

def calculate_route():
    routes.calculate(
        "trip-route",
        [37.7750, -122.4183],
        [37.7774, -122.4151],
        on_result=route_ready,
        profile="driving",       # driving, walking or cycling
        alternatives=False,
        timeout=15,
    )

def cancel_route():
    routes.cancel("trip-route")
~~~

The default route service is the public OSRM demo endpoint. Production or
privacy-sensitive apps can supply a compatible self-hosted endpoint. No
coordinate is sent until `routes.calculate()` is called.

!!! info "Previewer versus device GPS"
    The desktop Previewer replays only the explicit `preview_route`. An Android
    emulator moves when a route is played from its Location controls. A
    physical device moves from real location samples after permission is
    granted and tracking is started.

## 8. Native rich text, Markdown and trees

`rich_text()`, `markdown()` and `tree_view()` cover structured content without
adding a WebView or JavaScript runtime. The Previewer keeps text selectable;
Android generates `SpannableStringBuilder` content and a recycled
`RecyclerView` for hierarchies.

~~~ python
from apkpy_lib import Screen, markdown, rich_text, tree_view

knowledge = Screen(id="knowledge", scroll=True)

rich_text(
    [
        {"text": "FIELD NOTE  /  04\n", "bold": True,
         "color": "#22D3EE", "size": 12},
        {"text": "Small interfaces, ", "bold": True, "size": 23},
        {"text": "deep structure.", "bold": True, "italic": True,
         "color": "#C4B5FD", "size": 23},
    ],
    id="document_lead",
    selectable=True,
    screen=knowledge,
)

markdown(
    """## Build log · 1.2

> Content remains selectable and native.

- [x] **Bold**, *italic*, ~~strike~~ and `inline code`
- [x] Lists, quotes, links and dividers
- [ ] Connect the renderer to your own storage
""",
    id="release_note",
    screen=knowledge,
)

tree_view(
    [
        {
            "key": "product",
            "title": "Product",
            "subtitle": "18 pages",
            "children": [
                {"title": "Roadmap", "subtitle": "Q3 planning"},
                {"title": "Release notes", "subtitle": "12 entries"},
            ],
        },
        {
            "key": "archive",
            "title": "Archive",
            "expanded": False,
            "children": [{"title": "2025"}, {"title": "2024"}],
        },
    ],
    id="workspace_tree",
    expand_depth=1,
    row_height=60,
    screen=knowledge,
)
~~~

The Markdown subset includes headings, emphasis, links, inline/fenced code,
quotes, ordered and unordered lists, checkboxes and dividers. Rich spans accept
`bold`, `italic`, `underline`, `strike`, `code`, `color`, `size` and `link`.
Tree nodes accept `title`, `subtitle`, `key`, `expanded` and recursive
`children`.

This is a renderer, not a storage service. A notes app can keep Markdown in
SQLite or encrypted storage, a forum can receive comment data from an API, and
a knowledge base can construct its tree from parent IDs. ApkPy renders the
result without silently sending that content elsewhere.

[Read the complete native rich-content guide](rich-content.md).

## Audio baseline clarified for 1.2.0

The following player capabilities existed before the new runtime work and are
documented here to avoid understating what ApkPy can already generate:

- local-file and URL playback;
- foreground Android media service and native `MediaSession`;
- notification and lock-screen metadata and transport controls;
- audio-focus pause, duck and resume behavior;
- queues with next, previous, shuffle and repeat;
- seeking and synchronized progress, cover, title and artist bindings;
- persistent mini-player, favourites and editable playlists;
- explicit downloads to app-private storage;
- buffering state, guarded polling and one controlled retry of the same source.

~~~ python
from apkpy_lib import audio, mini_player

audio.play_playlist(
    sources,
    titles=titles,
    artists=artists,
    arts=artwork,
    start=0,
)

audio.now_playing(
    progress=seek,
    time=elapsed,
    cover=cover,
    title=track_title,
    artist=track_artist,
)
audio.controls(play_pause=play_pause, shuffle=shuffle, repeat=repeat)
mini_player(open=player_screen)
~~~

[Open the complete audio, playlist and offline-file guide](media-auth.md).

## Generated output

<div id="generated-output" class="release12-output">
  <div><span>virtual_collection</span><strong>RecyclerView + Adapter + ViewHolder</strong><p>Only emitted when a virtual collection appears in source.</p></div>
  <div><span>state + lifecycle</span><strong>Activity fields + lifecycle overrides</strong><p>Bindings update views on the Android UI thread.</p></div>
  <div><span>uploads</span><strong>Streaming multipart worker</strong><p>Supports files and content URIs without an in-memory copy.</p></div>
  <div><span>websocket</span><strong>OkHttp WebSocket client</strong><p>Connection callbacks return to the Activity safely.</p></div>
  <div><span>video</span><strong>Media3 ExoPlayer + PlayerView</strong><p>Native playback and lifecycle-safe release.</p></div>
  <div><span>push</span><strong>Firebase messaging service</strong><p>Generated only when push is used and configured.</p></div>
  <div><span>map + location</span><strong>ApkpyMapView + Fused Location + service</strong><p>Tile cache, gestures, GPS filtering and background tracking.</p></div>
  <div><span>documents</span><strong>Spannable text + visible-row RecyclerView</strong><p>Native Markdown, inline styles and expandable trees without a WebView.</p></div>
</div>

## Current boundaries

Version 1.2.0 does not claim automatic audio quality selection, predictive
audio caching, guaranteed gapless playback, crossfade, DRM catalogue playback,
video-feed preloading, resumable uploads across process death or a hosted
WebSocket/route backend or a hosted collaborative document editor. Rich content
renders application data but does not replace storage, synchronization or
moderation. ApkPy supplies the client-side native building blocks; the
application still owns its servers, authorization policy and production data.

## Local validation snapshot

- the compiler/transpiler suite completes with **162 passing tests**;
- generated XML parses and generated Java passes structural assertions;
- the generated GPS Android project builds successfully;
- foreground location was exercised with changing emulator coordinates;
- background location remained a typed foreground service with its system
  notification active;
- the release wheel and source distribution pass `twine check`.

<section class="release12-closing">
  <span class="release12-kicker">BUILD THE BEHAVIOR, THEN INSPECT THE OUTPUT</span>
  <h2>Start in the Previewer. Finish the check on Android.</h2>
  <p>Fast feedback and native verification are two parts of the same workflow, not substitutes for each other.</p>
  <div><a class="md-button md-button--primary" href="../getting-started/">Open the build guide</a><a href="../api-reference/">Browse the public API →</a></div>
</section>
