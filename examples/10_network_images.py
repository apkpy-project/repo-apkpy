# Example 10 — Images from the Internet
# Demonstrates image("https://...") — ApkPy detects a URL and loads the image at
# runtime in a background thread, so the UI never freezes. Works with 100%
# identical code in the Hot Previewer and on a real Android device.
#
# In the Hot Previewer the image is downloaded with urllib (a "loading…"
# placeholder shows until it arrives). On Android it compiles to a background
# Thread + HttpURLConnection + BitmapFactory.decodeStream(...) → setImageBitmap,
# and the INTERNET permission is declared automatically. No Glide/Picasso needed.
#
# Run it with: python 10_network_images.py

from apkpy_lib import Screen, label, image, button, run

main = Screen(id="main")

# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────
label("🌐 Network Images Demo", id="title", screen=main)
label("These images are downloaded from the internet at runtime.", id="subtitle", screen=main)

# A remote banner — full URL, loaded on the device. Same CSS as a local image:
# width, height, border-radius, object-fit, opacity, box-shadow all apply.
image("https://picsum.photos/600/300", id="banner", screen=main)

# A round avatar from a URL — border-radius makes it circular.
image("https://i.pravatar.cc/200", id="avatar", screen=main)

label("Tip: pair this with https.get() + list_view to show images from an API.",
      id="tip", screen=main)

# ─────────────────────────────────────────────
# STYLING
# ─────────────────────────────────────────────
style = """
main {
    background-color: #0F172A;
    flex-direction: column;
    padding: 24px;
    gap: 16px;
}

title {
    color: #60A5FA;
    font-size: 22px;
    font-weight: bold;
    text-align: center;
    margin-top: 24px;
}

subtitle {
    color: #94A3B8;
    font-size: 13px;
    text-align: center;
    margin-bottom: 8px;
}

banner {
    width: 300px;
    height: 150px;
    border-radius: 16px;
}

avatar {
    width: 120px;
    height: 120px;
    border-radius: 60px;
    border-color: #60A5FA;
    border-width: 3px;
}

tip {
    color: #64748B;
    font-size: 12px;
    text-align: center;
    margin-top: 8px;
}
"""

if __name__ == "__main__":
    run(start_screen=main)
