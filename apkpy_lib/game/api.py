"""What a game file sees after  from apkpy_lib.game import *.

Stubs: they give the IDE names and parameters. The game's build never
runs them; it reads the game file (the ApkPy rule). Running game/main.py
with Python does nothing but say so.
"""
from typing import Any, List, Optional, Sequence, Tuple, Union

from ._components import *  # noqa: F401,F403
from ._components import __all__ as _COMPONENTS
from ._data import Ref, from_json, saves, table, to_json  # noqa: F401

__all__ = ["Game", "Entity", "prefab", "assets", "t", "when", "Script", "Sound", "Prefab", "Optional",
           "input", "audio", "scene", "saves", "table", "Ref", "to_json", "from_json"] + list(_COMPONENTS)


class Script:
    """A component written in Python and translated to Java by the build:

        class Ship(Script):
            speed: float = 200.0            # fields: typed, set in declarations: Ship(speed=240.0)
            def update(self, dt: float):    # also on_start, on_collide(other, side), on_tap, on_destroy
                self.x += input.axis_x() * self.speed * dt

    Inside methods: self.x / y / rotation / scale / entity / body / sprite / text / animator,
    self.destroy(), and the objects game, input, audio, scene, math, random.
    """

    x: float
    y: float
    rotation: float
    scale: float

    def destroy(self) -> None:
        """Removes the entity."""


class Sound:
    """The type of a script field holding a sound: boom: Sound = pop."""


class Prefab:
    """The type of a script field holding an entity to copy: bullet: Prefab = bullet()  (scene.spawn(self.bullet, x, y))."""


class _GameAtRunTime:
    """What scripts can do with the game (the name bound to Game(...), usually game)."""
    width: float
    height: float
    time: float
    view_width: float
    view_height: float
    arrival: str

    def get(self, var: str) -> float: ...
    def set(self, var: str, value: float) -> None: ...
    def add(self, var: str, amount: float) -> None: ...
    def exit(self, result: dict = None) -> None: ...
    def open_app(self, screen: str) -> None: ...
    def goto(self, scene: str, at: str = "", fade: float = 0.0) -> None:
        """Changes scene; entities tagged "arrives" appear at the entity or Tiled object called at; fade: seconds."""
    def store_get(self, key: str) -> str: ...
    def store_set(self, key: str, value: str) -> None: ...
    def text(self, key: str) -> str: ...


class _Input:
    def axis_x(self) -> float: ...
    def axis_y(self) -> float: ...
    def key_down(self, key: str) -> bool: ...
    def key_pressed(self, key: str) -> bool: ...
    def pointer_down(self) -> bool: ...
    def pointer_pressed(self) -> bool: ...
    def pointer_x(self) -> float: ...
    def pointer_y(self) -> float: ...
    def pointer_on_ui(self) -> bool:
        """The first finger is on the interface: a tap there is not a tap on the world."""


class _Audio:
    def play(self, sound: "Sound", volume: float = 1.0) -> None: ...
    def set_music(self, on: bool) -> None:
        """The scene's music on or off (the options screen)."""
    def set_sound_volume(self, volume: float) -> None:
        """0 to 1, for every sound from now on."""


class _SceneNow:
    def spawn(self, prefab: "Prefab", x: float, y: float) -> "Entity": ...
    def find(self, name: str) -> "Optional[Entity]": ...
    def count(self, tag: str) -> int: ...
    def with_tag(self, tag: str) -> list: ...
    def tile_tag(self, x: float, y: float, key: str) -> str: ...
    def pause(self, group: str) -> None:
        """Stops a group of entities ("world" by default, "ui" for interface entities); it is still drawn."""
    def resume(self, group: str) -> None: ...
    def is_paused(self, group: str) -> bool: ...


input = _Input()
audio = _Audio()
scene = _SceneNow()

_told = []


def _tell():
    if not _told:
        _told.append(True)
        print("[ApkPy] This file is read by the game's build (apkpy run, apkpy game play); "
              "running it with Python does nothing.")


