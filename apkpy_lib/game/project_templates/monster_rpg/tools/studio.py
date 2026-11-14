"""The Studio: one window to make your game, for the project this file is in.

    python tools/studio.py

It only reads and writes the project's own files (maps_src/, story/, data/, assets/), so you can also change them by hand
and build with plain apkpy. Nothing in the game depends on it.
"""
import os
import re
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import map_editor  # noqa: E402
import story_editor  # noqa: E402
import studio_art  # noqa: E402
import studio_publish  # noqa: E402
import studio_test  # noqa: E402
import studio_data  # noqa: E402
import studio_forms  # noqa: E402
import studio_ui  # noqa: E402
from studio_ui import ACCENT, BAD, GOOD, LINE, MUTED, PANEL, SIDE, SIDE_TEXT, px  # noqa: E402
from apkpy_lib.game.studio.shell import CopiesScreen, Shell  # noqa: E402

SECTIONS = (("play", "Play"), ("test", "Test"), ("game", "My game"), ("maps", "Maps"), ("story", "Story"), ("monsters", "Monsters"), ("moves", "Moves"), ("types", "Types"), ("items", "Items"),
            ("shops", "Shops"), ("trainers", "Trainers"), ("wild", "Wild monsters"), ("natures", "Natures"), ("effects", "Effects"), ("statuses", "Statuses"), ("rules", "Rules"), ("words", "Words"), ("art", "Art"), ("look", "Title and icon"), ("sound", "Music and sound"), ("publish", "Publish"), ("backups", "Copies"), ("help", "Help"))
TABLE_SCREENS = {"game": studio_forms.GameScreen, "monsters": studio_forms.MonsterScreen, "moves": studio_forms.MoveScreen, "types": studio_forms.TypeScreen,
                 "items": studio_forms.ItemScreen, "shops": studio_forms.ShopScreen, "trainers": studio_forms.TrainerScreen, "wild": studio_forms.WildScreen,
                 "natures": studio_forms.NatureScreen, "effects": studio_forms.EffectScreen, "statuses": studio_forms.StatusScreen,
                 "rules": studio_forms.RulesScreen, "words": studio_forms.WordsScreen}
SECTION_OF = {"GameInfo": "game", "Species": "monsters", "Move": "moves", "Type": "types", "Item": "items", "Shop": "shops", "Trainer": "trainers", "EncounterTable": "wild", "Nature": "natures",
              "Effect": "effects", "Status": "statuses", "Rules": "rules", "Words": "words"}
FILES = {"game": "game", "moves": "moves", "types": "types", "items": "items", "shops": "shops", "trainers": "trainers", "encounters": "wild", "natures": "natures", "effects": "effects", "statuses": "statuses", "rules": "rules", "texts": "words"}


