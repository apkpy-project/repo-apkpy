"""What the build needs from the ApkPy app (writehere.py), read the same way: ast, never run.

- the screen ids, so open_app("x") in the game is checked against Screen(id="x");
- the translations({...}, default=...) table, copied into the bundle as
  texts.json so the game's t("key") shows the app's words, in the device's
  language (one table translates the app and the game).
"""
import ast
import os

from ..errors import GameError


class App:
    def __init__(self):
        self.screens = {}          # id -> line
        self.languages = {}        # lang -> {key: text}
        self.default = None
        self.path = None


def read(path, display="writehere.py"):
    app = App()
    if not os.path.isfile(path):
        return None
    app.path = display
    with open(path, encoding="utf-8") as fh:
        try:
            tree = ast.parse(fh.read(), display)
        except SyntaxError as e:
            raise GameError("G1002", "Python syntax error: %s" % e.msg, display, e.lineno)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id == "Screen":
            for k in node.keywords:
                if k.arg == "id" and isinstance(k.value, ast.Constant) and isinstance(k.value.value, str):
                    app.screens[k.value.value] = node.lineno
        elif node.func.id == "translations" and node.args:
            try:
                table = ast.literal_eval(node.args[0])     # ApkPy requires this table to be literal too
            except ValueError:
                continue
            if isinstance(table, dict):
                app.languages = {str(lang): {str(k): str(v) for k, v in words.items()}
                                 for lang, words in table.items() if isinstance(words, dict)}
            default = next((k.value for k in node.keywords if k.arg == "default"), None)
            app.default = default.value if isinstance(default, ast.Constant) else None
            if not app.default and app.languages:
                app.default = next(iter(app.languages))
    return app
