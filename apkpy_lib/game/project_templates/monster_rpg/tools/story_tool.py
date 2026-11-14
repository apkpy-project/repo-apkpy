"""Turns the story (story/*.story) into events the game reads (data/events/_story.json). The build runs it for you.

    python tools/story_tool.py

A story file is plain text. Lines that start with # are comments, and blocks go by their indentation:

    event cave.old_man
        once met_old_man:
            say Nobody has come down here for years. Take this.
            give tonic 3
        otherwise:
            say Mind the reeds.

    trainer tess
        before:
            say Halt!
        won:
            say You tie a good knot.
            give money 50
        after:
            say The road is open.

What can go in an event:

    say TEXT                     the dialog box
    ask TEXT                     Yes or No: followed by  yes:  and/or  no:  blocks
    if FLAG:  /  if not FLAG:    a block, and optionally an  otherwise:  block after it
    once [FLAG]:                 a block that runs one time, and optionally an  otherwise:  block for the times after
    set FLAG  /  clear FLAG      flags are how the game remembers things: names you make up
    give ITEM [COUNT]            give money COUNT  /  give monster SPECIES [LEVEL]
    heal                         the whole team
    open SCREEN                  menu, team, bag, dex, options, save or starter: waits for it to close
    shop SHOP                    opens that shop (data/shops.json)
    battle TRAINER               a fight (data/trainers.json). If you lose, the event stops
    warp MAP MARKER              another map
    step_back                    the hero goes back one cell
    end                          stops here

Put an event on a map with event=cave.old_man. A trainer on a map (trainer 5 17 tess) plays its "trainer" block by itself.
"""
import difflib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "story")
OUTPUT = os.path.join(ROOT, "data", "events", "_story.json")
COMMANDS = ["say", "ask", "if", "once", "set", "clear", "give", "heal", "open", "shop", "battle", "warp", "step_back", "end"]
SCREENS = ["menu", "team", "bag", "dex", "shop", "options", "save", "starter"]


class StoryError(Exception):
    pass


def maybe(word, options):
    close = difflib.get_close_matches(word, list(options), 1)
    return " Did you mean %r?" % close[0] if close else ""


def ids(path):
    full = os.path.join(ROOT, path)
    if os.path.isdir(full):
        return {n[:-5] for n in os.listdir(full) if n.endswith(".json")}
    with open(full, encoding="utf-8") as fh:
        return {row["id"] for row in json.load(fh)}


class Line:
    def __init__(self, where, indent, text):
        self.where, self.indent, self.text = where, indent, text
        self.head, _, self.rest = text.partition(" ")
        self.rest = self.rest.strip()
        self.body = []


def read_lines(path, name, text=None):
    lines = []
    with (io.StringIO(text) if text is not None else open(path, encoding="utf-8")) as fh:
        for number, raw in enumerate(fh, 1):
            text = raw.rstrip()
            if not text.strip() or text.lstrip().startswith("#"):
                continue
            if "\t" in text[:len(text) - len(text.lstrip())]:
                raise StoryError("story/%s:%d: use spaces to indent, not tabs" % (name, number))
            lines.append(Line("story/%s:%d" % (name, number), len(text) - len(text.lstrip()), text.strip()))
    return lines


def nest(lines):
    """Blocks by indentation: each line gets the lines under it."""
    top, stack = [], []
    for line in lines:
        while stack and stack[-1].indent >= line.indent:
            stack.pop()
        if stack:
            stack[-1].body.append(line)
        else:
            if line.indent:
                raise StoryError("%s: this line is indented, but it is under nothing" % line.where)
            top.append(line)
        stack.append(line)
    return top


