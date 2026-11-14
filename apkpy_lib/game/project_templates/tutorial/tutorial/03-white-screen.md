# 3. A white screen

Make a folder called `game`, and in it a file called `main.py` (so: `game/main.py`), with this inside:

```python
from apkpy_lib.game import *

game = Game("Tutorial", size=(360, 640), scale="expand", orientation="portrait", background="#ffffff")

main = game.scene("main", start=True)
```

Now run it on your computer:

```bash
apkpy game play
```

A window opens, all white. That is your game. Close the window when you have seen it.

## What each part means

**`from apkpy_lib.game import *`** gives you all the names used below.

**`Game(...)`** describes the whole game:

| Part | Meaning |
|---|---|
| `"Tutorial"` | The game's name |
| `size=(360, 640)` | The game's screen is 360 units wide and 640 tall, whatever the phone |
| `scale="expand"` | On a phone of another shape, show more of the game instead of black bars |
| `orientation="portrait"` | Hold the phone upright |
| `background="#ffffff"` | The colour behind everything. `#ffffff` is white |

**`game.scene("main", start=True)`** makes a scene. A scene is one "place" of a game, like a level or a menu, and this game only needs one. `start=True` says the game begins here. `"main"` is the same name that `writehere.py` opens with `game_play("main", ...)`.

Next: [4. A red square](04-red-square.md)