class Studio(Shell):
    """ApkPy's Studio, with the monster RPG's sections: maps, story, monsters, moves... and its tests."""

    SECTIONS = SECTIONS
    FIRST = "game"
    ICON_PLACE = "Title and icon"

    def __init__(self, root, folder=ROOT):
        self.after_save_forget = []
        self.game = None
        Shell.__init__(self, root, folder)

    def make_project(self):
        return studio_data.Project(self.folder)

    def backup(self, reason):
        return studio_data.make_backup(reason, self.folder)

    def restore_files(self, name):
        studio_data.restore_backup(name, self.folder)

    def copies_hold(self):
        return "They hold your maps, story, data and art."

    def sections(self):
        return list(SECTIONS)

    def make_screen(self, key):
        if key == "maps":
            frame = tk.Frame(self.area)
            self.map_frame = frame
            self.editor = map_editor.Editor(self.root, parent=frame, shell=self)
            frame.go_to = lambda target: self.editor.open_map(target)
            return frame
        if key == "story":
            return story_editor.StoryPanel(self.area, on_saved=self.story_saved, test_event=self.test_event)
        if key in TABLE_SCREENS:
            return TABLE_SCREENS[key](self.area, self)
        if key == "publish":
            return studio_publish.PublishScreen(self.area, self)
        if key == "help":
            return studio_publish.HelpScreen(self.area, self)
        if key == "play":
            return studio_test.GameScreen(self.area, self)
        if key == "test":
            return studio_test.TestScreen(self.area, self)
        if key == "art":
            return studio_art.ArtScreen(self.area, self)
        if key == "look":
            return studio_art.LookScreen(self.area, self)
        if key == "sound":
            return studio_art.SoundScreen(self.area, self)
        return CopiesScreen(self.area, self)

    def refreshes(self, key):
        return key in TABLE_SCREENS or key in ("test", "publish", "art")

    def check_command(self):
        return [sys.executable, os.path.join(ROOT, "tools", "prepare.py")]

    def undo_key(self, name):
        if self.current in TABLE_SCREENS or self.current == "art":
            getattr(self.screens[self.current], name)()

    def go_use(self, use):
        """Goes to a place that uses a row."""
        if use.section == "story":
            name, line = use.target.split(":")
            story = self.show("story")
            story.problem_at = (name, int(line))
            story.go_to_problem()
        elif use.section == "maps":
            self.show("maps")
            self.editor.open_map(use.target)
        elif use.section == "story_event":
            self.show("story").open_event(use.target)
        elif use.section == "story_flag":
            self.show("story").find_word(use.target)
        elif use.section == "code":
            self.summary.config(text="That is in %s: it is code, so change it in a text editor." % use.target, fg=MUTED)
        elif use.section in SECTION_OF:
            self.go(SECTION_OF[use.section], use.target)

    def open_story(self):
        """What the map editor asks for, to write what someone says."""
        return self.show("story")

    def maps_active(self):
        return self.current == "maps"

    def dirty_sections(self):
        out = set()
        editor = getattr(self, "editor", None)
        if editor is not None and any(t.dirty for t in editor.tabs):
            out.add("maps")
        story = self.screens.get("story")
        if story is not None and story.dirty():
            out.add("story")
        for cls, key in SECTION_OF.items():
            if cls in self.project.tables and self.project.tables[cls].dirty:
                out.add(key)
        if self.project.app.values.get("icon") != self.project.app.saved.get("icon"):
            out.add("look")
        if any(self.project.app.values.get(k) != self.project.app.saved.get(k) for k in self.project.app.values if k != "icon"):
            out.add("game")
        if self.project.look.dirty:
            out.add("sound" if self.project.look.sounds() != re.findall(r'^(\w+)\s*=\s*assets\.sound\("([^"]+)"\)', self.project.look.saved, re.M) else "look")
        if self.project.main.dirty:
            out.add("sound")
        art = self.screens.get("art")
        if art is not None and art.dirty():
            out.add("art")
        return out

    def save_all(self):
        if self.dirty_sections() and not self.saved_once:
            studio_data.make_backup("before saving", ROOT)
            self.saved_once = True
        editor = getattr(self, "editor", None)
        if editor is not None:
            editor.save_all()
        story = self.screens.get("story")
        if story is not None:
            story.save()
        art = self.screens.get("art")
        art_changed = art is not None and art.save()
        self.project.save()
        for name in self.after_save_forget:
            species, _, variant = name.partition(".")
            row = self.project.table("Species").get(species)
            if row is not None and (not variant or any(v.get("id") == variant for v in row.get("variants", []))):
                continue                     # it came back before the save: keep its picture
            self.project.forget_sprite(name)
        self.after_save_forget = []
        self.update_marks()
        self.name_changed()
        if art_changed:
            self.art_changed()
        self.run_check()

    def art_changed(self):
        """Pictures changed: whoever shows them, see them again."""
        editor = getattr(self, "editor", None)
        if editor is not None:
            editor.images = {}
            editor.build_palette()
            editor.redraw()
        monsters = self.screens.get("monsters")
        if monsters is not None:
            monsters.images = {}

    def pictures_drawn(self, monsters_drawn):
        """The check drew placeholders for new things: show them where they belong."""
        self.art_changed()
        art = self.screens.get("art")
        if art is not None:
            art.refresh()
        screen = self.screens.get("monsters")
        if screen is not None:
            screen.fill_list()
            if self.current == "monsters" and screen.selected and screen.selected["id"] in monsters_drawn:
                screen.show_row()

    def draw_monster(self, row_id, variant=""):
        """From a monster (or one of its variants) to its sheet in Art: drawn now if it has none yet."""
        path = self.project.draw_sprite(row_id, variant)
        self.pictures_drawn([row_id])
        self.go("art", "monsters/" + os.path.basename(path)[:-4])

    def story_saved(self):
        editor = getattr(self, "editor", None)
        if editor is not None:
            editor.show_fields()
        self.update_marks()

    def reload_everything(self, select=None):
        """The files changed underneath: read them again."""
        self.project.reload()
        story = self.screens.get("story")
        if story is not None:
            story.reload_files()
        editor = getattr(self, "editor", None)
        if editor is not None:
            editor.reload_all()
        for key in TABLE_SCREENS:
            screen = self.screens.get(key)
            if screen is not None:
                screen.reload()
                if select and screen.table().get(select) is not None and key == self.current:
                    screen.select(select)
        for key in ("backups", "art", "look", "sound", "publish"):
            screen = self.screens.get(key)
            if screen is not None:
                screen.reload()
        self.art_changed()
        self.update_marks()
        self.run_check()

    def watch_check(self):
        if self.checker.poll() is None:
            self.root.after(150, self.watch_check)
            return
        said = self.checker.stdout.read()
        if not self.project.main.dirty:
            self.project.main.load()        # the check can add the scene of a new map
        self.show_problems(self.read_check(said, self.checker.returncode))
        if "drew a placeholder" in said:
            self.pictures_drawn(re.findall(r"drew a placeholder: monsters/(\w+)\.png", said))
        if self.check_again:
            self.check_again = False
            self.run_check()

    @staticmethod
    def read_check(said, code):
        """(problems, notes) from what tools/prepare.py said."""
        problems, notes = [], []
        for line in said.splitlines():
            text = line.strip()
            if not text or re.fullmatch(r"\d+ problem\(s\) in the content\.", text):
                continue
            if text.startswith("note: "):
                notes.append(text[6:])
            elif code and not re.fullmatch(r"(maps|data/events)/\S+", text) and not text.startswith(("drew a placeholder", "game/main.py: added")):
                problems.append(text)
        return problems, notes

    def show_problems(self, found):
        problems, notes = found
        self.problems = problems + notes
        self.real_problems = problems
        self.problem_box.delete(0, "end")
        for text in problems:
            self.problem_box.insert("end", text)
        for text in notes:
            self.problem_box.insert("end", "note: " + text)
        if problems:
            self.summary.config(text="%d problem%s in the saved files. Click to see." % (len(problems), "" if len(problems) == 1 else "s"), fg=BAD)
            if not self.list_open:
                self.toggle_problems()
        elif notes:
            self.summary.config(text="No problems. %d note%s: click to see." % (len(notes), "" if len(notes) == 1 else "s"), fg=GOOD)
        else:
            self.summary.config(text="No problems in the saved files.", fg=GOOD)
            if self.list_open:
                self.toggle_problems()
        screen = self.screens.get("monsters")
        if screen is not None and not self.dirty_sections():
            screen.images = {}
            screen.fill_list()

    def open_problem(self):
        """Goes to what a line talks about."""
        chosen = self.problem_box.curselection()
        if not chosen:
            return
        text = self.problem_box.get(chosen[0]).replace("note: ", "")
        m = re.match(r"maps_src/(\w+)\.map(?::(\d+))?", text) or re.match(r"maps/(\w+)\.tmj()", text)
        if m:
            self.show("maps")
            self.editor.open_map(m.group(1))
            if m.group(2):
                self.editor.problem_at = (m.group(1), int(m.group(2)))
                self.editor.go_to_problem()
            return
        m = re.match(r"story/([\w.]+):(\d+)", text)
        if m:
            story = self.show("story")
            story.problem_at = (m.group(1), int(m.group(2)))
            story.go_to_problem()
            return
        m = re.match(r"event (\S+?),", text)
        if m:
            self.show("story").open_event(m.group(1))
            return
        m = re.match(r"data/species/(\w+)\.json", text) or re.match(r"assets/monsters/(\w+)\.png", text)
        if m and self.project.tables["Species"].get(m.group(1)):
            self.go("monsters", m.group(1))
            return
        m = re.match(r"(?:data/)?(\w+)\.json", text)
        if m and m.group(1) in FILES:
            self.show(FILES[m.group(1)])

    # ── playing, closing ──
    def play(self):
        self.show("play").play_from_title()

    def has_map_problem(self):
        return bool(map_editor.find_problem({}))

    def test_setup(self):
        """What the tests start with: what the Test section says."""
        screen = self.screen("test")
        screen.clean_setup()
        return screen.setup

    def start_test(self, name, col, row, event=""):
        """The game on this map at this cell, with the team, items and flags of the Test section."""
        self.save_all()
        setup = self.test_setup()
        process = studio_test.ask_lab(ROOT, "save", dict(setup, map=name))
        answer, problem = studio_test.lab_answer(process)
        screen = self.show("play")
        if answer is None:
            screen.status.config(text=problem[:140], fg=BAD)
            return
        map_editor.start_test_here(name, col, row, answer["save"], event)
        screen.start(name)

    def test_event(self, event):
        """Starts an event where its object is, or where the Test section says if nothing has it."""
        place = self.project.event_place(event)
        setup = self.test_setup()
        if place is None:
            spot = self.project.marker_cell(setup.get("map", ""), setup.get("marker", ""))
            if spot is None:
                return
            place = (setup["map"],) + spot
        self.start_test(place[0], place[1], place[2], event)

    def close_screens(self):
        Shell.close_screens(self)
        editor = getattr(self, "editor", None)
        if editor is not None:
            editor.remember_session()
            preview = editor.preview
            if preview is not None and preview.winfo_exists():
                preview.destroy()


def main():
    root = studio_ui.make_root("Studio")
    Studio(root)
    root.mainloop()


if __name__ == "__main__":
    main()
