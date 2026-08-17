"""Onda — a focused daily wellbeing app built with ApkPy."""

from apkpy_lib import (
    Screen, Theme, bottom_nav, button, container, device, label, run, toast,
)


device("Pixel 9")

theme = Theme(
    mode="dark",
    primary="#C8FF5A",
    secondary="#FF8A6B",
    background="#101412",
    surface="#1A211D",
    text="#F4F7F3",
    text_secondary="#9EAAA2",
    border="#303A34",
    radius=20,
    spacing=14,
    font_family="sans-serif",
)

today = Screen(id="onda_today", scroll=True)
trends = Screen(id="onda_trends", scroll=True)
coach = Screen(id="onda_coach", scroll=True)
settings = Screen(id="onda_settings", scroll=True)

header = container(id="onda_header", screen=today)
brand = container(id="onda_brand", parent=header)
label("ONDA", id="onda_wordmark", parent=brand)
label("Tuesday · 16 July", id="onda_day", parent=brand)
button("", id="onda_profile", icon="person", variant="icon", parent=header,
       command=lambda: toast("Good morning, Sam"))

label("Your pace, clearly.", id="onda_title", screen=today)
label("A practical view of recovery, without the noise.", id="onda_intro", screen=today)

readiness = container(id="readiness_card", screen=today)
readiness_copy = container(id="readiness_copy", parent=readiness)
label("DAILY READINESS", id="readiness_kicker", parent=readiness_copy)
label("84", id="readiness_score", parent=readiness_copy)
label("Ready for a focused day", id="readiness_state", parent=readiness_copy)
label("READY", id="readiness_badge", parent=readiness)

metrics = container(id="health_metrics", screen=today)
sleep = container(id="sleep_metric", parent=metrics)
label("Sleep", id="sleep_label", parent=sleep)
label("7h 42m", id="sleep_value", parent=sleep)
label("+28m vs average", id="sleep_meta", parent=sleep)
recovery = container(id="recovery_metric", parent=metrics)
label("Recovery", id="recovery_label", parent=recovery)
label("91%", id="recovery_value", parent=recovery)
label("Heart rate settled", id="recovery_meta", parent=recovery)

label("Today's rhythm", id="rhythm_title", screen=today)
rhythm = container(id="rhythm_card", screen=today)
rhythm_copy = container(id="rhythm_copy", parent=rhythm)
label("08:30 · Deep work window", id="rhythm_name", parent=rhythm_copy)
label("Your energy typically peaks for 94 minutes.", id="rhythm_meta", parent=rhythm_copy)
button("Start", id="start_focus", icon="play_arrow", variant="outlined", parent=rhythm,
       command=lambda: toast("Focus session started"))

button("Plan the rest of my day", id="plan_day", icon="arrow_forward", variant="filled", screen=today,
       command=lambda: toast("Your plan is ready"))

for page, title, copy in [
    (trends, "Trends", "Patterns across sleep, focus and movement."),
    (coach, "Coach", "Small suggestions grounded in your routine."),
    (settings, "Settings", "Goals, privacy and connected devices."),
]:
    label(title, id=page.id + "_title", screen=page)
    label(copy, id=page.id + "_copy", screen=page)

bottom_nav(
    [today, trends, coach, settings],
    labels=["Today", "Trends", "Coach", "Settings"],
    icons=["home", "chart", "star", "settings"],
)

style = """
body { font-family: var(--font-family); }
onda_today, onda_trends, onda_coach, onda_settings {
    background-color: var(--background); padding: 20px;
}
label { color: var(--text); }
onda_header {
    display: flex; flex-direction: row; align-items: center; width: 100%;
    background-color: var(--background); border-width: 0px; padding: 0px;
    margin-top: 4px; margin-bottom: 18px;
}
onda_brand { flex-grow: 1; background-color: var(--background); border-width: 0px; padding: 0px; }
onda_wordmark { color: var(--primary); font-size: 13px; font-weight: bold; letter-spacing: 2px; }
onda_day { color: var(--text-secondary); font-size: 12px; margin-top: 3px; }
onda_profile { color: var(--text); background-color: var(--surface); border-radius: 20px; }
onda_title { color: var(--text); font-size: 29px; font-weight: bold; margin-bottom: 6px; }
onda_intro { color: var(--text-secondary); font-size: 14px; margin-bottom: 18px; }
readiness_card {
    display: flex; flex-direction: row; align-items: center; width: 100%;
    background-color: #C8FF5A; border-width: 0px; border-radius: 22px;
    padding: 19px; margin-bottom: 12px;
}
readiness_copy {
    flex-grow: 1; background-color: #C8FF5A; border-width: 0px; padding: 0px;
}
readiness_kicker { color: #40531D; font-size: 10px; font-weight: bold; letter-spacing: 1.2px; }
readiness_score { color: #101412; font-size: 42px; font-weight: bold; margin-top: 2px; }
readiness_state { color: #293516; font-size: 13px; }
readiness_badge {
    color: #101412; background-color: #E8FFB9; border-radius: 20px;
    padding: 8px; font-size: 10px; font-weight: bold;
}
health_metrics {
    display: flex; flex-direction: row; gap: 10px; width: 100%;
    background-color: var(--background); border-width: 0px; padding: 0px;
    margin-bottom: 18px;
}
sleep_metric, recovery_metric {
    flex-grow: 1; flex-basis: 140px; background-color: var(--surface);
    border-color: var(--border); border-width: 1px; border-radius: 17px; padding: 14px;
}
sleep_label, recovery_label { color: var(--text-secondary); font-size: 12px; }
sleep_value, recovery_value { color: var(--text); font-size: 20px; font-weight: bold; margin-top: 5px; }
sleep_meta, recovery_meta { color: #A7D66A; font-size: 10px; margin-top: 5px; }
rhythm_title { color: var(--text); font-size: 18px; font-weight: bold; margin-bottom: 9px; }
rhythm_card {
    display: flex; flex-direction: row; align-items: center; gap: 10px; width: 100%;
    background-color: var(--surface); border-color: var(--border); border-width: 1px;
    border-radius: 18px; padding: 14px; margin-bottom: 12px;
}
rhythm_copy { flex-grow: 1; background-color: var(--surface); border-width: 0px; padding: 0px; }
rhythm_name { color: var(--text); font-size: 14px; font-weight: bold; }
rhythm_meta { color: var(--text-secondary); font-size: 10px; margin-top: 3px; }
start_focus { color: var(--primary); background-color: var(--surface); border-color: var(--primary); border-width: 1px; }
plan_day {
    width: 100%; background-color: var(--secondary); color: #201310;
    border-radius: 15px; padding: 13px; font-weight: bold; margin-bottom: 10px;
}
onda_trends_title, onda_coach_title, onda_settings_title {
    color: var(--text); font-size: 28px; font-weight: bold; margin-top: 30px;
}
onda_trends_copy, onda_coach_copy, onda_settings_copy {
    color: var(--text-secondary); font-size: 14px; margin-top: 8px;
}
"""

if __name__ == "__main__":
    run(start_screen=today, theme=theme)