class _Scene:
    def add(self, entity: "Entity", at: Union[Tuple[float, float], Tuple[float, float, float]] = (0, 0),
            rotation: float = 0, scale: Union[float, Tuple[float, float]] = 1, name: Optional[str] = None,
            ui: bool = False) -> None:
        """Puts an entity (or a prefab's) in the scene, at a position: (x, y), or (x, y, elevation) in 2.5D."""


class Game(_GameAtRunTime):
    """The game: one per project.

    size: the virtual resolution (world units on screen); scale: fit | fill | expand;
    orientation: portrait | landscape | any.
    renderer (Android): auto (OpenGL ES, or Canvas if OpenGL ES cannot start) | gles | canvas.
    font: assets.font(...), used by every Text without one.
    pixel_scale: a virtual pixel is a whole number of screen pixels (pixel art).
    """

    def __init__(self, name: str, size: Tuple[float, float] = (360, 640), scale: str = "fit",
                 orientation: str = "portrait", background: str = "#000000", fixed_hz: int = 60,
                 debug: bool = False, seed: int = 1, vars: Optional[dict] = None, renderer: str = "auto",
                 font: Any = None, pixel_scale: bool = False):
        _tell()

    def scene(self, name: str, start: bool = False, background: Optional[str] = None, music: Any = None,
              music_volume: float = 1.0, camera: Optional[dict] = None, on_back: Any = None,
              vars: Optional[dict] = None, rules: Optional[list] = None, kind: str = "2d") -> _Scene:
        """A scene (what game_play("name") opens). camera: {"x":..., "y":..., "zoom":...}.

        kind="2.5d": drawn in perspective (DS style), the game logic stays 2D (the ground) plus an elevation.
        Its camera: {"follow": "hero", "pitch": 40, "yaw": 0, "distance": 220, "fov": 40, "fog": (250, 500)}.

        on_back: what Back (phone) / Esc (PC) does, e.g. open_app("pause_menu"); by default it ends the game.
        """
        return _Scene()


class Entity:
    """A thing in a scene: a name, components, and optionally tags and children."""

    def __init__(self, name: str, *components: Any, tags: Sequence[str] = (), children: List["Entity"] = (),
                 at: Tuple[float, float] = (0, 0), rotation: float = 0,
                 scale: Union[float, Tuple[float, float]] = 1, active: bool = True, ui: bool = False,
                 group: Optional[str] = None, persistent: bool = False, anchor: str = "top-left"):
        pass


def t(key: str) -> Any:
    """A word of the app's translations({...}) in writehere.py, in the device's language: Text(t("score"))."""


def when(condition: str, *actions: Any) -> Any:
    """A scene rule, for game.scene(..., rules=[...]): when("lives <= 0", exit_game(...)),
    when("count(coin) == 0", goto_scene("level2")). Runs once each time the condition becomes true."""


def prefab(function):
    """@prefab over a function that returns an Entity: a reusable entity with parameters."""
    return function


class _Assets:
    def image(self, path: str) -> Any:
        """A PNG/JPEG/WebP of the project (path relative to the project folder)."""

    def sheet(self, path: str, frame: Tuple[int, int] = (16, 16)) -> Any:
        """An image cut into equal frames (numbered left to right, top to bottom): Sprite(sheet, frame=3), Animator."""

    def tilemap(self, path: str) -> Any:
        """A map made in Tiled, saved as JSON (.tmj): Tilemap(map, solid=["ground"], objects={...})."""

    def atlas(self, pattern: str) -> Any:
        """Several images packed into one: Sprite(atlas, frame="name")."""

    def folder(self, path: str) -> Any:
        """Every image of a folder goes in the bundle; scripts choose one by its path: self.sprite.set_image("assets/x/y.png")."""

    def font(self, path: str) -> Any:
        """A font: TTF/OTF, or a bitmap font in the BMFont text format (.fnt, one page, its .png beside it)."""

    def sound(self, path: str) -> Any:
        """A short sound (WAV/OGG/MP3)."""

    def music(self, path: str) -> Any:
        """A music track (WAV/OGG/MP3), played by a scene: game.scene(..., music=...)."""


assets = _Assets()
