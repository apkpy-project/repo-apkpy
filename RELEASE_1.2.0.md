# ApkPy 1.2.0 release guide

Version 1.2.0 connects ApkPy applications to large data, observable state,
streaming transfers, real-time channels, native video, remote push, continuous
location and structured documents. It also makes the existing native audio
foundation impossible to overlook.

This guide documents the released Python surface, the generated Android
foundation and the boundaries that still belong to application or server code.

## The eight runtime areas

| Area | Public surface | Generated Android foundation |
| --- | --- | --- |
| Virtual collections | `virtual_collection()` | `RecyclerView`, adapter and recycled `ViewHolder`s |
| Reactive UI | `state()`, bindings and `lifecycle()` | Activity fields, lifecycle methods and UI-thread updates |
| Streaming uploads | `uploads` | bounded multipart worker with progress and cancellation |
| Real-time messages | `websocket` | OkHttp WebSocket, ping/pong, send queue and reconnect |
| Video | `video()` | Media3/ExoPlayer and lifecycle-safe player release |
| Remote push | `push` | conditional Firebase Messaging service and token callbacks |
| Maps and GPS | `map_view()`, `routes`, `location` | OpenStreetMap view, Fused Location and typed foreground service |
| Native documents | `rich_text()`, `markdown()`, `tree_view()` | `Spannable` text and visible-row `RecyclerView` |

The detailed guide, including runnable code for every area and exact Previewer
versus Android behavior, lives in
[`docs/version-1.2.0.md`](docs/version-1.2.0.md).

## Structured content example

~~~ python
from apkpy_lib import Screen, markdown, rich_text, tree_view

knowledge = Screen(id="knowledge", scroll=True)

rich_text(
    [
        {"text": "FIELD NOTE\n", "bold": True,
         "color": "#22D3EE", "size": 12},
        {"text": "Small interfaces, ", "bold": True, "size": 23},
        {"text": "deep structure.", "bold": True, "italic": True,
         "color": "#C4B5FD", "size": 23},
    ],
    screen=knowledge,
)

markdown(
    """## Release notes

> Selectable native text.

- [x] **Bold**, *italic* and `inline code`
- [x] Lists, links, quotes and dividers
""",
    screen=knowledge,
)

tree_view(
    [{
        "key": "product",
        "title": "Product",
        "children": [
            {"title": "Roadmap", "subtitle": "Q3 planning"},
            {"title": "Release notes", "subtitle": "12 entries"},
        ],
    }],
    expand_depth=1,
    row_height=60,
    screen=knowledge,
)
~~~

This produces native selectable text and a recycled hierarchy. It does not add
a browser, JavaScript engine, hosted editor or storage service. The application
can keep the source in SQLite, encrypted storage or its own API.

## A music player, not a foreground sound button

An ApkPy music application can already keep playing after the user leaves its
Activity. The generated Android project includes a foreground media service and
a native `MediaSession`; playback metadata and transport actions are exposed to
the Android notification area and lock screen.

~~~ python
from apkpy_lib import (
    Screen, audio, button, image, inputs, label, mini_player, run,
)

library = Screen(id="library", scroll=True)
player = Screen(id="player")

cover = image("cover-placeholder.png", id="cover", screen=player)
track_title = label("Nothing playing", id="track_title", screen=player)
track_artist = label("", id="track_artist", screen=player)
seek = inputs("", type="range", id="seek", screen=player)
elapsed = label("0:00 / 0:00", id="elapsed", screen=player)

play_pause = button("Play", icon="play_arrow", variant="icon", screen=player)
shuffle = button("Shuffle", icon="shuffle", variant="icon", screen=player)
repeat = button("Repeat", icon="repeat", variant="icon", screen=player)

sources = [
    "https://cdn.example.com/first-light.mp3",
    "https://cdn.example.com/night-drive.mp3",
]

audio.play_playlist(
    sources,
    titles=["First Light", "Night Drive"],
    artists=["Nova", "Nova"],
    arts=[
        "https://cdn.example.com/first-light.jpg",
        "https://cdn.example.com/night-drive.jpg",
    ],
    start=0,
)

audio.now_playing(
    progress=seek,
    time=elapsed,
    cover=cover,
    title=track_title,
    artist=track_artist,
)
audio.controls(
    play_pause=play_pause,
    shuffle=shuffle,
    repeat=repeat,
)
mini_player(open=player)

run(start_screen=library)
~~~

## What the generated Android project already does

| Capability | Current behaviour |
| --- | --- |
| Local and remote audio | Plays local paths and normal HTTP/HTTPS audio sources accepted by Android's media stack |
| Background playback | A generated foreground service owns playback outside the Activity |
| Lock-screen integration | `MediaSession` publishes title, artist, artwork, state and transport actions |
| Notification controls | Previous, play/pause and next actions control the same service queue |
| Audio focus | Handles pause, duck and resume transitions requested by Android |
| Queue | Keeps sources, titles, artists and artwork together; starts by index or source URL |
| Queue controls | Next, previous, shuffle and repeat are available from Python and bound controls |
| Seeking | `audio.seek()` and a bound range input seek the active player |
| Player UI | Progress, elapsed/duration, cover, title and artist remain synchronized |
| Mini-player | Follows the service above bottom navigation and opens the full player |
| Library | Favourites and editable user playlists persist source and metadata |
| Offline files | Downloads run asynchronously into app-private storage and can be played by path |
| Previewer | Exposes the same public playback, queue, binding and playlist API for desktop testing |

## Reliability protections already present

The generated player does not blindly poll an unprepared `MediaPlayer`.
Duration and position return safe values until the source is prepared, and the
service reports a buffering state while preparation is in progress. A prepare
failure receives one controlled retry of the same source. If it still fails,
the player stops that attempt instead of automatically advancing through every
track and creating overlapping playback or a skip storm.

The service owns the queue and active metadata, rather than each Activity
creating an unrelated player. Moving between the library, search and player
screens therefore does not replace the playback session.

## Offline playback is explicit

~~~ python
from apkpy_lib import audio, files, toast

def saved(success, path):
    if success:
        audio.play(path)
    else:
        toast("The download failed")

files.download(
    "https://cdn.example.com/night-drive.mp3",
    "night-drive.mp3",
    on_result=saved,
)

if files.exists("night-drive.mp3"):
    audio.play(files.path("night-drive.mp3"))
~~~

Files stay in the application's private directory, so this flow does not ask
for broad access to the user's shared storage.

## Exact boundary: what is not being claimed

These features are not part of the current audio API:

- transparent or predictive audio caching;
- automatic bitrate or adaptive-quality selection;
- guaranteed gapless transitions between tracks;
- crossfade;
- DRM-protected catalogue playback;
- resumable downloads with progress and cancellation;
- a licensed Spotify catalogue or a way around provider restrictions.

Normal URL playback preserves the source chosen by the application; ApkPy does
not lower or improve its bitrate by transcoding it. Artwork can use the bounded
image cache, and complete tracks can be downloaded explicitly, but neither is
described as an intelligent streaming cache.

This distinction is intentional. The purpose of the 1.2.0 documentation is to
show the substantial native player that already exists while keeping future
work measurable.
