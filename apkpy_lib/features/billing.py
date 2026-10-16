"""Google Play in-app purchases -- ``from apkpy_lib import billing``.

    billing.prices(["pro_unlock", "coins_100"], on_result=shown)
    billing.buy("pro_unlock", on_result=bought)
    billing.buy("coins_100", consumable=True, on_result=bought)

    billing.prices(["monthly"], kind="subscription", on_result=shown)
    billing.subscribe("monthly", on_result=bought)

    billing.owned(on_result=restored)

The desktop has no Play Store, so the Previewer runs a **make-believe shop**:
it invents a price for each id, shows a sheet that says plainly it is not real,
and remembers what was bought so ``owned()`` answers and a second ``buy()``
reports ``owned``. Nothing is charged and no account is touched.

What that buys you is the shape of the flow -- the sheet, the cancel, the
restore, the second purchase being refused -- without a Play Console account.
What it cannot tell you is whether your product ids are right, which only a
real build on a real track can.

The reason vocabulary lives in :mod:`apkpy_lib.core.features.billing` and is
imported by both runtimes.
"""

from __future__ import annotations

import json

from ..core.features.billing import REASONS, SUCCESS, normalise_kind

__all__ = ["BillingAPI", "billing", "REASONS"]

# Openly invented, and openly not a real currency amount.
_PRETEND_PRICE = "€4.99"
_PRETEND_SUB = "€2.99 / month"

_owned = {}          # id -> the row owned() will report
_counter = [1000]


class BillingAPI:
    """Selling something inside the app.

        def shown(ok, items):
            if ok:
                shop.set_items(items, title="title", subtitle="price")

        billing.prices(["pro_unlock"], on_result=shown)
        billing.buy("pro_unlock", on_result=bought)

    ``on_result`` receives ``(success, value)``. On success ``value`` is JSON;
    on failure it is one of the words in :data:`REASONS` -- including
    ``"pending"``, which is **not** a purchase: a slow payment method has
    started and nothing should be unlocked yet.

    Every completed purchase is acknowledged for you. Google refunds anything
    an app leaves unacknowledged for three days, so this is not optional and
    is deliberately not something you can forget to call. Pass
    ``consumable=True`` for something meant to be bought again, and it is
    consumed instead.
    """

    reasons = REASONS

    def prices(self, ids=None, on_result=None, kind=None):
        """Ask the store what these cost, in the person's own currency."""
        wanted = _as_list(ids)
        if not wanted:
            _report(on_result, False, "not_found")
            return
        subscription = normalise_kind(kind) == "subs"
        rows = [
            {
                "id": product,
                "title": _title(product),
                "description": "Pretend product, Previewer only",
                "price": _PRETEND_SUB if subscription else _PRETEND_PRICE,
            }
            for product in wanted
        ]
        _report(on_result, True, json.dumps(rows))

    def buy(self, product=None, on_result=None, consumable=False, kind=None):
        """Open the payment sheet for one product."""
        _purchase(str(product or ""), on_result, bool(consumable),
                  normalise_kind(kind) == "subs")

    def subscribe(self, product=None, on_result=None):
        """Open the payment sheet for a subscription."""
        _purchase(str(product or ""), on_result, False, True)

    def owned(self, on_result=None):
        """What this person has bought, as JSON, each row carrying a token."""
        _report(on_result, True, json.dumps(list(_owned.values())))

    def consume(self, product=None, on_result=None):
        """Use up a consumable so it can be bought again."""
        row = _owned.pop(str(product or ""), None)
        if row is None:
            _report(on_result, False, "not_owned")
        else:
            _report(on_result, True, json.dumps(row))


billing = BillingAPI()


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _title(product):
    return str(product).replace("_", " ").replace("-", " ").strip().title()


def _report(callback, ok, value):
    if not callback:
        return
    from ..ui import report_exception
    try:
        callback(ok, value)
    except Exception as exc:                       # pragma: no cover - user code
        report_exception(exc, context="billing callback")


def _row(product):
    _counter[0] += 1
    return {
        "id": product,
        # Named so nobody mistakes it for something a server could check.
        "token": "previewer-not-a-real-token-%d" % _counter[0],
        "order": "PREVIEWER.%d" % _counter[0],
        "time": "0",
    }


