"""Onda -- a calm wellbeing app written in Python with ApkPy."""

from apkpy_lib import *

theme = Theme(
    mode="light",
    primary="#1F6F68",
    secondary="#B4462B",
    background="#F7F4EF",
    surface="#FFFFFF",
    text="#1E2A28",
    text_secondary="#5B6663",
    border="#ECE6DC",
    radius=20,
)

today = Screen(id="today", scroll=True)
explore = Screen(id="explore", scroll=True)
sleep = Screen(id="sleep", scroll=True)
you = Screen(id="you", scroll=True)


# ── Today ────────────────────────────────────────────────────────────────────

top = container(id="top", screen=today)
words = container(id="top_words", parent=top)
label("Thursday, 14 November", id="top_date", parent=words)
label("Hi, Inês", id="top_name", parent=words)
container(id="spacer", parent=top)
avatar("art/face_ines.png", size=44, id="me", parent=top, describe="Inês")

hero = container(id="hero", screen=today)
image("art/wave_sea.jpg", id="hero_art", parent=hero, describe="")
hero_words = container(id="hero_words", parent=hero)
label("DAILY CALM", id="hero_kicker", parent=hero_words)
label("Morning reset", id="hero_title", parent=hero_words)
label("8 min · Breathing", id="hero_meta", parent=hero_words)
button("", id="hero_play", icon="play_arrow", describe="Play", parent=hero, command=lambda: toast("Breathe in..."))

label("How do you feel?", id="heading", screen=today)
chips(["Calm", "Happy", "Tired", "Stressed"], selected="Calm", id="mood", screen=today, on_change=lambda value: toast("Noted: " + str(value)))

rings = container(id="rings", screen=today)
for name, value, goal, note in [("Mindful", 12, 20, "12 of 20 min"), ("Steps", 6240, 8000, "6,240"), ("Water", 5, 8, "5 of 8 cups")]:
    cell = container(id="ring_cell", parent=rings)
    chart(kind="ring", value=value, max=goal, id="ring_" + name.lower(), parent=cell)
    label(name, id="ring_name", parent=cell)
    label(note, id="ring_note", parent=cell)

picks_head = container(id="section", screen=today)
label("For you", id="section_title", parent=picks_head)
container(id="spacer", parent=picks_head)
label("See all", id="section_link", parent=picks_head)

picks = container(id="picks", screen=today)
for art, title, meta in [("art/wave_dawn.jpg", "Let go of the day", "12 min · Evening"), ("art/wave_lilac.jpg", "Deep focus", "20 min · Work")]:
    pick = container(id="pick", parent=picks)
    image(art, id="pick_art", parent=pick, describe="")
    label(title, id="pick_title", parent=pick)
    label(meta, id="pick_meta", parent=pick)

night = container(id="night", screen=today)
night_words = container(id="night_words", parent=night)
label("LAST NIGHT", id="night_kicker", parent=night_words)
label("7h 42m of sleep", id="night_title", parent=night_words)
label("Your best this week", id="night_note", parent=night_words)
container(id="spacer", parent=night)
button("", id="night_go", icon="bedtime", describe="Open sleep", parent=night, command=lambda: toast("Sleep well"))
container(id="bottom_room", screen=today)


# ── Explore ──────────────────────────────────────────────────────────────────

label("Explore", id="page_title", screen=explore)
inputs("Search sessions", type="search", id="find", screen=explore)
chips(["All", "Sleep", "Focus", "Stress"], selected="All", id="topics", screen=explore)

feature = container(id="feature", screen=explore)
image("art/wave_night.jpg", id="feature_art", parent=feature, describe="")
feature_words = container(id="feature_words", parent=feature)
label("NEW SERIES", id="feature_kicker", parent=feature_words)
label("Seven nights of rest", id="feature_title", parent=feature_words)
label("7 sessions · 10 min each", id="feature_meta", parent=feature_words)

