"""Lumen — a restrained personal finance dashboard built with ApkPy."""

from apkpy_lib import (
    Screen, Theme, action, app_bar, bottom_nav, button, chart, container,
    device, label, list_view, run, toast,
)


device("Pixel 9")

theme = Theme(
    mode="light",
    primary="#16324F",
    secondary="#BF4428",      # 4.5:1 for small text on the background
    background="#F3F0E9",
    surface="#FFFFFF",
    text="#17212B",
    text_secondary="#5E6A76",
    border="#DED9CF",
    radius=18,
    spacing=14,
    font_family="sans-serif",
)

home = Screen(id="lumen_home", scroll=True)
insights = Screen(id="lumen_insights", scroll=True)
cards = Screen(id="lumen_cards", scroll=True)
profile = Screen(id="lumen_profile", scroll=True)

app_bar(
    "Lumen",
    actions=[
        action("notifications", label="Notifications", command=lambda: toast("You're all caught up")),
        action("person", label="Profile", command=lambda: toast("Profile opened")),
    ],
    screen=home,
)

label("TUESDAY, 16 JULY", id="lumen_date", screen=home)
label("Good morning, Maya.", id="lumen_hello", screen=home)
label("Your money is moving in the right direction.", id="lumen_intro", screen=home)

balance = container(id="lumen_balance", screen=home)
label("TOTAL BALANCE", id="balance_kicker", parent=balance)
label("$24,680.40", id="balance_value", parent=balance)
label("+$1,842 this month", id="balance_change", parent=balance)

actions_row = container(id="money_actions", screen=home)
button("Add money", id="add_money", icon="add", variant="filled", parent=actions_row,
       command=lambda: toast("Deposit flow ready"))
button("Transfer", id="transfer", icon="arrow_forward", variant="outlined", parent=actions_row,
       command=lambda: toast("Choose a recipient"))

label("Recent activity", id="activity_title", screen=home)

list_view(
    [
        {"title": "Northline Rail", "subtitle": "Travel · Today", "meta": "−$42.80", "icon": "local_shipping"},
        {"title": "Studio invoice", "subtitle": "Income · Yesterday", "meta": "+$1,260", "icon": "download"},
        {"title": "Sage Market", "subtitle": "Groceries · 14 Jul", "meta": "−$68.24", "icon": "inventory_2"},
    ],
    id="lumen_activity",
    rich=True,
    screen=home,
    on_click=lambda item: toast(item["title"]),
)

label("Spending is 12% below your July plan.", id="lumen_note", screen=home)

# ── Insights: four native charts ───────────────────────────────────────────
MONTHS = [
    {"label": "Feb", "value": 1920, "text": "$1,920"},
    {"label": "Mar", "value": 1610, "text": "$1,610"},
    {"label": "Apr", "value": 1745, "text": "$1,745"},
    {"label": "May", "value": 1530, "text": "$1,530"},
    {"label": "Jun", "value": 1488, "text": "$1,488"},
    {"label": "Jul", "value": 1284, "text": "$1,284 so far", "color": "#E85D3F"},
]
CATEGORIES = [
    {"label": "Groceries", "value": 412, "color": "#16324F"},
    {"label": "Travel", "value": 286, "color": "#E85D3F"},
    {"label": "Home", "value": 236, "color": "#3E8E6A"},
    {"label": "Dining", "value": 198, "color": "#D9A441"},
    {"label": "Other", "value": 152, "color": "#A9B4BF"},
]
JULY = [
    {"label": "1", "value": 42},
    {"label": "3", "value": 180},
    {"label": "5", "value": 260},
    {"label": "7", "value": 410},
    {"label": "9", "value": 520},
    {"label": "11", "value": 760},
    {"label": "13", "value": 905},
    {"label": "15", "value": 1110},
    {"label": "16", "value": 1284},
]


def show_month(item):
    month_note.set_value(item["label"] + ": " + item["text"])


label("Insights", id="lumen_insights_title", screen=insights)
label("July so far, next to the months before it.", id="lumen_insights_copy", screen=insights)

plan = container(id="insight_plan", screen=insights)
label("JULY PLAN", id="plan_kicker", parent=plan)
label("$1,284 of $2,800", id="plan_value", parent=plan)
chart(kind="ring", value=1284, max=2800, id="plan_ring", parent=plan)
label("$1,516 left for the last 15 days of the month.", id="plan_left", parent=plan)

months = container(id="insight_months", screen=insights)
label("Monthly spending", id="months_title", parent=months)
month_note = label("Your lightest month this year. Tap a bar.", id="months_note", parent=months)
chart(MONTHS, kind="bar", id="months_chart", parent=months, on_click=show_month)

