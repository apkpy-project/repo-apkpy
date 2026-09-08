"""Order Desk — local notification examples; no server or account needed."""
from apkpy_lib import (
    Screen, Theme, app_bar, label, button, run, notify, notifications,
    on_click_navigate, background_job, toast,
)

home = Screen(id="home", scroll=True)
detail = Screen(id="detail", scroll=True)
app_bar("Order Desk", screen=home)
app_bar("Order #42", screen=detail)
label("Updates that stay with you.", variant="title", screen=home)
label("Send an update, then open the notification drawer. Tap a card or an action to return here.", screen=home)
status = label("Ready to send", id="status", screen=home)
notifications.channel("orders", "Order updates", importance="high")
notifications.channel("work", "Background tasks", importance="low")


def viewed():
    notifications.cancel("order_42")
    status.set_value("Order #42 opened")
    on_click_navigate(detail)


def later():
    notifications.cancel("order_42")
    status.set_value("Notification cleared — no reminder scheduled")
    toast("Notification cleared. Check the order later.")


def dismissed():
    status.set_value("Notification dismissed")


def send_order():
    notify("Order shipped", "Your order arrives tomorrow between 9 AM and noon. Everything is packed and ready. Tap to see the delivery details.",
           id="order_42", channel="orders", icon="local_shipping", style="big_text",
           actions=[("View", viewed), ("Later", later)], on_tap=detail,
           on_dismiss=dismissed, group="orders")
    status.set_value("Order update sent")


def send_digest():
    notify("Today's deliveries", "Three updates from your delivery team", id="digest",
           channel="orders", icon="inbox", style="inbox",
           lines=["Order #42 is on its way", "Order #43 is being packed", "Order #44 was delivered"], group="orders")
    status.set_value("Digest sent — expand it in the drawer")


def send_picture():
    notify("A closer look", "Your ApkPy package is ready", id="picture",
           channel="orders", icon="image", style="big_picture", picture="preview.png")
    status.set_value("Picture sent — expand it in the drawer")


def show_progress():
    notify("Preparing export", "35% complete", id="export", channel="work",
           icon="download", ongoing=True, progress=35)
    status.set_value("Progress notification: 35%")


def finish_progress():
    notify("Export ready", "The same notification was updated", id="export",
           channel="work", icon="check", progress=100)
    status.set_value("Progress notification: complete")


def permission_status():
    if notifications.allowed():
        status.set_value("Notifications are allowed")
    else:
        status.set_value("Notifications are disabled — use Allow notifications")


def ask_permission():
    notifications.ask()


def clear_notifications():
    notifications.cancel_all()
    status.set_value("Notifications cleared")


def go_home():
    on_click_navigate(home)


def task():
    notifications.channel("work", "Background tasks", importance="low")
    notify("Task complete", "This notification came from a background worker", id="worker", channel="work")


worker = background_job("notification_demo", run=task)


def enqueue_task():
    worker.enqueue({})
    status.set_value("Background task queued")


button("Allow notifications", command=ask_permission, variant="outlined", screen=home)
button("Check permission", command=permission_status, variant="outlined", screen=home)
button("Send order update", command=send_order, icon="local_shipping", screen=home)
button("Send inbox digest", command=send_digest, icon="inbox", screen=home)
button("Send picture", command=send_picture, icon="image", screen=home)
button("Show progress", command=show_progress, variant="outlined", screen=home)
button("Finish progress", command=finish_progress, variant="outlined", screen=home)
button("Run background task", command=enqueue_task, variant="outlined", screen=home)
button("Clear notifications", command=clear_notifications, variant="outlined", screen=home)
label("Tomorrow, 9 AM – noon", variant="title", screen=detail)
label("This screen was opened directly from the notification. Actions and dismissals are shown on the home screen.", screen=detail)
button("Back to Order Desk", command=go_home, screen=detail)

style = """
Screen { padding: 20px; gap: 12px; }
label { color: var(--text-secondary); margin-bottom: 8px; }
status { color: var(--primary); font-weight: bold; }
button { min-height: 48px; margin-bottom: 10px; }
"""

run(start_screen=home, theme=Theme(mode="dark"))
