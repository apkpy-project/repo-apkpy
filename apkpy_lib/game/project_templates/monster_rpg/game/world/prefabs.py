"""What can stand on a map: the hero, and the OBJECTS the maps name (the first word of an object in maps_src/*.map).

To add a new kind: a @prefab here and its line in OBJECTS (game/main.py).
"""
from apkpy_lib.game import *

from game.battle.engine import begin_wild
from game.data.defs import ENCOUNTERS, game_info
from game.rules.monsters import make_monster
from game.state.new_game import new_save
from game.state.store import RUN, SESSION, Save, UI, has_flag
from game.ui.screens import SLOT, save_game_text
from game.world.encounters import pick_row, roll_level
from game.world.events import start_event
import random

CELL = 16

people_files = assets.folder("assets/people")      # one sheet per look: look=vendor on a map is assets/people/vendor.png
hero_sheet = assets.sheet("assets/people/hero.png", frame=(16, 24))
person_sheet = assets.sheet("assets/people/villager.png", frame=(16, 24))
tree_image = assets.image("assets/tree.png")
knot_image = assets.image("assets/knot.png")
wall_image = assets.image("assets/house_wall.png")
roof_red = assets.image("assets/roof_red.png")
roof_blue = assets.image("assets/roof_blue.png")
lighthouse_image = assets.image("assets/lighthouse.png")
door_image = assets.image("assets/door.png")
mat_image = assets.image("assets/doormat.png")