split = container(id="insight_split", screen=insights)
label("Where it went", id="split_title", parent=split)
chart(CATEGORIES, kind="donut", center="$1,284", id="split_chart", parent=split)

pace = container(id="insight_pace", screen=insights)
label("July, day by day", id="pace_title", parent=pace)
label("On pace for about $2,460, 12% under plan.", id="pace_note", parent=pace)
chart(JULY, kind="line", fill=True, id="pace_chart", parent=pace)

for page, title, copy in [
    (cards, "Cards", "Manage limits, freezes and travel settings."),
    (profile, "Profile", "Your account, security and preferences."),
]:
    label(title, id=page.id + "_title", screen=page)
    label(copy, id=page.id + "_copy", screen=page)

bottom_nav(
    [home, insights, cards, profile],
    labels=["Home", "Insights", "Cards", "Profile"],
    icons=["home", "chart", "description", "person"],
)

style = """
body { font-family: var(--font-family); }
lumen_home, lumen_insights, lumen_cards, lumen_profile {
    background-color: var(--background); padding: 20px;
}
label { color: var(--text); }
lumen_date {
    color: var(--secondary); font-size: 11px; font-weight: bold;
    letter-spacing: 1.5px; margin-top: 8px; margin-bottom: 8px;
}
lumen_hello {
    color: var(--text); font-size: 28px; font-weight: bold;
    margin-bottom: 5px;
}
lumen_intro {
    color: var(--text-secondary); font-size: 14px; margin-bottom: 18px;
}
lumen_balance {
    width: 100%; background-color: #16324F; border-width: 0px;
    border-radius: 22px; padding: 20px; margin-bottom: 12px;
    box-shadow: 0 8px 20px #16324F33;
}
balance_kicker {
    color: #A9BDD0; font-size: 11px; font-weight: bold;
    letter-spacing: 1.4px; margin-bottom: 8px;
}
balance_value { color: #FFFFFF; font-size: 31px; font-weight: bold; margin-bottom: 7px; }
balance_change { color: #AEE6C7; font-size: 13px; }
money_actions {
    display: flex; flex-direction: row; gap: 10px; width: 100%;
    background-color: var(--background); border-width: 0px; padding: 0px;
    margin-bottom: 14px;
}
add_money, transfer {
    flex-grow: 1; flex-basis: 140px; padding: 12px; border-radius: 14px;
    font-size: 13px; font-weight: bold;
}
add_money { background-color: var(--secondary); color: #FFFFFF; }
transfer { background-color: #FFFFFF; color: #16324F; border-color: #B9C4CC; border-width: 1px; }
activity_title {
    color: var(--text); font-size: 18px; font-weight: bold;
    margin-top: 2px; margin-bottom: 9px;
}
lumen_activity {
    color: var(--text); background-color: #FFFFFF; border-color: var(--border);
    border-width: 1px; border-radius: 18px; margin-bottom: 12px;
}
lumen_note {
    color: #3E6952; background-color: #E1F0E7; border-radius: 13px;
    padding: 12px; font-size: 12px; margin-bottom: 12px;
}
lumen_insights_title, lumen_cards_title, lumen_profile_title {
    color: var(--text); font-size: 28px; font-weight: bold; margin-top: 30px;
}
lumen_insights_copy, lumen_cards_copy, lumen_profile_copy {
    color: var(--text-secondary); font-size: 14px; margin-top: 8px;
}
lumen_insights_copy { margin-bottom: 6px; }
insight_plan, insight_months, insight_split, insight_pace {
    display: flex; flex-direction: column; align-items: flex-start; gap: 4px;
    width: 100%; background-color: #FFFFFF; border-color: var(--border);
    border-width: 1px; border-radius: 20px; padding: 18px;
}
plan_kicker {
    color: var(--secondary); font-size: 11px; font-weight: bold; letter-spacing: 1.4px;
}
plan_value { color: var(--text); font-size: 24px; font-weight: bold; }
plan_ring {
    align-self: stretch; height: 170px; margin-top: 8px; margin-bottom: 6px;
    color: #16324F; track-color: #ECE7DD; title-color: #16324F; stroke-width: 14px;
}
plan_left, months_note, pace_note { color: var(--text-secondary); font-size: 13px; }
months_title, split_title, pace_title { color: var(--text); font-size: 17px; font-weight: bold; }
months_chart, pace_chart, split_chart {
    align-self: stretch; margin-top: 10px;
    color: #16324F; label-color: #65717D; grid-color: #ECE7DD; title-color: #17212B;
}
"""

if __name__ == "__main__":
    run(start_screen=home, theme=theme)
