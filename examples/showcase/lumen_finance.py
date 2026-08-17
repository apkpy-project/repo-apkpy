"""Lumen — a restrained personal finance dashboard built with ApkPy."""

from apkpy_lib import (
    Screen, Theme, action, app_bar, bottom_nav, button, container, device,
    label, list_view, run, toast,
)


device("Pixel 9")

theme = Theme(
    mode="light",
    primary="#16324F",
    secondary="#E85D3F",
    background="#F3F0E9",
    surface="#FFFFFF",
    text="#17212B",
    text_secondary="#65717D",
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
        {"title": "Northline Rail", "subtitle": "Travel · Today", "meta": "−$42.80", "icon": "train"},
        {"title": "Studio invoice", "subtitle": "Income · Yesterday", "meta": "+$1,260", "icon": "payments"},
        {"title": "Sage Market", "subtitle": "Groceries · 14 Jul", "meta": "−$68.24", "icon": "shopping_bag"},
    ],
    id="lumen_activity",
    rich=True,
    screen=home,
    on_click=lambda item: toast(item["title"]),
)

label("Spending is 12% below your July plan.", id="lumen_note", screen=home)

for page, title, copy in [
    (insights, "Insights", "A calm overview of your monthly habits."),
    (cards, "Cards", "Manage limits, freezes and travel settings."),
    (profile, "Profile", "Your account, security and preferences."),
]:
    label(title, id=page.id + "_title", screen=page)
    label(copy, id=page.id + "_copy", screen=page)

bottom_nav(
    [home, insights, cards, profile],
    labels=["Home", "Insights", "Cards", "Profile"],
    icons=["home", "chart", "credit_card", "person"],
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
"""

if __name__ == "__main__":
    run(start_screen=home, theme=theme)
