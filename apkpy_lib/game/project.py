"""An ApkPy project with a game: where its files are."""
import os
import re

from .errors import GameError

try:
    import tomllib
except ImportError:                     # Python < 3.11
    tomllib = None


class Project:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.toml_path = os.path.join(self.root, "apkpy.toml")
        self.writehere = os.path.join(self.root, "writehere.py")
        self.main = os.path.join(self.root, "game", "main.py")
        self.build_dir = os.path.join(self.root, "build", "apkpygame")
        self.bundle_dir = os.path.join(self.build_dir, "bundle")
        self.cache_dir = os.path.join(self.build_dir, "cache")
        self.store_file = os.path.join(self.build_dir, "store.json")
        self._toml = None

    @classmethod
    def find(cls, start=None):
        """The folder with apkpy.toml or writehere.py, from start upwards."""
        here = os.path.abspath(start or os.getcwd())
        if os.path.isfile(here):
            here = os.path.dirname(here)
        probe = here
        while True:
            if os.path.isfile(os.path.join(probe, "apkpy.toml")) or os.path.isfile(os.path.join(probe, "writehere.py")):
                return cls(probe)
            parent = os.path.dirname(probe)
            if parent == probe:
                raise GameError("G1003", "this is not an ApkPy project (no apkpy.toml or writehere.py in %s or above)"
                                % here, fix=["cd into the project folder",
                                             "apkpy start mygame --game   (a new project)"])
            probe = parent

    @property
    def toml(self):
        if self._toml is None:
            self._toml = {}
            if os.path.isfile(self.toml_path):
                with open(self.toml_path, "rb") as fh:
                    raw = fh.read()
                if tomllib:
                    self._toml = tomllib.loads(raw.decode("utf-8"))
                else:
                    section = None
                    for line in raw.decode("utf-8").splitlines():
                        m = re.match(r"\s*\[(\w+)\]", line)
                        if m:
                            section = self._toml.setdefault(m.group(1), {})
                            continue
                        m = re.match(r'\s*(\w+)\s*=\s*"?([^"]*)"?\s*$', line)
                        if m and section is not None:
                            section[m.group(1)] = m.group(2)
        return self._toml

    @property
    def before_build(self):
        """[game] before_build = ["tools/x.py"] in apkpy.toml: Python scripts of the project that every build runs first."""
        if not os.path.isfile(self.toml_path):
            return []
        with open(self.toml_path, encoding="utf-8") as fh:
            m = re.search(r"^\s*before_build\s*=\s*\[(.*?)\]", fh.read(), re.M | re.S)
        return re.findall(r'"([^"]+)"', m.group(1)) if m else []

    @property
    def application_id(self):
        app = self.toml.get("app", {})
        value = app.get("application_id") or app.get("id")
        if not value:
            raise GameError("G1004", "apkpy.toml has no application_id", self.toml_path,
                            cause="The app's Play Store id: the game's saves and store live under it on the phone.",
                            fix='[app]\napplication_id = "com.example.mygame"   (or run  apkpy init)')
        return value

    @property
    def name(self):
        return self.toml.get("app", {}).get("name") or os.path.basename(self.root)

    def rel(self, path):
        return os.path.relpath(path, self.root).replace("\\", "/")
