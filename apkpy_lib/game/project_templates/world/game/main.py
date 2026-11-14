"""Gem Valley: a small 2.5D valley to walk, seen from above at an angle. Find the four lanterns.

Tap a place to walk there (or use the arrow keys). Houses are Blocks, trees are crossed Planes, people and lanterns
are Billboards that turn to the camera. The valley is levels/valley.tmj: the hedges and the pond are on the solid
layer "walls" (the hedge tile is raised, a Tiled property "height"), and everything else is placed on its object
layer. Change it in the Studio's Levels, or in Tiled.

Made of components only: open it in the Studio (apkpy game studio) to change any of it, or change it here.
scale="expand": on a taller or wider screen more of the valley shows, with no bands.
"""
from apkpy_lib.game import *

game = Game("Gem Valley", size=(360, 640), scale="expand", orientation="portrait", background="#9fd6ff",
            vars={"lanterns": 0, "score": 0})

valley = assets.tilemap("levels/valley.tmj")
hero_sheet = assets.sheet("assets/hero.png", frame=(16, 24))
elder_sheet = assets.sheet("assets/elder.png", frame=(16, 24))
lantern_img = assets.image("assets/lantern.png")
tree_img = assets.image("assets/tree.png")
roof_red = assets.image("assets/roof_red.png")
roof_blue = assets.image("assets/roof_blue.png")
wall_img = assets.image("assets/wall.png")
chime = assets.sound("assets/chime.wav")
win = assets.sound("assets/win.wav")
theme = assets.music("assets/theme.wav")


@prefab
def hero():
    return Entity("hero", Billboard(hero_sheet, directions=4), GridController(tile=16, speed=4),
                  Collider(shape="circle", radius=5), tags=["hero"])


@prefab
def villager(sheet=elder_sheet, facing: float = 0):
    return Entity("villager", Billboard(sheet, directions=4, facing=facing, auto_facing=False), tags=["solid"])


@prefab
def house(roof=roof_red, width: float = 48, depth: float = 32):
    return Entity("house", Block((width, depth), 30, top=roof, side=wall_img), tags=["solid"])


@prefab
def tree():
    return Entity("tree", Plane(tree_img, size=(28, 44), cross=True), tags=["solid"])


@prefab
def lantern():
    return Entity("lantern", Billboard(lantern_img), Collider(shape="circle", radius=5, trigger=True),
                  OnCollide("hero", sound(chime), var_add("lanterns"), var_add("score", 25), destroy()),
                  tags=["lantern"])


@prefab
def pause():
    return Entity("pause", Shape(shape="circle", radius=20, color="#2a3a5a", layer=10), OnTap(open_app("pause_menu")),
                  children=[Entity("bars", Text("II", size=16, align="center", layer=11), at=(0, 6))])


main = game.scene("main", start=True, kind="2.5d", music=theme, music_volume=0.35, on_back=open_app("pause_menu"),
                  camera={"follow": "hero", "pitch": 50, "distance": 270, "fov": 40, "fog": (260, 520), "bounds": "map"},
                  rules=[when("count(lantern) == 0", sound(win), store_set("score", "{score}"), exit_game({"result": "win"}))])

main.add(Entity("map", Tilemap(valley, objects={
    "hero": hero(), "elder": villager(), "lantern": lantern(), "tree": tree(),
    "house0": house(), "house1": house(roof_blue, 32, 32), "house2": house(roof_blue)})))
main.add(Entity("hud", Text(t("hud"), size=20, align="center", layer=10)), at=(180, 44), ui=True)
main.add(Entity("hint", Text(t("hint"), size=14, align="center", layer=10)), at=(180, 612), ui=True)
main.add(pause(), at=(330, 34), ui=True)