class Compiler:
    def __init__(self):
        self.items = ids("data/items.json")
        self.species = ids("data/species")
        self.trainers = ids("data/trainers.json")
        self.shops = ids("data/shops.json")
        folder = os.path.join(ROOT, "maps_src")
        self.maps = {n[:-4] for n in os.listdir(folder) if n.endswith(".map")}
        self.labels = 0
        self.seen_flags = 0
        self.event = ""

    def label(self):
        self.labels += 1
        return "L%d" % self.labels

    def block(self, lines, steps):
        i = 0
        while i < len(lines):
            line = lines[i]
            following = lines[i + 1] if i + 1 < len(lines) else None
            if line.head.rstrip(":") in ("if", "once") and following is not None and following.head == "otherwise:":
                self.branch(line, following, steps)
                i += 2
            elif line.head == "ask":
                i += self.ask(lines, i, steps)
            else:
                self.command(line, steps)
                i += 1

    def condition(self, line):
        """(flag, runs when the flag is set?, set it afterwards?)"""
        text = line.text.rstrip(":").split()
        if not line.text.endswith(":"):
            raise StoryError("%s: %r needs a ':' at the end, and a block under it" % (line.where, line.text))
        if not line.body:
            raise StoryError("%s: there is nothing under this" % line.where)
        if text[0] == "once":
            if len(text) > 2:
                raise StoryError("%s: once takes one flag at most" % line.where)
            if len(text) == 2:
                return text[1], False, True
            self.seen_flags += 1
            return "%s_%d" % (self.event.replace(".", "_"), self.seen_flags), False, True
        if len(text) == 2:
            return text[1], True, False
        if len(text) == 3 and text[1] == "not":
            return text[2], False, False
        raise StoryError("%s: write  if FLAG:  or  if not FLAG:" % line.where)

    def branch(self, line, otherwise, steps):
        flag, when_set, remember = self.condition(line)
        other, done = self.label(), self.label()
        steps.append({"do": "jump_unless" if when_set else "jump_if", "flag": flag, "to": other})
        self.block(line.body, steps)
        if remember:
            steps.append({"do": "set_flag", "flag": flag})
        if otherwise is not None:
            steps.append({"do": "jump", "to": done})
        steps.append({"do": "label", "to": other})
        if otherwise is not None:
            if not otherwise.body:
                raise StoryError("%s: there is nothing under this" % otherwise.where)
            self.block(otherwise.body, steps)
            steps.append({"do": "label", "to": done})

    def ask(self, lines, i, steps):
        line = lines[i]
        if not line.rest:
            raise StoryError("%s: ask needs its question" % line.where)
        used = 1
        blocks = {}
        while i + used < len(lines) and lines[i + used].head in ("yes:", "no:"):
            blocks[lines[i + used].head] = lines[i + used].body
            used += 1
        yes, done = self.label(), self.label()
        steps.append({"do": "ask", "text": line.rest, "to": yes})
        self.block(blocks.get("no:", []), steps)
        steps.append({"do": "jump", "to": done})
        steps.append({"do": "label", "to": yes})
        self.block(blocks.get("yes:", []), steps)
        steps.append({"do": "label", "to": done})
        return used

    def command(self, line, steps):
        head, rest = line.head.rstrip(":"), line.rest.split()
        if head in ("if", "once"):
            self.branch(line, None, steps)
        elif line.head == "otherwise:":
            raise StoryError("%s: otherwise has to come right after an  if  or  once  block" % line.where)
        elif line.head in ("yes:", "no:"):
            raise StoryError("%s: %s has to come right after an  ask" % (line.where, line.head))
        elif head == "say":
            if not line.rest:
                raise StoryError("%s: say needs its text" % line.where)
            steps.append({"do": "say", "text": line.rest})
        elif head == "set" and len(rest) == 1:
            steps.append({"do": "set_flag", "flag": rest[0]})
        elif head == "clear" and len(rest) == 1:
            steps.append({"do": "clear_flag", "flag": rest[0]})
        elif head == "give":
            self.give(line, rest, steps)
        elif head in ("heal", "step_back", "end") and not rest:
            steps.append({"do": head})
        elif head == "open" and len(rest) == 1:
            self.known(line, rest[0], SCREENS, "screen")
            steps.append({"do": "open", "screen": rest[0]})
        elif head == "shop" and len(rest) == 1:
            self.known(line, rest[0], self.shops, "shop in data/shops.json")
            steps.append({"do": "shop", "shop": rest[0]})
        elif head == "battle" and len(rest) == 1:
            self.known(line, rest[0], self.trainers, "trainer in data/trainers.json")
            steps.append({"do": "battle", "trainer": rest[0]})
        elif head == "warp" and len(rest) == 2:
            steps.append({"do": "warp", "to": rest[0], "at": rest[1]})
        elif head in COMMANDS:
            raise StoryError("%s: %r is not how %s is written (see the top of tools/story_tool.py)" % (line.where, line.text, head))
        else:
            raise StoryError("%s: I do not know %r.%s" % (line.where, line.head, maybe(line.head, COMMANDS)))

    def known(self, line, word, options, what):
        if word not in options:
            raise StoryError("%s: there is no %s called %r.%s" % (line.where, what, word, maybe(word, options)))

    def give(self, line, rest, steps):
        if not rest:
            raise StoryError("%s: give what?" % line.where)
        try:
            if rest[0] == "money" and len(rest) == 2:
                steps.append({"do": "give_money", "count": int(rest[1])})
            elif rest[0] == "monster" and len(rest) in (2, 3):
                self.known(line, rest[1], self.species, "monster")
                steps.append({"do": "give_monster", "species": rest[1], "level": int(rest[2]) if len(rest) == 3 else 5})
            elif len(rest) in (1, 2):
                self.known(line, rest[0], self.items, "item in data/items.json")
                steps.append({"do": "give_item", "item": rest[0], "count": int(rest[1]) if len(rest) == 2 else 1})
            else:
                raise ValueError
        except ValueError:
            raise StoryError("%s: write  give ITEM [COUNT],  give money COUNT  or  give monster SPECIES [LEVEL]" % line.where)

    def part(self, top, name):
        for line in top.body:
            if line.head == name + ":":
                return line.body
        return []

    def trainer(self, top):
        who = top.rest
        self.known(top, who, self.trainers, "trainer in data/trainers.json")
        for line in top.body:
            if line.head not in ("before:", "won:", "after:"):
                raise StoryError("%s: a trainer has  before:,  won:  and  after:  blocks.%s" % (line.where, maybe(line.head, ("before:", "won:", "after:"))))
        after = self.label()
        steps = [{"do": "jump_if", "flag": "beat_" + who, "to": after}]
        self.block(self.part(top, "before"), steps)
        steps += [{"do": "battle", "trainer": who}, {"do": "set_flag", "flag": "beat_" + who}]
        self.block(self.part(top, "won"), steps)
        steps += [{"do": "end"}, {"do": "label", "to": after}]
        self.block(self.part(top, "after"), steps)
        return steps

    def all(self, texts=None):
        """texts: what files would say (the story editor, before saving)."""
        texts = texts or {}
        events, where = [], {}
        for name in sorted(set(os.listdir(SOURCE)) | set(texts)):
            if not name.endswith(".story"):
                continue
            for top in nest(read_lines(os.path.join(SOURCE, name), name, texts.get(name))):
                self.labels = 0
                self.seen_flags = 0
                if top.head == "event" and top.rest:
                    event_id = top.rest
                    self.event = event_id
                    steps = []
                    self.block(top.body, steps)
                elif top.head == "trainer" and top.rest:
                    event_id = "trainer." + top.rest
                    self.event = event_id
                    steps = self.trainer(top)
                else:
                    raise StoryError("%s: a story file holds  event NAME  and  trainer NAME  blocks.%s" % (top.where, maybe(top.head, ("event", "trainer"))))
                if event_id in where:
                    raise StoryError("%s: the event %s is already in %s" % (top.where, event_id, where[event_id]))
                where[event_id] = top.where
                events.append({"id": event_id, "steps": steps})
        return events


def find_problem(texts=None):
    """What is wrong with the story, with these files as they are in the editor: "" when fine. Nothing is written."""
    try:
        Compiler().all(texts)
        return ""
    except StoryError as e:
        return str(e)


def main():
    if not os.path.isdir(SOURCE):
        return
    try:
        events = Compiler().all()
    except StoryError as e:
        sys.exit(str(e))
    text = json.dumps(events, indent=1)
    old = None
    if os.path.isfile(OUTPUT):
        with open(OUTPUT, encoding="utf-8") as fh:
            old = fh.read()
    if text != old:
        os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
        with open(OUTPUT, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("data/events/_story.json")


if __name__ == "__main__":
    main()
