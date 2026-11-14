from apkpy_lib import *

enable_game()

# The app around the game: it opens the game at once, and closes when the game ends.
home = Screen(id="home")

close_app = native.java(
    "closeApp",
    imports=["android.app.Activity"],
    code="((Activity) context).finish(); return \"\";",
    preview=lambda: "",
)


def finished(ok, value):
    close_app()


def opened():
    game_play("main", "{}", on_result=finished)


label("", id="blank", screen=home)
lifecycle(home, on_resume=opened)

run(start_screen=home, theme=Theme(mode="light"))
