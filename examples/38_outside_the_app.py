"""Edge - what an app has outside its own screens.

A widget on the home screen, a tile in quick settings, ads, a newer version
from Google Play, and what the phone's health records say.

The four lines under the import change what is built: that the app has a
widget and a tile, which AdMob app it is, and where its privacy policy
lives. Each row below is one call.

Needs ApkPy 1.13.0.
"""

from apkpy_lib import *

home_widget.define("Steps today", "0", caption="steps", icon="directions_walk")
quick_tile.define("Walk", icon="directions_walk")
ads.setup("test")
health.policy("https://example.com/privacy")

home = Screen(id="home", scroll=True)

label("Edge", id="title", screen=home)
label("What an app has outside its own screens.", id="lead", screen=home)

answer = container(id="answer", screen=home)
label("LAST ANSWER", id="answer_kicker", parent=answer)
status = label("Nothing yet", id="status", parent=answer)
detail = label("Tap a row to make a call.", id="detail", parent=answer)


def show(call, word):
    status.set_value(word)
    detail.set_value(call)


def arrived():
    ads.banner("test")
    ads.prepare(interstitial="test", rewarded="test")
    if quick_tile.opened():
        show("quick_tile.opened()", "The tile opened the app")
        quick_tile.clear()


lifecycle(home, on_mount=arrived)


def walk():
    steps = int(storage.get("steps", "0")) + 500
    storage.set("steps", str(steps))
    show("home_widget.set()", home_widget.set(str(steps), caption="steps"))


def pin_widget():
    show("home_widget.pin()", home_widget.pin())


def count_widgets():
    show("home_widget.count()", home_widget.count())


def flip_tile():
    if quick_tile.is_active():
        show("quick_tile.set(False)", quick_tile.set(False))
    else:
        show("quick_tile.set(True)", quick_tile.set(True, subtitle="On a walk"))


def offered(ok, word):
    show("quick_tile.offer()", word)


def offer_tile():
    quick_tile.offer(on_result=offered)


def banner_on():
    show("ads.banner()", ads.banner("test"))


def banner_off():
    show("ads.hide_banner()", ads.hide_banner())


def between(ok, word):
    show("ads.interstitial()", word)


def show_between():
    ads.interstitial("test", on_result=between)


def earned(ok, amount):
    if ok:
        show("ads.rewarded() paid", amount + " coins")
    else:
        show("ads.rewarded()", amount)


def watch():
    ads.rewarded("test", on_result=earned)


def settled(ok, word):
    show("ads.consent()", word)


def ask_consent():
    ads.consent(on_result=settled)


def checked(ok, word):
    show("updates.check()", word)


def check():
    updates.check(on_result=checked)


def updating(ok, word):
    show("updates.start()", word)


def update_now():
    updates.start("flexible", on_result=updating)


def restart():
    show("updates.install()", updates.install())


def asked(ok, word):
    show("health.ask()", word)


def ask_health():
    health.ask("steps, heart_rate, sleep", on_result=asked)


def got_steps(ok, value):
    if ok:
        show("health.read(steps)", value + " steps")
    else:
        show("health.read(steps)", value)


def read_steps():
    health.read("steps", on_result=got_steps)


def got_heart(ok, value):
    if ok:
        show("health.read(heart_rate)", value + " bpm")
    else:
        show("health.read(heart_rate)", value)


def read_heart():
    health.read("heart_rate", on_result=got_heart)


def got_sleep(ok, value):
    if ok:
        show("health.read(sleep)", value + " min")
    else:
        show("health.read(sleep)", value)


def read_sleep():
    health.read("sleep", start="2026-10-04 20:00", on_result=got_sleep)


label("HOME SCREEN", id="k_widget", screen=home)
g_widget = container(id="g_widget", screen=home)
list_row("Walk 500 steps", subtitle="The widget shows the new total", icon="directions_walk", id="r_walk", parent=g_widget, command=walk)
list_row("Add the widget", subtitle="The launcher asks where to put it", icon="add_to_home_screen", trailing_icon="chevron_right", id="r_pin", parent=g_widget, command=pin_widget)
list_row("Count them", subtitle="How many are on the home screen", icon="widgets", id="r_count", parent=g_widget, command=count_widgets)

