"""Classes - objects that keep their own values.

A month's budget. Entry is the parent class, and Expense and Income each say
how they move the total. Budget keeps the entries in a list, adds them up and
writes itself out with __str__.

Objects behave as in Python: every name for an object sees the same changes,
the method that runs is the one of the object's class, and super() reaches
the parent. A class can also live in a module next to this file.

Needs ApkPy 1.14.1.
"""

from apkpy_lib import *


class Entry:
    def __init__(self, name, amount):
        self.name = name
        self.amount = amount

    def signed(self):
        return self.amount

    def line(self):
        return f"{self.name}   {self.signed():.2f}"


class Expense(Entry):
    def signed(self):
        return -self.amount


class Income(Entry):
    pass


class Budget:
    def __init__(self, month):
        self.month = month
        self.entries = []

    def add(self, entry):
        self.entries.append(entry)

    def undo(self):
        if self.entries:
            self.entries.pop()

    def total(self):
        result = 0.0
        for entry in self.entries:
            result += entry.signed()
        return result

    def __str__(self):
        return f"{self.total():.2f}"


budget = Budget("October")

home = Screen(id="home", scroll=True)

label("Budget", id="title", screen=home)
label("Each entry is an object of its own class.", id="lead", screen=home)

total_card = container(id="total_card", screen=home)
label("OCTOBER", id="total_kicker", parent=total_card)
total = label("0.00", id="total", parent=total_card)
count = label("No entries yet", id="count", parent=total_card)

add_card = container(id="add_card", screen=home)
name = inputs("What was it?", id="name", parent=add_card)
amount = inputs("How much", id="amount", parent=add_card)
add_actions = container(id="add_actions", parent=add_card)

list_card = container(id="list_card", screen=home)
label("ENTRIES", id="list_kicker", parent=list_card)
lines = label("Nothing yet.", id="lines", parent=list_card)


def read_amount():
    try:
        return float(amount.get_value())
    except ValueError:
        return 0.0


def refresh():
    shown = [entry.line() for entry in budget.entries]
    lines.set_value("\n".join(shown) or "Nothing yet.")
    total.set_value(str(budget))
    count.set_value(f"{len(budget.entries)} entries")
    name.set_value("")
    amount.set_value("")


def spent():
    budget.add(Expense(name.get_value() or "Something", read_amount()))
    refresh()


def earned():
    budget.add(Income(name.get_value() or "Something", read_amount()))
    refresh()


def undo():
    budget.undo()
    refresh()


button("Spent", id="spent", command=spent, parent=add_actions)
button("Earned", id="earned", variant="outlined", command=earned, parent=add_actions)
button("Undo last", id="undo", variant="text", command=undo, parent=list_card)

theme = Theme(primary="#257C39")

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
total_card, add_card, list_card {
    background-color: var(--surface);
    border-radius: 18px;
    padding: 18px;
    gap: 6px;
}
total_kicker, list_kicker {
    color: var(--text-secondary);
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.2px;
}
total {
    color: var(--primary);
    font-size: 44px;
    font-weight: bold;
}
count {
    color: var(--text-secondary);
    font-size: 14px;
}
name, amount {
    background-color: var(--background);
    border-radius: 14px;
    border-width: 0px;
    padding: 14px 16px;
    font-size: 16px;
}
add_actions {
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    gap: 8px;
    margin-top: 6px;
}
spent, earned {
    border-radius: 24px;
    min-height: 48px;
    padding: 0px 24px;
}
lines {
    color: var(--text);
    font-size: 16px;
    line-height: 1.6;
}
"""

run(start_screen=home, theme=theme)
