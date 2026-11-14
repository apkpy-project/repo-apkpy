"""enable_game() in writehere.py: the Previewer runs it, and `apkpy run`, `build` and `release` read it (the game is
built, and the line becomes the declarations). An app with no game is left as it is."""
import os
import re
import subprocess
import sys
import textwrap

from apkpy_lib.game import glue

from conftest import new_game  # noqa: E402

ID = "com.test.spike"
APP = '''from apkpy_lib import *
%s
home = Screen(id="home")


def finished(ok, value):
    pass


def opened():
    game_play("main", "{}", on_result=finished)


label("", id="blank", screen=home)
lifecycle(home, on_resume=opened)

run(start_screen=home)
'''
ENABLED = APP % "enable_game()\n"
PLAIN = APP.replace('    game_play("main", "{}", on_result=finished)\n', "    pass\n") % ""
OLD_BLOCK = ('# >>> apkpygame:glue v1 (ApkPyGame 1.0.0: generated, do not edit; python -m apkpygame glue --update) >>>\n'
             'native.gradle("implementation files(\\"${System.getProperty(\'user.home\')}/.apkpygame/1.0.0/'
             'apkpygame-engine.aar\\")")\n'
             '# <<< apkpygame:glue v1 <<<\n')
OLD = APP % ("\nfrom apkpygame.app import enable_game\n" + OLD_BLOCK)


def compile_app(text):
    from apkpy_lib.cli import translate_python_to_android
    files = translate_python_to_android(text)
    assert "error.txt" not in files, files.get("error.txt")
    return "".join(v for k, v in files.items() if k.startswith("java/") and isinstance(v, str)), files["native/gradle.txt"]


def test_the_forms_are_told_apart():
    assert glue.status(ENABLED) == "enabled"
    assert glue.status(PLAIN) == "missing"
    assert glue.status(OLD) == "old"
    assert glue.status(glue.enable(PLAIN)) == "enabled"


def test_the_old_block_becomes_enable_game():
    text = glue.enable(OLD)
    assert glue.status(text) == "enabled"
    assert "apkpygame" not in text and text.count("enable_game()") == 1


def test_enable_game_compiles_with_the_engine_inside_the_project():
    java, gradle = compile_app(glue.expand(ENABLED))
    assert "Host.play" in java
    assert "implementation files('libs/apkpygame-engine.aar')" in gradle
    assert "implementation files('libs/apkpygame-game.aar')" in gradle
    assert "user.home" not in gradle and ".apkpygame" not in gradle


def test_lines_keep_their_numbers():
    lines = ENABLED.split("\n")
    expanded = glue.expand(ENABLED).split("\n")
    assert len(expanded) == len(lines)
    changed = [i for i in range(len(lines)) if lines[i] != expanded[i]]
    assert len(changed) == 1 and lines[changed[0]] == "enable_game()"


def test_unread_enable_game_is_not_built_into_something_wrong():
    """The translator alone (no project to build the game from) refuses it with the reason."""
    from apkpy_lib.cli import translate_python_to_android
    files = translate_python_to_android(ENABLED)
    assert "error.txt" in files and "U2033" in files["error.txt"]


def read_with_apkpy(cwd):
    """In a new Python: what `apkpy run` gets when it reads writehere.py."""
    code = textwrap.dedent("""
        import sys
        from apkpy_lib import cli
        text = cli._read_writehere()
        sys.stdout.reconfigure(encoding="utf-8")
        print("@@BEGIN@@" + str(text) + "@@END@@")
    """)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", APKPY_RELOAD="0")
    r = subprocess.run([sys.executable, "-c", code], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                       env=env)
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
    return r.stdout.split("@@BEGIN@@", 1)[1].split("@@END@@", 1)[0], r.stdout + r.stderr


def project_with(folder, writehere):
    (folder / "game").mkdir(parents=True)
    (folder / "apkpy.toml").write_text('[app]\nname = "T"\napplication_id = "%s"\nversion_name = "0.1.0"\nversion_code = 1\n' % ID)
    (folder / "writehere.py").write_text(writehere, encoding="utf-8")
    (folder / "game" / "main.py").write_text('from apkpy_lib.game import *\n\ngame = Game("T", size=(100, 100))\nmain = game.scene("main", start=True)\n')


def test_a_plain_apkpy_app_is_not_touched(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "writehere.py").write_text(PLAIN, encoding="utf-8")
    text, _ = read_with_apkpy(tmp_path / "app")
    assert text == PLAIN


def test_apkpy_reads_enable_game_and_the_game_is_built(tmp_path):
    project_with(tmp_path / "new", ENABLED)
    text, _ = read_with_apkpy(tmp_path / "new")
    assert text == glue.expand(ENABLED)
    assert (tmp_path / "new" / "build" / "apkpygame" / "bundle").is_dir()
    assert (tmp_path / "new" / "build" / "apkpygame" / "apkpygame-game.aar").is_file()
    assert compile_app(text)
    libs = glue.android_libs(str(tmp_path / "new"))
    assert sorted(libs) == ["app/libs/apkpygame-engine.aar", "app/libs/apkpygame-game.aar"]
    assert all(os.path.isfile(p) for p in libs.values())


def test_the_old_block_stops_apkpy_with_what_to_do(tmp_path):
    project_with(tmp_path / "old", OLD)
    text, out = read_with_apkpy(tmp_path / "old")
    assert text == "None" and "APKPY G1101" in out and "enable_game()" in out


def test_a_broken_game_stops_apkpy_with_its_message(tmp_path):
    project_with(tmp_path / "bad", ENABLED)
    (tmp_path / "bad" / "game" / "main.py").write_text('from apkpy_lib.game import *\n\nfor x in y:\n    pass\n')
    text, out = read_with_apkpy(tmp_path / "bad")
    assert text == "None" and "APKPY G1" in out


def test_enable_game_in_python_gives_the_names(tmp_path):
    """It comes with `from apkpy_lib import *`: no other import."""
    project_with(tmp_path / "p", ENABLED)
    code = ('from apkpy_lib import *\nenable_game()\n'
            'print(all(callable(f) for f in (game_play, game_resume, game_get, game_set, game_last_result, game_suspended)))\n')
    path = tmp_path / "p" / "probe.py"
    path.write_text(code)
    r = subprocess.run([sys.executable, str(path)], cwd=str(tmp_path), capture_output=True, text=True,
                       env=dict(os.environ, APKPY_RELOAD="0"))
    assert r.returncode == 0 and "True" in r.stdout, r.stdout + r.stderr


def test_a_new_project_uses_enable_game(tmp_path):
    for template in ("menus", "blank"):
        folder = tmp_path / template
        r = new_game(folder, template, ID)
        assert r.returncode == 0, r.stdout + r.stderr
        text = (folder / "writehere.py").read_text()
        assert glue.status(text) == "enabled" and "apkpygame" not in text
        assert re.search(r"^enable_game\(\)$", text, re.M)
        assert compile_app(glue.expand(text))


def test_game_init_adds_a_game_and_mends_an_old_block(tmp_path):
    from conftest import apkpy
    project_with(tmp_path / "old", OLD)
    (tmp_path / "old" / "game" / "main.py").unlink()
    r = apkpy("game", "init", cwd=tmp_path / "old")
    assert r.returncode == 0, r.stdout + r.stderr
    assert glue.status((tmp_path / "old" / "writehere.py").read_text()) == "enabled"
    assert (tmp_path / "old" / "game" / "main.py").is_file()
