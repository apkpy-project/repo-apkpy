"""Typed local notes with ApkPy 1.3.0 Data Core."""

from apkpy_lib import (
    Screen, Theme, button, db, inputs, label, lifecycle, run,
    virtual_collection,
)


notes = db.model(
    "notes",
    fields={
        "id": db.integer(primary_key=True, auto_increment=True),
        "title": db.text(required=True, max_length=120),
        "favorite": db.boolean(default=False),
        "updated_at": db.datetime(default=db.now()),
    },
    indexes=[db.index("idx_notes_favorite_updated", ["favorite", "updated_at"])],
)

migration_1_2 = db.migration(
    1,
    2,
    operations=[
        db.add_column(notes, "favorite", db.boolean(default=False)),
        db.create_index(
            notes,
            "idx_notes_favorite_updated",
            ["favorite", "updated_at"],
        ),
    ],
)

schema = db.schema(
    "notes_example",
    version=2,
    models=[notes],
    migrations=[migration_1_2],
)

home = Screen(id="home", scroll=True)
label("DATA CORE / 1.3.0", id="kicker", screen=home)
label("Notes that survive the screen.", id="title", screen=home)

title_input = inputs("Write a note title", id="note_title", screen=home)
status = label("Opening the database...", id="status", screen=home)


def failed(message):
    feed.finish_load()
    status.set_value("Database error · " + str(message))


def loaded(rows):
    feed.set_items(rows, has_more=False)
    status.set_value(str(len(rows)) + " notes stored locally")


def load_notes():
    notes.find(
        order_by=[db.desc("updated_at")],
        limit=100,
        on_result=loaded,
        on_error=failed,
    )


def created(note_id):
    title_input.set_value("")
    status.set_value("Saved note #" + str(note_id))
    load_notes()


def create_note():
    title = title_input.get_value()
    if title == "":
        status.set_value("Write a title first")
        return

    notes.insert(
        {"title": title, "favorite": False},
        on_result=created,
        on_error=failed,
    )


button("SAVE NOTE", command=create_note, screen=home)

feed = virtual_collection(
    [],
    template={
        "title": "{title}",
        "subtitle": "Stored in native SQLite",
        "meta": "#{id}",
    },
    on_refresh=load_notes,
    id="notes_feed",
    screen=home,
)

lifecycle(home, on_mount=load_notes)

style = """
home {
    background-color: var(--background);
    padding: 22px;
    gap: 12px;
}
kicker { color: var(--secondary); font-size: 11px; font-weight: bold; }
title { color: var(--text); font-size: 28px; font-weight: bold; margin-bottom: 8px; }
note_title {
    background-color: var(--surface); color: var(--text);
    border-color: var(--border); border-radius: 14px; padding: 14px;
}
button {
    background-color: var(--primary); color: var(--on-primary);
    border-radius: 14px; padding: 14px;
}
status { color: var(--secondary); font-size: 12px; }
notes_feed {
    height: 430px; background-color: var(--background);
    item-background-color: var(--surface); title-color: var(--text);
    subtitle-color: var(--text-secondary); meta-color: var(--secondary);
    item-border-color: var(--border);
}
"""

run(
    start_screen=home,
    theme=Theme(
        mode="dark",
        primary="#6D5DFB",
        secondary="#50E3C2",
        background="#090B10",
        surface="#151922",
        text="#F7F8FA",
        text_secondary="#9EA8BA",
        border="#2A3140",
    ),
)
