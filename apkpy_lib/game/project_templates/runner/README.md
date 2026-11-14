# Rooftop Run

An endless runner to build on: the runner never stops, and the crates, the birds and the coins come to it.

```
python writehere.py                 # on the PC: the app, in the Previewer; press Play
apkpy game play                     # on the PC: only the game, in a window
apkpy run --usb                     # on a phone
```

**How to play:** A tap (or Space) is a hop over a crate. Held, it is a high jump, which reaches the coins. The birds fly high: a hop goes under them, a high jump does not. After 120 m it gets faster; 300 m wins.

## Change it in the Studio

```
apkpy game studio
```

One window for the whole game, and you write no code: it writes `game/main.py` for you, and you can read what it
wrote. A check of the project is always at the bottom.

| Section | What you change there |
|---|---|
| **Objects** | The runner (how high it jumps), the crate, the bird, the coin, the cloud: each with its speed |
| **Scenes** | The two speeds of the run: how often each thing comes (each `Spawner`), how far before it gets faster, how far to win |

**Art** draws any picture of `assets/` pixel by pixel, **Sounds** makes a new sound or tune, **My game** has the
name, the icon and the numbers the game starts with, and **Publish** makes the file for the phone or the store.

## Change it in the code

| File | What it is |
|---|---|
| `game/main.py` | The game: the objects (`@prefab`) and one scene for each speed |
| `writehere.py` | The app around the game: the title, the pause and the result screens, the best score, the words in English and Portuguese |
| `assets/` | The pictures and the sounds |

The Studio and the code are the same thing: change one and the other follows.

## Ideas

- Make it endless: take away the rule that wins at 300 m, and the distance is the score.
- A shield: a rare object from its own `Spawner` that sets a variable.
- A third speed, at night: a new scene with another `background`.
- A tall crate that only the high jump clears: a copy of the crate with a taller picture and `Collider`.
