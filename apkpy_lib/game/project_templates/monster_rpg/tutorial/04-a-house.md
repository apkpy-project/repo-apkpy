# 4. A house with a room inside

First, the room. This is what a map looks like, each letter a tile (`maps_src/legend.txt` says which).

Create `maps_src/sam_house.map`:

```
# Sam's house, inside.
tiles:
wwwwwwww
wffffffw
wffuuffw
wffffffw
wwwffwww
objects:
exit 3 4 width=2
```

`exit` is the way out, 2 cells wide. You walk against it to leave.

Now the house. Add to `maps_src/village.map`:

```
house_blue 12 8 inside=sam_house
```

That is the whole house: its walls are solid, it has a door, and the door and the exit are linked. The build also adds the new map to `game/main.py`.

Play, and walk into the blue house below the stall.

Next: [5. Wild monsters](05-wild-monsters.md)
