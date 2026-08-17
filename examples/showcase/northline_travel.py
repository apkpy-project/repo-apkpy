"""Northline — a clear, editorial travel companion built with ApkPy."""

from apkpy_lib import (
    Screen, Theme, action, app_bar, bottom_nav, button, container, device,
    label, run, toast,
)


device("Pixel 9")

theme = Theme(
    mode="light",
    primary="#0B3B60",
    secondary="#E4573D",
    background="#F5F3EE",
    surface="#FFFFFF",
    text="#14202A",
    text_secondary="#68727A",
    border="#DCD8CF",
    radius=18,
    spacing=14,
    font_family="sans-serif",
)

trip = Screen(id="northline_trip", scroll=True)
discover = Screen(id="northline_discover", scroll=True)
saved = Screen(id="northline_saved", scroll=True)
account = Screen(id="northline_account", scroll=True)

app_bar(
    "Northline",
    leading="menu",
    actions=[action("notifications", label="Travel alerts", command=lambda: toast("No new travel alerts"))],
    screen=trip,
)

label("NEXT JOURNEY", id="journey_kicker", screen=trip)
label("Lisbon to Copenhagen", id="journey_title", screen=trip)
label("Thursday, 18 July · 4 nights", id="journey_meta", screen=trip)

ticket = container(id="flight_ticket", screen=trip)
ticket_top = container(id="ticket_top", parent=ticket)
origin = container(id="origin", parent=ticket_top)
label("LIS", id="origin_code", parent=origin)
label("07:15", id="origin_time", parent=origin)
route = container(id="route", parent=ticket_top)
label("DIRECT", id="route_type", parent=route)
label("3h 35m", id="route_time", parent=route)
destination = container(id="destination", parent=ticket_top)
label("CPH", id="destination_code", parent=destination)
label("11:50", id="destination_time", parent=destination)
label("SK 891 · Gate 42 · Seat 8A", id="flight_details", parent=ticket)
button("Open boarding pass", id="boarding_pass", icon="arrow_forward", variant="filled", parent=ticket,
       command=lambda: toast("Boarding pass ready"))

section = container(id="plan_header", screen=trip)
label("Thursday plan", id="plan_title", parent=section)
label("LOCAL TIME", id="plan_timezone", parent=section)

timeline = container(id="trip_timeline", screen=trip)
morning = container(id="timeline_morning", parent=timeline)
label("12:30", id="morning_time", parent=morning)
morning_copy = container(id="morning_copy", parent=morning)
label("Check in at Hotel Sanders", id="morning_title", parent=morning_copy)
label("Tordenskjoldsgade 15", id="morning_meta", parent=morning_copy)
afternoon = container(id="timeline_afternoon", parent=timeline)
label("15:00", id="afternoon_time", parent=afternoon)
afternoon_copy = container(id="afternoon_copy", parent=afternoon)
label("Architecture walk", id="afternoon_title", parent=afternoon_copy)
label("Meet Liv outside BLOX", id="afternoon_meta", parent=afternoon_copy)
evening = container(id="timeline_evening", parent=timeline)
label("19:30", id="evening_time", parent=evening)
evening_copy = container(id="evening_copy", parent=evening)
label("Dinner at Barr", id="evening_title", parent=evening_copy)
label("Table for two · Ref. 4J7P", id="evening_meta", parent=evening_copy)

button("Add to itinerary", id="add_itinerary", icon="add", variant="outlined", screen=trip,
       command=lambda: toast("New itinerary item"))

for page, title, copy in [
    (discover, "Discover", "Places selected for pace, craft and character."),
    (saved, "Saved", "Trips, stays and ideas worth returning to."),
    (account, "Account", "Documents, travellers and notification settings."),
]:
    label(title, id=page.id + "_title", screen=page)
    label(copy, id=page.id + "_copy", screen=page)

bottom_nav(
    [trip, discover, saved, account],
    labels=["Trip", "Discover", "Saved", "Account"],
    icons=["train", "search", "heart", "person"],
)

