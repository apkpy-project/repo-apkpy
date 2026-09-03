"""A shop: a one-time unlock, a consumable, a subscription, and a restore.

Nothing here writes a price down. Play answers with the person's own currency,
and every completed purchase is acknowledged before the callback is told --
Google refunds anything an app leaves unacknowledged for three days.
"""

from apkpy_lib import (
    Screen, Theme, app_bar, billing, button, container, label, lifecycle,
    list_view, run, storage,
)

home = Screen(id="home")

app_bar("Shop", screen=home)
label("Go Pro", id="title", screen=home)
status = label("", id="status", screen=home)

shop = list_view([], id="shop", screen=home)

actions = container(id="actions", screen=home)
button("SHOW PRICES", id="b_prices", icon="star", parent=actions,
       command=lambda: ask_prices())
button("SHOW PLANS", id="b_plans", icon="chart", parent=actions,
       command=lambda: ask_plans())
button("BUY PRO (one-time)", id="b_pro", icon="lock_open", parent=actions,
       command=lambda: buy_pro())
button("BUY 100 COINS (again and again)", id="b_coins", icon="add",
       parent=actions, command=lambda: buy_coins())
button("SUBSCRIBE MONTHLY", id="b_sub", icon="refresh", parent=actions,
       command=lambda: subscribe())
button("RESTORE PURCHASES", id="b_restore", icon="done_all", parent=actions,
       command=lambda: restore())


def shown(ok, items):
    if ok:
        shop.set_items(items, title="title", subtitle="price")
        status.set_value("")
    else:
        status.set_value(explain(items))


def listed(ok, items):
    if ok:
        shop.set_items(items, title="id", subtitle="order")
        status.set_value("Anything above was already paid for.")
    else:
        status.set_value(explain(items))


def bought(ok, value):
    if ok:
        # `value` is JSON carrying a token. Something worth real money should
        # be checked on a server with it before anything is unlocked.
        storage.set("pro", "yes")
        status.set_value("Thank you. Pro is on.")
    elif value == "owned":
        # Not an error: they paid before, on this account or another phone.
        storage.set("pro", "yes")
        status.set_value("You already had it. Pro is on.")
    elif value == "pending":
        # Cash or a slow method. Unlock nothing until it clears.
        status.set_value("Payment started. Nothing is unlocked yet.")
    elif value == "cancelled":
        status.set_value("")
    else:
        status.set_value(explain(value))


def spent(ok, value):
    if ok:
        status.set_value("Coins added.")
    else:
        status.set_value(explain(value))


def explain(reason):
    if reason == "not_found":
        return "No such product. Check the id in Play Console, and that the " \
               "app is on a track."
    if reason == "not_supported":
        return "This phone has no Play Store."
    if reason == "unavailable":
        return "Could not reach Play. Try again in a moment."
    if reason == "network":
        return "The network dropped during the payment."
    if reason == "denied":
        return "Play refused. An unsigned build, or an account that is not a " \
               "licensed tester."
    if reason == "not_owned":
        return "Nothing to use up."
    return "That did not work: " + reason


def ask_prices():
    billing.prices(["pro_unlock", "coins_100"], on_result=shown)


def ask_plans():
    billing.prices(["monthly", "yearly"], kind="subscription", on_result=shown)


def buy_pro():
    billing.buy("pro_unlock", on_result=bought)


def buy_coins():
    # consumable: it is consumed on the spot, so it can be bought again.
    billing.buy("coins_100", consumable=True, on_result=spent)


def subscribe():
    billing.subscribe("monthly", on_result=bought)


def restore():
    # A reinstall, or a second phone on the same account.
    billing.owned(on_result=listed)


def on_open():
    # Asking on every open is what makes a reinstall find what was paid for.
    billing.owned(on_result=quietly)


def quietly(ok, items):
    if ok:
        status.set_value("")


lifecycle(home, on_resume=on_open)

run(start_screen=home, theme=Theme(mode="dark"))

style = """
home { background-color: var(--background); padding: 18px; }

title {
    color: var(--text); font-size: var(--text-2xl); font-weight: bold;
    margin-bottom: 6px;
}
status {
    color: var(--primary); font-size: var(--text-base);
    line-height: var(--leading-normal); margin-bottom: 12px;
}

shop {
    background-color: var(--surface-high); border-radius: 16px;
    divider-color: var(--border); divider-width: 1px; margin-bottom: 14px;
}

actions { background-color: #00000000; }
b_prices, b_plans, b_pro, b_coins, b_sub, b_restore {
    width: 100%; min-height: 46px; border-radius: 13px;
    font-weight: bold; margin-bottom: 9px;
}
"""
