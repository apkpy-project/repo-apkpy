"""Trips - a sheet of filters over a list.

The Filters button opens a bottom sheet that holds components: a segmented
button, chips, a number field with help under it and two buttons in a row.
Apply reads them, changes the line over the list and closes the sheet; the
sheet also closes when it is dragged down, when the screen behind it is
tapped and on Back. What was chosen is still there the next time it opens.

apply() and reset() are written above the sheet because its buttons name
them -- and apply() closes a sheet that is created further down.

Needs ApkPy 1.12.0.
"""

from apkpy_lib import *

home = Screen("home")

label("Trips", id="title", screen=home)
shown = label("Newest first, any kind", id="shown", screen=home)

TRIPS = [
    {"title": "Lisbon", "subtitle": "City · 3 nights"},
    {"title": "Comporta", "subtitle": "Beach · 5 nights"},
    {"title": "Gerês", "subtitle": "Mountain · 2 nights"},
    {"title": "Costa Vicentina", "subtitle": "Road trip · 6 nights"},
]
list_view(TRIPS, id="trips", screen=home)


def apply():
    if budget.get_value() == "0":
        budget.set_error("Give a price above zero")
        return
    shown.set_value(order.get_value() + " first, up to " + budget.get_value())
    filters.close()


def reset():
    order.set_value("Newest")
    budget.set_value("")


def closed():
    toast("Filters closed")


filters = bottom_sheet("Filters", "Choose how the list is sorted and what it shows.",
                       id="filters", screen=home, on_close=closed)
label("Sort by", id="sort_by", parent=filters)
order = segmented(["Newest", "Price", "Rating"], selected="Newest", parent=filters)
label("Kind", id="kind", parent=filters)
kinds = chips(["City", "Beach", "Mountain", "Road trip"], multiple=True,
              selected=["City"], parent=filters)
budget = inputs("Max price a night", id="budget", type="number",
                help="In euros. Leave it empty for any price.", parent=filters)
actions = container(id="actions", parent=filters)
button("Reset", id="reset", variant="text", command=reset, parent=actions)
button("Apply", id="apply", command=apply, parent=actions)

button("Filters", id="open", icon="tune", command=filters.open, screen=home)

style = """
title { font-size: 24px; font-weight: bold; }
shown { color: #49454F; }
sort_by, kind { font-size: 14px; font-weight: bold; }
actions { display: flex; flex-direction: row; justify-content: flex-end; gap: 8px; padding: 0px; }
"""

run(home, theme=Theme())
