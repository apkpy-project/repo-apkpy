"""A checkout screen whose money lives in another file.

Run it:  python writehere.py      (money.py has to sit beside it)
Build it: apkpy run

`import money` is merged into the application before anything is translated,
so `money.euros(1999)` becomes a normal method in the generated Activity. The
Previewer needs nothing special: next to the script, it is the import Python
already does.
"""

import money

from apkpy_lib import (
    Screen, Theme, button, container, device, label, run, toast,
)

device("Pixel 9")

theme = Theme(
    mode="light",
    primary="#16324F",
    secondary="#C0431F",
    background="#F3F0E9",
    surface="#FFFFFF",
    text="#17212B",
    text_secondary="#5A6670",
    border="#DED9CF",
    radius=18,
    spacing=14,
)

home = Screen(id="home", scroll=True)

label("YOUR BASKET", id="kicker", screen=home)
label("Two things and the tax", id="headline", screen=home)

basket = container(id="basket", screen=home)
first = label("", id="first", parent=basket)
second = label("", id="second", parent=basket)

total_card = container(id="total_card", screen=home)
label("TOTAL WITH VAT", id="total_kicker", parent=total_card)
total = label("", id="total", parent=total_card)


def pay():
    toast("Nothing is really for sale here")


button("Pay", id="pay", icon="arrow_forward", variant="filled", screen=home,
       command=pay)

label("money.py holds the arithmetic. This file holds the screen.",
      id="footnote", screen=home)

first.set_value(money.line("Filter coffee", 450))
second.set_value(money.line("Ceramic mug", 1999))
total.set_value(money.euros(money.with_vat(2449)))

style = """
kicker { color: var(--secondary); font-size: 12px; margin-top: 24px; }
headline { font-size: 26px; font-weight: 700; color: var(--text); margin-top: 6px; }
basket {
    background-color: var(--surface); border-radius: 18px;
    padding: 18px; margin-top: 16px;
}
first { color: var(--text); font-size: 15px; }
second { color: var(--text); font-size: 15px; margin-top: 8px; }
total_card {
    background-color: var(--surface); border-radius: 18px;
    border-width: 2px; border-color: var(--primary);
    padding: 20px; margin-top: 16px;
}
total_kicker { color: var(--text-secondary); font-size: 11px; }
total { color: var(--primary); font-size: 30px; font-weight: 700; margin-top: 6px; }
pay { margin-top: 16px; }
footnote { color: var(--text-secondary); font-size: 12px; margin-top: 18px; }
"""

if __name__ == "__main__":
    run(start_screen=home, theme=theme)
