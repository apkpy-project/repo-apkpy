"""Lumen -- a personal finance app written in Python with ApkPy."""

from apkpy_lib import *

theme = Theme(
    mode="light",
    primary="#5B4BFF",
    secondary="#0E7A46",
    background="#F4F5FA",
    surface="#FFFFFF",
    text="#14162B",
    text_secondary="#5E6380",
    border="#E6E8F2",
    radius=20,
)

home = Screen(id="home", scroll=True)
insights = Screen(id="insights", scroll=True)
cards = Screen(id="cards", scroll=True)
profile = Screen(id="profile", scroll=True)


# ── Home ─────────────────────────────────────────────────────────────────────

top = container(id="top", screen=home)
avatar("art/face_maya.png", size=44, id="me", parent=top, describe="Maya")
hello = container(id="hello", parent=top)
label("Good morning", id="hello_small", parent=hello)
label("Maya Santos", id="hello_name", parent=hello)
container(id="spacer", parent=top)
button("", id="bell", icon="notifications", describe="Notifications", parent=top, command=lambda: toast("No new alerts"))

balance = container(id="balance", screen=home)
label("Total balance", id="balance_label", parent=balance)
label("$24,680.40", id="balance_value", parent=balance)
balance_foot = container(id="balance_foot", parent=balance)
label("+2.4% this month", id="balance_change", parent=balance_foot)
container(id="spacer", parent=balance_foot)
label("•••• 4821", id="balance_card", parent=balance_foot)

quick = container(id="quick", screen=home)
for icon, word in [("north_east", "Send"), ("south_west", "Request"), ("add", "Top up"), ("receipt_long", "Bills")]:
    cell = container(id="quick_cell", parent=quick)
    button("", id="quick_button", icon=icon, describe=word, parent=cell, command=lambda: toast("Choose an amount"))
    label(word, id="quick_word", parent=cell)

people_head = container(id="section", screen=home)
label("Send again", id="section_title", parent=people_head)
container(id="spacer", parent=people_head)
label("See all", id="section_link", parent=people_head)

people = container(id="people", screen=home)
for face, name in [("art/face_leo.png", "Léo"), ("art/face_kai.png", "Kai"), ("art/face_zoe.png", "Zoe"), ("art/face_ines.png", "Inês")]:
    person = container(id="person", parent=people)
    avatar(face, size=52, id="person_face", parent=person, describe=name)
    label(name, id="person_name", parent=person)

WEEK = [
    {"label": "M", "value": 64, "color": "#D9D3FF"},
    {"label": "T", "value": 38, "color": "#D9D3FF"},
    {"label": "W", "value": 92, "color": "#D9D3FF"},
    {"label": "T", "value": 51, "color": "#D9D3FF"},
    {"label": "F", "value": 128, "color": "#5B4BFF"},
    {"label": "S", "value": 74, "color": "#D9D3FF"},
    {"label": "S", "value": 39, "color": "#D9D3FF"},
]

spend = container(id="spend", screen=home)
spend_head = container(id="spend_head", parent=spend)
label("Spending", id="spend_title", parent=spend_head)
container(id="spacer", parent=spend_head)
label("This week", id="spend_pill", parent=spend_head)
label("$486.20", id="spend_value", parent=spend)
label("12% less than last week", id="spend_note", parent=spend)
chart(WEEK, kind="bar", id="spend_chart", parent=spend)

recent_head = container(id="section", screen=home)
label("Recent", id="section_title", parent=recent_head)
container(id="spacer", parent=recent_head)
label("See all", id="section_link", parent=recent_head)

PAYMENTS = [
    {"id": "1", "tile": "art/tile_food.png", "title": "Sage Kitchen", "when": "Today, 13:20", "out": "−$24.60", "in": ""},
    {"id": "2", "tile": "art/tile_salary.png", "title": "Studio Norte", "when": "Today, 09:00", "out": "", "in": "+$3,240.00"},
    {"id": "3", "tile": "art/tile_train.png", "title": "City Rail", "when": "Yesterday", "out": "−$3.80", "in": ""},
    {"id": "4", "tile": "art/tile_shop.png", "title": "Atelier Mira", "when": "Yesterday", "out": "−$128.00", "in": ""},
    {"id": "5", "tile": "art/tile_coffee.png", "title": "Kaffe Hus", "when": "Mon, 08:12", "out": "−$4.50", "in": ""},
]


