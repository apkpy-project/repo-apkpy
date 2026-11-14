"""What the line at the bottom of the Studio says: the game read, checked against the app and its scripts translated,
as the build does, on the saved files, in the background. It writes nothing: Play builds at the same time, in the
same build folder. One problem per line, as "file:line: what (code)".

    python -m apkpy_lib.game.studio.check        (in the project's folder)
"""
import sys


def problem_line(error):
    where = error.path or ""
    if where and error.line:
        where += ":%d" % error.line
    words = error.message.replace("\n", " ")
    return "%s%s (%s)" % (where + ": " if where else "", words, error.code)


def check(folder="."):
    """None, or the GameError the build would stop with."""
    from ..build import check_against_app
    from ..compiler import app as app_reader
    from ..compiler import reader, scripts
    from ..errors import GameError
    from ..project import Project
    project = Project(folder)
    try:
        model = reader.read(project.main, project.root)
        app = app_reader.read(project.writehere, project.rel(project.writehere))
        check_against_app(model, app, project)
        if any(m.scripts or m.functions or m.records or m.state or m.tables for m in model.modules):
            scripts.translate_program(model.modules)
    except GameError as e:
        return e
    return None


def main():
    error = check(".")
    if error is not None:
        print(problem_line(error))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
