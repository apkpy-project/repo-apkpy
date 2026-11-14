"""Afterglow -- a music player written in Python with ApkPy."""

from apkpy_lib import *

theme = Theme(
    mode="dark",
    primary="#FF6A88",
    secondary="#7CE0C3",
    background="#0E0B16",
    surface="#1A1524",
    text="#FFFFFF",
    text_secondary="#B3ABC4",
    border="#2A2236",
    radius=20,
)

home = Screen(id="home", scroll=True)
search = Screen(id="search", scroll=True)
library = Screen(id="library", scroll=True)
playing = Screen(id="playing", scroll=True)


# ── Home ─────────────────────────────────────────────────────────────────────

top = container(id="top", screen=home)
label("Good evening", id="top_title", parent=top)
container(id="spacer", parent=top)
button("", id="top_icon", icon="notifications", describe="What's new", parent=top, command=lambda: toast("Nothing new"))
button("", id="top_icon", icon="settings", describe="Settings", parent=top, command=lambda: toast("Settings"))

chips(["All", "Music", "Podcasts", "Live"], selected="All", id="kinds", screen=home)

for left, right in [
    (("art/cover_neon_tides.jpg", "Neon Tides"), ("art/cover_low_orbit.jpg", "Low Orbit")),
    (("art/cover_velvet_hour.jpg", "Velvet Hour"), ("art/cover_after_rain.jpg", "After Rain")),
]:
    pair = container(id="quick_pair", screen=home)
    for art, name in (left, right):
        quick = container(id="quick", parent=pair)
        image(art, id="quick_art", parent=quick, describe="")
        label(name, id="quick_name", parent=quick)

label("Made for you", id="heading", screen=home)
mixes = container(id="mixes", screen=home)
for art, name, note in [("art/cover_city_lights.jpg", "Late Night Drive", "Mara Vale and more"), ("art/cover_glass_garden.jpg", "Slow Sunday", "Paper Moon and more")]:
    mix = container(id="mix", parent=mixes)
    image(art, id="mix_art", parent=mix, describe="")
    label(name, id="mix_name", parent=mix)
    label(note, id="mix_note", parent=mix)

live = container(id="live", screen=home)
live_words = container(id="live_words", parent=live)
label("LIVE TONIGHT · 21:00", id="live_kicker", parent=live_words)
label("Soft Static at the Lighthouse", id="live_title", parent=live_words)
label("12,480 waiting", id="live_note", parent=live_words)
container(id="spacer", parent=live)
button("", id="live_bell", icon="notifications_active", describe="Remind me", parent=live, command=lambda: toast("We'll remind you"))

label("Recently played", id="heading", screen=home)

RECENT = [
    {"id": "1", "art": "art/cover_paper_moon.jpg", "title": "Paper Moon", "meta": "Album · Iris Hale"},
    {"id": "2", "art": "art/cover_soft_static.jpg", "title": "Static Bloom", "meta": "Single · Soft Static"},
    {"id": "3", "art": "art/cover_low_orbit.jpg", "title": "Low Orbit Radio", "meta": "Station · 24 h"},
]


def recent(row):
    image("{art}", id="recent_art", parent=row, describe="")
    texts = container(id="recent_words", parent=row)
    label("{title}", id="recent_title", parent=texts)
    label("{meta}", id="recent_meta", parent=texts)


virtual_collection(RECENT, row=recent, id="recents", screen=home, on_click=lambda item: toast(item["title"]))
container(id="bottom_room", screen=home)


# ── Search ───────────────────────────────────────────────────────────────────

label("Search", id="page_title", screen=search)
inputs("What do you want to hear?", type="search", id="find", screen=search)
label("Browse all", id="heading", screen=search)
for left, right in [(("Chill", "genre_chill"), ("Focus", "genre_focus")), (("Indie", "genre_indie"), ("Workout", "genre_workout")), (("Jazz", "genre_jazz"), ("Podcasts", "genre_podcasts"))]:
    row = container(id="genres", screen=search)
    for name, look in (left, right):
        tile = container(id=look, parent=row)
        label(name, id="genre_name", parent=tile)