label("Popular this week", id="heading", screen=explore)

SESSIONS = [
    {"id": "1", "art": "art/wave_sea.jpg", "title": "Body scan", "meta": "Sleep · with Noah", "length": "15 min"},
    {"id": "2", "art": "art/wave_dawn.jpg", "title": "Slow mornings", "meta": "Energy · with Maya", "length": "8 min"},
    {"id": "3", "art": "art/wave_mint.jpg", "title": "Walking calm", "meta": "Move · with Léo", "length": "20 min"},
    {"id": "4", "art": "art/wave_lilac.jpg", "title": "Untangle a worry", "meta": "Stress · with Zoe", "length": "11 min"},
    {"id": "5", "art": "art/wave_night.jpg", "title": "Rain on the window", "meta": "Sleep · soundscape", "length": "45 min"},
]


def session(row):
    image("{art}", id="session_art", parent=row, describe="")
    texts = container(id="session_words", parent=row)
    label("{title}", id="session_title", parent=texts)
    label("{meta}", id="session_meta", parent=texts)
    label("{length}", id="session_length", parent=row)


virtual_collection(SESSIONS, row=session, id="sessions", screen=explore, on_click=lambda item: toast(item["title"]))
container(id="bottom_room", screen=explore)


# ── Sleep ────────────────────────────────────────────────────────────────────

label("Sleep", id="sleep_title", screen=sleep)
label("Last night", id="sleep_kicker", screen=sleep)
label("7h 42m", id="sleep_total", screen=sleep)
label("23:18 – 07:00 · 94% asleep in bed", id="sleep_note", screen=sleep)

stages = container(id="stages", screen=sleep)
for name, time in [("Deep", "1h 50m"), ("Light", "4h 32m"), ("REM", "1h 20m")]:
    stage = container(id="stage", parent=stages)
    label(name, id="stage_name", parent=stage)
    label(time, id="stage_time", parent=stage)

WEEK = [
    {"label": "M", "value": 6.8},
    {"label": "T", "value": 7.1},
    {"label": "W", "value": 5.9},
    {"label": "T", "value": 6.4},
    {"label": "F", "value": 7.0},
    {"label": "S", "value": 8.2},
    {"label": "S", "value": 7.7},
]

week = container(id="week", screen=sleep)
label("This week", id="week_title", parent=week)
label("7h 01m on average", id="week_note", parent=week)
chart(WEEK, kind="bar", id="week_chart", parent=week)

label("Sounds for tonight", id="sounds_title", screen=sleep)
for art, title, meta in [("art/wave_night.jpg", "Rain on leaves", "45 min"), ("art/wave_sea.jpg", "Ocean, far away", "60 min"), ("art/wave_mint.jpg", "Night forest", "30 min")]:
    sound = container(id="sound", screen=sleep)
    image(art, id="sound_art", parent=sound, describe="")
    sound_words = container(id="sound_words", parent=sound)
    label(title, id="sound_title", parent=sound_words)
    label(meta, id="sound_meta", parent=sound_words)
    button("", id="sound_play", icon="play_arrow", describe="Play " + title, parent=sound, command=lambda: toast("Playing"))
container(id="bottom_room", screen=sleep)


# ── You ──────────────────────────────────────────────────────────────────────

who = container(id="who", screen=you)
avatar("art/face_ines.png", size=88, id="who_face", parent=who, describe="Inês")
label("Inês Almeida", id="who_name", parent=who)
label("Breathing with Onda since 2024", id="who_note", parent=who)

streak = container(id="streak", screen=you)
label("12-day streak", id="streak_title", parent=streak)
label("Your longest yet. One more today?", id="streak_note", parent=streak)
days = container(id="days", parent=streak)
for letter, done in [("M", True), ("T", True), ("W", True), ("T", True), ("F", True), ("S", False), ("S", False)]:
    label(letter, id="day_done" if done else "day_open", parent=days)

