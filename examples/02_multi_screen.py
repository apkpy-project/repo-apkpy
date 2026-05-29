# Example 02 — Multi-Screen Navigation
# Shows how to create multiple screens and navigate between them.
# Run it with: python 02_multi_screen.py

from apkpy_lib import Screen, label, button, inputs, toast, run

# --- Define all screens first ---
login_screen   = Screen(id="login_screen")
home_screen    = Screen(id="home_screen")
profile_screen = Screen(id="profile_screen")

# ─────────────────────────────────────────────
# LOGIN SCREEN
# ─────────────────────────────────────────────
label("Welcome Back", id="login_title", screen=login_screen)
label("Sign in to continue", id="login_sub", screen=login_screen)

email_field    = inputs("Email address", type="text",     id="email_field",    screen=login_screen)
password_field = inputs("Password",      type="password", id="password_field", screen=login_screen)

btn_login = button("Sign In", id="btn_login", screen=login_screen)

# Navigate to home screen on login button press
login_screen.on_click_navigate(button=btn_login, to=home_screen)

# ─────────────────────────────────────────────
# HOME SCREEN
# ─────────────────────────────────────────────
label("🏠 Home", id="home_title", screen=home_screen)
label("You are now logged in!", id="home_sub", screen=home_screen)

btn_to_profile = button("View Profile →", id="btn_profile", screen=home_screen)
home_screen.on_click_navigate(button=btn_to_profile, to=profile_screen)

# ─────────────────────────────────────────────
# PROFILE SCREEN
# ─────────────────────────────────────────────
label("👤 Profile", id="profile_title", screen=profile_screen)
label("Alice Wonderland",   id="profile_name",  screen=profile_screen)
label("alice@example.com",  id="profile_email", screen=profile_screen)

def log_out():
    toast("Logged out! See you soon.")

button("Log Out", id="btn_logout", command=log_out, screen=profile_screen)

# ─────────────────────────────────────────────
# STYLING
# ─────────────────────────────────────────────
style = """
login_screen {
    background-color: #0f0f1a;
    flex-direction: column;
    padding: 40px;
    gap: 16px;
}

login_title {
    color: #ffffff;
    font-size: 30px;
    font-weight: bold;
    margin-bottom: 4px;
    animation-name: slideDown;
    animation-duration: 700ms;
}

login_sub {
    color: #888899;
    font-size: 16px;
    margin-bottom: 20px;
}

email_field, password_field {
    border-color: #333355;
    border-radius: 14px;
    padding: 16px;
    background-color: #1a1a2e;
    color: #ffffff;
    focus-border-color: #7c6af7;
}

btn_login {
    background-color: #7c6af7;
    color: white;
    border-radius: 25px;
    padding: 16px;
    font-size: 17px;
    font-weight: bold;
    pressed-color: #5a49d6;
    margin-top: 10px;
}

home_screen {
    background-color: #f5f5ff;
    flex-direction: column;
    padding: 40px;
    gap: 20px;
}

home_title {
    color: #1a1a2e;
    font-size: 32px;
    font-weight: bold;
}

home_sub {
    color: #555566;
    font-size: 17px;
}

btn_profile {
    background-color: #7c6af7;
    color: white;
    border-radius: 20px;
    padding: 14px 24px;
    font-size: 16px;
    pressed-color: #5a49d6;
}

profile_screen {
    background-color: #ffffff;
    flex-direction: column;
    padding: 40px;
    gap: 14px;
}

profile_title {
    color: #1a1a2e;
    font-size: 28px;
    font-weight: bold;
}

profile_name {
    color: #333344;
    font-size: 20px;
    font-weight: bold;
}

profile_email {
    color: #888899;
    font-size: 16px;
}

btn_logout {
    background-color: #ff4757;
    color: white;
    border-radius: 20px;
    padding: 14px 24px;
    font-size: 16px;
    pressed-color: #cc2233;
    margin-top: 20px;
}

@keyframes slideDown {
    from { opacity: 0; margin-top: -30px; }
    to   { opacity: 1; margin-top: 0px; }
}
"""

if __name__ == "__main__":
    run(start_screen=login_screen)