container(id="bottom_room", screen=search)


# ── Library ──────────────────────────────────────────────────────────────────

head = container(id="top", screen=library)
label("Your library", id="top_title", parent=head)
container(id="spacer", parent=head)
button("", id="top_icon", icon="add", describe="New playlist", parent=head, command=lambda: toast("New playlist"))
segmented(["Playlists", "Albums", "Artists"], selected="Playlists", id="shelf", screen=library)

SHELF = [
    {"id": "1", "art": "art/cover_neon_tides.jpg", "title": "Liked songs", "meta": "Playlist · 412 songs"},
    {"id": "2", "art": "art/cover_city_lights.jpg", "title": "Late Night Drive", "meta": "Playlist · 48 songs"},
    {"id": "3", "art": "art/cover_after_rain.jpg", "title": "After Rain", "meta": "Album · Mara Vale"},
    {"id": "4", "art": "art/cover_velvet_hour.jpg", "title": "Velvet Hour", "meta": "Playlist · 31 songs"},
    {"id": "5", "art": "art/cover_glass_garden.jpg", "title": "Glass Garden", "meta": "Album · Paper Moon"},
    {"id": "6", "art": "art/cover_soft_static.jpg", "title": "Soft Static", "meta": "Artist"},
]


def shelf_item(row):
    image("{art}", id="shelf_art", parent=row, describe="")
    texts = container(id="shelf_words", parent=row)
    label("{title}", id="shelf_title", parent=texts)
    label("{meta}", id="shelf_meta", parent=texts)


virtual_collection(SHELF, row=shelf_item, id="shelf_list", screen=library, on_click=lambda item: toast(item["title"]))
container(id="bottom_room", screen=library)


# ── Now playing ──────────────────────────────────────────────────────────────

bar = container(id="top", screen=playing)
button("", id="top_icon", icon="expand_more", describe="Close", parent=bar, command=lambda: toast("Minimised"))
container(id="spacer", parent=bar)
source = container(id="source", parent=bar)
label("PLAYING FROM PLAYLIST", id="source_kicker", parent=source)
label("Late Night Drive", id="source_name", parent=source)
container(id="spacer", parent=bar)
button("", id="top_icon", icon="more_vert", describe="More", parent=bar, command=lambda: toast("More"))

image("art/cover_neon_tides.jpg", id="cover", screen=playing, describe="Neon Tides cover")

song = container(id="song", screen=playing)
song_words = container(id="song_words", parent=song)
label("Neon Tides", id="song_title", parent=song_words)
label("Mara Vale", id="song_artist", parent=song_words)
container(id="spacer", parent=song)
button("", id="song_like", icon="favorite", describe="Liked", parent=song, command=lambda: toast("Removed from Liked songs"))

position = inputs("", type="range", id="position", screen=playing)
position.set_value("43")
times = container(id="times", screen=playing)
label("1:42", id="time", parent=times)
container(id="spacer", parent=times)
label("3:58", id="time", parent=times)

controls = container(id="controls", screen=playing)
button("", id="control", icon="shuffle", describe="Shuffle", parent=controls, command=lambda: toast("Shuffle on"))
button("", id="control", icon="skip_previous", describe="Previous", parent=controls, command=lambda: toast("Previous"))
button("", id="play", icon="pause", describe="Pause", parent=controls, command=lambda: toast("Paused"))
button("", id="control", icon="skip_next", describe="Next", parent=controls, command=lambda: toast("Next"))
button("", id="control", icon="repeat", describe="Repeat", parent=controls, command=lambda: toast("Repeat on"))

lyrics = container(id="lyrics", screen=playing)
label("Lyrics", id="lyrics_title", parent=lyrics)
label("Streetlights fold into the water,", id="lyric_past", parent=lyrics)
label("we drive until the city hums", id="lyric_now", parent=lyrics)
label("a song we only half remember", id="lyric_next", parent=lyrics)
container(id="bottom_room", screen=playing)