def _purchase(product, on_result, consumable, subscription):
    from .. import ui

    if not product:
        _report(on_result, False, "not_found")
        return
    if product in _owned and not consumable:
        # Play refuses a second purchase of something already owned, and an
        # app that has not handled that word will misbehave the same way here.
        _report(on_result, False, "owned")
        return

    app = getattr(ui, "_app", None)
    if app is None or getattr(app, "_instance", None) is None:
        # No window -- a unit test, or `apkpy build`. Answer rather than
        # opening one, and rather than pretending money changed hands.
        _report(on_result, False, "unavailable")
        return

    _sheet(ui, app, product, subscription, consumable, on_result)


def _sheet(ui, app, product, subscription, consumable, on_result):
    """A payment sheet that says what it is."""
    import tkinter as tk

    body = getattr(app, "body", None)
    root = getattr(app, "root", None)
    if body is None or root is None:
        _report(on_result, False, "unavailable")
        return

    tokens = ui.global_styles.get("__theme__", {})
    surface = tokens.get("surface_high") or tokens.get("surface", "#1C1B1F")
    on_surface = tokens.get("text", "#E6E1E5")
    muted = tokens.get("text_secondary", "#CAC4D0")
    primary = tokens.get("primary", "#D0BCFF")
    background = tokens.get("background", "#000000")
    scrim_colour = ui._mix_color(str(background or "#000000"), "#000000", 0.55)

    root.update_idletasks()
    host_w = max(1, body.winfo_width())
    host_h = max(1, body.winfo_height())

    scrim = tk.Frame(body, bg=scrim_colour)
    scrim.place(x=0, y=0, relwidth=1, relheight=1)

    height = 250
    panel = tk.Frame(body, bg=surface, highlightthickness=0)
    panel.place(x=0, y=host_h - height, width=host_w, height=height)

    state = {"done": False}

    def finish(ok, value):
        if state["done"]:
            return
        state["done"] = True
        for widget in (panel, scrim):
            try:
                widget.destroy()
            except Exception:
                pass
        _report(on_result, ok, value)

    tk.Label(panel, text="GOOGLE PLAY  ·  PREVIEWER, NOT A REAL PURCHASE",
             bg=surface, fg=muted,
             font=(ui.get_native_font(""), -11, "bold")).pack(pady=(16, 10))
    tk.Label(panel, text=_title(product), bg=surface, fg=on_surface,
             font=(ui.get_native_font(""), -20, "bold")).pack()
    tk.Label(panel, text=_PRETEND_SUB if subscription else _PRETEND_PRICE,
             bg=surface, fg=primary,
             font=(ui.get_native_font(""), -16, "bold")).pack(pady=(4, 2))
    tk.Label(panel, text="Invented price. Nothing is charged.", bg=surface,
             fg=muted, font=(ui.get_native_font(""), -12)).pack(pady=(0, 14))

    def confirm():
        row = _row(product)
        if not consumable:
            _owned[product] = row
        finish(True, json.dumps(row))

    buttons = tk.Frame(panel, bg=surface)
    buttons.pack(fill="x", padx=20)
    tk.Button(buttons, text="Cancel", command=lambda: finish(False, "cancelled"),
              bg=surface, fg=muted, relief="flat", bd=0, cursor="hand2",
              activebackground=surface,
              font=(ui.get_native_font(""), -14, "bold"), pady=10).pack(
                  side="left", expand=True, fill="x")
    tk.Button(buttons, text="Subscribe" if subscription else "Buy",
              command=confirm, bg=primary,
              fg=tokens.get("on_primary", "#381E72"), relief="flat", bd=0,
              cursor="hand2", activebackground=primary,
              font=(ui.get_native_font(""), -14, "bold"), pady=10).pack(
                  side="left", expand=True, fill="x", padx=(12, 0))

    scrim.bind("<Button-1>", lambda _e: finish(False, "cancelled"))
    root.bind("<Escape>", lambda _e: finish(False, "cancelled"), "+")
