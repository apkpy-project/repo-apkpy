# Keys of the Keep

A top-down adventure to build on: rooms, keys, doors, chests with gems, slimes, and stairs down. Two floors.

```
python writehere.py                 # on the PC: the app, in the Previewer; press Play
apkpy game play                     # on the PC: only the game, in a window
apkpy run --usb                     # on a phone
```

**How to play:** Touch where to go (or use the arrow keys). A key opens one door, and there are more doors than keys, so choose. A slime costs one of three lives and sends you back to where the floor starts.

## Change it in the Studio

```
apkpy game studio
```

One window for the whole game, and you write no code: it writes `game/main.py` for you, and you can read what it
wrote. A check of the project is always at the bottom.

| Section | What you change there |
|---|---|
| **Levels** | Paint the walls and the water, and place the hero, keys, doors, chests, slimes and the stairs |
| **Objects** | The hero (its speed), the key, the door (what it asks for), the chest, the slime (how far it walks), the stairs |
| **Scenes** | One scene for each floor: the camera that follows the hero, the music, the rule that ends the game |

**Art** draws any picture of `assets/` pixel by pixel, **Sounds** makes a new sound or tune, **My game** has the
name, the icon and the numbers the game starts with, and **Publish** makes the file for the phone or the store.

## Change it in the code

| File | What it is |
|---|---|
| `game/main.py` | The game: the objects (`@prefab`) and one scene for each floor |
| `writehere.py` | The app around the game: the title, the pause and the result screens, the best score, the words in English and Portuguese |
| `levels/` | The two floors, as Tiled files (`.tmj`): open them in the Studio's Levels or in Tiled |
| `assets/` | The pictures and the sounds |

The Studio and the code are the same thing: change one and the other follows.

## Ideas

- A third floor: **New level...** in Levels, a scene for it, and make the stairs of floor 2 go to it.
- A door that asks for gems: `only_if("gems >= 3", ...)` on a copy of the door.
- A heart that gives a life: a copy of the chest with `var_add("lives")`.
- A chest that needs a key: `only_if("keys >= 1", var_add("keys", -1), var_add("gems", 3), destroy())`.
