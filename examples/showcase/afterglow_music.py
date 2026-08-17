"""Afterglow — an editorial music discovery screen built with ApkPy."""

from apkpy_lib import (
    Screen, Theme, action, app_bar, bottom_nav, button, container, device,
    image, label, run, toast,
)


device("Pixel 9")

theme = Theme(
    mode="dark",
    primary="#F4D35E",
    secondary="#7BDFF2",
    background="#111315",
    surface="#1B1E21",
    text="#F5F3EF",
    text_secondary="#A5A7AA",
    border="#34383C",
    radius=18,
    spacing=14,
    font_family="sans-serif",
)

listen = Screen(id="afterglow_listen", scroll=True)
radio = Screen(id="afterglow_radio", scroll=True)
library = Screen(id="afterglow_library", scroll=True)
profile = Screen(id="afterglow_profile", scroll=True)

app_bar(
    "Afterglow",
    actions=[
        action("search", label="Search", command=lambda: toast("Search your library")),
        action("more_vert", label="More", command=lambda: toast("More options")),
    ],
    screen=listen,
)

label("EDITOR'S PICK · 16 JULY", id="pick_kicker", screen=listen)
label("Music for the hour after midnight.", id="pick_title", screen=listen)
label("A slow-burn selection from Lisbon, Seoul and Detroit.", id="pick_intro", screen=listen)

feature = container(id="feature_card", screen=listen)
image("premium_music.png", id="feature_art", parent=feature, aspect_ratio="16:9")
label("NOCTURNE 04", id="feature_eyebrow", parent=feature)
label("City lights, low ceilings", id="feature_title", parent=feature)
label("43 min · Curated by Mara Vale", id="feature_meta", parent=feature)
feature_actions = container(id="feature_actions", parent=feature)
button("Play mix", id="play_mix", icon="play_arrow", variant="filled", parent=feature_actions,
       command=lambda: toast("Playing Nocturne 04"))
button("Save", id="save_mix", icon="heart", variant="outlined", parent=feature_actions,
       command=lambda: toast("Saved to your library"))

label("Up next", id="queue_title", screen=listen)

queue = container(id="queue_card", screen=listen)
for number, title, artist, duration in [
    ("01", "Soft Static", "Mira Nox", "4:12"),
    ("02", "Glass District", "Frame Relay", "3:48"),
    ("03", "Still Awake", "June Lumen", "5:03"),
]:
    track = container(id="track_" + number, parent=queue)
    label(number, id="track_no_" + number, parent=track)
    track_copy = container(id="track_copy_" + number, parent=track)
    label(title, id="track_title_" + number, parent=track_copy)
    label(artist, id="track_artist_" + number, parent=track_copy)
    label(duration, id="track_duration_" + number, parent=track)

for page, title, copy in [
    (radio, "Radio", "Live rooms and independent stations."),
    (library, "Library", "Albums, mixes and tracks you kept."),
    (profile, "Profile", "Listening history and audio settings."),
]:
    label(title, id=page.id + "_title", screen=page)
    label(copy, id=page.id + "_copy", screen=page)

bottom_nav(
    [listen, radio, library, profile],
    labels=["Listen", "Radio", "Library", "Profile"],
    icons=["home", "star", "list", "person"],
)

style = """
body { font-family: var(--font-family); }
afterglow_listen, afterglow_radio, afterglow_library, afterglow_profile {
    background-color: var(--background); padding: 20px;
}
label { color: var(--text); }
pick_kicker {
    color: var(--primary); font-size: 10px; font-weight: bold;
    letter-spacing: 1.4px; margin-top: 8px; margin-bottom: 8px;
}
pick_title { color: var(--text); font-size: 28px; font-weight: bold; margin-bottom: 6px; }
pick_intro { color: var(--text-secondary); font-size: 13px; margin-bottom: 16px; }
feature_card {
    width: 100%; background-color: var(--surface); border-color: var(--border);
    border-width: 1px; border-radius: 20px; padding: 12px; margin-bottom: 14px;
}
feature_art {
    width: 100%; object-fit: cover; border-radius: 14px; margin-bottom: 13px;
}
feature_eyebrow { color: var(--secondary); font-size: 10px; font-weight: bold; letter-spacing: 1.2px; }
feature_title { color: var(--text); font-size: 20px; font-weight: bold; margin-top: 5px; }
feature_meta { color: var(--text-secondary); font-size: 11px; margin-top: 4px; margin-bottom: 10px; }
feature_actions {
    display: flex; flex-direction: row; gap: 9px; width: 100%;
    background-color: var(--surface); border-width: 0px; padding: 0px;
}
play_mix, save_mix { flex-grow: 1; flex-basis: 130px; border-radius: 13px; padding: 11px; font-weight: bold; }
play_mix { background-color: var(--primary); color: #17150D; }
save_mix { background-color: var(--surface); color: var(--primary); border-color: var(--primary); border-width: 1px; }
queue_title {
    color: var(--text); font-size: 18px; font-weight: bold;
    margin-top: 2px; margin-bottom: 9px;
}
queue_card {
    width: 100%; background-color: var(--surface); border-color: var(--border);
    border-width: 1px; border-radius: 18px; padding: 5px 13px; margin-bottom: 10px;
}
track_01, track_02, track_03 {
    display: flex; flex-direction: row; align-items: center; gap: 12px; width: 100%;
    background-color: var(--surface); border-width: 0px; border-bottom-color: var(--border);
    border-bottom-width: 1px; border-radius: 0px; padding: 10px 0px;
}
track_03 { border-bottom-width: 0px; }
track_no_01, track_no_02, track_no_03 { color: var(--primary); font-size: 10px; font-weight: bold; }
track_copy_01, track_copy_02, track_copy_03 {
    flex-grow: 1; background-color: var(--surface); border-width: 0px; padding: 0px;
}
track_title_01, track_title_02, track_title_03 { color: var(--text); font-size: 13px; font-weight: bold; }
track_artist_01, track_artist_02, track_artist_03 { color: var(--text-secondary); font-size: 10px; margin-top: 2px; }
track_duration_01, track_duration_02, track_duration_03 { color: var(--text-secondary); font-size: 10px; }
afterglow_radio_title, afterglow_library_title, afterglow_profile_title {
    color: var(--text); font-size: 28px; font-weight: bold; margin-top: 30px;
}
afterglow_radio_copy, afterglow_library_copy, afterglow_profile_copy {
    color: var(--text-secondary); font-size: 14px; margin-top: 8px;
}
"""

if __name__ == "__main__":
    run(start_screen=listen, theme=theme)
