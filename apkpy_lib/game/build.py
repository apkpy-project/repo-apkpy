"""The game's build: read game/main.py, check it against the app, write the bundle, pack game.aar."""
import os
import subprocess
import sys

from . import engine
from .compiler import app as app_reader
from .compiler import bundle, pack, reader
from .errors import GameError
from .model import ActionValue, EntityModel, TextRef


def _walk_values(model):
    """Every action and text the game uses: in scenes, entities, children, templates (spawn, Spawner) and rules."""
    def value(v):
        if isinstance(v, TextRef):
            yield v
        elif isinstance(v, ActionValue):
            yield v
            for x in v.values.values():
                for y in value(x):
                    yield y
        elif isinstance(v, EntityModel):
            for y in entity(v):
                yield y
        elif isinstance(v, (list, tuple)):
            for x in v:
                for y in value(x):
                    yield y
        elif isinstance(v, dict):
            for x in v.values():
                for y in value(x):
                    yield y

    def entity(e):
        for c in e.components:
            for v in c.values.values():
                for y in value(v):
                    yield y
        for child in e.children:
            for y in entity(child):
                yield y

    for s in model.scenes:
        for a in s.on_back:
            for y in value(a):
                yield y
        for r in s.rules:
            for y in value(r.actions):
                yield y
        for e in s.entities:
            for y in entity(e):
                yield y


def check_against_app(model, app, project):
    """open_app("x") needs Screen(id="x"); t("k") needs the key; goto_scene("s") needs the scene."""
    src = model.source
    scenes = [s.name for s in model.scenes]
    for value in _walk_values(model):
        if isinstance(value, ActionValue) and value.do == "goto" and value.values["scene"] not in scenes:
            raise GameError("G1210", 'goto_scene("%s"): there is no such scene' % value.values["scene"], src,
                            value.line, fix="Scenes: %s" % ", ".join(scenes))
        if isinstance(value, ActionValue) and value.do == "open":
            screen = value.values["screen"]
            if app is None:
                raise GameError("G1102", 'open_app("%s"): there is no writehere.py to open it in' % screen, src,
                                value.line)
            if screen not in app.screens:
                raise GameError("G1102", 'open_app("%s"): the app has no Screen(id="%s")' % (screen, screen), src,
                                value.line, cause="The game hands the screen id to the ApkPy app, which opens it.",
                                fix=["Screens in writehere.py: %s" % (", ".join(sorted(app.screens)) or "none"),
                                     'Add  %s = Screen(id="%s")  near the top of writehere.py' % (screen, screen)])
        if isinstance(value, TextRef):
            words = app.languages.get(app.default, {}) if app else {}
            if value.key not in words:
                raise GameError("G1103", 't("%s"): the key is not in the app\'s translations' % value.key, src,
                                value.line,
                                cause="The game shows the app's words: translations({...}) in writehere.py, "
                                      "default language %s." % ((app and app.default) or "(none)"),
                                fix='Add "%s": "..." to the default language in translations({...}).' % value.key)


def run_before_build(project):
    """The project's own steps: the build fails with their message, and shows what they say."""
    for script in project.before_build:
        path = os.path.join(project.root, script)
        if not os.path.isfile(path):
            raise GameError("G1010", "before_build in apkpy.toml names %s, and it does not exist" % script, project.rel(project.toml_path))
        r = subprocess.run([sys.executable, path], cwd=project.root, capture_output=True, text=True)
        said = (r.stdout + r.stderr).strip()
        if r.returncode:
            raise GameError("G1010", "%s found a problem:\n  %s" % (script, said.replace("\n", "\n  ")), project.rel(path))
        if said:
            print(said)


def bundle_only(project):
    """Read + check + translate the scripts + bundle (no AAR, no glue check): what the desktop needs."""
    from .compiler import javac, scripts
    run_before_build(project)
    model = reader.read(project.main, project.root)
    app = app_reader.read(project.writehere, project.rel(project.writehere))
    check_against_app(model, app, project)
    files = {}
    if any(m.scripts or m.functions or m.records or m.state or m.tables for m in model.modules):
        files = scripts.translate_program(model.modules)
    info = bundle.write(model, project, app)
    info["game_jar"] = javac.compile_scripts(project, files)
    info["scripts"] = [c.name for c in model.scripts]
    return info


def build(project, log=print):
    info = bundle_only(project)
    for w in info["warnings"]:
        log("  warning: " + w)
    engine.folder()
    aar, count = pack.game_aar(project)
    log("Game: %d scene(s) (%s), %d entities, %d asset(s), %d script(s)%s"
        % (len(info["scenes"]), ", ".join(info["scenes"]), info["entities"], info["assets"], len(info["scripts"]),
           (" (" + ", ".join(info["scripts"]) + ")") if info["scripts"] else ""))
    log("  bundle:   %s" % project.rel(info["bundle"]))
    log("  game:     %s (%d files)" % (project.rel(aar), count))
    return info
