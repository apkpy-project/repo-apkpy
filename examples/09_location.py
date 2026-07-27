# Example 09 — Location / GPS
# Demonstrates location.get_current() — opens the device GPS and returns the
# current latitude, longitude AND resolved city name asynchronously via
# on_result(success, lat, lng, city), with 100% identical code between the Hot
# Previewer and a real Android device.
#
# IMPORTANT: your computer has no GPS, so the Hot Previewer SIMULATES it by
# asking you to type the coordinates (defaults to Lisbon). The city name is then
# resolved via OpenStreetMap. On a real Android device, the exact same code reads
# the actual GPS via LocationManager and resolves the city via Geocoder — the
# ACCESS_FINE_LOCATION permission is requested automatically.
#
# Run it with: python 09_location.py

from apkpy_lib import Screen, label, button, toast, location, run

main = Screen(id="main")

# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────
label("📍 Location / GPS Demo", id="title", screen=main)
label("Tap the button to read your current position.", id="subtitle", screen=main)

coords_label = label("Location: unknown", id="coords", screen=main)
city_label   = label("City: —",          id="city",   screen=main)

# ─────────────────────────────────────────────
# LOCATION
# ─────────────────────────────────────────────
# location.get_current() reads the GPS and asynchronously delivers
# (success, lat, lng, city) to on_result — same async pattern as camera/https.
# lat, lng and city are always strings (like every get_value()).
def on_location(success, lat, lng, city):
    if success:
        coords_label.set_value(f"Lat: {lat}, Lng: {lng}")
        city_label.set_value(f"City: {city}" if city else "City: (unknown)")
        toast("Location found! 📍")
    else:
        coords_label.set_value("Location: unavailable")
        toast("Couldn't get your location.")

def locate_me():
    location.get_current(on_result=on_location)

button("WHERE AM I?", id="btn_loc", command=locate_me, screen=main)

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
    color: #34D399;
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

coords {
    color: #38BDF8;
    font-size: 15px;
    font-weight: bold;
}

city {
    color: #A78BFA;
    font-size: 15px;
    font-weight: bold;
    margin-bottom: 6px;
}

btn_loc {
    background-color: #059669;
    color: #ECFDF5;
    border-radius: 14px;
    font-weight: bold;
    font-size: 15px;
    padding: 14px;
    margin-top: 8px;
    pressed-color: #047857;
}
"""

if __name__ == "__main__":
    run(start_screen=main)
