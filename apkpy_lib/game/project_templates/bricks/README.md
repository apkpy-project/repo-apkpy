# Brickfall

A brick breaker to build on: a paddle, a ball that bounces, and two levels of bricks.

```
python writehere.py                 # on the PC: the app, in the Previewer; press Play
apkpy game play                     # on the PC: only the game, in a window
apkpy run --usb                     # on a phone
```

**How to play:** Slide a finger (or use the arrow keys) to move the paddle and keep the ball up. The ball leaves the paddle turned by where it landed: straight up from the middle, to the sides from the ends, so you aim it. Break every brick to go on. A ball that falls costs one of three lives.

## Change it in the Studio

```
apkpy game studio
```

One window for the whole game, and you write no code: it writes `game/main.py` for you, and you can read what it
wrote. A check of the project is always at the bottom.

| Section | What you change there |
|---|---|
| **Levels** | Place the bricks: each colour is a kind of brick (blue and purple are worth more) |
| **Objects** | The brick (its points), the ball (its speed, and `deflect`: how much the paddle turns it), the paddle (its width, its speed), the walls |
| **Scenes** | One scene for each level, and the rule that goes on when no brick is left |

**Art** draws any picture of `assets/` pixel by pixel, **Sounds** makes a new sound or tune, **My game** has the
name, the icon and the numbers the game starts with, and **Publish** makes the file for the phone or the store.

## Change it in the code

| File | What it is |
|---|---|
| `game/main.py` | The game: the objects (`@prefab`) and one scene for each level |
| `writehere.py` | The app around the game: the title, the pause and the result screens, the best score, the words in English and Portuguese |
| `levels/` | Where the bricks are, as Tiled files (`.tmj`): open them in the Studio's Levels or in Tiled |
| `assets/` | The pictures and the sounds |

The Studio and the code are the same thing: change one and the other follows.

## Ideas

- A third level: **New level...** in Levels, and a scene for it.
- A brick worth more: another colour in the scene's `objects={...}`, with its points.
- A prize that falls from a brick: `spawn(...)` an object with a `Mover`, and the paddle catches it for a life.
- A wider paddle, a faster ball: two numbers in Objects.
