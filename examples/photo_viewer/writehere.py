"""Harbour - pictures that open over the whole screen and zoom.

Four pictures carry zoom=True: a tap opens one on black, where two fingers
zoom it, a double tap zooms in and back, a drag moves it and a drag down
closes it. The button opens the first one by name with view_image(), the
way a list would open the picture of the row that was tapped.

The pictures are drawn by make_assets.py, so nothing here is anybody's
photograph: run it once in this folder before the app.

    python make_assets.py
    python writehere.py

Needs ApkPy 1.12.0.
"""

from apkpy_lib import *

home = Screen("home")

label("Harbour", id="title", screen=home)
label("Tap a picture to open it. Pinch or double-tap to zoom.", id="hint", screen=home)

image("harbour.jpg", id="hero", zoom=True, describe="A harbour at dusk", screen=home)

shelf = container(id="shelf", screen=home)
image("coast.jpg", id="thumb", zoom=True, describe="The coast at sunset", parent=shelf)
image("peak.jpg", id="thumb", zoom=True, describe="A snowy peak", parent=shelf)
image("city.jpg", id="thumb", zoom=True, describe="A city at night", parent=shelf)


def open_harbour():
    view_image("harbour.jpg", describe="A harbour at dusk")


button("Open the harbour", id="open", icon="zoom_in", command=open_harbour, screen=home)

style = """
title { font-size: 24px; font-weight: bold; }
hint { color: #49454F; }
hero { width: 100%; aspect-ratio: 3/2; object-fit: cover; border-radius: 16px; }
shelf { display: flex; flex-direction: row; gap: 8px; padding: 0px; }
thumb { width: 110px; height: 110px; object-fit: cover; border-radius: 12px; }
"""

run(home, theme=Theme())