bottom_nav([home, search, library, playing], labels=["Home", "Search", "Library", "Playing"], icons=["home", "search", "library_music", "graphic_eq"])

style = """
home, search, library, playing {
    background-color: var(--background);
    padding: 20px;
}
spacer {
    flex-grow: 1;
    background-color: #00000000;
    padding: 0px;
}
bottom_room {
    height: 88px;
    background-color: #00000000;
}

top {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 4px;
    background-color: #00000000;
    padding: 4px 0px 14px 0px;
}
top_title {
    font-size: 26px;
    font-weight: bold;
    color: #FFFFFF;
}
top_icon {
    width: 48px;
    height: 48px;
    border-radius: 24px;
    background-color: #00000000;
    icon-color: #FFFFFF;
}
kinds {
    accent-color: var(--primary);
    margin-bottom: 14px;
}

quick_pair {
    display: flex;
    flex-direction: row;
    gap: 10px;
    background-color: #00000000;
    padding: 0px;
    margin-bottom: 10px;
}
quick {
    flex-grow: 1;
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 10px;
    background-color: #221B2E;
    border-radius: 14px;
    padding: 0px 10px 0px 0px;
}
quick_art {
    width: 56px;
    height: 56px;
    object-fit: cover;
    border-radius: 14px;
}
quick_name {
    font-size: 14px;
    font-weight: bold;
    color: #FFFFFF;
}

heading {
    padding: 22px 0px 12px 0px;
    font-size: 20px;
    font-weight: bold;
    color: #FFFFFF;
}
mixes {
    display: flex;
    flex-direction: row;
    gap: 14px;
    background-color: #00000000;
    padding: 0px;
}
mix {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    background-color: #00000000;
    padding: 0px;
}
mix_art {
    width: 100%;
    height: 160px;
    object-fit: cover;
    border-radius: 20px;
    margin-bottom: 8px;
}
mix_name {
    font-size: 15px;
    font-weight: bold;
    color: #FFFFFF;
}
mix_note {
    font-size: 12px;
    color: var(--text-secondary);
}

live {
    display: flex;
    flex-direction: row;
    align-items: center;
    background: linear-gradient(135deg, #6A1B4D 0%, #C2185B 55%, #FF6A88 100%);
    border-radius: 24px;
    padding: 20px;
    margin-top: 22px;
    box-shadow: 0 14px 30px rgba(255, 106, 136, 0.28);
}
live_words {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    background-color: #00000000;
    padding: 0px;
}
live_kicker {
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.5px;
    color: #FFE1EA;
}
live_title {
    font-size: 18px;
    font-weight: bold;
    color: #FFFFFF;
}
live_note {
    font-size: 13px;
    color: #FFE1EA;
}
live_bell {
    width: 48px;
    height: 48px;
    border-radius: 24px;
    background-color: rgba(255, 255, 255, 0.18);
    icon-color: #FFFFFF;
}

recents, shelf_list {
    height: auto;
    background-color: #00000000;
    padding: 0px;
}
recents_row, shelf_list_row {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 14px;
    padding: 8px 0px;
    background-color: #00000000;
}
recent_art, shelf_art {
    width: 60px;
    height: 60px;
    object-fit: cover;
    border-radius: 12px;
}
recent_words, shelf_words {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    background-color: #00000000;
    padding: 0px;
}
recent_title, shelf_title {
    font-size: 16px;
    font-weight: bold;
    color: #FFFFFF;
}
recent_meta, shelf_meta {
    font-size: 13px;
    color: var(--text-secondary);
}

page_title {
    padding: 0px;
    font-size: 30px;
    font-weight: bold;
    color: #FFFFFF;
    margin: 8px 0px 14px 0px;
}
find {
    background-color: #FFFFFF;
    color: #14101C;
    border-radius: 14px;
}
genres {
    display: flex;
    flex-direction: row;
    gap: 12px;
    background-color: #00000000;
    padding: 0px;
    margin-bottom: 12px;
}
genre_chill, genre_focus, genre_indie, genre_workout, genre_jazz, genre_podcasts {
    flex-grow: 1;
    height: 100px;
    border-radius: 18px;
    padding: 16px;
}
genre_chill {
    background: linear-gradient(135deg, #155E68 0%, #23847A 100%);
}
genre_focus {
    background: linear-gradient(135deg, #33267A 0%, #5B4BE0 100%);
}
genre_indie {
    background: linear-gradient(135deg, #7A2546 0%, #C2386E 100%);
}
genre_workout {
    background: linear-gradient(135deg, #8A2F10 0%, #C9551F 100%);
}
genre_jazz {
    background: linear-gradient(135deg, #4F3A0C 0%, #8F6618 100%);
}
genre_podcasts {
    background: linear-gradient(135deg, #124A28 0%, #1F7A49 100%);
}
genre_name {
    padding: 0px;
    font-size: 18px;
    font-weight: bold;
    color: #FFFFFF;
}

shelf {
    margin-bottom: 12px;
}

source {
    display: flex;
    flex-direction: column;
    align-items: center;
    background-color: #00000000;
    padding: 0px;
}
source_kicker {
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.5px;
    color: var(--text-secondary);
}
source_name {
    font-size: 14px;
    font-weight: bold;
    color: #FFFFFF;
}
cover {
    width: 100%;
    height: 340px;
    object-fit: cover;
    border-radius: 28px;
    margin: 12px 0px 24px 0px;
    box-shadow: 0 20px 40px rgba(255, 79, 216, 0.30);
}
song {
    display: flex;
    flex-direction: row;
    align-items: center;
    background-color: #00000000;
    padding: 0px;
}
song_words {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    background-color: #00000000;
    padding: 0px;
}
song_title {
    font-size: 24px;
    font-weight: bold;
    color: #FFFFFF;
}
song_artist {
    font-size: 15px;
    color: var(--text-secondary);
}
song_like {
    width: 48px;
    height: 48px;
    border-radius: 24px;
    background-color: #00000000;
    icon-color: var(--primary);
}
position {
    accent-color: #FFFFFF;
    margin-top: 14px;
}
times {
    display: flex;
    flex-direction: row;
    background-color: #00000000;
    padding: 0px;
}
time {
    font-size: 12px;
    color: var(--text-secondary);
}
controls {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    background-color: #00000000;
    padding: 10px 0px;
}
control {
    width: 48px;
    height: 48px;
    border-radius: 24px;
    background-color: #00000000;
    icon-color: #FFFFFF;
    icon-size: 28px;
}
play {
    width: 72px;
    height: 72px;
    border-radius: 36px;
    background-color: #FFFFFF;
    icon-color: #0E0B16;
    icon-size: 36px;
}
lyrics {
    background: linear-gradient(160deg, #4A1D6E 0%, #2A1240 100%);
    border-radius: 24px;
    padding: 20px;
    margin-top: 16px;
}
lyrics_title {
    padding: 0px;
    font-size: 15px;
    font-weight: bold;
    color: #FFFFFF;
    margin-bottom: 10px;
}
lyric_past {
    padding: 0px;
    font-size: 20px;
    font-weight: bold;
    color: #C9B6DD;
}
lyric_now {
    padding: 0px;
    font-size: 20px;
    font-weight: bold;
    color: #FFFFFF;
}
lyric_next {
    padding: 0px;
    font-size: 20px;
    font-weight: bold;
    color: #C9B6DD;
}

bottom_nav {
    margin: 16px;
    border-radius: 28px;
    background-color: #1F1929;
    color: #A79FB8;
    active-color: #FFFFFF;
    indicator-color: #3A2F4A;
}
"""

run(start_screen=home, theme=theme)
