"""Sorting with key= - a scoreboard.

sorted(players, key=lambda p: p["score"], reverse=True) puts the best score
first, and 10 comes before 9 because a score stays a number. By name sorts
with key=lambda p: p["name"].lower(), so "ana" and "Rui" sit where a person
would look for them. max(players, key=...) finds who is leading.

Needs ApkPy 1.14.2.
"""

from apkpy_lib import *

players = [
    {"name": "Rui", "score": 12, "joined": 1},
    {"name": "ana", "score": 9, "joined": 2},
    {"name": "Eva", "score": 10, "joined": 3},
]
order = "Score"

home = Screen(id="home", scroll=True)

label("Scoreboard", id="title", screen=home)
label("Sorted with key=: by score, by name, or in the order they joined.", id="lead", screen=home)

add_card = container(id="add_card", screen=home)
who = inputs("Name", id="who", parent=add_card)
points = inputs("Score", id="points", parent=add_card)
message = label("", id="message", parent=add_card)
add_actions = container(id="add_actions", parent=add_card)

board_card = container(id="board_card", screen=home)
leader = label("", id="leader", parent=board_card)
board = label("", id="board", parent=board_card)


def ordered():
    if order == "Name":
        return sorted(players, key=lambda p: p["name"].lower())
    if order == "Joined":
        return sorted(players, key=lambda p: p["joined"])
    return sorted(players, key=lambda p: p["score"], reverse=True)


def refresh():
    rows = [f"{p['name']}   {p['score']}" for p in ordered()]
    board.set_value("\n".join(rows))
    top = max(players, key=lambda p: p["score"])
    leader.set_value(f"{top['name']} is leading with {top['score']}")


def add():
    name = who.get_value().strip()
    typed = points.get_value().strip()
    if name == "" or not typed.isdigit():
        message.set_value("Type a name and a whole number.")
        return
    players.append({"name": name, "score": int(typed), "joined": len(players) + 1})
    message.set_value("")
    who.set_value("")
    points.set_value("")
    refresh()


def reorder(choice):
    global order
    order = choice
    refresh()


button("Add", id="add", command=add, parent=add_actions)
segmented(["Score", "Name", "Joined"], id="sort_by", on_change=reorder, parent=board_card)

lifecycle(home, on_mount=refresh)

theme = Theme(primary="#2E6A4F")

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
add_card, board_card {
    background-color: var(--surface);
    border-radius: 18px;
    padding: 18px;
    gap: 8px;
}
who, points {
    background-color: var(--background);
    border-radius: 14px;
    border-width: 0px;
    padding: 14px 16px;
    font-size: 16px;
}
message {
    color: var(--error);
    font-size: 14px;
}
add_actions {
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    gap: 8px;
}
add {
    border-radius: 24px;
    min-height: 48px;
    padding: 0px 20px;
}
leader {
    color: var(--text);
    font-size: 15px;
    font-weight: bold;
}
board {
    color: var(--text);
    font-size: 18px;
    line-height: 1.6;
}
"""

run(start_screen=home, theme=theme)
