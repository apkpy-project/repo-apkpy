"""Saving with json - a reading list kept in a file.

json.dumps(books, indent=2) turns the list into text, files.write() keeps it
as books.json, and json.loads(files.read("books.json")) brings it back the
next time the app opens. The same text is in the box at the bottom: change it
and press Save, and a typo comes back as Python's own message, with the line
and the column.

Needs ApkPy 1.14.2.
"""

import json

from apkpy_lib import *

FIRST = [
    {"title": "Dune", "pages": 412},
    {"title": "Emma", "pages": 474},
]
books = []

home = Screen(id="home", scroll=True)

label("Reading list", id="title", screen=home)
label("Kept in books.json with json.dumps() and read back with json.loads().", id="lead", screen=home)

add_card = container(id="add_card", screen=home)
book = inputs("Title", id="book", parent=add_card)
pages = inputs("Pages", id="pages", type="number", parent=add_card)
add_message = label("", id="add_message", parent=add_card)
add_actions = container(id="add_actions", parent=add_card)

list_card = container(id="list_card", screen=home)
summary = label("", id="summary", parent=list_card)
shelf = label("", id="shelf", parent=list_card)

file_card = container(id="file_card", screen=home)
label("books.json", id="file_name", parent=file_card)
editor = inputs("", id="editor", type="textarea", parent=file_card)
file_message = label("", id="file_message", parent=file_card)
file_actions = container(id="file_actions", parent=file_card)


def keep():
    files.write("books.json", json.dumps(books, indent=2))


def refresh():
    total = sum([int(b["pages"]) for b in books])
    shelf.set_value("\n".join([f"{b['title']}   {b['pages']} pages" for b in books]))
    summary.set_value(f"{len(books)} books, {total} pages")
    editor.set_value(json.dumps(books, indent=2))


def load():
    global books
    text = files.read("books.json")
    if text == "":
        text = json.dumps(FIRST)
    books = json.loads(text)
    refresh()


def add():
    title = book.get_value().strip()
    typed = pages.get_value().strip()
    if title == "" or not typed.isdigit():
        add_message.set_value("Type a title and the number of pages.")
        return
    books.append({"title": title, "pages": int(typed)})
    keep()
    add_message.set_value("")
    book.set_value("")
    pages.set_value("")
    refresh()


def save():
    global books
    try:
        typed = json.loads(editor.get_value())
    except json.JSONDecodeError as e:
        file_message.set_value(str(e))
        return
    if not isinstance(typed, list):
        file_message.set_value("books.json holds a list, between [ and ].")
        return
    books = typed
    file_message.set_value("")
    keep()
    refresh()


button("Add", id="add", command=add, parent=add_actions)
button("Save", id="save", command=save, parent=file_actions)

lifecycle(home, on_mount=load)

theme = Theme(primary="#7A4E2D")

style = """
home {
    background-color: var(--background);
    padding: 24px;
    gap: 14px;
}
title {
    color: var(--text);
    font-size: 28px;
    font-weight: bold;
}
lead {
    color: var(--text-secondary);
    font-size: 15px;
}
add_card, list_card, file_card {
    background-color: var(--surface);
    border-radius: 18px;
    padding: 18px;
    gap: 8px;
}
book, pages {
    background-color: var(--background);
    border-radius: 14px;
    border-width: 0px;
    padding: 14px 16px;
    font-size: 16px;
}
add_message, file_message {
    color: var(--error);
    font-size: 14px;
}
add_actions, file_actions {
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    gap: 8px;
}
add, save {
    border-radius: 24px;
    min-height: 48px;
    padding: 0px 20px;
}
summary {
    color: var(--text);
    font-size: 15px;
    font-weight: bold;
}
shelf {
    color: var(--text);
    font-size: 18px;
    line-height: 1.6;
}
file_name {
    color: var(--text-secondary);
    font-family: monospace;
    font-size: 13px;
}
editor {
    background-color: var(--background);
    border-radius: 14px;
    border-width: 0px;
    padding: 14px 16px;
    font-family: monospace;
    font-size: 14px;
    rows: 8;
    max-rows: 16;
}
"""

run(start_screen=home, theme=theme)
