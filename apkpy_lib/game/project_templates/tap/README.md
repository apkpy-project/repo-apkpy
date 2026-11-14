# Quick Pop

A reflex game to build on: stars pop up all over the screen and each must be tapped before it goes. The bombs must not.

```
python writehere.py                 # on the PC: the app, in the Previewer; press Play
apkpy game play                     # on the PC: only the game, in a window
apkpy run --usb                     # on a phone
```

**How to play:** Tap the stars: 1 point, and 3 for the blue ones, which go sooner. 40 seconds. Eight stars missed, or three bombs tapped, and it ends early.

## Change it in the Studio

```
apkpy game studio
```

One window for the whole game, and you write no code: it writes `game/main.py` for you, and you can read what it
wrote. A check of the project is always at the bottom.

| Section | What you change there |
|---|---|
| **Objects** | The star (its points, how long it stays), the bomb, the burst when one is tapped |
| **Scenes** | How often each thing pops up and where (each `Spawner`), the clock, the rules that end the game |

**Art** draws any picture of `assets/` pixel by pixel, **Sounds** makes a new sound or tune, **My game** has the
name, the icon and the numbers the game starts with, and **Publish** makes the file for the phone or the store.

## Change it in the code

| File | What it is |
|---|---|
| `game/main.py` | The game: the objects (`@prefab`) and the scene |
| `writehere.py` | The app around the game: the title, the pause and the result screens, the best score, the words in English and Portuguese |
| `assets/` | The pictures and the sounds |

The Studio and the code are the same thing: change one and the other follows.

## Ideas

- A golden star worth 10 that stays half a second: another `Spawner` with a long `every`.
- More time for a good run: a star that does `var_add("time", 2)`.
- Levels: a second scene with faster spawners, opened by a rule at a score.
- Stars that move: add a `Mover` to the star.
