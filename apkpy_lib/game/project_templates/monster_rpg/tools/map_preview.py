"""A picture of a map as the game draws it, seen from a cell, with no hero and no buttons. The map editor uses this.

    python tools/map_preview.py village 10 8 picture.png
    python tools/map_preview.py village 10 8 picture.png --no-build     faster, if nothing changed since the last time
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    args = [a for a in sys.argv[1:] if a != "--no-build"]
    if len(args) != 4:
        sys.exit(__doc__)
    name, col, row, picture = args
    os.chdir(ROOT)
    from apkpy_lib.game import desktop
    from apkpy_lib.game.build import bundle_only
    from apkpy_lib.game.errors import GameError
    from apkpy_lib.game.project import Project
    project = Project(ROOT)
    try:
        if "--no-build" not in sys.argv or not os.path.isdir(project.bundle_dir):
            bundle_only(project)
    except GameError as e:
        sys.exit(str(e))
    data = {}
    if os.path.isfile(project.store_file):
        with open(project.store_file, encoding="utf-8") as fh:
            data = json.load(fh)
    data.update({"editor_map": name, "editor_col": col, "editor_row": row, "editor_view": "1"})
    with open(project.store_file, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    desktop._config.update({"bundle": None, "store": None, "project": project})
    try:
        r = subprocess.run(desktop.command(name, "{}", "--screenshot", os.path.abspath(picture), "--steps", "4", "--width", "960", "--height", "540"),
                           capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        sys.exit("The game took too long to draw this map. Try Refresh.")
    if not os.path.isfile(picture):
        sys.exit("The game could not draw this map:\n" + (r.stdout + r.stderr)[-800:])


if __name__ == "__main__":
    main()
