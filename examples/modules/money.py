"""Money, out of the screen file.

A helper module holds functions and constants. Screens, themes and widgets
stay in writehere.py, where ApkPy reads them in the order they appear.
"""

CURRENCY = "EUR"
VAT = 23


def euros(cents):
    """1999 -> "EUR 19.99". `cents` arrives as a number, not as text."""
    whole = cents / 100
    return CURRENCY + " " + str(round(whole, 2))


def with_vat(cents):
    return cents + cents * VAT / 100


def line(name, cents):
    return name + " - " + euros(cents)
