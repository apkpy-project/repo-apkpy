"""The game: its scenes, one per map. Everything else is in the files this one imports (see README.md).

To add a map: write maps_src/<name>.map. The next build adds its scene at the end of this file, and you can change it there.
"""
from apkpy_lib.game import *

from game.battle.presenter import ally_sprite, battle_ui, foe_sprite
from game.ui.hud import hud
from game.ui.kit import pixel
from game.ui.title import title_scenery, title_screen
from game.world.prefabs import door, exit_door, hero, house, knot, lighthouse, marker, person, roof_blue, roof_red, sign, trainer, tree, trigger, warp

game = Game("Saltmere", size=(480, 270), orientation="landscape", scale="expand", pixel_scale=True, background="#7cb4d8", font=pixel, seed=20261104)

town_music = assets.music("assets/music_town.wav")
battle_music = assets.music("assets/music_battle.wav")

CAMERA = {"follow": "hero", "pitch": 52, "distance": 210, "fov": 40, "bounds": "map"}
OBJECTS = {
    "marker": marker(), "warp": warp(), "door": door(), "exit": exit_door(), "trigger": trigger(), "tree": tree(), "sign": sign(), "knot": knot(),
    "house_red": house(roof_red, 5, 3), "house_blue": house(roof_blue, 4, 3), "lighthouse": lighthouse(),     # houses: width and depth, in cells
    "person": person(), "trainer": trainer(),
}

title = game.scene("title", start=True, background="#102448", music=town_music, music_volume=0.5)
title.add(title_scenery())
title.add(title_screen())

village = game.scene("village", kind="2.5d", camera=CAMERA, music=town_music, music_volume=0.5, background="#7cb4d8")
village.add(Entity("map", Tilemap(assets.tilemap("maps/village.tmj"), solid=["solid"], objects=OBJECTS)))
village.add(hero())
village.add(hud())

house_inside = game.scene("house", kind="2.5d", camera=CAMERA, music=town_music, music_volume=0.5, background="#101018")
house_inside.add(Entity("map", Tilemap(assets.tilemap("maps/house.tmj"), solid=["solid"], objects=OBJECTS)))
house_inside.add(hero())
house_inside.add(hud())

route = game.scene("route", kind="2.5d", camera=CAMERA, music=town_music, music_volume=0.5, background="#7cb4d8")
route.add(Entity("map", Tilemap(assets.tilemap("maps/route.tmj"), solid=["solid"], objects=OBJECTS)))
route.add(hero())
route.add(hud())

battle = game.scene("battle", kind="2.5d", music=battle_music, music_volume=0.6, background="#a8d0e8",
                    camera={"x": 192, "y": 165, "pitch": 20, "distance": 330, "fov": 34})
battle.add(Entity("map", Tilemap(assets.tilemap("maps/arena.tmj"), solid=[])))
battle.add(foe_sprite(), at=(250, 130))
battle.add(ally_sprite(), at=(120, 172))
battle.add(battle_ui())
