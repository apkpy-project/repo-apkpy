# ============================================================
#  ApkPy Example 15 — For Loops (lists, range, db rows, API)
# ============================================================
#  What it shows:
#    • for x in ["a", "b"]:     -> iterate a list
#    • for i in range(n):       -> classic counter
#    • for row in db.query():   -> iterate database rows  *
#    • for item in resp:        -> iterate an API response *
#
#  (*) row["column"] reads each field — a real dict in the
#  Previewer, safe JSON access in the generated Java.
#  Loops run identically on both platforms; non-array JSON
#  simply runs the loop zero times (never crashes).
#
#  Preview : python 15_for_loops.py
#  Android : apkpy build
# ============================================================

from apkpy_lib import Screen, label, button, list_view, toast, db, https, run

home = Screen(id="home", scroll=True)

label("For Loops 🔁", id="title", screen=home)
label("Lists, range, db rows and API items", id="hint", screen=home)

status = label("Press a button.", id="status", screen=home)

fruits_list = list_view([], id="fruits_list", screen=home)

db.execute("CREATE TABLE IF NOT EXISTS fruits (name TEXT)")

def seed():
    # 1) Loop over a list literal -> one INSERT per item
    db.execute("DELETE FROM fruits")
    for fruta in ["Apple", "Pear", "Grape", "Mango"]:
        db.execute("INSERT INTO fruits (name) VALUES (?)", [fruta])
    refresh()
    toast("4 fruits inserted!")

def refresh():
    # 2) Loop over database rows -> row["column"] reads each field
    rows = db.query("SELECT name FROM fruits")
    fruits_list.set_items(rows, title="name")
    for row in rows:
        status.set_value(f"Last row seen: {row['name']}")

def count():
    # 3) Classic counter
    for i in range(5):
        status.set_value(f"Counted up to {i}")
    toast("Counted 0..4")

def from_api(ok, resp):
    # 4) Loop over an API response (JSON array)
    if ok:
        for post in resp:
            status.set_value(f"API title: {post['title']}")
        toast("Looped 100 posts!")
    else:
        toast("Request failed.")

def load_api():
    status.set_value("Loading...")
    https.get("https://jsonplaceholder.typicode.com/posts", on_response=from_api)

button("SEED DB (list loop)",  id="btn_seed",  screen=home, command=seed)
button("COUNT (range loop)",   id="btn_count", screen=home, command=count)
button("API (response loop)",  id="btn_api",   screen=home, command=load_api)

# Module-level loop -> runs on app start
for msg in ["App started"]:
    status.set_value(msg)

refresh()

style = """
home {
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
status {
    color: #38BDF8;
    font-size: 15px;
    margin-top: 8px;
}
fruits_list {
    background-color: #1E293B;
    color: #F8FAFC;
    border-color: #334155;
    margin-top: 12px;
}
btn_seed {
    color: #F8FAFC;
    background-color: #10B981;
    border-radius: 10px;
    font-weight: bold;
    padding: 12px;
    margin-top: 12px;
    pressed-color: #047857;
}
btn_count {
    color: #F8FAFC;
    background-color: #6366F1;
    border-radius: 10px;
    font-weight: bold;
    padding: 12px;
    pressed-color: #4338CA;
}
btn_api {
    color: #F8FAFC;
    background-color: #F59E0B;
    border-radius: 10px;
    font-weight: bold;
    padding: 12px;
    pressed-color: #B45309;
}
"""

if __name__ == "__main__":
    run(start_screen=home)
