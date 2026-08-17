from apkpy_lib import Screen, button, inputs, label, list_view, run, state


NOTES = [
    {
        "title": f"Note {index:03d}",
        "subtitle": "Same deterministic row in every framework",
        "meta": "Favorite" if index % 5 == 0 else "Standard",
    }
    for index in range(1, 101)
]

home = Screen(id="home", scroll=True)
query_state = state("", id="benchmark_query")
favorites_state = state(False, id="benchmark_favorites")
next_state = state(101, id="benchmark_next")


def visible_notes():
    query = query_state.get().strip().lower()
    return [
        item for item in NOTES
        if (not favorites_state.get() or item["meta"] == "Favorite")
        and (not query or query in item["title"].lower()
             or query in item["subtitle"].lower())
    ]


def refresh_rows():
    notes.set_items(visible_notes())
    status.set_value(f"Showing {len(visible_notes())} notes")


def search_changed(value):
    query_state.set(value)
    refresh_rows()


def toggle_favorites(value=None):
    favorites_state.toggle()
    refresh_rows()


def add_note():
    index = next_state.get()
    NOTES.append({
        "title": f"Note {index:03d}",
        "subtitle": "Added from the shared benchmark action",
        "meta": "Standard",
    })
    next_state.increment()
    refresh_rows()


label("BENCHMARK NOTES / 0.1", id="kicker", screen=home)
label("One small app. Four native packaging paths.", id="title", screen=home)
label(
    "Search 100 notes, add a row, toggle favorites and scroll the same dataset.",
    id="copy", screen=home,
)
query = inputs(
    "Search notes", id="search", type="search", screen=home,
    on_change=search_changed,
)
button("FAVORITES ONLY", id="favorites", icon="star", screen=home,
        command=toggle_favorites)
button("ADD NOTE", id="add", icon="add", screen=home, command=add_note)
status = label("Showing 100 notes", id="status", screen=home)
notes = list_view(NOTES, id="notes", screen=home, rich=True)

style = """
home { background-color: #090B10; padding: 18px; }
kicker { color: #50E3C2; font-size: 11px; font-weight: bold; margin-bottom: 8px; }
title { color: #F5F7FB; font-size: 26px; font-weight: bold; margin-bottom: 8px; }
copy, status { color: #9EA8BA; font-size: 13px; margin-bottom: 12px; }
search { background-color: #10141C; color: #F5F7FB; placeholder-color: #9EA8BA; border-color: #30394A; border-radius: 14px; min-height: 48px; margin-bottom: 10px; }
favorites, add { border-radius: 14px; min-height: 48px; font-weight: bold; margin-bottom: 10px; }
favorites { background-color: #1D5660; color: #FFFFFF; }
add { background-color: #7C5CFF; color: #24164A; }
notes { height: 560px; background-color: #090B10; color: #F5F7FB; item-background-color: #151922; title-color: #F5F7FB; subtitle-color: #9EA8BA; meta-color: #50E3C2; item-border-color: #30394A; }
"""

run(start_screen=home)
