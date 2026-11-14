# 7. Try changing things

The best way to learn the rest is to change one thing at a time and run the game again with `apkpy game play`.

## Easy changes

| Change | Result |
|---|---|
| `color="#ff0000"` to `color="#0066ff"` | A blue square |
| `background="#ffffff"` to `background="#000000"` | A black screen |
| `size=(60, 60)` to `size=(20, 120)` | A tall, thin rectangle |
| `Shape(size=(60, 60), ...)` to `Shape(shape="circle", radius=30, ...)` | A circle |
| `speed=600` to `speed=100` | It moves slowly, and you see it chase your finger |
| `at=(180, 320)` to `at=(180, 50)` | It starts near the top |

## Jump to the finger, with your own code

`TopDownController` slides the square to your finger. To make it **jump** there at once, you need something it does not do, so you write it yourself. Code that runs in the game goes in a **Script**:

```python
from apkpy_lib.game import *

game = Game("Tutorial", size=(360, 640), scale="expand", orientation="portrait", background="#ffffff")


class FollowFinger(Script):
    def update(self, dt: float):
        if input.pointer_down():
            self.x = input.pointer_x()
            self.y = input.pointer_y()


main = game.scene("main", start=True)
main.add(Entity("square", Shape(size=(60, 60), color="#ff0000"), FollowFinger()), at=(180, 320))
```

A script is a component you write. The engine calls its `update` once per step of the game, many times a second. This one says: if the finger is down, put me where the finger is.

## Where next

- [`docs/guide.md`](../../../docs/guide.md) makes a real game, step by step: scripts, sounds, collisions, menus.
- [`docs/reference.md`](../../../docs/reference.md) lists every component and what it can do.
