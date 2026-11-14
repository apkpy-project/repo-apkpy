"""The component schema (components.json), loaded once."""
import json
import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "components.json")
_cache = {}


def load():
    if "schema" not in _cache:
        with open(_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        data["by_name"] = {c["name"]: c for c in data["components"]}
        data["actions_by_name"] = {a["name"]: a for a in data["actions"]}
        _cache["schema"] = data
    return _cache["schema"]


def component(name):
    return load()["by_name"].get(name)


def action(name):
    return load()["actions_by_name"].get(name)