style = """
body { font-family: var(--font-family); }
northline_trip, northline_discover, northline_saved, northline_account {
    background-color: var(--background); padding: 20px;
}
label { color: var(--text); }
journey_kicker {
    color: var(--secondary); font-size: 10px; font-weight: bold;
    letter-spacing: 1.5px; margin-top: 8px; margin-bottom: 8px;
}
journey_title { color: var(--text); font-size: 27px; font-weight: bold; margin-bottom: 4px; }
journey_meta { color: var(--text-secondary); font-size: 13px; margin-bottom: 17px; }
flight_ticket {
    width: 100%; background-color: #0B3B60; border-width: 0px;
    border-radius: 22px; padding: 18px; margin-bottom: 17px;
    box-shadow: 0 8px 18px #0B3B602E;
}
ticket_top {
    display: flex; flex-direction: row; align-items: center; width: 100%;
    background-color: #0B3B60; border-width: 0px; padding: 0px; margin-bottom: 14px;
}
origin, destination, route { background-color: #0B3B60; border-width: 0px; padding: 0px; }
origin, destination { flex-grow: 1; }
destination { align-items: flex-end; }
route { align-items: center; }
origin_code, destination_code { color: #FFFFFF; font-size: 30px; font-weight: bold; }
origin_time, destination_time { color: #C6D9E7; font-size: 12px; margin-top: 2px; }
route_type { color: #F3AE9F; font-size: 9px; font-weight: bold; letter-spacing: 1px; }
route_time { color: #C6D9E7; font-size: 11px; margin-top: 3px; }
flight_details {
    color: #D7E4EC; border-top-color: #3D6684; border-top-width: 1px;
    padding-top: 11px; font-size: 12px; margin-bottom: 12px;
}
boarding_pass {
    width: 100%; background-color: #FFFFFF; color: #0B3B60;
    border-radius: 13px; padding: 12px; font-weight: bold;
}
plan_header {
    display: flex; flex-direction: row; align-items: center; width: 100%;
    background-color: var(--background); border-width: 0px; padding: 0px;
    margin-bottom: 8px;
}
plan_title { color: var(--text); font-size: 18px; font-weight: bold; flex-grow: 1; }
plan_timezone { color: var(--text-secondary); font-size: 9px; font-weight: bold; letter-spacing: 1px; }
trip_timeline {
    width: 100%; background-color: #FFFFFF; border-color: var(--border);
    border-width: 1px; border-radius: 18px; padding: 6px 14px; margin-bottom: 12px;
}
timeline_morning, timeline_afternoon, timeline_evening {
    display: flex; flex-direction: row; align-items: center; gap: 12px;
    width: 100%; background-color: #FFFFFF; border-width: 0px;
    border-bottom-color: #E4E0D8; border-bottom-width: 1px; border-radius: 0px;
    padding: 11px 0px;
}
timeline_evening { border-bottom-width: 0px; }
morning_time, afternoon_time, evening_time { color: var(--secondary); font-size: 11px; font-weight: bold; }
morning_copy, afternoon_copy, evening_copy {
    flex-grow: 1; background-color: #FFFFFF; border-width: 0px; padding: 0px;
}
morning_title, afternoon_title, evening_title { color: var(--text); font-size: 13px; font-weight: bold; }
morning_meta, afternoon_meta, evening_meta { color: var(--text-secondary); font-size: 10px; margin-top: 3px; }
add_itinerary {
    width: 100%; color: #0B3B60; background-color: var(--background);
    border-color: #0B3B60; border-width: 1px; border-radius: 14px;
    padding: 12px; font-weight: bold; margin-bottom: 10px;
}
northline_discover_title, northline_saved_title, northline_account_title {
    color: var(--text); font-size: 28px; font-weight: bold; margin-top: 30px;
}
northline_discover_copy, northline_saved_copy, northline_account_copy {
    color: var(--text-secondary); font-size: 14px; margin-top: 8px;
}
"""

if __name__ == "__main__":
    run(start_screen=trip, theme=theme)

