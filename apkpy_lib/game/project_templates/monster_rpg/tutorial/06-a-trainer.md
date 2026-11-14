# 6. A trainer

Ask for a trainer, with their team as `monster:level`:

```bash
python tools/new.py trainer nell pebblit:2
```

What they say goes in the story. Add to `story/village.story`:

```
trainer nell
    before:
        say This is my cellar. Prove you deserve to be here!
    won:
        say All right, all right. Stay.
    after:
        say I am watching you.
```

And they stand on a map. Add to `maps_src/cellar.map`:

```
trainer 6 3 nell look=rival facing=left
```

Nell looks to the left. If you cross that line, she sees you and comes to fight.

You now know how to make a game's content: maps, people, monsters and story. The [README](../README.md) has the rest.
