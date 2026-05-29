# Example 01 — Hello World
# The simplest possible ApkPy app.
# Run it with: python 01_hello_world.py

from apkpy_lib import Screen, label, button, toast, run

# Create the screen
home = Screen(id="home")

# Add some UI
label("Hello, ApkPy! 👋", id="title", screen=home)
label("Your first Python-powered Android app.", id="subtitle", screen=home)

def on_press():
    toast("It works! 🎉")

button("Press Me", id="btn", command=on_press, screen=home)

# Style it
style = """
home {
    background-color: #1a1a2e;
    flex-direction: column;
    gap: 20px;
    padding: 40px;
}

title {
    color: #e94560;
    font-size: 28px;
    font-weight: bold;
    animation-name: fadeIn;
    animation-duration: 800ms;
}

subtitle {
    color: #a8a8b3;
    font-size: 16px;
}

btn {
    background-color: #e94560;
    color: white;
    border-radius: 25px;
    padding: 15px 30px;
    font-size: 18px;
    font-weight: bold;
    pressed-color: #c73652;
    margin-top: 20px;
    animation-name: fadeInUp;
    animation-duration: 1000ms;
}

@keyframes fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
}

@keyframes fadeInUp {
    from { opacity: 0; margin-top: 30px; }
    to   { opacity: 1; margin-top: 0px; }
}
"""

if __name__ == "__main__":
    run(start_screen=home)
