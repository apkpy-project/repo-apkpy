# 2. Make the project

Your game goes in one file, but an Android app also needs two small files around it. You write them once and never need to touch them again.

Make a folder for your game, and go into it:

```bash
mkdir my_square
```
```bash
cd my_square
```

## `apkpy.toml`: the app's name

Create a file called `apkpy.toml` with this inside:

```toml
[app]
name = "My Square"
application_id = "com.example.mysquare"
version_name = "0.1.0"
version_code = 1
```

- `name` is what the phone shows under the icon.
- `application_id` is the app's unique id. Two apps with the same id replace each other on a phone, so give each game its own.

## `writehere.py`: the app that opens the game

Create a file called `writehere.py` with this inside:

```python
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
```

You do not need to understand this file yet. It says: when the app opens, start the game; when the game ends, close the app.

`enable_game()` is what connects the app to the game: it gives the app `game_play` and the other functions that talk to a game.

Next: [3. A white screen](03-white-screen.md)
