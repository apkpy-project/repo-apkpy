"""Lanterns of Mossbrook: an original 2.5D example, in the style of the DS-era RPGs.

The village is a Tiled map (assets/village.tmj: a hill with stairs, a pond, hedges); houses are Blocks,
trees crossed Planes, people Billboards that walk cell by cell. Tap a cell to walk there (or use the arrows); tap a villager (or Space) to talk.
Find the three lanterns, then bring them to the elder on the hill. Talking opens the app's "dialog" screen.

Read by the build, never run: the declarations become the bundle, the Script classes become Java.
"""
from apkpy_lib.game import *

game = Game("Lanterns of Mossbrook", size=(360, 640), orientation="portrait", background="#9fd6ff",
            vars={"lanterns": 0})

village = assets.tilemap("assets/village.tmj")
hero_sheet = assets.sheet("assets/hero.png", frame=(16, 24))
elder_sheet = assets.sheet("assets/elder.png", frame=(16, 24))
miller_sheet = assets.sheet("assets/miller.png", frame=(16, 24))
lantern_img = assets.image("assets/lantern.png")
tree_img = assets.image("assets/tree.png")
roof_red = assets.image("assets/roof_red.png")
roof_blue = assets.image("assets/roof_blue.png")
wall_img = assets.image("assets/wall.png")
chime = assets.sound("assets/chime.wav")
talk = assets.sound("assets/talk.wav")
theme = assets.music("assets/theme.wav")
CELL = 16
LANTERNS = 3


class Talker(Script):
    """A villager: tapping them (next to the hero) talks. The elder ends the game with every lantern found."""
    who: str = "miller"
    voice: Sound = talk

    def update(self, dt: float):
        hero = scene.find("hero")
        if hero is not None:
            if self.next_to(hero) and (self.tapped() or self.asked(hero)):
                self.talk()

    def asked(self, hero: Entity) -> bool:
        """Space or Enter, next to the villager and facing them."""
        if not (input.key_pressed("space") or input.key_pressed("enter")):
            return False
        want = 0.0
        if self.x > hero.x:
            want = 90.0
        elif self.x < hero.x:
            want = 270.0
        elif self.y < hero.y:
            want = 180.0
        return abs(hero.billboard.facing - want) < 1

    def next_to(self, hero: Entity) -> bool:
        return abs(hero.x - self.x) + abs(hero.y - self.y) <= CELL * 1.1

    def tapped(self) -> bool:
        """The tap is on the villager: their cell, or the cells behind it where the picture stands."""
        if not input.pointer_pressed():
            return False
        dx = abs(input.pointer_x() - self.x)
        up = self.y - input.pointer_y()
        return dx <= CELL * 0.7 and up >= -CELL * 0.6 and up <= CELL * 2.2

    def talk(self):
        audio.play(self.voice)
        found = int(game.get("lanterns"))
        if self.who == "elder" and found >= LANTERNS:
            game.store_set("mossbrook_done", "1")
            game.exit({"result": "done", "lanterns": found})
            return
        game.store_set("mossbrook_talk", self.who + str(found))
        game.open_app("dialog")


@prefab
def villager(sheet=elder_sheet, who: str = "elder", facing: float = 0):
    return Entity("villager", Billboard(sheet, directions=4, facing=facing, auto_facing=False),
                  Talker(who=who), tags=["solid"])


@prefab
def house(roof=roof_red, width: float = 48, depth: float = 32):
    return Entity("house", Block((width, depth), 30, top=roof, side=wall_img))


@prefab
def tree():
    return Entity("tree", Plane(tree_img, size=(28, 44), cross=True))


@prefab
def lantern():
    return Entity("lantern", Billboard(lantern_img), Collider(shape="circle", radius=5, trigger=True),
                  OnCollide("hero", sound(chime), var_add("lanterns", 1), destroy()), tags=["lantern"])


@prefab
def hero():
    return Entity("hero", Billboard(hero_sheet, directions=4), GridController(tile=CELL, speed=4),
                  Collider(shape="circle", radius=5), tags=["hero"])


town = game.scene("town", start=True, kind="2.5d", music=theme, music_volume=0.35, on_back=open_app("pause_menu"),
                  camera={"follow": "hero", "pitch": 50, "distance": 270, "fov": 40, "fog": (260, 520), "bounds": "map"})
town.add(Entity("map", Tilemap(village, objects={
    "hero": hero(), "elder": villager(), "miller": villager(miller_sheet, "miller", 270),
    "lantern": lantern(), "tree": tree(),
    "house0": house(), "house1": house(roof_blue, 32, 32), "house2": house(roof_blue)})))
town.add(Entity("hud", Text(t("lanterns_hud"), size=20, align="center", layer=10)), at=(180, 44), ui=True)
town.add(Entity("hint", Text(t("hint"), size=14, align="center", layer=10)), at=(180, 612), ui=True)
town.add(Entity("pause", Shape(shape="circle", radius=20, color="#2a3a5a", layer=10), OnTap(open_app("pause_menu")),
                children=[Entity("bars", Text("II", size=16, align="center", layer=11), at=(0, 6))]),
         at=(330, 34), ui=True)
