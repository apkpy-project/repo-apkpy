# Example 04 — Coffee Haven (Full Multi-Screen App)
# A complete real-world app featuring images, storage, radio buttons,
# navigation, toasts, and a fully custom dark + light CSS design.
# Run it with: python 04_coffee_haven.py
# Note: Place a 'logo.png' in the same folder for the best experience.

from apkpy_lib import Screen, button, label, inputs, image, run, toast, storage

# ─────────────────────────────────────────────
# SCREENS
# ─────────────────────────────────────────────
welcome_screen = Screen(id="welcome_container")
order_screen   = Screen(id="order_container")

# ─────────────────────────────────────────────
# LOGIC
# ─────────────────────────────────────────────
def place_order():
    coffee = coffee_select.get_value()
    notes  = special_notes.get_value()

    # Persist the user's choices for next time
    storage.set("coffee_select",  coffee)
    storage.set("special_notes",  notes)

    toast(f"Order placed! One {coffee} coming right up ☕")

# ─────────────────────────────────────────────
# WELCOME SCREEN
# ─────────────────────────────────────────────
image("logo.png", id="welcome_logo", screen=welcome_screen)
label("COFFEE HAVEN",          id="welcome_title",    screen=welcome_screen)
label("The best brew in town.", id="welcome_subtitle", screen=welcome_screen)

btn_start = button("EXPLORE MENU", id="btn_primary", screen=welcome_screen)
welcome_screen.on_click_navigate(button=btn_start, to=order_screen)

# ─────────────────────────────────────────────
# ORDER SCREEN
# ─────────────────────────────────────────────
label("SELECT YOUR COFFEE", id="menu_title", screen=order_screen)

coffee_select = inputs(
    "Espresso|Latte|Cappuccino|Mocha",
    type="radio",
    id="coffee_select",
    screen=order_screen
)

special_notes = inputs(
    "Special instructions (e.g., extra sugar)",
    type="text",
    id="special_notes",
    screen=order_screen
)

# Auto-restore last order preferences
saved_coffee = storage.get("coffee_select", "")
if saved_coffee != "":
    coffee_select.set_value(saved_coffee)

saved_notes = storage.get("special_notes", "")
if saved_notes != "":
    special_notes.set_value(saved_notes)

button("PLACE ORDER", id="btn_order", command=place_order, screen=order_screen)

# ─────────────────────────────────────────────
# STYLING
# ─────────────────────────────────────────────
style = """
welcome_container {
    background-color: #2D1E17;
    flex-direction: column;
    gap: 0px;
}

order_container {
    background-color: #FDF8F5;
    flex-direction: column;
    padding: 30px;
    gap: 20px;
}

welcome_logo {
    width: 180px;
    height: 180px;
    border-radius: 90px;
    margin-top: 100px;
    box-shadow: 0 10px 20px #000;
    animation-name: fadeInDown;
    animation-duration: 1000ms;
}

welcome_title {
    color: #FDF8F5;
    font-size: 32px;
    font-weight: bold;
    margin-top: 40px;
    margin-bottom: 5px;
    animation-name: fadeInDown;
    animation-duration: 1200ms;
}

welcome_subtitle {
    color: #D4A373;
    font-size: 18px;
    margin-bottom: 60px;
    animation-name: fadeIn;
    animation-duration: 2000ms;
}

btn_primary {
    background-color: #D4A373;
    color: #2D1E17;
    border-radius: 30px;
    font-weight: bold;
    font-size: 18px;
    padding: 18px 45px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    pressed-color: #B88B5B;
    animation-name: fadeInUp;
    animation-duration: 1000ms;
}

menu_title {
    color: #2D1E17;
    font-size: 24px;
    font-weight: bold;
    margin-top: 10px;
    margin-bottom: 10px;
    animation-name: fadeIn;
    animation-duration: 1000ms;
}

coffee_select {
    color: #3E2723;
    font-size: 18px;
    animation-name: fadeIn;
    animation-duration: 1200ms;
}

special_notes {
    border-color: #D4A373;
    border-radius: 12px;
    padding: 20px;
    font-size: 16px;
    background-color: #ffffff;
    focus-border-color: #2D1E17;
}

btn_order {
    background-color: #2D1E17;
    color: #FDF8F5;
    border-radius: 15px;
    font-weight: bold;
    font-size: 18px;
    padding: 20px;
    pressed-color: #1A110D;
    margin-top: 30px;
    animation-name: zoomIn;
    animation-duration: 800ms;
}

@keyframes fadeInDown {
    from { opacity: 0; margin-top: -40px; }
    to   { opacity: 1; margin-top: 0px; }
}

@keyframes fadeInUp {
    from { opacity: 0; margin-top: 40px; }
    to   { opacity: 1; margin-top: 0px; }
}

@keyframes zoomIn {
    from { opacity: 0; scale: 0.8; }
    to   { opacity: 1; scale: 1.0; }
}

@keyframes fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
}
"""

if __name__ == "__main__":
    run(start_screen=welcome_screen)
