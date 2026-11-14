from apkpy_lib import *

# Parity check on the phone: replays played by the engine with no window must end exactly as on the PC.
# The game it replays is another example's: platformer; scripted, with Java from Python scripts;
# sunbeam, whose solution replay taps the mirrors; mossbrook, 2.5D;
# the many-files game of tests/test_modules.py, 600 steps: modules, @dataclass and module state;
# a list, tabs, toggle, slider and keyboard, with drags (tests/test_lists.py).
home = Screen(id="home", scroll=True)

# The engine and a game's AAR, copied into the Android project by the build (tools/game/parity.py
# puts the game to replay in build/apkpygame/apkpygame-game.aar).
native.gradle("implementation files('libs/apkpygame-engine.aar')")
native.gradle("implementation files('libs/apkpygame-game.aar')")

game_replay = native.java(
    "apkpygameReplay", args=("scene", "script", "steps"), imports=["apkpygame.android.Host"],
    code="return Host.replay(context, scene, script, steps);",
    preview=lambda scene, script, steps: "preview: the replay runs on the phone",
)

out = label("Tap a button", id="out", screen=home)


def run_main():
    out.set_value(game_replay("main", "", "7200"))


SOLUTION = "30:tap:60:480,142:tap:300:180,154:tap:300:360,266:tap:60:300,278:tap:300:300,290:tap:60:420,402:tap:60:180,414:tap:60:480,426:tap:240:480,538:tap:180:180,550:tap:240:300,562:tap:180:360,574:tap:240:360,686:tap:240:180,698:tap:240:300,710:tap:120:360,722:tap:300:360,734:tap:240:480,746:tap:300:480"


def run_solution():
    out.set_value(game_replay("main", SOLUTION, "3000"))


MOSSBROOK = "10:left:down,12:left:up,14:left:down,21:left:up,38:left:down,45:left:up,62:left:down,69:left:up,86:up:down,88:up:up,90:up:down,97:up:up,114:up:down,121:up:up,138:up:down,145:up:up,162:up:down,169:up:up,186:up:down,193:up:up,210:up:down,217:up:up,234:up:down,241:up:up,258:up:down,265:up:up,282:left:down,284:left:up,286:left:down,293:left:up,310:left:down,317:left:up,334:left:down,341:left:up,358:up:down,360:up:up,362:up:down,369:up:up,386:up:down,393:up:up,410:left:down,412:left:up,414:left:down,421:left:up,438:down:down,440:down:up,442:down:down,449:down:up,466:down:down,473:down:up,490:down:down,497:down:up,514:down:down,521:down:up,538:right:down,540:right:up,542:right:down,549:right:up,566:right:down,573:right:up,590:right:down,597:right:up,614:right:down,621:right:up,638:down:down,640:down:up,642:down:down,649:down:up,666:right:down,668:right:up,670:right:down,677:right:up,694:right:down,701:right:up,718:right:down,725:right:up,742:down:down,744:down:up,746:down:down,753:down:up,770:right:down,772:right:up,774:right:down,781:right:up,798:right:down,805:right:up,822:right:down,829:right:up,846:right:down,853:right:up,870:right:down,877:right:up,894:right:down,901:right:up,918:right:down,925:right:up,942:right:down,949:right:up,966:up:down,968:up:up,970:up:down,977:up:up,994:up:down,1001:up:up,1018:up:down,1025:up:up,1042:up:down,1049:up:up,1066:up:down,1073:up:up,1090:left:down,1092:left:up,1094:left:down,1101:left:up,1118:left:down,1125:left:up,1142:left:down,1149:left:up,1166:up:down,1168:up:up,1170:up:down,1177:up:up,1194:up:down,1201:up:up,1218:up:down,1225:up:up,1242:up:down,1249:up:up,1266:up:down,1273:up:up,1290:up:down,1297:up:up,1314:space:down,1315:space:up"


def run_25d():
    out.set_value(game_replay("town", MOSSBROOK, "1344"))


DRAGS = "20:drag:100:240:100:60:30,120:tap:30:115,200:tap:170:66,260:drag:170:162:170:80:20,400:drag:100:60:100:250:10,500:tap:300:30,520:tap:300:30,540:tap:250:60,560:drag:200:90:320:90:8,600:tap:15:345,620:tap:45:345,640:tap:75:375"


def run_drags():
    out.set_value(game_replay("main", DRAGS, "800"))


def run_modules():
    out.set_value(game_replay("main", "", "600"))


def run_selftest():
    out.set_value(game_replay("selftest", "", "10"))


button("Replay main", command=run_main, screen=home)
button("Self-test", command=run_selftest, screen=home)
button("Replay solution", command=run_solution, screen=home)
button("Replay 2.5D", command=run_25d, screen=home)
button("Replay modules", command=run_modules, screen=home)
button("Replay drags", command=run_drags, screen=home)
run(start_screen=home, theme=Theme(mode="dark"))
