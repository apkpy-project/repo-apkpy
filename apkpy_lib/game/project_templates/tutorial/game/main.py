from apkpy_lib.game import *

game = Game("Tutorial", size=(360, 640), scale="expand", orientation="portrait", background="#ffffff")

main = game.scene("main", start=True)
main.add(Entity("square", Shape(size=(60, 60), color="#ff0000"), TopDownController(speed=600, clamp=False)), at=(180, 320))
