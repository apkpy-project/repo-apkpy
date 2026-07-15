# Audio, playlists and Spotify

ApkPy provides the building blocks for music and podcast applications: foreground playback, queues, player bindings, favourites, user playlists, downloads and OAuth.

## Play audio

~~~ python
audio.play("intro.mp3")
audio.pause()
audio.resume()
audio.seek(30)
audio.stop()
~~~

Use background playback when audio should continue while the user changes screen or leaves the app:

~~~ python
audio.play_background(
    "https://cdn.example.com/midnight-drive.mp3",
    title="Midnight Drive",
    artist="Nova",
    art="https://cdn.example.com/midnight-drive.jpg",
)
~~~

Android uses a foreground media service. The notification and system media controls are maintained by the generated native project.

## Queues

~~~ python
sources = [
    "https://cdn.example.com/track-1.mp3",
    "https://cdn.example.com/track-2.mp3",
]

audio.play_playlist(
    sources,
    titles=["First Light", "Midnight Drive"],
    artists=["Nova", "Nova"],
    arts=["cover-1.jpg", "cover-2.jpg"],
    start=0,
)

audio.next()
audio.previous()
audio.shuffle()
audio.repeat()
~~~

The <code>start</code> value can be an index or the selected source URL.

## Bind a player screen

~~~ python
progress = inputs("", type="range", screen=player)
elapsed = label("0:00 / 0:00", screen=player)
cover = image("", screen=player)
title = label("", screen=player)
artist = label("", screen=player)

play_pause = button("Play", variant="icon", icon="play_arrow", screen=player)
shuffle = button("Shuffle", variant="icon", icon="shuffle", screen=player)
repeat = button("Repeat", variant="icon", icon="repeat", screen=player)

audio.now_playing(
    progress=progress,
    time=elapsed,
    cover=cover,
    title=title,
    artist=artist,
)
audio.controls(
    play_pause=play_pause,
    shuffle=shuffle,
    repeat=repeat,
)
~~~

Moving the bound range seeks through the track. The labels, artwork and buttons stay synchronized with playback.

## Favourites

~~~ python
audio.like_button(like_button, liked="Liked", unliked="Like")
audio.liked_list(liked_tracks)
~~~

The binding watches the current track and refreshes the button/list automatically.

## User playlists

~~~ python
audio.add_to_playlist("Focus")
audio.play_saved_playlist("Focus")

audio.playlists_list(playlist_list)
audio.edit_playlist("Focus")
audio.playlist_editor(playlist_tracks)

audio.remove_from_playlist("Focus")
audio.delete_playlist("Focus")
~~~

When <code>add_to_playlist</code> or <code>remove_from_playlist</code> receives no explicit item, it uses the current track. You may also pass an item dictionary containing <code>src</code>, <code>title</code>, <code>artist</code> and <code>art</code>.

Playlist lists and editors refresh when their screen resumes, keeping the Previewer and generated Android app aligned.

## Offline downloads

~~~ python
def downloaded(success, path):
    if success:
        audio.play(path)
    else:
        toast("Download failed")

files.download(
    "https://cdn.example.com/midnight-drive.mp3",
    "midnight-drive.mp3",
    on_result=downloaded,
)

if files.exists("midnight-drive.mp3"):
    audio.play(files.path("midnight-drive.mp3"))

files.delete("midnight-drive.mp3")
~~~

Files are stored in app-private storage, so broad storage permission is not required.

## Spotify OAuth

~~~ python
def signed_in(user):
    account_name.set_value(user["name"])

auth.login(
    provider="spotify",
    client_id="YOUR_SPOTIFY_CLIENT_ID",
    scopes=["user-read-email", "user-read-private"],
    then=home,
)

auth.user(on_result=signed_in)
token = auth.token()
logged_in = auth.is_logged_in()
auth.logout()
~~~

Register both redirect styles with the provider:

- Android: <code>apkpy://auth</code>
- Previewer: the loopback callback shown by the login flow, normally <code>http://127.0.0.1:8888/callback</code>

OAuth uses Authorization Code with PKCE, avoiding an embedded client secret in the APK.

!!! important "What ApkPy does not include"
    ApkPy provides playback, interface, download, playlist and authentication primitives. It does not provide Spotify catalogue rights or bypass provider rules. Only access media and APIs that your application is authorized to use.
