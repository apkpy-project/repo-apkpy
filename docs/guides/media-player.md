---
title: Spotify-style background audio
description: Build native playlists, MediaSession controls and background playback with ApkPy.
---

# Spotify-style background audio

```python
from apkpy_lib import Screen, audio, button, label, mini_player, run

library = Screen(id="library", scroll=True)
label("Night Library", variant="title", screen=library)

sources = [
    "https://cdn.example.com/northbound.mp3",
    "https://cdn.example.com/afterimage.mp3",
]
titles = ["Northbound", "Afterimage"]
artists = ["Signal Club", "Mira Vale"]
artwork = [
    "https://cdn.example.com/northbound.jpg",
    "https://cdn.example.com/afterimage.jpg",
]

def play_mix():
    audio.play_playlist(
        sources,
        titles=titles,
        artists=artists,
        arts=artwork,
        start=0,
    )

button("Play mix", command=play_mix, screen=library)
button("Previous", command=audio.previous, screen=library)
button("Next", command=audio.next, screen=library)
mini_player(open=library)
run(library)
```

On Android, background playback is owned by a generated foreground service and
native `MediaSession`. This supplies notification and lock-screen metadata,
transport controls, audio focus and guarded progress polling.

## Honest limits

Normal source playback, explicit downloaded files, queues, playlists,
favourites, seek, shuffle and repeat are supported. ApkPy does not currently
promise DRM, automatic adaptive audio quality, crossfade, a smart cache or
gapless playback for every codec/device combination.

Use [Audio, playlists and Spotify](../media-auth.md) for the complete API.
