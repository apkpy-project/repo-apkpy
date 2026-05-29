# Example 05 — Native Permissions
# Shows how to declare and request Android permissions at runtime.
# Run it with: python 05_permissions.py

from apkpy_lib import Screen, label, button, toast, declare_permissions, permissions, run

# Tell ApkPy to add these to AndroidManifest.xml during the build step
declare_permissions(["CAMERA", "ACCESS_FINE_LOCATION"])

main = Screen(id="perms_screen")

label("📱 Permissions Demo", id="title",    screen=main)
label("Tap a button to request a permission.", id="subtitle", screen=main)

# ─────────────────────────────────────────────
# CAMERA PERMISSION
# ─────────────────────────────────────────────
def request_camera():
    def on_result(granted):
        if granted:
            toast("✅ Camera access granted! You can now use the camera.")
        else:
            toast("❌ Camera permission denied.")

    permissions.request("CAMERA", on_response=on_result)

# ─────────────────────────────────────────────
# LOCATION PERMISSION
# ─────────────────────────────────────────────
def request_location():
    def on_result(granted):
        if granted:
            toast("✅ Location access granted! Getting your position...")
        else:
            toast("❌ Location permission denied.")

    permissions.request("ACCESS_FINE_LOCATION", on_response=on_result)

# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────
button("📷 Request Camera",   id="btn_camera",   command=request_camera,   screen=main)
button("📍 Request Location", id="btn_location", command=request_location, screen=main)

# ─────────────────────────────────────────────
# STYLING
# ─────────────────────────────────────────────
style = """
perms_screen {
    background-color: #ffffff;
    flex-direction: column;
    padding: 30px;
    gap: 20px;
}

title {
    color: #1a1a2e;
    font-size: 26px;
    font-weight: bold;
    animation-name: fadeIn;
    animation-duration: 600ms;
}

subtitle {
    color: #6c757d;
    font-size: 16px;
    margin-bottom: 20px;
}

btn_camera {
    background-color: #1a1a2e;
    color: white;
    border-radius: 20px;
    padding: 16px;
    font-size: 17px;
    font-weight: bold;
    pressed-color: #0f0f1a;
}

btn_location {
    background-color: #ffffff;
    color: #1a1a2e;
    border-color: #1a1a2e;
    border-width: 2px;
    border-radius: 20px;
    padding: 15px;
    font-size: 17px;
    font-weight: bold;
    pressed-color: #e8e8f0;
}

@keyframes fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
}
"""

if __name__ == "__main__":
    run(start_screen=main)
