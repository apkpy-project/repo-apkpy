"""Northline -- a travel planner written in Python with ApkPy."""

from apkpy_lib import *

theme = Theme(
    mode="light",
    primary="#0F4C81",
    secondary="#C2410C",
    background="#F6F7F9",
    surface="#FFFFFF",
    text="#101828",
    text_secondary="#5B6577",
    border="#E4E7EC",
    radius=20,
)

discover = Screen(id="discover", scroll=True)
trips = Screen(id="trips", scroll=True)
saved = Screen(id="saved", scroll=True)
me = Screen(id="me", scroll=True)


def place_card(art, name, meta, parent):
    card = container(id="place", parent=parent)
    image(art, id="place_art", parent=card, describe="")
    label(name, id="place_name", parent=card)
    label(meta, id="place_meta", parent=card)


# ── Discover ─────────────────────────────────────────────────────────────────

top = container(id="top", screen=discover)
words = container(id="top_words", parent=top)
label("Good afternoon, Kai", id="top_hello", parent=words)
label("Where to next?", id="top_title", parent=words)
container(id="spacer", parent=top)
avatar("art/face_kai.png", size=44, id="me_face", parent=top, describe="Kai")

inputs("Search places, stays, flights", type="search", id="find", screen=discover)
chips(["Cities", "Coast", "Peaks", "Food"], selected="Cities", id="kinds", screen=discover)

hero = container(id="hero", screen=discover)
image("art/place_porto.jpg", id="hero_art", parent=hero, describe="")
button("", id="hero_save", icon="favorite_border", describe="Save Porto", parent=hero, command=lambda: toast("Saved"))
hero_words = container(id="hero_words", parent=hero)
label("EDITOR'S PICK", id="hero_kicker", parent=hero_words)
label("Porto", id="hero_title", parent=hero_words)
label("Golden hour on the Douro · from €129", id="hero_meta", parent=hero_words)

popular_head = container(id="section", screen=discover)
label("Popular now", id="section_title", parent=popular_head)
container(id="spacer", parent=popular_head)
label("See all", id="section_link", parent=popular_head)

pair = container(id="pair", screen=discover)
place_card("art/place_kyoto.jpg", "Kyoto", "Japan · 4.9", pair)
place_card("art/place_banff.jpg", "Banff", "Canada · 4.8", pair)

label("Weekend escapes", id="heading", screen=discover)

ESCAPES = [
    {"id": "1", "art": "art/place_lisbon.jpg", "name": "Lisbon", "when": "2 nights · Fri – Sun", "price": "€189"},
    {"id": "2", "art": "art/place_copenhagen.jpg", "name": "Copenhagen", "when": "3 nights · Thu – Sun", "price": "€312"},
    {"id": "3", "art": "art/place_marrakech.jpg", "name": "Marrakech", "when": "3 nights · Fri – Mon", "price": "€245"},
    {"id": "4", "art": "art/place_santorini.jpg", "name": "Santorini", "when": "4 nights · Wed – Sun", "price": "€398"},
]


def escape(row):
    image("{art}", id="escape_art", parent=row, describe="")
    texts = container(id="escape_words", parent=row)
    label("{name}", id="escape_name", parent=texts)
    label("{when}", id="escape_when", parent=texts)
    label("{price}", id="escape_price", parent=row)


virtual_collection(ESCAPES, row=escape, id="escapes", screen=discover, on_click=lambda item: toast(item["name"]))
container(id="bottom_room", screen=discover)


# ── Trips ────────────────────────────────────────────────────────────────────

label("Trips", id="page_title", screen=trips)
segmented(["Upcoming", "Past"], selected="Upcoming", id="when", screen=trips)

trip = container(id="trip", screen=trips)
image("art/place_reykjavik.jpg", id="trip_art", parent=trip, describe="")
label("In 21 days", id="trip_count", parent=trip)
trip_words = container(id="trip_words", parent=trip)
label("Reykjavík, Iceland", id="trip_title", parent=trip_words)
label("6 – 11 December · 2 travellers", id="trip_meta", parent=trip_words)

flight = container(id="flight", screen=trips)
route = container(id="route", parent=flight)
start = container(id="end_left", parent=route)
label("LIS", id="code", parent=start)
label("Lisbon · 10:40", id="city", parent=start)
container(id="spacer", parent=route)
button("", id="plane", icon="flight", describe="Flight", parent=route, command=lambda: toast("Flight NL 204"))
container(id="spacer", parent=route)
finish = container(id="end_right", parent=route)
label("KEF", id="code", parent=finish)
label("Keflavík · 14:05", id="city", parent=finish)
facts = container(id="facts", parent=flight)
for value, name in [("B12", "Gate"), ("14A", "Seat"), ("09:50", "Boarding")]:
    fact = container(id="fact", parent=facts)
    label(name, id="fact_name", parent=fact)
    label(value, id="fact_value", parent=fact)

