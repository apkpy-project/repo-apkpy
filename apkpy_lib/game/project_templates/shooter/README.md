# Star Guard

A shooter to build on: the ship at the bottom fires by itself, rocks fall, and the second wave brings saucers that fire back.

```
python writehere.py                 # on the PC: the app, in the Previewer; press Play
apkpy game play                     # on the PC: only the game, in a window
apkpy run --usb                     # on a phone
```

**How to play:** Slide a finger (or use the arrow keys) to move the ship. A rock is 1 point and a saucer 3; 15 points open wave 2 and 45 win. A heart gives a life.

## Change it in the Studio

```
apkpy game studio
```

One window for the whole game, and you write no code: it writes `game/main.py` for you, and you can read what it
wrote. A check of the project is always at the bottom.

| Section | What you change there |
|---|---|
| **Objects** | The ship (its speed, how often it fires), the bullet, the rocks, the saucer and its shot, the heart, the explosions |
| **Scenes** | The two waves: what falls and how often (each `Spawner`), the score that opens the next wave, the music |

**Art** draws any picture of `assets/` pixel by pixel, **Sounds** makes a new sound or tune, **My game** has the
name, the icon and the numbers the game starts with, and **Publish** makes the file for the phone or the store.

## Change it in the code

| File | What it is |
|---|---|
| `game/main.py` | The game: the objects (`@prefab`) and one scene for each wave |
| `writehere.py` | The app around the game: the title, the pause and the result screens, the best score, the words in English and Portuguese |
| `assets/` | The pictures and the sounds |

The Studio and the code are the same thing: change one and the other follows.

## Ideas

- A third wave: a new scene in Scenes, and change wave 2's rule to go to it.
- A shield: an object like the heart that sets a variable, and `only_if("shield <= 0", ...)` around what a hit does.
- A boss: a saucer without its `Lifetime`, a variable for its strength and a rule for when it reaches 0.
- Two bullets at once: a second `Timer` on the ship with another `offset`.
