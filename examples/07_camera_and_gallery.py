# Example 07 — Camera & Gallery
# Demonstrates camera.capture() and gallery.pick() — the v0.9.8 APIs that open
# the device's native camera / image picker and return the result asynchronously
# via on_result(success, path), with 100% identical code between the Hot
# Previewer and a real Android device.
#
# IMPORTANT: your computer has no camera app or photo gallery, so the Hot
# Previewer SIMULATES both by opening your OS's file explorer (filtered to
# images) — whatever image you pick is treated as "the photo you took" / "the
# image you chose". On a real Android device, the exact same code opens the
# actual native camera and gallery apps. This is what keeps your Python code
# 100% identical in both worlds — only what happens "behind the scenes" changes.
#
# Run it with: python 07_camera_and_gallery.py

from apkpy_lib import Screen, label, button, toast, camera, gallery, run

main = Screen(id="main")

# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────
label("📸 Camera & Gallery Demo", id="title", screen=main)
label("Take a photo or pick one from the gallery — async on_result(success, path).", id="subtitle", screen=main)

result_label = label("No photo or image chosen yet.", id="result", screen=main)

# ─────────────────────────────────────────────
# CAMERA
# ─────────────────────────────────────────────
# camera.capture() opens the native camera app, takes a photo, and asynchronously
# delivers (success, path) to on_result — same async pattern as https.get/post.
# On Android: requests the CAMERA permission at runtime and writes the photo to
# a content:// URI via FileProvider — all set up automatically by ApkPy.
def foto_tirada(success, path):
    if success:
        result_label.set_value(f"📷 Photo taken: {path}")
        toast("Photo captured!")
    else:
        result_label.set_value("No photo or image chosen yet.")
        toast("No photo was taken.")

def tirar_foto():
    camera.capture(on_result=foto_tirada)

# ─────────────────────────────────────────────
# GALLERY
# ─────────────────────────────────────────────
# gallery.pick() opens the system's native image picker and asynchronously
# delivers (success, path) to on_result. On Android it requires NO storage
# permissions — it's scoped-storage compliant out of the box.
def imagem_escolhida(success, path):
    if success:
        result_label.set_value(f"🖼️ Picked from gallery: {path}")
        toast("Image picked!")
    else:
        result_label.set_value("No photo or image chosen yet.")
        toast("No image was picked.")

def escolher_da_galeria():
    gallery.pick(on_result=imagem_escolhida)

button("📷 Take Photo",        id="btn_camera",  command=tirar_foto,          screen=main)
button("🖼️ Pick from Gallery", id="btn_gallery", command=escolher_da_galeria, screen=main)

# ─────────────────────────────────────────────
# STYLING
# ─────────────────────────────────────────────
style = """
main {
    background-color: #0F172A;
    flex-direction: column;
    padding: 28px;
    gap: 12px;
}

title {
    color: #A78BFA;
    font-size: 22px;
    font-weight: bold;
    text-align: center;
    margin-top: 24px;
}

subtitle {
    color: #94A3B8;
    font-size: 13px;
    text-align: center;
    margin-bottom: 18px;
}

result {
    color: #38BDF8;
    font-size: 13px;
    font-weight: bold;
    margin-bottom: 6px;
}

btn_camera {
    background-color: #334155;
    color: #A78BFA;
    border-radius: 14px;
    font-weight: bold;
    font-size: 14px;
    padding: 14px;
    margin-top: 8px;
    pressed-color: #1E293B;
}

btn_gallery {
    background-color: #334155;
    color: #FB923C;
    border-radius: 14px;
    font-weight: bold;
    font-size: 14px;
    padding: 14px;
    margin-top: 8px;
    pressed-color: #1E293B;
}
"""

if __name__ == "__main__":
    run(start_screen=main)