label("The plan", id="heading", screen=trips)
plan = container(id="plan", screen=trips)
list_row("Northern lights by the bay", subtitle="Day 1 · 22:00", icon="nights_stay", trailing_icon="chevron_right", id="step", parent=plan, command=lambda: toast("Day 1"))
list_row("Hot springs at Sky Lagoon", subtitle="Day 2 · 16:00", icon="hot_tub", trailing_icon="chevron_right", id="step", parent=plan, command=lambda: toast("Day 2"))
list_row("The Golden Circle by car", subtitle="Day 3 · 09:00", icon="directions_car", trailing_icon="chevron_right", id="step", parent=plan, command=lambda: toast("Day 3"))
list_row("Hótel Viðey, 5 nights", subtitle="Check in 15:00", icon="hotel", trailing_icon="chevron_right", id="step", parent=plan, command=lambda: toast("Stay"))
container(id="bottom_room", screen=trips)


# ── Saved ────────────────────────────────────────────────────────────────────

label("Saved", id="page_title", screen=saved)
label("8 places in 7 countries", id="page_note", screen=saved)
row = container(id="pair", screen=saved)
place_card("art/place_santorini.jpg", "Santorini", "Greece · €398", row)
place_card("art/place_banff.jpg", "Banff", "Canada · €720", row)
row = container(id="pair", screen=saved)
place_card("art/place_marrakech.jpg", "Marrakech", "Morocco · €245", row)
place_card("art/place_lisbon.jpg", "Lisbon", "Portugal · €189", row)
row = container(id="pair", screen=saved)
place_card("art/place_copenhagen.jpg", "Copenhagen", "Denmark · €312", row)
place_card("art/place_reykjavik.jpg", "Reykjavík", "Iceland · €540", row)
container(id="bottom_room", screen=saved)


# ── Me ───────────────────────────────────────────────────────────────────────

who = container(id="who", screen=me)
avatar("art/face_kai.png", size=88, id="who_face", parent=who, describe="Kai")
label("Kai Oliveira", id="who_name", parent=who)
label("Exploring since 2019", id="who_note", parent=who)

stats = container(id="stats", screen=me)
for number, word in [("23", "countries"), ("41", "trips"), ("86k", "km flown")]:
    stat = container(id="stat", parent=stats)
    label(number, id="stat_number", parent=stat)
    label(word, id="stat_word", parent=stat)

alerts = container(id="alerts", screen=me)
label("Alerts", id="alerts_title", parent=alerts)
prices = inputs("Price drops on saved places", type="switch", id="alert", parent=alerts)
inputs("Gate and boarding changes", type="switch", id="alert", parent=alerts)
prices.set_value("true")

more = container(id="more", screen=me)
list_row("Passport and visas", icon="badge", trailing_icon="chevron_right", id="more_row", parent=more, command=lambda: toast("Documents"))
list_row("Payment methods", icon="credit_card", trailing_icon="chevron_right", id="more_row", parent=more, command=lambda: toast("Payments"))
list_row("Help", icon="help", trailing_icon="chevron_right", id="more_row", parent=more, command=lambda: toast("Help"))
container(id="bottom_room", screen=me)


bottom_nav([discover, trips, saved, me], labels=["Discover", "Trips", "Saved", "Me"], icons=["explore", "luggage", "favorite", "person"])

