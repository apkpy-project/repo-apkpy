# Hop Hills

A platformer to build on: run, jump, take the coins, jump on the slimes, and reach the flag. Two levels.

```
python writehere.py                 # on the PC: the app, in the Previewer; press Play
apkpy game play                     # on the PC: only the game, in a window
apkpy run --usb                     # on a phone
```

**How to play:** Left and right to run, jump with the button on the right (arrow keys and Space on the PC). Hold the jump to go higher. A slime touched from the side, or a fall, costs one of three lives.

## Change it in the Studio

```
apkpy game studio
```

One window for the whole game, and you write no code: it writes `game/main.py` for you, and you can read what it
wrote. A check of the project is always at the bottom.

| Section | What you change there |
|---|---|
| **Levels** | Paint the ground and the platforms, and place coins, slimes, the player and the flag. **New level...** starts another one |
| **Objects** | The player (how fast it runs, how high it jumps), the coin, the slime, the flag: each with its picture, its animations and what happens when it is touched |
| **Scenes** | One scene for each level: its music, its camera, the buttons on the screen and the rule that ends the game |

**Art** draws any picture of `assets/` pixel by pixel, **Sounds** makes a new sound or tune, **My game** has the
name, the icon and the numbers the game starts with, and **Publish** makes the file for the phone or the store.

## Change it in the code

| File | What it is |
|---|---|
| `game/main.py` | The game: the objects (`@prefab`) and one scene for each level |
| `writehere.py` | The app around the game: the title, the pause and the result screens, the best score, the words in English and Portuguese |
| `levels/` | The two levels, as Tiled files (`.tmj`): open them in the Studio's Levels or in Tiled |
| `assets/` | The pictures and the sounds |

The Studio and the code are the same thing: change one and the other follows.

## Ideas

- A third level: **New level...** in Levels, then a scene for it in Scenes, and make the flag of level 2 go to it.
- A spring: an object with `OnCollide("player", impulse((0, -420), "other"))`.
- A gate that needs coins: `OnCollide("player", only_if("coins >= 5", destroy()))` on a solid object.
- A second kind of slime, faster, with another tint.
