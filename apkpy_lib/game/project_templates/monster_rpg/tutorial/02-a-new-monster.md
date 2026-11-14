# 2. A new monster

Ask for one, with its name and type:

```bash
python tools/new.py monster spark_toad ember
```

That made two files:

- `data/species/spark_toad.json`: its name, stats and moves. Change what you like. The [README](../README.md) says what each field means.
- `assets/monsters/spark_toad.png`: a placeholder drawing. Its front on the left, its back on the right. Draw over it with any image editor, whenever you want.

Now make it your first partner. In `data/game.json`, change `"starters": ["cindlet",` to `"starters": ["spark_toad",`

Play, go to the Keeper's house with the red roof, and your monster is the first choice.

Next: [3. Someone to talk to](03-someone-to-talk-to.md)
