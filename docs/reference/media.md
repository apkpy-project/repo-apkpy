---
title: Media and files API
description: ApkPy audio, video, uploads and local file reference.
---

# Media and files API

## Audio

`audio` exposes `play`, `play_background`, `pause`, `resume`, `stop`, `seek`,
`play_playlist`, `next`, `previous`, `shuffle`, `repeat`, `now_playing`,
`controls`, favourites and playlist management.

Background playback generates an Android foreground service and MediaSession.
Use [Spotify-style background audio](../guides/media-player.md).

## Video

The `video(...)` component supports source/poster, native controls, buffering
callbacks, seek, speed and mute. Component methods include `play`, `pause`,
`stop`, `seek`, `set_source`, `set_speed` and `set_muted`.

Android uses Media3. The Previewer uses its desktop media backend.

## Uploads

`uploads.multipart`, `uploads.file`, `uploads.image`, `uploads.audio`,
`uploads.video` and `uploads.cancel`.

Progress callbacks receive `(percent, bytes_sent, total_bytes)`. Result
callbacks receive `(success, response)`.

## Files

`files.download`, `files.path`, `files.exists` and `files.delete`.

See [Streaming multipart uploads](../guides/uploads.md).