style = """
discover, trips, saved, me {
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
    background-color: #00000000;
    padding: 4px 0px 16px 0px;
}
top_words {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    background-color: #00000000;
    padding: 0px;
}
top_hello {
    font-size: 13px;
    color: var(--text-secondary);
}
top_title {
    font-size: 26px;
    font-weight: bold;
    color: var(--text);
}
find {
    background-color: #FFFFFF;
    border-radius: 16px;
    margin-bottom: 12px;
}
kinds {
    accent-color: var(--primary);
}

hero {
    position: relative;
    height: 300px;
    padding: 0px;
    margin-top: 16px;
    background-color: #00000000;
}
hero_art {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 28px;
}
hero_save {
    position: absolute;
    bottom: 18px;
    right: 18px;
    width: 48px;
    height: 48px;
    border-radius: 24px;
    background-color: #FFFFFF;
    icon-color: #C2410C;
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
    color: #FFE3C8;
}
hero_title {
    font-size: 30px;
    font-weight: bold;
    color: #FFFFFF;
}
hero_meta {
    font-size: 13px;
    color: #F3EEFF;
}

section {
    display: flex;
    flex-direction: row;
    align-items: center;
    background-color: #00000000;
    padding: 22px 0px 10px 0px;
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
heading {
    padding: 22px 0px 10px 0px;
    font-size: 18px;
    font-weight: bold;
    color: var(--text);
}

pair {
    display: flex;
    flex-direction: row;
    gap: 12px;
    background-color: #00000000;
    padding: 0px;
    margin-bottom: 12px;
}
place {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    background-color: #FFFFFF;
    border-radius: 22px;
    padding: 8px 8px 14px 8px;
}
place_art {
    width: 100%;
    height: 130px;
    object-fit: cover;
    border-radius: 16px;
    margin-bottom: 8px;
}
place_name {
    font-size: 16px;
    font-weight: bold;
    color: var(--text);
    margin-left: 6px;
}
place_meta {
    font-size: 12px;
    color: var(--text-secondary);
    margin-left: 6px;
}

escapes {
    height: auto;
    background-color: #FFFFFF;
    border-radius: 24px;
    padding: 6px 0px;
}
escapes_row {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 14px;
    padding: 10px 16px;
    background-color: #00000000;
}
escape_art {
    width: 64px;
    height: 64px;
    object-fit: cover;
    border-radius: 16px;
}
escape_words {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    background-color: #00000000;
    padding: 0px;
}
escape_name {
    font-size: 16px;
    font-weight: bold;
    color: var(--text);
}
escape_when {
    font-size: 12px;
    color: var(--text-secondary);
}
escape_price {
    font-size: 16px;
    font-weight: bold;
    color: var(--secondary);
}

page_title {
    padding: 0px;
    font-size: 30px;
    font-weight: bold;
    color: var(--text);
    margin: 8px 0px 14px 0px;
}
page_note {
    padding: 0px;
    font-size: 14px;
    color: var(--text-secondary);
    margin-bottom: 16px;
}
when {
    margin-bottom: 16px;
}

trip {
    position: relative;
    height: 220px;
    padding: 0px;
    background-color: #00000000;
}
trip_art {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 26px;
}
trip_count {
    position: absolute;
    top: 16px;
    left: 16px;
    font-size: 12px;
    font-weight: bold;
    color: #0F4C81;
    background-color: #FFFFFF;
    border-radius: 14px;
    padding: 6px 12px;
}
trip_words {
    position: absolute;
    left: 20px;
    bottom: 18px;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    background-color: #00000000;
}
trip_title {
    font-size: 24px;
    font-weight: bold;
    color: #FFFFFF;
}
trip_meta {
    font-size: 13px;
    color: #D7F5EE;
}

flight {
    background-color: #FFFFFF;
    border-radius: 24px;
    padding: 20px;
    margin-top: 14px;
}
route {
    display: flex;
    flex-direction: row;
    align-items: center;
    background-color: #00000000;
    padding: 0px;
}
end_left {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    background-color: #00000000;
    padding: 0px;
}
end_right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    background-color: #00000000;
    padding: 0px;
}
code {
    font-size: 28px;
    font-weight: bold;
    color: var(--text);
}
city {
    font-size: 12px;
    color: var(--text-secondary);
}
plane {
    width: 48px;
    height: 48px;
    border-radius: 24px;
    background-color: #E8F0F8;
    icon-color: var(--primary);
}
facts {
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    background-color: #F6F7F9;
    border-radius: 16px;
    padding: 12px 16px;
    margin-top: 16px;
}
fact {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    background-color: #00000000;
    padding: 0px;
}
fact_name {
    font-size: 12px;
    color: var(--text-secondary);
}
fact_value {
    font-size: 16px;
    font-weight: bold;
    color: var(--text);
}
plan {
    background-color: #FFFFFF;
    border-radius: 24px;
    padding: 6px 0px;
    divider-color: #EEF0F3;
}
step {
    icon-color: var(--primary);
    color: var(--text);
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
stats {
    display: flex;
    flex-direction: row;
    gap: 10px;
    background-color: #00000000;
    padding: 0px;
}
stat {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    background: linear-gradient(135deg, #0F4C81 0%, #2B6CB0 100%);
    border-radius: 20px;
    padding: 16px;
}
stat_number {
    font-size: 24px;
    font-weight: bold;
    color: #FFFFFF;
}
stat_word {
    font-size: 12px;
    color: #DCE8F5;
}
alerts {
    background-color: #FFFFFF;
    border-radius: 24px;
    padding: 20px;
    margin-top: 16px;
}
alerts_title {
    padding: 0px;
    font-size: 17px;
    font-weight: bold;
    color: var(--text);
}
alert {
    font-size: 15px;
    color: var(--text);
    accent-color: var(--primary);
}
more {
    background-color: #FFFFFF;
    border-radius: 24px;
    padding: 6px 0px;
    margin-top: 16px;
    divider-color: #EEF0F3;
}
more_row {
    icon-color: var(--primary);
    color: var(--text);
}

bottom_nav {
    margin: 16px;
    border-radius: 28px;
    background-color: #FFFFFF;
    color: #8A93A3;
    active-color: #0F4C81;
    indicator-color: #E8F0F8;
}
"""

run(start_screen=discover, theme=theme)
