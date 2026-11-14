# 5. Wild monsters

Let us give Sam a cellar with reeds growing in it. Ask for a small map, then look at it:

```bash
python tools/new.py map cellar
```

It is only walls and grass. Replace it. Create `maps_src/cellar.map`:

```
# Sam's cellar. Something grows down here.
tiles:
cccccccc
c.rrrr.c
c.rrrr.c
c......c
cccccccc
objects:
link 1 3 sam_house
```

The letter `r` is reeds with a **zone**: monsters can come out of it. `link` joins two maps, so `sam_house` needs one back to here. Add to `maps_src/sam_house.map`:

```
link 6 1 cellar
```

Now say what comes out of the reeds in this map:

```bash
python tools/new.py wild cellar reeds spark_toad pebblit
```

Walk in the reeds, and something jumps out. You can tune how often and how strong in `data/encounters.json`.

Next: [6. A trainer](06-a-trainer.md)
