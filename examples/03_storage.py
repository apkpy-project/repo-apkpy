# Example 03 — Storage & Persistence
# Demonstrates saving, loading, and clearing persistent data.
# Data survives across app restarts — even on real Android devices!
# Run it with: python 03_storage.py

from apkpy_lib import Screen, label, inputs, button, toast, storage, run

main = Screen(id="main")

# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────
label("💾 Storage Demo", id="title", screen=main)
label("Your data is saved even if you close the app.", id="subtitle", screen=main)

name_field  = inputs("Your name",       type="text", id="name_field",  screen=main)
city_field  = inputs("Your city",       type="text", id="city_field",  screen=main)
theme_field = inputs("Light|Dark",      type="radio", id="theme_field", screen=main)

# ─────────────────────────────────────────────
# AUTO-LOAD SAVED DATA ON APP START
# ─────────────────────────────────────────────
# This runs immediately when the app launches.
# If the user has saved data before, it's loaded automatically.
saved_name  = storage.get("name", "")
saved_city  = storage.get("city", "")
saved_theme = storage.get("theme", "Light")

if saved_name  != "": name_field.set_value(saved_name)
if saved_city  != "": city_field.set_value(saved_city)
if saved_theme != "": theme_field.set_value(saved_theme)

# ─────────────────────────────────────────────
# SAVE / CLEAR LOGIC
# ─────────────────────────────────────────────
def save_all():
    name  = name_field.get_value()
    city  = city_field.get_value()
    theme = theme_field.get_value()

    if name == "" or city == "":
        toast("Please fill in all fields first! ⚠️")
        return

    storage.set("name",  name)
    storage.set("city",  city)
    storage.set("theme", theme)
    toast(f"Saved! Hello {name} from {city} 👋")

def clear_all():
    storage.clear()               # Wipes all stored keys
    name_field.set_value("")
    city_field.set_value("")
    theme_field.set_value("Light")
    toast("All data cleared! 🗑️")

button("💾 Save Data",  id="btn_save",  command=save_all,  screen=main)
button("🗑️ Clear Data", id="btn_clear", command=clear_all, screen=main)

# ─────────────────────────────────────────────
# STYLING
# ─────────────────────────────────────────────
style = """
main {
    background-color: #f8f9fa;
    flex-direction: column;
    padding: 30px;
    gap: 18px;
}

title {
    color: #212529;
    font-size: 26px;
    font-weight: bold;
    animation-name: fadeIn;
    animation-duration: 600ms;
}

subtitle {
    color: #6c757d;
    font-size: 15px;
    margin-bottom: 10px;
}

name_field, city_field {
    border-color: #dee2e6;
    border-radius: 12px;
    padding: 15px;
    background-color: #ffffff;
    focus-border-color: #0d6efd;
}

theme_field {
    color: #212529;
    font-size: 17px;
}

btn_save {
    background-color: #0d6efd;
    color: white;
    border-radius: 20px;
    padding: 15px;
    font-size: 17px;
    font-weight: bold;
    pressed-color: #0a58ca;
    margin-top: 10px;
}

btn_clear {
    background-color: #ffffff;
    color: #dc3545;
    border-color: #dc3545;
    border-width: 2px;
    border-radius: 20px;
    padding: 14px;
    font-size: 16px;
    pressed-color: #f8d7da;
}

@keyframes fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
}
"""

if __name__ == "__main__":
    run(start_screen=main)
