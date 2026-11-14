"""Glue, schema/stubs consistency, CLI new/build, and the Previewer path."""
import os
import subprocess
import sys
import threading

import pytest

from conftest import EXAMPLES, TOOLS, ROOT, apkpy  # noqa: E402

@pytest.fixture(scope="module")
def tk_root():
    """One Tk for the whole module: a second tkinter.Tk() in one process fails on Windows."""
    import tkinter
    root = tkinter.Tk()
    root.withdraw()
    yield root
    root.destroy()


SRC = ROOT


def test_stubs_are_up_to_date():
    subprocess.run([sys.executable, os.path.join(TOOLS, "gen_api.py"), "--check"], check=True)


def test_schema_matches_the_java_readers():
    subprocess.run([sys.executable, os.path.join(TOOLS, "check_schema.py")], check=True)


def test_new_then_build(tmp_path):
    r = apkpy("start", "mygame", "--game", cwd=tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    project = tmp_path / "mygame"
    r = apkpy("game", "build", cwd=project)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (project / "build" / "apkpygame" / "bundle" / "scenes" / "main.json").is_file()
    assert (project / "build" / "apkpygame" / "apkpygame-game.aar").is_file()
    (project / "game" / "main.py").write_text("from apkpy_lib.game import *\n\nfor x in y:\n    pass\n")
    r = apkpy("game", "build", cwd=project)
    assert r.returncode == 1 and "APKPY G1201" in r.stderr, r.stdout + r.stderr


@pytest.mark.slow
def test_previewer_path(tmp_path, monkeypatch, tk_root):
    """Under a Tk loop, as in ApkPy's Previewer: the glue's preview= opens the desktop runner."""
    import tkinter
    from apkpy_lib.game import cli, desktop
    from apkpy_lib.game.project import Project
    monkeypatch.chdir(tmp_path)
    cli.new("pv")
    monkeypatch.setenv("APKPYGAME_PREVIEW", "window")
    monkeypatch.setenv("APKPYGAME_AUTOEXIT_MS", "1500")
    desktop._config.update({"bundle": None, "store": None, "project": Project(str(tmp_path / "pv"))})
    root = tk_root
    got = {}

    class Done:
        def run(self, ok, value):
            got["value"], got["thread"] = value, threading.current_thread()
            root.after(50, root.quit)

    root.after(10, lambda: desktop.play("main", "{}", Done()))
    root.after(20000, root.quit)
    root.mainloop()
    assert '"action":"exit"' in got.get("value", ""), got
    assert got["thread"] is threading.main_thread()
    assert '"action":"exit"' in desktop.last_result()


@pytest.mark.slow
def test_previewer_suspend_and_resume_keep_the_world(tmp_path, monkeypatch, tk_root):
    """Back opens the pause screen (open_app); game_resume continues the SAME run: the steps go on."""
    import json
    import tkinter
    from apkpy_lib.game import cli, desktop
    from apkpy_lib.game.project import Project
    monkeypatch.chdir(tmp_path)
    cli.new("pv", "menus")
    monkeypatch.setenv("APKPYGAME_PREVIEW", "window")
    monkeypatch.setenv("APKPYGAME_AUTOBACK_MS", "900")
    monkeypatch.setenv("APKPYGAME_AUTOEXIT_MS", "2600")
    desktop._config.update({"bundle": None, "store": None, "project": Project(str(tmp_path / "pv"))})
    root = tk_root
    answers = []

    class Done:
        def run(self, ok, value):
            answers.append(value)
            if '"suspended":true' in value:
                assert desktop.suspended() == "true"
                root.after(10, lambda: desktop.resume(Done()))
            else:
                root.after(50, root.quit)

    root.after(10, lambda: desktop.play("main", "{}", Done()))
    root.after(30000, root.quit)
    root.mainloop()
    assert len(answers) == 2, answers
    first, second = json.loads(answers[0]), json.loads(answers[1])
    assert first["action"] == "open" and first["screen"] == "pause_menu" and first["suspended"] is True
    assert second["action"] == "exit" and second["result"]["reason"] == "auto"
    assert second["result"]["steps"] > 60, "the resumed run kept stepping the same world"
    assert desktop.suspended() == "false"


@pytest.mark.slow
def test_embedded_suspend_and_resume_in_the_previewer_window(tmp_path, monkeypatch, tk_root):
    """The default inside a Tk loop: the game is drawn in the Tk window itself (no Java window).
    Back opens the pause screen (the Label hides), game_resume shows the same run again."""
    import json
    from apkpy_lib.game import cli, desktop
    from apkpy_lib.game.project import Project
    monkeypatch.chdir(tmp_path)
    cli.new("pv", "menus")
    monkeypatch.delenv("APKPYGAME_PREVIEW", raising=False)
    monkeypatch.setenv("APKPYGAME_AUTOBACK_MS", "900")
    monkeypatch.setenv("APKPYGAME_AUTOEXIT_MS", "2600")
    desktop._config.update({"bundle": None, "store": None, "project": Project(str(tmp_path / "pv"))})
    root = tk_root
    answers, seen = [], {}

    class Done:
        def run(self, ok, value):
            answers.append(value)
            if '"suspended":true' in value:
                game = desktop.current()
                seen["hidden"] = not game.label.winfo_manager()
                seen["frames"] = game.shown
                assert desktop.suspended() == "true"
                root.after(10, lambda: desktop.resume(Done()))
            else:
                root.after(50, root.quit)

    root.after(10, lambda: desktop.play("main", "{}", Done()))
    root.after(30000, root.quit)
    root.mainloop()
    assert len(answers) == 2, answers
    first, second = json.loads(answers[0]), json.loads(answers[1])
    assert first["action"] == "open" and first["screen"] == "pause_menu" and first["suspended"] is True
    assert seen["hidden"] and seen["frames"] > 10, seen
    assert second["action"] == "exit" and second["result"]["steps"] > 60
    assert desktop.suspended() == "false" and desktop.current() is None
    assert not [w for w in root.winfo_children() if w.winfo_class() == "Label"], "the game's Label is gone"
    assert '"action":"exit"' in desktop.last_result()


@pytest.mark.slow
def test_embedded_landscape_game_turns_the_previewer(monkeypatch, tk_root):
    """A landscape game turns the Previewer's phone (as GameActivity does) and the engine draws at the new
    size; the window is upright again when the game ends."""
    from apkpy_lib.game import desktop
    from apkpy_lib.game.project import Project
    monkeypatch.delenv("APKPYGAME_PREVIEW", raising=False)
    monkeypatch.setenv("APKPYGAME_AUTOEXIT_MS", "1500")
    desktop._config.update({"bundle": None, "store": None,
                            "project": Project(os.path.join(EXAMPLES, "platformer"))})
    root = tk_root
    root.geometry("411x914")
    root.deiconify()
    seen = {}

    def look():
        game = desktop.current()
        if game is None or game.photo is None:
            root.after(50, look)
            return
        seen["window"] = (root.winfo_width(), root.winfo_height())
        seen["frame"] = (game.photo.width(), game.photo.height())
        root.geometry("700x400")                # the window changes size during play: the engine follows
        root.after(400, lambda: seen.update(resized=(game.photo.width(), game.photo.height())))

    class Done:
        def run(self, ok, value):
            seen["value"] = value
            root.after(100, root.quit)

    root.after(10, lambda: desktop.play("", "{}", Done()))
    root.after(1200, look)
    root.after(30000, root.quit)
    try:
        root.mainloop()
        root.update_idletasks()
        seen["after"] = (root.winfo_width(), root.winfo_height())
    finally:
        root.withdraw()
    assert '"action":"exit"' in seen.get("value", ""), seen
    assert seen["window"] == (914, 411) and seen["frame"] == (914, 411), seen
    assert seen["resized"] == (700, 400), seen
    assert seen["after"] == (411, 914), seen


@pytest.mark.slow
def test_embedded_build_error_is_shown_in_the_window(tmp_path, monkeypatch, tk_root):
    """A build error (G1xxx) appears where the game would be; a tap closes it and the app gets the error."""
    import json
    from apkpy_lib.game import cli, desktop
    from apkpy_lib.game.project import Project
    monkeypatch.chdir(tmp_path)
    cli.new("pv")
    main = tmp_path / "pv" / "game" / "main.py"
    main.write_text(main.read_text() + "\nfor i in range(3):\n    pass\n")
    monkeypatch.delenv("APKPYGAME_PREVIEW", raising=False)
    desktop._config.update({"bundle": None, "store": None, "project": Project(str(tmp_path / "pv"))})
    root = tk_root
    got = {}

    def texts():
        return [c.cget("text") for p in root.winfo_children() if p.winfo_class() == "Frame"
                for c in p.winfo_children() if c.winfo_class() == "Label"]

    def tap():
        panels = [p for p in root.winfo_children() if p.winfo_class() == "Frame"]
        if not panels or not panels[-1].winfo_ismapped():      # still building, or not on screen yet
            root.after(100, tap)
            return
        got["texts"] = texts()
        panels[-1].event_generate("<ButtonRelease-1>", x=5, y=5)

    class Done:
        def run(self, ok, value):
            got["ok"], got["value"] = ok, value
            root.after(10, root.quit)

    root.geometry("411x914")
    root.deiconify()                            # Tk gives clicks only to a window on screen
    root.after(10, lambda: desktop.play("main", "{}", Done()))
    root.after(800, tap)
    root.after(10000, root.quit)
    try:
        root.mainloop()
    finally:
        root.withdraw()
    assert "ok" in got, got
    assert got["ok"] is False and json.loads(got["value"])["error"]["code"] == "G1201", got
    assert any(t.startswith("G1201") for t in got["texts"]), got["texts"]
    assert not [p for p in root.winfo_children() if p.winfo_class() == "Frame"], "the panel closed"


@pytest.mark.slow
def test_game_inside_the_real_apkpy_previewer(tmp_path):
    """ApkPy's own Previewer (writehere.py of src/examples/menus): Play -> taps -> Alt+Left -> the ApkPy
    pause screen -> Continue -> Done -> the results screen, all in one window; then a hot-reload-like
    close of the window takes the Java process with it."""
    import json
    import shutil
    project = tmp_path / "menus"
    shutil.copytree(os.path.join(EXAMPLES, "menus"), project, ignore=shutil.ignore_patterns("build"))
    r = subprocess.run([sys.executable, os.path.join(TOOLS, "preview_embedded.py"), str(project)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    log = json.loads(r.stdout.strip().splitlines()[-1])
    assert log["toplevels"] == 0 and log["frames"] > 30, log
    assert log["answers"][0]["action"] == "open" and log["answers"][0]["suspended"] is True, log
    assert log["pause_screen"], log
    assert log["answers"][1]["action"] == "exit" and log["answers"][1]["result"]["reason"] == "done", log
    assert log["results_screen"], log
    assert log["java_ended_with_the_window"], log


@pytest.mark.slow
def test_platformer_example_can_be_won():
    """The phase-4 platformer: the bot's replay wins (no code in the game, only components)."""
    r = subprocess.run([sys.executable, os.path.join(TOOLS, "platformer_bot.py")], capture_output=True,
                       text=True)
    assert r.returncode == 0 and "WON" in r.stdout, r.stdout[-2000:]


@pytest.mark.slow
def test_sunbeam_solution_wins():
    """The phase-6 puzzle: its levels' best solutions (found by the generator's solver) win with par taps."""
    import json
    import re
    from apkpy_lib.game import engine
    from apkpy_lib.game._host import toolchain
    from apkpy_lib.game.build import bundle_only
    from apkpy_lib.game.project import Project
    folder = os.path.join(EXAMPLES, "sunbeam")
    project = Project(folder)
    bundle_only(project)
    pars = re.search(r'PARS = "(\d+)"', open(os.path.join(folder, "game", "main.py"), encoding="utf-8").read())
    script = open(os.path.join(folder, "solution_replay.txt"), encoding="utf-8").read().strip()
    classpath = engine.desktop_jar() + os.pathsep + os.path.join(os.path.dirname(project.bundle_dir), "game.jar")
    out = subprocess.run([toolchain().java, "-cp", classpath, "apkpygame.desktop.Main", "--bundle", project.bundle_dir,
                          "--replay", script, "--steps", "3000"], capture_output=True, text=True).stdout
    end = json.loads(re.search(r"APKPYGAME_RESULT (.*)", out).group(1))
    assert end["result"] == {"result": "win", "taps": sum(int(c) for c in pars.group(1))}, out


def _alive(pid):
    out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/NH"], capture_output=True, text=True).stdout
    return str(pid) in out


def _wait(cond, seconds):
    import time
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.2)
    return False


@pytest.mark.slow
@pytest.mark.skipif(sys.platform != "win32", reason="checks processes with tasklist")
def test_hot_reload_with_the_game_on_screen(tmp_path):
    """ApkPy's own hot reload (python writehere.py, reload on) while the embedded game plays: saving
    game/main.py brings up a new window whose Play runs the new code, the old engine process ends, and
    closing everything leaves no Java behind."""
    import json
    import shutil
    project = tmp_path / "menus"
    shutil.copytree(os.path.join(EXAMPLES, "menus"), project, ignore=shutil.ignore_patterns("build"))
    log = tmp_path / "reload.log"
    env = dict(os.environ, APKPYGAME_RELOAD_LOG=str(log),
               PYTHONPATH=os.pathsep.join([os.path.join(TOOLS, "reload_driver"), ROOT]))
    env.pop("APKPY_RELOAD", None)
    env.pop("APKPYGAME_PREVIEW", None)
    proc = subprocess.Popen([sys.executable, "writehere.py"], cwd=str(project), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def playing():
        return [line.split() for line in log.read_text().splitlines()] if log.exists() else []

    try:
        assert _wait(lambda: len(playing()) >= 1, 90), "the first window never showed the game"
        first_python, first_java = int(playing()[0][1]), int(playing()[0][2])
        main = project / "game" / "main.py"
        main.write_text(main.read_text().replace('t("tap_hint")', '"Reloaded"'))
        assert _wait(lambda: any(int(p[1]) != first_python for p in playing()), 90), playing()
        second_java = int(playing()[-1][2])
        scene = json.loads((project / "build" / "apkpygame" / "bundle" / "scenes" / "main.json").read_text())
        assert "Reloaded" in json.dumps(scene), "Play in the new window built the saved code"
        assert _wait(lambda: not _alive(first_java), 10), "the old window's engine ended with it"
        assert second_java != first_java and _alive(second_java)
    finally:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    assert _wait(lambda: not _alive(second_java), 10), "no Java left once the Previewer is gone"


@pytest.mark.slow
def test_window_mode_runner_ends_when_the_previewer_dies():
    """APKPYGAME_PREVIEW=window: the Java window (--parent-pipe) closes when its stdin ends (a killed Previewer)."""
    from apkpy_lib.game import engine
    from apkpy_lib.game._host import toolchain
    bundle = os.path.join(EXAMPLES, "stress", "bundle")
    proc = subprocess.Popen([toolchain().java, "-jar", engine.desktop_jar(), "--bundle", bundle, "--mute",
                             "--parent-pipe"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL)
    try:
        assert _wait(lambda: False, 2) is False and proc.poll() is None, "it runs while the pipe is open"
        proc.stdin.close()
        assert _wait(lambda: proc.poll() is not None, 10), "the window closed with the pipe"
    finally:
        if proc.poll() is None:
            proc.kill()


def test_reference_is_up_to_date():
    subprocess.run([sys.executable, os.path.join(TOOLS, "gen_docs.py"), "--check"], check=True)


@pytest.mark.slow
def test_the_guide_game_builds_and_plays(tmp_path):
    """The whole game of the guide, game_engine/docs/index.md (section 8), in a new project: it builds, and with no taps
    five balloons get away and the game ends with the score, as the guide says."""
    import json
    import re
    from apkpy_lib.game import cli, engine
    from apkpy_lib.game._host import toolchain
    from apkpy_lib.game.build import bundle_only
    from apkpy_lib.game.project import Project
    guide = open(os.path.join(ROOT, "game_engine", "docs", "index.md"), encoding="utf-8").read()
    code = [b for b in re.findall(r"```python\n(.*?)```", guide, re.S) if b.startswith('"""Balloon Pop')]
    assert len(code) == 1, "the guide has its whole game once"
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        cli.new("balloons")
    finally:
        os.chdir(cwd)
    (tmp_path / "balloons" / "game" / "main.py").write_text(code[0], encoding="utf-8")
    project = Project(str(tmp_path / "balloons"))
    bundle_only(project)
    classpath = engine.desktop_jar() + os.pathsep + os.path.join(os.path.dirname(project.bundle_dir), "game.jar")
    out = subprocess.run([toolchain().java, "-cp", classpath, "apkpygame.desktop.Main", "--bundle", project.bundle_dir,
                          "--replay", "", "--steps", "5000"], capture_output=True, text=True).stdout
    end = json.loads(re.search(r"APKPYGAME_RESULT (.*)", out).group(1))
    assert end["action"] == "exit" and end["result"] == {"score": 0}, out


@pytest.mark.slow
def test_mossbrook_can_be_won():
    """The phase-7 2.5D example: the bot walks the village (GridController, stairs, heights), picks up the
    three lanterns and talks to the elder; the game ends with them."""
    folder = os.path.join(EXAMPLES, "mossbrook")
    from apkpy_lib.game.build import bundle_only
    from apkpy_lib.game.project import Project
    bundle_only(Project(folder))
    r = subprocess.run([sys.executable, os.path.join(TOOLS, "mossbrook_bot.py")], capture_output=True, text=True)
    assert r.returncode == 0 and "WON" in r.stdout, r.stdout[-2000:] + r.stderr[-2000:]