stats = container(id="stats", screen=you)
for number, word in [("48", "sessions"), ("6h 20m", "mindful"), ("92", "sleep score")]:
    stat = container(id="stat", parent=stats)
    label(number, id="stat_number", parent=stat)
    label(word, id="stat_word", parent=stat)

reminders = container(id="reminders", screen=you)
label("Reminders", id="reminders_title", parent=reminders)
morning = inputs("Morning breathing, 08:00", type="switch", id="reminder", parent=reminders)
inputs("Wind down, 22:30", type="switch", id="reminder", parent=reminders)
inputs("Weekly summary", type="switch", id="reminder", parent=reminders)
morning.set_value("true")

more = container(id="more", screen=you)
list_row("Connected apps", icon="favorite", trailing_icon="chevron_right", id="more_row", parent=more, command=lambda: toast("Connected apps"))
list_row("Sounds and haptics", icon="graphic_eq", trailing_icon="chevron_right", id="more_row", parent=more, command=lambda: toast("Sounds"))
list_row("Privacy", icon="lock", trailing_icon="chevron_right", id="more_row", parent=more, command=lambda: toast("Privacy"))
container(id="bottom_room", screen=you)


bottom_nav([today, explore, sleep, you], labels=["Today", "Explore", "Sleep", "You"], icons=["spa", "explore", "bedtime", "person"])

