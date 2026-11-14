# The Studio

The Studio is one window to make your game. Open it in your project's folder:

```
apkpy game studio
```

It reads and writes only your project's own files, so you can also change them by hand, in any editor, and build with
plain ApkPy. Nothing in your game depends on the Studio. What you change here is written into your game's Python as
you would write it, and only that line: open `game/main.py` to see it.

## The sections

- **Play**: your game, inside the window, with the same engine as on the phone. Pick the scene it starts from. Click
  the game first; then the arrow keys and space play, Esc is the phone's Back button, and the mouse is a finger.
- **My game**: the name under the icon, the app id, the version, and the icon; then the game's size, orientation,
  scaling, background, and its variables (score, lives...): a text shows one as `{score}`.
- **Objects**: the things of your game, each a `@prefab` in your code. Each part (a picture, a body, a controller,
  what happens on a touch...) is a card: change its settings, add one from "Add a component", or take it away. Your
  own `Script` classes are there too, as behaviours. An `Animator` plays each animation beside its line.
- **Scenes**: the places of your game. For each: its settings, its camera, its rules ("when lives <= 0, the game
  ends"), and what is in it. "Add to the scene" puts an object, a text on the screen, a shape or a level in it.
- **Levels**: maps of tiles, the files Tiled makes (`.tmj`): paint tiles (left button) and erase (right button), fill,
  pick a tile from the level, place objects on an object layer and drag them, mark a layer solid. New level makes one,
  with a starter set of tiles if you have none.
- **Sounds**: listen to each sound, bring one in, or make one: pick a kind (jump, coin, laser...), Play, "Another
  one" until you like it, then "Keep it". "Make a tune" does the same for music.
- **Data**: one section for each data table of your game, if it has any. A table is a `@dataclass` and a
  `table("data/enemies", Enemy)` line in your code; the comment at the end of a field's line is its help here.
- **Art**: every picture in `assets/`. Draw pixel by pixel (P pencil, E eraser, G fill, I pick a colour), import a
  picture, flip, copy and paste a frame. A picture your code cuts in frames, `assets.sheet("assets/hero.png",
  frame=(16, 16))`, shows its frames, and its preview plays them.
- **Publish**: a test version, a signed version, a file for the Play Store, and your phone: install, open, read
  what the game says.
- **Copies**: a copy of your project is made when the Studio opens, before the first save, and before anything big.
  Go back to one at any time.

## At the bottom

The line at the bottom says what the build says about your saved files. Click it to see each problem, and click a
problem to go where it is.

## Another game

**New game...**, at the bottom of the side bar, makes another game in a folder beside this one: choose the kind from
its picture (a platformer, a shooter, a runner, a brick breaker, an adventure, a tap game, a puzzle, a 2.5D world,
the monster RPG, or an empty one), give it a name, and it opens in a Studio of its own. This one stays open.
`apkpy game studio` in a folder with no project starts the same way.

## Keys

Ctrl+S saves everything. Ctrl+Z and Ctrl+Y undo and redo in the section you are in.
