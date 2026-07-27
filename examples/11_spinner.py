# Example 11 — Loading Spinner
# Demonstrates spinner() — a native circular loading indicator you show while
# work is in progress (an https request here) and hide when the result arrives.
# Toggle it with .show() / .hide(). Same code in the Hot Previewer and on Android.
#
# In the Hot Previewer it's an animated rotating arc; on Android it compiles to an
# indeterminate ProgressBar, with .show()/.hide() → setVisibility(VISIBLE/GONE).
#
# Run it with: python 11_spinner.py

from apkpy_lib import Screen, label, button, spinner, https, json_get, run

main = Screen(id="main")

label("⏳ Loading Spinner Demo", id="title", screen=main)
result = label("Press FETCH to load a to-do from the internet.", id="result", screen=main)

# Start hidden — we only show it while the request is running.
loading = spinner(id="loading", screen=main, visible=False)

def on_response(success, response):
    loading.hide()                       # result is back → hide the spinner
    if success:
        result.set_value("Title: " + json_get(response, "title"))
    else:
        result.set_value("Request failed — check your connection.")

def fetch():
    loading.show()                       # request starting → show the spinner
    result.set_value("Loading…")
    https.get("https://jsonplaceholder.typicode.com/todos/1", on_response=on_response)

button("FETCH", id="btn", command=fetch, screen=main)

style = """
main    { background-color: #0F172A; flex-direction: column; padding: 28px; gap: 16px; }
title   { color: #818CF8; font-size: 22px; font-weight: bold; margin-top: 24px; }
result  { color: #E2E8F0; font-size: 14px; }
loading { color: #6366F1; width: 48px; height: 48px; }
btn     { background-color: #6366F1; color: #FFFFFF; border-radius: 14px; font-weight: bold; padding: 14px; pressed-color: #4338CA; }
"""

if __name__ == "__main__":
    run(start_screen=main)
