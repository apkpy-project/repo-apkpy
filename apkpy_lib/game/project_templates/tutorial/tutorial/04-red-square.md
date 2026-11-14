# 4. A red square

Add one line to the end of `game/main.py`, so the whole file is:

```python
from apkpy_lib.game import *

game = Game("Tutorial", size=(360, 640), scale="expand", orientation="portrait", background="#ffffff")

main = game.scene("main", start=True)
main.add(Entity("square", Shape(size=(60, 60), color="#ff0000")), at=(180, 320))
```

Run it again:

```bash
apkpy game play
```

There is a red square in the middle of the white screen.

## What the new line means

Read it from the inside out:

| Part | Meaning |
|---|---|
| `Shape(size=(60, 60), color="#ff0000")` | Draws a rectangle, 60 by 60 units. `#ff0000` is red |
| `Entity("square", ...)` | An **entity** is one thing in the game. It has a name and a list of **components**, which are what it can do. So far it has one: it draws a shape |
| `main.add(..., at=(180, 320))` | Puts it in the scene, at that position |

## Where things are

Positions count from the **top left** corner of the screen:

- `x` goes to the right: 0 is the left edge.
- `y` goes **down**: 0 is the top edge, and bigger numbers are lower on the screen.

So `(180, 320)` is half of 360 and half of 640: the middle. The position is the **centre** of the square.

Next: [5. Follow the finger](05-follow-the-finger.md)
