# 3. Someone to talk to

A person takes two things: what they say, and where they stand.

Add to `story/village.story`:

```
event village.sam
    once met_sam:
        say Hi! I am Sam. You look new here.
        give tonic 2
    otherwise:
        say Good luck out there.
```

`once` is for what happens only the first time. `met_sam` is a **flag**: a name you make up, which the game remembers.

Add to `maps_src/village.map`:

```
person 12 12 sam look=vendor event=village.sam
```

That is column 12, row 12, counting from 0 at the top left. To see the columns and rows, open `python tools/map_editor.py` (the bottom line says where the mouse is), or run `python tools/map_tool.py --view village` for a picture with a ruler.

`look=vendor` is the picture `assets/people/vendor.png`. For a new one, run `python tools/new.py person sam` and use `look=sam`.

Next: [4. A house with a room inside](04-a-house.md)