label("QUICK SETTINGS", id="k_tile", screen=home)
g_tile = container(id="g_tile", screen=home)
list_row("Light the tile", subtitle="Tap again to put it out", icon="toggle_on", id="r_tile", parent=g_tile, command=flip_tile)
list_row("Offer the tile", subtitle="Android asks to add it", icon="add_circle", trailing_icon="chevron_right", id="r_offer", parent=g_tile, command=offer_tile)

label("ADS", id="k_ads", screen=home)
g_ads = container(id="g_ads", screen=home)
list_row("Banner", subtitle="Along the bottom of this screen", icon="call_to_action", id="r_banner", parent=g_ads, command=banner_on)
list_row("Take it away", subtitle="The screen gets its room back", icon="close", id="r_hide", parent=g_ads, command=banner_off)
list_row("Between two screens", subtitle="A full-screen ad", icon="fullscreen", id="r_between", parent=g_ads, command=show_between)
list_row("Watch for a reward", subtitle="An ad the person chooses", icon="redeem", id="r_reward", parent=g_ads, command=watch)
list_row("Ask for consent", subtitle="Only where the law requires it", icon="verified_user", id="r_consent", parent=g_ads, command=ask_consent)

label("UPDATES", id="k_updates", screen=home)
g_updates = container(id="g_updates", screen=home)
list_row("Check", subtitle="Is there a newer version on Play?", icon="system_update", id="r_check", parent=g_updates, command=check)
list_row("Update", subtitle="Downloads behind the app", icon="download", id="r_update", parent=g_updates, command=update_now)
list_row("Restart into it", subtitle="Once it is downloaded", icon="restart_alt", id="r_restart", parent=g_updates, command=restart)

label("HEALTH", id="k_health", screen=home)
g_health = container(id="g_health", screen=home)
list_row("Ask to read", subtitle="Steps, heart rate and sleep", icon="health_and_safety", trailing_icon="chevron_right", id="r_ask", parent=g_health, command=ask_health)
list_row("Steps today", subtitle="A total since midnight", icon="directions_walk", id="r_steps", parent=g_health, command=read_steps)
list_row("Heart rate today", subtitle="An average", icon="favorite", id="r_heart", parent=g_health, command=read_heart)
list_row("Last night's sleep", subtitle="Minutes since yesterday evening", icon="bedtime", id="r_sleep", parent=g_health, command=read_sleep)

theme = Theme(
    primary="#0B7A6B",
    background="#F2F5F4",
    surface="#FFFFFF",
    text="#17201E",
    text_secondary="#5F6B68",
    border="#E1E7E5",
    radius=18,
)

style = """
home {
    background-color: var(--background);
    padding: 24px 16px 32px 16px;
}
title {
    color: var(--text);
    font-size: 32px;
    font-weight: bold;
    letter-spacing: -0.6px;
}
lead {
    color: var(--text-secondary);
    font-size: 15px;
    line-height: 1.5;
    margin-bottom: 18px;
}
answer {
    background-color: var(--primary);
    border-radius: 22px;
    padding: 18px 20px 20px 20px;
    gap: 4px;
}
answer_kicker {
    color: #DDF3EF;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.2px;
}
status {
    color: #FFFFFF;
    font-size: 22px;
    font-weight: bold;
    letter-spacing: -0.2px;
}
detail {
    color: #E6F6F3;
    font-size: 13px;
}
k_widget, k_tile, k_ads, k_updates, k_health {
    color: var(--text-secondary);
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.2px;
    margin-top: 22px;
    margin-bottom: 8px;
    margin-left: 6px;
}
g_widget, g_tile, g_ads, g_updates, g_health {
    background-color: var(--surface);
    border-radius: 18px;
    padding: 0px;
    divider-color: var(--border);
    divider-inset: 58px;
}
list_row {
    background-color: #00000000;
    border-radius: 0px;
    padding: 0px 18px;
    min-height: 64px;
    color: var(--text);
    subtitle-color: var(--text-secondary);
    trailing-color: var(--text-secondary);
    icon-color: var(--primary);
}
"""

run(start_screen=home, theme=theme)
