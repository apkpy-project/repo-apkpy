# -*- coding: utf-8 -*-
"""A label that is given more lines takes more room.

A container with an ``align-self``, a ``position`` or a ``flex-grow`` among
its children places them itself, as ApkpyLayout does on the phone. In the
Previewer it measured them when the screen was drawn and never again:
``set_value()`` with two lines where there had been one drew the second line
over whatever came next, and the card kept the height it had.
"""

import unittest

from test_real_screens import Previewed

BODY = (
    'home = Screen(id="home")\n'
    'card = container(id="card", screen=home)\n'
    'label("HISTORY", id="kicker", parent=card)\n'
    'history = label("one line", id="history", parent=card)\n'
    'clear = button("Clear", id="clear", variant="text", parent=card)\n'
    'after = label("after the card", id="after", screen=home)\n'
)
CARD = 'card { background-color: #EEEEEE; border-radius: 18px; padding: 18px; gap: 8px; }\n'
THREE = "one line\nand a second\nand a third"


def _top(widget):
    return widget.winfo_rooty()


class ALabelGrows(unittest.TestCase):

    def _grows(self, css):
        with Previewed(BODY, css) as shown:
            history, clear, after = (shown.widget(name) for name in ("history", "clear", "after"))
            line = history.winfo_height()
            was = {"clear": _top(clear), "after": _top(after)}
            shown.ns["history"].set_value(THREE)
            shown.settle()
            grown = history.winfo_height() - line
            # Three lines where there was one.
            self.assertGreater(history.winfo_height(), 2.4 * line)
            # What comes after it, inside the card and below it, moved down
            # by what the label took -- nothing is drawn over anything.
            self.assertGreaterEqual(_top(clear), _top(history) + history.winfo_height())
            self.assertAlmostEqual(_top(clear) - was["clear"], grown, delta=3)
            self.assertAlmostEqual(_top(after) - was["after"], grown, delta=3)
            # And it gives the room back.
            shown.ns["history"].set_value("one line")
            shown.settle()
            self.assertAlmostEqual(history.winfo_height(), line, delta=1)
            self.assertAlmostEqual(_top(after), was["after"], delta=3)

    def test_in_a_card_that_places_its_children_itself(self):
        self._grows(CARD + 'clear { align-self: flex-start; }\n')

    def test_in_a_plain_card(self):
        self._grows(CARD)


if __name__ == "__main__":
    unittest.main()