style = """
today, explore, you {
    background-color: var(--background);
    padding: 20px;
}
sleep {
    background-color: #12152E;
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
    background-color: #00000000;
    padding: 4px 0px 18px 0px;
}
top_words {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    background-color: #00000000;
    padding: 0px;
}
top_date {
    font-size: 13px;
    color: var(--text-secondary);
}
top_name {
    font-size: 26px;
    font-weight: bold;
    color: var(--text);
}

hero {
    position: relative;
    height: 230px;
    padding: 0px;
    background-color: #00000000;
}
hero_art {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 28px;
}
hero_words {
    position: absolute;
    left: 22px;
    top: 22px;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    background-color: #00000000;
}
hero_kicker {
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.5px;
    color: #1F6F68;
}
hero_title {
    font-size: 26px;
    font-weight: bold;
    color: #14332F;
}
hero_meta {
    font-size: 13px;
    color: #2D4F4A;
}
hero_play {
    position: absolute;
    right: 18px;
    bottom: 18px;
    width: 56px;
    height: 56px;
    border-radius: 28px;
    background-color: #FFFFFF;
    icon-color: #1F6F68;
    icon-size: 30px;
}

section {
    display: flex;
    flex-direction: row;
    align-items: center;
    background-color: #00000000;
    padding: 22px 0px 10px 0px;
}
heading {
    padding: 22px 0px 10px 0px;
    font-size: 18px;
    font-weight: bold;
    color: var(--text);
}
section_title {
    font-size: 18px;
    font-weight: bold;
    color: var(--text);
}
section_link {
    font-size: 13px;
    font-weight: bold;
    color: var(--primary);
}
mood, topics {
    accent-color: var(--primary);
}

rings {
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    background-color: #FFFFFF;
    border-radius: 24px;
    padding: 18px 14px;
    margin-top: 16px;
}
ring_cell {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    background-color: #00000000;
    padding: 0px;
}
ring_mindful, ring_steps, ring_water {
    width: 76px;
    height: 76px;
    font-size: 15px;
    stroke-width: 8px;
    track-color: #EEF2EF;
    background-color: #00000000;
}
ring_mindful {
    color: #1F6F68;
}
ring_steps {
    color: #E8734F;
}
ring_water {
    color: #3B82F6;
}
ring_name {
    font-size: 14px;
    font-weight: bold;
    color: var(--text);
    margin-top: 6px;
}
ring_note {
    font-size: 12px;
    color: var(--text-secondary);
}

picks {
    display: flex;
    flex-direction: row;
    gap: 12px;
    background-color: #00000000;
    padding: 0px;
}
pick {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    background-color: #FFFFFF;
    border-radius: 22px;
    padding: 8px 8px 14px 8px;
}
pick_art {
    width: 100%;
    height: 112px;
    object-fit: cover;
    border-radius: 16px;
    margin-bottom: 8px;
}
pick_title {
    font-size: 15px;
    font-weight: bold;
    color: var(--text);
    margin-left: 6px;
}
pick_meta {
    font-size: 12px;
    color: var(--text-secondary);
    margin-left: 6px;
}

night {
    display: flex;
    flex-direction: row;
    align-items: center;
    background: linear-gradient(135deg, #1B1F4B 0%, #3A3388 100%);
    border-radius: 24px;
    padding: 20px;
    margin-top: 16px;
}
night_words {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    background-color: #00000000;
    padding: 0px;
}
night_kicker {
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.5px;
    color: #C9C2FF;
}
night_title {
    font-size: 19px;
    font-weight: bold;
    color: #FFFFFF;
}
night_note {
    font-size: 13px;
    color: #D6D2F5;
}
night_go {
    width: 48px;
    height: 48px;
    border-radius: 24px;
    background-color: rgba(255, 255, 255, 0.16);
    icon-color: #FFFFFF;
}

page_title {
    padding: 0px;
    font-size: 30px;
    font-weight: bold;
    color: var(--text);
    margin: 8px 0px 14px 0px;
}
find {
    background-color: #FFFFFF;
    border-radius: 16px;
    margin-bottom: 12px;
}
feature {
    position: relative;
    height: 210px;
    padding: 0px;
    margin-top: 16px;
    background-color: #00000000;
}
feature_art {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 26px;
}
feature_words {
    position: absolute;
    left: 22px;
    bottom: 20px;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    background-color: #00000000;
}
feature_kicker {
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.5px;
    color: #E4DFFF;
}
feature_title {
    font-size: 22px;
    font-weight: bold;
    color: #FFFFFF;
}
feature_meta {
    font-size: 13px;
    color: #E4DFFF;
}

sessions {
    height: auto;
    background-color: #FFFFFF;
    border-radius: 24px;
    padding: 6px 0px;
}
sessions_row {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 14px;
    padding: 10px 16px;
    background-color: #00000000;
}
session_art {
    width: 56px;
    height: 56px;
    object-fit: cover;
    border-radius: 16px;
}
session_words {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    background-color: #00000000;
    padding: 0px;
}
session_title {
    font-size: 15px;
    font-weight: bold;
    color: var(--text);
}
session_meta {
    font-size: 12px;
    color: var(--text-secondary);
}
session_length {
    font-size: 12px;
    font-weight: bold;
    color: var(--primary);
    background-color: #E3F2EF;
    border-radius: 12px;
    padding: 5px 10px;
}

sleep_title {
    padding: 0px;
    font-size: 30px;
    font-weight: bold;
    color: #FFFFFF;
    margin: 8px 0px 18px 0px;
}
sleep_kicker {
    padding: 0px;
    font-size: 13px;
    color: #B9B6D9;
}
sleep_total {
    padding: 0px;
    font-size: 48px;
    font-weight: bold;
    color: #FFFFFF;
}
sleep_note {
    padding: 0px;
    font-size: 13px;
    color: #B9B6D9;
}
stages {
    display: flex;
    flex-direction: row;
    gap: 10px;
    background-color: #00000000;
    padding: 0px;
    margin-top: 20px;
}
stage {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    background-color: #1E2246;
    border-radius: 18px;
    padding: 14px;
}
stage_name {
    font-size: 12px;
    color: #B9B6D9;
}
stage_time {
    font-size: 17px;
    font-weight: bold;
    color: #FFFFFF;
}
week {
    background-color: #1E2246;
    border-radius: 24px;
    padding: 20px;
    margin-top: 14px;
}
week_title {
    padding: 0px;
    font-size: 17px;
    font-weight: bold;
    color: #FFFFFF;
}
week_note {
    padding: 0px;
    font-size: 13px;
    color: #B9B6D9;
    margin-top: 2px;
}
week_chart {
    height: 150px;
    margin-top: 10px;
    color: #9C8CFF;
    label-color: #B9B6D9;
    grid-color: #2C3160;
    background-color: #00000000;
}
sounds_title {
    padding: 0px;
    font-size: 18px;
    font-weight: bold;
    color: #FFFFFF;
    margin: 24px 0px 6px 0px;
}
sound {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 14px;
    background-color: #1E2246;
    border-radius: 20px;
    padding: 10px 10px 10px 10px;
    margin-top: 8px;
}
sound_art {
    width: 52px;
    height: 52px;
    object-fit: cover;
    border-radius: 14px;
}
sound_words {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    background-color: #00000000;
    padding: 0px;
}
sound_title {
    font-size: 15px;
    font-weight: bold;
    color: #FFFFFF;
}
sound_meta {
    font-size: 12px;
    color: #B9B6D9;
}
sound_play {
    width: 48px;
    height: 48px;
    border-radius: 24px;
    background-color: #9C8CFF;
    icon-color: #12152E;
}

who {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    background-color: #00000000;
    padding: 20px 0px 22px 0px;
}
who_name {
    font-size: 22px;
    font-weight: bold;
    color: var(--text);
    margin-top: 10px;
}
who_note {
    font-size: 14px;
    color: var(--text-secondary);
}
streak {
    background: linear-gradient(135deg, #17544F 0%, #1F6F68 100%);
    border-radius: 26px;
    padding: 22px;
    box-shadow: 0 14px 28px rgba(31, 111, 104, 0.30);
}
streak_title {
    padding: 0px;
    font-size: 22px;
    font-weight: bold;
    color: #FFFFFF;
}
streak_note {
    padding: 0px;
    font-size: 13px;
    color: #E3F6F1;
    margin-top: 2px;
}
days {
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    background-color: #00000000;
    padding: 0px;
    margin-top: 18px;
}
day_done, day_open {
    width: 36px;
    height: 36px;
    border-radius: 18px;
    font-size: 13px;
    font-weight: bold;
    text-align: center;
    padding: 8px 0px;
}
day_done {
    background-color: #FFFFFF;
    color: #1F6F68;
}
day_open {
    background-color: rgba(255, 255, 255, 0.18);
    color: #FFFFFF;
}
stats {
    display: flex;
    flex-direction: row;
    gap: 10px;
    background-color: #00000000;
    padding: 0px;
    margin-top: 16px;
}
stat {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    background-color: #FFFFFF;
    border-radius: 20px;
    padding: 14px;
}
stat_number {
    font-size: 20px;
    font-weight: bold;
    color: var(--text);
}
stat_word {
    font-size: 12px;
    color: var(--text-secondary);
}
reminders {
    background-color: #FFFFFF;
    border-radius: 24px;
    padding: 20px;
    margin-top: 16px;
}
reminders_title {
    padding: 0px;
    font-size: 17px;
    font-weight: bold;
    color: var(--text);
}
reminder {
    font-size: 15px;
    color: var(--text);
    accent-color: var(--primary);
}
more {
    background-color: #FFFFFF;
    border-radius: 24px;
    padding: 6px 0px;
    margin-top: 16px;
    divider-color: #F0ECE4;
}
more_row {
    icon-color: var(--primary);
    color: var(--text);
}

bottom_nav {
    margin: 16px;
    border-radius: 28px;
    background-color: #FFFFFF;
    color: #8A9592;
    active-color: #1F6F68;
    indicator-color: #E3F2EF;
}
"""

run(start_screen=today, theme=theme)