def payment(row):
    image("{tile}", id="pay_tile", parent=row, describe="")
    words = container(id="pay_words", parent=row)
    label("{title}", id="pay_title", parent=words)
    label("{when}", id="pay_when", parent=words)
    label("{out}", id="pay_out", parent=row, visible="{out}")
    label("{in}", id="pay_in", parent=row, visible="{in}")


virtual_collection(PAYMENTS, row=payment, id="payments", screen=home, on_click=lambda item: toast(item["title"]))
container(id="bottom_room", screen=home)


# ── Insights ─────────────────────────────────────────────────────────────────

label("Insights", id="page_title", screen=insights)
segmented(["Week", "Month", "Year"], selected="Month", id="period", screen=insights)

CATEGORIES = [
    {"label": "Food", "value": 642, "color": "#FF7A1A"},
    {"label": "Shopping", "value": 518, "color": "#E2368F"},
    {"label": "Travel", "value": 436, "color": "#2F6BFF"},
    {"label": "Transport", "value": 214, "color": "#6A4DF5"},
    {"label": "Coffee", "value": 96, "color": "#9A5B24"},
]

split = container(id="panel", screen=insights)
label("Where it went", id="panel_title", parent=split)
label("November, so far", id="panel_note", parent=split)
chart(CATEGORIES, kind="donut", center="$1,906", id="split_chart", parent=split)

goal = container(id="goal", screen=insights)
goal_words = container(id="goal_words", parent=goal)
label("SAVING FOR", id="goal_kicker", parent=goal_words)
label("Kyoto in spring", id="goal_title", parent=goal_words)
label("$6,400 of $10,000", id="goal_note", parent=goal_words)
chart(kind="ring", value=6400, max=10000, id="goal_ring", parent=goal)

TREND = [
    {"label": "Jun", "value": 18200},
    {"label": "Jul", "value": 19650},
    {"label": "Aug", "value": 19100},
    {"label": "Sep", "value": 21480},
    {"label": "Oct", "value": 23020},
    {"label": "Nov", "value": 24680},
]

trend = container(id="panel", screen=insights)
label("Balance", id="panel_title", parent=trend)
label("Up $6,480 since June", id="panel_good", parent=trend)
chart(TREND, kind="line", fill=True, id="trend_chart", parent=trend)
container(id="bottom_room", screen=insights)


# ── Cards ────────────────────────────────────────────────────────────────────

label("Cards", id="page_title", screen=cards)

card = container(id="plastic", screen=cards)
plastic_top = container(id="plastic_row", parent=card)
label("Lumen", id="plastic_brand", parent=plastic_top)
container(id="spacer", parent=plastic_top)
label("Virtual", id="plastic_kind", parent=plastic_top)
label("4821  ••••  ••••  7730", id="plastic_number", parent=card)
plastic_foot = container(id="plastic_row", parent=card)
label("MAYA SANTOS", id="plastic_name", parent=plastic_foot)
container(id="spacer", parent=plastic_foot)
label("08/29", id="plastic_date", parent=plastic_foot)

controls = container(id="panel", screen=cards)
label("Card controls", id="panel_title", parent=controls)
inputs("Freeze card", type="switch", id="control", parent=controls)
online = inputs("Online payments", type="switch", id="control", parent=controls)
tap = inputs("Contactless", type="switch", id="control", parent=controls)
inputs("Withdrawals abroad", type="switch", id="control", parent=controls)
online.set_value("true")
tap.set_value("true")

limit = container(id="panel", screen=cards)
limit_head = container(id="spend_head", parent=limit)
label("Monthly limit", id="panel_title", parent=limit_head)
container(id="spacer", parent=limit_head)
limit_value = label("$3,000", id="limit_value", parent=limit_head)
slider = inputs("", type="range", id="limit", parent=limit, on_change=lambda value: limit_value.set_value("$" + str(int(float(value)) * 60)))
slider.set_value("50")
label("You have spent $1,906 of it this month.", id="panel_note", parent=limit)
container(id="bottom_room", screen=cards)


# ── Profile ──────────────────────────────────────────────────────────────────

who = container(id="who", screen=profile)
avatar("art/face_maya.png", size=88, id="who_face", parent=who, describe="Maya")
label("Maya Santos", id="who_name", parent=who)
label("maya@lumen.example", id="who_mail", parent=who)
label("PREMIUM", id="who_plan", parent=who)

