# 5. Follow the finger

To make the square move, give the entity one more component. Change the last line, so the whole file is:

```python
from apkpy_lib.game import *

game = Game("Tutorial", size=(360, 640), scale="expand", orientation="portrait", background="#ffffff")

main = game.scene("main", start=True)
main.add(Entity("square", Shape(size=(60, 60), color="#ff0000"), TopDownController(speed=600, clamp=False)), at=(180, 320))
```

Run it:

```bash
apkpy game play
```

Hold the mouse button down anywhere in the window: the square goes there. Move the mouse and it follows. On the computer, the mouse is your finger.

**The game is finished.** This is the same file as [`game/main.py`](../game/main.py) in this folder.

## What the new part means

`TopDownController` is a ready-made component that moves its entity towards the finger while the finger is down.

| Part | Meaning |
|---|---|
| `speed=600` | How fast it moves: 600 units per second. It crosses the 360 wide screen in just over half a second |
| `clamp=False` | Let it go anywhere. By default it stays inside the 360 by 640 area, but a long phone shows more than that, and the square could not reach your finger there |

It also moves with the arrow keys or WASD, if you press them on the computer. You did not ask for that, but it comes with the component.

You wrote no code that runs: no loop, no reading the finger, no moving by hand. You described a square that has this component, and the engine does the rest. This is how most of a game is made: an entity, plus the components that give it what it needs.

Next: [6. On your phone](06-on-your-phone.md)