def cell_of(v: float) -> int:
    return int(v // CELL)


class MapObject(Script):
    """Reads what a map says about an object: look=, facing=, and hide_if= (gone once that flag is set)."""

    def on_start(self):
        look = self.props.get_str("look", "")
        if look != "":
            self.billboard.set_image("assets/people/" + look + ".png")
        facing = self.props.get_str("facing", "")
        if facing != "":
            self.billboard.facing = 90.0 if facing == "right" else 270.0 if facing == "left" else 180.0 if facing == "up" else 0.0

    def update(self, dt: float):
        flag = self.props.get_str("hide_if", "")
        if flag != "" and has_flag(flag):
            self.destroy()


class Hero(Script):
    """Walking is the GridController's job (the pad, or the arrow keys: tapping the map does nothing, on purpose).
    This is what happens on arriving at a cell, and when the player presses A."""
    arrivals: int = 0
    last_x: float = 0.0
    last_y: float = 0.0

    def on_start(self):
        self.editor_test()
        save = SESSION.save
        if UI.restore_position:
            UI.restore_position = False
            self.x = save.x
            self.y = save.y
        save.x = self.x
        save.y = self.y
        self.last_x = self.x
        self.last_y = self.y
        if UI.autosave:
            UI.autosave = False
            saves.write(SLOT, save_game_text())

    def editor_test(self):
        """The map editor's "Test the game from here": a new game with the first starter, on this map, at that cell."""
        where = game.store_get("editor_map")
        if where == "":
            return
        game.store_set("editor_map", "")
        text = game.store_get("editor_save")                    # the Studio's test: the team, items and flags you chose
        if text != "":
            game.store_set("editor_save", "")
            SESSION.save = from_json(text, Save)
        else:
            info = game_info()
            save = new_save()
            save.map = where
            save.team.append(make_monster(info.starters[0], info.starter_level))
            SESSION.save = save
        event = game.store_get("editor_event")                  # the Studio's "Test this event"
        if event != "":
            game.store_set("editor_event", "")
            start_event(event)
        self.x = (int(game.store_get("editor_col")) + 0.5) * CELL
        self.y = (int(game.store_get("editor_row")) + 0.5) * CELL
        if game.store_get("editor_view") != "":                 # tools/map_preview.py: only the map
            game.store_set("editor_view", "")
            self.billboard.visible = False
            buttons = scene.find("hud")
            if buttons is not None:
                buttons.active = False

    def update(self, dt: float):
        if UI.step_back:
            UI.step_back = False
            self.grid.stop()
            self.x = self.last_x
            self.y = self.last_y
            SESSION.save.x = self.last_x
            SESSION.save.y = self.last_y
        if self.grid.arrivals != self.arrivals:
            self.arrivals = self.grid.arrivals
            self.arrived()
        if not self.grid.walking:
            self.walk_into_door()
            self.interact()

    def arrived(self):
        save = SESSION.save
        save.steps += 1
        if self.check_warps():
            return
        self.last_x = save.x
        self.last_y = save.y
        save.x = (cell_of(self.x) + 0.5) * CELL
        save.y = (cell_of(self.y) + 0.5) * CELL
        if self.check_triggers() or self.check_trainers():
            self.grid.stop()
            return
        zone = scene.tile_tag(self.x, self.y, "zone")
        if zone != "":
            self.maybe_encounter(save.map + "." + zone)

    def same_cell(self, e: Entity) -> bool:
        return cell_of(e.x) == cell_of(self.x) and cell_of(e.y) == cell_of(self.y)

    def check_warps(self) -> bool:
        for e in scene.with_tag("warp"):
            if self.same_cell(e):
                save = SESSION.save
                save.map = e.props.get_str("to", "")
                UI.autosave = True
                self.grid.stop()
                game.goto(save.map, e.props.get_str("at", ""), 0.4)
                return True
        return False

    def walk_into_door(self):
        """A door opens by walking against it: the pad pressed towards it, from the cell next to it."""
        ax = input.axis_x()
        ay = input.axis_y()
        dx = 1 if ax > 0 else -1 if ax < 0 else 0
        dy = 0 if dx != 0 else 1 if ay > 0 else -1 if ay < 0 else 0
        if dx == 0 and dy == 0:
            return
        for e in scene.with_tag("door"):
            if cell_of(e.x) == cell_of(self.x) + dx and cell_of(e.y) == cell_of(self.y) + dy:
                self.use_door(e)
                return

    def use_door(self, e: Entity):
        """to= and at=: it leads there. event=: it plays that instead (a locked door)."""
        target = e.props.get_str("to", "")
        if target == "":
            start_event(e.props.get_str("event", ""))
            return
        save = SESSION.save
        save.map = target
        UI.autosave = True
        game.goto(target, e.props.get_str("at", ""), 0.4)

    def check_triggers(self) -> bool:
        for e in scene.with_tag("trigger"):
            unless = e.props.get_str("unless", "")
            if unless != "" and has_flag(unless):
                continue
            if self.same_cell(e):
                start_event(e.props.get_str("event", ""))
                return RUN.active
        return False

    def check_trainers(self) -> bool:
        """A Warden who has not fought you yet sees you along their line, and comes to you."""
        for e in scene.with_tag("trainer"):
            if has_flag(e.props.get_str("flag", "")):
                continue
            dx = cell_of(self.x) - cell_of(e.x)
            dy = cell_of(self.y) - cell_of(e.y)
            sight = e.props.get_int("sight", 3)
            look = e.props.get_str("facing", "down")
            seen = ((look == "left" and dy == 0 and dx < 0 and dx >= -sight) or (look == "right" and dy == 0 and dx > 0 and dx <= sight)
                    or (look == "up" and dx == 0 and dy < 0 and dy >= -sight) or (look == "down" and dx == 0 and dy > 0 and dy <= sight))
            if seen:
                start_event(e.props.get_str("event", ""))
                return True
        return False

    def maybe_encounter(self, table_id: str):
        if table_id not in ENCOUNTERS or len(SESSION.save.team) == 0:
            return
        table = ENCOUNTERS.get(table_id)
        if random.randint(1, 100) > table.rate:
            return
        self.grid.stop()
        row = pick_row(table)
        begin_wild(row.species, roll_level(row))
        UI.restore_position = True
        game.goto("battle", "", 0.4)

    def interact(self):
        """The A button (or Space), facing someone."""
        if not UI.press_a:
            return
        facing = self.billboard.facing
        dx = 1 if facing == 90.0 else -1 if facing == 270.0 else 0
        dy = -1 if facing == 180.0 else 1 if facing == 0.0 else 0
        for e in scene.with_tag("talk"):
            cx = cell_of(e.x)
            cy = cell_of(e.y)
            if cx == cell_of(self.x) + dx and cy == cell_of(self.y) + dy:
                start_event(e.props.get_str("event", ""))
                return
        for e in scene.with_tag("door"):
            if cell_of(e.x) == cell_of(self.x) + dx and cell_of(e.y) == cell_of(self.y) + dy:
                self.use_door(e)
                return


@prefab
def hero():
    return Entity("hero", Billboard(hero_sheet, directions=4, fps=10), GridController(tile=CELL, speed=5, tap=False), Hero(),
                  Collider(shape="circle", radius=5), tags=["hero", "arrives"])


@prefab
def person():
    return Entity("person", Billboard(person_sheet, directions=4, auto_facing=False), MapObject(), tags=["talk", "solid"])


@prefab
def trainer():
    return Entity("trainer", Billboard(person_sheet, directions=4, auto_facing=False), MapObject(), tags=["talk", "solid", "trainer"])


@prefab
def sign():
    return Entity("sign", Block((10, 6), 10, top_color="#a88858", side_color="#886838"), tags=["talk", "solid"])


@prefab
def knot():
    return Entity("knot", Billboard(knot_image), MapObject(), tags=["talk", "solid"])


@prefab
def tree():
    return Entity("tree", Plane(tree_image, size=(28, 44), cross=True), tags=["solid"])


@prefab
def house(roof=roof_red, width: float = 5, depth: float = 3):
    """Width and depth in cells. tools/map_tool.py reads them from OBJECTS, to make the walls solid and place the door."""
    return Entity("house", Block((width * CELL, depth * CELL), 34, top=roof, side=wall_image))


@prefab
def lighthouse():
    return Entity("lighthouse", Billboard(lighthouse_image))


@prefab
def door():
    """On the front wall of a house: the object is on the wall's last cell, and the picture stands at its edge."""
    return Entity("door", tags=["door"], children=[Entity("picture", Plane(door_image, size=(16, 24)), at=(0, 8.2))])


@prefab
def exit_door():
    """The way out, seen from inside: a mat on the floor of the cell you walk against."""
    return Entity("exit", Plane(mat_image, size=(16, 16), flat=True), tags=["door"])


@prefab
def warp():
    return Entity("warp", tags=["warp"])


@prefab
def trigger():
    return Entity("trigger", tags=["trigger"])


@prefab
def marker():
    return Entity("marker")