settings = container(id="settings", screen=profile)
list_row("Personal details", icon="person", trailing_icon="chevron_right", id="setting", parent=settings, command=lambda: toast("Personal details"))
list_row("Security", subtitle="Face unlock is on", icon="shield", trailing_icon="chevron_right", id="setting", parent=settings, command=lambda: toast("Security"))
list_row("Notifications", icon="notifications", trailing="On", trailing_icon="chevron_right", id="setting", parent=settings, command=lambda: toast("Notifications"))
list_row("Linked accounts", icon="account_balance", trailing="2", trailing_icon="chevron_right", id="setting", parent=settings, command=lambda: toast("Linked accounts"))
list_row("Help", icon="help", trailing_icon="chevron_right", id="setting", parent=settings, command=lambda: toast("Help"))
button("Sign out", id="sign_out", variant="text", screen=profile, command=lambda: toast("Signed out"))
container(id="bottom_room", screen=profile)


bottom_nav([home, insights, cards, profile], labels=["Home", "Insights", "Cards", "Profile"], icons=["home", "insights", "credit_card", "person"])

style = """
home, insights, cards, profile {
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
    gap: 12px;
    background-color: #00000000;
    padding: 4px 0px 18px 0px;
}
hello {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    background-color: #00000000;
    padding: 0px;
}
hello_small {
    font-size: 13px;
    color: var(--text-secondary);
}
hello_name {
    font-size: 18px;
    font-weight: bold;
    color: var(--text);
}
bell {
    width: 48px;
    height: 48px;
    border-radius: 24px;
    background-color: #FFFFFF;
    icon-color: var(--text);
    box-shadow: 0 4px 12px rgba(20, 22, 43, 0.08);
}

balance {
    background: linear-gradient(135deg, #2B1C93 0%, #5B4BFF 55%, #9C83FF 100%);
    border-radius: 28px;
    padding: 22px;
    box-shadow: 0 16px 32px rgba(91, 75, 255, 0.35);
}
balance_label {
    padding: 0px;
    font-size: 13px;
    color: rgba(255, 255, 255, 0.92);
}
balance_value {
    padding: 0px;
    font-size: 36px;
    font-weight: bold;
    color: #FFFFFF;
    margin: 6px 0px 18px 0px;
}
balance_foot {
    display: flex;
    flex-direction: row;
    align-items: center;
    background-color: #00000000;
    padding: 0px;
}
balance_change {
    font-size: 12px;
    font-weight: bold;
    color: #FFFFFF;
    background-color: rgba(20, 22, 43, 0.28);
    border-radius: 12px;
    padding: 6px 10px;
}
balance_card {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.92);
}

quick {
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    background-color: #00000000;
    padding: 22px 6px 8px 6px;
}
quick_cell {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    background-color: #00000000;
    padding: 0px;
}
quick_button {
    width: 58px;
    height: 58px;
    border-radius: 20px;
    background-color: #FFFFFF;
    icon-color: var(--primary);
    icon-size: 26px;
    box-shadow: 0 6px 16px rgba(20, 22, 43, 0.07);
}
quick_word {
    font-size: 12px;
    color: var(--text);
}

section {
    display: flex;
    flex-direction: row;
    align-items: center;
    background-color: #00000000;
    padding: 20px 0px 12px 0px;
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

people {
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    background-color: #FFFFFF;
    border-radius: 24px;
    padding: 16px 18px;
}
person {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    background-color: #00000000;
    padding: 0px;
}
person_name {
    font-size: 12px;
    color: var(--text);
}

spend {
    background-color: #FFFFFF;
    border-radius: 24px;
    padding: 18px;
    margin-top: 14px;
}
spend_head {
    display: flex;
    flex-direction: row;
    align-items: center;
    background-color: #00000000;
    padding: 0px;
}
spend_title {
    font-size: 15px;
    font-weight: bold;
    color: var(--text);
}
spend_pill {
    font-size: 12px;
    font-weight: bold;
    color: var(--primary);
    background-color: #EEEBFF;
    border-radius: 12px;
    padding: 5px 10px;
}
spend_value {
    padding: 0px;
    font-size: 28px;
    font-weight: bold;
    color: var(--text);
    margin-top: 10px;
}
spend_note {
    padding: 0px;
    font-size: 13px;
    color: var(--secondary);
}
spend_chart {
    height: 150px;
    margin-top: 6px;
}

payments {
    height: auto;
    background-color: #FFFFFF;
    border-radius: 24px;
    padding: 6px 0px;
}
payments_row {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 14px;
    padding: 12px 18px;
    background-color: #00000000;
}
pay_tile {
    width: 46px;
    height: 46px;
}
pay_words {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    background-color: #00000000;
    padding: 0px;
}
pay_title {
    font-size: 15px;
    font-weight: bold;
    color: var(--text);
}
pay_when {
    font-size: 12px;
    color: var(--text-secondary);
}
pay_out {
    font-size: 15px;
    font-weight: bold;
    color: var(--text);
}
pay_in {
    font-size: 15px;
    font-weight: bold;
    color: var(--secondary);
}

page_title {
    padding: 0px;
    font-size: 30px;
    font-weight: bold;
    color: var(--text);
    margin: 8px 0px 16px 0px;
}
period {
    margin-bottom: 16px;
}
panel {
    background-color: #FFFFFF;
    border-radius: 24px;
    padding: 20px;
    margin-bottom: 16px;
}
panel_title {
    padding: 0px;
    font-size: 17px;
    font-weight: bold;
    color: var(--text);
}
panel_note {
    padding: 0px;
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 4px;
}
panel_good {
    padding: 0px;
    font-size: 13px;
    color: var(--secondary);
    margin-top: 4px;
}
split_chart {
    height: 230px;
    margin-top: 8px;
}
goal {
    display: flex;
    flex-direction: row;
    align-items: center;
    background: linear-gradient(135deg, #EEEBFF 0%, #FFFFFF 100%);
    border-radius: 24px;
    padding: 20px;
    margin-bottom: 16px;
}
goal_words {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
    background-color: #00000000;
    padding: 0px;
}
goal_kicker {
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.5px;
    color: var(--primary);
}
goal_title {
    font-size: 19px;
    font-weight: bold;
    color: var(--text);
}
goal_note {
    font-size: 13px;
    color: var(--text-secondary);
}
goal_ring {
    background-color: #00000000;
    width: 96px;
    height: 96px;
}
trend_chart {
    height: 170px;
    margin-top: 8px;
}

plastic {
    background: linear-gradient(135deg, #14162B 0%, #2B1C93 60%, #5B4BFF 100%);
    border-radius: 26px;
    padding: 22px;
    margin-bottom: 18px;
    box-shadow: 0 16px 30px rgba(20, 22, 43, 0.30);
}
plastic_row {
    display: flex;
    flex-direction: row;
    align-items: center;
    background-color: #00000000;
    padding: 0px;
}
plastic_brand {
    font-size: 20px;
    font-weight: bold;
    color: #FFFFFF;
}
plastic_kind {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.7);
}
plastic_number {
    padding: 0px;
    font-size: 20px;
    color: #FFFFFF;
    margin: 54px 0px 18px 0px;
}
plastic_name {
    font-size: 13px;
    font-weight: bold;
    letter-spacing: 1px;
    color: rgba(255, 255, 255, 0.85);
}
plastic_date {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.85);
}
control {
    font-size: 15px;
    color: var(--text);
    accent-color: var(--primary);
}
limit_value {
    font-size: 17px;
    font-weight: bold;
    color: var(--primary);
}
limit {
    accent-color: var(--primary);
    margin-top: 12px;
}

who {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    background-color: #00000000;
    padding: 20px 0px 24px 0px;
}
who_name {
    font-size: 22px;
    font-weight: bold;
    color: var(--text);
    margin-top: 10px;
}
who_mail {
    font-size: 14px;
    color: var(--text-secondary);
}
who_plan {
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.5px;
    color: var(--primary);
    background-color: #EEEBFF;
    border-radius: 12px;
    padding: 5px 12px;
    margin-top: 8px;
}
settings {
    background-color: #FFFFFF;
    border-radius: 24px;
    padding: 6px 0px;
    divider-color: #EEF0F6;
}
setting {
    icon-color: var(--primary);
    color: var(--text);
}
sign_out {
    color: #C42B30;
    text-transform: none;
    margin-top: 12px;
}

bottom_nav {
    margin: 16px;
    border-radius: 28px;
    background-color: #FFFFFF;
    color: #9AA0B8;
    active-color: #5B4BFF;
    indicator-color: #EEEBFF;
}
"""

run(start_screen=home, theme=theme)
