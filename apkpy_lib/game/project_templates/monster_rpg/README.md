# Monster RPG template

The opening of a monster-catching RPG, to build your own game on. It is called *Saltmere* here: a village, a house, a road, a lighthouse, a rival. The story, the creatures and all the art are placeholders made for this template; replace what you like.

```
apkpy start MyGame --game monster-rpg
cd MyGame
apkpy game play                     # on the PC
apkpy run --usb                     # on a phone
```

**The easy way:** `apkpy game studio` (or `python tools/studio.py`) opens the Studio, one window for your maps, story, monsters, moves, types, items, shops, trainers, wild monsters, art and sound, with a check of the whole project always at the bottom. It only reads and writes the files described below, so you can use it, change them by hand, or both.

**New here? Do the [tutorial](tutorial/README.md).** In a few short steps you change the story, add a monster, a person, a house with a room inside, wild monsters and a trainer. You do not write any code.

## How it works

You change files, and every build (including `play`) prepares them for you: it draws missing art, reads your maps and your story, and checks that everything points at something that exists. If something is wrong, it says which file and line. To run only that part: `python tools/prepare.py`.

**Words you will meet**

| Word | What it is |
|---|---|
| map | A place: the village, a room. A text file in `maps_src/` |
| tile | One square of a map's ground. A picture in `assets/tiles/` |
| object | Anything standing on a map: a person, a tree, a door |
| event | What happens when you talk to someone or step somewhere. It is written in `story/` |
| flag | A name the game remembers, such as `got_partner`. You make them up: `set got_partner` in the story, and `if got_partner:` later |
| zone | Ground that wild monsters come out of, such as reeds |
| marker | A named spot on a map, for arriving at. Links and buildings make their own |

## The Studio

```
apkpy game studio
```

| Section | What it does |
|---|---|
| **Play** | The real game, inside the window |
| **Test** | **Start a test** anywhere with the team, items, flags and money you choose. **Try a fight** many times. **Balance** shows every fight against every starter. **World** shows your maps and how they connect. **Forgotten** lists what is probably a mistake, such as a monster that never appears or a map with no way in |
| **Maps** | The map editor |
| **Story** | The story editor. **Test this event** plays the one the cursor is in, beside whatever starts it |
| **My game** | Its name and version, how it starts, the starters, the title's monsters, the money's name |
| **Monsters** | Stats, types, moves, evolution, pictures and variants |
| **Moves**, **Items**, **Shops**, **Natures** | Everything about each one |
| **Effects**, **Statuses** | What moves do besides damage, and what monsters can suffer from |
| **Rules** | The numbers of battles and of growing |
| **Words** | Everything the game says |
| **Types** | Their colours, and a table of what each does to the others: click a cell to change it |
| **Trainers** | Their team, reward and what they say: the button opens the story on them |
| **Wild monsters** | What comes out of each zone of each map, with each one's chance worked out for you |
| **Art** | Draw monsters, people, tiles and everything else, pixel by pixel, at the right sizes. People walk in the preview, and tiles repeat. **Import a picture** takes any picture: the whole sheet, or one cell, made to fit |
| **Title and icon** | The word on the title screen, the phone's icon (a picture, or one of your monsters), and the font with its sizes |
| **Music and sound** | Each place's music, volume and background. Listen to any sound, replace it, or add a piece of music. WAV, OGG and MP3 all work |
| **Publish** | Install on your phone, open it, and read what it says. Make a test version, a signed version, or one for the Play Store. It lists what to look at first, and saves a copy of your signing key |
| **Copies** | The automatic copies of your project, to go back to. They are in `.studio_backups/`, and the last 20 are kept |
| **Help** | [How to use the Studio](tutorial/studio.md), the tutorial and this page |

The forms come from `game/data/defs.py`: add a field there, and it shows up. Each row says where it is used, and each of those is a link.

A `*` beside a section means it has changes to save. Ctrl+S saves everything, and Ctrl+Z and Ctrl+Y undo and redo in the section you are in.

**Rename everywhere** changes an id in every file that names it, after making a copy. **Delete** refuses while something uses that row, and says what.

The bottom line says what the build thinks of your saved files. Click it to see each problem, and click a problem to go there.

## What to change, from easiest to hardest

### 1. Content: no code

| To change | Go to |
|---|---|
| How the game starts, the starters, the money's name | `data/game.json` |
| What people say, and what happens | `story/*.story` |
| Maps | `maps_src/*.map`, or `python tools/map_editor.py village` to paint them |
| Monsters | `data/species/` |
| Moves, types, items, shops, trainers, wild monsters | `data/*.json` |

### 2. The look: no code

