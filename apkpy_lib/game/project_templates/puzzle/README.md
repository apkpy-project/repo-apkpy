# Lights Off

A grid puzzle to build on: a tap turns a light and the four next to it, and every light must go off. Five boards.

```
python writehere.py                 # on the PC: the app, in the Previewer; press Play
apkpy game play                     # on the PC: only the game, in a window
apkpy run --usb                     # on a phone
```

**How to play:** Tap a light. Fewer moves, more points.

## Change it in the Studio

```
apkpy game studio
```

One window for the whole game, and you write no code: it writes `game/main.py` for you, and you can read what it
wrote. A check of the project is always at the bottom.

| Section | What you change there |
|---|---|
| **Objects** | The tile and the lamp (colours, sizes), and the board's settings: its levels, its size, where it is on the screen |
| **Scenes** | The texts on the screen and the music |

**Art** draws any picture of `assets/` pixel by pixel, **Sounds** makes a new sound or tune, **My game** has the
name, the icon and the numbers the game starts with, and **Publish** makes the file for the phone or the store.

## Change it in the code

| File | What it is |
|---|---|
| `game/main.py` | The game: the lamp and the tile (`@prefab`), and `Board`, a small `Script` with the rules: about 70 lines of Python, which the build turns into the phone's code |
| `writehere.py` | The app around the game: the title, the pause and the result screens, the best score, the words in English and Portuguese |
| `assets/` | The pictures and the sounds |

The Studio and the code are the same thing: change one and the other follows.

## Ideas

- More boards: a level is 25 letters, `1` a light on and `0` off, the rows one after the other. Add them to `LEVELS` and raise `count`. Start from a dark board and press a few lights: a board made that way can always be solved.
- A bigger board: `size` 6, and 36 letters for each level.
- Another rule: change `update` so a tap turns the whole row and column.
- This is the template to read when a game needs rules of its own: `Board` shows how a `Script` reads taps, makes objects and ends the game.
