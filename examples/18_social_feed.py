"""Production feed with pagination, refresh and keyed updates."""

from apkpy_lib import (
    Screen, Theme, app_bar, button, container, device, label, run, toast,
    virtual_collection,
)


PAGE_ONE = [
    {"id": "note-1", "image": "https://picsum.photos/seed/feed-amber/160/160",
     "author": "Amber Reed",
     "message": "A stable key lets this row change without moving the reader.",
     "time": "2m", "tag": "DESIGN"},
    {"id": "note-2", "image": "https://picsum.photos/seed/feed-jonah/160/160",
     "author": "Jonah Bell",
     "message": "The next page is requested before the final row is visible.",
     "time": "8m", "tag": "SYSTEM"},
    {"id": "note-3", "image": "https://picsum.photos/seed/feed-iman/160/160",
     "author": "Iman Fox",
     "message": "Refresh replaces the dataset and clears pending snapshots.",
     "time": "15m", "tag": "API"},
    {"id": "note-4", "image": "https://picsum.photos/seed/feed-oren/160/160",
     "author": "Oren Clay",
     "message": "Fast scrolling cannot start the same page request twice.",
     "time": "21m", "tag": "RELEASE"},
]

PAGE_TWO = [
    {"id": "note-5", "image": "https://picsum.photos/seed/feed-nell/160/160",
     "author": "Nell Shore",
     "message": "This row arrived without rebuilding the existing page.",
     "time": "34m", "tag": "PAGE 2"},
    {"id": "note-6", "image": "https://picsum.photos/seed/feed-rio/160/160",
     "author": "Rio Moss",
     "message": "has_more=False prevents another request at the end.",
     "time": "41m", "tag": "END"},
]

LIVE_NOTE = [
    {"id": "note-live", "image": "https://picsum.photos/seed/feed-live/160/160",
     "author": "Live desk",
     "message": "A new note arrived above the current reading position.",
     "time": "now", "tag": "LIVE"},
]

home = Screen(id="home", scroll=True)
app_bar("Signal Feed", screen=home)


def open_note(item):
    toast(item["author"] + ": " + item["message"])


def load_more():
    feed.append_items(PAGE_TWO, has_more=False)
    status.set_value("Page 2 inserted - no more results")


def reload_feed():
    feed.set_items(PAGE_ONE, has_more=True)
    status.set_value("Refresh complete - page 1 restored")
    toast("Feed refreshed")


def add_live_note():
    feed.remove_item("note-live")
    feed.prepend_items(LIVE_NOTE)
    status.set_value("Live note prepended without moving the current row")
    toast("Scroll upward to see the new live note")


label("PRODUCTION FEED", id="kicker", screen=home)
label("A feed that keeps its place.", id="title", screen=home)
label(
    "Pagination, refresh and live inserts share one virtualized collection.",
    id="copy",
    screen=home,
)
status = label("Page 1 ready", id="status", screen=home)

feed = virtual_collection(
    PAGE_ONE,
    template={
        "image": "{image}", "title": "{author}", "subtitle": "{message}",
        "meta": "{time}", "badge": "{tag}",
    },
    id="feed",
    item_height=122,
    buffer=3,
    on_click=open_note,
    on_end_reached=load_more,
    on_refresh=reload_feed,
    prefetch=3,
    screen=home,
)

actions = container(id="actions", screen=home)
button("ADD LIVE NOTE", command=add_live_note, parent=actions)
button("REFRESH", variant="outlined", command=feed.refresh, parent=actions)

theme = Theme(
    mode="dark", primary="#7457F6", secondary="#31D4C2",
    background="#090B0E", surface="#15181D", text="#F5F7FA",
    text_secondary="#99A4B2", border="#2D333C", radius=18, spacing=14,
)

style = """
home { background-color: var(--background); padding: 18px; }
kicker { color: var(--secondary); font-size: 11px; font-weight: bold; }
title { color: var(--text); font-size: 26px; font-weight: bold; }
copy { color: var(--text-secondary); font-size: 13px; margin-bottom: 8px; }
status { color: var(--secondary); font-size: 12px; font-weight: bold; }
feed {
    height: 530px; item-background-color: var(--surface);
    item-border-color: var(--border); title-color: var(--text);
    subtitle-color: var(--text-secondary); meta-color: var(--secondary);
    badge-background-color: var(--primary); badge-color: #FFFFFF;
}
actions { display: flex; flex-direction: row; gap: 10px; margin-top: 12px; }
button { flex-grow: 1; border-radius: 15px; min-height: 46px; }
"""

device("Pixel 9")
run(start_screen=home, theme=theme)
