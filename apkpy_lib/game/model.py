"""What the declaration reader produces: a plain description of the game.

Nothing here runs game code; these are records the bundle writer turns
into JSON.
"""
import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AssetRef:
    kind: str           # image | sound | music
    path: str           # relative to the project, posix


@dataclass
class AtlasRef:
    pattern: str
    name: str
    files: List[str]    # relative to the project, sorted

    def frame_index(self, frame):
        names = [f.rsplit("/", 1)[-1].rsplit(".", 1)[0] for f in self.files]
        if isinstance(frame, int):
            return frame if 0 <= frame < len(self.files) else None
        return names.index(frame) if frame in names else None


@dataclass
class SheetRef:
    """assets.sheet(path, frame=(w, h)): an image cut into equal frames, numbered left to right, top to bottom."""
    path: str
    frame_w: int
    frame_h: int
    cols: int
    rows: int

    def region(self, i):
        return [(i % self.cols) * self.frame_w, (i // self.cols) * self.frame_h, self.frame_w, self.frame_h]


@dataclass
class TilemapRef:
    """assets.tilemap(path): a Tiled map (.tmj), read at build time."""
    path: str
    name: str
    data: Any            # the parsed map (compiler/tiled.py)


@dataclass
class RuleModel:
    """when("lives <= 0", ...): var or count(tag), op, value, actions."""
    var: Optional[str]
    count: Optional[str]
    op: str
    value: float
    actions: List[Any]
    line: int = 0


@dataclass
class TextRef:
    """t("key"): a word of the app's translations()."""
    key: str
    line: int = 0


@dataclass
class ComponentValue:
    type: str
    values: Dict[str, Any]


@dataclass
class ActionValue:
    name: str
    do: str
    values: Dict[str, Any]
    line: int = 0


@dataclass
class EntityModel:
    name: str
    components: List[ComponentValue] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    children: List["EntityModel"] = field(default_factory=list)
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    elevation: float = 0.0
    scale: Any = 1
    active: bool = True
    ui: bool = False
    props: Dict[str, Any] = field(default_factory=dict)    # the Tiled object's custom properties
    marker: Optional[str] = None                           # the Tiled object's name
    group: Optional[str] = None
    persistent: bool = False
    anchor: Optional[List[float]] = None
    line: int = 0

    def clone(self):
        return copy.deepcopy(self)


@dataclass
class SceneModel:
    name: str
    kind: str = "2d"
    start: bool = False
    background: Optional[str] = None
    music: Optional[AssetRef] = None
    music_volume: float = 1.0
    camera: Optional[Dict[str, Any]] = None
    on_back: List[ActionValue] = field(default_factory=list)
    vars: Dict[str, float] = field(default_factory=dict)
    rules: List[RuleModel] = field(default_factory=list)
    entities: List[EntityModel] = field(default_factory=list)
    line: int = 0


@dataclass
class GameModel:
    name: str = "game"
    size: List[float] = field(default_factory=lambda: [360, 640])
    scale: str = "fit"
    orientation: str = "portrait"
    renderer: str = "auto"
    font: Any = None                                    # AssetRef of assets.font(...)
    pixel_scale: bool = False
    fonts: Dict[str, Any] = field(default_factory=dict)  # path -> measures, written beside the font
    background: str = "#000000"
    fixed_hz: int = 60
    debug: bool = False
    seed: int = 1
    vars: Dict[str, float] = field(default_factory=dict)
    scenes: List[SceneModel] = field(default_factory=list)
    assets: List[Any] = field(default_factory=list)     # AssetRef / AtlasRef, in declaration order
    scripts: List[Any] = field(default_factory=list)    # compiler.scripts.ScriptClass
    functions: List[Any] = field(default_factory=list)  # compiler.scripts.Function
    constants: Dict[str, Any] = field(default_factory=dict)
    modules: List[Any] = field(default_factory=list)    # compiler.scripts.ModuleCode: main.py first, then game/**
    tables: List[Any] = field(default_factory=list)     # (compiler.scripts.TableVar, rows), checked
    game_var: str = "game"
    source: str = "game/main.py"