| To change | Go to |
|---|---|
| A monster | `assets/monsters/<id>.png`: two cells of 64 x 64, its front then its back |
| A person | `assets/people/<look>.png`: cells of 16 x 24, a row per direction (down, left, up, right), four columns (standing, a step, standing, the other step) |
| A tile | `assets/tiles/<name>.png`: 16 x 16 |
| Everything else | The other pictures in `assets/`: draw over them |

`python tools/make_art.py` only draws files that are missing, so your art is safe. To get a placeholder back, delete the file.

### 3. The rules: with code

| To change | Go to |
|---|---|
| Stats, damage, capture | `game/rules/` |
| How battles work | `game/battle/`: `engine.py` decides, `presenter.py` shows |
| Kinds of objects, the hero | `game/world/prefabs.py`, and the list `OBJECTS` in `game/main.py` |
| Screens and menus | `game/ui/`. `kit.py` holds the font, the box and the colours |
| What is saved | `game/state/store.py` |

**Before you change code:** the files in `game/` are read and translated to Java, never run as Python. So code has a few rules (no list comprehensions, no `try`, no tuples, no keyword arguments in plain function calls), and the build says so if you break one. The games guide and its reference (https://repo-apkpy.pages.dev/games/) list what code can do.

## Recipes

### A monster

```
python tools/new.py monster spark_toad ember
```

This writes `data/species/spark_toad.json` and placeholder sprites. Then put it somewhere: `python tools/new.py wild route reeds spark_toad`, a trainer's team, or `give monster spark_toad 5` in the story.

| Field | What it means |
|---|---|
| `types` | One or two, from `data/types.json` |
| `base` | Its stats. The placeholders go from about 30 (weak) to about 110 (strong) |
| `learnset` | The moves it learns, and at which level |
| `catch_rate` | 1 (very hard) to 255 (very easy) |
| `exp_yield` | How much experience it gives. About 50 for a weak one |
| `ev_stat` | The stat that grows a little when you beat one |
| `evolves_to`, `evolve_level` | Optional: what it becomes, and at which level |
| `evolve_item`, `evolve_flag` | Optional: evolve with an item instead, or only once a flag is set |
| `variants` | Optional: other looks of it, as many as you like (see below) |

### Variants

A variant is another look of a monster, such as a rare golden one. Only the look changes: its stats, moves and everything else stay the same.

```json
"variants": [
  {"id": "gold", "name": "Gold", "one_in": 4096},
  {"id": "frost", "name": "Frost", "one_in": 0}
]
```

- **Its drawing:** `assets/monsters/<monster>.<id>.png`, such as `reedling.gold.png`, the same size as the usual one. If it is missing, the build draws the usual one in other colours, for you to draw over.
- **In the wild:** each variant has a chance of 1 in `one_in`, tried in order. `0` means it never appears in the wild, only with trainers. A monster with no variants is always the usual one.
- **A trainer's monster:** add `"variant": "gold"` to it in `data/trainers.json`. Without it, or with `"default"`, it has the usual look.
- **The player sees it:** in battle, in the team, and in the team's details, as "Variant: Gold" (or "default"; both words are in `data/texts.json`).
- **Evolving:** it keeps its variant if the monster it becomes has one with the same id, and goes back to the usual look if not.
- **In the Studio:** **Monsters**, then **+ Add a variant** at the bottom of the form. **Draw it in Art** opens its drawing. A trainer's team has a **Variant** column.

### A move, a type, an item

- **A move:** a row in `data/moves.json`, then name it in a monster's `learnset`. `kind` is `physical`, `special` or `status`. `effect` is one of `data/effects.json`, and `chance` its percent.
- **An effect:** a row in `data/effects.json`. It can give a status, move a stat up or down for the battle (`stat`, `amount`, on the `foe` or on `self`), or give HP back (`heal_percent`).
- **A status:** a row in `data/statuses.json`: what it says, the HP it takes each turn (`turn_share`), what it does to attacks (`attack_factor`), the turns it makes a monster miss (`min_turns`, `max_turns`), and how much easier it makes catching.
- **The rules:** `data/rules.json` has the numbers: clean hits, the bonus of a move of one's own type, the moves a monster can know, the team size, how fast monsters grow, what losing costs.
- **The words:** everything the game says is in `data/texts.json`, by id. `{name}`, `{count}` and the like are filled in. The tabs of the bag and of the team, and the music switch, still say their words in `game/ui/screens.py`.
- **A type:** a row in `data/types.json` (`strong`, `weak`, `immune`: what its moves do to those types), and name it in other types' lists.
- **An item:** a row in `data/items.json`. `kind` is the pocket of the bag (`heal`, `cure`, `capture` or `key`). What it does: `heal`, `cures` (or `cures_all`), `revive`, `capture`. To sell it, add it to a shop in `data/shops.json`. A monster with `evolve_item` evolves when that item is used on it.

### The map editor

```
python tools/map_editor.py
```

Your maps are on the left: click one to open it in a tab, or press **New map**. It reads and writes the same `.map` files, so you can also change them in a text editor.

| To | Do this |
|---|---|
| Paint | **Brush** (B), **Fill** (F) or **Rectangle** (R), with a tile from the left |
| Use a tile from the map | Right click it |
| Add an object | Pick it on the left and click on the map, or right click |
| Change or move an object | **Select** (V): click it, drag it, or use the arrow keys. Its fields are on the right, with the names that exist to choose from |
| Open the map behind a door | Double click the door or link |
| See a problem | The bottom line says what is wrong as you work. Click it to go there |
| Try it | Right click a cell: **Test the game from here**. In the Studio, you start there with what the Test section says. On its own, with your first starter, and flags start empty |
| Change the size | Select nothing: the panel on the right has **+** and **-** for each side |
| Rename a map | Pick it in the list, then **Rename...**. Its scene, the doors and links that lead to it, `warp` in the story, its wild monsters, `data/game.json` and its events (`route.sign` becomes `coast.sign`, and `story/route.story` becomes `story/coast.story`) change with it. Also `python tools/map_files.py rename route coast` |
| Delete a map | **Delete...** says first what goes: the map, its scene, its wild monsters, and the links and doors of other maps to it. Its story stays. The map where the game starts or where you wake up, or one the story warps to, has to be changed there first. A copy is kept, so **Copies** in the Studio brings it back |
| Paint 3D blocks | Pick a tile, then a **Height** on the left. A block starts solid; untick **Solid** for a hill you can walk up. The map shows each block's height |
| Copy part of a map | **Area** (A): drag a box, Ctrl+C or Ctrl+X, then Ctrl+V and click. It works between tabs, and it takes the objects too |
| See it as in the game | **See in 3D**, or right click a cell. It saves your maps, and the real game draws them |
| Write what someone says | Select them, then **Write what happens...**: the story opens on their event, and writes a first version if it has none. **Story** opens it on its own |

Undo and redo are Ctrl+Z and Ctrl+Y, for each tab. Ctrl+S saves, Ctrl+W closes a tab, Ctrl+wheel zooms. The tabs you had open come back next time.

### A map

```
python tools/new.py map cave
```

Paint it in the map editor, or write it by hand:

```
# A cave.
tiles:
cccccccc
c..rr..c
c..rr..c
c......c
ccc,,ccc
objects:
link 3 4 route width=2
person 5 2 old_man look=villager event=cave.old_man
```

The letters are in `maps_src/legend.txt`. A map can add its own above `tiles:`, such as `x = snow solid`. For a new tile, add a picture at `assets/tiles/snow.png`.

What a letter can say: `solid`, `height=N` (a 3D block, N tiles high), `zone=NAME` (wild monsters) and `edges`. With `edges`, the corners are cut where it meets other flat ground, so water and paths do not look square. To draw those cuts yourself, add `assets/tiles/<tile>_edges.png`: 4 x 4 cells of 16 x 16 with transparency, one per combination (add 1 for a cut at the top, 2 right, 4 bottom, 8 left).

The first build gives a new map a scene at the end of `game/main.py`, where you can change its camera, music and background.

Columns and rows count from 0, from the top left. `python tools/map_tool.py --view cave` writes a picture with a ruler, at `build/map_views/cave.png`. The editor shows the column and row in its title.

**Objects** are `<kind> <column> <row> [name] [key=value...]`:

| Object | What it does |
|---|---|
| `house_red 3 2 inside=house` | A building, by its top left corner. It makes its walls solid, puts a door in the middle of its front, and links it to the map `house`. The cell in front of the door must be free. The sizes are in `OBJECTS`, in `game/main.py` |
| `house_blue 14 2 event=village.locked` | A building whose door plays an event |
| `exit 3 6 width=2` | The way out of a map a building leads to. You walk against it |
| `link 10 0 route width=2` | Stepping here goes to the map `route`, which needs a `link` back here |
| `person 7 11 sam look=villager event=village.sam facing=left hide_if=some_flag` | Someone to talk to |
| `trainer 5 17 tess look=rival facing=right sight=3` | Sees you along their line, plays `trainer tess` from the story, and remembers it in the flag `beat_tess` |
| `sign`, `knot` | Things to read or pick up, with `event=` |
| `trigger 10 1 gate event=village.gate unless=got_partner` | An event when you step here. With that flag set, it is as if it were not there |
| `marker 10 13 start` | A named spot. Links and buildings make their own, called `from_<the other map>` |
| `tree 2 7`, `lighthouse 7 2 tower` | Scenery |

`width=` and `height=` repeat `link`, `exit`, `warp`, `door` and `trigger` over several cells.

For anything more unusual, `warp`, `door` and `exit` take `to=<map> at=<marker>`.

### A building of another size

Add a line to `OBJECTS` in `game/main.py`: `"barn": house(roof_red, 7, 4)` is 7 cells wide and 4 deep.

### Wild monsters

Give a letter a zone in `maps_src/legend.txt` (`r = reeds zone=reeds`), then say what comes out of it in that map:

```
python tools/new.py wild cave reeds pebblit gustlet
```

That adds a row `cave.reeds` to `data/encounters.json`, where you can tune `rate` and each monster's levels and `weight`. If a map's zone has no row, the build leaves a note, and nothing comes out of it. The letter `R` is the same tile with no zone, for decoration.

### The story

Story files are in `story/`. Write them in any text editor or in `python tools/story_editor.py`, which colours them, has a button for each kind of line and shows problems as you type. The full list of what you can write is at the top of `tools/story_tool.py`.

```
event cave.old_man
    once met_old_man:
        say Nobody has come down here for years. Take this.
        give tonic 3
    otherwise:
        say Mind the reeds.
```

| Line | What it does |
|---|---|
| `say TEXT` | The dialog box |
| `ask TEXT`, then `yes:` and `no:` blocks | A question |
| `if FLAG:` / `if not FLAG:`, optionally `otherwise:` | Only sometimes |
| `once [FLAG]:`, optionally `otherwise:` | Only the first time |
| `set FLAG` / `clear FLAG` | Remember or forget |
| `give ITEM [COUNT]`, `give money COUNT`, `give monster SPECIES [LEVEL]` | Gifts |
| `heal` | The whole team |
| `open SCREEN` | `menu`, `team`, `bag`, `dex`, `options`, `save` or `starter`. It waits for it to close |
| `shop SHOP` | Opens a shop |
| `battle TRAINER` | A fight. If you lose, the event stops |
| `warp MAP MARKER` | Another map |
| `step_back` | The hero goes back one cell |
| `end` | Stops here |

The game reads `data/events/*.json`. Your story becomes `data/events/_story.json`, which is rewritten each time, so do not edit that one. You can also add your own JSON files there.

A new kind of line takes four changes: an `elif` in `EventRunner.do` (`game/world/events.py`), any new field in `Step` (`game/data/defs.py`), its name in `STEPS` (`tools/validate_data.py`), and how it is written, in `command` (`tools/story_tool.py`).

### A trainer

```
python tools/new.py trainer tess pebblit:3 gustlet:4
```

In a story file:

```
trainer tess
    before:
        say Halt!
    won:
        say You tie a good knot.
    after:
        say The road is open.
```

On a map:

```
trainer 5 17 tess look=villager facing=right
```

### A person's look

`python tools/new.py person sam` draws `assets/people/sam.png`, to draw over. Then use `look=sam` on a map.

### How hard is it?

`python tools/balance.py` plays each wild monster and trainer many times with each starter, and prints how often it wins and how much HP it has left. The tests fail if a starter wins less than 80% of the fights named in `fair_fights`, in `data/game.json`: list there the fights that come first in your game. Tune the levels in `data/encounters.json` and `data/trainers.json` (with `expect_level`, how strong your partner should be by that fight), and the `base` of the species.

## In Tiled

The text maps are the simplest way, and the only source: everything in `maps/` is generated from them (do not edit it), and the build refuses to overwrite a `.tmj` that was changed by hand.

To go on with one map in [Tiled](https://www.mapeditor.org/) instead, delete its `.map`. Then its `maps/<name>.tmj` is the map, and the tools leave it alone. Another map's `link` and `inside=` can no longer find it, so use `to=` and `at=` with it.

## Checking the game

```
python tools/prepare.py             # the content
python -m pytest tests              # the rules, with your data
```

**Optional, for those who know Java:** `python tools/advanced/play_bot.py` plays the whole opening with keys and taps, using `tools/advanced/bot/Bot.java`. It follows the placeholder story step by step, so change `Bot.play()` or delete `tools/advanced/` once you replace the story.

## What is left to you

- Saves are one slot (`slot1`), written at each warp and from the Save screen.
- Only the player gets a name; nicknames are in the save (`Monster.nickname`) with no screen yet.
- Everyone grows alike (`exp_for_level` in `game/rules/monsters.py`).
- Text is in one language, in the data files: `data/texts.json` for what the rules and screens say.
- There are no held items or abilities, and no day and night.
