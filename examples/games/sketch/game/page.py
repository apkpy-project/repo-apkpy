"""The page and its tools: what runs while the player paints (translated to Java by the build)."""
from dataclasses import dataclass

from apkpy_lib.game import *

sticker = assets.image("assets/sticker.png")
pop = assets.sound("assets/pop.wav")

PAPER = "#fbf7ee"
INK = "#1d1f27"


@dataclass
class Tools:
    color: str = INK
    size: int = 3
    mode: str = "brush"


TOOLS = Tools()


class Page(Script):
    def update(self, dt: float):
        c = self.canvas
        if TOOLS.mode == "brush":
            c.set_brush(TOOLS.color)
            c.brush_size = TOOLS.size
        else:
            c.set_brush("")

    def on_tap(self):
        c = self.canvas
        if c.pointer_x < 0:
            return
        if TOOLS.mode == "fill":
            c.flood(c.pointer_x, c.pointer_y, TOOLS.color)
        elif TOOLS.mode == "sticker":
            c.stamp(sticker, c.pointer_x - 14, c.pointer_y - 14)
            audio.play(pop, 0.4)


class Swatch(Script):
    color: str = INK

    def update(self, dt: float):
        if TOOLS.color == self.color:
            self.scale = 1.25
        else:
            self.scale = 1.0

    def on_tap(self):
        TOOLS.color = self.color
        if TOOLS.mode == "sticker":
            TOOLS.mode = "brush"


class Tool(Script):
    kind: str = ""

    def update(self, dt: float):
        on = TOOLS.mode == self.kind
        if self.kind == "thin":
            on = TOOLS.mode == "brush" and TOOLS.size == 3
        elif self.kind == "thick":
            on = TOOLS.mode == "brush" and TOOLS.size == 9
        if on:
            self.shape.alpha = 1.0
        else:
            self.shape.alpha = 0.45

    def on_tap(self):
        if self.kind == "thin":
            TOOLS.mode = "brush"
            TOOLS.size = 3
        elif self.kind == "thick":
            TOOLS.mode = "brush"
            TOOLS.size = 9
        elif self.kind == "clear":
            page = scene.find("page")
            if page is not None:
                page.canvas.fill(PAPER)
        else:
            TOOLS.mode = self.kind
