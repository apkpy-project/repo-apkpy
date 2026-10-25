"""Dataclasses and errors of your own - a pantry list.

Item is a @dataclass: its __init__, its repr and its == are written from the
fields. Adding an item checks what was typed and raises one of the app's own
errors; the screen shows the message of whichever one it caught.

PantryError is the family, so one except catches NoName and BadAmount alike,
and NoName has a message of its own for raise NoName().

Needs ApkPy 1.14.1.
"""

from dataclasses import dataclass, field
from apkpy_lib import *


class PantryError(Exception):
    pass


class NoName(PantryError):
    def __init__(self, message="Type what it is first."):
        super().__init__(message)


class BadAmount(PantryError):
    pass


@dataclass
class Item:
    name: str
    qty: int = 1
    added: list = field(default_factory=list)

    def line(self):
        return f"{self.qty} x {self.name}"


pantry = []

home = Screen(id="home", scroll=True)

label("Pantry", id="title", screen=home)
label("Each line is a dataclass. Wrong input raises an error of the app's own.", id="lead", screen=home)

add_card = container(id="add_card", screen=home)
name = inputs("What is it?", id="name", parent=add_card)
qty = inputs("How many (1 if empty)", id="qty", parent=add_card)
message = label("", id="message", parent=add_card)
add_actions = container(id="add_actions", parent=add_card)

list_card = container(id="list_card", screen=home)
label("IN THE PANTRY", id="list_kicker", parent=list_card)
lines = label("Nothing yet.", id="lines", parent=list_card)


def read_item():
    text = name.get_value().strip().lower()
    if text == "":
        raise NoName()
    typed = qty.get_value().strip() or "1"
    try:
        amount = int(typed)
    except ValueError:
        raise BadAmount(f"{typed} is not a whole number.")
    if amount < 1:
        raise BadAmount("The amount has to be 1 or more.")
    return Item(text, amount)


def refresh():
    shown = [item.line() for item in pantry]
    lines.set_value("\n".join(shown) or "Nothing yet.")


def add():
    try:
        item = read_item()
    except PantryError as e:
        message.set_value(str(e))
        return
    found = False
    for kept in pantry:
        if kept.name == item.name:
            kept.qty += item.qty
            kept.added.append(item.qty)
            found = True
    if not found:
        item.added.append(item.qty)
        pantry.append(item)
    message.set_value("")
    name.set_value("")
    qty.set_value("")
    refresh()


def use_one():
    message.set_value("")
    if pantry:
        last = pantry[-1]
        last.qty -= 1
        if last.qty == 0:
            pantry.pop()
    refresh()


button("Add", id="add", command=add, parent=add_actions)
button("Use one", id="use", variant="outlined", command=use_one, parent=add_actions)

theme = Theme(primary="#A65A2E")

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
add_card, list_card {
    background-color: var(--surface);
    border-radius: 18px;
    padding: 18px;
    gap: 8px;
}
name, qty {
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
add, use {
    border-radius: 24px;
    min-height: 48px;
    padding: 0px 20px;
}
list_kicker {
    color: var(--text-secondary);
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.2px;
}
lines {
    color: var(--text);
    font-size: 16px;
    line-height: 1.6;
}
"""

run(start_screen=home, theme=theme)
