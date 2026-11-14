# Gem Valley

A small 2.5D world to build on: a valley seen from above at an angle, with houses, trees, a pond, a villager, and four lanterns to find.

```
python writehere.py                 # on the PC: the app, in the Previewer; press Play
apkpy game play                     # on the PC: only the game, in a window
apkpy run --usb                     # on a phone
```

**How to play:** Tap a place to walk there (or use the arrow keys). Find the four lanterns.

## Change it in the Studio

```
apkpy game studio
```

One window for the whole game, and you write no code: it writes `game/main.py` for you, and you can read what it
wrote. A check of the project is always at the bottom.

| Section | What you change there |
|---|---|
| **Levels** | Paint the ground, the paths, the hedges and the water, and place the hero, houses, trees, lanterns and people. It is the same editor as for a flat game: the engine raises what you paint |
| **Objects** | The hero (its speed), the houses (their size, roof and walls), the trees, the lantern and what finding one does |
| **Scenes** | The camera (how steep, how far, the fog), the music, the rule that ends the game |

**Art** draws any picture of `assets/` pixel by pixel, **Sounds** makes a new sound or tune, **My game** has the
name, the icon and the numbers the game starts with, and **Publish** makes the file for the phone or the store.

## Change it in the code

| File | What it is |
|---|---|
| `game/main.py` | The game: the objects (`@prefab`) and the scene, which is `kind="2.5d"` |
| `writehere.py` | The app around the game: the title, the pause and the result screens, the best score, the words in English and Portuguese |
| `levels/` | The valley, as a Tiled file (`.tmj`): open it in the Studio's Levels or in Tiled |
| `assets/` | The pictures and the sounds |

The Studio and the code are the same thing: change one and the other follows.

## Ideas

- A bigger valley: **Size...** in Levels, and paint more of it.
- A hill: a tile with the Tiled property `height` is raised (the hedge is, by 1).
- A second place: another level and another scene, and an object that goes to it (`goto_scene`).
- Gems to find too: a copy of the lantern with a variable of its own, and a rule that waits for both.
