# ============================================================
#  ApkPy Example 14 — Notes App (SQLite → list_view)
# ============================================================
#  What it shows:
#    • my_list.set_items(json_rows, title=..., subtitle=...)
#      -> feeds a list_view straight from db.query() JSON
#    • db.execute(sql, [params])  -> safe INSERT (no SQL injection)
#    • Module-level refresh()     -> the list loads on app start
#
#  This is the "data -> UI" pattern every real app needs:
#  fetch rows, show them in a list, keep them in sync.
#  set_items also accepts JSON from https responses — feeding a
#  list from Supabase/Firebase works exactly the same way.
#
#  Preview : python 14_db_notes_list.py
#  Android : apkpy build
# ============================================================

from apkpy_lib import Screen, label, button, inputs, list_view, toast, db, run

notes = Screen(id="notes", scroll=True)

label("My Notes 🗒️", id="title", screen=notes)
label("SQLite → list_view, fully dynamic", id="hint", screen=notes)

note_in = inputs("Write a note...", id="note_in", screen=notes)

notes_list = list_view([], id="notes_list", screen=notes)

db.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, created TEXT)")

def refresh():
    rows = db.query("SELECT content, created FROM notes ORDER BY id DESC")
    # The new bit: the JSON string from db.query goes straight into the list.
    # title= / subtitle= pick which field of each row to display.
    notes_list.set_items(rows, title="content", subtitle="created")

def add_note():
    texto = note_in.get_value()
    if texto:
        # `?` placeholder = safe against SQL injection and apostrophes
        db.execute("INSERT INTO notes (content, created) VALUES (?, datetime('now'))", [texto])
        note_in.set_value("")
        refresh()
        toast("Note saved! 🗒️")
    else:
        toast("Write something first.")

def clear_all():
    db.execute("DELETE FROM notes")
    refresh()
    toast("All notes deleted.")

button("ADD NOTE",  id="btn_add",     screen=notes, command=add_note)
button("REFRESH",   id="btn_refresh", screen=notes, command=refresh)
button("CLEAR ALL", id="btn_clear",   screen=notes, command=clear_all)

# Module-level call -> runs in onCreate on Android: the list is filled on launch
refresh()

style = """
notes {
    background-color: #0F172A;
}
title {
    color: #F8FAFC;
    font-size: 22px;
    font-weight: bold;
    margin-top: 20px;
}
hint {
    color: #94A3B8;
    font-size: 13px;
}
note_in {
    color: #F8FAFC;
    background-color: #1E293B;
    border-radius: 10px;
    padding: 12px;
    margin-top: 12px;
}
notes_list {
    background-color: #1E293B;
    color: #F8FAFC;
    border-color: #334155;
    margin-top: 12px;
}
btn_add {
    color: #F8FAFC;
    background-color: #10B981;
    border-radius: 10px;
    font-weight: bold;
    padding: 12px;
    margin-top: 12px;
    pressed-color: #047857;
}
btn_refresh {
    color: #F8FAFC;
    background-color: #6366F1;
    border-radius: 10px;
    font-weight: bold;
    padding: 12px;
    pressed-color: #4338CA;
}
btn_clear {
    color: #F8FAFC;
    background-color: #EF4444;
    border-radius: 10px;
    font-weight: bold;
    padding: 12px;
    pressed-color: #B91C1C;
}
"""

if __name__ == "__main__":
    run(start_screen=notes)
