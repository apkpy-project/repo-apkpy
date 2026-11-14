"""Sketchbook: paint on a page with a finger, pick colours, fill, stick stars, clear.

Read by the build (apkpy game build / play / run), never run. What runs is in game/page.py.
"""
from apkpy_lib.game import *
from game.page import INK, PAPER, Page, Swatch, Tool

game = Game("Sketchbook", size=(360, 640), scale="fit", orientation="portrait", background="#20232e")


@prefab
def swatch(color: str = INK):
    return Entity("swatch",
                  Shape(shape="circle", radius=17, color=color, layer=5),
                  Swatch(color=color),
                  children=[Entity("ring", Shape(shape="circle", radius=19, color="#6b7290", filled=False, stroke=2, layer=6))])


@prefab
def tool(label: str = "", kind: str = ""):
    return Entity("tool",
                  Shape(size=(52, 40), color="#4a5068", layer=5),
                  Tool(kind=kind),
                  children=[Entity("label", Text(label, size=14, align="center", layer=6), at=(0, 5))])


draw = game.scene("main", start=True)
draw.add(Entity("title", Text("Sketchbook", size=22, align="center")), at=(180, 44), ui=True)
draw.add(Entity("page", Canvas(320, 400, color=PAPER, brush=INK, brush_size=3), Page()), at=(180, 270))

draw.add(swatch(INK), at=(40, 512), ui=True)
draw.add(swatch("#e8483b"), at=(96, 512), ui=True)
draw.add(swatch("#f2a33a"), at=(152, 512), ui=True)
draw.add(swatch("#3fb37f"), at=(208, 512), ui=True)
draw.add(swatch("#3a7bd5"), at=(264, 512), ui=True)
draw.add(swatch("#9b59d0"), at=(320, 512), ui=True)

draw.add(tool("Thin", "thin"), at=(35, 576), ui=True)
draw.add(tool("Thick", "thick"), at=(93, 576), ui=True)
draw.add(tool("Fill", "fill"), at=(151, 576), ui=True)
draw.add(tool("Star", "sticker"), at=(209, 576), ui=True)
draw.add(tool("Clear", "clear"), at=(267, 576), ui=True)
draw.add(Entity("done",
                Shape(size=(52, 40), color="#3fb37f", layer=5),
                OnTap(exit_game({"result": "done"})),
                children=[Entity("label", Text("Done", size=14, align="center", layer=6), at=(0, 5))]),
         at=(325, 576), ui=True)
